# BUG-0037: `road_dist` over-reads near the Canadian border — TIGER has no Canadian roads

## 1. Description
`generate_road_distance.py` builds distance-to-nearest-paved-road from
TIGER/Line, which covers US counties only. Just south of the Canadian
border the nearest real road can be in Canada, so the TIGER distance is
too large — a plausible-looking but wrong reading, not missing data.

## 2. Where encountered
- `generate_road_distance.py` `build_distance_raster` (`:184` before
  CR-0014): distances computed from TIGER roads only; pixels outside US
  counties were set to nodata, pixels inside them never were.
- The generator's own docstring (`:74-78` before CR-0014) already said
  "distances just SOUTH of the Canadian border are still upper bounds".
- Found in CR-0008 round-7 review (R7-4).

## 3. What it caused to fail
In-coverage pixels whose nearest Canadian land is closer than the
nearest TIGER road — the necessary condition for an over-read:
ME 822,494 / NH 108,684 / VT 69,475 px (CR-0014's pinned set `C`, on
correct TIGER-2023 distances). Records whose centre lies in `C`:
positives ME 10 / NH 6 / VT 2, negatives ME 2 / NH 0 / VT 0 (X1,
`docs/quality/evidence/CR-0014-gates.txt`).

## 4. What the defect was
```python
    dist_m = distance_transform_edt(mask == 0, sampling=(res_y, res_x))
    ...
        dist_m = np.where(inside, dist_m, np.nan)
        encoded = np.where(inside, encoded,
                           ROAD_DIST_NODATA).astype(np.int16)
```
`inside` (the US county union) was the only coverage condition, although
the distance at a pixel depends on the whole neighbourhood out to the
nearest road — which, near the border, crosses into Canada.

## 5. Root cause analysis (Five Whys)
1. *Why too large near the border?* Only TIGER roads are loaded.
2. *Why is that wrong only near the border?* A distance transform is a
   neighbourhood operation: its value depends on data up to the nearest
   road, and there the neighbourhood leaves US coverage.
3. *Why wasn't that treated as uncovered?* Coverage was defined per
   pixel (is the pixel in a US county?), not per neighbourhood.
4. *Why per pixel?* PA-0017's fix for BUG-0023 wrote nodata outside the
   county union and added a pad for neighbouring *states*; the national
   border was known ("upper bounds") but noted rather than handled.
5. *Why noted and not handled?* Neither PA-0017's nor PA-0018's sweep
   read "margin for neighbourhood operations" as applying at a national
   border.

**Root cause:** a neighbourhood computation (distance transform) was
treated as covered wherever its centre pixel was covered, although its
source data ends at a national border inside the neighbourhood.

## 6. Corrective action
CR-0014: pixels in US coverage whose nearest Canadian land (LANDFIRE evt
2024, not a sentinel, not Open Water) is closer than the nearest TIGER
road are written as nodata. Verified by `check_road_dist.py` R2 — the
nodata set inside coverage equals the independently computed, pinned
`C` exactly, reproduced by two reviewers' own implementations. Evidence:
`docs/quality/evidence/CR-0014-gates.txt`.

**Residual (open):** Canadian land beyond the grid edge is not seen.
Review measured NH 6,884 px and VT 1,881 px at the top edges (ME 0);
`check_road_dist.py` X2 reports a looser upper bound (pixels nearer any
edge within 20 km of Canadian land than any road): ME 8,522 / NH 24,841 /
VT 17,804. Closes only with Canadian
road data (Statistics Canada NRN).

Status: **FIXED within the grid (CR-0014); edge residual OPEN.**

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`:
- **BUG-0023** (`road_dist` from home-state roads only) and **PA-0017**
  ("computed from source data covering the whole grid, plus a margin for
  neighbourhood operations"): same mechanism at a different boundary.
- **PA-0018** (any spatial computation's source must be everything that
  intersects its extent): same mechanism generalised.
- This is a **recurrence**.

**Prior-preventive-action failure analysis.** PA-0017 and PA-0018 both
cover this case in their wording. They failed in application: every
sweep read them as "use neighbouring **US states'** data" — the source
(TIGER) was treated as complete because it had no gaps *within its own
domain*. The generator's docstring shows the border was known; nothing
turned a known limitation into nodata. Wrong layer of attention, not a
too-narrow rule.

## 8. Preventive action
**PA-0023** (extends PA-0018): a neighbourhood computation whose source
data ends at a national (or any data-domain) border inside the
neighbourhood must either use cross-border data or write nodata where
the neighbourhood crosses that border; a documented "upper bound" is not
a substitute.

**Sweep (§3.5)** — neighbourhood computations near the Canadian border:
- `road_dist` generator: fixed (CR-0014).
- Negatives' 300 m exclusion buffer against sightings: sightings include
  Canadian records where the sources do (eBird/GBIF), and the buffer
  queries pooled sightings — to be confirmed in CR-0012's buffer gate
  (E7). Tracked.
- Positive thinning and spatial block holdouts: operate on records, not a
  foreign-data neighbourhood — not affected.
- KDE density in `analyze_grouse.py`: records near the border have
  Canadian neighbours only if Canadian sightings are loaded — tracked
  with the buffer item.
- `diagnose_road_bias.py`: same TIGER-only roads — covered by BUG-0026.
