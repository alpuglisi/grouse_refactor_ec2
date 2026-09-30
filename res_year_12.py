import os
os.chdir('/home/ec2-user/grouse2')
import numpy as np, rasterio, collections
for y in [2022,2023,2024,2025]:
    p=f'data/landfire/NH_{y}_fdist.tif'
    if not os.path.exists(p): print(y,"MISSING"); continue
    with rasterio.open(p) as s:
        a=s.read(1, out_shape=(1, s.height//8, s.width//8))
        nd=s.nodata
    u,c=np.unique(a,return_counts=True)
    top=sorted(zip(u,c),key=lambda t:-t[1])[:6]
    print(f"fdist {y}: nodata={nd} n_unique={len(u)} top={[(int(v),int(n)) for v,n in top]}")
