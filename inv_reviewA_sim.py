"""Independent re-derivation of CR-0006 section 'Evidence that the proposed fix works'."""
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.transform import rowcol
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
BLOCK_M, VAL_FRAC, SEED = 3000, 0.2, 42

cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
def statetag(lon,lat):
    g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon,lat),crs="EPSG:4326")
    j=gpd.sjoin(g,cty[["STATEFP","geometry"]],how="left",predicate="within")
    j=j[~j.index.duplicated()]
    return pd.Series(j.STATEFP.map(FIPS).values)

# ---------- A: reproduce the author's pooling of EXISTING split files ----------
rows=[]
for reg in R:
    for kind,pat in (("pos","data/pipeline/{s}_positives_%s.csv"%reg),
                     ("neg","data/negatives/{s}_negatives_%s.csv"%reg)):
        for sp in ("train","val"):
            d=pd.read_csv(pat.format(s=sp))[["longitude","latitude"]]
            d=d.assign(src_region=reg,kind=kind,old_split=sp)
            rows.append(d)
allr=pd.concat(rows,ignore_index=True)
allr["key"]=allr.longitude.round(5).astype(str)+","+allr.latitude.round(5).astype(str)
allr["state"]=statetag(allr.longitude.values,allr.latitude.values).values
print("=== A1 coverage ===")
print(f"pooled rows: {len(allr)}; records with no state: {int(allr.state.isna().sum())}")
print(allr.groupby('kind').state.apply(lambda s:int(s.isna().sum())).to_dict())
print("\n=== A2 region changes (rows) ===")
print(allr[allr.state.notna()&(allr.state!=allr.src_region)].groupby(["kind","src_region","state"]).size().to_string())
print("\n=== A3 dedup ===")
for kind in ("pos","neg"):
    k=allr[allr.kind==kind]
    print(f"  {kind}: {len(k)} rows -> {k.key.nunique()} unique coords (removes {len(k)-k.key.nunique()})")
print("\n=== A4 inside own state's BOX? ===")
from regions import BOXES
for st in R:
    s=allr[allr.state==st]; lo,la,hi,ha=BOXES[st]
    out=~(s.longitude.between(lo,hi)&s.latitude.between(la,ha))
    print(f"  {st}: {int(out.sum())} of {len(s)} outside BOXES['{st}']")
print("\n=== A5 full 64x64 window in own state's raster? ===")
import glob
for st in R:
    p=sorted(glob.glob(f"data/landfire/{st}_*_evt.tif"))[-1]
    with rasterio.open(p) as src:
        t=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
        s=allr[allr.state==st]
        x,y=t.transform(s.longitude.values,s.latitude.values)
        r,c=rowcol(src.transform,x,y); r,c=np.asarray(r),np.asarray(c)
        bad=((r-32<0)|(c-32<0)|(r+32>src.height)|(c+32>src.width))
        bad31=((r-32<0)|(c-32<0)|(r+31>=src.height)|(c+31>=src.width))
    print(f"  {st}: {int(bad.sum())} of {len(s)} lack full 64x64 in {p.split('/')[-1]} (strict variant: {int(bad31.sum())})")
print("\n=== A6 global block grid, one draw (author's method: pool EXISTING thinned) ===")
to5070=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def blocks_and_split(df):
    x,y=to5070.transform(df.longitude.values,df.latitude.values)
    df=df.assign(x=x,y=y)
    df["gblock"]=np.floor(x/BLOCK_M).astype(int).astype(str)+"_"+np.floor(y/BLOCK_M).astype(int).astype(str)
    counts=df.gblock.value_counts()
    order=counts.sample(frac=1,random_state=SEED).index.tolist()
    target=int(round(VAL_FRAC*len(df))); vb=set(); run=0
    for b in order:
        if run>=target: break
        vb.add(b); run+=counts[b]
    df["new_split"]=np.where(df.gblock.isin(vb),"val","train")
    return df,counts,vb
pos=allr[allr.kind=="pos"].drop_duplicates("key").copy()
pos,counts,vb=blocks_and_split(pos)
tr=pos[pos.new_split=="train"]; va=pos[pos.new_split=="val"]
print(f"  pooled unique positives {len(pos)}  occupied blocks {len(counts)}  val blocks {len(vb)}  val records {len(va)} ({len(va)/len(pos):.1%})")
print(f"  coords in BOTH train and val: {len(set(tr.key)&set(va.key))}")
d,_=cKDTree(tr[['x','y']].values).query(va[['x','y']].values,k=1)
for m in (30,300,3000): print(f"  val with train pos within {m:>5} m: {(d<=m):.0%}" if False else f"  val with train pos within {m:>5} m: {(d<=m).mean():6.2%}")
print("  val by state:",va.state.value_counts().to_dict())
