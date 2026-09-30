# BUG-0026: `diagnose_road_bias.py` measures distance to the home state's roads only

## 1. Description
Found by the PA-0017 sweep (BUG-0023). The diagnostic behind the
CHANGELOG's "positives sit 2–5× farther from roads than negatives" loads
primary/secondary roads for the region's own state only. Sighting and
background points near a state line are measured against home-state
roads only, overstating their distances.

## 2. Where encountered
`diagnose_road_bias.py:79-83`, `load_roads`.

## 3. What it caused to fail
Distances for near-border points are upper bounds, biasing the medians it
reports. That result was used as evidence in the road-hugging
investigation, and in BUG-0023 §3 to explain why falsely remote land
scores high. The direction of the effect on the positive/negative
comparison is unknown until it is re-run.

## 4. What the defect was
```python
def load_roads(region):
    ...
    fips = STATE_FIPS[region]
    fname = f"tl_{TIGER_YEAR}_{fips}_prisecroads.zip"
```

## 5. Root cause analysis
Same mechanism as BUG-0023: a per-state source used for a computation
whose inputs (points near borders) need neighbouring-state data. **Root
cause:** source coverage not matched to the extent of the computation.

## 6. Corrective action
None yet. Proposed: load PRISECROADS for every state intersecting the
region box plus a margin (ME, NH, VT, MA, NY cover all three regions),
then re-run and update the CHANGELOG figures. It's a single-function
change, so it's CR-exempt under `CLAUDE.md`'s trivial-fix rule.

Status: **OPEN**.

## 7. Recurrence review
Same mechanism as BUG-0023, found by its sweep. Not a recurrence.

## 8. Preventive action
Originally recorded as "Covered by PA-0017". **Corrected 2026-09-30:**
PA-0017 is worded for derived *rasters written onto a grid*, and this
bug is a point-distance computation with no raster. PA-0017 would not
clearly catch it in a new diagnostic. Hence:

**PA-0018** (new, extends PA-0017): any spatial computation (distances,
nearest-neighbour queries, buffers, thinning, block holdouts, sampling)
must draw its source data from everything intersecting its full extent
plus a margin, never from a per-state or per-region subset chosen by
label. Computations whose guarantee must hold across pooled data run
once over the pooled data, and records belong to exactly one region.

**Sweep under PA-0018 (§3.5)**, every per-region spatial computation on
`main`, from code:
- **BUG-0027** (new): overlapping region boxes plus a per-region block
  split → cross-region train/val leakage and duplicated records.
- This bug, BUG-0026.
- `generate_negatives.py` 300 m buffer: uses the region's box-clipped
  sightings, which already include neighbouring-state sightings inside
  the box. No new instance beyond the outer box edge.
- Per-region thinning: folded into BUG-0027.
