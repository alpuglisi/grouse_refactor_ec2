"""For positives whose REGION CHANGES under the partition, compare the 64x64
window they get now (old region raster) with the one they would get (new
region raster): nodata fraction and center-pixel value."""
import pandas as pd, numpy as np, rasterio, geopandas as gpd
from rasterio.windows import Window
from pyproj import Transformer
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
rows=[]
for r in R:
    p=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")[["longitude","latitude"]]
    rows.append(p.assign(src=r))
P=pd.concat(rows,ignore_index=True)
g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(P.longitude,P.latitude),crs="EPSG:4326")
j=gpd.sjoin(g,cty[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
P["st"]=j.STATEFP.map(FIPS).values
ch=P[P.st.notna()&(P.st!=P.src)]
print("positives whose region changes:",len(ch), ch.groupby(['src','st']).size().to_dict())
samp=ch.sample(min(300,len(ch)),random_state=0)
def win(feat,reg,lon,lat,size=64):
    path=f"data/landfire/{reg}_2024_{feat}.tif"
    with rasterio.open(path) as s:
        t=Transformer.from_crs("EPSG:4326",s.crs,always_xy=True)
        x,y=t.transform(lon,lat); rr,cc=s.index(x,y)
        h=size//2
        a=s.read(1,window=Window(cc-h,rr-h,size,size),boundless=True,
                 fill_value=s.nodata if s.nodata is not None else -9999).astype(float)
        nd=s.nodata if s.nodata is not None else -9999
        return (a==nd).mean(), a[h,h]
for feat in ("evt","road_dist"):
    o=[];n=[];co=[];cn=[]
    for _,row in samp.iterrows():
        a,b=win(feat,row.src,row.longitude,row.latitude); o.append(a); co.append(b)
        a,b=win(feat,row.st,row.longitude,row.latitude);  n.append(a); cn.append(b)
    o=np.array(o);n=np.array(n);co=np.array(co);cn=np.array(cn)
    print(f"\n{feat}: mean window-nodata frac OLD region {o.mean():.4f}  NEW region {n.mean():.4f}")
    print(f"  records whose window gains >1% nodata after reassignment: {(n-o>0.01).sum()} of {len(samp)}; max gain {(n-o).max():.3f}")
    diff = co!=cn
    print(f"  centre-pixel value CHANGES for {int(diff.sum())} of {len(samp)} ({100*diff.mean():.1f}%)")
    if feat=="road_dist":
        from models import road_dist_decode
        mo=road_dist_decode(co.astype(float)); mn=road_dist_decode(cn.astype(float))
        ok=(co!=-9999)&(cn!=-9999)
        print(f"  road_dist metres: median OLD {np.median(mo[ok]):.0f}  NEW {np.median(mn[ok]):.0f}  median |diff| {np.median(abs(mo-mn)[ok]):.0f} m")
