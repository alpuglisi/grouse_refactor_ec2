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
| 2 | v2 | A (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1 wording) | 0 |
| 2 | v2 | B (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1 wording) | 0 |

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

## Round 2 (v2), reviewer A (bounded, CR-0011 A2)
Every round-1 BLOCKING/MAJOR concern verified RESOLVED in the v2 text
against the code (A1/B2, A2/B7, A3/B6, A4, A5/B4/B5, A6/B3, B1); the 34
`TRAIN_DEFAULTS` values re-derived equal to `train.py:629-916`; the two
`PARSER_DEST` entries are the only dest mismatches.
- **A-N1 MAJOR:** §2 "compares `set(cfg) − LOSS_CONFIG_KEYS` against
  `_model_config`" fails on an interim checkpoint carrying the legacy
  `early_attn_pos_enc` key (`model_handler.py:485-491`,
  `models.py:876-879`): `KeyError` or a spurious mismatch inside
  `load()`, where today (`:556-557`, iterating `actual`) it loads.
- A-N2 MEDIUM: `from_checkpoint`'s non-geometry kwargs unspecified
  (library `flip_tta=False`, `select_by='loss'`), so a tool calling
  `evaluate()` on it reproduces BUG-0085; the source-shape test accepts
  `from_checkpoint(` as compliant.
- A-N3 MEDIUM: the `GrouseResNet(` rule and the scorer rule are not
  decidable on `pretrain.py` (`:212-220` literals by design; `:245`,
  `:252` SimSiam forward); name the accepted spread forms.
- A-N4 MEDIUM: section 2 keeps `lr=0.0003` (`:120`) and
  `clip_grad_norm_(…, 1.0)` (`:133`); `focal_alpha` is not a
  `TRAIN_DEFAULTS` key.
- A-N5 LOW: `diagnose_training.py:147` → `:158`.
- A-N6 LOW (A4): review facts inside the CR text.
- A-N7 LOW: `load()`'s row check must skip features absent from the
  state (`_orig_mod.` prefix).
- A-N8 LOW: bench `store_true` flags with `default=TRAIN_DEFAULTS[...]`.
- A-N9 LOW: add the positive `load()` assertion (PA-0040(c)).
- A-N10 LOW: `_batch_loss` `w` depends on CR-0027's choice.
- A-N11 LOW: `pretrain.py --weight-decay` neither shared nor named
  SSL-specific.
- CR-0027 (same reviewer): no MAJOR; L1 PA-0042 table gaps
  (`train.py:221`, `calibrate.py:142`, `diagnose_wetland.py:134`,
  `acceptance_split.py:739`, `:1261`) and the recorded search; L2 smoke
  lines `:121-122`, `:146`, `:147`; L3 the test's own needle; L4 fix the
  `w` choice; L5 status-line review sentence, `NONVEG_WEIGHT` wording.

## Round 2 (v2), reviewer B (bounded, CR-0011 A2)
Same RESOLVED table (A1/B2, A2, A3/B6, A4, A5/B4/B5, A6/B3, B1), with
`_wrap_checkpoint`'s fifteen keys and the `--resume` equality at
`model_handler.py:1102` re-derived.
- **B-N1 MAJOR:** same as A-N1; remedy "compares every key of
  `_model_config(model, features)` present in `cfg`".
- B-N2 MEDIUM: same as A-N2; remedy: build with
  `{**TRAIN_DEFAULTS, **geometry_kw, **{loss keys from cfg}}` and extend
  the round trip to `evaluate()` parity.
- B-N3 MEDIUM: scorer-shape test not implementable as stated
  (`pretrain.py:245`, `:252`); state the predicate and record
  `diagnose_training.py:128`, `:174` as the pre-change FAIL set.
- B-N4 MEDIUM: cross-CR coupling on `_batch_loss`'s `w`.
- B-N5 LOW: `FocalLoss(alpha=TRAIN_DEFAULTS-derived 0.5)` and the
  optimizer literals; use `handler.hp[...]`.
- B-N6 LOW: section 3 `from_checkpoint(path)` without `features`.
- B-N7 LOW: stale cites `:147`, `:1096`; `--n-train` help.
- B-N8 LOW: pin `pretrain.py`'s shared defaults; `BooleanOptionalAction`;
  the `GrouseResNet(` predicate.
- B-N9 LOW: `_model_config` `int()`/`'none'` fallback; `load()` `.get`.
- B-N10 LOW: smoke `--epochs 2` never leaves the warmup criterion.
- B-N11 LOW: tracker row for BUG-0021 with an owner (PA-0024(b)).
- CR-0027 (same reviewer): N1 MEDIUM fix the `w` choice ("keeps `w`");
  N2 LOW smoke lines; N3 LOW `NONVEG_WEIGHT` still read by O6; N4 LOW
  "about 3×" → "3–4×"; N5 LOW AST-node match; N6 LOW landing order.

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-N1 / B-N1 | MAJOR | **Accept** — §2 `check_checkpoint_config` bullet: iterates `_model_config`'s keys present in `cfg`; cfg keys outside the union plus `early_attn_pos_enc` ignored; `from_checkpoint` does not call it; round trip accepts an `early_attn_pos_enc` checkpoint |
| A-N2 / B-N2 | MEDIUM | **Accept** — §2 `from_checkpoint` bullet: full construction from `TRAIN_DEFAULTS` + geometry + loss keys; § 3 round trip: identical `hp` and `evaluate()` parity |
| A-N3 / B-N3 / B-N8(c) | MEDIUM / LOW | **Accept** — § 3: accepted spread forms; `GrouseResNet(` predicate restated; `pretrain.py` allow-list; scorer predicate stated; pre-change FAIL set `:128`, `:174` |
| A-N4 / B-N5 | MEDIUM / LOW | **Accept** — §2 `diagnose_training.py`: `handler.hp[...]` for alpha, gamma, lr, weight_decay, grad_clip; `:120`, `:133` literals named |
| A-N5 / B-N7 | LOW | **Accept** — `:158`, `:1102`; `--n-train` help; FAIL set re-recorded on the tree tested |
| A-N6 | LOW | **Accept** — review sentences removed from §2 and § Out of scope |
| A-N7 / B-N9 | LOW | **Accept** — §2 `load()` and `_model_config` bullets |
| A-N8 / B-N8(b) | LOW | **Accept** — §2 bench: `BooleanOptionalAction` |
| A-N9 | LOW | **Accept** — § 3 round trip: positive `load()` assertion |
| A-N10 / B-N4 | LOW / MEDIUM | **Accept** — CR-0027 v3 fixes "keeps `w`"; § Impact landing-order bullet |
| A-N11 | LOW | **Accept** — §2 `pretrain.py`: `--weight-decay` named SSL-specific |
| B-N6 | LOW | **Accept** — section 3 passes `features=feats`; `except` names its types |
| B-N8(a) | LOW | **Accept** — § 3 pin covers `pretrain.py`'s shared defaults |
| B-N10 | LOW | **Accept** — §2 smoke `--epochs` default 4 |
| B-N11 | LOW | **Accept** — deliverable 5: tracker row for BUG-0021, owner lead |

## Versions
| version | change |
|---|---|
| v1 | initial draft |
| v2 | round-1 dispositions; predict/calibrate re-point split out |
| v3 | round-2 dispositions above; approved by agent quorum |
