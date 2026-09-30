import pandas as pd, numpy as np, geopandas as gpd, glob, os, re
from shapely.geometry import Point
FIPS={"23":"ME","33":"NH","50":"VT"}
c=gpd.read_file("data/roads/tl_2023_us_county.zip")
c=c[c['STATEFP'].isin(FIPS)]
st=c.dissolve(by='STATEFP').reset_index()
st['state']=st['STATEFP'].map(FIPS)
st=st.to_crs(4326)
print("dissolved polygons:",dict(zip(st.state,st.geometry.geom_type)))
for _,r in st.iterrows():
    b=r.geometry.bounds
    print(f"  {r.state} bounds lon[{b[0]:.5f},{b[2]:.5f}] lat[{b[1]:.5f},{b[3]:.5f}]")
# ---- raw sightings
files=sorted(glob.glob("data/sightings/*_sightings_*.csv"))
rx=re.compile(r"^([A-Za-z]{2})_sightings_(\d{4})\.csv$")
L=[]
for f in files:
    m=rx.match(os.path.basename(f))
    if not m: print("skip",f); continue
    d=pd.read_csv(f,low_memory=False)
    lon=next(cc for cc in d.columns if 'lon' in cc.lower()); lat=next(cc for cc in d.columns if 'lat' in cc.lower())
    d=d.rename(columns={lon:'longitude',lat:'latitude'})
    d['state']=m.group(1).upper(); d['year']=int(m.group(2))
    keep=['longitude','latitude','state','year']
    if 'stateProvince' in d.columns: keep.append('stateProvince')
    L.append(d[keep])
raw=pd.concat(L,ignore_index=True).dropna(subset=['longitude','latitude'])
print("\nraw sightings loaded:",len(raw))
if 'stateProvince' in raw.columns:
    mp={"Maine":"ME","New Hampshire":"NH","Vermont":"VT"}
    print("  stateProvince vs filename state mismatches:",int((raw['stateProvince'].map(mp)!=raw['state']).sum()))
    print("  stateProvince values:",raw['stateProvince'].value_counts().to_dict())
g=gpd.GeoDataFrame(raw,geometry=gpd.points_from_xy(raw.longitude,raw.latitude),crs=4326)
j=gpd.sjoin(g,st[['state','geometry']].rename(columns={'state':'poly_state'}),how='left',predicate='within')
j=j[~j.index.duplicated()]
print("  within-agreement:",int((j['poly_state']==j['state']).sum()),"/",len(j))
print("  outside all polygons:",int(j['poly_state'].isna().sum()))
print("  disagree (in a different polygon):",int(((~j['poly_state'].isna())&(j['poly_state']!=j['state'])).sum()))
# max distance to own polygon
stm=st.to_crs(5070).set_index('state')
gm=g.to_crs(5070)
mx=0
for s in ["ME","NH","VT"]:
    sub=gm[gm.state==s]
    d=sub.distance(stm.loc[s,'geometry'])
    print(f"  {s}: n={len(sub)} max dist to own polygon = {d.max():.3f} m")
    mx=max(mx,d.max())
print("  overall max dist to own polygon:",round(mx,3),"m")
# ---- candidate pool (gbif_negatives)
cand=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv").assign(_reg=r) for r in ["ME","NH","VT"]],ignore_index=True)
print("\ncandidate pool rows:",len(cand),"cols:",list(cand.columns)[:12])
cg=gpd.GeoDataFrame(cand,geometry=gpd.points_from_xy(cand.longitude,cand.latitude),crs=4326)
cj=gpd.sjoin(cg,st[['state','geometry']].rename(columns={'state':'poly_state'}),how='left',predicate='within')
cj=cj[~cj.index.duplicated()]
bad=cj[(cj['poly_state'].isna())|(cj['poly_state']!=cj['state'])]
print("  candidate pool failures:",len(bad),"of",len(cj))
print(bad[['longitude','latitude','state','poly_state']].to_string())
# ---- final negatives
neg=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv").assign(_reg=r) for r in ["ME","NH","VT"]],ignore_index=True)
ng=gpd.GeoDataFrame(neg,geometry=gpd.points_from_xy(neg.longitude,neg.latitude),crs=4326)
nj=gpd.sjoin(ng,st[['state','geometry']].rename(columns={'state':'poly_state'}),how='left',predicate='within')
nj=nj[~nj.index.duplicated()]
nbad=nj[(nj['poly_state'].isna())|(nj['poly_state']!=nj['state'])]
print("\n  final negatives rows:",len(nj)," failures:",len(nbad))
print(nbad[['longitude','latitude','state','poly_state','_reg']].to_string())
print("  negatives state vs filing region mismatches:",int((neg['state']!=neg['_reg']).sum()))
