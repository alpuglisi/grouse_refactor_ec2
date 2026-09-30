"""What does LANDFIRE evt (and nlcd) actually SAY outside the NLCD footprint?
Decides whether evt's beyond-border validity is real mapping or a fill class."""
import os, sys, glob, numpy as np, rasterio
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
def load(region, name, shape):
    a = np.load(os.path.join(SCRATCH, f"{region}_{name}.npy"))
    return np.unpackbits(a)[:shape[0]*shape[1]].astype(bool).reshape(shape)
for region in sys.argv[1:]:
    tpl = sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s:
        evt = s.read(1); shape = evt.shape
    nlcd_m = load(region, "nlcd", shape)
    print(f"\n=== {region}  {tpl}")
    for lbl, sel in (("outside NLCD", ~nlcd_m), ("inside NLCD", nlcd_m)):
        v, c = np.unique(evt[sel], return_counts=True)
        o = np.argsort(-c)[:12]
        print(f"  evt values {lbl} ({sel.sum():,} px): " +
              ", ".join(f"{v[i]}x{c[i]:,}" for i in o))
    npath = tpl.replace("_evt.tif", "_nlcd.tif")
    if os.path.exists(npath):
        with rasterio.open(npath) as s:
            nl = s.read(1)
        v, c = np.unique(nl[nlcd_m], return_counts=True)
        o = np.argsort(-c)[:12]
        print(f"  nlcd values inside its own footprint: " +
              ", ".join(f"{v[i]}x{c[i]:,}" for i in o))
