# CR-0022: Negatives acquisition: round-robin rollover across years, per-year quotas on a resumed run, and per-year totals

**Status: v4, 2026-09-30 — APPROVED by agent quorum and signed off by the lead on 2026-09-30 (CLAUDE.md §1.4; round 2 on v3: reviewers A and B both APPROVE WITH FOLLOW-UPS, conditional on the interrupt path, the `year` key type and the fetch signature being in the operative text; met in v4 §2). No re-fetch: the user decided on 2026-09-30 that today's negatives files are not regenerated; this CR is a latent code fix. Nothing has been implemented; the lead has signed off; implementation may begin (deliverables that need the data host wait for one).** Review log: `CR-0022-review-log.md`. The year-distribution observation that v2 carried is CR-0030.

## Scope
Change `get_negatives.py` so that a species' unmet quota is spread across the years that still have data on every pass, including the first pass of a resumed run over an existing file, and print the per-year totals (BUG-0077; PA-0034). No data change.

## Why now
BUG-0073 measured, after CR-0019 equalised the year supports, negatives at 1,861 of 4,809 in 2020 against positives peaking in 2022. BUG-0077 identifies the acquisition-side mechanism at `get_negatives.py:306-340`: the rollover hands each species' entire remaining shortfall to the first non-exhausted year in ascending order. A resumed run has the same defect on its first pass: `load_existing` (`:144-165`) counts existing rows per (state, species) only, so a re-run with a larger `--headroom` or a widened `--years` gives the whole delta to the first year before any rollover runs. Today's files keep their distribution (Status); the code is fixed so that the next acquisition, in any of these forms, does not repeat it. Today's residual imbalance is BUG-0073's and is addressed without network by harmonising the representative-year rules (§ Out of scope); CR-0030 measures the distribution at every acceptance run.

## The change
### 1. Root cause
As BUG-0077 §5: greedy fixed-order quota allocation with no per-year bound. PA-0034 states the rule.

### 2. Code (normative), `get_negatives.py`
- `load_existing(states)` returns `(counts, by_year, seen)`: `counts[(st, common)]` as today, plus `by_year[(st, common, int(row["year"]))]` from each existing row's `year` field (`fetch_capped` writes it from `r.get("year")`, `:202`, under a query filtered by `year`, `:269-272`, so it is the query year or empty; an empty field counts toward `counts` only and is printed as unattributed). The key uses `int(...)` because `args.years` are integers (`:230-231`); a string key would make every lookup miss and leave the resumed-run defect intact. Its only caller is `main()`.
- **Pass 1** quota per (state, species, year) becomes `min(year_cap - by_year.get((st, common, year), 0), sp_cap - counts.get(k, 0))`; a non-positive quota skips the year. On a fresh run `by_year` is empty and pass 1 is exactly today's.
- **Rollover passes**: per (state, species) and per pass, `open_years = [y for y in args.years if not pstate[(st, common, y)]["exhausted"]]`; the i-th open year (0-based, `args.years` order) is fetched with `cap = math.ceil(remaining / (len(open_years) - i))`, `remaining` decreasing as today, so the last open years are not shorted by a rounding taken at the pass start (10 over 3 open years gives 4, 3, 3; a year exhausted mid-pass leaves its unfilled share to the later years of the same pass and is excluded from the next pass). The `while progress` loop, `pstate`, `exhausted`, `stalled_final` and `fetch_capped` are unchanged.
- The two passes move into `run_passes(states, years, taxa, caps, counts, by_year, seen, pstate, writers, fetch, base_params, tally, log=print)`. `fetch` has the signature `fetch(writer, params, st, common, sci, cap_left, seen, start_offset) -> (n, stopped, exhausted, offset)`; `main()` passes `functools.partial(fetch_capped, session)` (`fetch_capped` takes `session` first, `:168-169`). `tally` is a caller-supplied dict that `run_passes` updates in place (`tally["total"]`, `tally["stalled_final"]`) and returns; `main()` initialises it before its existing `try` / `except KeyboardInterrupt` / `finally` (`:277-278`, `:341-345`) around the call, so a Ctrl-C mid-fetch (a supported path, `:342`, docstring `:27-28`) still reaches the summary (`:347`) and the per-year print with the partial tallies bound. `by_year` is updated on every fetch.
- `build_parser()` is factored out of `main()` (`:225-237`) so the parser can be exercised without the `requests.Session()` that `main()` opens next (`:239-241`).
- After the passes, `main()` prints per (state, species) the count by year and per state the total by year, existing rows included.
- No new flag. The old allocation is not kept reachable (PA-0034 forbids it; git history holds it). `gbif_negatives_{R}.csv` on disk is not touched and its schema (`CSV_FIELDS`) is unchanged.

### 3. Acceptance
`tests/test_cr0022.py` drives `run_passes` with a fake fetch of the §2 signature whose per-(species, year) supply is fixed (for example 2020: 1,000 rows, 2021: 1,000, 2022: 100, 2023: 100, 2024: 0) and a small cap:
| case | assertion | fails on today's code because (PA-0021(a)) |
|---|---|---|
| fresh run | pass-1 counts per year equal `min(year_cap, supply, sp_cap - counts)` (the last year of pass 1 is clipped by the species cap, `:287-288`); on every rollover pass each year's fetch is bounded by `ceil(remaining / n_open_left)`; the final per-year counts equal the values recorded in the test | `_greedy_reference`, a copy of today's loop (`:306-340` at `7f40bc4`, cited in its docstring) kept inside the test, gives 2020 the whole shortfall; the test asserts the two allocations differ exactly where the spec says they must |
| resumed run | a temporary `gbif_negatives_{R}.csv` written with `CSV_FIELDS` and front-loaded rows (2020 at twice `year_cap`, 2024 at 0) is read by `load_existing` itself; pass 1 requests nothing for 2020 and `year_cap` for 2024 | today's `load_existing` has no per-year counts and pass 1 requests `year_cap` for 2020 first |
| exhaustion | a year reporting `exhausted` on pass 1 is never requested again; a species with no open years stops | (regression guard; passes today) |
| interrupt | a fake fetch raising `KeyboardInterrupt` on its third call leaves `tally["total"]` equal to the rows written before it | today's `total` is a local of `main()` (guard for the refactor) |
| parser | `build_parser().parse_args([...])` has no `rollover` attribute | (guards against re-adding the flag) |
Commit order for deliverable 1: extract `run_passes` with today's allocation; add the test (fails); apply the fix. The test stubs `sys.modules["numpy"]` (`regions.py:24` imports numpy at module level and `get_negatives.py:46-48` imports `regions`; numpy is used only inside `regions.py`'s functions) and, where absent, `sys.modules["requests"]`, so it runs here.

## Alternatives considered
- **Re-fetch now:** declined (Status).
- **Proportional allocation** (shortfall split in proportion to the positives' per-year counts): couples acquisition to the positives' files; round-robin is source-independent and enough to remove the front-loading.
- **Harmonise the representative-year rule instead:** a different mechanism (BUG-0073's other candidate); § Out of scope.

## Impact
- No data change, no split-file change, no acceptance change; `standing_checks` untouched.
- A future fetch, fresh or resumed, distributes each species' shortfall across the open years.
- Paging cost: `fetch_capped` does not advance its offset past a partially consumed page (`:210-213`); with per-pass caps each open year re-reads at most one page per pass (dedupe by `seen` skips the rows already taken). The number of passes is visible in the log. Accepted, not changed here.

## One change per CR (CR-0011 A5)
Acquisition code only (O11 is CR-0030).

## Risk: LOW
| risk | mitigation |
|---|---|
| The refactor changes pass-1 behaviour on a fresh run | § 3 fresh-run case: pass-1 counts equal today's formula |
| A resumed run over a file with empty `year` fields | such rows count toward the species cap only (as today); the per-year print shows them as unattributed |
| The refactor loses the interrupt path's summary | § 3 interrupt case; `tally` bound in `main()` before the `try` |

## Test plan
**Validatable here:** `tests/test_cr0022.py` (pure Python; numpy and, if absent, `requests` stubbed).
**Not validatable here:** a real fetch (network; none is planned).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0022.py` on an unmerged branch in the § 3 commit order, with `_greedy_reference` showing the failing allocation of today's loop.
- [ ] 2. Code (§2).
- [ ] 3. Bookkeeping: BUG-0077 → FIXED (code; latent until the next fetch); `BUG_LOG.md`; PA-0034 Swept? cell; BUG-0073 §6 records the no-re-fetch decision and points to CR-0030 for the measurement and to its harmonisation CR for the remedy; CHANGELOG.
- [ ] 4. Close-out.

## Out of scope
- O11, the per-class year-distribution observation: CR-0030.
- The representative-year rules (positives' latest visit vs negatives' smallest `gbif_id`): BUG-0073's no-network remedy, its own CR (measured variants: AUC 0.5584 if positives take `max(first_year, YEAR_MIN)`, 0.6125 if negatives take their key's latest year).
- A year-matched draw (6 of 30 cells short of candidates on today's pool).
- GBIF result ordering (`get_negatives.py:269-272`): a question for review; moot without a re-fetch.
- `fetch_capped`'s page re-read on a partially consumed page (§ Impact).
- Rollover passes on a resumed run split the shortfall equally over the open years regardless of the existing per-year totals (PA-0034-compliant; a front-loaded file keeps its head start on those passes).
