"""CR-0036 acceptance tests (written before approval, CR-0011 A3).

Two groups:
  GateTests       check_lidar_structure.py: every gate passes on a good
                  synthetic world and REJECTS its negative control
                  (PA-0021(a)); edge cases fail rather than pass.
  GeneratorTests  generate_lidar_structure.py's pure functions against
                  brute-force oracles. They skip until CR-0036 deliverable
                  2 lands the generator; deliverable 2 removes the skip
                  guard (GENERATOR_REQUIRED = True), so after it they can
                  never pass vacuously.

Generator API these tests pin (CR-0036 section 1):
  bin_points(x, y, transform, shape)          -> int64 flat cell, -1 outside
  compute_hag(x, y, z, is_ground)             -> float64 HAG, NaN = no ground
  cell_metrics(cell, hag, is_first, n_cells)  -> {feature: float64[n_cells]},
                                                 NaN = NODATA
  mask_a(Y, A, tsd_years_at_max)              -> bool, True = NODATA
  mask_b(Y, A, tsd_years_at_A)                -> bool, True = NODATA
  lidar_share_encode / lidar_height_encode    -> int16, raise on bad input
  keep_points(classification, class_flags=None, withheld=None)
                                              -> bool keep mask (section 1.3)
  is_first(return_number)                     -> bool, ReturnNumber == 1
  assign_order(rows)                          -> rows sorted newest-first with
                                                 the pinned tie-break
  to_metres_z(z, row)                         -> z * row['z_to_m']
  transform_xy(x, y, row)                     -> template-CRS metres via the
                                                 row's pinned 'pipeline'
  check_source(row, header)                   -> raises ValueError when the
                                                 header CRS or units differ
                                                 from the row
"""
import importlib.util
import os
import sys
import unittest

import numpy as np

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

import check_lidar_structure as chk  # noqa: E402

GENERATOR_REQUIRED = False   # deliverable 2 flips this to True
_HAVE_GEN = importlib.util.find_spec("generate_lidar_structure") is not None
_skip_gen = unittest.skipUnless(
    _HAVE_GEN or GENERATOR_REQUIRED,
    "generate_lidar_structure.py lands in CR-0036 deliverable 2")


# ----------------------------------------------------------------------
class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = chk.synthetic_world()

    def test_self_test_passes(self):
        self.assertTrue(chk.self_test())

    def test_gate_requires_control_to_fail(self):
        self.assertFalse(chk.gate("x", (True, ""), (True, "")))
        self.assertFalse(chk.gate("x", (False, ""), (False, "")))
        self.assertTrue(chk.gate("x", (True, ""), (False, "")))

    def test_registration_rejects_shift(self):
        w = self.w
        ok, _ = chk.check_registration(w["wcov"], w["valid"], w["road"])
        self.assertTrue(ok)
        for dy, dx in ((1, 0), (0, 1), (1, 1)):
            s = np.zeros_like(w["wcov"])
            s[dy:, dx:] = w["wcov"][:s.shape[0] - dy, :s.shape[1] - dx]
            ok, _ = chk.check_registration(s, w["valid"], w["road"])
            self.assertFalse(ok, (dy, dx))

    def test_registration_needs_enough_windows(self):
        w = self.w
        small = (slice(0, 200), slice(0, 200))   # at most 1 window
        ok, msg = chk.check_registration(w["wcov"][small], w["valid"][small],
                                         w["road"][small])
        self.assertFalse(ok, msg)

    def test_height_rejects_feet_and_too_few(self):
        w = self.w
        self.assertTrue(chk.check_height(w["p95"], w["ch"], w["forest"],
                                         w["valid"])[0])
        self.assertFalse(chk.check_height(chk.as_feet(w["p95"]), w["ch"],
                                          w["forest"], w["valid"])[0])
        few = np.zeros_like(w["forest"])
        few.flat[:chk.MIN_CELLS - 1] = True
        self.assertFalse(chk.check_height(w["p95"], w["ch"], few,
                                          w["valid"])[0])

    def test_regen_rejects_permutation_and_reversal(self):
        w = self.w
        args = (w["tsd"], w["cc"], w["forest"], w["valid"], w["tsd_cap"])
        self.assertTrue(chk.check_regen(w["u13"], *args)[0])
        self.assertFalse(chk.check_regen(chk.permute(w["u13"], w["valid"]),
                                         *args)[0])
        self.assertFalse(chk.check_regen(1000 - w["u13"], *args)[0])

    def test_coverage_rejects_dropped_unit(self):
        w = self.w
        self.assertTrue(chk.check_coverage(w["valid"], w["forest"], w["wu"])[0])
        self.assertFalse(chk.check_coverage(
            chk.drop_unit(w["valid"], w["wu"], w["forest"]),
            w["forest"], w["wu"])[0])
        self.assertFalse(chk.check_coverage(
            w["valid"], np.zeros_like(w["forest"]), w["wu"])[0])

    def test_regen_needs_beating_null(self):
        w = self.w
        args = (w["tsd"], w["cc"], w["forest"], w["valid"], w["tsd_cap"])
        null = chk.regen_null(w["u13"], *args)
        self.assertEqual(null.size, chk.N_PERM)
        self.assertLess(np.nanpercentile(null, chk.PERM_Q),
                        chk.MIN_REGEN_CONTRAST)

    def test_coverage_slivers_are_obs(self):
        w = self.w
        wu = w["wu"].copy()
        idx = np.flatnonzero(w["forest"].ravel())[:chk.MIN_CELLS - 1]
        wu.ravel()[idx] = 7                    # a sliver work unit
        v = w["valid"].copy()
        v.ravel()[idx] = False                 # with no data at all
        ok, msg = chk.check_coverage(v, w["forest"], wu)
        self.assertTrue(ok, msg)
        self.assertIn("slivers (OBS) [7]", msg)

    def test_seam_compares_every_band(self):
        a = {f: np.arange(16).reshape(4, 4) for f in ("p", "q", "n_returns")}
        b = {k: v.copy() for k, v in a.items()}
        self.assertTrue(chk.check_seam(a, b)[0])
        b["n_returns"] = chk.perturb_one(b["n_returns"])
        ok, msg = chk.check_seam(a, b)
        self.assertFalse(ok)
        self.assertIn("n_returns", msg)

    def test_seam_rejects_one_cell(self):
        a = self.w["p95"]
        self.assertTrue(chk.check_seam(a, a.copy())[0])
        self.assertFalse(chk.check_seam(a, chk.perturb_one(a))[0])
        self.assertFalse(chk.check_seam(a, a[:-1])[0])

    def test_grid_rejects_half_cell(self):
        from rasterio.crs import CRS
        from rasterio.transform import from_origin
        g = chk._Grid(CRS.from_epsg(5070), from_origin(0, 0, 30, 30))
        self.assertTrue(chk.check_grid(g, g)[0])
        self.assertFalse(chk.check_grid(chk.half_cell_off(g), g)[0])


# ----------------------------------------------------------------------
# Brute-force oracles for the generator (CR-0036 section 1)
# ----------------------------------------------------------------------
def oracle_bin(x, y, transform, shape):
    H, W = shape
    inv = ~transform
    out = np.full(len(x), -1, np.int64)
    for i, (xi, yi) in enumerate(zip(x, y)):
        u, v = inv * (xi, yi)
        c, r = int(np.floor(u)), int(np.floor(v))
        if 0 <= r < H and 0 <= c < W:
            out[i] = r * W + c
    return out


def oracle_hag(x, y, z, is_ground, k, maxdist):
    gx, gy, gz = x[is_ground], y[is_ground], z[is_ground]
    hag = np.full(len(x), np.nan)
    for i in range(len(x)):
        if is_ground[i]:
            hag[i] = 0.0
            continue
        d = np.hypot(gx - x[i], gy - y[i])
        keep = d <= maxdist
        if not keep.any():
            continue
        order = np.argsort(d[keep], kind="stable")[:k]
        dd, zz = d[keep][order], gz[keep][order]
        if np.any(dd == 0):
            g = zz[dd == 0].mean()
        else:
            wgt = 1.0 / dd ** 2
            g = (wgt * zz).sum() / wgt.sum()
        hag[i] = z[i] - g
    return hag


def oracle_metrics(cell, hag, is_first, n_cells, min_returns, min_denom):
    out = {f: np.full(n_cells, np.nan) for f in chk.LIDAR_FEATURES}
    for c in range(n_cells):
        h = hag[(cell == c) & np.isfinite(hag)]
        f = is_first[(cell == c) & np.isfinite(hag)]
        if h.size < min_returns:
            continue

        def frac(a, b):
            num = ((h >= a) & (h < b)).sum()
            den = ((h >= -2) & (h < b)).sum()
            return 1000.0 * num / den if den >= min_denom else np.nan
        out["lid_u05_2"][c] = frac(0.5, 2)
        out["lid_u1_3"][c] = frac(1, 3)
        out["lid_u3_5"][c] = frac(3, 5)
        out["lid_u5_10"][c] = frac(5, 10)
        tall = h[h >= 0.5]
        out["lid_p95"][c] = (10 * np.percentile(tall, 95, method="linear")
                             if tall.size >= 5 else 0.0)
        out["lid_sd"][c] = 10 * tall.std(ddof=0) if tall.size >= 5 else 0.0
        nf = f.sum()
        out["lid_wcov5"][c] = (1000.0 * (f & (h > 5)).sum() / nf
                               if nf >= min_denom else np.nan)
    return out


@_skip_gen
class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import generate_lidar_structure as gen
        cls.gen = gen

    def test_bin_half_open_edges(self):
        from rasterio.transform import from_origin
        t = from_origin(1000.0, 2000.0, 30.0, 30.0)
        # exactly on edges, just inside, just outside, far outside
        x = np.array([1000.0, 1030.0, 1029.999, 999.999, 1000.0, 1300.0])
        y = np.array([2000.0, 1970.0, 1970.001, 2000.0, 1700.0, 1900.0])
        got = self.gen.bin_points(x, y, t, (10, 10))
        np.testing.assert_array_equal(got, oracle_bin(x, y, t, (10, 10)))
        self.assertEqual(got[0], 0)
        self.assertEqual(got[1], 1 * 10 + 1)
        self.assertEqual(got[3], -1)
        self.assertEqual(got[4], -1)        # y = bottom edge: outside

    def test_bin_random_vs_oracle(self):
        from rasterio.transform import from_origin
        rng = np.random.default_rng(3)
        t = from_origin(500.0, 900.0, 30.0, 30.0)
        x = rng.uniform(450, 900, 5000)
        y = rng.uniform(500, 950, 5000)
        np.testing.assert_array_equal(self.gen.bin_points(x, y, t, (12, 13)),
                                      oracle_bin(x, y, t, (12, 13)))

    def _cloud(self, n=4000, slope=0.0, seed=5):
        rng = np.random.default_rng(seed)
        x = rng.uniform(0, 300, n)
        y = rng.uniform(0, 300, n)
        ground = rng.random(n) < 0.35
        z0 = 100 + slope * x
        z = z0 + np.where(ground, rng.normal(0, 0.05, n),
                          rng.uniform(0, 25, n))
        return x, y, z, ground

    def test_hag_flat_and_slope(self):
        for slope in (0.0, 0.6):
            x, y, z, g = self._cloud(slope=slope)
            got = self.gen.compute_hag(x, y, z, g)
            exp = oracle_hag(x, y, z, g, self.gen.LIDAR_HAG_K,
                             self.gen.LIDAR_HAG_MAXDIST_M)
            np.testing.assert_allclose(got, exp, rtol=0, atol=1e-9,
                                       equal_nan=True)

    def test_hag_no_ground_in_range_is_nan(self):
        x = np.array([0.0, 1000.0])
        y = np.array([0.0, 0.0])
        z = np.array([100.0, 110.0])
        g = np.array([True, False])
        self.assertTrue(np.isnan(self.gen.compute_hag(x, y, z, g)[1]))

    def test_metrics_vs_oracle(self):
        rng = np.random.default_rng(7)
        n_cells, n = 9, 3000
        cell = rng.integers(0, n_cells, n)
        cell[cell == 4] = 3            # cell 4 empty -> NODATA
        hag = rng.uniform(-1, 30, n)
        hag[cell == 5] = rng.uniform(-1, 0.4, (cell == 5).sum())  # open
        hag[rng.random(n) < 0.02] = np.nan
        first = rng.random(n) < 0.6
        got = self.gen.cell_metrics(cell, hag, first, n_cells)
        exp = oracle_metrics(cell, hag, first, n_cells,
                             self.gen.LIDAR_MIN_RETURNS,
                             self.gen.LIDAR_MIN_DENOM)
        for f in chk.LIDAR_FEATURES:
            np.testing.assert_allclose(got[f], exp[f], atol=1e-9,
                                       equal_nan=True, err_msg=f)

    def test_seam_exact(self):
        # A block computed whole equals the same block computed as four
        # quadrants, each read with the pad (HAG then metrics).
        x, y, z, g = self._cloud(n=20000, slope=0.3, seed=11)
        whole = self.gen.compute_hag(x, y, z, g)
        pad = self.gen.LIDAR_PAD_M
        part = np.full_like(whole, np.nan)
        for x0, y0 in ((0, 0), (150, 0), (0, 150), (150, 150)):
            inb = (x >= x0) & (x < x0 + 150) & (y >= y0) & (y < y0 + 150)
            rd = (x >= x0 - pad) & (x < x0 + 150 + pad) & \
                (y >= y0 - pad) & (y < y0 + 150 + pad)
            h = self.gen.compute_hag(x[rd], y[rd], z[rd], g[rd])
            part[np.flatnonzero(rd)[inb[rd]]] = h[inb[rd]]
        np.testing.assert_array_equal(np.isnan(whole), np.isnan(part))
        np.testing.assert_array_equal(whole[~np.isnan(whole)],
                                      part[~np.isnan(part)])

    def test_mask_a_both_directions(self):
        m = self.gen.mask_a
        cap = self.gen.TSD_MAX_YEARS
        # (Y, A, years since disturbance at max(Y, A), expected NODATA)
        cases = [
            (2025, 2019, 3.0, True),    # D = 2022 in [2019, 2025]
            (2025, 2019, 8.0, False),   # D = 2017 before the flight
            (2020, 2023, 1.0, True),    # Y < A: D = 2022 in [2020, 2023]
            (2020, 2023, 5.0, False),   # D = 2018 before both
            (2023, 2023, 0.0, True),    # same year: ambiguous order
            (2023, 2023, 2.0, False),
            (2025, 2019, cap, False),   # undisturbed cap never masks
        ]
        for Y, A, yrs, exp in cases:
            got = bool(m(np.array([Y]), np.array([A]), np.array([yrs]))[0])
            self.assertEqual(got, exp, (Y, A, yrs))
        self.assertTrue(bool(m(np.array([2025]), np.array([2019]),
                               np.array([np.nan]))[0]))   # tsd nodata

    def test_mask_a_rounds_decoded_years(self):
        # tsd_decode is not exact: 3 years may decode as 2.9995 or 3.0004
        for eps in (-4e-4, 4e-4):
            got = self.gen.mask_a(np.array([2020]), np.array([2017]),
                                  np.array([3.0 + eps]))
            self.assertTrue(bool(got[0]), eps)       # D = 2017 = A

    def test_mask_b_regrowth(self):
        m = self.gen.mask_b
        cap = self.gen.TSD_MAX_YEARS
        # (Y, A, years since disturbance at A, expected NODATA)
        cases = [(2025, 2015, 5.0, True),    # young stand, gap 10
                 (2017, 2015, 5.0, False),   # gap within tolerance
                 (2025, 2015, 25.0, False),  # old disturbance
                 (2025, 2015, cap, False)]
        for Y, A, yrs, exp in cases:
            got = bool(m(np.array([Y]), np.array([A]), np.array([yrs]))[0])
            self.assertEqual(got, exp, (Y, A, yrs))

    def test_encoders_refuse(self):
        for enc, good, bad in (
                (self.gen.lidar_share_encode, [0.0, 1000.0],
                 [np.nan, np.inf, -1.0, 1000.5]),
                (self.gen.lidar_height_encode, [0.0, 800.0],
                 [np.nan, -0.1, 800.1])):
            out = enc(np.array(good))
            self.assertEqual(out.dtype, np.int16)
            for b in bad:
                with self.assertRaises(ValueError, msg=(enc.__name__, b)):
                    enc(np.array([b]))

    def test_point_filter(self):
        cls = np.array([0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 17, 18,
                        19, 20, 21, 22, 2, 2])
        flags = np.zeros(cls.size, np.uint8)
        flags[-2] = 0x04          # withheld (LAS ClassFlags bit 2)
        flags[-1] = 0x08          # overlap (bit 3): KEPT
        keep = self.gen.keep_points(cls, class_flags=flags)
        exp = np.isin(cls, (0, 1, 2, 3, 4, 5, 9)) & \
            ((flags & 0x04) == 0)
        np.testing.assert_array_equal(keep, exp)
        w = np.zeros(cls.size, bool)
        w[0] = True               # LAS 1.4 Withheld dimension
        self.assertFalse(self.gen.keep_points(cls, withheld=w)[0])

    def test_assign_order_tie_break(self):
        rows = [dict(work_unit="B", collect_end="2019/12/01", ql="QL2",
                     reader="ept"),
                dict(work_unit="A", collect_end="2019/12/01", ql="QL1",
                     reader="las"),
                dict(work_unit="C", collect_end="2019/12/01", ql="QL1",
                     reader="ept"),
                dict(work_unit="D", collect_end="2020/01/01", ql="QL2",
                     reader="las"),
                dict(work_unit="E", collect_end="2019/12/01", ql="QL1",
                     reader="ept")]
        got = [r["work_unit"] for r in self.gen.assign_order(rows)]
        self.assertEqual(got, ["D", "C", "E", "A", "B"])

    def test_first_return(self):
        np.testing.assert_array_equal(self.gen.is_first(np.array([1, 2, 1, 3])),
                                      [True, False, True, False])

    def _row(self, **kw):
        row = dict(work_unit="TEST", reader="las", horiz_epsg=6348,
                   xy_to_m=1.0, z_to_m=1.0,
                   pipeline="+proj=noop")
        row.update(kw)
        return row

    def test_z_units(self):
        feet = self._row(z_to_m=1200 / 3937)
        np.testing.assert_allclose(self.gen.to_metres_z(np.array([3937.0]),
                                                        feet), [1200.0])
        ept = self._row(reader="ept", z_to_m=1.0)
        np.testing.assert_allclose(self.gen.to_metres_z(np.array([5.0]),
                                                        ept), [5.0])

    def test_xy_pipeline_used_exactly(self):
        # UTM 19N (NAD83(2011), EPSG:6348) -> CONUS Albers (EPSG:5070) via
        # an explicit pinned pipeline; must equal pyproj's from_pipeline.
        from pyproj import Transformer
        pipe = ("+proj=pipeline +step +inv +proj=utm +zone=19 +ellps=GRS80 "
                "+step +proj=aea +lat_0=23 +lon_0=-96 +lat_1=29.5 "
                "+lat_2=45.5 +x_0=0 +y_0=0 +ellps=GRS80")
        row = self._row(pipeline=pipe)
        x, y = np.array([300000.0, 310000.0]), np.array([4800000.0, 4810000.0])
        gx, gy = self.gen.transform_xy(x, y, row)
        ex, ey = Transformer.from_pipeline(pipe).transform(x, y)
        np.testing.assert_allclose(gx, ex, atol=1e-6)
        np.testing.assert_allclose(gy, ey, atol=1e-6)

    def test_source_header_mismatch_refused(self):
        row = self._row(horiz_epsg=6348, xy_to_m=1.0, z_to_m=1.0)
        self.gen.check_source(row, dict(horiz_epsg=6348, xy_to_m=1.0,
                                        z_to_m=1.0))
        for bad in (dict(horiz_epsg=6589, xy_to_m=1.0, z_to_m=1.0),
                    dict(horiz_epsg=6348, xy_to_m=1200 / 3937, z_to_m=1.0),
                    dict(horiz_epsg=6348, xy_to_m=1.0, z_to_m=1200 / 3937)):
            with self.assertRaises(ValueError, msg=bad):
                self.gen.check_source(row, bad)

    def test_hag_ground_zero_noise_and_water(self):
        # ground points get HAG 0; HAG < -2 or > LIDAR_HAG_MAX_M -> NaN
        # (dropped as noise); water (class 9) points at the surface get ~0
        x = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.zeros(6)
        z = np.array([100.0, 100.0, 105.0, 95.0, 100.0 + 200.0, 100.1])
        g = np.array([True, True, False, False, False, False])
        h = self.gen.compute_hag(x, y, z, g)
        self.assertEqual(h[0], 0.0)
        self.assertAlmostEqual(h[2], 5.0, places=9)
        self.assertTrue(np.isnan(h[3]))      # -5 m: noise
        self.assertTrue(np.isnan(h[4]))      # +200 m: noise
        self.assertAlmostEqual(h[5], 0.1, places=9)

    def test_mask_b_before_tsd_record(self):
        # A = 2015 precedes the first tsd vintage (2016): years since
        # disturbance at A come from tsd_2016 minus (2016 - A).
        got = self.gen.mask_b(np.array([2025]), np.array([2015]),
                              np.array([5.0]))      # tsd_A, already shifted
        self.assertTrue(bool(got[0]))
        self.assertEqual(self.gen.tsd_years_at(
            2015, {2016: np.array([6.0])})[0], 5.0)
        self.assertTrue(np.isnan(self.gen.tsd_years_at(
            2015, {2016: np.array([0.0])})[0]))      # cut in 2016: after A


class LintTests(unittest.TestCase):
    FORBIDDEN = ("reproject(", "WarpedVRT", "writers.gdal",
                 "calculate_default_transform", '"resolution"',
                 "'resolution'", "filters.hag_nn", "filters.hag_delaunay",
                 "filters.sample", "filters.voxel", "filters.decimation",
                 "ignore_unreadable", "Transformer.from_crs")

    @_skip_gen
    def test_generator_has_no_warp_or_thinning(self):
        src = open(os.path.join(_root, "generate_lidar_structure.py")).read()
        for tok in self.FORBIDDEN:
            self.assertNotIn(tok, src, tok)


if __name__ == "__main__":
    unittest.main()
