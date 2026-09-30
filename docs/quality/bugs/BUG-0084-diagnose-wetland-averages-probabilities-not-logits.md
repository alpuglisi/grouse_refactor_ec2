# BUG-0084: `diagnose_wetland.score_points` averages sigmoids over the 4 rotations and omits the mirror, so its per-class score table and "overall per-point AUC" are not the model's validated or deployed score

> Found by the 2026-09-30 static code review at `3b3e7d1`.
> **Status: OPEN; owner: lead; trivial fix (one function).**

## 1. Description
The canonical per-point score averages **logits** over the D4 views
before the sigmoid (`models.d4_tta_logits`;
`model_handler._pooled_logits` with the mirror). `score_points` applies
the sigmoid per rotation, averages the four probabilities, and never
scores the mirror. Mean-of-sigmoids is not a monotone function of
mean-of-logits across points, so the ranking, the per-NLCD-class means
and the printed AUC can differ from `tta_auc` in the training log for
the same checkpoint, and the intact-versus-ablated "drop" column mixes
the two conventions.

## 2. Where encountered
- `diagnose_wetland.py:121-138`.
- Canonical: `models.py:817-842` (`d4_tta_logits`),
  `model_handler.py:397-417` (`_pooled_logits`), `:1888-1896`
  (`evaluate` groups logits).

## 3. What it caused to fail
Per-class conclusions ("wetland classes score anomalously high") drawn
from a score the model does not produce. Diagnostic output only.

## 4. What the defect was
`diagnose_wetland.py:129-138`:
```python
    for cat_x, cont_x, _y, _w in loader:
        cat_x = cat_x.to(device)
        cont_x = cont_x.to(device)
        if nlcd_idx is not None:
            cat_x = cat_x.clone()
            cat_x[:, nlcd_idx] = MISSING_CODE
        outs.append(torch.sigmoid(
            model.logits(cat_x, cont_x).float()).squeeze(1).cpu())
    s = torch.cat(outs).numpy()
    return s.reshape(-1, 4).mean(axis=1)
```

## 5. Root cause analysis (Five Whys)
1. *Why does the score differ?* Sigmoid is applied before the average
   and the mirror view is absent.
2. *Why was a second scorer written?* The script predates
   `d4_tta_logits`; the single-scorer refactor (CHANGELOG 2026-09-20)
   unified the three copies it knew of (`predict_region`,
   `_tb_capture_windows`, `inspect_point`).
3. *Why was this copy missed?* The refactor found copies by knowing
   them, not by searching for the call shape (`sigmoid(model.logits`).
4. *Why no rule?* The invariant lives in ARCHITECTURE.md and a
   docstring; no PA row, no lint.

**Root cause:** a per-point scorer outside the canonical one implements
its own view average (probability space, no mirror), and the
single-scorer invariant is documented but neither listed as a rule nor
mechanically checked.

## 6. Corrective action
**None yet.** Trivial fix: `return d4_tta_logits(model, cat_x, cont_x,
flip_tta=True)` per batch on the unrotated view, or average the four
stored rotations' logits plus mirror before one sigmoid, matching
`evaluate`. Status: **OPEN**. Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md`, `PREVENTIVE_ACTIONS.md` and `CHANGELOG.md`
for "scorer", "sigmoid", "TTA", "d4_tta_logits".

**Matches:** CHANGELOG 2026-09-20 ("one inference-side scorer",
three copies unified; no BUG id), BUG-0083 (section 3 scores through
`forward()`), BUG-0062 (TTA grouping inferred from length).

**Prior-preventive-action failure analysis.** No PA exists for the
invariant; the refactor's sweep was by memory (the same failure PA-0032
(b) names for neighbourhood computations). Category: not a rule, no
recorded search.

## 8. Preventive action
**PA-0041**: every per-point score in any script comes from
`models.d4_tta_logits` or `model_handler._pooled_logits`; averaging over
views happens on logits before the sigmoid; no script calls
`model.forward()`/`model(...)` to score or averages probabilities.
Enforcement: a source-shape test over tracked `*.py` (minus `inv_*`/
`res_*`/`docs/`) flags `torch.sigmoid(` applied to `model.logits`/
`model(` followed by a mean, and any `handler.model(`/`model(` call
outside `models.py`/`model_handler.py`; recorded search terms:
`sigmoid(`, `.mean(axis=1)`, `reshape(-1, 4)`, `model(`.

**Sweep (§3.5), with those terms over the tracked tree:**
`diagnose_wetland.py:135-138` (this); `diagnose_training.py:163-170`
(BUG-0083); `inspect_point.py:175` (sigmoid after `d4_tta_logits`,
correct); `symptom_check.py` (through `predict`'s scorer, correct);
`calibrate.collect_val_logits`, `train.score_ensemble`,
`train._score_teacher_probs` (logit mean then sigmoid, correct).

## Cross-references
ARCHITECTURE.md "exactly one inference-side scorer"; CHANGELOG
2026-09-20; BUG-0062, BUG-0083; PA-0032 (b), PA-0041.
