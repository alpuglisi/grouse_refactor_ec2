import sys, os, numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2"); os.chdir("/home/ec2-user/grouse2")
from grouse_data import GrouseData
from analyze_grouse import sample_raster
OUT = "/tmp/claude-1000/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/scratchpad/cr0007_A"
F9 = ['ch', 'cc', 'tcc', 'road_dist', 'tsd', 'balive', 'tpa_live', 'qmd', 'carbon_dwn']
P = pd.read_csv(f"{OUT}/pool_prebuffer.csv", low_memory=False)
d = GrouseData(); out = []
for r in ['ME', 'NH', 'VT']:
    sub = P[P.state == r].copy(); rd = d[r]
    for f in F9:
        v = np.full(len(sub), np.nan)
        for y in sorted(sub.year.dropna().unique()):
            m = (sub.year == y).values
            v[m] = sample_raster(rd.raster_path(f, int(y), validate=False), sub.loc[m, 'longitude'].values, sub.loc[m, 'latitude'].values)
        sub[f] = v
    out.append(sub)
P = pd.concat(out, ignore_index=True)
print(P[F9].isna().mean().round(4).to_dict())
P.to_csv(f"{OUT}/pool_prebuffer_f9.csv", index=False)
