# CR-0005: Validate checkpoint config on load (BUG-0010) and align `diagnose_training.py` (BUG-0011)

## Scope
Add a shared config-validation check to `GrouseModelHandler` that compares
a loaded checkpoint's stored `config` against the actual model it's being
loaded into, called from both `GrouseModelHandler.load()` and `train.py`'s
`score_ensemble()`. Separately, fix `diagnose_training.py` to construct its
handler with `train.py`'s real defaults and to catch the new validation
error (and any other load-time `RuntimeError`) instead of only
`FileNotFoundError`.

## Why now
BUG-0010 (severity high): `_wrap_checkpoint`'s own docstring explains the
checkpoint format carries `config` specifically because mean/center/gauss
pooling share identical parameter shapes and are otherwise
indistinguishable — but `load()` and `score_ensemble()` both discard the
unpacked config without ever checking it, so a mismatched load succeeds
silently. BUG-0011 (severity medium): `diagnose_training.py` compounds
this by constructing its diagnostic handler with the library's generic
defaults (`pool='mean', center_skip=False`) instead of `train.py`'s real
training defaults (`pool='attn', center_skip=True`), and its `except
FileNotFoundError` can't catch the resulting `RuntimeError`, crashing the
whole diagnostic tool instead of reporting the mismatch.

## The change

### 1. `model_handler.py` — add shared validation (fixes BUG-0010)
Add two staticmethods on `GrouseModelHandler`, next to the existing
`unwrap_checkpoint`:
```python
@staticmethod
def _model_config(model, features):
    return {"pool": model.pool_mode,
            "center_skip": bool(model.center_skip),
            "features": list(features),
            "keep_early_resolution": bool(model.keep_early_resolution),
            "early_attn": model.early_attn is not None,
            "early_attn_kv_stride": model._early_attn_kv_stride}

@staticmethod
def check_checkpoint_config(model, features, cfg, source="checkpoint"):
    """Raise if a checkpoint's stored config doesn't match the model
    it's being loaded into. BUG-0010: config was saved but never
    validated on load, allowing a checkpoint trained with one pooling
    mode to silently load into a handler built with a different one -
    mean/center/gauss pooling share identical parameter shapes, so
    load_state_dict succeeds either way. cfg=None (legacy checkpoints
    written before the config field existed) skips validation, matching
    unwrap_checkpoint's documented backward-compatibility contract."""
    if cfg is None:
        return
    actual = GrouseModelHandler._model_config(model, features)
    mismatches = {k: (cfg[k], actual[k]) for k in actual
                  if k in cfg and cfg[k] != actual[k]}
    if mismatches:
        raise ValueError(
            f"{source}: checkpoint config does not match this model's "
            f"construction - refusing to load a mismatched architecture "
            f"(BUG-0010). Mismatched fields as (checkpoint, actual): "
            f"{mismatches}.")
```
`load()`:
```python
def load(self, path=None):
    state, cfg = self.unwrap_checkpoint(torch.load(
        path or self.save_path, map_location=self.device,
        weights_only=True))
    self.check_checkpoint_config(
        self.model, list(self.cat_features) + list(self.cont_features),
        cfg, source=path or self.save_path)
    self.model.load_state_dict(state)
    return self
```

### 2. `train.py`'s `score_ensemble()` — use the same check
```python
state, cfg = GrouseModelHandler.unwrap_checkpoint(
    torch.load(path, map_location=device, weights_only=True))
GrouseModelHandler.check_checkpoint_config(
    model, cat_f + cont_f, cfg, source=path)
model.load_state_dict(state)
```
(replaces the current `state, _cfg = ...` / discard pattern; `model` here
is already constructed with the per-member `pool` from the `members` list
and `args.center_skip`, so this check now verifies that declared pairing
against the checkpoint's actual stored config instead of trusting it
silently.)

### 3. `diagnose_training.py` — fix BUG-0011
```python
# before
handler2 = GrouseModelHandler(feats, pretrained=False,
                              save_path="data/models/grouse_single_best.pth")
handler2.load("data/models/grouse_single_best.pth")
...
except FileNotFoundError:
    print("  grouse_single_best.pth not found in this directory - "
         "run from where train.py saved it, or skip this section.")

# after
handler2 = GrouseModelHandler(feats, pretrained=False,
                              save_path="data/models/grouse_single_best.pth",
                              pool='attn', center_skip=True)
handler2.load("data/models/grouse_single_best.pth")
...
except FileNotFoundError:
    print("  grouse_single_best.pth not found in this directory - "
         "run from where train.py saved it, or skip this section.")
except (RuntimeError, ValueError) as e:
    print(f"  Couldn't load grouse_single_best.pth into this section's "
         f"handler (pool='attn', center_skip=True, matching train.py's "
         f"defaults) - if you trained with different --pool/--center-skip "
         f"flags, this diagnostic doesn't know that yet: {e}")
```
(mirrors `train.py`'s actual `--pool`/`--center-skip` argparse defaults,
confirmed at `train.py:255`/`:285`; still doesn't read the checkpoint's own
stored config to auto-detect the true architecture — that would require
reconstructing `GrouseModelHandler` from `cfg` before calling `load()`,
which is out of scope here, see below.)

## Impact on other parts of the system
- `GrouseModelHandler.load()` gains a new failure mode: it can now raise
  `ValueError` where it previously silently succeeded on a mismatched
  checkpoint. Any caller relying on `load()` never raising for a
  config-carrying checkpoint (i.e. anyone currently loading a mismatched
  checkpoint and getting away with it) will now see a loud, actionable
  error instead. This is the intended fix, not a regression — silent
  wrong-model inference is the worse outcome.
- `train.py`'s `score_ensemble()` gains the same new failure mode for
  ensemble members whose declared `pool` (in the `members` list) doesn't
  match the checkpoint's actual stored config.
- `diagnose_training.py` section 3 now runs against real checkpoints
  trained with `train.py`'s actual defaults instead of crashing; if a
  checkpoint was trained with non-default `--pool`/`--center-skip` flags,
  the new `except` clause reports that clearly instead of a raw traceback.
- `smoke_test_training.py:132-134` also calls `.load()` on a
  `GrouseModelHandler` — confirmed via independent review it saves and
  loads with matching library defaults on both sides (no `pool`/
  `center_skip` override), so `check_checkpoint_config` finds no mismatch
  and this caller is unaffected by the new validation.
- Legacy checkpoints saved before the `config` field existed (`cfg is
  None`) are unaffected — validation is skipped for them, matching
  `unwrap_checkpoint`'s existing documented behavior.

## Risk assessment
**Risk level: medium.** The validation logic itself is a direct,
mechanical comparison with no ambiguity. Main risk: if any current,
intentionally-mismatched-but-working workflow exists (e.g. someone
deliberately loading a checkpoint into a differently-configured handler
for some legitimate reason not evident in code), this CR would now block
it. **Mitigation:** the error message names every mismatched field
explicitly, so any legitimate case is immediately diagnosable and
override-able by matching the handler's construction args to the
checkpoint's `config` (which the error message effectively surfaces).

## Test plan
- `python -c "import ast; [ast.parse(open(f).read()) for f in ['model_handler.py','train.py','diagnose_training.py']]"`
  to confirm all three files still parse.
- Synthetic verification (in this environment): construct two small
  `GrouseResNet` instances with different `pool` values, save one's
  wrapped checkpoint via `_wrap_checkpoint`, and confirm
  `check_checkpoint_config` raises `ValueError` when validated against the
  other's config, and does not raise when validated against a
  matching-pool instance.
- Cannot validate against a real trained checkpoint or the actual
  `diagnose_training.py` end-to-end flow in this environment (no `data/`
  tree, no real `grouse_single_best.pth` present) — flagged as an accepted
  test gap; recommend the project owner run `diagnose_training.py` against
  a real checkpoint after this lands to confirm section 3 completes.

## Deliverables
- [x] Add `_model_config`/`check_checkpoint_config` staticmethods to
      `GrouseModelHandler` in `model_handler.py`.
- [x] Update `GrouseModelHandler.load()` to call the new check.
- [x] Update `train.py`'s `score_ensemble()` to call the new check.
- [x] Update `diagnose_training.py`'s handler construction to mirror
      `train.py`'s real defaults and widen its `except` clause.
- [x] Run the synthetic mismatch/match check described in the test plan.
- [x] Update `BUG-0010-checkpoint-config-discarded.md` and
      `BUG-0011-diagnose-training-wrong-defaults.md` corrective actions and
      `BUG_LOG.md` statuses.

## Out of scope
- Reconstructing the model/handler automatically from a checkpoint's
  stored config (rather than just validating against the caller's
  construction) — a larger API change (`GrouseModelHandler.from_checkpoint(path)`
  or similar) that `diagnose_training.py` and other tooling could use to
  avoid needing to know the right defaults at all; worth a future CR if
  this keeps coming up.
- Any other checkpoint/config field beyond the six already present in
  `_wrap_checkpoint`'s existing `config` dict.

## § Review

**Reviewer (independent agent, re-derived from current source): APPROVE.**
Confirmed `load()`/`score_ensemble()` currently discard `cfg` exactly as
quoted; confirmed all six config fields exist as the exact attribute names
the proposed `_model_config` references (`models.py:144,174,186-190,221`);
confirmed `self.cat_features`/`self.cont_features` exist on
`GrouseModelHandler`; confirmed `diagnose_training.py`'s current handler
construction and `train.py`'s actual `--pool`/`--center-skip` defaults
(`attn`/`True`) match the CR's proposed fix.

Two non-blocking notes: (1) the CR cited `train.py:283` for the
`--center-skip` default; the reviewer's independent read found it at
`train.py:285` — a citation drift, not a functional issue. (2) the CR's
"Impact on other parts of the system" section discussed `load()`/
`score_ensemble()` in the abstract but didn't name a third caller the
reviewer found via grep, `smoke_test_training.py:132-134`. The reviewer
traced it and confirmed it's a same-defaults round-trip (save then load
with no `pool`/`center_skip` override on either side) that `
check_checkpoint_config` will find no mismatch for — not a defect in the
fix, but a completeness gap in the write-up.

**Disposition: accepted, corrected below.** Citation fixed to `:285`;
`smoke_test_training.py` added to the impact analysis and confirmed
unaffected (same-defaults round-trip, no mismatch raised).

**Author sign-off:** approved for implementation as revised.
