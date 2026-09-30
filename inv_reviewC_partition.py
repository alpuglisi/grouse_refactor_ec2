"""Reviewer C: independent check of the CR's partition-key claim."""
import glob, os, re, pandas as pd, geopandas as gpd, numpy as np
from shapely.geometry import Point

DATA="/home/ec2-user/grouse2/"
files=sorted(glob.glob(DATA+"data/sightings/*_sightings_*.csv"))
rows=[]
for f in files:
    m=re.match(r'^([A-Za-z]{2})_sightings_(\d{4})\.csv$',os.path.basename(f))
    st=m.group(1).upper(); yr=int(m.group(2))
    d=pd.read_csv(f,low_memory=False)
    d=d.rename(columns={'decimalLongitude':'longitude','decimalLatitude':'latitude'})
    d['state_fname']=st; d['year']=yr
    rows.append(d[['longitude','latitude','state_fname','year','stateProvince','countryCode']])
raw=pd.concat(rows,ignore_index=True).dropna(subset=['longitude','latitude'])
print("raw rows (post lon/lat dropna):",len(raw))
print("stateProvince vs filename mismatches:",
      int((raw.stateProvince.str.strip().map({'Maine':'ME','New Hampshire':'NH','Vermont':'VT'})!=raw.state_fname).sum()))

cty=gpd.read_file(DATA+"data/roads/tl_2023_us_county.zip")
FIPS={"23":"ME","33":"NH","50":"VT"}
sub=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
allst=cty.dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")

g=gpd.GeoDataFrame(raw.copy(),geometry=gpd.points_from_xy(raw.longitude,raw.latitude),crs="EPSG:4326")
j=gpd.sjoin(g,sub[["STATEFP","geometry"]],how="left",predicate="within")
j=j[~j.index.duplicated()]
j["poly3"]=j.STATEFP.map(FIPS)
print("\n--- 3-state polygon join ---")
print("no polygon (outside ME/NH/VT):",int(j.poly3.isna().sum()))
print("disagreements:",int((j.poly3.notna()&(j.poly3!=j.state_fname)).sum()))
print("agreement:",int((j.poly3==j.state_fname).sum()),"of",len(j))

# where do the no-polygon points land against ALL US states?
nb=j[j.poly3.isna()]
if len(nb):
    g2=gpd.GeoDataFrame(nb[['longitude','latitude','state_fname']],
        geometry=gpd.points_from_xy(nb.longitude,nb.latitude),crs="EPSG:4326")
    j2=gpd.sjoin(g2,allst[["STATEFP","geometry"]],how="left",predicate="within")
    j2=j2[~j2.index.duplicated()]
    print("\nno-3state points: their STATEFP among all US counties:")
    print(j2.groupby(['state_fname','STATEFP'],dropna=False).size().to_string())
    print(nb[['longitude','latitude','state_fname']].head(20).to_string())

# distance of every record to its filed state's polygon (to detect near-misses)
m=sub.to_crs("EPSG:5070").set_index('STATEFP')
gm=g.to_crs("EPSG:5070")
for fips,st in FIPS.items():
    pts=gm[gm.state_fname==st]
    dd=pts.distance(m.loc[fips,'geometry'])
    print(f"\n{st}: n={len(pts)} dist_to_own_polygon m: max={dd.max():.1f} "
          f">0 count={(dd>0).sum()} >100m={(dd>100).sum()}")
