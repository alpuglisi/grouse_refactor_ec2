"""CR-0006 review, part 4 (read-only): if positives become state-only but
analyze_grouse's envelope AVAILABILITY sample stays box-wide
(background_envelope_sample: rng.uniform over BOXES[region]), how much of
that availability sample is outside the state whose records it is
compared against?"""
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import Point
from regions import BOXES
from analyze_grouse import BACKGROUND_N
FIPS = {"23": "ME", "33": "NH", "50": "VT"}
cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
st = (cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index()
      .to_crs("EPSG:4326"))
st["ST"] = st.STATEFP.map(FIPS)
print(f"BACKGROUND_N = {BACKGROUND_N} uniform points per region box")
for r in ("ME", "NH", "VT"):
    lo, la, hi, ha = BOXES[r]
    rng = np.random.default_rng(1)
    lons = rng.uniform(lo, hi, BACKGROUND_N)
    lats = rng.uniform(la, ha, BACKGROUND_N)
    g = gpd.GeoDataFrame(geometry=[Point(a, b) for a, b in zip(lons, lats)],
                         crs="EPSG:4326")
    j = gpd.sjoin(g, st[["ST", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    own = (j.ST == r).mean()
    other = j.ST.notna().mean() - own
    print(f"  {r}: {own:6.1%} of the availability sample is inside {r}, "
          f"{other:6.1%} in another study state, "
          f"{1-own-other:6.1%} outside all three (Canada/ocean/NY/MA/QC)")
