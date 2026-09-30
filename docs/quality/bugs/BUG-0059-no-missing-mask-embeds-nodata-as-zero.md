# BUG-0059: With `missing_mask=False`, nodata is embedded as class/value 0, and `fdist` uses 0 as a real code

> Id allocated by the lead (2026-09-30); filed as a placeholder by the
> CR-0015 implementer. Found by the CR-0015 deliverable 4 PA-0006 re-sweep.

## 1. Description
`GrouseResNet.embed` handles nodata in two ways, depending on
`missing_mask`:
- **`missing_mask=True`** (the default in `train.py` and `pretrain.py`):
  a validity channel says which zeros are absent.
- **`missing_mask=False`** (legacy checkpoints, or
  `train.py --no-missing-mask`): no validity channel is added.
  - A categorical `MISSING_CODE` (-32768) is clamped to embedding row 0.
  - A continuous NaN is filled with 0.0.

For `fdist`, code 0 is a real reading in about 92–96 % of in-coverage
pixels (sweep probe: ME 2022, 9,219,880 of 9,964,042 valid pixels). In
that mode, fdist nodata and fdist 0 are the same input. So is any
continuous nodata and a real 0 (0 % canopy, on a road).

## 2. Where encountered
- `models.py`, `GrouseResNet.embed`: `idx = torch.clamp(codes, 0, vocab
  - 1)` without the `missing_mask` branch, and
  `parts.append(cont_x.masked_fill(nan, 0.0))`.
- The guard `grouse_data.refuse_legacy_checkpoint_on_repaired`
  (`grouse_data.py:232-245`) only fires on CR-0010-repaired rasters.
- `train.py --missing-mask` is a `BooleanOptionalAction` (`train.py:707`),
  so `--no-missing-mask` still trains such a model.
- Found by manual read in the CR-0015 deliverable 4 sweep.

## 3. What it caused to fail
- **Legacy (pre-validity-channel) checkpoints:** where they read `fdist`
  nodata (outside LANDFIRE coverage, e.g. the Canadian parts of the
  region boxes), they see it as "fdist 0". That is the dominant real
  code, so nothing flags it. The same holds for continuous nodata read
  as 0.
- **`--no-missing-mask` training:** trains such a model today with no
  refusal.
- **Not affected:** CR-0009's pinned retrain (default
  `--missing-mask`), and every `missing_mask=True` checkpoint.
- **Impact:** latent. It applies only to opt-in or legacy
  configurations.

## 4. What the defect was
`models.py`, `embed`:
```python
            idx = torch.clamp(codes, 0, vocab - 1)
            if self.missing_mask:
                ...
                miss = (codes == MISSING_CODE) | (codes >= vocab)
                idx = idx.masked_fill(miss, 0)
                valid.append(~miss)
            e = self.embeddings[name](idx).permute(0, 3, 1, 2)
...
            nan = torch.isnan(cont_x)
            parts.append(cont_x.masked_fill(nan, 0.0))
            if self.missing_mask:
                valid.extend((~nan).unbind(1))
```
The docstring states the behaviour ("to the embedding / stem as 0,
exactly as before; missing_mask adds the channels that say which 0s
were really absent"). Without the mask, nothing says which zeros were
absent.

## 5. Root cause analysis (Five Whys)
1. *Why can a `missing_mask=False` model not tell fdist nodata from
   fdist 0?* Both reach it as embedding row 0.
2. *Why row 0?* `MISSING_CODE` is clamped into the vocabulary, and
   row 0 is also the index of the real code 0.
3. *Why is that mode still reachable?* It is kept so that legacy
   checkpoints load, and `--no-missing-mask` is still a training flag.
4. *Why doesn't the existing guard catch it?* The guard was scoped to
   the CR-0010-repaired rasters (tsd/TreeMap/tcc), where the conflation
   was first noticed. fdist's own nodata was not considered.
5. *Why wasn't fdist considered?* BUG-0017's open question ("is 0 ever
   a real class?") was never answered with data. The sweep's probe
   answers it: yes, for fdist.

**Root cause:** in the legacy/opt-out embedding mode, nodata is mapped
onto the representation of a legitimate 0 (PA-0006's mechanism). The
guard that refuses the mode is scoped to the repaired rasters, not to
every feature where 0 is real.

## 6. Corrective action
**None yet — OPEN. Owner: the lead**, to decide in a CR. The options
are:
- refuse `--no-missing-mask` for training;
- widen `refuse_legacy_checkpoint_on_repaired` to any input where a
  `missing_mask=False` model would read nodata (fdist and continuous
  features);
- or record an accepted risk for legacy checkpoints only.

This touches a CLI flag, so it is not a trivial fix. CR-0009's
retrained checkpoint uses validity channels, so this does not block it.

## 7. Recurrence review
- It is the same mechanism as BUG-0008, BUG-0017, BUG-0036 and BUG-0032
  (PA-0006).
- It is the residual of **BUG-0017**. `51a4ad0` added `MISSING_CODE`
  and `missing_mask`, which fixed BUG-0017 for the default
  configuration, but the opt-out path keeps the conflation. BUG-0017
  was left open "pending domain confirmation", so no one checked
  whether the fix covered every mode.
- The prior-PA failure analysis for PA-0006 is in BUG-0032 §7: sweeps
  were scoped by file, and the rule was not enforced.

## 8. Preventive action
Covered by **PA-0028** (extends PA-0006), whose sweep found it. No new
PA. L1 cannot see this form, because the 0 comes through `clamp` and
`masked_fill`, not a literal comparison next to a nodata name.
