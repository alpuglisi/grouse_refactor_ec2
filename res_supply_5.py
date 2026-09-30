"""RESEARCH (read-only): design + calibrate a CANDIDATE-SUPPLY gate.
CR-0007 gates the negative DRAW (I19, I8, I16b); nothing gates the negative
SUPPLY.  Sweeps a family of geographic depletions of the candidate pool, scores
CR-0007's draw-side gates on each (so only depletions CR-0007 LETS THROUGH are
used to calibrate), and calibrates supply statistics against aspatial-depletion
nulls at four removal fractions x 400 replicates."""
import os, sys, pickle, numpy as np, pandas as pd
from scipy.spatial import cKDTree
import generate_negatives as GN
from inv_formalA_thin import fast_thin_mask
import inv_formalC_lib as L

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME","NH","VT"]; RF = 1920.0; GCELL = 20000.0; NMIN = 10
def p(*a): print(*a); sys.stdout.flush()

POS = pd.read_csv(f"{SCR}/fc_pos.csv")
FAIR = pd.read_csv(f"{SCR}/fc_pool.csv")
POS['blk'] = L.blk(POS.x_5070.values, POS.y_5070.values)
FAIR['blk'] = L.blk(FAIR.x_5070.values, FAIR.y_5070.values)
vb = L.val_blocks(POS, L.SEED)
POS['split'] = np.where(POS.blk.isin(vb), 'val','train')
pbset = set(POS.blk.unique()); bt = {b:('val' if b in vb else 'train') for b in pbset}
GVF = len(vb)/len(pbset)
FAIR['split'] = [bt[b] if b in bt else L.hash_split(b,GVF,L.SEED) for b in FAIR.blk]
L.TARGETS = {(r,s): int(((POS.state==r)&(POS.split==s)).sum()) for r in R for s in ('train','val')}
PXY = POS[['x_5070','y_5070']].values
CELL = (np.floor(POS.x_5070.values/GCELL).astype(np.int64)*1000000
        + np.floor(POS.y_5070.values/GCELL).astype(np.int64))
CELLDF = pd.DataFrame({'c':CELL})

def supply(C):
    """SUPPLY statistics: positives vs the CANDIDATE POOL (no draw involved)."""
    dA = np.full(len(POS), np.inf); dS = np.full(len(POS), np.inf)
    for r in R:
        pm = POS.state.values==r; cr = C[C.state==r]
        if len(cr):
            dA[pm],_ = cKDTree(cr[['x_5070','y_5070']].values).query(PXY[pm],k=1)
        for s in ('train','val'):
            pmS = pm & (POS.split.values==s); cs = cr[cr.split==s]
            if pmS.sum() and len(cs):
                dS[pmS],_ = cKDTree(cs[['x_5070','y_5070']].values).query(PXY[pmS],k=1)
    o = {}
    for tag,d in (('A',dA),('S',dS)):
        per = [d[POS.state.values==r] for r in R]
        o[f'{tag}_frac']  = max(float((v>RF).mean()) for v in per)
        o[f'{tag}_q95']   = max(float(np.quantile(v,.95)) for v in per)/1000
        g = pd.DataFrame({'c':CELL,'d':d}).groupby('c')
        med = [np.median(x.d.values)/1000 for _,x in g if len(x)>=NMIN]
        o[f'{tag}_cellmed'] = max(med)
    return o

def draw_side(C, seeds=(0,1,2,3,4)):
    """CR-0007's draw-side gates that the pool can move: I19 worst, I8, I16b."""
    i19, i8, i16b = [], [], []
    for sd in seeds:
        neg = L.real_draw(C, L.TARGETS, sd)
        i19.append(L.i19(POS,neg)['worst'])
        i8.append(all(int(((neg.state==r)&(neg.split==s)).sum())==n for (r,s),n in L.TARGETS.items()))
        rec = pd.concat([POS.assign(cls='pos'), neg.assign(cls='neg')], ignore_index=True)
        ar = rec.drop_duplicates('blk')
        i16b.append(abs(L.moran(ar.blk.values,(ar.split=='val').values,8)))
    return dict(I19_max=max(i19), I19_min=min(i19), I8_all=all(i8), I16b_k8_max=max(i16b))

def harm(C, seed=0):
    neg = L.real_draw(C, L.TARGETS, seed); out={}
    for r in R:
        pm = POS.state.values==r
        d,_ = cKDTree(neg[neg.state==r][['x_5070','y_5070']].values).query(PXY[pm],k=1)
        out[r]=(float(np.median(d))/1000, int((d>10000).sum()))
    return out

# ---------- depletion family ----------
def strip(q, regions):
    out=[]
    for r in R:
        s=FAIR[FAIR.state==r]
        if r in regions: s=s[s.y_5070.values<=np.quantile(s.y_5070.values,q)]
        out.append(s)
    return pd.concat(out,ignore_index=True)
def skew(f,G,regions):
    out=[]
    for r in R:
        s=FAIR[FAIR.state==r]
        if r in regions:
            cv=np.floor(s.y_5070.values/G)
            lo=pd.Series(s.y_5070.values).groupby(cv).transform(lambda v:v.quantile(f)).values
            s=s[s.y_5070.values<=lo]
        out.append(s)
    return pd.concat(out,ignore_index=True)

ATT = {}
for q in (0.97,0.95,0.92,0.90,0.85,0.80):
    ATT[f"north strip q={q} ME+VT"] = strip(q,("ME","VT"))
ATT["north strip q=0.90 ME only"] = strip(0.90,("ME",))
ATT["north strip q=0.90 VT only"] = strip(0.90,("VT",))
ATT["north strip q=0.90 all 3"]   = strip(0.90,("ME","NH","VT"))
for f,G in ((0.85,30000.),(0.75,60000.),(0.60,60000.),(0.90,20000.)):
    ATT[f"cell skew f={f} G={G/1000:.0f}km ME+VT"] = skew(f,G,("ME","VT"))

rows=[]
base_s = supply(FAIR); base_d = draw_side(FAIR)
p("=== FAIR (today's pool, 22,201 candidates) ===")
p("  supply:", {k:round(v,4) for k,v in base_s.items()})
p("  CR-0007 draw-side:", {k:(round(v,4) if isinstance(v,float) else v) for k,v in base_d.items()})
p("  harm (median pos->nearest-neg km, n>10km):", {k:(round(v[0],2),v[1]) for k,v in harm(FAIR).items()})

cov = pd.read_csv(f"{SCR}/rs1_cand_predropna.csv")
outk = set(map(tuple, cov[cov.keep_today & ~(cov.in_nlcd&cov.in_tiger&cov.in_dist)][['longitude','latitude']].round(5).values))
POST8 = FAIR[[k not in outk for k in map(tuple, FAIR[['longitude','latitude']].round(5).values)]].reset_index(drop=True)
ATT = {"POST-CR-0008 (real)": POST8, **ATT}

p(f"\n{'depletion':34} {'kept':>6} | {'I19max':>7} {'I8':>4} {'I16b':>7} {'CR7?':>6} | "
  f"{'A_frac':>7} {'A_q95':>7} {'A_cell':>7} {'S_frac':>7} {'S_q95':>7} {'S_cell':>7} | {'harm ME/VT km':>15}")
for nm,C in ATT.items():
    s = supply(C); d = draw_side(C); h = harm(C)
    ok = (d['I19_max']<=0.64) and d['I8_all'] and (d['I16b_k8_max']<=0.0159*3)
    rows.append(dict(name=nm, kept=len(C), **s, **d, cr7_pass=ok,
                     harmME=h['ME'][0], harmVT=h['VT'][0]))
    p(f"{nm:34} {len(C):>6} | {d['I19_max']:>7.4f} {str(d['I8_all']):>4} {d['I16b_k8_max']:>7.4f} "
      f"{'PASS' if ok else 'FAIL':>6} | {s['A_frac']:>7.4f} {s['A_q95']:>7.3f} {s['A_cellmed']:>7.3f} "
      f"{s['S_frac']:>7.4f} {s['S_q95']:>7.3f} {s['S_cellmed']:>7.3f} | "
      f"{h['ME'][0]:>7.2f}/{h['VT'][0]:<7.2f}")
AT = pd.DataFrame(rows)

# ---------- aspatial-depletion nulls ----------
p("\n=== aspatial-depletion nulls, 400 replicates at each removal fraction ===")
nulls={}
for frac in (0.05,0.115,0.25,0.40):
    rs=[]
    for i in range(400):
        rng=np.random.default_rng(int(frac*1000)*100000+i); keep=[]
        for r in R:
            s=FAIR[FAIR.state==r]
            idx=rng.choice(len(s),int(round(len(s)*(1-frac))),replace=False)
            keep.append(s.iloc[idx])
        rs.append(supply(pd.concat(keep,ignore_index=True)))
    nulls[frac]=pd.DataFrame(rs)
    p(f"  frac={frac:.3f} done")
for k in ('A_frac','A_q95','A_cellmed','S_frac','S_q95','S_cellmed'):
    p(f"  {k:10} fair {base_s[k]:>8.4f} | " + "  ".join(
        f"{f:.3f}: p99 {nulls[f][k].quantile(.99):>8.4f} max {nulls[f][k].max():>8.4f}" for f in nulls))

# ---------- threshold selection ----------
p("\n=== threshold selection: separate {fair, aspatial nulls} from {CR-0007-PASSING depletions} ===")
passing = AT[(AT.cr7_pass) & (AT.name!="POST-CR-0008 (real)")]
p("CR-0007-PASSING depletions used for calibration:", list(passing.name))
for k in ('A_frac','A_q95','A_cellmed','S_frac','S_q95','S_cellmed'):
    nmax25 = nulls[0.25][k].max(); nmax40 = nulls[0.40][k].max()
    amin = passing[k].min() if len(passing) else float('nan')
    thr = round(float(np.sqrt(max(nmax25, base_s[k])*amin)),4) if amin==amin else float('nan')
    ff = {f: int((nulls[f][k]>thr).sum()) for f in nulls}
    p(f"  {k:10} fair {base_s[k]:>8.4f}  null25max {nmax25:>8.4f}  null40max {nmax40:>8.4f}  "
      f"attackMIN {amin:>8.4f}  geom-mean THR {thr:>8.4f}  margin x{amin/thr:.2f}/{thr/max(nmax25,base_s[k]):.2f}  "
      f"false-fail {ff}")
pickle.dump({'AT':AT,'nulls':nulls,'base_s':base_s,'base_d':base_d}, open(f"{SCR}/rs5.pkl","wb"))
AT.to_csv(f"{SCR}/rs5_attacks.csv", index=False)
p("\nsaved rs5.pkl rs5_attacks.csv")
