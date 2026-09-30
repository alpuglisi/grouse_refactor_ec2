import numpy as np, rasterio
from grouse_data import GrouseData
d=GrouseData(); STEP=8
print("ATTACK 2: post-process masks in-coverage tsd==0 as well as outside-coverage.")
for reg in ['ME']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s: nl=s.read(1)
    valid=(nl>=11)&(nl<=95); del nl
    for y in [2016,2020,2024]:
        with rasterio.open(r.raster_path('tsd',y)) as s: a=s.read(1)
        old=a.copy()
        new=np.where(valid,a,-9999)          # correct part
        new=np.where(valid&(a==0),-9999,new) # the bug
        n=a.size
        print(f"\n {reg} tsd {y}:")
        print(f"   legit in-cov px destroyed        = {int(((old==0)&valid).sum()):,}")
        print(f"   A1 outside-cov nodata frac       = {(new[~valid]==-9999).mean():.6f}  PASS")
        sat_old=(old[valid]==3434).sum()/valid.sum(); sat_new=(new[valid]==3434).sum()/valid.sum()
        print(f"   A3 share reading TSD_MAX inside coverage: before {sat_old:.6f} after {sat_new:.6f}  -> UNCHANGED, PASS")
        print(f"   A2 covers tsd?  no ('TreeMap zeros'/'tcc zeros' rows only); A3 asserts tsd has 0 in-cov zeros -> {int(((old==0)&valid).sum()):,} is the real number")
        del a,old,new
    del valid

print("\n"+"="*70)
print("ATTACK 3: exploit the >=0.99 threshold directly (leave 1% of outside-coverage fabricated)")
d2=GrouseData()
for reg in ['ME','NH','VT']:
    with rasterio.open(d2[reg].raster_path('nlcd',2016)) as s: nl=s.read(1)
    out=((nl<11)|(nl>95)); n=nl.size
    allow=int(0.01*out.sum())
    budget=int(0.0005*n)
    print(f" {reg}: grid {n:,} | outside-cov {out.sum():,} | A1 permits {allow:,} fabricated px ({100*allow/n:.4f}% of grid)"
          f" | CR's stated disagreement budget 0.05% of grid = {budget:,} px -> A1 is {allow/budget:.1f}x looser")
    del nl,out
