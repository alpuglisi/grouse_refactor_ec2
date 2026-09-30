import numpy as np, rasterio
from grouse_data import GrouseData
d=GrouseData(); STEP=8
print("A1 nlcd row: which reference produces 0.998 / 0.997 / -- ?")
for reg in ['ME','NH','VT']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s: nl=s.read(1)[::STEP,::STEP]
    with rasterio.open(r.raster_path('evt',2022)) as s: ev=s.read(1)[::STEP,::STEP]
    outUS=((nl<11)|(nl>95)); evnd=(ev==-9999)
    print(f"  {reg}: nlcd-nodata frac among NLCD-invalid px (A1's own reference) = {(nl[outUS]==-9999).mean():.4f}")
    if evnd.sum():
        print(f"       nlcd-nodata frac among EVT-nodata  px (the rejected ref)  = {(nl[evnd]==-9999).mean():.4f}   [n={evnd.sum()}]")
    else:
        print(f"       nlcd-nodata frac among EVT-nodata  px = UNDEFINED (0 evt-nodata px) -> explains the '--' cell")
    del nl,ev,outUS,evnd

print("\nATTACK 4: destroy ALL in-coverage NON-ZERO information; keep the zero count.")
reg='ME'; r=d[reg]
with rasterio.open(r.raster_path('nlcd',2016)) as s: nl=s.read(1)
us=(nl>=11)&(nl<=95); del nl
with rasterio.open(r.raster_path('balive',2025)) as s:
    ba=s.read(1); prof=dict(transform=s.transform,width=s.width,height=s.height,crs=str(s.crs),dtype=s.dtypes[0],nodata=s.nodata)
old=ba.copy()
new=np.where(us, np.where(old==0,0,np.int16(57)), np.int16(-9999)).astype(np.int16)  # constant fill
print(f"  A1 outside-cov nodata frac      : {(new[~us]==-9999).mean():.6f}  (req >=0.99)  PASS")
print(f"  A2 in-cov zero count before/after: {int(((old==0)&us).sum()):,} / {int(((new==0)&us).sum()):,}  UNCHANGED  PASS")
print(f"  A5 transform/size/crs/dtype/nodata: identical by construction          PASS")
print(f"  A6 out-of-coverage window counts : function of the footprint only      PASS")
print(f"  ACTUAL DAMAGE: in-coverage non-zero px overwritten = {int((us&(old!=0)).sum()):,} "
      f"({100*(us&(old!=0)).sum()/old.size:.2f}% of the ME grid); unique in-cov values {len(np.unique(old[us]))} -> {len(np.unique(new[us]))}")
print("  NO acceptance row in CR-0008 constrains in-coverage NON-ZERO pixel values.")
