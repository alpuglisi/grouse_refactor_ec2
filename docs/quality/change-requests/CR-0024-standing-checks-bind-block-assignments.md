# CR-0024: `standing_checks` binds `block_assignments.csv`; the standing file list is code-owned and checked at run time against every CSV path `build_datasets` resolved

**Status: v4, 2026-09-30 — APPROVED by agent quorum and signed off by the lead on 2026-09-30 (CLAUDE.md §1.4; round 2: reviewer B2 APPROVE WITH FOLLOW-UPS; round 3: reviewer C APPROVE WITH FOLLOW-UPS). Nothing has been implemented; the lead has signed off; implementation may begin (deliverables that need the data host wait for one).** Review log: `CR-0024-review-log.md`.

## Scope
Add the block table to the standing acceptance subset (digest, E0 and E6 with `include_B=True`), derive the standing file list from one code-owned constant in `acceptance_split.py`, and make `train.build_datasets` refuse a run that resolved a CSV path outside that list (BUG-0080; PA-0037).

## Why now
BUG-0080: `standing_checks` digests the 18 split CSVs and runs E6 with `include_B=False` (`acceptance_split.py:2822`, `:2840`); `train.py --an-background` reads `block_assignments.csv` at run time (`train.py:369-374`, `grouse_data.py:569-576`) to keep assumed negatives out of validation blocks (CR-0015's fix for BUG-0042). A replaced block table passes the standing check and re-opens the leak with no gate. Latent while the flag is forbidden (BUG-0074), but it is the one training-time consumer the standing subset was meant to protect.

## The change
### 1. Root cause
As BUG-0080 §5: the standing file list is a hand list fixed at CR-0013, not derived from what training-time code reads; CR-0015's gate on the run-time producer was one-time.

### 2. Code (normative)
- `acceptance_split.py` gains `STANDING_KINDS = P_KINDS + N_KINDS + ("block_assignments",)` (`:58-59` hold `P_KINDS`/`N_KINDS`): the union of the CSV kinds `build_datasets` reads (`train_positives`, `val_positives`, `train_negatives`, `val_negatives` through `RegionData.positives/negatives`, `grouse_data.py:453-475`; `block_assignments` through `GrouseData.block_assignments`, `:569-576`) and the kinds the standing gates read (`thinned_positives`, `negatives` for E6 and E14; `block_assignments` for E0's and E6's B checks). The list lives in code, not in `acceptance_split.json`: a config-owned list would be a downgrade vector (CR-0013 design rule 3; `load_config` floors `float_rel_tol` and `domain_edge`, `:101-110`, for the same reason), and `acceptance_split.py` needs no `grouse_data` import for it (`tests/test_acceptance_split.py:2264-2266`; `standing_checks` stays numpy/pandas/scipy, `:1960-1969`). The config sha is unchanged, so no record re-issue is needed.
- `standing_csv_paths(cfg)` = `[rpath(cfg, k, R) for R in regions for k in P_KINDS + N_KINDS] + [rpath(cfg, "block_assignments")]` (19 files; region-outer order as today's `digested_paths`, kept for readability: `write_json_atomic` sorts keys, `:231`, so the record's bytes never depended on it); `digested_paths(cfg)` = `standing_csv_paths(cfg) + [rpath(cfg, "candidate_pool")]` (the same 20 paths as today, `:119-123`).
- `standing_checks` runs `("E0", gate_E0, {"sets": ("P", "N", "B")})` (E0's B check exists, `:1576-1577`) and `("E6", gate_E6, {"include_C": False, "include_B": True})`; `gate_E6`'s B branch reports a problem, instead of silently skipping (`:1787-1790`), when B lacks `block_id`/`split`. After its gates run, `standing_checks` asserts that every relative path its `Context` read (`ctx._csv`, `:1483`, `:1493-1498`) is in `standing_csv_paths(cfg)`, so the gates' own reads cannot drift outside the bound list (the gate-side half of PA-0037's "derived from the consumers' input list"); E0 reads headers through `read_header(ctx.full(rel))` (`:1556`), bypassing `_csv`, so its reads are bound by the source pin of its tuple instead. `standing_checks` returns `cfg` instead of `True` (its callers test truthiness only: `tests/test_acceptance_split.py:1922-1924`, `tests/test_cr0012.py:381-396`).
- `grouse_data.RegionData.path` (`:267-284`) and `GrouseData.path` (`:557-567`) record, for every kind whose template ends in `.csv` and regardless of `must_exist`, the resolved path relative to `config.base_dir` in a `csv_paths_read` set on the `GrouseData` instance (`RegionData` gains a `_data` back-reference set by `GrouseData.__getitem__`, `:588-592`; a `RegionData` built directly records into a set of its own); every CSV load in the module except `evt_crosswalk` (`:598-606`, glob-derived, not read at training time; a PA-0003 residual) goes through `path()`, so `_load_csv`, `block_assignments`, `sightings()` and a direct `pd.read_csv(rd.path(...))` are all recorded. `train.build_datasets` keeps the `cfg` returned by `standing_checks` and, immediately after the region loop and before concatenating the parts (`:394`), asserts `data.csv_paths_read <= set(standing_csv_paths(cfg))` and raises `acceptance_split.AcceptanceError` naming any other path: the consumer-side half, checked against what was resolved, in the same path namespace as the standing list (kind names differ between `PATH_TEMPLATES` and the config's `paths`: `thinned` vs `thinned_positives`, raw `sightings` vs `evaluated_sightings`; paths do not). A literal path outside `PATH_TEMPLATES` is a PA-0003 defect and stays a review-only residual; `sample_background_points` takes `assignments` as an argument, and the read that produces it (`data.block_assignments`) is recorded.
- Pins: `tests/test_acceptance_split.py:2239` → 19; a source pin for the E0 and E6 tuples as `test_e14_in_standing_subset_without_C` does (`:1870-1872`); a test that `standing_csv_paths(cfg)` equals the paths of `STANDING_KINDS` and that every kind is a `paths` key; `digested_paths` still 20 (`:2238`).

### 3. Acceptance
| id | kind | check | how it can fail (PA-0021(a)) |
|---|---|---|---|
| digest | GATE, standing | a record made with the current block table, then one block relabelled `"train"` in `block_assignments.csv` → `standing_checks` fails naming `block_assignments.csv` | today: passes (18 files) |
| E0/E6 with B | GATE, standing (defence behind the digest) | with the digest line removed from the harness, the relabel fails E6's B branch, and a file under B's name whose columns differ from `columns.block_assignments` (a restored pre-CR-0012 per-region file, BUG-0080 §3, when its header differs) fails E0's B check and E6's column report | today: `include_B=False`; E6 skips a B without the columns silently |
| gate-side list | GATE, standing | a `standing_checks` variant whose `Context` reads `candidate_pool` fails the post-gate assertion naming it | today: no assertion |
| consumer guard | GATE, run time | harness unit test: `build_datasets(data=<fake GrouseData with csv_paths_read = {"data/negatives/candidate_pool.csv"}>, regions=[], ...)` with `standing_checks` mocked to return a loaded config → `AcceptanceError` naming the path; on the data host, `build_datasets(..., background_per_pos=0.05)` on the live tree passes the guard (B is in the list) as a guard exercise only, no checkpoint written (BUG-0074 forbids training with the flag) | today: no guard |
| must-change | pin | the §2 counts (`standing_csv_paths`, `digested_paths`) | — |

## Impact
- Training, calibration and benchmarking refuse if the block table changed since acceptance (as they already do for the 18 CSVs), and if training resolved any CSV outside the standing list; a `build_datasets` call naming a region outside `cfg["constants"]["REGIONS"]` is therefore refused too (its paths are not in the list; today the digest loop simply does not cover it), which PA-0037 intends.
- The config sha is unchanged and the live record already carries B's digest (`write_record` digests all 20, `:2785`), so the existing record stays valid; deliverable 3 only confirms `standing_checks` passes.
- Standing check cost: one small CSV digest, E0's and E6's block reads and one set comparison; one set comparison at build time.
- CR-0013's standing table gains a row.
- PA-0037's third clause (a CR-time gate on a run-time producer is re-run by `standing_checks` or its absence is recorded): CR-0015's V1 gate on what `sample_background_points` produces is not re-run here; deliverable 4 records it in the tracker as an open item naming `sample_background_points`' output as unbound (with BUG-0074, which forbids the flag).

## One change per CR (CR-0011 A5)
Binding B (the list and the standing gates) alone closes BUG-0080; the path recording and the run-time guard are PA-0037's enforcement and could land alone. They are kept together because the guard is what keeps the list honest from the consumer side, both touch the same test file and pins, and they are validated by one data-host session.

## Risk: LOW
| risk | mitigation |
|---|---|
| A consumer resolves a CSV outside the list in future | the guard refuses at run time and names the path |
| A gate reads a file outside the list in future | the post-gate assertion refuses and names it |

## Test plan
**Validatable here:** none (`acceptance_split.py` needs numpy, pandas and scipy; scipy absent here).
**Not validatable here:** the harness tests and the data-host guard exercise.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): the harness tests and the list tests on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. Confirm `standing_checks` passes on the live record and the guard exercise passes.
- [ ] 4. Bookkeeping: BUG-0080 → FIXED; `BUG_LOG.md`; PA-0037 Swept? cell; CR-0013 standing table; BUG-0042 §sweep correction ("gated by standing_checks" now true for B); tracker item for CR-0015 V1 (§ Impact).
- [ ] 5. Close-out.

## Out of scope
- `candidate_pool.csv` in the standing subset (not read at training time).
- Lifting the BUG-0074 rule on `--an-background` (its own CR).
- Re-running CR-0015's V1 gate (tracked).
