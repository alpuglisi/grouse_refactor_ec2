"""FORMAL C -- BREAK 10A, realistic mechanism + multi-seed robustness.
Mechanism that is NOT contrived: generate_negatives drops any candidate with
nodata in feats_needed.  CR-0008 (the very next CR in this sequence, for
BUG-0024/0025) converts out-of-coverage fill to NODATA in derived rasters over
exactly the northern border strip of ME/VT.  Negatives in that strip vanish;
positives, filtered earlier on other layers, do not.  Result: a negative-free
band.  Does I19-per-region see it?   READ-ONLY."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L

P, C = L.load()
def build(seed):
    vb = L.val_blocks(P, seed)
    P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
    pb = set(P.blk.unique()); bt = {b:('val' if b in vb else 'train') for b in pb}
    gvf = len(vb)/len(pb)
    C2 = C.copy()
    C2['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed) for b in C2.blk]
    tg = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
    return C2, tg

def strip(C2, tg, regions, q):
    """drop candidates above the q-quantile of the region's candidate latitude"""
    keep = []
    for r in L.R:
        sub = C2[C2.state==r]
        if r in regions:
            thr = np.quantile(sub.y_5070.values, q)
            cut = sub[sub.y_5070.values <= thr]
            okall = True
            for s in ('train','val'):
                p = cut[cut.split==s]; n = tg[(r,s)]
                nv = int(p.is_nonveg.sum()); hb = len(p)-nv
                n_nv = min(int(round(n*L.NONVEG_MAX_FRAC)), nv)
                if hb < n-n_nv or len(p) < n: okall = False
            if okall: sub = cut
            else: return None, thr
        keep.append(sub)
    return pd.concat(keep, ignore_index=True), None

print("Scan: northern-strip removal of negative candidates (ME+VT), "
      "largest strip with adequate supply")
C2, tg = build(L.SEED); L.TARGETS = tg
for q in (0.95,0.90,0.85,0.80,0.75,0.70,0.65,0.60):
    pool, _ = strip(C2, tg, ("ME","VT"), q)
    if pool is None:
        print(f"  q={q:.2f}: supply short"); continue
    neg = L.real_draw(pool, tg, 0); v = L.i19(P, neg)
    print(f"  q={q:.2f} (top {100*(1-q):.0f}% of ME+VT stripped)  I19 ME {v['ME']:.4f} "
          f"NH {v['NH']:.4f} VT {v['VT']:.4f} worst {v['worst']:.4f}  "
          f"{'PASSES 0.64' if v['worst']<=0.64 else 'fails'}")

print("\nMulti-seed robustness, 20 seeds each:")
for tag, mk in (("FAIR", None),
                ("10A  ME+VT southern-80%-of-30km-cell skew", 'cell'),
                ("10A' ME+VT northern-25%-strip removal", 'strip')):
    ws, harms = [], []
    for sd in range(20):
        C2, tg = build(sd); L.TARGETS = tg
        if mk is None: pool = C2
        elif mk == 'strip':
            pool, _ = strip(C2, tg, ("ME","VT"), 0.75)
            if pool is None: continue
        else:
            sub = []
            for (r,s),n in tg.items():
                p = C2[(C2.state==r)&(C2.split==s)]
                if r in ("ME","VT"):
                    cell = np.floor(p.y_5070.values/30000.)
                    lo = pd.Series(p.y_5070.values).groupby(cell).transform(
                            lambda v: v.quantile(0.80)).values
                    k = p[p.y_5070.values <= lo]
                    nv=int(k.is_nonveg.sum()); hb=len(k)-nv
                    n_nv=min(int(round(n*L.NONVEG_MAX_FRAC)),nv)
                    if hb>=n-n_nv and len(k)>=n: p=k
                sub.append(p)
            pool = pd.concat(sub, ignore_index=True)
        neg = L.real_draw(pool, tg, sd)
        v = L.i19(P, neg); ws.append(v['worst'])
        # harm: worst-region frac of positives with NO negative within the
        # receptive field, restricted to the stranded area
        hh = []
        for r in ("ME","VT"):
            p = P[P.state==r]; n = neg[neg.state==r]
            d,_ = cKDTree(n[['x_5070','y_5070']].values).query(p[['x_5070','y_5070']].values,k=1)
            if mk == 'strip':
                thr = np.quantile(C2[C2.state==r].y_5070.values, 0.75)
                m = p.y_5070.values > thr
            else:
                cy = np.floor(p.y_5070.values/30000.)
                thr = pd.Series(p.y_5070.values).groupby(cy).transform(
                        lambda v: v.quantile(0.80)).values
                m = p.y_5070.values > thr
            hh.append(float((d[m] > L.RF).mean()) if m.sum() else np.nan)
        harms.append(max(hh))
    ws = np.array(ws); harms = np.array(harms)
    print(f"  {tag:44} I19 worst min {ws.min():.4f} max {ws.max():.4f} "
          f"| all <=0.64: {bool((ws<=0.64).all())} | stranded-band "
          f"frac>1920m max {np.nanmax(harms):.4f}")
