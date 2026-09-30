"""Independent check of bf8d31a: at random points inside MAINE that lie in the
NH grid, compare OLD NH road_dist, NEW NH road_dist, and ground truth computed
directly from the cached TIGER road shapefiles."""
import numpy as np, rasterio, geopandas as gpd, pandas as pd, glob
from pyproj import Transformer
from shapely.geometry import box
from scipy.spatial import cKDTree
from models import road_dist_decode
rng=np.random.default_rng(0)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
me=cty[cty.STATEFP=="23"].dissolve().geometry.iloc[0]
old="old_road_dist/NH_2024_road_dist.tif"; new="data/landfire/NH_2024_road_dist.tif"
with rasterio.open(new) as s: crs=s.crs; b=s.bounds
# sample random points in the NH grid, keep those inside Maine
t=Transformer.from_crs(crs,"EPSG:4326",always_xy=True)
pts=[]
while len(pts)<400:
    x=rng.uniform(b.left,b.right,4000); y=rng.uniform(b.bottom,b.top,4000)
    lon,lat=t.transform(x,y)
    g=gpd.GeoSeries(gpd.points_from_xy(lon,lat),crs="EPSG:4326")
    m=g.within(me).values
    for i in np.where(m)[0]:
        pts.append((x[i],y[i],lon[i],lat[i]))
        if len(pts)>=400: break
P=pd.DataFrame(pts,columns=["x","y","lon","lat"])
def samp(path):
    with rasterio.open(path) as s:
        v=np.array([val[0] for val in s.sample(list(zip(P.x,P.y)))]).astype(float)
        v[v==(s.nodata if s.nodata is not None else -9999)]=np.nan
    return v
vo=samp(old); vn=samp(new)
# ground truth: paved roads from every cached county intersecting a small buffer
MT=["S1100","S1200","S1400","S1630","S1640"]
frames=[]
for f in glob.glob("data/roads/tl_2023_*_roads.zip"):
    if "us_county" in f: continue
    d=gpd.read_file(f); d=d[d.MTFCC.isin(MT)]
    frames.append(d[["geometry"]])
roads=pd.concat(frames,ignore_index=True)
roads=gpd.GeoDataFrame(roads,geometry="geometry",crs=frames[0].crs).to_crs(crs)
print("truth road segments:",len(roads))
# densify road vertices to 30 m and use KD-tree (good to ~15 m)
from shapely import segmentize
seg=segmentize(roads.geometry.values,15.0)
xs=[];ys=[]
for g in seg:
    if g is None: continue
    if g.geom_type=="LineString": cs=[g.coords]
    else: cs=[p.coords for p in g.geoms]
    for c in cs:
        a=np.asarray(c); xs.append(a[:,0]); ys.append(a[:,1])
XY=np.column_stack([np.concatenate(xs),np.concatenate(ys)])
print("truth vertices:",len(XY))
tree=cKDTree(XY)
dtrue,_=tree.query(P[["x","y"]].values,k=1)
dold=road_dist_decode(vo); dnew=road_dist_decode(vn)
out=pd.DataFrame({"truth_m":dtrue,"old_m":dold,"new_m":dnew})
print(out.describe(percentiles=[.5]).round(1).to_string())
print("\nmedians: truth %.0f  OLD %.0f  NEW %.0f"%(np.nanmedian(dtrue),np.nanmedian(dold),np.nanmedian(dnew)))
print("median |new-truth| = %.0f m ; median |old-truth| = %.0f m"%(np.nanmedian(abs(dnew-dtrue)),np.nanmedian(abs(dold-dtrue))))
print("NaN (nodata) in NEW at Maine-side points:",int(np.isnan(dnew).sum()),"of",len(P))
