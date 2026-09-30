"""CR-0014 unit tests (U1-U4) for generate_road_distance.py: atomic
download, poisoned-cache recovery, the Canada rule and the densified
county footprint.

    python -m unittest tests.test_cr0014 -v
"""
import io
import os
import shutil
import sys
import tempfile
import types
import unittest
import zipfile
from unittest import mock

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import generate_road_distance as g  # noqa: E402

H, W = 20, 400
TR = from_origin(0, H * 30, 30, 30)


def write(path, arr):
    with rasterio.open(path, "w", driver="GTiff", height=H, width=W, count=1,
                       dtype="int16", crs="EPSG:5070", transform=TR,
                       nodata=-9999) as d:
        d.write(arr.astype("int16"), 1)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.txt", "x" * 5000)
        self.good = buf.getvalue()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def src(self, data, name):
        p = os.path.join(self.tmp, name)
        with open(p, "wb") as f:
            f.write(data)
        return "file://" + p


class U1U2Download(Tmp):
    def test_interrupted_download_leaves_nothing_then_refetches(self):
        dst = os.path.join(self.tmp, "cache", "x.zip")

        def dies(url, path):
            with open(path, "wb") as f:
                f.write(self.good[:30])
            raise KeyboardInterrupt

        with mock.patch.object(g.urllib.request, "urlretrieve", dies):
            with self.assertRaises(KeyboardInterrupt):
                g._download("http://x/x.zip", dst)
        self.assertFalse(os.path.exists(dst))
        self.assertFalse(os.path.exists(dst + ".part"))
        g._download(self.src(self.good, "good.zip"), dst)
        self.assertTrue(g._zip_ok(dst))

    def test_truncated_download_rejected(self):
        dst = os.path.join(self.tmp, "x.zip")
        with self.assertRaises(RuntimeError):
            g._download(self.src(self.good[:100], "t.zip"), dst)
        self.assertFalse(os.path.exists(dst))
        self.assertFalse(os.path.exists(dst + ".part"))

    def test_poisoned_cache_refetched(self):
        dst = os.path.join(self.tmp, "x.zip")
        with open(dst, "wb") as f:
            f.write(self.good[:40])
        g._download(self.src(self.good, "good.zip"), dst)
        self.assertTrue(g._zip_ok(dst))


class U3CanadaRule(Tmp):
    """US coverage on columns 0-299, one road along column 0, land beyond
    column 300. A pixel at column c is ~30c m from the road and ~30(300-c)
    m from Canadian land, so c > 150 becomes nodata."""

    def run_rule(self, evt):
        template = os.path.join(self.tmp, "tmpl.tif")
        write(template, np.zeros((H, W)))
        evt_path = os.path.join(self.tmp, "evt.tif")
        write(evt_path, evt)
        x0, y1 = 0.0, H * 30.0
        roads = types.SimpleNamespace(
            geometry=[LineString([(15, 0), (15, y1)])])
        cov = [box(x0, 0, 300 * 30.0, y1)]
        enc, dist, *_, n = g.build_distance_raster(
            roads, template, pad_px=0, coverage=cov, land_evt_path=evt_path)
        return enc, n

    def test_land_nearer_than_road_is_nodata(self):
        evt = np.full((H, W), 7555)
        enc, n = self.run_rule(evt)
        row = enc[10]
        self.assertTrue((row[300:] == -9999).all())          # outside US
        self.assertTrue((row[160:300] == -9999).all())       # Canada rule
        self.assertTrue((row[:140] != -9999).all())          # road nearer
        self.assertEqual(n, int((enc[:, :300] == -9999).sum()))

    def test_water_is_not_land(self):
        evt = np.full((H, W), 7292)                          # open water
        enc, n = self.run_rule(evt)
        self.assertEqual(n, 0)
        self.assertTrue((enc[:, :300] != -9999).all())

    def test_no_land_at_all(self):
        enc, n = self.run_rule(np.full((H, W), -9999))
        self.assertEqual(n, 0)


class U4Densify(unittest.TestCase):
    def test_densified_selection_is_superset(self):
        import geopandas as gpd
        counties = gpd.GeoDataFrame(
            {"STATEFP": ["50", "33"], "COUNTYFP": ["001", "003"]},
            geometry=[box(-73.3, 43.0, -72.5, 45.0),
                      box(-72.4, 43.0, -71.5, 45.0)], crs="EPSG:4326")
        bounds = (1.80e6, 2.40e6, 1.95e6, 2.60e6)          # EPSG:5070 metres
        got = g.counties_for_grid(counties, bounds, "EPSG:5070")
        plain = counties[counties.intersects(
            gpd.GeoSeries([box(*bounds)], crs="EPSG:5070")
            .to_crs(counties.crs).iloc[0])]
        self.assertTrue(set(plain["COUNTYFP"]) <= set(got["COUNTYFP"]))


if __name__ == "__main__":
    unittest.main()
