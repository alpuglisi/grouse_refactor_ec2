import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np
R=['ME','NH','VT']
parts=[]
for r in R:
    for pre in ['train','val']:
        df=pd.read_csv(f'data/pipeline/{pre}_positives_{r}.csv'); df['region']=r; df['split']=pre
        parts.append(df)
P=pd.concat(parts,ignore_index=True)
P['pre2020']=P['year']<2020
print("n pre2020=%d post=%d"%(P['pre2020'].sum(),(~P['pre2020']).sum()))
print("\nby region:")
print(pd.crosstab(P['region'],P['pre2020'],normalize='columns'))
print("\nby recorded state:")
print(pd.crosstab(P['state'],P['pre2020'],normalize='columns'))
print("\nby split:")
print(pd.crosstab(P['split'],P['pre2020'],normalize='columns'))
num=['latitude','longitude','n_visits','slope','aspect_gradient','spatial_density','evh','evc','sclass','evt']
print("\nnumeric means (pre2020 vs post2020):")
for c in num:
    if c in P.columns and pd.api.types.is_numeric_dtype(P[c]):
        a=P.loc[P['pre2020'],c].mean(); b=P.loc[~P['pre2020'],c].mean()
        sd=P[c].std()
        print(f"  {c:16s} pre={a:12.4f} post={b:12.4f} diff={a-b:+12.4f} cohend={(a-b)/sd if sd else 0:+.3f}")
for c in ['evt_phys','nonveg_landcover','spatial_zone','env_zone']:
    if c in P.columns:
        print(f"\n{c} share by group:")
        t=pd.crosstab(P[c],P['pre2020'],normalize='columns')
        t['diff']=t[True]-t[False]
        print(t.sort_values('diff',key=abs,ascending=False).head(8))
