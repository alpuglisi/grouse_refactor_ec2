import numpy as np, pandas as pd, geopandas as gpd, rasterio, glob
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
B,MINSP,SEED=3000,30,42
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def thin(df,min_m,seed):
    rng=np.random.default_rng(seed); order=rng.permutation(len(df))
    coords=df[['x','y']].values[order]
    kept=np.zeros(len(df),bool); kc=[]; tree=None
    for i,pt in enumerate(coords):
        keep=True if (tree is None or not kc) else (tree.query(pt,k=1)[0]>=min_m)
        if keep: kc.append(pt); kept[order[i]]=True; tree=cKDTree(np.array(kc))
    return df[kept].copy()

print("=== (1) Is reviewer B's 6,508 the result of RE-thinning the already-thinned pool? ===")
th=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(src=r) for r in R],ignore_index=True)
th["key"]=th.longitude.round(5).astype(str)+","+th.latitude.round(5).astype(str)
ded=th.drop_duplicates("key").copy()
x,y=t.transform(ded.longitude.values,ded.latitude.values); ded["x"],ded["y"]=x,y
print(f"  pooled already-thinned, deduped: {len(ded)}")
for s in (42,0,1):
    r2=thin(ded,MINSP,s); print(f"    re-thin at 30 m (seed {s}) -> {len(r2)}")

print("\n=== (2) Does a POOLED thin leave any pair < 30 m? (the missing invariant) ===")
ev=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in R],ignore_index=True)
ev["key"]=ev.longitude.round(5).astype(str)+","+ev.latitude.round(5).astype(str)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty2=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(ev.longitude,ev.latitude),crs="EPSG:4326")
j=gpd.sjoin(g,cty2[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
ev["st"]=j.STATEFP.map(FIPS).values
part=ev[ev.st==ev.src].drop_duplicates("key")
hab=part[~part.nonveg_landcover.astype(bool)].copy()
xx,yy=t.transform(hab.longitude.values,hab.latitude.values); hab["x"],hab["y"]=xx,yy
pt=thin(hab,MINSP,SEED)
tree=cKDTree(pt[["x","y"]].values)
pr=[p for p in tree.query_pairs(MINSP) ]
strict=[p for p in pr if np.hypot(pt.iloc[p[0]].x-pt.iloc[p[1]].x, pt.iloc[p[0]].y-pt.iloc[p[1]].y) < MINSP-1e-6]
print(f"  pooled thin output {len(pt)}; pairs <= 30 m: {len(pr)}; STRICTLY < 30 m: {len(strict)}")

print("\n=== (3) CR v2 section 8: what share of a box-wide availability sample is inside the state? ===")
allst=cty.dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
from regions import BOXES
rng=np.random.default_rng(0)
for reg in R:
    lo,la,hi,ha=BOXES[reg]
    # mirror analyze_grouse: uniform in the box, keep points with valid evt
    p=f"data/landfire/{reg}_2024_evt.tif"
    with rasterio.open(p) as s:
        tr=Transformer.from_crs("EPSG:4326",s.crs,always_xy=True)
        lon=rng.uniform(lo,hi,40000); lat=rng.uniform(la,ha,40000)
        xs,ys=tr.transform(lon,lat)
        v=np.array([a[0] for a in s.sample(zip(xs,ys))],dtype=float)
        ok=(v!=(s.nodata if s.nodata is not None else -9999))&np.isfinite(v)&(v!=0)
    lon,lat=lon[ok],lat[ok]
    gg=gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon,lat),crs="EPSG:4326")
    jj=gpd.sjoin(gg,allst[["STATEFP","geometry"]],how="left",predicate="within"); jj=jj[~jj.index.duplicated()]
    st=jj.STATEFP.map(FIPS)
    inside=(st==reg).mean()
    print(f"  {reg}: {ok.sum()} valid-evt background points; inside {reg} = {inside:.3f} "
          f"(CR claims ME .526 / NH .477 / VT .540); other states/none = {(st!=reg).mean():.3f}")
