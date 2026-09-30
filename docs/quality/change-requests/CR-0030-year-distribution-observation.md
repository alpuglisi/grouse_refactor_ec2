# CR-0030: Observation O11 — per-class year distribution of the split files (year-only AUC and total-variation distance, with a permutation null)

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented. Split out of CR-0022 v2 (CR-0011 A5; CR-0022 review log A3/B1).** Review log: `CR-0030-review-log.md`, to be created by the first reviewer.

## Scope
Add observation O11 to CR-0013's acceptance run: on the split files, the year-only AUC and the total-variation distance between the two classes' year distributions, per region and pooled, per split and pooled, each with an in-run label-permutation z (BUG-0073's standing measurement; PA-0034(ii), which requires the PA-0020(ii) comparison to cover each class's distribution over the stratum as a named OBS statistic). Not a gate. No data change.

## Why now
E14 (CR-0019) gates the year supports and O9 prints the per-class year histograms; nothing summarises the distribution difference or gives it a null. BUG-0073 measured a year-only AUC of 0.6615 on today's files with a one-off script (`docs/quality/evidence/CR-0019/preregister.py:94-102`, `:230`; `preregister.txt:41`); its remedy (harmonising the representative-year rules, its own CR) needs the same statistic before and after, computed by the acceptance run rather than by hand.

## The change
### 1. Root cause
As BUG-0073 §5 / BUG-0077 §5: the classes' year distributions within an equal support are never compared at build time.

### 2. Code (normative), `acceptance_split.py`
- In `stats_fixed` (`:2520`), after the O9 block (`:2596-2601`), for each subset s ∈ {train, val, pooled} (rows with `split == s`; pooled = all rows) and each region group R ∈ config regions ∪ {"pooled"}, when both frames carry `year` (as O9 tests at `:2599`):
  - `O11.year_auc.{s}.{R}`: Mann-Whitney AUC of `year` as a score for the positive label, average ranks for ties: `(sum of the P rows' ranks - n_P (n_P + 1) / 2) / (n_P n_N)` over the pooled P and N years (the definition of `preregister.py:94-102`; ties are the rule here, with five distinct years). `nan` if either class is empty in (s, R).
  - `O11.year_tv.{s}.{R}`: `_tv(p, q)` (`:2382`) on the two classes' per-year share dictionaries (total-variation distance, half the sum of absolute share differences; it bounds the largest per-year share difference from above).
  - Null (PA-0021(f)): for each key, `cfg["obs"]["n_perm"]` permutations of the class label within (s, R) using `stats_fixed`'s generator (`obs.perm_seed`), reported as the in-run z in `zs` exactly as O3/O4 do (`:2559-2563`), so `obs_report` prints `(z=...)` and flags `|z| > OBS_Z`.
- `OBS_IDS = tuple(f"O{i}" for i in range(1, 12))` (`:65`); the module docstring (`:27`) and `compute_obs`'s docstring (`:2632`) read "O1-O11".
- No config key is added: O11 reuses `obs.n_perm`, `obs.perm_seed` and `obs.OBS_Z`. The config sha256 is therefore unchanged and `standing_checks`, which never reads OBS values, is unaffected.
- The full run rewrites `acceptance_record.json` (`write_record`, `:2776`, called at `:2914`) with the new `obs` block; its `config_sha256` and `artifacts` are unchanged, so the record stays valid for the standing checks. `--calibrate` is not re-run: O11 carries its own in-run z and needs no reference.

### 3. Acceptance (amends CR-0013 § Observations)
| id | class | subset | null | how it can fail (PA-0021(a)) |
|---|---|---|---|---|
| O11 (OBS) | P vs N | per split and pooled, per region and pooled | in-run label permutation, `n_perm` | `tests/test_acceptance_split.py`: on the fixture, an N whose `year` column is shifted by +2 gives `O11.year_auc.pooled.pooled` < 0.5 and `|z| > OBS_Z`; an N drawn with P's own years gives 0.5 within noise and `|z| <= OBS_Z`; on a 6-row frame with ties the reported AUC equals the hand value to 1e-12 (tie averaging); every O11 key is present for every (s, R) of the fixture |
Consistency check, recorded once: on today's files `O11.year_auc.pooled.pooled` reproduces BUG-0073's 0.6615 to four decimals (same definition, same rows: all P vs all N, both splits, three regions).
Pins that change: `OBS_IDS` (`:65`); `test_every_gate_and_obs_row_reported_once` (`tests/test_acceptance_split.py:950-963`) iterates `OBS_IDS`, so O11 must print exactly one row.

## Impact
- Read-only on today's files apart from the acceptance record's `obs` block; no split-file change; `standing_checks` unchanged.
- Runtime: 24 keys × `n_perm` (1,000) rank computations over at most 9,618 rows; seconds.
- CR-0013's OBS table gains a row; CR-0022 and BUG-0073's harmonisation CR cite O11 for before/after.

## One change per CR (CR-0011 A5)
Acceptance design only.

## Risk: LOW
| risk | mitigation |
|---|---|
| a frame without `year` (a pre-CR-0019 file) | O11 keys are computed only when both frames carry `year`, as O9 does (`:2599`); otherwise absent and the row prints `n/a` |
| permutation cost on a larger future dataset | bounded by `obs.n_perm`; O3/O4 already run the same number |

## Test plan
**Validatable here:** none (`acceptance_split.py` needs numpy, pandas and scipy; scipy is absent from this clone).
**Not validatable here:** the § 3 tests and the consistency check on today's files (data host).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): the § 3 tests on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. Full acceptance run on today's files; O11 values and the 0.6615 consistency check recorded under `docs/quality/evidence/CR-0030/`, with the rewritten record's sha256.
- [ ] 4. Bookkeeping: CR-0013 OBS table; PA-0034 Swept? cell (the (ii) statistic now exists); BUG-0073 §3 names O11 as the standing measurement; CHANGELOG.
- [ ] 5. Close-out.

## Out of scope
- Any gate on the year distribution (a threshold needs BUG-0073's remedy first).
- The acquisition fix (CR-0022) and the representative-year rules (BUG-0073's own CR).
