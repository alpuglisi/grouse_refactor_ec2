"""Re-measure CR-0007's 'today' column from the shipped CSVs."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
P={r:pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in ("ME","NH","VT")}
TR={r:pd.read_csv(f"data/pipeline/train_positives_{r}.csv") for r in ("ME","NH","VT")}
VA={r:pd.read_csv(f"data/pipeline/val_positives_{r}.csv") for r in ("ME","NH","VT")}
TN={r:pd.read_csv(f"data/negatives/train_negatives_{r}.csv") for r in ("ME","NH","VT")}
VN={r:pd.read_csv(f"data/negatives/val_negatives_{r}.csv") for r in ("ME","NH","VT")}
for r in ("ME","NH","VT"):
    print(f"{r}: thinned {len(P[r])}  train {len(TR[r])} val {len(VA[r])}  "
          f"neg train {len(TN[r])} val {len(VN[r])}   out-of-state pos "
          f"{int((P[r].state!=r).sum())}   out-of-state neg {int((TN[r].state!=r).sum())+int((VN[r].state!=r).sum())}")
pos=pd.concat(P.values(),ignore_index=True)
print("\npooled thinned positives:",len(pos))
# I1
xy=pos[["x_5070","y_5070"]].values
print("I1 pooled 30 m pairs:",len(cKDTree(xy).query_pairs(30.0)),"  (CR: 1690)")
# I4
trp=pd.concat(TR.values(),ignore_index=True); vap=pd.concat(VA.values(),ignore_index=True)
trn=pd.concat(TN.values(),ignore_index=True); van=pd.concat(VN.values(),ignore_index=True)
k=lambda d:set(map(tuple,d[["longitude","latitude"]].round(5).values))
print(f"I4 pos train/val 5dp overlap: {len(k(trp)&k(vap))}  (CR: 522)   "
      f"neg: {len(k(trn)&k(van))}  (CR: 0)")
print(f"   val positives total {len(vap)}  (CR: 1,674) -> "
      f"{100*len(k(trp)&k(vap))/len(vap):.1f}%")
# I2/I3 with GLOBAL origin recompute
def bid(d,B=3000.0):
    return pd.Series([f"{a}_{b}" for a,b in zip(np.floor(d.x_5070.values/B).astype(int),
                                                np.floor(d.y_5070.values/B).astype(int))])
allrec=pd.concat([trp.assign(sp="train",cl="pos"),vap.assign(sp="val",cl="pos"),
                  trn.assign(sp="train",cl="neg"),van.assign(sp="val",cl="neg")],ignore_index=True)
allrec["gb"]=bid(allrec)
g=allrec.groupby("gb").sp.nunique()
print(f"I2 blocks holding both train and val (recomputed, global origin): "
      f"{int((g>1).sum())}  (CR: 882)")
both=set(g[g>1].index)
vn=allrec[(allrec.cl=='neg')&(allrec.sp=='val')]
print(f"I3 share of val negatives whose block holds any train record: "
      f"{100*vn.gb.isin(both).mean():.1f}%  (CR: 37.2%)")
# I10 per-region 30 km occupied-block pos-only fraction
for r in ("ME","NH","VT"):
    p=P[r]; n=pd.concat([TN[r],VN[r]],ignore_index=True)
    B=30000.0
    pb=set(zip(np.floor(p.x_5070/B).astype(int),np.floor(p.y_5070/B).astype(int)))
    nb=set(zip(np.floor(n.x_5070/B).astype(int),np.floor(n.y_5070/B).astype(int)))
    print(f"I10 {r}: pos-occupied 30 km blocks {len(pb)}, with no negative "
          f"{len(pb-nb)} -> {len(pb-nb)/len(pb):.4f}  "
          f"(CR: ME 0.0484 NH 0.3220 VT 0.2500)")
# candidate pool size
C=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
print(f"\nraw candidate rows pooled: {len(C)}")
c=C[~(C.coord_uncertainty_m>1000).fillna(False)]
c=c.loc[~c[['longitude','latitude']].round(5).duplicated()]
print(f"after hygiene + 5dp dedup: {len(c)}  (CR v2 said 35,792; correction says 35,678)")
print(f"coord_uncertainty_m all-null? {C.coord_uncertainty_m.isna().all()}  n={len(C)}")
