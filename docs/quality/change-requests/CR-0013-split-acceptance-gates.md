# CR-0013: Acceptance gates for the pooled split and draw, as a committed script

**Status: PROPOSED (v1), 2026-09-30 — awaiting review. All deliverables pending.**
History, verdicts and dispositions: `CR-0013-review-log.md`. Split from
CR-0007 v7's acceptance layer (user decision 2026-09-30); lineage in the
review log. This document states only current intent.

**Approval precondition:** PA-0021 and BUG-0033 are filed in
`PREVENTIVE_ACTIONS.md` and `BUG_LOG.md`. This CR applies PA-0021, so it
cannot be the first document to define it. See Deliverable 0.

## Scope
Specify and commit three files that decide whether CR-0012's artifacts are
accepted:
- `acceptance_split.py`
- its config, `docs/quality/acceptance_split.json`
- its attack suite, `tests/test_acceptance_split.py`

They are computed independently of the code under test. No escape mode.

## Why now
CR-0007 v1–v7 failed seven review rounds, and every break was in its
acceptance layer. The layer tested statistics of a random draw against
thresholds. Each statistic had a fair-pipeline spread wide enough to hide
a constructed attack. Ten attacks passed a whole table, and several
thresholds false-failed correct runs (for example, v7's per-region I18
failed ~52 %).

CR-0012 now specifies the split and the draw as deterministic functions of
their inputs and a seed. So acceptance can be **exact**: an independent
implementation of the specification must reproduce the artifacts
record-for-record. This CR also answers the reviewers' findings on v7's
layer; the review log carries the mapping.

## Design rules
1. **Independence (PA-0021(e)).** `acceptance_split.py` imports only
   numpy, pandas, scipy, pyproj, rasterio and geopandas, plus
   `grouse_data`'s `raster_years`/`raster_path` (not changed by CR-0012).
   - It never imports `prepare_training_data`, `generate_negatives`,
     `analyze_grouse`, `train` or `regions`.
   - It reads every constant from the config.
   - Gate E11 checks that `regions.py` and the manifest agree with the
     config, by parsing them rather than importing them.
2. **Exact gates only.** Every GATE is an exact predicate or an exact
   replay. A statistic is a GATE only if some constructed pipeline passes
   every exact gate and fails it (PA-0021(c): the two distributions must
   separate). No such pipeline is known (§ Attacks), so every statistic
   here is an OBS.
3. **No escape mode.** No flag, environment variable or config key
   disables or downgrades a GATE. Pre-CR data fails.
4. **Footing binding.** OBS references are tied to a digest of the inputs
   they were calibrated on. A changed input marks them stale; it never
   changes a GATE result.

## Config (`docs/quality/acceptance_split.json`)
- **Constants.** The CR-0007 and CR-0012 constants:
  - `REGIONS`, `MIN_SPACING_M`, `BLOCK_SIZE_M`, `BLOCK_ORIGIN_5070`,
    `BUFFER_M`, `VAL_FRACTION`, `SPLIT_SEED`, `WINDOW_PX`;
  - `NEG_RATIO`, `NONVEG_MAX_FRAC`, `W_FLOOR`, `W_CAP`, `NEUTRAL_WEIGHT`,
    `NONVEG_WEIGHT`, `MAX_COORD_UNCERTAINTY_M`;
  - `ENVELOPE_SCHEME`, the NonVeg SClass codes and EVT_PHYS prefixes;
  - the hash spec (algorithm, digest size, the three input-string
    formats);
  - the key precision (5 dp), and the path and sha256 of the county file.
- **Environment.** `pandas`, `numpy`, `scipy`, `pyproj` and PROJ versions,
  and the 4326→5070 operation string.
- **OBS references.** For each OBS cell: `mu`, `sigma`, `n_draws`, the
  null population and the footing digest. Written only by `--calibrate`.
- **`OBS_Z` = 4.** The two-sided level at which an OBS cell is flagged in
  the report. It is a reporting level, not a gate.

Deriving values:
- A **constant** changes only through a reviewed config edit, in the CR
  that changes the design value.
- The **environment** block is set when the config is committed. After an
  upgrade, E11 fails until the config is updated in a reviewed change and
  the artifacts are rebuilt and re-accepted.

## Gates (GATE, exact)
Record sets:
- **positives:** the `thinned_positives_R` files, both splits;
- **selected:** the per-region negative files;
- **pool:** `candidate_pool.csv`;
- **sightings:** every row of every `evaluated_sightings_R`.

All rows are pooled over `REGIONS` unless stated otherwise. Block ids are
recomputed from lon/lat with the config origin and size, never read from
a column.

| id | class / subset / pooling | predicate (must hold) |
|---|---|---|
| E1 | all record sets / all / per file | `state == region ==` the file's region on every row; the regions present equal `REGIONS` |
| E2 | positives / all / pooled | 0 pairs closer than `MIN_SPACING_M` |
| E3 | selected, and pool / all / pooled | 0 duplicate keys; 0 pairs closer than `MIN_SPACING_M` |
| E4 | positives, selected / per class and across classes / pooled | 0 keys in both train and val; 0 keys shared by a positive and a negative |
| E5 | positives ∪ selected / all / pooled | 0 recomputed blocks holding both a train and a val record |
| E6 | positives, selected, pool / all | recorded `block_id` equals the recomputed id on every row |
| E7 | selected, and pool / all / pooled vs sightings | nearest sighting farther than `BUFFER_M` from every row |
| E8 | positives, selected, pool / all / per region | full `WINDOW_PX` window in every `FEATURE_SPEC` raster at `rd.raster_path(feat, year)` (`dataset.py:127`). `year` is filled as at `dataset.py:98-101`: a missing or all-NaN column → the latest vintage; otherwise NaN → the column max. |
| E9 | selected / per (region, split) | count equals `round(n_pos × NEG_RATIO)`, with `n_pos` counted from the positive files; NonVeg count ≤ `round(n × NONVEG_MAX_FRAC)`; habitat pool ≥ habitat target (recounted from the pool) |
| E10 | pool, selected / all / per region | `evt_phys`, `envelope_id`, `is_nonveg`, `weight` and `weight_basis` equal the script's own recomputation, using config constants, the EVT crosswalk, binners refit on the region's `evaluated` habitat rows, and `envelope_metrics_R`; `weight` to relative 1e-12 |
| E11 | manifest | every manifest constant, the hash spec, the environment block and `REGIONS` equal the config; every artifact's sha256 equals the manifest's; `regions.py`'s values equal the config |
| E12 | pool, selected / all | `verify_partition` finds 0 records, reimplemented here (polygons, `within`, `to_crs`); the manifest's dropped list equals the recomputation on the deduplicated raw candidates |

**Replay gates.** The script re-implements CR-0012 §2 from:
- the upstream inputs: `evaluated_sightings_R`, `envelope_metrics_R`,
  `gbif_negatives_R`, the EVT crosswalk and the rasters;
- the config.

It never reads CR-0012's code. Each replayed artifact must equal the
shipped one.

| id | replayed artifact | equality required |
|---|---|---|
| R1 | thinned positives | same key set per region; same windowless-drop count |
| R2 | `block_assignments.csv` and each positive's `split` | identical |
| R3 | candidate pool | same key set; every §2 step-11 column equal (floats to relative 1e-12); every per-step count in the manifest equal. The script re-samples the rasters itself. |
| R4 | selected negatives | per (region, split) sub-pool, the same records as the top-n by `log(u)/weight`, using the pool's weights once E10 has verified them |

A pass writes `data/pipeline/acceptance_record.json`, containing:
- the sha256 of every artifact accepted;
- the config's sha256;
- the git commit;
- the OBS report.

**Standing subset.** `standing_checks()`, called by CR-0012 §5, runs:
- E1, E3 (selected only), E4, E5 and E6, over the CSVs for every config
  region;
- a check that the files' digests equal `acceptance_record.json`;
- a check that the caller's `img_size + 2·jitter` ≤ `WINDOW_PX`.

It needs no rasters and no geopandas. Every failure uses `raise`.

| gate | full run | `standing_checks` (train, calibrate, bench) | CR-0012 pipeline |
|---|---|---|---|
| E1, E3 (selected), E4, E5, E6 | GATE | GATE | — |
| E2, E3 (pool), E7–E12, R1–R4 | GATE | covered by the record digests | — |
| O1–O10 | OBS | — | — |

## Attacks (PA-0021(a))
Every recorded attack must fail at least one gate. Each attack is a
mutation in `tests/test_acceptance_split.py`. The fixture is the script's
own replay output (`--emit-reference DIR`), which must pass unmutated. So
the suite runs before CR-0012 is implemented.

| attack | recorded in | must fail |
|---|---|---|
| Box-clipped membership (pre-CR files) | `inv_reviewB_confirm.py` | E1, E4, E5 |
| Per-region thin, then pool | `inv_reviewB_pipeline.py` | E2, R1 |
| Positives thinned at 60 m | `inv_reviewF_i12.py` | R1, E11 |
| Order-dependent thinner or block draw (argv order) | `res_determ_orders.py`, `inv_reviewF_i14.py` | R1, R2 |
| Block draw with the shuffle dropped | `inv_reviewF_attack1.py` | R2 |
| Eastern-half or dense-first validation draw | `inv_reviewF_attack_i14.py`, `res_thresh_pos.py` | R2 |
| Neighbour-preferring stratified validation draw | `inv_reviewH_i14c.py` | R2 |
| Two origins, or block ids read from the column | `inv_reviewD_attack.py`, `inv_reviewD_attack2.py` | E5, E6 |
| Southern-half/southern-sixth negative draw | `inv_reviewD_cr7b.py`, `inv_reviewF_attack4b.py` | R4 |
| NH-only negative skew (Break 1) | `inv_formalA_break1.py` | R4 |
| Sorted-id split of positive-free blocks (Break 2) | `inv_formalA_attackC.py`, `inv_formalA_attackC2.py` | R3 |
| 10A, inter-region skew | `inv_formalC_attack1.py`, `inv_formalC_attack2.py` | R4 |
| 10B, feature-extremum split of positive-free blocks | `inv_formalC_attack3.py` | R3 |
| 10A″ northern candidate loss (nodata mechanism) | `inv_formalC_attack4.py`, `inv_formalC_attack5.py` | R3 |
| 10C, NonVeg top-up beyond cap | `inv_formalC_attack6.py` | E9, R4 |
| Pool strips at 3–20 % | `res_supply_*.py` | R3 |
| Weight collapse; NonVeg or species monoculture at the cap | `res_comp_attacks.py` | E10, R4 |
| Pool-side weight suppression (`weight = 1e-6`) | v7 stated limit 5 | E10 |
| `build_weight` formula changed | v7 stated limit 4 | E10 |
| No 300 m buffer | R7-A `attacks.py` A1; `inv_reviewF_attack_buffer.py` | E7, R3 |
| Draw with replacement | R7-A `attacks.py` A2 | E3, R4 |
| Draw probability ×20 within 1 km of grouse | R7-A `attacks.py` A3p | R4 |
| Validation candidates within 3 km of val positives thinned 30–40 % | R7-A `valattack.py` | R3 |
| Within-stratum duplicate negatives, 5–10 % | R7-A `comp.py`, `inv_reviewH_negdup.py` | E3, R4 |
| `--regions` subset run | v7 § The `--regions` hole | E1, E11; the CR-0012 write guard |
| Windowless record kept | `inv_reviewH_i5.py` | E8 |

The round-7 reviewer's scripts (`R7-A`) live in a session scratch
directory. Deliverable 1 commits them.

## Observations (OBS: reported, never blocking)
Each row names its class, subset, pooling axis and null population.
Values are reported as a two-sided z against the reference, and flagged
at |z| > `OBS_Z`.

Null populations:
- **N-split:** 400 replays of R2 with the block-draw seed varied, on the
  realised thinned positives.
- **N-draw:** 400 replays of R4 with the draw seed varied. The realised
  positive split and pool are held fixed.
- **N-perm:** 1,000 in-run permutations of the validation labels over the
  blocks, with the count fixed.
- **none:** reported against the previous accepted run's value.

| id | statistic | class / subset / pooling | null |
|---|---|---|---|
| O1 | median val→nearest-train distance (v7 I18) | positives / all / **pooled** | N-split |
| O2 | records per val block; block-vs-record val-fraction gap (I15) | positives / all / pooled | N-split |
| O3 | Moran's I of the val indicator, k=4 and 8 (I16) | positives / occupied blocks / pooled | N-perm |
| O4 | same over all-record blocks (I16b), selected and pool readings | both / all / pooled | N-perm |
| O5 | `Exc`, `S` (all positives vs nearest same-region negative), `Sws_val`, `Excws_val` (val vs val) beyond 1,920 m (I19′) | both / as named / **per region** | N-draw |
| O6 | NonVeg share gap; `weight_basis` TV (train vs val, and selected vs weight-proportional pool); habitat weight ratio; `evt_phys` TV within NonVeg; `common_name` TV vs pool (C9–C16) | selected vs pool / as named / per region | N-draw |
| O7 | habitat pool / habitat target, worst cell (C17); pool / target (SUP0); SUP-O; SUP-R | pool / per cell / per region | none |
| O8 | max KS val vs train over the 9 continuous features (I17); same for selected negatives, whole and habitat-only; max SMD (C5–C8) | positives; selected / as named / pooled and per region | N-split; N-draw |
| O9 | year histogram per class (PA-0020(ii); shows BUG-0034) | both / all / per region | none |
| O10 | validation fraction per class and region (I7) | both / all / per region | none |

- **`road_dist` (CR-0014).** O8 reads its values and E8 its extents; no
  other row reads it. Both are taken after CR-0014 lands. If CR-0014
  lands later, the full run and O8's calibration are repeated. The footing
  digest includes the `road_dist` rasters, so an earlier reference shows
  as stale.
- **Calibration.** `acceptance_split.py --calibrate` runs only after every
  GATE has passed. It computes the null populations with the script's own
  replay, so it never uses the pipeline under test, and writes the
  references and the footing digest.
- **Re-calibration** is required after any footing change: CR-0012's
  rebuild, CR-0014, BUG-0034's fix, or new raw inputs. It is a reviewed
  config change. The report shows old and new `mu` side by side, so a
  design-level shift is visible to that CR's reviewers.

## Stated limits
1. **Upstream inputs are taken as given**: raw candidates, rasters,
   `envelope_metrics`. They are gated by CR-0007 (P1–P7), CR-0008/0010
   and CR-0014. A defect there moves the replay with it.
2. **A shared misreading** of CR-0012 §2 by both implementations passes.
   Mitigations: the script's author and CR-0012's implementer must
   differ, and the attack suite runs. OBS flags are the residual signal.
3. **Design adequacy is not testable by a gate**: block size, validation
   fraction, NonVeg cap, weighting, and whether support is good enough.
   O1–O10 report it; CR-0009 measures its consequence.
4. **An environment change fails E11.** It is never accepted silently,
   and it requires a rebuild.

## Impact
- New files: `acceptance_split.py`, its config and the test.
  `acceptance_record.json` is written on a pass.
- Every training entry point depends on the standing subset (CR-0012 §5).
- **No escape.** CR-0009's pre-CR baselines must be captured before
  CR-0012 lands. That is a tracker item and CR-0012 deliverable 0.
- Code under test is not touched by this CR.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| The replay has a bug that false-fails a correct pipeline | Run the replay twice with shuffled input row order (outputs must be identical). The attack-suite fixture must pass unmutated. |
| Float or PROJ differences at thresholds | Squared-distance comparison in float64, specified in CR-0012 §2; environment pinned (E11) |
| Standing checks slow training start | Coordinate-only; no rasters |
| OBS mistaken for a gate, or ignored | Report states OBS in every line; flags summarised; CR-0009 reads them |

## Test plan
**Validatable here:**
- Unit tests for every E-row on synthetic records.
- The attack suite (§ Attacks) against `--emit-reference` output.
- The full script on today's pre-CR files, which must fail E1, E4, E5 and
  E11.
- Replay determinism under shuffled input order.
- `--calibrate` on the reference output.
- Runtime and memory of the full run and of `standing_checks`, recorded.

**Not validatable here:**
- Acceptance of real CR-0012 artifacts. That is CR-0012's deliverable 6.
- O8 references before CR-0014.
- Whether OBS flags predict model harm (CR-0009).

## Deliverables (in execution order)
- [ ] 0. **Precondition to approval:** file BUG-0033 and PA-0021 as a
      bookkeeping-only change, owned by this CR's author.
      - PA-0021 takes the draft text in
        `res_qms_PA-0019-0020-0021-draft-rows.md` plus clause (f): every
        distributional row names class, subset and null population.
      - Lineage: extends PA-0016.
      - Split the calibration-from-extrema root cause into its own BUG
        (next free id).
      - The Swept? cell names the sweep scope: the acceptance tables of
        CR-0007..0013, plus the thresholds in live code.
- [ ] 1. Commit only the untracked evidence scripts named in § Attacks
      (and any they import) — every other `inv_*`/`res_*` file stays
      untracked (user decision 2026-09-30). Copy the round-7 reviewer
      scripts into `docs/quality/evidence/CR-0007-r7/`.
- [ ] 2. The config, with constants and environment only (no OBS
      references yet).
- [ ] 3. `acceptance_split.py`: E1–E12, R1–R4, `standing_checks`,
      `--emit-reference`, `--calibrate`, the report and the record.
- [ ] 4. `tests/test_acceptance_split.py`: every attack row, plus the
      unit tests. Run it; all pass.
- [ ] 5. Run on today's pre-CR files. Record that the expected gates fail.
- [ ] 6. After CR-0012's rebuild: the full run passes, then
      `--calibrate`. Commit the references. After CR-0014: re-calibrate
      O8.

## Landing order
- Deliverables 0–5 before CR-0012 starts. §1.1 allows gate code before
  approval.
- Deliverable 6 runs inside CR-0012's deliverable 6.
- Independent of CR-0008 and CR-0010.
- O8 follows CR-0014.
- CR-0009 consumes the record and the OBS report.

## Out of scope
- The split and draw implementation (CR-0012); membership (CR-0007).
- Promoting any OBS to a GATE. That needs a constructed pipeline that
  passes every E and R row and fails the statistic. If one is found, it
  is a new CR.
- CI wiring (none exists; `CLAUDE.md` §3.4).
