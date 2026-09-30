import numpy as np, rasterio
from grouse_data import GrouseData
d=GrouseData()
for reg in ['ME','NH','VT']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s:
        nl=s.read(1)
    n=nl.size
    print(f"{reg}: grid={nl.shape} n={n}")
    print(f"   nlcd == -9999 frac          = {(nl==-9999).mean():.6f}")
    print(f"   nlcd outside [11,95] frac   = {((nl<11)|(nl>95)).mean():.6f}")
    u,c=np.unique(nl,return_counts=True)
    print(f"   nlcd unique values          = {list(zip(u.tolist(),c.tolist()))[:6]} ... n_uniq={len(u)}")
    with rasterio.open(r.raster_path('road_dist',2016)) as s:
        rd=s.read(1)
    print(f"   road_dist == -9999 frac     = {(rd==-9999).mean():.6f}")
    print(f"   road_dist min/max valid     = {rd[rd!=-9999].min()}/{rd[rd!=-9999].max()}")
    print(f"   road_dist ==10820 count     = {(rd==10820).sum()}")
    del nl, rd
