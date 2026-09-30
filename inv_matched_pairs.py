"""Step 3 of INVESTIGATION_PLAN_errol_map.md, run on automatically MATCHED
Maine/NH pairs instead of eyeballed ones.

Picks pairs of 30 m cells inside the prediction box, one on each side of
the ME/NH line, that are the SAME habitat by the model's own categorical
inputs (identical evt, evh, evc, sclass, nlcd) and close in the
continuous structure inputs (|dch|<=2 m, |dcc|<=5 %, |dtcc|<=5 %), then
reports every raw input value plus the OLD and NEW road_dist and the
model score before and after the road_dist regeneration.

Read-only apart from inv_matched_pairs.csv.
"""
import numpy as np, torch, rasterio, geopandas as gpd, pandas as pd
from rasterio.windows import Window
from rasterio.features import rasterize
from pyproj import Transformer
from grouse_data import GrouseData, MISSING_CODE
from models import d4_tta_logits, road_dist_decode, FEATURE_SPEC
import predict

BOUNDS = (-71.25, 44.70, -70.95, 44.90)
NPAIRS, SEED = 8, 0
DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
rng = np.random.default_rng(SEED)
rd = GrouseData()["NH"]
model, cat_f, cont_f, feats, cfg = predict.load_model(
    "bce.pth", list(rd.available_features()), DEV)
srcs, ref = predict.open_aligned_sources(rd, cat_f, cont_f)
r0, r1, c0, c1 = predict.bounds_to_window(ref, BOUNDS, pad=0)

cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
cty = cty[cty.STATEFP.isin(["23", "33"])].to_crs(ref.crs)
state = {}
for fp, nm in (("23", "ME"), ("33", "NH")):
    state[nm] = rasterize(((g, 1) for g in cty[cty.STATEFP == fp].geometry
                           if g is not None), out_shape=(ref.height, ref.width),
                          transform=ref.transform, fill=0, dtype="uint8").astype(bool)

# read the whole box once, per feature, for matching
win = Window(c0, r0, c1 - c0, r1 - r0)
box_cat, box_cont = predict.read_window_stack(srcs, cat_f, cont_f, win)
me = state["ME"][r0:r1, c0:c1]; nh = state["NH"][r0:r1, c0:c1]
# only cells with a full 64x64 window inside the raster
H, W = me.shape
valid = np.zeros_like(me)
valid[32:H-32, 32:W-32] = True
ci = {f: i for i, f in enumerate(cat_f)}
ni = {f: i for i, f in enumerate(cont_f)}
KEYC = ["evt", "evh", "evc", "sclass", "nlcd"]
key = np.stack([box_cat[ci[f]] for f in KEYC])
nomiss = (key != MISSING_CODE).all(0) & np.isfinite(box_cont).all(0)
sig = np.stack([key[i].astype(np.int64) for i in range(len(KEYC))])
ch, cc, tcc = (box_cont[ni["ch"]] * FEATURE_SPEC["ch"].get("scale", 1.0),
               box_cont[ni["cc"]] * FEATURE_SPEC["cc"].get("scale", 1.0),
               box_cont[ni["tcc"]] * FEATURE_SPEC["tcc"].get("scale", 1.0))

me_idx = np.argwhere(me & valid & nomiss)
nh_idx = np.argwhere(nh & valid & nomiss)
print(f"candidate cells: ME={len(me_idx)} NH={len(nh_idx)}")
# index NH cells by the categorical signature
from collections import defaultdict
buckets = defaultdict(list)
for r, c in nh_idx:
    buckets[tuple(sig[:, r, c])].append((r, c))
pairs = []
order = rng.permutation(len(me_idx))
for k in order:
    r, c = me_idx[k]
    cand = buckets.get(tuple(sig[:, r, c]), [])
    for (r2, c2) in cand:
        if (abs(ch[r, c] - ch[r2, c2]) <= 2 and abs(cc[r, c] - cc[r2, c2]) <= 5
                and abs(tcc[r, c] - tcc[r2, c2]) <= 5):
            pairs.append(((r, c), (r2, c2))); break
    if len(pairs) >= NPAIRS: break
print(f"matched pairs found: {len(pairs)}")

old_src = rasterio.open("old_road_dist/NH_2025_road_dist.tif")
ri = ni["road_dist"]; rscale = FEATURE_SPEC["road_dist"].get("scale", 1.0)

def window_at(r, c, use_old):
    w = Window(c0 + c - 32, r0 + r - 32, 64, 64)
    cat, cont = predict.read_window_stack(srcs, cat_f, cont_f, w)
    if use_old:
        a = old_src.read(1, window=w).astype(np.float32)
        a = np.where(a == old_src.nodata, np.nan, a)
        cont = cont.copy(); cont[ri] = a / rscale
    return cat, cont

def logit(cat, cont):
    with torch.no_grad():
        return d4_tta_logits(model, torch.from_numpy(cat)[None].to(DEV),
                             torch.from_numpy(cont)[None].to(DEV)).item()

inv = Transformer.from_crs(ref.crs, "EPSG:4326", always_xy=True)
CAL_S, CAL_B = 1.4555354749867293, -1.4895245138331301
def prob(l): return 1 / (1 + np.exp(-(l * CAL_S + CAL_B)))
rows = []
for n, ((mr, mc), (nr, nc)) in enumerate(pairs):
    for side, (r, c) in (("ME", (mr, mc)), ("NH", (nr, nc))):
        x, y = ref.xy(r0 + r, c0 + c)
        lon, lat = inv.transform(x, y)
        cat_o, cont_o = window_at(r, c, True)
        cat_n, cont_n = window_at(r, c, False)
        lo, ln = logit(cat_o, cont_o), logit(cat_n, cont_n)
        rec = dict(pair=n, side=side, lon=round(lon, 5), lat=round(lat, 5))
        for f in cat_f: rec[f] = int(box_cat[ci[f], r, c])
        for f in cont_f:
            rec[f] = round(float(box_cont[ni[f], r, c]
                                 * FEATURE_SPEC[f].get("scale", 1.0)), 2)
        rec["road_dist_m_OLD"] = round(float(road_dist_decode(
            cont_o[ri, 32, 32] * rscale)), 0)
        rec["road_dist_m_NEW"] = round(float(road_dist_decode(
            cont_n[ri, 32, 32] * rscale)), 0)
        rec["logit_OLD"], rec["logit_NEW"] = round(lo, 4), round(ln, 4)
        rec["prob_OLD"], rec["prob_NEW"] = round(prob(lo), 4), round(prob(ln), 4)
        rows.append(rec)
df = pd.DataFrame(rows)
df.to_csv("inv_matched_pairs.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 50)
print("\n--- matched habitat (identical evt/evh/evc/sclass/nlcd; ch,cc,tcc close) ---")
print(df[["pair", "side", "lon", "lat", "evt", "evh", "evc", "sclass", "nlcd",
          "ch", "cc", "tcc", "road_dist_m_OLD", "road_dist_m_NEW",
          "prob_OLD", "prob_NEW"]].to_string(index=False))
p = df.pivot(index="pair", columns="side")
print("\n--- ME minus NH, per pair ---")
for col, lab in (("road_dist_m_OLD", "road_dist m (OLD)"),
                 ("road_dist_m_NEW", "road_dist m (NEW)"),
                 ("prob_OLD", "prob (OLD)"), ("prob_NEW", "prob (NEW)")):
    d = p[col]["ME"] - p[col]["NH"]
    print(f"  {lab:20s} mean ME-NH = {d.mean():+10.4f}   per pair: "
          f"{[round(v, 3) for v in d.tolist()]}")
old_src.close()
for s in srcs.values(): s.close()
