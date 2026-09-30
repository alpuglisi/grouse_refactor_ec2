# BUG-0083: `diagnose_training.py` section 3 cannot load any `--missing-mask` checkpoint (hand-copied defaults, config check blind to `missing_mask`), misreports the cause, and would score through `forward().mean` over the logit and attention-score channels

> Found by the 2026-09-30 static code review at `3b3e7d1`. Third
> occurrence of the BUG-0010 / BUG-0011 class (PA-0008 / PA-0009).
> **Status: OPEN; owner: lead; small CR (shared loader) or removal of
> the section.**

## 1. Description
Section 3 rebuilds a handler with `pool='attn', center_skip=True`
(BUG-0011's fix) and the library defaults for everything else. Since
then `train.py` changed its defaults to `--missing-mask` (validity
channels widen the stem), `--dual-branch dilated` and `--early-attn-pos
rel`. `check_checkpoint_config` compares six hand-listed keys that do
not include `missing_mask`, `dual_branch` or `vocab`, so the check
passes and `load_state_dict` raises on the stem width; the `except`
prints that the checkpoint "was trained with different --pool/
--center-skip flags", which is false. If a legacy checkpoint does load,
the section scores with `handler2.model(...)`, i.e. `forward()`, which
returns the raw spatial map: for `pool='attn'` that map has two
channels (logit and attention score), so `.mean(dim=(2, 3))` yields
`(B, 2)`, `.squeeze(1)` is a no-op, and every printed statistic
("predicted positive %", logit mean/std/range, the COLLAPSED verdict)
is computed over logits and attention scores mixed, bypassing the
trained pooling, the centre-skip head and Branch B.

## 2. Where encountered
- `diagnose_training.py:147-150` (handler), `:163-165` (scoring),
  `:188-197` (misattributing handler).
- `model_handler.py:240` (`missing_mask=False` default), `:534-540`
  (`_model_config` key list), `:1966-1974` (`load`, no
  `spec_with_checkpoint_vocab`).
- `train.py:718-719` (`--missing-mask` default True), `:692` (dual
  branch default), `:667` (pos mode default).
- `models.py:1068` (`conv_out` has 2 channels under `pool='attn'`),
  `:1148-1153` (`forward` returns the map), `:1208-1218` (`logits`).

## 3. What it caused to fail
On the CR-0009 checkpoint and every current model the section never
runs and blames the wrong flags. On a `--no-missing-mask` attn model it
prints numbers that are not the model's score. The ARCHITECTURE
invariant "there is exactly one inference-side scorer" and its warning
that `forward()` "would silently bypass both the trained pooling ... and
the center-skip head" are violated in a shipped diagnostic. Diagnostic
output only.

## 4. What the defect was
`diagnose_training.py:147-150`:
```python
        handler2 = GrouseModelHandler(feats, pretrained=False,
                                      save_path="data/models/grouse_single_best.pth",
                                      pool='attn', center_skip=True)
        handler2.load("data/models/grouse_single_best.pth")
```
`diagnose_training.py:163-166`:
```python
                out = handler2.model(
                    cat_x.to(handler2.device),
                    cont_x.to(handler2.device)).mean(dim=(2, 3))
                all_logits.append(out.cpu().squeeze(1))
```
`model_handler.py:534-540`:
```python
    def _model_config(model, features):
        return {"pool": model.pool_mode,
                "center_skip": bool(model.center_skip),
                "features": list(features),
                "keep_early_resolution": bool(model.keep_early_resolution),
                "early_attn": model.early_attn is not None,
                "early_attn_kv_stride": model._early_attn_kv_stride}
```
`_wrap_checkpoint` (`model_handler.py:472-524`) writes fourteen config
keys, including `missing_mask`, `dual_branch`, `early_attn_pos_mode`
and `vocab`.

## 5. Root cause analysis (Five Whys)
1. *Why does the load fail on current checkpoints?* The handler is
   built without validity channels; the checkpoint's `conv1` is wider.
2. *Why is the handler built that way?* BUG-0011's fix copied the two
   flags that were wrong at the time; every later default change in
   `train.py` was not mirrored.
3. *Why does the config check not catch it first?* `_model_config`
   is a hand list of six keys written when those were the only geometry
   keys; `missing_mask`, `dual_branch` and `vocab` were added to
   `_wrap_checkpoint` later without extending the compare list.
4. *Why is the error misattributed?* The `except` message is a literal
   naming the two flags the fix knew about.
5. *Why is scoring wrong?* The section predates `logits()`/
   `d4_tta_logits` and scores the raw map; the single-scorer refactor
   (CHANGELOG 2026-09-20) unified three copies and did not sweep this
   one.

**Root cause:** the diagnostic reconstructs model geometry and scoring
by hand-copying `train.py`'s state rather than through the shared
loader and scorer (`config_to_model_kwargs`,
`spec_with_checkpoint_vocab`, `d4_tta_logits`), and the checkpoint
config check compares a hand-maintained key list rather than every key
the checkpoint writes; PA-0009 was satisfied by copying, not by sharing,
and had no enforcement.

## 6. Corrective action
**None yet.** Proposed: (1) load through the same path as `predict.py`
(`config_to_model_kwargs(cfg)` + `spec_with_checkpoint_vocab(state)`,
or a shared `load_model` moved out of `predict.py`); (2) score through
`models.d4_tta_logits`; (3) make `_model_config` derive its keys from
`_wrap_checkpoint`'s config dict so every geometry key is compared; (4)
or delete section 3, since `inspect_point.py` and `symptom_check.py`
already answer its question correctly. (3) changes production code and
needs a CR; (1), (2), (4) are confined to the diagnostic.
Status: **OPEN**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0026-train-defaults-and-checkpoint-config-compare.md` (v3, approved by agent quorum after two review rounds; nothing implemented).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for
"diagnose_training", "defaults", "config", "missing_mask", "scorer",
"forward".

**Matches:** BUG-0010 (config saved, never validated: PA-0008), BUG-0011
(this file's defaults: PA-0009), BUG-0021 (predict/calibrate
reimplement config handling), BUG-0059 (`missing_mask=False` path).

**Prior-preventive-action failure analysis.** PA-0009 says diagnostics
"must construct the model with the same defaults the training
entrypoint uses (or ... read them from the checkpoint per PA-0008)".
The fix chose the first branch and implemented it by copying two flag
values; the rule has no mechanical check and its sweep was the same
pass. `train.py`'s defaults changed four times since (missing mask,
dual branch, dual-branch channels, position mode) with no re-sweep.
PA-0008's compare list was likewise never tied to the writer's key set.
Category: not enforced-verifiable, and followed by copy rather than by
sharing. Third occurrence of the class.

## 8. Preventive action
**PA-0040** (supersedes PA-0009; extends PA-0008): (a) every script
that constructs a `GrouseModelHandler` or `GrouseResNet` other than
`train.py` loads through the shared loader (`config_to_model_kwargs` +
`spec_with_checkpoint_vocab`) or imports `train.py`'s parser defaults
from one shared `TRAIN_DEFAULTS` mapping; a hand-copied flag value is a
defect; (b) `check_checkpoint_config` compares every geometry key
`_wrap_checkpoint` writes, derived from that dict, never a hand list;
(c) a test builds a handler from `TRAIN_DEFAULTS` and asserts a
`train.py`-written checkpoint loads and that the compare list equals
the written key set.

**Sweep (§3.5), handler/model constructions outside `train.py`:**
`diagnose_training.py:106`, `:147` (this); `smoke_test_training.py:116`,
`:128`, `:137` and `bench_pipeline.py:121` (BUG-0085); `pretrain.py:212`
(its own parser; `missing_mask` default True matches `train.py`, pool is
irrelevant to SSL; recorded, not filed). Scorers outside the canonical
two: this section and `diagnose_wetland.py` (BUG-0084).

## Cross-references
BUG-0010, BUG-0011, BUG-0021, BUG-0059, BUG-0084, BUG-0085, PA-0008,
PA-0009, PA-0040, PA-0041; ARCHITECTURE.md "exactly one inference-side
scorer".
