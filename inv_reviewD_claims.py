import numpy as np, pandas as pd, rasterio, os
from rasterio.windows import Window
from pyproj import Transformer
REG=["ME","NH","VT"]
# out-of-state shares
for r in REG:
    p=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv"); n=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    po=(p.state!=r).sum(); no=(n.state!=r).sum()
    print(f"{r}: thinned positives {len(p)}, out-of-state {po} ({100*po/len(p):.2f}%); "
          f"negatives {len(n)}, out-of-state {no} ({100*no/len(n):.2f}%); diff {abs(100*po/len(p)-100*no/len(n)):.2f} pp")
# unique habitat positives that change region
allp=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allp[~allp['nonveg_landcover'].astype(bool)]
u=hab.drop_duplicates(subset=["longitude","latitude","year","src"])
moved=u[u.state!=u.src]
print(f"\nhabitat rows whose src region != state: {len(moved)}; unique (lon,lat): {moved.drop_duplicates(subset=['longitude','latitude']).shape[0]};"
      f" unique (lon,lat,year): {moved.drop_duplicates(subset=['longitude','latitude','year']).shape[0]}")
# 0 nodata evt pixels in 64x64 window for training records
tot=0; bad=0; anynd=0
for r in REG:
    src=rasterio.open(f"data/landfire/{r}_2023_evt.tif")
    T=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
    for f in (f"data/pipeline/train_positives_{r}.csv", f"data/negatives/train_negatives_{r}.csv"):
        df=pd.read_csv(f)
        x,y=T.transform(df.longitude.values,df.latitude.values)
        rows,cols=rasterio.transform.rowcol(src.transform,x,y)
        cnt=0
        for rr,cc in zip(np.asarray(rows),np.asarray(cols)):
            a=src.read(1,window=Window(cc-32,rr-32,64,64),boundless=True,fill_value=src.nodata)
            if (a==src.nodata).any(): cnt+=1
        print(f"  {os.path.basename(f)}: {cnt} of {len(df)} records with ANY nodata evt pixel in the 64x64 window")
        tot+=len(df); anynd+=cnt
    src.close()
print(f"TOTAL training records checked: {tot}; with any nodata evt pixel in-window: {anynd}")
