import pandas as pd, numpy as np
R=["ME","NH","VT"]
for r in R:
    ev=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    hab=ev[~ev['nonveg_landcover'].astype(bool)]
    tp=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
    ke=set(zip(hab['longitude'].round(7),hab['latitude'].round(7)))
    kt=set(zip(tp['longitude'].round(7),tp['latitude'].round(7)))
    print(f"{r}: habitat rows {len(hab)} uniq {len(ke)} | thinned rows {len(tp)} uniq {len(kt)} | thinned coords NOT in habitat: {len(kt-ke)}")
    # also check against full eval (incl nonveg)
    ka=set(zip(ev['longitude'].round(7),ev['latitude'].round(7)))
    print(f"    thinned coords not in full evaluated_sightings: {len(kt-ka)}")
# state distribution of thinned per region
print()
tot={}
for r in R:
    tp=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
    vc=tp['state'].value_counts().to_dict()
    print(f"thinned_{r}: n={len(tp)} by state: {vc}")
pooled=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
print("\npooled thinned by state:", pooled['state'].value_counts().to_dict())
print("in-state per region (state==reg):", {r:int(((pooled._reg==r)&(pooled.state==r)).sum()) for r in R})
