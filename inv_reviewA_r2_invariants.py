"""ROUND 2: does CR-0006 v2's INVARIANT acceptance set pass on a pipeline that
violates the PA-0018 requirement it is supposed to enforce?

Non-compliant pipeline: thin PER REGION (as today), pool, de-duplicate,
then ONE global 3 km block grid + ONE draw.  This is exactly what v1's
simulation did and what the revision note says must not happen.
"""
import numpy as np, pandas as pd, geopandas as gpd
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
B,VF,SEED,MINSP=3000,0.2,42,30
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
def tag(df):
    g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(df.longitude,df.latitude),crs="EPSG:4326")
    j=gpd.sjoin(g,cty[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
    return pd.Series(j.STATEFP.map(FIPS).values,index=df.index)

# ---- NON-COMPLIANT: pool the EXISTING per-region-thinned files, dedup, global split
th=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(src=r) for r in R],ignore_index=True)
th["key"]=th.longitude.round(5).astype(str)+","+th.latitude.round(5).astype(str)
th["st"]=tag(th)
pool=th[th.st==th.src].copy()          # keep the own-state copy (the partition)
extra=th[(th.st!=th.src)&(~th.key.isin(set(pool.key)))].drop_duplicates("key")
pool=pd.concat([pool,extra],ignore_index=True).drop_duplicates("key")
x,y=t.transform(pool.longitude.values,pool.latitude.values); pool["x"],pool["y"]=x,y
pool["gblock"]=np.floor(pool.x/B).astype(int).astype(str)+"_"+np.floor(pool.y/B).astype(int).astype(str)
cnt=pool.gblock.value_counts(); order=cnt.sample(frac=1,random_state=SEED).index.tolist()
target=int(round(VF*len(pool))); vb=set(); run=0
for b in order:
    if run>=target: break
    vb.add(b); run+=cnt[b]
pool["split"]=np.where(pool.gblock.isin(vb),"val","train")
tr=pool[pool.split=="train"]; va=pool[pool.split=="val"]
d,_=cKDTree(tr[["x","y"]].values).query(va[["x","y"]].values,k=1)
print("=== NON-COMPLIANT pipeline (per-region thin, then pool, then ONE global split) ===")
print(f"  pooled positives {len(pool)}  occupied blocks {len(cnt)}  val {len(va)} ({len(va)/len(pool):.1%})")
print(f"  INV: pooled train/val coord collisions (5dp)      : {len(set(tr.key)&set(va.key))}   [invariant: 0]")
print(f"  INV: val positives with train positive within 30 m: {(d<=30).mean():.2%}          [invariant: 0.0%]")
print(f"  INV: within 300 m                                 : {(d<=300).mean():.2%}          [invariant: <=1.4%]")
print(f"  INV: validation fraction                          : {len(va)/len(pool):.1%}         [invariant: 20% +-1pp]")
per=pool.groupby('st').size().to_dict()
print(f"  INV: unique pooled coords == sum of per-region rows: {len(pool)} == {sum(per.values())} -> {len(pool)==sum(per.values())}")
print(f"  INV: state == polygon for every record            : trivially true (st comes from the polygon)")
# the invariant the set is MISSING:
tree=cKDTree(pool[["x","y"]].values)
pairs=tree.query_pairs(MINSP)
print(f"\n  *** MISSING INVARIANT: pairs of pooled positives closer than {MINSP} m: {len(pairs)}")
print(f"      records involved: {len(set([i for p in pairs for i in p]))}")
if pairs:
    ex=list(pairs)[:5]
    for i,j in ex:
        a,b2=pool.iloc[i],pool.iloc[j]
        dd=np.hypot(a.x-b2.x,a.y-b2.y)
        print(f"      {dd:6.1f} m apart: src {a.src}/{b2.src}  state {a.st}/{b2.st}  splits {a.split}/{b2.split}")
# ---- COMPLIANT reference: pooled thin, for comparison
