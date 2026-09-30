"""Round-3: a record-weighted support statistic that is not quantised by
tiny block counts. Read-only."""
import numpy as np, pandas as pd
from pyproj import Transformer
from prepare_training_data import thin_by_min_distance, MIN_SPACING_M_DEFAULT
R=["ME","NH","VT"]; t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def ids(d,bs):
    x,y=t.transform(d.longitude.values,d.latitude.values)
    return np.array([f"{a}_{b}" for a,b in zip(np.floor(x/bs).astype(int),
                                               np.floor(y/bs).astype(int))])
def uncov(p,n,bs):   # share of POSITIVE RECORDS whose block holds no negative
    sn=set(ids(n,bs).tolist()); return float((~np.isin(ids(p,bs),list(sn))).mean())
print("statistic: share of POSITIVE RECORDS in a block with no negative")
for bs in (10000,30000):
    print(f"\n--- block size {bs} m ---")
    print("  CURRENT (defective):")
    for r in R:
        p=pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv") for s in ("train","val")],ignore_index=True)
        n=pd.concat([pd.read_csv(f"data/negatives/{s}_negatives_{r}.csv") for s in ("train","val")],ignore_index=True)
        print(f"    {r}: {uncov(p,n,bs):.4f}")
    ev=[pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in R]
    ev=pd.concat(ev,ignore_index=True)
    ev["key"]=ev.longitude.round(5).astype(str)+","+ev.latitude.round(5).astype(str)
    u=ev[~ev.nonveg_landcover.astype(bool)]; u=u.loc[~u.key.duplicated()].copy()
    thp=thin_by_min_distance(u,MIN_SPACING_M_DEFAULT,42)
    print("  POST-FIX (negatives re-sampled 40x):")
    rng=np.random.default_rng(0)
    for r in R:
        pos=thp[thp.state==r]
        cand=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
        cand=cand[~(cand.coord_uncertainty_m>1000).fillna(False)]
        cand=cand.loc[~cand[["longitude","latitude"]].round(5).duplicated()]
        v=np.array([uncov(pos,cand.sample(n=min(len(pos),len(cand)),
                    random_state=int(rng.integers(1e9))),bs) for _ in range(40)])
        print(f"    {r}: mean {v.mean():.4f} sd {v.std():.4f} max {v.max():.4f}")
