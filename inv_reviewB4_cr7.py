"""CR-0007 review (read-only): (d)'s 0.5 pp threshold under the negative
re-draw; the candidate pool's state/polygon integrity; whether pooled
candidate thinning really has 'no measured effect'; and the hash-split
val fraction change."""
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
st=(cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index()
    .to_crs("EPSG:4326")); st["ST"]=st.STATEFP.map(FIPS)
def poly(d):
    g=gpd.GeoDataFrame(d.copy(),geometry=[Point(a,b) for a,b in
        zip(d.longitude,d.latitude)],crs="EPSG:4326")
    j=gpd.sjoin(g,st[["ST","geometry"]],how="left",predicate="within")
    return j[~j.index.duplicated()].ST.fillna("NONE").values

print("=== 1. candidate pool: does the `state` column exist / vocabulary? ===")
cands={}
for r in R:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    cands[r]=c
    sc=c['state'].value_counts(dropna=False).to_dict() if 'state' in c.columns else "NO state COLUMN"
    print(f"  {r}: {len(c)} rows, state column -> {sc}")
tot=sum(len(c) for c in cands.values()); print(f"  pooled candidates: {tot}")

print("\n=== 2. candidate pool vs polygon (the (d) exception budget) ===")
bad_by={}
for r in R:
    c=cands[r]
    ps=poly(c)
    bad=int((ps!=r).sum()); bad_by[r]=bad
    print(f"  {r}: {bad} of {len(c)} candidates whose polygon != {r}  "
          f"{pd.Series(ps[ps!=r]).value_counts().to_dict()}")
print(f"  total mismatching candidates: {sum(bad_by.values())} of {tot} "
      f"(CR says 6 of 35,792)")

print("\n=== 3. (d) per-region polygon share gap, BEFORE and AFTER ===")
for r in R:
    p=pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv") for s in ("train","val")],ignore_index=True)
    n=pd.concat([pd.read_csv(f"data/negatives/{s}_negatives_{r}.csv") for s in ("train","val")],ignore_index=True)
    pp,nn=pd.Series(poly(p)),pd.Series(poly(n))
    keys=sorted(set(pp)|set(nn))
    a=pp.value_counts(normalize=True).reindex(keys,fill_value=0)*100
    b=nn.value_counts(normalize=True).reindex(keys,fill_value=0)*100
    gap=float((a-b).abs().max())
    print(f"  {r} BEFORE: max|delta| {gap:6.2f} pp -> "
          f"{'FAILS' if gap>0.5 else 'PASSES'} at 0.5 pp")
print("  AFTER (positives all own-state by polygon; negatives = drawn sample):")
for r in R:
    q=len(pd.read_csv(f"data/pipeline/train_positives_{r}.csv"))  # rough quota
    n_bad=bad_by[r]
    # worst case: every mismatching candidate lands in the draw
    print(f"    {r}: quota ~{q}, mismatching candidates {n_bad} -> worst-case "
          f"gap {100*n_bad/max(q,1):.3f} pp "
          f"{'(EXCEEDS 0.5)' if 100*n_bad/max(q,1)>0.5 else '(within 0.5)'}")

print("\n=== 4. does POOLED candidate thinning change anything? ===")
allc=[]
for r in R:
    c=cands[r].copy(); c["src"]=r
    c=c[~(c.coord_uncertainty_m>1000).fillna(False)]
    c=c.loc[~c[["longitude","latitude"]].round(5).duplicated()]
    allc.append(c)
allc=pd.concat(allc,ignore_index=True)
k=allc.longitude.round(5).astype(str)+","+allc.latitude.round(5).astype(str)
dup=int(k.duplicated().sum())
x,y=t.transform(allc.longitude.values,allc.latitude.values)
xy=np.column_stack([x,y])
pairs=cKDTree(xy).query_pairs(30.0)
cross=sum(1 for i,j in pairs if allc.src.iat[i]!=allc.src.iat[j])
print(f"  pooled candidates after per-file hygiene: {len(allc)}")
print(f"  exact duplicate coords ACROSS state files: {dup}")
print(f"  pairs < 30 m: {len(pairs)} total, {cross} of them CROSS-state")
print("  (CR says 'pooled negatives have 0 pairs under 30 m' - that was")
print("   measured on the SELECTED negatives, not the candidate pool)")

print("\n=== 5. hash-split val fraction: per-region today vs global ===")
for r in R:
    b=pd.read_csv(f"data/pipeline/block_assignments_{r}.csv")
    print(f"  {r}: {len(b)} blocks, val block fraction "
          f"{(b.split=='val').mean():.3f}")
print("  global (recomputed post-fix, from my round-1 sim): 0.190")
