# CR-0030: Observation O11 — per-class year distribution of the split files (year-only AUC and total-variation distance, with a permutation null)

**Status: v2, 2026-09-30 — APPROVED by agent quorum and signed off by the lead on 2026-09-30 (CLAUDE.md §1.4; round 1: reviewers A and B both APPROVE WITH FOLLOW-UPS, conditional on the `OBS_IDS` form, the lineage table and the null's name being in the operative text; met in v2). Split out of CR-0022 v2 (CR-0011 A5); the moved findings and their dispositions are in `CR-0030-review-log.md` § Lineage (PA-0024(b)). Nothing has been implemented; the lead has signed off; implementation may begin (deliverables that need the data host wait for one).**

## Scope
Add observation O11 to CR-0013's acceptance run: on the split files, the year-only AUC and the total-variation distance between the two classes' year distributions, per region and pooled, per split and pooled, each with an in-run class-label permutation z (BUG-0073's standing measurement; PA-0034(ii), which requires the PA-0020(ii) comparison to cover each class's distribution over the stratum as a named OBS statistic). Not a gate. No data change.

## Why now
E14 (CR-0019) gates the year supports and O9 prints the per-class year histograms; nothing summarises the distribution difference or gives it a null. BUG-0073 measured a year-only AUC on the frames the CR-0019 `Floored` replay predicted (`docs/quality/evidence/CR-0019/preregister.py:94-102`, `:189-190`, `:230`; `preregister.txt:41`), which CR-0019's live run reproduced (`00b0b84`; BUG-0073 §3 totals 4,809/4,809); its remedy (harmonising the representative-year rules, its own CR) needs the same statistic before and after, computed by the acceptance run rather than by hand.

## The change
### 1. Root cause
As BUG-0073 §5 / BUG-0077 §5: the classes' year distributions within an equal support are never compared at build time.

### 2. Code (normative), `acceptance_split.py`
- A module-level `_year_auc(pos_years, neg_years)` next to `_tv` (`:2382`): Mann-Whitney AUC of `year` as a score for the positive label, average ranks for ties (`(sum of the P rows' ranks - n_P (n_P + 1) / 2) / (n_P n_N)`, the definition of `preregister.py:94-102`; ties are the rule here, with five distinct years); `nan` if either class is empty. Used by the O11 code and by the § 3 tie test.
- In `stats_fixed` (`:2520`), after the O9 block (`:2593-2601`), **only when `Nsel` is not `None` and both frames carry `year`** (as O9 tests at `:2599`; years taken per class through O9's `dropna().astype(int)`), for each subset s ∈ {train, val, pooled} (rows with `split == s`; pooled = all rows) and each region group R ∈ config regions ∪ {"pooled"} (`_region_col`, `:2439`):
  - `O11.year_auc.{s}.{R}` = `_year_auc(P years, N years)` over the (s, R) rows.
  - `O11.year_tv.{s}.{R}` = `_tv(p, q)` on the two classes' per-year share dictionaries (total-variation distance, half the sum of absolute share differences; it bounds the largest per-year share difference from above).
  - Null (PA-0021(f)), named **N-perm-class**: `cfg["obs"]["n_perm"]` in-run permutations of the class label over the records within (s, R) using `stats_fixed`'s generator (`obs.perm_seed`); the ranks are computed once per (s, R) and the labels permuted, one permutation serving both statistics (12 cells × `n_perm` draws); reported as the in-run z in `zs` exactly as O3/O4 do (`:2558-2561`), so `obs_report` prints `(z=...)` and flags `|z| > OBS_Z`. This is a different population from CR-0013's **N-perm** (val labels over blocks); deliverable 4 adds the name to CR-0013's null list.
  - Guards are narrow (an empty class in a cell gives `nan`, no exception), so `compute_obs`'s broad handler (`:2657-2660`, pinned `('acceptance_split.py', 'compute_obs', 2)` in `tests/test_pa0027_lint.py:113`), `full_run` and their pinned handlers are not edited and O3/O4/O7/O9/O10 cannot be blanked by O11.
- `OBS_IDS` (`:65`) becomes an explicit tuple to which this CR appends `"O11"`; the docstrings at `:27`, `:2433` and `:2632` name O11. Id map across the open CRs, all in `acceptance_split.py`: O11 (this CR), O12 (CR-0029), O13 (CR-0020); each CR appends its own id, the tuple lists landed ids only and need not be contiguous (`obs_report`, `:2745`, and `full_run`, `:2905`, iterate it; a `range(1, n)` literal would either drop a landed id's row or demand a row nobody produces).
- No config key is added: O11 reuses `obs.n_perm`, `obs.perm_seed` and `obs.OBS_Z`. The config sha256 (the hash of the raw config bytes, `load_config`, `:114`) is therefore unchanged and `standing_checks`, which reads `config_sha256`, `artifacts` and `rasters` and never OBS values, is unaffected.
- The full run rewrites `acceptance_record.json` (`write_record`, `:2776`, called at `:2913`) with the new `obs` block and refreshed `created_utc`, `commit`, `dirty` and `rasters` entries; its `config_sha256` and `artifacts` are unchanged, so the record stays valid for the standing checks. `--calibrate` is not re-run: O11 carries its own in-run z and needs no reference (`calibrate` writes references for O1/O2/O5/O6/O8 only). The in-run z values are printed, not stored in the record (`:2794` stores `vals`), so deliverable 3 captures the log.
- CR-0013 design rule 4 (separate authorship of the acceptance code) binds: deliverable 1 is written by a fresh reviewer against this text.

### 3. Acceptance (amends CR-0013 § Observations)
| id | class | subset | null | how it can fail (PA-0021(a)) |
|---|---|---|---|---|
| O11 (OBS) | P vs N | per split and pooled, per region and pooled | N-perm-class, `obs.n_perm` (the test config's is 30, `tests/test_acceptance_split.py:466`) | `tests/test_acceptance_split.py`: on the fixture (four shared years, `:68`), an N whose `year` column is shifted by +2 gives `O11.year_auc.pooled.pooled` < 0.5 and `|z| > OBS_Z` even at 30 draws; an N drawn with P's own year multiset gives exactly 0.5 and `|z| <= OBS_Z`; `_year_auc` on a 6-row tied frame equals the hand value to 1e-12; every O11 key is present for every (s, R) of the fixture (the real pin: `test_every_gate_and_obs_row_reported_once` would also accept an `n/a` row) |
Consistency check, recorded once: on today's files `O11.year_auc.pooled.pooled` (all thinned positives vs all negatives, both splits, three regions: preregister's P1/N1) reproduces BUG-0073's value to four decimals (§ Why now); a larger difference is a finding to investigate, not a failed deliverable.

## Impact
- Read-only on today's files apart from the acceptance record's `obs` block and refreshed metadata; no split-file change; `standing_checks` unchanged.
- Runtime: 12 cells × `n_perm` (1,000) label permutations over at most 9,618 rows with ranks computed once per cell; seconds.
- CR-0013's OBS table gains a row and its null list gains N-perm-class; CR-0022 and BUG-0073's harmonisation CR cite O11 for before/after.
- Tracker item `CR-0007-0008-OPEN-ISSUES.md` (CR-0017 round 1, "optional OBS row for the edge-band support asymmetry", owner lead, "decide with the next change to `acceptance_split.py`'s OBS set"): this is that change; decision recorded here and in the tracker: **not bundled** (one observation per CR, A5; the edge band is a spatial axis unrelated to this CR's), it stays its own small acceptance amendment, owner lead.

## One change per CR (CR-0011 A5)
Acceptance design only.

## Risk: LOW
| risk | mitigation |
|---|---|
| a frame without `year` (a pre-CR-0019 file), or `Nsel is None` | O11 keys are computed only when both frames carry `year` and N is present; otherwise absent and the row prints `n/a` |
| permutation cost on a larger future dataset | bounded by `obs.n_perm`; O3/O4 already run the same number |

## Test plan
**Validatable here:** none (`acceptance_split.py` needs numpy, pandas and scipy; scipy is absent from this clone).
**Not validatable here:** the § 3 tests and the consistency check on today's files (data host).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): the § 3 tests and the O11 code on an unmerged branch, written by a fresh reviewer (CR-0013 design rule 4).
- [ ] 2. Code (§2) reviewed against this text.
- [ ] 3. Full acceptance run on today's files; O11 values, the in-run z values (from the log) and the consistency check recorded under `docs/quality/evidence/CR-0030/`, with the rewritten record's sha256.
- [ ] 4. Bookkeeping: CR-0013 OBS table and null list (N-perm-class); PA-0034 Swept? cell (the (ii) statistic now exists); BUG-0073 §3 names O11 as the standing measurement; tracker (edge-band decision, § Impact); CHANGELOG.
- [ ] 5. Close-out.

## Out of scope
- Any gate on the year distribution (a threshold needs BUG-0073's remedy first).
- The acquisition fix (CR-0022) and the representative-year rules (BUG-0073's own CR).
- The edge-band support-asymmetry OBS (§ Impact).
