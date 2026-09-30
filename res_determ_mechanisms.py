"""res_determ_mechanisms.py -- isolate each order/environment dependence in the
evaluated_sightings -> split path, and test candidate canonical forms.

Read-only.  Writes nothing but stdout.
"""
import hashlib, itertools, json
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from prepare_training_data import thin_by_min_distance

REGIONS = ("ME", "NH", "VT")
BLOCK = 3000.0; ORIGIN = (0.0, 0.0); VF = 0.20; SEED = 42; SPACING = 30.0

raw = {}
for r in REGIONS:
    d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    raw[r] = d[d["state"] == r].copy()


def concat(order, sort_key=None, sort_before=True):
    p = pd.concat([raw[r] for r in order], ignore_index=True)
    if sort_key and sort_before:
        p = p.sort_values(sort_key, kind="mergesort").reset_index(drop=True)
    p = p[~p["nonveg_landcover"].astype(bool)]
    p = p.drop_duplicates(subset=["longitude", "latitude", "year"])
    p = p.reset_index(drop=True)
    if sort_key and not sort_before:
        p = p.sort_values(sort_key, kind="mergesort").reset_index(drop=True)
    return p


def blocks_of(df):
    bx = np.floor((df["x_5070"].values - ORIGIN[0]) / BLOCK).astype(int)
    by = np.floor((df["y_5070"].values - ORIGIN[1]) / BLOCK).astype(int)
    return pd.Series([f"{a}_{b}" for a, b in zip(bx, by)], index=df.index)


def fill(order_list, counts, target):
    v, run = set(), 0
    for b in order_list:
        if run >= target:
            break
        v.add(b); run += counts[b]
    return v


def draw_asis(block_id, n, seed=SEED, vc_kind="stable"):
    """the real prepare_training_data:101-113"""
    counts = block_id.value_counts()
    if vc_kind != "stable":
        enc = block_id.drop_duplicates().tolist()
        counts = counts.reindex(enc).sort_values(ascending=False, kind=vc_kind)
    order = counts.sample(frac=1, random_state=seed).index.tolist()
    return fill(order, counts, int(round(VF * n))), counts


def draw_sorted_blocks(block_id, n, seed=SEED):
    """value_counts tie-break removed: shuffle a lexicographically sorted
    block list instead of value_counts' order"""
    counts = block_id.value_counts()
    counts = counts.reindex(sorted(counts.index))
    order = counts.sample(frac=1, random_state=seed).index.tolist()
    return fill(order, counts, int(round(VF * n))), counts


def draw_hash(block_id, n, seed=SEED):
    """order derived from a hash of the block id, not from row position or
    any RNG stream"""
    counts = block_id.value_counts()
    def h(b):
        return hashlib.blake2b(f"{seed}:{b}".encode(), digest_size=16).hexdigest()
    order = sorted(counts.index, key=h)
    return fill(order, counts, int(round(VF * n))), counts


def thin_hash(df, spacing, seed):
    """greedy thinner whose visit order is a hash of each record's rounded
    coordinates (+ seed), instead of rng.permutation(len(df))"""
    if len(df) == 0:
        return df
    keys = [hashlib.blake2b(
        f"{seed}:{lo:.6f},{la:.6f}".encode(), digest_size=16).hexdigest()
        for lo, la in zip(df["longitude"].values, df["latitude"].values)]
    order = np.argsort(np.array(keys))          # total order, no position input
    coords = df[["x_5070", "y_5070"]].values[order]
    kept_mask = np.zeros(len(df), dtype=bool)
    kept, tree = [], None
    for i, pt in enumerate(coords):
        keep = True if tree is None else tree.query(pt, k=1)[0] >= spacing
        if keep:
            kept.append(pt); kept_mask[order[i]] = True
            tree = cKDTree(np.array(kept))
    return df[kept_mask].copy()


def summary(t, vb, bid):
    iv = bid.isin(vb).values
    xy = t[["x_5070", "y_5070"]].values
    d, _ = cKDTree(xy[~iv]).query(xy[iv], k=1)
    per = t.assign(v=iv).groupby("state").v.mean() * 100
    return (len(t), len(vb), int(iv.sum()),
            tuple(round(x, 2) for x in per.values),
            round(float(np.median(d))), round(float((d < 1920).mean()*100), 2))


kc = lambda df: frozenset(map(tuple, df[["longitude", "latitude", "year"]]
                              .round(6).values.tolist()))

print("=" * 78)
print("M1  thinner visit order: pooled row order feeds rng.permutation(len(df))")
print("=" * 78)
base = concat(REGIONS)
print(f"pooled frame (fixed content, {len(base):,} rows) permuted by hand, "
      "spacing 30 m, seed 42:")
outs = {}
for label, frame in [("as concatenated ME,NH,VT", base),
                     ("rows reversed", base.iloc[::-1].reset_index(drop=True)),
                     ("rows shuffled (numpy seed 0)",
                      base.sample(frac=1, random_state=0).reset_index(drop=True)),
                     ("sorted by (state,lon,lat)",
                      base.sort_values(["state", "longitude", "latitude"],
                                       kind="mergesort").reset_index(drop=True))]:
    t = thin_by_min_distance(frame, SPACING, SEED)
    outs[label] = kc(t)
    print(f"  {label:30s} kept {len(t):,}")
ks = list(outs)
for a, b in itertools.combinations(ks, 2):
    print(f"  kept-set symmetric difference {a!r} vs {b!r}: "
          f"{len(outs[a] ^ outs[b])}")

print("\n" + "=" * 78)
print("M2  value_counts() tie order, with the thinned set held FIXED")
print("=" * 78)
t0 = thin_by_min_distance(base, SPACING, SEED).reset_index(drop=True)
bid0 = blocks_of(t0)
cnt = bid0.value_counts()
print(f"{len(t0):,} records, {len(cnt):,} occupied blocks; count histogram: "
      f"{dict(sorted(cnt.value_counts().items())[:8])} ...")
print(f"  blocks with count==1: {(cnt == 1).sum():,} "
      f"({100*(cnt == 1).mean():.1f}% of blocks) -> that many tied keys")
enc = bid0.drop_duplicates().tolist()
print("  value_counts index == first-encounter order within ties (pandas "
      f"{pd.__version__}, kind='stable'): "
      f"{cnt.index.tolist() == pd.Series(enc).reindex(range(len(enc))).tolist() or 'see below'}")
# does the encounter order of tied blocks equal value_counts order?
enc_rank = {b: i for i, b in enumerate(enc)}
vc_ties = [b for b in cnt.index if cnt[b] == 1]
print("  tied-block order equals encounter order:",
      vc_ties == [b for b in enc if cnt[b] == 1])
for vk in ("stable", "quicksort", "heapsort"):
    vb, c = draw_asis(bid0, len(t0), vc_kind=vk)
    print(f"  value_counts sort kind={vk:10s} -> {summary(t0, vb, bid0)}")
vb_st, _ = draw_asis(bid0, len(t0), vc_kind="stable")
vb_qs, _ = draw_asis(bid0, len(t0), vc_kind="quicksort")
iv1 = bid0.isin(vb_st).values; iv2 = bid0.isin(vb_qs).values
print(f"  stable vs quicksort: val-block symmetric diff {len(vb_st ^ vb_qs)}, "
      f"records changing split {int((iv1 != iv2).sum()):,} "
      f"({100*(iv1 != iv2).mean():.1f}%)")

print("\n  same thinned records, rows re-ordered before value_counts:")
for label, frame in [("as thinned", t0),
                     ("reversed", t0.iloc[::-1].reset_index(drop=True)),
                     ("sorted by (state,lon,lat)",
                      t0.sort_values(["state", "longitude", "latitude"],
                                     kind="mergesort").reset_index(drop=True))]:
    b = blocks_of(frame)
    vb, _ = draw_asis(b, len(frame))
    print(f"    {label:26s} -> {summary(frame, vb, b)}")

print("\n" + "=" * 78)
print("M3  CANDIDATE CANONICAL FORMS across all six region orders")
print("=" * 78)
variants = {
  "A  as-is (no canonicalisation)":
      dict(sort=None, thin=thin_by_min_distance, draw=draw_asis),
  "B  sort (state,lon,lat) after dedup":
      dict(sort=["state", "longitude", "latitude"], sort_before=False,
           thin=thin_by_min_distance, draw=draw_asis),
  "C  sort (state,lon,lat) before dedup":
      dict(sort=["state", "longitude", "latitude"], sort_before=True,
           thin=thin_by_min_distance, draw=draw_asis),
  "D  sort (lon,lat,year) before dedup":
      dict(sort=["longitude", "latitude", "year"], sort_before=True,
           thin=thin_by_min_distance, draw=draw_asis),
  "E  hash-ordered thinner + hash-ordered block draw (no sort at all)":
      dict(sort=None, thin=thin_hash, draw=draw_hash),
  "F  sort (lon,lat,year) + lexicographic block list + RNG shuffle":
      dict(sort=["longitude", "latitude", "year"], sort_before=True,
           thin=thin_by_min_distance, draw=draw_sorted_blocks),
}
for name, v in variants.items():
    sigs = {}
    for order in itertools.permutations(REGIONS):
        p = concat(order, v["sort"], v.get("sort_before", True))
        t = v["thin"](p, SPACING, SEED).reset_index(drop=True)
        b = blocks_of(t)
        vb, _ = v["draw"](b, len(t))
        sig = (frozenset(vb), kc(t),
               frozenset(map(tuple, t.loc[b.isin(vb),
                                          ["longitude", "latitude"]]
                             .round(6).values.tolist())))
        sigs.setdefault(sig, []).append("".join(order))
    st = summary(t, vb, b)
    print(f"  {name}\n     distinct outcomes over 6 orders: {len(sigs)}"
          f"   groups: {[g for g in sigs.values()]}\n     last summary "
          f"(n, val_blocks, val_recs, per-region val%, med nn m, %<1920m): {st}")

print("\n" + "=" * 78)
print("M4  residual ties under the canonical sort keys")
print("=" * 78)
p = concat(REGIONS)
for key in (["state", "longitude", "latitude"],
            ["longitude", "latitude"],
            ["longitude", "latitude", "year"],
            ["longitude", "latitude", "year", "n_visits"]):
    dup = p.duplicated(subset=key, keep=False)
    ng = p[dup].groupby(key, dropna=False).ngroups if dup.any() else 0
    print(f"  key {key}: {int(dup.sum()):,} rows in {ng:,} tied groups")
d2 = p[p.duplicated(subset=["longitude", "latitude"], keep=False)]
if len(d2):
    g = d2.groupby(["longitude", "latitude"])
    diff_cols = []
    for c in p.columns:
        if g[c].nunique(dropna=False).max() > 1:
            diff_cols.append(c)
    print(f"  columns that DIFFER inside a same-coordinate group: {diff_cols}")

print("\n" + "=" * 78)
print("M5  dedup keep-first: do dropped duplicate rows differ from kept ones?")
print("=" * 78)
p_all = pd.concat([raw[r] for r in REGIONS], ignore_index=True)
p_all = p_all[~p_all["nonveg_landcover"].astype(bool)]
dupmask = p_all.duplicated(subset=["longitude", "latitude", "year"], keep=False)
print(f"  {int(dupmask.sum()):,} rows in duplicate (lon,lat,year) groups")
if dupmask.any():
    g = p_all[dupmask].groupby(["longitude", "latitude", "year"])
    cols = [c for c in p_all.columns if g[c].nunique(dropna=False).max() > 1]
    print(f"  columns differing inside a duplicate group: {cols}")

print("\n" + "=" * 78)
print("M6  float knife-edges in the thinner: kept pairs near exactly 30 m")
print("=" * 78)
xy = t0[["x_5070", "y_5070"]].values
tr = cKDTree(xy)
pairs = tr.query_pairs(SPACING * 1.001, output_type="ndarray")
if len(pairs):
    dd = np.linalg.norm(xy[pairs[:, 0]] - xy[pairs[:, 1]], axis=1)
    for tol in (1e-9, 1e-6, 1e-3, 1e-2, 1.0):
        print(f"  kept pairs with |d - 30 m| < {tol:g}: "
              f"{int((np.abs(dd - SPACING) < tol).sum())}")
    print(f"  closest kept pair: {dd.min():.9f} m")
else:
    print("  no kept pair within 30.03 m at all")

print("\n" + "=" * 78)
print("M7  RNG stream identity: default_rng vs RandomState at the same seed")
print("=" * 78)
n = len(base)
a = np.random.default_rng(SEED).permutation(n)
b = np.random.RandomState(SEED).permutation(n)
print(f"  default_rng(42).permutation({n})[:8] = {a[:8]}")
print(f"  RandomState(42).permutation({n})[:8] = {b[:8]}")
print(f"  identical: {np.array_equal(a, b)}  (the thinner uses the first, "
      "pandas .sample(random_state=42) the second)")
ch = np.random.RandomState(SEED).choice(n, size=n, replace=False)
print(f"  RandomState.choice(n,n,replace=False) == RandomState.permutation(n): "
      f"{np.array_equal(ch, b)}   (what .sample(frac=1) actually calls)")
