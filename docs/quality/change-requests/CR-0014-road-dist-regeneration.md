# CR-0014: Regenerate `road_dist` from every intersecting county at TIGER 2023, with nodata where Canadian roads could be nearer

**Status: IMPLEMENTED (v3), 2026-09-30 — all deliverables complete; 153 gate rows, 0 failures (`docs/quality/evidence/CR-0014-gates.txt`). RD1/RD4 later demoted to OBS by CR-0016.**
History and dispositions: `CR-0014-review-log.md`. This document states
only current intent.

**Split from CR-0008** (v7's `road_dist` ME/VT scope). Decisions by the
user, 2026-09-30: TIGER vintage **2023**; pixels where Canadian land is
closer than the nearest TIGER road become **nodata**.

**Order:** independent of CR-0010 and CR-0008 (different files). Must land
before CR-0012's acceptance run, or that run is repeated: CR-0007's I17
reads `road_dist`. CR-0009 is gated on it.

**One CR, not several (§1.1):** the regeneration is a re-run of the fixed
generator, and the Canada rule can only be exercised by regenerating, so
the generator fix, the data change and their acceptance cannot land
separately.

## Scope
Regenerate all 30 `road_dist` rasters (ME, NH, VT × 10 year-copies) with
`generate_road_distance.py` fixed to use TIGER 2023, download atomically,
and write nodata wherever Canadian land within the grid is closer than
any TIGER road.

## Why now
- **BUG-0023:** ME and VT `road_dist` were built from home-state roads
  only (Maine median error 16,086 m at 400 points; ME state-line median
  367 m, grid-edge median 11,699 m). NH was regenerated with the fix
  (`bf8d31a`); ME and VT never were.
- **BUG-0037 (new):** TIGER has no Canadian roads, so near the border the
  distance can read too far. On today's rasters the exposed set is
  ME 978,374 / NH 109,251 / VT 281,662 in-coverage pixels (0.91 % /
  0.21 % / 0.56 %), about 19 positives' centres. The ME and VT figures
  are upper bounds (their current distances are too large).
- CR-0009's retrain needs correct inputs.

## The change

### 1. `generate_road_distance.py`
- **`TIGER_YEAR = 2023`** (`:114`, today `2025`). Every cached road file
  and the NH raster are 2023. CR-0007 centralises the constant into
  `regions.py`; whichever lands second reconciles it.
- **Atomic `_download`** (`:124-130`). Today an interrupted download
  leaves a truncated zip that `if os.path.exists(path): return path`
  reuses forever. New: download to `path + ".part"`; validate by opening
  with `zipfile.ZipFile` and requiring `testzip() is None` — a
  `BadZipFile` (how a truncated zip fails) counts as invalid; on invalid,
  delete the `.part` and raise; on valid, `os.replace`. A cached zip that
  fails the same check is deleted and re-fetched.
- **Densified footprint** in `counties_for_grid` (`:143-152`): segmentize
  the grid bbox (1 km) before `to_crs`. It changes no county selection
  today (ME 22/23, NH 27/31, VT 32/34 on grid/padded boxes, identical
  either way); it removes the dependence on the edges staying straight.
  `pad_px` is derived from the x resolution only, which is safe because
  every grid is 30 × 30 m.
- **Canada rule**, the recipe (the verifier uses the same one — R2):
  - `D_road`: float64 metres **before encoding**, from the Euclidean
    distance transform on the grid padded by `pad_px = round(10000 / 30)
    = 333` px, roads rasterised `all_touched=True`, roads from every county
    intersecting grid + 10 km, MTFCC `S1100 S1200 S1400 S1630 S1640`,
    sampling `(30, 30)`; cropped to the grid.
  - `T`: the county-union mask on the grid, `all_touched=True` (as today).
  - `L`: pixels outside `T` whose `{R}_2024_evt.tif` value is not in
    `NODATA_SENTINELS` and is not `7292` (Open Water). The evt file is
    pinned by sha256, not "latest".
  - `D_can`: float64 Euclidean distance transform to the nearest `L`
    pixel on the grid, sampling `(30, 30)`; `+inf` everywhere if `L` is
    empty (scipy's EDT of an all-foreground array is finite, which would
    silently mask pixels near the corner).
  - `C = T & (D_can < D_road)` (strict). Write `-9999` on `~T | C`,
    after `road_dist_encode` (which refuses NaN).
  - `L` covers the grid only. Canadian land beyond the grid edge is not
    seen: a stated residual, measured in review at NH 6,884 px and VT
    1,881 px (top edges, ME 0), reported by X2 and recorded in BUG-0037
    as open until Canadian road data exists.
- Tag `GROUSE_COVERAGE=tiger-minus-canada`, so the legacy-checkpoint
  refusal (`grouse_data.COVERAGE_TAGS`) applies. Its message is
  generalised from "repaired by CR-0010" to "carries nodata outside
  coverage".
- Add `--out-dir` (default: the pipeline raster dir) for the rehearsal;
  output years still come from the pipeline raster dir.

### 2. Data
After approval: fetch the 8 uncached VT-grid county road files into
`data/roads` (MA 25003, 25015; NY 36019, 36031, 36083, 36091, 36113,
36115 — six of them intersect the VT grid itself), then regenerate all
three regions (NH too — the Canada rule changes it).

## Acceptance gates
`check_road_dist.py`, constants in `docs/quality/cr0014_pins.json`, both
committed and reviewed **before approval** (§1.1). The verifier does not
import `generate_road_distance.py`, and keeps its **own** copy of the
TIGER files in `~/.cache/grouse_cr0014/` (downloaded before approval,
never written to `data/`). It takes `--root` (raster dir) for the
rehearsal. Digests are the first 32 hex digits of `sha256(np.packbits(mask))`.

| id | type | check | required |
|---|---|---|---|
| R0 | GATE | `T` inside count and digest | = pins (ME 107,441,621 / `22a9995e0b920e81c205a962e7e64237`; NH 51,386,748 / `1a29cc5bc79b7d4c73dc49e4fb9ac93a`; VT 50,450,367 / `52e5049c360a5143146ac1342d4177f8`) |
| R0b | GATE | Every county road zip the generator used is byte-identical to the verifier's copy | all equal |
| R1 | GATE | `count(~T & raster != -9999)` | 0 |
| R2 | GATE | `nodata ∩ T` equals `C` (count and digest) | = pins, computed by the verifier from its own TIGER copy with the recipe above — never from the current rasters |
| R3 | GATE | All 10 year-copies in a region byte-identical | 1 distinct sha256 per region |
| RD1–RD5 | GATE | Distance accuracy on sampled points (below) | per stratum |
| R6 | GATE | Profile and `tags(ns='IMAGE_STRUCTURE')` vs the pre-regeneration file | identical |
| R7 | GATE | `GROUSE_COVERAGE` tag present | every file |
| R8 | GATE | `count(data/cache/patches_*)` after purge | 0 |
| B0 | GATE | Backup of the 30 files hashes to the committed manifest | all match |
| X1 | OBS | `|C|`; positives and negatives with centre in `C` | report |
| X2 | OBS | Pixels in `T \ C` closer to a Canada-adjacent grid edge (edge pixels within 20 km of `L`) than to any road — the unseen-land residual, an upper bound | report |
| X3 | OBS | Sample points whose nearest truth road lies outside grid + 10 km (v7 measured 0 of 2,000 in NH and ME) | report |

**RD1–RD5.** Truth is the exact `shapely` STRtree distance from each
pixel centre to the nearest road in the recipe's road set — never the
region's own state, which would reproduce BUG-0023 inside the gate.
400 points per stratum, seed pinned, drawn from `T \ C`, five strata:
uniform; interior (> 5 km from coverage edge, other-state line and grid
edge); within 5 km of a land boundary with another US state; within 10 km
of the grid edge; within 5 km of the coverage boundary `∂T`.

| id | check | required |
|---|---|---|
| RD1 | median \|err\| | ≤ 20 m |
| RD2 | p99 \|err\| | ≤ 60 m |
| RD3 | `count(|err| > 60 m)` | 0 |
| RD4 | median signed err | in [−20, +5] m |
| RD5 | points in `T \ C` whose raster is nodata | 0 |

*Post-implementation (CR-0016, 2026-09-30): RD1 and RD4 are now reported as observations, not gates; this table records what CR-0014 accepted.*

The thresholds and their derivation live in `cr0014_pins.json` and the
script's docstring: truth is measured from the pixel centre, so the EDT
differs from it by at most the road's in-pixel offset (≤ 21.2 m, either
sign) plus log1p encoding (< 18 m below 35 km; max in-coverage `D_road`
is 17.2 km), so 60 m has headroom (observed max 21.4 m over 4,000 points
per region). RD4's band reflects `all_touched` widening each road
(observed median −8.8 m). Only the state-line and grid-edge strata separate
today's broken ME raster (a uniform median passes it).

## Impact
- **`road_dist` values change** in ME and VT near state lines and grid
  edges (the BUG-0023 fix): on the current record set 140 of 3,860 ME and
  717 of 2,261 VT positives differ by > 60 m from the corrected value.
- **New nodata** in all regions where `C` applies (X1 reports the records
  affected). Models with validity channels read it as missing; legacy
  checkpoints are refused.
- **CR-0007 I17 changes** (it reads `road_dist`); its value must be taken
  after this CR.
- **Patch cache** rebuilt (R8). **Not affected:** other rasters; records
  (`generate_negatives.py` does not read `road_dist`); model code.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Truth or `C` built from a different road set false-fails the fix | Recipe pinned; verifier's own TIGER copy; R0b |
| Canada rule over- or under-masks | R2 exact against the verifier's `C` |
| Over-masking by any other route | R2, RD5 |
| Truncated cached download | Atomic `_download` (U1, U2); R0b |
| Year-copies diverge | R3 |
| Stale patches served | R8 |
| Regeneration loses the originals | Backup + manifest (B0) and a restore rehearsal |

## Test plan
**Here:** U1 (interrupted download leaves no file; `.part` removed;
next call re-fetches), U2 (a truncated cached zip is detected and
re-fetched), U3 (Canada rule on a synthetic grid: road 5 km away, land
2 km away → nodata; land farther than the road → value; no land at all →
no new nodata), U4 (densified
footprint selects a superset of today's counties — trivially equal today).
A VT rehearsal into scratch with `--out-dir`, all gates, plus restoring
one backed-up file to scratch and matching its manifest hash. Then the
full run.

**Not here:** Canadian road data — the rule writes nodata rather than
estimating.

## Deliverables (in execution order)
- [x] 1. **Before approval:** `check_road_dist.py` and
      `docs/quality/cr0014_pins.json` (R0 pins, recipe, RD thresholds,
      sampling seed, and `C` count and digest per region from the
      verifier's own TIGER copy), unit-tested on a synthetic fixture;
      committed.
- [x] 2. `generate_road_distance.py` changes (§1); U1–U4.
- [x] 3. Fetch the 8 VT-grid county road files into `data/roads`.
- [x] 4. Manifest (sha256, mtime) and backup of the 30 `road_dist` files
      to `/home/ec2-user/grouse_backup/CR-0014/`.
- [x] 5. VT rehearsal into scratch; all gates; restore rehearsal.
- [x] 6. Regenerate ME, NH, VT in place; run `check_road_dist.py` one
      region at a time (ME peaks at ~15–20 GB), never alongside the
      generator; save to `docs/quality/evidence/CR-0014-gates.txt`.
- [x] 7. Purge `data/cache/patches_*`; R8.
- [x] 8. Bookkeeping:
      - BUG-0037 (Canada over-read), all §2 sections, `BUG_LOG.md` row.
      - §4 recurrence review: same mechanism as BUG-0023 under PA-0017
        ("plus a margin for neighbourhood operations") and PA-0018
        ("everything that intersects"). Prior-PA failure analysis: the
        generator's own docstring already said border distances are upper
        bounds, yet neither sweep recorded a Canada item — both were read
        as "US data across state lines".
      - PA-0023 (extends PA-0018): a neighbourhood computation whose
        source ends at a national border must use cross-border data or
        write nodata where the neighbourhood crosses it. §3.5 sweep:
        every neighbourhood computation near the Canadian border —
        negatives' 300 m buffer against sightings, thinning, block
        holdouts, KDE, `diagnose_road_bias.py`.
      - BUG-0023: status FIXED; its §6 records that this CR is the
        retroactive review of `bf8d31a` and that §1.1's ordering
        deviation stays recorded (a deviation, not an open bug).
      - PA-0017/PA-0018 Swept? cells.

## Out of scope
- `diagnose_road_bias.py`'s home-state roads (BUG-0026).
- Canadian road data (Statistics Canada NRN).
- TIGER 2025.
- `predict.py`'s validity mask; the retrain (CR-0009).
