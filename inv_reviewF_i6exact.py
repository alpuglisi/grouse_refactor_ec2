import pandas as pd, numpy as np
import prepare_training_data as P
R=["ME","NH","VT"]
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R}
allrows=pd.concat(ev.values(),ignore_index=True)
# I6's literal recipe: "habitat rows whose filing region equals their state,
# deduped on (lon,lat,year), then one pooled MIN_SPACING_M thin"
hab=allrows[~allrows['nonveg_landcover'].astype(bool)]
own=hab[hab.state==hab._reg]
print("habitat rows with region==state:",len(own))
ded=own.drop_duplicates(subset=['longitude','latitude','year'])
print("  deduped on (lon,lat,year):",len(ded))
ded2=own.drop_duplicates(subset=['longitude','latitude'])
print("  deduped on (lon,lat):",len(ded2))
for nm,d in [("(lon,lat,year)",ded),("(lon,lat)",ded2)]:
    for sp in (30,60,65,70):
        t=P.thin_by_min_distance(d,sp,42)
        band = 6230*0.98, 6230*1.02
        print(f"  {nm} thin {sp}m -> {len(t)}  {'INSIDE' if band[0]<=len(t)<=band[1] else 'outside'} I6 band [{band[0]:.0f},{band[1]:.0f}]")
# Impact bullet's chain
habpool=allrows[~allrows['nonveg_landcover'].astype(bool)]
print("\nImpact bullet chain: pooled habitat rows",len(habpool),
      "-> unique coords",habpool.drop_duplicates(subset=['longitude','latitude']).shape[0],
      "-> pooled 30m thin", len(P.thin_by_min_distance(habpool.drop_duplicates(subset=['longitude','latitude']),30,42)))
