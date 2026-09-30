import pandas as pd, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]
tp=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
trp=pd.concat([pd.read_csv(f"data/pipeline/train_positives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
vap=pd.concat([pd.read_csv(f"data/pipeline/val_positives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
trn=pd.concat([pd.read_csv(f"data/negatives/train_negatives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
van=pd.concat([pd.read_csv(f"data/negatives/val_negatives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def xy(df):
    x,y=T.transform(df['longitude'].values,df['latitude'].values); return np.c_[x,y]
# I1 variants
for name,df in [("thinned pooled",tp),("train+val pooled",pd.concat([trp,vap]))]:
    P=xy(df); print(f"I1 {name}: query_pairs(30) = {len(cKDTree(P).query_pairs(30))}  (recorded x_5070: {len(cKDTree(df[['x_5070','y_5070']].values).query_pairs(30))})")
# also strict < 30
P=xy(tp); print("I1 thinned pooled, pairs at dist<30 strictly:", len(cKDTree(P).query_pairs(30, output_type='ndarray')))
d=cKDTree(P).sparse_distance_matrix(cKDTree(P),30)
# I4: 5dp key
def key(df,dp=5): return set(zip(df['longitude'].round(dp),df['latitude'].round(dp)))
print("I4 pos train∩val (5dp):", len(key(trp)&key(vap)))
print("I4 neg train∩val (5dp):", len(key(trn)&key(van)))
for dp in (4,6,7):
    print(f"   pos at {dp}dp:", len(key(trp,dp)&key(vap,dp)), " neg:", len(key(trn,dp)&key(van,dp)))
# duplicates inside a single split
for nm,df in [("train pos",trp),("val pos",vap)]:
    k=df['longitude'].round(5).astype(str)+","+df['latitude'].round(5).astype(str)
    print(f"dupes within {nm}: {len(df)-k.nunique()} extra rows, {int((k.value_counts()>1).sum())} coords")
kall=tp['longitude'].round(5).astype(str)+","+tp['latitude'].round(5).astype(str)
print("pooled thinned: rows",len(tp),"unique coords",kall.nunique(),"=> duplicated coords:",int((kall.value_counts()>1).sum()),"extra rows:",len(tp)-kall.nunique())
# 522 / within-30m rates
Pt=xy(trp); Pv=xy(vap)
tree=cKDTree(Pt)
d1,_=tree.query(Pv,k=1)
print("val pos with a train pos within 30m (pooled):", int((d1<=30).sum()), f"{100*(d1<=30).mean():.2f}%")
print("val pos identical-coord in train (pooled, 5dp): ", int(pd.Series(list(zip(vap['longitude'].round(5),vap['latitude'].round(5)))).isin(key(trp)).sum()), f"{100*pd.Series(list(zip(vap['longitude'].round(5),vap['latitude'].round(5)))).isin(key(trp)).mean():.2f}%")
# within region
for r in R:
    a=trp[trp._reg==r]; b=vap[vap._reg==r]
    dd,_=cKDTree(xy(a)).query(xy(b),k=1)
    print(f"  within {r}: val pos w/ train pos <=30m: {int((dd<=30).sum())} ({100*(dd<=30).mean():.2f}%)")
