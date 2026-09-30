import pandas as pd, numpy as np
R=["ME","NH","VT"]
c=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
print("rows",len(c))
for dp in (4,5,6,7):
    k=c[['longitude','latitude']].round(dp)
    print(f" pooled unique at {dp}dp:",int((~k.duplicated()).sum()))
k=c[['longitude','latitude']].round(5)
print(" pooled unique 5dp incl state:",int((~c[['longitude','latitude','state']].assign(longitude=c.longitude.round(5),latitude=c.latitude.round(5)).duplicated()).sum()))
c2=c[~(c['coord_uncertainty_m']>1000).fillna(False)]
for dp in (5,):
    k=c2[['longitude','latitude']].round(dp); print(" after uncert, pooled unique 5dp:",int((~k.duplicated()).sum()))
# per-region dedup sum (already 35678). try dedup without fillna(False) semantics
s=0
for r in R:
    d=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    d=d[~(d['coord_uncertainty_m']>1000)]      # NaN -> dropped
    k=d[['longitude','latitude']].round(5); s+=int((~k.duplicated()).sum())
print(" per-region dedup with NaN-dropped uncert:",s)
s=0
for r in R:
    d=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    k=d[['longitude','latitude']].round(5); s+=int((~k.duplicated()).sum())
print(" per-region dedup, no uncert filter:",s)
s=0
for r in R:
    d=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    s+=len(d.drop_duplicates(subset=['longitude','latitude']))
print(" per-region raw-value dedup:",s)
