import os
os.chdir('/home/ec2-user/grouse2')
import numpy as np, rasterio
import grouse_data as G
cfg=G.DataConfig(); rd=G.RegionData('NH',cfg)
for f in ['evt','evh','evc','sclass','fdist','ch','cc','tcc','nlcd','road_dist','tsd','balive','tpa_live','qmd','carbon_dwn']:
    latest=rd.latest_raster_path(f)   # validated
    naive=max(rd.raster_years(f))
    print(f"{f:12s} years_max={naive}  latest_valid={os.path.basename(latest)}")
