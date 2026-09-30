"""Re-derive CR-0007's verify_partition() exceptions from scratch."""
import pandas as pd, geopandas as gpd
from shapely.geometry import Point
c=gpd.read_file("data/roads/tl_2023_us_county.zip")[["STATEFP","geometry"]]
st=c.dissolve(by="STATEFP").reset_index()
FIPS={"23":"ME","33":"NH","50":"VT"}
poly={FIPS[f]:st.loc[st.STATEFP==f,"geometry"].iloc[0] for f in FIPS}
allp=st.geometry.union_all()
def check(df,tag):
    bad_out,bad_mis=[],[]
    for lon,lat,s in zip(df.longitude,df.latitude,df.state):
        p=Point(lon,lat)
        if s in poly and poly[s].contains(p):   # 'within'
            continue
        if not allp.contains(p): bad_out.append((lon,lat,s))
        else:
            hit=[k for k,g in poly.items() if g.contains(p)]
            bad_mis.append((lon,lat,s,hit))
    print(f"{tag}: n={len(df)}  outside ALL US county polygons={len(bad_out)}  "
          f"state!=polygon={len(bad_mis)}")
    for b in bad_out[:8]: print("    OUTSIDE:",b)
    for b in bad_mis[:8]: print("    MISMATCH:",b)
# raw sightings
sg=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
print("NOTE: evaluated_sightings pooled rows =",len(sg),"(CR-0007 cites 43,024 RAW sightings)")
check(sg.drop_duplicates(["longitude","latitude","state"]),"evaluated sightings (unique lon/lat/state)")
# selected negatives
sel=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
check(sel,"selected negatives")
# candidate pool after hygiene
C=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
C=C[~(C.coord_uncertainty_m>1000).fillna(False)]
C=C.loc[~C[["longitude","latitude"]].round(5).duplicated()]
check(C,"pooled candidate pool (35,678)")
