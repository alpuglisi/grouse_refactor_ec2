"""FORMAL C -- BREAK 10, variant B: the NEGATIVE split's FEATURE geometry is
ungated.  I17 (ks_feat_max) is scoped 'positives only'; I16b gates only the
LOCATION of the val indicator.  The CR's own defence of I16 is that "as the
attack moves to finer cells, detectability and harm decay TOGETHER" -- true for
location bias, FALSE for feature bias, which lives at 30 m.  So: choose which
positive-free blocks are val by a LOCAL feature extremum (spatially
salt-and-pepper -> Moran ~ 0 or negative -> z gate passes one-sided) and the
validation negatives come from a different feature distribution than the
training negatives, with every GATE row green.   READ-ONLY."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
import inv_formalC_lib as L

CONT = ["ch","cc","tcc","road_dist","tsd","balive","tpa_live","qmd","carbon_dwn"]
P, C = L.load()
FP = pd.read_csv(f"{L.SCR}/fc_feat_pos.csv"); FC = pd.read_csv(f"{L.SCR}/fc_feat_pool.csv")
P = pd.concat([P, FP], axis=1); C = pd.concat([C, FC], axis=1)

vb = L.val_blocks(P, L.SEED)
P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
pb = set(P.blk.unique()); bt = {b: ('val' if b in vb else 'train') for b in pb}
gvf = len(vb)/len(pb)
L.TARGETS = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}

free = C.loc[~C.blk.isin(pb)]
fb = free.groupby('blk').agg({f:'mean' for f in CONT})
fb['x'] = L.bcentre(fb.index.values)[:,0]; fb['y'] = L.bcentre(fb.index.values)[:,1]
nfree = len(fb); nval = int(round(gvf*nfree))
print(f"positive-free blocks {nfree} (CR-0007 says 5,621; faithful = this), "
      f"val quota {nval}")

def assign(mode, feat="road_dist", k=9):
    if mode == 'fair':
        return {b: L.hash_split(b, gvf, L.SEED) for b in fb.index}
    # local-extremum pick: inside every k-nearest-neighbour cluster of
    # positive-free blocks, send the top-ranked block on `feat` to val.
    XY = fb[['x','y']].values
    _, idx = cKDTree(XY).query(XY, k=k)
    v = fb[feat].values
    rank = np.array([(v[i] >= v[idx[i]]).mean() for i in range(len(fb))])
    sel = set(fb.index.values[np.argsort(-rank)[:nval]])
    return {b: ('val' if b in sel else 'train') for b in fb.index}

pool_blk = None
def run(tag, mode, feat="road_dist"):
    global pool_blk
    fs = assign(mode, feat)
    C2 = C.copy()
    C2['split'] = [bt[b] if b in bt else fs[b] for b in C2.blk]
    pool_blk = C2.drop_duplicates('blk')[['blk','split']]
    neg = L.real_draw(C2, L.TARGETS, 0)
    g = L.gate_report(P, neg, pool_blocks=pool_blk, label=tag)
    # the ungated statistic: ks_feat over the NEGATIVES
    res = {}
    for f in CONT:
        a = neg.loc[neg.split=='val', f].dropna(); b = neg.loc[neg.split=='train', f].dropna()
        res[f] = ks_2samp(a,b).statistic
    kmax = max(res, key=res.get)
    resp = {}
    for f in CONT:
        a = P.loc[P.split=='val', f].dropna(); b = P.loc[P.split=='train', f].dropna()
        resp[f] = ks_2samp(a,b).statistic
    print(f"  I17 as specified (POSITIVES only)  ks_feat_max {max(resp.values()):.4f}"
          f" ({max(resp,key=resp.get)})   gate <= 0.095  -> "
          f"{'PASS' if max(resp.values())<=0.095 else 'FAIL'}")
    print(f"  UNGATED: ks_feat_max over the NEGATIVES  {res[kmax]:.4f} ({kmax})")
    print("     " + "  ".join(f"{f}={res[f]:.3f}" for f in CONT))
    # val/train mean shift in SE units for each feature, negatives
    print("     val-neg vs train-neg mean shift (SE): " + "  ".join(
        f"{f}={(neg.loc[neg.split=='val',f].mean()-neg.loc[neg.split=='train',f].mean())/(neg[f].std()/np.sqrt(len(neg.loc[neg.split=='val']))):+.1f}"
        for f in CONT))
    return g, res[kmax]

gf, kf = run("A: FAIR (hash split of positive-free blocks)", 'fair')
for feat in ("road_dist","tcc","balive","tsd"):
    ga, ka = run(f"B: BREAK 10B - positive-free blocks val-assigned by LOCAL "
                 f"'{feat}' extremum", 'atk', feat)
