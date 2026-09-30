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

## Versions
| version | change |
|---|---|
| v1 | initial draft (options A/B) |
| v2 | option A only; dispositions above |
