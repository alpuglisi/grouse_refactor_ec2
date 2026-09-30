"""Cost measurement: cheap (coordinate-only) acceptance gates.
READ-ONLY. Times each candidate gate on today's real pooled CSVs."""
import time, os, resource, sys
import numpy as np, pandas as pd

T0 = time.perf_counter()
def rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

def tic(): return time.perf_counter()
def toc(t, label, extra=""):
    print(f"{label:52s} {1000*(time.perf_counter()-t):9.1f} ms   maxRSS {rss():7.0f} MB  {extra}")

REGIONS = ["ME","NH","VT"]
BLOCK = 3000.0
ORIGIN = (0.0, 0.0)

# ---------- load pass ----------
t = tic()
frames = {}
for r in REGIONS:
    frames[("pos","train",r)] = pd.read_csv(f"data/pipeline/train_positives_{r}.csv")
    frames[("pos","val",r)]   = pd.read_csv(f"data/pipeline/val_positives_{r}.csv")
    frames[("neg","train",r)] = pd.read_csv(f"data/negatives/train_negatives_{r}.csv")
    frames[("neg","val",r)]   = pd.read_csv(f"data/negatives/val_negatives_{r}.csv")
toc(t, "LOAD 12 CSVs (pd.read_csv, uncached by RegionData)")

t = tic()
pooled = {}
for cls in ("pos","neg"):
    for sp in ("train","val"):
        d = pd.concat([frames[(cls,sp,r)].assign(region=r) for r in REGIONS],
                      ignore_index=True)
        pooled[(cls,sp)] = d
allrec = pd.concat([pooled[k].assign(cls=k[0], split=k[1]) for k in pooled],
                   ignore_index=True)
toc(t, "POOL concat(ignore_index=True) 4 frames")
print("   pooled sizes:", {k: len(v) for k,v in pooled.items()}, "all:", len(allrec))

# ---------- reprojection (needed by I1,I2,I3,I11,I15-I19) ----------
from pyproj import Transformer
t = tic()
tr = Transformer.from_crs("EPSG:4326","EPSG:5070", always_xy=True)
toc(t, "pyproj Transformer.from_crs(4326->5070)")
t = tic()
X, Y = tr.transform(allrec['longitude'].values, allrec['latitude'].values)
toc(t, f"reproject {len(allrec)} pts 4326->5070")
allrec['X'], allrec['Y'] = X, Y

# ---------- I1: 30 m pair check over pooled positives ----------
from scipy.spatial import cKDTree
pos = allrec[allrec['cls']=='pos']
t = tic()
pairs = cKDTree(np.c_[pos['X'],pos['Y']]).query_pairs(30.0)
toc(t, "I1 cKDTree.query_pairs(30m) over pooled positives",
    f"n={len(pos)} violations={len(pairs)}")

# ---------- I11/I2/I3: recomputed block ids ----------
t = tic()
bx = np.floor((allrec['X'].values - ORIGIN[0]) / BLOCK).astype(np.int64)
by = np.floor((allrec['Y'].values - ORIGIN[1]) / BLOCK).astype(np.int64)
bid = pd.Series([f"{a}_{b}" for a,b in zip(bx,by)])
toc(t, "recompute block ids (floor + f-string join)")
t = tic()
bid_fast = bx * 100000 + by
toc(t, "recompute block ids (integer key, no f-string)")

t = tic()
g = pd.DataFrame({"bid": bid_fast, "split": allrec['split'].values})
both = g.groupby("bid")['split'].nunique()
viol = int((both > 1).sum())
toc(t, "I2 blocks holding both train+val (recomputed ids)", f"viol={viol}")

t = tic()
train_blocks = set(g.loc[allrec['split'].values=='train','bid'])
vneg = allrec[(allrec['cls']=='neg') & (allrec['split']=='val')]
vneg_b = (np.floor((vneg['X'].values)/BLOCK).astype(np.int64)*100000
          + np.floor((vneg['Y'].values)/BLOCK).astype(np.int64))
share = float(np.mean([b in train_blocks for b in vneg_b]))
toc(t, "I3 share of val negs whose block holds a train rec", f"{share:.3f}")

# I11 recorded vs recomputed -- recorded ids are region-local today, so
# only measure the cost of the comparison.
t = tic()
mismatch = int((allrec['block_id'].astype(str).values != bid.values).sum())
toc(t, "I11 recorded vs recomputed block_id compare", f"mismatch={mismatch}/{len(allrec)}")

# ---------- I4: 5 dp coordinate key set intersection, per class ----------
t = tic()
out = {}
for cls in ("pos","neg"):
    sub = allrec[allrec['cls']==cls]
    key = list(zip(sub['longitude'].round(5), sub['latitude'].round(5)))
    ktr = set(k for k,s in zip(key, sub['split']) if s=='train')
    kva = set(k for k,s in zip(key, sub['split']) if s=='val')
    out[cls] = len(ktr & kva)
toc(t, "I4 5dp coord key train/val intersection, per class", str(out))

# ---------- I15: records per val block / block-vs-record val fraction ----------
t = tic()
p = allrec[allrec['cls']=='pos']
pb = (np.floor(p['X'].values/BLOCK).astype(np.int64)*100000
      + np.floor(p['Y'].values/BLOCK).astype(np.int64))
dfp = pd.DataFrame({"b":pb,"split":p['split'].values})
nval_blocks = dfp.loc[dfp.split=='val','b'].nunique()
rec_per_val = (dfp.split=='val').sum()/max(nval_blocks,1)
block_frac = nval_blocks / dfp['b'].nunique()
rec_frac = (dfp.split=='val').mean()
toc(t, "I15 records/val block + block-vs-record val fraction",
    f"{rec_per_val:.3f} recs/blk, blockfrac {block_frac:.4f} recfrac {rec_frac:.4f}")
print(f"   occupied positive blocks = {dfp['b'].nunique()}")
ab = pd.DataFrame({"b":bid_fast,"split":allrec['split'].values})
print(f"   occupied ALL-record blocks = {ab['b'].nunique()}")

# ---------- I18: median val->nearest-train distance (positives) ----------
t = tic()
ptr = p[p.split=='train']; pva = p[p.split=='val']
tree = cKDTree(np.c_[ptr['X'],ptr['Y']])
d,_ = tree.query(np.c_[pva['X'],pva['Y']], k=1)
toc(t, "I18 median val->nearest-train dist (positives)", f"{np.median(d)/1000:.3f} km")

# ---------- I19: frac(pos->nearest-neg > 1920 m), per region, worst ----------
t = tic()
worst = 0.0
for r in REGIONS:
    pr = allrec[(allrec.cls=='pos') & (allrec.region==r)]
    nr = allrec[(allrec.cls=='neg') & (allrec.region==r)]
    dd,_ = cKDTree(np.c_[nr['X'],nr['Y']]).query(np.c_[pr['X'],pr['Y']], k=1)
    v = float((dd > 1920.0).mean()); worst = max(worst, v)
    print(f"      {r}: {v:.4f}")
toc(t, "I19 per-region frac(pos->nearest-neg>1920m), worst", f"{worst:.4f}")

# ---------- I16 / I16b: Moran's I of val indicator over block centres ----------
def morans_I(xy, z, k):
    tree = cKDTree(xy)
    d, idx = tree.query(xy, k=k+1)
    idx = idx[:,1:]
    zc = z - z.mean()
    n = len(z)
    # row-standardised kNN weights: each row weight 1/k
    lag = zc[idx].mean(axis=1)
    num = float((zc*lag).sum())
    den = float((zc*zc).sum())
    return n/ n * num/den if den else 0.0   # W = n (rows sum to 1) -> I = num/den

for label, sel in (("I16 positives-only blocks", allrec.cls=='pos'),
                   ("I16b ALL-record blocks", allrec.cls.notna())):
    sub = allrec[sel]
    b = (np.floor(sub['X'].values/BLOCK).astype(np.int64),
         np.floor(sub['Y'].values/BLOCK).astype(np.int64))
    key = b[0]*100000 + b[1]
    dfb = pd.DataFrame({"key":key, "cx": b[0]*BLOCK+BLOCK/2,
                        "cy": b[1]*BLOCK+BLOCK/2,
                        "isval": (sub['split'].values=='val').astype(float)})
    bl = dfb.groupby("key").agg(cx=("cx","first"), cy=("cy","first"),
                                isval=("isval","max")).reset_index()
    xy = np.c_[bl.cx, bl.cy]; z = bl.isval.values
    for k in (4,8):
        t = tic()
        I = morans_I(xy, z, k)
        toc(t, f"{label} Moran k={k}", f"nblocks={len(bl)} I={I:+.6f}")

# ---------- cost of a 1000-draw empirical null for Moran ----------
sub = allrec[allrec.cls=='pos']
key = (np.floor(sub['X'].values/BLOCK).astype(np.int64)*100000
       + np.floor(sub['Y'].values/BLOCK).astype(np.int64))
dfb = pd.DataFrame({"key":key,"cx":np.floor(sub['X'].values/BLOCK)*BLOCK,
                    "cy":np.floor(sub['Y'].values/BLOCK)*BLOCK,
                    "isval":(sub['split'].values=='val').astype(float)})
bl = dfb.groupby("key").agg(cx=("cx","first"),cy=("cy","first"),
                            isval=("isval","max")).reset_index()
xy = np.c_[bl.cx,bl.cy]; z0 = bl.isval.values
rng = np.random.default_rng(0)
t = tic()
tree = cKDTree(xy); d, idx = tree.query(xy, k=5); idx = idx[:,1:]
vals=[]
for _ in range(200):
    z = rng.permutation(z0)
    zc = z - z.mean()
    vals.append(float((zc*zc[idx].mean(axis=1)).sum()/ (zc*zc).sum()))
toc(t, "Moran permutation null, 200 draws (k=4, tree reused)",
    f"mean {np.mean(vals):+.6f} sd {np.std(vals):.6f}")

print(f"\nTOTAL script wall {time.perf_counter()-T0:.1f}s  maxRSS {rss():.0f} MB")
