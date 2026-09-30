import numpy as np, rasterio
from grouse_data import GrouseData
STEP=8
rd=GrouseData()["ME"]
with rasterio.open(rd.latest_raster_path("evt")) as s:
    evt=s.read(1)[::STEP,::STEP]; nd=s.nodata
ins=evt!=nd
with rasterio.open(rd.latest_raster_path("nlcd")) as s: nl=s.read(1)[::STEP,::STEP]
with rasterio.open(rd.latest_raster_path("tcc")) as s: tc=s.read(1)[::STEP,::STEP]
hole = ins & (nl==-9999)
print("nlcd-hole-inside-evt px:",hole.sum(), "of", ins.sum())
u,c=np.unique(evt[hole],return_counts=True); o=np.argsort(-c)[:10]
print("evt codes there:", [(int(u[i]),int(c[i])) for i in o])
# row profile: is the hole a contiguous band?
rp = hole.sum(1)/np.maximum(ins.sum(1),1)
print("nlcd hole fraction by row decile:", np.round([rp[i*len(rp)//10:(i+1)*len(rp)//10].mean() for i in range(10)],3))
cp = hole.sum(0)/np.maximum(ins.sum(0),1)
print("nlcd hole fraction by col decile:", np.round([cp[i*len(cp)//10:(i+1)*len(cp)//10].mean() for i in range(10)],3))
z = ins & (tc==0)
print("\ntcc==0 inside evt:",z.sum())
u,c=np.unique(evt[z],return_counts=True); o=np.argsort(-c)[:10]
print("evt codes where tcc==0:", [(int(u[i]),int(c[i])) for i in o])
rp2 = z.sum(1)/np.maximum(ins.sum(1),1)
print("tcc0 fraction by row decile:", np.round([rp2[i*len(rp2)//10:(i+1)*len(rp2)//10].mean() for i in range(10)],3))
print("\ntcc hist inside evt:", np.histogram(tc[ins],bins=[-10000,-1,1,10,25,50,75,90,101])[0])
print("overlap: tcc==0 & nlcd==-9999 inside:", (z&hole).sum(), " tcc==0 & nlcd valid:", (z&~hole).sum())
