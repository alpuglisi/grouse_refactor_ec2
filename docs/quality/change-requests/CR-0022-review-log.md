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
| 2 | v3 | A (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1 text) | 0 |
| 2 | v3 | B (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on M1 text) | 0 |

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

## Round 2 (v3), reviewer A (bounded, CR-0011 A2)
A1/B4 (BLOCKING) verified RESOLVED (today's `load_existing` `:144-165`,
pass 1 `:287-288`; the resumed-run row fails today); A2/B2 resolved by
move to CR-0030 (each item verified there); A3/B1 resolved.
- **A-N1 MAJOR:** `run_passes` "returning `(total, stalled_final)`" with
  the `KeyboardInterrupt` handler unmentioned: today `total`/`stalled_final`
  are bound before the `try` (`:277-278`) and the handler (`:341-342`)
  falls through to the summary (`:347`); a Ctrl-C mid-fetch would leave
  both unbound → `UnboundLocalError` after the files close.
- A-N2 MEDIUM: `fetch_capped` needs `session` (`:168-169`), which
  `run_passes` does not receive; state the fetch callable's signature.
- A-N3 LOW: `by_year` key type (string `row["year"]` vs int `args.years`).
- A-N4 LOW: the parser is built inside `main()` (`:225-237`), which then
  opens a session; say how the test obtains the `Namespace`.
- A-N5 LOW: rollover passes on a resumed run ignore existing per-year
  totals (PA-0034-compliant); record.
- A-N6 LOW (A4): the decision repeated.

## Round 2 (v3), reviewer B (bounded, CR-0011 A2)
Same RESOLVED table; the per-open-year cap re-derived (4,3,3; 3,3,2,2;
mid-pass exhaustion; termination); `load_existing`'s single caller.
- **B-M1 MAJOR:** `by_year` key type — a string key makes every lookup
  miss and A1 is intact — and the resumed-run test pre-loads `by_year`
  without going through `load_existing`, so it would pass anyway.
- B-M2 MEDIUM: same as A-N2 (`functools.partial(fetch_capped, session)`).
- B-M3 MEDIUM: "stubs `requests` so it runs here" is false here:
  `requests` is installed, numpy is not, and `regions.py:24` imports it
  (`get_negatives.py:46-48` import `regions`); a numpy stub suffices.
- B-L1 LOW: fresh-run pass-1 assertion omits the `sp_cap - counts` clip.
- B-L2 LOW: pin `_greedy_reference` to today's loop by commit; commit
  order extract → test → fix.
- B-L3 LOW (A4): pointers repeated.

## v4 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-N1 | MAJOR | **Accept** — §2 `run_passes` bullet: caller-supplied `tally` dict updated in place; `main()` keeps its `try`/`except KeyboardInterrupt`/`finally`; § 3 interrupt case; risk row |
| B-M1 / A-N3 | MAJOR / LOW | **Accept** — §2 first bullet: `int(row["year"])`, empty unattributed; § 3 resumed-run case goes through `load_existing` on a temp CSV |
| A-N2 / B-M2 | MEDIUM | **Accept** — §2 `run_passes` bullet: fetch signature; `functools.partial(fetch_capped, session)` |
| B-M3 | MEDIUM | **Accept** — § 3 last paragraph and § Test plan: numpy stub (and `requests` only if absent) |
| A-N4 | LOW | **Accept** — §2 `build_parser()` bullet; § 3 parser case |
| A-N5 | LOW | **Accept** — § Out of scope last bullet |
| A-N6 / B-L3 | LOW | **Accept** — decision and pointer stated once in Status and referenced |
| B-L1 | LOW | **Accept** — § 3 fresh-run case includes the clip |
| B-L2 | LOW | **Accept** — § 3: `_greedy_reference` cites `:306-340` at `7f40bc4`; commit order stated; deliverable 1 |

## Versions
| version | change |
|---|---|
| v1 | initial draft (re-fetch of 2023–2024 negatives) |
| v2 | no re-fetch (user decision 2026-09-30); latent code fix plus O11 |
| v3 | code only; O11 split to CR-0030; resumed-run quotas; per-year cap recomputed per open year; no flag; round-1 dispositions |
| v4 | `tally` and the interrupt path; `int(year)` keys; fetch signature; `build_parser()`; numpy stub; round-2 dispositions above; approved by agent quorum |
