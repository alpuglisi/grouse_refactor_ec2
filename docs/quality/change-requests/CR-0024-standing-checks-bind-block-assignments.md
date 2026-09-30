# CR-0024: `standing_checks` binds `block_assignments.csv`; the standing file list is config-owned and checked at run time against what `build_datasets` reads

**Status: DRAFT v2, 2026-09-30 — awaiting round-2 review (CLAUDE.md §1.2, CR-0011 A2). Nothing has been implemented.** Review log: `CR-0024-review-log.md`.

## Scope
Add the block table to the standing acceptance subset (digest, and E6 with `include_B=True`), move the standing file list into `acceptance_split.json`, and make `train.build_datasets` refuse a run that read a CSV kind outside that list (BUG-0080; PA-0037).

## Why now
BUG-0080: `standing_checks` digests the 18 split CSVs and runs E6 with `include_B=False` (`acceptance_split.py:2822`, `:2840`); `train.py --an-background` reads `block_assignments.csv` at run time (`train.py:369-374`, `grouse_data.py:570-576`) to keep assumed negatives out of validation blocks (CR-0015's fix for BUG-0042). A replaced block table passes the standing check and re-opens the leak with no gate. Latent while the flag is forbidden (BUG-0074), but it is the one training-time consumer the standing subset was meant to protect.

## The change
### 1. Root cause
As BUG-0080 §5: the standing file list is a hand list fixed at CR-0013, not derived from what training-time code reads; CR-0015's gate on the run-time producer was one-time.

### 2. Code (normative)
- `docs/quality/acceptance_split.json`, section `standing`, gains `"kinds": ["thinned_positives", "train_positives", "val_positives", "negatives", "train_negatives", "val_negatives", "block_assignments"]`: the union of the CSV kinds `build_datasets` reads (`train_positives`, `val_positives`, `train_negatives`, `val_negatives` through `RegionData.positives/negatives`, `grouse_data.py:453-475`; `block_assignments` through `GrouseData.block_assignments`, `:570-576`) and the kinds the standing gates read (`thinned_positives` and `negatives` for E6 and E14; `block_assignments` for E6's B branch). The list lives in the config, not in `grouse_data.py`: `acceptance_split.py` may not import `grouse_data` (`tests/test_acceptance_split.py:2264-2266`) and `standing_checks` must not load rasterio (`:1960-1969`; CR-0013 design, review log B-C12).
- `acceptance_split.standing_csv_paths(cfg)` derives from `cfg["standing"]["kinds"]`: for each kind, one path per config region when its `paths` template contains `{region}`, else one path (19 files today; `rpath` already handles both). `digested_paths(cfg)` = standing paths + `candidate_pool` (20, unchanged). `P_KINDS`/`N_KINDS` (`:58-59`) remain for the gates.
- `standing_checks` runs `("E6", gate_E6, {"include_C": False, "include_B": True})`.
- `grouse_data.RegionData._load_csv` (`:285-289`) and `GrouseData.block_assignments` (`:570-576`) record the kind they load in a `csv_kinds_read` set; `GrouseData.csv_kinds_read` is the union over its regions and itself. After building the datasets, `train.build_datasets` asserts `data.csv_kinds_read <= set(cfg["standing"]["kinds"])` and raises `acceptance_split.AcceptanceError` naming any other kind: the run-time half of PA-0037, checked against what was actually read rather than a hand list. `cfg` is the config `standing_checks` loaded (`acceptance_split.load_config`; `train.py:315` already imports the module).
- Pins: `tests/test_acceptance_split.py:2239` → 19; the `standing` section sha at `:2039` (the section changes); a source pin for the E6 tuple as `test_e14_in_standing_subset_without_C` does (`:1870-1872`); a test that `standing_csv_paths(cfg)`'s kinds equal `cfg["standing"]["kinds"]` and that every kind is a `paths` key.

### 3. Acceptance
| id | kind | check | how it can fail (PA-0021(a)) |
|---|---|---|---|
| digest | GATE, standing | a record made with the current block table, then one block relabelled `"train"` in `block_assignments.csv` → `standing_checks` fails naming `block_assignments.csv` | today: passes (18 files) |
| E6 with B | GATE, standing (defence behind the digest) | the same edit also fails E6's B branch when the harness drops the digest line | today: `include_B=False` |
| consumer guard | GATE, run time | a fake `GrouseData` whose `csv_kinds_read` contains `candidate_pool` → `AcceptanceError` naming it (harness unit test with `standing_checks` and `split_features` mocked as `tests/test_cr0012.py:385-396` does); on the data host, `build_datasets(..., background_per_pos=0.05)` on the live tree passes the guard (B is in the list) | today: no guard |
| must-change | pin | `len(standing_csv_paths) == 19`; config `standing` sha updated; `digested_paths` still 20 | — |

## Impact
- Training, calibration and benchmarking refuse if the block table changed since acceptance (as they already do for the 18 CSVs).
- The config sha256 changes (the `standing` section), so the live acceptance record must be re-issued by a full run on unchanged files (deliverable 3); the record already carries B's digest (`write_record` digests all 20, `:2785`), so the re-issue is for the config sha only.
- Standing check cost: one small CSV digest and E6's block read; one set comparison at build time.
- CR-0013's standing table gains a row.
- PA-0037's second clause (a CR-time gate on a run-time producer is re-run by `standing_checks` or its absence is recorded): CR-0015's V1 gate on what `sample_background_points` produces is not re-run here; deliverable 4 records it in the tracker as an open item naming `sample_background_points`' output as unbound (with BUG-0074, which forbids the flag).

## One change per CR (CR-0011 A5)
Acceptance design (the config list, the standing gate) and the one code change it needs (the run-time guard and the kind recording) cannot be separated: the list is what the guard checks against.

## Risk: LOW
| risk | mitigation |
|---|---|
| A live record made before this change | `standing_checks` fails with "made under a different config" until deliverable 3 re-issues it |
| `build_datasets` reads a kind not in the list in future | the guard refuses at run time and names it |

## Test plan
**Validatable here:** none (`acceptance_split.py` needs numpy, pandas and scipy; scipy is absent here).
**Not validatable here:** the harness tests and the record re-issue (data host).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): the harness tests and the list tests on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. Re-issue the acceptance record (config sha changes; files unchanged) and confirm `standing_checks` passes.
- [ ] 4. Bookkeeping: BUG-0080 → FIXED; `BUG_LOG.md`; PA-0037 Swept? cell; CR-0013 standing table; BUG-0042 §sweep correction ("gated by standing_checks" now true for B); tracker item for CR-0015 V1 (§ Impact).
- [ ] 5. Close-out.

## Out of scope
- `candidate_pool.csv` in the standing subset (not read at training time).
- Lifting the BUG-0074 rule on `--an-background` (its own CR).
- Re-running CR-0015's V1 gate (tracked).
