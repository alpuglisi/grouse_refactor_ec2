import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np
from sklearn.metrics import roc_auc_score
import grouse_data as G
from models import FEATURE_SPEC
cfg=G.DataConfig(); R=['ME','NH','VT']
data={r:G.RegionData(r,cfg) for r in R}
sets=[set(data[r].available_features()) & set(FEATURE_SPEC) for r in R]
feats=sorted(set.intersection(*sets), key=lambda f: list(FEATURE_SPEC).index(f))
yrs={f:data['ME'].raster_years(f) for f in feats}
def rz(f,y): return min(yrs[f],key=lambda z:(abs(z-y),z))

rows=[]
for r in R:
    for pre in ['train','val']:
        p=pd.read_csv(f'data/pipeline/{pre}_positives_{r}.csv')[['year']]; p['label']=1
        n=pd.read_csv(f'data/negatives/{pre}_negatives_{r}.csv')[['year']]; n['label']=0
        for d in (p,n): d['region']=r; d['split']=pre; rows.append(d)
D=pd.concat(rows,ignore_index=True)
D['keep']=D['year'].map(lambda y: all(min(abs(z-y) for z in yrs[f])<=2 for f in feats))

for tag,sub in [('PRE-filter',D),('POST-filter (what trains)',D[D['keep']])]:
    print("="*60); print(tag, "n=",len(sub), "pos=",int(sub.label.sum()))
    print(" AUC of record year alone -> label: %.4f"%roc_auc_score(sub.label,sub.year))
    for f in ['nlcd','tcc','evt']:
        v=sub['year'].map(lambda y: rz(f,y))
        if v.nunique()>1:
            print("  AUC of %s VINTAGE alone -> label: %.4f  (vintages %s)"%(f,roc_auc_score(sub.label,v),sorted(v.unique())))
        else:
            print("  %s vintage constant"%f)
    ct=pd.crosstab(sub['year'].map(lambda y: rz('nlcd',y)), sub['label'])
    ct['pos_rate']=(ct[1]/(ct[0]+ct[1])).round(4)
    print(" nlcd-vintage x label:"); print(ct)
    ct=pd.crosstab(sub['year'].map(lambda y: rz('evt',y)), sub['label'])
    ct['pos_rate']=(ct[1]/(ct[0]+ct[1])).round(4)
    print(" evt(LANDFIRE)-vintage x label:"); print(ct)
    for spl in ['train','val']:
        s=sub[sub.split==spl]
        print(f"  {spl}: pos={int(s.label.sum())} neg={int((1-s.label).sum())} ratio={s.label.sum()/max(1,(1-s.label).sum()):.3f}")
