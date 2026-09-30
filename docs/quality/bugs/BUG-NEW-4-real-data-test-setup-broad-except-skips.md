# BUG-NEW-4: The CR-0015 real-data test setup turns any error into a skip

> Placeholder id: the lead allocates the real id and renames this file.
> Found in the CR-0015 implementation code review: reviewer A finding
> A-3, reviewer B finding B-2 (MEDIUM, PA-0027 violation), at `3add80b`.

## 1. Description
`tests/test_cr0015_real.py` builds its real-data fixtures in `_setup`
(the V1–V3 checker, `GrouseData`, the features and the block
assignments). Any exception from that step was caught by
`except Exception`. Without `GROUSE_REQUIRE_REAL_DATA=1`, the exception
became `unittest.SkipTest`. So a programming error made every real-data
test skip rather than fail. Examples: a `TypeError` from
`train.discover_features`, a `KeyError` in `PATH_TEMPLATES`, or an
`AttributeError` after renaming `data.block_assignments`. A skip is also
what a machine with no data root designedly reports.

## 2. Where encountered
- `tests/test_cr0015_real.py:40-46` at `3add80b`, in `_setup`.
- Found by independent code review of the CR-0015 implementation
  (reviewer A finding A-3, reviewer B finding B-2), 2026-09-30.
- It was never observed hiding a real error.

## 3. What it caused to fail
The default full suite (`python -m unittest discover`, no data root)
reports `OK (skipped=6)` in both of these cases:
- there is no real data here, which is the designed skip;
- the real-data harness or the code it calls is broken.

The two cannot be told apart from the summary. The skip message did
carry the exception type, but nobody reads skip reasons in an OK run.

The deliverable-7 evidence runs are **not** affected. They use
`GROUSE_REQUIRE_REAL_DATA=1`, which turns the same exception into a
failure. Their 6/6 OK with no skips stands, and reviewer B reproduced it
digit for digit.

## 4. What the defect was
`tests/test_cr0015_real.py`, `_setup`, at `3add80b`:
```python
    try:
        chk = C.Checker()
        data, feats, assign = C.real_inputs()
    except Exception as e:                 # missing file or package
        msg = f"real data unavailable from cwd {os.getcwd()}: {type(e).__name__}: {e}"
        _STATE["err"] = (case.failureException(msg) if REQUIRE
                         else unittest.SkipTest(msg))
        raise _STATE["err"]
```

## 5. Root cause analysis (Five Whys)
1. *Why did a programming error become a skip?* The handler caught
   every exception and resolved it to the skip branch, a designed
   non-error outcome.
2. *Why every exception?* The expected conditions were a missing file
   (the county zip or `block_assignments.csv`) or a missing package. They
   were written as one broad handler with a comment, not caught by their
   own types.
3. *Why was a broad handler written?* The implementer did not have
   PA-0027 in view. The CR-0015 branch was cut from `00c0b6f`, where
   `PREVENTIVE_ACTIONS.md` ends at PA-0026. PA-0027 was filed later on
   the integration branch (CR-0012 deliverable 8, from BUG-0049). The
   implementer consulted the branch's copy of the rule list, as
   `CLAUDE.md` §3.2 requires, and that copy did not contain the rule.
4. *Why did no mechanical check catch it?* PA-0027's enforcement is
   "review only until a lint test exists". CR-0018, which adds
   `tests/test_pa0027_lint.py`, was still a draft. Only this code review
   caught it.
5. *Why did PA-0027's sweep not cover it?* That sweep was a snapshot of
   the tracked tree on 2026-09-30 ("`tests/` has none"). Code written
   later on a parallel branch was outside it by construction.

**Root cause:** a broad handler resolved every error to a designed
non-error outcome (a skip) instead of catching only the expected types.
The rule that forbids this, PA-0027, was not visible on the branch the
code was written on, and it had no mechanical enforcement.

## 6. Corrective action
A trivial fix, confined to one function, with no API change, so no CR
(`CLAUDE.md` project notes). It was delivered in the CR-0015
review-follow-up commit, which is recorded in the review log.
```python
    from grouse_data import MissingDataError
    # PA-0027: only the expected "no real data here" conditions are caught
    # (a missing file or package); any other error propagates and fails.
    try:
        chk = C.Checker()
        data, feats, assign = C.real_inputs()
    except (FileNotFoundError, ImportError, MissingDataError) as e:
```
**Verified:**
- With no data root, the tests skip with
  `FileNotFoundError: data/roads/tl_2023_us_county.zip`, the designed
  skip.
- With a real data root and `train.discover_features` patched to raise
  `TypeError`, V1 reports `errors 1, skipped 0`.

This fixes the root cause in this function: an unexpected error now
fails. Keeping the rule visible and enforced across branches is covered
in §8.

Status: **FIXED**.

## 7. Recurrence review (`CLAUDE.md` §4)
I searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` on the integration
branch (`claude/quality-records-cr0006-0009`) for broad handlers,
PA-0011 and PA-0027.
- **BUG-0049 / PA-0027** is the same mechanism: a broad handler
  resolving to a success or designed non-error branch. There, a region
  was skipped in `generate_negatives.py`. Here, a test is skipped.
  **This is a recurrence.**
- **BUG-0013 / PA-0011** (superseded by PA-0027), and BUG-0052..0055
  (PA-0027's sweep findings): the same family.

**Prior-preventive-action failure analysis (PA-0027).** The category is
**not followed, because it was not visible, and not enforced**.
- *Not visible:* PA-0027 was filed on the integration branch after this
  branch was cut. The rule list a change is checked against is the
  branch's own copy. So a rule filed while a long-lived branch is open
  does not reach that branch's work until it merges. The rule's wording
  was not the problem: it names exactly this case ("a designed
  non-error case").
- *Not enforced:* the rule states "review only until a lint test
  exists". CR-0018 (the PA-0027 lint, `tests/test_pa0027_lint.py`,
  DRAFT) would have flagged this handler mechanically on any branch that
  carried the lint.
- *Sweep snapshot:* the sweep recorded "`tests/` has none" at filing
  time. That was true then, and is now stale.

## 8. Preventive action
**No new PA; PA-0027 is strengthened by its planned enforcement.**
- CR-0018's lint is the PA-0027 enforcement. Its scope should include
  `tests/` (this instance is in `tests/`), and it must run on every
  branch before merge.
- For the visibility gap, a proposal for the lead: before an
  implementer's branch merges, re-check its diff against the
  integration branch's **current** `PREVENTIVE_ACTIONS.md`, not the
  branch's copy. This is a tracker item rather than a PA, because the
  lint closes this instance mechanically.

**PA-0027 Swept? update:** add this instance (`tests/` now had one,
fixed). The text is in `docs/quality/evidence/CR-0015-bookkeeping-rows.md`.

**Sweep of this branch's other new handlers (§3.5):**
- `pretrain.py:166-174`: `except Exception` → `SystemExit` naming the
  error. Fail-closed, compliant (reviewer B).
- `tests/test_cr0015_sampler.py`: `except SystemExit`, narrow. A
  shortfall is counted as a U2 violation, which fails closed.
- `tests/cr0015_background_check.py` and
  `tests/cr0015_wrong_samplers.py`: no broad handlers.

No other instance.
