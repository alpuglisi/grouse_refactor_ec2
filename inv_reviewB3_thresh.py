"""Round-3: is v3's assertion (c) threshold 0.035 (per-region 30 km
pos-only fraction) robust to the fact that negatives are RE-SAMPLED at
every generate_negatives run? Read-only."""
import numpy as np, pandas as pd
from pyproj import Transformer
from prepare_training_data import thin_by_min_distance, MIN_SPACING_M_DEFAULT
R=["ME","NH","VT"]; t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
BS=30000
def blocks(d):
    x,y=t.transform(d.longitude.values,d.latitude.values)
    return set(f"{a}_{b}" for a,b in zip(np.floor(x/BS).astype(int),
                                         np.floor(y/BS).astype(int)))
print("=== CURRENT (defective) per-region 30 km pos-only fraction ===")
cur={}
for r in R:
    p=pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv") for s in ("train","val")],ignore_index=True)
    n=pd.concat([pd.read_csv(f"data/negatives/{s}_negatives_{r}.csv") for s in ("train","val")],ignore_index=True)
    sp,sn=blocks(p),blocks(n); cur[r]=len(sp-sn)/len(sp)
    print(f"  {r}: pos blocks {len(sp)} neg blocks {len(sn)} pos-only "
          f"{cur[r]:.4f}   (CR: defective ME = 0.048)")
print(f"  min before = {min(cur.values()):.4f}")

# ---- post-fix positives: partition + pooled thin + global grid ----------
ev=[]
for r in R:
    d=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv"); ev.append(d)
ev=pd.concat(ev,ignore_index=True)
ev["key"]=ev.longitude.round(5).astype(str)+","+ev.latitude.round(5).astype(str)
u=ev[~ev.nonveg_landcover.astype(bool)]; u=u.loc[~u.key.duplicated()].copy()
thp=thin_by_min_distance(u,MIN_SPACING_M_DEFAULT,42)
print("\n=== POST-FIX, with negatives RE-SAMPLED 40x at the new quotas ===")
rng=np.random.default_rng(0)
for r in R:
    pos=thp[thp.state==r]; sp=blocks(pos)
    cand=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    cand=cand[~(cand.coord_uncertainty_m>1000).fillna(False)]
    cand=cand.loc[~cand[["longitude","latitude"]].round(5).duplicated()]
    vals=[]
    for _ in range(40):
        take=cand.sample(n=min(len(pos),len(cand)),random_state=int(rng.integers(1e9)))
        sn=blocks(take); vals.append(len(sp-sn)/len(sp))
    v=np.array(vals)
    print(f"  {r}: pos {len(pos)} blocks {len(sp)} | quota {min(len(pos),len(cand))} "
          f"of {len(cand)} candidates | pos-only mean {v.mean():.4f} "
          f"sd {v.std():.4f} min {v.min():.4f} max {v.max():.4f}")
    print(f"      margin to the 0.035 gate: {(0.035-v.max())/max(v.std(),1e-9):.1f} sd")
