import numpy as np, pandas as pd, rasterio, os
from pyproj import Transformer
REG=["ME","NH","VT"]
# (a) separate "nodata pixel present" from "window extends outside raster"
for r in ("NH",):
    with rasterio.open(f"data/landfire/{r}_2023_evt.tif") as src:
        nd=(src.read(1)==src.nodata); H,W=nd.shape
        ii=np.zeros((H+1,W+1),np.int64); ii[1:,1:]=nd.cumsum(0).cumsum(1)
        T=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
        for f in (f"data/pipeline/train_positives_{r}.csv",f"data/pipeline/val_positives_{r}.csv"):
            df=pd.read_csv(f); x,y=T.transform(df.longitude.values,df.latitude.values)
            rows,cols=rasterio.transform.rowcol(src.transform,x,y); rows=np.asarray(rows);cols=np.asarray(cols)
            r0=np.clip(rows-32,0,H);r1=np.clip(rows+32,0,H);c0=np.clip(cols-32,0,W);c1=np.clip(cols+32,0,W)
            s=ii[r1,c1]-ii[r0,c1]-ii[r1,c0]+ii[r0,c0]
            oob=((rows-32<0)|(rows+32>H)|(cols-32<0)|(cols+32>W))
            print(f"{os.path.basename(f)}: real-nodata-in-window {int((s>0).sum())}; window-outside-raster {int(oob.sum())}; either {int(((s>0)|oob).sum())}")
            m=(s>0)|oob
            print(df.loc[m,["longitude","latitude","state","year"]].to_string())

# (b) what definition gives 1,012?
allp=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allp[~allp['nonveg_landcover'].astype(bool)]
print("\nhabitat rows:",len(hab),"unique(lon,lat):",hab.drop_duplicates(subset=['longitude','latitude']).shape[0])
g=hab.groupby(['longitude','latitude'])['src'].nunique()
print("unique habitat coords in >1 region file:",int((g>1).sum()))
print("habitat rows src!=state:",int((hab.state!=hab.src).sum()))
# coords whose set of region files != {state} i.e. the coordinate is read from a foreign grid somewhere
sub=hab[hab.state!=hab.src]
print("unique coords with at least one foreign-grid row:",sub.drop_duplicates(subset=['longitude','latitude']).shape[0])
# coords that appear ONLY in a foreign region file (so the partition truly moves them)
only_foreign=[]
for (lo,la),grp in hab.groupby(['longitude','latitude']):
    if grp.src.nunique()==1 and grp.src.iloc[0]!=grp.state.iloc[0]: only_foreign.append((lo,la))
print("unique habitat coords present ONLY in a foreign region file (genuinely move):",len(only_foreign))
