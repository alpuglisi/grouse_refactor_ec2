# BUG-0044: The region list `["ME", "NH", "VT"]` written inline as CLI defaults and loop literals (PA-0025 sweep, item a)

## 1. Description
Beyond the named constants of BUG-0043, the region list itself was written
inline as an argparse default or loop tuple in seven more places, so a
fourth region (or a dropped one) would have had to be edited in each.

## 2. Where encountered
PA-0025 §3.5 sweep, item (a); CR-0007 P6 scanner rule (ii) (a list, tuple
or set of string literals equal to `REGIONS`, case-folded). At `f8fafbc`:
`bench_pipeline.py:66`, `calibrate.py:310`, `diagnose_training.py:35`,
`diagnose_wetland.py:138`, `pretrain.py:118`, `train.py:394`,
`download_tcc_nlcd.py:460` (argparse defaults) and `check_raster.py:71`
(loop tuple). The six `REGIONS_DEFAULT` lines also match rule (ii); they
are counted in BUG-0043.

## 3. What it caused to fail
Nothing observed: all copies agreed. Latent: changing the region set in
`regions.py` would have left these defaults on the old set, so training,
calibration and pretraining would have used different region sets by
default.

## 4. What the defect was
`train.py:394` (and identically in the other six entry points):
```python
    parser.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"])
```
`check_raster.py:71`:
```python
                  for region in ("ME", "NH", "VT")
```

## 5. Root cause analysis
Same root cause as BUG-0043 (differential analysis: these lines differ from
BUG-0043's only in being values without a constant name). With no shared
`REGIONS`, each entry point wrote the list where it needed it. PA-0001's
sweep searched for named box constants, so unnamed values were not in
scope.

**Root cause:** no shared region list existed, and the only rule was scoped
to named geographic constants.

## 6. Corrective action
CR-0007 deliverable 2: each line now uses `default=list(REGIONS)` /
`for region in REGIONS`, importing `regions.REGIONS` (§1 re-point table).
Verified by the P6 scan: none of these lines is reported
(`docs/quality/evidence/CR-0007-gates.txt`).

Status: **FIXED** (CR-0007 deliverable 2).

## 7. Recurrence review
Swept under PA-0025 (BUG-0043), whose recurrence review against
BUG-0001/PA-0001 applies. No other prior instance.

## 8. Preventive action
Covered by **PA-0025**. P6 rule (ii) enforces it in
`tests/test_shared_constants.py`. No new rule.
