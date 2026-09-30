# CR-0022: Negatives acquisition: round-robin rollover across years, per-year totals, and a year-distribution observation beside E14

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2) and a user decision on the re-fetch. Nothing has been implemented.** Review log: `CR-0022-review-log.md`, to be created by the first reviewer.

## Scope
Change `get_negatives.py`'s rollover so a species' unmet quota is spread across the years that still have data instead of handed whole to the earliest one, print the per-year totals, add an observation comparing the two classes' year distributions, and re-fetch the negatives (BUG-0077; candidate cause of BUG-0073).

## Why now
BUG-0073 measured, after CR-0019 equalised the year supports, negatives at 1,861 of 4,809 in 2020 against positives peaking in 2022, and year alone predicting the label at AUC 0.6615; vintage-bearing features (`tsd`, `fdist`, TreeMap) then carry a label correlate into training. BUG-0077 identifies the acquisition-side mechanism: `get_negatives.py:311-333` passes the entire remaining shortfall to the first non-exhausted year in ascending order. The other candidate (the representative-year rules) stays with BUG-0073 (§ Out of scope).

## The change
### 1. Root cause
As BUG-0077 §5: greedy fixed-order quota allocation with no per-year bound, and no build-time check of the per-class year distributions (E14 compares supports only). PA-0034 states the rule.

### 2. Code (normative)
`get_negatives.py`, rollover passes (`:306-343`):
- Per (state, species) and per pass, `open_years = [y for y in args.years if not pstate[(st, common, y)]["exhausted"]]`; if empty, stop for that species.
- `per_year = math.ceil(remaining / len(open_years))`; each open year is fetched with cap `min(per_year, remaining)` (today: `remaining`), in `args.years` order; `remaining` decreases as today; the `while progress` loop repeats until caps are met or every year is exhausted.
- After both passes, print per (state, species) the counts by year and, per state, the total by year, so the log shows the distribution the pipeline will inherit.
- `--years` default unchanged (`range(YEAR_MIN, today + 1)`); a new `--rollover {round-robin,greedy}` flag defaulting to `round-robin` keeps the old behaviour reachable for comparison only.
Pass 1 is unchanged (it already caps per year).

### 3. Acceptance (amends CR-0013)
**OBS O11 (PA-0021(f)).** Per-class year distribution. Statistic: (a) the year-only AUC as BUG-0073 measured it (year as the score, class as the label) and (b) the largest absolute difference between the two classes' per-year shares. Class: pooled P vs N over the split files (train and val separately, and pooled); subset: per region and pooled; null: the same statistics over ≥ 100 label permutations, reported as quantiles. Not a gate: the achievable distribution depends on what GBIF holds per year. E14 (supports) is unchanged.

### 4. Re-fetch (user decision recorded in the review log)
`get_negatives.py` writes `data/negatives/gbif_negatives_{R}.csv`, the pipeline's input, so the change only takes effect through a re-fetch. A GBIF fetch is not reproducible over time (records are added and corrected), so the run records the date, the per-year counts, the `seen` key count and the sha256 of each output; the previous files are backed up under `grouse_backup/CR-0022/`. Then `generate_negatives.py` → `acceptance_split.py` (positives unchanged; E14 and O11 reported).

### 5. What the change does to the data (pre-registered)
The candidate pool and both negative draws change entirely. Pre-registered from the re-fetch, before the pipeline run: per-year negative counts by state and O11 before (today's files) and after.

## Alternatives considered
- **Proportional allocation** (shortfall split in proportion to the positives' per-year counts): closer to the goal but couples acquisition to the positives' files; round-robin is source-independent and enough to remove the front-loading; proportional stays an option if O11 remains large.
- **Year-matched draw in `generate_negatives.py`:** BUG-0073 measured 6 of 30 cells short of candidates; the re-fetch here may relieve that and is a precondition for it.
- **Harmonise the representative-year rule instead:** no network needed, but it is a different mechanism (BUG-0073's other candidate) and is measured separately (§ Out of scope).

## Impact
- Negatives regenerate; validation metrics and `calibration.json` before the change are not comparable; retrain follow-up (BUG-0060 applies).
- `get_negatives.py`'s output schema is unchanged.
- CR-0013 gains O11.

## One change per CR (CR-0011 A5)
Acquisition code, the re-fetch and the rebuild cannot land separately: the code has no effect without the fetch, and the fetch changes the pipeline input. O11 is bundled because it is the measurement this CR exists to move. The representative-year harmonisation is split out.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| GBIF now holds fewer or different records than at the original fetch; supports could shrink below `YEAR_MIN`..2024 | Pass 1 cap and E14 are unchanged; the pre-registration records per-year counts; E14 must still pass |
| The pool becomes undersupplied for a (region, split) | `generate_negatives.py` refuses (`RuntimeError`); `--headroom` is the lever; recorded |
| Front-loading moves to another year (an exhausted-year edge case) | The per-year table in the log and O11 make it visible; `--rollover greedy` reproduces the old run for comparison |
| A re-fetch fails part-way | Outputs written per state after each pass as today; backup first; the pipeline is not run on a partial fetch (deliverable order) |

## Test plan
**Validatable here:** a unit test of the allocation loop with a fake `fetch_capped` (pure Python): with one year holding all the data and six empty, round-robin fetches at most `ceil(remaining / n_open)` per year per pass and converges to the cap; greedy reproduces the old order. Runnable where `get_negatives.py` imports (it needs `requests`/`pandas` at module level, so the loop is factored into a function that the test imports without network).
**Not validatable here:** the fetch, O11, the rebuild.

## Deliverables (in execution order)
- [ ] 0. User decision: re-fetch yes/no (recorded in the review log).
- [ ] 1. Pre-approval (A3): O11 and the allocation unit test on an unmerged branch.
- [ ] 2. Code (§2) with the allocation factored into a testable function.
- [ ] 3. Backup of `gbif_negatives_*` and the negatives files; re-fetch; record counts and digests.
- [ ] 4. Pre-registration (O11 before/after, per-year counts).
- [ ] 5. Live pipeline run: `generate_negatives.py` → `acceptance_split.py` (E14, O11, every GATE).
- [ ] 6. Bookkeeping: BUG-0077 → FIXED; BUG-0073 → re-measured (its §5 candidate resolved or narrowed); `BUG_LOG.md`; PA-0034 Swept? cell; CHANGELOG.
- [ ] 7. Close-out.

## Out of scope
- The representative-year rules (positives' latest visit vs negatives' smallest `gbif_id`): BUG-0073's remaining candidate; decided after O11 is re-measured.
- A year-matched draw.
- GBIF result ordering (a prefix of the index order is not a random sample, `get_negatives.py:269-272`): recorded as a question for the same review; a `sort`/random parameter, if the API offers one, is a separate small change.
- The retrain.
