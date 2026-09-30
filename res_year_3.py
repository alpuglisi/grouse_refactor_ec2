import os, itertools, collections
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np
import grouse_data as G
from models import FEATURE_SPEC
cfg=G.DataConfig()
R=['ME','NH','VT']
data={r:G.RegionData(r,cfg) for r in R}
# discover_features equivalent
sets=[set(data[r].available_features()) & set(FEATURE_SPEC) for r in R]
feats=sorted(set.intersection(*sets), key=lambda f: list(FEATURE_SPEC).index(f))
print("discovered features:", feats)

for r in R:
    rd=data[r]
    yrs={f: rd.raster_years(f) for f in feats}
    print(r, {f:(min(v),max(v)) for f,v in yrs.items()})

# exact filter_by_year_gap verdict per year, tolerance 2
for tol in [2]:
    print(f"\n--- tolerance {tol} ---")
    for r in R:
        rd=data[r]
        yrs={f: rd.raster_years(f) for f in feats}
        yrs={f:v for f,v in yrs.items() if v}
        def ok(y):
            return all(min(abs(yy-y) for yy in v)<=tol for v in yrs.values())
        def blockers(y):
            return [f for f,v in yrs.items() if min(abs(yy-y) for yy in v)>tol]
        for y in range(2016,2026):
            print(f"  {r} {y}: ok={ok(y)} blockers={blockers(y)}")
        break  # identical across regions

# measured drop
print("\n--- measured drops, tol=2 ---")
tot_p=tot_pd=tot_n=tot_nd=0
for r in R:
    rd=data[r]
    yrs={f: rd.raster_years(f) for f in feats}
    def ok(y): return all(min(abs(yy-int(y)) for yy in v)<=2 for v in yrs.values())
    for kind,path,lab in [('train pos',f'data/pipeline/train_positives_{r}.csv','P'),
                          ('val pos',f'data/pipeline/val_positives_{r}.csv','P'),
                          ('train neg',f'data/negatives/train_negatives_{r}.csv','N'),
                          ('val neg',f'data/negatives/val_negatives_{r}.csv','N')]:
        df=pd.read_csv(path)
        keep=df['year'].map(ok)
        d=int((~keep).sum())
        print(f"  {r} {kind}: n={len(df)} dropped={d} ({100*d/len(df):.2f}%) kept={len(df)-d}")
        if lab=='P': tot_p+=len(df); tot_pd+=d
        else: tot_n+=len(df); tot_nd+=d
print(f"POOLED positives: {tot_p} dropped {tot_pd} = {100*tot_pd/tot_p:.2f}%")
print(f"POOLED negatives: {tot_n} dropped {tot_nd} = {100*tot_nd/tot_n:.2f}%")
