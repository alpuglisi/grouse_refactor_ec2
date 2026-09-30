"""RESEARCH (read-only): candidate-SUPPLY statistics and gate calibration.
CR-0007 gates the negative DRAW (I19) but nothing gates the negative SUPPLY.
Computes a battery of supply statistics on the candidate pool, calibrates them
over 400 faithful re-runs of the pipeline's own randomness (the 30 m thin seed),
checks specificity against 400 size-matched ASPATIAL depletions, and scores the
Break-10A attacks and the post-CR-0008 pool."""
import os, sys, numpy as np, pandas as pd
from scipy.spatial import cKDTree
import generate_negatives as GN
from inv_formalA_thin import fast_thin_mask
import inv_formalC_lib as L

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME","NH","VT"]; RF = 1920.0
def p(*a): print(*a); sys.stdout.flush()
FEATS = ['evh','evt','sclass']

DED = pd.read_csv(f"{SCR}/rs2_dedup_feat.csv")
POS = pd.read_csv(f"{SCR}/fc_pos.csv")
EVxy = None
# buffer set = pooled own-state evaluated rows
ev = [pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv", low_memory=False) for r in R]
EV = pd.concat([e[e.state==r] for e,r in zip(ev,R)], ignore_index=True)
from pyproj import Transformer
T = Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
ex,ey = T.transform(EV.longitude.values, EV.latitude.values)
EVT = cKDTree(np.c_[ex,ey])
DXY = DED[['x_5070','y_5070']].values
OKFEAT = DED[FEATS].notna().all(axis=1).values
p("deduped candidates:", len(DED), " feat-complete:", int(OKFEAT.sum()))

def pool_for_seed(seed):
    keep = fast_thin_mask(DXY, GN.MIN_SPACING_M, seed)
    d,_ = EVT.query(DXY[keep], k=1)
    idx = np.flatnonzero(keep)[(d > GN.BUFFER_M) & OKFEAT[keep]]
    return DED.iloc[idx].reset_index(drop=True)

FAIR = pool_for_seed(42)
p("fair pool (seed 42):", len(FAIR), FAIR.groupby('state').size().to_dict(),
  "  (fc_pool.csv has", len(pd.read_csv(f'{SCR}/fc_pool.csv')), "rows)")

# ---------- splits, exactly as CR-0007 does them ----------
POS['blk'] = L.blk(POS.x_5070.values, POS.y_5070.values)
vb = L.val_blocks(POS, L.SEED)
POS['split'] = np.where(POS.blk.isin(vb), 'val', 'train')
pbset = set(POS.blk.unique()); bt = {b:('val' if b in vb else 'train') for b in pbset}
GVF = len(vb)/len(pbset)
def add_split(C):
    C = C.copy(); C['blk'] = L.blk(C.x_5070.values, C.y_5070.values)
    C['split'] = [bt[b] if b in bt else L.hash_split(b, GVF, L.SEED) for b in C.blk]
    return C
TARGETS = {(r,s): int(((POS.state==r)&(POS.split==s)).sum()) for r in R for s in ('train','val')}
p("targets:", TARGETS)

# ---------- supply statistics ----------
def stats(C, G=20000.0, nmin=10):
    C = add_split(C); out = {}
    dA, dS = np.full(len(POS), np.inf), np.full(len(POS), np.inf)
    for r in R:
        pm = (POS.state.values==r)
        cr = C[C.state==r]
        if len(cr):
            dA[pm],_ = cKDTree(cr[['x_5070','y_5070']].values).query(
                        POS.loc[pm,['x_5070','y_5070']].values, k=1)
        for s in ('train','val'):
            pmS = pm & (POS.split.values==s)
            cs = cr[cr.split==s]
            if pmS.sum() and len(cs):
                dS[pmS],_ = cKDTree(cs[['x_5070','y_5070']].values).query(
                             POS.loc[pmS,['x_5070','y_5070']].values, k=1)
    for tag, d in (('A', dA), ('S', dS)):
        per = {r: d[POS.state.values==r] for r in R}
        out[f'{tag}_frac_worst'] = max(float((v>RF).mean()) for v in per.values())
        for r in R: out[f'{tag}_frac_{r}'] = float((per[r]>RF).mean())
        out[f'{tag}_q90_worst'] = max(float(np.quantile(v,0.90))/1000 for v in per.values())
        out[f'{tag}_q95_worst'] = max(float(np.quantile(v,0.95))/1000 for v in per.values())
        out[f'{tag}_q99_worst'] = max(float(np.quantile(v,0.99))/1000 for v in per.values())
        # sub-region cell statistics on the SPLIT-AWARE / BLIND distance
        cell = (np.floor(POS.x_5070.values/G).astype(np.int64)*1000000
                + np.floor(POS.y_5070.values/G).astype(np.int64))
        cmed, cfrac = [], []
        for k, g in pd.DataFrame({'c':cell,'d':d}).groupby('c'):
            if len(g) >= nmin:
                cmed.append(np.median(g.d.values)/1000); cfrac.append(float((g.d.values>RF).mean()))
        out[f'{tag}_cellmed_max'] = max(cmed) if cmed else 0.0
        out[f'{tag}_cellfrac_max'] = max(cfrac) if cfrac else 0.0
        out[f'{tag}_ncell'] = len(cmed)
    return out

KEYS = ['A_frac_worst','A_q90_worst','A_q95_worst','A_q99_worst','A_cellmed_max','A_cellfrac_max',
        'S_frac_worst','S_q90_worst','S_q95_worst','S_q99_worst','S_cellmed_max','S_cellfrac_max']

fair = stats(FAIR)
p("\n=== FAIR pool, seed 42 ===")
for k in KEYS: p(f"  {k:20s} {fair[k]:.4f}")
p(f"  cells with >=10 positives at 20 km: {fair['A_ncell']}")
for r in R: p(f"  A_frac_{r} = {fair[f'A_frac_{r}']:.4f}   S_frac_{r} = {fair[f'S_frac_{r}']:.4f}")

# ---------- the pools under test ----------
cov = pd.read_csv(f"{SCR}/rs1_cand_predropna.csv")
outc = cov[cov.keep_today & ~(cov.in_nlcd & cov.in_tiger & cov.in_dist)]
outkey = set(map(tuple, outc[['longitude','latitude']].round(5).values))
def key(D): return list(map(tuple, D[['longitude','latitude']].round(5).values))
POST8 = FAIR[[k not in outkey for k in key(FAIR)]].reset_index(drop=True)
p(f"\nPOST-CR-0008 pool (centre pixel outside any G0 mask removed): "
  f"{len(FAIR)} -> {len(POST8)}  (removed {len(FAIR)-len(POST8)})")

def strip(C, q=0.85, regions=("ME","VT")):
    out=[]
    for r in R:
        s=C[C.state==r]
        if r in regions:
            s = s[s.y_5070.values <= np.quantile(s.y_5070.values, q)]
        out.append(s)
    return pd.concat(out, ignore_index=True)
A10 = strip(FAIR, 0.85)
def skew(C, f, G, regions=("ME","VT")):
    out=[]
    for r in R:
        s=C[C.state==r]
        if r in regions:
            cellv = np.floor(s.y_5070.values/G)
            lo = pd.Series(s.y_5070.values).groupby(cellv).transform(lambda v: v.quantile(f)).values
            s = s[s.y_5070.values <= lo]
        out.append(s)
    return pd.concat(out, ignore_index=True)

POOLS = {"FAIR": FAIR, "POST-CR0008": POST8,
         "ATK 10A'' north-15% ME+VT": A10,
         "ATK 10 skew f=0.60 G=60km": skew(FAIR,0.60,60000.),
         "ATK 10 skew f=0.75 G=60km": skew(FAIR,0.75,60000.),
         "ATK 10 skew f=0.85 G=30km": skew(FAIR,0.85,30000.)}

# ---------- Null A: 400 faithful pipeline seeds ----------
SEEDS = list(range(1000,1400))
rowsA = []
for i,sd in enumerate(SEEDS):
    rowsA.append(stats(pool_for_seed(sd)))
    if (i+1)%50==0: p(f"  nullA {i+1}/{len(SEEDS)}")
NA = pd.DataFrame(rowsA)
NA.to_csv(f"{SCR}/rs3_nullA.csv", index=False)

# ---------- Null B: 400 size-matched ASPATIAL depletions (matched to 10A'') ----------
rm = {r: int((FAIR.state==r).sum()) - int((A10.state==r).sum()) for r in R}
p("\naspatial null removal counts (matched to 10A''):", rm)
rowsB = []
for i in range(400):
    rng = np.random.default_rng(5000+i); keep=[]
    for r in R:
        s = FAIR[FAIR.state==r]
        idx = rng.choice(len(s), len(s)-rm[r], replace=False)
        keep.append(s.iloc[idx])
    rowsB.append(stats(pd.concat(keep, ignore_index=True)))
    if (i+1)%50==0: p(f"  nullB {i+1}/400")
NB = pd.DataFrame(rowsB)
NB.to_csv(f"{SCR}/rs3_nullB.csv", index=False)

p("\n================ SUPPLY STATISTIC SEPARATION ================")
hdr = f"{'statistic':20} {'fairP50':>9} {'fairP99':>9} {'fairMAX':>9} | {'aspatP99':>9} {'aspatMAX':>9} | " + " ".join(f"{k[:14]:>15}" for k in POOLS)
p(hdr)
SC = {k: stats(v) for k,v in POOLS.items()}
for k in KEYS:
    line = (f"{k:20} {NA[k].quantile(.50):>9.4f} {NA[k].quantile(.99):>9.4f} {NA[k].max():>9.4f} | "
            f"{NB[k].quantile(.99):>9.4f} {NB[k].max():>9.4f} | ")
    line += " ".join(f"{SC[nm][k]:>15.4f}" for nm in POOLS)
    p(line)
import pickle
pickle.dump({'NA':NA,'NB':NB,'SC':SC,'fair':fair}, open(f"{SCR}/rs3.pkl","wb"))
p("\nsaved rs3_nullA.csv rs3_nullB.csv rs3.pkl")
