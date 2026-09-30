# CR-0016: Demote `check_road_dist.py` RD1 and RD4 from gates to observations

**Status: APPROVED (v2.1), 2026-09-30 — implementation in progress.**
History and dispositions: `CR-0016-review-log.md`. Current intent only.

## Scope
Report RD1 (per-stratum median |err|) and RD4 (per-stratum median signed
err) as uncalibrated observations instead of pass/fail gates in
`check_road_dist.py` (BUG-0040; user decision 2026-09-30).

## Why now
RD1's and RD4's references (`cr0014_pins.json`) were fitted to one
pinned-seed run, with no fair or broken distribution (PA-0021(a), (c)).
Measured in review on synthetic rasters: neither has any power against a
roads-`all_touched=False` raster (0/100 fails), RD4's stated reason for
existing; RD1 fails a 1-px crop offset in 16/100 draws, which RD3 and R2
already catch. They carry false-fail risk on every future regeneration
with no demonstrated benefit.

## The change
- **`rd_stats`** (`:245-258`): RD1 and RD4 return `(value, None)` — a value
  with no pass/fail — and read no threshold. RD2, RD3, RD5 unchanged.
- **Kind map**, module level: `RD_KIND = {"RD1": "OBS", "RD2": "GATE",
  "RD3": "GATE", "RD4": "OBS", "RD5": "GATE"}`, and a pure helper
  `rd_rows(stats, subject)` returning `(gid, kind, subject, value,
  required, ok)` rows, with `ok=None` for OBS so the report never prints
  "OBS FAIL" (`:456-458`). `cmd_check` (`:406-409`) calls it.
- **Pins** (`docs/quality/cr0014_pins.json`): `rd1_median_abs_m` and
  `rd4_signed_band_m` move to `"rd_obs_references"`, printed as the OBS
  rows' "reference (uncalibrated)". `rd_thresholds` keeps
  `rd2_p99_abs_m`, `rd3_max_abs_m`. `_comment` cites CR-0016.
- **Docstring and help:** `:27` lists RD2, RD3, RD5 as gates and RD1, RD4
  under Observations; `:33-41` keeps the 60 m derivation for RD2/RD3 and
  replaces the RD4 sentence with "RD1 and RD4 are reported, not gated
  (BUG-0040)"; the `--gates` help (`:487-489`) likewise.
- **RD1/RD4 as OBS (PA-0021(f)):** class = sampled pixel centres in
  `T \ C`; subset = the stratum, per region; null population = the
  correct-pipeline error model — **not calibrated**, so the printed
  reference is not a limit.

## The analytic bound (answers BUG-0040's open question)
RD2 (p99 ≤ 60 m) and RD3 (0 points > 60 m) stay gates on a **derived
bound, accepted as a substitute for a fair-side quantile**: the error is at
most the road's in-pixel offset (21.2 m) plus log1p encoding
(`0.5·(1 + d)/1000` m), about 30 m at the largest in-coverage distance
(17.2 km). The bound holds under two preconditions, stated in the script —
X3 **reports** the first (OBS) and the encoder caps `d`; neither is a
gate, and a violation makes RD3 false-fail, never false-pass: every truth road lies inside grid +
pad (X3 = 0; if X3 > 0 the bound can fail and RD3 can false-fail), and
`d < ROAD_DIST_MAX_M`. The **broken side** is measured, not asserted: T3
runs the check on the real pre-CR-0014 home-state-only rasters.

**Which gate catches what** (without RD1/RD4):

| construction | caught by |
|---|---|
| home-state-only roads (BUG-0023) | RD2/RD3 on the state-line and grid-edge strata (T3); R2 |
| roads rasterised `all_touched=False` | R2 (moves `C`'s boundary); RD2/RD3 do not separate it |
| 1-px crop offset | RD3, R2 |
| coverage mask `all_touched` changed | R0, R1, R2 |
| stale year-copy | R3 |
| wrong TIGER vintage | R0b, R2 |

R2 catches road-side constructions only while `C` is non-empty (ME
822,494 / NH 108,684 / VT 69,475 px today).

## Acceptance
| id | check | required |
|---|---|---|
| T1 | Unit tests (`tests/test_check_road_dist.py`): `rd_rows` marks RD1/RD4 OBS with `ok=None`; a constant +30 m error vector passes RD2/RD3 and produces no gate failure; a signed-median +10 m vector produces no gate failure; the home-state vector still fails RD2 and RD3; the existing tests pass | pass |
| T2 | `for r in VT NH ME: python check_road_dist.py check --regions $r --gates B0 R0b R8`, one region at a time, nothing else heavy running; outputs concatenated with `===== R` headers | 0 gate failures; RD1/RD4 values equal those in `docs/quality/evidence/CR-0014-gates.txt` (pinned seed) |
| T3 | `for r in ME VT: python check_road_dist.py check --regions $r --root /home/ec2-user/grouse_backup/CR-0014` (the pre-CR-0014 home-state-only rasters), one region at a time, nothing else heavy running | RD2 or RD3 FAIL on the **state-line** stratum in ME and in VT (pre-registered). The grid-edge stratum is recorded as measured, whatever it shows — it is not part of the requirement and is not adjusted after the run. Other rows may fail; recorded |

## Impact
CR-0014's acceptance stands: its run passed every gate, and the table above
shows each construction still has a gate. Only future runs change. RD2,
RD3 thresholds are unchanged.

## Risk: LOW
Removing two gates removes no demonstrated detection power (measured above).

## Test plan
**Here:** T1, T2, T3.
**Not here:** false-fail behaviour under a future TIGER vintage or a new
grid — no such input exists; the analytic bound's preconditions (X3,
`d`) are what guard it.

## Deliverables
- [ ] 1. Code, pins and test changes; T1.
- [ ] 2. T2 and T3; save to `docs/quality/evidence/CR-0016-check.txt`.
- [ ] 3. Bookkeeping:
      - BUG-0040 → FIXED, corrective action naming CR-0016 and
        `check_road_dist.py`'s `RD_KIND`/`rd_rows` (PA-0024(a));
        `BUG_LOG.md` row.
      - PA-0021's Swept? cell: the analytic-bound decision above.
      - CR-0014: a dated "Post-implementation change" entry in its review
        log (CR-0016, commit, affected rows) and a pointer in its status
        line; its acceptance table gets a one-line note under it, not a
        rewrite (it records what was accepted).
      - Tracker: the BUG-0040 lines.

## Out of scope
- Calibrating RD1/RD4 (≥ 50 seeds) — only if a future change needs them as
  gates.
- Changing RD2/RD3's thresholds or CR-0014's accepted result.
