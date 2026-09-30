import pandas as pd, numpy as np
from scipy.spatial import cKDTree
R=["ME","NH","VT"]
tr={r:pd.read_csv(f"data/pipeline/train_positives_{r}.csv") for r in R}
va={r:pd.read_csv(f"data/pipeline/val_positives_{r}.csv") for r in R}
th={r:pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in R}
for r in R:
    print(f"{r}: thinned {len(th[r])}, train {len(tr[r])}, val {len(va[r])}")
TR=pd.concat([tr[r].assign(src=r) for r in R], ignore_index=True)
VA=pd.concat([va[r].assign(src=r) for r in R], ignore_index=True)
print(f"\npooled train {len(TR)}, pooled val {len(VA)}, total {len(TR)+len(VA)}")
def key(d,nd=5):
    return d['longitude'].round(nd).astype(str)+","+d['latitude'].round(nd).astype(str)
for nd in (5,6,4):
    ktr=set(key(TR,nd)); kva=key(VA,nd)
    inboth = kva.isin(ktr)
    print(f"round={nd}: val rows whose coord also appears in pooled train: {int(inboth.sum())} of {len(VA)} ({100*inboth.mean():.2f}%)")
    # unique coords
    print(f"          unique val coords in both: {len(set(kva[inboth]))}; unique pooled train coords {len(ktr)}; unique pooled val coords {len(set(kva))}")
# distance based
trxy=TR[['x_5070','y_5070']].values
t=cKDTree(trxy)
d,_=t.query(VA[['x_5070','y_5070']].values,k=1)
for thr in (0.01,30,300,3000):
    print(f"pooled: val positives with a pooled-TRAIN positive within {thr:>6} m: {100*(d<=thr).mean():5.2f}%  (n={int((d<=thr).sum())})")
# same-region only
print()
for thr in (0.01,30,300,3000):
    tot=0; n=0
    for r in R:
        tt=cKDTree(tr[r][['x_5070','y_5070']].values)
        dd,_=tt.query(va[r][['x_5070','y_5070']].values,k=1)
        tot+=len(dd); n+=int((dd<=thr).sum())
    print(f"same-region: val positives with a same-region train positive within {thr:>6} m: {100*n/tot:5.2f}%  (n={n}/{tot})")
# exact coordinate duplicates across regions in pooled thinned
TH=pd.concat([th[r].assign(src=r) for r in R], ignore_index=True)
k=key(TH)
print(f"\npooled thinned rows {len(TH)} -> unique rounded coords {k.nunique()} (dupes {len(TH)-k.nunique()})")
# opposite split conflicts by coordinate
g=TH.assign(k=k).groupby('k')['split'].nunique()
print(f"coords with BOTH train and val label across regions: {(g>1).sum()}")
