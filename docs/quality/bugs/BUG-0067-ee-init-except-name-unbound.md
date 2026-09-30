# BUG-0067: `ee_init` reads an `except ... as` name after its clause, so the auth-failure message becomes `UnboundLocalError`

> Filed from CR-0018 lint candidate **C3** (`docs/quality/change-requests/CR-0018-pa0027-lint.md` §4),
> 2026-09-30. Keys `('download_tcc_nlcd.py', 'ee_init', 0)` and
> `('download_treemap.py', 'ee_init', 0)` (duplicate code, one BUG).

## 1. Description
`ee_init` tries Earth Engine's stored credentials, then Application
Default Credentials (ADC). The first failure was caught as
`except Exception as persistent_err: pass`, and the `SystemExit` raised
when ADC also fails interpolates `{persistent_err}`. In Python 3 the
name bound by `except ... as NAME` is deleted when the clause ends
(an implicit `del NAME`), so that interpolation raises
`UnboundLocalError`. The intended message, which names both errors and
the `gcloud` commands that fix a blocked OAuth client, is never shown.

## 2. Where encountered
- `download_tcc_nlcd.py:146-147` (handler) and `:162` (read) at
  `666474c`; `download_treemap.py:152-153` and `:168`.
- Found by the CR-0018 lint review (both reviewers), 2026-09-30. The
  PA-0027 sweep (BUG-0049 §8) described these as "fallback, then
  `SystemExit` naming every error", which was false.
- Not observed in a run (both auth paths have worked on this machine);
  confirmed by a repro, below.

## 3. What it caused to fail
When both auth paths fail, the script dies with
`UnboundLocalError: cannot access local variable 'persistent_err' ...`
(exit code 1, so it still fails closed). Lost: the stored-credentials
error text, the "Earth Engine init failed via both paths" summary and
the remediation instructions (`earthengine authenticate`, the `gcloud
auth application-default login` command for Workspace-blocked clients).
The ADC error survives only as the traceback's "During handling of the
above exception" context. That is exactly the situation the docstring
says users hit on Workspace-managed accounts.

Repro (`docs/quality/evidence/CR-0018-candidates/c3_repro.py`, same
shape, no network), Python 3.12.9:
```
raised : UnboundLocalError - cannot access local variable 'persistent_err' where it is not associated with a value
context: ValueError - path 2 failed
```

## 4. What the defect was
`download_tcc_nlcd.py:143-163` at `666474c` (`download_treemap.py:149-169`
is identical):
```python
    try:
        ee.Initialize(project=project) if project else ee.Initialize()
        return ee
    except Exception as persistent_err:
        pass
    try:
        import google.auth
        ...
        return ee
    except Exception as adc_err:
        raise SystemExit(
            f"Earth Engine init failed via both paths.\n"
            f"  earthengine's own credentials: {persistent_err}\n"
            f"  Application Default Credentials: {adc_err}\n"
```

## 5. Root cause analysis (differential analysis)
Compare the path that works with the path that fails:

| | first auth path succeeds | first fails, ADC succeeds | both fail |
|---|---|---|---|
| `persistent_err` read? | no | no | yes, at `:162` |
| outcome | returns `ee` | returns `ee` | `UnboundLocalError` |

1. The only path that reads `persistent_err` is the both-fail path, and
   it is the only one that breaks. The difference is the read of a name
   after its `except` clause ended.
2. Python 3 semantics (PEP 3110): `except E as N: body` is compiled as
   `try: body finally: del N`, to break the frame -> traceback -> frame
   reference cycle. So after the clause, `N` is unbound in the function.
   The repro confirms it on the interpreter used here.
3. Why was it written this way? The author treated the `as` name like an
   ordinary assignment that outlives the block (true in Python 2).
4. Why was it not caught? The both-fail path needs two credential
   failures on one machine, and no test or recorded run ever executed
   it. The PA-0027 sweep read the code and accepted the message as
   "naming every error" without running it.

**Root cause:** the abort message read a name bound by `except ... as`
outside its clause, where Python 3 has deleted it; and the abort path
had never been executed, so nothing showed that its message could not
be built.

## 6. Corrective action
Trivial fix (one function per file, no signature/CLI/schema change), no
CR. In both files the first handler keeps the error under another name,
and the message now also prints each error's type (PA-0027):
```python
    except Exception as e:
        # BUG-0067: the `as` name is deleted when the clause ends
        # (Python 3), so keep the error under a different name for the
        # SystemExit below; falls through to the ADC path.
        persistent_err = e
    ...
            f"  earthengine's own credentials: "
            f"{type(persistent_err).__name__}: {persistent_err}\n"
            f"  Application Default Credentials: "
            f"{type(adc_err).__name__}: {adc_err}\n"
```
The first handler still does not abort (it falls through to the second
auth path by design), so it is now an `ALLOWLIST` entry of class
`fallback` in `tests/test_pa0027_lint.py`, replacing the candidate entry.

**Verified:** `tests/test_cr0018_candidates.py::Bug0067EeInit` executes
the both-fail path with fake `ee` and `google.auth` modules (no network)
and checks the `SystemExit` names `RuntimeError: no stored creds` and
`ValueError: no ADC`, for both modules; it errors with
`UnboundLocalError` on `666474c`. The first-path success case is
unchanged.

Status: **FIXED** (`0355240`, branch `worktree-agent-a76c8932c8a2f4fc3`).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` (all rows) and `PREVENTIVE_ACTIONS.md` for
`UnboundLocalError`, `NameError`, "unbound", "except ... as", and for
defects in an error-reporting path that had never run.
- **Same mechanism (except-name lifetime): none found.** The only hit
  is PA-0027's Swept? cell, which records this candidate.
- **Related family:** BUG-0049 / PA-0027 and siblings BUG-0052..0055,
  BUG-0063 (broad handlers). This handler is a designed fallback, which
  PA-0027 allows; the defect here is not where the error goes but that
  the abort's message cannot be built. PA-0027's sweep did misdescribe
  it (§2), and that sweep failure is analysed in BUG-0065 §7 (manual
  sweep, not executed); CR-0018's lint is what surfaced it.
- **PA-0021 (a)** (an acceptance check is evidence only if it could have
  failed) is the nearest existing rule on executing a path, but it is
  about acceptance invariants, not error paths in scripts.

Not a recurrence of a prevented bug, so no prior-PA failure analysis is
owed for the new mechanism. A new PA is needed because no existing rule
names it.

## 8. Preventive action
**New PA-0031** (text for the lead in
`docs/quality/evidence/CR-0018-candidates-bookkeeping-rows.md`):
a name bound by `except ... as NAME` is never read outside that clause;
copy the exception to another name inside the clause if it is needed
later. An abort or fallback message that interpolates state captured by
earlier handlers is executed once by a test or recorded run.

**Enforcement:** the re-runnable AST sweep
`docs/quality/evidence/CR-0018-candidates/sweep_except_name.py` (flags
every read of an except-target name outside its clause in the same
scope). A lint test needs a CR (`CLAUDE.md` project notes); tracker item
added.

**Sweep (§3.5), by mechanism:** the script over `git ls-files '*.py'`
minus `inv_*`/`res_*`/`docs/` (72 files), output in
`sweep_except_name_output.txt`: at `666474c` exactly two hits, these two
`ee_init` reads; at the fix, 0 hits. Positive control: the repro
(`c3_repro.py`) is flagged; negative control: the fixed shape
(`err = e` inside the clause) is not. No other instance, so no further
BUG.
