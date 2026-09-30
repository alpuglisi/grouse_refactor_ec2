import pandas as pd, numpy as np
import prepare_training_data as P
from scipy.spatial import cKDTree
R=["ME","NH","VT"]
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R}
allrows=pd.concat(ev.values(),ignore_index=True)
allrows['_k']=allrows['longitude'].round(7).astype(str)+","+allrows['latitude'].round(7).astype(str)
print("all eval rows",len(allrows),"unique coords",allrows['_k'].nunique())
# own-state-grid habitat flag
own=allrows[allrows['state']==allrows['_reg']]
print("rows filed in their own state's region file:",len(own),"unique coords",own['_k'].nunique())
ownu=own.drop_duplicates('_k')
hab_own=ownu[~ownu['nonveg_landcover'].astype(bool)]
print("own-grid habitat unique coords:",len(hab_own))
th=P.thin_by_min_distance(hab_own,30,42)
print("  -> pooled thin 30m:",len(th),"  by state:",th['state'].value_counts().to_dict())
# coords with no own-state row at all
missing=set(allrows['_k'])-set(own['_k'])
print("coords with NO row in their own state's region file:",len(missing))
# variant: prefer own-state row, else any row
allrows['_own']=(allrows['state']==allrows['_reg'])
pref=allrows.sort_values('_own',ascending=False).drop_duplicates('_k')
habp=pref[~pref['nonveg_landcover'].astype(bool)]
print("prefer-own-else-any habitat unique coords:",len(habp))
th2=P.thin_by_min_distance(habp,30,42)
print("  -> pooled thin 30m:",len(th2),"  by state:",th2['state'].value_counts().to_dict())
# variant: any-region row says habitat (OR), unique coords
anyhab=allrows.groupby('_k')['nonveg_landcover'].apply(lambda s: not bool(s.astype(bool).all()))
print("unique coords habitat under OR-of-regions:",int(anyhab.sum()))
allhab=allrows[~allrows['nonveg_landcover'].astype(bool)].drop_duplicates('_k')
print("unique coords with >=1 habitat row:",len(allhab))
th3=P.thin_by_min_distance(allhab,30,42)
print("  -> pooled thin 30m:",len(th3))
# variant: AND-of-regions (habitat only if habitat in every file containing it)
andhab=allrows.groupby('_k')['nonveg_landcover'].apply(lambda s: not bool(s.astype(bool).any()))
ks=set(andhab[andhab].index)
sub=allrows.drop_duplicates('_k'); sub=sub[sub['_k'].isin(ks)]
print("unique coords habitat in EVERY containing file:",len(sub))
th4=P.thin_by_min_distance(sub,30,42)
print("  -> pooled thin 30m:",len(th4))
