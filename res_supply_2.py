"""RESEARCH (read-only): (a) 64x64 window exposure to CR-0008 nodata for the
CR-0007 positives and the negative candidate pool, per region and in the
northern border band; (b) cache evh/evt/sclass for the full deduped candidate
set so the supply-gate null can re-run the 30 m thin at many seeds faithfully."""
import os, sys, glob, numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from scipy.spatial import cKDTree
import generate_negatives as GN
from inv_formalA_thin import fast_thin
from analyze_grouse import ENVELOPE_SCHEME, sample_raster
from grouse_data import GrouseData

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME","NH","VT"]; IMG = 64
T = Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def p(*a): print(*a); sys.stdout.flush()
feats_needed = sorted({c for c,_ in ENVELOPE_SCHEME if c not in ("evt_phys","evt_group")} | {"sclass","evt"})

MASKS, GRID = {}, {}
for r in R:
    tpl = sorted(glob.glob(f"data/landfire/{r}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s: GRID[r] = (s.transform, s.crs, s.height, s.width)
    H, W = GRID[r][2], GRID[r][3]
    for nm,key in (("nlcd","nlcd"),("tiger_at1","tiger"),("dist2_cov_all_2025","dist")):
        MASKS[(r,key)] = np.unpackbits(np.load(f"{SCR}/{r}_{nm}.npy"))[:H*W].astype(bool).reshape(H,W)
p("masks loaded")

def rc(r, lon, lat):
    tr, crs, H, W = GRID[r]
    tx = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    x,y = tx.transform(np.asarray(lon,float), np.asarray(lat,float))
    c,rr = (~tr)*(x,y)
    return np.floor(rr).astype(np.int64), np.floor(c).astype(np.int64)

def win_out_frac(r, key, lon, lat):
    """fraction of the IMGxIMG window outside coverage (off-grid counts outside)"""
    tr,crs,H,W = GRID[r]; M = MASKS[(r,key)]
    rr,cc = rc(r, lon, lat); half = IMG//2
    out = np.empty(len(rr))
    for i in range(len(rr)):
        r0,c0 = rr[i]-half, cc[i]-half
        a,b = max(r0,0), max(c0,0)
        a2,b2 = min(r0+IMG,H), min(c0+IMG,W)
        inside = 0
        if a2>a and b2>b: inside = int(M[a:a2,b:b2].sum())
        out[i] = 1.0 - inside/(IMG*IMG)
    return out

POS = pd.read_csv(f"{SCR}/fc_pos.csv")
CAND = pd.read_csv(f"{SCR}/rs1_cand_predropna.csv")
CAND = CAND[CAND.keep_today].reset_index(drop=True)

# ---- northern band definitions ----
# (i) attack-comparable: top 15% of the region's CANDIDATE y_5070 (attack5's cut)
# (ii) geographic: within 25 km of the US/Canada land border, approximated as the
#      northern edge of the TIGER county union along the point's own column.
band_thr = {r: np.quantile(CAND[CAND.state==r].y_5070.values, 0.85) for r in R}
p("band thresholds (y_5070, top-15% of candidates):", {k: round(v) for k,v in band_thr.items()})

for name, D in (("POSITIVES", POS), ("CANDIDATES(kept)", CAND)):
    p(f"\n=== {name}: 64x64 window exposure to CR-0008 out-of-coverage ===")
    p(f"{'reg':4} {'n':>6} | {'any>0':>7} {'>10%':>6} {'>50%':>6} {'centre':>7} | "
      f"{'band n':>7} {'band any>0':>11} {'band centre':>12}")
    for r in R:
        s = D[D.state==r]
        if not len(s): continue
        f_nl = win_out_frac(r,"nlcd", s.longitude.values, s.latitude.values)
        f_ti = win_out_frac(r,"tiger", s.longitude.values, s.latitude.values)
        f_di = win_out_frac(r,"dist", s.longitude.values, s.latitude.values)
        f = np.max(np.c_[f_nl,f_ti,f_di], axis=1)     # worst of the three references
        rr,cc = rc(r, s.longitude.values, s.latitude.values)
        H,W = GRID[r][2], GRID[r][3]
        okg = (rr>=0)&(rr<H)&(cc>=0)&(cc<W)
        ctr = np.ones(len(s), bool)
        ctr[okg] = ~(MASKS[(r,"nlcd")][rr[okg],cc[okg]] & MASKS[(r,"tiger")][rr[okg],cc[okg]]
                     & MASKS[(r,"dist")][rr[okg],cc[okg]])
        b = s.y_5070.values > band_thr[r]
        p(f"{r:4} {len(s):>6} | {int((f>0).sum()):>7} {int((f>0.10).sum()):>6} "
          f"{int((f>0.50).sum()):>6} {int(ctr.sum()):>7} | {int(b.sum()):>7} "
          f"{int((f[b]>0).sum()):>11} {int(ctr[b].sum()):>12}")

# ---- cache features for the full deduped candidate set ----
if not os.path.exists(f"{SCR}/rs2_dedup_feat.csv"):
    C = pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv", low_memory=False)
                   for r in R], ignore_index=True)
    C = C[~(C['coord_uncertainty_m']>GN.MAX_COORD_UNCERTAINTY_M).fillna(False)].copy()
    C = C.loc[~C[['longitude','latitude']].round(5).duplicated()].copy()
    C['x_5070'],C['y_5070'] = T.transform(C.longitude.values, C.latitude.values)
    C = C.reset_index(drop=True)
    p(f"\ncaching {feats_needed} for {len(C)} deduped candidates ...")
    data = GrouseData()
    out = []
    for r in R:
        sub = C[C.state==r].copy(); rd = data[r]
        for f in feats_needed:
            vals = np.full(len(sub), np.nan)
            for yr in sorted(sub['year'].dropna().unique()):
                m = (sub['year']==yr).values
                vals[m] = sample_raster(rd.raster_path(f,int(yr)),
                                        sub.loc[m,'longitude'].values, sub.loc[m,'latitude'].values)
            sub[f]=vals
        out.append(sub); p(f"  {r} done ({len(sub)})")
    C = pd.concat(out, ignore_index=True)
    C[['longitude','latitude','state','year','x_5070','y_5070']+feats_needed].to_csv(
        f"{SCR}/rs2_dedup_feat.csv", index=False)
    p("cached", len(C))
