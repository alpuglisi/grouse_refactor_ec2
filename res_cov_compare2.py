"""Characterise the NLCD vs disturbance-intersection disagreement (the pair the
tsd decision turns on): boundary fringe or real interior geography?"""
import os, glob, numpy as np, rasterio
from scipy import ndimage
from pyproj import Transformer
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
def load(r, n, shape):
    a = np.load(os.path.join(SCRATCH, f"{r}_{n}.npy"))
    return np.unpackbits(a)[:shape[0]*shape[1]].astype(bool).reshape(shape)
for r in ("NH", "VT", "ME"):
    tpl = sorted(glob.glob(f"data/landfire/{r}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s: H, W, T, crs = s.height, s.width, s.transform, s.crs
    tf = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    A = load(r, "nlcd", (H, W)); B = load(r, "dist2_cov_all_2025", (H, W))
    print(f"\n=== {r}")
    for nm, D, REF in (("nlcd\\dist", A & ~B, B), ("dist\\nlcd", B & ~A, A)):
        if D.sum() == 0: print(f"  {nm}: 0"); continue
        edge = REF ^ ndimage.binary_erosion(REF, iterations=2, border_value=1)
        edge |= (~REF) ^ ndimage.binary_erosion(~REF, iterations=2, border_value=1)
        lab, nl = ndimage.label(D)
        sz = np.bincount(lab.ravel())[1:]
        big = np.argsort(-sz)[:5]; ls = []
        for i in big:
            ys, xs = np.where(lab == i+1)
            X, Y = T * (xs.mean()+0.5, ys.mean()+0.5)
            lon, lat = tf.transform(X, Y)
            ls.append(f"{sz[i]:,}px@({lon:.3f},{lat:.3f})")
        print(f"  {nm}: {int(D.sum()):,} ({100*D.mean():.4f}% of grid); within 2px of "
              f"the other mask's edge {int((D & edge).sum()):,} "
              f"({100*(D & edge).sum()/D.sum():.1f}%); {nl:,} components; "
              f"largest {', '.join(ls)}")
        del lab
