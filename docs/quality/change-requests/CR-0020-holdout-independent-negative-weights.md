# CR-0020: Fit the negatives' envelope weights on training-block sightings only, so the validation negatives are drawn independently of the validation positives

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented; no data has been touched.** Review log: `CR-0020-review-log.md`, to be created by the first reviewer.

## Scope
Compute `Selection_Ratio` and the envelope binners from habitat sightings in **training** blocks only, use those weights for both draws, record the rule in the manifest, and gate it (BUG-0076; tracker D3).

## Why now
BUG-0076: `analyze_grouse.py:881-923` fits the envelope metrics on every sighting before the split exists, and `generate_negatives.py:247-259`, `:466-469` draws the validation negatives with the resulting weights, so validation negatives are steered away from the envelopes the validation positives occupy. Every validation metric, checkpoint selection (`--select-by rank`), the divergence guard, `--dynamic-dropout` and the Platt fit consume that set. The size of the effect is unknown (the review environment has no data); measuring it is this CR's first deliverable (§4).

## The change
### 1. Root cause
As BUG-0076 §5: the statistics that parameterise the negative draw are fitted once on the whole sighting set and applied to the validation draw; no rule or gate covered holdout self-dependence. PA-0033 now states the rule; this CR implements it.

### 2. Pipeline (normative; amends CR-0012 §2 pool step 9)
**Ordering.** `analyze_grouse.py` runs before `prepare_training_data.py` writes `block_assignments.csv`, so the split is unknown when `envelope_metrics_{R}.csv` is written. The metrics that drive weighting therefore move to `generate_negatives.py`, which runs after both.

**Shared metric function.** `analyze_grouse.py` gains `envelope_metrics_table(habitat, availability, binners)` returning the `Envelope, Sightings, Avail_N, Used_Pct, Avail_Pct, Selection_Ratio, Classification` frame exactly as `analyze_region` computes it today (`:892-933`; constants `MIN_AVAIL_BG`, `SELECT_W_HI`, `SELECT_W_LO`). `analyze_region` calls it; its own output is unchanged and `envelope_metrics_{R}.csv` stays the all-sightings diagnostic table.

**Pool step 9, as amended.** For region R:
1. `habitat_R`: rows of `evaluated_sightings_R.csv` with `nonveg_landcover == False` whose block id (`regions.block_ids(regions.to_5070(lon, lat))`) is `"train"` under `block_assignments.csv` via `regions.block_split` (a block absent from the file follows the hash rule, as for candidates).
2. Binners: `fit_scheme_binners(habitat_R, ENVELOPE_SCHEME)` (EVH quantile edges from training-block habitat rows only).
3. Availability: the recorded `availability_sample_R.csv` (`PATH_TEMPLATES["availability_sample"]`) re-binned with those binners; `Avail_N` per envelope as today.
4. `metrics_train_R = envelope_metrics_table(habitat_R, availability_R, binners)`, written to a new `PATH_TEMPLATES["envelope_metrics_train"] = "data/pipeline/envelope_metrics_train_{region}.csv"` (provenance; digested into the manifest).
5. `attach_weights` uses `metrics_train_R` and those binners for `envelope_id`, `weight` and `weight_basis`; the NonVeg rule, `build_weight`, `W_FLOOR`/`W_CAP`/`NONVEG_MAX_FRAC` are unchanged.
6. The draw (step 11) is unchanged in code: both splits use `weight`, which now depends on training-block sightings only.

**Manifest.** The `negatives` section of `split_manifest.json` gains `"weights_fitted_on": "train_blocks"` and, per region, the sha256 of `envelope_metrics_train_R.csv` and the number of training-block habitat rows used.

**Buffer (pool step 6) unchanged.** It still tests every sighting, validation included: it removes candidates near validation positives rather than steering the draw by label. Recorded in BUG-0076 §8; D3's second half stays open.

### 3. Acceptance (amends CR-0013; normative for the replay author)
- **Config** (`docs/quality/acceptance_split.json`): `envelope.binners_fitted_on` → `"train_block_habitat_rows"`; `paths` gains `envelope_metrics_train`; `manifest_schema` gains `weights_fitted_on`.
- **Replay.** `annotate` (`acceptance_split.py:719`) recomputes the training-block habitat rows from P's coordinates and `block_assignments.csv` (never from the pipeline's new CSV), refits the binners, re-bins the recorded availability sample and recomputes the metrics table with the config constants. The pipeline's `envelope_metrics_train_R.csv` is compared to the replay's (exact after the config `rounding` rule).
- **New gate E15 (exact).** (a) For every validation-split negative, the recorded `weight` and `weight_basis` equal the replay's, computed from training-block sightings only. (b) The replay's metrics table is byte-identical when every validation-block positive is deleted from its input: the independence property, computed, not asserted.
- **Attack rows** (`tests/test_acceptance_split.py`, PA-0021(a); built by the reviewer, not the author): (i) weights fitted on all sightings (today's pipeline) → E15 FAIL; (ii) weights fitted on validation-block rows only → FAIL; (iii) binners fitted on all rows, metrics on training rows → FAIL; (iv) the intended pipeline → PASS.
- **Must-change pin MC (PA-0021(b), one-off).** Per (region, split), the number of negatives whose `weight` differs from today's file, pre-registered from the scratch run before the live run; a count of 0 for the validation split of any region fails.
- **OBS O10 (PA-0021(f)).** Envelope-only separability of the validation set: AUC of `Selection_Ratio_train(envelope_id)` as a score over validation rows. Class: validation P vs N; subset: per region and pooled; null: the same statistic over 200 label permutations. Reported before and after the change; not a gate.

### 4. What the change does to the data (pre-registered before the live run)
Every `weight` in `candidate_pool.csv` can change, and with it both splits' draws (the Efraimidis-Spirakis keys are fixed, the weights are not). Positives, block assignments and the buffer do not change. The pre-registration (`docs/quality/evidence/CR-0020/preregister.txt`) records from the scratch run: per (region, split) changed-negative counts, O10 before and after, the training-block habitat row counts, and the `Landscape-Rare` share before and after.

## Alternatives considered
- **Neutral weights for the validation draw** (uniform within the NonVeg cap): removes the dependence too, but changes the validation design away from the training design, so validation metrics stop estimating performance under the deployed prior. Rejected as the primary option; available to the reviewer as an alternative.
- **Fit on training positives inside `analyze_grouse.py`:** impossible without inverting the pipeline order (the split does not exist yet).
- **Accept D3 as a documented limitation:** rejected; the leak is into the number that selects checkpoints and fits the calibration.

## Impact
- `negatives_*`, `train_negatives_*`, `val_negatives_*`, `candidate_pool.csv`, `split_manifest.json` and `acceptance_record.json` regenerate; `standing_checks` refuses training on the old record until acceptance is re-run.
- Validation metrics before and after are not comparable (as CR-0019 recorded for the year floor); `calibration.json` is invalid until a retrain and re-calibration (follow-up CR; BUG-0060 applies).
- `envelope_metrics_{R}.csv` becomes diagnostic only; its readers (`tune_bins.py`, `diagnose_*`) are unaffected.
- CR-0013 gains E15 and O10; CR-0012 §2 gains a pointer; ARCHITECTURE.md stage 5 gains one sentence.

## One change per CR (CR-0011 A5)
Generator code, acceptance and regeneration cannot land separately: the code without the replay fails R1–R4 (no record, training refused); the replay without the code fails E15 on today's files. Bookkeeping closes BUG-0076. The retrain is split out (follow-up CR, as CR-0009 was from CR-0012). CR-0029 (availability draw) is independent: whichever lands first, step 3 re-bins whatever `availability_sample_R.csv` is on disk.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Replay and pipeline disagree on the training-block row set | Both derive it from P's coordinates and `block_assignments.csv` through `regions.block_split`; E15 exact; attack rows (i)–(iii) |
| Fewer habitat rows per envelope (training blocks only) push more envelopes under `MIN_AVAIL_BG` or into singletons, raising the `Neutral`/`Landscape-Rare` share | Recorded in the pre-registration; thresholds unchanged; a rise above 10 percentage points goes to the reviewer before the live run |
| A (region, split) habitat pool undersupplied after re-weighting | Weights change probabilities, not the pool; the draw refuses (`RuntimeError`) as today; checked in the scratch run |
| The old checkpoint evaluated or calibrated on the new validation set | CHANGELOG not-comparable statement; follow-up retrain CR; BUG-0060 |
| A live run that fails part-way | CR-0019 deliverable 6's order and restore rule (backup first) |

## Test plan
**Validatable here (no data, no rasterio):** the CR-0013 synthetic harness (`tests/test_acceptance_split.py` fixtures): E15 passes on the intended pipeline and fails on attack rows (i)–(iii); a unit test that `envelope_metrics_table` reproduces `analyze_region`'s table on a fixture; a PA-0033 review of the diff.
**Not validatable here:** the scratch-tree real-data run, the MC pre-registration, O10, the undersupply check and the live run; all run on the data host per CR-0019 deliverables 4–6.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (CR-0011 A3): E15, O10, attack rows and the harness test on an unmerged branch, reviewed with this CR.
- [ ] 2. Acceptance changes (§3) by a fresh reviewer, on the branch.
- [ ] 3. Pipeline changes (§2): `analyze_grouse.envelope_metrics_table`, `generate_negatives.attach_weights` (train-only metrics, new CSV, manifest field), the `PATH_TEMPLATES` entry, `tests/test_cr0020.py`.
- [ ] 4. Scratch-tree real-data run and pre-registration (`docs/quality/evidence/CR-0020/preregister.txt`).
- [ ] 5. Preconditions and backup (`grouse_backup/CR-0020/`), as CR-0019 deliverable 5.
- [ ] 6. Live run: `generate_negatives.py` → `acceptance_split.py` (E15, MC, every GATE) → record.
- [ ] 7. Pointers: CR-0012 §2, CR-0013 gate table, ARCHITECTURE.md stage 5.
- [ ] 8. Bookkeeping: BUG-0076 → FIXED naming §2/§3 (PA-0024(a)); `BUG_LOG.md` row; tracker D3; PA-0033 Swept? cell; CHANGELOG entry with the not-comparable statement.
- [ ] 9. Close-out: every item ticked; status IMPLEMENTED.

## Out of scope
- The retrain, calibration and new baseline (follow-up CR).
- The 300 m buffer's use of validation sightings (D3 second half; protective, recorded).
- D4 (no buffer between training and validation blocks).
- CR-0029 (availability draw uniform in degrees) and CR-0022 (year distributions).
