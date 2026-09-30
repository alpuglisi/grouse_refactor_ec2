import numpy as np, rasterio
from grouse_data import GrouseData
d=GrouseData(); STEP=8
print("=== Break-1 aliased mask vs the NLCD cross-check budget (0.05% of grid per direction) ===")
for reg in ['ME','NH','VT']:
    with rasterio.open(d[reg].raster_path('nlcd',2016)) as s: nl=s.read(1)
    TRUE=(nl>=11)&(nl<=95); H,W=nl.shape; N=nl.size; del nl
    A=np.repeat(np.repeat(TRUE[::STEP,::STEP],STEP,0),STEP,1)[:H,:W]
    d1=int((A&~TRUE).sum()); d2=int((~A&TRUE).sum())
    print(f"  {reg}: alias-in/true-out={d1:>8,} ({100*d1/N:.4f}%)  alias-out/true-in={d2:>8,} ({100*d2/N:.4f}%)"
          f"  -> {'CAUGHT' if max(d1,d2)/N>5e-4 else '*** MISSED by a 0.05% gate ***'}")
    del TRUE,A
print("  NH road_dist control (the only legitimate artifact) measures 0.0062% / 0.0017%")
print("  -> a 0.05% budget is 8x / 29x looser than its sole calibrating evidence (PA-0021(c))")

print("\n=== G1's road_dist exemption: what gates ME/VT road_dist IN-coverage? ===")
reg='ME'; r=d[reg]
with rasterio.open(r.raster_path('nlcd',2016)) as s: nl=s.read(1)
TRUE=(nl>=11)&(nl<=95); N=nl.size; del nl
with rasterio.open(r.raster_path('road_dist',2016)) as s: old=s.read(1)
new=np.where(TRUE,np.int16(4200),np.int16(-9999)).astype(np.int16)  # garbage in-coverage
out=~TRUE
print(f"  constructed: every in-coverage ME road_dist px set to a constant 4200 (~65 m decoded)")
print(f"    G1: road_dist ME/VT is EXEMPT (CR-0008:254-255)                       -> not evaluated")
print(f"    G2: outside-coverage nodata frac = {(new[out]==-9999).mean():.6f}      -> PASS (exactly 1.0000)")
print(f"    G6 grid identity: unchanged                                           -> PASS")
print(f"  in-coverage px left unconstrained by ANY gate = {int(TRUE.sum()):,} = {100*TRUE.mean():.2f}% of the ME grid")
print(f"  (the ground-truth spot-check in the v2 test plan survives at :377-378 with NO threshold)")

print("\n=== whole-ME predict feasibility (CR-0009 item 4) ===")
import os
for p in ['data/predictions/ME_custom_suitability.tif','data/predictions/NH_custom_suitability.tif']:
    with rasterio.open(p) as s:
        print(f"  {p}: {s.width}x{s.height} dtype={s.dtypes[0]} size={os.path.getsize(p)/1e6:.1f} MB")
