# CR-0008: Make the `tsd`, TreeMap and `tcc`/`nlcd` generators write nodata outside coverage

**Status: PROPOSED (v8) — awaiting review.** Nothing implemented.
History, verdicts and dispositions: `CR-0008-review-log.md`. v1–v7 text:
commit `bb170ea`. This document states only current intent.

**Order:** lands **after CR-0010** (its acceptance compares generator
output with CR-0010's repaired rasters). Independent of CR-0007. CR-0009
is gated on it. `road_dist` ME/VT moved to a separate CR (see Out of scope).

## Scope
Fix the three generators behind BUG-0024 (`tsd`), BUG-0025 (TreeMap) and
BUG-0030/BUG-0035 (`tcc`/`nlcd`) so that every future run writes the
declared nodata (`-9999`) outside the product's coverage instead of a
legitimate-looking value. No raster in `data/` is rewritten by this CR.

## Why now
CR-0010 repairs the files on disk, but the generators still produce the
defect: the next run of any of them restores fabricated values (CR-0010
guards against that with a refuse-to-overwrite check, which this CR
removes). PA-0017 is a rule about generators; the repair alone does not
satisfy it.

## The change

### 1. `generate_time_since_disturbance.py` (BUG-0024)
Today `_emit` writes `np.where(last >= 0, year - last, TSD_MAX_YEARS)`:
a pixel no vintage covers reads "undisturbed for 30 years".

- In the stripe loop, keep a boolean `cov` (initially all `True`) and for
  each vintage `d` read, `cov &= ~np.isin(arr, NODATA_SENTINELS)`.
  Because the loop emits output year `Y` before folding any vintage
  `d > Y`, `cov` at emit time is exactly the intersection over vintages
  `≤ Y` — the correct coverage for that year.
- `_emit` writes `-9999` where `~cov`, after `tsd_encode`.
- `hit` becomes `(arr > 0) & ~np.isin(arr, NODATA_SENTINELS)`. Today it
  excludes only the file's declared nodata tag, which is wrong for some
  vintages (e.g. `32767` fill under a `-32768` tag). Raw value `0` is the
  VAT "Background" class — covered, undisturbed — and correctly is not a
  hit.
- Add `--out-dir` (default: the pipeline raster dir) and `--years`.
- Write tag `GROUSE_COVERAGE=disturbance-intersection`.

### 2. `generate_treemap_features.py` (BUG-0025)
The raw TreeMap bands carry no sentinel: Earth Engine's `unmask(0)` has
already merged "non-forest" and "outside CONUS" into one `0`
(`data/treemap_raw` has `nodata=None`, 0 % NaN/negative). So coverage
must come from an external reference, and the only local one is NLCD —
the same reference CR-0010 uses for these features.

- `write_vintage` opens the region's NLCD raster
  (`rd.latest_raster_path("nlcd")`), asserts it has the output grid
  (`grid_mismatch` returns nothing), and reads `nlcd != -9999` as
  `cov` per stripe. If no NLCD raster exists, exit with an error.
- `_clean` returns `(values, bad)` where `bad` marks non-finite,
  `< 0` or `≥ NODATA_FLOOR` raw values, instead of silently setting them
  to `0.0`. In-coverage zeros remain `0` (Branch A, user decision
  2026-09-30).
- After encoding, write `-9999` where `~cov | bad`.
- The `shutil.copy2` year fan-out is unchanged: it copies an output that
  is now correct.
- Add `--out-dir` and `--years`.
- Write tag `GROUSE_COVERAGE=nlcd`.

### 3. `models.py` encoders
`tsd_encode`, `road_dist_encode`, `tpa_live_encode`, `treemap_encode`
and `qmd_from_balive_tpa` map NaN to `0` without error (`np.clip` then
`np.rint(...).astype(int16)`, or `tpa > 0` being False for NaN). Each
now raises `ValueError` on any non-finite input. Contract, in each
docstring: encoders take in-coverage values only; the generator writes
nodata by mask after encoding. All current callers already pass finite
values (checked: `generate_road_distance.py:216` encodes the EDT result
before masking; the other two generators after §1/§2).

### 4. `download_tcc_nlcd.py` (BUG-0030 `tcc`, BUG-0035 `nlcd`)
Earth Engine exports masked pixels as `0`. For `tcc`, `0` is also a real
reading (0 % canopy), so `build_raster`'s range mask
(`(arr >= lo) & (arr <= hi)`, `lo = 0`) keeps them. For `nlcd`,
`valid_range` starts at 11, so the mask rejects them — correct only by
accident.

- In `year_image`, return `sub.select(band).mosaic().unmask(-1)`. `-1`
  is outside both products' `valid_range`, so the existing range mask
  turns it into `-9999`. Applies to both products; `nlcd` no longer
  depends on the accident.
- Factor the range mask into `mask_to_valid(arr, lo, hi)` so it can be
  unit-tested.
- Write tag `GROUSE_COVERAGE=ee-mask`.

### 5. Remove CR-0010's generator guard
Delete the `grouse_data.refuse_if_repaired` calls CR-0010 added to the
three generators (and the helper, if nothing else calls it). CR-0010's
legacy-checkpoint refusal in `predict.py`/`calibrate.py` stays.

## Acceptance gates
All exact; no statistical thresholds. Outputs go to a scratch directory,
never `data/landfire/`.

| id | check | required |
|---|---|---|
| G4-D | `generate_time_since_disturbance.py --out-dir <scratch> --years Y` for ME 2016, NH 2025, VT 2025, compared with CR-0010's repaired file of the same name | pixel-identical |
| G4-T | `generate_treemap_features.py --src-dir data/treemap_raw --out-dir <scratch>` for VT, representative year of each vintage, all four features, compared with CR-0010's repaired files | pixel-identical |
| U1 | `_clean`: a sentinel injected at an in-coverage pixel yields `-9999` in the output, not `0` | pass |
| U2 | Each of the five encoder functions raises on NaN and on ±inf | pass |
| U3 | `mask_to_valid`: `-1 → -9999`, `0 → 0` for `tcc`; `0 → -9999`, `-1 → -9999` for `nlcd` | pass |
| U4 | `tsd` coverage: a synthetic 3-vintage stack where one vintage has a sentinel at a pixel yields `-9999` there for output years ≥ that vintage and a value for earlier years | pass |
| G9 | Profile and `IMAGE_STRUCTURE` tags of G4 outputs equal the originals' (except the new `GROUSE_COVERAGE` tag) | identical |

A G4 mismatch is a finding to investigate (e.g. a vintage added since the
file was generated), not something to waive.

## Impact
- **Data on disk:** none. Future runs of the three generators produce
  what CR-0010 produced by repair.
- **Code:** the three generators, five `models.py` functions, one
  helper in `grouse_data.py` removed.
- **Callers of the encoders** that pass NaN would now fail loudly instead
  of storing `0`. None do today.
- **CR-0007:** no effect (no data change).

## Risk: LOW
| risk | mitigation |
|---|---|
| Generator fix differs from CR-0010's repair | G4-D/G4-T require pixel identity |
| TreeMap run with a stale or missing NLCD raster | Grid assertion; exit if missing |
| Earth Engine change cannot be run here (no GCP auth) | U3 tests the local half; the first real run is checked with CR-0010's `check_raster_repair.py` G2 against the NLCD pin (deliverable 9) |
| Guard removed before the generators are fixed | Deliverable order: guard removal is after G4 passes |

## Test plan
**Here:** U1–U4, G4-D, G4-T, G9. Disk: G4 outputs are VT-sized except
one ME `tsd` year; under 1 GB in total, deleted after the run.

**Not here:** the Earth Engine change in `download_tcc_nlcd.py` (no GCP
credentials). Accepted gap; deliverable 9 verifies the first real run.

## Deliverables (in execution order)
- [ ] 1. `models.py` encoder contract and non-finite check (§3); U2.
- [ ] 2. `generate_time_since_disturbance.py` (§1); U4.
- [ ] 3. `generate_treemap_features.py` (§2); U1.
- [ ] 4. `download_tcc_nlcd.py` (§4); U3.
- [ ] 5. Run G4-D, G4-T, G9; save output to
      `docs/quality/evidence/CR-0008-gates.txt`.
- [ ] 6. Remove CR-0010's generator guard (§5).
- [ ] 7. File BUG-0035 (`nlcd` correct only by accident) with all §2
      sections, recurrence review against PA-0017, and a `BUG_LOG.md` row.
- [ ] 8. Close BUG-0024 and BUG-0025 (corrective action: data CR-0010,
      generator CR-0008); add this CR to BUG-0030's corrective action.
      Update PA-0017's Swept? cell: `tsd`, TreeMap, `tcc`, `nlcd`
      generators fixed.
- [ ] 9. Add a line to `download_tcc_nlcd.py`'s docstring and to the
      open-issues tracker: the next real download must be checked with
      `check_raster_repair.py` G2 against the NLCD pin before use.

## Out of scope
- **`road_dist` ME/VT** (BUG-0023): regeneration, `_download` atomicity,
  `TIGER_YEAR`, Canadian-border roads, G7/RD1–RD5 → a separate CR, not
  yet written (tracker).
- **Repairing existing rasters** → CR-0010.
- **`download_treemap.py`**: its raw output is an intermediate the model
  never reads, and its `0` cannot be disambiguated in Earth Engine
  without an external boundary. Coverage is resolved once, in the
  generator (§2). Its `nodata=None` and `:315` clip affect only raw
  values the mask overwrites.
- `predict.py`'s validity mask; Branch B; the retrain (CR-0009).
- The duplicate 15 GB disturbance extraction.
