"""Verify v2's claim that filter_by_year_gap drops 22-24% of positives and 0% of
negatives (the justification for running both assertions BEFORE it)."""
import pandas as pd, numpy as np, glob, re, os
from models import FEATURE_SPEC
TOL=2
def raster_years(reg,feat):
    ys=[]
    for p in glob.glob(f"data/landfire/{reg}_*_{feat}.tif"):
        m=re.match(rf"^{reg}_(\d{{4}})_{feat}\.tif$",os.path.basename(p))
        if m: ys.append(int(m.group(1)))
    return sorted(ys)
feats=sorted(FEATURE_SPEC)
for reg in ["ME","NH","VT"]:
    yrs={f:raster_years(reg,f) for f in feats}
    yrs={f:v for f,v in yrs.items() if v}
    missing=[f for f in feats if f not in yrs]
    def ok(y):
        return all(min(abs(a-int(y)) for a in v)<=TOL for v in yrs.values())
    print(f"\n{reg}: features with rasters {len(yrs)}/{len(feats)}"+(f" (absent: {missing})" if missing else ""))
    print("   per-feature year sets:", {f:(min(v),max(v),len(v)) for f,v in list(yrs.items())})
    for kind,paths in (("pos",[f"data/pipeline/train_positives_{reg}.csv",f"data/pipeline/val_positives_{reg}.csv"]),
                       ("neg",[f"data/negatives/train_negatives_{reg}.csv",f"data/negatives/val_negatives_{reg}.csv"])):
        d=pd.concat([pd.read_csv(p) for p in paths],ignore_index=True)
        yv=d['year']
        keep=yv.map(lambda y: True if pd.isna(y) else ok(y))
        print(f"   {kind}: n={len(d)} dropped={int((~keep).sum())} ({100*(~keep).mean():.1f}%) "
              f"year range {int(yv.min())}-{int(yv.max())} | dropped years {sorted(set(yv[~keep].dropna().astype(int)))[:12]}")
