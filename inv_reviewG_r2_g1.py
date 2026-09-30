import numpy as np, rasterio
from grouse_data import GrouseData
d=GrouseData(); STEP=8
reg='ME'; r=d[reg]
with rasterio.open(r.raster_path('nlcd',2016)) as s: nl=s.read(1)
TRUE=(nl>=11)&(nl<=95); H,W=nl.shape; N=nl.size; del nl
dec=TRUE[::STEP,::STEP]
ALIAS=np.repeat(np.repeat(dec,STEP,0),STEP,1)[:H,:W]   # Break-1 mask

def gates(old,new,mask_used_by_verifier,label):
    changed = (old!=new)
    outside = ~mask_used_by_verifier
    viol = int((changed & ~outside).sum())
    nd_frac = float((new[outside]==-9999).mean()) if outside.any() else float('nan')
    print(f"   {label:34s} G1 violating px = {viol:>10,}  {'PASS' if viol==0 else 'FAIL'}"
          f" | G2 = {nd_frac:.6f} {'PASS' if abs(nd_frac-1.0)<1e-9 else 'FAIL'}")
    return viol==0 and abs(nd_frac-1.0)<1e-9

# ---- Break 2: tsd, mask in-coverage zeros too
with rasterio.open(r.raster_path('tsd',2016)) as s: old=s.read(1)
new=np.where(TRUE,old,-9999); new=np.where(TRUE&(old==0),-9999,new).astype(np.int16)
print("BREAK 2 (mask in-coverage tsd==0), ME tsd 2016:")
gates(old,new,TRUE,"G1/G2 vs TRUE mask")
print(f"      legit in-coverage px destroyed = {int(((old==0)&TRUE).sum()):,}")
del old,new

# ---- Break 4: constant-fill in-coverage nonzero
with rasterio.open(r.raster_path('balive',2025)) as s: old=s.read(1)
new=np.where(TRUE,np.where(old==0,0,np.int16(57)),np.int16(-9999)).astype(np.int16)
print("\nBREAK 4 (constant-fill in-coverage non-zero), ME balive 2025:")
gates(old,new,TRUE,"G1/G2 vs TRUE mask")
print(f"      in-coverage px overwritten = {int((TRUE&(old!=0)).sum()):,}")
del old,new

# ---- Break 1: decimation-aliased MASK, repair uses ALIAS
with rasterio.open(r.raster_path('balive',2025)) as s: old=s.read(1)
new=np.where(ALIAS,old,np.int16(-9999)).astype(np.int16)
print("\nBREAK 1 (coverage MASK aliased at 8x; repair applied ~ALIAS), ME balive 2025:")
gates(old,new,ALIAS,"G1/G2 vs the mask the REPAIR used")
gates(old,new,TRUE, "G1/G2 vs an INDEPENDENT true mask")
fab=int(((~TRUE)&(new!=-9999)).sum()); des=int((TRUE&(new==-9999)).sum())
print(f"      still-fabricated outside-coverage px = {fab:,}   destroyed in-coverage px = {des:,}")
del old,new

# ---- Break 6 (new): M = whole grid -> no-op repair
with rasterio.open(r.raster_path('balive',2025)) as s: old=s.read(1)
new=old.copy()
M_all=np.ones_like(TRUE)
print("\nBREAK 6 (NEW: coverage mask M = whole grid -> no-op repair), ME balive 2025:")
ch=(old!=new); out=~M_all
print(f"   G1 violating px = {int((ch&~out).sum()):,}  PASS (nothing changed)")
print(f"   G2 outside-coverage set is EMPTY (n={int(out.sum())}) -> 1.0000 by vacuity or 0/0")
print(f"   ACTUAL STATE LEFT: {int(((~TRUE)&(new!=-9999)).sum()):,} fabricated ME px = every BUG-0025 pixel")
