# BUG-0010: Checkpoint's stored `config` is saved but never validated/used on load

## 1. Description
`model_handler.py`'s checkpoint format wraps model weights together with a
`config` dict specifically so a loader can tell which architecture variant
(pooling mode, center-skip, etc.) produced the weights — pool variants share
identical parameter shapes and are otherwise indistinguishable. `load()`
unpacks the config and discards it without ever consulting it.

## 2. Where encountered
- `model_handler.py:340-357` (`_wrap_checkpoint`, which documents the
  hazard in its own docstring)
- `model_handler.py:904-909` (`load()`, which discards `_cfg`)
- `train.py:184-186` (`score_ensemble`, same discard pattern)

## 3. What it caused to fail
`_wrap_checkpoint`'s docstring states the exact risk this was built to
prevent: "Weights alone are ambiguous: mean/center/gauss pooling produce
byte-identical parameter shapes and differ only in how the spatial map is
collapsed, so a loader that guesses will silently run a gauss-trained model
with mean pooling." Loading a `pool='gauss'`-trained checkpoint into a
handler constructed with the library default `pool='mean'`
(`GrouseModelHandler`'s own constructor default, which differs from
`train.py`'s CLI default of `pool='attn'`) succeeds silently via
`load_state_dict` (shapes match) and runs gauss-trained weights through
mean pooling at inference — wrong-but-plausible predictions with no error.
(Mismatching against an `attn`-pooled checkpoint instead raises a loud
`RuntimeError`, because `conv_out` has a different channel count — so this
failure mode is specifically silent for the mean/center/gauss family.)

## 4. What the defect was
```python
def load(self, path=None):
    state, _cfg = self.unwrap_checkpoint(torch.load(
        path or self.save_path, map_location=self.device,
        weights_only=True))
    self.model.load_state_dict(state)
    return self
```
`_cfg` is bound and never read. `train.py`'s `score_ensemble` has the
identical unused-`_cfg` pattern.

## 5. Root cause analysis (Five Whys)
1. Why can a checkpoint silently load into the wrong architecture variant?
   Because `load()` never checks the checkpoint's own stored config against
   the handler's actual construction.
2. Why doesn't it check? Because `_cfg` is unpacked from the checkpoint and
   then simply discarded — no code path reads it.
3. Why was `config` saved in the checkpoint at all if never read? Because
   the format was designed anticipating this exact ambiguity (per its own
   docstring), but the *loader* side of that design was never implemented
   — only the *saver* side was.
4. Why did the loader side get left out? Likely because `load()` predates
   or was written independently of `_wrap_checkpoint`'s hazard note, or the
   validation step was deferred and never revisited.
5. Why does this matter more than a typical loose end? Because it defeats
   a safety mechanism that was specifically designed into the file format
   for this exact failure mode — the ambiguity `_wrap_checkpoint` warns
   about is live and unguarded on every `load()` call.

**Root cause:** the checkpoint format was designed with a `config` field to
disambiguate architecture variants that share parameter shapes, but the
loader (`load()`/`score_ensemble`) was never wired to validate against or
reconstruct from that stored config, so the ambiguity the field exists to
resolve remains fully unresolved at load time.

## 6. Corrective action
CR-0005 (approved after independent review): added
`GrouseModelHandler.check_checkpoint_config` (option (a) from the original
recommendation — assert-and-raise, not silent reconstruction), called from
both `load()` and `train.py`'s `score_ensemble()`. `cfg is None` (legacy
checkpoints) skips validation, preserving `unwrap_checkpoint`'s documented
backward compatibility. Verified via a standalone reimplementation test in
this environment (torch unavailable to install here): a mismatched pool
config correctly raises `ValueError` naming the mismatched field, a
matching config does not raise, and `cfg=None` does not raise. Reviewer
additionally confirmed `smoke_test_training.py`'s `.load()` caller is
unaffected (matching defaults on both sides). **Status: CLOSED.**

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug concerns
model/checkpoint architecture validation. Result: **none found**. (See
BUG-0011 below, which is a distinct but closely related defect in
`diagnose_training.py` that is made worse by this bug.)

## 8. Preventive action
**PA-0008** (see `PREVENTIVE_ACTIONS.md`): a model checkpoint's stored
config/metadata must be validated against (or used to reconstruct) the
loading handler on every `load()` call, not merely saved — a loader that
discards it and trusts the caller's own constructor defaults can silently
run architecture variants that share parameter shapes with the checkpoint's
true training configuration.
