"""Refine: records near the border shared with ANOTHER US STATE (the only place
adding neighbouring-county roads can change road_dist).  Coastline excluded."""
import pandas as pd, geopandas as gpd
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
FIPS={"ME":"23","NH":"33","VT":"50"}
allst=cty.dissolve(by="STATEFP").to_crs("EPSG:5070")
for r,fp in FIPS.items():
    own=allst.loc[fp,"geometry"]
    others=allst.drop(index=fp).union_all()
    shared=own.boundary.intersection(others.buffer(50))   # land border with other US states
    if shared.is_empty: print(r,"no shared border?"); continue
    for name,paths in (("pos",[f"data/pipeline/{s}_positives_{r}.csv" for s in ("train","val")]),
                       ("neg",[f"data/negatives/{s}_negatives_{r}.csv" for s in ("train","val")])):
        df=pd.concat([pd.read_csv(p) for p in paths],ignore_index=True)
        g=gpd.GeoSeries(gpd.points_from_xy(df.longitude,df.latitude),crs="EPSG:4326").to_crs("EPSG:5070")
        d=g.distance(shared)
        print(f"  {r} {name} n={len(df):5d}: <2km {int((d<2000).sum()):4d} ({100*(d<2000).mean():5.2f}%) "
              f"<5km {int((d<5000).sum()):4d} ({100*(d<5000).mean():5.2f}%) <10km {int((d<10000).sum()):4d} ({100*(d<10000).mean():5.2f}%)")
