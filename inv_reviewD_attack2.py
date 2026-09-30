"""Reviewer D: (1) a more plausible variant of the same break -- two different
global origins in the two scripts; (2) independent check of CR §6(c)'s numbers."""
import numpy as np, pandas as pd, hashlib
from pyproj import Transformer
from scipy.spatial import cKDTree
REG=["ME","NH","VT"]; BS=3000.0; VF=0.2; SEED=42
BOXES={"ME":(-71.158,42.889,-66.852,47.555),"NH":(-72.626,42.605,-70.600,45.398),
       "VT":(-73.510,42.632,-71.422,45.112)}

allpos=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allpos[~allpos['nonveg_landcover'].astype(bool)]
own=hab[hab.state==hab.src].drop_duplicates(subset=["longitude","latitude","year"]).reset_index(drop=True)
def thin(df,m,seed):
    rng=np.random.default_rng(seed); o=rng.permutation(len(df))
    c=df[['x_5070','y_5070']].values[o]; keep=np.zeros(len(df),bool); kept=[]; t=None
    for i,pt in enumerate(c):
        if t is None or t.query(pt,k=1)[0]>=m: kept.append(pt); keep[o[i]]=True; t=cKDTree(np.array(kept))
    return df[keep].copy()
pos=thin(own,30.0,SEED)
negsrc=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in REG],ignore_index=True)

def ids_at(df,ox,oy):
    bx=np.floor((df.x_5070.values-ox)/BS).astype(int); by=np.floor((df.y_5070.values-oy)/BS).astype(int)
    return pd.Series([f"{a}_{b}" for a,b in zip(bx,by)],index=df.index)
def assign(df,ids):
    cnt=ids.value_counts(); shuf=cnt.sample(frac=1,random_state=SEED).index.tolist()
    tgt=int(round(VF*len(df))); val=set(); run=0
    for b in shuf:
        if run>=tgt: break
        val.add(b); run+=cnt[b]
    return ids.map(lambda b:'val' if b in val else 'train')

def evaluate(label, pos_ox,pos_oy, neg_ox,neg_oy):
    pid=ids_at(pos,pos_ox,pos_oy); psp=assign(pos,pid)
    table=dict(zip(pid,psp)); vf=(psp=='val').mean()
    n=negsrc.copy(); nid=ids_at(n,neg_ox,neg_oy)
    def h(b): return 'val' if int(hashlib.md5(f"{SEED}:{b}".encode()).hexdigest(),16)%10000<vf*10000 else 'train'
    n['block_id']=nid.values
    n['split']=[table.get(b) or h(b) for b in nid]
    hit=sum(1 for b in nid if b in table)
    rec=pd.concat([pd.DataFrame({'x':pos.x_5070,'y':pos.y_5070,'b':pid,'s':psp,'c':'pos'}),
                   pd.DataFrame({'x':n.x_5070,'y':n.y_5070,'b':n.block_id,'s':n.split,'c':'neg'})],ignore_index=True)
    rec['gb']=[f"{a}_{b}" for a,b in zip(np.floor(rec.x/BS).astype(int),np.floor(rec.y/BS).astype(int))]
    g=rec.groupby('b')['s'].nunique(); g2=rec.groupby('gb')['s'].nunique()
    vn=rec[(rec.s=='val')&(rec.c=='neg')]
    trb=set(rec.loc[rec.s=='train','b']); trg=set(rec.loc[rec.s=='train','gb'])
    xy=pos[['x_5070','y_5070']].values; t=cKDTree(xy)
    i4={}
    for c in ('pos','neg'):
        s=rec[rec.c==c]
        ktr=set(map(tuple,np.round(s.loc[s.s=='train',['x','y']].values,3)))
        kva=list(map(tuple,np.round(s.loc[s.s=='val',['x','y']].values,3)))
        i4[c]=sum(1 for k in kva if k in ktr)
    print(f"\n### {label}")
    print(f"  negative block ids found in the positive table: {hit}/{len(nid)} ({100*hit/len(nid):.1f}%)")
    print(f"  I1 pooled pos pairs<30m .............. {len(t.query_pairs(30.0,output_type='ndarray'))}   require 0")
    print(f"  I2 (block_id COLUMN) ................. {(g>1).sum()}   require 0")
    print(f"  I3 (block_id COLUMN) ................. {100*vn.b.isin(trb).mean():.2f}%   require 0%")
    print(f"  I4 pos/neg ........................... {i4['pos']}/{i4['neg']}   require 0/0")
    print(f"  val fraction (pos) ................... {100*(psp=='val').mean():.2f}%")
    print(f"  --> I2' RECOMPUTED on one global grid  {(g2>1).sum()}")
    print(f"  --> I3' RECOMPUTED on one global grid  {100*vn.gb.isin(trg).mean():.2f}%")

evaluate("A  compliant: both scripts origin (0,0)", 0,0, 0,0)
evaluate("B  per-region origin in BOTH scripts (the '--global origin' line never landed)",
         None,None,None,None) if False else None
# B: per-region origins in both scripts
def evaluate_perregion():
    def pr(df):
        T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
        out=pd.Series(index=df.index,dtype=object)
        for r in REG:
            m=(df.state==r).values
            cx,cy=T.transform([BOXES[r][0],BOXES[r][2]],[BOXES[r][1],BOXES[r][3]])
            ox,oy=min(cx),min(cy)
            bx=np.floor((df.x_5070.values[m]-ox)/BS).astype(int); by=np.floor((df.y_5070.values[m]-oy)/BS).astype(int)
            out.loc[df.index[m]]=[f"{a}_{b}" for a,b in zip(bx,by)]
        return out
    pid=pr(pos); psp=assign(pos,pid); table=dict(zip(pid,psp)); vf=(psp=='val').mean()
    n=negsrc.copy(); nid=pr(n)
    def h(b): return 'val' if int(hashlib.md5(f"{SEED}:{b}".encode()).hexdigest(),16)%10000<vf*10000 else 'train'
    n['block_id']=nid.values; n['split']=[table.get(b) or h(b) for b in nid]
    rec=pd.concat([pd.DataFrame({'x':pos.x_5070,'y':pos.y_5070,'b':pid,'s':psp,'c':'pos'}),
                   pd.DataFrame({'x':n.x_5070,'y':n.y_5070,'b':n.block_id,'s':n.split,'c':'neg'})],ignore_index=True)
    rec['gb']=[f"{a}_{b}" for a,b in zip(np.floor(rec.x/BS).astype(int),np.floor(rec.y/BS).astype(int))]
    g=rec.groupby('b')['s'].nunique(); g2=rec.groupby('gb')['s'].nunique()
    vn=rec[(rec.s=='val')&(rec.c=='neg')]
    trb=set(rec.loc[rec.s=='train','b']); trg=set(rec.loc[rec.s=='train','gb'])
    print("\n### B  per-region origins in BOTH scripts (one pooled block table)")
    print(f"  I2 (COLUMN) {(g>1).sum()}   I3 (COLUMN) {100*vn.b.isin(trb).mean():.2f}%")
    print(f"  --> I2' GLOBAL {(g2>1).sum()}   I3' GLOBAL {100*vn.gb.isin(trg).mean():.2f}%")
evaluate_perregion()
# C: 1500 m offset between the two scripts' "global" origins
evaluate("C  positives origin (0,0), negatives origin (1500,1500)", 0,0, 1500,1500)
# D: positives (0,0), negatives use the union-of-boxes min corner
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
cx,cy=T.transform([-73.510,-66.852],[42.605,47.555]); ux,uy=min(cx),min(cy)
evaluate(f"D  positives (0,0), negatives union-box corner ({ux:.0f},{uy:.0f})", 0,0, ux,uy)

# ---------- CR 6(c): per-region occupied-block support, 30 km ----------
print("\n=== CR §6(c) per-region occupied-block support, 30 km, pos-only fraction ===")
KB=30000.0
def blk(x,y): return set(zip(np.floor(x/KB).astype(int),np.floor(y/KB).astype(int)))
print("BEFORE (current per-region files):")
for r in REG:
    p=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv"); q=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    P=blk(p.x_5070.values,p.y_5070.values); N=blk(q.x_5070.values,q.y_5070.values)
    print(f"  {r}: pos-only/union = {len(P-N)}/{len(P|N)} = {len(P-N)/len(P|N):.4f}   jaccard {len(P&N)/len(P|N):.4f}")
print("AFTER (state-partitioned positives, current negatives):")
for r in REG:
    p=pos[pos.state==r]; q=negsrc[negsrc.state==r]
    P=blk(p.x_5070.values,p.y_5070.values); N=blk(q.x_5070.values,q.y_5070.values)
    print(f"  {r}: pos-only/union = {len(P-N)}/{len(P|N)} = {len(P-N)/len(P|N):.4f}   jaccard {len(P&N)/len(P|N):.4f}")
print("POOLED (before / after):")
pb=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in REG]); nb=negsrc
for lbl,pp in (("before",pb),("after",pos)):
    P=blk(pp.x_5070.values,pp.y_5070.values); N=blk(nb.x_5070.values,nb.y_5070.values)
    print(f"  {lbl}: pos-only {len(P-N)/len(P|N):.4f}  jaccard {len(P&N)/len(P|N):.4f}")
