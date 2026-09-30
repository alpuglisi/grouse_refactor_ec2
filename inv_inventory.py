"""Step 1 of INVESTIGATION_PLAN_errol_map.md: inventory. Read-only."""
import os, json, datetime as dt, torch, rasterio
from grouse_data import GrouseData, grid_mismatch
from models import FEATURE_SPEC
from model_handler import GrouseModelHandler

CKPT, REGION = "bce.pth", "NH"
obj = torch.load(CKPT, map_location="cpu", weights_only=True)
state, cfg = GrouseModelHandler.unwrap_checkpoint(obj)
print("checkpoint mtime:", dt.datetime.fromtimestamp(os.path.getmtime(CKPT)))
print("config:", json.dumps(cfg, indent=1, default=str))
cal = "data/calibration/calibration.json"
if os.path.exists(cal):
    c = json.load(open(cal))
    print("calibration mtime:", dt.datetime.fromtimestamp(os.path.getmtime(cal)))
    print("calibration:", json.dumps({k: c.get(k) for k in ("model_path", "fitted_at",
          "scale", "bias", "temperature", "val_prevalence",
          "ece_cross_fitted")}, indent=1, default=str))
    print("calibration all keys:", sorted(c.keys()))
rd = GrouseData()[REGION]
feats = cfg["features"]
print("\nfeatures in checkpoint:", feats)
paths = {f: rd.latest_raster_path(f) for f in feats}
with rasterio.open(paths[feats[0]]) as ref:
    for f in feats:
        with rasterio.open(paths[f]) as s:
            print(f"{f:12s} {os.path.basename(paths[f]):32s} crs={s.crs.to_string()[:25]:25s} "
                  f"nodata={s.nodata} bounds={tuple(round(b) for b in s.bounds)} "
                  f"grid={'OK' if not grid_mismatch(s, ref) else grid_mismatch(s, ref)}")
print("\nref years available per feature:")
for f in feats:
    print(f"  {f:12s} {rd.raster_years(f)}")
