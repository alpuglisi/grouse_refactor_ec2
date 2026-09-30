"""Step 5 of INVESTIGATION_PLAN_errol_map.md: train/predict reader parity.
Read-only.

Changes from the plan's listing (investigation-script fixes only):
 - the plan called GrousePatchDataset(...) which needs a 'year' column;
   val positives carry one, so no change was needed there.
 - added a second pass using latest_raster_path (what predict.py really
   uses) to measure how much the VINTAGE alone moves the score.
"""
import numpy as np, torch, rasterio
from pyproj import Transformer
from rasterio.windows import Window
from grouse_data import GrouseData, MISSING_CODE
from dataset import GrousePatchDataset
from models import d4_tta_logits
import predict

N = 20
rd = GrouseData()["NH"]
model, cat_f, cont_f, feats, cfg = predict.load_model(
    "bce.pth", list(rd.available_features()), torch.device("cpu"))
pts = rd.positives("val").head(N).copy()
ds = GrousePatchDataset(pts, rd, cat_f, cont_f, img_size=64, label=1.0)
worst = 0.0; worst_v = 0.0; bad = []
for i in range(len(pts)):
    c_ds, x_ds, _, _ = ds[i]
    lon, lat, yr = pts.longitude.iloc[i], pts.latitude.iloc[i], int(ds._year[i])
    # (a) prediction reader on the SAME year's rasters
    srcs = {f: rasterio.open(rd.raster_path(f, yr)) for f in cat_f + cont_f}
    ref = srcs[(cat_f + cont_f)[0]]
    x, y = Transformer.from_crs("EPSG:4326", ref.crs, always_xy=True).transform(lon, lat)
    r, c = ref.index(x, y)
    cat, cont = predict.read_window_stack(srcs, cat_f, cont_f, Window(c - 32, r - 32, 64, 64))
    for s in srcs.values(): s.close()
    # (b) prediction reader on latest_raster_path (what predict.py uses)
    srcs2, ref2 = predict.open_aligned_sources(rd, cat_f, cont_f)
    x2, y2 = Transformer.from_crs("EPSG:4326", ref2.crs, always_xy=True).transform(lon, lat)
    r2, c2 = ref2.index(x2, y2)
    cat2, cont2 = predict.read_window_stack(srcs2, cat_f, cont_f, Window(c2 - 32, r2 - 32, 64, 64))
    for s in srcs2.values(): s.close()
    same_cat = np.array_equal(c_ds.numpy(), cat)
    same_cont = np.allclose(x_ds.numpy(), cont, equal_nan=True)
    with torch.no_grad():
        a = d4_tta_logits(model, c_ds[None], x_ds[None]).item()
        b = d4_tta_logits(model, torch.from_numpy(cat)[None], torch.from_numpy(cont)[None]).item()
        cc = d4_tta_logits(model, torch.from_numpy(cat2)[None], torch.from_numpy(cont2)[None]).item()
    worst = max(worst, abs(a - b)); worst_v = max(worst_v, abs(b - cc))
    if not (same_cat and same_cont):
        for j, f in enumerate(cat_f):
            if not np.array_equal(c_ds.numpy()[j], cat[j]):
                d = np.argwhere(c_ds.numpy()[j] != cat[j])
                bad.append((i, f, len(d), tuple(d[0])))
        for j, f in enumerate(cont_f):
            if not np.allclose(x_ds.numpy()[j], cont[j], equal_nan=True):
                d = np.argwhere(~np.isclose(x_ds.numpy()[j], cont[j], equal_nan=True))
                bad.append((i, f, len(d), tuple(d[0])))
    print(f"pt{i:2d} yr{yr} cat_equal={same_cat} cont_equal={same_cont} "
          f"logit_train={a:+.4f} logit_predict_sameyear={b:+.4f} "
          f"logit_predict_latest={cc:+.4f}")
print(f"\nmax |logit diff| train vs predict (same year): {worst:.2e}")
print(f"max |logit diff| same-year vs latest vintage : {worst_v:.4f}")
if bad:
    print("\nfirst differing channels/pixels (pt, feature, n_diff, first_idx):")
    for b_ in bad[:20]: print("  ", b_)
else:
    print("no channel differences")
