# BUG-0085: `smoke_test_training.py` and `bench_pipeline.py` build handlers with the library defaults (mean pool, no centre skip, no validity channels, no flip TTA, no Branch B), so neither exercises the geometry `train.py` ships

> Found by the 2026-09-30 static code review at `3b3e7d1`. Sibling of
> BUG-0083 (same mechanism, different files).
> **Status: OPEN; owner: lead; fixed with BUG-0083's `TRAIN_DEFAULTS`.**

## 1. Description
`GrouseModelHandler.__init__` defaults to `pool='mean'`,
`center_skip=False`, `missing_mask=False`, `flip_tta=False`,
`dual_branch='off'`. `train.py`'s CLI defaults are `attn`,
centre skip on, missing mask on, flip TTA on, dual branch `dilated`
with 32 channels. The smoke test constructs three handlers and the
benchmark one with only a subset of those flags, so the end-to-end
smoke test never touches the validity-channel stem, the attention
pooling, the centre-skip head, Branch B or the mirror TTA, and the
benchmark measures a narrower network than the one whose throughput
it is meant to protect.

## 2. Where encountered
- `smoke_test_training.py:116-118`, `:128-131`, `:137` (three
  `GrouseModelHandler(feats, pretrained=..., save_path=...)` calls).
- `bench_pipeline.py:121-126` (passes `pool`, `dropout`,
  `keep_early_resolution`, `early_attn`, `dual_branch`, `flip_tta`;
  omits `center_skip` and `missing_mask`).
- Defaults: `model_handler.py:225-246`; `train.py:629`, `:692`, `:718`,
  `:728-729`, `:915`.

## 3. What it caused to fail
A regression confined to `missing_mask`'s validity channels, the
attention pool, the centre-skip head or Branch B passes the smoke test
("all 7 stages"), and `bench_pipeline.py`'s before/after numbers are for
a model without validity channels or the centre head. Tooling only.

## 4. What the defect was
`smoke_test_training.py:116-118`:
```python
        handler = GrouseModelHandler(
            feats, pretrained=not args.no_pretrained,
            save_path="data/models/smoke_test_model.pth")
```
`bench_pipeline.py:121-126`:
```python
    handler = GrouseModelHandler(
        features, pretrained=False, pool=args.pool, dropout=args.dropout,
        keep_early_resolution=args.keep_early_resolution,
        early_attn=args.early_attn, dual_branch=args.dual_branch,
        flip_tta=args.flip_tta, save_path=os.path.join(
            args.cache_dir or ".", "bench_discard.pth"))
```

## 5. Root cause analysis (Five Whys)
1. *Why the wrong geometry?* The constructor's own defaults are the
   original project's recipe; `train.py` overrides them in its parser.
2. *Why do these scripts not pass the overrides?* They were written
   against the constructor and never updated as `train.py`'s defaults
   moved (attn pool, centre skip, missing mask, dual branch).
3. *Why was that not caught?* PA-0009 (BUG-0011) required diagnostics to
   use the training entrypoint's defaults but was satisfied by copying
   two flags in one file; there is no shared definition and no test.

**Root cause:** the training defaults live only in `train.py`'s parser,
so every other constructor call restates them by hand or omits them;
the same root cause as BUG-0083.

## 6. Corrective action
**None yet.** With BUG-0083's CR: construct from a shared
`TRAIN_DEFAULTS` mapping (`GrouseModelHandler(feats, **TRAIN_DEFAULTS,
save_path=...)`) in both scripts, and pass `expand_rotations=True` to the
smoke test's train negatives (the documented deviation at `:87-89`) so
its data path matches `train.py` too. Status: **OPEN**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0026-train-defaults-and-checkpoint-config-compare.md` (DRAFT v1, awaiting independent review under CLAUDE.md §1.2; nothing implemented).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** as BUG-0083. **Matches:** BUG-0011 / PA-0009 (same
rule), BUG-0057 (smoke test's validation builder), BUG-0083 (sibling).

**Prior-preventive-action failure analysis.** As BUG-0083: PA-0009
followed by copy, no enforcement, no re-sweep when defaults changed.

## 8. Preventive action
**PA-0040** (filed under BUG-0083) covers it; the sweep there lists
these four constructions. No separate rule.

## Cross-references
BUG-0011, BUG-0057, BUG-0083; PA-0009, PA-0040.
