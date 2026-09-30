# CR-0027: Remove the loss-side envelope weighting behind `--use-weights`

**Status: DRAFT v2, 2026-09-30 — round-1 concerns dispositioned (`CR-0027-review-log.md`); awaiting re-review (CLAUDE.md §1.2, bounded per A2). Both round-1 reviewers concluded independently that option B (keep as a documented second application) has no principled reading; it is dropped. Nothing has been implemented.**

## Scope
Remove the per-sample loss weighting (`use_sample_weights`) and make `--use-weights` refuse with an explanation, so the negatives' envelope weight is applied once, by the draw (BUG-0086; PA-0042).

## Why now
BUG-0086: since CR-0012 the habitat negatives are drawn in proportion to `weight` (Efraimidis-Spirakis, `generate_negatives.py:288-292`) and the NonVeg negatives come from a separate pool at a fixed quota (`NONVEG_MAX_FRAC`, `:303-306`) where every weight is `NONVEG_WEIGHT` = 10. `--use-weights` then multiplies each negative's loss by the same column, in training (`model_handler.py:445-447`) and in the validation loss (`:1812-1815`, `:1860-1865`): habitat rows get ∝w draw and ×w loss, NonVeg rows their quota plus ten times the loss, and, because `(per_sample * w).mean()` is not normalised, the negative class's gradient mass grows by roughly `mean(w_neg)` (about 3× at a 30 % NonVeg share), undoing the stratified sampler's balance. The flag's help text still describes the pre-CR-0012 meaning. Off in every recorded recipe.

## The change
### 1. Root cause
As BUG-0086 §5: CR-0012 changed the column's upstream use without enumerating its consumers.

### 2. Code (normative)
- `train.py`: immediately after `parse_args()` (before `GrouseData()` at `:977`), `if args.use_weights: raise SystemExit("--use-weights was removed (CR-0027): since CR-0012 the negatives draw already applies the envelope weight (habitat rows drawn in proportion to it, NonVeg rows at a fixed quota); a second application at the loss counted it twice.")`; the flag stays parseable with help text "removed (CR-0027)"; the `:36` recipe line and the `use_sample_weights=args.use_weights` argument go.
- `model_handler.py`: remove the `use_sample_weights` parameter and attribute, both `_batch_loss` branches (`:445-447`, `:459-460`), both `reduction = 'none' if ...` sites (`:1011`, `:1812`) and the `:16` docstring paragraph; `_batch_loss` keeps its `w` argument (ignored) so callers are unchanged, or drops it with every call site updated (implementer's choice, stated in the commit).
- `smoke_test_training.py`: stage 6 ("Weighted-loss mode") removed and the stages renumbered; its docstring (`:9-11`) and the print at `:109-112` updated.
- `dataset.py` keeps serving `w` (the 4-tuple contract is unpacked at `train.py:294/:451`, `model_handler.py:1202/:1840`, `diagnose_training.py`, `smoke_test_training.py`); `NONVEG_WEIGHT` becomes a `weight_basis` label with no numeric effect (E9 counts by `weight_basis`, unaffected).

### 3. Tests
`tests/test_cr0027.py`: an AST test that `train.py` raises `SystemExit` naming CR-0027 when `args.use_weights` is true and that no `use_sample_weights` name remains in tracked `*.py`; on a torch host, a subprocess `python train.py --use-weights` exits non-zero with the message before touching data.

## Impact
- None on recorded recipes (flag off). A workflow passing `--use-weights` stops with the reason.
- **PA-0042 consumers of `weight` / `use_sample_weights`:** `model_handler.py:445-447`, `:459-460`, `:1011`, `:1812-1815`, `:1860-1865`, `:16` (removed); `train.py:487-490`, `:36`, `:1168` (flag refuses, argument removed); `smoke_test_training.py:9-11`, `:109-112`, `:127-133` (stage removed); `dataset.py:87-89`, `:116-117`, `:388` (unchanged, still serves `w`); `grouse_data.training_frame` (unchanged); `generate_negatives.py` (producer, unchanged; `NONVEG_WEIGHT` label only); `acceptance_split.py` E9/E10/O6 (`weight_basis`, unchanged); CR-0020 (changes what the weights are fitted on, not how the draw uses them).

## One change per CR (CR-0011 A5)
One flag's semantics with the code that implemented it and its test; no data or acceptance change.

## Risk: LOW
| risk | mitigation |
|---|---|
| Someone relied on the compounded weighting | No recorded recipe does; the message explains; the pre-CR-0027 code is in history |

## Test plan
**Validatable here:** the AST tests.
**Not validatable here:** the subprocess test (needs torch).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0027.py` on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. Bookkeeping: BUG-0086 → FIXED; `BUG_LOG.md`; PA-0042 Swept? cell; CHANGELOG.
- [ ] 4. Close-out.

## Out of scope
- Changing how the draw uses `weight` (CR-0020 changes what the weights are fitted on).
