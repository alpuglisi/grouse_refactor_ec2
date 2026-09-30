"""Could the proposed support assertion actually DETECT BUG-0029?
Compare the metric on the CURRENT (defective) data and on a state-partitioned
version, at several block sizes, per region and pooled."""
import pandas as pd, numpy as np, geopandas as gpd
from pyproj import Transformer
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
def tag(df):
    g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(df.longitude,df.latitude),crs="EPSG:4326")
    j=gpd.sjoin(g,cty[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
    return pd.Series(j.STATEFP.map(FIPS).values,index=df.index)
def blk(df,B):
    x,y=t.transform(df.longitude.values,df.latitude.values)
    return set(zip(np.floor(np.asarray(x)/B).astype(int),np.floor(np.asarray(y)/B).astype(int)))
pos={r:pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in R}
neg={r:pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in R}
for r in R:
    pos[r]["st"]=tag(pos[r]); neg[r]["st"]=tag(neg[r])
for B in (3000,10000,30000):
    print(f"\n--- block {B/1000:.0f} km ---")
    for r in R:
        bp,bn=blk(pos[r],B),blk(neg[r],B)
        pp=pos[r][pos[r].st==r]; nn=neg[r][neg[r].st==r]
        bp2,bn2=blk(pp,B),blk(nn,B)
        print(f" {r}: DEFECTIVE pos-only-frac {len(bp-bn)/len(bp):.3f} J={len(bp&bn)/len(bp|bn):.3f}"
              f"   PARTITIONED pos-only-frac {len(bp2-bn2)/len(bp2):.3f} J={len(bp2&bn2)/len(bp2|bn2):.3f}")
