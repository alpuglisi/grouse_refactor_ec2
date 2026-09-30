import glob,os,re,pandas as pd,numpy as np,geopandas as gpd
files=sorted(glob.glob("data/sightings/*_sightings_*.csv"))
rows=[]
for f in files:
    m=re.match(r"^([A-Za-z]{2})_sightings_(\d{4})\.csv$",os.path.basename(f))
    d=pd.read_csv(f)
    lon=next(c for c in d.columns if 'lon' in c.lower()); lat=next(c for c in d.columns if 'lat' in c.lower())
    rows.append(pd.DataFrame({'longitude':d[lon],'latitude':d[lat],'file_state':m.group(1).upper()}))
s=pd.concat(rows,ignore_index=True).dropna(subset=['longitude','latitude'])
cty=gpd.read_file("data/roads/tl_2023_us_county.zip"); FIPS={"23":"ME","33":"NH","50":"VT"}
allst=cty.dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
g=gpd.GeoDataFrame(s.reset_index(drop=True),geometry=gpd.points_from_xy(s.longitude,s.latitude),crs="EPSG:4326")
j=gpd.sjoin(g,allst[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
s["poly_state"]=j.STATEFP.map(FIPS).values
print(pd.crosstab(s.file_state,s.poly_state.fillna("NONE")).to_string())
dis=s.file_state!=s.poly_state
print(f"\nfile_state != polygon_state: {int(dis.sum())} of {len(s)} ({100*dis.mean():.3f}%)")
# negatives: GBIF state column vs polygon
for r in ["ME","NH","VT"]:
    n=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    gg=gpd.GeoDataFrame(n.reset_index(drop=True),geometry=gpd.points_from_xy(n.longitude,n.latitude),crs="EPSG:4326")
    jj=gpd.sjoin(gg,allst[["STATEFP","geometry"]],how="left",predicate="within"); jj=jj[~jj.index.duplicated()]
    ps=jj.STATEFP.map(FIPS).values
    print(f"neg {r}: 'state' col values {n['state'].value_counts().to_dict()}  polygon {pd.Series(ps).fillna('NONE').value_counts().to_dict()}  disagree {int((n['state'].values!=ps).sum())}")
