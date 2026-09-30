import numpy as np, pandas as pd, geopandas as gpd, rasterio, os
from regions import BOXES
from analyze_grouse import sample_raster, ENVELOPE_SCHEME, NON_VEG_SCLASS_CODES
FIPS={"23":"ME","33":"NH","50":"VT"}
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
allst=cty.dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
needed=sorted({c for c,_ in ENVELOPE_SCHEME if c not in ("evt_phys","evt_group")}|{"sclass","evt"})
print("ENVELOPE_SCHEME needs:",needed)
for reg in ["ME","NH","VT"]:
    rng=np.random.default_rng(1); lo,la,hi,ha=BOXES[reg]
    lon=rng.uniform(lo,hi,20000); lat=rng.uniform(la,ha,20000)
    bg=pd.DataFrame({"longitude":lon,"latitude":lat})
    for f in needed:
        tif=f"data/landfire/{reg}_2024_{f}.tif"
        if not os.path.exists(tif): print("  missing",tif); continue
        bg[f]=sample_raster(tif,lon,lat)
    def frac(d):
        g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(d.longitude,d.latitude),crs="EPSG:4326")
        j=gpd.sjoin(g,allst[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
        return (j.STATEFP.map(FIPS)==reg).mean(), len(d)
    f_raw,n_raw=frac(bg)
    bgv=bg.dropna(subset=[c for c in needed if c in bg.columns])
    f_val,n_val=frac(bgv)
    bgh=bgv[~bgv['sclass'].isin(NON_VEG_SCLASS_CODES)]
    f_hab,n_hab=frac(bgh)
    print(f"  {reg}: raw box sample inside {reg} = {f_raw:.3f} (n={n_raw}) | after dropna = {f_val:.3f} (n={n_val}) | after non-veg drop = {f_hab:.3f} (n={n_hab})")
