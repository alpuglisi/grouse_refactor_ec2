# CR-0020: Fit the negatives' envelope weights on training-block sightings only, so the validation negatives are drawn independently of the validation positives

**Status: v3, 2026-09-30 — APPROVED by agent quorum (CLAUDE.md §1.4; round 2: reviewers A and B both APPROVE WITH FOLLOW-UPS, conditional on the input binding and the availability-value check being in the operative text; met in v3 §2 Step 0/Manifest and §3 E15b). Nothing has been implemented; no data has been touched; implementation waits for the lead's go-ahead and a data host.** Review log: `CR-0020-review-log.md`.

## Scope
Compute `Selection_Ratio` and the envelope binners from habitat sightings in **training** blocks only, use those weights for both draws, record the rule in the manifest, and gate it by exact replay (BUG-0076; tracker D3).

## Why now
BUG-0076: `analyze_grouse.py:881-923` fits the envelope metrics on every sighting before the split exists, and `generate_negatives.py:247-259`, `:466-469` draws the validation negatives with the resulting weights, so validation negatives are steered away from the envelopes the validation positives occupy. Every validation metric, checkpoint selection (`--select-by rank`), the divergence guard, `--dynamic-dropout` and the Platt fit consume that set. The size of the effect is unknown (the review environment has no data); measuring it is a deliverable (§4).

## The change
### 1. Root cause
As BUG-0076 §5: the statistics that parameterise the negative draw are fitted once on the whole sighting set and applied to the validation draw; no rule or gate covered holdout self-dependence. PA-0033 states the rule; this CR implements it.

### 2. Pipeline (normative; amends CR-0012 §2 pool step 9 and CR-0007's availability sample)
**Ordering.** `analyze_grouse.py` runs before `prepare_training_data.py` writes `block_assignments.csv`, so the split is unknown when the all-sightings `envelope_metrics_{R}.csv` is written. The metrics that drive weighting therefore move to `generate_negatives.py`, which runs after both.

**Step 0. Availability sample carries its feature values.** `analyze_grouse.background_envelope_sample` (`:467-556`) writes, for every background point, the sampled `evt`, `evh`, `sclass` (the features it samples, `needed` at `:479-482`), the derived `evt_phys`, and the raster year used per feature (`year_evt`, `year_evh`, `year_sclass`) alongside today's `longitude, latitude, used, envelope_id` (a superset schema of `availability_sample_{R}.csv`; `check_partition.py` P5 reads `longitude, latitude, used, envelope_id`, `:482-492`, and is unaffected). The values are taken from `bg[feat]` and the chosen year **joined by row index** to `points` (`bg` is filtered by `dropna` at `:524` and the non-veg rule at `:541`, so a positional copy would misalign rows). Downstream binning of the sample, in the pipeline and in the replay, uses these recorded values and never re-samples rasters, so no vintage rule has to be reproduced; E15b (§3) verifies the recorded values against the rasters.

**Shared metric function.** `analyze_grouse.py` gains `envelope_metrics_table(habitat, availability, binners)` returning the `Envelope, Sightings, Avail_N, Used_Pct, Avail_Pct, Selection_Ratio, Classification` frame exactly as `analyze_region` computes it today (`:892-933`; constants `MIN_AVAIL_BG`, `SELECT_W_HI`, `SELECT_W_LO`), rows ordered by `Envelope` ascending; it raises if `availability` is empty, and `analyze_region` calls it only inside its `bg_counts is not None` branch (today's no-availability fallback at `:974-985` is kept). Its own outputs keep their content (S and the all-sightings table become diagnostic only for the metrics).

**Step 1. The fitting set (one definition).** For region R, `habitat_R` = every row of `evaluated_sightings_R.csv` (S; every year from `START_YEAR`, thinned-away and windowless rows included, consistent with CR-0019 §2 "the envelope metrics still use every sighting year") with `nonveg_landcover == False` whose block id `regions.block_ids(*regions.to_5070(lon, lat))` is `"train"` under `block_assignments.csv` via `regions.block_split`. A block absent from the file follows the hash rule, as for candidates; S rows in hash-"val" blocks are excluded although no validation positive lives there (conservative, harmless).

**Step 2.** Binners: `fit_scheme_binners(habitat_R, ENVELOPE_SCHEME)` (EVH quantile edges from `habitat_R` only).

**Step 3.** Availability: `availability_sample_R.csv` rows with `used == True`, re-binned from their recorded feature values with the step-2 binners; `Avail_N` per envelope as today. `generate_negatives.build` reads the file through `read_csv(digest(rd.path("availability_sample")))` (its own pattern, `:350-352`, `:409`), so its digest enters the manifest.

**Step 4.** `metrics_train_R = envelope_metrics_table(habitat_R, availability_R, binners)`, written to `PATH_TEMPLATES["envelope_metrics_train"] = "data/pipeline/envelope_metrics_train_{region}.csv"` (rows by `Envelope` ascending, the canonical order E0/E15 use).

**Step 5.** `attach_weights` uses `metrics_train_R` and the step-2 binners for the candidates' `envelope_id`, `weight` and `weight_basis`; the NonVeg rule, `build_weight`, `W_FLOOR`/`W_CAP`/`NONVEG_MAX_FRAC` are unchanged. `generate_negatives.py` no longer reads `envelope_metrics_R.csv`.

**Step 6.** The draw (step 11) is unchanged in code: both splits use `weight`, which now depends on training-block sightings only.

**Manifest.** The negatives section of `split_manifest.json`: `outputs` gains the three `envelope_metrics_train_R.csv` digests; `inputs` drops `envelope_metrics_R.csv` and gains the three `availability_sample_R.csv` digests; a field `"weights_fitted_on": "train_blocks"` and, per region, the number of `habitat_R` rows.

**Buffer (pool step 6) unchanged.** It still tests every sighting, validation included: it removes candidates near validation positives rather than steering the draw by label. Recorded as an accepted deviation in PA-0033's Swept? cell (deliverable 8); D3's second half stays open.

### 3. Acceptance (amends CR-0013; normative for the replay author)
- **Config** (`docs/quality/acceptance_split.json`): `envelope.binners_fitted_on` → `"train_block_habitat_rows"`; `paths` gains `envelope_metrics_train` and `availability_sample` (the latter is also needed by CR-0029's O12; whichever CR lands first adds it); `columns` gains `availability_sample` (the Step 0 columns, `year_*` included) and `envelope_metrics_train` (for E0's header check); `row_order` gains `envelope_metrics_train` (by `Envelope`); `comparison.rule` gains "envelope tables keyed on `Envelope`"; `manifest_schema.outputs` gains the new file, `manifest_schema.inputs` names the availability sample, and `manifest_schema` gains `weights_fitted_on`; the negatives `inputs` list drops `envelope_metrics` and gains `availability_sample`, and E11's required input kinds (`acceptance_split.py:2104-2110`) change the same way, so the sample is digest-bound like every other input (E11(a)). `digested_paths` gains the three tables (derived, not pinned by number; CR-0024 derives it from the standing list plus `candidate_pool`, and this CR's three files are appended after that) and E0/E11(d)/`write_record` follow it. Pins updated: `GATE_SECTION_SHA256` for `paths`, `envelope`, `columns`, `row_order`, `comparison`, `manifest_schema`; `GATE_IDS` and its length; `standing` unchanged.
- **Replay.** `annotate` (`acceptance_split.py:719`) builds `habitat_R` from S and the replay's **own recomputed** block table (`Replay.assign_split` already uses `self.B`, never the file), refits the binners, re-bins the recorded availability rows from their recorded feature values, and recomputes the metrics table with the config constants. E10's reference becomes this train-only recomputation (it therefore depends on the replay's positives stage succeeding; a positives-stage failure reports E10 as missing, as today for R-gates).
- **New gate E15 (exact).** The pipeline's `envelope_metrics_train_R.csv` equals the replay's table, rows keyed on `Envelope`, every column compared, floats under `comparison.float_rel_tol`. (The C and N rows' `envelope_id`, `weight`, `weight_basis` are compared by R3/R4 and the amended E10; E15 does not repeat them.)
- **New check E15b (exact; PA-0021(e)).** For every availability row with `used == True`, the replay re-samples `{R}_{year_<feat>}_{feat}.tif` at the recorded coordinates through `Rasters.sample` (as `Replay.extract` does for C, `:1183-1197`) for `evt`, `evh`, `sclass`, recomputes `evt_phys` from `evt` through the pinned crosswalk (as `annotate` does for C, `:727`), and requires equality with the recorded values (NaN equals NaN). The vintage **choice** (`:494-507`) is not verified by E15b: recorded as an accepted gap with owner lead in the tracker (deliverable 8). Attack row: a sample whose `evh` column is shifted by one row → FAIL.
- **Replay unit test (not a gate).** With the block table held fixed, the replay's table is unchanged when every validation-block S row is deleted from the fitting input only (not from `Replay.sightings()`, whose change would move the replay's own B); true by construction of the filter, so it tests the replay, not the pipeline.
- **Attack rows** (`tests/test_acceptance_split.py`, PA-0021(a); built by the reviewer, not the author): (i) weights fitted on all S rows (today's pipeline) → E15 FAIL; (ii) fitted on validation-block rows only → FAIL; (iii) binners on all rows, metrics on training rows → FAIL; (iv) availability re-binned from the old recorded `envelope_id` instead of its feature values → FAIL; (v) the intended pipeline → PASS. The fixture writer asserts that the train-only EVH edges differ from the all-rows edges (`fit_scheme_binners`, `:418-432`, integer EVH), otherwise (iii) and (iv) pass by coincidence.
- **Pre-registration (PA-0021(b),(e)).** A `Replay` subclass with a control (CR-0019 `preregister.py` pattern), run on the live tree after deliverable 5's `analyze_grouse.py` run (so the sample carries its feature columns) and before `generate_negatives.py`, records per region: the `habitat_R` row count, the `Landscape-Rare`/`Neutral` share and the share of envelopes at `Selection_Ratio == 0` (used only by validation positives; weight `1/W_FLOOR`, numerically `W_CAP`, `generate_negatives.py:154`), and the set of `candidate_pool.csv` rows (5 dp key) whose `weight` changes; the live run must reproduce them exactly (MC). The control is the pre-CR replay code under the pre-CR config and shows that it reproduces today's C on keys, split **and** `weight`.
- **OBS O13 (PA-0021(f)).** Envelope-only separability of the validation set: AUC of `Selection_Ratio_train(envelope_id)` as a score over validation rows, with P re-binned from its recorded `evh` under the train-only binners. Class: validation P vs N; subset: per region and pooled; null: the same statistic over `obs.n_perm` label permutations. Reported before and after; not a gate. The id presumes O11 (CR-0030) and O12 (CR-0029) land first; otherwise the next free id is taken and this CR's text updated.

### 4. What the change does to the data (pre-registered)
Every `weight` in `candidate_pool.csv` can change, and with it both splits' draws (the Efraimidis-Spirakis keys are coordinate hashes, so only weights move). Positives, block assignments and the buffer do not change. `availability_sample_R.csv` gains columns (a re-run of `analyze_grouse.py` with fixed seeds); S is expected byte-identical: deliverable 5 records the sha256 of the three S files before and after that run and aborts on any difference, and E11 binds S's digest through the positives manifest `inputs` (`prepare_training_data.py:373`, `acceptance_split.py:2160`). P's `envelope_id`/`env_zone` in S remain all-sightings diagnostic columns (not consumed on the training path); no gate compares them to N's (E9/E10 read C and N only).

## Alternatives considered
- **Neutral weights for the validation draw:** removes the dependence but changes the validation design away from the training design; rejected as primary, available to the reviewer.
- **Fit on training positives inside `analyze_grouse.py`:** impossible without inverting the pipeline order.
- **Accept D3 as a documented limitation:** rejected; the leak is into the number that selects checkpoints and fits the calibration.

## Impact
- `availability_sample_*` (new columns), `negatives_*`, `train/val_negatives_*`, `candidate_pool.csv`, the new `envelope_metrics_train_*`, `split_manifest.json` and `acceptance_record.json` regenerate; `standing_checks` refuses training on the old record until acceptance is re-run.
- Validation metrics before and after are not comparable; `calibration.json` is invalid until a retrain and re-calibration (follow-up CR; BUG-0060).
- **PA-0042 consumers of `weight`, `weight_basis`, `envelope_id` (C/N):** `dataset.py:87-89` (passthrough, unchanged), `grouse_data.training_frame` (fillna, unchanged), `model_handler.py:445-447` + `train.py:487` (`--use-weights`, CR-0027), `acceptance_split.py` E9 (counts by `is_nonveg`, `:1979`; unchanged), E10 (reference changes as §3), O6 (reads `weight_basis`, `:2493-2501`; unchanged), `smoke_test_training.py` (prints one weight). Readers of `envelope_metrics_R.csv` (all-sightings table, now diagnostic): `check_partition.py` P5, `organize_project.py`, `tune_bins.py`; `diagnose_*` do not read it. P's columns: unchanged producers.
- CR-0013 gains E15, E15b and O13; CR-0012 §2 and CR-0007 (availability sample schema) gain pointers; ARCHITECTURE.md stage 5 gains one sentence.

## One change per CR (CR-0011 A5)
Generator code, the availability schema, acceptance and regeneration cannot land separately: the code without the replay fails R1–R4; the replay without the code fails E15 on today's files; the schema change is what makes the replay possible. Bookkeeping closes BUG-0076. The retrain is split out. **Landing order with CR-0029** (area-uniform draw): CR-0029 changes only the draw and inherits this schema; if CR-0029 lands first, its acceptance re-run rewrites the sample and this CR's step 0 is a no-op on the draw; if this CR lands first, CR-0029's rebuild re-runs this CR's acceptance. Either order; each CR's replay reads the sample on disk; `paths.availability_sample` is added by whichever lands first. **With CR-0024:** `digested_paths` is derived (standing list + `candidate_pool` + this CR's three tables), so the two CRs compose in either order.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Replay and pipeline disagree on `habitat_R` | Both derive it from S and a block table computed by `regions.block_split`; the replay recomputes B; E15 exact; attack rows (i)–(iv) |
| Recorded availability values wrong (misaligned or wrong vintage) | E15b re-samples the rasters at the recorded year; the vintage choice itself is the recorded accepted gap |
| Fewer habitat rows per envelope (training blocks only) push more envelopes under `MIN_AVAIL_BG`/into singletons; envelopes used only by validation positives get `Selection_Ratio == 0` → weight `1/W_FLOOR` | Pre-registered shares (§3); a rise above 10 percentage points in either goes to the reviewer before the live run |
| A (region, split) habitat pool undersupplied after re-weighting | Weights change probabilities, not the pool; the draw refuses (`RuntimeError`) as today; checked in the scratch run |
| `analyze_grouse.py` re-run changes S | Fixed seeds; deliverable 5's S sha256 check before and after; E11 binds S's digest |
| The old checkpoint evaluated or calibrated on the new validation set | CHANGELOG not-comparable statement; follow-up retrain CR; BUG-0060 |
| A live run that fails part-way | CR-0019 deliverable 6's order and restore rule (backup first) |

## Test plan
**Validatable here:** nothing beyond review (the harness needs rasterio/geopandas; `analyze_grouse.py`, `generate_negatives.py` and `acceptance_split.py` need pandas).
**On the data host, before approval of the acceptance code (A3):** harness: a new fixture writer for `availability_sample_R.csv` with feature columns (asserting distinct EVH edges); E15 and E15b pass on the intended pipeline and fail on the attack rows; the replay unit test; `envelope_metrics_table` reproduces `analyze_region`'s table on a fixture.
**On the data host, after approval:** scratch-tree run; live `analyze_grouse.py` with the S check; pre-registration with control; live run.

## Deliverables (in execution order)
- [ ] 1. Acceptance code (A3): E15, E15b, O13, attack rows, the availability fixture writer and the harness tests on an unmerged branch, written by a fresh reviewer against §3 and reviewed with this CR; pins updated.
- [ ] 2. Pipeline changes (§2): availability columns, `envelope_metrics_table`, `attach_weights`, `PATH_TEMPLATES` entry, manifest fields; `tests/test_cr0020.py`.
- [ ] 3. Scratch-tree real-data run (E15, E15b, MC dry run).
- [ ] 4. Preconditions and backup (`grouse_backup/CR-0020/`).
- [ ] 5. Live `analyze_grouse.py` (the sample gains its columns); sha256 of the three S files recorded before and after, abort on any difference.
- [ ] 6. Pre-registration with control on the live tree (`docs/quality/evidence/CR-0020/preregister.txt`).
- [ ] 7. Live `generate_negatives.py` → `acceptance_split.py` (E15, E15b, MC, every GATE) → record.
- [ ] 8. Pointers and bookkeeping: CR-0007 (availability schema), CR-0012 §2, CR-0013 gate table, ARCHITECTURE.md stage 5; BUG-0076 → FIXED naming §2/§3 (PA-0024(a)); `BUG_LOG.md`; tracker D3 and the E15b vintage-choice gap (owner lead); PA-0033 Swept? cell (buffer deviation recorded); CHANGELOG with the not-comparable statement.
- [ ] 9. Close-out.

## Out of scope
- The retrain, calibration and new baseline (follow-up CR).
- The 300 m buffer's use of validation sightings (D3 second half; protective, recorded).
- D4 (no buffer between training and validation blocks).
- The draw rule of the availability sample (CR-0029) and year distributions (CR-0022, CR-0030).
- Verifying the availability sample's vintage choice (tracker item, deliverable 8).
