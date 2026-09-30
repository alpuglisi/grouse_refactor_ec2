"""Reviewer D: independent verification of CR-0006 v3's four acceptance numbers.
READ-ONLY. Writes nothing into data/."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree

REG = ["ME","NH","VT"]
BS = 3000.0

def load(tmpl, label):
    out=[]
    for r in REG:
        d = pd.read_csv(tmpl.format(r=r))
        d["region"]=r
        out.append(d)
    d = pd.concat(out, ignore_index=True)
    print(f"{label}: {len(d)} rows  ({ {r:int((d.region==r).sum()) for r in REG} })")
    return d

trp = load("data/pipeline/train_positives_{r}.csv","train pos")
vap = load("data/pipeline/val_positives_{r}.csv","val pos")
trn = load("data/negatives/train_negatives_{r}.csv","train neg")
van = load("data/negatives/val_negatives_{r}.csv","val neg")
thp = load("data/pipeline/thinned_positives_{r}.csv","thinned pos")

# ---------- I1: pooled positive pairs < 30 m ----------
def pairs_under(df, m=30.0):
    xy = df[["x_5070","y_5070"]].values
    t = cKDTree(xy)
    return t.query_pairs(m, output_type='ndarray')

for name, df in (("thinned (train+val union file)", thp),
                 ("train+val concat", pd.concat([trp,vap], ignore_index=True))):
    p = pairs_under(df)
    print(f"I1 [{name}] pooled positive pairs with dist < 30 m: {len(p)}")
    p2 = pairs_under(df, 30.0-1e-9)
    print(f"   strictly < 30m (eps): {len(p2)}")
    # exact-equal coordinate pairs among them
    xy = df[["x_5070","y_5070"]].values
    d = np.linalg.norm(xy[p[:,0]]-xy[p[:,1]], axis=1)
    print(f"   of which dist == 0: {(d==0).sum()};  0<d<30: {((d>0)&(d<30)).sum()}")
    # cross-region only?
    reg = df["region"].values
    print(f"   cross-region pairs: {(reg[p[:,0]]!=reg[p[:,1]]).sum()}; same-region: {(reg[p[:,0]]==reg[p[:,1]]).sum()}")

# ---------- global block id ----------
def gblock(df):
    return (np.floor(df["x_5070"].values/BS).astype(int).astype(str) + "_" +
            np.floor(df["y_5070"].values/BS).astype(int).astype(str))

allrec = pd.concat([
    trp.assign(cls="pos", split="train"), vap.assign(cls="pos", split="val"),
    trn.assign(cls="neg", split="train"), van.assign(cls="neg", split="val"),
], ignore_index=True)
allrec["gblock"] = gblock(allrec)
allrec["rblock"] = allrec["region"] + ":" + allrec["block_id"].astype(str)

# ---------- I2: blocks holding train AND val, either class ----------
for key in ("gblock","rblock","block_id"):
    g = allrec.groupby(key)["split"].nunique()
    print(f"I2 [{key}] blocks holding BOTH train and val (either class): {(g>1).sum()} of {len(g)} blocks")
    for c in ("pos","neg"):
        sub = allrec[allrec.cls==c]
        g2 = sub.groupby(key)["split"].nunique()
        print(f"     {c}-only: {(g2>1).sum()} of {len(g2)}")

# ---------- I3: val negatives sharing a block with train ----------
for key in ("gblock","rblock","block_id"):
    tr_any = set(allrec.loc[allrec.split=="train", key])
    tr_pos = set(allrec.loc[(allrec.split=="train")&(allrec.cls=="pos"), key])
    tr_neg = set(allrec.loc[(allrec.split=="train")&(allrec.cls=="neg"), key])
    vn = allrec[(allrec.split=="val")&(allrec.cls=="neg")]
    print(f"I3 [{key}] val negs in a block with ANY train record: "
          f"{100*vn[key].isin(tr_any).mean():.2f}%  "
          f"(train pos only {100*vn[key].isin(tr_pos).mean():.2f}%, "
          f"train neg only {100*vn[key].isin(tr_neg).mean():.2f}%)")
    vp = allrec[(allrec.split=="val")&(allrec.cls=="pos")]
    print(f"     val POS in a block with any train record: {100*vp[key].isin(tr_any).mean():.2f}%")

# ---------- I4: train/val coordinate collisions, per class ----------
for c,(tr,va) in (("pos",(trp,vap)), ("neg",(trn,van))):
    ktr = set(map(tuple, np.round(tr[["x_5070","y_5070"]].values,3)))
    kva = list(map(tuple, np.round(va[["x_5070","y_5070"]].values,3)))
    n = sum(1 for k in kva if k in ktr)
    print(f"I4 [{c}] val records at a coordinate also present in train: {n} of {len(kva)} "
          f"({100*n/len(kva):.1f}%)")
    # lon/lat rounded key as an alternative
    ktr2 = set(map(tuple, np.round(tr[["longitude","latitude"]].values,5)))
    kva2 = list(map(tuple, np.round(va[["longitude","latitude"]].values,5)))
    n2 = sum(1 for k in kva2 if k in ktr2)
    print(f"     lon/lat(5dp) key: {n2}")
