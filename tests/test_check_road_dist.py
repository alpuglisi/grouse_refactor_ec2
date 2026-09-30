"""Unit tests for check_road_dist.py (CR-0014's verifier): the Canada rule,
the RD statistics and the atomic, validated download.

    python -m unittest tests.test_check_road_dist -v
"""
import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

import numpy as np
from rasterio.transform import from_origin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import check_road_dist as c  # noqa: E402

TR = from_origin(0, 30 * 400, 30, 30)
T_ = {"rd1_median_abs_m": 20.0, "rd2_p99_abs_m": 60.0,
      "rd3_max_abs_m": 60.0, "rd4_signed_band_m": [-20.0, 5.0]}


class CanadaRule(unittest.TestCase):
    def setUp(self):
        # 1 row x 400 px strip, 30 m pixels: US on the left, Canada right.
        self.T = np.zeros((1, 400), bool)
        self.T[0, :300] = True

    def test_land_nearer_than_road_is_masked(self):
        L = ~self.T                              # Canadian land from px 300
        d_road = np.full((1, 400), 5000.0)       # nearest road 5 km away
        C = c.canada_set(self.T, L, d_road, TR)
        d_can = (300 - np.arange(300)) * 30.0    # px 299 is 30 m from land
        np.testing.assert_array_equal(C[0, :300], d_can < 5000.0)
        self.assertFalse(C[0, 300:].any())       # never outside T

    def test_road_nearer_than_land_keeps_value(self):
        L = ~self.T
        d_road = np.full((1, 400), 20.0)
        self.assertFalse(c.canada_set(self.T, L, d_road, TR).any())

    def test_strict_inequality_at_ties(self):
        L = ~self.T
        d_road = np.full((1, 400), 60.0)         # px 298 is exactly 60 m
        C = c.canada_set(self.T, L, d_road, TR)
        self.assertTrue(C[0, 299])
        self.assertFalse(C[0, 298])

    def test_no_land_no_new_nodata(self):
        L = np.zeros((1, 400), bool)
        d_road = np.full((1, 400), 1e6)
        self.assertFalse(c.canada_set(self.T, L, d_road, TR).any())

    def test_water_is_not_land(self):
        evt = np.full((1, 400), 7292)            # Open Water beyond the US
        evt[0, 350:] = 7555                      # real land further out
        evt[0, 390:] = -9999                     # sentinel
        L = c.canada_land(self.T, evt)
        self.assertFalse(L[0, :350].any())
        self.assertTrue(L[0, 350:390].all())
        self.assertFalse(L[0, 390:].any())


class RDStats(unittest.TestCase):
    def test_correct_raster_passes(self):
        rng = np.random.default_rng(0)
        err = rng.uniform(-21, 5, 400) - 5
        r = c.rd_stats(err, 0, T_)
        self.assertTrue(all(ok for _, ok in r.values()), r)

    def test_home_state_only_fails(self):
        err = np.concatenate([np.full(300, -8.0), np.full(100, 600.0)])
        r = c.rd_stats(err, 0, T_)
        self.assertFalse(r["RD2"][1])
        self.assertFalse(r["RD3"][1])

    def test_excluded_points_fail(self):
        r = c.rd_stats(np.zeros(10), 3, T_)
        self.assertFalse(r["RD5"][1])


class Download(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.txt", "x" * 5000)
        self.good = buf.getvalue()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _src(self, data, name):
        p = os.path.join(self.tmp, name)
        with open(p, "wb") as f:
            f.write(data)
        return "file://" + p

    def test_truncated_download_leaves_nothing(self):
        url = self._src(self.good[: len(self.good) // 2], "trunc.zip")
        dst = os.path.join(self.tmp, "out", "x.zip")
        with self.assertRaises(RuntimeError):
            c.fetch(url, dst)
        self.assertFalse(os.path.exists(dst))
        self.assertFalse(os.path.exists(dst + ".part"))

    def test_truncated_cache_is_refetched(self):
        dst = os.path.join(self.tmp, "x.zip")
        with open(dst, "wb") as f:
            f.write(self.good[:40])                  # poisoned cache
        c.fetch(self._src(self.good, "good.zip"), dst)
        self.assertTrue(c.zip_ok(dst))


if __name__ == "__main__":
    unittest.main()
