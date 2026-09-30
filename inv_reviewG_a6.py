import numpy as np, rasterio, pyproj
from grouse_data import GrouseData
d=GrouseData()
WIN=64
for reg in ['ME','NH']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s:
        nl=s.read(1); T=s.transform; crs=s.crs; H,W=nl.shape
    us=(nl>=11)&(nl<=95); del nl
    tr=pyproj.Transformer.from_crs('EPSG:4326',crs,always_xy=True)
    inv=~T
    for nm in ['positives','negatives']:
        df=getattr(r,nm)('train')
        x,y=tr.transform(df.longitude.values,df.latitude.values)
        cols,rows=inv*(np.array(x),np.array(y))
        cols=np.floor(cols).astype(int); rows=np.floor(rows).astype(int)
        anynd=0; gt10=0; at100=0; centre=0; mx=0.0; ids=[]
        for i,(rr,cc) in enumerate(zip(rows,cols)):
            r0,c0=rr-WIN//2, cc-WIN//2
            if r0<0 or c0<0 or r0+WIN>H or c0+WIN>W: continue
            w=us[r0:r0+WIN,c0:c0+WIN]
            f=1.0-w.mean()
            if f>0: anynd+=1
            if f>0.10: gt10+=1
            if f>=0.999: at100+=1
            if f>mx: mx=f
            if 0<=rr<H and 0<=cc<W and not us[rr,cc]:
                centre+=1; ids.append((round(float(df.longitude.values[i]),5),round(float(df.latitude.values[i]),5),f))
        print(f"{reg} train {nm}: n={len(df)} any-nodata-in-64win={anynd} >10%={gt10} ~100%={at100} maxfrac={mx:.3f} centre-out-of-coverage={centre} {ids[:5]}")
    del us
