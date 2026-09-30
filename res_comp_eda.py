"""RES-COMP: EDA + timing on the faithful FORMAL-C pool.  READ-ONLY."""
import time, numpy as np, pandas as pd
import inv_formalC_lib as L
CONT = ["ch","cc","tcc","road_dist","tsd","balive","tpa_live","qmd","carbon_dwn"]
P, C = L.load()
FP = pd.read_csv(f"{L.SCR}/fc_feat_pos.csv"); FC = pd.read_csv(f"{L.SCR}/fc_feat_pool.csv")
P = pd.concat([P, FP], axis=1); C = pd.concat([C, FC], axis=1)
print("pos", len(P), P.state.value_counts().to_dict())
print("pool", len(C), C.state.value_counts().to_dict())
print("pool nonveg share overall", round(float(C.is_nonveg.mean()),4))
print("pool nonveg by region", C.groupby('state').is_nonveg.mean().round(4).to_dict())
print("\nfeature nan frac (pool):", {f: round(float(C[f].isna().mean()),4) for f in CONT})
print("feature nan frac (pos ):", {f: round(float(P[f].isna().mean()),4) for f in CONT})
print("\npool feature describe:")
print(C[CONT].describe().T[['mean','std','min','50%','max']].round(2))
print("\nhabitat-only pool feature describe:")
print(C.loc[~C.is_nonveg, CONT].describe().T[['mean','std','min','50%','max']].round(2))
print("\nweight_basis pool:", C.weight_basis.value_counts().to_dict())
print("weight by basis:", C.groupby('weight_basis').weight.agg(['mean','min','max']).round(3).to_dict('index'))
print("n distinct envelope_id in pool:", C.envelope_id.nunique(),
      " habitat-only:", C.loc[~C.is_nonveg,'envelope_id'].nunique())

t0=time.time()
vb = L.val_blocks(P, 42)
P['split'] = np.where(P.blk.isin(vb),'val','train')
pb = set(P.blk.unique()); bt = {b:('val' if b in vb else 'train') for b in pb}
gvf = len(vb)/len(pb)
C['split'] = [bt[b] if b in bt else L.hash_split(b,gvf,42) for b in C.blk]
L.TARGETS = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
print("\nsplit assign %.2fs" % (time.time()-t0))
print("global block val fraction", round(gvf,4), " positive blocks", len(pb),
      " positive-free candidate blocks", C.loc[~C.blk.isin(pb),'blk'].nunique())
print("TARGETS", L.TARGETS)
print("eligible pool per (r,s):")
for (r,s),n in L.TARGETS.items():
    p = C[(C.state==r)&(C.split==s)]
    print(f"  {r}/{s}: pool {len(p):5d} hab {int((~p.is_nonveg).sum()):5d} "
          f"nv {int(p.is_nonveg.sum()):5d} | target {n:5d} hab-target {n-min(int(round(n*0.30)),int(p.is_nonveg.sum())):5d}")
t0=time.time()
neg = L.real_draw(C, L.TARGETS, 0)
print("real_draw %.3fs -> %d" % (time.time()-t0, len(neg)))
print("delivered nonveg share by (r,s):")
print(neg.groupby(['state','split']).is_nonveg.mean().round(4).to_dict())
from scipy.stats import ks_2samp
t0=time.time()
for f in CONT:
    ks_2samp(neg.loc[neg.split=='val',f].dropna(), neg.loc[neg.split=='train',f].dropna())
print("9 pooled ks %.3fs" % (time.time()-t0))
