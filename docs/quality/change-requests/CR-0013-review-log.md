# CR-0013 review log

History, verdicts and dispositions for CR-0013. The CR itself states only
current intent (`CLAUDE.md` §1.1, CR-0011 A4).

## Lineage
Split from CR-0007 v7's acceptance layer (commit `bb170ea`: test-plan
table I1–I19′, § Composition gates, § Supply gates, § The `--regions`
hole, § Stated limits) on 2026-09-30, by user decision.

**Why the layer is redesigned rather than carried over.** Every CR-0007
rejection from round 2 to round 7 was a break in that layer.
- **Rounds 2–6:** a constructed pipeline passed every gate.
- **Round 7:** two things.
  - Two gates were inverted or blind: the per-region I18 (A-1) and the
    missing buffer predicate (A-2).
  - The composition and supply thresholds rested on a footing the CR
    itself changed (A-6).

The common cause: gates were thresholds on statistics of a random draw,
and every threshold traded false-fails against blind spots.

CR-0012 makes the draw deterministic. CR-0013 therefore replaces
statistical gates with exact predicates and an independent replay. The
statistics survive as observations: PA-0021(c) leaves no separation to
calibrate once replay catches every recorded attack.

v7 row → CR-0013 row:
| v7 | CR-0013 |
|---|---|
| I1 | E2 |
| I2, I3, (c) | E5 |
| I4, (b) | E4 |
| I5 | E8 |
| I6 | R1 |
| I7 | O10 |
| I8, C4 | E9 |
| I9 | E12 (negatives); CR-0007 P4 (positives) |
| I10 | not carried (retired in v4) |
| I11 | E6 |
| I12, I14 | E11 + R1–R4 |
| I13 | CR-0007 O3 |
| I15 | O2 |
| I16 | O3 |
| I16b | O4 |
| I17, C5–C8 | O8 |
| I18 | O1 |
| I19′ | O5 |
| C1, C2 | E9 |
| C3 | E10 |
| C9–C16 | O6 |
| C17, SUP0, SUP-O, SUP-R | O7 |
| (a) | E1 |

New rows, from round-7 findings:
- E3: A-5, and C7-5 from round 3.
- E7: A-2.
- E10 on the pool: v7 stated limit 5.
- O9: PA-0020(ii).

Every round 1–7 concern about v7 is dispositioned in
`CR-0007-review-log.md` § v8 dispositions. The table below lists those
whose resolution lives in this CR.

## Dispositions of CR-0007 concerns resolved here
| id (CR-0007 log) | sev | where in CR-0013 |
|---|---|---|
| A-1 | BLOCKING | The per-region I18 gate no longer exists. O1 is pooled, OBS, with an N-split null taken on post-CR data. BUG-0027's leak is gated exactly by E4/E5 (pre-CR: 522 keys, 882 blocks). |
| A-2 | BLOCKING | E7 (exact minimum distance, selected and pool, vs pooled sightings); R3 replays the buffer count; O5 two-sided; attack row "No 300 m buffer". `BUFFER_M` centralised by CR-0007. |
| A-4 | MAJOR | O5's N-draw null holds the realised positive split and pool fixed. The val-candidate thinning attack fails R3, so v7's stated limit 3 no longer applies. |
| A-5, C7-5 | MAJOR | E3 |
| A-6 | MAJOR | C rows become O6–O8. References come from `--calibrate` on the rebuilt footing (deliverable 6), bound to a footing digest. |
| A-10, B-4 | MEDIUM/MAJOR | O4: in-run permutation null, z reported, no frozen constants |
| A-12 | MEDIUM | O7, compared with the previous accepted run; no headroom claim |
| B-3, FC-C4 | MAJOR/BLOCKING | Call-site matrix; one implementation |
| B-5 | MAJOR | No GATE uses a null. OBS nulls come from this script's own replay, calibrated only after every GATE passes. |
| B-6 | MAJOR | § Attacks; deliverables 1 and 4. Broken evidence scripts are pinned to `ec1470a` (CR-0012 §7) or committed (deliverable 1). |
| B-16, FA-C8, FC-C11 | MEDIUM/MAJOR | No min/max or multiple-of-max threshold remains. The family-wise false-fail rate of the GATE set is 0 in the pinned environment, because every gate is an exact predicate on deterministic data. OBS rows name class, subset, pooling and null. |
| B-17 | MEDIUM | R1: the target is the replayed set |
| C7-2, H-I14a | BLOCKING/unrated | Not applicable: R2 and E11 replace I14, and the reviewer's Jaccard-0.992 draw fails R2 |
| C7-9 | LOW | E11 checks the manifest's sha256 values |
| F3-D8, E-18, E-3, E-4, E-PAa, FA-Q3, FC-C7, B-8 (part) | various | Deliverable 0 (PA-0021 and BUG-0033 filing, lineage, sweep scope, split calibration BUG) |
| B-R (part) | unrated | Risk rows: replay false-fail, float/PROJ. Stated limit 2: equivalence of harness and implementation cannot be validated. |
| F2-C8 (support scale) | MAJOR | O5 (receptive-field scale, per region), O9 |
| CR-0014 B6 / tracker "I17 WILL change" | — | O8 and E8 taken after CR-0014, or repeated |

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| — | v1 | not yet reviewed | — | — |

## Versions
| version | date | change |
|---|---|---|
| v1 | 2026-09-30 | Split from CR-0007 v7; exact-replay design |
