"""Calibrate a ground-truth gate for road_dist's IN-COVERAGE values.

Truth = EXACT shapely distance from the sample point to the nearest paved
TIGER-2023 road line (MTFCC S1100/S1200/S1400/S1630/S1640) from every county
intersecting the grid + 10 km -- no densification, no KD-tree approximation.

Stratified sample so the strata where BUG-0023 lived cannot be diluted away:
  S1 interior   : >=5 km inside coverage, >=5 km from any other-state line,
                  >=10 km from the grid edge
  S2 stateline  : within 5 km of a land boundary with a DIFFERENT US state
  S3 gridedge   : within 10 km of the grid edge, inside coverage
  S4 covedge    : within 5 km of the coverage (county-union) boundary
                  -> truth is an UPPER BOUND near Canada; reported, not gated

Usage: res_cov_roadgate.py REGION RASTER [RASTER ...]
"""
import os, sys, glob, numpy as np, rasterio, geopandas as gpd, pandas as pd
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box, Point
from shapely import STRtree, unary_union
from models import road_dist_decode

MT = ["S1100", "S1200", "S1400", "S1630", "S1640"]
STATE_FIPS = {"ME": "23", "NH": "33", "VT": "50"}
PAD_KM = 10.0
N_PER_STRATUM = int(os.environ.get("NPS", "250"))
SEED = 12345

region = sys.argv[1]
rasters = sys.argv[2:]
tpl = sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
with rasterio.open(tpl) as s:
    crs, T, H, W = s.crs, s.transform, s.height, s.width
pad_px = int(round(PAD_KM * 1000.0 / abs(T.a)))
pt = T * Affine.translation(-pad_px, -pad_px)
w, s_, e, n = array_bounds(H + 2*pad_px, W + 2*pad_px, pt)
gb = (min(w, e), min(s_, n), max(w, e), max(s_, n))
gw, gs, ge, gn = array_bounds(H, W, T)
grid_box = box(min(gw, ge), min(gs, gn), max(gw, ge), max(gs, gn))

cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
fp = gpd.GeoSeries([box(*gb)], crs=crs).to_crs(cty.crs).iloc[0]
sel = cty[cty.intersects(fp)].to_crs(crs)
cov = unary_union(sel.geometry.values)
home = unary_union(sel[sel.STATEFP == STATE_FIPS[region]].geometry.values)
other = unary_union(sel[sel.STATEFP != STATE_FIPS[region]].geometry.values)
print(f"{region}: {len(sel)} counties; coverage area "
      f"{cov.area/1e6:,.0f} km2 in grid CRS")

frames = []
for st, cf in zip(sel.STATEFP, sel.COUNTYFP):
    p = f"data/roads/tl_2023_{st}{cf}_roads.zip"
    if not os.path.exists(p):
        print(f"   [MISSING county roads] {p} -- truth would be wrong; abort")
        sys.exit(2)
    d = gpd.read_file(p)
    frames.append(d[d.MTFCC.isin(MT)][["geometry"]])
roads = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                         geometry="geometry", crs=frames[0].crs).to_crs(crs)
print(f"   paved segments: {len(roads):,}")
tree = STRtree(roads.geometry.values)

rng = np.random.default_rng(SEED)
cov_in_grid = cov.intersection(grid_box)
line_other = home.boundary.intersection(other.buffer(1.0))  # shared land line
cov_bnd = cov.boundary
edge_ring = grid_box.buffer(0).boundary

def sample(pred, k, maxtries=400):
    out = []
    for _ in range(maxtries):
        x = rng.uniform(min(gw, ge), max(gw, ge), 20000)
        y = rng.uniform(min(gs, gn), max(gs, gn), 20000)
        g = gpd.points_from_xy(x, y)
        keep = pred(g, x, y)
        for i in np.where(keep)[0]:
            out.append((x[i], y[i]))
            if len(out) >= k:
                return out
    return out

inside = lambda g: gpd.GeoSeries(g, crs=crs).within(cov_in_grid).values
d_edge = lambda x, y: np.minimum.reduce([x - min(gw, ge), max(gw, ge) - x,
                                         y - min(gs, gn), max(gs, gn) - y])

def dist_to(geom, g):
    return gpd.GeoSeries(g, crs=crs).distance(geom).values

strata = {}
print("   sampling ...")
strata["S2_stateline"] = sample(
    lambda g, x, y: inside(g) & (dist_to(line_other, g) <= 5000), N_PER_STRATUM)
strata["S3_gridedge"] = sample(
    lambda g, x, y: inside(g) & (d_edge(x, y) <= 10000), N_PER_STRATUM)
strata["S4_covedge"] = sample(
    lambda g, x, y: inside(g) & (dist_to(cov_bnd, g) <= 5000), N_PER_STRATUM)
strata["S1_interior"] = sample(
    lambda g, x, y: inside(g) & (dist_to(cov_bnd, g) > 5000)
                    & (dist_to(line_other, g) > 5000) & (d_edge(x, y) > 10000),
    N_PER_STRATUM)
strata["S0_uniform"] = sample(lambda g, x, y: inside(g), N_PER_STRATUM)

rows = []
per = []
for name, pts in strata.items():
    if not pts:
        print(f"   {name}: EMPTY")
        continue
    P = np.asarray(pts)
    geoms = [Point(xy) for xy in P]
    _, dtrue = tree.query_nearest(geoms, all_matches=False,
                                  return_distance=True)
    for rp in rasters:
        with rasterio.open(rp) as src:
            v = np.array([q[0] for q in src.sample(list(map(tuple, P)))],
                         dtype=float)
            nd = src.nodata if src.nodata is not None else -9999
        nodata_n = int((v == nd).sum())
        ok = v != nd
        dr = road_dist_decode(v[ok])
        err = dr - dtrue[ok]
        a = np.abs(err)
        per.append(pd.DataFrame(dict(stratum=name, raster=os.path.basename(os.path.dirname(rp)) + "/" + os.path.basename(rp), x=P[ok,0], y=P[ok,1], truth=dtrue[ok], ras=dr, err=err)))
        rows.append(dict(stratum=name, raster=os.path.basename(os.path.dirname(rp)) + "/" + os.path.basename(rp),
                         n=len(P), nodata=nodata_n,
                         truth_med=np.median(dtrue), ras_med=np.median(dr),
                         med_abs=np.median(a), p90=np.percentile(a, 90),
                         p95=np.percentile(a, 95), p99=np.percentile(a, 99),
                         mx=a.max(), bias_med=np.median(err),
                         frac_gt_100=float((a > 100).mean()),
                         frac_gt_1000=float((a > 1000).mean())))
df = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(df.to_string(index=False, float_format=lambda v: f"{v:,.1f}"))
df.to_csv(f"res_cov_roadgate_{region}.csv", index=False)
pd.concat(per, ignore_index=True).to_csv(f"res_cov_roadpts_{region}.csv", index=False)
