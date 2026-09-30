"""RESEARCH (read-only): final gate scoring from the pickled nulls, the pool-size
floor SUP0, the I6-tolerance null at the 10 km key, and the band-level harm of
Break 10A against the post-CR-0008 pool."""
import pickle, numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
SCR="/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R=["ME","NH","VT"]; RF=1920.0
def p(*a): print(*a)
d7=pickle.load(open(f"{SCR}/rs7.pkl","rb")); A,N=d7['A'],d7['N']
POS=pd.read_csv(f"{SCR}/fc_pos.csv"); FAIR=pd.read_csv(f"{SCR}/fc_pool.csv")
POS['blk']=L.blk(POS.x_5070.values,POS.y_5070.values)
FAIR['blk']=L.blk(FAIR.x_5070.values,FAIR.y_5070.values)
vb=L.val_blocks(POS,L.SEED); POS['split']=np.where(POS.blk.isin(vb),'val','train')
pb=set(POS.blk.unique()); bt={b:('val' if b in vb else 'train') for b in pb}
GVF=len(vb)/len(pb)
FAIR['split']=[bt[b] if b in bt else L.hash_split(b,GVF,L.SEED) for b in FAIR.blk]
L.TARGETS={(r,s):int(((POS.state==r)&(POS.split==s)).sum()) for r in R for s in ('train','val')}

p("=== SUP0: candidate pool per (region, split) / negative target ===")
p(f"{'reg/split':12} {'target':>7} {'pool':>7} {'ratio':>7} {'habitat':>8} {'hab ratio':>10}")
for (r,s),n in L.TARGETS.items():
    pl=FAIR[(FAIR.state==r)&(FAIR.split==s)]
    hb=int((~pl.is_nonveg.astype(bool)).sum())
    p(f"{r}/{s:<7} {n:>7} {len(pl):>7} {len(pl)/n:>7.2f} {hb:>8} {hb/n:>10.2f}")
p(f"  worst overall ratio = {min(len(FAIR[(FAIR.state==r)&(FAIR.split==s)])/n for (r,s),n in L.TARGETS.items()):.2f}")

p("\n=== exact false-fail counts at the proposed thresholds ===")
for stat,thr in (('ORPH_10k',3),('RATR_10k',9.0),('SUP2_10k',11.0)):
    row=" ".join(f"{f}:{int((N[f][stat]>thr).sum())}/400" for f in N)
    p(f"  {stat} <= {thr}   fair {A['FAIR'][stat]}   aspatial-null false-fail  {row}")

p("\n=== the 10A attack the brief names (northern 15 % of ME+VT candidates) ===")
def strip(q,regs=("ME","VT")):
    out=[]
    for r in R:
        s=FAIR[FAIR.state==r]
        if r in regs: s=s[s.y_5070.values<=np.quantile(s.y_5070.values,q)]
        out.append(s)
    return pd.concat(out,ignore_index=True)
cov=pd.read_csv(f"{SCR}/rs1_cand_predropna.csv")
outk=set(map(tuple,cov[cov.keep_today&~(cov.in_nlcd&cov.in_tiger&cov.in_dist)][['longitude','latitude']].round(5).values))
POST8=FAIR[[k not in outk for k in map(tuple,FAIR[['longitude','latitude']].round(5).values)]].reset_index(drop=True)
A10=strip(0.85)
for tag,C in (("FAIR",FAIR),("POST-CR-0008",POST8),("BREAK 10A'' q=0.85",A10)):
    neg=L.real_draw(C,L.TARGETS,0); tot=0
    line=[]
    for r in R:
        pm=POS.state.values==r
        thr=np.quantile(FAIR[FAIR.state==r].y_5070.values,0.85)
        band=pm&(POS.y_5070.values>thr)
        d,_=cKDTree(neg[neg.state==r][['x_5070','y_5070']].values).query(
              POS.loc[band,['x_5070','y_5070']].values,k=1)
        tot+=int(band.sum())
        line.append(f"{r}: n={int(band.sum())} med={np.median(d)/1000:.1f}km frac>1920m={(d>RF).mean():.3f}")
    p(f"  {tag:20} band positives {tot} | " + " | ".join(line))
