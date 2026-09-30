"""CR-0010 unit tests: the repair + checker on a synthetic fixture, and
the legacy-checkpoint refusal. (The generator refuse-to-overwrite guard
and its tests were removed by CR-0008, which fixed the generators.)

    python -m unittest tests.test_cr0010 -v
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import grouse_data  # noqa: E402

H = W = 48
CRS = "EPSG:5070"
TR = from_origin(0, H * 30, 30, 30)
PROFILE = dict(driver="GTiff", height=H, width=W, count=1, dtype="int16",
               crs=CRS, transform=TR, nodata=-9999, compress="deflate",
               predictor=2, tiled=True, blockxsize=16, blockysize=16)


def write(path, arr, **tags):
    with rasterio.open(path, "w", **PROFILE) as dst:
        dst.write(arr.astype("int16"), 1)
        if tags:
            dst.update_tags(**tags)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def digest(mask):
    return hashlib.sha256(np.packbits(mask.ravel())).hexdigest()[:32]


class Fixture:
    """VT grid 48x48. nlcd nodata in the left 12 columns; disturbance
    fill in the top 6 rows (Dist19) and bottom 4 rows (Dist20)."""

    def __init__(self):
        self.tmp = tempfile.mkdtemp()
        self.land = os.path.join(self.tmp, "landfire")
        self.dist = os.path.join(self.tmp, "dist")
        self.backup = os.path.join(self.tmp, "backup")
        for d in (self.land, self.dist, self.backup):
            os.makedirs(d)
        nlcd = np.full((H, W), 41)
        nlcd[:, :12] = -9999
        for y in (2020, 2021):
            write(os.path.join(self.land, f"VT_{y}_nlcd.tif"), nlcd)
        d19 = np.zeros((H, W))
        d19[:6] = -9999
        d19[20, 20] = 5
        d20 = np.zeros((H, W))
        d20[-4:] = 32767
        write(os.path.join(self.dist, "LF2020_Dist19_CONUS.tif"), d19)
        write(os.path.join(self.dist, "LF2020_Dist20_CONUS.tif"), d20)
        self.nlcd_mask = nlcd != -9999
        self.dist_mask = np.ones((H, W), bool)
        self.dist_mask[:6] = False
        self.dist_mask[-4:] = False
        write(os.path.join(self.land, "VT_2020_tsd.tif"),
              np.full((H, W), 3434))
        bal = np.full((H, W), 50)
        bal[30:, 20:] = 0
        write(os.path.join(self.land, "VT_2020_balive.tif"), bal)
        write(os.path.join(self.land, "VT_2020_tcc.tif"), np.full((H, W), 20))
        # an out-of-scope raster that must stay untouched (F2)
        write(os.path.join(self.land, "VT_2020_evt.tif"), np.full((H, W), 7))

        self.pins = os.path.join(self.tmp, "pins.json")
        feats = {"tsd": "disturbance", "balive": "nlcd", "tcc": "nlcd"}
        out = {"tsd": int((~self.dist_mask).sum()),
               "balive": int((~self.nlcd_mask).sum()),
               "tcc": int((~self.nlcd_mask).sum())}
        json.dump({
            "nodata": -9999, "n_files": 3, "feature_mask": feats,
            "masks": {"VT": {
                "nlcd": {"inside": int(self.nlcd_mask.sum()),
                         "sha256": digest(self.nlcd_mask)},
                "disturbance": {"inside": int(self.dist_mask.sum()),
                                "sha256": digest(self.dist_mask)}}},
            "n_pre": {"VT": out}}, open(self.pins, "w"))
        self.man_in = os.path.join(self.tmp, "man_in.tsv")
        self.man_other = os.path.join(self.tmp, "man_other.tsv")
        self._manifest(self.man_in, ["VT_2020_tsd.tif", "VT_2020_balive.tif",
                                     "VT_2020_tcc.tif"])
        self._manifest(self.man_other, ["VT_2020_nlcd.tif", "VT_2021_nlcd.tif",
                                        "VT_2020_evt.tif"])
        for n in ("VT_2020_tsd.tif", "VT_2020_balive.tif", "VT_2020_tcc.tif"):
            shutil.copyfile(os.path.join(self.land, n),
                            os.path.join(self.backup, n))

    def _manifest(self, path, names):
        with open(path, "w") as f:
            f.write("name\tsha256\tsize\tmtime_ns\n")
            for n in names:
                p = os.path.join(self.land, n)
                st = os.stat(p)
                f.write(f"{n}\t{sha(p)}\t{st.st_size}\t{st.st_mtime_ns}\n")

    def repair(self):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "repair_coverage_rasters.py"),
             "repair", "--root", self.land, "--mask-root", self.land,
             "--dist-dir", self.dist, "--pins", self.pins, "--jobs", "1"],
            capture_output=True, text=True)

    def check(self):
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "check_raster_repair.py"),
             "--root", self.land, "--mask-root", self.land,
             "--dist-dir", self.dist, "--backup-dir", self.backup,
             "--pins", self.pins, "--manifest-inscope", self.man_in,
             "--manifest-other", self.man_other,
             "--gates", "B0", "F1", "F2", "G0", "G1", "G2", "G2p", "G6",
             "G7", "G8.2", "--obs"],
            capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def failing(self, out):
        return {line.split()[0] for line in out.splitlines()
                if " FAIL " in line}

    def cleanup(self):
        shutil.rmtree(self.tmp)


class RepairAndCheck(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()

    def tearDown(self):
        self.fx.cleanup()

    def test_correct_repair_passes_every_gate(self):
        r = self.fx.repair()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        code, out = self.fx.check()
        self.assertEqual(code, 0, out)
        with rasterio.open(os.path.join(self.fx.land,
                                        "VT_2020_balive.tif")) as s:
            a = s.read(1)
            self.assertEqual(s.tags(ns="IMAGE_STRUCTURE")["PREDICTOR"], "2")
        self.assertTrue((a[:, :12] == -9999).all())
        self.assertEqual(a[40, 30], 0)      # in-coverage zero survives

    def test_noop_fails(self):
        code, out = self.fx.check()
        self.assertEqual(code, 1)
        self.assertTrue({"G2", "G2p", "G7"} <= self.fx.failing(out), out)

    def test_inflated_mask_fails(self):
        self.fx.repair()
        p = os.path.join(self.fx.land, "VT_2020_tcc.tif")
        with rasterio.open(p, "r+") as s:
            a = s.read(1)
            a[:, 12:14] = -9999            # two extra in-coverage columns
            s.write(a, 1)
        code, out = self.fx.check()
        self.assertEqual(code, 1)
        self.assertIn("G1", self.fx.failing(out), out)

    def test_in_coverage_edit_fails(self):
        self.fx.repair()
        p = os.path.join(self.fx.land, "VT_2020_tsd.tif")
        with rasterio.open(p, "r+") as s:
            a = s.read(1)
            a[24, 24] = 1
            s.write(a, 1)
        code, out = self.fx.check()
        self.assertEqual(code, 1)
        self.assertIn("G1", self.fx.failing(out), out)

    def test_out_of_scope_change_fails(self):
        self.fx.repair()
        write(os.path.join(self.fx.land, "VT_2020_evt.tif"),
              np.full((H, W), 8))
        code, out = self.fx.check()
        self.assertEqual(code, 1)
        self.assertIn("F2", self.fx.failing(out), out)

    def test_repair_refuses_unpinned_mask(self):
        pins = json.load(open(self.fx.pins))
        pins["masks"]["VT"]["nlcd"]["inside"] += 1
        json.dump(pins, open(self.fx.pins, "w"))
        r = self.fx.repair()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("pin", r.stdout + r.stderr)


class Guards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tagged = os.path.join(self.tmp, "VT_2017_balive.tif")
        write(self.tagged, np.zeros((H, W)), GROUSE_REPAIR="CR-0010")
        self.plain = os.path.join(self.tmp, "VT_2016_balive.tif")
        write(self.plain, np.zeros((H, W)))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_legacy_checkpoint(self):
        with self.assertRaises(SystemExit):
            grouse_data.refuse_legacy_checkpoint_on_repaired(
                types.SimpleNamespace(missing_mask=False), [self.tagged])
        grouse_data.refuse_legacy_checkpoint_on_repaired(
            types.SimpleNamespace(missing_mask=True), [self.tagged])
        grouse_data.refuse_legacy_checkpoint_on_repaired(
            types.SimpleNamespace(missing_mask=False), [self.plain])


if __name__ == "__main__":
    unittest.main()
