"""G6 prerequisite: grid identity across ALL files CR-0008 touches, not a
54-file sample."""
import glob, collections, rasterio
by=collections.defaultdict(list)
for p in sorted(glob.glob("data/landfire/*.tif")):
    n=p.split("/")[-1][:-4].split("_")
    reg,yr,feat=n[0],n[1],"_".join(n[2:])
    with rasterio.open(p) as s:
        by[reg].append((feat,yr,s.width,s.height,tuple(round(v,6) for v in s.transform[:6]),
                        s.crs.to_wkt()[:60],s.dtypes[0],s.nodata))
POST={"balive","tpa_live","qmd","carbon_dwn","tcc","tsd"}
for reg,rows in by.items():
    ref=None; bad=[]
    n_post=0
    for feat,yr,w,h,t,c,dt,nd in rows:
        if feat in POST: n_post+=1
        sig=(w,h,t,c)
        if ref is None: ref=(sig,feat,yr)
        if sig!=ref[0]: bad.append((feat,yr,w,h))
        if dt!="int16" or nd!=-9999.0: bad.append((feat,yr,"dtype/nodata",dt,nd))
    print(f"{reg}: {len(rows)} tifs ({n_post} in the post-process set), "
          f"reference grid from {ref[1]}_{ref[2]} {ref[0][0]}x{ref[0][1]}")
    if bad:
        print("   MISMATCHES:")
        for b in bad: print("     ",b)
    else:
        print("   all identical in width/height/transform/CRS/dtype/nodata")
