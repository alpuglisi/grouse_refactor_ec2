"""Full-resolution validity masks per region: nlcd (all years), evt (all years).
Saves packed bit masks to scratch. READ-ONLY on project data."""
import os, sys, glob, re
import numpy as np, rasterio

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
SENT = (-9999, -32768, 32767, -1111)
REGIONS = ("ME", "NH", "VT")

def valid_mask(path):
    with rasterio.open(path) as s:
        a = s.read(1)
        nd = s.nodata
        m = np.ones(a.shape, bool)
        if nd is not None:
            m &= (a != nd)
        for v in SENT:
            m &= (a != v)
        return m, a.shape

def save(name, m):
    np.save(os.path.join(SCRATCH, name + ".npy"), np.packbits(m.ravel()))

def main():
    for r in REGIONS:
        shapes = set()
        base = None
        print(f"\n=== {r}")
        for feat in ("nlcd", "evt"):
            ys = sorted(int(re.search(r"_(\d{4})_", os.path.basename(p)).group(1))
                        for p in glob.glob(f"data/landfire/{r}_*_{feat}.tif"))
            prev = None
            for y in ys:
                m, shp = valid_mask(f"data/landfire/{r}_{y}_{feat}.tif")
                shapes.add(shp)
                n = int(m.sum()); tot = m.size
                line = (f"{feat} {y}: valid {n:,}/{tot:,} = {n/tot:.6f}  "
                        f"nodata_frac {1-n/tot:.6f}")
                if prev is not None:
                    d = int((m != prev).sum())
                    line += f"  diff_vs_prev_year {d:,}"
                print("  " + line)
                prev = m
                if y == ys[-1]:
                    save(f"{r}_{feat}", m)
        print(f"  shapes: {shapes}")

main()
