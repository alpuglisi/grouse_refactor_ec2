# BUG-0038: Acceptance thresholds calibrated from extrema, one side only, or on the wrong footing

Filed 2026-09-30 by CR-0013's author, as part of CR-0013 deliverable 0
(bookkeeping only). This is the calibration root cause that round-3
reviewer E (E-3) asked to have split out of BUG-0033. It takes the next
free id at filing: BUG-0034 is a root-level draft, and BUG-0035..0037 are
taken. E had proposed the id "BUG-0034" for it, but that id was later
used for the year-asymmetry defect (`CR-0007-review-log.md`, E-3).

## 1. Description
The CRs set thresholds on statistics of a random draw, such as a val
split or a negative draw. They set them from:
- the maximum or minimum of a handful of fair draws;
- a single realisation;
- a simulation of a pipeline other than the one under test.

They set them from the fair side only, never from the distribution of a
broken pipeline, and never checked that the two separate. The resulting
thresholds either false-failed correct pipelines or passed broken ones.
The same thresholds were also inferred to be "impossible" from too few
draws.

## 2. Where encountered
- CR-0007 v3–v7: I6, I10/(d), I15, I18, I19/I19′, C5–C17. Found by
  reviewers F (round 2), Formal A (round 5), Formal C (round 6), and
  round-7 A and B: FA-C8, FC-C2, FC-C11, A-4, A-6, B-5, B-16.
- CR-0008 v7 (`bb170ea`): the ≤0.06 % three-lineage cross-check and the
  G6 "≤ ~1.2×" size check. Found in round 7 (`CR-0008-review-log.md`
  item 12).
- CR-0009 v3 (committed at `HEAD`): the item-2 gates, 500 m and +0.15.
  Found by the two round-3 reviewers (`CR-0009-review-log.md`, defect 2).
- Found in review, never observed running (`CLAUDE.md` §2).

## 3. What it caused to fail
- **False-fails of correct pipelines:**
  - v7's I18 band false-fails 1 in 400 fair draws (FA-C8);
  - v5's provisional I19 ≤ 0.55 false-fails 100 % of fair draws on the
    post-BUG-0034 footing (v7 hand-off table);
  - CR-0009 v3's item-2 gates false-fail 6.2 % and 21.1 % under an
    unchanged truth.
- **False passes:**
  - I10 ≤ 0.15 passed the rescaled "southern sixth" attack (F2-C2);
  - v6's `max_r S ≤ 0.64` sat 1.037× above the faithful fair maximum and
    missed 7 of 11 attacks (v7 revision note 2).
- **Wrong impossibility claims.** A 5-seed maximum was used to argue
  that "no threshold can both pass a legitimate draw and fail it" for ME.
- **Thresholds invalidated by the CR's own change.** C5–C17 rested on a
  footing the CR itself changed (A-6). So did every v5 threshold under
  BUG-0034's footing shift (I6 6,230 → 4,809).

## 4. What the defect was
The §2.4 statement in BUG-0033 § 4 applies here too. Only CR-0007 v3
(`1445ccd`) and v7 (`bb170ea`) can be quoted; v1, v2, v4, v5 and v6 are
unrecoverable.

**Threshold from a 5-sample maximum.** v3 (`1445ccd`, §6, assertion (d)):
> Calibrated across 5 seeds against a fair draw and that skewed draw,
> rather than from one realisation:
> ```
>              ME       NH       VT
> fair  max  0.0252   0.0513   0.0250
> skew  min  0.6975   0.5897   0.4000
> pre-CR     0.0484   0.3220   0.2500
> ```
> **This gate fails NH and VT on today's data and does NOT fail ME**
> (0.0484 sits below the fair-draw ceiling of 0.0513, so no threshold
> can both pass a legitimate draw and fail it).

The same document later withdraws it (`1445ccd`):
> It was set from
> a 5-seed maximum. Over 12 seeds a *fair* draw reaches NH **0.0769** and
> VT **0.0500** against the ceilings of 0.0513 and 0.0250 I derived — so
> the inference "no threshold can both pass a legitimate draw and fail it"
> rests on a 5-sample maximum, which is not a bound.

**Thresholds as a multiple of, or a band around, fair extrema.**
v7 (`bb170ea`, § Test plan):
> | I15 | GATE | **positives only.** Records per val block / block-vs-record val fraction | fair max 1.734 / 1.161 pp | **≤ 2.5** (3.0 pp if the draw is stratified). v3's 1 pp false-fails 3.75 % |
>
> | I18 | GATE | … Median val→nearest-train distance, **two-sided** | **pooled 1.634 km (FAILS); per-region ME 2.553 / NH 2.628 / VT 2.392 km (all pass)** | within **[2.33, 2.75] km per region**. …

v7 revision note 2 (`bb170ea`) describes the v6 threshold:
> v6's single
> `max_r S <= 0.64` misses **7 of 11** attacks, and its stated margin was
> wrong: the faithful 600-seed fair max is **0.6172**, so 0.64 is
> **1.037×**, not "1.09× / 16 % both sides".

**Calibrated on a simulation of a different pipeline.** v7 (`bb170ea`,
§ Review, round 5):
> It treated the author's own
> calibrations as unverified — correctly, because they were produced with
> `inv_fix_breaks.py`, which **approximates** the negative sampler instead
> of running the real draw

**Fitted thresholds in CR-0008.** v7 (`bb170ea`):
> Note also that ≤0.06 % is a **fitted** threshold — the
> observed ME maximum is 0.0590 % (`tiger`-vs-`dist`, 120,177 px), leaving
> 1.7 % headroom.

and
> Plus a post-repair
> total-size check: ≤ ~1.2× the backup.

**CR-0009 v3** (`HEAD`, § Symptom acceptance):
> pairs, gate **|ME−NH| ≤ 500 m** (was +4,255 m pre-fix, +203 m after);
> and ME−NH mean probability, gate **≤ +0.15** (currently +0.1078).

## 5. Root cause analysis (Five Whys)
1. **Why did the thresholds false-fail correct pipelines or pass broken
   ones?** Each was set just outside the fair values the author had
   observed: a maximum, a band, or a small multiple. The broken
   pipeline's distribution was either not measured or measured as a
   single value.
2. **Why just outside the observed fair values?** A threshold was
   treated as a parameter fitted to the intended pipeline, the smallest
   value it passes. It was not treated as a classifier between two
   distributions, which must separate them at a stated error rate.
3. **Why were a handful of draws accepted?** Nothing tied the quantile
   quoted to the number of draws behind it. A 5-draw maximum was read as
   a bound. So was a 400-draw min/max band, which false-fails about
   1/400 by construction. The draws also came from an approximating
   harness or a superseded footing, because nothing required
   calibration on the pipeline under test.
4. **Why was that not caught at authoring?** No rule governed how a
   non-exact gate's threshold is derived. PA-0021(c) existed only as an
   unfiled draft (see BUG-0033 § 5, step 4). Reviewers found each
   instance after the fact: FA-C8, FC-C11 and B-16 were all "NOT
   DISPOSITIONED" at v7.
5. **Root cause:** there was no standing rule that a non-exact threshold
   must be calibrated on the pipeline under test against both the fair
   and the broken distribution, as quantiles over enough draws to
   support the quantile quoted, and must separate them (otherwise it is
   not a gate). So thresholds were fitted to fair extrema, one side
   only.

## 6. Corrective action
- **PA-0021(c)** (§ 8) states the calibration requirement. It exempts
  exact predicates, and where the two distributions overlap it demotes
  the row to an observation.
- **CR-0013** removes every statistical GATE from the split and draw
  acceptance. Its gates are exact on deterministic data, so the
  family-wise false-fail rate in the pinned environment is 0
  (CR-0013 review log, B-16). Former I15, I18 and I19′ become OBS
  (O2, O1, O5). Their nulls come from the script's own replay on the
  rebuilt footing (`--calibrate`, deliverable 6) and are bound to a
  footing digest (A-6, B-5). No min/max or multiple-of-max rule remains.
- **CR-0008 v8+** has no statistical thresholds; every gate is exact
  (`CR-0008-review-log.md`, R7-12).
- **CR-0009 v4** revised the item-2 thresholds (600 m, +0.20), but it
  still does not meet PA-0021(c). The PA-0021 sweep files that as
  **BUG-0039**.
- **Does this address the root cause?** Yes, for the rule: PA-0021(c)
  is the missing calibration rule. The sweep (CR-0013 deliverable 2a)
  found two live instances outside CR-0013, BUG-0039 and BUG-0040, which
  are remediated under their own records.
- **Status:** **FIXED. CR-0013 was approved and IMPLEMENTED on
  2026-09-30.** The live sweep instances stand as follows:
  - BUG-0040 is FIXED (CR-0016).
  - BUG-0039's gates are demoted to OBS in CR-0009 v5, and BUG-0039
    closes at CR-0009 deliverable 10.
  - PA-0021's sweep was re-run at CR-0013's close-out with no new
    instance (`CR-0013-review-log.md` § Close-out).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` (BUG-0001..0037) and `PREVENTIVE_ACTIONS.md`
(PA-0001..0018, 0022, 0023) for a threshold, tolerance or calibration
defect, and for a statistic inferred from too few samples.
- **None found** before this batch. No earlier bug concerns how a
  threshold is derived.
- The nearest is **BUG-0033**, the sibling filed in this batch. It has a
  different root cause (falsifiability, not calibration), shares the
  evidence, and has the same preventive action (PA-0021). There is no
  earlier preventive action to have failed.
- **Prior-rule failure note.** A draft PA-0021(c) was already in CR-0007
  v3's own deliverables (`1445ccd`): "any threshold in a hard gate must be
  calibrated against the statistic's sampling distribution, stated as a
  quantile over ≥50 draws, never a min/max over a handful". Yet I15, I18
  and the CR-0008 rows still carried extremum thresholds at v7. The draft failed because it
  was **not filed**, so it was not binding (`CLAUDE.md` §3.2), and it
  had no owned sweep. Filing PA-0021 with an owned sweep (PA-0022) fixes
  both.

## 8. Preventive action
**PA-0021(c)** (`PREVENTIVE_ACTIONS.md`, row PA-0021). It extends
PA-0016. This bug is the source of clause (c) and of the null-population
field in clause (f). No separate PA is filed: one clause of the same
rule covers this root cause, and a second PA would split one admission
rule in two.
- **Mechanical enforcement:** none for other CRs; there is no CI. In
  CR-0013 it is enforced by construction, because the design has no
  statistical GATE.
- **Sweep:** CR-0013 deliverable 2a (see PA-0021's Swept? cell).
