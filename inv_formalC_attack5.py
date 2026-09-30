"""FORMAL C: full GATE table for the realistic variant of BREAK 10A -- the
northern 15 % of ME and VT loses its negative CANDIDATES (a coverage-mask /
nodata-dropna loss, the exact mechanism CR-0008 introduces for BUG-0024/0025).
READ-ONLY."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
P, C = L.load()
vb = L.val_blocks(P, L.SEED)
P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
pb = set(P.blk.unique()); bt = {b:('val' if b in vb else 'train') for b in pb}
gvf = len(vb)/len(pb)
C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, L.SEED) for b in C.blk]
L.TARGETS = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
def strip(q, regions=("ME","VT")):
    out=[]
    for r in L.R:
        s=C[C.state==r]
        if r in regions:
            thr=np.quantile(s.y_5070.values,q); s=s[s.y_5070.values<=thr]
        out.append(s)
    return pd.concat(out,ignore_index=True)
for tag,pool in (("A: FAIR", C), ("B: BREAK 10A'' northern-15% candidate loss in ME+VT", strip(0.85))):
    neg=L.real_draw(pool,L.TARGETS,0)
    g=L.gate_report(P,neg,pool_blocks=pool.drop_duplicates('blk')[['blk','split']],label=tag)
    print(f"  ==> I19 worst {g['I19_worst']:.4f} vs 0.64  -> "
          f"{'PASSES' if g['I19_worst']<=0.64 else 'FAILS'};  "
          f"400-seed fair envelope is [0.5264, 0.6172]")
    for r in ("ME","VT","NH"):
        p=P[P.state==r]; n=neg[neg.state==r]
        d,_=cKDTree(n[['x_5070','y_5070']].values).query(p[['x_5070','y_5070']].values,k=1)
        thr=np.quantile(C[C.state==r].y_5070.values,0.85); m=p.y_5070.values>thr
        pbk=set(zip(np.floor(p.x_5070/30000).astype(int),np.floor(p.y_5070/30000).astype(int)))
        nbk=set(zip(np.floor(n.x_5070/30000).astype(int),np.floor(n.y_5070/30000).astype(int)))
        print(f"    {r}: positives in the stranded northern 15% n={m.sum():>4}  "
              f"frac with NO negative within 1920 m = {(d[m]>L.RF).mean():.4f}  "
              f"median dist {np.median(d[m]):>7.0f} m (rest {np.median(d[~m]):.0f} m)"
              f" | I10(OBS) {len(pbk-nbk)}/{len(pbk)}")
