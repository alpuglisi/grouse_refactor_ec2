import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np
import grouse_data as G
from models import FEATURE_SPEC
cfg=G.DataConfig(); R=['ME','NH','VT']
data={r:G.RegionData(r,cfg) for r in R}
sets=[set(data[r].available_features()) & set(FEATURE_SPEC) for r in R]
feats=sorted(set.intersection(*sets), key=lambda f: list(FEATURE_SPEC).index(f))

def resolve(years, y):
    return min(years, key=lambda yy:(abs(yy-y), yy))

def load(kind):
    parts=[]
    for r in R:
        for pre,d in [('train','p'),('val','p')] if kind=='pos' else [('train','n'),('val','n')]:
            path=(f'data/pipeline/{pre}_positives_{r}.csv' if kind=='pos'
                  else f'data/negatives/{pre}_negatives_{r}.csv')
            df=pd.read_csv(path)[['year']]; df['region']=r; df['split']=pre
            parts.append(df)
    return pd.concat(parts, ignore_index=True)

P=load('pos'); N=load('neg')
yrs={f: data['ME'].raster_years(f) for f in feats}   # identical across regions

def stats(df, label, postfilter):
    d=df.copy()
    if postfilter:
        d=d[d['year'].map(lambda y: all(min(abs(yy-y) for yy in v)<=2 for v in yrs.values()))]
    rows={}
    for f in feats:
        rv=d['year'].map(lambda y: resolve(yrs[f], y))
        gap=(rv-d['year']).abs()
        rows[f]=dict(mean_vintage=rv.mean(), mean_abs_gap=gap.mean(),
                     frac_exact=(gap==0).mean(),
                     vint_dist=dict(rv.value_counts().sort_index()))
    return len(d), rows

for postfilter in [False, True]:
    print("="*70)
    print("POST-filter" if postfilter else "PRE-filter (all records)")
    np_, pr = stats(P,'pos',postfilter)
    nn_, nr = stats(N,'neg',postfilter)
    print(f"n pos={np_}  n neg={nn_}")
    print(f"{'feature':12s} {'pos_mean_vint':>13s} {'neg_mean_vint':>13s} {'delta':>7s} "
          f"{'pos_gap':>8s} {'neg_gap':>8s} {'gapdelta':>9s}")
    for f in feats:
        a,b=pr[f],nr[f]
        print(f"{f:12s} {a['mean_vintage']:13.3f} {b['mean_vintage']:13.3f} "
              f"{a['mean_vintage']-b['mean_vintage']:+7.3f} "
              f"{a['mean_abs_gap']:8.3f} {b['mean_abs_gap']:8.3f} "
              f"{a['mean_abs_gap']-b['mean_abs_gap']:+9.3f}")
    print("\nmean record year: pos %.3f neg %.3f delta %+0.3f"%(
        (P if not postfilter else P[P['year']>=2020])['year'].mean(),
        N['year'].mean(),
        (P if not postfilter else P[P['year']>=2020])['year'].mean()-N['year'].mean()))
print()
print("Per-feature vintage distributions PRE-filter, for features reaching pre-2020:")
_,pr=stats(P,'pos',False); _,nr=stats(N,'neg',False)
for f in ['tcc','nlcd','tsd','balive','evt']:
    print(f" {f}: pos {pr[f]['vint_dist']}")
    print(f" {f}: neg {nr[f]['vint_dist']}")
