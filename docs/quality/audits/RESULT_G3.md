# G3 verification: findings #4, #7, #13, #14, #15, #21, #22

Audited commit 472ba5e; working tree 9b1f741. `git diff --stat 472ba5e HEAD -- model_handler.py predict.py calibrate.py train.py` is empty, so every line cited below is the same at both commits. `dataset.py` and `models.py` are cited at HEAD. Probes are in `probes/g3_*.py`. Each one extracts the real function with `ast` and runs it under `python3 -I`. torch is not installed, so no GPU, autocast or `torch.compile` code was run. Those parts are judged by reading the code.

## Summary

| # | Verdict | Severity: mine (auditor) | Tracked | Disposition | Reason |
|---|---|---|---|---|---|
| 4 | VALID (reachable; in practice it only matters for degenerate models) | Low (High) | none | Trivial fix in one function, plus a BUG entry and a tie-permutation test. About 15 lines. | Reproduced 1.0 / 0.3655 / 0.5. `--select-by rank` (the default) uses `tta_ap`. Validation logits are fp16 under CUDA autocast, so ties do occur, but on realistic logits the bias is about 1e-5 to 1e-4. |
| 7 | VALID | Medium (High) | none directly (BUG-0060 is related: split provenance only) | Needs its own CR: a schema change to calibration.json and a change from warning to refusing. Medium size. | Warn-and-apply confirmed. `flip_tta` is not enforced. `--temperature` is not validated. With the default paths, the warnings fire even on a correct workflow. |
| 13 | ALREADY TRACKED (BUG-0062), VALID-LATENT | Low (Medium) | BUG-0062; OPEN-ISSUES lines 199 and 202; PA-0030 | Carry on with the CR already planned in BUG-0062 §6. Add the auditor's points about shuffling and `-O` to that CR. | Mechanism reproduced. Every shipped builder follows the expected layout. |
| 14 | ALREADY TRACKED (BUG-0061), VALID-LATENT | Low (Medium) | BUG-0061; OPEN-ISSUES line 200; PA-0030 | Trivial fix already recommended in BUG-0061: check the header and raise. Also cover the case of an existing empty file. | Reproduced. `--metrics-csv` is off by default, and CR-0009 required a fresh file. |
| 15 | VALID-LATENT | Low (Medium) | none | Trivial fix in one function plus a BUG entry. Bundle it with a check on the sibling `fit_platt` (below). | Reproduced: ECE and MCE are both 0.0 on NaN. Only reachable if logits are non-finite. Sibling finding: NaN logits make `fit_platt` return (1.0, 0.0), so an identity calibration gets written. |
| 21 | VALID (the 15 m figure is correct) | Low (Medium) | none (same family as BUG-0009 / BUG-0094, PA-0007 / PA-0049) | Small CR, because the GeoTIFF/KMZ georeferencing changes. About 5 lines plus a test. | The emitted output-cell centre is 0.5 source pixel north-west of the pixel that training labels and that prediction masks and captures. |
| 22 | VALID (known in CHANGELOG, never logged as a BUG) | Low (Medium) | not in BUG_LOG; acknowledged in CHANGELOG.md:509-511 and model_handler.py:686-691 | Trivial fix (compile `model.logits` the way `fit` does) plus a BUG entry. About 5 lines. | The flag is a no-op: output is eager, so results stay correct, but the message "Compiling..." is misleading. No recorded predict run uses `--compile`. |

---

## #4 Average precision and tied scores

**Code.** `model_handler.py:78-90`:
```python
order = np.argsort(-scores, kind='mergesort')
y = labels[order]
tp = np.cumsum(y)
precision = tp / np.arange(1, len(y) + 1)
return float((precision * y).sum() / n_pos)
```
Precision is accumulated row by row in stable-sort order. Tied scores are never grouped, unlike `roc_auc` at lines 55-75, which does handle ties.

**Reproduction** (`probes/g3_ap.py`, using the real function): eight zero scores give **1.0** with labels `[1,1,1,1,0,0,0,0]` and **0.3654761904761905** with the labels reversed. A threshold-grouped reference AP gives **0.5** for both. sklearn is not installed, so the reference is a 10-line distinct-threshold implementation inside the probe. All three numbers match the audit.

**Does the order inside a tie favour positives?** Yes. `train.py:458-465` appends each region's validation positives before its negatives (`val_pos_df`, then `val_neg_df`), and the evaluation loader is not shuffled (`model_handler.py:1897` comment). Stable sorting therefore puts positives first within every tie. With three regions (ME, NH, VT, `regions.REGIONS`) the layout is pos/neg/pos/neg/pos/neg. A constant predictor on balanced 120/120/129 data then gets AP **0.714**, against a true value of 0.5, and a rank score of 0.607 (`probes/g3_ap_regions.py`).

**Are logits continuous or quantised?** They are quantised to fp16 on GPU. `evaluate()` runs `_pooled_logits` inside `torch.amp.autocast('cuda')` (`model_handler.py:1852-1854`). The head output and the flip average `0.5*(out[:b]+out[b:])` (`:416`) are fp16, and `.float()` is applied only afterwards (`:1867`). The TTA mean over the 4 rotations is then a float32 numpy `reshape(...).mean` (`:1893`). So ties do happen. Simulation (`probes/g3_ap_ties.py`): 738 to 2,952 points (CR-0009's validation set was 738 points, i.e. 2,952 samples ÷ 4, judging from the accuracy denominators in `evidence/CR-0009/retrain/metrics.csv`), per-view fp16 logits with AUC around 0.7, and labels ordered positives first. That gives 5 to 85 tied points. The AP bias has a mean of about **2.5e-5** and a maximum of about **1.6e-4**. For comparison, the AUC standard error quoted in train.py's help is about 0.006. `calibrate.collect_val_logits` (`calibrate.py:146`) does not use autocast, so its AP is float32 and close to tie-free.

**Does `--select-by rank` use AP?** Yes. `selection_score` (`model_handler.py:633-635`) computes `0.5*(tta_auc + tta_ap)`. `train.py:935` sets the default to `"rank"`, and the current recipe does not override it. So this metric chooses the checkpoint.

**Exposure.** The mechanism is real and runs every epoch. For a working model the inflation is negligible, and because it is almost constant from epoch to epoch it does not change which epoch is selected. It only becomes significant when a model collapses to (near-)constant fp16 logits. The project has seen that before (`model_handler.py:247-258`), but a collapsed run scores around 0.61 on rank, well below a trained model's 0.71, and it is already visible through `logit_std` and AUC = 0.5. Severity is Low, not High.

**Disposition.** This qualifies as a trivial fix: one function, same signature, and the only behaviour change is the defect itself. Compute precision at distinct thresholds, the same way `roc_auc` groups ties. Add a BUG entry, a permutation-invariance test and a constant-score test. Recurrence review should check PA-0030 / BUG-0056-type "metric depends on row order" cases. None were found in BUG_LOG.

## #7 Calibration mismatch: warned, then applied anyway

**Code.** In `predict.py:931-960`, scale, bias and prevalence are loaded and assigned first. The identity checks at `:961-982` come afterwards and only call `_say("[warn] ...")`. Neither path stops execution or resets the values. `calibrate.py:448` saves `flip_tta`, but nothing in predict.py reads it back (grep for `flip_tta` in predict.py finds only the CLI and scoring uses). `--temperature` (`predict.py:851, 933`) has no sign or finiteness check, so a negative T inverts the ranking. A loaded `scale` of 0 raises ZeroDivisionError; that is a crash, not a silent failure. A NaN scale gives a NaN map.

**Additional observation (strengthens the finding).** The default paths disagree. `train.py:588` defaults to `--save-path grouse_single_best.pth` (cwd), `calibrate.py:310` to `--model grouse_single_best.pth` (cwd), and `predict.py:794` to `--model data/models/grouse_single_best.pth`. When the defaults are used, the `model_path` warning therefore fires even when the calibration really does belong to the model. If the checkpoint is copied into `data/models/` after calibrating, `cp` gives the copy a newer mtime, so the mtime warning fires falsely too. Warnings that fire on a correct workflow can't tell a correct workflow from a wrong one.

**Calibration fits are not validated either.** `calibrate.py:381` refuses `a <= 0`. `fit_platt` cannot return NaN, though: NaN logits make it return the starting point `(1.0, 0.0)` (see #15), and that identity "calibration" is written to disk.

**Tracked?** BUG-0060 covers split provenance for `calibrate.py --model` (scenario 3) and does not cover predict-side identity binding. BUG-0021 covers config reconstruction. Nothing tracks warn-and-apply.

**Exposure.** Reachable. predict.py applies `data/calibration/calibration.json` automatically by default (`:839-843`). A fresh retrain that overwrites the checkpoint, followed by predict without re-running calibrate, is the obvious way to hit it. Scale is always positive, so ranking and `--style quantile` maps are unaffected. Absolute probabilities and the default `--style absolute` colouring are affected. Severity Medium, not High.

**Disposition.** A CR is needed because it changes the calibration.json schema (weight digest, `flip_tta`, features) and turns warnings into refusals. A finite/positive guard on loaded values and on `--temperature` could be a trivial fix by itself. Size: medium.

## #13 TTA grouping inferred from array length

**Code.** `model_handler.py:1888-1914` and `calibrate.py:157-162` group results by `len % tta_group == 0` and then a label `assert`. Reproduced: four distinct same-label points are merged into one value, 1.025 (`probes/g3_metrics_csv.py`). The audit's extra points hold. Shuffling within one class still passes the assert, `python -O` removes the assert, and `collect_val_logits` returns per-rotation logits when the length is not divisible by 4. **Already tracked as BUG-0062** (OPEN, latent; OPEN-ISSUES:199, :202; PA-0030). All shipped builders use `expand_rotations=True` with an unshuffled loader (`train.py:458-465`, `dataset.py:365`, rotation 0 first), so the current workflow does not reach it. VALID-LATENT, Low. Disposition: BUG-0062's planned CR, adding the shuffle and `-O` points.

An aside for that CR: the comment at `model_handler.py:1906-1911` says rotation maps the centre pixel to itself. For an even 64-pixel chip that is false, because pixel (32,32) maps to (31,32), (31,31) and (32,31). The code takes `[:, 0]` (rotation 0, the unrotated chip), so the value is still correct. Only the reasoning in the comment is wrong.

## #14 Metrics CSV schema drift

**Code.** `model_handler.py:1480-1490`. Reproduced with the real function: the output is `'auc,epoch\n0.8,1\n0.8,0.2,2\n'`. An existing empty file gets no header: `'0.8,1\n'`. **Already tracked as BUG-0061** (OPEN; OPEN-ISSUES:200; PA-0030 (b) already requires the check). `--metrics-csv` defaults to None (`train.py:637`). CR-0009 used it with a mandatory fresh file (CR-0009 review log A-R5-1). Within one run the key set is constant. VALID-LATENT, Low. Disposition: the trivial fix BUG-0061 already recommends, also covering the empty-file case (check `getsize`, not just `exists`).

## #15 Reliability on NaN reports ECE 0

**Code.** `calibrate.py:242-260`. Reproduced with the real function: `[NaN, NaN]` gives ECE 0.0, MCE 0.0, and 0 rows binned. With 10 % NaN, ECE drops from 0.0986 to 0.0870, with 900 of 1000 rows binned (`probes/g3_reliability.py`).

**Sibling found during verification (same input).** `fit_platt` (`calibrate.py:197-226`) given logits that include NaN gets f = NaN. `f_new <= f` is then always False, so it returns the start point **(1.0, 0.0)**, and that passes the `a <= 0` guard at `:381`. calibrate.py therefore writes an identity calibration together with an understated ECE. Nothing in calibrate.py checks for finite values (grep finds no `isfinite`).

**Exposure.** Needs non-finite logits. Continuous nodata reaches the model as NaN by design (`grouse_data.py:76-78`, the missing-mask path), so NaN logits would mean a model or embedding defect, and none has been observed. VALID-LATENT, Low. Not tracked. Disposition: a trivial fix (refuse non-finite or empty logits once, at the top of calibrate's main flow, or inside `reliability`/`fit_platt`) plus a BUG entry.

## #21 Output affine vs the scored centre pixel

**Code.** In `predict.py:349-350` and `:404-410`, the masked, scored and captured pixel is `cy, cx = y + IMG_SIZE // 2, x + IMG_SIZE // 2`, which is chip index 32. `predict.py:424-429` reads:
```python
ref.transform.c + (c_start + IMG_SIZE // 2 - 0.5 * stride) * ref.transform.a,
...
ref.transform.f + (r_start + IMG_SIZE // 2 - 0.5 * stride) * ref.transform.e)
```
The centre of output pixel (0,0) is therefore at source coordinate index `c_start + 32`. That is the top-left corner of source pixel 32, not its centre (`c_start + 32.5`).

**Reproduction** (`probes/g3_affine.py`, rasterio Affine with the expression copied from the code; 30 m north-up grid): the emitted centre is (960, -960) and pixel 32's centre is (975, -975). The offset is **15 m east and 15 m south of where the map puts it**, at strides 4, 8 and 16 alike. In other words, the map places each value 15 m north-west of the pixel it belongs to. The 15 m claim is correct.

**Which convention is right?** Training places each point inside source pixel `src.index(x, y)` and puts that pixel at chip index `half = n // 2` (`dataset.py:320-324`; with `pad` 0 on validation and no jitter, `read_size = 64`). The labelled point is therefore somewhere within pixel 32 of the north-up chip, so its expected position is 32.5. The D4 rotations seen in training are not north-up windows, so they don't change this. Prediction's mask (`ref_missing[cy, cx]`) and its centre-feature capture use the same pixel 32, so **training sampling, masking and feature capture all agree with one another**. Only the output georeference disagrees. (`models._center_vector` uses the central 2×2 block, rows and columns 31-32, whose centroid is 32.0. It is identical in training and prediction, so it is not a mismatch.) BUG-0009's fix (`docs/quality/bugs/BUG-0009-*.md` lines 28-30) treated the index `r_start + IMG_SIZE//2` as a centre coordinate. That is how the residual half source pixel survived.

**Rotation/shear claim.** True in principle: `b` and `d` are copied without scaling, and the translation ignores them. It is latent, because the region templates are north-up (b = d = 0).

**Exposure.** Every map has this offset. But 15 m is 1/8 of a 120 m output cell at the default stride 4, the scored pixel still lies inside its output cell (the cell covers source indices 30-34), and 15 m is half the resolution of the input rasters. This is a systematic georeferencing error of the same family as BUG-0009 and BUG-0094 (PA-0007, and PA-0049 pending with CR-0034). Not tracked. Severity Low. Disposition: a small CR, because the output GeoTIFF/KMZ georeferencing changes. Add `+ 0.5` in both terms (or use the composed Affine the audit proposes), with a test that the centre of output pixel (0,0) equals `ref * (c_start+32.5, r_start+32.5)`. Recurrence review should name PA-0007 as too narrow: it covers centre-versus-corner on the output grid, but not index-versus-centre on the source grid.

## #22 `--compile` in predict.py

**Code.** `predict.py:314-316` runs `model = torch.compile(model)`. `d4_tta_logits` (`models.py:886-889`) calls `model.logits(...)`. On an `OptimizedModule`, attribute access falls through to the original module, so `logits` runs eagerly, and `forward` (`models.py:1197`) is never called, so nothing is ever compiled. Training does this correctly: `model_handler.py:724` compiles `self.model.logits`. Not run here (no torch); based on reading the code and on torch's documented behaviour.

**Known and unlogged.** CHANGELOG.md:509-511 says: "which is why predict.py's `--compile` was a no-op". `model_handler.py:686-691` says the same. predict.py was never fixed, and there is no BUG entry. That is itself a gap under CLAUDE.md §2.

**Exposure.** Opt-in. None of the predict.py commands recorded under `docs/quality/evidence` use `--compile`. Output is correct because it runs eagerly; only the expected speed-up is missing and the "Compiling model graph" message is wrong. Severity Low. Disposition: a trivial fix (pass a compiled `model.logits` into `d4_tta_logits`, or bind `model.logits = torch.compile(model.logits)` on the module) plus a BUG entry noting that the defect was recorded in CHANGELOG without a bug log entry.
