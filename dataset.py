"""
dataset.py

GrousePatchDataset - rebuilt against the new pipeline (the original
dataset.py consumed GeoJSON point files + hardcoded CONUS mosaic paths;
neither exists anymore). Serves (cat_x, cont_x, y, w) samples where:

  cat_x  : (n_cat, H, W) integer patch stack, one channel per
           categorical feature (spec order)
  cont_x : (n_cont, H, W) float patch stack, scaled per FEATURE_SPEC
  y      : label float (1.0 positives / 0.0 negatives)
  w      : per-sample weight (negatives carry their envelope-derived
           weight from generate_negatives.py; positives default 1.0)

Rasters are resolved through grouse_data.RegionData.raster_path()
(nearest valid year to each record's own year, content-validated), so
patch sources inherit all the empty-raster/fallback protections. Window
reads are boundless with nodata fill, so edge-of-region points work.

Rotation augmentation preserved from the original: expand_rotations=True
maps each point to 4 dataset items (0/90/180/270 degrees), exactly the
i*4+rot convention the original used for positives.
"""
import os

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from pyproj import Transformer
from rasterio.windows import Window
import rasterio

from models import FEATURE_SPEC

NODATA_SENTINELS = {-9999, -32768, 32767, -1111}


class GrousePatchDataset(Dataset):
    def __init__(self, points_df, region_data, cat_features, cont_features,
                 img_size=64, expand_rotations=False, label=None,
                 spec=None, cache_dir=None, jitter=0, augment=False):
        """points_df needs longitude/latitude/year columns; 'label' column
        used unless the label argument overrides it; 'weight' column used
        when present (else 1.0). region_data: a grouse_data.RegionData.

        cache_dir : materialize every point's patch stack once into a
            memmapped int16 array and serve items from it. The rasters
            are static, so re-reading them every epoch is pure waste.
        jitter    : max random center offset IN PIXELS applied when
            augment=True. Patches are read jitter-padded so the crop is
            always real data, never fill.
        augment   : random D4 symmetry (8 orientations) + random jitter
            per access, instead of the deterministic idx%4 rotation.
            Train only - validation must stay deterministic."""
        self.spec = spec or FEATURE_SPEC
        self.cat_features = list(cat_features)
        self.cont_features = list(cont_features)
        self.img_size = int(img_size)
        self.expand_rotations = bool(expand_rotations)
        self.augment = bool(augment)
        self.pad = int(jitter) if augment else 0
        # Every read/cache entry is patch+2*pad wide; a jittered crop then
        # lands entirely inside real raster data.
        self.read_size = self.img_size + 2 * self.pad
        self.rd = region_data

        df = points_df.copy().reset_index(drop=True)
        if label is not None:
            df['label'] = float(label)
        if 'label' not in df.columns:
            raise ValueError("points_df needs a 'label' column or an "
                             "explicit label= argument")
        if 'weight' not in df.columns:
            df['weight'] = 1.0
        df['weight'] = df['weight'].fillna(1.0)
        if 'year' not in df.columns or df['year'].isna().all():
            df['year'] = max(self.rd.raster_years(self.cat_features[0])
                             if self.cat_features else
                             self.rd.raster_years(self.cont_features[0]))
        df['year'] = df['year'].fillna(df['year'].max()).astype(int)
        self.df = df

        # Resolve (feature, record-year) -> raster path once, up front.
        all_feats = self.cat_features + self.cont_features
        self._path_for = {}
        for feat in all_feats:
            for yr in sorted(df['year'].unique()):
                self._path_for[(feat, int(yr))] = self.rd.raster_path(feat, int(yr))

        # Raster handles and per-raster coordinate transformers are
        # created lazily per worker process. CRITICAL: points are
        # transformed from lon/lat into EACH RASTER'S OWN CRS - LFPS
        # clips arrive in a custom LOCAL Albers centered on the request
        # AOI (coordinates spanning ~+/-200km around 0), NOT EPSG:5070.
        # An earlier version transformed to 5070 unconditionally; every
        # point then fell outside the raster bounds, every patch read as
        # all-nodata fill, and the model trained on identical all-zero
        # tensors (constant predictor, frozen metrics). The probe below
        # makes that failure mode loud and immediate instead.
        self._handles = None
        self._transformers = None
        self._cache_pid = None

        self._probe_first_point()

        self.cache = None
        if cache_dir:
            self.cache = self._load_or_build_cache(cache_dir)

    # ---- patch cache -----------------------------------------------------
    def _cache_key(self, cache_dir):
        """Identity of the materialized patches: the points themselves,
        the feature set and channel order, the read geometry, and the
        resolved raster files. Any change to those invalidates the cache
        rather than silently serving stale patches."""
        import hashlib
        h = hashlib.sha1()
        feats = self.cat_features + self.cont_features
        h.update(repr(feats).encode())
        h.update(repr(self.read_size).encode())
        for f in feats:
            for yr in sorted(self.df['year'].unique()):
                p = self._path_for[(f, int(yr))]
                h.update(f"{f}:{yr}:{p}:{os.path.getmtime(p)}".encode())
        for col in ('longitude', 'latitude', 'year'):
            h.update(np.ascontiguousarray(
                self.df[col].values.astype(np.float64)).tobytes())
        return os.path.join(cache_dir, f"patches_{h.hexdigest()[:16]}.npy")

    def _load_or_build_cache(self, cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
        path = self._cache_key(cache_dir)
        n_pts = len(self.df)
        n_feat = len(self.cat_features) + len(self.cont_features)
        shape = (n_pts, n_feat, self.read_size, self.read_size)
        if os.path.exists(path):
            return np.load(path, mmap_mode='r')
        # Values are stored POST nodata-cleanup (sentinels -> 0) as int16:
        # every LANDFIRE band is int16 and every code fits, so this is
        # lossless and a quarter the size of float32.
        tmp = path + f".tmp{os.getpid()}"
        arr = np.lib.format.open_memmap(tmp, mode='w+', dtype=np.int16,
                                        shape=shape)
        feats = self.cat_features + self.cont_features
        for i in range(n_pts):
            row = self.df.iloc[i]
            lon, lat = float(row['longitude']), float(row['latitude'])
            yr = int(row['year'])
            for k, f in enumerate(feats):
                patch = self._read_patch(self._path_for[(f, yr)], lon, lat)
                arr[i, k] = np.nan_to_num(patch, nan=0.0).astype(np.int16)
        arr.flush()
        del arr
        os.replace(tmp, path)
        self._close_handles()
        return np.load(path, mmap_mode='r')

    def _close_handles(self):
        if self._handles:
            for src in self._handles.values():
                try:
                    src.close()
                except Exception:
                    pass
        self._handles, self._transformers, self._cache_pid = None, None, None

    def _probe_first_point(self):
        """Read one patch for the first point at construction time, with
        a throwaway handle (never cached - rasterio handles must not be
        created before DataLoader workers fork). If it comes back
        entirely nodata, the geolocation is broken (CRS/bounds mismatch,
        wrong-region raster...) - fail HERE with specifics, not after
        epochs of silent constant training."""
        if len(self.df) == 0:
            return
        feat = (self.cat_features + self.cont_features)[0]
        row = self.df.iloc[0]
        path = self._path_for[(feat, int(row['year']))]
        with rasterio.open(path) as src:
            t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            x, y = t.transform(float(row['longitude']), float(row['latitude']))
            r, c = src.index(x, y)
            half = self.img_size // 2
            window = Window(c - half, r - half, self.img_size, self.img_size)
            fill = src.nodata if src.nodata is not None else -9999
            arr = src.read(1, window=window, boundless=True,
                           fill_value=fill).astype(np.float32)
            if src.nodata is not None:
                arr[arr == src.nodata] = np.nan
            for s in NODATA_SENTINELS:
                arr[arr == s] = np.nan
            if np.all(np.isnan(arr)):
                raise ValueError(
                    f"Geolocation sanity probe FAILED: the patch for the "
                    f"first point (lon={row['longitude']:.4f}, "
                    f"lat={row['latitude']:.4f}) read as 100% nodata from "
                    f"{path}.\n  Raster CRS: {src.crs}\n  Raster bounds: "
                    f"{src.bounds}\n  Point in raster CRS: ({x:.0f}, "
                    f"{y:.0f})\nIf the point coordinates fall outside the "
                    f"bounds above, the raster doesn't cover this "
                    f"location (wrong region/extent?). Refusing to build "
                    f"a dataset that would silently feed all-zero "
                    f"patches.")

    def __len__(self):
        return len(self.df) * (4 if self.expand_rotations else 1)

    def _handle(self, path):
        # Handles are per-PROCESS. A rasterio/GDAL dataset inherited
        # across a fork shares file offsets and block cache with the
        # parent, and concurrent reads through it fail ("Read failed") or
        # return garbage. Anything that touches the dataset in the main
        # process before DataLoader forks its workers - e.g. the
        # handler's init-time feed sanity check, which indexes val_ds
        # directly - would otherwise poison every worker. Stamping the
        # cache with its owner PID and rebuilding it after a fork makes
        # that safe regardless of access order.
        if self._handles is None or self._cache_pid != os.getpid():
            self._handles = {}
            self._transformers = {}
            self._cache_pid = os.getpid()
        if path not in self._handles:
            src = rasterio.open(path)
            self._handles[path] = src
            # Transformer into THIS raster's CRS (see __init__ note).
            self._transformers[path] = Transformer.from_crs(
                "EPSG:4326", src.crs, always_xy=True)
        return self._handles[path], self._transformers[path]

    def _read_patch(self, path, lon, lat):
        src, transformer = self._handle(path)
        x, y = transformer.transform(lon, lat)
        row, col = src.index(x, y)
        n = self.read_size
        half = n // 2
        r0, c0 = row - half, col - half
        fill = src.nodata if src.nodata is not None else -9999
        # boundless=True is NOT used here even though the semantics below
        # reproduce it exactly. rasterio implements boundless reads by
        # constructing a VRT dataset from serialized XML on EVERY call:
        # measured 13.8 ms vs 0.04 ms for the equivalent in-bounds
        # windowed read, x7 features x every sample. That single call was
        # holding the loader to ~8 samples/s while the GPU could consume
        # ~1160/s - i.e. it, not the model, was the training bottleneck.
        if 0 <= r0 and 0 <= c0 and r0 + n <= src.height and c0 + n <= src.width:
            arr = src.read(1, window=Window(c0, r0, n, n)).astype(np.float32)
        else:
            # Edge-of-region point: read whatever intersects the raster
            # and pad the remainder with the fill value by hand.
            rs, re = max(r0, 0), min(r0 + n, src.height)
            cs, ce = max(c0, 0), min(c0 + n, src.width)
            arr = np.full((n, n), fill, dtype=np.float32)
            if re > rs and ce > cs:
                arr[rs - r0:re - r0, cs - c0:ce - c0] = src.read(
                    1, window=Window(cs, rs, ce - cs, re - rs))
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        for s in NODATA_SENTINELS:
            arr[arr == s] = np.nan
        return arr

    def _raw_stack(self, i, lon, lat, year):
        """(n_feat, read_size, read_size) float32, nodata already 0."""
        if self.cache is not None:
            return np.asarray(self.cache[i], dtype=np.float32)
        feats = self.cat_features + self.cont_features
        return np.stack([
            np.nan_to_num(self._read_patch(self._path_for[(f, year)], lon, lat),
                          nan=0.0) for f in feats])

    def __getitem__(self, idx):
        if self.expand_rotations:
            i, rot = idx // 4, idx % 4
        else:
            i, rot = idx, 0
        row = self.df.iloc[i]
        lon, lat, year = (float(row['longitude']), float(row['latitude']),
                          int(row['year']))

        stack = self._raw_stack(i, lon, lat, year)

        n, pad = self.img_size, self.pad
        flip = False
        if self.augment:
            # torch's RNG (not numpy's) because DataLoader reseeds it per
            # worker AND per epoch; numpy's global seed is duplicated
            # across workers, which would make every worker draw the same
            # "random" augmentation sequence.
            rot = int(torch.randint(0, 4, (1,)).item())
            flip = bool(torch.randint(0, 2, (1,)).item())
            if pad:
                dy = int(torch.randint(-pad, pad + 1, (1,)).item())
                dx = int(torch.randint(-pad, pad + 1, (1,)).item())
            else:
                dy = dx = 0
            stack = stack[:, pad + dy:pad + dy + n, pad + dx:pad + dx + n]
        elif pad:
            stack = stack[:, pad:pad + n, pad:pad + n]

        n_cat = len(self.cat_features)
        cat_np, cont_np = stack[:n_cat], stack[n_cat:]
        cat_x = (torch.from_numpy(np.ascontiguousarray(cat_np)).long()
                 if n_cat else torch.zeros((0, n, n), dtype=torch.long))
        if len(self.cont_features):
            scales = np.array([[[float(self.spec[f].get("scale", 1.0))]]
                               for f in self.cont_features], dtype=np.float32)
            cont_x = torch.from_numpy(
                np.ascontiguousarray(cont_np / scales)).float()
        else:
            cont_x = torch.zeros((0, n, n), dtype=torch.float32)

        # D4 symmetry: rotation alone covers 4 of the 8 orientations;
        # adding the reflection covers the rest. Habitat suitability is
        # invariant to both, so this is free label-preserving data.
        if rot:
            cat_x = torch.rot90(cat_x, k=rot, dims=(1, 2))
            cont_x = torch.rot90(cont_x, k=rot, dims=(1, 2))
        if flip:
            cat_x = torch.flip(cat_x, dims=(2,))
            cont_x = torch.flip(cont_x, dims=(2,))

        yl = torch.tensor(float(row['label']), dtype=torch.float32)
        w = torch.tensor(float(row['weight']), dtype=torch.float32)
        return cat_x, cont_x, yl, w

    @property
    def labels(self):
        """Per-item labels WITHOUT reading any raster - needed by the
        stratified batch sampler, which must know every item's class up
        front. Order matches __getitem__ indexing exactly (each point
        contributes 4 consecutive items when expand_rotations)."""
        import numpy as np
        base = self.df['label'].values.astype(np.float32)
        return np.repeat(base, 4) if self.expand_rotations else base


class StratifiedBatchSampler(torch.utils.data.Sampler):
    """Yields index batches with CONTROLLED positive/negative composition
    so no batch is ever all-one-class and 'lazy constant guessing' is
    penalized within every step.

    Two modes:
      ALTERNATING (default, fracs=(0.25, 0.75)): batch compositions
        alternate - e.g. 25% pos / 75% neg, then 75% pos / 25% neg.
        Across each PAIR of batches the model sees exactly 50/50, but no
        single batch resembles a constant-guess-friendly distribution,
        and the batch-majority gradient direction flips sign every step -
        Adam's momentum then damps that oscillating class-prior component
        while consistent feature-learning gradients pass through.
      FIXED (fracs=single float or (x,) ): every batch has the same
        composition; None -> the dataset's global ratio.

    Minority draws recycle (reshuffled) so the schedule always completes;
    an epoch is sized so each class is consumed about once."""

    def __init__(self, labels, batch_size, pos_frac=None, seed=0):
        import numpy as np
        import math
        self.labels = np.asarray(labels)
        self.batch_size = int(batch_size)
        self.pos_idx = np.where(self.labels == 1)[0]
        self.neg_idx = np.where(self.labels == 0)[0]
        if len(self.pos_idx) == 0 or len(self.neg_idx) == 0:
            raise ValueError("StratifiedBatchSampler needs both classes "
                             "present in the dataset.")
        if pos_frac is None:
            fracs = (0.25, 0.75)          # alternating default
        elif isinstance(pos_frac, (tuple, list)):
            fracs = tuple(float(f) for f in pos_frac)
        else:
            fracs = (float(pos_frac),)    # fixed composition
        self.fracs = fracs
        self.n_pos_pb = [max(1, min(self.batch_size - 1,
                                    round(self.batch_size * f)))
                         for f in fracs]
        self.n_neg_pb = [self.batch_size - n for n in self.n_pos_pb]
        self.rng = np.random.default_rng(seed)
        # Size an epoch so each class is consumed ~once at its average
        # per-batch rate across the composition cycle.
        avg_pos = sum(self.n_pos_pb) / len(self.n_pos_pb)
        avg_neg = sum(self.n_neg_pb) / len(self.n_neg_pb)
        n = max(math.ceil(len(self.pos_idx) / avg_pos),
                math.ceil(len(self.neg_idx) / avg_neg))
        # Round up to a full composition cycle so every epoch nets the
        # intended overall ratio (e.g. exactly 50/50 for (0.25, 0.75)).
        cycle = len(fracs)
        self.n_batches = math.ceil(n / cycle) * cycle

    def _stream(self, idx):
        while True:
            order = self.rng.permutation(idx)
            for i in order:
                yield i

    def __iter__(self):
        pos_stream = self._stream(self.pos_idx)
        neg_stream = self._stream(self.neg_idx)
        for b in range(self.n_batches):
            k = b % len(self.fracs)
            batch = ([next(pos_stream) for _ in range(self.n_pos_pb[k])]
                     + [next(neg_stream) for _ in range(self.n_neg_pb[k])])
            self.rng.shuffle(batch)
            yield batch

    def __len__(self):
        return self.n_batches

