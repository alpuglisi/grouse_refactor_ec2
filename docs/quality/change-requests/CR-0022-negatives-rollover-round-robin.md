# CR-0022: Negatives acquisition: round-robin rollover across years, per-year totals, and a year-distribution observation beside E14

**Status: DRAFT v2, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented. User decision 2026-09-30: the negatives are NOT re-fetched; this CR is a latent code fix plus a read-only observation on today's files.** Review log: `CR-0022-review-log.md`, to be created by the first reviewer.

## Scope
Change `get_negatives.py`'s rollover so a species' unmet quota is spread across the years that still have data instead of handed whole to the earliest one, print the per-year totals, and add an observation comparing the two classes' year distributions on the split files (BUG-0077; candidate cause of BUG-0073). No re-fetch, no data change.

## Why now
BUG-0073 measured, after CR-0019 equalised the year supports, negatives at 1,861 of 4,809 in 2020 against positives peaking in 2022, and year alone predicting the label at AUC 0.6615. BUG-0077 identifies the acquisition-side mechanism: `get_negatives.py:311-333` passes the entire remaining shortfall to the first non-exhausted year in ascending order. The user has decided not to re-fetch, so today's files keep their distribution; the code is fixed so the next acquisition (a new region, a new epoch, a widened `--years`) does not repeat it, and the observation makes the distribution visible at every acceptance run. The remaining year imbalance on today's files is BUG-0073's, to be addressed without network by harmonising the representative-year rules (§ Out of scope).

## The change
### 1. Root cause
As BUG-0077 §5: greedy fixed-order quota allocation with no per-year bound, and no build-time check of the per-class year distributions (E14 compares supports only). PA-0034 states the rule.

### 2. Code (normative)
`get_negatives.py`, rollover passes (`:306-343`), factored into `allocate_rollover(remaining, open_years)` (pure, testable) and the loop that calls it:
- Per (state, species) and per pass, `open_years = [y for y in args.years if not pstate[(st, common, y)]["exhausted"]]`; if empty, stop for that species.
- `per_year = math.ceil(remaining / len(open_years))`; each open year is fetched with cap `min(per_year, remaining)` (today: `remaining`), in `args.years` order; `remaining` decreases as today; the `while progress` loop repeats until caps are met or every year is exhausted.
- After both passes, print per (state, species) the counts by year and, per state, the total by year.
- `--years` default unchanged; a `--rollover {round-robin,greedy}` flag defaulting to `round-robin` keeps the old behaviour reachable for comparison only.
Pass 1 is unchanged (it already caps per year). `gbif_negatives_{R}.csv` on disk is not touched.

### 3. Acceptance (amends CR-0013)
**OBS O11 (PA-0021(f)).** Per-class year distribution on the split files. Statistic: (a) the year-only AUC as BUG-0073 measured it (year as the score, class as the label) and (b) the largest absolute difference between the two classes' per-year shares. Class: pooled P vs N (train and val separately, and pooled); subset: per region and pooled; null: the same statistics over ≥ 100 label permutations, reported as quantiles. Not a gate. Computed by `acceptance_split.py --obs` on today's files; E14 unchanged. Its first value on today's files should reproduce BUG-0073's 0.6615 (a consistency check on the implementation, recorded).

## Alternatives considered
- **Re-fetch now:** declined by the user (2026-09-30); would have been the only way to change today's distribution through this mechanism.
- **Proportional allocation** (shortfall split in proportion to the positives' per-year counts): couples acquisition to the positives' files; round-robin is source-independent and enough to remove the front-loading.
- **Harmonise the representative-year rule instead:** a different mechanism (BUG-0073's other candidate), no network needed; § Out of scope.

## Impact
- No data change; no split-file change; `standing_checks` unaffected (O11 is an OBS, not part of the standing subset).
- `get_negatives.py`'s output schema is unchanged; a future fetch distributes the shortfall evenly.
- CR-0013 gains O11.

## One change per CR (CR-0011 A5)
Acquisition code and one observation; no data or gate change.

## Risk: LOW
| risk | mitigation |
|---|---|
| The refactor changes pass-1 behaviour | Pass 1 untouched; the unit test replays a recorded pass-1/pass-2 sequence with a fake `fetch_capped` and asserts pass-1 counts identical, rollover counts per year bounded by `ceil(remaining / n_open)` |
| `--rollover greedy` left as the default by mistake | The test asserts the parser default |

## Test plan
**Validatable here:** the allocation unit test with a fake `fetch_capped` (pure Python once the loop is factored out; `get_negatives.py` imports `requests`/`pandas` at module level, so the function lives where the test can import it without network, or the test stubs those modules).
**Not validatable here:** O11 on the real files (data host, read-only).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): O11 and the allocation unit test on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. O11 on today's files (read-only), recorded under `docs/quality/evidence/CR-0022/`; consistency with BUG-0073's 0.6615.
- [ ] 4. Bookkeeping: BUG-0077 → FIXED (code; latent until the next fetch); `BUG_LOG.md`; PA-0034 Swept? cell; BUG-0073 §6 records the no-re-fetch decision and points to its harmonisation CR; CHANGELOG.
- [ ] 5. Close-out.

## Out of scope
- The representative-year rules (positives' latest visit vs negatives' smallest `gbif_id`): BUG-0073's no-network remedy, its own CR (measured variants: AUC 0.5584 if positives take `max(first_year, YEAR_MIN)`, 0.6125 if negatives take their key's latest year).
- A year-matched draw (6 of 30 cells short of candidates on today's pool).
- GBIF result ordering (`get_negatives.py:269-272`): recorded as a question for the review; moot without a re-fetch.
