"""Will the EXISTING GBIF negative candidate pools still supply a 1:1
negative set after the state partition redistributes positives?  Read-only."""
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from prepare_training_data import thin_by_min_distance
R=["ME","NH","VT"]; t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)

ev = pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r)
                for r in R], ignore_index=True)
ev["key"]=ev.longitude.round(5).astype(str)+","+ev.latitude.round(5).astype(str)
print("evaluated rows pooled:", len(ev), " unique coords:", ev.key.nunique())
print("\ncurrent per-region-file counts (habitat only):")
hab = ev[~ev.nonveg_landcover.astype(bool)]
print(hab.groupby("src").size().to_string())
print("\npost-partition habitat counts, flag from the record's OWN state file:")
own = hab[hab.src == hab.state].drop_duplicates("key")
print(own.groupby("state").size().to_string(), " total", len(own))

# pooled 30 m thin, one draw (what S3 specifies)
own = own.copy()
own["x_5070"], own["y_5070"] = t.transform(own.longitude.values, own.latitude.values)
thin = thin_by_min_distance(own, 30, 42)
print("\nafter pooled 30 m thin:", len(thin))
print(thin.groupby("state").size().to_string())

print("\n--- negative candidate supply vs 1:1 need ---")
for r in R:
    c = pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    n0=len(c)
    c = c[~(c.coord_uncertainty_m>1000).fillna(False)]
    c = c.loc[~c[['longitude','latitude']].round(5).duplicated()]
    c = c.copy(); c["x_5070"],c["y_5070"]=t.transform(c.longitude.values,c.latitude.values)
    c = thin_by_min_distance(c,30,42)
    # 300 m buffer against POOLED grouse locations (S5 requires pooled)
    px,py = t.transform(ev.longitude.values, ev.latitude.values)
    d,_ = cKDTree(np.column_stack([px,py])).query(c[['x_5070','y_5070']].values,k=1)
    surv = int((d>300).sum())
    need = int((thin.state==r).sum())
    print(f"  {r}: raw {n0:6,} -> after hygiene/thin {len(c):6,} -> after pooled 300 m buffer {surv:6,}"
          f"   | 1:1 need after partition = {need:5,}  headroom x{surv/max(need,1):.2f}")

# --- per-region validation fraction under ONE GLOBAL draw (S3) --------------
print("\n--- per-region val fraction under one pooled block draw (origin 0,0) ---")
BLK=3000; VF=0.2
for seed in (42,1,7,2024):
    a=thin.copy()
    a["blk"]=(np.floor(a.x_5070/BLK).astype(int).astype(str)+"_"+
              np.floor(a.y_5070/BLK).astype(int).astype(str))
    cnt=a.blk.value_counts()
    order=cnt.sample(frac=1,random_state=seed).index.tolist()
    tgt,vb,run=int(round(VF*len(a))),set(),0
    for b in order:
        if run>=tgt: break
        vb.add(b); run+=cnt[b]
    a["split"]=np.where(a.blk.isin(vb),"val","train")
    g=a.groupby("state").split.apply(lambda s:(s=="val").mean())
    print(f"  seed {seed}: global {100*(a.split=='val').mean():.1f}%  " +
          "  ".join(f"{k} {100*v:.1f}%" for k,v in g.items()))
