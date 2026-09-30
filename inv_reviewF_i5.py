import pandas as pd, numpy as np, rasterio, os, collections
from grouse_data import GrouseData, RASTER_FEATURES
gd=GrouseData()
R=["ME","NH","VT"]
for size_label,n in [("64x64",64),("80x80 (img_size 64 + 2*jitter 8)",80)]:
    print(f"\n=== window {size_label} ===")
    for r in R:
        rd=gd[r]
        recs=[]
        for p in [f"data/pipeline/thinned_positives_{r}.csv"]:
            d=pd.read_csv(p); d['_src']='pos'; recs.append(d[['longitude','latitude','year','_src']])
        d=pd.read_csv(f"data/negatives/negatives_{r}.csv"); d['_src']='neg'; recs.append(d[['longitude','latitude','year','_src']])
        df=pd.concat(recs,ignore_index=True)
        fail=np.zeros(len(df),dtype=bool)
        failfeat=collections.Counter()
        for feat in RASTER_FEATURES:
            try: years=rd.raster_years(feat)
            except Exception as e: print("  ",feat,"ERR",e); continue
            # resolve year per record
            yr=df['year'].fillna(max(years)).astype(int).values
            res=np.array([min(years,key=lambda y:(abs(y-v),y)) for v in yr])
            for y in sorted(set(res)):
                try: path=rd.path("raster",feature=feat,year=int(y))
                except Exception: continue
                if not os.path.exists(path): continue
                with rasterio.open(path) as src:
                    inv=~src.transform; H,W=src.height,src.width
                m=res==y
                cols,rows=inv*(df.loc[m,'longitude'].values,df.loc[m,'latitude'].values)
                # note: transform is in raster CRS; need lon/lat -> crs
                # redo with proper transform
                with rasterio.open(path) as src:
                    crs=src.crs
                from pyproj import Transformer
                T=Transformer.from_crs("EPSG:4326",crs,always_xy=True)
                x,y2=T.transform(df.loc[m,'longitude'].values,df.loc[m,'latitude'].values)
                c,ro=inv*(x,y2)
                c=np.floor(c).astype(int); ro=np.floor(ro).astype(int)
                half=n//2
                bad=(c-half<0)|(ro-half<0)|(c-half+n>W)|(ro-half+n>H)
                idx=np.where(m)[0][bad]
                if len(idx): failfeat[feat]+=len(idx)
                fail[idx]=True
        print(f"  {r}: {int(fail.sum())} of {len(df)} records fail; by feature: {dict(failfeat)}")
        if fail.sum(): print("     ", df[fail][['longitude','latitude','_src']].to_string())
