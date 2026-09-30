import numpy as np, rasterio
for r in ("NH","ME","VT"):
    try:
        rd=rasterio.open(f"data/landfire/{r}_2023_road_dist.tif")
        nl=rasterio.open(f"data/landfire/{r}_2023_nlcd.tif")
    except Exception as e:
        print(r,"open fail",e); continue
    print(f"\n=== {r} ===  road_dist {rd.shape} nodata={rd.nodata} crs={rd.crs.to_string()}  |  nlcd {nl.shape} nodata={nl.nodata}")
    if rd.shape!=nl.shape or rd.transform!=nl.transform:
        print("   GRIDS DIFFER: rd.transform",rd.transform,"nl.transform",nl.transform)
    a=rd.read(1); b=nl.read(1)
    if a.shape!=b.shape:
        print("   shapes differ, skipping pixelwise"); continue
    rdnd = (a==rd.nodata) if rd.nodata is not None else np.zeros(a.shape,bool)
    nlnd = (b==nl.nodata) if nl.nodata is not None else (b==0)
    nlnd = nlnd | (b==0)
    tot=a.size
    print(f"   road_dist NODATA share: {100*rdnd.mean():.2f}%   nlcd-invalid share: {100*nlnd.mean():.2f}%")
    print(f"   D1  valid road_dist where nlcd INVALID (fabricated outside coverage): {100*(~rdnd & nlnd).sum()/tot:.3f}%  ({(~rdnd&nlnd).sum()} px)")
    print(f"   D2  road_dist NODATA where nlcd VALID   (over-masked inside coverage): {100*(rdnd & ~nlnd).sum()/tot:.3f}%  ({(rdnd&~nlnd).sum()} px)")
    vals=a[~rdnd]
    print(f"   road_dist valid range {vals.min()}..{vals.max()}  saturated(==10820?): {(vals==10820).sum()}")
    print(f"   nlcd distinct (first 12): {np.unique(b)[:12]}")
