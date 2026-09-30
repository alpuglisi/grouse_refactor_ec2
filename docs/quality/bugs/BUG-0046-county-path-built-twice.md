# BUG-0046: The TIGER county-polygon path is built by hand in more than one place (PA-0025 sweep, item c)

## 1. Description
The national TIGER county file `data/roads/tl_{year}_us_county.zip` had no
`PATH_TEMPLATES` entry. `generate_road_distance.py` built the path from its
own `CACHE_DIR`, and CR-0007 needed a second reader (`regions.verify_partition`).
Without a template, that reader would have been a second hand-built copy.

## 2. Where encountered
PA-0025 §3.5 sweep, item (c) (PA-0025 covers data paths via
`PATH_TEMPLATES`; see also PA-0003). Sites:
- `generate_road_distance.py:173` (pre- and post-CR-0007 line number):
  ```python
      path = os.path.join(CACHE_DIR, f"tl_{tiger_year}_us_county.zip")
  ```
- `check_road_dist.py:132`: `name = f"tl_{y}_us_county.zip"` (CR-0014's
  verifier).
- New reader: `regions._state_polygons` (CR-0007).

## 3. What it caused to fail
Nothing observed: both copies resolve to the same file today. Latent: if
the cache directory or naming changed in one place, the membership
polygons and the road generator's county footprint could come from
different files or vintages.

## 4. What the defect was
`generate_road_distance.py:110,173`, verbatim:
```python
CACHE_DIR = "data/roads"
...
    path = os.path.join(CACHE_DIR, f"tl_{tiger_year}_us_county.zip")
```
and no `"tiger_county"` key in `grouse_data.PATH_TEMPLATES`.

## 5. Root cause analysis
Differential analysis against the paths that do use `PATH_TEMPLATES`
(`evaluated`, `negatives`, ...): the county file was introduced by the road
generator as a download cache, not as a pipeline artifact, so it was never
added to the template table. PA-0003 applies only where a template already
exists ("that should describe the same location as an existing
`PATH_TEMPLATES` entry"). A path with no template was outside it.

**Root cause:** a shared input path was introduced without a
`PATH_TEMPLATES` entry, and PA-0003 does not require one to be created.

## 6. Corrective action
- CR-0007 §1: `grouse_data.PATH_TEMPLATES["tiger_county"] =
  "data/roads/tl_{year}_us_county.zip"`. `regions._state_polygons` reads it
  (`regions.py`, `_state_polygons`). `check_partition.py` (independent
  checker) also reads it through the template.
- `generate_road_distance.py:173` re-points to the template in **CR-0007
  deliverable 7**, after CR-0016 and CR-0014 close. Not done yet.
- `check_road_dist.py:132` keeps its own name by design: it is CR-0014's
  verifier and resolves its inputs from its own pins (CR-0007 §1). This is
  justified, not a remediation.

Status: **FIXED** — `PATH_TEMPLATES["tiger_county"]` is read by
`regions.verify_partition` (CR-0007 §1) and by
`generate_road_distance.load_counties` (CR-0007 deliverable 7, `fbd4e4c`);
`check_road_dist.py` keeps its own pinned path (justified above).

## 7. Recurrence review
- **BUG-0020 / PA-0003** (path templates duplicated across 13 files): same
  family, for paths. This instance differs in having had no template at
  all. That is the gap PA-0025's clause "a data path only in
  `PATH_TEMPLATES`" closes.
- BUG-0005 (a glob re-hardcoded instead of derived): same family.

**Prior-preventive-action failure analysis (PA-0003).** PA-0003's scope was
too narrow: it binds paths to *existing* templates and says nothing when
none exists. PA-0025 extends it: a data path lives only in `PATH_TEMPLATES`.

## 8. Preventive action
Covered by **PA-0025** (its `PATH_TEMPLATES` clause). P6 pins the
`tiger_county` entry in `tests/test_shared_constants.py`. No new rule.
