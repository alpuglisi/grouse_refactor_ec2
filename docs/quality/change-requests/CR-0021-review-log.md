# CR-0021 review log

Verdicts, concern dispositions and revision history for
`CR-0021-year-matched-negative-draw.md` (v1 was filed as
`CR-0021-harmonised-year-and-year-stratified-draw.md`; renamed with v2
when the scope changed). The CR states only current intent (CR-0011 A4).

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 (`9422a38`) | A: correctness of diagnosis and fix (fresh agent; read-only; no data) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR, 4 MEDIUM, 3 LOW) |
| 1 | v1 (`9422a38`) | B: implementability, composition, acceptance (fresh agent; read-only; no data; pytest not installed, suites not run) | APPROVE WITH FOLLOW-UPS | 0 (3 MAJOR, 5 MEDIUM, 3 LOW) |
| 2 | v2 | A, B (bounded per CR-0011 A2; §2–§5 rewritten, so in scope in full) | pending | – |

**Approval: not reached.** Waits on round 2 and on deliverable 1 (the
top-up fetch and the pre-registration on the EC2 host), which has not
run. Both round-1 reviewers accept a pre-registration-gated approval as
CR-0011 A3 practice (CR-0019 precedent).

## Scope decision (user, 2026-10-03)
Round 1 showed that A1, A2/B1, A3, A4, A6, B2 and B3 all follow from part
A or from v1's merged stratum, and that strata
`((2020,),(2021,),(2022,2023,2024))` are feasible on CR-0019's measured
supplies without part A. Three scopes were put to the user: (i) A + B as
v1; (ii) B only with merged strata; (iii) re-fetch 2023–2024 negatives (C)
+ B with single-year strata. **The user chose (iii).** v2 adds, from
round 1, a strata list fixed in advance and evaluated finest-first (B1),
which keeps (ii) as the last fallback entry.

## Round 1, reviewer A: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where (v2) |
|---|---|---|---|---|
| A1 | MAJOR | Rule A judges positives' habitat and nodata at the latest vintage but trains them at the earliest; negatives judged and trained at one year | resolved by scope: part A dropped; positives untouched (MC1); recorded as the reason in § Alternatives and § Residual | §2, §5, Alternatives |
| A2 | MAJOR | v1 strata infeasible on CR-0019 supplies (~155 short); ES weighting degrades near exhaustion | resolved: top-up C; strata chosen by a pre-fixed finest-first rule (S1→S3) before any AUC; `n_hab / supply` reported per stratum, > 0.8 named | §2 C, §4 |
| A3 | MEDIUM | No tolerance for a within-stratum residual; O11 null unnamed | accepted: O11 class, subset, statistic and within-cell permutation null stated; tolerance 0.55 pooled if a merged stratum is chosen; exactly 0.5 under S1 | §3 O11 |
| A4 | MEDIUM | New pool step 3 changes the representative row | resolved by scope: step 3 unchanged. The new raw rows can still win a 5 dp key or the thin order: measured by the pre-registration and pinned (MC3) | §4, §3 MC |
| A5 | MEDIUM | `analyze_grouse.py` re-run assumed reproducible | resolved by scope: not re-run | §2 B "Unchanged" |
| A6 | MEDIUM | "B only" missing from alternatives | accepted: row (ii) | Alternatives |
| A7 | LOW | "B and C expected unchanged" not guaranteed | accepted: P and B are now unchanged by construction (positives not regenerated; MC1 byte-identity); C is a measured output | §3 MC, §4 |
| A8 | LOW | Per-stratum NonVeg rounding changes the cell total | accepted: totals defined as sums; E9 amended accordingly | §2 B, §3 E9 |
| A9 | LOW | `tune.py`, `tune_bins.py` read S | accepted: listed (S unchanged) | § Impact |

## Round 1, reviewer B: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where (v2) |
|---|---|---|---|---|
| B1 | MAJOR | v1 strata leave 155 short; pre-fix a finest-first candidate list and a selection rule before any AUC; define "within reason" | accepted: S1→S3, first with zero SHORT, selected before O11 is computed; never coarser than S3 (a single stratum is today's draw) | §4 |
| B2 | MAJOR | `first_year_min` unchecked independently | resolved by scope: no new column | – |
| B3 | MAJOR | Unbounded `analyze_grouse.py` re-run | resolved by scope: not re-run; the new unbounded input (GBIF) is bounded instead by fetching once into a scratch tree, pinning the raw files' sha256 and copying them live (MC2) | §2 C, §3 MC |
| B4 | MEDIUM | Acceptance under-specified for the replay author | accepted: exact `draw` JSON shape; totals as sums and the `NEG_RATIO == 1.0` dependence; config sections (`manifest_schema.draw`, `rounding`, `obs`); code (`GATE_IDS`, registry, `OBS_IDS`, standing tuple). `dedup.rule` unchanged under (iii) | §2 B, §3 |
| B5 | MEDIUM | Attack rows named wrong gates | accepted: rows rewritten for the v2 change, each with the fixture rows that make the named gate fail | §3 Attacks |
| B6 | MEDIUM | Missing attack rows | accepted: config vs `regions.py` (E11), overlapping/gapped strata (E15(a)), C year outside strata, NonVeg cap per cell (R4), manifest breakdown (R4). The S-value row lapses with part A | §3 Attacks |
| B7 | MEDIUM | §4 expected C and P unchanged | accepted: P and B unchanged by construction and pinned; C measured | §3 MC, §4 |
| B8 | MEDIUM | O11 class/subset/null; tolerance; how acquisition order is tested | accepted: O11 fully specified with a tolerance; acquisition order: the fix does not depend on it (the draw no longer takes the pool's mix); it stays a recorded candidate | §3, §5 |
| B9 | LOW | `YEAR_STRATA` a pure literal; replay reads the config | accepted | §2 B, §3 |
| B10 | LOW | `tests/test_cr0012.py` calls; `tune.py`, `tune_bins.py`, `filter_by_year_gap` | accepted | Code table, § Impact |
| B11 | LOW | BUG-0075 and the envelope epoch undispositioned | accepted: both left to their own CRs, stated in § Out of scope; tracker updated at deliverable 8 | § Out of scope |

## Found by the author while revising (v2)
- **E9 would fail a correct stratified draw.** `gate_E9` caps NonVeg at
  `round(n × NONVEG_MAX_FRAC)` per cell (`acceptance_split.py:1979-1982`);
  per-stratum caps can sum above it by rounding. v2 amends E9 to
  per-stratum caps and the count to a sum over strata (§3).
- **`get_negatives.py` cannot top up as written.** Caps are per (state,
  species) over all years and are already met, so `--years 2023 2024`
  fetches nothing (`get_negatives.py:245-249, 287-290`). v2 uses a
  one-off evidence script, run once in a scratch tree, with its output
  pinned (§2 C).
