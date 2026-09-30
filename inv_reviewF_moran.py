import pandas as pd, numpy as np
from scipy.spatial import cKDTree
import prepare_training_data as P
R=["ME","NH","VT"]
a=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
own=a[(~a['nonveg_landcover'].astype(bool))&(a.state==a._reg)].drop_duplicates(subset=['longitude','latitude'])
base=P.thin_by_min_distance(own,30,42).reset_index(drop=True)
SZ=3000.0
bx=np.floor(base.x_5070/SZ).astype(int); by=np.floor(base.y_5070/SZ).astype(int)
base['blk']=[f"{x}_{y}" for x,y in zip(bx,by)]
blks=base.drop_duplicates('blk')[['blk']].copy()
blks['cx']=[ (int(b.split('_')[0])+0.5)*SZ for b in blks.blk]
blks['cy']=[ (int(b.split('_')[1])+0.5)*SZ for b in blks.blk]
XY=blks[['cx','cy']].values
def moran(vb,k):
    y=np.array([1.0 if b in vb else 0.0 for b in blks.blk]); n=len(y)
    z=y-y.mean()
    _,idx=cKDTree(XY).query(XY,k=k+1); idx=idx[:,1:]
    I=(z[idx].mean(axis=1)*z).sum()/ (z**2).sum()
    return I,n
def z(vb,k,mu,sd): I,_=moran(vb,k); return (I-mu)/sd
def correct(seed,vf=0.2):
    bc=base['blk'].value_counts(); order=bc.sample(frac=1,random_state=seed).index.tolist()
    t=int(round(vf*len(base))); vb=set(); run=0
    for b in order:
        if run>=t: break
        vb.add(b); run+=bc[b]
    return vb
def east(seed,vf=0.2):
    vb=set(); rng=np.random.default_rng(seed)
    for r in R:
        sub=base[base.state==r]; bc=sub['blk'].value_counts()
        bxx=pd.Series({b:int(b.split('_')[0]) for b in bc.index}); cut=bxx.median()
        el=[b for b in bc.index if bxx[b]>=cut]; rng.shuffle(el)
        t=int(round(vf*len(sub))); run=0
        for b in el:
            if run>=t: break
            vb.add(b); run+=bc[b]
    return vb
for k in (4,8):
    Is=np.array([moran(correct(s),k)[0] for s in range(200)])
    mu,sd=Is.mean(),Is.std(ddof=1)
    zc=np.array([(i-mu)/sd for i in Is])
    ze=np.array([z(east(s),k,mu,sd) for s in range(10)])
    print(f"k={k}: fair null mu={mu:+.6f} sd={sd:.6f} (CR: k=4 -0.000191/0.011383, k=8 -0.000206/0.007941)")
    print(f"      fair z: max {zc.max():+.2f}   |   EAST-HALF attack z over 10 seeds: "
          f"min {ze.min():+.1f} median {np.median(ze):+.1f} max {ze.max():+.1f}  -> gate z<=5.0: "
          f"{'CAUGHT' if ze.min()>5.0 else 'ESCAPES at some seed'}")
