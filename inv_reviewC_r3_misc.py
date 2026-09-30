"""R3: (a) verify §8's corrected availability figures; (b) sensitivity of §6(c)'s
0.035 threshold to the block-grid origin this CR changes."""
import numpy as np, pandas as pd, geopandas as gpd, sys
sys.path.insert(0,".")
import analyze_grouse as ag
from regions import BOXES
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
FIPS={"ME":"23","NH":"33","VT":"50"}
poly={r:cty[cty.STATEFP==f].dissolve().to_crs("EPSG:4326").geometry.iloc[0] for r,f in FIPS.items()}
print("=== (a) background_envelope_sample-equivalent in-state share (post dropna + nonveg drop)")
xw=ag.load_evt_crosswalk(ag.RASTER_DIR)
for r in ("ME","NH","VT"):
    rng=np.random.default_rng(1); a,b,c,d=BOXES[r]
    lons=rng.uniform(a,c,ag.BACKGROUND_N); lats=rng.uniform(b,d,ag.BACKGROUND_N)
    import glob,os,re
    yrs={}
    for p in glob.glob(f"data/landfire/{r}_*_*.tif"):
        m=re.match(rf'^{r}_(\d{{4}})_(.+)\.tif$',os.path.basename(p))
        if m: yrs.setdefault(m.group(2),[]).append(int(m.group(1)))
    vals={}
    for f in ("evt","evh","sclass"):
        y=max(yrs[f]); vals[f]=ag.sample_raster(f"data/landfire/{r}_{y}_{f}.tif",lons,lats)
    df=pd.DataFrame(dict(longitude=lons,latitude=lats,**vals))
    n0=len(df); df=df.dropna()
    n1=len(df)
    ph=pd.Series(df.evt.astype(int)).map(xw["phys"]) if xw else pd.Series("",index=df.index)
    nonveg=df.sclass.isin(ag.NON_VEG_SCLASS_CODES) | ag.is_evt_phys_nonveg(ph)
    df=df[~nonveg.values]
    g=gpd.GeoSeries(gpd.points_from_xy(df.longitude,df.latitude),crs="EPSG:4326")
    inside=g.within(poly[r])
    print(f"  {r}: {n0} drawn -> {n1} after dropna -> {len(df)} after non-veg drop | "
          f"in-state share {100*inside.mean():.1f}%   (CR v3 says ME 95.9 / NH 53.2 / VT 55.2)")
print("\n=== (b) §6(c) 30 km pos-only fraction: sensitivity to block-grid origin")
from pyproj import Transformer
def frac(r, origin, bs=30000.0, partition=False):
    p=pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv") for s in ("train","val")],ignore_index=True)
    n=pd.concat([pd.read_csv(f"data/negatives/{s}_negatives_{r}.csv") for s in ("train","val")],ignore_index=True)
    if partition: p=p[p.state==r]
    x0,y0=origin
    B=lambda d:set(zip(np.floor((d.x_5070-x0)/bs).astype(int),np.floor((d.y_5070-y0)/bs).astype(int)))
    P,N=B(p),B(n); U=P|N
    return len(P-N)/len(U), len(P&N)/len(U), len(U)
for r in ("ME","NH","VT"):
    a,b,c,d=BOXES[r]
    t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
    cx,cy=t.transform([a,c],[b,d]); boxorg=(min(cx),min(cy))
    for label,org in (("box-anchored",boxorg),("global 0,0",(0.0,0.0))):
        for lab2,part in (("before",False),("after ",True)):
            po,jac,nb=frac(r,org,partition=part)
            print(f"  {r} {label:13s} {lab2}: pos-only={po:.4f} jaccard={jac:.4f} blocks={nb}")
