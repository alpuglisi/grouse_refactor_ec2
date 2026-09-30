import numpy as np, rasterio
from grouse_data import GrouseData, NODATA_SENTINELS
d=GrouseData()
STEP=8
FEATS=['tsd','balive','tpa_live','qmd','carbon_dwn','tcc','road_dist','nlcd']
for reg in ['ME','NH','VT']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s:
        nl=s.read(1)[::STEP,::STEP]; nlnd=s.nodata
    valid = (nl>=11)&(nl<=95)
    outside = ~valid
    n=nl.size
    print("="*72)
    print(f"{reg}  grid(dec)={nl.shape} n={n}  NLCD-invalid frac={outside.mean():.4f}  nlcd nodata={nlnd}")
    with rasterio.open(r.raster_path('evt',2022)) as s:
        ev=s.read(1)[::STEP,::STEP]; evnd=s.nodata
    evnd_mask = (ev==evnd) if evnd is not None else np.isin(ev,NODATA_SENTINELS)
    print(f"   evt nodata frac={evnd_mask.mean():.4f}  (nodata={evnd})  valid-evt & outside-US={(valid==False)[ (ev!=evnd) ].mean() if evnd is not None else float('nan'):.4f}")
    print(f"   share of grid with valid evt AND outside-US = {((~evnd_mask)&outside).mean():.4f}")
    for f in FEATS:
        yrs=r.raster_years(f)
        for y in [yrs[0], yrs[-1]]:
            with rasterio.open(r.raster_path(f,y)) as s:
                a=s.read(1)[::STEP,::STEP]; nd=s.nodata
            nodm = np.isin(a, NODATA_SENTINELS)
            frac_out_nod = nodm[outside].mean()
            inz = int(((a==0)&valid).sum())
            print(f"   {f:11s} y={y} nodata_decl={nd} | outside-cov nodata frac={frac_out_nod:.4f} | in-cov zeros(dec)={inz} | in-cov nodata frac={nodm[valid].mean():.5f}")
