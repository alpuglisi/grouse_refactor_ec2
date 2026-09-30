"""RESEARCH (read-only): SIZE-INVARIANT candidate-supply gate.
res_supply_6 showed the raw statistics are confounded with pool SIZE: a 25 %
aspatial loss reaches SUP1 0.359 / SUP2 12.10 km, which swamps a 1-5 % northern
band loss.  Fix: normalise the worst sub-region reading by the TYPICAL
sub-region reading of the same pool.  Aspatial loss scales both and the ratio
is invariant; a geographic band loss inflates only the numerator."""
import sys, pickle, numpy as np, pandas as pd
from scipy.spatial import cKDTree
SCR="/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R=["ME","NH","VT"]; RF=1920.0
def p(*a): print(*a); sys.stdout.flush()
POS=pd.read_csv(f"{SCR}/fc_pos.csv"); FAIR=pd.read_csv(f"{SCR}/fc_pool.csv")
PXY=POS[['x_5070','y_5070']].values; PST=POS.state.values
PM={r:(PST==r) for r in R}
CXY={r:FAIR[FAIR.state==r][['x_5070','y_5070']].values for r in R}
CY ={r:FAIR[FAIR.state==r].y_5070.values for r in R}

def groups(G,nmin):
    c=(np.floor(PXY[:,0]/G).astype(np.int64)*1000000+np.floor(PXY[:,1]/G).astype(np.int64))
    o=np.argsort(c,kind='stable'); cs=c[o]
    b=np.flatnonzero(np.r_[True,cs[1:]!=cs[:-1]]); e=np.r_[b[1:],len(cs)]
    sel=(e-b)>=nmin; return o,b[sel],e[sel]
KEYS=[(10000.,5),(20000.,10)]
GR={k:groups(*k) for k in KEYS}
REGOF={}
for k in KEYS:
    o,b,e=GR[k]; REGOF[k]=np.array([PST[o[i]] for i in b])

def dists(pools):
    d=np.full(len(PXY),np.inf)
    for r in R:
        if len(pools[r]): d[PM[r]],_=cKDTree(pools[r]).query(PXY[PM[r]],k=1)
    return d
def cellmeds(d,k):
    o,b,e=GR[k]; ds=d[o]
    return np.array([np.median(ds[i:j]) for i,j in zip(b,e)])

def ALL(pools):
    d=dists(pools); o={}
    o['SUP1']=max(float((d[PM[r]]>RF).mean()) for r in R)
    o['SUP3n']=int((d>10000).sum())
    for k in KEYS:
        cm=cellmeds(d,k); tag=f"{int(k[0]/1000)}k"
        o[f'SUP2_{tag}']=cm.max()/1000
        o[f'RAT_{tag}']=float(cm.max()/np.median(cm))              # global worst/typical
        pr=[]                                                       # per-region worst/typical
        for r in R:
            v=cm[REGOF[k]==r]
            if len(v)>=5: pr.append(v.max()/np.median(v))
        o[f'RATR_{tag}']=float(max(pr))
        # orphan count, size-free: positives farther than 10x the pool's typical cell median
        thr=10.0*float(np.median(cm)); o[f'ORPH_{tag}']=int((d>thr).sum())
    return o

def strip(q,regs=("ME","VT")):
    return {r:(CXY[r][CY[r]<=np.quantile(CY[r],q)] if r in regs else CXY[r]) for r in R}
def skew(f,G,regs=("ME","VT")):
    out={}
    for r in R:
        if r not in regs: out[r]=CXY[r]; continue
        cv=np.floor(CY[r]/G)
        lo=pd.Series(CY[r]).groupby(cv).transform(lambda v:v.quantile(f)).values
        out[r]=CXY[r][CY[r]<=lo]
    return out
cov=pd.read_csv(f"{SCR}/rs1_cand_predropna.csv")
outk=set(map(tuple,cov[cov.keep_today&~(cov.in_nlcd&cov.in_tiger&cov.in_dist)][['longitude','latitude']].round(5).values))
k8=np.array([kk not in outk for kk in map(tuple,FAIR[['longitude','latitude']].round(5).values)])
P8={r:FAIR[k8&(FAIR.state.values==r)][['x_5070','y_5070']].values for r in R}

POOLS={"FAIR":CXY,"POST-CR-0008":P8}
for q in (0.995,0.99,0.98,0.97,0.95,0.90,0.85): POOLS[f"strip q={q}"]=strip(q)
for f,G in ((0.97,20000.),(0.95,20000.),(0.90,20000.),(0.85,30000.),(0.75,60000.)):
    POOLS[f"skew f={f} G={int(G/1000)}k"]=skew(f,G)
POOLS["strip q=0.90 ME only"]=strip(0.90,("ME",))
POOLS["strip q=0.90 VT only"]=strip(0.90,("VT",))

COLS=['SUP1','SUP3n','SUP2_10k','RAT_10k','RATR_10k','ORPH_10k','SUP2_20k','RAT_20k','RATR_20k','ORPH_20k']
A={nm:ALL(PL) for nm,PL in POOLS.items()}
p("=== pools ===")
p(f"{'pool':22} " + " ".join(f"{c:>9}" for c in COLS))
for nm in POOLS: p(f"{nm:22} " + " ".join(f"{A[nm][c]:>9.4f}" if isinstance(A[nm][c],float) else f"{A[nm][c]:>9d}" for c in COLS))

p("\n=== nulls: aspatial candidate loss (400x each) + I6 positive tolerance ===")
N={}
for frac in (0.05,0.115,0.25,0.40,0.60):
    rs=[]
    for i in range(400):
        rng=np.random.default_rng(int(frac*1000)*7717+i)
        PL={r:CXY[r][rng.choice(len(CXY[r]),int(round(len(CXY[r])*(1-frac))),replace=False)] for r in R}
        rs.append(ALL(PL))
    N[frac]=pd.DataFrame(rs); p(f"  frac={frac} done")
p(f"\n{'stat':10} {'FAIR':>9} " + " ".join(f"{'asp'+str(f)+'max':>11}" for f in N) + f" {'ASPMAX':>9}")
ASP={}
for c in COLS:
    ASP[c]=max(N[f][c].max() for f in N)
    p(f"{c:10} {A['FAIR'][c]:>9.4f} " + " ".join(f"{N[f][c].max():>11.4f}" for f in N) + f" {ASP[c]:>9.4f}")

p("\n=== separation: ASPATIAL-NULL MAX (all fractions to 60%) vs each depletion ===")
p(f"{'stat':10} {'aspMAX':>9} " + " ".join(f"{nm.replace('strip ','s').replace('skew ','k')[:9]:>9}" for nm in POOLS if nm not in('FAIR','POST-CR-0008')))
for c in COLS:
    p(f"{c:10} {ASP[c]:>9.4f} " + " ".join(f"{A[nm][c]:>9.4f}" if isinstance(A[nm][c],float) else f"{A[nm][c]:>9d}"
      for nm in POOLS if nm not in('FAIR','POST-CR-0008')))
pickle.dump({'A':A,'N':N,'ASP':ASP}, open(f"{SCR}/rs7.pkl","wb"))
p("\nsaved rs7.pkl")
