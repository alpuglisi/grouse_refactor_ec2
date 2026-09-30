import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd
REG=["ME","NH","VT"]
FIPS={"23":"ME","33":"NH","50":"VT"}
c=gpd.read_file("zip://data/roads/tl_2023_us_county.zip")
print("counties:",len(c), c.crs)
c=c[c.STATEFP.isin(FIPS)].copy()
c["ST"]=c.STATEFP.map(FIPS)
st=c.dissolve(by="ST").reset_index()[["ST","geometry"]]
print(st[["ST"]].to_string(), " bounds NH:", st[st.ST=="NH"].total_bounds)

def check(df,label):
    g=gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df.longitude,df.latitude), crs="EPSG:4326")
    j=gpd.sjoin(g, st, how="left", predicate="within")
    j=j[~j.index.duplicated()]
    bad_out = j.ST.isna()
    bad_mis = (~bad_out) & (j.ST != j.state)
    print(f"\n{label}: n={len(j)}  outside all 3 polygons: {bad_out.sum()}   state!=polygon: {bad_mis.sum()}")
    if bad_out.sum():
        print(j.loc[bad_out,["longitude","latitude","state"]].drop_duplicates().head(20).to_string())
    if bad_mis.sum():
        print(j.loc[bad_mis,["longitude","latitude","state","ST"]].drop_duplicates().head(20).to_string())
    return j

# positives: raw evaluated (all rows, all regions), unique coords
pos=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in REG],ignore_index=True)
pos=pos.drop_duplicates(subset=["longitude","latitude","state"])
check(pos,"POSITIVES (unique lon/lat/state from evaluated_sightings)")

# raw sightings files (the 43,024 the CR cites)
import glob
raws=[]
for f in sorted(glob.glob("data/sightings/*_sightings_*.csv")):
    d=pd.read_csv(f)
    stt=f.split("/")[-1].split("_")[0].upper()
    d["state"]=stt if "state" not in d.columns else d["state"]
    raws.append(d)
raw=pd.concat(raws,ignore_index=True)
print("\nraw sightings rows:",len(raw), "states:",raw.state.value_counts().to_dict())
check(raw.drop_duplicates(subset=["longitude","latitude","state"]),"RAW SIGHTINGS unique")

# negatives: selected + full candidate pools
neg=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in REG],ignore_index=True)
check(neg,"SELECTED NEGATIVES")
cand=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv") for r in REG],ignore_index=True)
cand=cand.drop_duplicates(subset=["longitude","latitude","state"])
j=check(cand,"NEGATIVE CANDIDATE POOL (unique lon/lat/state)")
