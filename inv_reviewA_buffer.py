"""Does the state partition WEAKEN generate_negatives.py's 300 m buffer?
Under the partition, region R's `evaluated` holds only R's own-state positives,
so a candidate in R within 300 m of a NEIGHBOURING state's grouse record is no
longer excluded.  Count them."""
import pandas as pd, numpy as np, geopandas as gpd
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
def tag(df):
    g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(df.longitude,df.latitude),crs="EPSG:4326")
    j=gpd.sjoin(g,cty[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
    return pd.Series(j.STATEFP.map(FIPS).values,index=df.index)
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in R}
allev=pd.concat([ev[r] for r in R],ignore_index=True)
allev["key"]=allev.longitude.round(5).astype(str)+","+allev.latitude.round(5).astype(str)
allev=allev.drop_duplicates("key")
allev["st"]=tag(allev)
x,y=t.transform(allev.longitude.values,allev.latitude.values); allev["x"],allev["y"]=x,y
print("unique grouse locations pooled:",len(allev),allev.st.value_counts().to_dict())
for r in R:
    cand=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    cand=cand.drop_duplicates(subset=None) if False else cand
    cx,cy=t.transform(cand.longitude.values,cand.latitude.values)
    own=allev[allev.st==r]; other=allev[allev.st!=r]
    d_own,_=cKDTree(own[["x","y"]].values).query(np.column_stack([cx,cy]),k=1)
    d_all,_=cKDTree(allev[["x","y"]].values).query(np.column_stack([cx,cy]),k=1)
    # today's buffer set = region's box-clipped evaluated file
    e=ev[r].drop_duplicates(["longitude","latitude"])
    ex,ey=t.transform(e.longitude.values,e.latitude.values)
    d_today,_=cKDTree(np.column_stack([ex,ey])).query(np.column_stack([cx,cy]),k=1)
    newly = (d_today<=300) & (d_own>300)
    print(f"{r}: {len(cand)} candidates | excluded today {int((d_today<=300).sum())} | "
          f"excluded under partition (own-state only) {int((d_own<=300).sum())} | "
          f"excluded if pooled-all-states {int((d_all<=300).sum())}")
    print(f"    candidates that NEWLY become eligible negatives under the partition "
          f"(within 300 m of a real grouse record, no longer buffered): {int(newly.sum())}")
