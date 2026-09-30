"""Fourth independent land reference: Census cartographic-boundary state file
(1:20,000,000, data/maps/map_data/cb_2023_us_state_20m.zip).  Coarse by design
-- measured only to show how far a generalised boundary is from usable."""
import os, glob, numpy as np, rasterio, rasterio.features, geopandas as gpd
from shapely.geometry import box
from shapely import unary_union
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
cb = gpd.read_file("data/maps/map_data/cb_2023_us_state_20m.zip")
print("states:", len(cb), cb.crs)
for r in ("ME", "NH", "VT"):
    tpl = sorted(glob.glob(f"data/landfire/{r}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s: T, crs, H, W = s.transform, s.crs, s.height, s.width
    a = np.load(os.path.join(SCRATCH, f"{r}_nlcd.npy"))
    nl = np.unpackbits(a)[:H*W].astype(bool).reshape(H, W)
    sel = cb.to_crs(crs)
    m = rasterio.features.rasterize(((g, 1) for g in sel.geometry), out_shape=(H, W),
            transform=T, fill=0, default_value=1, all_touched=True,
            dtype="uint8").astype(bool)
    print(f"{r}: cb20m inside {m.sum():,} ({m.mean():.6f}) outside {1-m.mean():.6f} | "
          f"cb&~nlcd {int((m & ~nl).sum()):,} ({(m & ~nl).mean()*100:.4f}%)  "
          f"nlcd&~cb {int((nl & ~m).sum()):,} ({(nl & ~m).mean()*100:.4f}%)")
