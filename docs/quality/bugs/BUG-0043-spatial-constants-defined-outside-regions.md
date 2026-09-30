# BUG-0043: Spatial and region-domain constants assigned as literals in many files outside `regions.py`

## 1. Description
`regions.py` (CR-0002, BUG-0001) held only `BOXES`. Every other
project-chosen spatial or region-domain constant (the region list, state
FIPS codes, the TIGER vintage, thinning spacing, block size, the negatives'
exclusion buffer) was assigned a literal in each file that used it, often
under a `_DEFAULT` alias or as a CLI default. Two copies of `TIGER_YEAR`
disagreed (2025 in the road-distance generator, 2023 in the road
diagnostic) until CR-0014 set 2023.

## 2. Where encountered
CR-0007 round-8 review (reviewers A and B, finding A1/B1) and CR-0007's P6
scanner (`check_partition.scan_repository`, rule (i): an assignment to a
§1 name, `BOXES` or its `_DEFAULT` alias whose value contains a literal).
At `f8fafbc`, outside the files CR-0007 exempts, rule (i) matched 13 lines:

- `check_exotic.py:31`, `diagnose_water_bias.py:58`, `dupe_check.py:27`,
  `tune.py:40`, `tune_bins.py:40`, `prepare_training_data.py:42` —
  `REGIONS_DEFAULT`
- `prepare_training_data.py:49,52` — `MIN_SPACING_M_DEFAULT`,
  `BLOCK_SIZE_M_DEFAULT`
- `generate_negatives.py:70,71` — `BUFFER_M`, `MIN_SPACING_M`
- `diagnose_road_bias.py:71,72` — `STATE_FIPS`, `TIGER_YEAR`
- `repair_coverage_rasters.py:53` — `REGIONS`

and, in files exempt until later deliverables, `generate_road_distance.py:116,122`
(`TIGER_YEAR`, `STATE_FIPS`; CR-0007 deliverable 7), `clean.py:47,50` and
`legacy/gen_negs.py:77-78` (stale copies; CR-0012 §6 guards).

## 3. What it caused to fail
- **Observed drift:** `generate_road_distance.py` carried `TIGER_YEAR = 2025`
  while `diagnose_road_bias.py` carried `2023`. The generator would have
  built `road_dist` from a different TIGER vintage than the one the
  diagnostic measured against. CR-0014 fixed the value in `05d788d`:
  ```
  -TIGER_YEAR = 2025
  +TIGER_YEAR = 2023
  ```
- **Latent:** thinning spacing and block size were defined in
  `prepare_training_data.py` and again in `generate_negatives.py` (which
  also imported `BLOCK_SIZE_M_DEFAULT` from the former). A change to one
  copy would have split positives and negatives on different grids
  without an error.

## 4. What the defect was
Verbatim, pre-CR-0007:

`diagnose_road_bias.py:70-72`
```python
DATA_DIR = "data/roads"
STATE_FIPS = {"ME": "23", "NH": "33", "VT": "50"}
TIGER_YEAR = 2023
```
`generate_negatives.py:70-71`
```python
BUFFER_M = 300                  # exclusion radius around every grouse location
MIN_SPACING_M = 30              # same candidate thinning as positives
```
`prepare_training_data.py:42,49,52`
```python
REGIONS_DEFAULT = ["ME", "NH", "VT"]
MIN_SPACING_M_DEFAULT = 30
BLOCK_SIZE_M_DEFAULT = 3000     # matches KDE_BANDWIDTH_M in analyze_grouse.py
```
`repair_coverage_rasters.py:53`
```python
REGIONS = ("ME", "NH", "VT")
```

## 5. Root cause analysis (Five Whys)
1. *Why did two `TIGER_YEAR` values exist?* Each road script defined its
   own.
2. *Why did each define its own?* The shared module held only `BOXES`, so
   there was nowhere to import the others from.
3. *Why only `BOXES`?* BUG-0001's fix (CR-0002) extracted the one constant
   that had been seen to drift. PA-0001's sweep was run for bounding boxes.
4. *Why was the sweep not broader?* PA-0001 names "bounding box, CRS,
   buffer distance" as examples. The sweep searched for the box values it
   had just fixed, not for every constant of that kind.
5. *Why did nothing catch later copies?* No check existed. A new script
   could assign `TIGER_YEAR = 2025` and nothing would notice.

**Root cause:** the rule against duplicating spatial constants was applied
to the one constant that had drifted, and had no mechanical check, so every
other constant of the same kind stayed a per-file literal.

## 6. Corrective action
CR-0007 deliverable 2 (§1):
- `regions.py` now defines `REGIONS`, `STATE_FIPS`, `STATE_NAMES`,
  `TIGER_YEAR`, `COUNTY_POLYGONS_YEAR`, `MIN_SPACING_M`, `BLOCK_SIZE_M`,
  `BUFFER_M` and `BOXES` (`regions.py:24-52`).
- Every rule-(i) line above re-pointed to import them (§1 re-point table),
  except `generate_road_distance.py`, which waits for CR-0007 deliverable 7
  (after CR-0016/CR-0014), and the stale copies `clean.py` and
  `legacy/gen_negs.py`, which CR-0012 §6 guards.
- Mechanical check: `tests/test_shared_constants.py` pins the values and
  scans the tree (P6).

The fix addresses the root cause: there is now one definition per constant
and a test that fails when a literal copy appears.

Status: **FIXED** — constants in `regions.py` (CR-0007 deliverable 2);
the road generator re-pointed by deliverable 7 (`fbd4e4c`); the
repository-tree P6 test passes (v9.1, `fab0795`).

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`:
- **BUG-0001 / PA-0001: same mechanism, and this is a recurrence.**
  BUG-0001 was the NH box duplicated across 7 files. This is the same
  mechanism for every other spatial constant.
- BUG-0020 / PA-0003 (path templates duplicated across 13 files): the
  same shape for paths. PA-0003 is the path counterpart; the county path
  is sweep item (c) below.

**Prior-preventive-action failure analysis (PA-0001).** PA-0001 was the
right rule, but it did not prevent this recurrence:
- **Too narrow in practice.** Its sweep ("found a 7th duplicate") covered
  `BOXES` only. It did not search for region lists, FIPS maps, vintages,
  spacing or buffer literals.
- **Not enforced-verifiable.** No test or scan existed, so every new
  script could add a copy. `TIGER_YEAR` drifted after PA-0001 was filed.
- **Aliases and CLI defaults not named.** `_DEFAULT` aliases and argparse
  defaults read as configuration, not constants, and the rule did not say
  they count.

## 8. Preventive action
**PA-0025** (extends PA-0001): "A project-chosen spatial or region-domain
constant is assigned a literal only in `regions.py` (a data path only in
`PATH_TEMPLATES`) and imported everywhere else, CLI defaults and
`_DEFAULT` aliases included; enforced by `tests/test_shared_constants.py`,
whose pins and names grow with each new such constant."

**Sweep (§3.5), by mechanism (any literal copy of a project-chosen
spatial/region-domain value, not only the named constants):**
- (a) region-code sequences and dicts (P6 rules ii–iii): **BUG-0044**,
  fixed by CR-0007 deliverable 2.
- (b) state name / eBird-code maps: **BUG-0045**, fixed by CR-0007
  deliverable 2.
- (c) the county-polygon path built twice: **BUG-0046**, partly fixed
  (§1 `PATH_TEMPLATES["tiger_county"]`); the rest is CR-0007 deliverable 7.
- (d) the analysis CRS `"EPSG:5070"`: **BUG-0047**, open and deferred.
  Owner: CR-0007's author, who opens a CR after CR-0012 lands.

**Mechanical enforcement:** `tests/test_shared_constants.py` (run with
`python -m unittest`; no CI in this repository).
