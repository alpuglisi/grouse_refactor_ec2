# CR-0021: One representative-year rule for both classes, and a year-stratified negative draw

**Status: DRAFT v1, 2026-10-03. Not approvable yet:** every count in this
CR comes from a pre-registration (deliverable 1) that must run on the live
data tree on the EC2 host, and has not run. Verdicts and dispositions:
`CR-0021-review-log.md`. This document states only current intent.

## Scope
Give both classes the same representative year for a repeated location
(the earliest recorded year at or after `YEAR_MIN`), draw the negatives of
each (region, split) per year stratum so that each stratum holds as many
negatives as positives, and add an exact acceptance gate that compares the
classes' year **distributions** per stratum, not only their supports.
Then regenerate the split files.

## Fixes
- **BUG-0073** (within-epoch year distribution differs by class; year
  alone predicts the label at AUC 0.6615): its two candidate causes, the
  representative-year rules (§2 A) and the unstratified draw (§2 B).
  Whether the acquisition order (`get_negatives.py:247-248`) is a third
  cause is tested by the pre-registration (§4), not assumed (PA-0016).

## Why now
- The tracker (`CR-0007-0008-OPEN-ISSUES.md` § CR-0019) requires BUG-0073
  to be decided before CR-0020's baseline is taken as final.
- Models trained on today's split can separate the classes by raster
  vintage instead of habitat (BUG-0073 §3). Every tuning comparison made
  on today's split carries that confound.

## The change

### 1. Root cause (from BUG-0073 §5; candidate, tested by §4)
On the time axis the classes differ at two steps after CR-0019:

| step | positives | negatives |
|---|---|---|
| representative year of a repeated location | **latest** visit: `analyze_grouse.collapse_duplicate_locations` takes `idxmax` of `year` (`analyze_grouse.py:268-272`) | year of the **smallest `gbif_id`** (`generate_negatives.dedup_min_gbif_id`, `generate_negatives.py:158-180`); the earliest year for 98.9 % of selected negatives |
| draw | – | per (region, split), `n = round(n_pos × NEG_RATIO)`, not stratified by year (`generate_negatives.draw_region_split`, `:298-313`) |

The first pulls positives late and negatives early; the second lets the
negatives inherit the candidate pool's year mix (front-loaded on 2020).

### 2. Pipeline (normative; amends CR-0012 §2 and CR-0019 §2)

**Constants (`regions.py`; PA-0025, the only literals).**
- `YEAR_STRATA`: a tuple of tuples of years, in increasing order,
  contiguous, starting at `YEAR_MIN`; v1 value
  `((2020,), (2021,), (2022,), (2023, 2024))`. The 2023–2024 merge is
  there because the pool is short of 2023–2024 habitat candidates
  (CR-0019 `preregister.txt` § REJECTED OPTION 1b: 215 short over 6 of 30
  cells at single-year strata). The value is **fixed by review, never
  adapted at run time**; if the pre-registration (§4) shows any shortfall
  under v1's strata, this CR is revised with coarser strata before
  approval.
- A helper `regions.year_stratum(year)` returns the index of the stratum
  holding `year` and raises `ValueError` for a year in no stratum (e.g.
  a future year after a re-acquisition), so a year outside the strata
  fails closed instead of being dropped or lumped.
- `tests/test_shared_constants.py` pins both names.

**A. One representative-year rule: the earliest recorded year
`>= YEAR_MIN` at the location.**

*Positives.* `analyze_grouse.collapse_duplicate_locations` gains one
output column, `first_year_min`: the smallest visit year `>= YEAR_MIN` at
the location, null when the location has none. Nothing else in
`collapse_duplicate_locations` changes: the representative row is still
the latest visit, so the sampled feature columns, `evaluated_sightings_*`'s
existing columns and the envelope metrics stay as they are (selection,
not acquisition, as CR-0019 §2).

`prepare_training_data` positives step 2, as amended:
1. Raise `ValueError` if the column is missing, or if
   `first_year_min.notna()` differs from `year >= YEAR_MIN` on any row
   (the two must agree, because `year` is the latest visit; a disagreement
   means the evaluated file and the floor are out of step).
2. Keep the habitat rows with `first_year_min` non-null (same rows as
   today's step 2).
3. Set `year := first_year_min` (integer). This happens **before** step 3,
   so the window check reads the raster vintage that will train.

The positives' file schema (`POSITIVE_COLUMNS`, CR-0013 config
`columns.positives`) is unchanged; `first_year_min` is consumed, not
carried. `first_year`/`last_year`/`n_visits` keep their meaning. After the
change a positive's `year` can differ from the year its feature columns
(`evt` … `envelope_id`) were sampled at (the latest visit); those columns
are metadata for analysis, and training reads rasters by `year`
(`dataset.py:122-126`). § Impact lists the readers of those columns.

*Negatives.* Pool step 3 becomes "one row per 5 dp key: the row with the
smallest non-null `year`, ties broken by the smallest `gbif_id`; a key
whose rows all have a null `year` keeps its smallest-`gbif_id` row" (that
row is then dropped at step 7, as today). Pool step 1 already removed
every non-null `year < YEAR_MIN`, so this is the earliest year
`>= YEAR_MIN`. The existing raises (null or repeated `gbif_id`, a key
under two states) are kept. The function is renamed
`dedup_earliest_year`; the docstring states the rule.

**B. Year-stratified draw.** `draw_region_split` takes the cell's
positives' years instead of their count. Per (region, split), and per
stratum `k` of `YEAR_STRATA`:
- `n_k = round(n_pos_k × NEG_RATIO)`, `n_pos_k` = the cell's positives in
  stratum `k`;
- NonVeg cap per stratum: `n_nv_k = min(round(n_k × NONVEG_MAX_FRAC),
  NonVeg supply in k)`, habitat `n_hab_k = n_k − n_nv_k`;
- a habitat shortfall in any stratum **raises** (no top-up, no borrowing
  from another stratum; CR-0012 policy unchanged);
- each sub-pool is sampled exactly as today (`es_select`, Efraimidis-
  Spirakis keys from the seeded coordinate hash), restricted to the
  stratum.

With `NEG_RATIO = 1.0` the cell total equals today's
`round(n_pos × NEG_RATIO)`. A pool row's stratum is
`year_stratum(year)` of its post-A year. The manifest's `draw` entry per
(region, split) gains a per-stratum breakdown (`n`, `n_nv`, `n_hab` per
stratum, keyed by the stratum's first year); the existing totals stay.

**Code.**

| file | change |
|---|---|
| `regions.py` | `YEAR_STRATA`, `year_stratum` |
| `analyze_grouse.py` | `collapse_duplicate_locations` adds `first_year_min`; docstring |
| `prepare_training_data.py` | step 2 as above; module docstring; `measured_constants()` gains `YEAR_STRATA` |
| `generate_negatives.py` | step 3 rule and rename; `draw_region_split` stratified; call site passes the cell's positive years; manifest `draw` breakdown; module docstring steps 3 and Draw |
| `tests/test_cr0021.py` (new) | § Test plan |
| `tests/test_shared_constants.py` | pin `YEAR_STRATA`, `year_stratum` |

`analyze_grouse.py` must then be re-run before `prepare_training_data.py`
(deliverable 6), because the new column comes from it.

### 3. Acceptance (amends CR-0013; normative for the replay author)
**Config (`docs/quality/acceptance_split.json`).** `constants.YEAR_STRATA`
(list of lists of integers); E11(c) then requires it in both manifest
sections' constants, and `regions_py.names.YEAR_STRATA` makes E11(e)
compare it with `regions.py`. `GATE_SECTION_SHA256` pins in
`tests/test_acceptance_split.py` are updated as part of this CR's review.

**Replay.** Positives step 2 (A), pool step 3 (A) and the stratified draw
(B) exactly as §2. R1–R4 then check the change row for row; R4 checks
the per-stratum draw breakdown in the manifest.

**New gate E15 (exact).**

| id | set | predicate |
|---|---|---|
| E15(a) | P, N combined; C | every non-null `year` of P, N and C lies in exactly one stratum of `YEAR_STRATA` (config), and the strata are contiguous from `YEAR_MIN` |
| E15(b) | P vs N, per (region, split, stratum) | count of N = `round(count of P × NEG_RATIO)` |

- E15 joins the standing subset on P and N (pandas only).
- E15(b) is where PA-0020(ii)'s comparison is extended from supports
  (E14) to distributions, per stratum, exactly. It does not see a
  difference **within** a merged stratum (2023 vs 2024); that residual is
  measured by OBS below, not gated (a statistical threshold; PA-0021
  prefers exact gates).
- E14 is unchanged.

**New observation O11 (reported, not gated).** Year→label ROC AUC,
pooled and per region, on P ∪ N; the pre-registration (§4) states the
predicted value, produced by the committed script, not restated here
(CR-0011 A3). O9's per-class year histograms are already reported.

**Attack rows** (`tests/test_acceptance_split.py`, synthetic fixture;
each names the fixture rows it needs and the test asserts they exist,
PA-0021(a)):

| attack | fixture rows required | must fail |
|---|---|---|
| Positives keep the latest-visit year | ≥ 1 habitat location with two visits `>= YEAR_MIN` in different strata | R1, E15(b) |
| `year := max(first_year, YEAR_MIN)` (fabricated year) | ≥ 1 location with visits only before `YEAR_MIN` and after `YEAR_MIN + 1` | R1 |
| Pool step 3 unchanged (smallest `gbif_id`) | ≥ 1 key whose smallest `gbif_id` is not its earliest year, and whose years fall in different strata | R3, R4 |
| Draw not stratified | ≥ 1 cell whose pool year mix differs from its positives' | E15(b), R4 |
| Strata from the pre-A positive years | as row 1 | E15(b), R4 |
| Off-by-one stratum boundary | ≥ 1 row with year = a stratum's first year | E15(b), R4 |
| Shortfall silently topped up from another stratum | a fixture variant with a stratum short of habitat candidates | the pipeline raises; the replay raises `ReplayError` |

Existing fixtures that contradict the new rules change with this CR;
every existing attack row's existence assertion must still pass, and a
row the change removes is re-seeded, never deleted (as CR-0019 §3).

**Must-change gate MC (PA-0021(b); one-off).**
`docs/quality/evidence/CR-0021/check_must_change.py --old <pre-CR tree>
--new <post-CR tree>`, committed before approval with its pinned
pre-registration CSVs (as CR-0019's): exact P rows (key, split, block_id,
year), exact N rows (key, split, `is_nonveg`, year), B and C as
pre-registered, and the per-stratum counts.

### 4. Pre-registration (deliverable 1; must run before approval)
`docs/quality/evidence/CR-0021/preregister.py` runs CR-0013's replay
(`acceptance_split.Replay`), subclassed only at the three changed steps,
on the live tree. Its control first reproduces today's P, B, C and N
(and aborts otherwise). It writes `preregister.txt` with:
1. positives whose `year` changes, as a from→to table, and how many
   locations straddle `YEAR_MIN` (first visit before it, a later one at
   or after it);
2. pool keys whose `year` changes under the new step 3;
3. per (region, split, stratum): `n_pos`, `n`, `n_nv`, `n_hab`, NonVeg
   and habitat supply, and any SHORT;
4. year→label AUC: today; after A only; after A + B (the O11 prediction);
   and within the merged 2023–2024 stratum;
5. N keys kept / removed / added; B and C changes (B and C are expected
   unchanged: no positive row and no block assignment changes).

**Approval conditions:** zero SHORT cells under the strata in §2, and
the A + B AUC recorded. If any cell is short, the CR is revised (coarser
strata) and re-registered; if no strata within reason are feasible, the
re-fetch (alternative C) becomes a user decision.

### 5. Retrain decision: no retrain under this CR
- No model is retrained here. CR-0020 (retrain, calibration, baseline)
  should be taken on the post-CR-0021 split; if CR-0020 runs first, it
  records the residual year→label AUC with its baseline (tracker rule).
- After the regeneration, **no checkpoint trained on an earlier split**
  is used in any BUG-0060 entry point (`calibrate.py --model`,
  `--distill-from`, `--init-from`, `--resume`) or evaluated on the new
  validation set: validation negatives change. `CHANGELOG.md` and the
  tracker carry the warning, as CR-0019 §6.
- Validation metrics after the change are not comparable with earlier
  ones and are expected to be **lower**, by however much of today's
  separation came from vintage. That is not a regression.

## Alternatives considered
| option | verdict |
|---|---|
| **A + B as above** | **Chosen.** No network. A removes the rule asymmetry; B makes the per-stratum distribution equal by construction. |
| A only | Rejected as the whole fix: BUG-0073's counterfactual leaves AUC 0.5584 (positives `max(first_year, 2020)`, negatives unchanged), and nothing gates distributions. |
| A′: negatives take their latest year | Rejected: removes less (AUC 0.6125, BUG-0073 §5) and moves negatives off the smallest-`gbif_id` record for most keys. |
| Positives `year := max(first_year, YEAR_MIN)` (BUG-0073's measured variant) | Rejected: assigns a year at which the location may never have been visited (a straddling location gets `YEAR_MIN`). §2 A uses a recorded visit year. |
| Move the representative row itself to the earliest visit in `collapse_duplicate_locations` | Rejected: changes every evaluated feature value and the envelope metrics, hence the negatives' weights, for no gain in the year axis. |
| B with single-year strata | Rejected for now: 215 short over 6 of 30 cells (CR-0019 pre-registration). Reopened if §4 shows it feasible after A. |
| B with a cross-stratum top-up | Rejected: recreates a distribution difference exactly where the pool is thin, invisibly. |
| C: re-fetch 2023–2024 negatives | Not chosen: network, outward-facing, a user decision; kept as the fallback if §4 finds no feasible strata. |
| Reweight training samples by year (train-time) | Rejected: a run-time producer of training weights no file gate sees (PA-0029), and calibration would read a set CR-0013 never accepted. |

## Impact
- **Data (deliverable 6):** `evaluated_sightings_*` gain a column; every
  P and N file, the candidate pool, both manifest sections and
  `acceptance_record.json` are rewritten; OBS references recalibrated.
  The envelope metrics, the raw candidates and every raster are
  unchanged. Pre-CR files are backed up first.
- **Acceptance:** `acceptance_split.py`, its config and tests change; the
  config sha256 changes, so `standing_checks` refuses all training until
  the new record exists. Same branch-and-merge refusal window as CR-0019
  § Impact.
- **Readers of the positives' feature columns** (now sampled at the
  latest visit while `year` is the earliest): `diagnose_road_bias.py`,
  `diagnose_training.py`, `diagnose_water_bias.py`, `diagnose_wetland.py`,
  `symptom_check.py`, `clean.py`, `smoke_test_training.py` read the
  positive files; which of them read those columns, and whether any
  needs the training vintage, is deliverable 3's checklist (each is
  recorded as unaffected or changed).
- **Models:** §5. Checkpoints and logs made before the change are not
  comparable afterwards.
- **`train.sample_background_points` (BUG-0074, open):** unaffected by
  this CR and still single-vintage; the tracker's rule (no
  `--an-background > 0` until fixed) stands.
- **CR texts:** pointer lines in CR-0012 §2 (pool step 3, Draw), CR-0013
  (E-table, standing subset, § Attacks) and CR-0019 §2 (positives step 2);
  `ARCHITECTURE.md` and `CHANGELOG.md`.

## One change per CR (CR-0011 A5)
The deliverables span pipeline code, acceptance design, data
regeneration and bookkeeping; A and B are two pipeline changes.
- The pipeline and the replay cannot land separately (as CR-0019 § One
  change per CR: either alone fails R1–R4, so no record is written).
- **A and B could land separately.** They are bundled because B's strata
  are counted on the years A assigns: B pre-registered against today's
  years would be invalidated by A, and landing A alone means a full
  regeneration and acceptance change for a split that still fails the
  distribution gate B introduces. A reviewer may require the split
  (CR-0021a = A, CR-0021b = B on top of it); the review log records the
  decision.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| A stratum is short of habitat candidates | Pre-registration (§4) is an approval condition; the pipeline raises, never tops up |
| Pipeline and replay disagree | Exact R1–R4 replay by a separate agent; MC pins every row |
| The new column and the floor disagree | §2 A step 1 raises |
| Positives' feature columns no longer match `year` | Documented; readers checked (§ Impact); training reads by `year` |
| A future year outside `YEAR_STRATA` | `year_stratum` raises; E15(a) fails |
| A merged stratum hides a 2023-vs-2024 difference | O11 reports the residual within it; the pre-registration predicts it |
| A regenerated split used with an old model | §5 warning; BUG-0060 owns the mechanical refusal |
| A live run that fails part-way | CR-0019's live-run order and restore rule, reused |

## Test plan
**Validatable in this repository (synthetic):**
- `tests/test_cr0021.py`:
  - `collapse_duplicate_locations`: `first_year_min` is the earliest
    visit `>= YEAR_MIN`; null when all visits are earlier; the
    representative row is still the latest visit;
  - positives step 2: `year` becomes `first_year_min`; raises on a
    missing column or a floor disagreement; the window check sees the new
    year (test seam);
  - pool step 3: earliest non-null year wins, ties by smallest `gbif_id`;
    an all-null-year key keeps its smallest `gbif_id` and is dropped at
    step 7; existing raises kept;
  - stratified draw: per-stratum counts equal the positives', NonVeg cap
    per stratum, raise on a habitat shortfall in one stratum while
    another has surplus;
  - `year_stratum` raises outside the strata.
- Acceptance: E15 unit tests, the attack rows, the config pins, the
  existing suites.

**Validatable only on the EC2 host (real data):**
- Pre-registration (§4) and MC self-test.
- Read-only acceptance on today's files: exactly the expected FAILs
  (E11 for the missing constant, E15(b), R1–R4).
- Scratch-tree run (copied CSVs, symlinked rasters): `analyze_grouse.py`,
  `prepare_training_data.py`, `generate_negatives.py`,
  `acceptance_split.py` → all GATEs PASS, MC PASS, second run
  byte-identical.

**Not validatable under this CR:**
- How much model separation came from vintage: needs a retrain on the new
  split (CR-0020) and a seed-varied comparison (BUG-0039's lesson).
- The residual inside the merged 2023–2024 stratum beyond what O11
  reports.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (CR-0011 A3), reviewed with this CR:
      `docs/quality/evidence/CR-0021/preregister.py`, its output
      `preregister.txt` and CSVs from the live tree, `check_must_change.py`,
      `mc_selftest.py` and its output; a reviewer's PA-0021(a) wrong-tree
      runs of MC.
- [ ] 2. Acceptance changes (§3) on an unmerged CR-0021 branch by a fresh
      agent that does not write deliverable 3 (CR-0013 rule 4); read-only
      run on today's files gives exactly the expected FAILs.
- [ ] 3. Pipeline changes (§2), `tests/test_cr0021.py`, and the
      feature-column readers checklist (§ Impact); suites pass.
- [ ] 4. Scratch-tree real-data run on the EC2 host; evidence under
      `docs/quality/evidence/CR-0021/scratch/`.
- [ ] 5. Preconditions and backup (to
      `/home/ec2-user/grouse_backup/CR-0021/`, sha256 verified), as
      CR-0019 deliverable 5, plus the `evaluated_sightings_*` files.
- [ ] 6. Live run (user-authorised), as CR-0019 deliverable 6, with
      `analyze_grouse.py` run first; restore on any FAIL.
- [ ] 7. Pointer lines (§ Impact), `ARCHITECTURE.md`, `CHANGELOG.md`
      (data change, metrics not comparable, §5 warning).
- [ ] 8. Bookkeeping: BUG-0073 corrective action, recurrence review and
      status; `BUG_LOG.md`; the PA-0020 extension drafted in BUG-0073 §8
      written to `PREVENTIVE_ACTIONS.md` once §4 confirms the cause, with
      a sweep by mechanism for other per-class rules that assign a
      label-correlated attribute; tracker.
- [ ] 9. Close-out.

## Out of scope
- The retrain, calibration and new baseline: CR-0020.
- Re-fetching negatives (alternative C): a user decision, only if §4
  finds no feasible strata.
- BUG-0074 (`sample_background_points` single vintage): its own CR.
- Re-sampling the positives' feature columns at the new `year`.
- The envelope metrics' epoch (2016+ sightings; CR-0019 §2).
- `predict.py`'s latest-vintage rule.
