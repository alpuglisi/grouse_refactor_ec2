"""diagnose_layer_registration.py - BUG-0094 sweep: is every raster layer
registered with the template grid?

diagnose_grid_registration.py found the on-disk NLCD (NH) about one cell
off the template grid against TIGER roads. This sweep measures EVERY
feature raster on disk, in every region, against the same reference -
road_dist, rasterised locally from TIGER road vectors onto the template
grid (no Earth Engine) - without any Earth Engine call.

Per region it picks N_WINDOWS seeded windows of WINDOW_PX cells holding at
least MIN_ROAD_CELLS road cells (road_dist <= ROAD_M), and for each
feature's latest raster scores how distinct the road cells are at every
offset (dy, dx) up to K cells, averaged over the windows:
  categorical: total-variation distance between the class mix on road
               cells and on all valid cells;
  continuous:  |mean on road - mean off road| / sd.
A registered layer peaks at (0, 0). The LANDFIRE clips define the template
grid and are the control: if they peak elsewhere, road_dist is the
suspect, not the layer.

Read-only: reads data/landfire, writes nothing.

Usage (repository root):
    python diagnose_layer_registration.py
    python diagnose_layer_registration.py --regions NH --windows 12
"""
import argparse

import numpy as np
import rasterio
from rasterio.windows import Window

from grouse_data import GrouseData, NODATA_SENTINELS, grid_mismatch
from models import FEATURE_SPEC, road_dist_decode
from regions import REGIONS

K = 2
ROAD_M = 15.0
WINDOW_PX = 256
MIN_ROAD_CELLS = 500
N_WINDOWS = 8
SEED = 0


def shifted(pad, dy, dx, h, w):
    return pad[K + dy:K + dy + h, K + dx:K + dx + w]


def score_categorical(x, valid, road):
    v_all = x[valid]
    v_road = x[valid & road]
    if v_road.size < 20:
        return np.nan
    cls, inv = np.unique(v_all, return_inverse=True)
    p_all = np.bincount(inv, minlength=len(cls)) / v_all.size
    idx = np.searchsorted(cls, v_road)
    p_road = np.bincount(idx, minlength=len(cls)) / v_road.size
    return 0.5 * float(np.abs(p_road - p_all).sum())


def score_continuous(x, valid, road):
    on, off = x[valid & road], x[valid & ~road]
    sd = float(x[valid].std())
    if on.size < 20 or off.size < 20 or sd == 0:
        return np.nan
    return abs(float(on.mean()) - float(off.mean())) / sd


def pick_windows(road_full, n, seed):
    """Seeded windows with >= MIN_ROAD_CELLS road cells, away from the
    edge by K so every shift stays inside the raster."""
    H, W = road_full.shape
    cand = []
    for r in range(K, H - WINDOW_PX - K, WINDOW_PX):
        for c in range(K, W - WINDOW_PX - K, WINDOW_PX):
            if road_full[r:r + WINDOW_PX, c:c + WINDOW_PX].sum() \
                    >= MIN_ROAD_CELLS:
                cand.append((r, c))
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(cand), size=min(n, len(cand)), replace=False)
    return [cand[i] for i in sorted(pick)], len(cand)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--regions", nargs="+", default=list(REGIONS))
    ap.add_argument("--windows", type=int, default=N_WINDOWS)
    args = ap.parse_args()
    data = GrouseData()
    summary = []
    for R in args.regions:
        rd = data[R]
        with rasterio.open(rd.latest_raster_path("road_dist")) as src:
            raw = src.read(1)
            road_full = (road_dist_decode(raw) <= ROAD_M) & \
                ~np.isin(raw, NODATA_SENTINELS)
            wins, n_cand = pick_windows(road_full, args.windows, SEED)
        print(f"\n{R}: {len(wins)} windows of {WINDOW_PX} px with >= "
              f"{MIN_ROAD_CELLS} road cells (of {n_cand} eligible)")
        if not wins:
            continue
        feats = [f for f in rd.available_features()
                 if f != "road_dist" and f in FEATURE_SPEC]
        for f in feats:
            path = rd.latest_raster_path(f)
            kind = FEATURE_SPEC[f]["kind"]
            score = score_categorical if kind == "categorical" \
                else score_continuous
            with rasterio.open(path) as src, \
                    rasterio.open(rd.latest_raster_path("road_dist")) as ref:
                mm = grid_mismatch(src, ref)
                if mm is not None:
                    print(f"   {f:11s} not on road_dist's grid ({mm}) - "
                          f"skipped")
                    continue
                tab = {(dy, dx): [] for dy in range(-K, K + 1)
                       for dx in range(-K, K + 1)}
                for r, c in wins:
                    x = src.read(1, window=Window(c, r, WINDOW_PX,
                                                  WINDOW_PX))
                    valid = ~np.isin(x, NODATA_SENTINELS)
                    if src.nodata is not None:
                        valid &= x != src.nodata
                    rpad = road_full[r - K:r + WINDOW_PX + K,
                                     c - K:c + WINDOW_PX + K]
                    for (dy, dx) in tab:
                        tab[(dy, dx)].append(score(
                            x, valid, shifted(rpad, dy, dx, WINDOW_PX,
                                              WINDOW_PX)))
            mean = {o: float(np.nanmean(v)) if np.isfinite(v).any()
                    else np.nan for o, v in tab.items()}
            if not np.isfinite(mean[(0, 0)]):
                print(f"   {f:11s} no usable windows")
                continue
            best = max((o for o in mean if np.isfinite(mean[o])),
                       key=mean.get)
            ratio = mean[(0, 0)] / mean[best] if mean[best] else np.nan
            verdict = "aligned" if best == (0, 0) else f"OFF {best}"
            print(f"   {f:11s} {kind[:4]}  best {str(best):8s} "
                  f"{mean[best]:.4f}  at (0,0) {mean[(0, 0)]:.4f} "
                  f"({ratio:.0%} of best)  {verdict}  "
                  f"[{rd.latest_raster_path(f).split('/')[-1]}]")
            summary.append((R, f, best, ratio))
    print("\nSummary - layers not peaking at (0, 0):")
    off = [(R, f, b, r) for R, f, b, r in summary if b != (0, 0)]
    for R, f, b, r in off:
        print(f"   {R} {f:11s} best {b}, (0,0) at {r:.0%} of best")
    if not off:
        print("   none")


if __name__ == "__main__":
    main()
