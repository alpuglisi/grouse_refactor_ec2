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

    def lattice_copy(self, origin_shift, nw_tie=False, src=None, name=None):
        """The source re-gridded onto its own lattice (shift 0) or onto
        the 0-origin lattice (shift 15: BUG-0094, ties to the SE; nw_tie:
        the same offset with ties broken to the NW instead)."""
        s = src or self.src
        x0, y0 = s.sx0 + origin_shift, s.sy0 + origin_shift
        w, h = s.w - 2, s.h - 2
        cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
        e = -1e-6 if nw_tie else 0.0
        arr = s.sample(x0 + cols * 30 + e, y0 - rows * 30 - e)
        p = os.path.join(self.tmp, name or f"raw_{origin_shift}_{nw_tie}.tif")
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

    def grid(self):
        return {"crs": self.src.crs, "x0": float(self.src.sx0),
                "y0": float(self.src.sy0)}

    def test_template_file(self):
        fn = point_sampler(self.src)
        good = clr.check_template_file(self.on_template(self.lattice_copy(0)),
                                       fn, grid=self.grid())
        bad = clr.check_template_file(self.on_template(self.lattice_copy(15)),
                                      fn, grid=self.grid())
        self.assertGreaterEqual(good["equal"], clr.MIN_EQUAL)
        self.assertLess(bad["equal"], clr.MIN_EQUAL)
        # diagnostic: the shifted file matches the source at the BUG-0094
        # offset far better than the repaired one does
        self.assertGreater(bad["equal_at_bug_offset"], 0.9)
        self.assertLess(good["equal_at_bug_offset"], 0.5)

    def test_raw_file(self):
        fn = point_sampler(self.src)
        self.assertEqual(clr.check_raw_file(self.lattice_copy(0), fn)["equal"], 1.0)
        for nw in (False, True):     # a tie broken either way fails (A35-2-2)
            with self.subTest(nw_tie=nw):
                self.assertLess(clr.check_raw_file(self.lattice_copy(15, nw),
                                                   fn)["equal"], clr.MIN_EQUAL)

    def test_edge_distance(self):
        g = {"x0": 15.0, "y0": 615.0}
        d = clr.edge_distance(np.array([15.0, 30.0, 17.0]),
                              np.array([600.0, 600.0, 600.0]), g)
        self.assertEqual(d.tolist(), [0.0, 15.0, 2.0])


class DerivedGate(RegistrationGate):
    """Each derived TreeMap layer vs its own raw attributes, encoded as
    generate_treemap_features does (A35-2-1): includes harvested plots
    with down wood but no live basal area."""
    def raw_attr(self, attr, values, shift=0):
        src = Source(self.src.sx0, self.src.sy0, self.src.w, self.src.h,
                     crs=self.src.crs)
        src.a = values
        return self.lattice_copy(shift, src=src, name=f"{attr}_{shift}.tif")

    def derived(self, feat, raws):
        """Simulate generate_treemap_features: an EXACT nearest warp of
        each raw attribute onto the template (independent of the warp
        code CR-0034 repairs), then rebuild_derived."""
        from rasterio.enums import Resampling
        from rasterio.warp import reproject
        vals = {}
        with rasterio.open(self.tpl) as t:
            prof = t.profile
        for at, p in raws.items():
            dst = np.full((prof["height"], prof["width"]), -9999, np.int16)
            with rasterio.open(p) as s:
                reproject(s.read(1), dst, src_transform=s.transform,
                          src_crs=s.crs, src_nodata=-9999,
                          dst_transform=prof["transform"], dst_crs=prof["crs"],
                          dst_nodata=-9999, resampling=Resampling.nearest,
                          tolerance=0)
            vals[at] = dst.astype(np.float64)
        enc = clr.rebuild_derived(feat, {k: v.ravel() for k, v in vals.items()})
        enc = enc.reshape(next(iter(vals.values())).shape)
        enc[next(iter(vals.values())) == -9999] = -9999
        path = os.path.join(self.tmp, f"derived_{feat}.tif")
        prof.update(dtype="int16", nodata=-9999)
        with rasterio.open(path, "w", **prof) as d:
            d.write(enc.astype(np.int16), 1)
        return path

    def test_carbon_dwn_without_live_trees(self):
        rng = np.random.default_rng(1)
        h, w = self.src.h, self.src.w
        balive = rng.uniform(0, 200, (h, w)).astype(np.int16)
        carbon = rng.uniform(0, 30, (h, w)).astype(np.int16)
        balive[::4, :] = 0            # harvested: no live basal area ...
        carbon[::4, :] = 12           # ... but down wood
        good = {"BALIVE": self.raw_attr("BALIVE", balive),
                "CARBON_DWN": self.raw_attr("CARBON_DWN", carbon)}
        for feat, at in (("balive", "BALIVE"), ("carbon_dwn", "CARBON_DWN")):
            with self.subTest(feat=feat):
                d = self.derived(feat, {at: good[at]})
                r = clr.check_derived_file(d, feat, {at: good[at]})
                self.assertGreaterEqual(r["equal"], clr.MIN_EQUAL)
                shifted = {at: self.raw_attr(at, {"BALIVE": balive,
                                                  "CARBON_DWN": carbon}[at], 15)}
                self.assertLess(clr.check_derived_file(d, feat, shifted)["equal"],
                                clr.MIN_EQUAL)


class SplitGate(unittest.TestCase):
    def test_compare(self):
        paths = ["a.csv", "b.csv"]
        same = {"a.csv": "1", "b.csv": "2"}
        self.assertEqual(csu.compare(same, same, same, paths), [])
        self.assertTrue(csu.compare(same, same, {"a.csv": "1", "b.csv": "X"}, paths))
        self.assertTrue(csu.compare(same, {"a.csv": "1"}, same, paths))
        self.assertTrue(csu.compare(same, same, {"a.csv": "1", "b.csv": None}, paths))
        self.assertTrue(csu.compare({"a.csv": "1"}, same, same, paths))


if __name__ == "__main__":
    unittest.main()
