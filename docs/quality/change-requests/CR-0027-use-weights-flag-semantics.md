# CR-0027: `--use-weights`: stop applying the envelope weight a second time

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2) and a lead decision between the two options. Nothing has been implemented.** Review log: `CR-0027-review-log.md`, to be created by the first reviewer.

## Scope
Resolve the double application of the negatives' envelope weight (draw and loss) by removing the loss-side weighting or by documenting it as a deliberate second application (BUG-0086; PA-0042).

## Why now
BUG-0086: since CR-0012 the negatives are drawn in proportion to `weight`; `--use-weights` multiplies the loss by the same column, so NonVeg rows (weight 10, up to 30 % of the draw) get ten times the loss on top of their draw share and the flag's help text still describes the pre-CR-0012 meaning. Latent (the flag is off in every recorded recipe), but a user reading the help would turn it on expecting the old behaviour.

## The change
### 1. Root cause
As BUG-0086 §5: CR-0012 changed the column's upstream use without enumerating its consumers.

### 2. Options (lead decision; A recommended)
**A. Remove the loss-side weighting.** `train.py --use-weights` stays parseable and raises `SystemExit` with: "removed in CR-0027: since CR-0012 the negatives draw already samples by envelope weight; a second application at the loss would count it twice". `GrouseModelHandler(use_sample_weights=...)` keeps the parameter (library API) with a docstring note; `_batch_loss` unchanged. The dataset keeps serving `w` (the tensor shape contract is unchanged).
**B. Keep it as an explicit second application.** Help text rewritten to say exactly that; a warning printed at startup with the effective mean weight per class. No code change beyond text and the warning.
Option B is only sensible if a future experiment wants the compounding; A removes a trap.

### 3. Tests
`tests/test_cr0027.py`: with A, `train.py --use-weights --help`-free argparse test that the flag exits with the message; with B, the help text contains "second" and the warning fires on a fixture.

## Impact
None on recorded recipes (flag off). Under A, a workflow that passed `--use-weights` stops with a message naming the reason.

## One change per CR (CR-0011 A5)
A flag semantics change with its test; no data or acceptance change.

## Risk: LOW
| risk | mitigation |
|---|---|
| Someone relied on the compounded weighting | No recorded recipe does; the message explains; B is the fallback |

## Test plan
**Validatable here:** the argparse test (parses `train.py` with `ast` to find the flag or runs `python train.py --use-weights` in a subprocess where torch exists).
**Not validatable here:** a training run comparison (not required for A).

## Deliverables (in execution order)
- [ ] 0. Lead decision: A or B (recorded in the review log).
- [ ] 1. Pre-approval (A3): the test on an unmerged branch.
- [ ] 2. Code and help text.
- [ ] 3. Bookkeeping: BUG-0086 → FIXED; `BUG_LOG.md`; PA-0042 Swept? cell; CHANGELOG.
- [ ] 4. Close-out.

## Out of scope
- Changing how the draw uses `weight` (CR-0020 changes what the weights are fitted on, not how the draw uses them).
