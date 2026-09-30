"""Reviewer D vs CR-0007 Break-4 retest: (d) is a state-histogram check. Does anything
in CR-0007 detect a within-state spatial support mismatch (BUG-0029's actual defect)?"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, hashlib, geopandas as gpd
from pyproj import Transformer
from scipy.spatial import cKDTree
REG=["ME","NH","VT"]; BS=3000.0; ORIGIN=(0.0,0.0); VF=0.2; SEED=42
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
FIPS={"23":"ME","33":"NH","50":"VT"}
cty=gpd.read_file("zip://data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].copy(); cty["ST"]=cty.STATEFP.map(FIPS)
POLY=cty.dissolve(by="ST").reset_index()[["ST","geometry"]]

# ---- compliant positives ----
allp=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allp[~allp['nonveg_landcover'].astype(bool)]
own=hab[hab.state==hab.src].drop_duplicates(subset=["longitude","latitude","year"]).reset_index(drop=True)
def thin(df,m,seed):
    # O(n) greedy: 30 m occupancy cells + 3x3 neighbourhood check (identical rule)
    rng=np.random.default_rng(seed); o=rng.permutation(len(df))
    xs=df["x_5070"].values; ys=df["y_5070"].values
    from collections import defaultdict
    cells=defaultdict(list); keep=np.zeros(len(df),bool)
    for i in o:
        cx,cy=int(np.floor(xs[i]/m)),int(np.floor(ys[i]/m)); ok=True
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for (px,py) in cells.get((cx+dx,cy+dy),()):
                    if (xs[i]-px)**2+(ys[i]-py)**2 < m*m: ok=False; break
                if not ok: break
            if not ok: break
        if ok: cells[(cx,cy)].append((xs[i],ys[i])); keep[i]=True
    return df[keep].copy()

def _thin_old(df,m,seed):
    rng=np.random.default_rng(seed); o=rng.permutation(len(df)); c=df[['x_5070','y_5070']].values[o]
    k=np.zeros(len(df),bool); kept=[]; t=None
    for i,pt in enumerate(c):
        if t is None or t.query(pt,k=1)[0]>=m: kept.append(pt); k[o[i]]=True; t=cKDTree(np.array(kept))
    return df[k].copy()
def gid(x,y):
    return np.array([f"{a}_{b}" for a,b in zip(np.floor((x-ORIGIN[0])/BS).astype(int),
                                               np.floor((y-ORIGIN[1])/BS).astype(int))])
pos=thin(own,30.0,SEED).reset_index(drop=True)
pid=gid(pos.x_5070.values,pos.y_5070.values)
cnt=pd.Series(pid).value_counts(); shuf=cnt.sample(frac=1,random_state=SEED).index.tolist()
tgt=int(round(VF*len(pos))); valb=set(); run=0
for b in shuf:
    if run>=tgt: break
    valb.add(b); run+=cnt[b]
psp=np.array(['val' if b in valb else 'train' for b in pid])
tab=dict(zip(pid,psp)); blockvf=pd.DataFrame({'b':pid,'s':psp}).drop_duplicates('b')['s'].eq('val').mean()
print(f"compliant positives: {len(pos)}  pooled val {100*(psp=='val').mean():.2f}%")

# ---- candidate pool: hygiene + pooled buffer ----
cs=[]
for r in REG:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    c=c[~(c.coord_uncertainty_m>1000).fillna(False)]
    cs.append(c)
cand=pd.concat(cs,ignore_index=True)
cand=cand.loc[~cand[['longitude','latitude']].round(5).duplicated()].copy()
x,y=T.transform(cand.longitude.values,cand.latitude.values); cand['x_5070']=x; cand['y_5070']=y
cand=thin(cand,30.0,SEED)
ev=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in REG],ignore_index=True)
ex,ey=T.transform(ev.longitude.values,ev.latitude.values)
d,_=cKDTree(np.column_stack([ex,ey])).query(cand[['x_5070','y_5070']].values,k=1)
cand=cand[d>300].copy().reset_index(drop=True)
cand['b']=gid(cand.x_5070.values,cand.y_5070.values)
def hsplit(b): return 'val' if int(hashlib.md5(f"{SEED}:{b}".encode()).hexdigest(),16)%10000<blockvf*10000 else 'train'
cand['split']=[tab.get(b) or hsplit(b) for b in cand.b]
print(f"candidate pool after pooled hygiene/thin/buffer: {len(cand)}  {cand.state.value_counts().to_dict()}")

rng=np.random.default_rng(SEED)
def draw(bias):
    out=[]
    for r in REG:
        for sp in ('train','val'):
            need=int(((pos.state==r).values & (psp==sp)).sum())
            pool=cand[(cand.state==r)&(cand.split==sp)]
            if bias:   # southern half of the state's candidates only
                cut=np.median(cand.loc[cand.state==r,'y_5070'])
                pool=pool[pool.y_5070<=cut]
            take=pool if len(pool)<=need else pool.loc[rng.choice(pool.index.values,need,replace=False)]
            out.append(take.assign(split=sp))
    return pd.concat(out,ignore_index=True)

def audit(label,neg):
    print(f"\n########## {label} ##########")
    rec=pd.concat([pd.DataFrame({'x':pos.x_5070.values,'y':pos.y_5070.values,'lon':pos.longitude.values,
                                 'lat':pos.latitude.values,'st':pos.state.values,'s':psp,'c':'pos'}),
                   pd.DataFrame({'x':neg.x_5070.values,'y':neg.y_5070.values,'lon':neg.longitude.values,
                                 'lat':neg.latitude.values,'st':neg.state.values,'s':neg.split.values,'c':'neg'})],
                  ignore_index=True)
    rec['gb']=gid(rec.x.values,rec.y.values)
    # I1
    print(f"  I1  pooled positive pairs <30 m ............. {len(cKDTree(pos[['x_5070','y_5070']].values).query_pairs(30.0,output_type='ndarray'))}  req 0")
    # I2 / I3 recomputed geometrically
    g=rec.groupby('gb')['s'].nunique()
    print(f"  I2  blocks w/ train AND val (RECOMPUTED) .... {(g>1).sum()}  req 0")
    trg=set(rec.loc[rec.s=='train','gb']); vn=rec[(rec.s=='val')&(rec.c=='neg')]
    print(f"  I3  val negs in a train block (RECOMPUTED) .. {100*vn.gb.isin(trg).mean():.2f}%  req 0%")
    # I4 / (b)
    for c in ('pos','neg'):
        s=rec[rec.c==c]
        ktr=set(map(tuple,np.round(s.loc[s.s=='train',['lon','lat']].values,5)))
        n=sum(1 for k in map(tuple,np.round(s.loc[s.s=='val',['lon','lat']].values,5)) if k in ktr)
        print(f"  I4/(b) [{c}] 5dp coord in both splits ...... {n}  req 0")
    # I6 / I7 / I8
    print(f"  I6  pooled positive count .................. {len(pos)}  req 6230 +/-2% [6105,6355]")
    for c,lbl in ((('pos'),'pos'),(('neg'),'neg')):
        s=rec[rec.c==c]; print(f"  I7  val fraction [{lbl}] ................... {100*(s.s=='val').mean():.2f}%  req 20+/-1pp")
    nvp=int(((rec.c=='pos')&(rec.s=='val')).sum()); nvn=int(((rec.c=='neg')&(rec.s=='val')).sum())
    print(f"  I8  val neg:pos ............................ {nvn/max(nvp,1):.3f}  req 1.000 +/-0.02")
    # (a)
    bad_a=int((rec.st.isin(REG)==False).sum())
    print(f"  (a) partition state==region ................ {bad_a} violations  req 0")
    # (d) state histograms per region, BOTH readings
    gp=gpd.GeoDataFrame(rec,geometry=gpd.points_from_xy(rec.lon,rec.lat),crs="EPSG:4326")
    j=gpd.sjoin(gp,POLY,how="left",predicate="within"); j=j[~j.index.duplicated()]
    worst_col=worst_poly=0.0
    for r in REG:
        sub=j[j.st==r]
        for key,nm in (('st','state column'),('ST','polygon')):
            a=sub[sub.c=='pos'][key].value_counts(normalize=True)
            b=sub[sub.c=='neg'][key].value_counts(normalize=True)
            ks=set(a.index)|set(b.index)
            diff=max(abs(a.get(k,0)-b.get(k,0)) for k in ks)*100
            if nm=='state column': worst_col=max(worst_col,diff)
            else: worst_poly=max(worst_poly,diff)
    print(f"  (d) worst per-region state-histogram gap ... state-col {worst_col:.3f} pp | polygon {worst_poly:.3f} pp  req <=0.5 pp")
    # THE THING NOTHING CHECKS: within-state spatial support
    KB=30000.0
    def blk(x,yv): return set(zip(np.floor(x/KB).astype(int),np.floor(yv/KB).astype(int)))
    print("  --- within-state spatial support (NOT in CR-0007's acceptance set) ---")
    for r in REG:
        P=blk(rec[(rec.c=='pos')&(rec.st==r)].x.values,rec[(rec.c=='pos')&(rec.st==r)].y.values)
        N=blk(rec[(rec.c=='neg')&(rec.st==r)].x.values,rec[(rec.c=='neg')&(rec.st==r)].y.values)
        print(f"      {r}: 30 km pos-only/union = {len(P-N)}/{len(P|N)} = {len(P-N)/len(P|N):.4f}"
              f"   jaccard {len(P&N)/len(P|N):.4f}"
              f"   mean pos y {rec[(rec.c=='pos')&(rec.st==r)].y.mean():.0f} vs neg y {rec[(rec.c=='neg')&(rec.st==r)].y.mean():.0f}")

audit("FAIR negative draw (CR-0007 as intended)", draw(False))
audit("ATTACK: negatives drawn ONLY from the southern half of each state", draw(True))
