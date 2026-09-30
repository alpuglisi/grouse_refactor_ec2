# BUG-0049: `generate_negatives.py` turned any error loading a region's pipeline inputs into "skip this region" (PA-0011 recurrence)

## 1. Description
Before CR-0012, `generate_negatives.py` processed one region at a time.
It read that region's evaluated sightings, envelope metrics, block
assignments and train/val positives inside one `try` block, with
`except Exception`. Any exception printed a one-line message and
returned from `process_region`. The loop then moved on to the next region
and the script exited 0.

So a missing input file and a programming error in the loaders were
handled the same way: both became a skipped region. The negatives files
that the skipped region had from any earlier run stayed on disk, and
`train.py` pooled them with the regions that had just been rebuilt.
Nothing marked them as stale.

## 2. Where encountered
- `generate_negatives.py:148-156` at `3230262`, the last commit before
  CR-0012's code (`20a52c1`, merged at `4eb10dd`). CR-0012 §3 cites it as
  `generate_negatives.py:153`, which is inside the `try` block.
- Found in review: CR-0007 v7 reviewer B, item B-18 (tracker
  `docs/quality/CR-0007-0008-OPEN-ISSUES.md`, § CR-0007). Assigned to
  CR-0012 deliverable 8.

## 3. What it caused to fail
- **Observed:** nothing. No known run took the skip path. The defect was
  found in review.
- **Possible outcome:** a run could finish with exit 0 and a "done"
  summary while one region's negatives were either missing or left over
  from an earlier run. Its selected negatives would then no longer match
  the rebuilt positives in that region. Two things would be wrong:
  - the 1:1 ratio;
  - the block split: the stale negatives' `split` came from the previous
    block assignment.
- **Masking:** a programming error in a loader, such as a `KeyError` in
  `GrouseData.positives`, looked exactly like "input not produced yet".
  No traceback was printed.

## 4. What the defect was
`git show 3230262:generate_negatives.py`, lines 148-156, verbatim:
```python
    try:
        evaluated = data[region].evaluated
        metrics = data[region].envelope_metrics
        blocks = data[region].block_assignments
        n_train_pos = len(data[region].positives("train"))
        n_val_pos = len(data[region].positives("val"))
    except Exception as e:
        print(f"  [!] Missing pipeline inputs for {region}: {e}. Skipping.")
        return
```
The caller at `3230262:generate_negatives.py:344-345` carried on:
```python
    for region in args.regions:
        process_region(region, data, evt_xwalk, args.seed)
```
The same function had a second skip path for the candidate file, at
`:141-144`:
```python
    if not os.path.exists(cand_path):
        print(f"  [!] {cand_path} not found - run gbif_negatives_download.py. Skipping.")
        return
```

## 5. Root cause analysis (Five Whys)
1. **Why could the script exit 0 with one region's negatives missing or
   stale?** The handler printed a message and returned. The loop treated
   that return the same way as a successful region.
2. **Why did the handler return instead of raising?** It used a broad
   `except Exception` to cover one expected case, "this region's inputs
   have not been produced yet". That case sits in the same branch as
   every unexpected error.
3. **Why was skipping thought to be safe?** The script was written for a
   per-region workflow. Each region's output files stood alone, so
   skipping a region seemed to leave the other regions valid.
4. **Why was that premise wrong?** The regions' outputs are consumed
   together. `train.py` pools every region, and a skipped region's old
   files are still on disk and get pooled with the new ones. After
   CR-0012 the computation itself is pooled (one buffer and one split
   over every region), so a skipped region makes the result wrong, not
   just incomplete.
5. **Why did no standing rule catch it?** The only rule on broad
   handlers, PA-0011 (from BUG-0013), covers "retry/polling loops". It
   asks only that the exception type and traceback be logged "before
   continuing". Its sweep searched retry and polling loops, so a
   load-and-skip handler in a pipeline script was outside both the rule
   and the sweep. Even inside that scope, a handler that logs and then
   continues would satisfy PA-0011.

**Root cause:** a broad handler resolved every error to the
"skip and continue" branch, which is the branch that reports success. The
standing rule on broad handlers (PA-0011) was scoped to the trigger that
first surfaced it (retry loops) and only asked for logging. It did not
address the mechanism: an unexpected error converted into normal
completion.

## 6. Corrective action
**CR-0012 §2–§3**, code `20a52c1`, merged at `4eb10dd`, with code-review
follow-ups at `df83c27`:
- The per-region pass is gone. `generate_negatives.run` is one pooled
  pass with no skip path.
- A missing input raises `MissingDataError` from the `GrouseData`
  accessors.
- `main()` (`generate_negatives.py:490-506`) lets `MissingDataError`
  propagate unchanged. Any other exception is printed with its type and
  traceback, then re-raised:
  ```python
      try:
          run(".")
      except MissingDataError:
          raise
      except Exception as e:
          print(f"[!] generate_negatives failed: {type(e).__name__}: {e}")
          traceback.print_exc()
          raise
  ```
- All outputs are built in memory before anything is written, and each
  file is replaced atomically (CR-0012 §2 Writes). A failed run leaves the
  previous files byte-identical.
- The standing checks (CR-0013, called from `train.py:250`) refuse
  training on any file whose digest differs from the acceptance record.
  So a stale region cannot be pooled silently.

**Verification:**
- `tests/test_cr0012.py::ExceptionsPropagate`:
  - `test_missing_data_propagates`;
  - `test_other_logged_and_reraised`.
  Both pass (re-run 2026-09-30).
- The real run in CR-0012 deliverable 6 completed with 18/18 CR-0013
  gates (`docs/quality/evidence/CR-0012-d6/acceptance.log`).

This addresses the root cause in this file: the error branch now raises
instead of resolving to success. The general mechanism is covered by
PA-0027 (§8) and its sweep.

Status: **FIXED** (CR-0012).

## 7. Recurrence review
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`, for exception
handling, `except Exception`, "skip", "swallow" and "masks".

**Match: BUG-0013 / PA-0011.** BUG-0013 is a broad `except Exception` in
download and polling loops that "masks real bugs as transient network
errors". That is the same mechanism: an unexpected error handled as an
expected outcome, followed by continuing. This bug is a recurrence of it.

**Other results:**
- BUG-0012 and BUG-0014 (dict keys) and BUG-0015 (validity check not
  backported) are different mechanisms.
- BUG-0036 (encoders turn NaN into 0) has a similar shape, a bad input
  turned into a legitimate value. It works on values, not exceptions,
  and PA-0006 covers it.

**Why PA-0011 did not prevent this recurrence:**
- **Too narrow.** PA-0011 names "retry/polling loops", the context in
  which BUG-0013 was first seen. The mechanism is not about loops: any
  broad handler whose error branch produces the success outcome can do
  this. `generate_negatives.py:154` is a load step, not a retry, so the
  rule did not apply to it.
- **Wrong remedy.** PA-0011 allows a broad catch if the type and
  traceback are logged "before continuing". Continuing is the defect. A
  handler that fully complies with PA-0011 can still skip a region and
  exit 0.
- **Sweep scoped by the trigger.** PA-0011's sweep (BUG-0013 §7) looked
  at retry and polling loops, and at other files only for
  narrow-exception counterexamples. It never listed load-and-skip
  handlers.
- **Not enforced.** BUG-0013 has been OPEN and deferred since 2026-09-22,
  and no lint or test checks for broad handlers (`CLAUDE.md`: no CI).

## 8. Preventive action
**PA-0027**, which supersedes PA-0011 (see `PREVENTIVE_ACTIONS.md`):
- it widens the scope from retry/polling loops to every broad handler;
- it replaces "log and continue" with "re-raise, or resolve to the
  fail-closed outcome and record the error visibly";
- a missing required input raises.

PA-0011's row stays in the table, marked "superseded by PA-0027".

**Mechanical enforcement:** not feasible in this pass, which is
documentation only. A lint test in the style of
`tests/test_nodata_zero_lint.py` would do it: flag every broad handler
that neither re-raises nor sits on an allow-list with a reason. That
test needs its own CR. It is listed in the tracker.

**Sweep (§3.5), 2026-09-30, scoped by mechanism:**
- Scope: every broad handler (`except Exception`, `except BaseException`,
  bare `except`, or a tuple containing one of them) in git-tracked `*.py`,
  minus `inv_*`, `res_*` and `docs/`. `tests/` had none.
- Each handler was read in context and classed by where its error branch
  goes:
  - **re-raise;**
  - **fail-closed:** refuse, invalid, FAIL or abort;
  - **visible "unknown":** a diagnostic or OBS row, or a printed reason;
  - **success/continue:** the defect.
- Findings:
  - BUG-0052: `download_rev.py:113-126`;
  - BUG-0053: `analyze_grouse.py:343-347`;
  - BUG-0054: `download_tcc_nlcd.py:257-267`;
  - BUG-0055: `diagnose_wetland.py:66-69`.
- Already owned by BUG-0013: `ebird.py:106`, `download_rev.py:218` and
  `:234`.
- The `legacy/` copies need nothing. Each starts with `raise SystemExit`
  (PA-0026), so none can run.
- Every other handler conforms. The full classification is in PA-0027's
  Swept? cell.
