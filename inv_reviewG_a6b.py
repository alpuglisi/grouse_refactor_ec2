import numpy as np, rasterio, pyproj, pandas as pd
from grouse_data import GrouseData
d=GrouseData(); WIN=64
for reg in ['ME','NH','VT']:
    r=d[reg]
    with rasterio.open(r.raster_path('nlcd',2016)) as s:
        nl=s.read(1); T=s.transform; crs=s.crs; H,W=nl.shape
    us=(nl>=11)&(nl<=95); del nl
    pad=np.zeros((H+2*WIN,W+2*WIN),bool); pad[WIN:WIN+H,WIN:WIN+W]=us
    tr=pyproj.Transformer.from_crs('EPSG:4326',crs,always_xy=True); inv=~T
    for nm in ['positives','negatives']:
        for split in ['train','val']:
            df=getattr(r,nm)(split)
            x,y=tr.transform(df.longitude.values,df.latitude.values)
            c,rw=inv*(np.array(x),np.array(y))
            c=np.floor(c).astype(int); rw=np.floor(rw).astype(int)
            res=[]
            for i,(rr,cc) in enumerate(zip(rw,c)):
                r0,c0=rr-WIN//2+WIN, cc-WIN//2+WIN
                f=1.0-pad[r0:r0+WIN,c0:c0+WIN].mean()
                ctr = not pad[rr+WIN,cc+WIN]
                res.append((f,ctr))
            f=np.array([a for a,_ in res]); ctr=np.array([b for _,b in res])
            print(f"{reg} {split} {nm}: n={len(df)} any={int((f>0).sum())} >10%={int((f>0.10).sum())} =100%={int((f>=0.999).sum())} max={f.max():.3f} centre_out={int(ctr.sum())}")
            if ctr.sum():
                for i in np.where(ctr)[0]:
                    print(f"     centre-out record: lon={df.longitude.values[i]:.5f} lat={df.latitude.values[i]:.5f} state={df['state'].values[i] if 'state' in df.columns else '?'} winfrac={f[i]:.3f}")
    del us,pad
print()
print("=== look up CR-0007's known exceptions in the negatives files ===")
for reg in ['ME','NH','VT']:
    for split in ['train','val','all']:
        df=d[reg].negatives(split)
        for lon,lat in [(-70.92538,43.3258),(-67.10082,44.501766)]:
            m=(df.longitude.round(5)==round(lon,5))&(df.latitude.round(5)==round(lat,5))
            if m.any(): print(f"  FOUND ({lon},{lat}) in {reg} {split} negatives: state={df[m]['state'].values}")
