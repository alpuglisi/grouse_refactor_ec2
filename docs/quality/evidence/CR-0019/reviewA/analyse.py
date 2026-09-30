"""Reviewer A (CR-0019): independent measurements on the live tree (OLD),
the pre-CR-0017 backup (the tree grouse_cr0009.pth trained on) and the
reviewer's own real-pipeline run with the floor (NEW; pipeline_floor_run.py).
Usage: PYTHONPATH=. python .../analyse.py NEW_ROOT"""
import io, contextlib, json, os, sys
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from grouse_data import GrouseData, DataConfig
import train as T
import generate_negatives as gn

NEW = os.path.abspath(sys.argv[1])
OLD = os.path.abspath(".")
BK = "/home/ec2-user/grouse_backup/CR-0017"
R = ("ME", "NH", "VT")
key = lambda d: set(zip(d.longitude.round(6), d.latitude.round(6)))

def load(root, kind, r):
    return pd.read_csv(os.path.join(root, f"data/{'pipeline' if 'positives' in kind else 'negatives'}/{kind}_{r}.csv"))

def summary(root, tag):
    data = GrouseData(DataConfig(base_dir=root))
    feats = T.discover_features(data, list(R))
    print(f"== {tag}: features {feats}")
    P = pd.concat([load(root, f"{s}_positives", r).assign(split=s, region=r) for r in R for s in ("train","val")])
    N = pd.concat([load(root, f"{s}_negatives", r).assign(split=s, region=r) for r in R for s in ("train","val")])
    for nm, d in (("P", P), ("N", N)):
        print(f"  {nm} n={len(d)} null years={d.year.isna().sum()} years={d.year.value_counts().sort_index().to_dict()} <2020={int((d.year<2020).sum())}")
    for tol in (2, 1, 0):
        kept = {}
        for nm, d in (("P", P), ("N", N)):
            k = 0; per = {}
            for r in R:
                for s in ("train","val"):
                    sub = d[(d.region==r)&(d.split==s)].drop(columns=["region"])
                    with contextlib.redirect_stdout(io.StringIO()):
                        out = T.filter_by_year_gap(sub, data[r], feats, tol, nm, r)
                    per[(r,s)] = len(out)
            kept[nm] = per
        dp = len(P) - sum(kept["P"].values()); dn = len(N) - sum(kept["N"].values())
        vp = sum(v for (r,s),v in kept["P"].items() if s=="val"); vn = sum(v for (r,s),v in kept["N"].items() if s=="val")
        tp = sum(v for (r,s),v in kept["P"].items() if s=="train"); tn = sum(v for (r,s),v in kept["N"].items() if s=="train")
        print(f"  tol {tol}: dropped P {dp}/{len(P)} N {dn}/{len(N)}; val prev {vp}/{vp+vn}={vp/(vp+vn):.4f}; train prev {tp}/{tp+tn}={tp/(tp+tn):.4f}")
        if tol == 2:
            print("   per (R,s) P kept:", kept["P"]); print("   per (R,s) N kept:", kept["N"])
    y = np.r_[np.ones(len(P)), np.zeros(len(N))]; yr = np.r_[P.year, N.year]
    m = yr >= 2020
    print(f"  year->label AUC all {roc_auc_score(y, yr):.4f}; year>=2020 {roc_auc_score(y[m], yr[m]):.4f}")
    return P, N

Po, No = summary(OLD, "OLD (live, CR-0017)")
Pn, Nn = summary(NEW, "NEW (reviewer pipeline run with floor)")
print("calibration.json val_prevalence", json.load(open("data/calibration/calibration.json"))["val_prevalence"])

# P set changes
ko, kn = key(Po), key(Pn)
print(f"P kept {len(ko&kn)}, removed {len(ko-kn)}, added {len(kn-ko)}")
rem = Po[[k in (ko-kn) for k in zip(Po.longitude.round(6), Po.latitude.round(6))]]
print("  removed years:", rem.year.value_counts().sort_index().to_dict())
add = Pn[[k in (kn-ko) for k in zip(Pn.longitude.round(6), Pn.latitude.round(6))]]
print("  added:", len(add), "years", add.year.value_counts().sort_index().to_dict(), "splits", add.split.value_counts().to_dict())
# were the added ones suppressed by pre-2020 neighbours? distance to nearest removed (old kept pre-2020) positive
import prepare_training_data as ptd
xa, ya = ptd.to_5070(add.longitude.values, add.latitude.values)
xr_, yr_ = ptd.to_5070(rem.longitude.values, rem.latitude.values)
from scipy.spatial import cKDTree
d, _ = cKDTree(np.c_[xr_, yr_]).query(np.c_[xa, ya])
from regions import MIN_SPACING_M
print(f"  added: nearest removed pre-2020 positive distance max {d.max():.1f} m (MIN_SPACING_M {MIN_SPACING_M}); all < spacing: {(d<MIN_SPACING_M).all()}")
# split moves of kept P
mo = Po.set_index([Po.longitude.round(6), Po.latitude.round(6)]).split
mn = Pn.set_index([Pn.longitude.round(6), Pn.latitude.round(6)]).split
common = mo.index.intersection(mn.index)
ch = pd.DataFrame({"o": mo.loc[common], "n": mn.loc[common]})
print("  kept P split moves:", ch[ch.o != ch.n].value_counts().to_dict())
# Blocks
Bo = pd.read_csv(os.path.join(OLD, "data/pipeline/block_assignments.csv")); Bn = pd.read_csv(os.path.join(NEW, "data/pipeline/block_assignments.csv"))
bo, bn = Bo.set_index("block_id").split, Bn.set_index("block_id").split
cb = bo.index.intersection(bn.index)
print(f"B {len(Bo)} -> {len(Bn)}; vanished {len(bo.index.difference(bn.index))}, new {len(bn.index.difference(bo.index))}, flips {pd.DataFrame({'o':bo[cb],'n':bn[cb]}).query('o!=n').value_counts().to_dict()}")
print(f"  val share of blocks old {(Bo.split=='val').mean():.6f} new {(Bn.split=='val').mean():.6f}; val P share old {(Po.split=='val').mean():.4f} new {(Pn.split=='val').mean():.4f}")
# Pool
Co = pd.read_csv(os.path.join(OLD, "data/negatives/candidate_pool.csv")); Cn = pd.read_csv(os.path.join(NEW, "data/negatives/candidate_pool.csv"))
same = (Co[["longitude","latitude"]].values == Cn[["longitude","latitude"]].values).all()
chg = Co.split.values != Cn.split.values
print(f"C rows {len(Co)} vs {len(Cn)}; same keys/order {same}; split changes {chg.sum()}: {pd.Series(list(zip(Co.split[chg], Cn.split[chg]))).value_counts().to_dict()}")
print("  C year range", Cn.year.min(), Cn.year.max())
# N set changes
kno, knn = key(No), key(Nn)
print(f"N kept {len(kno&knn)}, removed {len(kno-knn)}, added {len(knn-kno)}")
# leakage into new val
def trainset(root, kind):
    return key(pd.concat([pd.read_csv(os.path.join(root, f"data/{'pipeline' if 'positives' in kind else 'negatives'}/train_{kind}_{r}.csv")) for r in R]))
valN = key(Nn[Nn.split=="val"]); valP = key(Pn[Pn.split=="val"])
print(f"new val N ({len(valN)}) that are live(CR-0017) train N: {len(valN & trainset(OLD,'negatives'))}")
print(f"new val N that are pre-CR-0017 backup train N (grouse_cr0009.pth's actual training set): {len(valN & trainset(BK,'negatives'))}")
print(f"new val P ({len(valP)}) that are live train P: {len(valP & trainset(OLD,'positives'))}")
# spatial leak: new val rows in blocks that held OLD train positives (incl. pre-2020 ones the model trained on)
import regions
def blk(d):
    x, y = ptd.to_5070(d.longitude.values, d.latitude.values); return regions.block_ids(x, y)
old_train_pos_blocks = set(blk(Po[Po.split=="train"]))
nv = Nn[Nn.split=="val"]; pv = Pn[Pn.split=="val"]
print(f"new val N in blocks holding a live-train positive: {int(pd.Series(blk(nv)).isin(old_train_pos_blocks).sum())}; new val P in such blocks: {int(pd.Series(blk(pv)).isin(old_train_pos_blocks).sum())}")
# Option 1b shortfall, own computation on NEW pool
tot = 0; rows = []
for r in R:
    for s in ("train","val"):
        pos = Pn[(Pn.region==r)&(Pn.split==s)]
        pool = Cn[(Cn.region==r)&(Cn.split==s)]
        for yv in sorted(pos.year.unique()):
            n = int((pos.year==yv).sum()); n_nv = int(round(n*gn.NONVEG_MAX_FRAC)); sub = pool[pool.year==yv]
            nvs = int(sub.is_nonveg.astype(bool).sum()); hs = len(sub) - nvs
            n_nv = min(n_nv, nvs); short = max(0, (n - n_nv) - hs); tot += short
            if short: rows.append((r, s, int(yv), n, n - n_nv, hs, short))
print("1b shortfalls:", rows, "total", tot)
# coarser matching: per (region, split, year-bin) with 2023+2024 merged, and per (split, year) pooled over regions
for label, grp in (("per (R,s) 2023-24 merged", lambda y: np.minimum(y, 2023)),):
    tot2 = 0
    for r in R:
        for s in ("train","val"):
            pos = Pn[(Pn.region==r)&(Pn.split==s)]; pool = Cn[(Cn.region==r)&(Cn.split==s)]
            gp, gc = grp(pos.year.values), grp(pool.year.values)
            for yv in np.unique(gp):
                n = int((gp==yv).sum()); sub = pool[gc==yv]; nvs = int(sub.is_nonveg.astype(bool).sum())
                n_nv = min(int(round(n*gn.NONVEG_MAX_FRAC)), nvs); tot2 += max(0, (n-n_nv) - (len(sub)-nvs))
    print(f"  {label}: shortfall {tot2}")
