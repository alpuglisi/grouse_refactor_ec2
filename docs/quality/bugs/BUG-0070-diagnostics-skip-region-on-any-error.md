# BUG-0070: `diagnose_training` and `diagnose_water_bias` skip a region on any error and report as if complete

> Filed from CR-0018 lint candidate **C6** (`docs/quality/change-requests/CR-0018-pa0027-lint.md` §4),
> 2026-09-30. Keys `('diagnose_training.py', 'main', 0)` and
> `('diagnose_water_bias.py', 'process_region', 0)`.

## 1. Description
Both diagnostics loop over regions and wrap a region's loading step in
`except Exception`, printing `str(e)` and skipping the region.
- `diagnose_training.main` then prints the summed train/val counts, the
  positive:negative ratios and "expected train samples in train.py" as
  if every requested region had been counted.
- `diagnose_water_bias.process_region` returns `None`, and `main`'s
  VERDICT silently leaves the region out.

Any exception did this, so a programming error (a `KeyError`, a
`TypeError`) looked like "files missing" and produced partial totals.
PA-0027 names this outcome: "skipping a unit of a batch (a region)".

## 2. Where encountered
- `diagnose_training.py:52` and `diagnose_water_bias.py:115` at
  `666474c`.
- Found by the CR-0018 lint review, 2026-09-30. The PA-0027 sweep
  (BUG-0049 §8) classed both "visible unknown".
- Never observed producing wrong totals.

## 3. What it caused to fail
`diagnose_training` is used to explain a training run (class balance,
expected sample counts). With one region skipped, the printed
"expected train samples in train.py" and the ratio, which drives the
"[!] Training imbalance is severe" advice, are computed over fewer
regions than `--regions` names, with nothing in the summary saying so.
A reader comparing them with `train.py`'s log sees a mismatch with no
explanation, or draws a class-balance conclusion from a subset.
`diagnose_water_bias` prints the skip in the region's section, but the
VERDICT reads as a complete list.

## 4. What the defect was
`diagnose_training.py:47-55` at `666474c`:
```python
    for region in args.regions:
        rd = data[region]
        try:
            tp, tn = len(rd.positives("train")), len(rd.negatives("train"))
            vp, vn = len(rd.positives("val")), len(rd.negatives("val"))
        except Exception as e:
            print(f"  {region}: FAILED to load files - {e}")
            continue
```
`diagnose_water_bias.py:113-117` at `666474c`:
```python
    try:
        nlcd_path = rd.latest_raster_path("nlcd")
    except Exception as e:
        print(f"  [!] No usable NLCD raster for {region} ({e}). Skipping.")
        return None
```

## 5. Root cause analysis (Five Whys)
1. *Why could totals be partial without notice?* A region's failure was
   turned into `continue` / `None`, and the code after the loop does not
   know a region is missing.
2. *Why `continue` for every error?* The expected condition (a region
   without split files, or without a valid NLCD raster, raised by
   `grouse_data` as `MissingDataError`) was caught by `Exception`, not
   by its own type.
3. *Why does the summary not say so?* No list of skipped regions was
   kept, so the summary could not report it.
4. *Why was it not caught?* The scripts predate PA-0027; the PA-0027
   sweep saw the printed line and classed the handlers as "visible
   unknown", although the rule lists a region skip as a forbidden
   continue branch.
5. *Why?* The same manual-sweep gap as BUG-0065/BUG-0069: the handler
   was judged by its own print, not by what the batch reports after it.

**Root cause:** a batch loop resolved every per-region error to a skip
via a broad handler, and the batch's summary did not record that a unit
was skipped.

## 6. Corrective action
Trivial fixes, one function each, no signature/CLI/schema change, no CR.
The only added import is the existing `grouse_data.MissingDataError`.
- `diagnose_training.main`: catch `MissingDataError` only (it subclasses
  `FileNotFoundError`; `GrouseData.path` raises it for an absent split
  file), print `SKIPPED` with type and message, record the region, and
  after the loop print
  `[!] INCOMPLETE: the totals below EXCLUDE skipped region(s) [...]`.
  Any other error propagates.
- `diagnose_water_bias.process_region`: catch `MissingDataError` only
  (what `latest_raster_path` raises for no raster / no valid raster),
  print type and message and that the region is absent from the
  VERDICT. Any other error propagates.
```python
        except MissingDataError as e:
            # BUG-0070 (PA-0027): only a missing split file is an
            # expected skip; it is printed and the totals below say
            # they exclude it. Any other error propagates.
            print(f"  {region}: SKIPPED, split files missing - "
                  f"{type(e).__name__}: {e}")
            skipped.append(region)
            continue
```
Both handlers are now narrow, so the lint no longer flags them; both
`EXPECTED_UNCLASSIFIED` entries were removed.

**Remaining (LOW, tracker):** `diagnose_water_bias.main`'s VERDICT loop
still omits a skipped region without a line of its own (the skip is
printed in the region's section and says it is absent from the
VERDICT). Adding a "skipped: [...]" line to the VERDICT is a change to a
second function; tracked, owner: next change to
`diagnose_water_bias.py`.

**Verified:** `tests/test_cr0018_candidates.py::Bug0070WaterBiasRegionSkip`
and `::Bug0070DiagnoseTrainingRegionSkip` (fake regions, no data):
a `MissingDataError` region is skipped with its type printed and, in
`diagnose_training`, the INCOMPLETE line names it; a complete run
prints no INCOMPLETE line; a `TypeError` propagates in both. The skip
and propagate tests fail on `666474c`.

Status: **FIXED** (`0355240`; VERDICT line: LOW follow-up in the tracker).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for region skips,
broad handlers, PA-0027.
- **BUG-0049** (`generate_negatives.process_region` skipped a region on
  any error) and **BUG-0055** (`diagnose_wetland` skipped a year
  silently): **same mechanism**, unit-of-a-batch skip via a broad
  handler. BUG-0055 is the diagnostic-script twin and was fixed the
  same way (`MissingDataError` only, skip printed). **Recurrence.**
- BUG-0052..0054, BUG-0063: the same family.

**Prior-preventive-action failure analysis (PA-0027).** The rule names
this exact case. It failed as **not followed in its sweep**
(misclassified "visible unknown" because a line was printed) and **not
enforced** (review only at the time). The BUG-0055 fix, in a sibling
diagnostic, was not propagated to these two scripts because the sweep
had put them in a different class. CR-0018's lint closes the
enumeration and classification step: an unclassified broad handler
fails the test, and each classification is a reviewed entry with a
reason citing the rule.

## 8. Preventive action
**No new PA.** PA-0027 is the rule and CR-0018's lint enforces the
classification. Sweep for the same mechanism (a broad handler whose
body ends in `continue`, or returns inside a per-unit function whose
caller loops): the lint's non-conforming list at the fix head, read for
unit-of-batch skips. The remaining ones are BUG-0013's (`KNOWN_OPEN`),
`acceptance_split`'s gate/stage loops (error recorded as FAIL), the
visible-unknown OBS/hash rows of BUG-0069 (not a batch whose summary
claims completeness), `dataset._close_handles` (cleanup) and
`download_tcc_nlcd.resolve_collection` (candidate fallback that prints
each skipped id with its type and aborts if none is readable). No
other instance. PA-0027 Swept? text for the lead:
`docs/quality/evidence/CR-0018-candidates-bookkeeping-rows.md`.
