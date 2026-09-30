"""res_determ_orders.py -- CR-0007 I14 determinism research.

STEP 1: reproduce the six-region-order finding using the REAL code path
(prepare_training_data.thin_by_min_distance, the real value_counts /
sample(frac=1, random_state=seed) greedy fill), under the CR-0007 v2 design:
state partition, pooled thin, global grid anchored at BLOCK_ORIGIN_5070.

Read-only: reads data/pipeline/evaluated_sightings_*.csv, writes nothing
except stdout and res_determ_*.csv scratch files.
"""
import itertools, json
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from prepare_training_data import thin_by_min_distance

REGIONS = ("ME", "NH", "VT")
BLOCK = 3000.0
ORIGIN = (0.0, 0.0)
VF = 0.20
SEED = 42
SPACING = 30.0

raw = {}
for r in REGIONS:
    d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    d["filed"] = r
    raw[r] = d[d["state"] == r].copy()
    print(f"{r}: {len(d):,} rows in file, {len(raw[r]):,} with state=={r}")


def pooled(order, dedup=True, canonical_sort=None):
    p = pd.concat([raw[r] for r in order], ignore_index=True)
    p = p[~p["nonveg_landcover"].astype(bool)]
    if dedup:
        p = p.drop_duplicates(subset=["longitude", "latitude", "year"])
    p = p.reset_index(drop=True)
    if canonical_sort:
        p = p.sort_values(canonical_sort, kind="mergesort").reset_index(drop=True)
    return p


def blocks_of(df):
    bx = np.floor((df["x_5070"].values - ORIGIN[0]) / BLOCK).astype(int)
    by = np.floor((df["y_5070"].values - ORIGIN[1]) / BLOCK).astype(int)
    return pd.Series([f"{a}_{b}" for a, b in zip(bx, by)], index=df.index)


def split_of(thinned, seed=SEED, vf=VF, vc_kind="stable", order_override=None):
    """Exact transcription of assign_spatial_blocks (origin-anchored form)."""
    block_id = blocks_of(thinned)
    block_counts = block_id.value_counts()
    if vc_kind != "stable":
        # emulate pandas<3.0, whose value_counts sorted with the default
        # (unstable) quicksort
        enc = block_id.drop_duplicates().tolist()
        counts = block_id.value_counts()
        block_counts = counts.reindex(enc).sort_values(
            ascending=False, kind=vc_kind)
    if order_override is not None:
        block_counts = block_counts.reindex(order_override(block_counts))
    shuffled = block_counts.sample(frac=1, random_state=seed).index.tolist()
    target_val = int(round(vf * len(thinned)))
    val_blocks, running = set(), 0
    for b in shuffled:
        if running >= target_val:
            break
        val_blocks.add(b)
        running += block_counts[b]
    split = block_id.map(lambda b: "val" if b in val_blocks else "train")
    return block_id, split, val_blocks, block_counts


def stats(thinned, block_id, split, val_blocks):
    xy = thinned[["x_5070", "y_5070"]].values
    iv = (split == "val").values
    d, _ = cKDTree(xy[~iv]).query(xy[iv], k=1)
    per = thinned.assign(v=iv).groupby("state").v.mean() * 100
    return dict(
        n=len(thinned),
        n_blocks=block_id.nunique(),
        n_val_blocks=len(val_blocks),
        val_records=int(iv.sum()),
        val_pct=round(100 * iv.mean(), 4),
        per_region={k: round(v, 3) for k, v in per.items()},
        rec_per_val_block=round(iv.sum() / len(val_blocks), 3),
        med_val_nn_m=round(float(np.median(d)), 1),
        frac_within_1920m=round(float((d < 1920).mean() * 100), 3),
        frac_within_500m=round(float((d < 500).mean() * 100), 3),
    )


print("\n" + "=" * 78)
print("STEP 1  six region-concatenation orders, manifest fixed at "
      f"(spacing={SPACING:.0f}, block={BLOCK:.0f}, origin={ORIGIN}, "
      f"seed={SEED}, vf={VF})")
print("=" * 78)

res = {}
for order in itertools.permutations(REGIONS):
    p = pooled(order)
    t = thin_by_min_distance(p, SPACING, SEED)
    t = t.reset_index(drop=True)
    bid, sp, vb, bc = split_of(t)
    s = stats(t, bid, sp, vb)
    key = "".join(order)
    res[key] = dict(stats=s, val_blocks=vb,
                    kept=set(map(tuple, t[["longitude", "latitude", "year"]]
                                 .round(6).values.tolist())),
                    pooled_n=len(p),
                    valset=set(map(tuple,
                                   t.loc[sp == "val",
                                         ["longitude", "latitude"]].round(6)
                                   .values.tolist())))
    print(f"\norder {key}: pooled {len(p):,} -> thinned {s['n']:,}")
    print("   " + json.dumps(s))

print("\n--- distinct outcomes across the six orders ---")
print("thinned counts        :", sorted({v['stats']['n'] for v in res.values()}))
print("pooled (pre-thin) n   :", sorted({v['pooled_n'] for v in res.values()}))
print("distinct val-block sets:",
      len({frozenset(v['val_blocks']) for v in res.values()}))
print("distinct kept-record sets:",
      len({frozenset(v['kept']) for v in res.values()}))
print("distinct val-record sets:",
      len({frozenset(v['valset']) for v in res.values()}))
print("val record counts     :", sorted({v['stats']['val_records']
                                         for v in res.values()}))
print("n_val_blocks          :", sorted({v['stats']['n_val_blocks']
                                         for v in res.values()}))

keys = list(res)
print("\npairwise: |val blocks symmetric diff| / Jaccard ; "
      "|kept-record symm diff|")
for a, b in itertools.combinations(keys, 2):
    A, B = res[a]['val_blocks'], res[b]['val_blocks']
    KA, KB = res[a]['kept'], res[b]['kept']
    VA, VB = res[a]['valset'], res[b]['valset']
    print(f"  {a} vs {b}:  blocks sym {len(A ^ B):5d}  J {len(A & B)/len(A | B):.4f}"
          f" | kept sym {len(KA ^ KB):4d} | val-records sym {len(VA ^ VB):5d}"
          f" ({100*len(VA ^ VB)/max(len(VA | VB),1):.1f}% of union)")

# how many records that survive in BOTH thinned sets change split
print("\nrecords present in both thinned sets that change split "
      "(ME NH VT baseline):")
base = "MENHVT"
bt = res[base]
for k in keys:
    if k == base:
        continue
    common = bt['kept'] & res[k]['kept']
    # val membership by (lon,lat) for records common to both
    ca = {c[:2] for c in common}
    va = {c for c in bt['valset'] if c in ca}
    vb2 = {c for c in res[k]['valset'] if c in ca}
    print(f"  {base} vs {k}: {len(common):,} common records, "
          f"{len(va ^ vb2):,} change split ({100*len(va ^ vb2)/len(common):.1f}%)")
