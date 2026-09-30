"""Does running assertion (b) BEFORE filter_by_year_gap leave a hole?
Compare class support pre- and post-filter on the STATE-PARTITIONED data."""
import pandas as pd, numpy as np, geopandas as gpd, glob, re, os
from pyproj import Transformer
from models import FEATURE_SPEC
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}; TOL=2
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
def tag(d):
    g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(d.longitude,d.latitude),crs="EPSG:4326")
    j=gpd.sjoin(g,cty[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
    return pd.Series(j.STATEFP.map(FIPS).values,index=d.index)
def blk(d,B):
    x,y=t.transform(d.longitude.values,d.latitude.values)
    return set(zip(np.floor(np.asarray(x)/B).astype(int),np.floor(np.asarray(y)/B).astype(int)))
def ryears(reg,f):
    ys=[]
    for p in glob.glob(f"data/landfire/{reg}_*_{f}.tif"):
        m=re.match(rf"^{reg}_(\d{{4}})_{f}\.tif$",os.path.basename(p))
        if m: ys.append(int(m.group(1)))
    return ys
feats=sorted(FEATURE_SPEC)
for reg in R:
    yrs={f:ryears(reg,f) for f in feats}; yrs={f:v for f,v in yrs.items() if v}
    ok=lambda y: all(min(abs(a-int(y)) for a in v)<=TOL for v in yrs.values())
    pos=pd.read_csv(f"data/pipeline/thinned_positives_{reg}.csv")
    neg=pd.read_csv(f"data/negatives/negatives_{reg}.csv")
    pos=pos[tag(pos)==reg].copy(); neg=neg[tag(neg)==reg].copy()     # the partition
    kp=pos['year'].map(lambda y: True if pd.isna(y) else ok(y))
    kn=neg['year'].map(lambda y: True if pd.isna(y) else ok(y))
    for B in (3000,30000):
        bpre_p,bpre_n=blk(pos,B),blk(neg,B)
        bpo_p,bpo_n=blk(pos[kp],B),blk(neg[kn],B)
        print(f"{reg} @{B//1000:>2}km  PRE-filter  pos={len(pos):5d} neg={len(neg):5d} "
              f"pos-only-frac={len(bpre_p-bpre_n)/len(bpre_p):.3f} J={len(bpre_p&bpre_n)/len(bpre_p|bpre_n):.3f}")
        print(f"{reg} @{B//1000:>2}km  POST-filter pos={int(kp.sum()):5d} neg={int(kn.sum()):5d} "
              f"pos-only-frac={len(bpo_p-bpo_n)/len(bpo_p):.3f} J={len(bpo_p&bpo_n)/len(bpo_p|bpo_n):.3f}")
    print()
