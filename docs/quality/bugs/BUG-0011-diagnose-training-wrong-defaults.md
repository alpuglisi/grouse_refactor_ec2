# BUG-0011: `diagnose_training.py` loads real checkpoints with mismatched architecture defaults and can't catch the resulting crash

## 1. Description
`diagnose_training.py` constructs `GrouseModelHandler` with no `pool=`/
`center_skip=` arguments (so it defaults to `pool='mean', center_skip=False`)
before loading a real checkpoint that was, under `train.py`'s actual
defaults, trained with `pool='attn', center_skip=True`. Combined with
BUG-0010 (checkpoint config discarded on load), this either silently
mispools or crashes with an unhandled `RuntimeError` that the script's
narrow `except FileNotFoundError` cannot catch.

## 2. Where encountered
`diagnose_training.py:131-134` (handler construction + `load()` call),
`diagnose_training.py:169` (the too-narrow `except` clause). Contrast:
`train.py:255-289` (the actual training defaults: `pool='attn',
center_skip=True`) and `model_handler.py:201` (`GrouseModelHandler`'s own
constructor default: `pool='mean', center_skip=False`).

## 3. What it caused to fail
Running `python diagnose_training.py` against any checkpoint produced by
`train.py`'s real default recipe crashes at the `handler2.load(...)` call
in section 3 with an unhandled `RuntimeError` (conv_out shape mismatch: 2
channels for `attn` pooling vs. 1 for `mean`), killing the whole diagnostic
script — including the two sections that had already printed useful output
before this point. The tool exists specifically to diagnose "prediction
collapse," and this defect prevents it from ever reaching that check against
a real checkpoint trained the normal way.

## 4. What the defect was
```python
handler2 = GrouseModelHandler(feats, pretrained=False,
                              save_path="data/models/grouse_single_best.pth")
handler2.load("data/models/grouse_single_best.pth")
...
except FileNotFoundError:
    print("  grouse_single_best.pth not found in this directory - ...")
```

## 5. Root cause analysis (Five Whys)
1. Why does `diagnose_training.py` crash on a real checkpoint? Because it
   constructs the handler with defaults that don't match how the checkpoint
   was actually trained (`attn`/`center_skip=True` vs. the handler's own
   library defaults `mean`/`center_skip=False`).
2. Why does that mismatch cause a hard crash instead of a silent wrong
   answer here (unlike the mean/center/gauss case in BUG-0010)? Because
   `attn` pooling changes `conv_out`'s output channel count, so
   `load_state_dict` raises `RuntimeError` for a shape mismatch rather than
   succeeding silently.
3. Why doesn't the diagnostic script handle that error? Because its
   `except` clause only catches `FileNotFoundError`, anticipating "the file
   doesn't exist" but not "the file exists but doesn't match the handler's
   assumed architecture."
4. Why does the diagnostic tool use different defaults than `train.py` in
   the first place? Because it constructs `GrouseModelHandler` directly
   with no `pool=`/`center_skip=` arguments, silently falling back to the
   class's own generic defaults rather than mirroring the training
   entrypoint's defaults or reading them from the checkpoint (which, per
   BUG-0010, isn't wired up to be usable for this anyway).
5. Why does this compound with BUG-0010? Because if `load()` validated the
   checkpoint's stored config against the handler's construction (BUG-0010's
   fix), this specific defect would either be caught earlier with a clear
   message, or `diagnose_training.py` could use the config to construct the
   handler correctly in the first place.

**Root cause:** the diagnostic tool's handler construction doesn't mirror
`train.py`'s actual training defaults (and can't yet fall back to the
checkpoint's own stored config, per BUG-0010), and its exception handling
is scoped only to the failure mode its author anticipated (missing file),
not the one that actually occurs (architecture mismatch).

## 6. Corrective action
CR-0005 (approved after independent review, alongside BUG-0010's fix):
`diagnose_training.py`'s section-3 handler now constructs with
`pool='attn', center_skip=True`, mirroring `train.py`'s actual defaults
(confirmed at `train.py:255`/`:285`), and the `except` clause is widened to
`(RuntimeError, ValueError)` alongside the existing `FileNotFoundError`, so
a config mismatch (including the new BUG-0010 validation error) is
reported clearly instead of crashing the script. Verified: file parses.
Reconstructing from the checkpoint's own stored config (rather than a
hardcoded mirror of `train.py`'s defaults) remains out of scope, as noted
in CR-0005. **Status: CLOSED.**

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: **related to BUG-0010**
(same underlying gap — checkpoint config not used to guarantee architecture
consistency) but a distinct defect (this one is in the diagnostic tool's own
hardcoded defaults and exception scope, not in `model_handler.py`'s `load()`
itself). Not a strict recurrence of a previously-written preventive action
(BUG-0010's PA-0008 was written in this same review round), but this bug is
evidence that PA-0008 alone is insufficient — callers also need to not
silently fall back to mismatched local defaults.

## 8. Preventive action
**PA-0009** (see `PREVENTIVE_ACTIONS.md`) — extends PA-0008: diagnostic/
tooling scripts that load a real checkpoint must construct the model with
the same defaults the training entrypoint uses (or, once available, read
them from the checkpoint per PA-0008), and must not narrow their exception
handling to only the error they expect — an unexpected `RuntimeError` from
a mismatched load should be caught and reported, not left to crash the
whole diagnostic.
