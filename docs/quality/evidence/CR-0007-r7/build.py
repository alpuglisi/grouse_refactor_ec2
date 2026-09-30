"""Independent rebuild of CR-0007's post-partition positives + negative pool.
Reads repo data read-only; writes only to this scratch dir."""
import os, sys, hashlib, numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData
from analyze_grouse import (ENVELOPE_SCHEME, build_envelope_id, fit_scheme_binners,
                            load_evt_crosswalk, sample_raster, NON_VEG_SCLASS_CODES,
                            is_evt_phys_nonveg, RASTER_DIR)
import generate_negatives as GN
OUT = "/tmp/claude-1000/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/scratchpad/cr0007_A"
R = ["ME", "NH", "VT"]
T = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)

def grid_thin(x, y, spacing, seed):
    """exact greedy equivalent of thin_by_min_distance (same permutation,
    keep iff nearest kept >= spacing) using a hash grid."""
    n = len(x); order = np.random.default_rng(seed).permutation(n)
    keep = np.zeros(n, bool); cells = {}
    for i in order:
        cx, cy = int(np.floor(x[i] / spacing)), int(np.floor(y[i] / spacing))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cells.get((cx + dx, cy + dy), ()):
                    if (x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2 < spacing ** 2:
                        ok = False; break
                if not ok: break
            if not ok: break
        if ok:
            keep[i] = True; cells.setdefault((cx, cy), []).append(i)
    return keep

# ---------- positives
ev_all = []
for r in R:
    e = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv", low_memory=False)
    e['file'] = r
    ev_all.append(e)
EVA = pd.concat(ev_all, ignore_index=True)
own = EVA[EVA.state == EVA.file]
print("evaluated rows all/own-state:", len(EVA), len(own))
hab = own[~own.nonveg_landcover.astype(bool)].copy()
print("own-state habitat rows:", len(hab))
hab = hab.drop_duplicates(['longitude', 'latitude', 'year']).reset_index(drop=True)
print("dedup lon/lat/year:", len(hab))
hab['x_5070'], hab['y_5070'] = T.transform(hab.longitude.values, hab.latitude.values)
k = grid_thin(hab.x_5070.values, hab.y_5070.values, 30, 42)
pos = hab[k].reset_index(drop=True)
print("pooled thin positives:", len(pos), pos.state.value_counts().to_dict())
pos.to_csv(f"{OUT}/pos_thinned.csv", index=False)

# ---------- negative pool
EVown = own  # veg + nonveg, own state: buffer set
C = pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv", low_memory=False)
               for r in R], ignore_index=True)
print("raw cands", len(C), C.state.value_counts().to_dict())
C = C[~(C.coord_uncertainty_m > GN.MAX_COORD_UNCERTAINTY_M).fillna(False)]
C = C.loc[~C[['longitude', 'latitude']].round(5).duplicated()].reset_index(drop=True)
print("dedup", len(C))
C['x_5070'], C['y_5070'] = T.transform(C.longitude.values, C.latitude.values)
C['pre_thin'] = True
Cfull = C.copy()
k = grid_thin(C.x_5070.values, C.y_5070.values, 30, 42)
C = C[k].reset_index(drop=True)
print("thin", len(C))
ex, ey = T.transform(EVown.longitude.values, EVown.latitude.values)
tree = cKDTree(np.c_[ex, ey])
d, _ = tree.query(C[['x_5070', 'y_5070']].values, k=1)
C['d_grouse'] = d
# per-state-only buffer distance (buffer computed on own-state sightings only)
C['d_grouse_ownstate'] = np.nan
for r in R:
    m = (C.state == r).values
    sub = EVown[EVown.state == r]
    sx, sy = T.transform(sub.longitude.values, sub.latitude.values)
    C.loc[m, 'd_grouse_ownstate'] = cKDTree(np.c_[sx, sy]).query(C.loc[m, ['x_5070', 'y_5070']].values)[0]
print("within 300m of any grouse:", int((C.d_grouse <= 300).sum()),
      " within 300 of foreign-state grouse only:",
      int(((C.d_grouse <= 300) & (C.d_grouse_ownstate > 300)).sum()))

data = GrouseData(); xw = load_evt_crosswalk(RASTER_DIR)
feats = sorted({c for c, _ in ENVELOPE_SCHEME if c not in ("evt_phys", "evt_group")} | {"sclass", "evt"})
out = []
for r in R:
    sub = C[C.state == r].copy(); rd = data[r]
    for f in feats:
        vals = np.full(len(sub), np.nan)
        for yr in sorted(sub.year.dropna().unique()):
            m = (sub.year == yr).values
            vals[m] = sample_raster(rd.raster_path(f, int(yr)), sub.loc[m, 'longitude'].values,
                                    sub.loc[m, 'latitude'].values)
        sub[f] = vals
    n4 = len(sub); sub = sub.dropna(subset=feats).copy()
    print(r, "extraction dropna", n4, "->", len(sub))
    sub['evt_phys'] = sub.evt.astype(int).map(xw['phys']).fillna("Unmapped")
    e = rd.evaluated; h = e[~e.nonveg_landcover.astype(bool)]
    sub['envelope_id'] = build_envelope_id(sub, ENVELOPE_SCHEME, binners=fit_scheme_binners(h, ENVELOPE_SCHEME))
    sub['is_nonveg'] = sub.sclass.isin(NON_VEG_SCLASS_CODES) | is_evt_phys_nonveg(sub.evt_phys)
    mm = {row['Envelope']: row for _, row in rd.envelope_metrics.iterrows()}
    ww = [GN.build_weight(a, mm, b) for a, b in zip(sub.envelope_id, sub.is_nonveg)]
    sub['weight'] = [a for a, _ in ww]; sub['weight_basis'] = [b for _, b in ww]
    out.append(sub)
P = pd.concat(out, ignore_index=True)
P.to_csv(f"{OUT}/pool_prebuffer.csv", index=False)
print("pool pre-buffer (extracted):", len(P), " post-buffer:", int((P.d_grouse > 300).sum()),
      P[P.d_grouse > 300].state.value_counts().to_dict())
