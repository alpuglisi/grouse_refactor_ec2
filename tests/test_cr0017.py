"""CR-0017 implementation tests: pool step 6 (b), candidates within
BUFFER_M of the edge of the sightings' acquisition domain D are dropped.

    python -m unittest tests.test_cr0017 -v

Synthetic only: no county file is read. The domain is injected through
regions.domain_edge_m's `domain=` seam, or by patching regions'
county reader / D builder. Written from CR-0017 v3 section 2 and its test
plan; nothing here reads acceptance_split.py (CR-0013 design rule 4).
"""
import ast
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import numpy as np
import pandas as pd
import shapely

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import regions  # noqa: E402
import prepare_training_data as ptd  # noqa: E402
import generate_negatives as gn  # noqa: E402
from tests import test_cr0012 as t12  # noqa: E402

BUF = float(regions.BUFFER_M)
SQUARE = shapely.box(0.0, 0.0, 10_000.0, 10_000.0)


def identity_5070(lon, lat):
    return (np.atleast_1d(np.asarray(lon, dtype=np.float64)),
            np.atleast_1d(np.asarray(lat, dtype=np.float64)))


# ---------------------------------------------------------------------------
# regions.domain_edge_m
# ---------------------------------------------------------------------------
class EdgeDistance(unittest.TestCase):
    def test_inside_outside_boundary(self):
        x = np.array([1_000.0, 5_000.0, 9_950.0, -500.0, 20_000.0,
                      0.0, 10_000.0, 4_000.0])
        y = np.array([5_000.0, 5_000.0, 5_000.0, 5_000.0, 20_000.0,
                      5_000.0, 10_000.0, 0.0])
        got = regions.domain_edge_m(x, y, domain=SQUARE)
        self.assertEqual(got.dtype, np.float64)
        np.testing.assert_allclose(
            got, [1_000.0, 5_000.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    def test_interior_ring_is_an_edge(self):
        holed = SQUARE.difference(shapely.box(4_000, 4_000, 6_000, 6_000))
        got = regions.domain_edge_m([3_900.0, 5_000.0], [5_000.0, 5_000.0],
                                    domain=holed)
        np.testing.assert_allclose(got, [100.0, 0.0])

    def test_scalar_and_empty(self):
        self.assertEqual(regions.domain_edge_m(1.0, 2.0, domain=SQUARE).shape,
                         (1,))
        self.assertEqual(regions.domain_edge_m([], [], domain=SQUARE).shape,
                         (0,))
        with self.assertRaises(ValueError):
            regions.domain_edge_m([1.0, 2.0], [1.0], domain=SQUARE)


# ---------------------------------------------------------------------------
# generate_negatives.domain_edge_drop_mask: the <= BUFFER_M boundary
# ---------------------------------------------------------------------------
class DropThreshold(unittest.TestCase):
    def mask(self, x, y, domain=SQUARE):
        with mock.patch.object(gn, "to_5070", identity_5070):
            return gn.domain_edge_drop_mask(np.asarray(x, dtype=float),
                                            np.asarray(y, dtype=float),
                                            domain=domain)

    def test_exactly_buffer_dropped_just_beyond_kept(self):
        got = self.mask([BUF, BUF + 1e-6, 10_000.0 - BUF,
                         10_000.0 - BUF - 1e-6, 5_000.0],
                        [5_000.0] * 5)
        self.assertEqual(got.tolist(), [True, False, True, False, False])

    def test_outside_domain_dropped(self):
        got = self.mask([-1.0, -5_000.0, 15_000.0], [5_000.0] * 3)
        self.assertEqual(got.tolist(), [True, True, True])

    def test_empty(self):
        self.assertEqual(self.mask([], []).tolist(), [])

    def test_uses_to_5070_of_lonlat(self):
        # Real transform: a point at the domain's lon/lat corner edge.
        x, y = regions.to_5070([-71.0], [44.0])
        dom = shapely.box(x[0] - BUF, y[0] - 10_000, x[0] + 10_000,
                          y[0] + 10_000)
        self.assertEqual(
            gn.domain_edge_drop_mask(np.array([-71.0]), np.array([44.0]),
                                     domain=dom).tolist(), [True])
        dom = shapely.box(x[0] - BUF - 5, y[0] - 10_000, x[0] + 10_000,
                          y[0] + 10_000)
        self.assertEqual(
            gn.domain_edge_drop_mask(np.array([-71.0]), np.array([44.0]),
                                     domain=dom).tolist(), [False])


# ---------------------------------------------------------------------------
# Domain D: dissolved, one county reader, projected from the file CRS
# ---------------------------------------------------------------------------
def three_states(crs="EPSG:5070", drop=None):
    """Three adjacent 10 km 'states' (one county each, STATE_FIPS codes),
    plus a split of the middle state into two counties."""
    import geopandas as gpd
    fips = [regions.STATE_FIPS[r] for r in regions.REGIONS]
    geoms = [shapely.box(0, 0, 10_000, 10_000),
             shapely.box(10_000, 0, 20_000, 5_000),
             shapely.box(10_000, 5_000, 20_000, 10_000),
             shapely.box(20_000, 0, 30_000, 10_000)]
    codes = [fips[0], fips[1], fips[1], fips[2]]
    gdf = gpd.GeoDataFrame({"STATEFP": codes}, geometry=geoms, crs=crs)
    if drop is not None:
        gdf = gdf[gdf["STATEFP"] != drop].reset_index(drop=True)
    return "synthetic.zip", gdf


class DomainD(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(regions._DOMAIN_5070, clear=True)
        p.start()
        self.addCleanup(p.stop)

    POINTS = ([10_050.0, 20_100.0, 15_000.0, 25_000.0, 29_900.0],
              [5_000.0, 5_000.0, 5_050.0, 5_000.0, 5_000.0])

    def test_state_lines_are_not_edges(self):
        with mock.patch.object(regions, "_county_polygons", three_states):
            got = regions.domain_edge_m(*self.POINTS)
        # 50 m / 100 m from the ME|NH and NH|VT lines and 50 m from the
        # internal NH county line: the distance is to the outer edge.
        np.testing.assert_allclose(got, [5_000.0, 5_000.0, 4_950.0,
                                         5_000.0, 100.0])

    def test_undissolved_would_differ(self):
        # Guards the test above: per-state polygons (the wrong D) put the
        # state lines on the edge, so the first two points fall in the band.
        _, gdf = three_states()
        per_state = gdf.dissolve(by="STATEFP").geometry.to_numpy()
        got = [min(g.boundary.distance(shapely.Point(x, y))
                   for g in per_state if g.contains(shapely.Point(x, y)))
               for x, y in zip(*self.POINTS)]
        np.testing.assert_allclose(got, [50.0, 100.0, 4_950.0, 5_000.0,
                                         100.0])

    def test_projected_from_file_crs(self):
        import geopandas as gpd
        _, g5070 = three_states()
        g4269 = g5070.to_crs(4269)

        def reader():
            return "synthetic.zip", g4269.copy()

        with mock.patch.object(regions, "_county_polygons", reader):
            dom = regions._domain_5070()
        direct = shapely.union_all(
            gpd.GeoSeries(list(g4269.geometry), crs=4269).to_crs(5070)
            .to_numpy())
        self.assertTrue(dom.equals(direct))
        self.assertAlmostEqual(dom.area, 3e8, delta=3e8 * 1e-6)

    def test_missing_state_raises(self):
        fips = regions.STATE_FIPS["NH"]
        with mock.patch.object(regions, "_county_polygons",
                               lambda: three_states(drop=fips)):
            with self.assertRaises(RuntimeError) as cm:
                regions.domain_edge_m([1.0], [1.0])
        self.assertIn(fips, str(cm.exception))

    def test_cached(self):
        calls = []

        def reader():
            calls.append(1)
            return three_states()

        with mock.patch.object(regions, "_county_polygons", reader):
            regions.domain_edge_m([1.0], [1.0])
            regions.domain_edge_m([2.0], [2.0])
        self.assertEqual(len(calls), 1)

    def test_state_polygons_share_the_reader(self):
        with mock.patch.dict(regions._STATE_POLYGONS, clear=True), \
                mock.patch.object(regions, "_county_polygons",
                                  lambda: three_states(crs="EPSG:4269")):
            got = regions._state_polygons()
        self.assertEqual(sorted(got["region"]), sorted(regions.REGIONS))
        self.assertEqual(str(got.crs).upper(), "EPSG:4326")


class SourceShape(unittest.TestCase):
    """CR-0017 section 2 code rules, checked on the source."""

    def setUp(self):
        with open(os.path.join(ROOT, "regions.py")) as f:
            self.src = f.read()

    def test_one_county_reader(self):
        self.assertEqual(self.src.count('PATH_TEMPLATES["tiger_county"]'), 1)
        self.assertEqual(self.src.count("read_file("), 1)

    def test_no_module_level_geo_import(self):
        for node in ast.parse(self.src).body:
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for n in names:
                self.assertNotIn(n.split(".")[0],
                                 {"geopandas", "shapely", "pyogrio"})


# ---------------------------------------------------------------------------
# Pool step 6 in build(): drops = (a) union (b), on the synthetic tree
# ---------------------------------------------------------------------------
def region_domain():
    """Union of one box per synthetic region whose west edge is 3 km west
    of the region centre (so a strip of candidates is outside or in the
    band) and whose other edges lie just beyond the candidates."""
    boxes = []
    for cx, cy in t12.region_centres_5070().values():
        boxes.append(shapely.box(cx - 3_000, cy - 9_000, cx + 9_000,
                                 cy + 9_000))
    return shapely.union_all(boxes)


def independent_edge_m(lon, lat, dom):
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    x, y = t.transform(np.asarray(lon, float), np.asarray(lat, float))
    edge = dom.boundary
    return np.array([edge.distance(shapely.Point(a, b))
                     if dom.contains(shapely.Point(a, b)) else 0.0
                     for a, b in zip(x, y)])


class Step6Union(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        cls.bad = t12.build_tree(cls.d, seed=3)
        vp = t12.fake_verify_partition(cls.bad)
        far = shapely.box(-1e8, -1e8, 1e8, 1e8)
        cls.dom = region_domain()
        pool_rel = "data/negatives/candidate_pool.csv"
        man_rel = "data/pipeline/split_manifest.json"

        with mock.patch.object(gn, "verify_partition", vp), \
                redirect_stdout(io.StringIO()):
            ptd.run(cls.d)
        with mock.patch.object(gn, "verify_partition", vp), \
                mock.patch.object(regions, "_domain_5070", lambda: far), \
                redirect_stdout(io.StringIO()):
            gn.run(cls.d)
        cls.base = t12.output_bytes(cls.d)

        cls.spy = {}
        real_a, real_b = gn.buffer_drop_mask, gn.domain_edge_drop_mask

        def spy_a(clon, clat, slon, slat, **kw):
            out = real_a(clon, clat, slon, slat, **kw)
            cls.spy["a"] = (np.array(clon), np.array(clat), out.copy())
            return out

        def spy_b(lon, lat, domain=None):
            out = real_b(lon, lat, domain=domain)
            cls.spy["b"] = (np.array(lon), np.array(lat), out.copy())
            return out

        buf = io.StringIO()
        with mock.patch.object(gn, "verify_partition", vp), \
                mock.patch.object(regions, "_domain_5070",
                                  lambda: cls.dom), \
                mock.patch.object(gn, "buffer_drop_mask", spy_a), \
                mock.patch.object(gn, "domain_edge_drop_mask", spy_b), \
                redirect_stdout(buf):
            gn.run(cls.d)
        cls.log = buf.getvalue()
        cls.new = t12.output_bytes(cls.d)
        cls.pool_rel, cls.man_rel = pool_rel, man_rel

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d)

    def counts(self, out):
        return json.loads(out[self.man_rel])["negatives"]["counts"]

    def test_fixture_not_vacuous(self):
        a = self.spy["a"][2]
        b = self.spy["b"][2]
        self.assertGreater(int((a & ~b).sum()), 0)
        self.assertGreater(int((b & ~a).sum()), 0)
        self.assertGreater(int((a & b).sum()), 0)
        self.assertGreater(int((~a & ~b).sum()), 0)

    def test_both_masks_see_the_same_step5_pool(self):
        np.testing.assert_array_equal(self.spy["a"][0], self.spy["b"][0])
        np.testing.assert_array_equal(self.spy["a"][1], self.spy["b"][1])

    def test_count6_is_step5_minus_union(self):
        lon, _, a = self.spy["a"]
        b = self.spy["b"][2]
        c = self.counts(self.new)
        tot5 = sum(c[r]["5"] for r in regions.REGIONS)
        tot6 = sum(c[r]["6"] for r in regions.REGIONS)
        self.assertEqual(tot5, len(lon))
        self.assertEqual(tot6, tot5 - int((a | b).sum()))
        base = self.counts(self.base)
        for r in regions.REGIONS:
            for k in ("1", "2", "3", "4", "5"):
                self.assertEqual(c[r][k], base[r][k])

    def test_log_prints_three_counts(self):
        a = self.spy["a"][2]
        b = self.spy["b"][2]
        m = re.search(r"([\d,]+) within \d+ m of a grouse location dropped "
                      r"\(a\); ([\d,]+) more within \d+ m of the "
                      r"acquisition-domain edge dropped \(b only\); "
                      r"([\d,]+) in both", self.log)
        self.assertIsNotNone(m, self.log)
        got = [int(g.replace(",", "")) for g in m.groups()]
        self.assertEqual(got, [int(a.sum()), int((b & ~a).sum()),
                               int((a & b).sum())])

    def test_pool_is_old_pool_minus_edge_rows(self):
        old_lines = self.base[self.pool_rel].decode().splitlines()
        new_lines = self.new[self.pool_rel].decode().splitlines()
        self.assertEqual(old_lines[0], new_lines[0])
        old = pd.read_csv(io.BytesIO(self.base[self.pool_rel]),
                          float_precision="round_trip")
        e = independent_edge_m(old["longitude"], old["latitude"], self.dom)
        self.assertGreater(int((e <= regions.BUFFER_M).sum()), 0)
        self.assertGreater(float(np.min(np.abs(e - regions.BUFFER_M))),
                           1e-3)   # no row sits on the threshold
        keep = [ln for ln, drop in zip(old_lines[1:],
                                       e <= regions.BUFFER_M) if not drop]
        self.assertEqual(new_lines[1:], keep)

    def test_no_selected_negative_in_band(self):
        for r in regions.REGIONS:
            rel = os.path.relpath(
                os.path.join(self.d, t12.PATH_TEMPLATES["negatives"].format(
                    region=r)), self.d)
            neg = pd.read_csv(io.BytesIO(self.new[rel]),
                              float_precision="round_trip")
            e = independent_edge_m(neg["longitude"], neg["latitude"],
                                   self.dom)
            self.assertTrue((e > regions.BUFFER_M).all(), r)
            self.assertTrue((neg["label"] == 0).all())


if __name__ == "__main__":
    unittest.main()
