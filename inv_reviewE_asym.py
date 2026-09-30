"""Live, NON-geographic per-class dataset-defining filters — evidence for
PA-0020's broadening, replacing the withdrawn coord_uncertainty_m example.
Read-only."""
import pandas as pd, numpy as np, glob, os
R=["ME","NH","VT"]

# --- 1. year support asymmetry ----------------------------------------------
pos=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv",
               usecols=["year","state"]).assign(src=r) for r in R],ignore_index=True)
neg=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv",
               usecols=["year","state"]).assign(src=r) for r in R],ignore_index=True)
print("=== selected TRAINING records, year support by class ===")
print("positives:", dict(sorted(pos.year.value_counts().items())))
print("negatives:", dict(sorted(neg.year.value_counts().items())))
pre=(pos.year<2020).sum()
print(f"\npositives before 2020: {pre} of {len(pos)} ({100*pre/len(pos):.1f}%)")
print(f"negatives before 2020: {(neg.year<2020).sum()} of {len(neg)}")

# --- 2. required-feature asymmetry ------------------------------------------
from analyze_grouse import ENVELOPE_SCHEME, REQUIRED_FEATURES, sample_raster, RASTER_DIR
feats_needed=sorted({c for c,_ in ENVELOPE_SCHEME if c not in ("evt_phys","evt_group")}|{"sclass","evt"})
print(f"\n=== required-feature sets ===")
print(f"positives REQUIRED_FEATURES : {REQUIRED_FEATURES}")
print(f"negatives feats_needed      : {feats_needed}")
only_pos=sorted(set(REQUIRED_FEATURES)-set(feats_needed))
print(f"required of POSITIVES only  : {only_pos}")

# how many selected negatives would a positives-grade filter drop?
from grouse_data import GrouseData
data=GrouseData()
tot=0; drop=0
for r in R:
    d=pd.read_csv(f"data/negatives/negatives_{r}.csv",
                  usecols=["longitude","latitude","year"])
    rd=data[r]; bad=np.zeros(len(d),bool)
    for f in only_pos:
        vals=np.full(len(d),np.nan)
        for y in sorted(d.year.dropna().unique()):
            m=(d.year==y).values
            try: tif=rd.raster_path(f,int(y))
            except Exception: continue
            vals[m]=sample_raster(tif,d.loc[m,"longitude"].values,d.loc[m,"latitude"].values)
        bad|=~np.isfinite(vals)
    tot+=len(d); drop+=int(bad.sum())
    print(f"  {r}: {int(bad.sum())} of {len(d)} selected negatives nodata in {only_pos}")
print(f"  TOTAL: {drop} of {tot} ({100*drop/max(tot,1):.2f}%)")
