import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer
REG=["ME","NH","VT"]

# ---- 1. pooled NEGATIVE pairs < 30 m (no invariant covers this) ----
neg = pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv").assign(region=r) for r in REG],
                ignore_index=True)
print("pooled selected negatives:", len(neg), neg.region.value_counts().to_dict())
t=cKDTree(neg[["x_5070","y_5070"]].values)
p=t.query_pairs(30.0, output_type='ndarray')
d=np.linalg.norm(neg[["x_5070","y_5070"]].values[p[:,0]]-neg[["x_5070","y_5070"]].values[p[:,1]],axis=1)
rg=neg.region.values
print(f"NEG pooled pairs <30m: {len(p)}  (d==0: {(d==0).sum()}, 0<d<30: {((d>0)&(d<30)).sum()})")
print("   cross-region:", (rg[p[:,0]]!=rg[p[:,1]]).sum(), " same-region:", (rg[p[:,0]]==rg[p[:,1]]).sum())
if len(p): 
    print("   split pairs (train/val mix):", (neg.split.values[p[:,0]]!=neg.split.values[p[:,1]]).sum())
print("   state col of negatives:", neg.state.value_counts().to_dict())

# ---- 2. pooled negative CANDIDATE overlap between region files ----
for r in REG:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    print(f"gbif_negatives_{r}: {len(c)} rows, state col: {c['state'].value_counts().to_dict() if 'state' in c else 'n/a'}")

# ---- 3. state column of positives: what values exist ----
for r in REG:
    e=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    print(f"evaluated_{r}: {len(e)}  states={e['state'].value_counts().to_dict()}")

# ---- 4. NH box problem: state==NH records outside NH box ----
BOXES={"ME":(-71.158,42.889,-66.852,47.555),"NH":(-72.626,42.605,-70.600,45.398),
       "VT":(-73.510,42.632,-71.422,45.112)}
allpos = pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],
                   ignore_index=True)
uniq = allpos.drop_duplicates(subset=["longitude","latitude","year"])
for st in REG:
    s=uniq[uniq.state==st]
    b=BOXES[st]
    out=s[(s.longitude<b[0])|(s.longitude>b[2])|(s.latitude<b[1])|(s.latitude>b[3])]
    print(f"state=={st}: {len(s)} unique(lon,lat,year) records; OUTSIDE {st} box: {len(out)}")
    if len(out): print(out[["longitude","latitude","year","src"]].head(10).to_string())
    print(f"   lon range {s.longitude.min():.5f}..{s.longitude.max():.5f}  lat {s.latitude.min():.5f}..{s.latitude.max():.5f}")
