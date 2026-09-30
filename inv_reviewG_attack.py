import numpy as np, rasterio
from grouse_data import GrouseData
d=GrouseData(); STEP=8
print("ATTACK 1: coverage mask computed on the 8x-decimated grid, nearest-upsampled.")
print("          (a natural implementation choice given every CR-0008 figure is 8x-decimated)")
for reg in ['ME','NH','VT']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s:
        nl=s.read(1)
    true_valid=(nl>=11)&(nl<=95); H,W=nl.shape; del nl
    dec=true_valid[::STEP,::STEP]
    up=np.repeat(np.repeat(dec,STEP,axis=0),STEP,axis=1)[:H,:W]
    # attacker masks only where `up` says outside
    attacker_masked = ~up
    truly_outside = ~true_valid
    left_fabricated = truly_outside & ~attacker_masked
    destroyed       = true_valid & attacker_masked
    n=H*W
    print(f"\n{reg}: grid {H}x{W} n={n:,}")
    print(f"  outside-coverage px left FABRICATED = {left_fabricated.sum():,}  ({100*left_fabricated.sum()/n:.4f}% of grid)")
    print(f"  in-coverage px DESTROYED            = {destroyed.sum():,}  ({100*destroyed.sum()/n:.4f}% of grid)")
    a1_full = 1.0 - left_fabricated.sum()/truly_outside.sum()
    print(f"  A1 measured FULL-RES  = {a1_full:.6f}   ({'PASS' if a1_full>=0.99 else 'FAIL'} vs >=0.99)")
    lo=truly_outside[::STEP,::STEP]; lf=left_fabricated[::STEP,::STEP]
    a1_dec = 1.0 - lf.sum()/lo.sum()
    print(f"  A1 measured 8x-DECIM  = {a1_dec:.6f}   ({'PASS' if a1_dec>=0.99 else 'FAIL'} vs >=0.99)  <-- the CR's stated method")
    ld=destroyed[::STEP,::STEP]
    print(f"  A2 in-cov zeros: destroyed px seen on the ::8 lattice = {ld.sum():,}")
    del true_valid, up, attacker_masked, truly_outside, left_fabricated, destroyed
