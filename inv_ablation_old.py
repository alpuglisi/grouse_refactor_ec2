"""Step 6 of INVESTIGATION_PLAN_errol_map.md: feature ablation over the
prediction box. Read-only (writes only inv_ablationOLD_*.npy).

Changed from the plan's listing: runs on CUDA when available (the plan's
listing hardcoded CPU), and reports the ME-vs-NH split of each feature's
delta-logit so the ablation speaks directly to the reported symptom.
"""
import numpy as np, torch, rasterio, geopandas as gpd
from rasterio.windows import Window
from rasterio.features import rasterize
from grouse_data import GrouseData, MISSING_CODE
from models import d4_tta_logits
import predict

BOUNDS, STEP = (-71.25, 44.70, -70.95, 44.90), 24          # 24 px = 720 m grid
DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
rd = GrouseData()["NH"]
# INVESTIGATION OVERRIDE: resolve road_dist to the pre-fix raster copy so
# this ablation runs on the inputs that produced the reported map.
_orig_lrp = rd.latest_raster_path
rd.latest_raster_path = lambda f, **kw: ("old_road_dist/NH_2025_road_dist.tif"
    if f == "road_dist" else _orig_lrp(f, **kw))
model, cat_f, cont_f, feats, cfg = predict.load_model(
    "bce.pth", list(rd.available_features()), DEV)
srcs, ref = predict.open_aligned_sources(rd, cat_f, cont_f)
r0, r1, c0, c1 = predict.bounds_to_window(ref, BOUNDS, pad=0)
rows = list(range(r0, r1 - 64, STEP)); cols = list(range(c0, c1 - 64, STEP))
coords = [(r, c) for r in rows for c in cols]
H, W = len(rows), len(cols)
print(f"device={DEV} windows={len(coords)} grid={H}x{W}")

# state mask at each window CENTRE (+32 px), on ref's grid
cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
cty = cty[cty.STATEFP.isin(["23", "33"])].to_crs(ref.crs)
full = {}
for fp, nm in (("23", "ME"), ("33", "NH")):
    full[nm] = rasterize(((g, 1) for g in cty[cty.STATEFP == fp].geometry
                          if g is not None), out_shape=(ref.height, ref.width),
                         transform=ref.transform, fill=0, dtype="uint8").astype(bool)
me_mask = np.array([full["ME"][r + 32, c + 32] for r, c in coords]).reshape(H, W)
nh_mask = np.array([full["NH"][r + 32, c + 32] for r, c in coords]).reshape(H, W)
print(f"centres: ME={me_mask.sum()} NH={nh_mask.sum()}")
np.save("inv_ablationOLD_me_mask.npy", me_mask); np.save("inv_ablationOLD_nh_mask.npy", nh_mask)

cats, conts = zip(*[predict.read_window_stack(srcs, cat_f, cont_f, Window(c, r, 64, 64))
                    for r, c in coords])
cat, cont = torch.from_numpy(np.stack(cats)), torch.from_numpy(np.stack(conts))
B = 256
def score(cx, nx):
    out = []
    with torch.no_grad():
        for i in range(0, len(cx), B):
            out.append(d4_tta_logits(model, cx[i:i+B].to(DEV), nx[i:i+B].to(DEV)).cpu())
    return torch.cat(out).numpy()
base = score(cat, cont).reshape(H, W)
np.save("inv_ablationOLD_base.npy", base)
print(f"{'feature':12s} {'mean dl':>8s} {'mean|dl|':>9s} {'sp.std':>7s} "
      f"{'dl ME':>8s} {'dl NH':>8s} {'dl ME-NH':>9s}")
print(f"{'(base)':12s} {'':>8s} {'':>9s} {'':>7s} {base[me_mask].mean():8.3f} "
      f"{base[nh_mask].mean():8.3f} {base[me_mask].mean()-base[nh_mask].mean():9.3f}")
for i, f in enumerate(cat_f + cont_f):
    cx, nx = cat.clone(), cont.clone()
    if i < len(cat_f): cx[:, i] = MISSING_CODE
    else: nx[:, i - len(cat_f)] = float("nan")
    d = (score(cx, nx).reshape(H, W) - base)
    np.save(f"inv_ablationOLD_{f}.npy", d)
    print(f"{f:12s} {d.mean():+8.3f} {np.abs(d).mean():9.3f} {d.std():7.3f} "
          f"{d[me_mask].mean():+8.3f} {d[nh_mask].mean():+8.3f} "
          f"{d[me_mask].mean()-d[nh_mask].mean():+9.3f}")
for s in srcs.values(): s.close()
