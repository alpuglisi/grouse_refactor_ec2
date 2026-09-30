import pandas as pd, geopandas as gpd, numpy as np
from shapely.geometry import Point
cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
print("county layer:", len(cty), "crs", cty.crs, "cols", [c for c in cty.columns][:8])
FIPS={"23":"ME","33":"NH","50":"VT"}
st = cty[cty['STATEFP'].isin(FIPS)].copy()
st['ST']=st['STATEFP'].map(FIPS)
states = st.dissolve(by='ST')[['geometry']].reset_index()
print(states)
R=["ME","NH","VT"]
def tag(df):
    g=gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df['longitude'],df['latitude']), crs="EPSG:4326")
    j=gpd.sjoin(g, states.to_crs("EPSG:4326"), how='left', predicate='within')
    j=j[~j.index.duplicated()]
    return j['ST'].fillna('none/other')
rows=[]
for r in R:
    pos=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
    neg=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    tp=tag(pos); tn=tag(neg)
    print(f"\n{r} pos: n={len(pos)} by state {tp.value_counts().to_dict()}")
    print(f"{r} neg: n={len(neg)} by state {tn.value_counts().to_dict()}")
    print(f"  {r} positives OUTSIDE {r}: {int((tp!=r).sum())};  negatives OUTSIDE {r}: {int((tn!=r).sum())}")
    for k,v in tp.value_counts().items(): rows.append((r,'pos',k,v))
    for k,v in tn.value_counts().items(): rows.append((r,'neg',k,v))
t=pd.DataFrame(rows,columns=['region','kind','state','n'])
piv=t.pivot_table(index='state',columns='kind',values='n',aggfunc='sum').fillna(0)
piv['prevalence_pct']=100*piv['pos']/(piv['pos']+piv['neg'])
print("\npooled by TRUE state:"); print(piv)
