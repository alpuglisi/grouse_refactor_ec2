import os, collections
os.chdir('/home/ec2-user/grouse2')
import grouse_data as G
cfg=G.DataConfig()
print("raster_dir:", cfg.raster_dir)
for r in ['ME','NH','VT']:
    rd=G.RegionData(r,cfg)
    print("==",r)
    for f in G.RASTER_FEATURES:
        ys=rd.raster_years(f)
        print(f"  {f:12s} {ys}")
