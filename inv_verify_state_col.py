"""Author-side verification of reviewer A's Concern 8: does the sighting
`state` column agree with the TIGER state polygon for every record?
Read-only."""
import pandas as pd, geopandas as gpd
from shapely.geometry import Point
d = pd.read_csv("evaluated_sightings.csv", low_memory=False)
cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
FIPS = {"23": "ME", "33": "NH", "50": "VT"}
cty = cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
g = gpd.GeoDataFrame(d[["state","longitude","latitude"]],
                     geometry=[Point(x,y) for x,y in zip(d.longitude,d.latitude)],
                     crs="EPSG:4326")
j = gpd.sjoin(g, cty[["STATEFP","geometry"]], how="left", predicate="within")
j = j[~j.index.duplicated()]
j["poly"] = j.STATEFP.map(FIPS)
print("rows:", len(j))
print("records with NO polygon:", int(j.poly.isna().sum()))
dis = j[j.poly.notna() & (j.poly != j.state)]
print("DISAGREEMENTS (state column vs polygon):", len(dis))
if len(dis): print(dis.groupby(["state","poly"]).size().to_string())
print("\nagreement:", f"{(j.poly==j.state).sum()} of {len(j)}")
print("\nNH-filed max longitude:", d[d.state=="NH"].longitude.max())
print("NH box max_lon from regions.py: -70.600")
