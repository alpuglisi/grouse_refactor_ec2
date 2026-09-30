import pandas as pd, numpy as np, geopandas as gpd, glob, os, re
from shapely.geometry import box as sbox
from regions import BOXES
FIPS={"23":"ME","33":"NH","50":"VT"}
c=gpd.read_file("data/roads/tl_2023_us_county.zip"); c=c[c['STATEFP'].isin(FIPS)]
st=c.dissolve(by='STATEFP').reset_index(); st['state']=st['STATEFP'].map(FIPS); st=st.to_crs(4326)
nh=st[st.state=='NH'].geometry.iloc[0]
for name,margin_px in [("box",0),("box+32px(30m)",32)]:
    for r in ["NH"]:
        mnx,mny,mxx,mxy=BOXES[r]
        poly=st[st.state==r].geometry.iloc[0]
        # margin in degrees approx: compute in 5070
        g=gpd.GeoSeries([sbox(mnx,mny,mxx,mxy)],crs=4326).to_crs(5070)
        if margin_px: g=g.buffer(-margin_px*30.0)   # inward margin: window must fit
        b=g.to_crs(4326).iloc[0]
        p=gpd.GeoSeries([poly],crs=4326).to_crs(5070).iloc[0]
        bb=gpd.GeoSeries([b],crs=4326).to_crs(5070).iloc[0]
        outside=p.difference(bb)
        print(f"{r} {name}: polygon area {p.area/1e6:.1f} km2, outside {outside.area/1e6:.4f} km2 = {100*outside.area/p.area:.4f}%")
# records in the sliver
neg=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv").assign(_reg=r) for r in ["ME","NH","VT"]],ignore_index=True)
cand=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv").assign(_reg=r) for r in ["ME","NH","VT"]],ignore_index=True)
files=sorted(glob.glob("data/sightings/*_sightings_*.csv")); rx=re.compile(r"^([A-Za-z]{2})_sightings_(\d{4})\.csv$")
L=[]
for f in files:
    m=rx.match(os.path.basename(f))
    d=pd.read_csv(f,low_memory=False)
    lon=next(cc for cc in d.columns if 'lon' in cc.lower()); lat=next(cc for cc in d.columns if 'lat' in cc.lower())
    d=d.rename(columns={lon:'longitude',lat:'latitude'}); d['state']=m.group(1).upper()
    L.append(d[['longitude','latitude','state']])
raw=pd.concat(L,ignore_index=True).dropna(subset=['longitude','latitude'])
for nm,d in [("raw sightings",raw),("final negatives",neg),("candidate pool",cand)]:
    for r in ["ME","NH","VT"]:
        mnx,mny,mxx,mxy=BOXES[r]
        sub=d[d.state==r]
        out=sub[~(sub.longitude.between(mnx,mxx)&sub.latitude.between(mny,mxy))]
        if len(out): print(f"{nm}: state=={r} records OUTSIDE {r}'s BOXES entry: {len(out)}  lon range [{out.longitude.min():.5f},{out.longitude.max():.5f}]")
        else: print(f"{nm}: state=={r} records outside {r}'s box: 0")
# 32px inward margin version
print()
for nm,d in [("raw sightings",raw),("final negatives",neg)]:
    for r in ["ME","NH","VT"]:
        mnx,mny,mxx,mxy=BOXES[r]
        g=gpd.GeoSeries([sbox(mnx,mny,mxx,mxy)],crs=4326).to_crs(5070).buffer(-32*30.0).to_crs(4326).iloc[0]
        sub=d[d.state==r]
        pts=gpd.GeoDataFrame(sub,geometry=gpd.points_from_xy(sub.longitude,sub.latitude),crs=4326)
        n=int((~pts.within(g)).sum())
        print(f"{nm}: state=={r} records NOT 32px-inside {r}'s box: {n}")
