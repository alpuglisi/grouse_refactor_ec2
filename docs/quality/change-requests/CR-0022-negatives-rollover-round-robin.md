# CR-0022: Negatives acquisition: round-robin rollover across years, per-year quotas on a resumed run, and per-year totals

**Status: DRAFT v3, 2026-09-30 — awaiting round-2 review (CLAUDE.md §1.2, CR-0011 A2). Nothing has been implemented. No re-fetch: the user decided on 2026-09-30 that today's negatives files are not regenerated; this CR is a latent code fix.** Review log: `CR-0022-review-log.md`. The year-distribution observation that v2 carried is CR-0030.

## Scope
Change `get_negatives.py` so that a species' unmet quota is spread across the years that still have data on every pass, including the first pass of a resumed run over an existing file, and print the per-year totals (BUG-0077; PA-0034). No data change.

## Why now
BUG-0073 measured, after CR-0019 equalised the year supports, negatives at 1,861 of 4,809 in 2020 against positives peaking in 2022. BUG-0077 identifies the acquisition-side mechanism at `get_negatives.py:306-340`: the rollover hands each species' entire remaining shortfall to the first non-exhausted year in ascending order. A resumed run has the same defect on its first pass: `load_existing` (`:144-165`) counts existing rows per (state, species) only, so a re-run with a larger `--headroom` or a widened `--years` gives the whole delta to the first year before any rollover runs. Today's files keep their distribution; the code is fixed so that the next acquisition, in any of these forms, does not repeat it. Today's residual imbalance is BUG-0073's and is addressed without network by harmonising the representative-year rules (§ Out of scope); CR-0030 makes the distribution visible at every acceptance run.

## The change
### 1. Root cause
As BUG-0077 §5: greedy fixed-order quota allocation with no per-year bound. PA-0034 states the rule.

### 2. Code (normative), `get_negatives.py`
- `load_existing(states)` returns `(counts, by_year, seen)`: `counts[(st, common)]` as today, plus `by_year[(st, common, year)]` from each existing row's `year` field (an integer-valued string; a row whose `year` is empty counts toward `counts` only). Its only caller is `main()`.
- **Pass 1** quota per (state, species, year) becomes `min(year_cap - by_year.get((st, common, year), 0), sp_cap - counts.get(k, 0))`; a non-positive quota skips the year. On a fresh run `by_year` is empty and pass 1 is exactly today's.
- **Rollover passes**: per (state, species) and per pass, `open_years = [y for y in args.years if not pstate[(st, common, y)]["exhausted"]]`; the i-th open year (0-based, `args.years` order) is fetched with `cap = min(math.ceil(remaining / (len(open_years) - i)), remaining)`, `remaining` decreasing as today, so the last open years are not shorted by a rounding taken at the pass start (10 over 3 open years gives 4, 3, 3). The `while progress` loop, `pstate`, `exhausted`, `stalled_final` and `fetch_capped` are unchanged.
- The two passes move into `run_passes(states, years, taxa, caps, counts, by_year, seen, pstate, writers, fetch, base_params, log=print)` returning `(total, stalled_final)`, called from `main()` with `fetch=fetch_capped`, so that a test can drive it with a fake fetch. `by_year` is updated on every fetch.
- After the passes, `main()` prints per (state, species) the count by year and per state the total by year, existing rows included.
- No new flag. The old allocation is not kept reachable (PA-0034 forbids it; git history holds it). `gbif_negatives_{R}.csv` on disk is not touched and its schema (`CSV_FIELDS`) is unchanged.

### 3. Acceptance
`tests/test_cr0022.py` drives `run_passes` with a fake fetch whose per-(species, year) supply is fixed (for example 2020: 1,000 rows, 2021: 1,000, 2022: 100, 2023: 100, 2024: 0) and a small cap:
| case | assertion | fails on today's code because (PA-0021(a)) |
|---|---|---|
| fresh run | pass-1 counts per year equal `min(year_cap, supply)`; on every rollover pass each year's fetch is bounded by `ceil(remaining / n_open_left)`; the final per-year counts equal the values recorded in the test | `_greedy_reference`, a copy of today's loop kept inside the test, gives 2020 the whole shortfall; the test asserts the two allocations differ exactly where the spec says they must |
| resumed run | `by_year` pre-loaded with a front-loaded file (2020 at twice `year_cap`, 2024 at 0): pass 1 requests nothing for 2020 and `year_cap` for 2024 | today's pass 1 requests `year_cap` for 2020 first |
| exhaustion | a year reporting `exhausted` on pass 1 is never requested again; a species with no open years stops | (regression guard; passes today) |
| parser | the parsed `Namespace` has no `rollover` attribute | (guards against re-adding the flag) |
`get_negatives.py` imports `requests` at module level (`:40`); the test stubs `sys.modules["requests"]` when the import fails, so it runs here.

## Alternatives considered
- **Re-fetch now:** declined by the user (2026-09-30).
- **Proportional allocation** (shortfall split in proportion to the positives' per-year counts): couples acquisition to the positives' files; round-robin is source-independent and enough to remove the front-loading.
- **Harmonise the representative-year rule instead:** a different mechanism (BUG-0073's other candidate); § Out of scope.

## Impact
- No data change, no split-file change, no acceptance change; `standing_checks` untouched.
- A future fetch, fresh or resumed, distributes each species' shortfall across the open years.
- Paging cost: `fetch_capped` does not advance its offset past a partially consumed page (`:210-213`); with per-pass caps each open year re-reads at most one page per pass (dedupe by `seen` skips the rows already taken). The number of passes is visible in the log. Accepted, not changed here.

## One change per CR (CR-0011 A5)
Acquisition code only. The observation that v2 carried (O11) lands separately as CR-0030.

## Risk: LOW
| risk | mitigation |
|---|---|
| The refactor changes pass-1 behaviour on a fresh run | § 3 fresh-run case: pass-1 counts equal today's formula |
| A resumed run over a file with empty `year` fields | such rows count toward the species cap only (as today); the per-year print shows them as unattributed |

## Test plan
**Validatable here:** `tests/test_cr0022.py` (pure Python; `requests` stubbed).
**Not validatable here:** a real fetch (network; none is planned).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0022.py` on an unmerged branch, with `_greedy_reference` showing the failing allocation of today's loop.
- [ ] 2. Code (§2).
- [ ] 3. Bookkeeping: BUG-0077 → FIXED (code; latent until the next fetch); `BUG_LOG.md`; PA-0034 Swept? cell; BUG-0073 §6 records the no-re-fetch decision and points to CR-0030 for the measurement and to its harmonisation CR for the remedy; CHANGELOG.
- [ ] 4. Close-out.

## Out of scope
- O11, the per-class year-distribution observation: CR-0030.
- The representative-year rules (positives' latest visit vs negatives' smallest `gbif_id`): BUG-0073's no-network remedy, its own CR (measured variants: AUC 0.5584 if positives take `max(first_year, YEAR_MIN)`, 0.6125 if negatives take their key's latest year).
- A year-matched draw (6 of 30 cells short of candidates on today's pool).
- GBIF result ordering (`get_negatives.py:269-272`): a question for review; moot without a re-fetch.
- `fetch_capped`'s page re-read on a partially consumed page (§ Impact).
