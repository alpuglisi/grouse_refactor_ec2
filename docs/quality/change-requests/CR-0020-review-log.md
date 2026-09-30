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
| 2 | v2 | A (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1, N2 text) | 0 |
| 2 | v2 | B (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N2 text) | 0 |

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

## Round 2 (v2), reviewer A (bounded, CR-0011 A2)
Every round-1 BLOCKING/MAJOR verified RESOLVED against the code
(A1/B1: `bg[feat]` in scope at `analyze_grouse.py:515` before `:524`;
A2/B2: `Replay.assign_split` uses `self.B`, `acceptance_split.py:1199-1205`;
A3/B3; B4; B5; A7/B6: `env_zone`/`envelope_id` not on the training path).
- **A-N1 MAJOR (PA-0021(e)):** the availability half of E15's reference
  is read from a file this CR produces and nothing verifies the recorded
  feature values; a positional (misaligned) copy after `bg.dropna()`
  (`:524`) gives pipeline and replay identical wrong `Avail_N`.
- **A-N2 MAJOR:** the availability sample is not bound as an input:
  `paths` has no `availability_sample`, the negatives `inputs` are only
  reduced, E11's required list only loses a kind; following the file's
  own `digest(rd.path(...))` pattern makes E11 FAIL "outside S and I"
  (`:2164-2165`), omitting it leaves the input unrecorded.
- A-N3 MEDIUM: E15's comparison key unspecified (`comparison.rule` keys
  on coordinates or `block_id`; the table has neither; `:942` sort is not
  canonical among ties).
- A-N4 MEDIUM: the replay unit test as worded cannot pass (deleting
  validation-block S rows moves the replay's own B).
- A-N5 MEDIUM: "R1 compares S row-for-row" is false (R1 compares P,
  `:2261-2275`); E11 last-wins (`:2142`).
- A-N6 MEDIUM: attack rows (iii)/(iv) fail only if the fixture's
  train-only EVH median differs from the all-rows median.
- A-N7 LOW: the CR-0019 control compares keys and split only; say it
  compares `weight` too.
- A-N8 LOW: Step 0 lists `evc`, which `needed` (`:479-482`) lacks; "P5
  reads only the coordinates" is wrong (`check_partition.py:482`).
- A-N9 LOW: consumer list: `diagnose_*` do not read the metrics table;
  `check_partition.py` P5 and `organize_project.py` do; E9 counts by
  `is_nonveg`; the ratio-0 weight is `1/W_FLOOR`.
- A-N10 LOW (A4): E15's C/N half duplicates E10.
- A-N11 LOW: `envelope_metrics_table` raising on empty availability vs
  today's fallback (`:974-985`).

## Round 2 (v2), reviewer B (bounded, CR-0011 A2)
Same RESOLVED table.
- **B-N1 MAJOR:** same as A-N1 (remedy: a re-sampling gate; may be a
  tracked follow-up with a PA-0024(a) location).
- **B-N2 MAJOR:** same as A-N2 (`Replay.read_input` resolves through
  `rpath`, `:950-956`; E11 loops only required kinds, `:2157-2160`).
- B-N3 MEDIUM: deliverable order: the pre-registration needs a sample
  with feature columns, which exists on the live tree only after
  `analyze_grouse.py` runs.
- B-N4 MEDIUM: `evc` (same as A-N8).
- B-N5 LOW: the new table needs a match key, canonical order and a
  `columns` entry for E0.
- B-N6 LOW: "R1 checks S" (same as A-N5); S is bound by E11 through the
  positives manifest inputs (`prepare_training_data.py:373`).
- B-N7 LOW: E9/O6 and P5 wording (same as A-N9/A-N8).
- B-N8 LOW: O13's id presumes O11/O12 land first; `digested_paths`
  20→23 interacts with CR-0024; E10's reference depends on the replay's
  positives stage; attack row (iv) needs distinct edges.

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-N1 / B-N1 | MAJOR | **Accept** — §3 new check E15b re-samples the rasters at the recorded year and recomputes `evt_phys`; §2 Step 0 requires the index-aligned join; the vintage choice is the recorded accepted gap (tracker, deliverable 8) |
| A-N2 / B-N2 | MAJOR | **Accept** — §2 Step 3 and Manifest: the sample is read through `digest(rd.path(...))` and its three digests enter the negatives `inputs`; §3 Config: `paths.availability_sample`, E11 required kinds, `manifest_schema.inputs` |
| A-N3 / B-N5 | MEDIUM / LOW | **Accept** — §2 Step 4 canonical order by `Envelope`; §3 E15 keyed on `Envelope`; `row_order`, `columns`, `comparison.rule` entries |
| A-N4 | MEDIUM | **Accept** — §3 replay unit test holds B fixed and deletes from the fitting input only |
| A-N5 / B-N6 | MEDIUM / LOW | **Accept** — §4, risk table and deliverable 5: sha256 of S before and after, abort on difference; E11 binds S through the positives inputs |
| A-N6 / B-N8 | MEDIUM / LOW | **Accept** — §3 attack rows: the fixture writer asserts distinct EVH edges |
| A-N7 | LOW | **Accept** — §3 pre-registration: control = pre-CR replay under pre-CR config, compares `weight` |
| A-N8 / B-N4 | LOW / MEDIUM | **Accept** — §2 Step 0: `evt`, `evh`, `sclass` (+ derived `evt_phys`), P5 columns named |
| A-N9 / B-N7 | LOW | **Accept** — § Impact consumer list corrected |
| A-N10 | LOW | **Accept** — §3 E15 is the table comparison only |
| A-N11 | LOW | **Accept** — §2 shared metric function: called only inside the `bg_counts is not None` branch |
| B-N3 | MEDIUM | **Accept** — deliverables 5–7 reordered: live `analyze_grouse.py` with S check, then pre-registration, then `generate_negatives.py` |
| B-N8 | LOW | **Accept** — §3 O13 id caveat; § One change per CR: `digested_paths` derived, composes with CR-0024; E10 dependence stated |

## Versions
| version | change |
|---|---|
| v1 | initial draft |
| v2 | round-1 dispositions; availability schema step; single fitting-set definition; E15 redefined; O13; manifest and pin list; PA-0042 table; landing order with CR-0029 |
| v3 | round-2 dispositions above (E15b, input binding, canonical order, deliverable order); approved by agent quorum |
