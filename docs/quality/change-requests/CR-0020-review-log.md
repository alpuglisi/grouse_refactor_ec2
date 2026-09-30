# CR-0020 review log

## Lineage
From BUG-0076 (2026-09-30 static review; tracker D3). Author: the review
session that filed BUG-0076. Reviewers: two fresh agents, each re-deriving
from the code before reading the CR (CLAUDE.md §1.2, §1.4 agent-only
quorum). Review logs were not read by the reviewers.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | REVISE | 2 |
| 1 | v1 | B (agent, fresh) | REVISE | 2 |

## Round 1, reviewer A
- **A1 BLOCKING:** §2 step 3 "re-bin the recorded availability sample" is
  not implementable: `availability_sample_R.csv` holds only
  `longitude, latitude, used, envelope_id` (`analyze_grouse.py:484-485`
  copies `bg` before features are attached; `:546-549` writes). Either the
  old bin labels are reused (train-only edges never applied; attack row
  (iii) becomes the intended pipeline) or the pipeline re-samples rasters
  under a vintage rule that differs from `background_envelope_sample`'s
  (`:487-506`) and the replay disagrees.
- **A2 BLOCKING:** the training-block row set is defined twice: §2 from
  S (`evaluated_sightings`, all years, unthinned) and §3 from P (thinned
  positives). Different EVH edges and counts → E15 fails on the intended
  pipeline.
- A3 MAJOR: E15(b) reads nothing the pipeline produced and holds for every
  pipeline (PA-0021(a),(e)); the real exact gate is pipeline
  `envelope_metrics_train_R.csv` vs the replay's table, unlabelled.
- A4 MEDIUM: manifest placement of the new file undefined (E11(d) set
  equality `:2130-2132`, `digested_paths :125-129`, E0,
  `GATE_SECTION_SHA256` pins).
- A5 MEDIUM: OBS id O10 exists (`acceptance_split.py:2603`).
- A6 MEDIUM: test plan "validatable here" false (harness needs rasterio/
  geopandas; no availability fixture; `_write_metrics` random).
- A7 MEDIUM: PA-0042 consumer list absent for `weight`, `weight_basis`,
  `envelope_id`.
- A8 LOW: MC wording (draws differ; pin `candidate_pool.csv` by key);
  `comparison.float_rel_tol`; "Avoided at ratio 0 → weight 10" share.
- Sound: ordering claim; `block_split` for S rows; no other holdout
  dependence beyond the buffer; alternatives; A5; attack rows (i)–(iii).

## Round 1, reviewer B
- **B1 BLOCKING:** same as A1 (availability sample has no feature values;
  vintage rule not recorded). Fix requires the availability schema change
  and an `analyze_grouse.py` re-run, which v1 says does not happen.
- **B2 BLOCKING:** same as A2 (S vs P); the replay must derive the set
  from S + its own recomputed B (`Replay.assign_split` uses `self.B`,
  `:1201`).
- B3 MAJOR: same as A3 (E15(b) not a gate; "byte-identical" has no
  serialisation rule).
- B4 MAJOR: fate of `envelope_metrics_R.csv` in E10 (`:2014, :2023`),
  E11 (`:2106`), `generate_negatives.py:443` unspecified.
- B5 MAJOR: MC pre-registered from the pipeline's own scratch run
  (PA-0021(e)); use a `Replay` subclass with a control as CR-0019 did.
- B6 MAJOR: PA-0042 consumer list; P's `envelope_id` (all-sightings
  binned) no longer means the same as N's (train-binned).
- B7 MEDIUM: O10 collision; "200 permutations" vs config `n_perm`.
- B8 MEDIUM: same as A4 (manifest key; `write_record`, E11 amendment).
- B9 LOW: PA-0033 text vs buffer (record the deviation in the PA cell);
  blocks absent from B (conservative, say so); `*` unpack; pins
  `GATE_IDS`, `len(GATE_IDS)`, `GATE_SECTION_SHA256`;
  `envelope_metrics_table` without availability → raise.
- Sound: ordering; `block_split`; buffer; alternatives; retrain split
  out; A5.

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location, PA-0024(a)) |
|---|---|---|
| A1 / B1 | BLOCKING | **Accept** — §2 step 0: `analyze_grouse.background_envelope_sample` writes the sampled feature values and per-feature vintage into `availability_sample_R.csv` (superset schema); pipeline and replay bin from recorded values, never re-sample; `analyze_grouse.py` re-run is deliverable 6 step 1; landing order with CR-0029 stated (§ One change per CR) |
| A2 / B2 | BLOCKING | **Accept** — one definition, §2 step 1: S-train-block habitat rows (every year); §3 replay derives the block split from S + its own recomputed B, never from P; rationale (CR-0019 §2 "metrics keep every sighting year") stated |
| A3 / B3 | MAJOR | **Accept** — E15 is the exact artifact comparison (`envelope_metrics_train_R.csv`, and C/N `envelope_id`, `weight`, `weight_basis`) against the replay; the independence property becomes a replay unit test (§ Test plan); serialisation = config `comparison.float_rel_tol` |
| B4 | MAJOR | **Accept** — §3: `envelope_metrics_R.csv` leaves the negatives `inputs` (no longer read by `generate_negatives.py`); E10's reference is the train-only recomputation; E11 required-input list, `paths`, `manifest_schema` amended |
| B5 | MAJOR | **Accept** — §4: pre-registration via a `Replay` subclass with a control (CR-0019 `preregister.py` pattern), never the pipeline's own run |
| A7 / B6 | MAJOR | **Accept** — § Impact gains the PA-0042 consumer table; P's `envelope_id`/`env_zone` stay all-sightings diagnostic columns and no gate compares them to N's (E9/E10 read C/N only); the OBS re-bins P from `evh` |
| A4 / B8 | MEDIUM | **Accept** — §3 Manifest: new file in `outputs` of the negatives section; `digested_paths` 20 → 23; E11(d), E0, `manifest_schema.outputs`, `write_record`, pins named |
| A5 / B7 | MEDIUM | **Accept** — OBS renumbered O13; permutation count = config `obs.n_perm` |
| A6 | MEDIUM | **Accept** — § Test plan: nothing validatable here; host harness needs an availability-sample fixture writer with feature columns (deliverable 1) |
| A8 | LOW | **Accept** — MC pins `candidate_pool.csv` rows by 5 dp key; `float_rel_tol`; risk row for the ratio-0 share |
| B9 | LOW | **Accept** — buffer deviation recorded in PA-0033's Swept? cell (deliverable 8); absent blocks conservative (§2 step 1); `*` unpack; pins listed; `envelope_metrics_table` raises without availability |

## Versions
| version | change |
|---|---|
| v1 | initial draft |
| v2 | dispositions above; availability schema step; single fitting-set definition; E15 redefined; O13; manifest and pin list; PA-0042 table; landing order with CR-0029 |
