"""FORMAL C review: build a FAITHFUL pooled candidate pool for CR-0007's
post-partition pipeline -- including the raster extraction dropna, the
envelope weights, is_nonveg and the full-evaluated 300 m buffer that
inv_fix_breaks.py omitted.  READ-ONLY; writes only scratch files.
"""
import os, numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData
from prepare_training_data import thin_by_min_distance
from analyze_grouse import (ENVELOPE_SCHEME, build_envelope_id,
                            fit_scheme_binners, load_evt_crosswalk,
                            sample_raster, NON_VEG_SCLASS_CODES,
                            is_evt_phys_nonveg, RASTER_DIR)
import generate_negatives as GN

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
os.makedirs(SCR, exist_ok=True)
R = ["ME", "NH", "VT"]
T = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
data = GrouseData()

# ---------------- positives: CR-0007 recipe (I6) ----------------
ev_all = []
pos = []
for r in R:
    e = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv", low_memory=False)
    ev_all.append(e)
    h = e[~e['nonveg_landcover'].astype(bool)]
    pos.append(h[h['state'] == r])
EV = pd.concat(ev_all, ignore_index=True)
P = pd.concat(pos, ignore_index=True)
print("habitat rows own-state (pre-dedup):", len(P))
P = P.drop_duplicates(subset=['longitude', 'latitude', 'year']).copy()
print("after (lon,lat,year) dedup:", len(P))
P['x_5070'], P['y_5070'] = T.transform(P.longitude.values, P.latitude.values)
P = thin_by_min_distance(P, 30, 42).reset_index(drop=True)
print("I6 pooled positives after 30m thin:", len(P), " (CR target 6230 +/-10)")
print("  per region:", P.state.value_counts().to_dict())
P[['longitude','latitude','state','year','x_5070','y_5070']].to_csv(f"{SCR}/fc_pos.csv", index=False)

# ---------------- negative candidates: pooled, faithful ----------------
cands = []
for r in R:
    d = pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv", low_memory=False)
    cands.append(d)
C = pd.concat(cands, ignore_index=True)
n0 = len(C)
C = C[~(C['coord_uncertainty_m'] > GN.MAX_COORD_UNCERTAINTY_M).fillna(False)].copy()
print(f"uncertainty drop {n0-len(C)}")
n1 = len(C)
C = C.loc[~C[['longitude','latitude']].round(5).duplicated()].copy()
print(f"dup-coord collapse {n1-len(C)} -> {len(C)}")
C['x_5070'], C['y_5070'] = T.transform(C.longitude.values, C.latitude.values)
n2 = len(C)
C = thin_by_min_distance(C, GN.MIN_SPACING_M, 42)
print(f"pooled 30m thin {n2} -> {len(C)}")
# 300 m buffer against EVERY evaluated_sightings row (as the real code does)
ex, ey = T.transform(EV.longitude.values, EV.latitude.values)
dist, _ = cKDTree(np.c_[ex, ey]).query(C[['x_5070','y_5070']].values, k=1)
n3 = len(C)
C = C[dist > GN.BUFFER_M].copy()
print(f"300m buffer (vs ALL {len(EV)} evaluated rows) {n3} -> {len(C)}")

# ---------------- envelope extraction, per region (CR keeps this per-region)
feats = sorted({c for c, _ in ENVELOPE_SCHEME if c not in ("evt_phys","evt_group")} | {"sclass","evt"})
print("feats_needed:", feats)
xw = load_evt_crosswalk(RASTER_DIR)
out = []
for r in R:
    sub = C[C['state'] == r].copy()
    rd = data[r]
    for f in feats:
        vals = np.full(len(sub), np.nan)
        for yr in sorted(sub['year'].dropna().unique()):
            m = (sub['year'] == yr).values
            tif = rd.raster_path(f, int(yr))
            vals[m] = sample_raster(tif, sub.loc[m,'longitude'].values, sub.loc[m,'latitude'].values)
        sub[f] = vals
    n4 = len(sub)
    sub = sub.dropna(subset=feats).copy()
    print(f"  {r}: extraction dropped {n4-len(sub)} -> {len(sub)}")
    sub['evt_phys'] = sub['evt'].astype(int).map(xw['phys']).fillna("Unmapped")
    ev = rd.evaluated
    hab = ev[~ev['nonveg_landcover'].astype(bool)]
    binners = fit_scheme_binners(hab, ENVELOPE_SCHEME)
    sub['envelope_id'] = build_envelope_id(sub, ENVELOPE_SCHEME, binners=binners)
    sub['is_nonveg'] = (sub['sclass'].isin(NON_VEG_SCLASS_CODES)
                        | is_evt_phys_nonveg(sub['evt_phys']))
    mm = {row['Envelope']: row for _, row in rd.envelope_metrics.iterrows()}
    w, wc = [], []
    for eid, nv in zip(sub['envelope_id'], sub['is_nonveg']):
        a, b = GN.build_weight(eid, mm, nv)
        w.append(a); wc.append(b)
    sub['weight'] = w; sub['weight_basis'] = wc
    out.append(sub)
C = pd.concat(out, ignore_index=True)
print("FINAL faithful pooled candidate pool:", len(C))
print(C.groupby('state').size().to_dict())
print("nonveg share:", C.is_nonveg.mean().round(4))
C[['longitude','latitude','state','year','x_5070','y_5070','envelope_id',
   'is_nonveg','weight','weight_basis']].to_csv(f"{SCR}/fc_pool.csv", index=False)
print("saved", f"{SCR}/fc_pool.csv")
