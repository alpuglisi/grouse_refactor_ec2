"""Do the SAME ground coordinate's derived attributes differ between region files?
(each region has its own raster grid -> reassigning a record changes its features)"""
import pandas as pd, numpy as np, geopandas as gpd
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in R}
allev=pd.concat([ev[r].assign(src=r) for r in R],ignore_index=True)
allev["key"]=allev.longitude.round(5).astype(str)+","+allev.latitude.round(5).astype(str)
g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(allev.longitude,allev.latitude),crs="EPSG:4326")
j=gpd.sjoin(g,cty[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
allev["state"]=j.STATEFP.map(FIPS).values
dup=allev[allev.key.duplicated(keep=False)]
print("coords appearing in >1 region file:",dup.key.nunique())
for col in ["evt","evh","evc","sclass","nonveg_landcover","envelope_id","spatial_zone","env_zone"]:
    if col not in allev.columns: continue
    nu=dup.groupby("key")[col].nunique(dropna=False)
    print(f"  {col}: coords with DIFFERENT value across region files: {int((nu>1).sum())} of {len(nu)} ({100*(nu>1).mean():.1f}%)")
# how many records flip habitat/nonveg depending on which region evaluated them
piv=dup.pivot_table(index="key",columns="src",values="nonveg_landcover",aggfunc="first")
print("\nnonveg flag disagreement detail (subset of shared coords):")
print(piv.head(3).to_string())
# habitat count under partition vs union-of-any
own=allev[allev.state==allev.src]
hab_own=set(own[~own.nonveg_landcover.astype(bool)].key)
hab_any=set(allev[~allev.nonveg_landcover.astype(bool)].key)
print(f"\nhabitat coords under partition (own-state file): {len(hab_own)}")
print(f"habitat coords if 'habitat in ANY region file'   : {len(hab_any)}")
print(f"coords habitat in another region's file but NONVEG in their own state's file: {len(hab_any-hab_own)}")
