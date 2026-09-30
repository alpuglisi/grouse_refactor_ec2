# CR-0026: One `TRAIN_DEFAULTS` for every handler construction, a checkpoint config check that compares every geometry key, and `diagnose_training.py` sections 2 and 3 through the shared loader and scorer

**Status: v3, 2026-09-30 — APPROVED by agent quorum and signed off by the lead on 2026-09-30 (CLAUDE.md §1.4; round 2: reviewers A and B both APPROVE WITH FOLLOW-UPS, conditional on the §2 compare-direction wording, met in v3). Nothing has been implemented; the lead has signed off; implementation may begin (deliverables that need the data host wait for one).** Review log: `CR-0026-review-log.md`.

## Scope
Define `train.py`'s recipe defaults once, build every non-`train.py` handler from them, make `check_checkpoint_config` compare every geometry key the checkpoint writes, and rebuild `diagnose_training.py` sections 2 and 3 on the shared loader and scorer (BUG-0083, BUG-0085; PA-0040, PA-0041).

## Why now
BUG-0083: section 3 cannot load any `--missing-mask` checkpoint, misreports the cause, and would score a legacy checkpoint through `forward().mean` over the logit and attention-score channels. BUG-0085: the smoke test and the benchmark build handlers with library defaults and never exercise the shipped geometry. Third occurrence of the BUG-0010/BUG-0011 class; PA-0009 was followed by copying two flags and had no enforcement.

## The change
### 1. Root cause
As BUG-0083 §5: geometry and scoring are reconstructed by hand-copying `train.py` rather than through the shared loader and scorer, and the config compare list is hand-maintained.

### 2. Code (normative)
**`train_defaults.py` (new leaf module; constants only; imports nothing).**
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
    strict_objective=None, divergence_patience=3, on_divergence="warn",
    divergence_dampen_factor=0.5,
)
# argparse dest names that differ from the handler keyword
PARSER_DEST = {"early_attn_pos_mode": "early_attn_pos", "ema_decay": "ema"}
# handler kwargs shared with pretrain.py's encoder construction
PRETRAIN_SHARED_KEYS = ("keep_early_resolution", "early_attn", "early_attn_heads",
                        "early_attn_kv_stride", "early_attn_pos_mode", "missing_mask")
```
Every value is today's `train.py` parser default (`:629-916`); every key is a `GrouseModelHandler.__init__` keyword (`model_handler.py:225-247`), so `GrouseModelHandler(features, **TRAIN_DEFAULTS, ...)` is valid. Keys derived in `train.py` from other flags (`focal_alpha` from `--pos-neg-ratio`, `an_pos_weight`, `sched_t0`/`sched_tmult`; `train.py:1092-1100`) are not in the dict and keep their derivation. The §3 pin test compares each value to a literal copy so a wiring mistake cannot change a production default silently.

**`train.py`.** Every `parser.add_argument(...)` whose dest maps to a key in `TRAIN_DEFAULTS` (through `PARSER_DEST` where the names differ) reads `default=TRAIN_DEFAULTS[key]`; `main` builds the handler as today. Behaviour under default flags is unchanged (pinned).

**`model_handler.py`.**
- `_model_config(model, features)` returns every geometry key: `pool`, `center_skip`, `features`, `keep_early_resolution`, `early_attn`, `early_attn_kv_stride`, `early_attn_heads`, `early_attn_pos_mode`, `dual_branch`, `dual_branch_channels`, `missing_mask`, `vocab` (all readable from the model: `_vocab`, `_early_attn_heads`, `early_attn.pos_mode`, `dual_branch`, `_dual_branch_channels`, `missing_mask`; `vocab` values stay `int()`, and `early_attn_pos_mode` is `"none"` when `model.early_attn is None`, as today). `_wrap_checkpoint` writes `{**_model_config(self.model, features), "loss": ..., "an_pos_weight": ..., "focal_alpha": ...}`; `LOSS_CONFIG_KEYS = ("loss", "an_pos_weight", "focal_alpha")`. The written key set is therefore exactly today's fifteen keys and is pinned by the §3 test, so `--resume`'s whole-config equality (`:1102`) keeps accepting every existing `.resume` sidecar.
- `check_checkpoint_config(model, features, cfg)` iterates the keys of `_model_config(model, features)` and compares each one present in `cfg` (today's direction, `:551-557`; a key absent from an older checkpoint is skipped). Keys of `cfg` outside `set(_model_config) | LOSS_CONFIG_KEYS | {"early_attn_pos_enc"}` are ignored, so an interim checkpoint carrying the legacy `early_attn_pos_enc` key (`:479-491`; decoded by `models.py:876-879`) still loads. The §3 key-set pin is what guarantees every written geometry key is compared. `from_checkpoint` does not call it (it rebuilds from `cfg`).
- `GrouseModelHandler.from_checkpoint(path, *, device=None, features=None, **cli_fallbacks)` (classmethod, for diagnostics and tools): unwraps, strips `_orig_mod.`, takes the feature list from the config (else `features`, else raises), geometry through `config_to_model_kwargs(cfg, defaults=cli_fallbacks if cfg is None else None)` so the shared base defaults stay authoritative for keys absent from a wrapped checkpoint (interim checkpoints without `missing_mask`/`dual_branch` keep loading, as `predict.load_model` loads them today), the vocab through `spec_with_checkpoint_vocab(state)`, and builds `cls(features, spec=..., pretrained=False, device=device, save_path=path, **{**TRAIN_DEFAULTS, **geometry_kw, **{k: cfg[k] for k in LOSS_CONFIG_KEYS if k in cfg}})`, so the non-geometry hyper-parameters (`flip_tta`, thresholds, loss, and so on) are the recipe's and the checkpoint's, never library defaults; loads the state; stores `self.ckpt_config = cfg`.
- `load()`: before `load_state_dict`, for each feature whose `embeddings.<f>.weight` is present in the state (`.get`; a `_orig_mod.`-prefixed key is absent and skipped, and `load_state_dict` then gives the real error), compare its row count to `self.model.embeddings[f].weight.shape[0]` (= `spec[f]["vocab"]`, `models.py:996-999`) and raise `ValueError` naming the feature and both sizes (bare and wrapped alike), instead of the shape error.

**`diagnose_training.py`.** Section 2 builds `GrouseModelHandler(feats, **TRAIN_DEFAULTS, pretrained=False, save_path=...)`, scores through `handler._pooled_logits(cat_x, cont_x)`, computes its loss through `handler._batch_loss(criterion, out, y, w)` (CR-0027 keeps the `w` argument) with `FocalLoss(alpha=handler.hp["focal_alpha"], gamma=handler.hp["focal_gamma"])`, and its optimizer from `handler.hp["lr"]`, `handler.hp["weight_decay"]` and `handler.hp["grad_clip"]`; the hand-copied literals at `:120` (`AdamW(lr=0.0003, weight_decay=1e-2)`), `:133` (`clip_grad_norm_(..., 1.0)`) and the `alpha=0.25` go. Section 3 uses `GrouseModelHandler.from_checkpoint(path, features=feats)` and scores through `models.d4_tta_logits(handler.model, cat_x, cont_x, flip_tta=TRAIN_DEFAULTS["flip_tta"])`; the `except` (`:196-199`) names the exception types it catches and prints the exception type and text.

**`smoke_test_training.py` and `bench_pipeline.py`.** Every handler is `GrouseModelHandler(feats, **{**TRAIN_DEFAULTS, **overrides}, pretrained=..., save_path=...)`; the benchmark's own parser defaults (`:83-89`) read `TRAIN_DEFAULTS[...]` so a CLI flag left at its default no longer re-imposes `dual_branch="off"`, and its `--keep-early-resolution` / `--early-attn` (`:84-85`, `store_true` today) become `BooleanOptionalAction` as in `train.py`, so a flipped default stays switchable; the smoke test's train negatives use `expand_rotations=True`, its `--n-train` help (`:40-41`, "x4 rotations for positives") is corrected, and its default `--epochs` becomes 4 so the focal phase after `warmup_epochs=3` runs (today's 2 epochs never leave the gamma=0 warmup criterion, `model_handler.py:1043`, `:1159`). **`pretrain.py`**: the `PRETRAIN_SHARED_KEYS` flags default from `TRAIN_DEFAULTS` (`:146-159`); its SSL-specific `--lr`, `--weight-decay`, `--embed-dropout`, `--jitter` and its literal `pool='mean'`, `center_skip=False`, `dropout=0.0` (`:212-220`) keep their own values by design.

### 3. Tests (`tests/test_cr0026.py`; pre-approval per A3)
- **Pin:** `train_defaults.py` imports here; each `train.py` parser default (read by `ast`, since `train.py` imports torch) equals `TRAIN_DEFAULTS[key]` through `PARSER_DEST`; each `pretrain.py` `PRETRAIN_SHARED_KEYS` default likewise; `TRAIN_DEFAULTS` equals a literal copy of today's values.
- **Key set:** `set(_model_config(model, f)) | LOSS_CONFIG_KEYS == set(_wrap_checkpoint(...)["config"])`, pinned to the literal fifteen keys (needs torch: host).
- **Source shape (PA-0040(a), able to fail):** an AST walk over tracked `*.py` minus `inv_*`/`res_*`/`docs/`/`tests/` requires that every `GrouseModelHandler(` call outside `train.py` either spreads `TRAIN_DEFAULTS` (accepted forms: `**TRAIN_DEFAULTS`, `**{**TRAIN_DEFAULTS, ...}`, `**{k: TRAIN_DEFAULTS[k] ...}`) or is `GrouseModelHandler.from_checkpoint(`; and that every `GrouseResNet(` call outside `models.py`/`model_handler.py` takes each `PRETRAIN_SHARED_KEYS` kwarg as `args.<dest>` whose `add_argument` has `default=TRAIN_DEFAULTS[key]`, with `pretrain.py`'s SSL-specific literal kwargs (`pool`, `center_skip`, `dropout`, `embed_dropout`) allow-listed by name. Recorded to FAIL on today's tree (`diagnose_training.py:117`, `:158`; `smoke_test_training.py:116/128/137`; `bench_pipeline.py:121`; re-recorded on the tree actually tested if CR-0027 lands first and removes `:128`).
- **Scorer shape (PA-0041):** outside `models.py`/`model_handler.py`, no `Call` on `model`/`.model`, or on a name bound from `GrouseModelHandler`/`GrouseResNet`/`from_checkpoint`, whose result feeds `.mean(dim=`, `torch.sigmoid(` or a logits list; `pretrain.py`'s SimSiam forward (`:245`, `:252`, a `(loss, z_std)` wrapper, not a score) excluded by name. Recorded to FAIL on today's tree at `diagnose_training.py:128`, `:174`.
- **Round trip (host):** a handler from `TRAIN_DEFAULTS` saves a checkpoint that `from_checkpoint` reloads into identical geometry and identical `hp`, and `GrouseModelHandler(feats, **TRAIN_DEFAULTS).load(path)` accepts it (PA-0040(c)); `handler.evaluate()` on the same batch gives the same numbers through both; `check_checkpoint_config` rejects a checkpoint whose `missing_mask` differs and accepts one carrying `early_attn_pos_enc`; `load()` names a vocab mismatch.

## Impact
- No change to what `train.py` does by default (pinned).
- `check_checkpoint_config` becomes stricter for `load()`'s one caller (`:1976`): a checkpoint whose stored `missing_mask`/`dual_branch`/`vocab` disagrees with the handler fails with a named field instead of a shape error. `predict.py`, `calibrate.py`, `score_ensemble` and `--distill-from` rebuild from the checkpoint's own config and never call it; `--resume` unchanged.
- The smoke test and benchmark exercise the shipped geometry; the benchmark's numbers change (validity channels, centre head, Branch B): a new baseline line in `bench_pipeline.py`'s docstring.
- `from_checkpoint` prints the handler's construction banners; a plain `load()` into a handler built from `TRAIN_DEFAULTS` still refuses an interim wrapped checkpoint that lacks `missing_mask` (named error), which is the intended behaviour: use `from_checkpoint`.
- Landing order with CR-0027: `_batch_loss` keeps `w` under both, so either order works; the source-shape FAIL set is re-recorded by whichever lands second.
- PA-0009 superseded (recorded); PA-0040 and PA-0041 enforced by the tests.

## One change per CR (CR-0011 A5)
Tooling and library code with no data or acceptance change; the pieces share one constant and one test file. The predict/calibrate loader unification (BUG-0021) is **split out** (§ Out of scope) because it is independently landable and changes the deployed path's return contracts.

## Risk: LOW–MEDIUM
| risk | mitigation |
|---|---|
| A default changes while wiring the parser to the constant | The pin test compares to a literal copy of today's values, through `PARSER_DEST` |
| A stricter config check refuses a checkpoint that used to load through `load()` | Only where a stored geometry key already disagrees with the handler (the load would shape-error today); the message names the key; `from_checkpoint` is the remedy |
| `from_checkpoint` drifts from `predict.load_model` | Both call `config_to_model_kwargs` + `spec_with_checkpoint_vocab`; unification is BUG-0021's CR |

## Test plan
**Validatable here:** the parser-default pin (AST + import of the torch-free leaf), the source-shape and scorer-shape tests.
**Not validatable here:** the torch tests, the smoke test, the benchmark baseline, `diagnose_training.py` on the CR-0009 checkpoint.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0026.py` on an unmerged branch, with the source-shape and scorer-shape tests recorded failing on today's tree.
- [ ] 2. `train_defaults.py`, `train.py` wiring, `model_handler.py` changes.
- [ ] 3. `diagnose_training.py` (sections 2 and 3), `smoke_test_training.py`, `bench_pipeline.py`, `pretrain.py` re-pointed.
- [ ] 4. Data-host run: smoke test all stages; benchmark new baseline; `diagnose_training.py` on the CR-0009 checkpoint.
- [ ] 5. Bookkeeping: BUG-0083, BUG-0085 → FIXED; `BUG_LOG.md`; PA-0040/PA-0041 Swept? cells; ARCHITECTURE.md "Checkpoints come in two formats" names `from_checkpoint`; tracker row for BUG-0021 (loader unification: `predict.load_model`/`calibrate.load_model` return contracts, `_orig_mod.` strip, disk-feature fallback, `score_ensemble` and `--distill-from` loaders), owner lead; CHANGELOG.
- [ ] 6. Close-out.

## Out of scope
- Re-pointing `predict.load_model` and `calibrate.load_model` to one loader (BUG-0021; its own CR, keeping their return contracts, the `_orig_mod.` strip, the disk-feature fallback, the vocab notes and the bare-checkpoint CLI fallbacks); `train.score_ensemble` and the `--distill-from` loader likewise (PA-0044 sweep item recorded there).
- `--use-weights` (CR-0027).
- Deleting `diagnose_training.py` sections 2 and 3 outright (then deliverable 3 shrinks).
