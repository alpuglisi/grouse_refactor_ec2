# CR-0016: Demote `check_road_dist.py` RD1 and RD4 from gates to observations

**Status: PROPOSED (v1) — awaiting review.** Nothing implemented.
History: `CR-0016-review-log.md`. Current intent only.

## Scope
Report RD1 (per-stratum median |err|) and RD4 (per-stratum median signed
err) as observations instead of pass/fail gates in `check_road_dist.py`
(BUG-0040; user decision 2026-09-30).

## Why now
RD1's 20 m and RD4's [−20, +5] m were fitted to one pinned-seed run; no
fair or broken distribution was measured and no failing construction is
shown (PA-0021(a), (c)). The unit test's home-state-only vector passes both
(`tests/test_check_road_dist.py:74-78`). They carry false-fail risk on any
future regeneration with no demonstrated power. The round-7 finding that
said so was lost in the CR-0008 → CR-0014 split (BUG-0041).

## The change
- `check_road_dist.py` `cmd_check` (`:406-409`): RD1 and RD4 rows are
  added with kind `OBS` and required value "report (reference 20 m /
  [−20, +5] m)"; RD2, RD3, RD5 stay `GATE`. `rd_stats` is unchanged, so
  the values are still computed.
- Docstring (`:33-41`): the 60 m derivation stays as RD2/RD3's basis; the
  sentence justifying RD4's band is replaced by "RD1 and RD4 are reported,
  not gated (BUG-0040)".
- `docs/quality/cr0014_pins.json`: `rd1_median_abs_m` and
  `rd4_signed_band_m` move under a `"rd_obs_references"` key (kept for the
  report); the gate thresholds keep only RD2/RD3.

## Acceptance
| id | check | required |
|---|---|---|
| T1 | `tests/test_check_road_dist.py` updated: RD1/RD4 appear as OBS rows; a vector with median 30 m no longer fails the check; RD2/RD3/RD5 unchanged | pass |
| T2 | Re-run `check_road_dist.py check` on the current rasters, one region at a time | 0 gate failures; RD1/RD4 rows marked OBS with the same values as `docs/quality/evidence/CR-0014-gates.txt` |

## Impact
CR-0014's acceptance stands: its run passed every gate, and RD2, RD3, RD5
and the exact R-gates carry it (they fail the home-state-only
construction). Only future runs are affected.

## Risk: LOW
Removing two gates removes no demonstrated detection power (BUG-0040 §3).

## Deliverables
- [ ] 1. The code, pins and test changes; T1.
- [ ] 2. T2; save to `docs/quality/evidence/CR-0016-check.txt`.
- [ ] 3. BUG-0040 → FIXED; `BUG_LOG.md` row; CR-0014's review log notes
      the change.

## Out of scope
Calibrating RD1/RD4 (≥ 50 seeds) — only if a future change needs them as
gates.
