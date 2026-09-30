"""After the state partition, is every state-filed record still inside its own
region's BOX (= its raster grid extent)?  And does the state polygon itself
stick out of the box?"""
import glob,os,re,pandas as pd,numpy as np,geopandas as gpd,rasterio
import sys; sys.path.insert(0,"/home/ec2-user/grouse2")
from regions import BOXES
from shapely.geometry import box as shbox
rows=[]
for f in sorted(glob.glob("data/sightings/*_sightings_*.csv")):
    m=re.match(r'^([A-Za-z]{2})_sightings_(\d{4})\.csv$',os.path.basename(f))
    d=pd.read_csv(f,low_memory=False).rename(columns={'decimalLongitude':'longitude','decimalLatitude':'latitude'})
    d['state']=m.group(1).upper(); rows.append(d[['longitude','latitude','state']])
raw=pd.concat(rows,ignore_index=True).dropna(subset=['longitude','latitude'])
print("raw:",len(raw))
for st,b in BOXES.items():
    s=raw[raw.state==st]
    out=~(s.longitude.between(b[0],b[2]) & s.latitude.between(b[1],b[3]))
    print(f"{st}: {out.sum()} of {len(s)} state-filed records OUTSIDE BOXES[{st}]")
    if out.sum():
        print(s[out][['longitude','latitude']].describe().loc[['min','max']].to_string())
# negatives
for st,b in BOXES.items():
    n=pd.read_csv(f"data/negatives/gbif_negatives_{st}.csv")
    out=~(n.longitude.between(b[0],b[2]) & n.latitude.between(b[1],b[3]))
    print(f"{st} gbif negatives: {out.sum()} of {len(n)} OUTSIDE BOXES[{st}]")
# polygon vs box
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
FIPS={"23":"ME","33":"NH","50":"VT"}
for fp,st in FIPS.items():
    g=cty[cty.STATEFP==fp].dissolve().to_crs("EPSG:4326").geometry.iloc[0]
    bb=shbox(*[BOXES[st][0],BOXES[st][1],BOXES[st][2],BOXES[st][3]])
    outside=g.difference(bb)
    print(f"{st}: polygon bounds {tuple(round(v,4) for v in g.bounds)} box {BOXES[st]} "
          f"| polygon area outside box = {100*outside.area/g.area:.3f}%")
# also: raster grid footprint vs box (does the grid actually cover the box?)
from grouse_data import GrouseData
for st in FIPS.values():
    rd=GrouseData()[st]
    with rasterio.open(rd.latest_raster_path("evt")) as s:
        from rasterio.warp import transform_bounds
        bb=transform_bounds(s.crs,"EPSG:4326",*s.bounds)
    print(f"{st} evt raster lonlat bounds {tuple(round(v,4) for v in bb)}  box {BOXES[st]}")
