import pandas as pd, numpy as np
import prepare_training_data as P
R=["ME","NH","VT"]
allrows=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
own=allrows[(~allrows['nonveg_landcover'].astype(bool))&(allrows.state==allrows._reg)].drop_duplicates(subset=['longitude','latitude'])
lo,hi=6230*0.98,6230*1.02
for sp in (80,90,100,120,150,200,250):
    n=len(P.thin_by_min_distance(own,sp,42))
    print(f"  thin {sp:4}m -> {n}  {'INSIDE' if lo<=n<=hi else 'OUTSIDE'} band [{lo:.0f},{hi:.0f}]")
