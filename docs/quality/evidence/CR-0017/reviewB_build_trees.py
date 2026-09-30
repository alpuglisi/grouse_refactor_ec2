"""Reviewer B (CR-0017): build wrong/right post-CR trees in scratch, from the
live artifacts (read-only), for check_must_change.py. Draw re-done with the
pipeline's own ES selection on the modified pool (a simulated regeneration)."""
import os, shutil, sys
import numpy as np, pandas as pd, shapely, geopandas as gpd
from pyproj import Transformer
sys.path.insert(0, "/home/ec2-user/grouse2")
from generate_negatives import draw_region_split, NEGATIVE_COLUMNS, NEGATIVE_ORDER, SPLITS
from prepare_training_data import canonical, csv_bytes
import regions as R

LIVE = "/home/ec2-user/grouse2"
OUT = "/tmp/claude-1000/-home-ec2-user-grouse2/491a150a-d26d-456d-b9b4-036cd4a6478b/scratchpad/reviewB/trees"
POOL = "data/negatives/candidate_pool.csv"
KEYS = pd.read_csv(f"{LIVE}/docs/quality/evidence/CR-0017/preregister_keys.csv")
kc = KEYS[KEYS.set == "C"]
old_c = pd.read_csv(f"{LIVE}/{POOL}", float_precision="round_trip")
old_lines = open(f"{LIVE}/{POOL}").read().splitlines()
old_n = {r: pd.read_csv(f"{LIVE}/data/negatives/negatives_{r}.csv", float_precision="round_trip") for r in R.REGIONS}
npos = {(r, s): len(pd.read_csv(f"{LIVE}/data/pipeline/{s}_positives_{r}.csv")) for r in R.REGIONS for s in SPLITS}
key = lambda df: list(zip(df.longitude.astype(float), df.latitude.astype(float)))

def draw(pool, mode="es"):
    out = {}
    for r in R.REGIONS:
        parts = []
        for s in SPLITS:
            sub = pool[(pool.region == r) & (pool.split == s)]
            got, _ = draw_region_split(sub, npos[(r, s)])
            parts.append(got)
        out[r] = pd.concat(parts, ignore_index=True)
    return out

# sanity: redraw on the old pool == old N keys
d0 = draw(old_c)
for r in R.REGIONS:
    assert set(key(d0[r])) == set(key(old_n[r])), r
print("sanity: ES redraw on old C reproduces old N keys in all regions")

def build(name, drop_keys, mutate=None, repl=None):
    root = os.path.join(OUT, name)
    if os.path.exists(root):
        shutil.rmtree(root)
    for sub in ("data/pipeline", "data/negatives"):
        os.makedirs(os.path.join(root, sub))
    for k in ("thinned", "train", "val"):
        for r in R.REGIONS:
            shutil.copyfile(f"{LIVE}/data/pipeline/{k}_positives_{r}.csv", f"{root}/data/pipeline/{k}_positives_{r}.csv")
    shutil.copyfile(f"{LIVE}/data/pipeline/block_assignments.csv", f"{root}/data/pipeline/block_assignments.csv")
    ks = key(old_c)
    keep = np.array([k not in drop_keys for k in ks])
    with open(f"{root}/{POOL}", "w") as f:
        f.write("\n".join([old_lines[0]] + [l for l, kp in zip(old_lines[1:], keep) if kp]) + "\n")
    new_c = old_c[keep].reset_index(drop=True)
    dn = draw(new_c) if repl is None else repl(new_c)
    for r in R.REGIONS:
        on = old_n[r].set_index(["longitude", "latitude"], drop=False)
        rows = []
        for _, row in dn[r].iterrows():
            k = (float(row.longitude), float(row.latitude))
            if k in on.index:
                rows.append(on.loc[[k]].iloc[0])
            else:
                rr = {c: row[c] if c in row.index else np.nan for c in NEGATIVE_COLUMNS}
                rr["label"] = 0
                rows.append(pd.Series(rr))
        sel = pd.DataFrame(rows)[NEGATIVE_COLUMNS]
        if mutate:
            sel = mutate(sel)
        sel = canonical(sel, NEGATIVE_ORDER)
        open(f"{root}/data/negatives/negatives_{r}.csv", "wb").write(csv_bytes(sel))
        for s in SPLITS:
            open(f"{root}/data/negatives/{s}_negatives_{r}.csv", "wb").write(csv_bytes(sel[sel.split == s]))
    print(f"built {name}: C {len(old_c)} -> {len(new_c)}")
    return root

k88 = set(zip(kc.longitude.astype(float), kc.latitude.astype(float)))
kca = set(zip(kc[kc.nearest_outside == "CA/sea"].longitude.astype(float), kc[kc.nearest_outside == "CA/sea"].latitude.astype(float)))

# W3: undissolved domain (per-state polygons; internal state lines are edges)
T = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
st = R._state_polygons().to_crs(5070)
x, y = T.transform(old_c.longitude.to_numpy(float), old_c.latitude.to_numpy(float))
p = shapely.points(x, y)
dmin = np.full(len(p), np.inf)
for g in st.geometry:
    inside = shapely.contains(g, p)
    dmin = np.where(inside, np.minimum(dmin, shapely.distance(p, g.boundary)), dmin)
dmin[np.isinf(dmin)] = 0.0
kund = set(k for k, d in zip(key(old_c), dmin) if d <= R.BUFFER_M)
print("undissolved drop set", len(kund), "superset of 88:", k88 <= kund)

build("W1_every_us_county", kca)
build("W2_correct", k88)
build("W3_undissolved", kund)

# W4: right C, wrong replacements: lowest-ES-ranked unselected rows of the same cell
def worst_repl(new_c):
    good = draw(new_c)
    out = {}
    for r in R.REGIONS:
        ok = set(key(old_n[r]))
        g = good[r]
        added = [k not in ok for k in key(g)]
        base = g[[not a for a in added]]
        extra = []
        for (s, nv), cell in g[added].groupby(["split", "is_nonveg"]):
            cand = new_c[(new_c.region == r) & (new_c.split == s) & (new_c.is_nonveg == nv)]
            cand = cand[[k not in ok and k not in set(key(g)) for k in key(cand)]]
            extra.append(cand.sort_values("weight").head(len(cell)))   # deliberately not the ES draw
        out[r] = pd.concat([base] + extra, ignore_index=True)
    return out
build("W4_wrong_replacements", k88, repl=worst_repl)

# W5: right keys, every retained negative's weight doubled
def dbl(sel):
    sel = sel.copy(); sel["weight"] = sel["weight"] * 2; return sel
build("W5_weights_corrupted", k88, mutate=dbl)
