"""Formal-review harness: build the CR-0007 intended pipeline end-to-end from
the raw CSVs (no writes anywhere), then score the § Acceptance GATE rows on it
and on constructed attacks.

READ-ONLY. Writes nothing outside stdout.
"""
import hashlib
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

from inv_formalA_thin import fast_thin, fast_thin_mask

R = ["ME", "NH", "VT"]
BS = 3000.0                 # regions.BLOCK_SIZE_M
ORIGIN = (0.0, 0.0)         # regions.BLOCK_ORIGIN_5070
MIN_SPACING_M = 30
BUFFER_M = 300
VF = 0.20
SEED = 42
NEG_RATIO = 1.0
MAX_COORD_UNC = 1000        # generate_negatives.MAX_COORD_UNCERTAINTY_M

T = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)


def blk(x, y, size=BS):
    bx = np.floor((x - ORIGIN[0]) / size).astype(np.int64)
    by = np.floor((y - ORIGIN[1]) / size).astype(np.int64)
    return bx * 100000 + by          # single int key, order-free


def load_positives():
    a = pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
                   .assign(_reg=r) for r in R], ignore_index=True)
    own_all = a[a.state == a._reg].copy()           # veg + nonveg, for the buffer
    hab = own_all[~own_all['nonveg_landcover'].astype(bool)]
    hab = hab.drop_duplicates(subset=['longitude', 'latitude', 'year'])
    return own_all.reset_index(drop=True), hab.reset_index(drop=True)


def val_blocks_fair(pos, seed, vf=VF):
    bc = pos['blk'].value_counts()
    order = bc.sample(frac=1, random_state=seed).index.tolist()
    target = int(round(vf * len(pos)))
    vb, run = set(), 0
    for b in order:
        if run >= target:
            break
        vb.add(b)
        run += bc[b]
    return vb


def hash_split(b, vf, seed):
    h = int(hashlib.md5(f"{seed}:{b}".encode()).hexdigest(), 16)
    return 'val' if (h % 10000) < vf * 10000 else 'train'


def build_candidates(buffer_pos_xy, unc_filter=True):
    c = pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
                   for r in R], ignore_index=True)
    if unc_filter:
        c = c[~(c['coord_uncertainty_m'] > MAX_COORD_UNC).fillna(False)].copy()
    key = c[['longitude', 'latitude']].round(5)
    c = c.loc[~key.duplicated()].copy()
    c['x_5070'], c['y_5070'] = T.transform(c.longitude.values, c.latitude.values)
    c = fast_thin(c.reset_index(drop=True), MIN_SPACING_M, SEED)
    d, _ = cKDTree(buffer_pos_xy).query(c[['x_5070', 'y_5070']].values, k=1)
    c = c[d > BUFFER_M].copy().reset_index(drop=True)
    c['blk'] = blk(c.x_5070.values, c.y_5070.values)
    return c
