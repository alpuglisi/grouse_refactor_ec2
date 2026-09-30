"""Remaining cheap-gate costs: assertion (a), (d)/I10, I7, I8,
in-run permutation nulls for I16 and I16b, and the whole pooled
assertion pass end-to-end.  READ-ONLY."""
import time, resource
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree


def rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def tic():
    return time.perf_counter()


def toc(t, l, e=""):
    print(f"{l:54s} {1000*(time.perf_counter()-t):9.1f} ms  "
          f"maxRSS {rss():7.0f} MB  {e}")


REGIONS = ["ME", "NH", "VT"]
BLOCK = 3000.0
T0 = tic()

t = tic()
rows = []
for r in REGIONS:
    for cls, sp, p in (("pos", "train", f"data/pipeline/train_positives_{r}.csv"),
                       ("pos", "val",   f"data/pipeline/val_positives_{r}.csv"),
                       ("neg", "train", f"data/negatives/train_negatives_{r}.csv"),
                       ("neg", "val",   f"data/negatives/val_negatives_{r}.csv")):
        d = pd.read_csv(p)[["longitude", "latitude", "state", "year"]]
        d["cls"], d["split"], d["region"] = cls, sp, r
        rows.append(d)
A = pd.concat(rows, ignore_index=True)
tr = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
A["X"], A["Y"] = tr.transform(A.longitude.values, A.latitude.values)
toc(t, "POOLED LOAD PASS (12 CSVs + reproject)", f"n={len(A)}")

# (a) partition
t = tic()
bad_a = int((A.state.values != A.region.values).sum())
toc(t, "(a) partition  state == region, both classes", f"viol={bad_a}")
print("    by region/class:",
      A[A.state != A.region].groupby(["region", "cls"]).size().to_dict())

# (d) / I10: per-region 30 km occupied-block positive-only fraction
t = tic()
G = 30000.0
res = {}
for r in REGIONS:
    s = A[A.region == r]
    kx = np.floor(s.X.values / G).astype(np.int64)
    ky = np.floor(s.Y.values / G).astype(np.int64)
    key = kx * 1000000 + ky
    pos_blocks = set(key[s.cls.values == "pos"])
    neg_blocks = set(key[s.cls.values == "neg"])
    res[r] = round(len(pos_blocks - neg_blocks) / max(len(pos_blocks), 1), 4)
toc(t, "(d)/I10 30 km occupied-block pos-only fraction", str(res))

# I7 validation fraction per class per region
t = tic()
i7 = (A.assign(isval=(A.split == "val"))
      .groupby(["region", "cls"])["isval"].mean().round(4).to_dict())
toc(t, "I7 val fraction per class per region", "")
print("   ", i7)

# I8 exact ratio per (region, split)
t = tic()
c = A.groupby(["region", "split", "cls"]).size().unstack("cls")
i8 = {(r, s): int(c.loc[(r, s), "neg"]) - int(round(c.loc[(r, s), "pos"] * 1.0))
      for r, s in c.index}
toc(t, "I8 exact per-(region,split) neg == round(n_pos*NEG_RATIO)", str(i8))


def moran(xy, z, k, idx=None):
    if idx is None:
        _, idx = cKDTree(xy).query(xy, k=k + 1)
        idx = idx[:, 1:]
    zc = z - z.mean()
    return float((zc * zc[idx].mean(axis=1)).sum() / (zc * zc).sum()), idx


for name, sel in (("I16 positives-only", A.cls == "pos"),
                  ("I16b all-record", A.index == A.index)):
    s = A[sel]
    key = (np.floor(s.X.values / BLOCK).astype(np.int64) * 100000
           + np.floor(s.Y.values / BLOCK).astype(np.int64))
    df = pd.DataFrame({"k": key,
                       "cx": np.floor(s.X.values / BLOCK) * BLOCK + BLOCK / 2,
                       "cy": np.floor(s.Y.values / BLOCK) * BLOCK + BLOCK / 2,
                       "v": (s.split.values == "val").astype(float)})
    b = df.groupby("k").agg(cx=("cx", "first"), cy=("cy", "first"),
                            v=("v", "max")).reset_index()
    xy = np.c_[b.cx, b.cy]
    z0 = b.v.values
    for k in (4, 8):
        t = tic()
        I, idx = moran(xy, z0, k)
        rng = np.random.default_rng(0)
        nulls = np.empty(1000)
        for i in range(1000):
            zz = rng.permutation(z0)
            zc = zz - zz.mean()
            nulls[i] = (zc * zc[idx].mean(axis=1)).sum() / (zc * zc).sum()
        mu, sd = nulls.mean(), nulls.std(ddof=1)
        toc(t, f"{name} Moran k={k} + 1000-draw in-run null",
            f"nblk={len(b)} I={I:+.5f} null {mu:+.6f}/{sd:.6f} z={(I-mu)/sd:+.2f}")

print(f"\nEND-TO-END pooled assertion pass (coord-only gates): "
      f"{time.perf_counter()-T0:.2f}s  maxRSS {rss():.0f} MB")
