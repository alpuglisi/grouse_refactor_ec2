"""
bench_pipeline.py

Throughput benchmark for the training pipeline on the REAL data and the
REAL machine - the numbers that decide whether a speed change helped.
Three stages, each timed separately so a change to one shows up in one:

  loader   samples/s the training DataLoader delivers (workers, cache,
           augmentation exactly as train.py builds them), with the GPU
           idle - the ceiling the data path imposes.
  eval     wall time of ONE full validation pass through
           GrouseModelHandler.evaluate() (the per-epoch cost of
           checkpoint selection, TTA included).
  train    samples/s over N optimizer steps of the real fit() loop
           (a short fit() with tqdm output, timed end to end).

Same flags as train.py for everything that affects geometry or the
data path, so the measurement is of the run you actually make.

PROTOCOL - one run per git revision, from the project directory. The
script imports the project code from the CURRENT DIRECTORY (not from
wherever the script file sits), so a copy kept outside the repo can
benchmark an older commit that does not contain this script:

    cp bench_pipeline.py /tmp/bench.py            # survives the checkout
    git checkout <before-commit>
    python /tmp/bench.py --steps 200 <your train.py geometry flags> | tee before.txt
    git checkout <your branch>
    python /tmp/bench.py --steps 200 <same flags> | tee after.txt
    python /tmp/bench.py --steps 200 <same flags> --compile | tee after_compile.txt

Run each configuration TWICE and keep the second (the first pays cache
builds, cudnn autotuning and, with --compile, compilation). Nothing
here changes any file; the checkpoint fit() writes is deleted after.
--compile needs the newer code and is ignored, with a note, on a
revision whose fit() has no compile_model argument.
"""
import argparse
import inspect
import os
import sys
import time

# The project directory is wherever this is RUN from, so a copy of this
# file outside the repo benchmarks whatever revision is checked out.
sys.path.insert(0, os.getcwd())

import torch
from torch.utils.data import DataLoader

from grouse_data import GrouseData
from train import (build_datasets, discover_features, IMG_SIZE, BATCH_SIZE,
                   WORKERS)
from model_handler import GrouseModelHandler, _loader_extra
from dataset import StratifiedBatchSampler


def sync():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"])
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--cache-dir", default="data/cache")
    ap.add_argument("--jitter", type=int, default=0)
    ap.add_argument("--loader-batches", type=int, default=300,
                    help="Training batches to pull for the loader stage.")
    ap.add_argument("--steps", type=int, default=0,
                    help="Optimizer steps for the train stage (0 = skip). "
                         "Runs fit() for one epoch capped at this many "
                         "batches via a sampler-sized epoch.")
    ap.add_argument("--compile", action="store_true")
    ap.add_argument("--no-eval", action="store_true")
    # geometry flags, same defaults as train.py
    ap.add_argument("--pool", default="attn")
    ap.add_argument("--keep-early-resolution", action="store_true")
    ap.add_argument("--early-attn", action="store_true")
    ap.add_argument("--dual-branch", default="off")
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--flip-tta", action=argparse.BooleanOptionalAction,
                    default=True)
    args = ap.parse_args()

    data = GrouseData()
    features = discover_features(data, args.regions)
    print(f"features: {features}")
    t0 = time.perf_counter()
    train_ds, val_ds, train_labels = build_datasets(
        data, args.regions, features, IMG_SIZE,
        cache_dir=args.cache_dir or None, jitter=args.jitter, augment=True)
    print(f"datasets built in {time.perf_counter() - t0:.1f}s "
          f"(train {len(train_ds):,} items, val {len(val_ds):,})")

    # ---- loader ----------------------------------------------------------
    sampler = StratifiedBatchSampler(train_labels, args.batch_size)
    loader = DataLoader(train_ds, batch_sampler=sampler,
                        num_workers=args.workers, pin_memory=True,
                        persistent_workers=args.workers > 0,
                        **_loader_extra(args.workers))
    it = iter(loader)
    for _ in range(10):                     # warm the workers
        next(it)
    t0 = time.perf_counter()
    n = 0
    for _ in range(args.loader_batches):
        batch = next(it)
        n += batch[0].shape[0]
    dt = time.perf_counter() - t0
    print(f"loader: {n / dt:,.0f} samples/s over {args.loader_batches} "
          f"batches of {args.batch_size} with {args.workers} workers")
    del it, loader

    handler = GrouseModelHandler(
        features, pretrained=False, pool=args.pool, dropout=args.dropout,
        keep_early_resolution=args.keep_early_resolution,
        early_attn=args.early_attn, dual_branch=args.dual_branch,
        flip_tta=args.flip_tta, save_path=os.path.join(
            args.cache_dir or ".", "bench_discard.pth"))

    # ---- eval ------------------------------------------------------------
    if not args.no_eval:
        eval_bs = handler._eval_batch_size(args.batch_size)
        val_loader = DataLoader(val_ds, batch_size=eval_bs,
                                num_workers=args.workers, pin_memory=True,
                                persistent_workers=args.workers > 0,
                                **_loader_extra(args.workers))
        if handler.device.type == 'cuda':
            handler.model = handler.model.to(memory_format=torch.channels_last)
            handler._mem_fmt = torch.channels_last
        if args.compile and not hasattr(handler, "_install_compiled_logits"):
            print("   --compile: this revision has no compile support; "
                  "measuring eager.")
            args.compile = False
        if args.compile:
            handler._install_compiled_logits(False)
            handler.evaluate(val_loader, None, 0, 1)      # pay the compile
        handler.evaluate(val_loader, None, 0, 1)          # warm
        sync(); t0 = time.perf_counter()
        handler.evaluate(val_loader, None, 0, 1)
        sync(); dt = time.perf_counter() - t0
        print(f"eval: {dt:.1f}s for one validation pass "
              f"({len(val_ds):,} items, batch {eval_bs}, "
              f"flip_tta={args.flip_tta}, compile={args.compile})")

    # ---- train -----------------------------------------------------------
    if args.steps > 0:
        # A sampler whose epoch is exactly --steps batches: fit() then
        # runs one real epoch (all of its per-step work: AMP, EMA, clip,
        # accumulators) of that length, plus one validation pass.
        class _Capped(StratifiedBatchSampler):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.n_batches = args.steps
        import dataset as _d
        _d.StratifiedBatchSampler = _Capped
        sync(); t0 = time.perf_counter()
        extra = ({"compile_model": True} if args.compile and "compile_model"
                 in inspect.signature(handler.fit).parameters else {})
        handler.fit(train_ds, val_ds, epochs=1, batch_size=args.batch_size,
                    workers=args.workers, train_labels=train_labels, **extra)
        sync(); dt = time.perf_counter() - t0
        print(f"train: {args.steps * args.batch_size / dt:,.0f} samples/s "
              f"end-to-end over {args.steps} steps of {args.batch_size} "
              f"(includes one validation pass and, with --compile, the "
              f"compile itself - run twice, keep the second)")
        try:
            os.remove(handler.save_path)
            os.remove(handler._resume_path())
        except OSError:
            pass


if __name__ == "__main__":
    main()
