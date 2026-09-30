# BUG-0021: `predict.py`/`calibrate.py` reimplement checkpoint-config handling instead of using the shared `check_checkpoint_config` (PA-0009 sweep finding)

## 1. Description
The PA-0009 sweep (run in response to BUG-0019) found that `predict.py`'s
and `calibrate.py`'s `load_model()` functions each independently
reconstruct a `GrouseResNet` directly from a checkpoint's stored `config`
(when present), instead of going through `GrouseModelHandler` and the
shared `check_checkpoint_config` validator added for BUG-0010. **Verified
this is not a live instance of BUG-0010's failure mode** — see §3 — but it
is a real design-consistency gap: two different mechanisms now solve the
same problem in this codebase, and one of them (`check_checkpoint_config`)
won't benefit the other's callers if it's ever extended.

## 2. Where encountered
`predict.py:80-126` (`load_model`), `calibrate.py:71-108` (`load_model`).

## 3. What it caused to fail
**Nothing — verified not a live defect.** Both functions build the model
*from* the checkpoint's own `cfg` when present (`pool = cfg.get("pool",
cli_pool)`, etc.), then construct `GrouseResNet` using those exact values.
Since the model's pool/center_skip/etc. are read directly from the same
`cfg` used to decide them, a mismatch between "what the checkpoint says"
and "what the model was built with" is structurally impossible here — this
is BUG-0010's original corrective-action option (b) ("use the stored
config to reconstruct the handler's architecture before calling
`load_state_dict`"), which CR-0005 explicitly marked out of scope in favor
of option (a) (validate caller-declared construction against the
checkpoint) for `GrouseModelHandler.load()`/`train.py`'s
`score_ensemble()`. `predict.py`/`calibrate.py` independently already
implement option (b) for their own call sites — correctly. The only
residual risk is the "bare checkpoint" (`cfg is None`) fallback, which
uses CLI-flag defaults; both files' CLI defaults are confirmed correct
(`--pool` default `"attn"`, `--center-skip` default `True`, matching
`train.py`'s real training defaults) — not a BUG-0011-style mismatch.

## 4. What the defect was
Not a correctness defect — a **duplication/consistency** issue: the same
"disambiguate a checkpoint's architecture" problem BUG-0010 named is
solved twice in this codebase, by two different, independently-maintained
mechanisms (`check_checkpoint_config`'s validate-against-caller approach
in `model_handler.py`/`train.py`, and `load_model()`'s reconstruct-from-
checkpoint approach in `predict.py`/`calibrate.py`), with no shared code
between them.

## 5. Root cause analysis (Five Whys)
1. Why do `predict.py`/`calibrate.py` not call `check_checkpoint_config`?
   Because they solve the underlying problem (architecture ambiguity) a
   different way — reconstructing from the checkpoint rather than
   validating a separately-constructed model against it — and that
   approach predates `check_checkpoint_config`'s introduction in CR-0005.
2. Why weren't they unified when `check_checkpoint_config` was added?
   Because CR-0005 was scoped to fix BUG-0010's two confirmed call sites
   (`load()`, `score_ensemble()`) plus BUG-0011's `diagnose_training.py`
   fix, and explicitly marked "reconstructing the model/handler
   automatically from a checkpoint's stored config" as out of scope —
   without recognizing that `predict.py`/`calibrate.py` already do exactly
   that, informally, for their own call sites.
3. Why does having two mechanisms matter if both currently work correctly?
   Because if `check_checkpoint_config`'s validated field set is ever
   extended (a new config key), `predict.py`/`calibrate.py`'s independent
   reconstruction logic won't pick up the change automatically — they'd
   need a separate, easy-to-forget edit, the same "fix in one place,
   sibling doesn't get it" mechanism as PA-0002, just for a helper
   function's logic rather than a whole duplicated script.

**Root cause:** two independent, correct-today implementations of the same
architecture-disambiguation concern exist in the codebase because the
CR-0005 fix didn't audit for pre-existing solutions to the same problem
elsewhere before adding a new one.

## 6. Corrective action
**None implemented — deliberately deferred, not urgent.** Both call sites
are verified correct today; unifying them (e.g. a
`GrouseModelHandler.from_checkpoint(path, ...)` constructor that
`predict.py`/`calibrate.py` could call instead of their own `load_model()`
logic) is the "reconstruct automatically" API CR-0005 already flagged as
future scope, not a bug fix — this finding is best read as evidence for
prioritizing that follow-up CR, not as something broken today. **Status:
OPEN, low priority** (no live correctness risk, pure consistency/future-
maintainability concern).

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: **related to BUG-0010/
PA-0008/PA-0009** (same underlying concern — checkpoint architecture
disambiguation) but **not a recurrence of BUG-0010's failure mode**, since
the mechanism here (reconstruct-from-config) already prevents the silent-
mismatch failure BUG-0010 described. This is closer to a documentation/
consistency finding than a bug recurrence.

**Prior-preventive-action failure analysis:** not applicable in the usual
sense — PA-0008/PA-0009 weren't violated by `predict.py`/`calibrate.py`
(both already satisfy the *intent* of "validate/reconstruct from stored
config"), they just satisfy it via an un-shared, parallel mechanism. No
prior preventive action failed to prevent a recurrence, because there was
no recurrence — the PA-0009 sweep's real value here was confirming this,
not finding a new instance of the original bug.

## 8. Preventive action
No new PA needed — this doesn't fit the "same defect recurred" pattern
PA-0008/0009 target. Recorded so a future CR unifying
`check_checkpoint_config` and `load_model()`'s reconstruction logic (per
CR-0005's own noted future scope) has this as supporting evidence, and so
the next reviewer doesn't have to re-derive that `predict.py`/`calibrate.py`
are already safe before considering whether to touch them.
