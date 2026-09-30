"""FORMAL C: sample the continuous FEATURE_SPEC features for the faithful pool
and for the positives, so the NEGATIVE class's ks_feat can be measured.
(CR-0007 scopes I17 'positives only'.)  READ-ONLY, scratch output."""
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
import inv_formalC_lib as L
CONT = ["ch","cc","tcc","road_dist","tsd","balive","tpa_live","qmd","carbon_dwn"]
V = 2022
tf = {}
for r in L.R:
    with rasterio.open(f"data/landfire/{r}_{V}_road_dist.tif") as s:
        tf[r] = Transformer.from_crs("EPSG:4326", s.crs, always_xy=True)
def samp(df):
    out = {f: np.full(len(df), np.nan) for f in CONT}
    for r in L.R:
        m = (df.state.values == r)
        if not m.any(): continue
        xs, ys = tf[r].transform(df.loc[m,'longitude'].values, df.loc[m,'latitude'].values)
        pts = list(zip(xs, ys))
        for f in CONT:
            with rasterio.open(f"data/landfire/{r}_{V}_{f}.tif") as s:
                v = np.array([x[0] for x in s.sample(pts)], dtype=float)
                v[v <= -9990] = np.nan
                out[f][m] = v
    return pd.DataFrame(out, index=df.index)
P, C = L.load()
for name, d in (("pos", P), ("pool", C)):
    F = samp(d)
    F.to_csv(f"{L.SCR}/fc_feat_{name}.csv", index=False)
    print(name, len(F), "nan frac:", {f: round(float(F[f].isna().mean()),4) for f in CONT})
