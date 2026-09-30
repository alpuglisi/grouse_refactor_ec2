import numpy as np, pandas as pd, rasterio, os
from pyproj import Transformer
REG=["ME","NH","VT"]
for r in REG:
    p=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv"); n=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    po=(p.state!=r).sum(); no=(n.state!=r).sum()
    print(f"{r}: thinned pos {len(p)}, out-of-state {po} ({100*po/len(p):.2f}%); neg {len(n)}, out-of-state {no} ({100*no/len(n):.2f}%); diff {abs(100*po/len(p)-100*no/len(n)):.2f} pp")
allp=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allp[~allp['nonveg_landcover'].astype(bool)]
moved=hab[hab.state!=hab.src]
print(f"\nhabitat rows src!=state: {len(moved)}; unique(lon,lat): {moved.drop_duplicates(subset=['longitude','latitude']).shape[0]}; unique(lon,lat,year): {moved.drop_duplicates(subset=['longitude','latitude','year']).shape[0]}")

print("\n--- nodata evt pixels inside 64x64 windows (integral-image, all training records) ---")
tot=0; anynd=0
for r in REG:
    with rasterio.open(f"data/landfire/{r}_2023_evt.tif") as src:
        nd=(src.read(1)==src.nodata)
        ii=np.zeros((nd.shape[0]+1,nd.shape[1]+1),np.int64); ii[1:,1:]=nd.cumsum(0).cumsum(1)
        T=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True); H,W=nd.shape
        for f in (f"data/pipeline/train_positives_{r}.csv", f"data/negatives/train_negatives_{r}.csv",
                  f"data/pipeline/val_positives_{r}.csv", f"data/negatives/val_negatives_{r}.csv"):
            df=pd.read_csv(f)
            x,y=T.transform(df.longitude.values,df.latitude.values)
            rows,cols=rasterio.transform.rowcol(src.transform,x,y)
            rows=np.asarray(rows);cols=np.asarray(cols)
            r0=np.clip(rows-32,0,H); r1=np.clip(rows+32,0,H); c0=np.clip(cols-32,0,W); c1=np.clip(cols+32,0,W)
            s=ii[r1,c1]-ii[r0,c1]-ii[r1,c0]+ii[r0,c0]
            oob=((rows-32<0)|(rows+32>H)|(cols-32<0)|(cols+32>W))
            cnt=int(((s>0)|oob).sum())
            print(f"  {os.path.basename(f)}: {cnt} of {len(df)} with any nodata evt pixel (or out-of-raster window) in 64x64")
            if "train" in os.path.basename(f): tot+=len(df); anynd+=cnt
print(f"TOTAL train records {tot}; with nodata/OOB evt in-window: {anynd}")
