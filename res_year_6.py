import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np, rasterio
from pyproj import Transformer
import grouse_data as G
cfg=G.DataConfig(); R=['ME','NH','VT']
data={r:G.RegionData(r,cfg) for r in R}
FE=['tsd','balive','tcc','qmd','road_dist','carbon_dwn','tpa_live']
rng=np.random.default_rng(0)

def load(kind,r):
    if kind=='pos':
        return pd.concat([pd.read_csv(f'data/pipeline/{p}_positives_{r}.csv') for p in ['train','val']],ignore_index=True)
    return pd.concat([pd.read_csv(f'data/negatives/{p}_negatives_{r}.csv') for p in ['train','val']],ignore_index=True)

def sample(region, feat, year, lons, lats):
    rd=data[region]
    yrs=rd.raster_years(feat)
    ry=min(yrs,key=lambda y:(abs(y-year),y))
    path=rd.path("raster",feature=feat,year=ry)
    with rasterio.open(path) as src:
        tr=Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        xs,ys=tr.transform(lons,lats)
        vals=np.array([v[0] for v in src.sample(list(zip(xs,ys)))],dtype=float)
        nd=src.nodata
    if nd is not None: vals[vals==nd]=np.nan
    return vals, ry

NSAMP=400
res={}
for feat in FE:
    rows=[]
    for region in R:
        P=load('pos',region); N=load('neg',region)
        pre=P[P['year']<2020]; post=P[P['year']>=2020]
        for name,df in [('pos_pre2020',pre),('pos_post2020',post),('neg',N)]:
            d=df.sample(min(NSAMP,len(df)),random_state=1)
            for y,g in d.groupby('year'):
                v,ry=sample(region,feat,int(y),g['longitude'].values,g['latitude'].values)
                rows.append(pd.DataFrame({'grp':name,'region':region,'rec_year':int(y),
                                          'rast_year':ry,'val':v}))
        # counterfactual: pre2020 positives read at 2022 vintage
        d=pre.sample(min(NSAMP,len(pre)),random_state=1)
        v,ry=sample(region,feat,2022,d['longitude'].values,d['latitude'].values)
        rows.append(pd.DataFrame({'grp':'pos_pre2020@2022','region':region,'rec_year':-1,'rast_year':ry,'val':v}))
    D=pd.concat(rows,ignore_index=True)
    res[feat]=D
    g=D.groupby('grp')['val']
    print(f"\n### {feat}")
    print(g.agg(['count','mean','std','median']).round(3))
