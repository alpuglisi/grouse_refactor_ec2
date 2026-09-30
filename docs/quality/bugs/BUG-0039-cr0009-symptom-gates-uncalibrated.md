# BUG-0039: CR-0009's symptom-acceptance GATEs are uncalibrated distributional thresholds

Filed 2026-09-30 by CR-0013's author. It is a finding of the PA-0021
sweep (CR-0013 deliverable 2a, `CLAUDE.md` §3.5). Found by reading
documents; never run.

## 1. Description
CR-0009's § Symptom acceptance has four GATEs: 1a, 1b, 2a and 2b. Each is
a threshold on a statistic of one retrained model's map, and each hard-
fails the CR. None is calibrated as PA-0021(c) requires. There is no
fair-pipeline sampling distribution over retraining (only one or two
checkpoints), and no broken-pipeline distribution (single values). No
row names the null population its threshold is judged against
(PA-0021(f)). Gate 2b has never been measured on a constructed failing
model (PA-0021(a)).

## 2. Where encountered
`docs/quality/change-requests/CR-0009-retrain-and-revalidate.md`,
§ Symptom acceptance. The text is the **working-tree v4** (uncommitted on
2026-09-30, "awaiting review"). Committed v3 at `HEAD` carries the same
1a band and the older 1b/2a/2b values (BUG-0038 § 4). CR-0009 is ON HOLD
for execution (user decision, 2026-09-30), so no gate has run.

## 3. What it caused to fail
Nothing has run yet. When CR-0009 executes, the four GATEs decide whether
the retrained model is accepted as not reintroducing the Errol symptom.
- **False-fail.** The fair spread of `P(ME>NH)` across retrains is
  unknown. Two checkpoints with byte-identical configs already give
  0.5089 and 0.5400. After CR-0007 halves NH, the spread may exceed the
  [0.44, 0.56] band, and a correct model would then fail.
- **False-pass on 2b.** No broken model has been measured on it.
- **2a/2b false-fail rate.** A bootstrap over 8 pairs of the *old*
  model's predictions sets these thresholds. It says nothing about
  variation across retrains, which is what the gate will see.

## 4. What the defect was
CR-0009 v4, working tree, § Symptom acceptance, verbatim:
> | 1a | GATE | `P(ME pixel > NH pixel)` | in [0.44, 0.56] | return of the reported symptom (pre-fix 0.82–0.85) |
> | 1b | GATE | ME ≥0.8 share − NH ≥0.8 share | ≤ 15 pp | a bimodal Maine side that passes 1a (constructed: 40.1 pp at P = 0.45); accepted baseline 5.36 pp, pre-fix 62.8 pp |
> | 2a | GATE | ME−NH `road_dist` on matched-habitat pairs, ME grid, new rasters | \|·\| ≤ 600 m | a `road_dist` regression (pre-fix +4,255 m, post-fix +203 m) |
> | 2b | GATE | ME−NH mean probability on those pairs | ≤ +0.20 | model-side reintroduction via `road_dist` |
>
> 2a/2b's thresholds sit above the values a bootstrap over the 8 recorded
> pairs requires for a < 5 % false-fail rate (534 m, +0.195);
> `symptom_check.py` re-runs that bootstrap and reports the rate.

`CR-0009-review-log.md` v4 dispositions:
> - BUG-0033/PA-0021 dependency removed: item 1 stands on its own
>   constructed attack.

Against PA-0021:

| clause | 1a | 1b | 2a | 2b |
|---|---|---|---|---|
| (a) constructed failing pipeline | pre-fix checkpoints (2 real broken models) | "constructed: 40.1 pp"; pre-fix 62.8 | pre-fix raster (+4,255 m) | **none** |
| (c) fair distribution, quantiles ≥ 50 draws | **none**: 2 checkpoints (0.5089, 0.5400) | **none**: 1 value (5.36) | bootstrap over pairs (draw count not stated in the CR); not over retrains | as 2a |
| (c) broken distribution | 2 values | 2 values | 1 value | **none** |
| (f) null population named | **no** | **no** | pair bootstrap (implicit) | pair bootstrap (implicit) |
| (d) labelled | GATE | GATE | GATE | GATE |

v3's reviewers had already asked for re-derivation "over ≥50 seeds"
(CR-0009 v3 header, defect 2). v4 did not do this.

## 5. Root cause analysis (differential analysis against CR-0013)
Both CR-0013 and CR-0009 v4 were revised on 2026-09-30, after the same
PA-0021 findings.
- **CR-0013** turned every statistic into an exact predicate or an OBS
  (design rule 2).
- **CR-0009 v4** kept statistical GATEs, and adjusted their values to
  sit above the observed baselines.

The difference:
- **Is there an exact alternative?** CR-0013's split is deterministic,
  so exact replay exists. CR-0009's statistic is a property of a trained
  model, and no exact predicate captures "the symptom did not return".
- **What was done without one?** CR-0009 v4 kept the GATE label and
  moved each threshold just past the known values. It neither calibrated
  the thresholds nor demoted the rows. It also removed its dependency on
  PA-0021, because PA-0021 was unfiled, so there was no rule to meet.

**Root cause:** the one route PA-0021(c) leaves when no exact predicate
exists was not taken. That route is to calibrate the threshold on the
pipeline under test's own randomness (retraining seeds), against fair and
broken models, or else label the row OBS. It was not taken because the
rule was unfiled when v4 was written (BUG-0033 § 5, step 4).

## 6. Corrective action
**Decided and applied (user, 2026-09-30): demote.** CR-0009 v4 (working
tree, uncommitted per user) now reports 1a/1b/2a/2b as OBS, with the
reference values beside them and the rule that a value past its reference
is investigated (PA-0016). Promotion needs ≥ 50 retrain seeds and a CR.
Status: **CLOSED (CR-0009 deliverable 10, 2026-09-30)** — every CR-0009 symptom row is OBS with PA-0021(f) fields (v5); CR-0009 ran and recorded them (`docs/quality/evidence/CR-0009/symptom/`). Earlier: FIXED in text — takes effect when CR-0009 v4 is committed.

Original analysis follows.

Not yet applied. **Owner: CR-0009** (its next revision, before its
review). CR-0009 is being revised by another session, so this record does
not edit it. The remediation must satisfy PA-0021(c)/(f) for each of 1a,
1b, 2a and 2b. Either:
- **calibrate:** fair distribution over ≥ 50 retraining seeds (or a
  stated cheaper proxy with its own justification), broken distribution
  from constructed broken models, quantiles stated, separation shown,
  null named. The compute is large, so this needs user sign-off.
- **demote** the unseparated rows to OBS, and say what then guards the
  symptom (PA-0021(c): "no gate exists").

Gate 2b additionally needs a constructed failing model (PA-0021(a)).
CR-0011 A3 also applies: the committed `symptom_check.py` must compute
the thresholds' calibration, not the CR's prose.

**Status:** CLOSED 2026-09-30 (see the status line above); earlier tracked in `docs/quality/CR-0007-0008-OPEN-ISSUES.md`.

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`.
- **Match: BUG-0038** (thresholds calibrated from extrema, one side
  only). This bug is a live instance of that mechanism, found by the
  sweep of the rule BUG-0038 produced. CR-0009 v3's 500 m / +0.15 gates
  are among BUG-0038's own examples.
- **Prior-preventive-action failure analysis.** The relevant rule is
  PA-0021(c). It was filed in the same batch as this sweep, and it did
  not exist as a binding rule when CR-0009 v4 was written. The draft did
  not prevent this because it was **not filed**, so it was not
  enforceable: v4 explicitly removed its PA-0021 dependency. The rule is
  not too narrow. It names exactly this case, including "If the two
  distributions overlap, no gate exists".

## 8. Preventive action
**No new PA. PA-0021(c)/(f)**, now filed, is the rule; this bug is an
instance found by its first sweep (§3.5). Strengthening it would add
nothing that PA-0021 does not already require.
- **Enforcement:** reviewer checking only (no CI). CR-0009's next
  reviewer must check 1a–2b against PA-0021(c).
