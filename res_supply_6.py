"""RESEARCH (read-only): finalise the candidate-SUPPLY gate -- sub-region scale
sweep, an 'orphaned positive' count statistic, and measured false-fail rates
under (1) the only positive-set variation CR-0007 admits (I6's +/-10 records)
and (2) aspatial candidate loss at five fractions.  Numpy-only hot loop."""
import sys, pickle, numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
SCR="/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R=["ME","NH","VT"]; RF=1920.0
def p(*a): print(*a); sys.stdout.flush()
POS=pd.read_csv(f"{SCR}/fc_pos.csv"); FAIR=pd.read_csv(f"{SCR}/fc_pool.csv")
PXY=POS[['x_5070','y_5070']].values; PST=POS.state.values
PM={r:(PST==r) for r in R}
CXY={r:FAIR[FAIR.state==r][['x_5070','y_5070']].values for r in R}
CY ={r:FAIR[FAIR.state==r].y_5070.values for r in R}

def cellcode(G): return (np.floor(PXY[:,0]/G).astype(np.int64)*1000000
                         +np.floor(PXY[:,1]/G).astype(np.int64))
def groups(G,nmin):
    c=cellcode(G); o=np.argsort(c,kind='stable'); cs=c[o]
    b=np.flatnonzero(np.r_[True,cs[1:]!=cs[:-1]]); e=np.r_[b[1:],len(cs)]
    sel=(e-b)>=nmin
    return o,b[sel],e[sel]
GRIDS={(G,n):groups(G,n) for G,n in ((10000.,5),(10000.,10),(20000.,10),(30000.,10),(60000.,10))}

def dists(pools, pmask=None):
    d=np.full(len(PXY),np.inf)
    for r in R:
        m=PM[r] if pmask is None else (PM[r]&pmask)
        if m.sum() and len(pools[r]): d[m],_=cKDTree(pools[r]).query(PXY[m],k=1)
    return d
def cellmax(d,key):
    o,b,e=GRIDS[key]; ds=d[o]
    return max(np.median(ds[i:j]) for i,j in zip(b,e))/1000.0
def SUP(pools,pmask=None,key=(20000.,10)):
    d=dists(pools,pmask); m=np.ones(len(d),bool) if pmask is None else pmask
    return {'SUP1':max(float((d[PM[r]&m]>RF).mean()) for r in R),
            'SUP2':cellmax(np.where(m,d,-1e9) if pmask is not None else d,key) if pmask is None
                   else cellmax(np.where(m,d,np.nan),key),
            'SUP3':float((d[m]>10000).mean()),'SUP3n':int((d[m]>10000).sum()),'_d':d}
def cellmax_nan(d,key):
    o,b,e=GRIDS[key]; ds=d[o]
    return max(np.nanmedian(ds[i:j]) for i,j in zip(b,e))/1000.0

def strip(q,regs):
    return {r:(CXY[r][CY[r]<=np.quantile(CY[r],q)] if r in regs else CXY[r]) for r in R}
def skew(f,G,regs):
    out={}
    for r in R:
        if r not in regs: out[r]=CXY[r]; continue
        cv=np.floor(CY[r]/G)
        lo=pd.Series(CY[r]).groupby(cv).transform(lambda v:v.quantile(f)).values
        out[r]=CXY[r][CY[r]<=lo]
    return out
cov=pd.read_csv(f"{SCR}/rs1_cand_predropna.csv")
outk=set(map(tuple,cov[cov.keep_today&~(cov.in_nlcd&cov.in_tiger&cov.in_dist)][['longitude','latitude']].round(5).values))
keep8=np.array([k not in outk for k in map(tuple,FAIR[['longitude','latitude']].round(5).values)])
P8={r:FAIR[keep8&(FAIR.state.values==r)][['x_5070','y_5070']].values for r in R}

POOLS={"FAIR":CXY,"POST-CR-0008":P8}
for q in (0.99,0.98,0.97,0.95,0.90,0.85): POOLS[f"strip q={q}"]=strip(q,("ME","VT"))
for f,G in ((0.95,20000.),(0.90,20000.),(0.85,30000.),(0.75,60000.)):
    POOLS[f"skew f={f} G={int(G/1000)}km"]=skew(f,G,("ME","VT"))

p("=== SUP2 sub-region scale sweep: max over G-km cells (>=nmin positives) of")
p("    median(positive -> nearest CANDIDATE), km ===")
p(f"{'pool':20} " + " ".join(f"{int(G/1000)}km/n{n:<2}" for G,n in GRIDS) + f"  {'SUP1':>7} {'SUP3n':>6}")
for nm,PL in POOLS.items():
    d=dists(PL)
    p(f"{nm:20} " + " ".join(f"{cellmax(d,k):9.2f}" for k in GRIDS) +
      f"  {max(float((d[PM[r]]>RF).mean()) for r in R):7.4f} {int((d>10000).sum()):>6}")
p(f"\ncells with >=10 positives at 20 km: {len(GRIDS[(20000.,10)][1])}; at 10 km/n5: {len(GRIDS[(10000.,5)][1])}")

KEY=(20000.,10)
def stats3(PL,pmask=None):
    d=dists(PL,pmask)
    if pmask is None:
        return dict(SUP1=max(float((d[PM[r]]>RF).mean()) for r in R),
                    SUP2=cellmax(d,KEY), SUP3=float((d>10000).mean()))
    dd=np.where(pmask,d,np.nan)
    return dict(SUP1=max(float((dd[PM[r]][~np.isnan(dd[PM[r]])]>RF).mean()) for r in R),
                SUP2=cellmax_nan(dd,KEY), SUP3=float(np.nanmean(dd>10000)))
base=stats3(CXY)
p(f"\nFAIR: SUP1 {base['SUP1']:.4f}  SUP2 {base['SUP2']:.3f} km  SUP3 {base['SUP3']:.5f}")

p("\n=== false-fail null 1: I6's own tolerance (10 positives dropped at random), 400x ===")
r1=[]
for i in range(400):
    rng=np.random.default_rng(700000+i); m=np.ones(len(PXY),bool)
    m[rng.choice(len(PXY),10,replace=False)]=False
    r1.append(stats3(CXY,m))
N1=pd.DataFrame(r1)
for k in ('SUP1','SUP2','SUP3'):
    p(f"  {k}: p50 {N1[k].quantile(.5):.4f} p99 {N1[k].quantile(.99):.4f} max {N1[k].max():.4f}")

p("\n=== false-fail null 2: aspatial candidate loss, 400x at each fraction ===")
N2={}
for frac in (0.05,0.115,0.25,0.40,0.60):
    rs=[]
    for i in range(400):
        rng=np.random.default_rng(int(frac*1000)*7717+i)
        PL={r:CXY[r][rng.choice(len(CXY[r]),int(round(len(CXY[r])*(1-frac))),replace=False)] for r in R}
        rs.append(stats3(PL))
    N2[frac]=pd.DataFrame(rs)
    p(f"  frac={frac:<5} " + "  ".join(f"{k} p99 {N2[frac][k].quantile(.99):.4f} max {N2[frac][k].max():.4f}"
                                        for k in ('SUP1','SUP2','SUP3')))

ATT={nm:stats3(PL) for nm,PL in POOLS.items()}
p("\n=== GATE SCORING ===")
for k,t in (('SUP1',0.33),('SUP2',12.0),('SUP3',0.004)):
    ff1=int((N1[k]>t).sum()); ff2={f:int((N2[f][k]>t).sum()) for f in N2}
    p(f"\n  {k} <= {t}   fair {base[k]:.4f}")
    p(f"    false-fail: I6-null {ff1}/400 ; aspatial-null " +
      " ".join(f"{f}:{v}/400" for f,v in ff2.items()))
    p("    " + "  ".join(f"{nm}={ATT[nm][k]:.4f}" for nm in POOLS))
pickle.dump({'N1':N1,'N2':N2,'ATT':ATT,'base':base}, open(f"{SCR}/rs6.pkl","wb"))
p("\nsaved rs6.pkl")
