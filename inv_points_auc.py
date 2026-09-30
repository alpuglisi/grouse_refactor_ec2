"""Step 7 of INVESTIGATION_PLAN_errol_map.md: known points vs the map.
Samples each prediction GeoTIFF at the in-box positives/negatives and
reports in-box AUC, overall and per state side. Read-only apart from
inv_points.kml.

usage: python inv_points_auc.py tif [tif ...]
"""
import sys, numpy as np, pandas as pd, rasterio, geopandas as gpd
from pyproj import Transformer
from sklearn.metrics import roc_auc_score, average_precision_score
from shapely.geometry import Point
from grouse_data import GrouseData

W, S, E, N = -71.25, 44.70, -70.95, 44.90
rd = GrouseData()["NH"]
frames = []
for name, df in (("pos", rd.positives("all")), ("neg", rd.negatives("all"))):
    d = df[(df.longitude.between(W, E)) & (df.latitude.between(S, N))].copy()
    d["label"] = 1 if name == "pos" else 0
    frames.append(d[["longitude", "latitude", "label"] +
                    ([c for c in ("split",) if c in d.columns])])
pts = pd.concat(frames, ignore_index=True)
print(f"in-box points: {len(pts)}  positives={int(pts.label.sum())} "
      f"negatives={int((pts.label == 0).sum())}")
if "split" in pts.columns:
    print(pts.groupby(["label", "split"]).size().to_string())

cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
cty = cty[cty.STATEFP.isin(["23", "33"])].to_crs("EPSG:4326")
g = gpd.GeoDataFrame(pts, geometry=[Point(x, y) for x, y in
                                    zip(pts.longitude, pts.latitude)],
                     crs="EPSG:4326")
j = gpd.sjoin(g, cty[["STATEFP", "geometry"]], how="left", predicate="within")
j = j[~j.index.duplicated()]
pts["state"] = j["STATEFP"].map({"23": "ME", "33": "NH"}).values
print(pts.groupby(["state", "label"]).size().to_string())

try:
    import simplekml
    k = simplekml.Kml()
    for _, r in pts.iterrows():
        p = k.newpoint(name=("pos" if r.label else "neg"),
                       coords=[(r.longitude, r.latitude)])
        p.style.iconstyle.color = "ff00ff00" if r.label else "ff0000ff"
    k.save("inv_points.kml"); print("wrote inv_points.kml")
except ImportError:
    print("simplekml not installed - skipping inv_points.kml")

for path in sys.argv[1:]:
    with rasterio.open(path) as src:
        t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = t.transform(pts.longitude.values, pts.latitude.values)
        v = np.array([s[0] for s in src.sample(list(zip(x, y)))], dtype=float)
        if src.nodata is not None:
            v[v == src.nodata] = np.nan
    ok = np.isfinite(v)
    print(f"\n=== {path}")
    print(f"  sampled {ok.sum()}/{len(v)} points inside the map")
    for sel, nm in ((ok, "in-box all"),
                    (ok & (pts.state.values == "ME"), "ME side"),
                    (ok & (pts.state.values == "NH"), "NH side")):
        lab, sc = pts.label.values[sel], v[sel]
        if len(np.unique(lab)) < 2:
            print(f"  {nm:11s}: n={sel.sum():4d} pos={int(lab.sum()):3d} "
                  f"- only one class, AUC undefined; mean score "
                  f"pos={sc[lab==1].mean() if (lab==1).any() else float('nan'):.4f} "
                  f"neg={sc[lab==0].mean() if (lab==0).any() else float('nan'):.4f}")
            continue
        print(f"  {nm:11s}: n={sel.sum():4d} pos={int(lab.sum()):3d} "
              f"AUC={roc_auc_score(lab, sc):.4f} AP={average_precision_score(lab, sc):.4f} "
              f"mean_pos={sc[lab==1].mean():.4f} mean_neg={sc[lab==0].mean():.4f}")
    # does the map rank ME points above NH points of the SAME label?
    for lb in (1, 0):
        me = v[ok & (pts.state.values == "ME") & (pts.label.values == lb)]
        nh = v[ok & (pts.state.values == "NH") & (pts.label.values == lb)]
        if len(me) and len(nh):
            from scipy.stats import mannwhitneyu
            u = mannwhitneyu(me, nh, alternative="two-sided")
            print(f"  label={lb}: ME n={len(me)} mean={me.mean():.4f} | "
                  f"NH n={len(nh)} mean={nh.mean():.4f} | "
                  f"P(ME>NH)={u.statistic/(len(me)*len(nh)):.4f}")
