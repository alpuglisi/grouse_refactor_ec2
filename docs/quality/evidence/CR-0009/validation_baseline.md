# CR-0009 deliverable 8 — new validation baseline (2026-09-30)

Model: `grouse_cr0009.pth` (sha256 `b2570c31…`), selected epoch 3 of 10 by
`--select-by rank`. Data: CR-0012 pooled global block split and pooled
negatives, acceptance record `66d63e1d…` (18/18 CR-0013 gates). Validation
set: 8,856 samples (4 D4 TTA copies per record); train 35,252.

| metric (selected epoch 3) | value |
|---|---|
| TTA AUC | 0.7783 |
| TTA AP | 0.6851 |
| rank = mean(TTA AUC, TTA AP) | 0.7317 |
| AUC / AP (no TTA) | 0.7770 / 0.6830 |
| val accuracy / tuned-threshold accuracy | 68.43 % / 68.77 % |
| strict accuracy (hedged = wrong) | 27.51 % |
| val loss (AN-full) | 0.5726 |
| train accuracy | 75.10 % |

Calibration (`calibrate.py`, `docs/quality/evidence/CR-0009/calibration/`):
scale 1.2035, bias −0.5154; ECE 0.0323 (cross-fitted 5-fold 0.0294),
MCE 0.1109, Brier 0.1890, NLL 0.5499; ranking preserved (AUC 0.778310
before and after). Reliability curve: `calibration/reliability.{csv,png}`.
Validation prevalence 0.437 positive.

Per-epoch values for all 10 epochs: `retrain/metrics.csv`.

**Not comparable to any pre-CR number.** Every earlier validation metric
(~0.82 AUC, ~0.79 AP, 0.811 best rank; also the 0.8858 / 0.8744 figures in
`grouse_model_results_summary.md`) was measured on a split whose train and
validation records shared 3 km blocks (BUG-0027; CR-0012) and on different
negatives. This number is lower by construction and is not a regression
signal (CR-0009 § Impact, § Risk rollback).

**BUG-0034 (open):** the year-gap filter drops about 23.6 % of positives
and 0 % of negatives, so raster vintage partly predicts the label. This
baseline inherits that; BUG-0034's fix will change the training set and
require a new baseline.

**BUG-0050 (open, CR-0017):** 12 of 6,232 negatives lie within 300 m of the
Canadian border without a cross-border presence check. This baseline was
trained and validated on those negatives.
