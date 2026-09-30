import numpy as np, rasterio
for reg in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s: nl=s.read(1)!=-9999
    with rasterio.open(f"data/landfire/{reg}_2025_balive.tif") as s: ba=s.read(1)
    print(f"{reg}: balive>0 outside the NLCD footprint = {int((ba[~nl]>0).sum()):,}"
          f"   (CR-0008 test plan: ME 11,700 / NH 4,464 / VT 2,137)")
