"""CR-0017 pre-registration (read-only; written before approval under
CLAUDE.md section 1 / CR-0011 A3). Computes, on today's accepted CR-0012
artifacts, which rows CR-0017's border rule must remove.

Rule (CR-0017 section 2): D = union of the TIGER COUNTY_POLYGONS_YEAR
county polygons whose STATEFP is in STATE_FIPS (the sightings' acquisition
domain), in EPSG:5070. A row is dropped iff its EPSG:5070 distance
(recomputed from lon/lat) to the complement of D is <= BUFFER_M.

Independent of generate_negatives.py and of regions' geometry helpers:
own transformer, own county read and dissolve. Constants and the county
path are read from regions.py / PATH_TEMPLATES (inputs, not logic).

For every row within 1 km, the nearest point of the complement is
classified: "CA/sea" if it lies in no US county of the national file,
else the US state it lies in (e.g. NY, MA) - within 1 m of the nearest
point, to allow for the boundary itself.

Also prints the smallest |d - BUFFER_M| over all rows (tie-risk margin),
and the count of interior rings of D (gaps that would read as outside).

Run from the repository root:
PYTHONPATH=. python docs/quality/evidence/CR-0017/preregister.py

Writes docs/quality/evidence/CR-0017/preregister_keys.csv: one row per
predicted removal (set C or N, region, split, is_nonveg, longitude,
latitude as written in the file, d_m, nearest_outside), read by
check_must_change.py.
"""
import hashlib
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from pyproj import Transformer
import regions as R
from grouse_data import PATH_TEMPLATES

CRS = "EPSG:5070"
county_path = PATH_TEMPLATES["tiger_county"].format(year=R.COUNTY_POLYGONS_YEAR)
T = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


codes = ",".join(f"'{v}'" for v in sorted(R.STATE_FIPS.values()))
dom = gpd.read_file(county_path, where=f"STATEFP IN ({codes})").to_crs(CRS)
D = shapely.union_all(dom.geometry.values)
polys = list(D.geoms) if D.geom_type == "MultiPolygon" else [D]
n_holes = sum(len(p.interiors) for p in polys)
fips2st = {"23": "ME", "33": "NH", "50": "VT", "36": "NY", "25": "MA"}

srcs = [("C", "data/negatives/candidate_pool.csv")] + \
       [(f"N_{r}", f"data/negatives/negatives_{r}.csv") for r in R.REGIONS]
print(f"county file {county_path} sha256 {sha(county_path)}")
print(f"domain D: STATEFP in {sorted(R.STATE_FIPS.values())}, {len(dom)} "
      f"counties, {len(polys)} polygon part(s), {n_holes} interior ring(s)")
print(f"BUFFER_M = {R.BUFFER_M}")

allpts = {}
for name, path in srcs:
    df = pd.read_csv(path, float_precision="round_trip")
    x, y = T.transform(df.longitude.to_numpy(float), df.latitude.to_numpy(float))
    pts = shapely.points(x, y)
    inside = shapely.contains(D, pts)
    d = shapely.distance(pts, D.boundary)
    d = np.where(inside, d, 0.0)       # outside D -> distance 0
    allpts[name] = (df, pts, d)

# national counties near any row within 1 km, for classification only
near_rows = [(n, i) for n, (df, pts, d) in allpts.items()
             for i in np.nonzero(d <= 1000)[0]]
lo = min(allpts[n][0].longitude.iloc[i] for n, i in near_rows) - 0.1
hi = max(allpts[n][0].longitude.iloc[i] for n, i in near_rows) + 0.1
la = min(allpts[n][0].latitude.iloc[i] for n, i in near_rows) - 0.1
ha = max(allpts[n][0].latitude.iloc[i] for n, i in near_rows) + 0.1
nat = gpd.read_file(county_path, bbox=(lo, la, hi, ha)).to_crs(CRS)
nat_other = nat[~nat.STATEFP.isin(list(R.STATE_FIPS.values()))]


def classify(pt):
    q = shapely.ops.nearest_points(pt, D.boundary)[1]
    disc = q.buffer(1.0)
    hit = nat_other[nat_other.intersects(disc)]
    if len(hit) == 0:
        return "CA/sea"
    return "/".join(sorted({fips2st.get(s, s) for s in hit.STATEFP}))


import shapely.ops  # noqa: E402

KEYS = "docs/quality/evidence/CR-0017/preregister_keys.csv"
rows = []
margin = min(float(np.min(np.abs(d - R.BUFFER_M))) for _, _, d in allpts.values())
print(f"min |d - BUFFER_M| over every row of C and N: {margin:.3f} m")
for name, path in srcs:
    df, pts, d = allpts[name]
    drop = d <= R.BUFFER_M
    cls = [classify(pts[i]) for i in np.nonzero(drop)[0]]
    by = pd.Series(cls, dtype=object).value_counts().to_dict() if cls else {}
    print(f"\n{name} ({path}, sha256 {sha(path)[:16]}...): rows {len(df):,}; "
          f"dropped (d <= {R.BUFFER_M} m) {int(drop.sum())} by nearest outside "
          f"{by}; <= 1 km {int((d <= 1000).sum())}")
    if name.startswith("N_"):
        sp = df.loc[drop, ["split", "is_nonveg"]].astype(str).agg("/".join, axis=1)
        print(f"   by split/is_nonveg: {sp.value_counts().to_dict()}")
    for i, c in zip(np.nonzero(drop)[0], cls):
        rows.append({"set": "C" if name == "C" else "N",
                     "region": df.region.iloc[i], "split": df["split"].iloc[i],
                     "is_nonveg": bool(df.is_nonveg.iloc[i]),
                     "longitude": repr(float(df.longitude.iloc[i])),
                     "latitude": repr(float(df.latitude.iloc[i])),
                     "d_m": round(float(d[i]), 3), "nearest_outside": c})
        print(f"   {df.longitude.iloc[i]:.6f},{df.latitude.iloc[i]:.6f} "
              f"{df.region.iloc[i]} {df['split'].iloc[i]} d={d[i]:.1f} m  {c}")

pd.DataFrame(rows).to_csv(KEYS, index=False)
print(f"\nwrote {KEYS}: {len(rows)} rows")
