"""CR-0032: Meta 1 m canopy-structure layers (mch_*). Synthetic rasters only;
no Earth Engine, no data/ access.

Written before approval (CR-0011 A3) and reviewed with the CR. Every test
fails until CR-0032 deliverable 2 lands (generate_canopy_structure.py, the
models.py constants/encoders/FEATURE_SPEC entries, RASTER_FEATURES).

Interface these tests pin (CR-0032 §2-§4):
  models.MCH_BIN_EDGES_M = (1.0, 5.0, 12.0), MCH_MIN_VALID_FRAC = 0.5,
  MCH_HEIGHT_MAX_M = 60.0, mch_height_encode(metres) -> int16 decimetres,
  mch_share_encode(fraction) -> int16 per mille (both refuse NaN/inf and
  out-of-range input with ValueError).
  generate_canopy_structure.MCH_FEATURES = ("mch_mean", "mch_f01",
  "mch_f15", "mch_f512"); vintage_years(rd); template_bounds_lonlat(path);
  build_region(ee, image, rd, bounds_lonlat, tile_m, workers=1,
  dry_run=False) -> {"years": [...], "written": [...], "valid_frac": f};
  tiles are fetched through download_tcc_nlcd.fetch_tile(ee, image, rect,
  dest) (monkeypatched here).

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
from grouse_data import DataConfig, RegionData, grid_mismatch  # noqa: E402

NODATA = -9999
# A local Albers like the LFPS clips (not EPSG:5070), so the warp is exercised.
LOCAL_ALBERS = ("+proj=aea +lat_0=44 +lon_0=-71.5 +lat_1=43 +lat_2=45 "
                "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
FEATS = ("mch_mean", "mch_f01", "mch_f15", "mch_f512")
# Values written by the fake Earth Engine tiles, per band, everywhere
# except the nodata block (east third of the area).
BAND_VALUES = {"mch_mean": 123, "mch_f01": 250, "mch_f15": 100, "mch_f512": 400}


def write_template(path, nx=120, ny=120, res=30.0):
    with rasterio.open(path, "w", driver="GTiff", height=ny, width=nx,
                       count=1, dtype="int16", crs=LOCAL_ALBERS,
                       transform=from_origin(-1800.0, 1800.0, res, res),
                       nodata=NODATA) as dst:
        dst.write(np.full((ny, nx), 7, np.int16), 1)


def build_region_dir(base, evt_years=(2022, 2024), tcc_years=(2020,)):
    d = os.path.join(base, "data", "landfire")
    os.makedirs(d, exist_ok=True)
    for y in evt_years:
        write_template(os.path.join(d, f"NH_{y}_evt.tif"))
    for y in tcc_years:
        write_template(os.path.join(d, f"NH_{y}_tcc.tif"))
    return RegionData("NH", DataConfig(base_dir=base))


def fake_fetch_factory(nodata_east_of_x=None, all_nodata=False):
    """fetch_tile replacement: writes a 4-band EPSG:5070 GeoTIFF for the
    requested rect on the 30 m lattice, with BAND_VALUES, and nodata
    east of a 5070 x coordinate (or everywhere)."""
    def fake(ee, image, rect, dest, retries=4):
        x0, y0, x1, y1 = rect
        nx, ny = int(round((x1 - x0) / 30)), int(round((y1 - y0) / 30))
        xs = x0 + 30 * (np.arange(nx) + 0.5)
        arr = np.empty((4, ny, nx), np.int16)
        for b, f in enumerate(FEATS):
            arr[b] = BAND_VALUES[f]
        if all_nodata:
            arr[:] = NODATA
        elif nodata_east_of_x is not None:
            arr[:, :, xs > nodata_east_of_x] = NODATA
        with rasterio.open(dest, "w", driver="GTiff", height=ny, width=nx,
                           count=4, dtype="int16", crs="EPSG:5070",
                           transform=from_origin(x0, y1, 30, 30),
                           nodata=NODATA) as dst:
            dst.write(arr)
    return fake


class T1Encoders(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(tuple(models.MCH_BIN_EDGES_M), (1.0, 5.0, 12.0))
        self.assertEqual(models.MCH_MIN_VALID_FRAC, 0.5)
        self.assertEqual(models.MCH_HEIGHT_MAX_M, 60.0)

    def test_height_round_trip_and_refusals(self):
        v = models.mch_height_encode(np.array([0.0, 12.34, 60.0]))
        self.assertEqual(v.dtype, np.int16)
        self.assertEqual(v.tolist(), [0, 123, 600])
        for bad in (np.nan, np.inf, -0.1, 60.5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                models.mch_height_encode(np.array([bad]))

    def test_share_round_trip_and_refusals(self):
        v = models.mch_share_encode(np.array([0.0, 0.2504, 1.0]))
        self.assertEqual(v.dtype, np.int16)
        self.assertEqual(v.tolist(), [0, 250, 1000])
        for bad in (np.nan, -0.01, 1.01):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                models.mch_share_encode(np.array([bad]))

    def test_no_code_collides_with_nodata(self):
        self.assertNotIn(int(models.mch_height_encode(np.array([0.0]))[0]),
                         grouse_data.NODATA_SENTINELS)


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

    def test_generator_feature_tuple(self):
        import generate_canopy_structure as g
        self.assertEqual(tuple(g.MCH_FEATURES), FEATS)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        with mock.patch("builtins.print"):
            self.rd = build_region_dir(self.tmp)
        import generate_canopy_structure as g
        self.g = g
        self.template = self.rd.latest_raster_path("evt")
        self.bounds = g.template_bounds_lonlat(self.template)

    def run_build(self, fake, dry_run=False):
        import download_tcc_nlcd as dtn
        with mock.patch.object(dtn, "fetch_tile", fake), \
             mock.patch("builtins.print"):
            return self.g.build_region(None, None, self.rd, self.bounds,
                                       tile_m=1800, workers=1,
                                       dry_run=dry_run)

    def path(self, f, y):
        return os.path.join(self.tmp, "data", "landfire", f"NH_{y}_{f}.tif")


class T4Years(Base):
    def test_union_of_other_features_vintages(self):
        self.assertEqual(self.g.vintage_years(self.rd), [2020, 2022, 2024])


class T3LocalBuild(Base):
    def test_writes_four_layers_per_year_on_template_grid(self):
        # nodata east of the template's centre, in EPSG:5070 terms
        from pyproj import Transformer
        lon_c = sum(self.bounds[0::2]) / 2
        lat_c = sum(self.bounds[1::2]) / 2
        xc, _ = Transformer.from_crs("EPSG:4326", "EPSG:5070",
                                     always_xy=True).transform(lon_c, lat_c)
        out = self.run_build(fake_fetch_factory(nodata_east_of_x=xc + 600))
        self.assertEqual(out["years"], [2020, 2022, 2024])
        with rasterio.open(self.template) as ref:
            for f in FEATS:
                for y in (2020, 2022, 2024):
                    with self.subTest(feature=f, year=y):
                        p = self.path(f, y)
                        self.assertTrue(os.path.exists(p))
                        with rasterio.open(p) as src:
                            self.assertIsNone(grid_mismatch(src, ref))
                            a = src.read(1)
                            self.assertEqual(src.nodata, NODATA)
                        # west part: the value; far east: nodata
                        self.assertTrue((a[:, :30] == BAND_VALUES[f]).all())
                        self.assertTrue((a[:, -20:] == NODATA).all())
        # static layer: byte-identical copies across vintages
        for f in FEATS:
            blobs = {open(self.path(f, y), "rb").read() for y in (2020, 2022, 2024)}
            self.assertEqual(len(blobs), 1, f)

    def test_dry_run_writes_nothing(self):
        self.run_build(fake_fetch_factory(), dry_run=True)
        for f in FEATS:
            for y in (2020, 2022, 2024):
                self.assertFalse(os.path.exists(self.path(f, y)))

    def test_refuses_when_almost_nothing_valid(self):
        with self.assertRaises(RuntimeError):
            self.run_build(fake_fetch_factory(all_nodata=True))
        for f in FEATS:
            self.assertFalse(os.path.exists(self.path(f, 2024)))

    def test_existing_files_untouched_on_refusal(self):
        p = self.path("mch_mean", 2024)
        write_template(p)
        before = open(p, "rb").read()
        with self.assertRaises(RuntimeError):
            self.run_build(fake_fetch_factory(all_nodata=True))
        self.assertEqual(open(p, "rb").read(), before)


if __name__ == "__main__":
    unittest.main()
