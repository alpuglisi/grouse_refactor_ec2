# CR-0035: re-download the Earth Engine layers on the source grid, re-accept, measure

**Status: DRAFT, 2026-10-05** — awaiting independent review. Depends on
CR-0034 (code). Verdicts and dispositions: `CR-0035-review-log.md`
(created at the first review). This document states only current intent.

## Scope
Replace every on-disk Earth Engine layer (`nlcd`, `tcc`, `balive`,
`tpa_live`, `qmd`, `carbon_dwn`, all regions and vintages) with a
CR-0034 download, prove each is registered with the template grid,
regenerate the split manifests and re-accept the split (split files
unchanged), and measure the effect on the model.

## Fixes
BUG-0094 (data half; the code half is CR-0034).

## Why now
The six layers are ~half a cell off in every region
(`evidence/CR-0032/layer_registration_sweep.txt`); every trained model
reads them; CR-0032's canopy layers need a registered NLCD for their
pilot grid check.

## The change (all steps on the EC2 host, run by the user; outputs
committed to `docs/quality/evidence/CR-0035/`)

### 0. Backup
Copy every file to be replaced (`data/landfire/*_{nlcd,tcc,balive,
tpa_live,qmd,carbon_dwn}.tif`, `data/treemap_raw/*`) to
`data/backup_bug0094/`, preserving names; record their sha256 list. The
backup is the rollback and the evaluation's "before" data.

### 1. Pilot (one region, one year, per product)
`download_tcc_nlcd.py --regions NH --features nlcd --years <latest>
--force --out-dir /tmp/cr0035_pilot`, the same for `tcc`, and
`download_treemap.py --regions NH --vintages 2022 --force --out-dir
/tmp/cr0035_pilot_treemap`. Nothing under `data/` is written. Purpose:
prove Earth Engine accepts each source's native CRS as `crs` (the
`AEA WGS84` and `Albers_Conical_Equal_Area` WKTs, EPSG:5070) and record
the native grids and the run time. The registration itself is gated in
step 3.

### 2. Full re-download, in dependency order
1. `download_tcc_nlcd.py --features nlcd --force` (all regions, the
   default years);
2. `download_tcc_nlcd.py --features tcc --force` (its coverage check reads
   the new NLCD);
3. `download_treemap.py --force` (2016, 2020, 2022);
4. `generate_treemap_features.py --src-dir data/treemap_raw` (coverage
   from the new NLCD; same years as today).
The years written must equal the years backed up in step 0 (listed in
the evidence).

### 3. Registration gate
`diagnose_layer_registration.py --require-aligned nlcd tcc balive
tpa_live qmd carbon_dwn` must exit 0 (every one at (0, 0) in ME, NH and
VT). The LANDFIRE layers stay at (0, 0) (control). Recorded in full.

### 4. Split manifests and acceptance
1. Keep sha256 of every split CSV (`thinned_positives`,
   `train/val_positives`, `block_assignments.csv`, `candidate_pool.csv`,
   `negatives_*` + splits).
2. Re-run `prepare_training_data.py` then `generate_negatives.py`.
3. **Gate: every split CSV is byte-identical** to step 4.1 (no split
   input reads an Earth Engine layer's values: the window mask reads
   raster extents, which are unchanged, and the only sampled features are
   LANDFIRE's: `analyze_grouse.FEATURES`, `ENVELOPE_FEATURES`). Only
   `split_manifest.json` changes (new input digests).
4. `acceptance_split.py` must PASS; the standing checks then accept the
   new raster sizes/mtimes.

### 5. Evaluation (measurement, not keep/remove)
Retrain the current best recipe (`grouse_cr0031_wd3e3_wr` command) on the
repaired data with seeds 0, 1, 2; calibrate each; report mean TTA AUC, AP
and out-of-sample Brier against the same recipe and seeds on the backup
data (3 runs, from `data/backup_bug0094/` swapped back in under a
separate data root). The fix stands regardless of the result (it is a
correctness fix); the numbers are recorded in CHANGELOG.

## Impact
- **Every future training run** reads the repaired layers; patch caches
  rebuild automatically (their key includes each raster's mtime).
- **Existing checkpoints** were trained on the shifted layers; they still
  load and predict, but on repaired inputs they see data ~21 m from
  what they learned. Recommendation recorded with the evaluation result:
  retrain before the next published map.
- **Split files:** unchanged by construction (gate 4.3).
- **CR-0032:** its pilot grid check against the on-disk NLCD becomes
  valid again once step 3 passes.

## One change per CR (CR-0011 A5)
Data repair only (re-runs of existing scripts, one gate flag); the code
fix is CR-0034. The evaluation is measurement of this repair, not a code
change.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| A long re-download fails midway | Per-file atomic writes (unchanged); `--force` per feature/region re-runs only what is missing; backup kept |
| Earth Engine rejects a native WKT `crs` | Step 1 pilot before the full run |
| The split changes unexpectedly | Gate 4.3 (byte identity) fails; roll back from step 0 |
| Product versions moved since the first download (e.g. new NLCD/TCC years) | Years pinned to the backed-up list (step 2) |
| Deprecated TreeMap assets disappear | Not this CR (tracked); the backup keeps the old raw files |

## Test plan
- `tests/test_cr0035.py` (pre-approval): the registration gate passes
  aligned layers and fails a layer moved one cell and an unmeasured one.
- CR-0034's tests cover the download code.
- EC2 evidence for steps 0-5 as above.

## Deliverables
- [ ] 1. This CR and `tests/test_cr0035.py`, gate flag in
      `diagnose_layer_registration.py`; two independent reviews; approval.
- [ ] 2. Steps 0-2 on EC2 (after CR-0034 lands).
- [ ] 3. Gate 3 passes.
- [ ] 4. Gates 4.3 and 4.4 pass.
- [ ] 5. Evaluation recorded.
- [ ] 6. Bookkeeping: BUG-0094 FIXED, PA-0049, BUG_LOG, CHANGELOG,
      ARCHITECTURE (step 2 note), tracker; close-out.

## Out of scope
- Migrating TreeMap to `projects/gtac-data-publish/assets/TreeMap/
  Product_Version/2023-1` (tracked follow-up).
- Re-publishing maps made with old checkpoints.
- Making the registration gate a standing check before training (a
  follow-up CR candidate under PA-0049(b)).
