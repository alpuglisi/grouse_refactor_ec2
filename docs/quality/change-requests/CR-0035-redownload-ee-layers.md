# CR-0035: re-download the Earth Engine layers on the source grid, re-accept, measure

**Status: APPROVED WITH FOLLOW-UPS (v4), 2026-10-05** — round 3 approved
v3 (both reviewers and the author); v4 applies the follow-ups. CR-0034's
code is in (`download_tcc_nlcd`, `download_treemap`, exact warps). Depends on CR-0034 (code). Verdicts and dispositions:
`CR-0035-review-log.md`. This document states only current intent.

## Scope
Replace every on-disk Earth Engine layer file (`nlcd`, `tcc`, `balive`,
`tpa_live`, `qmd`, `carbon_dwn`, every region and year, and the raw
TreeMap files) with a CR-0034 download, regenerate `tsd` with the exact
warp, prove each file is registered
with its source, regenerate the split manifests and re-accept the split
(split files unchanged), and measure the effect on the model.

## Fixes
BUG-0094, BUG-0095 and BUG-0096 (data half; the code half is CR-0034).

## Why now
The six layers are ~half a cell off in every region
(`evidence/CR-0032/layer_registration_sweep.txt`); every trained model
reads them; CR-0032's canopy layers need a registered NLCD.

## The change
All steps on the EC2 host, run by the user from `~/grouse2`; every output
is committed to `docs/quality/evidence/CR-0035/`.

### 0. Snapshot and clear
1. `cp -al data data_before_bug0094` - a hard-linked snapshot of the whole
   tree (no extra space; sizes and mtimes preserved, so its own
   `acceptance_record.json` still validates; re-downloads replace files by
   `os.replace`, which leaves the snapshot's inodes untouched). Record
   `find data_before_bug0094 -type f -print0 | sort -z | xargs -0
   sha256sum > snapshot.sha256` (evidence) and re-verify it with
   `sha256sum -c --quiet snapshot.sha256` before step 3's snapshot run,
   before the "before" arm and before any rollback (a shared inode can be
   changed by an in-place write in either tree).
2. `git worktree add ~/grouse2_before HEAD` and `ln -s
   ~/grouse2/data_before_bug0094 ~/grouse2_before/data`: a repository root
   whose `data` is the snapshot (used in steps 3 and 5).
3. Record, per region, the years on disk of each in-scope feature and the
   raw TreeMap file list (`inventory_before.txt`), and the collection id
   each NLCD/TCC file came from where known (none are tagged today; the
   pilot prints what `resolve_collection` picks now).
4. Delete the in-scope files from `data/landfire/` and
   `data/treemap_raw/` (`rm`; the snapshot keeps them). A missing file now
   means "not yet re-downloaded", so a rerun without `--force` does
   exactly the remaining work.

### 1. Pilot
- `download_tcc_nlcd.py --regions NH --features nlcd --years <latest NH
  year>`, then `check_layer_registration.py --regions NH --skip-treemap`
  on that one file; and `download_treemap.py --regions NH --vintages 2022
  --out-dir /tmp/cr0035_pilot_treemap`.
- Records: the chosen collection ids and native grids; one
  `ee.Image.pixelCoordinates(native projection)` tile fetched on the
  native lattice (`diagnose_fetch_tile_offset.py --native`) with every
  centre within 0.01 m; the PROJ pipeline from the native CRS to the
  template (`Transformer.from_crs(...).description`); the time per tile.
- The TCC pilot is not run separately: its coverage check reads the new
  NLCD, which exists only after step 2.1 (it runs first in step 2.2).

### 2. Re-download, in dependency order, years pinned
Per region R, with `Y_feat(R)` the years and `V(R)` the TreeMap vintages
recorded in step 0.3 and `C_feat`
the collection id recorded in step 1:
1. `download_tcc_nlcd.py --regions R --features nlcd --years Y_nlcd(R)
   --collection C_nlcd`
2. `download_tcc_nlcd.py --regions R --features tcc --years Y_tcc(R)
   --collection C_tcc`
3. `download_treemap.py --regions R --vintages V(R)`
4. `generate_treemap_features.py --src-dir data/treemap_raw --regions R
   --years Y_treemap(R)`
5. `generate_time_since_disturbance.py --regions R --years Y_tsd(R)` (the
   exact warp, BUG-0096; it always rewrites its outputs, so `tsd` is not
   deleted in step 0.4, only snapshotted)
The inventory after step 2 must equal step 0.3's (`inventory_after.txt`);
every new NLCD/TCC/raw TreeMap file carries `GROUSE_GRID=native-lattice`.

### 3. Registration gate (per file)
`check_layer_registration.py` must exit 0: every in-scope file, every
year, at least `MIN_EQUAL` of its sampled cells equal to the independent
reference (the script owns its constants and method: Earth Engine point
samples of the source at native scale for NLCD/TCC and the raw TreeMap
files; each derived TreeMap layer rebuilt from its own raw attributes as
`generate_treemap_features` builds it). The
same script run on the snapshot must exit 1 and report at least as many
files as the inventory (`check_layer_registration.py --data-root
~/grouse2_before --collection-nlcd C_nlcd --collection-tcc C_tcc`); its
"at BUG-0094 offset" column must be high there and low on the repaired
files, which attributes the failure to the shift rather than to a
version change.
**Pilot decision rule (pre-stated):** if a repaired file in step 1 scores
below `MIN_EQUAL`, the near-edge column decides: mismatches mostly within
`EDGE_M` of a source pixel edge mean placement jitter (datum or warp), and
the remedy is a code change under its own CR, never a lower bar;
mismatches away from edges mean misregistration (stop; diagnose). `diagnose_layer_registration.py` is run as
corroboration (OBS, not a gate; weak-signal layers are not measurable by
road contrast).

### 4. Split manifests and acceptance
1. Re-run `prepare_training_data.py` then `generate_negatives.py` (no
   flags).
2. **Gate:** `check_split_unchanged.py --old
   data_before_bug0094/pipeline/split_manifest.json` exits 0: the 20
   digested split artifacts (`acceptance_split.digested_paths`) are
   byte-identical on disk and in the new manifest. (No split input reads
   an Earth Engine layer's values: the window mask reads raster extents,
   unchanged; the sampled features are LANDFIRE's.)
3. `acceptance_split.py` must PASS. Expected and accepted: the OBS rows
   that use `tcc`/TreeMap values report fresh numbers or "references
   stale" (OBS never block); the standing checks then accept the new
   raster sizes/mtimes.

### 5. Evaluation (measurement, not keep/remove)
- **After:** the current best recipe (`grouse_cr0031_wd3e3_wr` command)
  with seeds 0, 1, 2 in `~/grouse2` (repaired data); calibrate each.
- **Before:** the same commands and seeds run in `~/grouse2_before`
  (step 0.2; `train.py` reads `./data`, the snapshot), after re-verifying
  `snapshot.sha256`.
- Report mean TTA AUC, AP and out-of-sample Brier per arm. The fix stands
  regardless (a correctness fix). The "after" arm is also CR-0032's base
  arm (CR-0032 deliverable 4 runs after this step).

### Rollback
Verify `snapshot.sha256`, then roll back the whole tree: `mv data
data_failed_bug0094 && cp -al data_before_bug0094 data`. Every file - the
rasters, the split CSVs, `split_manifest.json`, `acceptance_record.json`
- returns to its pre-repair bytes, sizes and mtimes, so the old
acceptance record validates without re-running acceptance.

## Impact
- **Every future training run** reads the repaired layers; patch caches
  rebuild automatically (their key includes each raster's mtime).
- **Existing checkpoints** were trained on the shifted layers; recommended
  retrain recorded with the evaluation.
- **Split files:** unchanged (gate 4.2).
- **Coverage repairs (CR-0010):** LANDFIRE coverage masks repaired from
  the shifted NLCD footprint keep a half-cell edge residual at borders and
  coasts; accepted here, tracked (re-running the CR-0010 repair is its own
  change).
- **CR-0032:** its pilot grid check against the on-disk NLCD becomes valid
  after gate 3.

## One change per CR (CR-0011 A5)
Data repair and its gates (re-runs of existing scripts, two read-only gate
scripts); the code fix is CR-0034. The evaluation measures this repair.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| A run fails midway | Files cleared in step 0.4, so missing = to do; `download_tcc_nlcd` and `download_treemap` write atomically (stage + `os.replace`), so a file under its final name is complete; `generate_treemap_features` and `generate_time_since_disturbance` always rewrite their outputs (re-run them after any interruption) |
| Earth Engine rejects a native WKT `crs` | Step 1 pilot |
| Product versions moved since the first download | `--collection` pins the id recorded in step 1; `--years` pins the years; inventories compared |
| The split changes | Gate 4.2 fails; rollback |
| A file still misregistered (any year) | Gate 3, per file, shown to fail on the snapshot |
| Deprecated TreeMap assets disappear | Not this CR (tracked); the snapshot keeps the old raw files |

## Test plan
- `tests/test_cr0035.py` (pre-approval): the road sweep's `--require-
  aligned` mode; `check_layer_registration` passes a registered template
  file and raw file and fails the BUG-0094-shifted versions (SE tie; raw
  also NW tie); its BUG-0094-offset diagnostic separates the two; derived
  TreeMap layers rebuilt exactly as the generator does (including
  harvested plots with down wood but no live basal area) pass and fail
  against a shifted raw; `check_split_unchanged.compare` passes identity
  and fails a changed file, a missing file and a missing digest.
- CR-0034's tests cover the download code.
- EC2 evidence for steps 0-5.

## Deliverables
- [x] 1. This CR, `check_layer_registration.py`, `check_split_unchanged.py`,
      `tests/test_cr0035.py`; two independent reviews; approval (round 3).
- [ ] 2. Steps 0-2 on EC2 (after CR-0034 lands), inventories equal.
- [ ] 3. Gate 3 passes on the repaired data and fails on the snapshot.
- [ ] 4. Gates 4.2 and 4.3 pass.
- [ ] 5. Evaluation recorded.
- [ ] 6. Bookkeeping: BUG-0094/0095/0096 FIXED, PA-0049, BUG_LOG, CHANGELOG,
      ARCHITECTURE (step 2 note), tracker; close-out.

## Out of scope
- Migrating TreeMap to `projects/gtac-data-publish/assets/TreeMap/
  Product_Version/2023-1` (tracked).
- Re-running the CR-0010 coverage repair (tracked).
- Re-publishing maps made with old checkpoints.
- A standing registration check before training (PA-0049(b) follow-up).
