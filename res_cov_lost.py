"""What is LOST by using the NLCD footprint as the operative mask for the
products whose own footprint was destroyed at source (TreeMap x4, tcc)?
Upper bound on the loss = pixels outside the NLCD footprint that still carry a
NON-ZERO reading (a zero outside the footprint is indistinguishable from the
unmask(0) fill, so it carries no information either way).
Also locates them: border fringe (within k px of the NLCD boundary) vs interior.
And the reverse direction: pixels INSIDE the NLCD footprint where the product
has no reading at all."""
import os, sys, glob, numpy as np, rasterio
from scipy import ndimage
from pyproj import Transformer
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
SENT = (-9999, -32768, 32767, -1111)
def load(region, name, shape):
    a = np.load(os.path.join(SCRATCH, f"{region}_{name}.npy"))
    return np.unpackbits(a)[:shape[0]*shape[1]].astype(bool).reshape(shape)
for region in sys.argv[1:]:
    tpl = sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s: H, W, T, crs = s.height, s.width, s.transform, s.crs
    shape = (H, W)
    nl = load(region, "nlcd", shape)
    tf = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    # 3-px-wide collar just outside the NLCD footprint
    collar = (~nl) & ndimage.binary_dilation(nl, iterations=3, border_value=0)
    print(f"\n=== {region}  outside-NLCD {int((~nl).sum()):,}  "
          f"3px collar {int(collar.sum()):,}")
    for feat, y in (("balive", 2025), ("tpa_live", 2025), ("carbon_dwn", 2025),
                    ("qmd", 2025), ("tcc", 2023)):
        p = f"data/landfire/{region}_{y}_{feat}.tif"
        with rasterio.open(p) as s: a = s.read(1)
        nd = np.zeros(shape, bool)
        for v in SENT: nd |= (a == v)
        pos = (~nd) & (a > 0)
        out_pos = pos & ~nl
        n = int(out_pos.sum())
        inc = int((out_pos & collar).sum())
        lab, nlab = ndimage.label(out_pos)
        locs = ""
        if nlab:
            sz = np.bincount(lab.ravel())[1:]
            big = np.argsort(-sz)[:3]
            ls = []
            for i in big:
                ys, xs = np.where(lab == i+1)
                X, Y = T * (xs.mean()+0.5, ys.mean()+0.5)
                lon, lat = tf.transform(X, Y)
                ls.append(f"{sz[i]:,}px@({lon:.3f},{lat:.3f})")
            locs = "; ".join(ls)
        print(f"  {feat:11s} {y}: >0 outside NLCD {n:>9,} "
              f"({n/(~nl).sum()*100:.4f}% of the outside area, "
              f"{n/a.size*100:.5f}% of grid); in 3px collar {inc:,} "
              f"({100*inc/max(n,1):.1f}%); {nlab:,} comps; {locs}")
        print(f"               nodata INSIDE NLCD: {int((nd & nl).sum()):,}")
        del a, nd, pos, out_pos, lab
