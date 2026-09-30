"""Cost of I9 / verify_partition(): geopandas + 80 MB TIGER county zip."""
import time, resource
import numpy as np, pandas as pd
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0
def tic(): return time.perf_counter()
def toc(t,l,e=""): print(f"{l:52s} {1000*(time.perf_counter()-t):9.1f} ms  maxRSS {rss():7.0f} MB  {e}")

T0=tic()
t=tic(); import geopandas as gpd; toc(t,"import geopandas")
t=tic()
c = gpd.read_file("data/roads/tl_2023_us_county.zip")
toc(t,"read_file tl_2023_us_county.zip (80 MB)", f"{len(c)} counties")
t=tic()
st = c[["STATEFP","geometry"]].dissolve(by="STATEFP")
toc(t,"dissolve by STATEFP", f"{len(st)} states")
FIPS={"23":"ME","33":"NH","50":"VT"}
st = st.loc[list(FIPS)].reset_index()
st["state"]=st["STATEFP"].map(FIPS)

recs=[]
for r in ("ME","NH","VT"):
    for k,p in (("pos","data/pipeline/train_positives_%s.csv"),
                ("pos","data/pipeline/val_positives_%s.csv"),
                ("neg","data/negatives/train_negatives_%s.csv"),
                ("neg","data/negatives/val_negatives_%s.csv")):
        d=pd.read_csv(p%r); d["region"]=r; d["cls"]=k; recs.append(d[["longitude","latitude","state","region","cls"]])
all_=pd.concat(recs,ignore_index=True)
print("   records:",len(all_))
t=tic()
g = gpd.GeoDataFrame(all_, geometry=gpd.points_from_xy(all_.longitude, all_.latitude), crs="EPSG:4326")
j = gpd.sjoin(g, st[["state","geometry"]].rename(columns={"state":"poly_state"}),
              how="left", predicate="within")
toc(t,"points_from_xy + sjoin(within) 3 dissolved states", f"{len(j)} rows")
bad = int((j["poly_state"].isna() | (j["poly_state"]!=j["state"])).sum())
print(f"   verify_partition violations on today's selected records: {bad}")

# candidate-pool scale (35,678 in the CR; today's raw pools are larger)
cands=[]
for r in ("ME","NH","VT"):
    d=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    cands.append(d[["longitude","latitude","state"]])
cd=pd.concat(cands,ignore_index=True)
cd=cd.loc[~cd[["longitude","latitude"]].round(5).duplicated()].copy()
print("   deduped candidate pool:",len(cd))
t=tic()
gc = gpd.GeoDataFrame(cd, geometry=gpd.points_from_xy(cd.longitude, cd.latitude), crs="EPSG:4326")
jc = gpd.sjoin(gc, st[["state","geometry"]].rename(columns={"state":"poly_state"}),
               how="left", predicate="within")
toc(t,f"sjoin(within) over {len(cd)} pooled candidates")
badc = int((jc["poly_state"].isna() | (jc["poly_state"]!=jc["state"])).sum())
print(f"   candidate-pool violations: {badc}")
print(f"\nTOTAL {time.perf_counter()-T0:.2f}s maxRSS {rss():.0f} MB")
