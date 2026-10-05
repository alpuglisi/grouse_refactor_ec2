"""CR-0032 v2: Meta 1 m canopy-structure layers (mch_*). Synthetic rasters
only; no Earth Engine, no data/ access.

Written before approval (CR-0011 A3) and reviewed with the CR. T1-T4 fail
until CR-0032 deliverable 2 lands; T5 tests the committed gate
(check_canopy_structure.py) and passes now.

Interface these tests pin (CR-0032 §3):
  models: MCH_BIN_EDGES_M = (1, 5, 12), MCH_MIN_VALID_FRAC = 0.5,
    MCH_HEIGHT_MAX_M = 60.0, mch_height_encode(m) -> int16 dm,
    mch_share_encode(fraction) -> int16 per mille (ValueError on
    NaN/inf/out of range).
  generate_canopy_structure: MCH_ASSET, MCH_FEATURES, STATIC_FEATURES,
    MCH_MAX_PIXELS, MCH_MAX_OVER_FRAC; vintage_years(rd);
    template_bounds_lonlat(path); encode_tile(raw5) -> ({feature: int16},
    n_over); fetch_window(ee, image, crs_wkt, transform, width, height,
    dest, retries=4) (a module global, monkeypatched here);
    build_region(ee, image, rd, tile_px=256, workers=8, dry_run=False,
    tile_dir=None, pilot_lonlat=None, pilot_out=None) -> {"years",
    "written", "valid_frac", "n_tiles", "skipped", "over_max"}.

Run with
    python -m unittest tests.test_cr0032
"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import rasterio
from rasterio.transform import from_origin

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import models  # noqa: E402
import grouse_data  # noqa: E402
import check_canopy_structure as chk  # noqa: E402
from grouse_data import DataConfig, RegionData, grid_mismatch  # noqa: E402

NODATA = -9999
LOCAL_ALBERS = ("+proj=aea +lat_0=44 +lon_0=-71.5 +lat_1=43 +lat_2=45 "
                "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
FEATS = ("mch_mean", "mch_f01", "mch_f15", "mch_f512")
N = 128                     # template is N x N at 30 m
TILE = 64                   # -> 2 x 2 windows
# Raw values every fetched cell gets, except the special cells below.
RAW = (12.34, 0.25, 0.10, 0.40, 1.0)          # h m, f01, f15, f512, valid
ENC = {"mch_mean": 123, "mch_f01": 250, "mch_f15": 100, "mch_f512": 400}
LOW_VALID_COLS = range(40, 50)                 # valid = 0.3 -> NODATA
MASKED_COLS = range(50, 60)                    # every band -1 -> NODATA
OVER_CELL = (5, 5)                             # h = 75 m -> NODATA, counted


def write_template(path):
    """N x N local-Albers grid; the top-right window (rows < 64, cols >=
    64) is template nodata, so it must not be fetched."""
    a = np.full((N, N), 7, np.int16)
    a[:TILE, TILE:] = NODATA
    with rasterio.open(path, "w", driver="GTiff", height=N, width=N,
                       count=1, dtype="int16", crs=LOCAL_ALBERS,
                       transform=from_origin(-1920.0, 1920.0, 30, 30),
                       nodata=NODATA) as dst:
        dst.write(a, 1)


def build_region_dir(base, evt_years=(2022, 2024), tcc_years=(2020,),
                     stale=()):
    d = os.path.join(base, "data", "landfire")
    os.makedirs(d, exist_ok=True)
    for y in evt_years:
        write_template(os.path.join(d, f"NH_{y}_evt.tif"))
    for y in tcc_years:
        write_template(os.path.join(d, f"NH_{y}_tcc.tif"))
    for name in stale:
        write_template(os.path.join(d, name))
    with mock.patch("builtins.print"):
        return RegionData("NH", DataConfig(base_dir=base))


def fake_fetch_factory(calls, all_over=False, all_masked=False,
                       shift_px=0):
    """fetch_window replacement: a 5-band float32 tile on exactly the
    requested window, raw values per RAW and the special cells."""
    def fake(ee, image, crs_wkt, transform, width, height, dest, retries=4):
        calls.append((transform.c, transform.f, width, height))
        tpl = from_origin(-1920.0, 1920.0, 30, 30)
        c0 = int(round((transform.c - tpl.c) / 30))
        r0 = int(round((tpl.f - transform.f) / 30))
        arr = np.empty((5, height, width), np.float32)
        for b, v in enumerate(RAW):
            arr[b] = v
        cols = c0 + np.arange(width)
        arr[4][:, np.isin(cols, LOW_VALID_COLS)] = 0.3
        arr[:, :, np.isin(cols, MASKED_COLS)] = -1
        r, c = OVER_CELL[0] - r0, OVER_CELL[1] - c0
        if 0 <= r < height and 0 <= c < width:
            arr[0, r, c] = 75.0
        if all_over:
            # ~16 % of each tile over 60 m: far past MCH_MAX_OVER_FRAC
            # while > 1 % stays valid, so only the over-max rule refuses
            arr[0, :10, :] = 75.0
        if all_masked:
            arr[:] = -1
        if shift_px:          # EE returned a tile off the requested grid
            transform = transform * transform.translation(shift_px, 0)
        with rasterio.open(dest, "w", driver="GTiff", height=height,
                           width=width, count=5, dtype="float32",
                           crs=crs_wkt, transform=transform) as dst:
            dst.write(arr)
    return fake


class T1Encoders(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(tuple(models.MCH_BIN_EDGES_M), (1.0, 5.0, 12.0))
        self.assertEqual(models.MCH_MIN_VALID_FRAC, 0.5)
        self.assertEqual(models.MCH_HEIGHT_MAX_M, 60.0)

    def test_height_values_and_refusals(self):
        v = models.mch_height_encode(np.array([0.0, 12.34, 60.0]))
        self.assertEqual(v.dtype, np.int16)
        self.assertEqual(v.tolist(), [0, 123, 600])
        for bad in (np.nan, np.inf, -0.1, 60.5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                models.mch_height_encode(np.array([bad]))

    def test_share_values_and_refusals(self):
        v = models.mch_share_encode(np.array([0.0, 0.2504, 1.0]))
        self.assertEqual(v.dtype, np.int16)
        self.assertEqual(v.tolist(), [0, 250, 1000])
        # float32 means a hair outside [0, 1] round into range (A2-3)
        self.assertEqual(models.mch_share_encode(
            np.array([1.0004, -0.0004])).tolist(), [1000, 0])
        for bad in (np.nan, -np.inf, -0.01, 1.01):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                models.mch_share_encode(np.array([bad]))

    def test_no_code_is_a_sentinel(self):
        codes = set(models.mch_height_encode(np.array([0.0, 60.0])).tolist())
        codes |= set(models.mch_share_encode(np.array([0.0, 1.0])).tolist())
        self.assertFalse(codes & set(grouse_data.NODATA_SENTINELS))


class T2Registration(unittest.TestCase):
    def test_raster_features(self):
        for f in FEATS:
            self.assertIn(f, grouse_data.RASTER_FEATURES)

    def test_feature_spec(self):
        want = {"mch_mean": 300.0, "mch_f01": 1000.0, "mch_f15": 1000.0,
                "mch_f512": 1000.0}
        for f, scale in want.items():
            spec = models.FEATURE_SPEC[f]
            self.assertEqual(spec["kind"], "continuous", f)
            self.assertEqual(float(spec["scale"]), scale, f)

    def test_generator_constants(self):
        import generate_canopy_structure as g
        self.assertEqual(tuple(g.MCH_FEATURES), FEATS)
        self.assertEqual(set(g.STATIC_FEATURES), {"road_dist", *FEATS})
        self.assertEqual(g.MCH_MAX_PIXELS, 4096)
        self.assertEqual(g.MCH_MAX_OVER_FRAC, 0.001)
        self.assertEqual(g.MCH_ASSET, chk.MCH_ASSET)
        self.assertEqual(chk.MIN_VALID_FRAC, models.MCH_MIN_VALID_FRAC)


class T3EncodeTile(unittest.TestCase):
    def raw(self, *cells):
        a = np.empty((5, 1, len(cells)), np.float32)
        for j, cell in enumerate(cells):
            a[:, 0, j] = cell
        return a

    def test_rules(self):
        import generate_canopy_structure as g
        raw = self.raw(RAW,                              # encoded
                       (0.0, 1.0, 0.0, 0.0, 1.0),        # 0 is a reading
                       (12.0, 0.2, 0.2, 0.2, 0.49),      # low validity
                       (-1, -1, -1, -1, 0.0),            # EE-masked
                       (75.0, 0.0, 0.0, 0.0, 1.0))       # > 60 m
        out, n_over = g.encode_tile(raw)
        self.assertEqual(n_over, 1)
        self.assertEqual(out["mch_mean"][0].tolist(), [123, 0, NODATA, NODATA, NODATA])
        self.assertEqual(out["mch_f01"][0].tolist(), [250, 1000, NODATA, NODATA, NODATA])
        for f in FEATS:
            self.assertEqual(out[f].dtype, np.int16)

    def test_nan_in_a_valid_cell_is_refused(self):
        import generate_canopy_structure as g
        with self.assertRaises(ValueError):
            g.encode_tile(self.raw((np.nan, 0.2, 0.2, 0.2, 1.0)))


class Base(unittest.TestCase):
    stale = ()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.rd = build_region_dir(self.tmp, stale=self.stale)
        import generate_canopy_structure as g
        self.g = g
        self.template = self.rd.latest_raster_path("evt")

    def run_build(self, fake, **kw):
        with mock.patch.object(self.g, "fetch_window", fake), \
             mock.patch("builtins.print"):
            return self.g.build_region(None, None, self.rd, tile_px=TILE,
                                       workers=1, **kw)

    def path(self, f, y):
        return os.path.join(self.tmp, "data", "landfire", f"NH_{y}_{f}.tif")


class T4Years(Base):
    stale = ("NH_2019_mch_mean.tif", "NH_2018_road_dist.tif")

    def test_union_excludes_static_features(self):
        self.assertEqual(self.g.vintage_years(self.rd), [2020, 2022, 2024])

    def test_bounds_cover_template(self):
        w, s, e, n = self.g.template_bounds_lonlat(self.template)
        self.assertTrue(w < -71.5 < e and s < 44.0 < n)


class T3Build(Base):
    def test_writes_layers_on_template_grid(self):
        calls = []
        out = self.run_build(fake_fetch_factory(calls),
                             tile_dir=os.path.join(self.tmp, "tiles"))
        self.assertEqual(out["years"], [2020, 2022, 2024])
        self.assertEqual(len(calls), 3)            # nodata window skipped
        self.assertEqual(out["skipped"], 1)
        self.assertEqual(out["over_max"], 1)
        with rasterio.open(self.template) as ref:
            for f in FEATS:
                with self.subTest(feature=f):
                    with rasterio.open(self.path(f, 2024)) as src:
                        self.assertIsNone(grid_mismatch(src, ref))
                        self.assertEqual(src.nodata, NODATA)
                        a = src.read(1)
                    self.assertTrue((a[TILE:, :40] == ENC[f]).all())
                    self.assertTrue((a[:, 40:60] == NODATA).all())
                    self.assertTrue((a[:TILE, TILE:] == NODATA).all())
                    self.assertEqual(int(a[OVER_CELL]), NODATA)
                    self.assertEqual(int(a[OVER_CELL[0], OVER_CELL[1] + 1]), ENC[f])
        for f in FEATS:
            blobs = {open(self.path(f, y), "rb").read()
                     for y in (2020, 2022, 2024)}
            self.assertEqual(len(blobs), 1, f)

    def test_resume_fetches_nothing(self):
        tiles = os.path.join(self.tmp, "tiles")
        self.run_build(fake_fetch_factory([]), tile_dir=tiles)
        before = open(self.path("mch_f512", 2024), "rb").read()

        def must_not_fetch(*a, **k):
            raise AssertionError("cached tile re-fetched")
        self.run_build(must_not_fetch, tile_dir=tiles)
        self.assertEqual(open(self.path("mch_f512", 2024), "rb").read(), before)

    def test_dry_run_writes_only_pilot(self):
        pilot = os.path.join(self.tmp, "pilot.tif")
        calls = []
        self.run_build(fake_fetch_factory(calls), dry_run=True,
                       pilot_out=pilot)
        self.assertEqual(len(calls), 1)
        for f in FEATS:
            for y in (2020, 2022, 2024):
                self.assertFalse(os.path.exists(self.path(f, y)))
        with rasterio.open(pilot) as src:
            self.assertEqual(src.count, 4)
            self.assertEqual(src.dtypes[0], "int16")
            self.assertEqual(int(src.read(1).max()), ENC["mch_mean"])

    def test_refuses_too_many_over_max(self):
        with self.assertRaises(RuntimeError):
            self.run_build(fake_fetch_factory([], all_over=True),
                           tile_dir=os.path.join(self.tmp, "tiles"))
        self.assertFalse(os.path.exists(self.path("mch_mean", 2024)))

    def test_refuses_almost_nothing_valid_existing_untouched(self):
        p = self.path("mch_mean", 2024)
        write_template(p)
        before = open(p, "rb").read()
        with self.assertRaises(RuntimeError):
            self.run_build(fake_fetch_factory([], all_masked=True),
                           tile_dir=os.path.join(self.tmp, "tiles"))
        self.assertEqual(open(p, "rb").read(), before)
        leftovers = [n for n in os.listdir(os.path.dirname(p))
                     if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])


class T3TileIdentity(Base):
    """CR-0032 round-2 A2-2/B2-2: tiles are checked against the requested
    window, and the cache is keyed on the template grid."""
    def test_off_grid_tile_refused(self):
        with self.assertRaises(RuntimeError):
            self.run_build(fake_fetch_factory([], shift_px=1),
                           tile_dir=os.path.join(self.tmp, "tiles"))
        self.assertFalse(os.path.exists(self.path("mch_mean", 2024)))

    def test_template_change_refetches(self):
        tiles = os.path.join(self.tmp, "tiles")
        self.run_build(fake_fetch_factory([]), tile_dir=tiles)
        # new latest evt vintage on a grid shifted by one cell
        d = os.path.join(self.tmp, "data", "landfire")
        with rasterio.open(os.path.join(d, "NH_2025_evt.tif"), "w",
                           driver="GTiff", height=N, width=N, count=1,
                           dtype="int16", crs=LOCAL_ALBERS,
                           transform=from_origin(-1890.0, 1920.0, 30, 30),
                           nodata=NODATA) as dst:
            dst.write(np.full((N, N), 7, np.int16), 1)
        calls = []
        self.run_build(fake_fetch_factory(calls), tile_dir=tiles)
        self.assertEqual(len(calls), 4)        # nothing reused
        with rasterio.open(self.path("mch_mean", 2025)) as src, \
             rasterio.open(os.path.join(d, "NH_2025_evt.tif")) as ref:
            self.assertIsNone(grid_mismatch(src, ref))


class T3GridCheck(Base):
    """CR-0032 round-2 B2-3: the pilot fetches an existing product over
    the pilot window through fetch_window and compares it with the file on
    disk, so an EE misreading of the template WKT is caught."""
    def fake_tcc(self, shift_px=0):
        def fake(ee, image, crs_wkt, transform, width, height, dest,
                 retries=4):
            with rasterio.open(self.rd.latest_raster_path("tcc")) as src:
                from rasterio.windows import from_bounds
                w = from_bounds(*rasterio.transform.array_bounds(
                    height, width, transform), transform=src.transform)
                a = src.read(1, window=w, boundless=True,
                             fill_value=NODATA)
            a = np.roll(a, shift_px, axis=1)
            with rasterio.open(dest, "w", driver="GTiff", height=height,
                               width=width, count=1, dtype="int16",
                               crs=crs_wkt, transform=transform,
                               nodata=NODATA) as dst:
                dst.write(a, 1)
        return fake

    def setUp(self):
        super().setUp()
        # give tcc structure so a shift is visible
        p = self.rd.latest_raster_path("tcc")
        with rasterio.open(p, "r+") as dst:
            dst.write((np.arange(N * N) % 97).astype(np.int16)
                      .reshape(N, N), 1)

    def grid_check(self, fake):
        from rasterio.windows import Window
        with mock.patch.object(self.g, "fetch_window", fake):
            return self.g.grid_check(None, None, self.rd, "tcc",
                                     Window(0, TILE, TILE, TILE))

    def test_same_grid_registered(self):
        g = self.grid_check(self.fake_tcc())
        self.assertTrue(g["ok"])
        self.assertEqual(g["best"], (0, 0))
        self.assertEqual(g["agree"][(0, 0)], 1.0)

    def test_registered_despite_resampling_noise(self):
        """Code review C1: the disk file went through two nearest steps,
        so ~15 % of cells differ even on a correct grid; registration,
        not equality, is the test."""
        base = self.fake_tcc()

        def noisy(ee, image, crs_wkt, transform, width, height, dest,
                  retries=4):
            base(ee, image, crs_wkt, transform, width, height, dest)
            with rasterio.open(dest, "r+") as dst:
                a = dst.read(1)
                rng = np.random.default_rng(1)
                flip = rng.random(a.shape) < 0.15
                a[flip] = (a[flip] + 1) % 97
                dst.write(a, 1)
        g = self.grid_check(noisy)
        self.assertTrue(g["ok"])
        self.assertLess(g["agree"][(0, 0)], 0.9)

    def test_shifted_grid_detected(self):
        g = self.grid_check(self.fake_tcc(shift_px=1))
        self.assertFalse(g["ok"])
        self.assertNotEqual(g["best"], (0, 0))

    def test_uniform_window_is_not_evidence(self):
        with rasterio.open(self.rd.latest_raster_path("tcc"), "r+") as dst:
            dst.write(np.full((N, N), 40, np.int16), 1)
        self.assertFalse(self.grid_check(self.fake_tcc())["ok"])


class T3CopyOnly(Base):
    """Code review C4: --copy-only copies only generator output on
    today's template grid."""
    def test_copies_missing_year(self):
        self.run_build(fake_fetch_factory([]),
                       tile_dir=os.path.join(self.tmp, "tiles"))
        os.remove(self.path("mch_f15", 2020))
        with mock.patch("builtins.print"):
            out = self.g.copy_only(self.rd)
        self.assertEqual(out, [self.path("mch_f15", 2020)])
        self.assertEqual(open(self.path("mch_f15", 2020), "rb").read(),
                         open(self.path("mch_f15", 2024), "rb").read())

    def test_refuses_untagged_file(self):
        for f in FEATS:
            write_template(self.path(f, 2024))
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            self.g.copy_only(self.rd)


class T6FetchErrors(unittest.TestCase):
    """fetch_window reports Earth Engine's error body; a 4xx (not 429) is
    raised at once, a 5xx retried (EC2 pilot 2026-10-05: four blind
    retries of an HTTP 400 with the reason discarded)."""
    class FakeEE:
        class EEException(Exception):
            pass

        @staticmethod
        def Projection(wkt):
            return wkt

        class Geometry:
            @staticmethod
            def Rectangle(*a, **k):
                return None

    class Image:
        def getDownloadURL(self, params):
            return "https://example.invalid/x"

    def call(self, status, text):
        import requests
        import generate_canopy_structure as g
        resp = mock.Mock(status_code=status, text=text)
        with mock.patch.object(requests, "get", return_value=resp) as get, \
             mock.patch.object(g.time, "sleep"), \
             mock.patch("sys.stderr"):
            try:
                g.fetch_window(self.FakeEE, self.Image(), "WKT",
                               from_origin(0, 0, 30, 30), 4, 4,
                               os.devnull, retries=2)
            except RuntimeError as e:
                return str(e), get.call_count
        return None, get.call_count

    def test_400_raised_once_with_body(self):
        msg, n = self.call(400, '{"error": {"message": "Bad CRS"}}')
        self.assertEqual(n, 1)
        self.assertIn("Bad CRS", msg)

    def test_500_retried_with_body(self):
        msg, n = self.call(503, "backend busy")
        self.assertEqual(n, 3)
        self.assertIn("backend busy", msg)


class T5Gate(unittest.TestCase):
    """check_canopy_structure.compare: passes agreement, fails each named
    failure mode (PA-0021: the gate is shown to fail)."""
    def setUp(self):
        rng = np.random.default_rng(0)
        n = 200
        self.ref = {"mch_mean": rng.uniform(0, 300, n),
                    "mch_f01": rng.uniform(1, 999, n),
                    "mch_f15": rng.uniform(1, 999, n),
                    "mch_f512": rng.uniform(1, 999, n)}
        self.gen = {f: np.rint(v).astype(np.int16) for f, v in self.ref.items()}

    def test_agreement_passes(self):
        ok, _ = chk.compare(self.gen, self.ref)
        self.assertTrue(ok)

    def test_metres_not_decimetres_fails(self):
        gen = dict(self.gen, mch_mean=np.rint(self.ref["mch_mean"] / 10).astype(np.int16))
        self.assertFalse(chk.compare(gen, self.ref)[0])

    def test_sampled_not_aggregated_fails(self):
        gen = {f: (np.where(v >= 500, 1000, 0).astype(np.int16)
                   if f != "mch_mean" else v) for f, v in self.gen.items()}
        self.assertFalse(chk.compare(gen, self.ref)[0])

    def test_over_masking_fails(self):
        gen = {f: np.where(np.arange(200) < 100, NODATA, v).astype(np.int16)
               for f, v in self.gen.items()}
        self.assertFalse(chk.compare(gen, self.ref)[0])

    def test_zero_for_nodata_fails(self):
        ref = {f: np.where(np.arange(200) < 100, np.nan, v)
               for f, v in self.ref.items()}
        gen = {f: np.where(np.arange(200) < 100, 0, v).astype(np.int16)
               for f, v in self.gen.items()}
        self.assertFalse(chk.compare(gen, ref)[0])


if __name__ == "__main__":
    unittest.main()
