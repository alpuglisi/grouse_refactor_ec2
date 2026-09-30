# BUG-0068: `acceptance_split.git_commit` failure is recorded in the manifest as a clean tree

> Filed from CR-0018 lint candidate **C4** (`docs/quality/change-requests/CR-0018-pa0027-lint.md` §4),
> 2026-09-30. Key `('acceptance_split.py', 'git_commit', 0)`, now in the
> lint's `KNOWN_OPEN` under this BUG.

## 1. Description
`git_commit()` returns `(commit, dirty)` for the CR-0013 records. Any
exception (git missing, timeout, not a repository) was caught by
`except Exception` and returned `(None, None)`: unknown. `full_run`
prints the `None` and `write_record` stores it as `null`, both visible.
But `build_manifest` writes `"dirty": bool(dirty)`, and `bool(None)` is
`False`, so the per-section manifests record an unknown working-tree
state as **clean**. The exception type is recorded nowhere.

A second path reaches the same result without an exception: if
`git status --porcelain` exits non-zero (e.g. not a repository), its
empty stdout gives `dirty = False` directly, since the return code is
not checked.

## 2. Where encountered
- `acceptance_split.py:152` (handler) at `666474c`; consumers
  `build_manifest` (`:1165`, `:1185`), `write_record` (`:2500`, `:2513`),
  `full_run` (`:2594`, `:2598`).
- Found by the CR-0018 lint review, 2026-09-30. The PA-0027 sweep
  (BUG-0049 §8) classed it "visible unknown (commit printed as `None`)",
  looking at the handler and the printed report but not at
  `build_manifest`.
- Never observed: every recorded acceptance run had a working `git`.

## 3. What it caused to fail
The manifests (`build_manifest` sections, written with the CR-0012/0013
outputs) are provenance records. With `git` unavailable, a run from a
modified working tree would be recorded as `"dirty": false` with
`"commit": null`. A reader checking "was this built from committed
code?" gets a wrong "yes" for the dirty field. No gate reads the field,
so no verdict changes.

## 4. What the defect was
`acceptance_split.py:141-153` at `666474c`:
```python
def git_commit():
    try:
        c = subprocess.run(["git", "-C", REPO_ROOT, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=30)
        commit = c.stdout.strip() or None
        s = subprocess.run(["git", "-C", REPO_ROOT, "status", "--porcelain"],
                           capture_output=True, text=True, timeout=60)
        dirty = any(line[:2].strip() and not line.startswith("??")
                    and line.rstrip().endswith(".py")
                    for line in s.stdout.splitlines())
        return commit, dirty
    except Exception:
        return None, None
```
and `acceptance_split.py:1184-1185`:
```python
                 "commit": commit,
                 "dirty": bool(dirty)}
```

## 5. Root cause analysis (fault tree)
Top event: a manifest says `"dirty": false` for a tree whose state is
unknown. Two OR-branches:
- **A. exception branch.** A1 `git` raises (not installed, timeout) AND
  A2 the handler returns `None` for "unknown" AND A3 `build_manifest`
  coerces with `bool()`, mapping unknown onto one of the two known
  values.
- **B. no-exception branch.** B1 `git status` fails with a non-zero
  return code AND B2 the return code is not checked, so empty stdout
  reads as "no modified files".

Common cause of A3 and B2: the tri-state (clean / dirty / unknown) is
collapsed to a boolean at a boundary — in the consumer (`bool(dirty)`)
or in the producer (empty stdout = clean). A2 by itself is PA-0027's
visible-unknown case and would be fine if every consumer kept it.

**Root cause:** the handler's fail-closed value ("unknown") was
converted to a success value ("clean") by a consumer in another
function, and the producer itself did not treat a failed `git status` as
unknown.

## 6. Corrective action
**Pending.** `acceptance_split.py` is being modified by CR-0017 on
another branch; this BUG does not touch it. Owner: after CR-0017 merges
(the CR-0013 author on the fix). A fix confined to `git_commit` is not
enough while `build_manifest` coerces with `bool()`, so the proposal is
two small edits:
1. `git_commit`: check both return codes; on a non-zero code or an
   exception, return `commit=None` and `dirty=None` and print (or return
   for recording) the reason with its exception type.
2. `build_manifest`: write `"dirty": dirty` (keep `None` as JSON `null`),
   matching `write_record`.

Two functions, and (2) changes the manifest schema's value domain
(`null` becomes possible), so it needs a CR or must ride in the next CR
that edits `acceptance_split.py`; check whether any gate or test
(`tests/test_acceptance_split.py`) reads the manifest's `dirty` field
before changing it.

The lint entry moved from `EXPECTED_UNCLASSIFIED` (candidate C4) to
`KNOWN_OPEN` under BUG-0068, same digest.

Status: **OPEN** (fix pending; owner: after CR-0017 merges).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for broad handlers,
PA-0027, "unknown" collapsed to a boolean, `bool(` coercions, and
provenance/manifest defects.
- **BUG-0049 / PA-0027**, and BUG-0052 (a probe returning `None` that the
  caller read as "passed") — **same mechanism**: an error value read by a
  caller as success. BUG-0052 is the closest sibling; here the reading
  is a `bool()` coercion. **Recurrence.**
- **BUG-0071** (this batch): same caller-side shape (a probe's `False`
  read by the caller as "absent").

**Prior-preventive-action failure analysis (PA-0027).** PA-0027's text
forbids this ("returning a value the caller reads as 'check passed'").
It failed as **not enforced where the defect is**: the sweep classified
the handler by its own body and its printed report, and did not follow
the value into `build_manifest`. CR-0018's lint pins the handler's own
function by digest, and CR-0018 §5 records explicitly that "whether a
caller in another function treats a handler's fail-closed value
correctly" is not detected (review only). So the lint surfaced this
handler for review, but it cannot close this class. The open tracker
item "MEDIUM (A-r2, R-A5a): lint limits in CR-0018 §5 ... caller-side
handling ... decide whether to extend PA-0027's text and the lint"
already owns that decision.

## 8. Preventive action
**No new PA now.** The residual gap (caller-side handling of a
fail-closed value) is already an owned decision in the tracker (CR-0018
review follow-up A-r2/R-A5a, owner lead). This BUG and BUG-0071 are
added there as its two concrete instances, so the decision is taken with
evidence. If the lead extends PA-0027 (for example "an allowlist
classification traces the handler's return value into every caller;
unknown is never coerced to a known value"), it should cite BUG-0068 and
BUG-0071.

Sweep for `bool(...)` coercion of a possibly-`None` handler result:
`grep -n "bool("` over every file holding one of the lint's 31
non-conforming handlers at the fix head. The hits other than
`acceptance_split.py:1185` coerce constructor flags or array tests
(`dataset.py:73,74,429`, `symptom_check.py:157,241,1099`), none a
handler's result. This is the only instance.
