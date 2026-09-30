"""FORMAL C: independent verification of I16b's calibration (CR-0007 v6):
claimed ALL-record block set = 9,482 blocks, fair p50 -0.0006 / p99 0.0138 /
max 0.0159 over 40 seeds, negative-split attack 0.3409-0.3763 at z = 61.4.
Measured here on the FAITHFUL pool AND on the two candidate record sets the
row's wording admits (pool-occupied blocks vs selected-record blocks)."""
import numpy as np, pandas as pd, inv_formalC_lib as L
P, C = L.load()
pbset = set(P.blk.unique())
print(f"pos-occupied {len(pbset)}   pool-occupied {C.blk.nunique()}   "
      f"union {len(set(P.blk)|set(C.blk))}   [CR says 9,482 / 5,621 pos-free]")
fair_pool, fair_sel, atk_pool, atk_sel = [], [], [], []
selcnt = []
for sd in range(40):
    vb = L.val_blocks(P, sd)
    P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
    bt = {b: ('val' if b in vb else 'train') for b in pbset}
    gvf = len(vb)/len(pbset)
    L.TARGETS = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
    free = np.array(sorted(set(C.blk) - pbset))
    nval = int(round(gvf*len(free)))
    # FAIR: md5 hash of the block id, as split_for_unassigned does
    fsp = {b: L.hash_split(b, gvf, sd) for b in free}
    # BREAK 2 ATTACK: any block-ordered rule -- global ids are bx_by so
    # sorting the id IS sorting on x
    bx = np.floor_divide(free, 1000000)
    atkset = set(free[np.argsort(-bx)[:nval]])
    asp = {b: ('val' if b in atkset else 'train') for b in free}
    for sp, poolacc, selacc in ((fsp, fair_pool, fair_sel), (asp, atk_pool, atk_sel)):
        C2 = C.copy()
        C2['split'] = [bt[b] if b in bt else sp[b] for b in C2.blk]
        pbk = C2.drop_duplicates('blk')
        poolacc.append(L.moran(np.array(sorted(set(P.blk)|set(C2.blk))),
                               [ (bt[b] if b in bt else sp[b])=='val'
                                 for b in sorted(set(P.blk)|set(C2.blk))], k=8))
        neg = L.real_draw(C2, L.TARGETS, sd)
        rec = pd.concat([P[['blk','split']], neg[['blk','split']]], ignore_index=True)
        ar = rec.drop_duplicates('blk')
        selacc.append(L.moran(ar.blk.values, (ar.split=='val').values, k=8))
        if sp is fsp: selcnt.append(len(ar))
q = lambda a: (f"min {np.min(a):.4f} p50 {np.median(a):.4f} p99 {np.percentile(a,99):.4f} "
               f"max {np.max(a):.4f} sd {np.std(a):.4f}")
print("\nI16b, k=8, 40 seeds")
print("  READING 1 'pool-occupied blocks' (what the author calibrated):")
print(f"     fair   {q(fair_pool)}")
print(f"     attack {q(atk_pool)}   z = {(np.mean(atk_pool)-np.mean(fair_pool))/np.std(fair_pool):.1f}")
print("  READING 2 'blocks occupied by the SELECTED records' (what a train.py-level")
print("            assertion can actually see -- mean block count "
      f"{int(np.mean(selcnt))}):")
print(f"     fair   {q(fair_sel)}")
print(f"     attack {q(atk_sel)}   z = {(np.mean(atk_sel)-np.mean(fair_sel))/np.std(fair_sel):.1f}")
