"""CR-0015 V1-V3: independent re-check of assumed-negative background points
on real data, and the V3 calibration (deliverable 7a).

Independence (CR-0015 Acceptance V1; PA-0021(e)). Nothing here calls
regions.in_state, regions.to_5070, regions.block_ids or regions.block_split:
- in-state: its own polygon test (shapely.contains_xy on the dissolved TIGER
  county polygons of the region's STATEFP, re-typed below);
- blocks: its own EPSG:4326 -> EPSG:5070 transformer and floor formula
  (origin (0, 0), 3000 m, re-typed);
- split: the block's row in block_assignments.csv, else a re-typed md5 rule
  with vf = share of 'val' rows in that file.
The county file and block_assignments.csv are located through
grouse_data.PATH_TEMPLATES (PA-0003); the path is not part of the rule.

Run with cwd = a data root (a directory holding data/), e.g.
    python <repo>/tests/cr0015_background_check.py calibrate --seeds 100
writes the V3 calibration to docs/quality/cr0015_v3_calibration.json (in the
repository) and prints the fair and broken distributions.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

CALIBRATION_JSON = os.path.join(REPO, "docs", "quality",
                                "cr0015_v3_calibration.json")

# Re-typed on purpose (independence from regions.py).
FIPS = {"ME": "23", "NH": "33", "VT": "50"}
BLOCK_EDGE_M = 3000.0
MD5_SEED = 42
V_REGIONS = ("ME", "NH", "VT")
V_N = 5000                 # points per region (V1, V3)
REF_MIN_CENTRES = 100_000  # in-state reference centres per region (V3)
SENTINELS = (-9999.0, -32768.0, 32767.0, -1111.0)


class Checker:
    """Classifies lon/lat points: in-state, block id, block kind."""

    def __init__(self):
        import geopandas as gpd
        import shapely
        from pyproj import Transformer
        from grouse_data import PATH_TEMPLATES
        from regions import COUNTY_POLYGONS_YEAR
        self.shapely = shapely
        cpath = PATH_TEMPLATES["tiger_county"].format(year=COUNTY_POLYGONS_YEAR)
        apath = PATH_TEMPLATES["block_assignments"]
        for p in (cpath, apath):
            if not os.path.exists(p):
                raise FileNotFoundError(p)
        codes = ",".join(f"'{c}'" for c in sorted(FIPS.values()))
        cty = gpd.read_file(cpath, where=f"STATEFP IN ({codes})")
        if cty.crs is None:
            cty = cty.set_crs(4269)
        cty = cty.to_crs(4326)
        self.state_geom = {}
        for reg, fp in FIPS.items():
            g = shapely.union_all(cty.loc[cty["STATEFP"] == fp, "geometry"].values)
            shapely.prepare(g)
            self.state_geom[reg] = g
        self.tf = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
        a = pd.read_csv(apath, dtype={"block_id": str, "split": str})
        self.listed = dict(zip(a["block_id"], a["split"]))
        self.vf = float((a["split"] == "val").sum()) / float(len(a))

    def in_state(self, lon, lat, region):
        return self.shapely.contains_xy(self.state_geom[region],
                                        np.asarray(lon, float),
                                        np.asarray(lat, float))

    def block_ids(self, lon, lat):
        x, y = self.tf.transform(np.asarray(lon, float), np.asarray(lat, float))
        bx = np.floor(np.atleast_1d(x) / BLOCK_EDGE_M).astype(np.int64)
        by = np.floor(np.atleast_1d(y) / BLOCK_EDGE_M).astype(np.int64)
        return [f"{i}_{j}" for i, j in zip(bx.tolist(), by.tolist())]

    def md5_val(self, bid, frac=None):
        frac = self.vf if frac is None else frac
        h = int(hashlib.md5(f"{MD5_SEED}:{bid}".encode()).hexdigest(), 16)
        return (h % 10000) < frac * 10000

    def kinds(self, lon, lat):
        """Per point: 'listed-train', 'listed-val', 'unassigned-train' or
        'unassigned-val'."""
        out = []
        for b in self.block_ids(lon, lat):
            s = self.listed.get(b)
            if s is not None:
                out.append("listed-" + s)
            else:
                out.append("unassigned-" + ("val" if self.md5_val(b) else "train"))
        return np.array(out, dtype=object)


def v1_counts(chk, df, region):
    lon, lat = df["longitude"].to_numpy(), df["latitude"].to_numpy()
    ins = chk.in_state(lon, lat, region)
    k = chk.kinds(lon, lat)
    val = np.isin(k, ["listed-val", "unassigned-val"])
    return {"n": int(len(df)), "out_of_state": int((~ins).sum()),
            "val_block": int(val.sum()),
            "val_block_listed": int((k == "listed-val").sum()),
            "val_block_unassigned": int((k == "unassigned-val").sum())}


def v3_share(chk, df):
    """Share of the points in unassigned-train blocks."""
    k = chk.kinds(df["longitude"].to_numpy(), df["latitude"].to_numpy())
    return float((k == "unassigned-train").mean())


def reference_share(chk, path, region):
    """Independent pixel-centre enumeration of the first-feature raster at a
    fixed stride giving >= REF_MIN_CENTRES in-state centres. Returns the
    unassigned-train share of the valid, in-state, train-block centres."""
    import rasterio
    from pyproj import Transformer
    with rasterio.open(path) as src:
        H, W = src.height, src.width
        stride = max(1, int(math.sqrt(H * W / (4.0 * REF_MIN_CENTRES))))
        while True:
            rows = np.arange(stride // 2, H, stride)
            cols = np.arange(stride // 2, W, stride)
            vals = np.empty((len(rows), len(cols)), dtype=np.float64)
            for i, r in enumerate(rows):
                line = src.read(1, window=((int(r), int(r) + 1), (0, W)))[0]
                vals[i] = line[cols]
            rr, cc = np.meshgrid(rows, cols, indexing="ij")
            a = src.transform
            x = a.c + a.a * (cc + 0.5) + a.b * (rr + 0.5)
            y = a.f + a.d * (cc + 0.5) + a.e * (rr + 0.5)
            to_ll = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
            lon, lat = to_ll.transform(x.ravel(), y.ravel())
            lon, lat = np.asarray(lon), np.asarray(lat)
            v = vals.ravel()
            valid = np.isfinite(v) & ~np.isin(v, SENTINELS)
            if src.nodata is not None:
                valid &= v != float(src.nodata)
            ins = chk.in_state(lon, lat, region)
            n_in = int(ins.sum())
            if n_in >= REF_MIN_CENTRES or stride == 1:
                break
            stride = max(1, stride // 2)
    sel = valid & ins
    k = chk.kinds(lon[sel], lat[sel])
    train = np.isin(k, ["listed-train", "unassigned-train"])
    share = float((k[train] == "unassigned-train").mean())
    return {"stride": int(stride), "centres": int(len(v)),
            "in_state_centres": n_in, "subset_centres": int(train.sum()),
            "share": share}


def real_inputs():
    """(GrouseData, features, assignments) for the cwd data root."""
    from grouse_data import GrouseData
    import train
    data = GrouseData()
    feats = train.discover_features(data, list(V_REGIONS))
    return data, feats, data.block_assignments


def draw(sampler, data, feats, assignments, region, seed, n=V_N):
    return sampler(data[region], feats, n, seed=seed, region=region,
                   train_blocks_only=True, assignments=assignments)


def calibrate(seeds, out_path):
    import train
    import cr0015_wrong_samplers as W
    data, feats, assign = real_inputs()
    chk = Checker()
    res = {"n": V_N, "seeds": seeds, "features0": feats[0], "vf": chk.vf,
           "regions": {}}
    for region in V_REGIONS:
        path = data[region].latest_raster_path(feats[0])
        ref = reference_share(chk, path, region)
        t = time.time()
        fair = []
        for s in range(seeds):
            df = draw(train.sample_background_points, data, feats, assign,
                      region, s)
            fair.append(abs(v3_share(chk, df) - ref["share"]))
        broken = {}
        for name in ("todays_sampler", "unassigned_excluded",
                     "unassigned_train", "md5_fraction_018"):
            vals = []
            for s in range(5):
                df = draw(W.WRONG_SAMPLERS[name], data, feats, assign, region, s)
                vals.append(abs(v3_share(chk, df) - ref["share"]))
            broken[name] = vals
        fair = np.asarray(fair)
        bound = float(np.quantile(fair, 0.99))
        res["regions"][region] = {
            "raster": os.path.relpath(path), "reference": ref,
            "fair": {"p50": float(np.quantile(fair, 0.5)),
                     "p95": float(np.quantile(fair, 0.95)),
                     "p99": bound, "max": float(fair.max()),
                     "values": [round(float(v), 6) for v in fair]},
            "broken": {k: {"min": float(min(v)), "values": [round(float(x), 6) for x in v]}
                       for k, v in broken.items()},
            "separates": {k: bool(min(v) > bound) for k, v in broken.items()},
            "bound": bound, "seconds": round(time.time() - t, 1)}
        print(region, json.dumps({k: res["regions"][region][k]
                                  for k in ("reference", "bound", "separates")}),
              flush=True)
        for k, v in broken.items():
            print(f"   {region} {k}: min {min(v):.4f} vs fair p99 {bound:.4f}",
                  flush=True)
    sep = {k: all(r["separates"][k] for r in res["regions"].values())
           for k in ("todays_sampler", "unassigned_excluded",
                     "unassigned_train", "md5_fraction_018")}
    res["separates_all_regions"] = sep
    # CR-0015 PA-0021(c): the bound is the fair p99 per region; if it does
    # not separate every broken sampler, V3 is demoted to OBS.
    res["v3_status"] = "GATE" if all(sep.values()) else "OBS"
    res["rule"] = ("bound = per-region p99 of the fair sampler's statistic "
                   f"over {seeds} seeds; broken samplers over 5 seeds each; "
                   "'separates' = broken min > bound; GATE iff every broken "
                   "sampler separates in every region, else OBS")
    with open(out_path, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
        f.write("\n")
    print("separates (all regions):", sep)
    print("wrote", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["calibrate"])
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--out", default=CALIBRATION_JSON)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(REPO, "tests"))
    calibrate(a.seeds, a.out)


if __name__ == "__main__":
    main()
