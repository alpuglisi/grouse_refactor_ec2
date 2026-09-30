"""Before/after panel for the report. Read-only apart from the PNG."""
import numpy as np, rasterio, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
def rd(p):
    with rasterio.open(p) as s: return s.read(1, masked=True).filled(np.nan)
panels = [
    ("road_dist (m), OLD NH raster", np.load("inv_road_dist_OLD_NH.npy"), "magma", (0, 7000)),
    ("road_dist (m), NEW NH raster", np.load("inv_road_dist_NEW_NH.npy"), "magma", (0, 7000)),
    ("suitability BEFORE (gap3.pth)", rd("inv_before/before_gap3_cal.tif"), "jet", (0, 1)),
    ("suitability AFTER (gap3.pth)", rd("inv_after/after_gap3_cal.tif"), "jet", (0, 1)),
    ("suitability BEFORE (bce.pth)", rd("inv_before/before_cal.tif"), "jet", (0, 1)),
    ("suitability AFTER (bce.pth)", rd("inv_after/after_cal.tif"), "jet", (0, 1)),
]
fig, ax = plt.subplots(3, 2, figsize=(11, 15))
for a, (t, arr, cm, (lo, hi)) in zip(ax.ravel(), panels):
    im = a.imshow(arr, cmap=cm, vmin=lo, vmax=hi, interpolation="nearest")
    a.set_title(t, fontsize=10); a.set_xticks([]); a.set_yticks([])
    plt.colorbar(im, ax=a, fraction=0.04)
fig.suptitle("Errol box -71.25 44.70 -70.95 44.90  |  ME side = right/east",
             fontsize=11)
fig.tight_layout(); fig.savefig("inv_before_after.png", dpi=110)
print("wrote inv_before_after.png")
