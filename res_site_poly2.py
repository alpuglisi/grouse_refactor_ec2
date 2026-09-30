"""Cheaper forms of verify_partition(): filter counties before dissolving."""
import time, resource
import numpy as np, pandas as pd, geopandas as gpd
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0
def tic(): return time.perf_counter()
def toc(t,l,e=""): print(f"{l:56s} {1000*(time.perf_counter()-t):9.1f} ms  maxRSS {rss():7.0f} MB  {e}")
T0=tic()
FIPS={"23":"ME","33":"NH","50":"VT"}
t=tic()
c = gpd.read_file("data/roads/tl_2023_us_county.zip",
                  columns=["STATEFP","geometry"])
toc(t,"read_file (columns=STATEFP,geometry)", f"{len(c)} rows crs={c.crs}")
t=tic()
c3 = c[c.STATEFP.isin(FIPS)]
st = c3.dissolve(by="STATEFP").reset_index()
st["state"]=st.STATEFP.map(FIPS)
toc(t,"filter to 3 states THEN dissolve", f"{len(c3)} counties -> {len(st)}")
t=tic()
st4326 = st.to_crs("EPSG:4326")
toc(t,"to_crs 4269->4326")
recs=[]
for r in ("ME","NH","VT"):
    for k,p in (("pos","data/pipeline/train_positives_%s.csv"),
                ("pos","data/pipeline/val_positives_%s.csv"),
                ("neg","data/negatives/train_negatives_%s.csv"),
                ("neg","data/negatives/val_negatives_%s.csv")):
        d=pd.read_csv(p%r); d["region"]=r; recs.append(d[["longitude","latitude","state","region"]])
all_=pd.concat(recs,ignore_index=True)
t=tic()
g = gpd.GeoDataFrame(all_, geometry=gpd.points_from_xy(all_.longitude, all_.latitude), crs="EPSG:4326")
j = gpd.sjoin(g, st4326[["state","geometry"]].rename(columns={"state":"poly_state"}),
              how="left", predicate="within")
toc(t,f"sjoin(within) {len(all_)} records")
bad=int((j.poly_state.isna()|(j.poly_state!=j.state)).sum())
print("   violations:",bad)
print(f"TOTAL {time.perf_counter()-T0:.2f}s maxRSS {rss():.0f} MB")
