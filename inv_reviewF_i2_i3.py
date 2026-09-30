import pandas as pd, numpy as np
from pyproj import Transformer
R=["ME","NH","VT"]
def L(p,r): 
    d=pd.read_csv(p.format(r=r)); d['_reg']=r; return d
trp=pd.concat([L("data/pipeline/train_positives_{r}.csv",r) for r in R],ignore_index=True)
vap=pd.concat([L("data/pipeline/val_positives_{r}.csv",r) for r in R],ignore_index=True)
trn=pd.concat([L("data/negatives/train_negatives_{r}.csv",r) for r in R],ignore_index=True)
van=pd.concat([L("data/negatives/val_negatives_{r}.csv",r) for r in R],ignore_index=True)
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def bid(df,size=3000.0,ox=0.0,oy=0.0):
    x,y=T.transform(df['longitude'].values,df['latitude'].values)
    return pd.Series([f"{a}_{b}" for a,b in zip(np.floor((x-ox)/size).astype(int),np.floor((y-oy)/size).astype(int))],index=df.index)
for nm,d,s in [("trp",trp,'train'),("vap",vap,'val'),("trn",trn,'train'),("van",van,'val')]:
    d['_split']=s; d['_gb']=bid(d)
allrec=pd.concat([trp,vap,trn,van],ignore_index=True)
allrec['_cls']=['pos']*(len(trp)+len(vap))+['neg']*(len(trn)+len(van))
g=allrec.groupby('_gb')['_split'].nunique()
print("I2 blocks holding both train and val (pooled, both classes together):",int((g>1).sum()),"of",g.size,"blocks")
for c in ['pos','neg']:
    gg=allrec[allrec._cls==c].groupby('_gb')['_split'].nunique()
    print(f"   class {c}: {int((gg>1).sum())} of {gg.size}")
gu=allrec.groupby('_gb').apply(lambda d:(d._split=='train').any() and (d._split=='val').any(),include_groups=False)
print("   union-of-per-class variant (blocks with both in either class separately):",
      int(sum(1 for b in g.index if ((allrec[(allrec._gb==b)&(allrec._cls=='pos')]._split.nunique()>1) or (allrec[(allrec._gb==b)&(allrec._cls=='neg')]._split.nunique()>1)))))
# I3
trainblocks=set(allrec.loc[allrec._split=='train','_gb'])
m=van['_gb'].isin(trainblocks)
print(f"I3 val negatives whose block holds any train record: {int(m.sum())}/{len(van)} = {100*m.mean():.2f}%")
mv=vap['_gb'].isin(trainblocks)
print(f"   (val positives same measure: {int(mv.sum())}/{len(vap)} = {100*mv.mean():.2f}%)")
# using recorded block_id column instead (tautology check)
allrec['_rb']=allrec['block_id']
g2=allrec.groupby('_rb')['_split'].nunique()
print("recorded-column form, pooled (ids collide across regions):",int((g2>1).sum()),"of",g2.size)
g3=allrec.groupby(['_reg','_rb'])['_split'].nunique()
print("recorded-column form, per-region:",int((g3>1).sum()),"of",g3.size)
# drifted origin demo
for ox,oy in [(1500.0,0.0),(1500.0,1500.0)]:
    d2=allrec.copy(); d2['_gb2']=bid(d2,3000.0,ox,oy)
    gg=d2.groupby('_gb2')['_split'].nunique()
    print(f"drifted origin ({ox},{oy}): blocks with both = {int((gg>1).sum())} of {gg.size}")
