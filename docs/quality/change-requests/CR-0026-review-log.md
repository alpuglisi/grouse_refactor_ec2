# CR-0026 review log

## Lineage
From BUG-0083 and BUG-0085 (2026-09-30 static review; third occurrence of
the BUG-0010/BUG-0011 class). Reviewers: two fresh agents (CLAUDE.md
§1.2, §1.4); review logs not read by them. Both verified every value in
the v1 `TRAIN_DEFAULTS` literal against `train.py`'s parser (30 of 30
match) and every key against `GrouseModelHandler.__init__`.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | REVISE | 1 |
| 1 | v1 | B (agent, fresh) | REVISE | 0 |

## Round 1, reviewer A
- **A1 BLOCKING:** `HANDLER_KEYS` (§2) is undefined; read as the geometry
  keys, the smoke handlers keep `flip_tta=False`, `dropout=0`,
  `label_smoothing=0`, `ema_decay=0`, so the mirror path is still never
  exercised.
- A2 MAJOR: no flag→key map (`--early-attn-pos` dest `early_attn_pos`
  → `early_attn_pos_mode`; `--ema` → `ema_decay`).
- A3 MAJOR: PA-0040(b) not met: `GEOMETRY_CONFIG_KEYS` is a hand list;
  the test only asserts ⊆; derive the compare set from the written
  config minus the loss keys and test equality.
- A4 MAJOR (BLOCKING if implemented naively): `from_checkpoint`'s
  fallback unspecified; passing `TRAIN_DEFAULTS` as `defaults` to
  `config_to_model_kwargs` rebuilds bare and pre-`missing_mask` wrapped
  checkpoints with validity channels and Branch B → `conv1` mismatch
  where `predict.load_model` loads them today.
- A5 MAJOR: predict/calibrate re-pointing is normative in deliverable 3
  but absent from Scope/§2; return contracts (5-tuple with `cfg`,
  imported by `inspect_point.py:40`, `symptom_check.py:476-486`,
  `diagnose_wetland.py:191`; 3-tuple in calibrate), `_orig_mod.` strip,
  disk-feature fallback and vocab notes must survive; independently
  landable (A5).
- A6 MAJOR: `diagnose_training.py` section 2 (`:117-129`) untouched:
  library defaults and `model(...).mean(dim=(2,3))`; wired to attn it
  broadcasts `(B,2)` against `(B,1)` silently.
- A7 MEDIUM: `bench_pipeline.py`'s own parser defaults (`:83-89`,
  `--dual-branch` "off") must read `TRAIN_DEFAULTS`.
- A8 MEDIUM: `pretrain.py`'s shared flags must be enumerated (SSL keeps
  its own lr/embed-dropout/jitter).
- A9 MEDIUM: `TRAIN_DEFAULTS` omits `strict_objective`,
  `divergence_patience`, `on_divergence`, `divergence_dampen_factor`.
- A10 LOW: `flip_tta=True` literal; AST test should cover `GrouseResNet(`.
- A11 LOW: Impact omits handler banners in predict/calibrate; plain
  `load()` of an interim wrapped checkpoint still shape-errors.
- Sound: diagnosis; literal values; `vocab` compare cannot refuse a
  legitimate path (`load()` is the only caller of the check); `--resume`
  unaffected; ast pin feasible.

## Round 1, reviewer B
- B1 MAJOR: the AST source test cannot fail on today's tree (the
  defective calls pass no geometry kwarg at all); require positively
  `**TRAIN_DEFAULTS` or `from_checkpoint`.
- B2 MAJOR: same as A1 + A7 (`HANDLER_KEYS` undefined; bench defaults).
- B3 MAJOR: same as A6 (section 2; `FocalLoss` on `(B,2)`).
- B4 MAJOR: same as A5 (re-pointing drops `cfg` used by
  `loss_logit_bias` at `predict.py:983`, `calibrate.py:346` and written
  to `calibration.json`; bare-checkpoint CLI fallbacks unmentioned;
  banners now print).
- B5 MEDIUM: A5 — the re-point is independently landable; "one loader"
  false while `train.py:432-448` and `:996-1050` remain copies.
- B6 MEDIUM: same as A3; also `--resume`'s dict equality is key-set
  sensitive, so adding keys orphans existing `.resume` sidecars.
- B7 LOW: dest→key map; `train_defaults.py` importable (torch-free);
  `flip_tta` literal; `load()`'s vocab error only for wrapped checkpoints
  with the key; PA-0041 test cited but not delivered.
- Sound: as reviewer A; no `tests/test_pa0027_lint.py` digest covers a
  touched function; `pretrain.py` defaults already equal `train.py`'s.

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location) |
|---|---|---|
| A1 / B2 | BLOCKING | **Accept** — §2: smoke and bench spread all of `TRAIN_DEFAULTS` (`HANDLER_KEYS` removed); bench's parser defaults read `TRAIN_DEFAULTS[...]` |
| A4 | MAJOR | **Accept** — §2 `from_checkpoint`: `config_to_model_kwargs(cfg, defaults=cli_fallbacks if cfg is None else None)`; `base` stays authoritative for absent keys of wrapped checkpoints |
| A5 / B4 / B5 | MAJOR | **Accept as split** — the predict/calibrate re-pointing is removed from this CR (BUG-0021 stays open; § Out of scope); `load_model` signatures and returns untouched; `from_checkpoint` serves diagnostics only |
| A6 / B3 | MAJOR | **Accept** — §2: section 2 builds from `TRAIN_DEFAULTS` and scores through `handler._pooled_logits`, loss through `handler._batch_loss`; its stale α=0.25/wd 1e-2 literals go |
| A3 / B6 | MAJOR | **Accept** — §2: `_wrap_checkpoint` writes `{**_model_config(model, features), **loss keys}`; `check_checkpoint_config` compares `cfg.keys() − LOSS_CONFIG_KEYS`; the written key set is pinned exactly and unchanged (no `.resume` sidecar orphaned) |
| B1 | MAJOR | **Accept** — §3 test requires positively `**TRAIN_DEFAULTS` (or a dict comprehension over it) or `from_checkpoint`; the test is recorded to FAIL on today's tree (PA-0021(a)) |
| A2 / B7 | MAJOR / LOW | **Accept** — §2 `PARSER_DEST` map; pin test uses it |
| A7 | MEDIUM | **Accept** — folded into A1 |
| A8 | MEDIUM | **Accept** — §2 enumerates `pretrain.py`'s shared flags |
| A9 | MEDIUM | **Accept** — the four recipe keys added to `TRAIN_DEFAULTS` |
| A10 / B7 | LOW | **Accept** — `TRAIN_DEFAULTS["flip_tta"]`; AST test covers `GrouseResNet(` with its allowed forms |
| A11 / B7 | LOW | **Accept** — § Impact; `load()` reads the vocab from `embeddings.<f>.weight` rows, so bare checkpoints get the named error too |
| B7 (PA-0041 test) | LOW | **Accept** — delivered in `tests/test_cr0026.py` |

## Versions
| version | change |
|---|---|
| v1 | initial draft |
| v2 | dispositions above; predict/calibrate re-point split out |
