# RESULT_G1: verification of audit findings #1, #2, #6, #8

Verifier: G1 agent, 2026-10-13. No repository file was edited.

Code basis: `model_handler.py`, `train.py`, `predict.py` and `calibrate.py` are byte-identical between 472ba5e and HEAD (9b1f741); `git diff --stat` is empty. `models.py` gained 49 lines at line ~595 (CR-0032 mch features), so `models.py` line numbers below are HEAD numbers. The audited lines are 49 lower; for example, the auditor's `models.py:1107-1143` is HEAD `1156-1197`. `grouse_data.py` gained 4 lines at 157-161, which do not touch the cited guard.

Probe: `probes/g1_probe.py`. It AST-extracts `GrouseModelHandler._model_config`, `check_checkpoint_config`, `roc_auc` and `average_precision` from `model_handler.py` and runs them against a stub model. torch is not installed, so `load_state_dict`, `EarlyAttentionBlock`, `embed` and `torch.load(weights_only=True)` could not be executed. Shape and allowlist claims below are reasoned from the code and from torch's documented behaviour, and are labelled as such.

Exposure baseline: the current recipe is a fresh `train.py --loss an_full --dual-branch unet --early-attn --sched warm_restarts ...` run with no `--init-from`, `--resume` or `--distill-from`. `--missing-mask` defaults to True (`train.py:792-793`). The latest pinned argv (`docs/quality/evidence/CR-0009/retrain/argv.txt`) also uses none of those flags. No evidence file shows `--no-missing-mask`, `--distill-from` or `--resume` in a real run.

---

## #1 Old checkpoints can import current validation labels into training

**Code.**
- `_wrap_checkpoint` (`model_handler.py:464-523`) stores architecture and loss fields only. It records no split digest, point identities or ancestry.
- The following entry points accept a checkpoint without checking its provenance:
  - `load_backbone` (`model_handler.py:640-683`, via `train.py:1284-1290` `--init-from`);
  - `--resume` (`model_handler.py:1083-1101`, geometry only);
  - `--distill-from` (`train.py:1066-1134`, which checks the feature list and geometry only);
  - `calibrate.load_model` (`calibrate.py:86-122`);
  - `train.score_ensemble` (`train.py:495-522`).
- Confirmed by reading. Nothing to probe numerically. The 81 % historical overlap comes from BUG-0060 §3 and was not re-measured.

**Tracking.** ALREADY TRACKED as **BUG-0060** (OPEN, owner the lead, "via a CR"; BUG_LOG row 49). It is cross-referenced by PA-0029, by the CHANGELOG warnings at lines 143-146 and 200-206 ("do not use a checkpoint trained on an earlier split in any BUG-0060 entry point"), and by open-issues lines 259 and 282. BUG-0060 already names the same four entry points and proposes the same mechanism: a split digest in the config, with a refusal on mismatch.

The auditor adds four points that BUG-0060 does not cover:
- Recursive teacher/initializer ancestry. This is defence in depth: if every entry point refuses a foreign split, a student cannot be built from a leaked teacher in the first place.
- Explicit classification of SSL checkpoints as transductive or inductive. BUG-0060 simply exempts them.
- Recording the git commit and dirty state.
- Evaluation-only consumers (`symptom_check.py`, `diagnose_*`, `bench_pipeline.py`). BUG-0060 §3 scenario 4 mentions `symptom_check`, and the CHANGELOG warns about evaluation, but the proposed refusal list omits them.

These should be added as review inputs to BUG-0060's CR. They are not a new bug.

**Exposure.** The current recipe trains fresh and then calibrates its own checkpoint, which shares the current split. It does not reach any affected path. The only protection against misuse is the prose warning in the CHANGELOG.

**Verdict.** ALREADY TRACKED (BUG-0060), VALID-LATENT.

**Severity.** Medium (auditor: High). Impact on misuse is severe: inflated metrics and a leaked calibration that every map applies. But it requires an operator action the CHANGELOG explicitly forbids, and no current run uses these paths.

**Disposition.** Fix under its own CR, as BUG-0060 already plans: a checkpoint format change plus refusals in 4 or 5 loaders. Fold in the auditor's evaluation-path and SSL-classification points. Estimated size is medium: about 60-120 lines across `model_handler.py`, `train.py` and `calibrate.py`, plus tests.

---

## #2 `load()` omits same-shape architecture checks

**Code.**
- `_model_config` (`model_handler.py:534-540`) compares only `pool`, `center_skip`, `features`, `keep_early_resolution`, `early_attn` and `early_attn_kv_stride`.
- `check_checkpoint_config` (`:543-563`) returns immediately for `cfg is None` and skips keys absent from `cfg` (`if k in cfg`).
- `load()` (`:1966-1974`) uses only that check.

**Probe output (real extracted functions).**
- A saved config differing in `early_attn_heads` (4 to 8), `early_attn_pos_mode` (none to abs), `dual_branch`, `dual_branch_channels` and `missing_mask` was ACCEPTED.
- `cfg=None` was ACCEPTED.
- A config containing only `{'pool': 'attn'}` was ACCEPTED.
- A `pool` mismatch was REJECTED (control).

So the auditor's claim about field coverage holds exactly.

**Does a head-count change keep parameter shapes? Checked per `early_attn_pos_mode` (from code; torch not run).**
- The block is always `EarlyAttentionBlock(64, num_heads=...)` (`models.py:1087`).
- `RelativeMultiheadAttention` (`models.py:52-84`) owns `in_proj_weight` (192, 64), `in_proj_bias` (192,) and `out_proj` (64, 64). These are independent of `num_heads`, which only sets `head_dim` for the `.view(b, l, heads, head_dim)` split (`:92-97`).
- **`'none'`:** no other parameter. Changing the head count keeps every shape, so a strict `load_state_dict` succeeds and Q/K/V are re-partitioned into different heads. This is a silent behavioural change. The claim is **TRUE**.
- **`'abs'`:** the sin-cos table is a function of `channels`, is cached and is not a parameter (`_pe`, `models.py:270-275`). The outcome is the same as `'none'`. The claim is **TRUE**.
- **`'rel'`** (default in both `train.py:741` and the handler): `rel_bias` is a parameter of shape `(num_heads, 2*REL_MAX+1, 2*REL_MAX+1)` (`models.py:240-251`). A head-count change therefore changes its shape and strict loading fails loudly. The claim is **FALSE** for the default mode, and the auditor correctly restricted it to none/abs.
- **Additional point the auditor did not state:** switching `pos_mode` between `'abs'` and `'none'` is also shape-identical and silent. Switching to or from `'rel'` adds or removes `rel_bias`, so strict loading fails loudly.

**Other omitted fields fail loudly rather than silently.**
- `dual_branch` changes module keys: `proj`/`stack` in dilated mode versus `enc`/`down`/`bott`/`fuse` in unet mode (`models.py:443-454`), and no Branch B at all when off.
- `dual_branch_channels` changes shapes.
- `missing_mask` changes the `conv1` input width (`models.py:1061-1068`).
- `vocab` lives in the embedding shapes.

The auditor's list of omitted fields is correct as a coverage statement. Only the heads and pos_mode (none/abs) omissions are silent.

**Reachability.**
- `GrouseModelHandler.load()` has exactly one caller: `diagnose_training.py:150`, a diagnostic.
- The production loaders all rebuild the model from the stored config through `models.config_to_model_kwargs` (`models.py:894-930`). That function covers `early_attn_heads`, `early_attn_pos_mode` with its legacy chain, `dual_branch`, `dual_branch_channels` and `missing_mask`. The loaders are `predict.load_model` (`predict.py:111-140`), `calibrate.load_model` (`calibrate.py:86-122`), `train.score_ensemble` (`train.py:505-522`) and `--distill-from` (`train.py:1114-1128`). The mismatch cannot arise on these paths.
- `--resume` compares the whole config with `!=` (`model_handler.py:1094-1101`), so it covers every field.
- The "bare checkpoint skips validation" behaviour is the documented legacy contract (BUG-0010 / CR-0005). For bare checkpoints, `predict.py` and `calibrate.py` fall back to CLI flags and say so.
- The `load_backbone` sub-claim is true. It loads every shape-matched tensor and only warns on a feature-set difference (`model_handler.py:651-682`), so a same-width stem trained for other features would transfer. This is reachable only via `--init-from`, which is not in the current recipe.

**Tracking.** Related but not identical:
- **BUG-0010 / PA-0008**: config must be validated on every `load()`. Validating a subset falls short of PA-0008's intent, so this is arguably a PA-0008 recurrence and the BUG doc needs §4.2's prior-PA failure analysis. The rule was followed only for the fields known at CR-0005 time; later geometry keys were added to `_wrap_checkpoint` and `config_to_model_kwargs` but not to `_model_config`.
- **BUG-0021**: duplicated config handling. The narrow `_model_config` gap itself is not logged.

**Verdict.** PARTLY VALID, and VALID-LATENT for the parts that hold.
- Holds: the coverage gap, the silent heads change in none/abs, and the `load_backbone` same-width transfer.
- Overstated: the dual-branch, missing-mask and vocab mismatches would fail loudly, not silently. The `'rel'` default fails loudly. Every production loader already rebuilds from the full config.

**Severity.** Low (auditor: High). The only silently affected path is a diagnostic script's `load()`, and only for none/abs attention checkpoints. The production paths are not affected.

**Disposition.** Trivial fix with a BUG log entry. Derive `_model_config` keys from the same set `config_to_model_kwargs` decodes (`early_attn_heads`, `early_attn_pos_mode`, `dual_branch`, `dual_branch_channels`, `missing_mask`), so that `load()` compares every geometry key. This is confined to one function with no signature or format change. The BUG doc needs a recurrence analysis against PA-0008, and possibly a PA extension: "every key written by `_wrap_checkpoint` is either compared or used to rebuild". A test asserting that key-set equality would provide mechanical enforcement. The `load_backbone` stem-transfer point is a separate design question for `--init-from` and belongs with BUG-0060's CR or the open-issues tracker. Size: about 10-20 lines plus a small test.

---

## #6 Resume artifacts permit arbitrary pickle execution

**Code.** `torch.load(resume_from, map_location=self.device, weights_only=False)` sits at `model_handler.py:1092-1093`, unchanged since 472ba5e. It was introduced in b7b1c60 ("Add --resume"). The geometry comparison runs after unpickling (`:1094-1101`), so the auditor is right that pickle executes before any check. Every other `torch.load` in the production code uses `weights_only=True`: `model_handler.py:651`, `:1789`, `:1969`, `predict.py:111`, `calibrate.py:87` and `train.py:507` / `:1076`.

**What the payload contains** (`_save_resume_state`, `model_handler.py:584-605`):
- `model_state` and `ema_state`: tensors.
- `optimizer_state`: an `AdamW.state_dict()` (`:985-991`). This holds tensors (`step`, `exp_avg`, `exp_avg_sq`), ints, floats, bools, None, a `betas` tuple and a `params` int list.
- `scheduler_state`: a `CosineAnnealingLR` or `CosineAnnealingWarmRestarts` `state_dict()` (`:1043-1049`). This is the scheduler's `__dict__` minus the optimizer, so ints, floats, lists, bools and str.
- `scaler_state`: a `torch.amp.GradScaler.state_dict()` (float scale, float factors, int counters) or None.
- `epoch`, `best_epoch`: int.
- `sel_ref`, `best_loss`, `best_auc`, `best_strict`, `best_rank`, `dynamic_dropout_value`, `dynamic_dropout_prev_gap`: Python float or None.
- `config`: a dict of str, bool, int, float, a str list and an int dict.

**Probe.** The real `roc_auc` and `average_precision` return Python `float`, and the derived `best_auc` and rank values stay Python `float`. `evaluate` coerces `val_loss`, `strict_accuracy` and `tta_accuracy` with `float()` (`model_handler.py:1878-1903`). So no NumPy scalar enters the payload. NumPy scalars are the usual reason `weights_only=True` fails, with the error "Unsupported global numpy.core.multiarray.scalar".

**Would `weights_only=True` load it (reasoned, not run)?**
- The project's recorded runtime is torch 2.6.0+cu124 (`docs/quality/evidence/CR-0012-d6/test_plan.txt:3`, `smoke_rerun.txt:39`).
- Under torch 2.4 to 2.6, the weights-only unpickler allows tensors and storages, primitive types (int, float including ±inf, bool, str, bytes, None), dict, list, tuple, OrderedDict, torch.Size and dtypes, plus anything registered with `add_safe_globals`.
- torch 2.6 also made `weights_only=True` the default, and its documentation and release notes state that optimizer and GradScaler state dicts load under it.
- Every object in the payload falls in that set, so `weights_only=True` should load it unchanged. The explicit `False` is therefore an opt-out from torch 2.6's own safe default that the payload does not need.
- This could not be executed here. It must be confirmed by a save-then-load round trip on the EC2 torch 2.6 environment.

**Tracking.** None. There is no `weights_only` or pickle entry in BUG_LOG, PREVENTIVE_ACTIONS, the open issues, the CHANGELOG or ARCHITECTURE.

**Exposure.** The `.resume` file is written by the same process next to `save_path` (`_resume_path`, `:578-579`), on a single-user EC2 host. `--resume` is not in the current recipe. Exploitation needs an attacker who can write a file the operator then passes to `--resume`, and such an attacker can usually already modify the `.py` sources.

**Verdict.** VALID-LATENT. The unsafe boundary is real and unnecessary, but the current workflow does not reach it, and exploiting it requires a hostile file on the host.

**Severity.** Low (auditor: High). It is a defence-in-depth gap with no untrusted artifact source in the workflow.

**Disposition.** Trivial fix with a BUG log entry: change it to `weights_only=True` in `fit()`'s resume block and optionally add a `"model_state" in state` schema check. This is one function, with no format, CLI or signature change. The only behaviour change is refusing non-weights pickles. Validation: a resume round-trip test on torch 2.6 (save after one epoch, resume, compare optimizer, scheduler and scaler state). It cannot run in this container. A PA ("every `torch.load` uses `weights_only=True`") plus a grep test would be cheap mechanical enforcement. The sweep finds no other `weights_only=False`. Size: 1-3 lines plus a test.

---

## #8 Missing-mask opt-out still manufactures physical zeros

**Code (HEAD `models.py:1156-1197`; audited 1107-1148).**
- `idx = torch.clamp(codes, 0, vocab - 1)`, and only under `missing_mask` is `miss = (codes == MISSING_CODE) | (codes >= vocab)` applied.
- `cont_x.masked_fill(torch.isnan(cont_x), 0.0)`.
- With `missing_mask=False`, `MISSING_CODE` (-32768, `grouse_data.py:84`) clamps to row 0 and NaN becomes 0.0. This is confirmed by reading; it is not run, since torch is not installed.
- The guard `refuse_legacy_checkpoint_on_repaired` (`grouse_data.py:236-249`) decides by raster tags only (`repaired_paths`, `:224-233`, `COVERAGE_TAGS`). It is called only in `predict.py:1006`, `calibrate.py:342` and `symptom_check.py:489`. It is not called in `train.py` training (`--no-missing-mask`, `train.py:792-800`, `BooleanOptionalAction`) or in the `--distill-from` teacher loader (`train.py:1066-1134`).
- Each sub-claim holds:
  - training can opt out;
  - teachers are unguarded;
  - untagged rasters with real nodata evade the guard.

**The auditor's extra claims (default `missing_mask=True` path).**
- Negative codes other than `MISSING_CODE` clamp to row 0 and are marked valid. This is true mechanically.
  - Reachability is narrow: both readers map the declared nodata and `NODATA_SENTINELS` (-9999, -32768, 32767, -1111) to `MISSING_CODE` first (`dataset.py:277-279,345-347,360`; `predict.py:251-253`).
  - Only an undeclared, non-sentinel negative categorical value would hit it. No evidence was found of such values in the current categorical rasters, but the data was not checked here.
- Validity uses `isnan`, not `isfinite`, so +/-Inf passes as valid. This is true mechanically.
  - The training cache stores int16, so Inf cannot survive there: `nan_to_num` turns it into an overflowed int, which is audit #16, not this finding.
  - The `predict.py` float path could pass Inf only if a source raster contained Inf.

Both extra claims are hardening items at Low severity.

**Tracking.** ALREADY TRACKED as **BUG-0059** (OPEN, owner the lead, via a CR; BUG_LOG row 50; PA-0028 sweep).
- BUG-0059 §3 covers legacy checkpoints and `--no-missing-mask` training. Its §5 root cause is exactly the auditor's point: the guard is scoped by tag rather than by actual missingness.
- Not explicitly in BUG-0059: the unguarded `--distill-from` teacher path, the negative-code clamp under `missing_mask=True`, and the `isnan`/`isfinite` distinction. These should be added to BUG-0059's CR scope as review inputs.

**Exposure.** `--missing-mask` defaults to True and the current recipe does not opt out, so new checkpoints are not affected. Only legacy checkpoints (calibration or prediction on rasters without tags, or used as teachers) and an explicit `--no-missing-mask` reach the main mechanism.

**Verdict.** ALREADY TRACKED (BUG-0059), VALID-LATENT. The extra negative-code and Inf sub-claims are VALID-LATENT, with Low severity.

**Severity.** Medium (auditor: High). The conflation is real and silent when reached (fdist 0 is about 92-96 % of pixels per BUG-0059), but it needs an opt-in or legacy configuration.

**Disposition.** Fix under its own CR, as BUG-0059 already plans, because it changes a CLI flag. Recommended scope:
- refuse `--no-missing-mask` for training, or require an explicit legacy override;
- apply the guard to `--distill-from` teachers;
- base the guard on actual missingness in each batch rather than on tags;
- in the `missing_mask=True` path, flag `codes < 0` as missing and use `isfinite`.

The last item touches only `embed` and could land as a separate trivial fix with its own BUG entry. Size: medium, about 30-60 lines plus tests.

---

## Summary table

| # | Verdict | Severity (auditor) | Tracked | Recommended disposition | Reason |
|---|---|---|---|---|---|
| 1 | ALREADY TRACKED, VALID-LATENT | Medium (High) | BUG-0060 (PA-0029) | Own CR (already planned); add the auditor's eval-path and SSL-classification points; ~60-120 lines | Checkpoints carry no split provenance, but the current fresh-train recipe uses no `--init-from`/`--resume`/`--distill-from` and calibrates its own checkpoint |
| 2 | PARTLY VALID / VALID-LATENT | Low (High) | none directly; related BUG-0010/PA-0008, BUG-0021 | Trivial fix + BUG entry with PA-0008 recurrence analysis; ~10-20 lines | Coverage gap and silent heads/pos_mode change hold for none/abs; dual-branch/missing-mask/vocab/rel fail loudly; production loaders rebuild from full config; only `diagnose_training.py` calls `load()` |
| 6 | VALID-LATENT | Low (High) | none | Trivial fix (`weights_only=True`) + BUG entry + torch 2.6 round-trip test; 1-3 lines | Payload is only tensors and primitives (metrics are Python floats), so the opt-out of torch 2.6's safe default looks unnecessary; `--resume` is unused and the file is self-produced |
| 8 | ALREADY TRACKED, VALID-LATENT | Medium (High) | BUG-0059 (PA-0028) | Own CR (already planned); add the distill-teacher guard, negative-code and `isfinite` points; ~30-60 lines | `missing_mask` defaults to True and the recipe does not opt out; guard is tag-based and absent from training and distillation |
