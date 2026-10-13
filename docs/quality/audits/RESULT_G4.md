# G4 verification results: audit findings #5, #10, #11, #17, #20 and the six follow-up boundaries

Audited commit: `472ba5e`. Working tree: `9b1f741` (HEAD). None of these files changed between the two commits: `regions.py`, `dataset.py`, `pretrain.py`, `analyze_grouse.py`, `generate_negatives.py`, `model_handler.py`, `calibrate.py`, `train.py`, `predict.py`, `acceptance_split.py` and `generate_road_distance.py`. Where a cited file did change, the change is noted below. Line numbers are the same at both commits unless stated.

Probes are in `probes/`:
- `g4_f5_overlap.py`
- `g4_f10_partial.py`
- `g4_f17_mem.py`
- `g4_add1_treemap_extent.py`
- `g4_add1_vrt_fill.py`
- `g4_add2_block_split.py`

Each probe calls the real repository function, either by import or by AST extraction.

What I could not run:
- Anything that needs torch: DataLoader memory, the SSL loop, `torch.save`.
- Anything that needs production data: no real `block_assignments.csv`, rasters, templates or sightings exist in this container. The files under `/tmp/acc_split_test_*` are test fixtures.

## Summary table

| # | Verdict | Severity: mine (auditor's) | Tracked ID | Disposition | Reason |
|---|---|---|---|---|---|
| 5 | ALREADY TRACKED (D1, D2, D3, D4), VALID; jitter and SSL parts VALID-LATENT | Medium (High) | D1–D4 in `CR-0007-0008-OPEN-ISSUES.md:239-243`; design competition V2/V6 and HYBRID §6 | No code change now. The user must decide on D1–D4. Add an OBS "core-val" metric, either with the D1 decision or in its own small CR. | Labels are isolated. Features and model selection are not. This biases the reported metrics, not the maps, and it is already acknowledged in the tracker. |
| 10 | VALID (partly superseded at HEAD for the downloaders) | Medium (High) | None as a class. Draft BUG-0028 is uncommitted and covers predict's fixed name. BUG-0016 covers tune's shared path. | Own CR: one shared staged-publish helper applied to about 9 writers, plus a BUG entry and a PA with a sweep. About 1–1.5 days. | A live-path `"w"` partial raster passes `_is_valid_raster` (reproduced). Checkpoints are overwritten in place. |
| 11 | PARTLY VALID | Medium (High) | Related: BUG-0060 (checkpoint split provenance), draft BUG-0028, PA-0048 (which deliberately scopes acceptance to split inputs) | Fold into the CR for BUG-0060: record the resolved feature/year/path/digest set in the checkpoint, and check it in train standing checks, predict and calibrate. About 1 day on top of BUG-0060. | The real gap is that no record of model-input provenance exists: `mch_*` rasters and new vintages are consumed unbound. The "acceptance should bind it" framing and the "tamper with the JSON" claims are weak. |
| 17 | PARTLY VALID | Low (Medium) | None | Trivial fix plus BUG entry: cap the default workers, for example `min(cpu-2, 16)`, and print the queue estimate. Under 0.5 day. | The arithmetic is right. "Exhaust RAM" does not hold for the recipe on GPU instance shapes, at about 0.2 GiB per vCPU against 4 GiB or more of RAM per vCPU. The other memory claims are minor. |
| 20 | ALREADY TRACKED (BUG-0037 residual, OPEN; CR-0014 A4), VALID | Low (Medium) | BUG-0037 §6 "Residual (open)"; CR-0014 review log A4 and X2 | No change. Keep it open until Canadian road data (NRN) exists. Optionally widen the over-mask (see below). | Measured residual: NH 6,884 px and VT 1,881 px (about 7.9 km² in total), against an upper bound of about 51k px. |
| A1 TreeMap source coverage | VALID (mechanism reproduced); exposure tiny or unverified | Low | None. Related: BUG-0025. | Trivial fix plus BUG entry: mask pixels outside the warped source footprint in `write_vintage`. | WarpedVRT fills outside a `nodata=None` source with 0. `_clean` does not flag it, so the pixel is written as non-forest under NLCD coverage. |
| A2 `block_split` schema | VALID-LATENT | Low | None | Trivial fix plus BUG entry: validate the table (non-empty, unique ids, labels in {train, val}). | Reproduced: an empty table makes every block train with no warning; for a duplicate, the last entry wins; `"VAL"` passes through unchanged. The production table is sha-checked. |
| A3 No-output SSL | VALID-LATENT | Low | None | Trivial fix plus BUG entry: refuse if `n_steps == 0` or `len(ds) < batch_size`. | `drop_last=True` with fewer tiles than a batch gives zero steps. The run still saves an "epoch" and only prints a collapse warning. SSL is not in the recipe. |
| A4 Edge diagnostics | ALREADY TRACKED (BUG-0058, OPEN), VALID | Low | BUG-0058 | As BUG-0058 already says: a one-function trivial fix | It affects the TensorBoard diagnostic only. |
| A5 Provenance dirty state | ALREADY TRACKED (BUG-0068, OPEN), VALID | Low | BUG-0068 | As BUG-0068 says: check the return codes, keep a tri-state; also count untracked `.py` files. Small CR or trivial fix. | A failed `git status` reads as clean. Untracked `.py` files are ignored. |
| A6 Source composition | ALREADY TRACKED (CR-0021 residuals, BUG-0073 §6), VALID as a caution | n/a (no defect) | Tracker § CR-0021: representative-year residual, wetland-guild CR | No new item | It restates open residuals. |

---

## #5: The spatial split does not isolate feature footprints or model selection

**Code.**
- Block geometry: `regions.py:45` sets `BLOCK_SIZE_M = 3000`. `regions.py:54` sets `VAL_FRACTION = 0.2`. `block_ids` is at `regions.py:239-251`.
- Assignment: `block_split` (`regions.py:270-286`) gives listed blocks their listed split. It gives any other block "val" when `md5 % 1e4 < vf*1e4`.
- The listed blocks come from `prepare_training_data.assign_spatial_blocks` (`:344-371`). It takes occupied blocks in hash order until 20% of the records are in validation. So "a random 20% of 3 km blocks" is a good approximation.
- Patch window: `dataset._read_patch` (`dataset.py:322-342`) reads rows `row-32 .. row+31`, which is 64 px or 1.92 km.
- Jitter: the read is `64 + 2*jitter` (`dataset.py:75-78`). The `train.py` default is `--jitter 0` (`train.py:614`). The recipe (Run B in `grouse_model_results_summary.md:129-132`) passes no `--jitter`, so in practice jitter is 0. `pretrain.py` defaults to `--jitter 8` (`:127`).

**Quantification.** `probes/g4_f5_overlap.py` calls the real `regions.block_ids` and `regions.block_split` (hash rule, vf = 0.2, a 60×60 block grid), samples 200k uniform centres, and applies the exact window convention.

| Measure | jitter 0 (recipe) | jitter 8 |
|---|---|---|
| Training-centred patches that contain any validation-block pixel | **29.6%** | 38.4% |
| Mean share of a training patch lying in validation blocks | **6.1%** (median 18.7% among those that touch) | 7.5% |
| Validation-centred patches that contain any training-block pixel | **76.5%** | 88.6% |
| Mean share of a validation patch lying in training blocks | **23.5%** (median 31% among those that touch) | 28.9% |
| Validation-block pixels inside the window of *some* training-centred patch | **76.9%** | — |
| Validation patches with at least 50% of their pixels reachable by a training patch | 86.7% | — |

Analytic cross-check: a 64 px patch stays inside its own 100 px block with probability (1 − 0.64)² ≈ 13%. So 87% of patches cross into a neighbouring block, and each neighbour is a validation block with probability 0.2.

Only 23.5% of validation patches lie entirely inside validation blocks. A "core-val" subset would therefore keep about a quarter of the validation rows.

These are geometric upper bounds on shared pixels. Realised sharing depends on how densely the positives (thinned to 30 m) and the `--an-background 1.0` draws sit near block edges. I could not measure that without the real tables.

D4 states the same mechanism in the tracker: "64 px window is about 1.9 km and the blocks are 3 km, so features leak across block edges. Labels do not."

**Design competition cross-check.**
- VOTE_REPORT V2 (`VOTE_REPORT.md:73`) computes the same edge geometry from the other side: 1 − 0.8⁸ ≈ 83% of a block's interior lies within 2.5 km of a held-out neighbour. A flat buffer would keep only 24–31% of the data.
- HYBRID (`HYBRID_REPORT.md:27,37,73`) adopts out-of-fold scoring over 24 km super-blocks with a "footprint + 0.5 km" edge buffer. That is the remedy the auditor proposes, but for the new model only.
- V6 (`VOTE_REPORT.md:77`) says hold-outs must come from `regions.block_split`, not from the CSV.
- HYBRID §6 (`:130`) lists both CNN leaks: checkpoint selection on the hold-out, and negative weights from all sightings. It marks the envelope path as "not yet traced". It is traced below.

**Envelope binners and selection weights: confirmed.**
- `analyze_grouse.py:880-889` fits `fit_scheme_binners(habitat, …)` on every non-nonveg sighting. `:905-918` computes `Selection_Ratio` from every sighting's envelope counts. `:1099-1100` writes `evaluated_sightings_{R}.csv` and `envelope_metrics_{R}.csv`. All of this happens before `prepare_training_data` assigns blocks.
- `generate_negatives.py:483-484` reads `envelope_metrics` and calls `attach_weights`.
- `attach_weights` (`:240-265`) refits the binners from the same all-sightings frame (`:251-252`). It then sets `weight = 1/clip(Selection_Ratio)` (`build_weight`, `:146-160`).
- `es_select` (`:282-298`) draws training and validation negatives by Efraimidis–Spirakis on that weight.

So validation positives, about 20% of each envelope's counts, shape the negative draw whether or not `--use-weights` is set (`train.py:561`, default off). The leak is aggregate, through envelope-level counts, not individual locations. The 300 m buffer also uses all sightings, which is D3.

**Model selection.**
- `--select-by rank` is the default (`train.py:935`) and selects on validation (`model_handler.py:1345-1358`).
- The divergence guard defaults to `warn` (`train.py:984`).
- `--dynamic-dropout` is off by default (`train.py:810-811`) and not in the recipe.
- Platt scaling is fitted on validation (`calibrate.py`). `cross_fitted_probs` uses random folds (`calibrate.py:229-239`).
- These are D1 and D2.

**Background sampler.** It checks only centre-block membership (`train.py:121-142`, via `block_split`). It does not check the footprint. The auditor cites this as `dataset.py:314-342`, which is a citation error: the sampler is in `train.py`.

**SSL.** `pretrain.py:190-200` passes `train_blocks_only=False`, and the comment claims no leak. The behaviour is transductive and real, but VALID-LATENT: the recipe does not use `--init-from` (`grouse_model_results_summary.md:291`).

**Exposure.** The split is reachable on every run. The recipe uses `--an-background 1.0` and selects by rank on validation. Labels are isolated, so this is not a label leak. The reported validation metrics are within-region, spatially blocked, and selection-biased. They are not external.

**Severity.** Medium, against the auditor's High. The maps are not corrupted, and the project already records the limitation as open decisions. The High rating would be fair only if someone presents the validation AUC as external generalisation.

**Disposition.** No code change from this audit. Escalate D1–D4 to the user for a decision; they have been open since CR-0015. A cheap step: report an OBS "core-val" metric on validation rows whose patch lies entirely in validation blocks (about 23% of rows), next to the full-validation metric. The real fix is the HYBRID super-block design for the new model. Retrofitting it to the CNN would be its own CR.

---

## #10: Outputs are truncated before replacement

**Reproduced.** `probes/g4_f10_partial.py` writes a good raster, then reopens the same path with `rasterio.open(path, "w")`, as the generators do. It writes 5% of the row blocks and then raises.
- The previous file is gone.
- The result is 5% data and 95% nodata.
- The real `RegionData._is_valid_raster` (`grouse_data.py:312-334`, `min_valid_frac=0.01`) returns **True**.

**Writers that open the live path in mode `w` or overwrite in place:**

| Writer | file:line (HEAD) | Consumed downstream? | Notes |
|---|---|---|---|
| TSD generator | `generate_time_since_disturbance.py:302-305` (472ba5e: `:302`) | yes (`tsd`, a split feature) | Opens every year's output before streaming blocks; widest window |
| TreeMap features | `generate_treemap_features.py:312-316` (472ba5e: `:312`) | yes (`balive`, `tpa_live`, `qmd`, `carbon_dwn`) | Block-streamed |
| Road distance | `generate_road_distance.py:367-375` | yes (`road_dist`) | **Not cited by the auditor.** One in-memory write per year, so a short window, but still the live path |
| Prediction map | `predict.py:1098-1105`; KMZ `predict.py:767,776` (`zipfile.ZipFile(output_kmz, "w")`) | product | Fixed name `{region}[_custom]_suitability.*`; overwrite and collision is draft BUG-0028 |
| Best checkpoint | `model_handler.py:1355-1357` (`torch.save(..., self.save_path)`) | yes (predict, calibrate) | Written on every improvement |
| Resume checkpoint | `model_handler.py:599-617` | `--resume` only (not in recipe) | Written every epoch |
| `save()` | `model_handler.py:1962-1964` | — | — |
| SSL backbone | `pretrain.py:275` | `--init-from` (not in recipe) | Written every epoch |
| Calibration | `calibrate.py:463-469` (`calibration.json`, `reliability.csv` with `open(..., "w")`) | yes (predict reads calibration) | — |
| Analysis outputs | `analyze_grouse.py:1099-1100` (`evaluated_sightings_*`, `envelope_metrics_*` via `to_csv`) | yes (split inputs) | Sha-pinned by acceptance, so a torn file fails loudly at acceptance |
| TCC/NLCD, no-template branch | `download_tcc_nlcd.py:577-578` (`shutil.copyfile(merged, out_path)`) | latent | Only when no LANDFIRE `evt` exists yet. A torn file would also be skipped as "exists" on rerun |
| Misc | `generate_canopy_structure.py:404` (pilot output); `tune.py:241`; `sightings.py:138`; `ebird.py:64` | diagnostic or acquisition | — |

**Writers that already stage and `os.replace`:**

| Writer | file:line | Notes |
|---|---|---|
| TreeMap raw download | `download_treemap.py:294-307` | Staged `.tmp`, then `os.replace`. Live at 472ba5e (`:331` wrote `out_path` directly). Changed in `d6db674` "CR-0034 implemented … CR-0035 approved"; the code comment cites CR-0035 review B35-3-1 |
| TCC/NLCD, template branch | `download_tcc_nlcd.py:575-576` | Already staged at 472ba5e (`:464-465`) |
| Canopy structure | `generate_canopy_structure.py:380, 428-485, 524-525` | — |
| Lidar structure (new, CR-0036) | `generate_lidar_structure.py:442, 689-694, 714-731` | Validates the grid before replace |
| Road-distance TIGER fetch | `generate_road_distance.py:144-166` | `.part` |
| Realign / repair | `realign_rasters.py:84-103`; `repair_coverage_rasters.py:231-239` | — |
| REV download | `download_rev.py:186` | — |
| Patch cache | `dataset.py:185-199` | — |
| Acceptance outputs | `acceptance_split.py:229-242` | No `fsync` of file or directory, as the auditor says |
| Split files | `prepare_training_data.py:220-235` (used by `generate_negatives.py:544-545`) | Fsyncs the file but not the directory, as the auditor says |

The auditor's durability point stands. Atomic visibility is not crash durability. That matters only on power loss or a kernel crash, so I rate it Low.

**Exposure.**
- Generators run whenever features are rebuilt, and recent CRs rebuild features often. The failure raises loudly, but the partial file stays behind and passes the content probe.
- For split features, the next `train.py` standing check fails on the size/mtime change (`acceptance_split.py:3186-3194`), unless acceptance is re-run first, and acceptance does not inspect raster content.
- `road_dist`, `tsd` and the TreeMap features are all live inputs.
- Checkpoint overwrites matter on EC2 if the process is killed during the few seconds of a `torch.save`, for example by spot interruption or the OOM killer. The recipe runs fresh with no `--resume`, so a torn resume file is latent. A torn best checkpoint would cost the run.

**Tracking.** No BUG or PA covers torn or live-path writes as a class. Related items:
- `DRAFT_BUG-0028-prediction-output-no-provenance.md` (repository root, not filed) covers predict's fixed path.
- BUG-0016 and PA-0014 cover shared mutable output paths, for diverged scripts only.

**Severity.** Medium, against the auditor's High. The failure is loud when it happens and gated for split features. The silent-acceptance path needs a rerun of acceptance after a failed generator.

**Disposition.** Own CR, because it touches several files and changes `predict.py`'s output naming:
1. One helper (stage in the destination directory, validate, fsync, `os.replace`, fsync the directory).
2. Apply it to the TSD, TreeMap, road-distance, predict, `model_handler` (three sites), `pretrain`, `calibrate` and `analyze_grouse` writers.
3. File a BUG entry and a new PA ("anything a later step consumes is published by stage-then-replace") with a sweep. A lint test grepping for `rasterio.open(<non-tmp>, "w")` and `torch.save(` is feasible.
4. Give predict output unique run names under BUG-0028's CR.

Estimate: about 1–1.5 days.

---

## #11: Standing acceptance does not bind the complete raster set

**Code.**
- `write_record` (`acceptance_split.py:3133-3152`) stores `rasters = [[rel, size, mtime_ns]]` for `ctx.raster_inputs`. These are the rasters the acceptance replay read (`:2343-2354`): the pinned `feature_spec_keys`, or `SPLIT_WINDOW_FEATURES`, at the split's record years, plus the envelope extraction.
- `standing_checks` (`:3155-3206`) loops over `rec.get("rasters") or []` and compares size and mtime only. Nothing requires the list to be non-empty or equal to what training will resolve.
- Training resolves `discover_features` (`train.py:107-118`), which is every `FEATURE_SPEC` feature on disk in all regions, and `rd.raster_path(feature, year)` with nearest-year fallback.

**Mechanism holds and is reachable at HEAD.**
- CR-0032 added `mch_mean`, `mch_f01`, `mch_f15` and `mch_f512` to `RASTER_FEATURES` (`grouse_data.py:157-164`, diff since 472ba5e) and to `FEATURE_SPEC` (`models.py:603`).
- `generate_canopy_structure.py` writes them. Once they are on disk, they enter training with no acceptance record entry.
- A new vintage, such as the TCC 2024–2025 migration item in the tracker, changes `raster_path` resolution for some years. The recorded old path is unchanged, so the check passes while training reads the new file.
- The checkpoint config stores feature names only (`model_handler.py` `_wrap_checkpoint`, around `:470-480`), not paths or digests.

**Claims that are weaker.**
- (a) The acceptance record binds split inputs by design. PA-0048 (`PREVENTIVE_ACTIONS.md:52`) and CR-0033 deliberately decoupled split inputs from `FEATURE_SPEC`, so a model feature does not change the split. So "acceptance should bind every consumed raster" mis-scopes what the record is. The real gap is that no artifact records model-input provenance.
- (b) Hand-deleting the `rasters` list from the record, or same-size replacement with mtime preserved, needs deliberate tampering or `cp -p`/`rsync -a` of an equal-size compressed GeoTIFF. That is a trust-model issue, not a likely accident.

**Tracking.** No direct ID. Adjacent items:
- BUG-0060 (OPEN): checkpoints carry no split provenance.
- Draft BUG-0028: prediction provenance.
- Tracker item: "NH `ch`/`cc` rasters … postdate … find what rewrote them". That is the same provenance class.

**Severity.** Medium, against the auditor's High. It is reachable now because `mch_*` exists and vintages are migrating. The effect is unattributed model inputs, not a wrong split.

**Disposition.** Fold into BUG-0060's CR:
- Record a resolved `{feature, year → path, sha256}` manifest in the checkpoint config.
- Have `train.py` compare it against the resolved set, and have predict and calibrate check against it.
- Optionally cache hashes by (path, size, mtime) for speed.

Estimate: about 1 day beyond BUG-0060's scope.

---

## #17: Default worker and prefetch counts can exhaust RAM

**Defaults.**
- `train.py:104`: `WORKERS = max(1, (os.cpu_count() or 4) - 2)`, the `--workers` default at `:557`.
- `model_handler.py:46-52`: `prefetch_factor = 4`.
- Both the train and validation loaders use `num_workers=workers`, `persistent_workers=True` and `pin_memory` (`model_handler.py:772, 799-829`). That makes 2W persistent worker processes. The two prefetch queues are not filled at the same time, because the iterators run in sequence.
- Batch tensors: `cat_x` int64 and `cont_x` float32, at 64×64 (`dataset.py:391-414`).
- The default `--cache-dir data/cache` (`train.py:611`) means workers read a shared memmap, not GDAL. So per-worker GDAL block caches are not the risk.

**Formula.** W = max(1, nproc − 2). Peak bytes queued by the train loader:

> Q ≈ W × 4 × B × 64² × (8·N_cat + 4·N_cont)

Add transient pinned copies of in-flight batches, roughly the same order. Add 2W persistent worker processes at an unmeasured base RSS each.

With the recipe's B = 128, N_cat = 6 (`evt`, `evh`, `evc`, `sclass`, `fdist`, `nlcd`) and N_cont = 13 (9 split continuous features plus 4 `mch_*`), each batch is 50 MiB, so **Q ≈ 0.195 GiB × W**.

`probes/g4_f17_mem.py`, which reads the real defaults:

| nproc | 8 | 16 | 32 | 48 | 64 | 96 | 128 | 192 |
|---|---|---|---|---|---|---|---|---|
| B=128, 19 features | 1.2G | 2.7G | 5.9G | 9.0G | 12.1G | 18.4G | 24.6G | 37.1G |
| B=256, 19 features | 2.3G | 5.5G | 11.7G | 18.0G | 24.2G | 36.7G | 49.2G | 74.2G |
| B=512, 19 features | 4.7G | 10.9G | 23.4G | 35.9G | 48.4G | 73.4G | 98.4G | 148.4G |

The auditor's 4+10 composition at B=256 and 128 vCPU gives 35.4 GiB, so the auditor's arithmetic is right.

**Judgement.**
- GPU EC2 shapes carry about 4 GiB of RAM per vCPU or more. Examples: g5/g6.4xlarge, 16 vCPU and 64 GiB; g5.48xlarge, 192 vCPU and 768 GiB; p4d, 96 vCPU and 1,152 GiB.
- The recipe queue is about 0.2 GiB per vCPU, roughly 5% of RAM. At B=512 it is about 20%.
- CHANGELOG.md:537-546 records "14 workers" on the training box. If that was the default, nproc = 16 and Q ≈ 2.7 GiB.
- "Exhaust RAM" is therefore overstated for the recipe. It is plausible only with large batches on a memory-lean host, or because of the unmeasured RSS of 2W persistent processes.

**Other claims in #17.**
- `_is_valid_raster` reads the whole band (`grouse_data.py:325`): true. It runs once per path, in the main process. ME is about 196 Mpx, so roughly 0.4 GB int16 plus a mask. This is transient.
- The download mosaics are one-off acquisition steps of a few GB.
- The predict strip `coords` list (`predict.py:336-338`) is per strip, not per map. Measured: 1.5 M tuples = 95 MiB at the default stride of 4, and 1.5 GiB at stride 1. The strip's feature array, about 2,111 × width × 19 × 4 B, is larger than the list.

**Tracking.** None found.

**Severity.** Low, against the auditor's Medium.

**Disposition.** Trivial fix plus BUG entry, confined to `train.py` and `pretrain.py` defaults. Cap the default, for example `min(nproc-2, 16)`, since the CHANGELOG measured 6× loader headroom at 14 workers. Print Q at start-up. Under half a day.

---

## #20: Canadian land outside the template

**Code.**
- `generate_road_distance.py:224-291`: roads are rasterised on the padded grid (`:248-252`). The distance transform runs on the padded grid and is then cropped (`:262-264`).
- The coverage mask (`:268-271`) and the Canadian `land` mask (`:279-280`, from the template-grid `evt`) exist only on the unpadded template.
- With `land.any() == False` the Canada rule is skipped (`:281`).
- The mechanism is exactly as the auditor describes.

**Tracking.** BUG-0037 §6 records "**Residual (open):** Canadian land beyond the grid edge is not seen":
- Measured NH 6,884 px and VT 1,881 px; ME 0.
- `check_road_dist.py` X2 gives an upper bound: ME 8,522, NH 24,841, VT 17,804.
- BUG-0037's status line is "FIXED within the grid (CR-0014); edge residual OPEN". CR-0014's review log (A4) accepted this as a stated residual.

**Exposure.** Every `road_dist` raster carries it. The measured residual is about 8.8k px, roughly 7.9 km² across NH and VT edges. That is about 1% of the in-grid Canada effect CR-0014 fixed.

**Severity.** Low, against the auditor's Medium.

**Disposition.** No new item. The residual closes with Canadian roads (NRN), as BUG-0037 says. An optional conservative interim, which needs a CR because it changes data:
- Rasterise US coverage on the padded grid.
- Treat every non-US padded cell as potential land (ocean over-masks along the ME coast).
- Mask US cells nearer to that area than to a road.

---

## Additional boundaries

**A1. TreeMap source coverage** (`generate_treemap_features.py:264-274, 277-330`).
- `probes/g4_add1_vrt_fill.py` puts a float32 source with `nodata=None`, which is how `download_treemap.py:298-304` writes it, under a WarpedVRT onto a wider grid. Outside the source, the VRT reads **0.0**. The real `_clean` does **not** flag it, so it is written as 0 (non-forest) wherever NLCD has coverage (`:319, :336`).
- Exposure: `probes/g4_add1_treemap_extent.py` uses the real `region_grid` (corners plus a 2 km pad, snapped). It shows that the densified `BOXES` sit inside the clip with about 2 km to spare. Against an *assumed* local-Albers template, which is LFPS-like but whose parameters I could not obtain, 0.09% (ME) and 0.01% (NH, VT) of template cells fall outside the clip, all at corners and outside the lon/lat box. Many of those cells are in Canada or the ocean, where NLCD is nodata.
- The hand-downloaded CONUS path, where a source's declared nodata could be a positive value below 1e9, is latent.
- Verdict: VALID, exposure tiny or unverified. Severity Low.
- Fix: inside `write_vintage`, mark pixels outside the warped source footprint as invalid, using `WarpedVRT(..., add_alpha=True)` or a warped all-ones mask, and honour the declared `src.nodata` before `_clean`. That is one function, so a trivial fix plus a BUG entry.

**A2. `block_split` schema** (`regions.py:270-286`). `probes/g4_add2_block_split.py`, using the real function:
- An empty table gives `vf = NaN`, every block "train" and no warning.
- Duplicate `A` (val, then train) gives "train"; the last entry wins.
- An invalid label `"VAL"` is returned unchanged.

The production `block_assignments.csv` is written by `prepare_training_data` and sha-checked by `standing_checks`, so this is VALID-LATENT, Low. Trivial fix plus BUG entry: validate the input.

**A3. No-output SSL** (`pretrain.py:205-218, 237-290`).
- `drop_last=True`. If `len(ds) < --batch-size` (default 256), then `n_steps = 0` and `mean_std = 0`, which prints a collapse warning.
- `torch.save` still writes a backbone labelled with `epoch`. That backbone is the initialisation, which with ImageNet init is pretrained but not SSL-trained.
- It needs `--tiles` of about 85 or fewer per three regions, or a nearly empty sampler. Read but not run (no torch).
- VALID-LATENT, because SSL and `--init-from` are not in the recipe. Low. Trivial fix: refuse when `n_steps == 0`.

**A4. Edge diagnostics** (`predict.py:369-380`).
- Categorical `!=` counts transitions to and from `MISSING_CODE`. `torch.nan_to_num` turns continuous NaN into 0.
- BUG-0058 (OPEN, "trivial-fix candidate, diagnostic only") covers it exactly. ALREADY TRACKED, Low.

**A5. Provenance dirty state** (`acceptance_split.py:170-182`).
- The return codes of `rev-parse` and `status` are ignored. A failed `git status` gives empty stdout, which reads as clean; on EC2, a "dubious ownership" error is a realistic cause.
- Only tracked `.py` changes count. Untracked `.py` files and quoted paths are ignored. `prepare_training_data.git_state` (`:298-314`) uses `check=True`, so it fails closed, but it also ignores untracked files.
- BUG-0068 (OPEN) covers the tri-state collapse and the "failed git status reads as clean" case. The untracked-source point is new and minor. ALREADY TRACKED, Low.

**A6. Source composition.** This restates open residuals:
- The representative-year rules differ (tracker § CR-0021, residual 1).
- The wetland-guild share differs between 2020–22 and 2023–24, and a follow-up CR is pending (residual 2).
- The envelope-metric epoch item is in tracker § CR-0019.

It is a valid caution, not a new defect. ALREADY TRACKED.
