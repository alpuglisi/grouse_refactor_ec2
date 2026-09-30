"""res_determ_final.py -- (1) which canonical forms survive a library-version
change, (2) how each behaves when one record is added/removed, (3) the real
float margin in the thinner.  Read-only.
"""
import hashlib, numpy as np, pandas as pd
from scipy.spatial import cKDTree
from prepare_training_data import thin_by_min_distance

REGIONS = ("ME", "NH", "VT"); BLOCK = 3000.0; ORIGIN = (0.0, 0.0)
VF = 0.20; SEED = 42; SPACING = 30.0

fr = []
for r in REGIONS:
    d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    fr.append(d[d["state"] == r])
pool = pd.concat(fr, ignore_index=True)
pool = pool[~pool["nonveg_landcover"].astype(bool)]
pool = pool.drop_duplicates(subset=["longitude", "latitude", "year"])
CANON = ["longitude", "latitude", "year"]
pool = pool.sort_values(CANON, kind="mergesort").reset_index(drop=True)
print(f"canonical pooled frame: {len(pool):,} rows")


def blocks_of(df):
    bx = np.floor((df["x_5070"].values - ORIGIN[0]) / BLOCK).astype(int)
    by = np.floor((df["y_5070"].values - ORIGIN[1]) / BLOCK).astype(int)
    return pd.Series([f"{a}_{b}" for a, b in zip(bx, by)], index=df.index)


def thin_hash(df, spacing, seed):
    keys = np.array([hashlib.blake2b(f"{seed}:{lo:.6f},{la:.6f}".encode(),
                                     digest_size=16).hexdigest()
                     for lo, la in zip(df["longitude"], df["latitude"])])
    order = np.argsort(keys, kind="stable")
    coords = df[["x_5070", "y_5070"]].values[order]
    kept_mask = np.zeros(len(df), dtype=bool); kept, tree = [], None
    for i, pt in enumerate(coords):
        if tree is None or tree.query(pt, k=1)[0] >= spacing:
            kept.append(pt); kept_mask[order[i]] = True
            tree = cKDTree(np.array(kept))
    return df[kept_mask].copy()


def fill(order, counts, target):
    v, run = set(), 0
    for b in order:
        if run >= target: break
        v.add(b); run += counts[b]
    return v


def draw_vc(bid, n, seed=SEED, vc_kind="stable"):
    c = bid.value_counts()
    if vc_kind != "stable":
        enc = bid.drop_duplicates().tolist()
        c = c.reindex(enc).sort_values(ascending=False, kind=vc_kind)
    return fill(c.sample(frac=1, random_state=seed).index.tolist(), c,
                int(round(VF * n)))


def draw_lexi(bid, n, seed=SEED, vc_kind="stable"):
    c = bid.value_counts().reindex(sorted(set(bid)))
    return fill(c.sample(frac=1, random_state=seed).index.tolist(), c,
                int(round(VF * n)))


def draw_hash(bid, n, seed=SEED, vc_kind="stable"):
    c = bid.value_counts()
    order = sorted(c.index, key=lambda b: hashlib.blake2b(
        f"{seed}:{b}".encode(), digest_size=16).hexdigest())
    return fill(order, c, int(round(VF * n)))


VARIANTS = {
    "canonical sort + value_counts order (reviewer's proposal)":
        (thin_by_min_distance, draw_vc),
    "canonical sort + lexicographic block list + RandomState shuffle":
        (thin_by_min_distance, draw_lexi),
    "hash-ordered thinner + hash-ordered block draw":
        (thin_hash, draw_hash),
}

print("\n" + "=" * 78)
print("F1  library-version proxy: same canonical frame, value_counts tie order")
print("    changed (pandas <3.0 sorted ties with quicksort, 3.0 with 'stable')")
print("=" * 78)
for name, (thin, draw) in VARIANTS.items():
    t = thin(pool, SPACING, SEED).reset_index(drop=True)
    b = blocks_of(t)
    v1 = draw(b, len(t), SEED, "stable")
    v2 = draw(b, len(t), SEED, "quicksort")
    iv1, iv2 = b.isin(v1).values, b.isin(v2).values
    print(f"  {name}\n     thinned {len(t):,}; val-block symmetric diff "
          f"{len(v1 ^ v2)}, records changing split {int((iv1 != iv2).sum()):,} "
          f"({100*(iv1 != iv2).mean():.2f}%)  -> "
          f"{'VERSION-FRAGILE' if v1 != v2 else 'version-proof'}")

print("\n" + "=" * 78)
print("F2  stability when the record set changes by one row (a new sighting")
print("    arrives, or one record is dropped upstream)")
print("=" * 78)
drop_i = len(pool) // 2
pool2 = pool.drop(index=pool.index[drop_i]).reset_index(drop=True)
for name, (thin, draw) in VARIANTS.items():
    ta = thin(pool, SPACING, SEED).reset_index(drop=True)
    tb = thin(pool2, SPACING, SEED).reset_index(drop=True)
    ba, bb = blocks_of(ta), blocks_of(tb)
    va, vb = draw(ba, len(ta)), draw(bb, len(tb))
    ka = dict(zip(zip(ta.longitude, ta.latitude), ba.isin(va)))
    kb = dict(zip(zip(tb.longitude, tb.latitude), bb.isin(vb)))
    common = set(ka) & set(kb)
    moved = sum(1 for c in common if ka[c] != kb[c])
    keptdiff = len(set(ka) ^ set(kb))
    print(f"  {name}\n     one record removed -> kept-set symmetric diff "
          f"{keptdiff}, val-block Jaccard {len(va & vb)/len(va | vb):.4f}, "
          f"{moved:,} of {len(common):,} surviving records change split "
          f"({100*moved/len(common):.1f}%)")

print("\n" + "=" * 78)
print("F3  float margin actually available in the thinner and the grid")
print("=" * 78)
t = thin_by_min_distance(pool, SPACING, SEED).reset_index(drop=True)
xy = t[["x_5070", "y_5070"]].values
tree = cKDTree(xy)
d, _ = tree.query(xy, k=2)
nn = d[:, 1]
print(f"  closest surviving pair: {nn.min():.6f} m (threshold {SPACING} m) -> "
      f"margin {nn.min()-SPACING:.6f} m")
print(f"  surviving pairs within 30.001 m: {int((nn < 30.001).sum())}; "
      f"within 30.1 m: {int((nn < 30.1).sum())}; within 31 m: "
      f"{int((nn < 31).sum())}")
# dropped-record margin: for records dropped, how far were they from their
# nearest kept neighbour?  (the other side of the knife edge)
kept = set(map(tuple, t[["longitude", "latitude"]].values.tolist()))
dropped = pool[[tuple(v) not in kept for v in
                pool[["longitude", "latitude"]].values.tolist()]]
if len(dropped):
    dd, _ = tree.query(dropped[["x_5070", "y_5070"]].values, k=1)
    print(f"  {len(dropped):,} dropped records; their distance to the nearest "
          f"KEPT record: max {dd.max():.4f} m, "
          f"{int((dd > 29.99).sum())} above 29.99 m")
