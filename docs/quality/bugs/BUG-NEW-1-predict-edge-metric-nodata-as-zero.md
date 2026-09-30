# BUG-NEW-1: `predict.py`'s Edge contrast metric reads nodata as 0

> Placeholder id: the lead assigns the real id (≥ BUG-0050) and renames
> this file. Found by the CR-0015 deliverable 4 PA-0006 re-sweep (see
> BUG-0032 §8).

## 1. Description
When a TensorBoard writer and edge-capture features are given,
`predict.py` computes a per-window "edge" magnitude:
- for each continuous feature, the mean absolute finite difference;
- for each categorical feature, the rate of class change.

The continuous path runs `torch.nan_to_num` first, so nodata (NaN)
becomes `0.0`, a legitimate scaled reading. The step from a real value
to that 0 is counted as gradient. The categorical path counts a
`MISSING_CODE`-to-class boundary as a class change.

## 2. Where encountered
`predict.py:376-380` (continuous) and `:370-374` (categorical), inside
the strip loop. The per-cell values feed `edge_maps`, which are logged
by `_tb_log_continuous_correlation(..., tag_prefix="Edge")`
(`predict.py:1086-1088`). Found by manual read in the CR-0015
deliverable 4 sweep. It is out of L1's reach (`nan_to_num` with its
default).

## 3. What it caused to fail
The TensorBoard `Edge/pearson_r/<feature>` scalar and its binned plot
are biased wherever windows are partly nodata. That happens at the
Canadian border, at the ocean, and at the tsd/TreeMap/tcc coverage
edges after the CR-0010 repair. Such windows are common because a
window is kept whenever its centre pixel is valid (`predict.py:347`).

Heatmaps, calibration and training are **not** affected. It is a
diagnostic-only defect. Severity LOW.

## 4. What the defect was
```python
                for f, idx in edge_cont_capture.items():
                    ch = torch.nan_to_num(t_cont[:, idx])
                    dx = (ch[:, :, 1:] - ch[:, :, :-1]).abs().mean(dim=(1, 2))
                    dy = (ch[:, 1:, :] - ch[:, :-1, :]).abs().mean(dim=(1, 2))
```
and, for categorical channels:
```python
                    neq_x = (ch[:, :, 1:] != ch[:, :, :-1]).float().mean(
                        dim=(1, 2))
```
where `ch` holds `MISSING_CODE` at nodata.

## 5. Root cause analysis (Five Whys)
1. *Why is the metric biased at coverage edges?* Pixel pairs with a
   nodata member are counted as real differences.
2. *Why?* The continuous channel's NaN is replaced by 0 before
   differencing, and the categorical channel's `MISSING_CODE` compares
   unequal to any class.
3. *Why was NaN replaced?* `abs().mean()` over NaN gives NaN.
   `nan_to_num` was the quick way to get a finite number, using its
   default `nan=0.0`.
4. *Why is 0 wrong here?* 0 is a legitimate scaled reading for tcc,
   road_dist, tsd and TreeMap. Nodata must be excluded from the pairs,
   not assigned a value.
5. *Why wasn't it caught?* This diagnostic was outside every earlier
   PA-0006 sweep's file or layer scope (BUG-0032 §7), and L1 cannot see
   a default-argument 0.

**Root cause:** a nodata value was converted to the legitimate value 0
(PA-0006's mechanism) instead of being excluded by a validity mask.

## 6. Corrective action
**None yet — OPEN.** The fix is confined to one function: compute the
differences only over pairs where both pixels are finite (continuous)
or neither is `MISSING_CODE` (categorical), and average over valid
pairs. **Owner: the lead**, as a trivial-fix candidate (`CLAUDE.md`
project notes: one function, no API change). Not done under CR-0015,
whose scope is the sampler.

## 7. Recurrence review
Same mechanism as BUG-0008, BUG-0017, BUG-0036 and BUG-0032 (PA-0006).
It was found by the PA-0006/PA-0028 re-sweep itself, so it is a sweep
finding, not a failure of the rule being swept. The prior-PA failure
analysis for PA-0006 (sweeps scoped by file, not mechanism) is in
BUG-0032 §7, and it applies unchanged.

## 8. Preventive action
Covered by **PA-0028** (extends PA-0006), whose sweep found it. No new
PA. L1 cannot see this form (`nan_to_num` default). PA-0028 therefore
keeps the manual read of `nan_to_num`, `fill_value=0` and integer-cast
forms as part of every sweep.
