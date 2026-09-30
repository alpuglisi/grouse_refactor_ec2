# Grouse Habitat Model — Training Results Summary

Compiled for handoff to a tuning agent. Covers all architecture/loss
configurations and training runs discussed to date, with per-epoch data
where available. All metrics are per-POINT (4 stored rotations averaged
as TTA unless noted), on the ME+NH+VT val set, from `train.py` /
`model_handler.py`.

## Project context

- Task: ruffed grouse habitat suitability, presence-only positives +
  generated/background negatives, CNN patch classifier (`GrouseResNet`)
  on 64x64 (1.9km at 30m) LANDFIRE-derived raster patches (EVT, EVH,
  EVC, SClass + others dynamically discovered from `landfire_data/`).
- Train/val split: spatial block-split (leakage-safe), separate from
  the retired 4x4 grid re-split.
- Deployment use case: ranking candidate habitat (not just binary
  classification) — AP and AUC are the metrics that matter more than
  raw threshold accuracy.
- Selection metric: `--select-by rank` (mean of TTA AUC and TTA AP) is
  now the default, replacing plain AUC, specifically because AUC-only
  selection kept saving epochs 12-30 in an earlier run for a marginal
  AUC gain while AP fell and val loss rose 38%.

## Baseline results (pre-AN-full, from train.py docstring)

Original focal-loss recipe, progressively improved, single model
unless noted:

| Configuration | AUC | AP | Accuracy | Val loss |
|---|---|---|---|---|
| Original recipe (`--pool mean --no-center-skip --no-augment --no-flip-tta --ema 0 --dropout 0 --label-smoothing 0 --sched warm_restarts --select-by loss`) | 0.8653 | 0.8249 | 79.21% | 0.335 (rising) |
| + center-skip, attn pool, regularization (single model) | **0.8858** | **0.8744** | 80.86% | 0.061 (stable) |
| + 4-member ensemble (diverse pooling/regularization per member) | 0.8975 | 0.8900 | 81.80% | — |

**0.8858 AUC / 0.8744 AP is the relevant single-model baseline** for
judging new single-model AN-full/dual-branch runs. The 0.8975 ensemble
figure is not apples-to-apples with any single-model run below — no
ensemble has been trained with AN-full or dual-branch yet.

## Loss function: L_AN-full (Cole et al., "full assume-negative")

Implemented in `model_handler.py` (`ANFullLoss`), selected via
`--loss an_full`. Lambda-weighted BCE where every negative (curated +
random background) is assumed a true negative; no focal phase
(`--warmup-epochs`/`--focal-gamma` ignored under this loss).

- `--an-pos-weight` / `--an-lambda`: lambda, the positive-term weight.
  Auto-selected when not given explicitly:
  - **1.0** under default stratified batching (batches already ~50/50,
    so no compensation needed) — this was the effective lambda in both
    runs below.
  - dataset neg:pos ratio if `--batch-pos-frac -1` (stratification
    disabled).
  - `--pos-neg-ratio` value if given (also maps to focal's alpha for
    the `focal` loss: alpha = R/(1+R)).
- `--an-background N`: adds N*positive_count random background
  assumed-negatives to training only (unbuffered from known
  positives — label noise is intentional, absorbed by lambda
  upweighting per Cole et al.'s design).
- `--max-train-year-gap`: excludes training records whose sighting
  year has no raster within N years for any feature (default 2;
  validation never filtered).

## Architecture options relevant to recent runs

- `--early-attn` + `--keep-early-resolution`: self-attention block at
  full 32x32 token resolution before downsampling, vs. default
  post-downsample attention pooling only.
- `--dual-branch {off,unet,dilated}`: second, resolution-preserving
  branch alongside the ResNet trunk (U-Net-lite w/ dilated bottleneck,
  or pure ASPP-style dilated stack), fused via zero-init head.
- `--init-from`: loads a self-supervised backbone from `pretrain.py`
  (SimSiam-style) instead of/alongside ImageNet init. Not used in any
  run below.
- Divergence guard (`--divergence-patience`, `--on-divergence`): flags
  N consecutive epochs of strict-accuracy-up while AUC-and-AP-both-down.
  All runs below used default `warn` mode (log only, continue
  training).

---

## Run A: 180-epoch AN-full, default architecture

**Command (reconstructed core flags):** `--loss an_full` (lambda
auto=1.0, stratified batching default), no `--dual-branch`, no
`--early-attn`, default pooling/regularization. **180 epochs
scheduled; log data available through epoch 20 (unfinished/cut off,
still improving).**

| Epoch | AN-full Loss | Val Acc | AUC | TTA AUC | AP | rank | tuned acc | strict% (hedged%) | train acc | logit std | Saved |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.6301 | 72.15% | 0.7927 | 0.7929 | 0.7673 | 0.7803 | 71.46% | 0.00 (100.0) | 71.8% | 0.281 | Y |
| 2 | 0.5843 | 72.94% | 0.8064 | 0.8067 | 0.7667 | 0.7870 | 73.15% | 7.02 (93.0) | 80.4% | 0.527 | Y |
| 3 | 0.5544 | 74.28% | 0.8007 | 0.8013 | 0.7523 | 0.7774 | 74.40% | 14.49 (85.4) | 82.4% | 0.752 | |
| 4 | 0.5065 | 77.00% | 0.8316 | 0.8332 | 0.7908 | 0.8131 | 77.30% | 25.48 (73.0) | 83.5% | 1.087 | Y |
| 5 | 0.4745 | 77.71% | 0.8466 | 0.8495 | 0.8153 | 0.8342 | 78.15% | 39.40 (57.2) | 84.5% | 1.467 | Y |
| 6 | 0.4688 | 77.04% | 0.8481 | **0.8523** | 0.8213 | 0.8392 | 76.77% | 46.05 (49.0) | 85.7% | 1.758 | Y |
| 7 | 0.4756 | 76.08% | 0.8454 | 0.8509 | 0.8212 | 0.8392 | 77.18% | 49.11 (44.7) | 86.8% | 1.937 | |
| 8 | 0.4857 | 75.69% | 0.8421 | 0.8487 | 0.8196 | 0.8381 | 75.71% | 50.83 (42.2) | 87.4% | 2.053 | |
| 9 | 0.4943 | 75.27% | 0.8398 | 0.8476 | 0.8188 | 0.8378 | 75.62% | 51.55 (41.1) | 88.0% | 2.139 | |
| **[DIVERGENCE flagged epochs 7-9: strict-acc rising while AUC & AP both falling 3 straight epochs — warn mode, training continued]** | | | | | | | | | | | |
| 10 | 0.5004 | 74.98% | 0.8385 | 0.8472 | 0.8184 | 0.8378 | 75.52% | 52.29 (40.0) | 88.4% | 2.199 | |
| 11 | 0.4962 | 74.91% | 0.8394 | 0.8479 | 0.8186 | 0.8385 | 76.08% | 51.80 (40.5) | 86.6% | 2.178 | |
| 12 | 0.4979 | 74.91% | 0.8406 | 0.8491 | 0.8203 | 0.8401 | 76.33% | 51.89 (40.6) | 87.5% | 2.204 | |
| 13 | 0.4998 | 74.89% | 0.8416 | 0.8504 | 0.8216 | 0.8416 | 76.05% | 52.14 (39.8) | 88.3% | 2.259 | Y (recovery begins) |
| 14 | 0.5059 | 74.77% | 0.8406 | 0.8503 | 0.8200 | 0.8411 | 75.65% | 53.39 (38.1) | 89.1% | 2.316 | |
| 15 | 0.5102 | 75.02% | 0.8406 | 0.8513 | 0.8213 | 0.8428 | 75.90% | 54.45 (36.4) | 89.8% | 2.377 | Y |
| 16 | 0.5154 | 74.66% | 0.8410 | 0.8526 | 0.8222 | 0.8442 | 76.15% | 55.17 (35.2) | 90.4% | 2.421 | Y |
| 17 | 0.5219 | 74.57% | 0.8409 | 0.8535 | 0.8225 | 0.8451 | 76.24% | 55.98 (34.0) | 91.6% | 2.484 | |
| 18 | 0.5297 | 74.79% | 0.8414 | 0.8547 | 0.8230 | 0.8463 | 75.46% | 56.95 (32.8) | 92.1% | 2.553 | Y |
| 19 | 0.5385 | 74.67% | 0.8407 | 0.8550 | 0.8230 | 0.8470 | 74.99% | 57.73 (31.5) | 92.7% | 2.608 | |
| 20 | 0.5473 | 74.48% | 0.8403 | **0.8555** | **0.8237** | **0.8480** | 75.59% | 58.26 (30.1) | 93.5% | 2.663 | Y |

**Notes:** raw "Val Accuracy" drifts DOWN from epoch 5 onward (77.71%
-> 74.48%) even as AUC/AP/rank keep improving — a fixed p=0.5 threshold
losing calibration as logit std grows, not a real stall; `tuned acc`
(threshold re-derived each epoch from train data) plateaus around
75-78% instead. Last logged state (epoch 20/180) still trending up on
every ranking metric; run not finished.

---

## Run B: 30-epoch AN-full, dual-branch UNET + early-attn

**Command:** `python train.py --keep-early-resolution --early-attn
--embed-dropout 0.05 --dropout 0.3 --batch-size 128 --lr-scaling none
--weight-decay 1e-3 --loss an_full --an-background 1.0
--dual-branch unet`

Deviations from Run A: adds `--dual-branch unet`, `--early-attn` +
`--keep-early-resolution`, `--an-background 1.0` (background
assumed-negatives), larger batch (128 vs default 32) with LR scaling
explicitly disabled (full `lr=3e-4` at 4x reference batch size, a
deliberate deviation from the sqrt-scaling recipe), higher
dropout/weight-decay. **30 epochs scheduled; best checkpoint epoch 16,
plateaued, run allowed to continue confirming no further improvement.**

| Epoch | AN-full Loss | Val Acc | AUC | TTA AUC | AP | rank | tuned acc | strict% (hedged%) | train acc | logit std | Saved |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.6090 | 73.42% | 0.8001 | 0.8003 | 0.7707 | 0.7857 | 73.81% | 0.00 (100.0) | 76.8% | 0.371 | Y |
| 2 | 0.5563 | 73.80% | 0.8019 | 0.8021 | 0.7644 | 0.7836 | 74.24% | 13.55 (86.4) | 81.8% | 0.710 | |
| 3 | 0.5176 | 75.41% | 0.8161 | 0.8168 | 0.7804 | 0.7990 | 75.15% | 30.97 (66.0) | 84.2% | 1.066 | Y |
| 4 | 0.4866 | 77.22% | 0.8384 | 0.8399 | 0.8106 | 0.8263 | 77.33% | 46.83 (46.7) | 85.8% | 1.500 | Y |
| 5 | 0.4734 | 77.94% | 0.8480 | 0.8503 | 0.8232 | 0.8380 | 78.36% | 53.48 (38.1) | 87.3% | 1.855 | Y |
| 6 | 0.4651 | 78.02% | 0.8527 | 0.8564 | 0.8302 | 0.8454 | 78.55% | 56.10 (35.9) | 88.9% | 2.121 | Y |
| 7 | 0.4702 | 77.46% | 0.8525 | 0.8579 | 0.8327 | 0.8482 | 78.05% | 58.16 (33.3) | 90.2% | 2.333 | Y |
| 8 | 0.4784 | 77.51% | 0.8528 | 0.8596 | 0.8340 | 0.8506 | 78.05% | 60.54 (30.0) | 91.4% | 2.514 | Y |
| 9 | 0.4854 | 77.47% | 0.8535 | 0.8614 | 0.8353 | 0.8526 | 77.99% | 61.69 (28.4) | 92.6% | 2.666 | Y |
| 10 | 0.4932 | 77.49% | 0.8542 | 0.8632 | 0.8364 | 0.8548 | 77.90% | 62.60 (27.2) | 93.3% | 2.779 | Y |
| 11 | 0.5029 | 77.49% | 0.8542 | 0.8642 | 0.8380 | 0.8565 | 77.77% | 63.75 (25.3) | 94.2% | 2.888 | Y |
| 12 | 0.5105 | 77.48% | 0.8541 | 0.8647 | 0.8380 | 0.8571 | 77.46% | 64.69 (23.9) | 94.8% | 2.955 | |
| 13 | 0.5190 | 77.21% | 0.8542 | 0.8657 | 0.8390 | 0.8584 | 77.71% | 64.66 (24.1) | 95.5% | 3.012 | Y |
| 14 | 0.5211 | 77.27% | 0.8555 | 0.8676 | 0.8418 | 0.8611 | 78.21% | 65.22 (23.3) | 96.0% | 3.049 | Y |
| 15 | 0.5258 | 77.36% | 0.8552 | 0.8678 | 0.8426 | 0.8618 | 78.18% | 66.16 (21.9) | 96.5% | 3.083 | |
| 16 | 0.5319 | 77.16% | 0.8544 | **0.8675** | **0.8432** | **0.8622** | 77.80% | 65.81 (22.1) | 96.6% | 3.101 | **Y — best checkpoint** |
| 17 | 0.5375 | 76.99% | 0.8535 | 0.8669 | 0.8428 | 0.8617 | 77.93% | 66.19 (21.3) | 97.1% | 3.124 | |
| 18 | 0.5403 | 76.89% | 0.8534 | 0.8671 | 0.8440 | 0.8628 | 77.71% | 66.41 (20.9) | 97.2% | 3.131 | (below min-delta) |
| 19 | 0.5444 | 76.85% | 0.8526 | 0.8665 | 0.8438 | 0.8624 | 77.68% | 66.34 (20.9) | 97.5% | 3.134 | |
| 20-30 | (not fully logged; plateau confirmed, no save beyond epoch 16) | | | | | | | | | | |

**Notes:** raw "Val Accuracy" plateaus ~77.5-78% from epoch 4-5 onward
while AUC/AP/rank kept climbing through epoch 16 (threshold-drift
pattern, confirmed independent by `tuned acc`). Logit std grows
steadily then levels off ~3.1-3.2. Plateau clearly onset ~epoch 14-16;
epochs 17-19 show AUC trending DOWN while AP/rank stay roughly flat —
model fully converged, train acc still climbing (97.5%+) with no
further val payoff.

---

## Run C: 30-epoch AN-full, dual-branch DILATED (ablation vs. Run B)

**Command:** identical to Run B except `--dual-branch dilated` instead
of `--dual-branch unet`. Direct ablation of the two `--dual-branch`
options with every other flag held constant.

**30 epochs scheduled. Run allowed to continue past its plateau to
confirm the ceiling; best checkpoint occurred at epoch 15, no
improvement through epoch 21 (run killed shortly after, epochs 22-30
not logged).**

| Epoch | AN-full Loss | Val Acc | AUC | TTA AUC | AP | rank | tuned acc | strict% (hedged%) | train acc | logit std | Saved |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.6049 | 73.49% | 0.8045 | 0.8046 | 0.7728 | 0.7888 | 73.59% | 0.03 (100.0) | 75.8% | 0.387 | Y |
| 2 | 0.5639 | 72.82% | 0.8192 | 0.8195 | 0.7877 | 0.8039 | 73.52% | 23.32 (72.3) | 81.8% | 0.768 | Y |
| 3 | 0.6273 | 70.61% | 0.8243 | 0.8252 | 0.7872 | 0.8067 | 70.28% | 53.92 (26.8) | 84.3% | 1.166 | Y |
| 4 | 0.6317 | 72.08% | 0.8409 | 0.8421 | 0.8085 | 0.8261 | 71.84% | 60.32 (20.4) | 85.8% | 1.629 | Y |
| **[transient rough patch: loss rose 2 straight epochs (3-4) alongside a Val Accuracy dip, even as AUC/AP/rank kept improving — resolved by epoch 5, not a real divergence]** | | | | | | | | | | | |
| 5 | 0.5777 | 75.05% | 0.8519 | 0.8539 | 0.8236 | 0.8400 | 75.52% | 62.44 (21.8) | 87.6% | 2.027 | Y |
| 6 | 0.5337 | 76.91% | 0.8579 | 0.8613 | 0.8333 | 0.8493 | 77.27% | 63.82 (22.6) | 89.1% | 2.331 | Y |
| 7 | 0.5149 | 77.73% | 0.8580 | 0.8627 | 0.8364 | 0.8524 | 77.86% | 64.16 (23.3) | 90.6% | 2.543 | Y |
| 8 | 0.5106 | 77.85% | 0.8576 | **0.8637** | 0.8385 | 0.8546 | 78.21% | 64.60 (23.7) | 91.8% | 2.711 | Y |
| 9 | 0.5141 | 77.81% | 0.8559 | 0.8630 | 0.8390 | 0.8550 | 78.24% | 64.97 (23.5) | 92.9% | 2.834 | |
| 10 | 0.5177 | 77.83% | 0.8552 | 0.8633 | 0.8397 | 0.8559 | 78.33% | 65.00 (23.2) | 94.1% | 2.941 | Y |
| 11 | 0.5239 | 77.58% | 0.8541 | 0.8630 | 0.8396 | 0.8561 | 78.15% | 65.38 (22.4) | 94.8% | 3.022 | |
| 12 | 0.5300 | 77.41% | 0.8537 | 0.8633 | 0.8400 | 0.8568 | 78.21% | 65.66 (21.9) | 95.5% | 3.092 | |
| 13 | 0.5354 | 77.25% | 0.8527 | 0.8629 | 0.8401 | 0.8570 | 77.83% | 65.56 (22.0) | 95.8% | 3.140 | Y |
| 14 | 0.5411 | 77.12% | 0.8518 | 0.8626 | 0.8409 | 0.8575 | 77.99% | 65.81 (21.6) | 96.5% | 3.165 | |
| 15 | 0.5443 | 77.07% | 0.8517 | **0.8628** | **0.8420** | **0.8585** | 77.71% | 65.66 (21.9) | 96.9% | 3.179 | **Y — best checkpoint** |
| 16 | 0.5484 | 76.84% | 0.8506 | 0.8621 | 0.8416 | 0.8581 | 77.83% | 65.91 (21.3) | 97.1% | 3.186 | |
| 17 | 0.5506 | 76.76% | 0.8506 | 0.8624 | 0.8424 | 0.8589 | 77.49% | 66.03 (21.2) | 97.4% | 3.194 | (below min-delta vs. ep.15) |
| 18 | 0.5551 | 76.68% | 0.8492 | 0.8613 | 0.8429 | 0.8588 | 77.68% | 65.78 (20.9) | 97.7% | 3.192 | |
| 19 | 0.5593 | 76.60% | 0.8480 | 0.8604 | 0.8421 | 0.8581 | 77.43% | 65.91 (20.7) | 97.9% | 3.190 | |
| 20 | 0.5609 | 76.47% | 0.8473 | 0.8602 | 0.8421 | 0.8582 | 77.49% | 65.72 (21.1) | 98.1% | 3.170 | |
| 21 | 0.5624 | 76.49% | 0.8468 | 0.8603 | 0.8421 | 0.8584 | 77.40% | 65.91 (20.9) | 98.1% | 3.164 | (train acc plateaus too) |

**Notes:** converged faster than Run B early on (matched Run B's
~epoch-11/12 rank score by epoch 8), but plateaued sooner and at a
LOWER ceiling. From epoch 15 onward AUC actively trends down
(0.8628->0.8602) while AP stays frozen (~0.842) and train accuracy
keeps climbing (96.9%->98.1%) then itself flattens — the model
exhausted transferable signal with no further val payoff. Run killed
at epoch 21 with no realistic prospect of the remaining 9 epochs
beating epoch 15.

## RESOLVED: dual-branch ablation (unet vs. dilated)

Direct, single-flag-changed comparison (all other Run B/C flags
identical):

| | `--dual-branch unet` (Run B, best=epoch 16) | `--dual-branch dilated` (Run C, best=epoch 15) |
|---|---|---|
| TTA AUC | **0.8675** | 0.8628 |
| AP | **0.8432** | 0.8420 |
| rank | **0.8622** | 0.8585 |
| Epochs to reach ~0.856 rank | ~11-12 | ~8 (faster) |
| Plateau onset | ~epoch 14 | ~epoch 12 (earlier) |

**Conclusion: `unet` reaches a higher final ceiling on every metric.**
`dilated` converges faster early but plateaus sooner and lower, and
had a rockier epoch 3-4 (transient loss increase + accuracy dip,
self-resolved). For further single-dual-branch-model tuning, `unet` is
the better default; `dilated`'s faster early convergence could still
be worth revisiting for a compute-constrained/fewer-epochs setting,
but not for chasing the best achievable single-model ceiling.

## Cross-run comparison

| | Baseline single-model (pre-AN-full) | Run A (epoch 20/180, unfinished, still climbing) | Run B best (`unet`, epoch 16/30, plateaued) | Run C best (`dilated`, epoch 15/30, plateaued) |
|---|---|---|---|---|
| AUC (TTA) | 0.8858 | 0.8555 (-0.0303) | 0.8675 (**-0.0183, best of the AN-full runs**) | 0.8628 (-0.0230) |
| AP | 0.8744 | 0.8237 (-0.0507) | 0.8432 (**-0.0312, best of the AN-full runs**) | 0.8420 (-0.0324) |
| rank | n/a (metric didn't exist for baseline) | 0.8480 | **0.8622 (best overall AN-full result)** | 0.8585 |

**No AN-full/dual-branch run has yet reached the pre-AN-full
single-model baseline (0.8858 AUC / 0.8744 AP).** Run B (`unet`) is the
best result obtained so far, converged/plateaued at epoch 16, still
~0.018 AUC / ~0.031 AP short of baseline. Run A (default architecture,
no dual-branch) was never run to convergence (stopped logging at
epoch 20/180, still improving) — its ceiling is unknown and it may
close more of the gap if resumed/finished. The dual-branch ablation
(unet vs. dilated) is now resolved (see above); AN-full vs. focal loss
and early-attn's individual contribution remain unisolated, since Run
B/C changed 5+ flags simultaneously versus Run A's single change.

## Open questions / suggested next steps for tuning

1. **Run A never finished** (stopped logging at epoch 20/180, still
   improving) — its true ceiling with the default architecture is
   unknown. Worth resuming/completing for a fair comparison against
   Run B's converged 0.8622 rank ceiling.
2. **RESOLVED: `--dual-branch unet` vs. `dilated`.** `unet` reaches a
   higher ceiling on every metric (0.8675 AUC / 0.8432 AP vs. 0.8628 /
   0.8420); `dilated` converges faster early but plateaus sooner and
   lower. Use `unet` as the default going forward. See "RESOLVED:
   dual-branch ablation" section above for full detail.
2a. **Still unisolated:** which of Run B's OTHER changes vs. Run A
   (early-attn+keep-early-resolution, an-background, batch-size 128 +
   lr-scaling none, dropout 0.3, weight-decay 1e-3) is driving its
   result — dual-branch is now known to be A factor, but not
   necessarily the only or largest one. Suggest single-flag-changed
   runs isolating early-attn and an-background specifically, since
   those are the next-largest architectural changes.
3. **Lambda (`--an-pos-weight`) has not been swept.** Both runs used
   the auto value of 1.0 (stratified batching default). Untested:
   values above/below 1.0, and whether disabling stratification
   (`--batch-pos-frac -1`) + relying on the auto neg:pos-ratio lambda
   changes convergence behavior.
4. **No ensemble has been trained on AN-full or dual-branch.** The only
   ensemble result (0.8975 AUC / 0.8900 AP) is from the old focal-loss
   recipe. If a single AN-full/dual-branch model reaches or beats
   0.8858/0.8744, ensembling 4 diverse members of it is the next
   natural comparison point against 0.8975/0.8900.
5. **`--max-train-year-gap`** (year-sanitization filtering) status in
   these runs is not confirmed — default is 2 years but no command
   line shown explicitly set it, so verify what was actually applied.
6. **`--init-from`** (self-supervised pretrained backbone) has not been
   used in any run described here — an available lever not yet tested.
7. Divergence guard fired once (Run A, epochs 7-9, warn mode) and the
   run recovered; Runs B and C never triggered it despite both
   eventually plateauing — worth testing `--on-divergence dampen` or
   `stop` behavior once a run actually diverges persistently, since
   only `warn` has been observed, and note the guard's definition
   (strict-up + AUC-down + AP-down together) doesn't catch a plateau
   or an AUC-only decline, which is what Runs B/C actually did.
