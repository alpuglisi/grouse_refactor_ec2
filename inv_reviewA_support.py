"""Would the proposed 'class support comparison' assertion be thresholdable?
Occupied 3 km blocks for positives vs negatives, on the CURRENT data and on a
state-partitioned pooled version."""
import pandas as pd, numpy as np, geopandas as gpd
from pyproj import Transformer
R=["ME","NH","VT"]; B=3000
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def blk(df):
    x,y=t.transform(df.longitude.values,df.latitude.values)
    return set(zip(np.floor(x/B).astype(int),np.floor(y/B).astype(int)))
allp=[];alln=[]
for r in R:
    p=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
    n=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    bp,bn=blk(p),blk(n)
    j=len(bp&bn)/len(bp|bn)
    print(f"{r}: pos blocks {len(bp)}, neg blocks {len(bn)}, shared {len(bp&bn)}, Jaccard {j:.3f}, "
          f"pos-only {len(bp-bn)}, neg-only {len(bn-bp)}")
    allp.append(p); alln.append(n)
P=pd.concat(allp); N=pd.concat(alln)
bp,bn=blk(P),blk(N)
print(f"POOLED: pos blocks {len(bp)}, neg blocks {len(bn)}, shared {len(bp&bn)}, Jaccard {len(bp&bn)/len(bp|bn):.3f}")
print(f"  frac of pos blocks with no negative: {len(bp-bn)/len(bp):.3f}")
print(f"  frac of neg blocks with no positive: {len(bn-bp)/len(bn):.3f}")
# coarser: 10 km and 30 km
for B2 in (10000,30000):
    def blk2(df):
        x,y=t.transform(df.longitude.values,df.latitude.values)
        return set(zip(np.floor(x/B2).astype(int),np.floor(y/B2).astype(int)))
    a,b=blk2(P),blk2(N)
    print(f"  at {B2/1000:.0f} km: pos {len(a)} neg {len(b)} Jaccard {len(a&b)/len(a|b):.3f} pos-only frac {len(a-b)/len(a):.3f}")
