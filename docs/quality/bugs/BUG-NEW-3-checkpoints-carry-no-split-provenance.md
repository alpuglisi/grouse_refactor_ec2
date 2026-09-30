# BUG-NEW-3: Checkpoints carry no split provenance, so a model fitted to today's validation rows can re-enter training and calibration

> Placeholder id: the lead assigns the real id (≥ BUG-0050) and renames
> this file. Found by the CR-0015 deliverable 2 producer sweep for
> BUG-0042 / PA-0029.

## 1. Description
Four entry points take an existing checkpoint and use it to produce
training targets, initial weights or a calibration fit. None of them
checks which train/val split that checkpoint was trained on:
- `train.py --distill-from`: the teachers' soft labels become training
  targets for every training row.
- `train.py --init-from`: `load_backbone` accepts any GrouseResNet-keyed
  state dict, supervised ones included.
- `train.py --resume`: checks geometry only.
- `calibrate.py --model`: fits Platt scaling on the validation rows
  using that checkpoint's logits.

The checkpoint config holds architecture fields only. It stores no
digest of `block_assignments.csv` or `split_manifest.json`.

## 2. Where encountered
Sweep for CR-0015 deliverable 2 (BUG-0042), 2026-09-30:
- `train.py:256-260`, `:201-236` (`_score_teacher_probs`), `:921-991`
  (`--distill-from` loading);
- `train.py:1141-1147` → `model_handler.py:640-658` (`load_backbone`);
- `model_handler.py:1092-1111` (`--resume`);
- `calibrate.py:310` → `:356-385`;
- `model_handler.py:464-510` (`_wrap_checkpoint`: the config keys).

## 3. What it caused to fail
Measured by the sweep with a read-only CSV comparison against
`/home/ec2-user/grouse_backup/CR-0012/`:
- 1,009 of 1,246 (81.0 %) of today's validation positives were
  **training** rows under the pre-CR-0012 split;
- 604 of 1,246 (48.5 %) of today's validation negatives were training
  rows.

Every checkpoint on disk predates CR-0012. Which split each one used
cannot be determined, and that is the defect. Scenarios that run today
without any refusal:
1. `train.py --distill-from gap3.pth bce.pth` trains a student on soft
   labels from teachers fitted to most of today's validation positives.
   The student's validation metrics and its `select_by` checkpoint
   choice are inflated by leaked labels.
2. `--init-from gap3.pth` has the same leak, through the initial
   weights.
3. `calibrate.py --model gap3.pth` fits Platt on points the model
   mostly trained on. It then writes `data/calibration/calibration.json`,
   which every `predict.py` map applies.
4. `symptom_check.py`'s per-split AUC for a pre-CR-0012 checkpoint, on
   today's files, is mostly a training-set AUC.

CR-0009's pinned retrain uses none of these flags and calibrates its own
new checkpoint, so it is not affected as written.

## 4. What the defect was
The checkpoint config is built in `model_handler._wrap_checkpoint`
(`:464-510`). Its keys are architecture only (`pool`, `center_skip`,
`features`, `keep_early_resolution`, `early_attn`, …, `missing_mask`),
with no split field. `load_backbone` states the acceptance explicitly:
```python
    def load_backbone(self, path):
        """Initialize matching weights from a pretraining checkpoint -
        pretrain.py's self-supervised SimSiam backbone, or any
        GrouseResNet-keyed state dict. ...
```
The only checkpoint gate on these paths,
`grouse_data.refuse_legacy_checkpoint_on_repaired`, tests
`missing_mask` only.

## 5. Root cause analysis (Five Whys)
1. *Why can a leaked checkpoint re-enter training or calibration?* No
   entry point compares the checkpoint's split with the current one.
2. *Why not?* The checkpoint does not record its split.
3. *Why not?* When checkpoints were designed, the split was assumed
   fixed. BUG-0027 and CR-0012 then changed it, and said in prose that
   "the split change invalidates every checkpoint" (BUG-0027 §6;
   CR-0012 Impact). Nothing turned that into a check.
4. *Why did CR-0012/CR-0013's gates not cover it?* They gate the split
   *files* and the data-reading path (`standing_checks`). They say
   nothing about the provenance of a *model* used as a source of
   training targets or weights.
5. *Why is that a holdout issue?* A teacher's soft label or a
   checkpoint's weights are rows' worth of information produced at run
   time. They are a producer of training signal, and they bypass the
   files (PA-0029).

**Root cause:** model artefacts that feed training or calibration carry
no record of the holdout they were fitted under. So the holdout is not
enforced on run-time producers of training signal derived from them.

## 6. Corrective action
**None yet — OPEN. Owner: the lead**, via a new CR. This touches the
checkpoint format and CLI behaviour, so it is not a trivial fix. The
sweep's suggested mechanism:
- write a split digest (sha256 of `block_assignments.csv` or of the
  manifest's outputs) into the checkpoint config;
- make `--distill-from`, `--init-from` (for supervised checkpoints),
  `--resume` and `calibrate.py` refuse on a mismatch or a missing
  digest;
- keep label-free SSL checkpoints (`pretrain.py`) exempt.

It does not block CR-0009.

## 7. Recurrence review
- **BUG-0027 / PA-0018 and BUG-0042 / PA-0029:** the same guarantee
  (spatial holdout) is bypassed by a producer that the file gates cannot
  see. This was found by PA-0029's own sweep, so it is a sweep finding.
- **BUG-0010 / PA-0008** (the checkpoint config must be validated on
  load): that rule covers architecture. This bug is its data-provenance
  analogue, which PA-0008 does not name.
- **BUG-0021** (a parallel config check that is not shared): unrelated
  mechanism.

## 8. Preventive action
Covered by **PA-0029** (extends PA-0018: every producer of training rows
or training signal is constrained by the holdout and gated). No new PA.
The lead may decide PA-0008 should also name split provenance when the
fixing CR is written.
