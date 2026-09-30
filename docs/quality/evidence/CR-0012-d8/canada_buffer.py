"""CR-0012 deliverable 8 / BUG-0050 evidence (read-only; provenance only).

Question (PA-0023 Swept? cell): does the negatives' 300 m exclusion buffer
(generate_negatives.py pool step 6) see sightings across the Canadian
border?

1. The buffer source is every row of every region's evaluated_sightings_R
   (generate_negatives.py:392-395). The raw sightings behind them are
   printed below by countryCode / stateProvince.
2. For every pool candidate and selected negative: its distance to the
   outer boundary of the union of TIGER 2023 counties of ME, NH, VT and
   their US land neighbours NY and MA. TIGER county polygons extend
   offshore, so an outer-boundary point near a record in these states is
   the international border. The nearest boundary point is printed in
   lon/lat so that each row can be checked by hand.

Run from the repository root:
PYTHONPATH=. python docs/quality/evidence/CR-0012-d8/canada_buffer.py
"""
import glob
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import nearest_points
from pyproj import Transformer
import regions as R
from grouse_data import PATH_TEMPLATES  # noqa: F401  (path layout reference)

NEIGHBOUR_FIPS = {"NY": "36", "MA": "25"}   # US land neighbours of ME/NH/VT
ANALYSIS_CRS = "EPSG:5070"                  # BUG-0047 (literal, deferred)

raw = pd.concat([pd.read_csv(f, usecols=["countryCode", "stateProvince"])
                 for f in sorted(glob.glob("data/sightings/*_sightings_*.csv"))],
                ignore_index=True)
print(f"raw sightings: {len(raw):,} rows; countryCode "
      f"{raw.countryCode.value_counts().to_dict()}; stateProvince "
      f"{raw.stateProvince.value_counts().to_dict()}")

fips = list(R.STATE_FIPS.values()) + list(NEIGHBOUR_FIPS.values())
cty = gpd.read_file(f"data/roads/tl_{R.COUNTY_POLYGONS_YEAR}_us_county.zip")
cty = cty[cty.STATEFP.isin(fips)].to_crs(ANALYSIS_CRS)
bnd = cty.union_all().boundary
inv = Transformer.from_crs(ANALYSIS_CRS, "EPSG:4326", always_xy=True)
srcs = [("candidate_pool", "data/negatives/candidate_pool.csv")] + \
       [(f"negatives_{r}", f"data/negatives/negatives_{r}.csv") for r in R.REGIONS]
for name, path in srcs:
    df = pd.read_csv(path)
    pts = gpd.GeoSeries(gpd.points_from_xy(df.x_5070, df.y_5070), crs=ANALYSIS_CRS)
    d = pts.distance(bnd).to_numpy()
    print(f"{name}: rows {len(df):,}; <= {R.BUFFER_M} m of the outer US "
          f"boundary: {(d <= R.BUFFER_M).sum()}; <= 1 km: {(d <= 1000).sum()}")
    for i in np.nonzero(d <= R.BUFFER_M)[0]:
        q = nearest_points(pts.iloc[i], bnd)[1]
        lo, la = inv.transform(q.x, q.y)
        print(f"   {df.longitude.iloc[i]:.5f},{df.latitude.iloc[i]:.5f} "
              f"{df.region.iloc[i]} {df['split'].iloc[i]} d={d[i]:.0f} m  "
              f"nearest boundary pt {lo:.4f},{la:.4f}")
