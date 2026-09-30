"""Pre-registration artefacts: SHA-256 of each candidate coverage mask, its
outside-fraction, and the three-lineage agreement table.  A repair that swaps
the mask (e.g. for the whole grid) cannot reproduce these digests."""
import os, glob, hashlib, numpy as np, rasterio, itertools
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
NAMES = ["nlcd", "tiger_at1", "tiger_at0", "dist2_cov_all_2025",
         "dist2_cov_all_2016", "dist2_cov_any", "evt"]
def load(region, name, shape):
    a = np.load(os.path.join(SCRATCH, f"{region}_{name}.npy"))
    return np.unpackbits(a)[:shape[0]*shape[1]].astype(bool).reshape(shape)
for r in ("ME", "NH", "VT"):
    tpl = sorted(glob.glob(f"data/landfire/{r}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s: H, W = s.height, s.width
    tot = H*W
    print(f"\n=== {r}  {W}x{H} = {tot:,}")
    M = {}
    for n in NAMES:
        m = load(r, n, (H, W)); M[n] = m
        h = hashlib.sha256(np.packbits(m.ravel()).tobytes()).hexdigest()
        print(f"  {n:20s} inside {int(m.sum()):>12,}  outside_frac {1-m.mean():.6f}  "
              f"sha256 {h[:32]}")
    print("  pairwise disagreement, as % of grid  (A\\B / B\\A):")
    for a, b in itertools.combinations(["nlcd", "tiger_at1", "dist2_cov_all_2025"], 2):
        A, B = M[a], M[b]
        p = (A & ~B).sum(); q = (B & ~A).sum()
        print(f"    {a:20s} vs {b:20s}  {p:>9,} ({100*p/tot:.4f}%) / "
              f"{q:>9,} ({100*q/tot:.4f}%)   union-minus-intersection "
              f"{p+q:>9,} ({100*(p+q)/tot:.4f}%)")
