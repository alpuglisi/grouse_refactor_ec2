"""Pairwise full-resolution comparison of candidate coverage references.
Characterises each disagreement as boundary fringe (within k px of the other
mask's edge) vs interior, and reports lon/lat centroids of the largest
interior components."""
import os, glob, numpy as np, rasterio
from scipy import ndimage
from pyproj import Transformer

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"

def load(region, name, shape):
    a = np.load(os.path.join(SCRATCH, f"{region}_{name}.npy"))
    return np.unpackbits(a)[:shape[0]*shape[1]].astype(bool).reshape(shape)

for r in ("ME", "NH", "VT"):
    tpl = sorted(glob.glob(f"data/landfire/{r}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s:
        shape = (s.height, s.width); T = s.transform; crs = s.crs
    tf = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    M = {n: load(r, n, shape) for n in ("nlcd", "evt", "tiger_at1", "tiger_at0")}
    print(f"\n{'='*70}\n{r}  grid {shape[1]}x{shape[0]} = {shape[0]*shape[1]:,}")
    for a, b in (("nlcd","tiger_at1"), ("nlcd","tiger_at0"), ("nlcd","evt"),
                 ("tiger_at1","evt")):
        A, B = M[a], M[b]
        aob = A & ~B; boa = B & ~A
        na, nb = int(aob.sum()), int(boa.sum())
        print(f"  {a} valid & {b} invalid: {na:,} ({na/A.size*100:.4f}% of grid)")
        print(f"  {b} valid & {a} invalid: {nb:,} ({nb/A.size*100:.4f}% of grid)")
        # fringe test: dilate B's boundary by 2px; how much of the disagreement
        # lies within 2 px of B's edge?
        for nm, D in (("A\\B", aob), ("B\\A", boa)):
            if D.sum() == 0: continue
            edgeB = B ^ ndimage.binary_erosion(B, iterations=2, border_value=1)
            edgeB |= (~B) ^ ndimage.binary_erosion(~B, iterations=2, border_value=1)
            fr = int((D & edgeB).sum())
            lab, nlab = ndimage.label(D)
            sizes = np.bincount(lab.ravel())[1:]
            big = np.argsort(-sizes)[:5]
            locs = []
            for i in big:
                ys, xs = np.where(lab == i+1)
                cy, cx = ys.mean(), xs.mean()
                X, Y = T * (cx+0.5, cy+0.5)
                lon, lat = tf.transform(X, Y)
                locs.append(f"{sizes[i]:,}px@({lon:.3f},{lat:.3f})")
            print(f"     {nm}: within 2px of {b} boundary: {fr:,} "
                  f"({100*fr/max(D.sum(),1):.1f}%); {nlab:,} components; "
                  f"largest: {', '.join(locs)}")
            del lab
        del aob, boa
