"""Unit tests for symptom_check.py (CR-0009 v5 deliverable 1), on
synthetic maps, polygons, pairs and points. No data/ access, no GPU.

    python -m unittest tests.test_symptom_check -v

The real-data test is R: `python symptom_check.py --reproduce ...`
(CR-0009 v5 § symptom_check.py).
"""
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd
from rasterio.transform import Affine, from_origin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import symptom_check as sc  # noqa: E402

PINS = sc.load_pins()
REF = PINS["reference"]
CRS = "EPSG:5070"


def side_by_side(me_vals, nh_vals):
    """(n, 2) map: NH cells in column 0, ME cells in column 1."""
    arr = np.stack([np.asarray(nh_vals, np.float32),
                    np.asarray(me_vals, np.float32)], axis=1)
    me = np.zeros(arr.shape, bool)
    me[:, 1] = True
    return arr, me, ~me


class Item1(unittest.TestCase):
    def test_symmetric_map(self):
        rng = np.random.default_rng(1)
        v = rng.uniform(0, 1, 5000)
        r = sc.item1(*side_by_side(v, rng.permutation(v)))
        self.assertAlmostEqual(r["p_me_gt_nh"], 0.5, places=12)
        self.assertAlmostEqual(r["gap08_pp"], 0.0, places=12)

    def test_known_p_and_shares(self):
        # ME {0.9, 0.9, 0.3, 0.3}, NH {0.5, 0.5, 0.5, 0.85}:
        # ME > NH in 2*3 + 2*1... count: 0.9 beats all 4 (x2 = 8),
        # 0.3 beats none -> 8/16 = 0.5; >=0.8: ME 50 %, NH 25 %.
        r = sc.item1(*side_by_side([0.9, 0.9, 0.3, 0.3],
                                   [0.5, 0.5, 0.5, 0.85]))
        self.assertEqual(r["p_me_gt_nh"], 0.5)
        self.assertEqual((r["ME"]["ge08_pct"], r["NH"]["ge08_pct"]),
                         (50.0, 25.0))
        self.assertEqual(r["gap08_pp"], 25.0)

    def test_bimodal_me_in_1a_band_but_beyond_1b(self):
        """CR-0009's constructed attack: a bimodal Maine side keeps
        P(ME>NH) near 0.45 while its >=0.8 share is far above NH's."""
        rng = np.random.default_rng(2)
        n = 20000
        nh = rng.uniform(0.2, 0.7, n)
        k = int(0.45 * n)
        me = np.concatenate([rng.uniform(0.85, 0.95, k),
                             rng.uniform(0.0, 0.1, n - k)])
        r = sc.item1(*side_by_side(rng.permutation(me), nh))
        self.assertAlmostEqual(r["p_me_gt_nh"], 0.45, places=6)
        lo, hi = REF["1a_band"]
        self.assertTrue(lo <= r["p_me_gt_nh"] <= hi)
        self.assertAlmostEqual(r["gap08_pp"], 45.0, places=6)
        self.assertGreater(r["gap08_pp"], REF["1b_max_pp"])

    def test_nan_cells_excluded_and_counted(self):
        r = sc.item1(*side_by_side([0.9, np.nan, 0.1], [0.5, 0.5, np.nan]))
        self.assertEqual(r["nan_cells"], {"ME": 1, "NH": 1})
        self.assertEqual((r["ME"]["n"], r["NH"]["n"]), (2, 2))
        self.assertAlmostEqual(r["p_me_gt_nh"], 0.5)
        self.assertAlmostEqual(r["gap08_pp"], 50.0)

    def test_other_cells_excluded(self):
        arr = np.array([[0.1, 0.9, 0.5]], np.float32)
        me = np.array([[False, True, False]])
        nh = np.array([[True, False, False]])
        r = sc.item1(arr, me, nh)
        self.assertEqual(r["other_cells"], 1)
        self.assertEqual(r["p_me_gt_nh"], 1.0)

    def test_ties_count_half(self):
        self.assertEqual(sc.rank_prob([0.5, 0.5], [0.5]), 0.5)


class SideAssignment(unittest.TestCase):
    """Synthetic two-polygon county file: NH west half, ME east half."""

    @classmethod
    def setUpClass(cls):
        import geopandas as gpd
        from shapely.geometry import box
        cls.tmp = tempfile.TemporaryDirectory()
        cls.county = os.path.join(cls.tmp.name, "counties.gpkg")
        gpd.GeoDataFrame({"STATEFP": ["33", "23"]}, geometry=[
            box(0, 0, 50, 100), box(50, 0, 100, 100)],
            crs=CRS).to_file(cls.county)
        cls.tr = from_origin(0, 100, 10, 10)                # 10 x 10 cells

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pixels_by_centre(self):
        arr = np.zeros((10, 10), np.float32)
        arr[:, 5:] = 0.9                                    # ME side high
        arr[0, 7] = np.nan
        r = sc.run_item1(arr, self.tr, CRS, county_path=self.county)
        self.assertEqual((r["ME"]["n"], r["NH"]["n"]), (49, 50))
        self.assertEqual(r["nan_cells"], {"ME": 1, "NH": 0})
        self.assertEqual(r["p_me_gt_nh"], 1.0)
        self.assertEqual(r["gap08_pp"], 100.0)

    def test_points_within_first_match(self):
        from pyproj import Transformer
        t = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
        xs, ys = [25, 75, 150], [50, 50, 50]
        lon, lat = t.transform(xs, ys)
        pts = pd.DataFrame({"longitude": lon, "latitude": lat})
        self.assertEqual(list(sc.point_sides(pts, county_path=self.county)),
                         ["NH", "ME", "none"])


class Pairs(unittest.TestCase):
    def test_frozen_lookup_and_means(self):
        """Frozen pairs CSV -> grid cells by lon/lat; per-pair and mean
        differences with and without the investigation's rounding."""
        import rasterio
        from pyproj import Transformer
        with tempfile.TemporaryDirectory() as d:
            tif = os.path.join(d, "grid.tif")
            tr = from_origin(1000, 2000, 30, 30)
            with rasterio.open(tif, "w", driver="GTiff", height=20,
                               width=20, count=1, dtype="float32", crs=CRS,
                               transform=tr) as dst:
                dst.write(np.zeros((1, 20, 20), np.float32))
            t = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
            cells = {("ME", 0): (3, 4), ("NH", 0): (5, 6),
                     ("ME", 1): (10, 11), ("NH", 1): (12, 2)}
            recs = []
            for (side, p), (r, c) in cells.items():
                lon, lat = t.transform(*tr * (c + 0.5, r + 0.5))
                recs.append({"pair": p, "side": side, "lon": lon,
                             "lat": lat})
            csv = os.path.join(d, "pairs.csv")
            pd.DataFrame(recs).to_csv(csv, index=False)
            pairs = sc.load_frozen_pairs(csv)
            with rasterio.open(tif) as ref:
                got = sc.pairs_to_cells(pairs, ref)
        self.assertEqual(got, [((3, 4), (5, 6)), ((10, 11), (12, 2))])

        rows = [{"pair": 0, "side": "ME", "road_dist_m": 100.4,
                 "prob": 0.61234, "missing_at_centre": ""},
                {"pair": 0, "side": "NH", "road_dist_m": 50.6,
                 "prob": 0.41236, "missing_at_centre": ""},
                {"pair": 1, "side": "ME", "road_dist_m": 10.0,
                 "prob": 0.2, "missing_at_centre": "tsd"},
                {"pair": 1, "side": "NH", "road_dist_m": 30.0,
                 "prob": 0.3, "missing_at_centre": ""}]
        i2 = sc.item2_from_rows(rows)
        np.testing.assert_allclose(i2["diff_road_m"], [49.8, -20.0])
        self.assertEqual(i2["diff_road_m_recorded"], [49.0, -20.0])
        self.assertAlmostEqual(i2["mean_diff_road_m"], 14.9)
        self.assertEqual(i2["mean_diff_road_m_recorded"], 14.5)
        np.testing.assert_allclose(i2["diff_prob_recorded"], [0.1999, -0.1])
        self.assertAlmostEqual(i2["mean_diff_prob"], 0.04999)
        self.assertEqual(i2["cells_missing_input"], 1)

    def test_pair_with_nan_excluded_from_mean(self):
        rows = [{"pair": 0, "side": "ME", "v": 5.0},
                {"pair": 0, "side": "NH", "v": 2.0},
                {"pair": 1, "side": "ME", "v": np.nan},
                {"pair": 1, "side": "NH", "v": 1.0}]
        d = sc.pair_diffs(rows, "v")
        self.assertEqual(d[0], 3.0)
        self.assertTrue(np.isnan(d[1]))

    def test_matcher_rules(self):
        H, W = 4, 6
        sig = np.ones((5, H, W), np.int64)
        sig[:, 0, 3] = 2                   # an ME cell with no NH twin
        ch = np.full((H, W), 10.0)
        ch[:, 3:] = 11.0                   # |dch| 1 <= 2
        ch[1, 3:] = 20.0                   # |dch| 10 > 2
        zero = np.zeros((H, W))
        me = np.zeros((H, W), bool)
        me[:, 3:] = True
        pairs = sc.match_pairs(sig, ch, zero, zero, me, ~me, n_pairs=50)
        want = {(r, c) for r in range(H) for c in range(3, W)} - {
            (0, 3), (1, 3), (1, 4), (1, 5)}
        self.assertEqual({m for m, _ in pairs}, want)
        self.assertTrue(all(n[1] < 3 for _, n in pairs))
        self.assertEqual(pairs, sc.match_pairs(sig, ch, zero, zero, me, ~me,
                                               n_pairs=50))

    def test_bootstrap_interval_deterministic(self):
        d = [-549, -185, 490, 1154, 203, -155, 835, -171]
        a = sc.bootstrap_interval(d, seed=7)
        self.assertEqual(a, sc.bootstrap_interval(d, seed=7))
        self.assertNotEqual(a["lo95"], sc.bootstrap_interval(d, seed=8)["lo95"])
        self.assertEqual(a["mean"], 202.75)
        self.assertLess(a["lo95"], a["mean"])
        self.assertGreater(a["hi95"], a["mean"])
        self.assertEqual(sc.bootstrap_interval([1.0])["n_boot"], 0)


class Points(unittest.TestCase):
    def test_duplicate_record_refused(self):
        a = pd.DataFrame({"longitude": [-71.1, -71.0], "latitude": [44.8, 44.8],
                          "label": [1, 0]})
        b = pd.DataFrame({"longitude": [-71.1], "latitude": [44.8],
                          "label": [1]})
        with self.assertRaises(sc.GuardError):
            sc.union_point_set([a, b])
        self.assertEqual(len(sc.union_point_set([a])), 2)
        c = b.assign(label=0)          # same place, other label: allowed
        self.assertEqual(len(sc.union_point_set([a.iloc[:1], c])), 2)

    def test_auc_by_split_and_side(self):
        lab = np.array([1, 1, 0, 0, 1, 0])
        score = np.array([0.9, 0.8, 0.1, 0.2, 0.7, np.nan])
        side = np.array(["NH", "NH", "NH", "NH", "ME", "NH"])
        split = np.array(["train", "val", "train", "val", "train", "val"])
        b, off = sc.item3_blocks(lab, score, side, split)
        self.assertEqual(b["all/all"]["n"], 5)
        self.assertEqual(off, {"NH": 1, "ME": 0})
        self.assertEqual(b["NH/all"]["auc"], 1.0)
        self.assertEqual((b["NH/val"]["pos"], b["NH/val"]["neg"]), (1, 1))
        self.assertEqual((b["NH/train"]["pos"], b["NH/train"]["neg"]), (1, 1))
        self.assertNotIn("auc", b["ME/all"])               # one class only
        # A reversed ranking on the NH side gives AUC 0.
        b2, _ = sc.item3_blocks(lab, 1 - score, side, split)
        self.assertEqual(b2["NH/all"]["auc"], 0.0)


class Provenance(unittest.TestCase):
    def fake_scorer(self, fn):
        ref = Affine(30.0, 0.0, 0.0, 0.0, -30.0, 9000.0)
        return SimpleNamespace(ref=SimpleNamespace(transform=ref),
                               probs=lambda centres, amp: fn(centres))

    def setUp(self):
        ref = Affine(30.0, 0.0, 0.0, 0.0, -30.0, 9000.0)
        stride = 4
        self.tr = Affine(ref.a * stride, 0, ref.c + (32 - 2) * ref.a, 0,
                         ref.e * stride, ref.f + (32 - 2) * ref.e)
        self.arr = np.random.default_rng(0).uniform(0, 1, (10, 10)).astype(
            np.float32)
        # "The model": the value stored at the cell whose window centre is
        # (row, col).
        self.lookup = {(32 + gy * stride, 32 + gx * stride): self.arr[gy, gx]
                       for gy in range(10) for gx in range(10)}

    def test_same_model_passes(self):
        s = self.fake_scorer(lambda cs: [self.lookup[c] for c in cs])
        r = sc.spot_check(s, self.arr, self.tr)
        self.assertEqual(r["n"], 20)
        self.assertEqual(r["max_abs_diff"], 0.0)

    def test_map_from_another_model_refused(self):
        s = self.fake_scorer(lambda cs: [self.lookup[c] + 0.01 for c in cs])
        with self.assertRaises(sc.GuardError):
            sc.spot_check(s, self.arr, self.tr)

    def test_map_cell_to_source_inverts_predict_transform(self):
        ref = Affine(30.0, 0.0, -82558.24, 0.0, -30.0, 155719.14)
        for stride, r0, c0 in ((4, 1800, 3900), (8, 0, 0)):
            m = Affine(ref.a * stride, ref.b,
                       ref.c + (c0 + 32 - 0.5 * stride) * ref.a,
                       ref.d, ref.e * stride,
                       ref.f + (r0 + 32 - 0.5 * stride) * ref.e)
            g = np.arange(50)
            rows, cols = sc.map_cell_to_source(m, ref, g, g)
            np.testing.assert_array_equal(rows, r0 + 32 + g * stride)
            np.testing.assert_array_equal(cols, c0 + 32 + g * stride)

    def test_never_writes_under_data(self):
        with self.assertRaises(sc.GuardError):
            sc.refuse_data_path(os.path.join(sc.HERE, "data", "predictions"))
        sc.refuse_data_path(os.path.join(sc.HERE, "docs", "x"))


class Reproduction(unittest.TestCase):
    def test_equal_at_printed_precision(self):
        self.assertTrue(sc.equal_at_precision(0.539979, "0.5400"))
        self.assertFalse(sc.equal_at_precision(0.53994, "0.5400"))
        self.assertTrue(sc.equal_at_precision(202.75, "+202.75"))
        self.assertTrue(sc.equal_at_precision(5.357963, "5.36"))
        self.assertFalse(sc.equal_at_precision(float("nan"), "0.5"))

    def test_pins_reproduction_block(self):
        rp = PINS["reproduction"]
        self.assertEqual(set(rp["maps"]), {"gap3.pth", "bce.pth"})
        self.assertEqual(np.mean(rp["pairs"]["diff_road_m"]), 202.75)


class Rows(unittest.TestCase):
    def synthetic_results(self):
        rng = np.random.default_rng(3)
        i1 = sc.item1(*side_by_side(rng.uniform(0, 1, 100),
                                    rng.uniform(0, 1, 100)))
        rows = [{"pair": p, "side": s, "road_dist_m": 100.0 * p + (s == "ME"),
                 "prob": 0.5, "missing_at_centre": ""}
                for p in range(8) for s in ("ME", "NH")]
        blocks, off = sc.item3_blocks(np.array([1, 0, 1]),
                                      np.array([0.9, 0.1, 0.5]),
                                      np.array(["NH", "NH", "ME"]),
                                      np.array(["train", "val", "train"]))
        arr = rng.uniform(0, 1, (4, 4))
        zone = np.array([[0, 0, 23, 23]] * 4)
        zs = sc.zone_summary(arr, zone, np.zeros((4, 4), bool),
                             {0: "outside_US", 23: "ME"})
        return {"calibration": {"path": "cal.json", "kind": "Platt",
                                "model_path": "m.pth",
                                "fitted_on_this_model": True},
                "item1": i1, "item2": sc.item2_from_rows(rows),
                "rematch": {"n": 8, "same_cells": True},
                "item3": [{"point_set": "x", "points": 3, "on_map": 3,
                           "off_map_by_side": off, "blocks": blocks}],
                "item4": [{"region": "ME", "map": "m.tif", "shape": [4, 4],
                           "stride_px": 8,
                           "all": sc.zone_summary(arr, np.zeros((4, 4), int),
                                                  None, {0: "all"})["all"],
                           "coverage": zs, "by_state": zs}],
                "maps": [], "provenance": {
                    "utc": "t", "git": {"head": "h", "dirty_tracked": ""},
                    "device": "cpu", "argv": [], "model": "m.pth",
                    "sha256": {"m.pth": "0" * 64}}}

    def test_every_row_is_obs_with_pa0021f_fields(self):
        res = self.synthetic_results()
        rows = sc.build_rows(res, PINS)
        self.assertEqual({r["id"] for r in rows},
                         {"1a", "1b", "2a", "2b", "3", "4", "5"})
        for r in rows:
            self.assertEqual(r["type"], "OBS")
            for f in ("class", "subset", "null_population", "calibration",
                      "counts", "investigate_if"):
                self.assertTrue(r[f], (r["id"], f))
        text = "\n".join(sc.render(res, rows))
        self.assertNotIn("GATE", text)
        self.assertNotIn("false-fail", text.lower())
        self.assertEqual(text.count("null population:"), len(rows))


class Cli(unittest.TestCase):
    def test_missing_inputs_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            rc = sc.main(["--model", os.path.join(d, "none.pth"),
                          "--map", os.path.join(d, "none.tif"),
                          "--calibration", os.path.join(d, "c.json"),
                          "--pairs", os.path.join(d, "p.csv"),
                          "--out", d])
        self.assertEqual(rc, 2)

    def test_map_or_predict_required(self):
        with self.assertRaises(SystemExit):
            sc.main(["--model", "x.pth", "--calibration", "c",
                     "--pairs", "p", "--out", "/nonexistent"])


if __name__ == "__main__":
    unittest.main()
