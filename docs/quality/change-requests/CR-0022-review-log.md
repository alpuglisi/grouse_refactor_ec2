# CR-0022 review log

## Lineage
From BUG-0077 (2026-09-30 static review; candidate cause of BUG-0073).
Author: the review session that filed BUG-0077. v1 (re-fetch) was
superseded by the user's decision of 2026-09-30 (no re-fetch) before any
review; v2 is the first reviewed version. Reviewers: two fresh agents,
each re-deriving from the code before reading the CR (CLAUDE.md §1.2,
§1.4 agent-only quorum). Review logs were not read by the reviewers.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v2 | A (agent, fresh) | REVISE | 1 |
| 1 | v2 | B (agent, fresh) | REVISE | 0 |

## Round 1, reviewer A
- **A1 BLOCKING:** the fix does not cover a resumed run. `load_existing`
  (`get_negatives.py:144-165`) counts per (state, species) only; pass 1
  walks years ascending with `quota = min(year_cap, sp_cap - counts)`, so
  a re-run with `--headroom 7` or a widened `--years` over today's
  front-loaded file gives the whole delta to 2020 before rollover runs.
  "Pass 1 is unchanged (it already caps per year)" is false on resume.
- A2 MAJOR: O11 not implementable as written: `acceptance_split.py --obs`
  does not exist (`main`, `:2926-2949`); `OBS_IDS = range(1, 11)` (`:65`)
  and the docstring (`:27`) must change; a new config key would make
  `standing_checks` refuse training until a full run rewrites the record;
  and the full run is not read-only (`write_record`, `:2776`, `:2914`).
- A3 MAJOR (A5): acquisition code and an acceptance amendment are two
  categories and can land separately.
- A4 MEDIUM: `--rollover greedy` keeps the PA-0034-forbidden allocation
  reachable by a flag.
- A5 LOW: `per_year` fixed at pass start with ascending order shorts the
  last open years (R=10, n=3 → 4, 4, 2).
- A6 LOW: `get_negatives.py` imports `requests`, not pandas (`:40`);
  per-year totals must include existing rows; O11(b) can be defined from
  O9's `year_hist` (`:2598-2601`) and `_tv` (`:2382`).

## Round 1, reviewer B
- B1 MAJOR (A5): same as A3; suggested making CR-0022 the O11 amendment
  and the loop change a fix confined to `main()`.
- B2 MAJOR: same as A2, plus: O11 must extend O9, live in `stats_fixed`
  with in-run permutation z like O3/O4, change `OBS_IDS`, the docstring
  and `tests/test_acceptance_split.py:958`; the AUC must be defined
  (Mann-Whitney with average tie ranks, `evidence/CR-0019/preregister.py:94-102`)
  or the "reproduce 0.6615" check is ill-posed.
- B3 MEDIUM: same as A4.
- B4 MEDIUM: per-year totals and pass 1 on resume need per-year existing
  counts (same mechanism as A1; at least record as out of scope).
- B5 LOW: `fetch_capped` does not advance `offset` on a partially
  consumed page (`:210-213`); small per-pass caps re-download the same
  page per open year.
- B6 LOW (A4): "no re-fetch" stated five times; line ref `:306-343` is
  `:306-340`.

## v3 dispositions (both reviewers)
| # | sev | disposition (operative location) |
|---|---|---|
| A1 / B4 | BLOCKING / MEDIUM | **Accept** — §2: `load_existing` returns `by_year`; pass-1 quota `min(year_cap - by_year[(st, common, year)], sp_cap - counts[k])`; § 3 resumed-run case fails on today's code |
| A2 / B2 | MAJOR | **Accept** — O11 moved to CR-0030, which specifies it inside `stats_fixed` with in-run z, no config key, `OBS_IDS`/docstring/test pins, the Mann-Whitney definition with average tie ranks, and states that the full run rewrites the record |
| A3 / B1 | MAJOR | **Accept** — split: CR-0022 v3 is acquisition code only; CR-0030 is the acceptance amendment. B's alternative (a `main()`-only fix) is not trivial under CLAUDE.md §1 once `load_existing` changes (A1), so the code side stays a CR |
| A4 / B3 | MEDIUM | **Accept** — §2: no flag; the old allocation is not kept reachable |
| A5 | LOW | **Accept** — §2: cap recomputed per open year as `ceil(remaining / n_open_left)` |
| A6 | LOW | **Accept** — § 3 last paragraph (`requests`); §2 per-year print includes existing rows; O11(b) uses `_tv` in CR-0030 |
| B5 | LOW | **Accept as recorded cost** — § Impact states the bound (one page per open year per pass) and § Out of scope leaves `fetch_capped` unchanged |
| B6 | LOW | **Accept** — the decision is stated once in Status and referenced elsewhere; `:306-340` |

## Versions
| version | change |
|---|---|
| v1 | initial draft (re-fetch of 2023–2024 negatives) |
| v2 | no re-fetch (user decision 2026-09-30); latent code fix plus O11 |
| v3 | code only; O11 split to CR-0030; resumed-run quotas; per-year cap recomputed per open year; no flag; dispositions above |
