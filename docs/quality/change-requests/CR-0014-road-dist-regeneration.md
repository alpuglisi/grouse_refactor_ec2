# CR-0014: Regenerate `road_dist` from every intersecting county at TIGER 2023, with nodata where Canadian roads could be nearer

**Status: PROPOSED (v1) — awaiting review.** Nothing implemented.
History and dispositions: `CR-0014-review-log.md`. This document states
only current intent.

**Split from CR-0008** (v7's `road_dist` ME/VT scope). Decisions by the
user, 2026-09-30: TIGER vintage **2023**; pixels where Canadian land is
closer than the nearest TIGER road become **nodata**.

**Order:** independent of CR-0010 and CR-0008 (different files). Must
land before CR-0012's acceptance run, or that run is repeated: I17 reads
`road_dist`. CR-0009 is gated on it.

## Scope
Regenerate all 30 `road_dist` rasters (ME, NH, VT × 10 year-copies) with
`generate_road_distance.py` fixed to use TIGER 2023, download atomically,
and write nodata wherever the true distance is unknown because a
Canadian road could be closer than any TIGER road.

## Why now
- **BUG-0023:** ME and VT `road_dist` were built from home-state roads
  only. At 400 Maine points the median error was 16,086 m; the ME
  state-line median is 367 m and the grid-edge median 11,699 m. NH was
  regenerated with the fix (`bf8d31a`); ME and VT never were.
- **BUG-0037 (new):** TIGER has no Canadian roads, so near the border the
  distance can read too far. Up to 978,374 ME / 109,251 NH / 281,662 VT
  in-coverage pixels are exposed (0.91 % / 0.21 % / 0.56 %; an upper
  bound measured on the current rasters), including about 19 positives.
- CR-0009's retrain needs correct inputs.

## The change

### 1. `generate_road_distance.py`
- **`TIGER_YEAR = 2023`** (`:114`, today `2025`). Every cached road file
  and the NH raster are 2023. CR-0007 centralises the constant into
  `regions.py`; whichever of CR-0007/CR-0014 lands second reconciles it.
- **Atomic `_download`** (`:124-130`). Today an interrupted download
  leaves a truncated zip that `if os.path.exists(path): return path`
  reuses forever. New: download to `path + ".part"`, verify with
  `zipfile.ZipFile(...).testzip() is None`, then `os.replace`; a cached
  zip that fails the same check is deleted and re-fetched.
- **Densified footprint** in `counties_for_grid` (`:143-152`): segmentize
  the grid bbox (e.g. 1 km) before `to_crs`, so a reprojected straight
  edge cannot bow inside a county and miss it.
- **Canada rule** in `build_distance_raster` (`:184`). With `T` = the
  TIGER county-union mask (`all_touched=True`, as today) and `D_road` the
  road distance:
  - `L` = pixels outside `T` that are land: the region's latest `evt`
    raster not in `NODATA_SENTINELS` and not `7292` (Open Water).
  - `D_can` = Euclidean distance transform to the nearest `L` pixel, same
    pixel sampling as `D_road`.
  - Write `-9999` where `T & (D_can < D_road)`, in addition to `~T`.
  - `L` covers the grid only; Canadian land beyond the grid edge is not
    seen (X2 reports the exposure).
- Write tag `GROUSE_COVERAGE=tiger-minus-canada`, so CR-0008's
  legacy-checkpoint refusal applies.
- Add `--out-dir` (default: the pipeline raster dir) for the rehearsal.

### 2. Data
Regenerate all three regions (NH too — the Canada rule changes it).
Fetch the 8 uncached VT-grid counties first (MA 25003, 25015; NY 36019,
36031, 36083, 36091, 36113, 36115).

## Acceptance gates
Implemented in `check_road_dist.py`, constants in
`docs/quality/cr0014_pins.json`. It must not import
`generate_road_distance.py`; it recomputes `T`, `L`, the Canada set and
the truth itself. All per region, full resolution.

| id | type | check | required |
|---|---|---|---|
| R0 | GATE | `T` re-derived (counties intersecting the grid bbox, `tl_2023_us_county.zip`, `all_touched=True`): inside count and `sha256(packbits)` | = pins (ME 107,441,621 / `22a9995e0b920e81c205a962e7e64237`; NH 51,386,748 / `1a29cc5bc79b7d4c73dc49e4fb9ac93a`; VT 50,450,367 / `52e5049c360a5143146ac1342d4177f8`) |
| R1 | GATE | `count(~T & raster != -9999)` | 0 |
| R2 | GATE | Canada set `C` recomputed by the verifier; `nodata ∩ T` equals `C` exactly (count and digest) | equal; `C`'s count and digest pinned before regeneration |
| R3 | GATE | All 10 year-copies in a region byte-identical | 1 distinct sha256 per region |
| RD1 | GATE | Per stratum, median \|err\| | ≤ 20 m |
| RD2 | GATE | Per stratum, p99 \|err\| | ≤ 60 m |
| RD3 | GATE | Per stratum, `count(|err| > 60 m)` | 0 |
| RD4 | GATE | Per stratum, median signed err | in [−20, +5] m |
| RD5 | GATE | Sample points inside `T \ C` whose raster is nodata (excluded points) | 0 |
| R6 | GATE | Profile and `tags(ns='IMAGE_STRUCTURE')` vs the pre-regeneration file | identical |
| R7 | GATE | `GROUSE_COVERAGE` tag present | every file |
| R8 | GATE | `count(data/cache/patches_*)` after purge | 0 |
| B0 | GATE | Backup of the 30 files hashes to the committed manifest | all match |
| X1 | OBS | `|C|` and positives/negatives with centre in `C` | report |
| X2 | OBS | Pixels in `T \ C` closer to the grid edge than to any road, on a Canada-facing edge | report |

**RD1–RD5 sampling and truth.** Truth = exact `shapely` STRtree distance
from the pixel centre to the nearest paved TIGER-2023 road (MTFCC
`S1100 S1200 S1400 S1630 S1640`, the generator's default), from **every
county intersecting grid + 10 km** — never the region's own state, which
would reproduce BUG-0023 inside the gate. 400 points per stratum, seed
pinned, drawn only from `T \ C`, five strata: uniform; interior (> 5 km
from coverage edge, other-state line and grid edge); within 5 km of a
land boundary with another US state; within 10 km of the grid edge;
within 5 km of the coverage boundary.

**Why these thresholds.** A median or p95 on a uniform sample passes
today's broken ME raster (uniform median 10.9 m); only the state-line
and grid-edge strata separate it (367 m and 11,699 m). 60 m is derived,
not fitted: the EDT can under-read by the road's in-pixel offset
(≤ 21.2 m) plus the sample point's offset (≤ 21.2 m) plus log1p encoding
(`0.5·(1+d)/1000` m; < 18 m below 35 km). Observed maximum over 2,000
correct NH points: 38.9 m. RD4's band reflects `all_touched=True`
widening each road (correct rasters read −7 to −9 m).

## Impact
- **`road_dist` values change** in ME and VT near state lines and grid
  edges (the BUG-0023 fix): on the current record set 140 of 3,860 ME and
  717 of 2,261 VT positives differ by > 60 m from the corrected value.
- **New nodata** in all regions where `C` applies; about 19 positives'
  centres (X1 reports the exact count). Models with validity channels
  read it as missing; legacy checkpoints are refused (R7 tag).
- **Patch cache** rebuilt (purged, R8).
- **CR-0012/CR-0013:** I17 reads `road_dist`; its acceptance run must
  follow this CR.
- **Not affected:** every other raster; records; model code.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Truth built from the wrong road set false-fails the fix | Truth spec pinned (vintage, MTFCC, counties ∩ grid+pad); verifier independent |
| Canada rule over-masks | R2 requires `nodata ∩ T` = the verifier's `C` exactly |
| Over-masking by any other route (e.g. `all_touched=False`) | R2 and RD5 |
| Truncated cached download | Atomic `_download` (U1, U2) |
| Year-copies diverge | R3 |
| Stale patches served | R8 purge |
| Regeneration loses the originals | Backup + manifest first (B0) |

## Test plan
**Here:** U1 (interrupted download leaves no file; next call re-fetches),
U2 (a truncated cached zip is detected and re-fetched), U3 (Canada rule on
a synthetic grid: a road 5 km away and Canadian land 2 km away → nodata;
land beyond the road → value), U4 (densified footprint selects a superset
of today's counties); a single-region rehearsal (VT) into scratch with
`--out-dir`, all gates; then the full run.

**Not here:** Canadian road data — the rule writes nodata rather than
estimating; adding Statistics Canada's road network is a separate change.

## Deliverables (in execution order)
- [ ] 1. `check_road_dist.py` and `docs/quality/cr0014_pins.json`; the
      verifier computes and commits `C`'s count and digest per region
      **before** regeneration; unit-tested on a synthetic fixture.
- [ ] 2. `generate_road_distance.py` changes (§1); U1–U4.
- [ ] 3. Fetch the 8 VT-grid county road files.
- [ ] 4. Manifest (sha256, mtime) and backup of the 30 `road_dist` files
      to `/home/ec2-user/grouse_backup/CR-0014/`.
- [ ] 5. VT rehearsal into scratch; all gates.
- [ ] 6. Regenerate ME, NH, VT in place; run `check_road_dist.py`; save
      to `docs/quality/evidence/CR-0014-gates.txt`.
- [ ] 7. Purge `data/cache/patches_*`; R8.
- [ ] 8. Bookkeeping: BUG-0037 (Canada over-read) with all §2 sections,
      recurrence review (PA-0017, which requires a margin for
      neighbourhood operations) and `BUG_LOG.md` row; close BUG-0023 with
      the §6 ruling below; PA-0017 Swept? cell.

**BUG-0023 §6.** `bf8d31a` (the NH-side fix) landed with no CR. This CR
is its retroactive review: it re-derives the diagnosis from the current
code, extends the fix to ME and VT, and is independently reviewed. It
cannot supply review *before* implementation, so §1.1's ordering
deviation for `bf8d31a` stays recorded and is not marked closed.

## Out of scope
- `diagnose_road_bias.py`'s home-state roads (BUG-0026).
- Canadian road data (Statistics Canada NRN).
- TIGER 2025.
- `predict.py`'s validity mask; the retrain (CR-0009).
