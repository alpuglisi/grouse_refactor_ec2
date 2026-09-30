import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np
R=['ME','NH','VT']
print("Per-region, per-year: GBIF candidate pool  vs  positives needing a year-matched negative")
print(f"{'reg':4s} {'year':5s} {'cand_pool':>10s} {'pos_train':>10s} {'pos_val':>8s} {'ratio':>8s}")
for r in R:
    c=pd.read_csv(f'data/negatives/gbif_negatives_{r}.csv')['year'].value_counts().sort_index()
    tp=pd.read_csv(f'data/pipeline/train_positives_{r}.csv')['year'].value_counts()
    vp=pd.read_csv(f'data/pipeline/val_positives_{r}.csv')['year'].value_counts()
    for y in range(2020,2025):
        need=int(tp.get(y,0))+int(vp.get(y,0))
        pool=int(c.get(y,0))
        print(f"{r:4s} {y:5d} {pool:10,d} {int(tp.get(y,0)):10,d} {int(vp.get(y,0)):8,d} {pool/max(need,1):8.1f}x")
print()
print("Current val-set prevalence (post year-gap filter):")
tp=tn=vp2=vn=0
import grouse_data as G
from models import FEATURE_SPEC
cfg=G.DataConfig(); data={r:G.RegionData(r,cfg) for r in R}
sets=[set(data[r].available_features()) & set(FEATURE_SPEC) for r in R]
feats=sorted(set.intersection(*sets), key=lambda f: list(FEATURE_SPEC).index(f))
yrs={f:data['ME'].raster_years(f) for f in feats}
ok=lambda y: all(min(abs(z-y) for z in yrs[f])<=2 for f in feats)
for r in R:
    tp+=int(pd.read_csv(f'data/pipeline/train_positives_{r}.csv')['year'].map(ok).sum())
    vp2+=int(pd.read_csv(f'data/pipeline/val_positives_{r}.csv')['year'].map(ok).sum())
    tn+=int(pd.read_csv(f'data/negatives/train_negatives_{r}.csv')['year'].map(ok).sum())
    vn+=int(pd.read_csv(f'data/negatives/val_negatives_{r}.csv')['year'].map(ok).sum())
print(f"  train {tp} pos / {tn} neg  prevalence {tp/(tp+tn):.4f}")
print(f"  val   {vp2} pos / {vn} neg  prevalence {vp2/(vp2+vn):.4f}")
print(f"  designed prevalence (1:1) = 0.5000")
