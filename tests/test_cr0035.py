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
