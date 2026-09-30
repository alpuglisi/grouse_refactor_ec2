# CR-0026: One `TRAIN_DEFAULTS` for every handler construction, a checkpoint config check that compares every geometry key, and `diagnose_training.py` section 3 through the shared loader and scorer

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented.** Review log: `CR-0026-review-log.md`, to be created by the first reviewer.

## Scope
Define `train.py`'s recipe defaults once, build every non-`train.py` handler from them, make `check_checkpoint_config` compare every geometry key the checkpoint writes, and rebuild `diagnose_training.py` section 3 on the shared loader and scorer (BUG-0083, BUG-0085; PA-0040, PA-0041).

## Why now
BUG-0083: section 3 cannot load any `--missing-mask` checkpoint, misreports the cause, and would score a legacy checkpoint through `forward().mean` over the logit and attention-score channels. BUG-0085: the smoke test and the benchmark build handlers with library defaults and never exercise the shipped geometry. Third occurrence of the BUG-0010/BUG-0011 class; PA-0009 was followed by copying two flags and had no enforcement.

## The change
### 1. Root cause
As BUG-0083 §5: geometry and scoring are reconstructed by hand-copying `train.py` rather than through the shared loader and scorer, and the config compare list is hand-maintained.

### 2. Code (normative)
**`train_defaults.py` (new leaf module, constants only).**
```python
TRAIN_DEFAULTS = dict(
    pool="attn", center_skip=True, missing_mask=True,
    dual_branch="dilated", dual_branch_channels=32,
    keep_early_resolution=False, early_attn=False, early_attn_heads=4,
    early_attn_kv_stride=1, early_attn_pos_mode="rel",
    early_attn_dropout=0.1, early_attn_droppath=0.1, early_attn_lr_factor=0.1,
    dropout=0.2, embed_dropout=0.0, label_smoothing=0.05, ema_decay=0.999,
    lr=3e-4, weight_decay=1e-4, loss="focal", focal_gamma=2.0,
    backbone_lr_factor=0.1, grad_clip=1.0, sched="cosine", warmup_epochs=3,
    select_by="rank", select_min_delta=1e-3, pos_threshold=0.75,
    neg_threshold=0.25, flip_tta=True,
)
HANDLER_GEOMETRY_KEYS = ("pool", "center_skip", "missing_mask", "dual_branch",
    "dual_branch_channels", "keep_early_resolution", "early_attn",
    "early_attn_heads", "early_attn_kv_stride", "early_attn_pos_mode")
```
Values are today's `train.py` parser defaults, verbatim (`train.py:629-919`); the test in §3 pins each one so a wiring mistake cannot change a production default silently.

**`train.py`.** Every `parser.add_argument(... default=X)` for a key in `TRAIN_DEFAULTS` reads `default=TRAIN_DEFAULTS[key]`; the `GrouseModelHandler(...)` call is unchanged in effect.

**`model_handler.py`.**
- `_wrap_checkpoint` tags its config keys: `GEOMETRY_CONFIG_KEYS = ("pool", "center_skip", "features", "keep_early_resolution", "early_attn", "early_attn_kv_stride", "early_attn_heads", "early_attn_pos_mode", "dual_branch", "dual_branch_channels", "missing_mask", "vocab")`; `_model_config(model, features)` returns exactly those keys from the model (adding `early_attn_heads`, `early_attn_pos_mode`, `dual_branch`, `dual_branch_channels`, `missing_mask`, `vocab`); `check_checkpoint_config` compares them all. Loss keys (`loss`, `an_pos_weight`, `focal_alpha`) stay out of the compare (not geometry).
- `GrouseModelHandler.from_checkpoint(path, features=None, device=None, **overrides)` (classmethod): unwraps, strips `_orig_mod.`, takes the feature list and geometry from the config through `config_to_model_kwargs`, the vocab through `spec_with_checkpoint_vocab`, builds the handler with `pretrained=False`, loads the state. `load()` keeps its contract and additionally raises a named `ValueError` when the checkpoint's embedding rows differ from the handler's spec (today a shape error).

**`diagnose_training.py` section 3.** `handler2 = GrouseModelHandler.from_checkpoint(path)`; scores through `models.d4_tta_logits(handler2.model, cat_x, cont_x, flip_tta=True)`; the `except` message names the real cause (the exception type and text) instead of the two flags.

**`smoke_test_training.py` and `bench_pipeline.py`.** Handlers built as `GrouseModelHandler(feats, **{k: TRAIN_DEFAULTS[k] for k in HANDLER_KEYS}, pretrained=..., save_path=...)` with the benchmark's CLI flags overriding; the smoke test's train negatives use `expand_rotations=True` (the documented deviation goes away). `pretrain.py`'s shared geometry flags default from `TRAIN_DEFAULTS` too.

### 3. Tests (`tests/test_cr0026.py`; pre-approval per A3)
- Each `train.py` parser default equals its `TRAIN_DEFAULTS` value, and `TRAIN_DEFAULTS` equals a literal copy of today's values (the pin).
- `set(_model_config(model, f)) == set(GEOMETRY_CONFIG_KEYS)` and every key is present in `_wrap_checkpoint(...)["config"]`.
- A handler built from `TRAIN_DEFAULTS` saves a checkpoint that `from_checkpoint` reloads into an identical geometry, and `check_checkpoint_config` rejects a checkpoint whose `missing_mask` differs (needs torch: data host).
- A source test: no `GrouseModelHandler(` call outside `train.py` passes a literal for a key in `HANDLER_GEOMETRY_KEYS` (AST walk over tracked `*.py` minus `inv_*`/`res_*`/`docs/`).

## Impact
- No change to what `train.py` does by default (pinned).
- `check_checkpoint_config` becomes stricter: a bare `load()` of a checkpoint with a different `missing_mask`/`dual_branch`/vocab now fails with a named field instead of a shape error. `--resume` (whole-config equality) is unchanged.
- The smoke test and benchmark exercise the shipped geometry; the benchmark's numbers change (wider stem, centre head): a new baseline line in `bench_pipeline.py`'s docstring.
- PA-0009 is superseded (already recorded); PA-0040 enforced by the tests.

## One change per CR (CR-0011 A5)
Tooling and library code with no data or acceptance change; the pieces share one constant and one test file and are reviewed together.

## Risk: LOW–MEDIUM
| risk | mitigation |
|---|---|
| A default changes while wiring the parser to the constant | The pin test compares to a literal copy of today's values |
| A stricter config check refuses a checkpoint that used to load | Only checkpoints whose stored config disagrees with the handler on a key that already changes the weights' shape or meaning; the message names the key |
| `from_checkpoint` drifts from `predict.load_model` | `predict.load_model` and `calibrate.load_model` are re-pointed to it (BUG-0021's unification), so there is one loader |

## Test plan
**Validatable here:** the parser-default pin and the AST source test (pure Python; `train.py` imports torch at module level, so the pin test reads the parser defaults by parsing the file with `ast` rather than importing it).
**Not validatable here:** the torch tests, the smoke test, the benchmark baseline.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0026.py` on an unmerged branch.
- [ ] 2. `train_defaults.py`, `train.py` wiring, `model_handler.py` changes.
- [ ] 3. `diagnose_training.py`, `smoke_test_training.py`, `bench_pipeline.py`, `pretrain.py` re-pointed; `predict.load_model`/`calibrate.load_model` re-pointed to `from_checkpoint`.
- [ ] 4. Data-host run: smoke test all stages; benchmark new baseline; `diagnose_training.py` section 3 loads the CR-0009 checkpoint.
- [ ] 5. Bookkeeping: BUG-0083, BUG-0085 → FIXED; BUG-0021 → CLOSED (one loader); BUG-0011's PA-0009 row already superseded; `BUG_LOG.md`; PA-0040/PA-0041 Swept? cells; ARCHITECTURE.md "Checkpoints come in two formats" paragraph names `from_checkpoint`; CHANGELOG.
- [ ] 6. Close-out.

## Out of scope
- `--use-weights` (CR-0027).
- Removing section 3 of `diagnose_training.py` altogether (an option the reviewer may prefer; then deliverable 3 shrinks).
