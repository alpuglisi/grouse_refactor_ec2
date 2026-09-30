"""Step 4 of INVESTIGATION_PLAN_errol_map.md: dump every model input over
the prediction box, and (added) split each layer's statistics by ME/NH
side so a layer that changes at the state line is visible as a number,
not only in a picture. Read-only apart from inv_feature_maps/.
"""
import os, numpy as np, rasterio, geopandas as gpd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rasterio.windows import Window
from rasterio.features import rasterize
from grouse_data import GrouseData, MISSING_CODE
from models import FEATURE_SPEC
import predict, torch

BOUNDS, OUT = (-71.25, 44.70, -70.95, 44.90), "inv_feature_maps"
os.makedirs(OUT, exist_ok=True)
rd = GrouseData()["NH"]
model, cat_f, cont_f, feats, cfg = predict.load_model(
    "bce.pth", list(rd.available_features()), torch.device("cpu"))
srcs, ref = predict.open_aligned_sources(rd, cat_f, cont_f)
r0, r1, c0, c1 = predict.bounds_to_window(ref, BOUNDS, pad=0)
win = Window(c0, r0, c1 - c0, r1 - r0)
cat, cont = predict.read_window_stack(srcs, cat_f, cont_f, win)
wt = ref.window_transform(win)
cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
cty = cty[cty.STATEFP.isin(["23", "33"])].to_crs(ref.crs)
sm = {}
for fp, nm in (("23", "ME"), ("33", "NH")):
    sm[nm] = rasterize(((g, 1) for g in cty[cty.STATEFP == fp].geometry
                        if g is not None), out_shape=(cat.shape[1], cat.shape[2]),
                       transform=wt, fill=0, dtype="uint8").astype(bool)
print(f"box window {cat.shape[1]}x{cat.shape[2]}  ME px={sm['ME'].sum()} "
      f"NH px={sm['NH'].sum()}\n")
hdr = (f"{'feature':12s} {'miss%':>6s} {'miss%ME':>8s} {'miss%NH':>8s} "
       f"{'nuniq':>6s} {'min':>9s} {'max':>10s} {'medME':>10s} {'medNH':>10s} "
       f"{'ME-NH':>10s}")
print(hdr)
for i, f in enumerate(cat_f + cont_f):
    isc = i < len(cat_f)
    if isc:
        raw = cat[i].astype(float); miss = cat[i] == MISSING_CODE
    else:
        raw = cont[i - len(cat_f)].astype(float) * FEATURE_SPEC[f].get("scale", 1.0)
        miss = ~np.isfinite(raw)
    arr = np.where(miss, np.nan, raw)
    g = ~miss
    mME, mNH = sm["ME"] & g, sm["NH"] & g
    med = lambda m: np.median(arr[m]) if m.any() else np.nan
    print(f"{f:12s} {miss.mean():6.2%} {miss[sm['ME']].mean():8.2%} "
          f"{miss[sm['NH']].mean():8.2%} "
          f"{(len(np.unique(arr[g])) if g.any() else 0):6d} "
          f"{(np.nanmin(arr) if g.any() else np.nan):9.2f} "
          f"{(np.nanmax(arr) if g.any() else np.nan):10.2f} "
          f"{med(mME):10.2f} {med(mNH):10.2f} {med(mME)-med(mNH):10.2f}")
    plt.figure(figsize=(8, 6))
    plt.imshow(arr, cmap="tab20" if isc else "viridis", interpolation="nearest")
    plt.title(f); plt.colorbar(); plt.savefig(f"{OUT}/{f}.png", dpi=110); plt.close()
    with rasterio.open(f"{OUT}/{f}.tif", "w", driver="GTiff", height=arr.shape[0],
                       width=arr.shape[1], count=1, dtype="float32", crs=ref.crs,
                       transform=wt, nodata=np.nan) as d:
        d.write(arr.astype("float32"), 1)
for s in srcs.values(): s.close()
