"""R3-JOB3: v3 claims 'the six regenerations change NO training input at all'
(Why now / Risk table), evidenced by '0 of 6,702 records have a nodata evt pixel
in their 64x64 window'.  But § Coverage says evt-nodata is the WRONG reference.
Re-measure against the NLCD footprint, and check road_dist separately."""
import rasterio, numpy as np, pandas as pd, geopandas as gpd
R=["ME","NH","VT"]
IMG=64; HALF=IMG//2
recs={}
for r in R:
    p=pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv") for s in ("train","val")],ignore_index=True)
    n=pd.concat([pd.read_csv(f"data/negatives/{s}_negatives_{r}.csv") for s in ("train","val")],ignore_index=True)
    recs[r]=(p,n)
print("=== records whose 64x64 window touches OUTSIDE the NLCD footprint, or has an out-of-coverage CENTRE")
for r in R:
    with rasterio.open(f"data/landfire/{r}_2016_nlcd.tif") as s:
        nl=s.read(1); inv=~s.transform
        valid=nl!=-9999
    # integral image of the INVALID mask for fast window sums
    ii=np.cumsum(np.cumsum((~valid).astype(np.int32),0),1)
    Hh,Ww=valid.shape
    def winbad(lons,lats):
        cols,rows=[],[]
        for x,y in zip(lons,lats): pass
        import rasterio.warp as rw
        xs,ys=rw.transform(  # lonlat -> raster crs
            "EPSG:4326", rasterio.open(f"data/landfire/{r}_2016_nlcd.tif").crs, list(lons), list(lats))
        with rasterio.open(f"data/landfire/{r}_2016_nlcd.tif") as s:
            rr,cc=rasterio.transform.rowcol(s.transform,xs,ys)
        rr=np.asarray(rr); cc=np.asarray(cc)
        r0=np.clip(rr-HALF,0,Hh-1); r1=np.clip(rr+HALF-1,0,Hh-1)
        c0=np.clip(cc-HALF,0,Ww-1); c1=np.clip(cc+HALF-1,0,Ww-1)
        def S(a,b):
            a=np.clip(a,0,Hh-1); b=np.clip(b,0,Ww-1); return ii[a,b]
        tot=S(r1,c1)-np.where(r0>0,S(r0-1,c1),0)-np.where(c0>0,S(r1,c0-1),0)+np.where((r0>0)&(c0>0),S(r0-1,c0-1),0)
        centre_bad=~valid[np.clip(rr,0,Hh-1),np.clip(cc,0,Ww-1)]
        offgrid=(rr<0)|(rr>=Hh)|(cc<0)|(cc>=Ww)
        return tot, centre_bad, offgrid
    for name,df in (("pos",recs[r][0]),("neg",recs[r][1])):
        tot,cb,og=winbad(df.longitude.values,df.latitude.values)
        print(f"  {r} {name} n={len(df):5d} | windows touching out-of-coverage: {int((tot>0).sum()):5d} "
              f"({100*(tot>0).mean():5.2f}%) | centre out-of-coverage: {int(cb.sum())} | off-grid: {int(og.sum())}")
print("\n=== road_dist: ME/VT regeneration changes IN-US values (roads from neighbouring states)")
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
FIPS={"23":"ME","33":"NH","50":"VT"}
for r in R:
    own=cty[cty.STATEFP=={v:k for k,v in FIPS.items()}[r]].dissolve().to_crs("EPSG:5070").geometry.iloc[0]
    bnd=own.boundary
    for name,df in (("pos",recs[r][0]),("neg",recs[r][1])):
        g=gpd.GeoSeries(gpd.points_from_xy(df.longitude,df.latitude),crs="EPSG:4326").to_crs("EPSG:5070")
        d=g.distance(bnd)
        print(f"  {r} {name}: within 2km of the state boundary {int((d<2000).sum()):5d} ({100*(d<2000).mean():5.2f}%) | "
              f"5km {int((d<5000).sum()):5d} ({100*(d<5000).mean():5.2f}%) | 10km {int((d<10000).sum()):5d}")
