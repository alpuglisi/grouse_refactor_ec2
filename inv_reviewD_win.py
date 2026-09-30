import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
REG=["ME","NH","VT"]
for r in REG:
    src=rasterio.open(f"data/landfire/{r}_2023_evt.tif") if __import__('os').path.exists(f"data/landfire/{r}_2023_evt.tif") else rasterio.open(f"data/landfire/{r}_2023_nlcd.tif")
    H,W=src.shape
    T=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
    for nm,p in (("thinned_pos",f"data/pipeline/thinned_positives_{r}.csv"),("negatives",f"data/negatives/negatives_{r}.csv")):
        df=pd.read_csv(p)
        x,y=T.transform(df.longitude.values,df.latitude.values)
        rows,cols=rasterio.transform.rowcol(src.transform,x,y)
        rows=np.asarray(rows);cols=np.asarray(cols)
        for half,lbl in ((32,"64x64"),(40,"80x80 (jitter=8)")):
            bad=((rows-half<0)|(rows+half>H)|(cols-half<0)|(cols+half>W)).sum()
            print(f"{r} {nm} {lbl}: {bad} of {len(df)} records whose window is NOT fully inside {src.name.split('/')[-1]} ({H}x{W})")
    src.close()
