"""ATTACK 1 vs the CURRENT acceptance set (I1-I13 + (a)-(d))."""
import pandas as pd, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
import prepare_training_data as P
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True); R=["ME","NH","VT"]
allrows=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
own=allrows[(~allrows['nonveg_landcover'].astype(bool))&(allrows.state==allrows._reg)].drop_duplicates(subset=['longitude','latitude'])
pool=P.thin_by_min_distance(own,30,42)
def run(shuffle,seed):
    size=3000.0
    bx=np.floor(pool.x_5070.values/size).astype(int); by=np.floor(pool.y_5070.values/size).astype(int)
    bid=pd.Series([f"{a}_{b}" for a,b in zip(bx,by)],index=pool.index)
    bc=bid.value_counts()
    blocks = bc.sample(frac=1,random_state=seed).index.tolist() if shuffle else bc.index.tolist()
    t=int(round(0.2*len(pool))); vb=set(); run_=0
    for b in blocks:
        if run_>=t: break
        vb.add(b); run_+=bc[b]
    d=pool.copy(); d['block_id']=bid; d['split']=bid.map(lambda b:'val' if b in vb else 'train')
    return d
print("                                      I6    I7pool   NH%    ME%    VT%   valblk  rec/valblk  medDensVal/medDensTrain")
for shuffle in (True,False):
    for seed in (42,7,1):
        d=run(shuffle,seed)
        v=d[d.split=='val']; tr=d[d.split=='train']
        pr={s:100*(d[d.state==s].split=='val').mean() for s in R}
        dens=np.median(v.spatial_density)/np.median(tr.spatial_density)
        lbl=("CORRECT" if shuffle else "ATTACK ")+f" seed={seed}"
        print(f"{lbl:36} {len(d):5} {100*(d.split=='val').mean():6.2f}% "
              f"{pr['NH']:6.2f} {pr['ME']:6.2f} {pr['VT']:6.2f} {v.block_id.nunique():6} "
              f"{len(v)/v.block_id.nunique():10.2f} {dens:20.2f}")
d=run(False,42)
print("\nATTACK seed=42 detail vs each acceptance item:")
print("  I1 pooled pairs<30m:",len(cKDTree(d[['x_5070','y_5070']].values).query_pairs(30)),"(req 0)")
kt=set(zip(d[d.split=='train'].longitude.round(5),d[d.split=='train'].latitude.round(5)))
kv=set(zip(d[d.split=='val'].longitude.round(5),d[d.split=='val'].latitude.round(5)))
print("  I4 pos train∩val:",len(kt&kv),"(req 0)")
g=d.groupby('block_id')['split'].nunique(); print("  I2/(c) blocks with both splits:",int((g>1).sum()),"(req 0)")
print("  I6 count:",len(d),"(req 6230 +/- 2%)")
print("  I7 pooled positive val fraction: %.2f%% (req 20 +/- 1); per-region max deviation %.2f pp (I7 asks 'justify if >3 pp')"
      %(100*(d.split=='val').mean(), max(abs(100*(d[d.state==s].split=='val').mean()-20) for s in R)))
print("  I11 recorded==recomputed: 0 by construction;  I10/(d) unaffected (block->split only)")
print("  I12 manifest: spacing 30, block 3000, origin (0,0), seed 42, val_fraction 0.2 -- all equal to the constants")
