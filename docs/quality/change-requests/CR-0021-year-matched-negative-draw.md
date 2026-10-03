# CR-0021: Year-matched negative draw, with a one-off 2023–2024 negative top-up

**Status: DRAFT v3, 2026-10-03.** Scope (iii) chosen by the user
(2026-10-03) after round 1; v3 dispositions round 2. Not approvable yet:
waits on round 3 (the last under CR-0011 A2, bounded to the round-2
MAJOR concerns and v3's changed text) and on deliverable 1 (the top-up
fetch and the pre-registration on the EC2 host), which has not run.
Verdicts and dispositions: `CR-0021-review-log.md`. This document states
only current intent.

## Scope
Draw each (region, split)'s negatives per year stratum so that every
stratum holds as many negatives as positives, with strata as fine as the
candidate supply allows (single years if possible). To make single-year
strata feasible, top up the raw negative candidates for 2023 and 2024
once, from the same GBIF dataset. Add exact acceptance checks on the
per-stratum counts. Then regenerate the negatives.

## Fixes
- **BUG-0073** (year alone predicts the label at AUC 0.6615). Its root
  cause is restated by this CR (§1, deliverable 8): the year-unmatched
  **draw** is the step that turns per-class differences on the time axis
  into a label correlation, and no check compared the classes' year
  distributions. Both are fixed: the draw is matched per stratum (§2 B)
  and E15 checks it exactly. With single-year strata the classes' year
  histograms are equal in every (region, split) whatever rule assigns a
  record's year. The differing representative-year rules are **not
  changed**; they remain as a residual with an owner (§5).

## Why now
- The tracker (`CR-0007-0008-OPEN-ISSUES.md` § CR-0019) requires BUG-0073
  decided before CR-0020's baseline is final.
- Today a model can separate the classes by raster vintage instead of
  habitat (BUG-0073 §3); every comparison on today's split carries it.

## The change

### 1. Root cause (BUG-0073 §5; candidate, PA-0016)
| step | positives | negatives |
|---|---|---|
| representative year | latest visit (`analyze_grouse.py:268-272`) | year of the smallest `gbif_id` (`generate_negatives.py:175-177`) |
| acquisition | full download | per-year first pass then rollover in year order (`get_negatives.py:280-340`), front-loading early years |
| draw | – | per (region, split) only, not per year (`generate_negatives.py:298-313`) |

The draw is the step where any of these becomes a label correlation: it
takes the pool's year mix. Matching the draw per year removes the
correlation regardless of the first two rows; that is the fix chosen. It
needs enough 2023–2024 candidates, which the acquisition order starved.

### 2. Change

**C. One-off top-up of 2023–2024 candidates (network; user-run).**
`get_negatives.py` cannot top up as it stands: its caps are per (state,
species) over all years (`:245-249`) and today's raw files already meet
them, so `--years 2023 2024` fetches nothing (`:287-290`). The top-up is
therefore done by a committed **evidence script**,
`docs/quality/evidence/CR-0021/fetch_topup.py`, which reuses
`get_negatives`' `verify_dataset`, `resolve_taxon_keys`, `api_get` and
`fetch_capped`, the same `EOD_DATASET_KEY`, the same 10 `TARGET_SPECIES`,
the same query (`country=US`, `stateProvince`, `year`,
`hasCoordinate=true`), the same `CSV_FIELDS` and the same `gbif_id`
de-duplication against the existing rows:
- For each state R, species s and year y in {2023, 2024}: append up to
  `TOPUP_MULTIPLE × e(R, s, y)` new rows, where `e` is the number of rows
  of (R, s, y) already in `gbif_negatives_R.csv`; `TOPUP_MULTIPLE = 2`.
  That up to triples the **raw** 2023–2024 rows; the usable pool grows by
  less, because most raw rows are lost to 5 dp de-duplication, the
  buffer and thinning, so S1's feasibility is uncertain until §4 runs. A
  partition with `e = 0` gets no top-up. Per-species quotas keep each
  (R, y)'s species mix equal to the existing rows' unless a partition is
  exhausted. No other year is fetched. Rows are appended with
  `get_negatives`' `csv.DictWriter` and `CSV_FIELDS` (same quoting and
  `\r\n` line endings); existing rows are never rewritten.
- **Single use, scratch only.** It refuses to run unless each target
  file's sha256 equals the pre-top-up hash pinned in the script (the
  live record's raw files), and unless the target directory's realpath
  differs from the live tree's `data/negatives/`. It writes no row whose
  GBIF `year` is outside {2023, 2024}. After deliverable 1 it is edited
  to `raise SystemExit` at the top, so it cannot run again.
- It logs per (R, s, y): existing, requested, written, zero-`e` and
  whether GBIF reported the partition exhausted.
- The resulting three raw files are the CR's pre-registered inputs:
  their sha256 is pinned in `check_must_change.py`, and the live run
  **copies these files** into `data/negatives/`; it never fetches again.
  GBIF's contents change over time, so a second fetch would not reproduce
  the pre-registration.
- `get_negatives.py` itself is not changed (§ Out of scope).

**B. Year-stratified draw (`generate_negatives.py`).**
- **Constant (`regions.py`, PA-0025).** `YEAR_STRATA`: a **pure literal**
  tuple of tuples of years (E11 reads it with `ast.literal_eval`,
  `acceptance_split.py:2043-2060`), increasing, contiguous, starting at
  `YEAR_MIN`. Its value is the first entry of the pre-fixed list in §4
  that the pre-registration finds feasible. `regions.year_stratum(year)`
  returns the index of the stratum holding `year` and raises
  `ValueError` for any other year (fails closed). `tests/test_shared_constants.py`
  pins both names.
- **Draw.** `draw_region_split(pool_rs, pos_years)` takes the cell's
  positives' `year` values (instead of their count). For each stratum `k`:
  `n_k = round(n_pos_k × NEG_RATIO)`; NonVeg cap
  `n_nv_k = min(round(n_k × NONVEG_MAX_FRAC), NonVeg supply in k)`;
  habitat `n_hab_k = n_k − n_nv_k`; a habitat shortfall in any stratum
  **raises** (no top-up from another stratum, no NonVeg top-up; CR-0012
  policy); each sub-pool is sampled with `es_select` as today, restricted
  to the stratum. A pool row's stratum is `year_stratum` of its `year`;
  every positive and pool row must map to a stratum (else raise).
- **Cell totals are sums over strata.** `n = Σ n_k`, `n_nv = Σ n_nv_k`,
  `n_hab = Σ n_hab_k`. `Σ n_k = round(n_pos × NEG_RATIO)` holds because
  `NEG_RATIO = 1.0`; for a non-integer `NEG_RATIO` it would not, and E9
  (§3) is defined on the sum so that it stays correct. `Σ n_nv_k` can
  exceed `round(n × NONVEG_MAX_FRAC)` by rounding (up to half the number
  of strata); that is intended (the cap is per stratum).
- **Manifest `draw` entry** per region R and split s (R4 compares the
  whole dictionary; keys and types are exact):
  `{"n": int, "n_nv": int, "n_hab": int, "strata": {"<first year of
  stratum>": {"n": int, "n_nv": int, "n_hab": int}, …}}`, strata keys
  as strings, in stratum order, every stratum present (zeros included).
- **Unchanged:** the representative-year rules of both classes, every
  pool step, the positives and their split. `analyze_grouse.py` and
  `prepare_training_data.py` are **not** re-run.

**Code.**

| file | change |
|---|---|
| `regions.py` | `YEAR_STRATA` (literal), `year_stratum` |
| `generate_negatives.py` | `draw_region_split` stratified; call site passes the cell's positive years; manifest `draw` breakdown; `measured_constants` gains `YEAR_STRATA`; module docstring § Draw |
| `tests/test_cr0012.py` | calls of `draw_region_split(sub, int)` (`:260-377`) updated to the new signature; expectations unchanged where one stratum holds every year |
| `tests/test_cr0021.py` (new) | § Test plan |
| `tests/test_shared_constants.py` | pin `YEAR_STRATA`, `year_stratum` |
| `docs/quality/evidence/CR-0021/fetch_topup.py` (new, evidence) | C |

### 3. Acceptance (amends CR-0013; normative for the replay author)
**Config (`docs/quality/acceptance_split.json`).**
- `constants.YEAR_STRATA` (list of lists of integers); with
  `regions_py.names.YEAR_STRATA`, E11(c) and E11(e) then require it in
  both manifest sections and equal to the `regions.py` literal.
- `manifest_schema.draw`: the shape in §2.
- `rounding`: per-stratum `round` (the existing `py_round`).
- `obs`: O11 (below).
- `GATE_SECTION_SHA256` pins in `tests/test_acceptance_split.py` updated
  with this CR's review.

**Code (`acceptance_split.py`).** `GATE_IDS` and the gate registry gain
E15; `OBS_IDS` gains O11; the standing subset tuple gains E15. The
replay's draw (`Replay.draw_targets`, `:1274-1276`) stratifies exactly as
§2 B, reading the strata **from the config**, not from
`regions.year_stratum` (the replay is independent of the code it
checks). It raises `ReplayError` where the pipeline raises.

**E9, amended** (strata read from the config). Per (region, split): the
negative count equals `Σ_k round(n_pos_k × NEG_RATIO)`. Per (region,
split, stratum k), with `n_k = round(n_pos_k × NEG_RATIO)`: NonVeg count
in N `≤ round(n_k × NONVEG_MAX_FRAC)`; and the habitat pool supply in C
`≥ n_hab_k`, where `n_hab_k = n_k − min(round(n_k × NONVEG_MAX_FRAC),
NonVeg rows of C in k)`, the per-stratum form of today's
`acceptance_split.py:1985-1988` (computed from the pool, not from N).
(Today's per-cell NonVeg cap would fail a correct stratified draw by
rounding, `:1979-1982`.) E9's count clause is implied by E15(b);
redundant, not conflicting.

**New gate E15 (exact).**

| id | set | predicate |
|---|---|---|
| E15(a) | config; P, N; C | the config's strata are increasing, contiguous, disjoint and start at `YEAR_MIN`; every non-null `year` of P, N and C lies in a stratum |
| E15(b) | P vs N, per (region, split, stratum) | count of N = `round(count of P × NEG_RATIO)` |

- E15 joins the standing subset (pandas only).
- E14 is unchanged and stays satisfiable (E15(b) implies equal supports
  wherever a stratum is non-empty).

**New observation O11 (reported).** Class: label. Score: `year`.
Subset: P ∪ N, each split separately and pooled over splits. Two
statistics, each per region and pooled:
- **O11a**, ROC AUC over all rows. Pairs from different strata score
  exactly 0.5 because per-stratum counts are equal, so O11a is diluted
  and **cannot detect** a within-stratum residual. It is reported only.
  Under S1 it is exactly 0.5.
- **O11w**, ROC AUC **within each merged stratum** (S2: 2023–2024; S3:
  2022–2024). Null population: O11w under 1,000 label permutations within
  that stratum's (region, split) cells.

**Criterion (only if S2 or S3 is chosen):** if pooled O11w exceeds the
99th percentile of its null, the merged stratum carries a year–label
residual the gate cannot see. The CR is then **not approvable without a
user decision**: accept the residual, top up further, or stop. No fixed
AUC threshold is used. The pre-registration computes the values, after
the strata are chosen.

**Attack rows** (`tests/test_acceptance_split.py`, synthetic). Each
names the fixture rows it needs. The test asserts on the **attacked
output itself** that the attack changes what the gate reads (PA-0021(a)),
not just that the rows exist. ES keys are deterministic, so this is
exact.

| attack | fixture rows required; asserted effect | must fail |
|---|---|---|
| Draw not stratified (today's code) | a cell whose habitat pool year mix differs from its positives'; the unstratified draw's per-stratum N counts differ from P's | E15(b), R4 |
| NonVeg cap per cell instead of per stratum | a cell where `Σ_k round(n_k·0.3) ≠ round(n·0.3)` and NonVeg supply is not the binding limit in some stratum; the attacked `n_nv_k` differs from the correct one | R4 |
| Stratum boundary off by one | positives and pool whose mixes differ across a boundary year; the attacked per-stratum counts differ | E15(b), R4 |
| Shortfall topped up from another stratum | a fixture variant with one stratum short of habitat while another has surplus | pipeline raises; replay raises `ReplayError`; E9 (supply clause) fails on the topped-up output |
| `YEAR_STRATA` in config ≠ `regions.py` | config edit | E11 |
| Strata overlapping, gapped, or not starting at `YEAR_MIN` | config edits | E15(a) |
| A C year outside every stratum | ≥ 1 pool row with such a year | E15(a) |
| Per-stratum manifest breakdown missing or wrong | manifest edit | R4 |

Existing fixtures: every existing attack row's existence assertion must
still pass; a row the change removes is re-seeded, never deleted.

**Must-change gate MC (PA-0021(b); one-off).**
`docs/quality/evidence/CR-0021/check_must_change.py --old <pre-CR tree>
--new <post-CR tree>`, committed before approval with its pinned
pre-registration outputs:

| check | pins |
|---|---|
| MC0 | old tree = deliverable 5's backup of today's live tree, whose digests equal the current acceptance record (`ed27583b…`), raw files included |
| MC1 | P and B byte-identical to old (positives untouched) |
| MC2 | the three raw `gbif_negatives_R.csv`: old rows byte-identical and in order as a prefix; appended rows exactly the pre-registered ones (sha256) |
| MC3 | C: exactly the pre-registered rows (key, split, year, `is_nonveg`) |
| MC4 | N: exactly the pre-registered rows (key, split, year, `is_nonveg`); per-stratum counts as pre-registered |
| MC5 | train/val files are the combined file's lines by split |

### 4. Pre-registration (deliverable 1; before approval)
Run on the EC2 host, in a scratch tree (CSVs copied, rasters and county
zip symlinked, no output path a symlink):
1. `fetch_topup.py` (C) → the three raw files and `fetch_topup.log`.
2. `preregister.py` runs CR-0013's replay (`acceptance_split.Replay`),
   subclassed only at the draw, on the scratch tree. **Control:** the
   unmodified replay on today's raw files reproduces today's P, B, C and N
   (keys, split, `block_id`, year) or it aborts. Then, on the topped-up
   raw files, it writes `preregister.txt` and CSVs with:
   - pool supply per (region, split, year), NonVeg and habitat, before and
     after the top-up, and the yield per (R, s, y) partition (raw rows →
     pool rows at step 11), including zero-`e` and exhausted partitions;
   - existing pool rows (any year) lost or relabelled by the new rows,
     **separately** by mechanism: (1) a new row wins a 5 dp key at step 3
     (smaller `gbif_id`; the key's year moves); (2) a new row displaces a
     neighbour in thinning; (3) any key the new rows put under two states
     (step 3 raises; reported before it would);
   - **comparability of the new rows (PA-0020(ii); a second acquisition
     pass for two years only)**, per region: species shares, occupancy of
     the 3 km blocks and of counties, and the share of non-null
     `coord_uncertainty_m`, each for (a) new 2023–2024 rows, (b) existing
     2023–2024 rows, (c) existing 2020–2022 rows, on the raw rows and on
     their pool survivors. **Tolerance:** total-variation distance
     between (a) and (b) ≤ 0.10 on species shares and on block occupancy,
     and non-null `coord_uncertainty_m` share within 10 percentage points
     of (b). Beyond any of these, the CR is not approvable without a user
     decision. (c) is reported for context; it differs from (a) and (b)
     by year by design;
   - **strata selection, by a rule fixed here, before any AUC is
     computed:** evaluate, in this order,
     `S1 = ((2020,),(2021,),(2022,),(2023,),(2024,))`,
     `S2 = ((2020,),(2021,),(2022,),(2023,2024))`,
     `S3 = ((2020,),(2021,),(2022,2023,2024))`, and take the **first with
     zero SHORT cells**; for the chosen strata, per (region, split,
     stratum): `n_pos`, `n`, `n_nv`, `n_hab`, supplies, and
     `n_hab / habitat supply`. ES weighting degrades as this ratio nears
     1. Any value above 0.8 is named in the CR. This is **report-only and
     does not block**: it states where the negatives are close to "all
     the supply" rather than an envelope-weighted sample;
   - only then: O11a and O11w for today's N and for the chosen strata,
     with O11w's permutation null;
   - N keys kept / removed / added.
3. `mc_selftest.py`: MC PASSes on the predicted tree and FAILs with the
   live tree as NEW.

**Approval conditions:** a feasible entry among S1–S3; the comparability
tolerance met; if S2 or S3, the O11w criterion met (§3). If none of S1–S3
is feasible, or a tolerance or criterion is exceeded, the CR returns to
the user (accept, top up further, or a different design). The strata
are never coarsened past S3 (a single stratum is today's draw).

**Writing the result in.** The chosen strata, the config pins, and the
pinned sha256 values and O11 values are then written into this CR and
the config by the author. A reviewer **verifies** them against
`preregister.txt`, checking that they are exactly the rule's output.
That is a check of transcription, not a further design round. Any
non-mechanical change at that point (a rule not followed, a tolerance
exceeded, a design change) goes to the user, not to a fourth review
round (CR-0011 A2).

### 5. Residual (not fixed here)
- **The two representative-year rules still differ** (positives: latest
  visit; negatives: smallest `gbif_id` ≈ earliest). With single-year
  strata this cannot create a year–label correlation, because the draw
  matches the classes' years exactly whatever rule produced them. It does
  leave a per-year **composition** difference: in year y, positives are
  "locations last visited in y" and negatives "keys first recorded in y".
  That is a standing per-class selection asymmetry on the time axis, of
  the kind PA-0020 targets. It is not fixed here because the only
  candidate fix found so far (round 1's part A) creates its own asymmetry
  (review log A1: habitat and nodata would be judged at one vintage and
  trained at another). It is filed at deliverable 8 as a **tracked
  residual with an owner** (lead; a tracker entry under PA-0022), not
  closed as accepted.
- **Inside a merged stratum** (only if S2 or S3 is chosen): bounded by
  O11's tolerance.
- **The acquisition order** (`get_negatives.py` rollover) still
  front-loads the raw pool; after B it only affects supply, not N's year
  mix. It stays a recorded candidate cause in BUG-0073; the fix does not
  depend on confirming it.

### 6. Retrain decision: no retrain under this CR
- No model is retrained here. CR-0020 (retrain, calibration, baseline)
  should run on the post-CR-0021 split; if it runs first, it records
  today's residual (tracker rule).
- After the regeneration, no checkpoint trained on an earlier split is
  used in any BUG-0060 entry point (`calibrate.py --model`,
  `--distill-from`, `--init-from`, `--resume`) or evaluated on the new
  validation set: validation negatives change. `CHANGELOG.md` and the
  tracker carry the warning.
- Validation metrics after the change are not comparable with earlier
  ones and are expected to be lower by whatever part of today's
  separation came from vintage. That is not a regression.

## Alternatives considered
| option | verdict |
|---|---|
| **C + B, strata chosen finest-first (S1→S3)** | **Chosen** (user, 2026-10-03). Equal per-year distributions by construction if S1 is feasible; no change to positives or to either year rule. |
| (i) A + B: harmonise the year rule, then stratify (v1) | Rejected after round 1: A judges positives' habitat and nodata at the latest vintage but trains them at the earliest (A1); needs an independent check of the new column (B2) and a bounded `analyze_grouse.py` re-run (B3); v1's strata were infeasible on measured supplies (A2/B1). |
| (ii) B only, strata S3, no fetch | Kept as the fallback inside the chosen option (S3 is its last entry); not chosen up front because it leaves a 2022–2024 residual that single-year strata avoid. |
| Positives `year := max(first_year, YEAR_MIN)` | Rejected: assigns a year in which the location may not have been visited. |
| Change `get_negatives.py` caps (`--headroom`) instead of a top-up script | Rejected: caps are per (state, species) and are recomputed from today's positive counts (4,809 after CR-0019), so the extra rows' year split is not controlled and existing rows may already exceed the new cap. |
| Re-fetch every year from scratch | Rejected: replaces a pool that passes every gate today, for no gain outside 2023–2024. |
| Reweight training samples by year | Rejected: a run-time producer of training weights no file gate sees (PA-0029). |

## Impact
- **Data (deliverable 6):** the three raw `gbif_negatives_R.csv` gain the
  pre-registered rows (append only); the candidate pool, every N file,
  the manifest's `negatives` section and `acceptance_record.json` are
  rewritten; OBS references recalibrated. P, B, `evaluated_sightings_*`,
  the envelope metrics and every raster are unchanged (MC1). Pre-CR files
  backed up first.
- **Acceptance:** `acceptance_split.py`, its config and tests change; the
  config sha256 changes, so `standing_checks` (`acceptance_split.py:2817`)
  refuses all training until the new record exists. Same branch-and-merge
  refusal window as CR-0019 § Impact.
- **Readers:** `tune.py` and `tune_bins.py` read `evaluated_sightings_*`
  (unchanged). `diagnose_*`, `symptom_check.py`, `clean.py`,
  `smoke_test_training.py`, `bench_pipeline.py` and `calibrate.py` read
  the split files through `GrouseData`; they see new negatives and no
  schema change. `train.filter_by_year_gap` passes at the default
  tolerance (every year ≥ 2020, E14 unchanged).
- **Models:** §6.
- **`train.sample_background_points` (BUG-0074, open):** unaffected; the
  tracker's rule (no `--an-background > 0` until fixed) stands.
- **CR texts:** pointer lines in CR-0012 §2 (Draw), CR-0013 (E9, E-table,
  standing subset, § Attacks); `ARCHITECTURE.md`; `CHANGELOG.md`.

## One change per CR (CR-0011 A5)
The deliverables span acquisition (one-off), pipeline code, acceptance
design, data regeneration and bookkeeping. They cannot land separately:
the draw change without the replay change fails R4 (no record, training
refused); the replay change without it fails E15(b) and R4 on today's
files; the top-up without the stratified draw changes the pool and N
without fixing the bug; the stratified draw without the top-up is only
feasible at S3. The regeneration is how they land together.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| GBIF has too few 2023–2024 records (partition exhausted) | `fetch_topup.log` reports it; the S1→S3 rule absorbs a partial shortfall; none feasible → back to the user |
| New candidates reduce earlier-year supply (a 5 dp key won, a thinning neighbour displaced, a two-state key) | Measured per mechanism by the pre-registration and pinned (MC3); a resulting SHORT cell moves the S1→S3 rule on |
| The top-up rows differ from earlier negatives by more than year (species, space, coordinate precision) | Per-species quotas preserve species mix; the §4 comparability tolerance; beyond it, a user decision |
| `fetch_topup.py` re-run or run on the live tree | Refuses unless the target files equal the pinned pre-top-up hashes and the path is not the live tree; disabled after deliverable 1 |
| A later `get_negatives.py` run counts the top-up rows toward its (state, species) caps | Recorded as the raw files' second producer in `ARCHITECTURE.md` and `CHANGELOG.md` (deliverable 7) |
| The live raw files differ from the pre-registered ones | The live run copies the scratch files; MC2 pins their sha256 |
| A stratum near supply exhaustion (weighting degrades) | `n_hab / supply` reported per stratum; > 0.8 named in the CR |
| Pipeline and replay disagree | Exact R1–R4 replay by a separate agent; MC pins every row |
| E9 fails a correct stratified draw | E9 amended (§3) |
| A future year outside `YEAR_STRATA` | `year_stratum` raises; E15(a) fails |
| A regenerated split used with an old model | §6 warning; BUG-0060 owns the mechanical refusal |
| A live run that fails part-way | CR-0019's order and restore rule |

## Test plan
**In this repository (synthetic):**
- `tests/test_cr0021.py`: per-stratum counts equal the positives'; NonVeg
  cap per stratum and totals as sums; raise on a habitat shortfall in one
  stratum while another has surplus; raise on a positive or pool year in
  no stratum; `year_stratum`; `fetch_topup.py` with the network mocked:
  partition arithmetic (incl. `e = 0`), refusal when a target file's
  sha256 differs from the pinned one or its realpath is the live tree's,
  refusal of a row with a year outside {2023, 2024}, and an append that
  leaves the old bytes as an exact prefix.
- `tests/test_cr0012.py` with the new signature; acceptance tests (E9
  amended, E15, O11, attack rows, config pins); the existing suites.

**On the EC2 host (real data):** §4; read-only acceptance on today's
files gives exactly the expected FAILs (E11 for the missing constant,
E15(b), R4); scratch-tree run of `generate_negatives.py` then
`acceptance_split.py` → all GATEs PASS, MC PASS, second run
byte-identical.

**Not validatable under this CR:** how much model separation came from
vintage (needs CR-0020's retrain and a seed-varied comparison, BUG-0039's
lesson).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (CR-0011 A3), reviewed with this CR:
      `fetch_topup.py`, `preregister.py`, `check_must_change.py`,
      `mc_selftest.py` committed; run on the EC2 host by the user
      (network): `fetch_topup.log`, `preregister.txt` and CSVs, the
      pinned raw files' sha256, `mc_selftest.txt`; a reviewer's
      PA-0021(a) wrong-tree runs of MC. Then v3 with the chosen strata.
- [ ] 2. Acceptance changes (§3) on an unmerged CR-0021 branch by a fresh
      agent that does not write deliverable 3 (CR-0013 rule 4); read-only
      run on today's files gives exactly the expected FAILs.
- [ ] 3. Pipeline changes (§2 B) and tests; suites pass.
- [ ] 4. Scratch-tree run with the code of 2–3 (§ Test plan).
- [ ] 5. Preconditions and backup (to
      `/home/ec2-user/grouse_backup/CR-0021/`, sha256 verified),
      including the three raw files.
- [ ] 6. Live run (user-authorised): copy the pinned raw files, then as
      CR-0019 deliverable 6 from `generate_negatives.py` on; restore on
      any FAIL.
- [ ] 7. Pointer lines, `ARCHITECTURE.md`, `CHANGELOG.md` (data change,
      metrics not comparable, §6 warning; the raw files' second producer
      `fetch_topup.py` and the pinned sha256 values, so the provenance
      chain MC2 → E11 input digests → acceptance record stays traceable).
- [ ] 8. Bookkeeping: BUG-0073's root cause restated as confirmed (§ Fixes)
      with its corrective action, recurrence review and status; the
      representative-year rule asymmetry filed as a tracked residual with
      an owner (§5, PA-0022); `BUG_LOG.md`; the PA-0020 extension written
      to `PREVENTIVE_ACTIONS.md` targeting the mechanism ("the classes'
      distributions on every label-correlated attribute are compared, per
      selection cell, by an exact gate where the draw can enforce it, else
      against a stated tolerance; per-class rules that assign such an
      attribute are listed and either made identical or recorded as a
      tracked residual"), with BUG-0073 §8 updated to justify the change
      from its draft wording ("must be the same rule"); a sweep by
      mechanism; tracker.
- [ ] 9. Close-out.

## Out of scope
- The retrain, calibration and baseline: CR-0020.
- A top-up mode in `get_negatives.py` (a reusable per-year fetch): its own
  CR if needed again.
- Harmonising the representative-year rules (round 1's part A).
- BUG-0074 (`sample_background_points` single vintage): its own CR.
- BUG-0075 (`START_YEAR` duplicated in `sightings.py`/`ebird.py`): its own
  small CR, as the tracker allows; positives' acquisition is not touched
  here.
- The envelope metrics' epoch (2016+ sightings; CR-0019 §2).
- `predict.py`'s latest-vintage rule.
