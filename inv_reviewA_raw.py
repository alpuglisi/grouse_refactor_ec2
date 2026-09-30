"""How many RAW sightings would the new state-polygon clip_to_region DROP?
(the CR measures 'records with no state' only on the final sampled sets)"""
import glob,os,re,pandas as pd,numpy as np,geopandas as gpd
from regions import BOXES
files=sorted(glob.glob("data/sightings/*_sightings_*.csv"))
rows=[]
for f in files:
    m=re.match(r"^([A-Za-z]{2})_sightings_(\d{4})\.csv$",os.path.basename(f))
    if not m: print("skip",f); continue
    d=pd.read_csv(f)
    lon=next(c for c in d.columns if 'lon' in c.lower()); lat=next(c for c in d.columns if 'lat' in c.lower())
    rows.append(pd.DataFrame({'longitude':d[lon],'latitude':d[lat],'file_state':m.group(1).upper(),'year':int(m.group(2))}))
s=pd.concat(rows,ignore_index=True).dropna(subset=['longitude','latitude'])
print("raw sightings:",len(s))
inany=np.zeros(len(s),bool)
for k,b in BOXES.items():
    m=(s.longitude.between(b[0],b[2])&s.latitude.between(b[1],b[3]))
    print(f"  in BOXES[{k}]: {int(m.sum())}")
    inany|=m.values
s=s[inany].copy()
print("in union of boxes:",len(s))
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
FIPS={"23":"ME","33":"NH","50":"VT"}
allst=cty.dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
g=gpd.GeoDataFrame(s.reset_index(drop=True),geometry=gpd.points_from_xy(s.longitude,s.latitude),crs="EPSG:4326")
j=gpd.sjoin(g,allst[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
s["statefp"]=j.STATEFP.values
s["region"]=s.statefp.map(FIPS)
print("\nrows by resolved STATEFP (top 10):"); print(s.statefp.fillna('OUTSIDE_US').value_counts().head(10).to_string())
drop=s.region.isna()
print(f"\nrows inside a BOX but in NO target-state polygon -> DROPPED by new clip_to_region: {int(drop.sum())} of {len(s)} ({100*drop.mean():.2f}%)")
u=s.assign(key=s.longitude.round(5).astype(str)+","+s.latitude.round(5).astype(str))
print(f"  unique coords dropped: {u[drop].key.nunique()} of {u.key.nunique()} unique coords in box union")
print("  their file_state:",s[drop].file_state.value_counts().to_dict())
