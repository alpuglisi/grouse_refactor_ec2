"""check_partition.py on synthetic fixtures (CR-0007 test plan).

A correct partition passes P1-P5 and P8. Each wrong construction the
round-8 reviewers named fails the check that exists to catch it.

The correct outputs are built here independently of check_partition.py:
raster values come from the analytic functions the rasters were written
from, the collapse uses pandas' groupby/idxmax (as analyze_grouse does),
and the KDE uses sklearn's KernelDensity (the checker uses its own numpy
sum). Run with: python -m unittest tests.test_check_partition
"""
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import check_partition as cp  # noqa: E402

REGIONS = ("ME", "NH")
BOXES = {"ME": (-70.6, 44.0, -69.0, 45.0), "NH": (-71.6, 44.0, -70.2, 45.0)}
POLY = {"NH": (-71.5, 44.02, -70.4, 44.98), "ME": (-70.4, 44.02, -69.1, 44.98)}
FIPS = {"ME": "23", "NH": "33"}
BG_N = 40
BW = 3000
MIN_STRATUM = 3
NODATA = -9999
# raster grid (EPSG:4326)
W0, N0, RES, WIDTH, HEIGHT = -71.7, 45.1, 0.01, 290, 120
NODATA_PATCH = (-69.55, 44.45, -69.45, 44.55)
NONVEG_PATCH = (-69.85, 44.05, -69.75, 44.25)
PHYS = {7001: "Conifer", 7002: "Hardwood"}
NONVEG_SCLASS = 120


def evt_at(lon, lat):
    return np.where(np.asarray(lon) < -70.0, 7001, 7002).astype(float)


def _inside(lon, lat, b):
    lon, lat = np.asarray(lon), np.asarray(lat)
    return (lon > b[0]) & (lon < b[2]) & (lat > b[1]) & (lat < b[3])


def sclass_at(lon, lat):
    v = np.ones(len(np.atleast_1d(lon)))
    v[_inside(lon, lat, NONVEG_PATCH)] = NONVEG_SCLASS
    v[_inside(lon, lat, NODATA_PATCH)] = np.nan
    return v


def write_rasters(root):
    import rasterio
    from rasterio.transform import from_origin
    d = os.path.join(root, "data", "landfire")
    os.makedirs(os.path.join(d, "attribute_tables"))
    cols = W0 + (np.arange(WIDTH) + 0.5) * RES
    rows = N0 - (np.arange(HEIGHT) + 0.5) * RES
    lon, lat = np.meshgrid(cols, rows)
    evt = evt_at(lon.ravel(), lat.ravel()).reshape(lon.shape)
    sc = sclass_at(lon.ravel(), lat.ravel()).reshape(lon.shape)
    sc = np.where(np.isnan(sc), NODATA, sc)
    prof = dict(driver="GTiff", height=HEIGHT, width=WIDTH, count=1,
                dtype="int16", crs="EPSG:4326", nodata=NODATA,
                transform=from_origin(W0, N0, RES, RES))
    for r in REGIONS:
        for feat, arr in (("evt", evt), ("sclass", sc)):
            with rasterio.open(os.path.join(d, f"{r}_2020_{feat}.tif"), "w", **prof) as f:
                f.write(arr.astype("int16"), 1)
    pd.DataFrame({"VALUE": list(PHYS), "EVT_PHYS": list(PHYS.values())}).to_csv(
        os.path.join(d, "attribute_tables", "LF2020_EVT.csv"), index=False)


def write_polygons(root):
    import geopandas as gpd
    from shapely.geometry import box
    d = os.path.join(root, "data", "roads")
    os.makedirs(d)
    gpd.GeoDataFrame({"STATEFP": [FIPS[r] for r in POLY]},
                     geometry=[box(*POLY[r]) for r in POLY],
                     crs="EPSG:4269").to_file(os.path.join(d, "counties_2023.gpkg"))


def raw_points():
    rng = np.random.default_rng(7)

    def cl(state, year, lon, lat, n, s=0.02):
        return [(state, year, lon + rng.uniform(-s, s), lat + rng.uniform(-s, s))
                for _ in range(n)]
    pts = []
    pts += cl("ME", 2020, -70.33, 44.50, 8)      # border cluster, Conifer
    pts += cl("ME", 2020, -69.30, 44.70, 6)      # interior, Hardwood
    pts += cl("ME", 2020, -69.80, 44.15, 3, 0.01)  # non-vegetated patch
    pts += [("ME", 2020, -69.503, 44.502)]        # sclass nodata -> dropped
    pts += cl("NH", 2020, -70.47, 44.50, 8)      # border cluster, Conifer
    pts += cl("NH", 2020, -71.20, 44.60, 5)      # interior, Conifer
    dup = pts[0]
    pts += [("ME", 2019, dup[2], dup[3])]         # repeat visit, older year
    return pd.DataFrame(pts, columns=["state", "year", "lon", "lat"]).round(6)


def write_sightings(root, raw):
    d = os.path.join(root, "data", "sightings")
    os.makedirs(d)
    for (st, yr), g in raw.groupby(["state", "year"]):
        pd.DataFrame({"gbifID": range(len(g)), "decimalLatitude": g["lat"].values,
                      "decimalLongitude": g["lon"].values}).to_csv(
            os.path.join(d, f"{st.lower()}_sightings_{yr}.csv"), index=False)


def write_stubs(root):
    with open(os.path.join(root, "regions.py"), "w") as f:
        f.write(f"REGIONS = {REGIONS!r}\nSTATE_FIPS = {FIPS!r}\n"
                f"COUNTY_POLYGONS_YEAR = 2023\nBOXES = {BOXES!r}\n")
    with open(os.path.join(root, "analyze_grouse.py"), "w") as f:
        f.write(f"BACKGROUND_N = {BG_N}\nREQUIRED_FEATURES = ['evt', 'sclass']\n"
                f"COORD_ROUND_DECIMALS = 5\nKDE_MODE = 'stratified'\n"
                f"STRATIFY_BY = 'evt_phys'\nMIN_STRATUM_FOR_KDE = {MIN_STRATUM}\n"
                f"KDE_BANDWIDTH_M = {{'ME': {BW}, 'NH': {BW}}}\n"
                f"RASTER_DIR = 'data/landfire'\n")
    tpl = {"sightings": "data/sightings/{state_lower}_sightings_{year}.csv",
           "evaluated": "data/pipeline/evaluated_sightings_{region}.csv",
           "envelope_metrics": "data/pipeline/envelope_metrics_{region}.csv",
           "nonveg_flagged": "data/pipeline/nonveg_flagged_{region}.csv",
           "availability_sample": "data/pipeline/availability_sample_{region}.csv",
           "tiger_county": "data/roads/counties_{year}.gpkg"}
    with open(os.path.join(root, "grouse_data.py"), "w") as f:
        f.write(f"NODATA_SENTINELS = ({NODATA},)\nPATH_TEMPLATES = {tpl!r}\n")


# ---------------------------------------------------------------------------
# the correct pipeline, built independently of check_partition.py
# ---------------------------------------------------------------------------
def to_albers(lon, lat):
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    return t.transform(np.asarray(lon), np.asarray(lat))


def box_source(raw, region):
    b = BOXES[region]
    s = raw[raw["lon"].between(b[0], b[2]) & raw["lat"].between(b[1], b[3])]
    s = s.reset_index(drop=True)
    key = s["lon"].round(5).astype(str) + "," + s["lat"].round(5).astype(str)
    s = s.loc[s.assign(k=key).groupby("k")["year"].idxmax()].copy()
    s["evt"] = evt_at(s["lon"], s["lat"])
    s["sclass"] = sclass_at(s["lon"].values, s["lat"].values)
    s = s.dropna(subset=["evt", "sclass"]).copy()
    s["evt_phys"] = s["evt"].astype(int).map(PHYS)
    s["nonveg_landcover"] = s["sclass"] == NONVEG_SCLASS
    s["x_5070"], s["y_5070"] = to_albers(s["lon"], s["lat"])
    return s.rename(columns={"lon": "longitude", "lat": "latitude"})


def sk_kde(frame):
    """analyze_grouse.kde_stratified semantics, with sklearn."""
    from sklearn.neighbors import KernelDensity
    d = pd.Series(np.nan, index=frame.index)
    z = pd.Series("Moderate Density (10-90%)", index=frame.index)
    for _, g in frame.groupby("evt_phys"):
        if len(g) < MIN_STRATUM:
            continue
        X = g[["x_5070", "y_5070"]].values
        v = np.exp(KernelDensity(bandwidth=BW, kernel="gaussian").fit(X).score_samples(X))
        d[g.index] = v
        p10, p90 = np.percentile(v, 10), np.percentile(v, 90)
        z[g.index[v <= p10]] = "Coldest 10%"
        z[g.index[v >= p90]] = "Hotspot 10%"
    return d, z


def envelope(frame):
    return ("EVT_PHYS:" + frame["evt_phys"].astype(str) + "|SCLASS:"
            + frame["sclass"].astype(int).astype(str))


def availability(region, seed, in_state=True, n=BG_N):
    rng = np.random.default_rng(seed)
    b = BOXES[region]
    lon, lat = [], []
    while len(lon) < n:
        x, y = rng.uniform(b[0], b[2]), rng.uniform(b[1], b[3])
        if in_state and not _inside([x], [y], POLY[region])[0]:
            continue
        lon.append(round(x, 6))
        lat.append(round(y, 6))
    a = pd.DataFrame({"longitude": lon, "latitude": lat})
    sc = sclass_at(a["longitude"].values, a["latitude"].values)
    a["used"] = ~np.isnan(sc) & (sc != NONVEG_SCLASS)
    fr = pd.DataFrame({"evt_phys": pd.Series(evt_at(a["longitude"], a["latitude"])
                                             ).astype(int).map(PHYS),
                       "sclass": np.nan_to_num(sc)})
    a["envelope_id"] = np.where(a["used"], envelope(fr), None)
    return a


def metrics(sight_ids, avail):
    s = sight_ids.value_counts()
    a = avail.loc[avail["used"], "envelope_id"].value_counts()
    env = sorted(set(s.index) | set(a.index))
    return pd.DataFrame({"Envelope": env,
                         "Sightings": [int(s.get(e, 0)) for e in env],
                         "Avail_N": [int(a.get(e, 0)) for e in env]})


def correct_outputs(raw, restrict_kde=False):
    out = {}
    for r in REGIONS:
        src = box_source(raw, r)
        own = src[src["state"] == r].copy()
        kde_on = own if restrict_kde else src
        d, z = sk_kde(kde_on)
        own["spatial_density"], own["spatial_zone"] = d[own.index], z[own.index]
        own["region"] = r
        own["envelope_id"] = np.where(~own["nonveg_landcover"], envelope(own), None)
        av = availability(r, seed=11)
        out[r] = {"evaluated": own, "src": src, "availability_sample": av,
                  "envelope_metrics": metrics(
                      own.loc[~own["nonveg_landcover"], "envelope_id"], av)}
        out[r]["nonveg_flagged"] = own[own["nonveg_landcover"]]
    return out


def write_outputs(root, outs):
    d = os.path.join(root, "data", "pipeline")
    os.makedirs(d, exist_ok=True)
    for r, o in outs.items():
        for name in ("evaluated", "nonveg_flagged", "envelope_metrics",
                     "availability_sample"):
            if name in o and o[name] is not None:
                fn = {"evaluated": f"evaluated_sightings_{r}.csv"}.get(
                    name, f"{name}_{r}.csv")
                o[name].to_csv(
                    os.path.join(d, fn), index=False)


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp()
        write_stubs(cls.base)
        write_rasters(cls.base)
        write_polygons(cls.base)
        cls.raw = raw_points()
        write_sightings(cls.base, cls.raw)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base)

    def root_with(self, outs):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        shutil.copytree(self.base, d, dirs_exist_ok=True)
        write_outputs(d, outs)
        return d

    def run_checks(self, outs, only=("P1", "P2", "P3", "P4", "P5", "P8")):
        lines = []
        root = self.root_with(outs)
        res = cp.run(root, root, only=list(only), out=lines.append)
        return res, "\n".join(lines)

    def assertFails(self, res, text, *ids):
        for i in ids:
            self.assertFalse(res[i], f"{i} should fail\n{text}")

    def assertPasses(self, res, text, *ids):
        for i in ids:
            self.assertTrue(res[i], f"{i} should pass\n{text}")


class CorrectPartition(Fixture):
    def test_correct_partition_passes(self):
        res, text = self.run_checks(correct_outputs(self.raw))
        self.assertPasses(res, text, "P1", "P2", "P3", "P4", "P5", "P8")

    def test_fixture_exercises_the_edge_cases(self):
        outs = correct_outputs(self.raw)
        # foreign records are in each KDE source, and the nodata record is not
        for r in REGIONS:
            self.assertGreater(int((outs[r]["src"]["state"] != r).sum()), 0)
        self.assertEqual(len(outs["ME"]["evaluated"]), 17)   # 18 keys, 1 nodata
        self.assertGreater(int(outs["ME"]["evaluated"]["nonveg_landcover"].sum()), 0)


class WrongConstructions(Fixture):
    def box_frames(self, overwrite_state=False, region_col=True):
        outs = correct_outputs(self.raw)
        for r in REGIONS:
            src = outs[r]["src"].copy()
            d, z = sk_kde(src)
            src["spatial_density"], src["spatial_zone"] = d, z
            src["envelope_id"] = np.where(~src["nonveg_landcover"], envelope(src), None)
            if overwrite_state:
                src["state"] = r
            if region_col:
                src["region"] = r
            outs[r]["evaluated"] = src
            outs[r]["nonveg_flagged"] = src[src["nonveg_landcover"]]
            outs[r]["envelope_metrics"] = metrics(
                src.loc[~src["nonveg_landcover"], "envelope_id"],
                outs[r]["availability_sample"])
        return outs

    def test_no_op(self):
        res, text = self.run_checks(self.box_frames(region_col=False))
        self.assertFails(res, text, "P1", "P2", "P3")

    def test_box_membership(self):
        res, text = self.run_checks(self.box_frames())
        self.assertFails(res, text, "P1", "P2", "P3")

    def test_box_membership_state_overwritten(self):
        res, text = self.run_checks(self.box_frames(overwrite_state=True))
        self.assertPasses(res, text, "P1")
        self.assertFails(res, text, "P2", "P3")

    def test_dropped_record(self):
        outs = correct_outputs(self.raw)
        ev = outs["ME"]["evaluated"]
        ev = ev.drop(ev.index[~ev["nonveg_landcover"]][0])
        outs["ME"]["evaluated"] = ev
        outs["ME"]["envelope_metrics"] = metrics(
            ev.loc[~ev["nonveg_landcover"], "envelope_id"],
            outs["ME"]["availability_sample"])
        res, text = self.run_checks(outs)
        self.assertFails(res, text, "P3")
        self.assertPasses(res, text, "P1", "P2", "P5", "P8")

    def test_avail_from_box_draw_while_file_holds_in_state_draw(self):
        outs = correct_outputs(self.raw)
        for r in REGIONS:
            box_draw = availability(r, seed=99, in_state=False)
            ev = outs[r]["evaluated"]
            outs[r]["envelope_metrics"] = metrics(
                ev.loc[~ev["nonveg_landcover"], "envelope_id"], box_draw)
        res, text = self.run_checks(outs)
        self.assertFails(res, text, "P5")
        # P5b prints on every run; pin the failure to a nonzero mismatch.
        self.assertRegex(text, r"P5b: .* [1-9]\d* envelopes whose Avail_N")

    def test_sightings_from_box_habitat(self):
        outs = correct_outputs(self.raw)
        for r in REGIONS:
            src = outs[r]["src"]
            hab = src[~src["nonveg_landcover"]]
            outs[r]["envelope_metrics"] = metrics(envelope(hab),
                                                  outs[r]["availability_sample"])
        res, text = self.run_checks(outs)
        self.assertFails(res, text, "P5")
        self.assertRegex(text, r"P5c: [1-9]")

    def test_availability_file_post_filter(self):
        outs = correct_outputs(self.raw)
        for r in REGIONS:
            av = outs[r]["availability_sample"]
            outs[r]["availability_sample"] = av[av["used"]]
        res, text = self.run_checks(outs)
        self.assertFails(res, text, "P5")

    def test_availability_drawn_over_box(self):
        outs = correct_outputs(self.raw)
        for r in REGIONS:
            av = availability(r, seed=5, in_state=False)
            ev = outs[r]["evaluated"]
            outs[r]["availability_sample"] = av
            outs[r]["envelope_metrics"] = metrics(
                ev.loc[~ev["nonveg_landcover"], "envelope_id"], av)
        res, text = self.run_checks(outs)
        self.assertFails(res, text, "P5")
        self.assertRegex(text, r"outside \w\w polygon [1-9]")

    def test_kde_restricted_to_own_state(self):
        res, text = self.run_checks(correct_outputs(self.raw, restrict_kde=True))
        self.assertFails(res, text, "P8")
        self.assertPasses(res, text, "P1", "P2", "P3", "P5")

    def test_record_filed_under_wrong_state(self):
        raw = self.raw.copy()
        raw.loc[len(raw)] = ["ME", 2020, -71.0, 44.6]   # ME file, NH polygon
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        shutil.copytree(self.base, d, dirs_exist_ok=True)
        shutil.rmtree(os.path.join(d, "data", "sightings"))
        write_sightings(d, raw)
        lines = []
        res = cp.run(d, d, only=["P4"], out=lines.append)
        self.assertFalse(res["P4"], "\n".join(lines))


class GuardDetection(unittest.TestCase):
    def check(self, text):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "m.py")
        with open(p, "w") as f:
            f.write(text)
        return cp.guard_first(p)

    def test_guard_first_statement(self):
        self.assertTrue(self.check('"""doc"""\nraise SystemExit("stale (BUG-0031)")\nimport os\n'))
        self.assertTrue(self.check('raise SystemExit("stale (BUG-0031)")\n'))

    def test_guard_not_first(self):
        self.assertFalse(self.check('import os\nraise SystemExit("x")\n'))
        self.assertFalse(self.check('if __name__ == "__main__":\n    raise SystemExit("x")\n'))
        self.assertFalse(self.check('"""doc"""\nimport os\n'))


if __name__ == "__main__":
    unittest.main()
