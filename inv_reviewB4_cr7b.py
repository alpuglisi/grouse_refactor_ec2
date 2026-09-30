"""CR-0007 review part 2 (read-only): post-hygiene exception budget for
assertion (d) / verify_partition, and a demonstration of the duplicate
index-label hazard the generate_negatives pooling introduces."""
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
st=(cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index()
    .to_crs("EPSG:4326")); st["ST"]=st.STATEFP.map(FIPS)
def poly(d):
    g=gpd.GeoDataFrame(d.copy(),geometry=[Point(a,b) for a,b in
        zip(d.longitude,d.latitude)],crs="EPSG:4326")
    j=gpd.sjoin(g,st[["ST","geometry"]],how="left",predicate="within")
    return j[~j.index.duplicated()].ST.fillna("NONE").values
print("=== post-hygiene candidate pool: polygon mismatches per region ===")
for r in R:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    c=c[~(c.coord_uncertainty_m>1000).fillna(False)]
    c=c.loc[~c[["longitude","latitude"]].round(5).duplicated()]
    ps=poly(c); bad=int((ps!=r).sum())
    q={"ME":3088,"NH":1794,"VT":1809}[r]
    print(f"  {r}: {len(c)} post-hygiene candidates, {bad} with polygon != {r} "
          f"{pd.Series(ps[ps!=r]).value_counts().to_dict()}")
    print(f"      if all {bad} were drawn into a quota of ~{q}: gap "
          f"{100*bad/q:.3f} pp  "
          f"{'EXCEEDS the 0.5 pp gate' if 100*bad/q>0.5 else 'within the gate'}")
    exp = bad*q/len(c)
    print(f"      expected number drawn (hypergeometric mean) {exp:.2f} -> "
          f"gap {100*exp/q:.3f} pp")

print("\n=== weighted_take under duplicate index labels "
      "(generate_negatives.py:273-274) ===")
a=pd.DataFrame({"weight":[1.0]*4,"v":list("abcd")})
b=pd.DataFrame({"weight":[1.0]*4,"v":list("efgh")})
pooled_bad=pd.concat([a,b])                    # no ignore_index
pooled_ok=pd.concat([a,b],ignore_index=True)
rng=np.random.default_rng(0)
for name,p in (("pd.concat WITHOUT ignore_index",pooled_bad),
               ("pd.concat WITH ignore_index",pooled_ok)):
    sub=p
    n=3
    w=sub["weight"].values/sub["weight"].sum()
    idx=rng.choice(sub.index.values,size=n,replace=False,p=w)
    taken=sub.loc[idx]
    print(f"  {name}: index={list(sub.index)}")
    print(f"     rng.choice picked {list(idx)} (n={n}) -> .loc returned "
          f"{len(taken)} rows {list(taken.v)}"
          f"{'   <-- TARGET OVERSHOOT / DUPLICATES' if len(taken)!=n else ''}")
