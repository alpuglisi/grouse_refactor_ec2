# CR-0010: Repair the 174 existing rasters that carry fabricated values outside coverage

**Status: APPROVED (v3), 2026-09-30 — implementation in progress.**
Review history and dispositions live in `CR-0010-review-log.md`, not here.
This document states only what is currently true and intended.

**Split from CR-0008** (2026-09-30). This is CR-0008's §1 "repair the
existing rasters" plus the gates that govern it — the part that survived
seven review rounds without a break. CR-0008 keeps the generator fixes,
the downloader fixes and the `road_dist` regeneration.

## Scope
Set every pixel outside each product's coverage to the file's declared
nodata (`-9999`) in the 174 existing `tsd`, TreeMap (`balive`,
`tpa_live`, `qmd`, `carbon_dwn`) and `tcc` rasters under `data/landfire/`,
by a local post-process, with backup and exact acceptance gates.

## Why now
Six model input channels feed fabricated readings outside coverage: `tsd`
reads a constant "undisturbed 30 years" (BUG-0024), TreeMap reads `0`
"non-forest" (BUG-0025), and `tcc` reads `0` (BUG-0030, to be filed) over
the ~47 % of the ME grid, ~10 % of NH and ~4 % of VT that lies outside the
US. The model cannot distinguish these from real readings. CR-0009's
retrain needs the repaired data.

## Files in scope (measured)
| feature | files | bytes |
|---|---|---|
| `tsd` | 30 (3 regions × 10 yr) | 154,889,996 |
| `balive`, `tpa_live`, `qmd`, `carbon_dwn` | 120 (4 × 3 × 10) | 7,995,262,151 |
| `tcc` | 24 (3 × 8 yr) | 1,307,967,557 |
| **total** | **174** | **9,458,119,704 B = 9,020 MiB** |

Within a region every in-scope file has identical transform, width,
height, CRS, `dtype=int16`, `nodata=-9999`. The repair is
index-for-index: no warp, resample or re-encode.

## The change
For each in-scope file, write `-9999` at every pixel where that feature's
**coverage mask** (below) is false. Nothing else changes.

**Coverage mask per feature** — derived at native resolution on the file's
own grid, never upsampled:

| feature | mask | predicate |
|---|---|---|
| `tsd` | `disturbance∩` | intersection over the 26 disturbance vintages (Dist99–Dist24) of `value ∉ grouse_data.NODATA_SENTINELS`, each vintage read onto the region grid with `WarpedVRT(..., resampling=Resampling.nearest)` and default error threshold, as `generate_time_since_disturbance.py` does |
| TreeMap ×4, `tcc` | `nlcd` | `{REGION}_{year}_nlcd.tif != -9999` (identical digest for every year) |

Rules:
1. **Spatial, not value-based.** `balive > 0` occurs outside NLCD coverage
   (ME 11,700 / NH 4,464 / VT 2,137 px), so "turn zeros into nodata" is
   wrong. In-coverage zeros are real readings (Branch A, user decision
   2026-09-30) and stay `0`.
   The masks are deliberately conservative: later disturbance vintages
   map some ground outside `disturbance∩` (e.g. VT 2023: 3,331 px), and
   TreeMap bleeds 1–2 px past the NLCD edge. Those readings also become
   nodata; one coverage per region is preferred over per-year edges.
2. **One mask per region serves all `tsd` years.** `cov(vintages ≤ 2016)`
   is byte-identical to `cov(all 26)` in all three regions (verified by
   two independent reviewers). The repair script asserts this at run time
   and aborts if it no longer holds.
3. **Write to a temp file in the same directory, then `os.replace`.**
   Preserve the full profile and `IMAGE_STRUCTURE` tags (including
   `PREDICTOR=2`). Do not copy the old file's mtime by any route.
4. **Add a provenance tag** (default namespace):
   `GROUSE_REPAIR=CR-0010`, plus the mask digest and date.
5. **Guard the three generators** that write these files. They still
   carry the defects CR-0008 fixes; without a guard the next run silently
   restores the fabricated values. Each refuses, **before any file is
   opened for writing or any download starts**, if any target path exists
   and carries `GROUSE_REPAIR`, unless passed `--overwrite-repaired`.
   Every write site is covered:

   | script | write site | check |
   |---|---|---|
   | `generate_time_since_disturbance.py` | all target years opened `"w"` together (`:293-295`) | every target year's path, before the loop |
   | `generate_treemap_features.py` | representative year `rasterio.open(path, "w")` (`:294`) **and** the `shutil.copy2` year fan-out (`:444-448`) | the representative path **and every `copy2` destination**, before `write_vintage` runs |
   | `download_tcc_nlcd.py` | `build_raster(...)` (`:488`), once per year | every year's output path, before the first `build_raster` call |

   The guard lives in one helper (`grouse_data.refuse_if_repaired(paths)`)
   so all three call the same check. CR-0008 removes the calls when it
   fixes the generators.
6. **Refuse legacy checkpoints on repaired rasters.** Checkpoints whose
   config has no `missing_mask` load with `missing_mask=False`
   (`models.py:835`), which feeds nodata to the network as `0`. After the
   repair that turns out-of-coverage `tsd` into "disturbed this year" — a
   new fabricated reading. Both copies of `grouse_single_best.pth` (the
   default for `predict.py` and `calibrate.py`) are such checkpoints.
   `predict.py` and `calibrate.py` exit with an explanatory error when the
   loaded model has `missing_mask == False` and any raster the run reads
   carries `GROUSE_REPAIR`. One helper in `grouse_data.py`, called by both
   after the model is loaded and the raster paths are resolved.

## Acceptance gates
Every gate is implemented in one committed script,
`check_raster_repair.py`, which reads its constants from
`docs/quality/cr0010_pins.json`. It must not import the repair code. It
takes `--root` (raster directory) and `--files` (subset) so the same
script runs the single-file rehearsal and the full check. All
measurements are at full resolution. **GATE** fails the CR; **OBS** is
reported only.

| id | type | check | required |
|---|---|---|---|
| B0 | GATE | sha256 of every backup file vs the hashes of the **originals**, taken before copying and committed | all match |
| G0 | GATE | Verifier re-derives each mask independently; `sha256(np.packbits(mask.ravel()))` and inside-pixel count | equal the pins below |
| G1 | GATE | `count(pixels inside coverage whose value changed)` vs the backup | 0, per file |
| G2 | GATE | `count(outside-coverage pixels != -9999)` | 0, per file |
| G2′ | GATE | `count(changed pixels)` | `== N_pre` below, per file |
| G6 | GATE | Full `rasterio` profile, `tags(ns='IMAGE_STRUCTURE')`, `tags(1)`, `overviews(1)`, `mask_flag_enums` vs backup; no `.aux.xml` sidecar | identical, per file (originals have no overviews, band tags or sidecars) |
| G7 | GATE | `tags()['GROUSE_REPAIR'] == 'CR-0010'` and the tagged mask digest equals the G0 pin | every file |
| F1 | GATE | Checked file set equals the manifest's 174 entries; no stray temp files in `data/landfire/` | no missing, extra or temp files |
| F2 | GATE | sha256 of every other `*.tif` in `data/landfire/` (out-of-scope features) vs a manifest taken before the repair | all unchanged |
| G8.1 | GATE | `count(data/cache/patches_*)` after purge (no extension anchor) | 0 |
| G8.2 | GATE | Each repaired file's mtime vs the pre-repair mtime recorded in the manifest | differs |
| G8.3 | PROCESS | No prediction, calibration or map artifact published until CR-0009 lands. Checked by presence of `STALE_SEE_CR-0010.txt` in `data/predictions/`, `data/calibration/` and `data/maps/` (not scripted) | markers present |
| X1 | OBS | Disagreement between the three coverage lineages (NLCD, TIGER, disturbance) | report; today ≤ 0.06 % of grid |
| X2 | OBS | Total repaired size / backup size | report |
| X3 | OBS | Training records with any out-of-coverage pixel in a 64×64 window, and with an out-of-coverage centre pixel, on whatever record set exists | report, name the record set |
| X4 | OBS | Per-year in-coverage `tsd == 0` and `TSD_MAX_YEARS` counts, before and after | report (must be unchanged; implied by G1) |

G1 ∧ G2 ∧ G2′ with pinned G0 masks determine the repair uniquely:
`changed ⊆ outside`, `|changed| = #(outside ∧ not already -9999)`, and every
outside pixel ends `-9999`. A no-op fails G2′; an inflated or aliased mask
fails G0; a value change inside coverage fails G1.

**G0 pins** (full resolution; sha256 first 32 hex):

| region | mask | inside px | sha256 |
|---|---|---|---|
| ME | `nlcd` | 107,406,613 | `59a7639b5fb0389d0955eb61e45ad3fc` |
| ME | `disturbance∩` | 107,321,500 | `9006374548fa58f4a59e3ff14c24130d` |
| NH | `nlcd` | 51,384,193 | `15375b62cca9ab85ec4c23869218a6d7` |
| NH | `disturbance∩` | 51,379,852 | `c10c46f12978de0e68fd1ded93b65a84` |
| VT | `nlcd` | 50,450,696 | `682ef390d584a2a7b30b3eed10c75e15` |
| VT | `disturbance∩` | 50,447,193 | `64677a7523a8b20e24f1e595dbf8c39a` |

**`N_pre`** (pixels per file that must change; same for every year):

| feature | ME | NH | VT |
|---|---|---|---|
| `tsd` | 96,300,932 | 5,663,604 | 2,104,152 |
| each TreeMap feature | 96,215,819 | 5,659,263 | 2,100,649 |
| `tcc` | 95,946,265 | 5,653,164 | 2,096,352 |

All pins were reproduced by independent code in review rounds 6 and 7 of
CR-0008. They are deterministic given the source files, so they are exact
constants, not thresholds. `data/disturbance/` holds two md5-identical
extractions of the vintages; either yields the same digest.

## Impact
- **Model inputs:** these six channels become nodata outside coverage.
  Checkpoints trained with `missing_mask` (e.g. `bce.pth`, `ed.pth`,
  `gap3.pth`) read that as missing. Checkpoints without it — including
  the default `grouse_single_best.pth` — would read `0`, a fabricated
  value, so rule 6 makes `predict.py` and `calibrate.py` refuse them on
  repaired rasters. Those checkpoints are invalid until CR-0009's retrain
  (`train.py` defaults to `--missing-mask`; CR-0009 must keep it on).
- **Training records:** 0 positives have a centre pixel outside any
  in-scope feature's mask (round-7 reviewer measurement). One ME
  validation negative, `(-67.10082, 44.50177)` in `val_negatives_ME.csv`,
  has an out-of-coverage centre; ME has 23 train + 4 val negatives with
  some out-of-coverage pixels in-window. Reported by X3; the record's
  disposition belongs to CR-0007.
- **CR-0007 interaction:** because no positive's centre value changes and
  `road_dist` is not touched here, no CR-0007 gate requires re-derivation.
  Either CR can land first.
- **Patch cache:** `data/cache` (28 GB, 206 `.npy` + 1 stray `.tmp`) holds
  patches built from pre-repair values and is purged.
- **Predictions and calibration** in `data/predictions/` and
  `data/calibration/` become stale and are marked so; no republish until
  CR-0009.
- **Code touched:** the new repair and check scripts; a guard helper in
  `grouse_data.py`; guard calls in the three generators, `predict.py` and
  `calibrate.py`. No change to `models.py`, `dataset.py` or `train.py`.
- **Not affected:** `road_dist`, the LANDFIRE vegetation channels, `nlcd`,
  record membership, splits, model architecture.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Wrong mask (aliased, inflated, shifted) | G0 pins, derived independently by the verifier |
| Repair damages in-coverage values | G1 = 0 against the backup |
| Backup corrupted or hard-linked, so G1 reads 0 by construction | Real copy on a separate inode set; B0 re-verifies hashes |
| Metadata-preserving replace keeps the old mtime, so the cache still hits | G8.2 against the manifest's recorded mtime; G8.1 purge |
| Profile or compression lost on rewrite | G6 |
| A generator re-run restores the defect before CR-0008 lands | Rule 5 guard at every write site, including the `copy2` fan-out; `check_raster_repair.py` G2 re-runnable at any time |
| A legacy checkpoint predicts on repaired rasters, reading nodata as 0 | Rule 6 refusal in `predict.py` and `calibrate.py` |
| Stale predictions published as if fixed | G8.3 |
| Disk: 16.67 GB free; backup 9.46 GB leaves 7.21 GB | Repair is one file at a time (largest 108.8 MB temp); no uncompressed intermediate |

## Test plan
**Validatable here:** every gate above, on the real files. Before
implementation, a rehearsal: back up, repair and restore **one** file
(`VT_2025_tsd.tif`) in a scratch directory, and run G0–G6 against it.
After implementation, restore is not rehearsed in place (it would revert
the repair); the manifest hashes (B0) are the restore guarantee.

**Not validatable here:** the effect on model performance (CR-0009).

## Deliverables (in execution order)
- [ ] 1. `docs/quality/cr0010_pins.json` with the G0 and `N_pre` tables above.
- [ ] 2. `check_raster_repair.py` implementing B0, F1, F2, G0–G8.2, X1–X4, with
      `--root` and `--files`; unit-tested against a synthetic 3-file
      fixture that includes a no-op, an inflated mask and an in-coverage
      edit, each of which must fail.
- [ ] 3. `repair_coverage_rasters.py` implementing § The change, rules 1–4.
- [ ] 4. `grouse_data.refuse_if_repaired` and its calls at every write site
      in rule 5's table; unit test covering the TreeMap `copy2` path (an
      untagged representative year with a tagged `copy2` destination must
      refuse), plus a test that each of the three generators refuses on a
      tagged scratch copy before opening anything for writing.
- [ ] 5. Legacy-checkpoint refusal in `predict.py` and `calibrate.py` (rule
      6); unit test with a `missing_mask=False` model and a tagged raster.
- [ ] 6. Single-file rehearsal (Test plan), in a scratch directory.
- [ ] 7. Hash the 174 originals and every other `*.tif` in `data/landfire/`;
      commit both manifests (`docs/quality/evidence/CR-0010-manifest-*.txt`).
      Then back up all 174 files to `/home/ec2-user/grouse_backup/CR-0010/`
      — outside `data/landfire/`, so the backup never matches
      `grouse_data`'s raster discovery globs — as real copies (not hard
      links); manifest with sha256, size and pre-repair mtime per file.
- [ ] 8. Run the repair; run `check_raster_repair.py`; all GATE rows pass.
      Save its output to `docs/quality/evidence/CR-0010-gates.txt`
      (create the directory).
- [ ] 9. Purge `data/cache/patches_*` (including the `.tmp` stray); G8.1.
- [ ] 10. Write `STALE_SEE_CR-0010.txt` in `data/predictions/`,
      `data/calibration/` and `data/maps/` (G8.3).
- [ ] 11. Bookkeeping. CR-0010 is the sole owner of BUG-0030.
      - File BUG-0030 (`tcc` fabricated `0` outside coverage) with all §2
        sections and a `BUG_LOG.md` row.
      - Recurrence review (§4) against BUG-0024/0025 and PA-0017, whose
        Swept? cell records TCC/NLCD as "not determined from code (needs a
        real-file check)". Include the prior-PA failure analysis: why
        PA-0017's sweep did not catch `tcc`.
      - Update PA-0017's Swept? cell with the real-file result, or add a PA
        that extends it if the analysis shows PA-0017 was too narrow.
      - Update BUG-0024 and BUG-0025 corrective-action sections: data
        repaired by CR-0010; generator fix pending CR-0008.

## Out of scope
- Generator and downloader fixes (`generate_time_since_disturbance.py`,
  `generate_treemap_features.py`, `models.py` encoders,
  `download_treemap.py`, `download_tcc_nlcd.py`) → CR-0008.
- `road_dist` regeneration, `TIGER_YEAR`, Canadian-border roads → CR-0008.
- `nlcd`'s incidental correctness (BUG-0035) → CR-0008.
- `predict.py`'s validity mask; Branch B; the retrain → CR-0009 or new CRs.
- Reclaiming the duplicate 15 GB disturbance extraction.
