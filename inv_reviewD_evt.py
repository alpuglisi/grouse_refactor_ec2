import numpy as np, rasterio
for r in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{r}_2023_evt.tif") as e, rasterio.open(f"data/landfire/{r}_2023_nlcd.tif") as n:
        ev=e.read(1); nl=n.read(1)
        evnd=(ev==e.nodata); nlnd=(nl==n.nodata)
        print(f"{r}: evt nodata {100*evnd.mean():.4f}%   nlcd nodata {100*nlnd.mean():.4f}%")
        vb=~evnd
        print(f"   evt-valid pixels outside NLCD footprint: {100*(vb&nlnd).sum()/max(vb.sum(),1):.2f}%")
        print(f"   nlcd-valid pixels where evt is nodata:   {100*((~nlnd)&evnd).sum()/max((~nlnd).sum(),1):.2f}%")
    for f in ("tcc","balive"):
        try:
            with rasterio.open(f"data/landfire/{r}_2023_{f}.tif") as s:
                a=s.read(1)
                print(f"   {f}==0 share of evt-valid grid: {100*((a==0)&vb).sum()/vb.sum():.1f}%")
        except Exception as ex: print("   ",f,"n/a",ex)
