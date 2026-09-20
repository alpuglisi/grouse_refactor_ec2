# Briefing: optimize training loop speed, algorithmic/programmatic only

Handoff for an AI model being asked to speed up this project's training
loop. Written by a prior session with working knowledge of the code —
where it conflicts with the code itself, the code wins.

## The hard constraint, stated precisely

**Wall-clock/throughput only. Everything the model sees, learns from,
or does must be unchanged.** Concretely, off-limits:

- Any change to the **content** of what reaches the model: no
  resampling, smoothing, re-encoding, dtype-narrowing-with-precision-loss,
  or reduced resolution of the raster features (`dataset.py`'s patch
  reads, `models.py`'s `road_dist_encode`, feature scaling in
  `FEATURE_SPEC`).
- Any change to **which** features exist, **how many** augmented views
  are produced, or **what distribution** of data the model trains on
  (rotation/jitter augmentation must produce the same statistical
  behavior it does today — reordering or re-batching *how* those views
  get computed is fine; changing *what* they are is not).
- Any change to **model architecture or its numerical behavior** —
  layer count, channel widths, pooling mode, `--dual-branch`,
  `--early-attn`, embedding tables, dropout *values* (dynamic dropout's
  schedule logic must keep working exactly as today).
- Removal, disabling, or silent behavior change of **any existing CLI
  flag or feature** — `--dynamic-dropout`, `--ensemble`,
  `--distill-from`, `--resume`, `--init-from`, EMA, the strict
  objective, differential LR groups, checkpoint selection, TensorBoard
  instrumentation, the divergence guard. All of it must still work
  identically after the change, just faster.

In scope: how tensors move, when synchronization happens, how kernels
are dispatched/fused, how many redundant Python-level or device-level
operations occur per step, how data is staged from disk/CPU to GPU,
compiler/graph-capture opportunities, and precision/format choices that
are numerically equivalent (e.g. layout changes, not value changes).

**If a change could plausibly alter model outputs, training dynamics,
or which numbers get logged — even slightly — it's out of scope for
this task, not just risky.** Flag it as a *separate* proposal instead
of bundling it in.

## What's already been done — verify it's intact, don't re-propose it

This training loop (`GrouseModelHandler.fit()` in `model_handler.py`)
has already had real performance work done on it, with measured
justifications in the comments. A review that "discovers" these and
re-proposes them as new findings is wasting effort — check first:

- **NHWC (`channels_last`) memory format** on CUDA, both model and
  `cont_x` — comment cites a measured 7% of total GPU time going to
  `nchwToNhwc` transpose kernels before this, ~+12% throughput at
  batch ≥128 after.
- **TF32** enabled for the fp32 residue (`torch.backends.cuda.matmul.allow_tf32`,
  `cudnn.allow_tf32`) alongside AMP for the convolutions.
- **AMP** (`torch.amp.autocast('cuda')` + `GradScaler`) already wraps
  the forward/backward.
- **Fused AdamW** (`fused=(self.device.type == 'cuda')`) already used.
- **`cudnn.benchmark = True`** already set (fixed 64×64 input geometry
  makes this safe/beneficial).
- **Accumulate-on-device, sync-once-per-epoch** — training loss/accuracy
  are summed as GPU tensors and only pulled to CPU once per epoch,
  explicitly to avoid ~5,000 device syncs/epoch collapsing to 1. Any
  change that reads a `.item()`/`.cpu()` mid-loop without a very good
  reason reintroduces exactly this cost — check for this regression
  pattern in whatever you touch.
- **Gradient-norm/histogram diagnostics are gated** to every
  `--tb-log-every`-th step specifically *because* they resync the
  device — this is a deliberate, already-made tradeoff, not an
  oversight.
- **`self._clip_params`** (the list passed to `clip_grad_norm_`) is
  built once outside the loop, not rebuilt every step.
- **DataLoader**: `persistent_workers=True`, `pin_memory=True` (on
  CUDA), `prefetch_factor=4` already set for both train and val loaders
  (`_loader_extra`) — workers are kept alive across epochs specifically
  to avoid re-opening every raster file and rebuilding a `pyproj`
  transformer per epoch.
- **`ModelEMA`** already uses in-place `torch._foreach_*` ops, not a
  Python loop over parameters — but see the Invariants section below,
  this one has a sharp edge.
- **Patch caching** (`dataset.py`, `--cache-dir`) memmaps every point's
  raw patch stack to disk once, so a cached run never re-hits rasterio
  after the first epoch. **Check whether the actual runs being profiled
  are using `--cache-dir`** — if not, that's a configuration/usage gap
  to point out, not a code defect to fix.

## Concrete candidates already identified, worth investigating first

These were spotted by static reading, not measured — verify with real
profiling before claiming a win, per the Verification section.

1. **`torch.compile` is not used anywhere in the training path.**
   `predict.py` has a `--compile` flag for inference; `train.py` /
   `model_handler.py` have nothing equivalent. This is plausibly the
   single highest-leverage lever available. It needs care, though:
   dynamic dropout mutates `nn.Dropout.p` at runtime
   (`_set_dropout`), `--early-attn`/`--dual-branch`/`--pool` all
   branch the forward graph at construction time (fine, static per
   run), and there's a `self.training`-gated branch inside
   `embed()`. Confirm compiled behavior matches eager numerically
   (see Verification) and that recompilation isn't triggered every
   epoch by the dropout-`.p` mutation (it shouldn't be — `.p` is a
   Python float read at call time, not a graph constant — but verify,
   don't assume).

2. **Validation's flip-TTA does two sequential forward passes per
   batch instead of one batched call.** `_pooled_logits` (`model_handler.py:391-395`):
   ```python
   def _pooled_logits(self, cat_x, cont_x, tta=False):
       out = self.model.logits(cat_x, cont_x)
       if tta and self.flip_tta:
           out = 0.5 * (out + self.model.logits(cat_x.flip(-1), cont_x.flip(-1)))
       return out
   ```
   Called with `tta=True` only in the per-epoch validation pass
   (`model_handler.py:1699,1703`). Concatenating `cat_x`/`cont_x` with
   their flipped versions along the batch dimension, running **one**
   forward call at 2× batch size, then splitting and averaging, is
   mathematically identical to the current two-call version (same
   operations, same result) and should reduce kernel-launch/Python
   overhead for this pass. This runs once per validation batch, once
   per epoch — real but bounded; worth doing, not the top priority.

3. **`GrousePatchDataset.__getitem__` calls `self.df.iloc[i]` per
   item** (`dataset.py:276`, and the SSL variant at `dataset.py:396`).
   This runs inside every `DataLoader` worker, on every single sample
   access, for the entire dataset, every epoch. Pandas per-row `.iloc`
   access has known, real per-call overhead (index alignment, boxing
   into a `Series`) compared to indexing pre-extracted numpy arrays.
   Precomputing `longitude`/`latitude`/`year`/`label`/`weight` (and
   `soft_label` when present) as numpy arrays once in `__init__` and
   indexing those by position in `__getitem__` instead would return
   the exact same values, just faster to fetch. This is a good example
   of the *kind* of change that's in scope: same data, cheaper access
   path.

4. **`StratifiedBatchSampler`** (`dataset.py:404` on) builds its index
   batches up front in `__init__`/whatever `__iter__` does — worth
   checking whether batch-index generation is fully vectorized (numpy)
   or has a per-batch Python loop that could be pushed into vectorized
   form, given it runs every epoch for the whole training run.

5. **DataLoader `num_workers` tuning.** Not a code change, a
   measurement question: is the current `--workers` value actually
   saturating the data pipeline, or is training GPU-bound already
   (in which case more workers won't help and isn't worth
   recommending)? This is exactly why profiling comes first — see
   below.

## Do this before proposing anything: profile, don't guess

`train.py`'s own header comment already contains a measured
batch-size-vs-throughput table (`samp/s` at batch 32/64/128/256/512 on
an A10G) — that's the standard this project holds itself to. Any
proposed change should come with:

1. **A profile identifying where time actually goes** per training
   step — data loading wait, forward, backward, optimizer step,
   logging/sync overhead. `torch.profiler`, or even simple
   `torch.cuda.synchronize()`-bracketed manual timing around each
   phase, is enough. Without this, it's impossible to tell whether the
   bottleneck is GPU compute, host-side data loading, or
   synchronization stalls — and the right fix is completely different
   depending on which.
2. **Before/after wall-clock numbers** for whatever's changed (e.g.
   seconds/epoch, or samples/sec at a fixed batch size), not just "this
   should be faster."

## Verification requirement — correctness, not just speed

A change that makes training faster but silently changes what the
model learns is a regression this task explicitly forbids, even if
nobody asked for a metrics change. For anything touching numerics
(`torch.compile`, batching the TTA flip, any dtype/precision change):

- Run a short training run (few epochs, small data subset is fine) with
  and without the change, and confirm loss/accuracy/AUC trajectories
  match within floating-point noise — not just "it didn't crash."
- For the TTA-batching change specifically, compare the *exact* output
  tensor from the batched-concat version against the current two-call
  version on the same input, before touching the training loop, since
  that's independently and cheaply checkable.
- For `torch.compile`, compare compiled-vs-eager outputs on a fixed
  batch, and confirm no unexpected recompilation happens epoch to epoch
  once dynamic dropout starts moving `.p`.

## Environment note

This container has no real raster data, no trained checkpoints, and no
GPU with the real training pipeline attached — data is gitignored by
design (`ARCHITECTURE.md`) and lives only on the machine that actually
trains. **You will not be able to run the real training loop or get
real timing numbers here.** What you *can* do: write and statically
verify the changes, and exercise the affected code paths against
synthetic data to prove they don't crash and produce numerically
equivalent output. A working pattern for that (used previously to
verify `--distill-from` end-to-end without real rasters): a fake
`RegionData` implementing just `raster_years`/`raster_path`, plus
monkeypatching `GrousePatchDataset._read_patch` to return synthetic
arrays instead of doing real I/O — this exercises the actual
dataset/model/training code without touching rasterio. Package the
actual speed measurement as a clear, copy-pasteable benchmarking
protocol for the project owner to run on the real machine, rather than
asserting a speedup you couldn't measure.

## Output format requested

For each proposed change: what it does, why it's expected to help
(ideally backed by a profile), exactly what in `dataset.py` /
`model_handler.py` / `train.py` it touches, the correctness-equivalence
check you ran or propose, and a benchmarking command/protocol the
owner can run to confirm the real-world speedup. Rank by expected
impact, and be explicit about which ones are verified vs. which are
untested hypotheses.
