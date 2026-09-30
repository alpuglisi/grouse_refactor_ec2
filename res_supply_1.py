"""RESEARCH (read-only): does CR-0008's repair actually drop negative
candidates at generate_negatives.py:213, and does it do so asymmetrically
vs positives?  Rebuilds the PRE-dropna candidate set (geometry only, no
raster sampling) and samples CR-0008's three pre-registered G0 coverage
masks at every candidate and every CR-0007 positive."""
import os, sys, glob, numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from scipy.spatial import cKDTree
import generate_negatives as GN
from inv_formalA_thin import fast_thin
from analyze_grouse import ENVELOPE_SCHEME, REQUIRED_FEATURES, sample_raster, RASTER_DIR

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME", "NH", "VT"]
T = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
def p(*a): print(*a); sys.stdout.flush()

feats_needed = sorted({c for c, _ in ENVELOPE_SCHEME if c not in ("evt_phys","evt_group")} | {"sclass","evt"})
CR8_SCOPE = ["road_dist","tsd","balive","tpa_live","qmd","carbon_dwn","tcc"]
p("negative-candidate dropna set (generate_negatives.py:196-207) :", feats_needed)
p("positive   dropna set (analyze_grouse.py:708 REQUIRED_FEATURES):", REQUIRED_FEATURES)
p("CR-0008 in-scope rasters                                       :", CR8_SCOPE)
p("intersection(neg filter, CR-0008 scope) =", sorted(set(feats_needed) & set(CR8_SCOPE)))
p("intersection(pos filter, CR-0008 scope) =", sorted(set(REQUIRED_FEATURES) & set(CR8_SCOPE)))

# ---------- masks ----------
MASKS = {}
GRID = {}
for r in R:
    tpl = sorted(glob.glob(f"data/landfire/{r}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s:
        GRID[r] = (s.transform, s.crs, s.height, s.width)
    H, W = GRID[r][2], GRID[r][3]
    for nm, key in (("nlcd","nlcd"), ("tiger_at1","tiger"), ("dist2_cov_all_2025","dist")):
        a = np.load(f"{SCR}/{r}_{nm}.npy")
        MASKS[(r,key)] = np.unpackbits(a)[:H*W].astype(bool).reshape(H, W)
    a = np.load(f"{SCR}/{r}_evt.npy")
    MASKS[(r,"evt")] = np.unpackbits(a)[:H*W].astype(bool).reshape(H, W)
p("masks loaded")

def mask_at(r, key, lon, lat):
    tr, crs, H, W = GRID[r]
    tx = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    x, y = tx.transform(np.asarray(lon), np.asarray(lat))
    inv = ~tr
    c, rr = inv * (x, y)
    c = np.floor(c).astype(np.int64); rr = np.floor(rr).astype(np.int64)
    ok = (c >= 0) & (c < W) & (rr >= 0) & (rr < H)
    out = np.zeros(len(c), bool)           # off-grid counts as OUTSIDE coverage
    out[ok] = MASKS[(r,key)][rr[ok], c[ok]]
    return out, ok

# ---------- positives (CR-0007 pooled record set) ----------
POS = pd.read_csv(f"{SCR}/fc_pos.csv")
p("\npositives (CR-0007 pooled):", len(POS), POS.groupby('state').size().to_dict())

# ---------- pre-dropna candidate set, geometry only ----------
ev = [pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv", low_memory=False) for r in R]
EV = pd.concat([e[e.state == r] for e, r in zip(ev, R)], ignore_index=True)
C = pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv", low_memory=False)
               for r in R], ignore_index=True)
n0 = len(C); C = C[~(C['coord_uncertainty_m'] > GN.MAX_COORD_UNCERTAINTY_M).fillna(False)].copy()
n1 = len(C); C = C.loc[~C[['longitude','latitude']].round(5).duplicated()].copy()
C['x_5070'], C['y_5070'] = T.transform(C.longitude.values, C.latitude.values)
n2 = len(C); C = fast_thin(C.reset_index(drop=True), GN.MIN_SPACING_M, 42)
ex, ey = T.transform(EV.longitude.values, EV.latitude.values)
d, _ = cKDTree(np.c_[ex, ey]).query(C[['x_5070','y_5070']].values, k=1)
n3 = len(C); C = C[d > GN.BUFFER_M].copy().reset_index(drop=True)
p(f"candidates: raw {n0} -> unc {n1} -> dedup {n2} -> thin {n3} -> buffer {len(C)}  (PRE-dropna)")
p("  per region:", C.groupby('state').size().to_dict())

# ---------- the REAL current dropna, reproduced ----------
rows = []
for r in R:
    sub = C[C.state == r].copy()
    from grouse_data import GrouseData
    rd = GrouseData()[r]
    for f in feats_needed:
        vals = np.full(len(sub), np.nan)
        for yr in sorted(sub['year'].dropna().unique()):
            m = (sub['year'] == yr).values
            vals[m] = sample_raster(rd.raster_path(f, int(yr)),
                                    sub.loc[m,'longitude'].values, sub.loc[m,'latitude'].values)
        sub[f] = vals
    sub['keep_today'] = sub[feats_needed].notna().all(axis=1)
    for key in ("nlcd","tiger","dist","evt"):
        inside, ong = mask_at(r, key, sub.longitude.values, sub.latitude.values)
        sub[f'in_{key}'] = inside
        sub[f'ongrid'] = ong
    rows.append(sub)
CC = pd.concat(rows, ignore_index=True)
CC.to_csv(f"{SCR}/rs1_cand_predropna.csv", index=False)

# positives mask status
prow = []
for r in R:
    sub = POS[POS.state == r].copy()
    for key in ("nlcd","tiger","dist","evt"):
        inside, ong = mask_at(r, key, sub.longitude.values, sub.latitude.values)
        sub[f'in_{key}'] = inside
    prow.append(sub)
PP = pd.concat(prow, ignore_index=True)
PP.to_csv(f"{SCR}/rs1_pos_cov.csv", index=False)

p("\n=== today's dropna at generate_negatives.py:207, per region ===")
for r in R:
    s = CC[CC.state == r]
    p(f"  {r}: pre {len(s):>6}  kept {int(s.keep_today.sum()):>6}  dropped {int((~s.keep_today).sum()):>6}"
      f"  ({100*(~s.keep_today).mean():.2f}%)")
p(f"  ALL: pre {len(CC)} kept {int(CC.keep_today.sum())} dropped {int((~CC.keep_today).sum())}")
p("  (cross-check vs fc_pool.csv rows =", len(pd.read_csv(f'{SCR}/fc_pool.csv')), ")")

p("\n=== CR-0008 coverage status of the SURVIVING candidate pool (kept_today) ===")
p(f"{'reg':4} {'pool':>7} {'out_nlcd':>9} {'out_tiger':>10} {'out_dist':>9} {'out_ANY3':>9}")
for r in R:
    s = CC[(CC.state == r) & CC.keep_today]
    anyout = (~s.in_nlcd) | (~s.in_tiger) | (~s.in_dist)
    p(f"{r:4} {len(s):>7} {int((~s.in_nlcd).sum()):>9} {int((~s.in_tiger).sum()):>10} "
      f"{int((~s.in_dist).sum()):>9} {int(anyout.sum()):>9}")

p("\n=== CR-0008 coverage status of the CR-0007 POSITIVES ===")
p(f"{'reg':4} {'pos':>7} {'out_nlcd':>9} {'out_tiger':>10} {'out_dist':>9} {'out_ANY3':>9}")
for r in R:
    s = PP[PP.state == r]
    anyout = (~s.in_nlcd) | (~s.in_tiger) | (~s.in_dist)
    p(f"{r:4} {len(s):>7} {int((~s.in_nlcd).sum()):>9} {int((~s.in_tiger).sum()):>10} "
      f"{int((~s.in_dist).sum()):>9} {int(anyout.sum()):>9}")
p("\nsaved rs1_cand_predropna.csv, rs1_pos_cov.csv")
