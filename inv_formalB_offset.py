"""Formal review B / CR-0008: attack the residual the CR admits.
Q1: how far apart are the three VERIFIED lineage masks (the measured
    cross-check budget)?
Q2: if ONE lineage's mask is displaced by a half/whole pixel (the
    common-mode defect class the CR names but leaves unclosed), does the
    <=0.06%-of-grid cross-check see it, and what does it cost?
Q3: how big is the boundary-pixel count the CR proposes as the cheapest
    mitigation, and does an offset move it?
READ-ONLY."""
import hashlib, numpy as np, rasterio, rasterio.features, geopandas as gpd
from rasterio.transform import Affine
from shapely.geometry import box
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
import glob, os, re

SENT=(-9999,-32768,32767,-1111)
cty = gpd.read_file('data/roads/tl_2023_us_county.zip')
def dyear(p):
    yy=int(re.search(r"Dist(\d{2})",os.path.basename(p)).group(1))
    return 1900+yy if yy>=90 else 2000+yy
DP={dyear(p):p for p in sorted(glob.glob(
   "data/disturbance/USAnnualDisturbance_1999_present/*/*/Tif/*.tif"))}

def boundary_count(m):
    """pixels of m whose 4-neighbourhood contains a non-m pixel."""
    b = np.zeros_like(m)
    b[:-1,:] |= m[:-1,:] & ~m[1:,:]
    b[1:,:]  |= m[1:,:]  & ~m[:-1,:]
    b[:,:-1] |= m[:,:-1] & ~m[:,1:]
    b[:,1:]  |= m[:,1:]  & ~m[:,:-1]
    return int(b.sum())

for reg in ['NH','ME']:
    tpl=f"data/landfire/{reg}_2025_nlcd.tif"
    with rasterio.open(tpl) as s:
        H,W,T,CRS=s.height,s.width,s.transform,s.crs
        nl=s.read(1)
    N=H*W
    M_nl = nl!=-9999; del nl
    g = cty[cty.intersects(gpd.GeoSeries([box(*rasterio.transform.array_bounds(H,W,T))],crs=CRS).to_crs(cty.crs).iloc[0])].to_crs(CRS).geometry
    def tiger(t):
        return rasterio.features.rasterize(((x,1) for x in g), out_shape=(H,W),
            transform=t, fill=0, default_value=1, all_touched=True, dtype='uint8').astype(bool)
    M_tg = tiger(T)
    M_ds = np.load(f"inv_formalB_cov_{reg}_2025.npy")
    def dist_at(t):
        cov=np.ones((H,W),dtype=bool); srcs=[];vrts=[]
        try:
            for d,p in sorted(DP.items()):
                s=rasterio.open(p); srcs.append(s)
                vrts.append(WarpedVRT(s,crs=CRS,transform=t,width=W,height=H,
                                      resampling=Resampling.nearest))
            for r0 in range(0,H,2048):
                n=min(2048,H-r0); from rasterio.windows import Window
                win=Window(0,r0,W,n); blk=np.ones((n,W),dtype=bool)
                for v in vrts: blk &= ~np.isin(v.read(1,window=win),SENT)
                cov[r0:r0+n]=blk
        finally:
            for v in vrts: v.close()
            for s in srcs: s.close()
        return cov
    print(f"\n===== {reg}  grid {H}x{W}={N:,}  0.06%-of-grid budget = {int(6e-4*N):,} px")
    V={'nlcd':M_nl,'tiger_at1':M_tg,'dist_int':M_ds}
    ks=list(V)
    for i in range(len(ks)):
        for j in range(i+1,len(ks)):
            a,b=V[ks[i]],V[ks[j]]
            an=int((a&~b).sum()); bn=int((b&~a).sum())
            print(f"  {ks[i]:10s} vs {ks[j]:10s}: A-not-B {an:>9,} ({100*an/N:.4f}%)  B-not-A {bn:>9,} ({100*bn/N:.4f}%)"
                  f"  {'WITHIN' if max(an,bn)<=6e-4*N else 'OVER'} budget")
    for k,m in V.items():
        print(f"  boundary px {k:10s} = {boundary_count(m):>10,}  inside={int(m.sum()):,}")
    # --- offset attacks
    print("  --- offset attacks (one lineage displaced):")
    for name, shift in (("tiger +1px east", (1,0)), ("tiger +half px east",(0.5,0)),
                        ("dist +1px east", (1,0)), ("dist +half px east",(0.5,0))):
        t = T*Affine.translation(shift[0], shift[1])
        if name.startswith('tiger'):
            M = tiger(t); base='tiger_at1'
        else:
            M = dist_at(t); base='dist_int'
        for other in ('nlcd',):
            a,b=M,V[other]
            an=int((a&~b).sum()); bn=int((b&~a).sum())
            print(f"    {name:20s} vs {other}: A-not-B {an:>9,} ({100*an/N:.4f}%) "
                  f"B-not-A {bn:>9,} ({100*bn/N:.4f}%) -> "
                  f"{'CROSS-CHECK PASSES (undetected)' if max(an,bn)<=6e-4*N else 'cross-check FAILS (detected)'}")
        sd=int((M^V[base]).sum())
        print(f"      symmetric difference vs the correct {base} mask: {sd:,} px"
              f" ({100*sd/N:.4f}% of grid); boundary px {boundary_count(M):,}"
              f" (correct {boundary_count(V[base]):,})")
        del M
    del V,M_nl,M_tg,M_ds
