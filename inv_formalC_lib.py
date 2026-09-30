"""FORMAL C: shared harness. Builds CR-0007's intended pooled pipeline from
the faithful pool (inv_formalC_pool.py) using the REAL two-pool weighted
negative draw, and scores every GATE row incl. the two new ones (I19
per-region, I16b all-record Moran).  READ-ONLY apart from scratch files."""
import hashlib
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME", "NH", "VT"]
BS = 3000.0
VF = 0.20
SEED = 42
RF = 1920.0
NEG_RATIO = 1.0
NONVEG_MAX_FRAC = 0.30

def blk(x, y, size=BS):
    return (np.floor(x/size).astype(np.int64)*1000000
            + np.floor(y/size).astype(np.int64))
def bcentre(keys, size=BS):
    k = np.asarray(keys, dtype=np.int64)
    bx = np.floor_divide(k, 1000000); by = k - bx*1000000
    return np.c_[(bx+0.5)*size, (by+0.5)*size]

def load():
    P = pd.read_csv(f"{SCR}/fc_pos.csv")
    C = pd.read_csv(f"{SCR}/fc_pool.csv")
    for d in (P, C):
        d['blk'] = blk(d.x_5070.values, d.y_5070.values)
    return P.reset_index(drop=True), C.reset_index(drop=True)

def val_blocks(P, seed, vf=VF):
    bc = P['blk'].value_counts()
    order = bc.sample(frac=1, random_state=seed).index.tolist()
    tgt, vb, run = int(round(vf*len(P))), set(), 0
    for b in order:
        if run >= tgt: break
        vb.add(b); run += bc[b]
    return vb

def hash_split(b, vf, seed):
    h = int(hashlib.md5(f"{seed}:{b}".encode()).hexdigest(), 16)
    return 'val' if (h % 10000) < vf*10000 else 'train'

def weighted_take(subpool, n, rng):
    """verbatim generate_negatives.weighted_take"""
    if n <= 0 or len(subpool) == 0: return subpool.iloc[0:0]
    if len(subpool) <= n: return subpool
    p = subpool['weight'].values / subpool['weight'].sum()
    idx = rng.choice(subpool.index.values, size=n, replace=False, p=p)
    return subpool.loc[idx]

def real_draw(cand, targets, seed, uniform=False, verbose=False):
    """generate_negatives' two-pool NonVeg-capped draw, per (region, split)."""
    rng = np.random.default_rng(seed)
    out = []
    for (r, s), n_target in targets.items():
        pool = cand[(cand.state.values == r) & (cand.split.values == s)]
        if len(pool) == 0:
            if verbose: print(f"    [!] {r}/{s}: empty pool, 0/{n_target}")
            continue
        if uniform:
            k = min(n_target, len(pool))
            out.append(pool.iloc[rng.choice(len(pool), k, replace=False)].assign(split=s))
            continue
        nv = pool[pool.is_nonveg.values]; hb = pool[~pool.is_nonveg.values]
        n_nv = min(int(round(n_target*NONVEG_MAX_FRAC)), len(nv))
        n_hb = n_target - n_nv
        th = weighted_take(hb, n_hb, rng)
        short = n_hb - len(th)
        if short > 0: n_nv = min(n_nv+short, len(nv))
        tn = weighted_take(nv, n_nv, rng)
        got = pd.concat([th, tn])
        if verbose and len(got) < n_target:
            print(f"    [!] {r}/{s}: only {len(got)}/{n_target}")
        out.append(got.assign(split=s))
    return pd.concat(out, ignore_index=True)

def moran(keys, isval, k=8):
    ctr = bcentre(keys)
    z = np.asarray(isval, dtype=float); z = z - z.mean()
    if z.std() == 0: return 0.0
    _, idx = cKDTree(ctr).query(ctr, k=k+1)
    return float((z[idx[:,1:]].mean(axis=1)*z).sum() / (z**2).sum())

def i19(P, neg):
    out = {}
    nxy_all = neg[['x_5070','y_5070']].values
    for r in R:
        p = P[P.state==r][['x_5070','y_5070']].values
        n = neg[neg.state==r][['x_5070','y_5070']].values
        if len(n)==0: out[r]=1.0; continue
        d,_ = cKDTree(n).query(p, k=1); out[r]=float((d>RF).mean())
    d,_ = cKDTree(nxy_all).query(P[['x_5070','y_5070']].values, k=1)
    out['pooled']=float((d>RF).mean()); out['worst']=max(out[r] for r in R)
    return out

def gate_report(P, neg, pool_blocks=None, null=None, label="", quiet=False):
    """Score every GATE row. Returns dict."""
    g = {}
    px = P[['x_5070','y_5070']].values
    g['I1'] = len(cKDTree(px).query_pairs(30.0, output_type='ndarray'))
    rec = pd.concat([P.assign(cls='pos'), neg.assign(cls='neg')], ignore_index=True)
    bn = rec.groupby('blk')['split'].nunique()
    g['I2'] = int((bn>1).sum())
    trb = set(rec.loc[rec.split=='train','blk'])
    vn = rec[(rec.split=='val')&(rec.cls=='neg')]
    g['I3'] = float(vn.blk.isin(trb).mean()) if len(vn) else 0.0
    for c in ('pos','neg'):
        s = rec[rec.cls==c]
        kt = set(map(tuple, np.round(s.loc[s.split=='train',['longitude','latitude']].values,5)))
        kv = list(map(tuple, np.round(s.loc[s.split=='val',['longitude','latitude']].values,5)))
        g[f'I4_{c}'] = sum(1 for k in kv if k in kt)
    g['I6'] = len(P)
    g['I8'] = all(int(((neg.state==r)&(neg.split==s)).sum())==n
                  for (r,s),n in TARGETS.items())
    # I15 positives only
    bl = P.drop_duplicates('blk')
    g['I15'] = abs(100*(bl.split=='val').mean() - 100*(P.split=='val').mean())
    g['I15_rec'] = (P.split=='val').sum()/max((bl.split=='val').sum(),1)
    # I16 positives-only Moran
    pb = P.drop_duplicates('blk')
    for k in (4,8):
        g[f'I16_k{k}'] = moran(pb.blk.values, (pb.split=='val').values, k)
    # I16b all-record Moran, two readings
    ar = rec.drop_duplicates('blk')
    for k in (4,8):
        g[f'I16b_sel_k{k}'] = moran(ar.blk.values, (ar.split=='val').values, k)
    if pool_blocks is not None:
        for k in (4,8):
            g[f'I16b_pool_k{k}'] = moran(pool_blocks['blk'].values,
                                         (pool_blocks['split']=='val').values, k)
    # I18 positives only
    t = P[P.split=='train'][['x_5070','y_5070']].values
    v = P[P.split=='val'][['x_5070','y_5070']].values
    d,_ = cKDTree(t).query(v, k=1); g['I18'] = np.median(d)/1000.0
    # I19
    g.update({f'I19_{k}': v for k, v in i19(P, neg).items()})
    if not quiet:
        print(f"\n===== {label} =====")
        print(f"  I1  {g['I1']:>6}  (0)   I2 {g['I2']:>4} (0)   I3 {100*g['I3']:.2f}% (0)"
              f"   I4 pos {g['I4_pos']} neg {g['I4_neg']} (0)")
        print(f"  I6  {g['I6']} (6230+/-10)   I8 {'PASS' if g['I8'] else 'FAIL'}"
              f"   I15 {g['I15']:.3f} pp (<=2.5)   I18 {g['I18']:.3f} km ([2.33,2.75])")
        print(f"  I16  pos-only   k4 {g['I16_k4']:+.4f}  k8 {g['I16_k8']:+.4f}")
        print(f"  I16b sel-record k4 {g['I16b_sel_k4']:+.4f}  k8 {g['I16b_sel_k8']:+.4f}")
        if pool_blocks is not None:
            print(f"  I16b pool-block k4 {g['I16b_pool_k4']:+.4f}  k8 {g['I16b_pool_k8']:+.4f}")
        print(f"  I19  ME {g['I19_ME']:.4f}  NH {g['I19_NH']:.4f}  VT {g['I19_VT']:.4f}"
              f" | worst {g['I19_worst']:.4f} (<=0.64)  pooled {g['I19_pooled']:.4f}")
        if null:
            for key, (m, sd) in null.items():
                if key in g:
                    print(f"     z[{key}] = {(g[key]-m)/sd:+.2f}   (gate z<=5.0)")
    return g

TARGETS = {}
