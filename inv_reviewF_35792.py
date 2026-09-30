import pandas as pd, numpy as np, geopandas as gpd
from scipy.spatial import cKDTree
from pyproj import Transformer
import prepare_training_data as P
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
R=["ME","NH","VT"]
tot={}
allsurv=[]
for r in R:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    n0=len(c)
    c=c[~(c['coord_uncertainty_m']>1000).fillna(False)].copy(); n1=len(c)
    k=c[['longitude','latitude']].round(5); c=c.loc[~k.duplicated()].copy(); n2=len(c)
    c['x_5070'],c['y_5070']=T.transform(c['longitude'].values,c['latitude'].values)
    c=P.thin_by_min_distance(c,30,42); n3=len(c)
    ev=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    px,py=T.transform(ev['longitude'].values,ev['latitude'].values)
    d,_=cKDTree(np.c_[px,py]).query(c[['x_5070','y_5070']].values,k=1)
    c=c[d>300].copy(); n4=len(c)
    print(f"{r}: raw {n0} -> uncert {n1} -> dedup {n2} -> thin30 {n3} -> buffer300 {n4}")
    tot[r]=(n0,n1,n2,n3,n4); allsurv.append(c.assign(_reg=r))
print("TOTALS:", [sum(t[i] for t in tot.values()) for i in range(5)])
surv=pd.concat(allsurv,ignore_index=True)
FIPS={"23":"ME","33":"NH","50":"VT"}
cc=gpd.read_file("data/roads/tl_2023_us_county.zip"); cc=cc[cc['STATEFP'].isin(FIPS)]
st=cc.dissolve(by='STATEFP').reset_index(); st['poly_state']=st['STATEFP'].map(FIPS); st=st.to_crs(4326)
g=gpd.GeoDataFrame(surv,geometry=gpd.points_from_xy(surv.longitude,surv.latitude),crs=4326)
j=gpd.sjoin(g,st[['poly_state','geometry']],how='left',predicate='within'); j=j[~j.index.duplicated()]
bad=j[(j.poly_state.isna())|(j.poly_state!=j.state)]
print("post-hygiene pool rows:",len(j)," polygon failures:",len(bad))
print(bad[['longitude','latitude','state','poly_state','_reg']].to_string())
