"""
diagnose_water_bias.py

Follow-up to diagnose_road_bias.py. That script disproved the leading
hypothesis for predict.py --tensorboard's Errol, NH suitability map
hugging Route 16/26: positives sit 2-5x FARTHER from roads (median
2,951-4,875m) than both the raw GBIF negative candidate pool and the
negatives actually trained on (844-1,451m) in all three states - the
opposite of an accessibility-bias signature. If anything, the trained-on
NEGATIVES are the road-biased class, which should suppress predicted
suitability near roads, not inflate it.

The alternative read: in mountainous northern New England, roads follow
valley bottoms and river/lake shorelines (the only buildable grade), and
Route 16 in the Errol screenshot runs directly along the Androscoggin
River and Umbagog Lake. Woody Wetlands (mean score 0.550) and Emergent
Wetlands (0.664) were already the two highest-scoring NLCD classes in
that same predict.py run (see Class/mean_score/* tiles) - both
concentrate near water. So the map may be tracing riparian/wetland
habitat structure that RUNS ALONGSIDE the road, not the road itself.

This is the direct test: distance to the nearest water/wetland NLCD
pixel (11=Open Water, 90=Woody Wetlands, 95=Emergent Wetlands - see
grouse_data.NLCD_NAMES/WETLAND_NLCD_CLASSES) instead of distance to the
nearest road, for the same three point sets per region (positives,
selected negatives, raw GBIF candidates). No new download: reuses each
region's already-on-disk NLCD raster (GrouseData.latest_raster_path) via
a Euclidean distance transform - the same feature the model itself
trains on.

Reading: if positives sit closer to water/wetland than raw candidates
and selected negatives do, that supports the riparian-corridor read
directly - habitat, not infrastructure, driving the road-hugging
appearance. If positives are no closer to water than the other two
point sets, water proximity doesn't explain it either and the pattern
needs a different explanation entirely.

CAVEAT: uses each region's SINGLE most recent NLCD raster (no per-point
year matching) - wetland/water extent doesn't shift much year to year
at this scale, so that's a reasonable simplification for a diagnostic,
unlike the per-feature year-matching training itself requires.

Usage:
    python diagnose_water_bias.py
    python diagnose_water_bias.py --regions NH
"""
import argparse
import os

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from scipy.ndimage import distance_transform_edt

from grouse_data import GrouseData, WETLAND_NLCD_CLASSES

REGIONS_DEFAULT = ["ME", "NH", "VT"]
OPEN_WATER_CODE = 11
THRESHOLDS_M = (300, 1000)

_transformers = {}
def _get_transformer(crs):
    key = crs.to_string()
    if key not in _transformers:
        _transformers[key] = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    return _transformers[key]


def build_distance_raster(nlcd_path, target_codes):
    """Euclidean distance (meters) from every pixel to the nearest pixel
    whose NLCD code is in target_codes. Returns (dist_array, transform,
    crs) so callers can sample it at arbitrary points."""
    with rasterio.open(nlcd_path) as src:
        nlcd = src.read(1)
        transform, crs, nodata = src.transform, src.crs, src.nodata
    mask = np.isin(nlcd, target_codes)
    res_x, res_y = abs(transform.a), abs(transform.e)
    dist = distance_transform_edt(~mask, sampling=(res_y, res_x))
    return dist, transform, crs


def sample_array(dist_arr, transform, crs, lons, lats):
    """Value of dist_arr at each (lon, lat), NaN for points outside the
    raster's extent - same CRS-transform + bounds-check pattern as
    analyze_grouse.sample_raster, adapted to sample a precomputed array
    (the distance transform) instead of reading a band from disk."""
    out = np.full(len(lons), np.nan)
    xs, ys = _get_transformer(crs).transform(np.asarray(lons), np.asarray(lats))
    rows, cols = rasterio.transform.rowcol(transform, xs, ys)
    rows, cols = np.asarray(rows), np.asarray(cols)
    h, w = dist_arr.shape
    inside = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
    out[inside] = dist_arr[rows[inside], cols[inside]]
    return out


def summarize(label, dists):
    if len(dists) == 0:
        print(f"    {label}: no points")
        return
    parts = [f"{100 * (dists <= t).mean():5.1f}% within {t}m"
            for t in THRESHOLDS_M]
    print(f"    {label:24s} n={len(dists):6,} | median {np.median(dists):7.0f} m "
         f"| mean {dists.mean():7.0f} m | " + " | ".join(parts))


def process_region(region, data):
    print(f"\n{'=' * 60}\n{region}\n{'=' * 60}")
    rd = data[region]
    try:
        nlcd_path = rd.latest_raster_path("nlcd")
    except Exception as e:
        print(f"  [!] No usable NLCD raster for {region} ({e}). Skipping.")
        return None
    print(f"  NLCD raster: {nlcd_path}")

    wetland_or_water = (OPEN_WATER_CODE,) + tuple(WETLAND_NLCD_CLASSES)
    dist_water, transform, crs = build_distance_raster(
        nlcd_path, (OPEN_WATER_CODE,))
    dist_wetland, _, _ = build_distance_raster(nlcd_path, wetland_or_water)

    pos_paths = [f"data/pipeline/train_positives_{region}.csv",
                f"data/pipeline/val_positives_{region}.csv"]
    pos_frames = [pd.read_csv(p) for p in pos_paths if os.path.exists(p)]
    pos = pd.concat(pos_frames, ignore_index=True) if pos_frames else pd.DataFrame()

    neg_path = f"data/negatives/negatives_{region}.csv"
    cand_path = f"data/negatives/gbif_negatives_{region}.csv"
    neg = pd.read_csv(neg_path) if os.path.exists(neg_path) else pd.DataFrame()
    cand = pd.read_csv(cand_path) if os.path.exists(cand_path) else pd.DataFrame()

    if len(pos) == 0:
        print(f"  [!] No positives found for {region} - run "
             f"prepare_training_data.py first. Skipping.")
        return None

    results = {}
    for label, df in (("positives (trained on)", pos),
                      ("selected negatives", neg),
                      ("raw GBIF candidates", cand)):
        if len(df) == 0:
            print(f"    [!] {label}: file missing/empty, skipping.")
            continue
        lons, lats = df["longitude"].values, df["latitude"].values
        d_water = sample_array(dist_water, transform, crs, lons, lats)
        d_wetland = sample_array(dist_wetland, transform, crs, lons, lats)
        print(f"  -- distance to OPEN WATER --")
        summarize(label, d_water[np.isfinite(d_water)])
        results.setdefault("water", {})[label] = d_water[np.isfinite(d_water)]
        results.setdefault("wetland", {})[label] = d_wetland[np.isfinite(d_wetland)]
    print(f"  -- distance to WATER OR WETLAND (11/90/95) --")
    for label, dists in results.get("wetland", {}).items():
        summarize(label, dists)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=REGIONS_DEFAULT,
                    choices=REGIONS_DEFAULT)
    args = ap.parse_args()

    data = GrouseData()
    all_results = {r: process_region(r, data) for r in args.regions}

    print(f"\n{'=' * 60}\nVERDICT\n{'=' * 60}")
    for region, res in all_results.items():
        if not res or "positives (trained on)" not in res.get("wetland", {}):
            continue
        wet = res["wetland"]
        pos_med = float(np.median(wet["positives (trained on)"]))
        line = f"  {region}: positives median {pos_med:.0f}m from water/wetland"
        for other in ("raw GBIF candidates", "selected negatives"):
            if other in wet:
                other_med = float(np.median(wet[other]))
                closer = " (positives CLOSER)" if pos_med < other_med * 0.8 else \
                         " (positives FARTHER)" if pos_med > other_med * 1.25 else \
                         " (comparable)"
                line += f" | {other} {other_med:.0f}m{closer}"
        print(line)


if __name__ == "__main__":
    main()
