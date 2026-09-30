"""The one legitimate exception class for the road_dist gate: a sample point
whose nearest paved road lies OUTSIDE the padded grid the generator rasterises
(pad_km = 10).  The generator cannot see it; the STRtree truth can.
Counts them on the already-drawn samples, and reports the truth-distance range."""
import os, glob, numpy as np, pandas as pd, rasterio, geopandas as gpd
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box, Point
from shapely import STRtree, unary_union
MT = ["S1100", "S1200", "S1400", "S1630", "S1640"]
PAD_KM = 10.0
for region in ("NH", "ME"):
    f = f"res_cov_roadpts_{region}.csv"
    d = pd.read_csv(f)
    d = d[~d.raster.str.startswith("old_road_dist")]
    tpl = sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s: T, crs, H, W = s.transform, s.crs, s.height, s.width
    pad_px = int(round(PAD_KM*1000.0/abs(T.a)))
    pt = T * Affine.translation(-pad_px, -pad_px)
    w, s_, e, n = array_bounds(H+2*pad_px, W+2*pad_px, pt)
    pbox = box(min(w, e), min(s_, n), max(w, e), max(s_, n))
    cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
    sel = cty[cty.intersects(gpd.GeoSeries([pbox], crs=crs).to_crs(cty.crs).iloc[0])].to_crs(crs)
    frames = [gpd.read_file(f"data/roads/tl_2023_{st}{cf}_roads.zip")
              for st, cf in zip(sel.STATEFP, sel.COUNTYFP)]
    roads = pd.concat([g[g.MTFCC.isin(MT)] for g in frames], ignore_index=True)
    roads = gpd.GeoDataFrame(roads[["MTFCC", "geometry"]], geometry="geometry",
                             crs=frames[0].crs).to_crs(crs)
    geoms = np.asarray(roads.geometry.values, dtype=object)
    tree = STRtree(geoms)
    pts = [Point(x, y) for x, y in zip(d.x, d.y)]
    idx, dist = tree.query_nearest(pts, all_matches=False, return_distance=True)
    idx = np.asarray(idx); idx = idx[1] if idx.ndim == 2 else idx
    dist = np.asarray(dist).ravel(); g = geoms[idx]
    from shapely.ops import nearest_points
    outside = np.array([not pbox.covers(nearest_points(p_, gi)[1])
                        for p_, gi in zip(pts, g)])
    print(f"{region}: n={len(d)}  nearest road OUTSIDE the padded grid: "
          f"{int(outside.sum())} ({100*outside.mean():.2f}%)   "
          f"truth d: med {np.median(dist):,.0f} p99 {np.percentile(dist,99):,.0f} "
          f"max {dist.max():,.0f} m  (ROAD_DIST_MAX_M=50,000)")
