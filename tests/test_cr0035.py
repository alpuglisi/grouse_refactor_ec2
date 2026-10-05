"""CR-0035: the registration gate (diagnose_layer_registration.py
--require-aligned) passes aligned layers and fails a layer moved one cell
(PA-0021: the gate is shown to fail). Synthetic rasters only.

Run with
    python -m unittest tests.test_cr0035
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
import grouse_data  # noqa: E402
import diagnose_layer_registration as dlr  # noqa: E402
from models import road_dist_encode  # noqa: E402

N = 600


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dir = os.path.join(self.tmp, "data", "landfire")
        os.makedirs(self.dir)
        rng = np.random.default_rng(0)
        dist = np.full((N, N), 500.0)
        dist[10::37, :] = 0.0
        dist[:, 7::53] = 0.0
        self.land = rng.integers(1, 6, (N, N))
        self.land[dist == 0] = 9
        self.write("road_dist", road_dist_encode(dist))
        self.write("evt", self.land)
        self.write("tcc", np.where(dist == 0, 5, 80) + rng.integers(0, 10, (N, N)))

    def write(self, name, arr):
        with rasterio.open(os.path.join(self.dir, f"NH_2024_{name}.tif"),
                           "w", driver="GTiff", height=N, width=N, count=1,
                           dtype="int16", crs="EPSG:5070",
                           transform=from_origin(0, N * 30, 30, 30),
                           nodata=-9999) as dst:
            dst.write(arr.astype(np.int16), 1)

    def run_gate(self, *feats):
        with mock.patch("builtins.print"):
            data = grouse_data.GrouseData(grouse_data.DataConfig(base_dir=self.tmp))
        argv = ["x", "--regions", "NH", "--require-aligned", *feats]
        with mock.patch.object(dlr, "GrouseData", lambda: data), \
             mock.patch.object(sys, "argv", argv), \
             mock.patch("builtins.print"), \
             self.assertRaises(SystemExit) as cm:
            dlr.main()
        return cm.exception.code

    def test_aligned_passes(self):
        self.write("nlcd", self.land)
        self.assertEqual(self.run_gate("nlcd", "tcc", "evt"), 0)

    def test_shifted_fails(self):
        self.write("nlcd", np.roll(np.roll(self.land, -1, 0), -1, 1))
        self.assertEqual(self.run_gate("nlcd", "tcc"), 1)

    def test_unmeasured_fails(self):
        self.assertEqual(self.run_gate("balive"), 1)


if __name__ == "__main__":
    unittest.main()


# ------------------------------------------------------------------ gates
import check_layer_registration as clr  # noqa: E402
import check_split_unchanged as csu  # noqa: E402
from tests.test_cr0034 import (Source, source_around,  # noqa: E402
                               write_template)


def point_sampler(src):
    """Local stand-in for Earth Engine point sampling at native scale:
    the source pixel containing each point."""
    from pyproj import Transformer

    def sample(xs, ys, crs):
        tx, ty = Transformer.from_crs(crs, src.crs, always_xy=True).transform(xs, ys)
        col = np.floor((np.asarray(tx) - src.sx0) / 30.0).astype(int)
        row = np.floor((src.sy0 - np.asarray(ty)) / 30.0).astype(int)
        ok = (col >= 0) & (col < src.w) & (row >= 0) & (row < src.h)
        out = np.full(len(xs), np.nan)
        out[ok] = src.a[row[ok], col[ok]]
        return out
    return sample


class RegistrationGate(unittest.TestCase):
    """check_layer_registration passes registered files and fails
    BUG-0094-shifted ones (half a pixel, via the measured SE tie)."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.tpl = os.path.join(self.tmp, "tpl.tif")
        write_template(self.tpl)
        self.src = source_around(self.tpl)

    def lattice_copy(self, origin_shift):
        """The source re-gridded onto its own lattice (shift 0) or onto
        the 0-origin lattice (shift 15: BUG-0094, ties to the SE)."""
        s = self.src
        x0, y0 = s.sx0 + origin_shift, s.sy0 + origin_shift
        w, h = s.w - 2, s.h - 2
        cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
        arr = s.sample(x0 + cols * 30, y0 - rows * 30)
        p = os.path.join(self.tmp, f"raw_{origin_shift}.tif")
        with rasterio.open(p, "w", driver="GTiff", height=h, width=w,
                           count=1, dtype="int16", crs=s.crs,
                           transform=from_origin(x0, y0, 30, 30),
                           nodata=-9999) as dst:
            dst.write(arr, 1)
        return p

    def on_template(self, raw):
        from realign_rasters import warp_to_grid
        out = raw.replace(".tif", "_tpl.tif")
        warp_to_grid(raw, self.tpl, out)
        return out

    def test_template_file(self):
        fn = point_sampler(self.src)
        good = self.on_template(self.lattice_copy(0))
        bad = self.on_template(self.lattice_copy(15))
        self.assertGreaterEqual(clr.check_template_file(good, fn)[0], clr.MIN_EQUAL)
        self.assertLess(clr.check_template_file(bad, fn)[0], clr.MIN_EQUAL)

    def test_raw_file(self):
        fn = point_sampler(self.src)
        self.assertEqual(clr.check_raw_file(self.lattice_copy(0), fn)[0], 1.0)
        self.assertLess(clr.check_raw_file(self.lattice_copy(15), fn)[0],
                        clr.MIN_EQUAL)

    def test_derived_file(self):
        """Forest mask of a derived layer vs the raw it was warped from."""
        self.src.a[::3, :] = 0                  # some non-forest
        raw = self.lattice_copy(0)
        derived = self.on_template(raw)
        other = self.lattice_copy(15)           # a different (shifted) raw
        self.assertGreaterEqual(clr.check_derived_file(derived, raw)[0], clr.MIN_EQUAL)
        self.assertLess(clr.check_derived_file(derived, other)[0], clr.MIN_EQUAL)


class SplitGate(unittest.TestCase):
    def test_compare(self):
        paths = ["a.csv", "b.csv"]
        same = {"a.csv": "1", "b.csv": "2"}
        self.assertEqual(csu.compare(same, same, same, paths), [])
        self.assertTrue(csu.compare(same, same, {"a.csv": "1", "b.csv": "X"}, paths))
        self.assertTrue(csu.compare(same, {"a.csv": "1"}, same, paths))
        self.assertTrue(csu.compare(same, same, {"a.csv": "1", "b.csv": None}, paths))
        self.assertTrue(csu.compare({"a.csv": "1"}, same, same, paths))
