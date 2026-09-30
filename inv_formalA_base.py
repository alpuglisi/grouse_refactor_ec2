"""Formal review A: rebuild the CR-0007 post-partition record set from scratch
and re-measure I6, the BUG-0034 costs, and per-region composition."""
import pandas as pd, numpy as np
from scipy.spatial import cKDTree
import prepare_training_data as P

R=["ME","NH","VT"]
a=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r)
             for r in R], ignore_index=True)
print(f"pooled evaluated_sightings rows: {len(a)}")
hab=a[~a['nonveg_landcover'].astype(bool)]
print(f"  habitat (nonveg False): {len(hab)}")
own=hab[hab.state==hab._reg]
print(f"  own-state rows: {len(own)}")
for key in [['longitude','latitude'],['longitude','latitude','year']]:
    d=own.drop_duplicates(subset=key)
    th=P.thin_by_min_distance(d.reset_index(drop=True),30,42)
    print(f"  dedup on {key} -> {len(d)} rows -> pooled 30m thin -> {len(th)}"
          f"  {th.state.value_counts().reindex(R).to_dict()}")

print("\n=== I6 recipe as written in the table: 'habitat rows whose filing region equals their state, deduped on (lon,lat,year), then one pooled thin' ===")
d=own.drop_duplicates(subset=['longitude','latitude','year']).reset_index(drop=True)
th=P.thin_by_min_distance(d,30,42)
print(f"   -> {len(th)}   (CR: 6230 +/- 10)")
print(f"   today-column claim '8,365 rows': own-state deduped = {len(d)}  habitat-own = {len(own)}")

print("\n=== BUG-0034 / v5 decision: restrict positives to 2020+ AT SELECTION, on the POST-PARTITION pooled set ===")
d20=d[d.year>=2020].reset_index(drop=True)
th20=P.thin_by_min_distance(d20,30,42)
print(f"   2020+ own-state deduped rows: {len(d20)} of {len(d)}  (dropped {len(d)-len(d20)}, {100*(1-len(d20)/len(d)):.2f}%)")
print(f"   pooled 30m thin of 2020+  -> {len(th20)}   vs all-years {len(th)}   delta {len(th20)-len(th)}")
print(f"   per region: 2020+ {th20.state.value_counts().reindex(R).to_dict()}")
print(f"               allyr {th.state.value_counts().reindex(R).to_dict()}")
print("\n   pre-2020 share of the THINNED all-years pooled set:")
print(f"     {(th.year<2020).sum()} of {len(th)} = {100*(th.year<2020).mean():.2f}%")
print(f"     per region: " + str({r:int((th[th.state==r].year<2020).sum()) for r in R}))

print("\n=== seed spread of I6 (fair draw), all-years and 2020+ ===")
for tag,src in (("allyr",d),("2020+",d20)):
    v=[len(P.thin_by_min_distance(src,30,s)) for s in range(40,60)]
    print(f"   {tag}: min {min(v)} max {max(v)} mean {np.mean(v):.1f}  (20 seeds)")
