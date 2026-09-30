# CR-0008: Make the `tsd`, TreeMap and `tcc`/`nlcd` generators write nodata outside coverage

**Status: IMPLEMENTED (v9), 2026-09-30 — all deliverables complete; G4/G9 15/15 pass (`docs/quality/evidence/CR-0008-gates.txt`), U1–U6 pass.**
History, verdicts and dispositions: `CR-0008-review-log.md`. v1–v7 text:
commit `bb170ea`. This document states only current intent.

**Order:** lands **after CR-0010** (its acceptance compares generator
output with CR-0010's repaired rasters). Independent of CR-0007. CR-0009
is gated on it. `road_dist` ME/VT moved to a separate CR (see Out of scope).

**One CR, not three (§1.1, one change per CR):** the three generator fixes
share one mechanism (PA-0017), one acceptance method (G4 against CR-0010)
and one guard removal; the bookkeeping deliverables are §1.5's
requirement, not a separate change.

## Scope
Fix the three generators behind BUG-0024 (`tsd`), BUG-0025 (TreeMap) and
BUG-0030/BUG-0035 (`tcc`/`nlcd`), and the encoders behind BUG-0036, so
that every future run writes the declared nodata (`-9999`) outside the
product's coverage instead of a legitimate-looking value. No raster in
`data/` is rewritten by this CR.

## Why now
CR-0010 repaired the files on disk, but the generators still produce the
defect; CR-0010's refuse-to-overwrite guard is all that stops the next run
from restoring fabricated values. PA-0017 is a rule about generators.

## The change

### 1. `generate_time_since_disturbance.py` (BUG-0024)
Today `_emit` writes `np.where(last >= 0, year - last, TSD_MAX_YEARS)`:
a pixel no vintage covers reads "undisturbed for 30 years".

- In the stripe loop keep a boolean `cov` (initially all `True`); for
  each vintage `d` read, `cov &= ~np.isin(arr, NODATA_SENTINELS)`. The
  loop emits output year `Y` before folding any vintage `d > Y`, so `cov`
  at emit time is the intersection over vintages `≤ Y`.
- `_emit` writes `-9999` where `~cov`, after `tsd_encode`.
- `hit` becomes `(arr > 0) & ~np.isin(arr, NODATA_SENTINELS)`. This is
  for clarity only: any pixel it would change is already `~cov`, so it
  changes no output (measured: 0 pixels, all regions).
- Add `--out-dir` (default: the pipeline raster dir) and `--years`
  (output years to write). `--out-dir` replaces `raster_dir` for every
  path the run writes.
- Write tag `GROUSE_COVERAGE=disturbance-intersection`.

### 2. `generate_treemap_features.py` (BUG-0025)
The raw TreeMap bands carry no sentinel: Earth Engine's `unmask(0)` merged
"non-forest" and "outside CONUS" into one `0`. Coverage therefore comes
from the region's NLCD raster — the same reference CR-0010 used.

- `write_vintage` opens `rd.latest_raster_path("nlcd")` and asserts
  `grid_mismatch` is `None` **and** `height`, `width` and `transform`
  equal the template's (windowed reads need identical extents). It reads
  `nlcd != -9999` as `cov` per stripe. No NLCD raster → exit with an error.
- `_clean(arr)` returns `(values, bad)`: `bad` marks non-finite, `< 0`
  and `≥ NODATA_FLOOR` raw values, and `values` holds a **finite
  placeholder `0.0`** at those pixels so the encoders (§3) never see
  NaN. The placeholder never reaches the output: per feature,
  `bad_balive = bad[BALIVE]`, `bad_tpa_live = bad[TPA_LIVE]`,
  `bad_qmd = bad[BALIVE] | bad[TPA_LIVE]`,
  `bad_carbon_dwn = bad[CARBON_DWN]`, and after encoding each feature is
  written `-9999` where `~cov | bad_<feature>`.
- In-coverage zeros remain `0` (Branch A, user decision 2026-09-30).
- Add `--out-dir` and `--years`. `--out-dir` **replaces
  `plan["raster_dir"]`**, so `write_vintage`, the `shutil.copy2` year
  fan-out and the guard all use it. `--years` filters output years
  **before** they are grouped by vintage.
- Write tag `GROUSE_COVERAGE=nlcd`.

### 3. `models.py` encoders (BUG-0036)
`tsd_encode`, `road_dist_encode`, `tpa_live_encode`, `treemap_encode`
and `qmd_from_balive_tpa` map NaN to `0` without error. Each now raises
`ValueError` on any non-finite input. Contract, in each docstring:
encoders take finite values; generators write nodata by mask after
encoding. Callers: `generate_road_distance.py:216` (EDT result, finite)
and the two generators above (finite after §1/§2). `predict.py` and
`dataset.py` do not call them.

### 4. `download_tcc_nlcd.py` (BUG-0030 `tcc`, BUG-0035 `nlcd`)
Earth Engine exports masked pixels as `0`. For `tcc` that is a real
reading; for `nlcd` (`valid_range` 11–95) it is rejected only by accident.

- `year_image` returns `sub.select(band).mosaic().toInt16().unmask(-1)`.
  The cast makes `-1` representable whatever the band's native type
  (both are unsigned 8-bit). `-1` is outside both valid ranges, so the
  existing range mask writes `-9999`.
- Factor the range mask into `mask_to_valid(arr, lo, hi)`.
- **Post-download coverage check, in code.** `build_raster` warps to
  `out_path + ".tmp"`, then for `tcc` requires
  `count(tmp != -9999 where the region's NLCD == -9999) == 0`, and only
  then `os.replace`s it. On failure it raises and leaves the existing
  file untouched. The check runs only when the output and the region's
  NLCD raster are on the same grid (same shape and transform); if there
  is no NLCD raster or no template (output left in EPSG:5070), it is
  skipped with a printed warning.
- Write tag `GROUSE_COVERAGE=ee-mask`.

### 5. Replace CR-0010's guard
- Delete `refuse_if_repaired`'s calls and the `--overwrite-repaired`
  flags from the three generators, and `refuse_if_repaired` itself.
- Delete CR-0010's generator-guard tests (`test_helper`,
  `test_treemap_copy2_destination_refuses`,
  `test_tsd_refuses_before_opening`, `test_tcc_refuses_before_download`).
- **Keep** the legacy-checkpoint refusal in `predict.py`/`calibrate.py`,
  and widen `repaired_paths` to match `GROUSE_COVERAGE` as well as
  `GROUSE_REPAIR`, so it still fires on files the fixed generators write.

## Acceptance gates
All exact. Outputs go to a scratch directory, never `data/landfire/`.

| id | check | required |
|---|---|---|
| G4-D | `generate_time_since_disturbance.py --regions R --years Y --out-dir <scratch> --block-rows 512` for (ME, 2016), (NH, 2025), (VT, 2025); values compared with CR-0010's repaired file | pixel-identical |
| G4-T | `generate_treemap_features.py --src-dir data/treemap_raw --regions VT --years 2016 2019 2022 --out-dir <scratch> --block-rows 512` (the representative year of each TreeMap vintage on disk); all 12 outputs compared with CR-0010's repaired files | pixel-identical |
| G9 | Profile and `tags(ns='IMAGE_STRUCTURE')` of every G4 output equal CR-0010's file's. Default-namespace tags (`GROUSE_*`) are not compared | identical |
| U1 | `_clean` + TreeMap write path: NaN, a negative value and a value ≥ 1e9, each injected at an in-coverage pixel of a different attribute, give `-9999` in the dependent features (per §2's `bad` mapping) and nowhere else | pass |
| U2 | Each of the five encoder functions raises on NaN and on ±inf | pass |
| U3 | `mask_to_valid`: `tcc` `-1 → -9999`, `0 → 0`; `nlcd` `0 → -9999`, `-1 → -9999` | pass |
| U4 | `tsd` coverage: synthetic 3-vintage stack, sentinel at one pixel in the middle vintage → `-9999` for output years ≥ that vintage, a value for earlier years | pass |
| U5 | Post-download check: a `tcc` temp file with a value inside the NLCD nodata footprint raises and leaves the existing file unchanged | pass |
| U6 | `refuse_legacy_checkpoint_on_repaired` fires for a `missing_mask=False` model on a file tagged `GROUSE_COVERAGE` | pass |

`--block-rows 512` is pinned: WarpedVRT nearest-neighbour output can
differ at single pixels between very different window heights (measured:
1-row vs 512-row reads), while 512 and 1024 give identical results.

A G4 mismatch is a finding to investigate, not to waive.

## Impact
- **Data on disk:** none. Future runs produce what CR-0010 produced.
- **Code:** the three generators, five `models.py` functions,
  `grouse_data.py` (guard removed, `repaired_paths` widened), tests.
- **Encoder callers** that pass NaN now fail loudly. None do today.
- **Legacy-checkpoint refusal** will also fire on freshly downloaded
  `nlcd` files (they carry `GROUSE_COVERAGE` too), although `nlcd` values
  do not change. Intended: the refusal keys on the tag, not the feature.
- **CR-0007:** no effect (no data change).

## Risk: LOW
| risk | mitigation |
|---|---|
| Generator output differs from CR-0010's repair | G4-D/G4-T pixel identity, G9 |
| `unmask(-1)` does nothing in Earth Engine (type clamp) | `toInt16()` cast; post-download check (U5) refuses to write a `tcc` file with values outside the NLCD footprint |
| TreeMap run with a stale or mismatched NLCD raster | Full grid and extent assertion; exit if missing |
| A regenerated file escapes the legacy-checkpoint refusal | `repaired_paths` matches `GROUSE_COVERAGE` (U6) |
| Guard removed before the generators are fixed | Guard removal is deliverable 6, after G4 passes |

## Test plan
**Here:** U1–U6, G4-D, G4-T, G9. Disk: G4 writes 3 `tsd` files and 12
VT TreeMap files to scratch (under 1 GB), deleted after the run.

**Not here:** a real Earth Engine download (no GCP credentials). Covered
by the `toInt16` cast and the in-code post-download check (U5), which
runs on every future download.

## Deliverables (in execution order)
- [x] 0. **Before approval:** BUG-0035 drafted (`nlcd` correct only by
      accident) — `docs/quality/bugs/BUG-0035-*.md`.
- [x] 1. `models.py` encoders (§3); U2.
- [x] 2. `generate_time_since_disturbance.py` (§1); U4.
- [x] 3. `generate_treemap_features.py` (§2); U1.
- [x] 4. `download_tcc_nlcd.py` (§4); U3, U5.
- [x] 5. Run G4-D, G4-T, G9; save to `docs/quality/evidence/CR-0008-gates.txt`.
- [x] 6. Replace CR-0010's guard (§5); U6; the remaining CR-0010 tests pass.
- [x] 7. Bookkeeping:
      - File BUG-0036 (encoders map NaN to 0 silently; PA-0006 class) with
        all §2 sections, recurrence review and `BUG_LOG.md` row.
      - Amend BUG-0025 §4 to quote `_clean`'s clamp (`a[a < 0] = 0.0`) and
        BUG-0024 §4 to quote `hit`, as part of the same defects.
      - Close BUG-0024, BUG-0025, BUG-0030, BUG-0035 (corrective action:
        data CR-0010, generator CR-0008); update their `BUG_LOG.md` rows.
      - PA-0017's Swept? cell: `tsd`, TreeMap, `tcc`, `nlcd` generators fixed.

## Out of scope
- **`road_dist` ME/VT** (BUG-0023) → a separate CR, not yet written. It
  must carry, from v7 and accepted dispositions: the regeneration;
  `_download` atomicity; the densified footprint reprojection;
  `TIGER_YEAR`; the Canadian-border roads decision; G7/RD1–RD5 including
  truth from every TIGER county intersecting grid + pad (PA-0018), the
  excluded-point count gated at 0, and all 10 year-copies byte-identical;
  G6 for the regenerated files; and the BUG-0023 §6 ruling that this
  retroactive CR reviews `bf8d31a` but cannot discharge its §1.1
  ordering deviation. Listed in the open-issues tracker.
- **Repairing existing rasters** → CR-0010.
- **`download_treemap.py`**: its raw output is an intermediate the model
  never reads; coverage is resolved once, in the generator (§2).
- `predict.py`'s validity mask; Branch B; the retrain (CR-0009).
