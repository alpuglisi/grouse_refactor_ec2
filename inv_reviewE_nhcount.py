import pandas as pd, numpy as np
from pyproj import Transformer
from prepare_training_data import thin_by_min_distance
R=["ME","NH","VT"]; t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
ev=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in R],ignore_index=True)
ev["key"]=ev.longitude.round(5).astype(str)+","+ev.latitude.round(5).astype(str)
th=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(src=r) for r in R],ignore_index=True)
th["key"]=th.longitude.round(5).astype(str)+","+th.latitude.round(5).astype(str)
print("CURRENT thinned_positives rows per region file:"); print(th.groupby("src").size().to_string())
print("\nstate-column composition of each region file (thinned):")
print(th.groupby(["src","state"]).size().unstack(fill_value=0).to_string())
hab=ev[~ev.nonveg_landcover.astype(bool)]
own=hab[hab.src==hab.state].drop_duplicates("key").copy()
# any state==X record that appears only in a FOREIGN file?
miss=hab[~hab.key.isin(own.key)].drop_duplicates("key")
print(f"\nhabitat coords present ONLY in a foreign region's file: {len(miss)}",
      dict(miss.state.value_counts()) if len(miss) else {})
own["x_5070"],own["y_5070"]=t.transform(own.longitude.values,own.latitude.values)
thin=thin_by_min_distance(own,30,42)
print("\nPOST-PARTITION (own-state habitat flag), before pooled thin:")
print(own.groupby("state").size().to_string(), " total", len(own))
print("after ONE pooled 30 m thin:")
print(thin.groupby("state").size().to_string(), " total", len(thin))
print("\nNH: thinned_positives_NH today = %d  ->  post-partition = %d  (%.1f%% of today)"
      % ((th.src=="NH").sum(), (thin.state=="NH").sum(),
         100*(thin.state=="NH").sum()/(th.src=="NH").sum()))
