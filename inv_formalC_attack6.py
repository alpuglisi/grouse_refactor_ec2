"""FORMAL C: I8 ('exact': len(selected)==round(n_pos*NEG_RATIO), shortfall 0)
is claimed to 'catch every supply-restricting attack'.  It cannot: when the
HABITAT pool is undersupplied, generate_negatives.py fills the quota from
NonVeg beyond the 30 % cap (:281-289), so the count is always exact.  Nothing
in I1-I19 measures the NonVeg share of the delivered negatives.  READ-ONLY."""
import numpy as np, pandas as pd, inv_formalC_lib as L
P, C = L.load()
vb = L.val_blocks(P, L.SEED)
P['split'] = np.where(P.blk.isin(vb),'val','train')
pb=set(P.blk.unique()); bt={b:('val' if b in vb else 'train') for b in pb}
gvf=len(vb)/len(pb)
C['split']=[bt[b] if b in bt else L.hash_split(b,gvf,L.SEED) for b in C.blk]
L.TARGETS={(r,s):int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
for keep in (1.0,0.5,0.25,0.10,0.0):
    rng=np.random.default_rng(7)
    hab=C[~C.is_nonveg]; nv=C[C.is_nonveg]
    k=hab.iloc[rng.choice(len(hab),int(keep*len(hab)),replace=False)] if keep<1 else hab
    pool=pd.concat([k,nv],ignore_index=True)
    neg=L.real_draw(pool,L.TARGETS,0)
    ok=all(int(((neg.state==r)&(neg.split==s)).sum())==n for (r,s),n in L.TARGETS.items())
    v=L.i19(P,neg)
    print(f"  habitat pool kept {keep:4.0%}  -> delivered {len(neg)}  I8 exact: {ok}"
          f"  NonVeg share of negatives {neg.is_nonveg.mean():.3f} (documented cap 0.30)"
          f"  I19 worst {v['worst']:.4f} {'PASS' if v['worst']<=0.64 else 'FAIL'}")
