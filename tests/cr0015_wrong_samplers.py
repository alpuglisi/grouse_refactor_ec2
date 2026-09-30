"""CR-0015 PA-0021(a) constructed WRONG background samplers.

Built 2026-09-30 by an independent agent (a Claude Code sub-agent that is
neither the CR-0015 author nor the implementer of train.py's
sample_background_points or of the CR-0015 acceptance checks), per
PREVENTIVE_ACTIONS.md PA-0021(a): every acceptance invariant must be
measured on a constructed pipeline that is wrong in the way the invariant
exists to catch, built by someone other than the invariant's author.

Every function here has exactly the signature of the correct sampler
(train.py sample_background_points at CR-0015 HEAD)

    (rd, features, n, seed=0, *, region, train_blocks_only,
     assignments=None, in_state=None)

and returns the same frame (longitude, latitude, year, label=0.0,
weight=1.0; exactly n rows; SystemExit on shortfall). Each is wrong in
exactly ONE way and otherwise reproduces the correct sampler (same RNG
stream, same validity rule, same in-state rule), except todays_sampler,
which is the pre-CR sampler verbatim. The block rules are re-typed here,
not delegated to regions.block_split.

| name                  | the one wrongness                                   | caught by (CR-0015 table) |
|-----------------------|-----------------------------------------------------|---------------------------|
| todays_sampler        | pre-CR (00c0b6f) body: no in-state test, no block    | V1 (both counts), U1, U2  |
|                       | rule, rejects 0 as nodata; new keywords ignored      |                           |
| unassigned_excluded   | blocks not listed in assignments are excluded (kept | V3, U2 (iv)               |
|                       | only if listed "train")                              |                           |
| unassigned_train      | blocks not listed in assignments are train (listed   | V1, U2 (iii)              |
|                       | "val" still excluded)                                |                           |
| md5_fraction_018      | md5 rule for unlisted blocks uses 0.18, not vf       | V1                        |
| val_fraction_constant | md5 rule uses regions.VAL_FRACTION (0.2), not vf     | U2 (v)                    |
| native_xy             | block ids from the raster's native x/y instead of    | U2                        |
|                       | lon/lat -> EPSG:5070                                  |                           |

Not a test module (no test_ prefix): imported by the CR-0015 acceptance
harness via WRONG_SAMPLERS.
"""
import hashlib

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1. today's sampler: faithful copy of 00c0b6f:train.py body.
# ---------------------------------------------------------------------------
def todays_sampler(rd, features, n, seed=0, *, region, train_blocks_only,
                   assignments=None, in_state=None):
    """WRONG: the pre-CR-0015 sampler. No in-state test, no block rule,
    0 rejected as nodata. region/train_blocks_only/assignments/in_state
    are accepted and ignored."""
    import rasterio
    from pyproj import Transformer
    from dataset import NODATA_SENTINELS

    feat = features[0]                     # spec order: categorical first
    path = rd.latest_raster_path(feat)
    year = max(rd.raster_years(feat))
    rng = np.random.default_rng(seed)
    lons, lats = [], []
    with rasterio.open(path) as src:
        to_lonlat = Transformer.from_crs(src.crs, "EPSG:4326",
                                         always_xy=True)
        nodata = src.nodata if src.nodata is not None else -9999
        bad = set(NODATA_SENTINELS) | {nodata, 0}
        attempts = 0
        while len(lons) < n and attempts < 40:
            attempts += 1
            m = max(64, 2 * (n - len(lons)))
            rows = rng.integers(0, src.height, m)
            cols = rng.integers(0, src.width, m)
            xs, ys = rasterio.transform.xy(src.transform, rows, cols)
            vals = np.array([v[0] for v in
                             src.sample(zip(xs, ys))], dtype=np.float64)
            ok = ~np.isin(vals, list(bad)) & np.isfinite(vals)
            if ok.any():
                glon, glat = to_lonlat.transform(
                    np.asarray(xs)[ok], np.asarray(ys)[ok])
                lons.extend(np.atleast_1d(glon)[:n - len(lons)])
                lats.extend(np.atleast_1d(glat)[:n - len(lats)])
        if len(lons) < n:
            raise SystemExit(
                f"Background sampling found only {len(lons)}/{n} valid "
                f"locations in {path} after {attempts} rounds - the "
                f"raster may be mostly nodata.")
    return pd.DataFrame({"longitude": lons, "latitude": lats,
                         "year": int(year), "label": 0.0, "weight": 1.0})


# ---------------------------------------------------------------------------
# Shared machinery for samplers 2-6 (independently re-typed).
# ---------------------------------------------------------------------------
def _md5_is_val(block_id, fraction):
    """Re-typed md5 rule: "val" iff md5(f"{SPLIT_SEED}:{id}") % 10_000 <
    fraction * 10_000."""
    import regions
    h = int(hashlib.md5(f"{regions.SPLIT_SEED}:{block_id}".encode())
            .hexdigest(), 16)
    return (h % 10_000) < fraction * 10_000


def _split(ids, assignments, unlisted):
    """"train"/"val"/"excluded" per block id. Listed blocks take their
    listed split; unlisted blocks follow `unlisted`:
    "vf" (correct), "excluded", "train", or a float md5 fraction."""
    listed = dict(zip(assignments["block_id"], assignments["split"]))
    vf = float((assignments["split"] == "val").mean())
    out = []
    for b in ids:
        if b in listed:
            out.append(listed[b])
        elif unlisted == "excluded":
            out.append("excluded")
        elif unlisted == "train":
            out.append("train")
        else:
            frac = vf if unlisted == "vf" else float(unlisted)
            out.append("val" if _md5_is_val(b, frac) else "train")
    return np.array(out, dtype=object)


def _sample(rd, features, n, seed, region, train_blocks_only, assignments,
            in_state, *, unlisted="vf", native_xy=False):
    """The correct sampler's loop, with the block rule parameterised."""
    import rasterio
    from pyproj import Transformer
    import regions
    from dataset import NODATA_SENTINELS

    if train_blocks_only and assignments is None:
        raise ValueError("train_blocks_only=True needs the block "
                         "assignments (block_assignments.csv)")
    if not train_blocks_only and assignments is not None:
        raise ValueError("assignments must be None when "
                         "train_blocks_only is False")
    if in_state is None:
        in_state = regions.in_state

    feat = features[0]
    path = rd.latest_raster_path(feat)
    year = max(rd.raster_years(feat))
    rng = np.random.default_rng(seed)
    sentinels = np.asarray(NODATA_SENTINELS, dtype=np.float64)
    lons, lats = [], []
    with rasterio.open(path) as src:
        to_lonlat = Transformer.from_crs(src.crs, "EPSG:4326",
                                         always_xy=True)
        declared_nodata = src.nodata
        attempts = 0
        while len(lons) < n and attempts < 40:
            attempts += 1
            m = max(64, 2 * (n - len(lons)))
            rows = rng.integers(0, src.height, m)
            cols = rng.integers(0, src.width, m)
            xs, ys = rasterio.transform.xy(src.transform, rows, cols)
            vals = np.array([v[0] for v in
                             src.sample(zip(xs, ys))], dtype=np.float64)
            ok = np.isfinite(vals) & ~np.isin(vals, sentinels)
            if declared_nodata is not None:
                ok &= vals != declared_nodata
            if not ok.any():
                continue
            nx = np.asarray(xs, dtype=np.float64)[ok]
            ny = np.asarray(ys, dtype=np.float64)[ok]
            glon, glat = to_lonlat.transform(nx, ny)
            glon = np.atleast_1d(np.asarray(glon, dtype=np.float64))
            glat = np.atleast_1d(np.asarray(glat, dtype=np.float64))
            keep = np.asarray(in_state(glon, glat, region), dtype=bool)
            if train_blocks_only and keep.any():
                if native_xy:
                    bx, by = nx[keep], ny[keep]          # WRONG CRS
                else:
                    bx, by = regions.to_5070(glon[keep], glat[keep])
                split = _split(regions.block_ids(bx, by), assignments,
                               unlisted)
                keep[np.flatnonzero(keep)] = split == "train"
            take = n - len(lons)
            lons.extend(glon[keep][:take].tolist())
            lats.extend(glat[keep][:take].tolist())
    if len(lons) < n:
        raise SystemExit(
            f"[{region}] background sampling found only {len(lons)}/{n} "
            f"accepted locations in {path} after {attempts} rounds.")
    return pd.DataFrame({"longitude": lons, "latitude": lats,
                         "year": int(year), "label": 0.0, "weight": 1.0})


# ---------------------------------------------------------------------------
# 2-6. One wrongness each.
# ---------------------------------------------------------------------------
def unassigned_excluded(rd, features, n, seed=0, *, region,
                        train_blocks_only, assignments=None, in_state=None):
    """WRONG: a block not listed in assignments is excluded; only blocks
    listed as "train" are kept."""
    return _sample(rd, features, n, seed, region, train_blocks_only,
                   assignments, in_state, unlisted="excluded")


def unassigned_train(rd, features, n, seed=0, *, region, train_blocks_only,
                     assignments=None, in_state=None):
    """WRONG: a block not listed in assignments is train (listed "val"
    still excluded)."""
    return _sample(rd, features, n, seed, region, train_blocks_only,
                   assignments, in_state, unlisted="train")


def md5_fraction_018(rd, features, n, seed=0, *, region, train_blocks_only,
                     assignments=None, in_state=None):
    """WRONG: the md5 rule for unlisted blocks uses fraction 0.18 instead
    of vf."""
    return _sample(rd, features, n, seed, region, train_blocks_only,
                   assignments, in_state, unlisted=0.18)


def val_fraction_constant(rd, features, n, seed=0, *, region,
                          train_blocks_only, assignments=None,
                          in_state=None):
    """WRONG: the md5 rule for unlisted blocks uses regions.VAL_FRACTION
    (0.2) instead of vf."""
    import regions
    return _sample(rd, features, n, seed, region, train_blocks_only,
                   assignments, in_state, unlisted=regions.VAL_FRACTION)


def native_xy(rd, features, n, seed=0, *, region, train_blocks_only,
              assignments=None, in_state=None):
    """WRONG: block ids computed from the raster's native x/y instead of
    lon/lat -> EPSG:5070."""
    return _sample(rd, features, n, seed, region, train_blocks_only,
                   assignments, in_state, native_xy=True)


WRONG_SAMPLERS = {
    "todays_sampler": todays_sampler,
    "unassigned_excluded": unassigned_excluded,
    "unassigned_train": unassigned_train,
    "md5_fraction_018": md5_fraction_018,
    "val_fraction_constant": val_fraction_constant,
    "native_xy": native_xy,
}
