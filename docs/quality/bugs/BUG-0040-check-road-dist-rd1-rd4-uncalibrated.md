# BUG-0040: `check_road_dist.py` gates RD1 and RD4 are thresholds fitted to one observed run

Filed 2026-09-30 by CR-0013's author. This is a finding of the PA-0021
sweep (CR-0013 deliverable 2a, `CLAUDE.md` §3.5), a live-code instance
found by reading the code. It was never observed to false-fail or
false-pass.

## 1. Description
CR-0014's acceptance script `check_road_dist.py` hard-fails on two
thresholds that are not calibrated as PA-0021(c) requires:
- **RD1**: median |err| ≤ 20 m;
- **RD4**: median signed error in [−20, +5] m.

Each is tighter than the script's own analytic error bound of about
39 m. Each was set around values observed at one pinned seed of 400
points per stratum ("observed −8.8 m"), with no fair or broken
distribution over draws. No constructed broken raster is shown failing
either gate (PA-0021(a)). The committed unit test's "home-state-only"
error vector passes both of them.

## 2. Where encountered
- `check_road_dist.py:249` (RD1), `:254-256` (RD4), in `rd_stats`;
  thresholds in `docs/quality/cr0014_pins.json` (`rd1_median_abs_m`,
  `rd4_signed_band_m`, `rd_seed` 20260930).
- Specified in `docs/quality/change-requests/CR-0014-road-dist-regeneration.md`
  § Acceptance (RD1–RD5). CR-0014 is IMPLEMENTED, and its gates passed
  (`docs/quality/evidence/CR-0014-gates.txt`, 0 FAIL rows).
- Flagged earlier as CR-0008 round-7 item 12 ("RD1/RD2/RD4 thresholds
  lack null quantiles"). CR-0008 v8 marked it resolved because v8 had
  no statistical thresholds: the RD gates had moved to the new CR
  (CR-0014). CR-0014's review log carries the RD gates over from CR-0008
  v7 G7 but does not carry item 12.

## 3. What it caused to fail
Nothing observed. CR-0014's accepted run passed RD1 at 8.7–10.3 m and RD4
at −6.4 to −9.5 m.
- **Latent false-fail.** The gates stay in the script, which is re-run
  whenever `road_dist` is regenerated. There, RD1 and RD4 can fail a
  correct raster whose error distribution shifts within the analytic
  bound, for example under another TIGER vintage or grid. Their
  false-fail rate is unknown.
- **No detection power shown.** Neither gate is shown to catch anything
  that RD2, RD3 and RD5 would miss. So both gates carry false-fail risk
  with no demonstrated benefit.

## 4. What the defect was
`check_road_dist.py`, verbatim:
```
        "RD1": (float(np.median(a)), float(np.median(a)) <= t["rd1_median_abs_m"]),
...
        "RD4": (float(np.median(err)),
                t["rd4_signed_band_m"][0] <= float(np.median(err))
                <= t["rd4_signed_band_m"][1]),
```
The derivation in the docstring (`check_road_dist.py:33-41`):
> RD thresholds (derivation, CR-0014): truth is measured from the pixel
> centre, so the EDT (pixel centre to nearest road-marked pixel centre)
> differs from it by at most the road's in-pixel offset (<= 21.2 m, half
> the 30 m diagonal, either sign) plus log1p encoding (0.5 * (1 + d) /
> 1000 m, < 18 m below 35 km; max in-coverage distance is 17.2 km): 60 m
> for p99 and the exceedance count leaves headroom (observed max 21.4 m
> over 4,000 points per region in review). all_touched widens each road,
> so correct rasters read slightly LOW - hence the signed-median band
> [-20, +5] m (observed -8.8 m).

The analytic bound justifies 60 m for RD2 and RD3. Nothing in the
derivation justifies 20 m (RD1) or the band [−20, +5] (RD4). RD4's band
is stated as a reaction to one observed median.

`tests/test_check_road_dist.py:74-78`:
```
    def test_home_state_only_fails(self):
        err = np.concatenate([np.full(300, -8.0), np.full(100, 600.0)])
        r = c.rd_stats(err, 0, T_)
        self.assertFalse(r["RD2"][1])
        self.assertFalse(r["RD3"][1])
```
On this vector RD1 = 8 m and RD4 = −8 m, so both pass. No test makes RD1
or RD4 fail.

Out of scope for this bug:
- **RD2 and RD3** rest on the analytic fair-side bound, and a
  constructed failing input exists for them. PA-0021(c) as filed has no
  explicit analytic-bound exemption, and their broken-side distribution
  is not recorded. The remediation CR should state which applies.
- **RD5** is exact.

## 5. Root cause analysis (Five Whys)
1. **Why do RD1 and RD4 have uncalibrated thresholds?** CR-0014 set them
   from the values observed in review (medians near −9 m), with margin.
   It derived only the p99 and max thresholds from the error model.
2. **Why was that accepted in review?** The finding that named them
   (CR-0008 R7 item 12) was dispositioned in CR-0008 as "v8 has no
   statistical thresholds". That was true only because the gates had
   moved to CR-0014. CR-0014's review log inherited the gates, not the
   open finding.
3. **Why did no rule catch it at CR-0014's authoring?** PA-0021 was
   unfiled when CR-0014 was written, reviewed and implemented. Its
   calibration clause was not binding (BUG-0033 § 5, step 4; BUG-0038).
4. **Root cause:** fitted distributional gates were admitted without the
   calibration PA-0021(c) requires, because that rule was unfiled. The
   one reviewer finding against them was lost when the gates moved to
   another CR.

## 6. Corrective action
**Decided (user, 2026-09-30): demote RD1 and RD4 to OBS — CR-0016**
(written, awaiting review). The dropped-finding mechanism is BUG-0041.

Original analysis follows.

Not applied: this deliverable is bookkeeping only, with no code changes.
It needs a CR, because the script is CR-0014's committed gate and a
threshold change alters its acceptance behaviour. **Owner:** this bug,
until a CR is opened (tracked in
`docs/quality/CR-0007-0008-OPEN-ISSUES.md`). Options:
- **Demote RD1 and RD4 to OBS.** RD2, RD3 and RD5 and the exact R-gates
  remain.
- **Calibrate them.** Seed-varied fair distributions on the accepted
  rasters (≥ 50 seeds), broken distributions on the backed-up
  pre-CR-0014 rasters and on a constructed home-state-only raster, and
  a stated separation.

Either way:
- add a test that makes each remaining gate fail;
- record in the CR whether RD2/RD3's analytic bound is an accepted
  substitute for a fair-side quantile.

**Status:** OPEN, low priority. No incorrect result has been produced,
and CR-0014's acceptance is not in doubt: RD2, RD3, RD5 and R0–R8 are
exact or analytically bounded and passed.

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`.
- **Match: BUG-0038** (thresholds from observed values or extrema, fair
  side only). Same mechanism, in live code.
- **Prior-preventive-action failure analysis.** PA-0021(c) did not
  prevent this because it was **not filed** when CR-0014 was written, so
  it was not binding. A second reason is **a finding lost across a CR
  boundary**: CR-0008 item 12 named these gates, and the move to CR-0014
  dropped it. `CLAUDE.md` §1.3 already forbids silently dropping a
  finding, so that part is a failure to follow an existing rule, not a
  missing rule. No new PA is derived from it here. It is flagged to the
  user as a possible process item (a disposition that moves a finding to
  another CR must be re-recorded in that CR's review log).

## 8. Preventive action
**No new PA. PA-0021(a)/(c)**, now filed, is the rule; this bug is an
instance found by its sweep (§3.5).
- **Enforcement:** reviewer checking only (no CI).
