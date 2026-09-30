"""CR-0008 unit tests (U1-U6): generators write nodata outside coverage,
encoders refuse non-finite input, the tcc/nlcd range mask and the
post-download coverage check.

    python -m unittest tests.test_cr0008 -v
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import models  # noqa: E402

H = W = 32
PROFILE = dict(driver="GTiff", height=H, width=W, count=1, crs="EPSG:5070",
               transform=from_origin(0, H * 30, 30, 30))


def write(path, arr, dtype="int16", nodata=-9999):
    with rasterio.open(path, "w", dtype=dtype, nodata=nodata,
                       **PROFILE) as dst:
        dst.write(arr.astype(dtype), 1)


def read(path):
    with rasterio.open(path) as s:
        return s.read(1), s.tags()


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def p(self, name):
        return os.path.join(self.tmp, name)


class U2Encoders(unittest.TestCase):
    def test_encoders_refuse_non_finite(self):
        calls = [
            lambda v: models.tsd_encode(v),
            lambda v: models.road_dist_encode(v),
            lambda v: models.tpa_live_encode(v),
            lambda v: models.treemap_encode("balive", v),
            lambda v: models.qmd_from_balive_tpa(v, np.ones_like(v)),
        ]
        for f in calls:
            for bad in (np.nan, np.inf, -np.inf):
                with self.assertRaises(ValueError):
                    f(np.array([1.0, bad]))
            f(np.array([0.0, 1.0]))     # finite input still works


class U3MaskToValid(unittest.TestCase):
    def test_ranges(self):
        from download_tcc_nlcd import mask_to_valid, PRODUCTS
        lo, hi = PRODUCTS["tcc"]["valid_range"]
        np.testing.assert_array_equal(
            mask_to_valid(np.array([-1, 0, 55]), lo, hi), [-9999, 0, 55])
        lo, hi = PRODUCTS["nlcd"]["valid_range"]
        np.testing.assert_array_equal(
            mask_to_valid(np.array([-1, 0, 41]), lo, hi), [-9999, -9999, 41])


class U4TsdCoverage(Tmp):
    def test_sentinel_in_middle_vintage(self):
        import generate_time_since_disturbance as g
        template = self.p("VT_2019_nlcd.tif")
        write(template, np.full((H, W), 41))
        vint = {}
        for d in (2019, 2020, 2021):
            a = np.zeros((H, W))
            if d == 2020:
                a[3, 4] = 32767           # fill: outside this vintage
            if d == 2019:
                a[8, 8] = 5               # a real disturbance
            vint[d] = self.p(f"LF_Dist{d % 100:02d}.tif")
            write(vint[d], a)
        rd = mock.MagicMock()
        rd.available_features.return_value = ["nlcd"]
        rd.latest_raster_path.return_value = template
        rd.raster_years.return_value = [2019, 2020, 2021]
        data = mock.MagicMock()
        data.__getitem__.return_value = rd
        out = self.p("out")
        g.process_region("VT", data, vint, 16, out_dir=out)
        for y, expect_nodata in ((2019, False), (2020, True), (2021, True)):
            a, tags = read(os.path.join(out, f"VT_{y}_tsd.tif"))
            self.assertEqual(a[3, 4] == -9999, expect_nodata, y)
            self.assertEqual(int((a == -9999).sum()), int(expect_nodata))
            self.assertEqual(tags["GROUSE_COVERAGE"],
                             "disturbance-intersection")
        a, _ = read(os.path.join(out, "VT_2020_tsd.tif"))
        self.assertEqual(a[8, 8], models.tsd_encode(np.array([1.0]))[0])


class U1TreeMapClean(Tmp):
    def test_bad_raw_values_become_nodata_per_feature(self):
        import generate_treemap_features as g
        ref = self.p("VT_2016_evt.tif")
        write(ref, np.full((H, W), 7))
        nlcd = np.full((H, W), 41)
        nlcd[:, :4] = -9999
        write(self.p("VT_2016_nlcd.tif"), nlcd)
        raw = {}
        for attr, val in (("BALIVE", 80.0), ("TPA_LIVE", 300.0),
                          ("CARBON_DWN", 2.0)):
            a = np.full((H, W), val, dtype=np.float32)
            a[20:, 20:] = 0.0               # in-coverage non-forest
            raw[attr] = a
        raw["BALIVE"][5, 5] = np.nan
        raw["TPA_LIVE"][10, 10] = -5.0
        raw["CARBON_DWN"][15, 15] = 1e10
        paths = {}
        for attr, a in raw.items():
            paths[attr] = self.p(f"raw_{attr}.tif")
            write(paths[attr], a, dtype="float32", nodata=None)
        out = self.p("out")
        os.makedirs(out)
        with rasterio.open(ref) as r:
            profile = r.profile.copy()
        profile.update(dtype="int16", nodata=-9999)
        with mock.patch.object(g, "find_source",
                               side_effect=lambda s, v, a, r=None: paths[a]):
            g.write_vintage("VT", 2016, 2016, self.tmp, ref, profile, out,
                            8, self.p("VT_2016_nlcd.tif"))
        expect = {"balive": {(5, 5)}, "tpa_live": {(10, 10)},
                  "qmd": {(5, 5), (10, 10)}, "carbon_dwn": {(15, 15)}}
        for feat, pts in expect.items():
            a, tags = read(os.path.join(out, f"VT_2016_{feat}.tif"))
            self.assertTrue((a[:, :4] == -9999).all(), feat)
            inside = a[:, 4:] == -9999
            got = {(int(r), int(c) + 4) for r, c in zip(*np.nonzero(inside))}
            self.assertEqual(got, pts, feat)
            self.assertEqual(a[25, 25], 0, feat)   # non-forest stays 0
            self.assertEqual(tags["GROUSE_COVERAGE"], "nlcd")


class U5PostDownloadCheck(Tmp):
    def test_tcc_value_outside_nlcd_refused(self):
        from download_tcc_nlcd import _check_coverage
        nl = np.full((H, W), 41)
        nl[:, :4] = -9999
        write(self.p("nlcd.tif"), nl)
        good = np.full((H, W), 30)
        good[:, :4] = -9999
        write(self.p("good.tif"), good)
        _check_coverage("tcc", self.p("good.tif"), self.p("nlcd.tif"),
                        self.p("out.tif"))
        bad = good.copy()
        bad[0, 0] = 0                       # EE mask exported as 0 %
        write(self.p("bad.tif"), bad)
        write(self.p("out.tif"), good)
        before = read(self.p("out.tif"))[0]
        with self.assertRaises(RuntimeError):
            _check_coverage("tcc", self.p("bad.tif"), self.p("nlcd.tif"),
                            self.p("out.tif"))
        np.testing.assert_array_equal(read(self.p("out.tif"))[0], before)
        # nlcd itself is not checked against itself
        _check_coverage("nlcd", self.p("bad.tif"), self.p("nlcd.tif"),
                        self.p("out.tif"))


class U6LegacyRefusal(Tmp):
    def test_generator_tag_triggers_refusal(self):
        import types
        import grouse_data
        path = self.p("VT_2020_tsd.tif")
        write(path, np.zeros((H, W)))
        with rasterio.open(path, "r+") as s:
            s.update_tags(GROUSE_COVERAGE="disturbance-intersection")
        with self.assertRaises(SystemExit):
            grouse_data.refuse_legacy_checkpoint_on_repaired(
                types.SimpleNamespace(missing_mask=False), [path])
        grouse_data.refuse_legacy_checkpoint_on_repaired(
            types.SimpleNamespace(missing_mask=True), [path])


if __name__ == "__main__":
    unittest.main()
