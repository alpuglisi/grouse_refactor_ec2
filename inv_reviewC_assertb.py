"""Reviewer C: does CR-0006 assertion (b) actually discriminate?"""
import pandas as pd, geopandas as gpd, numpy as np
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
poly=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")

def polystate(df):
    g=gpd.GeoDataFrame(df[[]].copy(),geometry=gpd.points_from_xy(df.longitude,df.latitude),crs="EPSG:4326")
    j=gpd.sjoin(g,poly[["STATEFP","geometry"]],how="left",predicate="within")
    j=j[~j.index.duplicated()]
    return j.STATEFP.map(FIPS).fillna("none").values

pos={}; neg={}
for r in R:
    p=pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv") for s in ("train","val")],ignore_index=True)
    n=pd.concat([pd.read_csv(f"data/negatives/{s}_negatives_{r}.csv") for s in ("train","val")],ignore_index=True)
    p["poly"]=polystate(p); n["poly"]=polystate(n)
    pos[r]=p; neg[r]=n
    print(f"{r} pos n={len(p)} col={p.state.value_counts().to_dict()} poly={p.poly.value_counts().to_dict()}")
    print(f"{r} neg n={len(n)} col={n.state.value_counts().to_dict()} poly={n.poly.value_counts().to_dict()}")
    bad=n[n.state!=n.poly]
    if len(bad): print("   NEG state-col != polygon rows:\n",bad[["longitude","latitude","state","poly"]].to_string())
    badp=p[p.state!=p.poly]
    print(f"   POS state-col != polygon: {len(badp)}")

def assertb(pcount,ncount,label):
    keys=sorted(set(pcount)|set(ncount))
    P=sum(pcount.values()); N=sum(ncount.values())
    worst=0; det=[]
    for k in keys:
        a=100*pcount.get(k,0)/P; b=100*ncount.get(k,0)/N
        det.append(f"{k}: pos {a:.2f}% neg {b:.2f}% d={a-b:+.2f}pp")
        worst=max(worst,abs(a-b))
    print(f"  {label}: worst |d| = {worst:.2f} pp -> {'FAIL' if worst>5 else 'pass'}   [{'; '.join(det)}]")
    return worst

print("\n=== READING 1: per-REGION-UNIT, grouping by the `state` COLUMN (CR's example) ===")
for r in R:
    assertb(pos[r].state.value_counts().to_dict(), neg[r].state.value_counts().to_dict(), f"region {r} TODAY")
print("\n=== READING 1 post-fix (positives restricted to state==region; negatives unchanged) ===")
for r in R:
    pf=pos[r][pos[r].state==r]
    assertb(pf.state.value_counts().to_dict(), neg[r].state.value_counts().to_dict(), f"region {r} AFTER")

print("\n=== READING 1b: per-region-unit, grouping by POLYGON ===")
for r in R:
    assertb(pos[r].poly.value_counts().to_dict(), neg[r].poly.value_counts().to_dict(), f"region {r} TODAY(poly)")
for r in R:
    pf=pos[r][pos[r].poly==r]
    assertb(pf.poly.value_counts().to_dict(), neg[r].poly.value_counts().to_dict(), f"region {r} AFTER(poly)")

print("\n=== READING 2: POOLED over regions, grouping by the region FILE the record came from ===")
pc={r:len(pos[r]) for r in R}; nc={r:len(neg[r]) for r in R}
assertb(pc,nc,"pooled-by-file TODAY")
print("\n=== READING 3: POOLED, grouping by `state` column ===")
allp=pd.concat([pos[r] for r in R]); alln=pd.concat([neg[r] for r in R])
assertb(allp.state.value_counts().to_dict(), alln.state.value_counts().to_dict(),"pooled-by-statecol TODAY")
pf=pd.concat([pos[r][pos[r].state==r] for r in R])
assertb(pf.state.value_counts().to_dict(), alln.state.value_counts().to_dict(),"pooled-by-statecol AFTER(pos only repartitioned)")
