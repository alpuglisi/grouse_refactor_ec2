# CR-0027: Remove the loss-side envelope weighting behind `--use-weights`

**Status: v3, 2026-09-30 — APPROVED by agent quorum and signed off by the lead on 2026-09-30 (CLAUDE.md §1.4; round 2: reviewers A and B both APPROVE WITH FOLLOW-UPS). Nothing has been implemented; the lead has signed off; implementation may begin (deliverables that need the data host wait for one).** Review log: `CR-0027-review-log.md`.

## Scope
Remove the per-sample loss weighting (`use_sample_weights`) and make `--use-weights` refuse with an explanation, so the negatives' envelope weight is applied once, by the draw (BUG-0086; PA-0042).

## Why now
BUG-0086: since CR-0012 the habitat negatives are drawn in proportion to `weight` (Efraimidis-Spirakis, `generate_negatives.py:288-292`) and the NonVeg negatives come from a separate pool at a fixed quota (`NONVEG_MAX_FRAC`, `:303-306`) where every weight is `NONVEG_WEIGHT` = 10. `--use-weights` then multiplies each negative's loss by the same column, in training (`model_handler.py:445-447`) and in the validation loss (`:1812-1815`, `:1860-1865`): habitat rows get ∝w draw and ×w loss, NonVeg rows their quota plus ten times the loss, and, because `(per_sample * w).mean()` is not normalised, the negative class's gradient mass grows by roughly `mean(w_neg)` (3–4× at a 30 % NonVeg share with habitat weights near 1), undoing the stratified sampler's balance. The flag's help text still describes the pre-CR-0012 meaning. Off in every recorded recipe.

## The change
### 1. Root cause
As BUG-0086 §5: CR-0012 changed the column's upstream use without enumerating its consumers.

### 2. Code (normative)
- `train.py`: immediately after `parse_args()` (`:963`, before `GrouseData()` at `:977`), `if args.use_weights: raise SystemExit("--use-weights was removed (CR-0027): since CR-0012 the negatives draw already applies the envelope weight (habitat rows drawn in proportion to it, NonVeg rows at a fixed quota); a second application at the loss counted it twice.")`; the flag stays parseable with help text "removed (CR-0027)"; the `:36` recipe line and the `use_sample_weights=args.use_weights` argument (`:1168`) go.
- `model_handler.py`: remove the `use_sample_weights` parameter (`:231`) and attribute (`:266`), both `_batch_loss` branches (`:445-447`, `:459-460`), both `reduction = 'none' if ...` sites (`:1011`, `:1812`) and the `:15-18` docstring paragraph. `_batch_loss` **keeps** its `w` argument, ignored, so its four call sites (`:1208`, `:1219`, `:1860`, `:1864`) and CR-0026's section-2 call stay valid in either landing order. Every criterion is then `reduction='mean'`, so `hard = criterion(outputs, y)` and the distillation `soft.mean()` (`:457-461`) are scalars as on today's default path.
- `smoke_test_training.py`: stage 6 ("Weighted-loss mode", `:127-133`, the direct `use_sample_weights=True` construction at `:130`) removed and the stages renumbered; its docstring (`:9-11`), the stage-5 label at `:121-122` ("unweighted - original behavior"), the "ALL 7 STAGES PASSED" line (`:146`) and the cleanup line naming `smoke_test_model_weighted.pth` (`:147`) updated; the stage-3 print at `:110-112` stays correct.
- `dataset.py` keeps serving `w` (the 4-tuple contract is unpacked at `train.py:294`, `:451`, `model_handler.py:1202`, `:1840`, `diagnose_training.py`, `smoke_test_training.py`; `calibrate.py:142` and `diagnose_wetland.py:134` discard it). `NONVEG_WEIGHT` stays a numeric `weight` value written to the CSVs (`generate_negatives.py:144`, `:259`) with no numeric effect on the draw (the NonVeg quota is drawn by `es_select(nv_pool, n_nv)` over equal weights, `:311-312`, so the order is uniform) or on the loss; O6 (OBS) still reads it (`acceptance_split.py:2500-2502`).

### 3. Tests
`tests/test_cr0027.py`: an AST test that `train.py` raises `SystemExit` naming CR-0027 when `args.use_weights` is true, and that no `use_sample_weights` `Name`/`keyword`/`Attribute` node remains in tracked `*.py` outside `tests/test_cr0027.py` itself (fails on today's tree at the nine sites in § Impact; PA-0021(a)); on a torch host, a subprocess `python train.py --use-weights` exits non-zero with the message before touching data.

## Impact
- None on recorded recipes (flag off). A workflow passing `--use-weights` stops with the reason.
- **PA-0042 consumers of `weight` / `use_sample_weights`** (search: `use_sample_weights`, `use_weights`, `reduction=`, `weight`, `NONVEG_WEIGHT`, `_w` over tracked `*.py` excluding `inv_*`/`res_*`; BUG-0086 §8): `model_handler.py:231`, `:266`, `:445-447`, `:459-460`, `:1011`, `:1812-1815`, `:1860-1865`, `:15-18` (removed); `train.py:487-490`, `:36`, `:1168` (flag refuses, argument removed); `smoke_test_training.py:9-11`, `:121-122`, `:127-133`, `:146-147` (stage removed, text updated); `dataset.py:87-89`, `:116-117`, `:388` (unchanged, still serves `w`); `train.py:221` (writes `weight = 1.0` for `--an-background` rows; unchanged); `calibrate.py:142`, `diagnose_wetland.py:134` (discard `_w`; unchanged); `grouse_data.training_frame` (unchanged); `generate_negatives.py` (producer, unchanged); `acceptance_split.py:739`, `:1261` (the replay draws with the numeric `weight`; unchanged), E9/E10/O6 (`weight_basis` and weight-summed O6; unchanged); CR-0020 (changes what the weights are fitted on, not how the draw uses them).
- Landing order with CR-0026: `_batch_loss` keeps `w`, so either order works; CR-0026's source-shape FAIL set loses `smoke_test_training.py:128` if this CR lands first and is re-recorded there.

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
