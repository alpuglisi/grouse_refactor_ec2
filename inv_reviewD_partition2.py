import warnings; warnings.filterwarnings("ignore")
import glob, numpy as np, pandas as pd, geopandas as gpd
REG=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
c=gpd.read_file("zip://data/roads/tl_2023_us_county.zip")
c=c[c.STATEFP.isin(FIPS)].copy(); c["ST"]=c.STATEFP.map(FIPS)
st=c.dissolve(by="ST").reset_index()[["ST","geometry"]]

def check(df,label,lon="longitude",lat="latitude"):
    g=gpd.GeoDataFrame(df.copy(),geometry=gpd.points_from_xy(df[lon],df[lat]),crs="EPSG:4326")
    j=gpd.sjoin(g,st,how="left",predicate="within"); j=j[~j.index.duplicated()]
    out=j.ST.isna(); mis=(~out)&(j.ST!=j.state)
    print(f"\n{label}: n={len(j)}  outside all polygons: {out.sum()}  state!=polygon: {mis.sum()}")
    if out.sum(): print(j.loc[out,[lon,lat,'state']].drop_duplicates().head(15).to_string())
    if mis.sum(): print(j.loc[mis,[lon,lat,'state','ST']].drop_duplicates().head(15).to_string())
    return j

raws=[]
for f in sorted(glob.glob("data/sightings/*_sightings_*.csv")):
    d=pd.read_csv(f,low_memory=False)
    d["state"]=f.split("/")[-1].split("_")[0].upper()
    raws.append(d[["decimalLongitude","decimalLatitude","state","stateProvince","year"]])
raw=pd.concat(raws,ignore_index=True)
raw=raw.dropna(subset=["decimalLongitude","decimalLatitude"])
print("raw sightings rows:",len(raw))
check(raw.drop_duplicates(subset=["decimalLongitude","decimalLatitude","state"]),
      "RAW SIGHTINGS unique",lon="decimalLongitude",lat="decimalLatitude")

neg=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in REG],ignore_index=True)
check(neg,"SELECTED NEGATIVES (the 8,365 in data/negatives/negatives_*.csv)")
cand=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv") for r in REG],ignore_index=True)
print("\ncandidate pool rows:",len(cand))
check(cand.drop_duplicates(subset=["longitude","latitude","state"]),"NEGATIVE CANDIDATE POOL unique")
