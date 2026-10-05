# BUG-0096: `generate_time_since_disturbance` warps the LANDFIRE CONUS disturbance stack onto the rotated local-Albers template with GDAL's approximate transformer (BUG-0095 sweep instance)

**Status:** OPEN — code fixed with CR-0034 (deliverable 2); data repaired by
CR-0035 step 2.5. Found 2026-10-05 by the BUG-0095 sweep (CR-0034 round-3
review A34-3-1).

## 1. Description
`tsd` (a training channel) is built from the Annual Disturbance rasters on
the LANDFIRE CONUS grid, warped by nearest-neighbour onto each region's
LFPS local-Albers template - a rotated grid - with the default 0.125 px
approximate transformer.

## 2. Where encountered
`generate_time_since_disturbance.py:297` (`WarpedVRT(..., resampling=
Resampling.nearest)` with no `tolerance`); its own comment (`:285-290`)
states the grids differ.

## 3. What it caused to fail
The same mechanism as BUG-0095 (measured there: ~5-7 % of nearest picks on
a neighbouring pixel on a 60 km rotated grid for a random field). For
`tsd` a swap matters only where a disturbance boundary lies within
0.125 px of a cell centre; not measured separately.

## 4. What the defect was
```python
            vrts[d] = WarpedVRT(s, crs=ref_crs, transform=ref_transform,
                                width=width, height=height,
                                resampling=Resampling.nearest)
```

## 5. Root cause analysis
Same root cause as BUG-0095 (resampling accuracy taken from library
defaults, never measured on content); this is a sweep instance, not a new
cause.

## 6. Corrective action
`tolerance=WARP_TOLERANCE_PX` (realign_rasters, 1e-6 px), with the CR-0034
code; G11 pins it. `tsd` regenerated in CR-0035 step 2.5.

## 7. Recurrence review
Instance of BUG-0095 found by its §8 sweep (CLAUDE.md §3.5); no prior
`tsd`-specific bug. PA-0049(c) covers it.

## 8. Preventive action
PA-0049(c) (BUG-0095). No new rule.

## Cross-references
BUG-0095, CR-0034, CR-0035, PA-0049.
