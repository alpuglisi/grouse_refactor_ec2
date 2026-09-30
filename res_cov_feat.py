"""Current state of the derived rasters at FULL resolution, measured against
each feature's own locally-derived reference:
   tsd            -> dist2 cov_all_{year<=2016 ? 2016 : 2025}  (LANDFIRE
                     disturbance intersection, from the bundle's own tables)
   treemap x4/tcc -> NLCD valid footprint  (footprint destroyed at source)
   road_dist      -> TIGER 2023 county union (all_touched=True)
   nlcd/evt       -> themselves (reported for contrast)
Reports, per feature/year: nodata fraction, nodata inside coverage,
non-nodata OUTSIDE coverage (= fabricated pixels), and the signature value
count inside coverage (the diagnostic the CR wants reported, not gated)."""
import os, sys, glob, numpy as np, rasterio
from models import tsd_encode, TSD_MAX_YEARS
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
SENT = (-9999, -32768, 32767, -1111)
SAT = int(tsd_encode(TSD_MAX_YEARS))
def load(region, name, shape):
    a = np.load(os.path.join(SCRATCH, f"{region}_{name}.npy"))
    return np.unpackbits(a)[:shape[0]*shape[1]].astype(bool).reshape(shape)
PLAN = {"tsd": (2016, 2025), "balive": (2016, 2025), "tpa_live": (2016, 2025),
        "qmd": (2016, 2025), "carbon_dwn": (2016, 2025), "tcc": (2016, 2023),
        "road_dist": (2024,), "nlcd": (2024,), "evt": (2024,)}
REF = {"tsd": "dist2_cov_all_2025", "road_dist": "tiger_at1"}
for region in sys.argv[1:]:
    tpl = sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s: H, W = s.height, s.width
    shape = (H, W); tot = H*W
    masks = {}
    print(f"\n=== {region} {W}x{H} = {tot:,}")
    print(f"{'feature':11s} {'yr':>5s} {'nodata':>13s} {'nd_frac':>9s} "
          f"{'ref_valid':>13s} {'FABRICATED':>12s} {'nd_IN_cov':>11s} "
          f"{'G2':>9s} {'signature_in_cov':>18s}")
    for feat, years in PLAN.items():
        refname = REF.get(feat, "nlcd")
        if refname not in masks: masks[refname] = load(region, refname, shape)
        ref = masks[refname]
        for y in years:
            p = f"data/landfire/{region}_{y}_{feat}.tif"
            if not os.path.exists(p):
                print(f"{feat:11s} {y:>5d}  [absent]"); continue
            with rasterio.open(p) as s: a = s.read(1)
            nd = np.zeros(shape, bool)
            for v in SENT: nd |= (a == v)
            out = ~ref
            fab = int((out & ~nd).sum())
            nd_in = int((ref & nd).sum())
            g2 = (out & nd).sum() / max(out.sum(), 1)
            if feat == "tsd":
                sig = f"=={SAT}: {int((ref & (a == SAT)).sum()):,}"
            elif feat in ("balive", "tpa_live", "qmd", "carbon_dwn", "tcc"):
                sig = f"==0: {int((ref & (a == 0)).sum()):,}"
            else:
                sig = ""
            print(f"{feat:11s} {y:>5d} {int(nd.sum()):>13,} {nd.mean():>9.6f} "
                  f"{int(ref.sum()):>13,} {fab:>12,} {nd_in:>11,} "
                  f"{g2:>9.6f} {sig:>18s}")
            del a, nd
