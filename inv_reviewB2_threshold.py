"""Round-2 review: what does v2's 5-percentage-point class-composition
assertion actually do? Read-only."""
import pandas as pd, numpy as np
R=["ME","NH","VT"]
pos={}; neg={}
for r in R:
    pos[r]=pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv") for s in ("train","val")],ignore_index=True)
    neg[r]=pd.concat([pd.read_csv(f"data/negatives/{s}_negatives_{r}.csv") for s in ("train","val")],ignore_index=True)
print("=== vocabulary of the 'state' column in each class ===")
for r in R:
    print(f"  {r}: positives {pos[r].state.value_counts().to_dict()}")
    print(f"      negatives {neg[r].state.value_counts(dropna=False).to_dict()}")

def shares(d, col):
    v=d[col].value_counts(normalize=True)
    return {k:100*v.get(k,0.0) for k in R}

print("\n=== READING 1: pooled share BY REGION-OF-ORIGIN (which file) ===")
P=pd.concat([pos[r].assign(region=r) for r in R],ignore_index=True)
N=pd.concat([neg[r].assign(region=r) for r in R],ignore_index=True)
sp,sn=shares(P,'region'),shares(N,'region')
print("  CURRENT pos",{k:round(v,1) for k,v in sp.items()},"neg",{k:round(v,1) for k,v in sn.items()})
print(f"  max |delta| = {max(abs(sp[k]-sn[k]) for k in R):.2f} pp   -> "
      f"{'FAILS' if max(abs(sp[k]-sn[k]) for k in R)>5 else 'PASSES'} at 5 pp")

print("\n=== READING 2: pooled share BY THE RECORD'S OWN state COLUMN ===")
sp,sn=shares(P,'state'),shares(N,'state')
print("  CURRENT pos",{k:round(v,1) for k,v in sp.items()},"neg",{k:round(v,1) for k,v in sn.items()})
d=max(abs(sp[k]-sn[k]) for k in R)
print(f"  max |delta| = {d:.2f} pp   -> {'FAILS' if d>5 else 'PASSES'} at 5 pp")

print("\n=== READING 3: PER REGION, the two classes' state distributions ===")
worst=0
for r in R:
    a,b=shares(pos[r],'state'),shares(neg[r],'state')
    dd=max(abs(a[k]-b[k]) for k in R); worst=max(worst,dd)
    print(f"  {r}: pos {{'ME':{a['ME']:.1f},'NH':{a['NH']:.1f},'VT':{a['VT']:.1f}}} "
          f"neg {{'ME':{b['ME']:.1f},'NH':{b['NH']:.1f},'VT':{b['VT']:.1f}}} "
          f"max|delta| {dd:.1f} pp -> {'FAILS' if dd>5 else 'PASSES'}")
print(f"  worst over regions: {worst:.1f} pp")
print("\n  POST-FIX (partition => every positive's state == its region):")
for r in R:
    b=shares(neg[r],'state')
    a={k:(100.0 if k==r else 0.0) for k in R}
    dd=max(abs(a[k]-b[k]) for k in R)
    print(f"  {r}: pos own-state 100.0 vs neg own-state {b[r]:.2f} "
          f"-> max|delta| {dd:.2f} pp -> {'FAILS' if dd>5 else 'PASSES'}")
print("\n=== single-region run (--regions ME): readings 1 and 2 ===")
for label,col in (("region-of-origin","region"),("state column","state")):
    a=shares(pos['ME'].assign(region='ME'),col); b=shares(neg['ME'].assign(region='ME'),col)
    d=max(abs(a[k]-b[k]) for k in R)
    print(f"  {label}: max|delta| CURRENT {d:.2f} pp -> {'FAILS' if d>5 else 'PASSES'}")
