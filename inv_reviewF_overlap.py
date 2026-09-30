import geopandas as gpd, pandas as pd, numpy as np, glob, os, re
FIPS={"23":"ME","33":"NH","50":"VT"}
c=gpd.read_file("data/roads/tl_2023_us_county.zip"); c=c[c['STATEFP'].isin(FIPS)]
st=c.dissolve(by='STATEFP').reset_index(); st['s']=st['STATEFP'].map(FIPS); st=st.to_crs(4326)
import itertools
for a,b in itertools.combinations(["ME","NH","VT"],2):
    ga=st[st.s==a].geometry.iloc[0]; gb=st[st.s==b].geometry.iloc[0]
    inter=ga.intersection(gb)
    m=gpd.GeoSeries([inter],crs=4326).to_crs(5070).area.iloc[0]
    print(f"{a}&{b}: intersection area {m/1e6:.4f} km2, type {inter.geom_type}")
# full-US: does any other state's county polygon contain our points?
call=gpd.read_file("data/roads/tl_2023_us_county.zip")
allst=call.dissolve(by='STATEFP').reset_index().to_crs(4326)
files=sorted(glob.glob("data/sightings/*_sightings_*.csv")); rx=re.compile(r"^([A-Za-z]{2})_sightings_(\d{4})\.csv$")
L=[]
for f in files:
    m=rx.match(os.path.basename(f)); d=pd.read_csv(f,low_memory=False)
    lon=next(cc for cc in d.columns if 'lon' in cc.lower()); lat=next(cc for cc in d.columns if 'lat' in cc.lower())
    d=d.rename(columns={lon:'longitude',lat:'latitude'}); d['state']=m.group(1).upper()
    L.append(d[['longitude','latitude','state']])
raw=pd.concat(L,ignore_index=True).dropna(subset=['longitude','latitude'])
g=gpd.GeoDataFrame(raw,geometry=gpd.points_from_xy(raw.longitude,raw.latitude),crs=4326)
j=gpd.sjoin(g,allst[['STATEFP','geometry']],how='left',predicate='within')
cnt=j.groupby(level=0)['STATEFP'].nunique()
print("\nraw sightings matching >1 state polygon (all 50 states):",int((cnt>1).sum()))
fipsmap={v:k for k,v in FIPS.items()}
mism=j[j['STATEFP']!=j['state'].map(fipsmap)]
print("raw sightings whose containing STATEFP != filed state (all-US polygons):",len(mism))
print(mism.groupby(['state','STATEFP']).size().to_string())
# how many raw sightings are offshore (in a county 'water' area)? approximate: use ALAND/AWATER per county
j2=gpd.sjoin(g,call[['GEOID','STATEFP','ALAND','AWATER','geometry']],how='left',predicate='within')
print("\nrecords in no county at all:",int(j2['GEOID'].isna().sum()))
