# BUG-0088: `predict.py --compile` is a no-op: `torch.compile(model)` wraps `forward()`, but the scorer calls `model.logits`, which the wrapper forwards uncompiled; the same defect was diagnosed and fixed in `model_handler.py`, whose docstring names this site

> Found by the 2026-09-30 static code review at `3b3e7d1`.
> **Status: FIXED in code (`2c05388`, 2026-09-30, trivial fix, no CR); validation pending on the data host; owner: lead.**

## 1. Description
`predict_region` does `model = torch.compile(model)` and then scores
through `d4_tta_logits`, which calls `model.logits(...)`.
`torch.compile` on a module returns an `OptimizedModule` whose
`forward` is compiled; attribute access to `logits` is forwarded to the
original module, so the scoring path runs eager. The
`_install_compiled_logits` docstring in `model_handler.py` states this
exact diagnosis ("predict.py's --compile was a silent no-op for exactly
that reason") and fixes it on the training side by compiling
`model.logits`; `predict.py` kept the old call.

## 2. Where encountered
- `predict.py:314-316`; scorer `models.py:817` (`model.logits(rc, rn)`).
- Fixed sibling: `model_handler.py:685-692` (docstring), `:724`
  (`self._logits_fn = torch.compile(self.model.logits)`).

## 3. What it caused to fail
`--compile` costs the compile message and nothing else; whole-state
predictions run eager. No numeric effect.

## 4. What the defect was
`predict.py:314-316`:
```python
    if use_compile:
        print("   Compiling model graph (torch.compile)...")
        model = torch.compile(model)
```

## 5. Root cause analysis (Five Whys)
1. *Why no effect?* The compiled object's `forward` is never called;
   `logits` is.
2. *Why was it left?* The fix (CHANGELOG 2026-09-20 throughput entry)
   was applied to `model_handler.py`; the docstring names `predict.py`
   but the change did not touch it.
3. *Why not swept?* PA-0012 sweeps by file-name similarity (numbered
   and suffixed copies); this is the same call shape in an unrelated
   file.

**Root cause:** a fix to a call pattern was applied at one site while
its own record named the other, and the repository's sweep rule is
keyed to file names, not call shapes.

## 6. Corrective action
**None yet.** Trivial fix: `model.logits = torch.compile(model.logits)`
(or pass a compiled callable into `d4_tta_logits`), or drop the flag.
**Implemented 2026-09-30, commit `2c05388` (trivial fix under CLAUDE.md §1: one function, no public signature, file format or schema change).** `predict_region` compiles `model.logits` (the method `d4_tta_logits` calls) instead of the module. Validation here: `python -m py_compile` only, since this environment has no numpy, torch, rasterio or data tree. To verify: `python predict.py --region NH --bounds <small box> --tif-only --compile` prints 'Compiling model.logits' and writes a GeoTIFF equal to the eager run to floating-point rounding, faster.
Status: **FIXED (code); validation pending on the data host.** Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md`, `PREVENTIVE_ACTIONS.md`, `CHANGELOG.md` for
"compile".

**Matches:** CHANGELOG 2026-09-20 ("Training-loop throughput"), which
introduced `_install_compiled_logits`; PA-0002 / PA-0012 / PA-0026
(stale copies and un-backported fixes).

**Prior-preventive-action failure analysis.** PA-0012 requires a sweep
for "file-name-similarity clusters"; PA-0026 finds stale copies by what
they write. Neither reaches a duplicated call pattern across unrelated
files, even when the fix's own text names it. Category: too narrow
(sweep keyed to names/paths, not call shape).

## 8. Preventive action
**PA-0044** (extends PA-0012): when a fix's own record names another
site with the same call shape, or the fix is to a call pattern rather
than a file, the repository is searched for that call shape (recorded
terms) and every hit is fixed or filed in the same change.

**Sweep (§3.5), `torch.compile(` over tracked `*.py`:**
`model_handler.py:724` (correct), `predict.py:316` (this). No other
instance.

## Cross-references
CHANGELOG 2026-09-20; PA-0012, PA-0026, PA-0044.
