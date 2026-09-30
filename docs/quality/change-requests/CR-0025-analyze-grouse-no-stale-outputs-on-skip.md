# CR-0025: `analyze_grouse.py` leaves no stale or partial region outputs on any exit and exits non-zero on a skip

**Status: DRAFT v2, 2026-09-30 — awaiting round-2 review (CLAUDE.md §1.2, CR-0011 A2). Nothing has been implemented.** Review log: `CR-0025-review-log.md`.

## Scope
Remove a region's four previous outputs when its analysis starts, so that every skip and every exception leaves nothing stale; make the all-non-vegetated case a full skip; make the run exit non-zero naming the skipped regions; write the four CSVs atomically and the two final ones before the diagnostic map (BUG-0081; PA-0038, PA-0036(a)).

## Why now
BUG-0081: five designed `return None` paths in `analyze_region` leave the previous run's `evaluated_sightings_{R}.csv` and `envelope_metrics_{R}.csv` in place, the run exits 0, and `prepare_training_data.py` / `generate_negatives.py` digest the stale files as current. Same outcome class as BUG-0049 (fixed in `generate_negatives.py` by CR-0012). It touches several functions and the CLI's exit status, so it is a CR.

## The change
### 1. Root cause
As BUG-0081 §5: outputs are written only after every stage completes, and a designed skip returns into a loop that continues and exits 0 without removing or marking the unit's previous outputs.

### 2. Code (normative), `analyze_grouse.py`
- `region_output_paths(region)` returns the region's four `PATH_TEMPLATES` paths: `evaluated`, `envelope_metrics`, `nonveg_flagged`, `availability_sample` (`grouse_data.py:112-114`, `:130`). `remove_region_outputs(region)` unlinks each that exists and prints each removal.
- `analyze_region` calls `remove_region_outputs(region)` as its first statement. Every exit other than the final `return valid, env_df` therefore leaves no output for the region: the designed skips at `:741` (via `clip_to_region`, `:252`), `:759`, `:787`, `:837` and `:884`, and an unhandled exception in any stage.
- The all-non-vegetated path (`:882-884`) becomes a full skip: it calls `remove_region_outputs(region)` again (removing the `nonveg_flagged` file written at `:875-877`, the only output by then) and returns `None`. `analyze_region` then returns either `None` or `(valid, env_df)` with `env_df` never `None`. The `evaluated` file is never written with a schema lacking `env_zone`/`envelope_id` (PA-0045), which writing `valid` at `:884` would have done.
- The four writes (`:551`, `:876`, `:1099`, `:1100`) go through `write_csv_atomic(df, path)`: `df.to_csv(path + ".tmp", index=False)` then `os.replace` (PA-0036(a)); paths come from `PATH_TEMPLATES` (`:876` and `:1099-1100` are literals today; PA-0003).
- The two final writes (`:1099-1100`) move ahead of the map block (`:1010-1097`). There is no exception handler around the map (BUG-0069's handlers are in `load_state_boundaries`, `:653-672`): a plotting exception propagates after the region's CSVs are complete, the summary is not printed, the process exits 1, and the regions after it in `REGIONS_TO_RUN` are not started (their previous outputs remain, correctly: they were not started).
- `__main__` (`:1110-1130`): after the summary, if any region's result is `None`, print `INCOMPLETE: skipped {regions}` and `raise SystemExit(1)`.
- Consumers are unchanged: a missing `evaluated_sightings_{R}.csv` already makes `prepare_training_data.py:371` and `generate_negatives.py:409`, `:443` raise `MissingDataError` through `RegionData.path` (`grouse_data.py:279-283`), and `check_partition.py:382`, `:477` raise on a missing `nonveg_flagged` / `availability_sample`.

### 3. Acceptance
None on the split files. `tests/test_cr0025.py` on a fixture tree, with the region's four output files **pre-seeded** with stale content before each run (PA-0021(a): on today's code every skip case fails because the stale files survive and the exit code is 0):
| case | assertion |
|---|---|
| a region with no raster for one feature (`:759`) | its four files are absent after the run; exit code 1; `INCOMPLETE` names it |
| a region whose raw files are absent while a neighbour's records fall inside its box (`:837`) | as above |
| a region whose every record is non-vegetated (`:884`) | its four files are absent, `nonveg_flagged` included; exit code 1 |
| a healthy region in the same run | its four files are rewritten; no `.tmp` remains |
| an exception injected into the map block | the healthy region's two CSVs exist and are complete; exit code 1 |
Healthy-tree run: byte-identical outputs (deliverable 3).

## Impact
- Behaviour on a healthy tree is unchanged (same files, same bytes, exit 0).
- A skip or a crash now leaves no output for that region and the run fails; a wrapper that ignored the exit status will notice.
- During a run a region's previous outputs are absent from the moment its analysis starts (the PA-0038 state).

## One change per CR (CR-0011 A5)
Pipeline code only; no data or acceptance change.

## Risk: LOW
| risk | mitigation |
|---|---|
| Removing outputs a user wanted to keep across a partial run | They are regenerated by a full run; each removal is printed; the alternative (stale files digested as current) is the defect |
| The exit-code change breaks an automation | None in the tree runs `analyze_grouse.py` as a subprocess (`generate_negatives.py:80` and three tests import the module; `__main__` guarded); CHANGELOG |

## Test plan
**Validatable here:** none (the script imports rasterio, sklearn, pyproj and matplotlib at module level).
**Not validatable here:** `tests/test_cr0025.py` and the healthy-tree run.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0025.py` on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. Healthy-tree run on the data host: outputs byte-identical to today's (sha256 recorded under `docs/quality/evidence/CR-0025/`).
- [ ] 4. Bookkeeping: BUG-0081 → FIXED; `BUG_LOG.md`; PA-0038 and PA-0036 Swept? cells (`analyze_grouse.py`'s writers now temp+replace); CHANGELOG.
- [ ] 5. Close-out.

## Out of scope
- `get_negatives.py`'s partial-file-by-design behaviour (recorded in PA-0038's sweep).
- A lint for designed skips (PA-0038 enforcement; its own CR).
- Per-region exception handling that records INCOMPLETE and continues (an exception is not a designed skip; PA-0027 forbids a swallow-all handler).
