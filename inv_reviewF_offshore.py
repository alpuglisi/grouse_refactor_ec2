import geopandas as gpd, pandas as pd, numpy as np
from shapely.geometry import Point
c=gpd.read_file("data/roads/tl_2023_us_county.zip").to_crs(4326)
p=Point(-70.6155,42.98926)
hit=c[c.contains(p)]
print(hit[['NAME','STATEFP','ALAND','AWATER']].to_string())
# southernmost ME land? use counties with ALAND>0 in ME
me=c[c.STATEFP=='23']
print("\nME county polygons: min lat of each (name, ALAND km2, AWATER km2, miny):")
for _,r in me.sort_values('AWATER',ascending=False).head(6).iterrows():
    print(f"  {r.NAME:12} ALAND={r.ALAND/1e6:9.1f} AWATER={r.AWATER/1e6:9.1f} miny={r.geometry.bounds[1]:.5f}")
# how many raw sightings + thinned positives land in the heavily-water counties south of 43.06 in ME?
R=["ME","NH","VT"]
tp=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
g=gpd.GeoDataFrame(tp,geometry=gpd.points_from_xy(tp.longitude,tp.latitude),crs=4326)
j=gpd.sjoin(g,c[['NAME','STATEFP','ALAND','AWATER','geometry']],how='left',predicate='within')
j=j[~j.index.duplicated()]
print("\nthinned positives: rows in no county:",int(j.NAME.isna().sum()))
sus=j[(j.state=='ME')&(j.latitude<43.06)]
print("state==ME thinned positives south of 43.06N (south of Maine's southernmost land):",len(sus))
print(sus[['longitude','latitude','NAME','_reg']].to_string())
