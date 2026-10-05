"""CR-0034: Earth Engine downloads requested on each source's own grid
(BUG-0094). Synthetic rasters and a fake Earth Engine only; no network,
no data/ access.

The fake serves a categorical source on an EPSG:5070 lattice whose pixel
edges sit at odd multiples of 15 m (as NLCD/TCC/TreeMap do) and answers
getDownloadURL by nearest-neighbour with ties broken to the south-east -
the behaviour measured on the real service
(docs/quality/evidence/CR-0032/source_lattice_NH.txt).

Written before approval (CR-0011 A3). Run with
    python -m unittest tests.test_cr0034
"""
import io
import math
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import download_tcc_nlcd as dtn  # noqa: E402

LOCAL_ALBERS = ("+proj=aea +lat_0=44 +lon_0=-71.5 +lat_1=43 +lat_2=45 "
                "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
NODATA = -9999
CLASSES = np.array([11, 21, 22, 41, 42, 43, 52, 71, 81, 90, 95], np.int16)
# A source CRS that is NOT EPSG:5070 (NLCD's native CRS is a custom Albers
# WKT): a hard-coded "EPSG:5070" anywhere on the path misplaces its pixels
# by kilometres (CR-0034 reviews B34-2/A34-2).
CUSTOM_ALBERS = ("+proj=aea +lat_0=23 +lon_0=-96 +lat_1=29.5 +lat_2=45.5 "
                 "+x_0=1000 +y_0=-500 +datum=WGS84 +units=m +no_defs")
MASKED = -1          # year_image's unmask marker


class FakeEE:
    class EEException(Exception):
        pass

    @staticmethod
    def Projection(crs):
        return ("proj", crs)

    class Geometry:
        @staticmethod
        def Rectangle(coords, proj=None, geodesic=True):
            return ("rect", tuple(coords), proj, geodesic)


class Source:
    """A synthetic source on a lattice (origin sx0, sy0) in `crs`."""
    def __init__(self, sx0, sy0, w, h, seed=0, crs="EPSG:5070"):
        self.sx0, self.sy0, self.w, self.h = sx0, sy0, w, h
        self.crs = crs
        rng = np.random.default_rng(seed)
        self.a = CLASSES[rng.integers(0, len(CLASSES), (h, w))]

    def sample(self, X, Y):
        """Nearest pixel; a centre exactly on an edge takes the pixel to
        the east / south (floor) - BUG-0094's tie rule."""
        col = np.floor((X - self.sx0) / 30.0).astype(int)
        row = np.floor((self.sy0 - Y) / 30.0).astype(int)
        ok = (col >= 0) & (col < self.w) & (row >= 0) & (row < self.h)
        out = np.full(X.shape, MASKED, np.int16)
        out[ok] = self.a[row[ok], col[ok]]
        return out

    def write(self, path):
        with rasterio.open(path, "w", driver="GTiff", height=self.h,
                           width=self.w, count=1, dtype="int16",
                           crs=self.crs,
                           transform=from_origin(self.sx0, self.sy0, 30, 30),
                           nodata=NODATA) as dst:
            dst.write(self.a, 1)


class FakeImage:
    """getDownloadURL -> token; fake_get renders the GeoTIFF."""
    def __init__(self, source, store, x_skew=0.0):
        self.source, self.store, self.x_skew = source, store, x_skew

    def select(self, *a, **k):
        return self

    def unmask(self, *a, **k):
        return self

    def toFloat(self):
        return self

    def getDownloadURL(self, params):
        token = f"https://fake.invalid/{len(self.store)}"
        self.store[token] = (self, params)
        return token


def make_fake_get(store, calls=None):
    def fake_get(url, timeout=None):
        img, p = store[url]
        if calls is not None:
            calls.append(p)
        from rasterio.crs import CRS
        # the fake serves only the source's own CRS (a copy, never a
        # reprojection): a request in any other CRS is a test failure
        assert CRS.from_user_input(p["crs"]) == \
            CRS.from_user_input(img.source.crs), p["crs"]
        a, _, c, _, e, f = p["crs_transform"]
        _, (x0, y0, x1, y1), _, _ = p["region"]
        w, h = int(round((x1 - x0) / a)), int(round((y1 - y0) / -e))
        cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
        X, Y = c + cols * a, f + rows * e
        arr = img.source.sample(X, Y)
        buf = MemoryFile()
        with buf.open(driver="GTiff", height=h, width=w, count=1,
                      dtype="int16", crs=p["crs"],
                      transform=from_origin(c + img.x_skew, f, a, -e)) as d:
            d.write(arr, 1)
        resp = mock.Mock(status_code=200, content=buf.read())
        resp.raise_for_status = lambda: None
        return resp
    return fake_get


def write_template(path, n=100):
    with rasterio.open(path, "w", driver="GTiff", height=n, width=n,
                       count=1, dtype="int16", crs=LOCAL_ALBERS,
                       transform=from_origin(-1500.0, 1500.0, 30, 30),
                       nodata=NODATA) as dst:
        dst.write(np.full((n, n), 7, np.int16), 1)


def source_around(template, margin=4000, crs="EPSG:5070"):
    """A source on a 15-m-offset lattice covering the template + margin."""
    with rasterio.open(template) as t:
        l, b, r, top = transform_bounds(t.crs, crs, *t.bounds,
                                        densify_pts=21)
    sx0 = math.floor((l - margin) / 30) * 30 + 15
    sy0 = math.ceil((top + margin) / 30) * 30 + 15
    w = int((r - l + 2 * margin) / 30) + 4
    h = int((top - b + 2 * margin) / 30) + 4
    return Source(sx0, sy0, w, h, crs=crs)


class Base(unittest.TestCase):
    SRC_CRS = "EPSG:5070"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.template = os.path.join(self.tmp, "tpl.tif")
        write_template(self.template)
        self.src = source_around(self.template, crs=self.SRC_CRS)
        self.grid = {"crs": self.SRC_CRS, "x0": float(self.src.sx0),
                     "y0": float(self.src.sy0)}
        with rasterio.open(self.template) as t:
            self.bounds = transform_bounds(t.crs, "EPSG:4326", *t.bounds,
                                           densify_pts=21)

    def expected(self):
        """The source warped straight onto the template (one nearest
        step), masked as build_raster masks it."""
        from realign_rasters import warp_to_grid
        p = os.path.join(self.tmp, "src.tif")
        self.src.write(p)
        out = os.path.join(self.tmp, "expected.tif")
        warp_to_grid(p, self.template, out)
        with rasterio.open(out) as s:
            return s.read(1)

    def build(self, grid, x_skew=0.0):
        store = {}
        img = FakeImage(self.src, store, x_skew)
        out = os.path.join(self.tmp, "NH_2025_nlcd.tif")
        spec = dtn.PRODUCTS["nlcd"]
        with mock.patch.object(dtn, "year_image",
                               return_value=(img, "b1")), \
             mock.patch.object(dtn, "year_native_grid",
                               return_value=grid), \
             mock.patch.object(dtn.requests, "get", make_fake_get(store)), \
             mock.patch("builtins.print"):
            dtn.build_raster(FakeEE, "nlcd", spec, "cid", 2025,
                             self.bounds, out, 96000, workers=1,
                             template=self.template, coverage_path=None)
        with rasterio.open(out) as s:
            self.tags = s.tags()
            return s.read(1)


def agreement(a, b):
    v = (a != NODATA) & (b != NODATA)
    return float((a[v] == b[v]).mean()) if v.any() else 0.0


class G1ParseNativeGrid(unittest.TestCase):
    def test_accepts_north_up_30m(self):
        g = dtn.parse_native_grid({"crs": "EPSG:5070",
                                   "transform": [30, 0, -2361585, 0, -30,
                                                 3177435.0000000037]})
        self.assertEqual(g["crs"], "EPSG:5070")
        self.assertAlmostEqual(g["x0"] % 30, 15.0, places=4)
        self.assertAlmostEqual(g["y0"] % 30, 15.0, places=4)

    def test_wkt_when_no_epsg(self):
        g = dtn.parse_native_grid({"wkt": 'PROJCS["AEA WGS84"]',
                                   "transform": [30, 0, -2415585, 0, -30,
                                                 3314805]})
        self.assertEqual(g["crs"], 'PROJCS["AEA WGS84"]')

    def test_refusals(self):
        for info in ({"crs": "EPSG:5070", "transform": [30, 1, 0, 0, -30, 0]},
                     {"crs": "EPSG:5070", "transform": [10, 0, 0, 0, -10, 0]},
                     {"crs": "EPSG:5070"},
                     {"transform": [30, 0, 0, 0, -30, 0]}):
            with self.subTest(info=info), self.assertRaises(ValueError):
                dtn.parse_native_grid(info)


class G2RegionGrid(unittest.TestCase):
    def test_snaps_to_lattice_and_covers(self):
        grid = {"crs": "EPSG:5070", "x0": -2415585.0, "y0": 3314805.0}
        b = (-71.8, 44.0, -71.2, 44.4)
        x0, y0, x1, y1 = dtn.region_grid(b, grid=grid)
        for v in (x0, y0, x1, y1):
            self.assertAlmostEqual(v % 30, 15.0, places=6)
        from pyproj import Transformer
        xs, ys = Transformer.from_crs("EPSG:4326", "EPSG:5070",
                                      always_xy=True).transform(
            [b[0], b[0], b[2], b[2]], [b[1], b[3], b[1], b[3]])
        self.assertTrue(x0 <= min(xs) and x1 >= max(xs))
        self.assertTrue(y0 <= min(ys) and y1 >= max(ys))

    def test_grid_required(self):
        with self.assertRaises(TypeError):
            dtn.region_grid((-71.8, 44.0, -71.2, 44.4))


class G3FetchTile(unittest.TestCase):
    def test_params_carry_source_crs(self):
        store, calls = {}, []
        src = Source(15, 615, 40, 40)
        img = FakeImage(src, store)
        rect = (15.0, 15.0, 615.0, 615.0)
        with mock.patch.object(dtn.requests, "get",
                               make_fake_get(store, calls)):
            dest = os.path.join(tempfile.mkdtemp(), "t.tif")
            dtn.fetch_tile(FakeEE, img, rect, dest, crs="EPSG:5070")
        p = calls[0]
        self.assertEqual(p["crs"], "EPSG:5070")
        self.assertEqual(list(p["crs_transform"]), [30, 0, 15.0, 0, -30, 615.0])
        self.assertEqual(p["region"][1], rect)
        self.assertEqual(p["region"][2], ("proj", "EPSG:5070"))
        with rasterio.open(dest) as s:      # an exact copy of the source
            self.assertTrue((s.read(1) == src.a[:20, :20]).all())

    def test_wkt_crs_passed_verbatim(self):
        """NLCD's native CRS is a WKT, not an EPSG code: fetch_tile must
        send the source's own CRS, not a hard-coded one."""
        from rasterio.crs import CRS
        wkt = CRS.from_epsg(5070).to_wkt()
        store, calls = {}, []
        img = FakeImage(Source(15, 615, 40, 40), store)
        with mock.patch.object(dtn.requests, "get",
                               make_fake_get(store, calls)):
            dtn.fetch_tile(FakeEE, img, (15.0, 15.0, 615.0, 615.0),
                           os.path.join(tempfile.mkdtemp(), "t.tif"),
                           crs=wkt)
        self.assertEqual(calls[0]["crs"], wkt)
        self.assertEqual(calls[0]["region"][2], ("proj", wkt))

    def test_crs_required(self):
        with self.assertRaises(TypeError):
            dtn.fetch_tile(FakeEE, None, (0, 0, 30, 30), "x")


class G4EndToEnd(Base):
    def test_registered_with_source(self):
        got = self.build(self.grid)
        self.assertGreaterEqual(agreement(got, self.expected()), 0.99)
        self.assertEqual(self.tags.get("GROUSE_GRID"), "native-lattice")
        self.assertEqual(self.tags.get("GROUSE_SOURCE"), "cid 2025")


class G4EndToEndCustomCrs(G4EndToEnd):
    SRC_CRS = CUSTOM_ALBERS


class G5Control(Base):
    """The simulation detects BUG-0094: the 0-origin lattice shifts."""
    def test_zero_origin_grid_is_shifted(self):
        zero = {"crs": "EPSG:5070", "x0": 0.0, "y0": 0.0}
        got = self.build(zero)
        self.assertLess(agreement(got, self.expected()), 0.6)


class G6LatticeCheck(Base):
    def test_off_lattice_mosaic_refused(self):
        with self.assertRaises(RuntimeError):
            self.build(self.grid, x_skew=15.0)

    def test_float_noise_below_lattice_accepted(self):
        """A lattice value a hair below a multiple of 30 is on the lattice
        (review A34-5)."""
        from rasterio.transform import Affine
        g = {"crs": "EPSG:5070", "x0": 15.0, "y0": 3177435.0000000037}
        dtn.check_on_lattice(Affine(30, 0, 45.0 - 1e-9, 0, -30,
                                    3177435.0), g, "t")


class G8CommonGrid(unittest.TestCase):
    def info(self, x0, y0, crs="EPSG:5070"):
        return {"crs": crs, "transform": [30, 0, x0, 0, -30, y0]}

    def test_same_lattice_accepted(self):
        g = dtn.common_native_grid([self.info(15, 615), self.info(9015, 315)],
                                   "t")
        self.assertEqual((g["x0"], g["y0"]), (15.0, 615.0))

    def test_refusals(self):
        cases = ([],
                 [self.info(15, 615), self.info(0, 615)],
                 [self.info(15, 615), self.info(15, 615, CUSTOM_ALBERS)])
        for infos in cases:
            with self.subTest(n=len(infos)), self.assertRaises(ValueError):
                dtn.common_native_grid(infos, "t")


class FakeCollection:
    """ImageCollection stand-in recording filterBounds; images carry
    projection infos."""
    def __init__(self, infos, log):
        self.infos, self.log = infos, log

    def filter(self, *a):
        return self

    def filterBounds(self, geom):
        self.log.append(geom)
        return self

    def size(self):
        return mock.Mock(getInfo=lambda: len(self.infos))


class G9NativeGridFromEE(unittest.TestCase):
    """year_native_grid / vintage_native_grid read every image that
    intersects the region (reviews B34-1, A34-1, B34-4)."""
    def fake_ee(self, infos, log, as_image=False):
        ee = mock.Mock()
        ee.EEException = FakeEE.EEException
        ee.Geometry = FakeEE.Geometry
        col = FakeCollection(infos, log)
        if as_image:
            col.size = lambda: mock.Mock(getInfo=mock.Mock(
                side_effect=FakeEE.EEException("not a collection")))
        ee.ImageCollection.return_value = col
        ee.Image.return_value.projection.return_value.getInfo.return_value = \
            infos[0] if infos else {}
        ee.Filter = mock.Mock()
        return ee

    def test_year_grid_filters_bounds_and_checks_all(self):
        log = []
        infos = [{"crs": "EPSG:5070", "transform": [30, 0, 15, 0, -30, 615]}]
        ee = self.fake_ee(infos, log)
        with mock.patch.object(dtn, "subset_projections",
                               lambda ee_, sub: sub.infos):
            g = dtn.year_native_grid(ee, "cid", 2025, (-72, 43, -71, 44))
        self.assertEqual(g["x0"], 15.0)
        w, so, e, n = log[0][1]      # padded around the region (A34-2-1)
        self.assertTrue(w < -72 and so < 43 and e > -71 and n > 44)
        self.assertTrue(w > -72.2 and n < 44.1)

    def test_year_grid_refuses_mixed(self):
        infos = [{"crs": "EPSG:5070", "transform": [30, 0, 15, 0, -30, 615]},
                 {"crs": "EPSG:5070", "transform": [30, 0, 0, 0, -30, 600]}]
        ee = self.fake_ee(infos, [])
        with mock.patch.object(dtn, "subset_projections",
                               lambda ee_, sub: sub.infos), \
             self.assertRaises(ValueError):
            dtn.year_native_grid(ee, "cid", 2025, (-72, 43, -71, 44))

    def test_vintage_grid_collection_and_image(self):
        import download_treemap as dtm
        infos = [{"crs": "EPSG:5070", "transform": [30, 0, 15, 0, -30, 615]}]
        for as_image in (False, True):
            with self.subTest(as_image=as_image):
                log = []
                ee = self.fake_ee(infos, log, as_image)
                with mock.patch.object(dtm, "subset_projections",
                                       lambda ee_, sub: sub.infos):
                    g = dtm.vintage_native_grid(ee, 2022, (-72, 43, -71, 44))
                self.assertEqual((g["x0"], g["y0"]), (15.0, 615.0))
                self.assertEqual(bool(log), not as_image)


class G7TreeMap(Base):
    def test_shares_the_fixed_functions(self):
        import download_treemap as dtm
        self.assertIs(dtm.region_grid, dtn.region_grid)
        self.assertIs(dtm.tiles, dtn.tiles)
        self.assertIs(dtm.fetch_tile, dtn.fetch_tile)

    def test_off_lattice_refused(self):
        import download_treemap as dtm
        store = {}
        img = FakeImage(self.src, store, x_skew=15.0)
        out = os.path.join(self.tmp, "TreeMap2022_NH_BALIVE.tif")
        with mock.patch.object(dtn.requests, "get", make_fake_get(store)), \
             mock.patch("builtins.print"), self.assertRaises(RuntimeError):
            dtm.build_raster(FakeEE, img, "BALIVE", self.bounds, out, 48000,
                             workers=1, grid=self.grid)
        self.assertFalse(os.path.exists(out))

    def test_raw_download_is_an_exact_copy(self):
        import download_treemap as dtm
        store = {}
        img = FakeImage(self.src, store)
        out = os.path.join(self.tmp, "TreeMap2022_NH_BALIVE.tif")
        with mock.patch.object(dtn.requests, "get", make_fake_get(store)), \
             mock.patch("builtins.print"):
            dtm.build_raster(FakeEE, img, "BALIVE", self.bounds, out, 48000,
                             workers=1, grid=self.grid)
        with rasterio.open(out) as s:
            a, t = s.read(1), s.transform
            from rasterio.crs import CRS
            self.assertEqual(s.crs, CRS.from_user_input(self.SRC_CRS))
            self.assertEqual(s.tags().get("GROUSE_GRID"), "native-lattice")
        self.assertAlmostEqual((t.c - self.src.sx0) % 30, 0.0, places=6)
        c0 = int(round((t.c - self.src.sx0) / 30))
        r0 = int(round((self.src.sy0 - t.f) / 30))
        want = self.src.a[r0:r0 + a.shape[0], c0:c0 + a.shape[1]]
        self.assertTrue((a == want.astype(a.dtype)).all())


class G10ExactWarp(unittest.TestCase):
    """realign_rasters.warp_to_grid takes, for every template cell, the
    source pixel containing the cell centre - on a 60 km rotated grid,
    where GDAL's default approximate transformer (0.125 px) misses ~7 %
    (BUG-0095)."""
    def test_large_rotated_grid(self):
        from pyproj import Transformer
        from realign_rasters import warp_to_grid
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        n, half = 2000, 30000.0
        tpl = os.path.join(tmp, "tpl.tif")
        with rasterio.open(tpl, "w", driver="GTiff", height=n, width=n,
                           count=1, dtype="int16", crs=LOCAL_ALBERS,
                           transform=from_origin(-half, half, 30, 30),
                           nodata=NODATA) as d:
            d.write(np.zeros((n, n), np.int16), 1)
        src = source_around(tpl, margin=3000)
        sp = os.path.join(tmp, "src.tif")
        src.write(sp)
        out = os.path.join(tmp, "out.tif")
        warp_to_grid(sp, tpl, out)
        rng = np.random.default_rng(0)
        r, c = rng.integers(0, n, 3000), rng.integers(0, n, 3000)
        X, Y = Transformer.from_crs(LOCAL_ALBERS, "EPSG:5070",
                                    always_xy=True).transform(
            -half + (c + 0.5) * 30, half - (r + 0.5) * 30)
        truth = src.sample(np.asarray(X), np.asarray(Y))
        with rasterio.open(out) as o:
            got = o.read(1)[r, c]
        self.assertEqual(float((got == truth).mean()), 1.0)


class G11RepairPathWarpsExact(unittest.TestCase):
    """Every WarpedVRT on the repair path passes the exact tolerance
    realign_rasters.WARP_TOLERANCE_PX (<= 1e-6 px) (BUG-0095);
    generate_treemap_features' warp sits inside write_vintage, so it is
    pinned in the source."""
    def test_tolerance_exact(self):
        import ast
        import realign_rasters
        self.assertLessEqual(realign_rasters.WARP_TOLERANCE_PX, 1e-6)
        for name in ("realign_rasters.py", "generate_treemap_features.py"):
            tree = ast.parse(open(os.path.join(REPO, name)).read())
            calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and getattr(n.func, "id", getattr(n.func, "attr", ""))
                     == "WarpedVRT"]
            self.assertTrue(calls, name)
            for call in calls:
                with self.subTest(file=name, line=call.lineno):
                    kw = {k.arg: k.value for k in call.keywords}
                    self.assertIn("tolerance", kw)
                    self.assertEqual(getattr(kw["tolerance"], "id", None),
                                     "WARP_TOLERANCE_PX")


class G7TreeMapCustomCrs(G7TreeMap):
    SRC_CRS = CUSTOM_ALBERS


if __name__ == "__main__":
    unittest.main()
