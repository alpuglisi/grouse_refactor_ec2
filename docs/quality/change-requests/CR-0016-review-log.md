# CR-0016 review log

## Lineage
From BUG-0040 (CR-0013's PA-0021 sweep), which re-owns CR-0008 round-7
finding R7-12 lost in the CR-0008 → CR-0014 split (BUG-0041). User
decision 2026-09-30: demote, not calibrate.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | B — implementability + §1 (fresh) | REJECT | 1 |
| 1 | v1 | A — correctness (fresh) | REJECT | 1 |

## Round 1, reviewer B (dispositions in v2)
- **B1 BLOCKING:** moving `rd1_median_abs_m`/`rd4_signed_band_m` out of
  `rd_thresholds` while `rd_stats` is "unchanged" → `KeyError` at
  `:249`/`:255-256` on the first stratum. (Author error.)
- M1 MAJOR: OBS rows must carry `ok=None` or they print "OBS FAIL"
  (`:456-458`); T1 untestable as written — move classification into a pure
  helper or restate T1.
- M2 MAJOR: BUG-0040 / tracker require stating whether RD2/RD3's analytic
  bound substitutes for a quantile; PA-0021's Swept? cell names BUG-0040 as
  owner — closing it would orphan the question (PA-0022).
- m1–m5 MEDIUM: docstring gate list (`:27-31`); PA-0021(f) fields for the
  OBS rows; deliverable 3 bookkeeping (tracker `:110`, `:134`; pins
  `_comment`; PA-0024(a) location); CR-0014 post-implementation record
  (log entry + status pointer, not rewriting its acceptance table); test
  plan's untestable items and T2 invocation.
- l1–l4 LOW: A4 duplicate numbers; RD5 does not fail the home-state vector;
  CR-0014 status line inconsistency (fixed: stray "Nothing implemented.");
  dispositions per PA-0024(a).

## Round 1, reviewer A
Measured on synthetic rasters: RD1/RD4 0/100 fails vs roads
`all_touched=False` (RD4's reason to exist); RD1 16/100 vs a 1-px offset
(RD3 25/100, R2 catches it). Demotion supported. Same BLOCKING B1 as
reviewer B; M1 analytic-bound question; M2 construction→gate table; M3
PA-0021(f) fields; M4 `ok=None`; M5 unit-testable helper + vectors; L1
docstring `:27`, help `:487-489`; L2 CR-0014 table; L3 say "uncalibrated".

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location, PA-0024(a)) |
|---|---|---|
| A-B1 / B-B1 | BLOCKING | **Accept** — `rd_stats` returns `(value, None)` for RD1/RD4 and reads no threshold for them (§ The change, first bullet) |
| B-M1 / A-M4 / A-M5 | MAJOR | **Accept** — `RD_KIND` + pure `rd_rows` with `ok=None` for OBS (§ The change); T1 vectors +30 m and +10 m (§ Acceptance T1) |
| B-M2 / A-M1 | MAJOR | **Accept** — § The analytic bound: accepted fair-side substitute with preconditions (X3 = 0, `d` < cap); broken side measured by T3 on the pre-CR-0014 rasters |
| A-M2 | MAJOR | **Accept** — construction → gate table (§ The analytic bound) |
| B-m2 / A-M3 | MEDIUM | **Accept** — PA-0021(f) fields (§ The change, last bullet) |
| B-m1 / A-L1 | MEDIUM | **Accept** — docstring `:27`, `:33-41`, help `:487-489` (§ The change) |
| B-m3 | MEDIUM | **Accept** — deliverable 3 lists BUG-0040 location, PA-0021 Swept?, tracker, pins `_comment` |
| B-m4 / A-L2 | MEDIUM | **Accept** — CR-0014 log entry + status pointer + a note under its table, no rewrite (deliverable 3) |
| B-m5 | MEDIUM | **Accept** — Test plan "Not here"; T2 invocation exact (§ Acceptance) |
| B-l1 | LOW | **Accept** — reference numbers now only in the pins |
| B-l2 | LOW | **Accept** — RD5 claim removed; Impact points at the table |
| B-l3 | LOW | **Fixed** — CR-0014 status line (stray "Nothing implemented." removed) |
| A-L3 | LOW | **Accept** — "reference (uncalibrated)" (§ The change) |

## Versions
| version | change |
|---|---|
| v1 | initial |
| v2 | round-1 dispositions above |

## Author sign-off
Pending.
