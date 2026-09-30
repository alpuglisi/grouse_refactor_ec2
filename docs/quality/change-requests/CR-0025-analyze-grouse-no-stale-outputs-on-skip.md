# CR-0025: `analyze_grouse.py` leaves no stale or partial region outputs on any exit and exits non-zero on a skip

**Status: v3, 2026-09-30 — APPROVED by agent quorum (CLAUDE.md §1.4; round 2: reviewers A and B both APPROVE WITH FOLLOW-UPS; the one MEDIUM text fix, the write position relative to the `env_zone` join, is met in v3 §2). Nothing has been implemented; implementation waits for the lead's go-ahead and a data host.** Review log: `CR-0025-review-log.md`.

## Scope
Remove a region's five previous outputs when its analysis starts, so that every skip and every exception leaves nothing of a previous run; make the all-non-vegetated case a full skip; make the run exit non-zero naming the skipped regions; write the four CSVs atomically and the two final ones after the `env_zone` join and before the diagnostic map (BUG-0081; PA-0038, PA-0036(a)).

## Why now
BUG-0081: five designed `return None` paths in `analyze_region` leave the previous run's `evaluated_sightings_{R}.csv` and `envelope_metrics_{R}.csv` in place, the run exits 0, and `prepare_training_data.py` / `generate_negatives.py` digest the stale files as current. Same outcome class as BUG-0049 (fixed in `generate_negatives.py` by CR-0012). It touches several functions and the CLI's exit status, so it is a CR.

## The change
### 1. Root cause
As BUG-0081 §5: outputs are written only after every stage completes, and a designed skip returns into a loop that continues and exits 0 without removing or marking the unit's previous outputs.

### 2. Code (normative), `analyze_grouse.py`
- `region_output_paths(region)` returns the region's five `PATH_TEMPLATES` paths: `evaluated`, `envelope_metrics`, `nonveg_flagged`, `availability_sample` and `diagnostic_map` (`grouse_data.py:112-114`, `:128`, `:130`; the map has no downstream reader but is a per-region output a skip would otherwise leave stale). `remove_region_outputs(region)` unlinks each that exists and prints each removal.
- `analyze_region` calls `remove_region_outputs(region)` as its first statement. Every exit other than the final `return valid, env_df` therefore leaves no output **of a previous run** for the region: the designed skips at `:741` (via `clip_to_region`, `:252`), `:759`, `:787`, `:837` and `:884`, and an unhandled exception in any stage (an exception after the `nonveg_flagged` write leaves that complete file of this run and nothing stale; consumers of the missing files fail closed).
- The all-non-vegetated check (`:882-884`) moves ahead of the `nonveg_flagged` write (`:877-878`), so the path is a full skip reached before any write (PA-0038(c)): it returns `None`, and `analyze_region` then returns either `None` or `(valid, env_df)` with `env_df` never `None` (`env_df` is built unconditionally at `:910`). The `evaluated` file is never written with a schema lacking `env_zone`/`envelope_id` (PA-0045), which writing `valid` at `:884` would have done.
- The four CSV writes (`:551`, `:877-878`, `:1099`, `:1100`) go through `write_csv_atomic(df, path)`: `df.to_csv(path + ".tmp", index=False)` then `os.replace` (PA-0036(a)); paths come from `PATH_TEMPLATES` (`:877-878` and `:1099-1100` are literals today; PA-0003).
- The two final writes (`:1099-1100`) move to **after the `env_zone`/`envelope_id` join (`:1010-1012`) and before the map block (`:1015-1097`)**; placed before the join they would write the second schema of the previous bullet. There is no exception handler around the map (BUG-0069's handlers are in `load_state_boundaries`, `:641-645`, `:654-663`, `:666-676`): a plotting exception propagates after the region's CSVs are complete, the summary is not printed, the process exits 1, and the regions after it in `REGIONS_TO_RUN` are not started (their previous outputs remain, correctly: they were not started).
- `__main__` (`:1108-1131`): after the summary, if any region's result is `None`, print `INCOMPLETE: skipped {regions}` and `raise SystemExit(1)`.
- Consumers are unchanged and fail closed: a missing `evaluated_sightings_{R}.csv` makes `prepare_training_data.py:371` and `generate_negatives.py:409`, `:443` raise `MissingDataError` through `RegionData.path` (`grouse_data.py:281-283`); `check_partition.py:382` and `:477` report a FAIL line through their `Missing` handling. `background_envelope_sample`'s own designed fallback (`return None` at `:546`: the region completes without an availability sample) is no longer masked by a previous run's file, so `check_partition.py:477` then reports it.

### 3. Acceptance
None on the split files. `tests/test_cr0025.py` on a fixture tree, run as a subprocess with the fixture as working directory (every path is cwd-relative) and `MPLBACKEND=Agg`, with the region's five output files **pre-seeded** with stale content before each run (PA-0021(a): on today's code every skip case fails because the stale files survive and the exit code is 0):
| case | assertion |
|---|---|
| a region with no box overlap (`:741`) | its five files are absent after the run; exit code 1; `INCOMPLETE` names it |
| a region with no raster for one feature (`:759`) | as above |
| a region whose every record is dropped at extraction (`:787`) | as above |
| a region whose raw files are absent while a neighbour's records fall inside its box (`:837`) | as above |
| a region whose every record is non-vegetated (`:884`) | as above, `nonveg_flagged` never written |
| a healthy region in the same run | its five files are rewritten; no `.tmp` remains |
| an exception injected into the map block | the healthy region's two CSVs exist and are complete; exit code 1 |
Healthy-tree run: the four CSVs byte-identical (deliverable 3; the PNG is excluded, matplotlib metadata varies).

## Impact
- Behaviour on a healthy tree is unchanged (same files, same bytes, exit 0).
- A skip or a crash now leaves no output of a previous run for that region and the run fails; a wrapper that ignored the exit status will notice.
- During a run a region's previous outputs are absent from the moment its analysis starts (the PA-0038 state); every consumer is a later stage, so nothing reads them concurrently.
- PA-0042 readers of `evaluated_sightings_{R}.csv` besides the pipeline consumers: `tune.py:221-223`, `tune_bins.py:219-221`, `clean.py:142-144`, `dupe_check.py:96-98`, `check_exotic.py:116-118` read it by literal path and `continue` on a missing file (pre-existing print-and-skip; they now see "absent" instead of "stale"); they are PA-0038 candidates in their own right and are recorded in the tracker (deliverable 4).

## One change per CR (CR-0011 A5)
Pipeline code only; no data or acceptance change.

## Risk: LOW
| risk | mitigation |
|---|---|
| Removing outputs a user wanted to keep across a partial run | They are regenerated by a full run; each removal is printed; the alternative (stale files digested as current) is the defect |
| The exit-code change breaks an automation | None in the tree runs `analyze_grouse.py` as a subprocess (`generate_negatives.py:80`, `tests/test_cr0018_candidates.py:23`, `tests/test_cr0012.py:504`, `tests/test_pa0027_fixes.py:25` import other names; `legacy/audit.py` has its own copy); CHANGELOG |

## Test plan
**Validatable here:** none (the script imports rasterio, sklearn, pyproj and matplotlib at module level, `:6-9`).
**Not validatable here:** `tests/test_cr0025.py` and the healthy-tree run.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0025.py` on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. Healthy-tree run on the data host: the four CSVs byte-identical to today's (sha256 recorded under `docs/quality/evidence/CR-0025/`).
- [ ] 4. Bookkeeping: BUG-0081 → FIXED; `BUG_LOG.md`; PA-0038 and PA-0036 Swept? cells (`analyze_grouse.py`'s writers now temp+replace); tracker items for the five print-and-skip readers (§ Impact); CHANGELOG.
- [ ] 5. Close-out.

## Out of scope
- `get_negatives.py`'s partial-file-by-design behaviour (recorded in PA-0038's sweep).
- A lint for designed skips (PA-0038 enforcement; its own CR).
- Per-region exception handling that records INCOMPLETE and continues (an exception is not a designed skip; PA-0027 forbids a swallow-all handler).
- The five diagnostic readers' print-and-skip (tracker).
