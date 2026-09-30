# CR-0027 review log

## Lineage
From BUG-0086 (2026-09-30 static review). Reviewers: two fresh agents
(CLAUDE.md §1.2, §1.4); review logs not read by them. Both concluded
independently that the loss-side weighting has no principled reading
once the draw is weight-proportional and the NonVeg quota is fixed, so
option B is dropped rather than left to a decision.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | REVISE | 0 |
| 1 | v1 | B (agent, fresh) | REVISE | 0 |
| 2 | v2 | A (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS | 0 |
| 2 | v2 | B (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS | 0 |

## Round 1, reviewer A
- A1 MAJOR: consumer list incomplete (PA-0042): `evaluate()` also
  weights the validation loss (`model_handler.py:1812-1815`, `:1860-1865`),
  so `select_by='loss'` was double-weighted too.
- A2 MAJOR: option A as written leaves the trap live (`use_sample_weights`
  and `_batch_loss` unchanged; `smoke_test_training.py:127-133` step 6
  constructs `use_sample_weights=True` directly).
- A3 MEDIUM: NonVeg rows come from a separate pool at a fixed quota
  (`draw_region_split :303-306`), not "over-represented by the draw";
  `NONVEG_WEIGHT` has no draw effect; under A it becomes a label only.
- A4 MEDIUM: place the guard right after `parse_args()`; state what is
  validatable here.
- A5 LOW: help text.

## Round 1, reviewer B
- B1 MAJOR: same as A1 (+ `:1011` and `:1812` `reduction` sites, `:16`
  docstring, smoke docstring `:9-11` and print `:109-112`, `train.py:36`
  recipe line).
- B2 MEDIUM: same as A2 (delete the parameter, both `_batch_loss`
  branches, both `reduction` sites, smoke step 6; dataset keeps `w`).
- B3 LOW: same as A4.
- Also: drop option B.

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location) |
|---|---|---|
| A1 / B1 | MAJOR | **Accept** — § Impact PA-0042 table lists every consumer with its disposition, including `evaluate()`'s weighted validation loss |
| A2 / B2 | MAJOR | **Accept** — §2: `use_sample_weights` and both `_batch_loss` branches and both `reduction` sites removed; smoke step 6 removed (stages renumbered); dataset keeps serving `w` |
| A3 | MEDIUM | **Accept** — § Why now and the `SystemExit` message reworded (quota + 10× loss for NonVeg; ∝w draw + ×w loss for habitat); `NONVEG_WEIGHT` becomes a label |
| A4 / B3 | MEDIUM / LOW | **Accept** — guard immediately after `parse_args()`; § Test plan states the AST-only check is what runs here |
| A5 | LOW | **Accept** — help text "removed (CR-0027)" |
| B (option B) | — | **Accept** — option B removed; decision recorded here as the reviewers' technical verdict; the lead may object at approval |

## Round 2 (v2), reviewers A and B (bounded, CR-0011 A2)
Both verified A1/B1 and A2/B2 RESOLVED against the code (`evaluate()`'s
weighted validation loss at `model_handler.py:1812`, `:1860-1865`; the
nine `use_sample_weights` sites; guard placement `:963` before `:977`).
No BLOCKING or MAJOR.
- A-L1 LOW: PA-0042 table gaps (`train.py:221`, `calibrate.py:142`,
  `diagnose_wetland.py:134`, `acceptance_split.py:739`, `:1261`) and the
  search terms not recorded.
- A-L2 / B-N2 LOW: smoke lines `:121-122`, `:146`, `:147` change;
  `:109-112` does not.
- A-L3 / B-N5 LOW: the "no name remains" test would trip on its own
  needle; match AST nodes and exclude itself.
- A-L4 / B-N1 LOW / MEDIUM: fix the `_batch_loss` `w` choice ("keeps
  `w`"; CR-0026 depends on the 4-argument form).
- A-L5 / B-N3 LOW: status-line review sentence (A4); `NONVEG_WEIGHT`
  stays a numeric value with no effect on draw or loss; O6 reads it.
- B-N4 LOW: "about 3×" → "3–4× (≈ mean(w_neg))".
- B-N6 LOW: landing order with CR-0026's recorded FAIL set.

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-L4 / B-N1 | LOW / MEDIUM | **Accept** — §2 `model_handler.py` bullet: `_batch_loss` keeps `w`; § Impact landing-order bullet |
| A-L1 | LOW | **Accept** — § Impact table lists the five sites and the search terms |
| A-L2 / B-N2 | LOW | **Accept** — §2 smoke bullet names `:121-122`, `:146`, `:147`; `:110-112` stays |
| A-L3 / B-N5 | LOW | **Accept** — § 3: AST `Name`/`keyword`/`Attribute` nodes, test file excluded |
| A-L5 / B-N3 | LOW | **Accept** — status line trimmed (sentence kept in this log's Lineage); §2 `dataset.py` bullet rewords `NONVEG_WEIGHT` |
| B-N4 | LOW | **Accept** — § Why now |
| B-N6 | LOW | **Accept** — § Impact landing-order bullet; CR-0026 v3 mirrors it |

## Approval
| party | verdict | date |
|---|---|---|
| reviewer quorum (CLAUDE.md §1.4, agent-only) | APPROVE WITH FOLLOW-UPS (see Rounds) | 2026-09-30 |
| lead | APPROVE ("if the CR has passed the review process, I approve"; recorded by the author from the session) | 2026-09-30 |
| author | sign-off | 2026-09-30 |
Open MEDIUM/LOW follow-ups above go to the tracker at close-out.

## Versions
| version | change |
|---|---|
| v1 | initial draft (options A/B) |
| v2 | option A only; round-1 dispositions |
| v3 | round-2 dispositions above; approved by agent quorum |
