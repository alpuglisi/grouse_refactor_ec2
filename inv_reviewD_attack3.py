import numpy as np, pandas as pd, hashlib
from pyproj import Transformer
from scipy.spatial import cKDTree
REG=["ME","NH","VT"]; BS=3000.0; VF=0.2; SEED=42
allpos=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allpos[~allpos['nonveg_landcover'].astype(bool)]
own=hab[hab.state==hab.src].drop_duplicates(subset=["longitude","latitude","year"]).reset_index(drop=True)
def thin(df,m,seed):
    rng=np.random.default_rng(seed); o=rng.permutation(len(df)); c=df[['x_5070','y_5070']].values[o]
    keep=np.zeros(len(df),bool); kept=[]; t=None
    for i,pt in enumerate(c):
        if t is None or t.query(pt,k=1)[0]>=m: kept.append(pt); keep[o[i]]=True; t=cKDTree(np.array(kept))
    return df[keep].copy()
pos=thin(own,30.0,SEED)
def gid(df,ox=0,oy=0):
    return pd.Series([f"{a}_{b}" for a,b in zip(np.floor((df.x_5070.values-ox)/BS).astype(int),
                                                np.floor((df.y_5070.values-oy)/BS).astype(int))],index=df.index)
def assign(df,ids):
    cnt=ids.value_counts(); shuf=cnt.sample(frac=1,random_state=SEED).index.tolist()
    tgt=int(round(VF*len(df))); val=set(); run=0
    for b in shuf:
        if run>=tgt: break
        val.add(b); run+=cnt[b]
    return ids.map(lambda b:'val' if b in val else 'train')
pid=gid(pos); psp=assign(pos,pid)

def check(label, negdf, negid, negsplit, posdf=pos, posid=pid, possplit=psp):
    rec=pd.concat([pd.DataFrame({'x':posdf.x_5070.values,'y':posdf.y_5070.values,'b':np.asarray(posid),'s':np.asarray(possplit),'c':'pos'}),
                   pd.DataFrame({'x':negdf.x_5070.values,'y':negdf.y_5070.values,'b':np.asarray(negid),'s':np.asarray(negsplit),'c':'neg'})],ignore_index=True)
    rec['gb']=[f"{a}_{b}" for a,b in zip(np.floor(rec.x/BS).astype(int),np.floor(rec.y/BS).astype(int))]
    g=rec.groupby('b')['s'].nunique(); g2=rec.groupby('gb')['s'].nunique()
    vn=rec[(rec.s=='val')&(rec.c=='neg')]
    trb=set(rec.loc[rec.s=='train','b']); trg=set(rec.loc[rec.s=='train','gb'])
    t=cKDTree(posdf[['x_5070','y_5070']].values)
    i4={}
    for c in ('pos','neg'):
        s=rec[rec.c==c]
        ktr=set(map(tuple,np.round(s.loc[s.s=='train',['x','y']].values,3)))
        i4[c]=sum(1 for k in map(tuple,np.round(s.loc[s.s=='val',['x','y']].values,3)) if k in ktr)
    print(f"\n### {label}")
    print(f"  I1 {len(t.query_pairs(30.0,output_type='ndarray'))} | I2col {(g>1).sum()} | I3col {100*vn.b.isin(trb).mean():.2f}% | I4 {i4['pos']}/{i4['neg']} | valfrac(pos) {100*np.mean(np.asarray(possplit)=='val'):.2f}% | valfrac(neg) {100*np.mean(np.asarray(negsplit)=='val'):.2f}%")
    print(f"  GEOMETRIC: I2' {(g2>1).sum()} | I3' {100*vn.gb.isin(trg).mean():.2f}%")

negsrc=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in REG],ignore_index=True)

# E: STALE negatives (Sept-18 files, their own block_id + split columns kept)
check("E  PARTIAL REBUILD: positives rebuilt, negatives stale (old region-local ids/splits)",
      negsrc, negsrc.block_id.values, negsrc['split'].values)

# F: compliant but 50% of every record silently dropped
tab=dict(zip(pid,psp)); vf=(psp=='val').mean()
def h(b): return 'val' if int(hashlib.md5(f"{SEED}:{b}".encode()).hexdigest(),16)%10000<vf*10000 else 'train'
nid=gid(negsrc); nsp=np.array([tab.get(b) or h(b) for b in nid])
rng=np.random.default_rng(7)
kp=rng.random(len(pos))<0.5; kn=rng.random(len(negsrc))<0.5
check("F  compliant pipeline, then 50% of ALL records silently dropped",
      negsrc[kn], np.asarray(nid)[kn], nsp[kn], pos[kp], np.asarray(pid)[kp], np.asarray(psp)[kp])

# G: compliant, but only 15% of the val-negative quota was delivered
vmask=(nsp=='val'); idx=np.where(vmask)[0]
drop=rng.choice(idx,size=int(0.85*len(idx)),replace=False)
keep=np.ones(len(negsrc),bool); keep[drop]=False
check("G  compliant, but val negatives 85% short (habitat pool undersupplied)",
      negsrc[keep], np.asarray(nid)[keep], nsp[keep])

# H: are the stored x_5070 columns consistent with reprojecting lon/lat?
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
for nm,df in (("thinned_positives",pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in REG])),
              ("negatives",negsrc)):
    x,y=T.transform(df.longitude.values,df.latitude.values)
    e=np.hypot(x-df.x_5070.values,y-df.y_5070.values)
    print(f"\nstored x_5070/y_5070 vs reprojected lon/lat, {nm}: max err {e.max():.6f} m")
