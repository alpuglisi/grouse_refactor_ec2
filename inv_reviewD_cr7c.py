import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from collections import defaultdict
REG=["ME","NH","VT"]
BOXES={"ME":(-71.158,42.889,-66.852,47.555),"NH":(-72.626,42.605,-70.600,45.398),"VT":(-73.510,42.632,-71.422,45.112)}
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def thin(df,m,seed=42):
    rng=np.random.default_rng(seed); o=rng.permutation(len(df))
    xs=df["x_5070"].values; ys=df["y_5070"].values
    cells=defaultdict(list); keep=np.zeros(len(df),bool)
    for i in o:
        cx,cy=int(np.floor(xs[i]/m)),int(np.floor(ys[i]/m)); ok=True
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for (px,py) in cells.get((cx+dx,cy+dy),()):
                    if (xs[i]-px)**2+(ys[i]-py)**2 < m*m: ok=False; break
                if not ok: break
            if not ok: break
        if ok: cells[(cx,cy)].append((xs[i],ys[i])); keep[i]=True
    return df[keep].copy()

allp=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allp[~allp['nonveg_landcover'].astype(bool)]
own=hab[hab.state==hab.src].drop_duplicates(subset=["longitude","latitude","year"]).reset_index(drop=True)
print("=== A: does I6 catch a --min-spacing-m override? pooled count at each spacing ===")
for m in (30,60,100,250,500):
    print(f"   pooled thin at {m:4d} m -> {len(thin(own,float(m))):5d}   (I6 band 6105..6355)")

print("\n=== B: NH negative candidates outside NH's BOXES entry (I5 / NH-box question) ===")
for r in REG:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    b=BOXES[r]
    out=c[(c.longitude<b[0])|(c.longitude>b[2])|(c.latitude<b[1])|(c.latitude>b[3])]
    print(f"   gbif_negatives_{r}: {len(c)} rows, OUTSIDE {r} box: {len(out)}")
    if len(out): print(out[["longitude","latitude","state"]].drop_duplicates().head(8).to_string())
    sel=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    o2=sel[(sel.longitude<b[0])|(sel.longitude>b[2])|(sel.latitude<b[1])|(sel.latitude>b[3])]
    print(f"     selected negatives_{r}: {len(sel)} rows, outside box: {len(o2)}")

print("\n=== C: I5 for NEGATIVES -- window containment in each region's raster ===")
for r in REG:
    with rasterio.open(f"data/landfire/{r}_2023_evt.tif") as s:
        H,W=s.shape; TT=Transformer.from_crs("EPSG:4326",s.crs,always_xy=True)
        for nm,p in (("negatives",f"data/negatives/negatives_{r}.csv"),
                     ("candidates",f"data/negatives/gbif_negatives_{r}.csv")):
            df=pd.read_csv(p)
            x,y=TT.transform(df.longitude.values,df.latitude.values)
            rows,cols=rasterio.transform.rowcol(s.transform,x,y); rows=np.asarray(rows);cols=np.asarray(cols)
            for half,lbl in ((32,"64"),(40,"80")):
                bad=int(((rows-half<0)|(rows+half>H)|(cols-half<0)|(cols+half>W)).sum())
                print(f"   {r} {nm} window {lbl}px not fully inside raster: {bad} of {len(df)}")
