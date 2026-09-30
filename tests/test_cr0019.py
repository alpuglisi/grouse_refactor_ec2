"""CR-0019 implementation tests: one year floor (regions.YEAR_MIN) for both
classes at selection, and train.filter_by_year_gap refusing instead of
dropping.

    python -m unittest tests.test_cr0019 -v

Written from CR-0019 v3 section 2 and its test plan only (CR-0013 design
rule 4): nothing here reads acceptance_split.py, its config or its tests.
The end-to-end tests reuse tests/test_cr0012.py's synthetic data tree
(rasters included; regions.verify_partition and domain D patched as
there). Every test that needs a particular row to reach a step asserts
that it does, so no test passes vacuously (PA-0021(a)).
"""
import ast
import io
import json
import os
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
import train  # noqa: E402
from grouse_data import PATH_TEMPLATES  # noqa: E402
from tests.test_cr0012 import (  # noqa: E402
    build_tree, fake_verify_partition, run_both, output_bytes, _to_lonlat)

_FAR_DOMAIN = mock.patch.object(
    regions, "_domain_5070",
    lambda: shapely.box(-1e8, -1e8, 1e8, 1e8))


def setUpModule():
    _FAR_DOMAIN.start()


def tearDownModule():
    _FAR_DOMAIN.stop()


def _csv(d, rel):
    return pd.read_csv(os.path.join(d, rel), float_precision="round_trip")


def _ev_path(d, r):
    return os.path.join(d, PATH_TEMPLATES["evaluated"].format(region=r))


def _cand_path(d, r):
    return os.path.join(d, PATH_TEMPLATES["gbif_candidates"].format(region=r))


def _positives(d):
    return pd.concat([_csv(d, PATH_TEMPLATES["thinned"].format(region=r))
                      for r in regions.REGIONS], ignore_index=True)


def _negatives(d):
    return pd.concat([_csv(d, PATH_TEMPLATES["negatives"].format(region=r))
                      for r in regions.REGIONS], ignore_index=True)


def _manifest(d):
    with open(os.path.join(d, PATH_TEMPLATES["split_manifest"])) as f:
        return json.load(f)


def _run_ptd(d):
    with redirect_stdout(io.StringIO()):
        ptd.run(d)


class TreeCase(unittest.TestCase):
    seed = 3

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.bad = build_tree(self.d, seed=self.seed)


# ---------------------------------------------------------------------------
# Constant and single sourcing
# ---------------------------------------------------------------------------
class Constant(unittest.TestCase):
    def test_value_and_manifest_constant(self):
        self.assertEqual(regions.YEAR_MIN, 2020)
        self.assertEqual(ptd.measured_constants()["YEAR_MIN"],
                         regions.YEAR_MIN)
        with mock.patch.object(regions, "YEAR_MIN", 2031):
            self.assertEqual(ptd.measured_constants()["YEAR_MIN"], 2031)

    def test_get_negatives_default_from_year_min(self):
        # AST only: importing get_negatives needs no network, but its
        # main() fetches, so it is never run here.
        with open(os.path.join(ROOT, "get_negatives.py")) as f:
            tree = ast.parse(f.read())
        imported = {a.name for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.module == "regions"
                    for a in n.names}
        self.assertIn("YEAR_MIN", imported)
        years = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", None) == "add_argument"
                 and n.args and getattr(n.args[0], "value", None) == "--years"]
        self.assertEqual(len(years), 1)
        default = [k.value for k in years[0].keywords if k.arg == "default"][0]
        rng = [n for n in ast.walk(default) if isinstance(n, ast.Call)
               and getattr(n.func, "id", None) == "range"]
        self.assertEqual(len(rng), 1)
        self.assertIsInstance(rng[0].args[0], ast.Name)
        self.assertEqual(rng[0].args[0].id, "YEAR_MIN")
        ints = [n.value for n in ast.walk(default)
                if isinstance(n, ast.Constant) and isinstance(n.value, int)
                and n.value > 1900]
        self.assertEqual(ints, [])


# ---------------------------------------------------------------------------
# Positives step 2
# ---------------------------------------------------------------------------
class PositivesStep2(TreeCase):
    def test_floor_drops_below_keeps_equal(self):
        r = "ME"
        ev = pd.read_csv(_ev_path(self.d, r), float_precision="round_trip")
        hab = np.flatnonzero(~ev["nonveg_landcover"].astype(bool).to_numpy())
        below, equal = hab[0::3], hab[1::3]
        ev.loc[below, "year"] = regions.YEAR_MIN - 1
        ev.loc[equal, "year"] = regions.YEAR_MIN
        ev.to_csv(_ev_path(self.d, r), index=False)
        _run_ptd(self.d)
        c = _manifest(self.d)["positives"]["counts"][r]
        self.assertEqual(c["1"], len(ev))
        want = int((~ev["nonveg_landcover"].astype(bool)
                    & (ev["year"] >= regions.YEAR_MIN)).sum())
        self.assertEqual(c["2"], want)
        self.assertEqual(c["2"], len(hab) - len(below))
        pos = _positives(self.d)
        self.assertGreater(len(pos), 0)
        self.assertTrue((pos["year"] >= regions.YEAR_MIN).all())
        # off-by-one guard: rows at exactly YEAR_MIN reach the output
        self.assertGreater(int((pos[pos.region == r]["year"]
                                == regions.YEAR_MIN).sum()), 0)

    def test_null_year_raises_habitat_or_not(self):
        r = "NH"
        ev0 = pd.read_csv(_ev_path(self.d, r), float_precision="round_trip")
        for nonveg in (True, False):
            with self.subTest(nonveg=nonveg):
                ev = ev0.copy()
                i = int(np.flatnonzero(
                    ev["nonveg_landcover"].astype(bool).to_numpy() == nonveg)[0])
                ev["year"] = ev["year"].astype(float)
                ev.loc[i, "year"] = np.nan
                ev.to_csv(_ev_path(self.d, r), index=False)
                with redirect_stdout(io.StringIO()):
                    with self.assertRaises(ValueError) as cm:
                        ptd.run(self.d)
                self.assertIn("null year", str(cm.exception))

    def test_floor_precedes_thinning(self):
        """A pre-floor point first in thin order must not suppress its
        post-floor neighbour closer than MIN_SPACING_M."""
        r = "VT"
        ev = pd.read_csv(_ev_path(self.d, r), float_precision="round_trip")
        cx, cy = ptd.to_5070(ev["longitude"], ev["latitude"])
        # a spot inside the raster, >= 200 m from every existing sighting
        centre = (float(np.mean(cx)), float(np.mean(cy)))
        best = None
        for dx in range(-3000, 3001, 250):
            for dy in range(-3000, 3001, 250):
                x, y = centre[0] + dx, centre[1] + dy
                dmin = float(np.min((cx - x) ** 2 + (cy - y) ** 2))
                if dmin >= 200.0 ** 2:
                    best = (x, y)
                    break
            if best:
                break
        self.assertIsNotNone(best)
        xs = np.array([best[0], best[0] + 10.0])
        ys = np.array([best[1], best[1]])
        lon, lat = _to_lonlat(xs, ys)
        lon, lat = np.round(lon, 6), np.round(lat, 6)
        keys = ptd.coord_keys(lon, lat)
        first = int(np.argmin(keys))        # first in thin order
        years = [0, 0]
        years[first] = regions.YEAR_MIN - 1
        years[1 - first] = regions.YEAR_MIN + 3
        tmpl = ev[~ev["nonveg_landcover"].astype(bool)].iloc[[0, 0]].copy()
        tmpl["longitude"], tmpl["latitude"] = lon, lat
        tmpl["x_5070"], tmpl["y_5070"] = xs, ys
        tmpl["year"] = years
        tmpl["first_year"] = years
        tmpl["last_year"] = years
        # control: with no floor, the pre-floor point wins the thin
        pair = tmpl.reset_index(drop=True)
        kept = ptd.thin_by_min_distance(pair)
        self.assertEqual(len(kept), 1)
        self.assertEqual(int(kept["year"].iloc[0]), regions.YEAR_MIN - 1)
        pd.concat([ev, tmpl], ignore_index=True).to_csv(
            _ev_path(self.d, r), index=False)
        _run_ptd(self.d)
        pos = _positives(self.d)
        got = pos[(pos.longitude == lon[1 - first])
                  & (pos.latitude == lat[1 - first])]
        self.assertEqual(len(got), 1, "post-floor neighbour was suppressed")
        self.assertEqual(len(pos[(pos.longitude == lon[first])
                                 & (pos.latitude == lat[first])]), 0)


# ---------------------------------------------------------------------------
# Pool step 1, step 7 and step 6 (a)
# ---------------------------------------------------------------------------
class PoolStep1(TreeCase):
    def test_floor_drops_below_keeps_equal_nulls_to_step7(self):
        raw_n, early_n = {}, {}
        for r in regions.REGIONS:
            c = pd.read_csv(_cand_path(self.d, r),
                            float_precision="round_trip")
            idx = np.flatnonzero(c["year"].notna().to_numpy())
            c.loc[idx[0::4], "year"] = float(regions.YEAR_MIN - 1)
            c.loc[idx[1::4], "year"] = float(regions.YEAR_MIN)
            c.to_csv(_cand_path(self.d, r), index=False)
            raw_n[r] = len(c)
            early_n[r] = len(idx[0::4])
            self.assertGreater(int(c["year"].isna().sum()), 0)
        seen = []
        real = gn.extract_envelope

        def spy(cand, rd):
            seen.append(int(cand["year"].isna().sum()))
            self.assertFalse((cand["year"] < regions.YEAR_MIN).any())
            return real(cand, rd)
        with mock.patch.object(gn, "extract_envelope", spy):
            run_both(self.d, self.bad)
        c1 = _manifest(self.d)["negatives"]["counts"]
        for r in regions.REGIONS:
            # count "1" is after the floor; null years are still counted
            self.assertEqual(c1[r]["1"], raw_n[r] - early_n[r])
        # null-year candidates reached step 7 and were dropped there
        self.assertGreater(sum(seen), 0)
        pool = _csv(self.d, PATH_TEMPLATES["candidate_pool"])
        self.assertTrue(pool["year"].notna().all())
        self.assertTrue((pool["year"] >= regions.YEAR_MIN).all())
        self.assertGreater(int((pool["year"] == regions.YEAR_MIN).sum()), 0)
        self.assertTrue((_negatives(self.d)["year"] >= regions.YEAR_MIN).all())

    def test_buffer_still_uses_pre_floor_sightings(self):
        """Pool step 6 (a): a candidate within BUFFER_M of a pre-floor
        sighting only is still dropped, while that sighting is not a
        positive."""
        run_both(self.d, self.bad)
        base_pos = {k: v for k, v in output_bytes(self.d).items()
                    if "positives" in k or "block_assignments" in k}
        pool = _csv(self.d, PATH_TEMPLATES["candidate_pool"])
        r = "ME"
        target = pool[pool.region == r].iloc[len(pool[pool.region == r]) // 2]
        tx, ty = ptd.to_5070([target.longitude], [target.latitude])
        slon, slat = _to_lonlat(tx + 100.0, ty)
        ev = pd.read_csv(_ev_path(self.d, r), float_precision="round_trip")
        row = ev.iloc[[0]].copy()
        row["longitude"] = np.round(slon, 6)
        row["latitude"] = np.round(slat, 6)
        row["x_5070"], row["y_5070"] = tx + 100.0, ty
        row["year"] = regions.YEAR_MIN - 4
        row["first_year"] = row["last_year"] = regions.YEAR_MIN - 4
        # non-habitat, so the envelope binners (pool step 9) are unchanged
        row["nonveg_landcover"] = True
        pd.concat([ev, row], ignore_index=True).to_csv(_ev_path(self.d, r),
                                                       index=False)
        run_both(self.d, self.bad)
        after = output_bytes(self.d)
        # the pre-floor sighting changed no positive output ...
        self.assertEqual({k: after[k] for k in base_pos}, base_pos)
        # ... but its buffer still removed the candidate
        pool2 = _csv(self.d, PATH_TEMPLATES["candidate_pool"])
        hit = pool2[(pool2.longitude == target.longitude)
                    & (pool2.latitude == target.latitude)]
        self.assertEqual(len(hit), 0)


class YearMinAboveLowestCandidate(TreeCase):
    """Test seam: with YEAR_MIN raised above the lowest candidate year,
    both classes are floored and the draw still runs."""

    def test_both_classes_floored_and_draw_runs(self):
        hi = 2024
        raw = pd.concat([_csv(self.d, PATH_TEMPLATES["gbif_candidates"]
                              .format(region=r)) for r in regions.REGIONS])
        ev = pd.concat([_csv(self.d, PATH_TEMPLATES["evaluated"]
                             .format(region=r)) for r in regions.REGIONS])
        self.assertLess(raw["year"].min(), hi)
        self.assertLess(ev["year"].min(), hi)
        with mock.patch.object(regions, "YEAR_MIN", hi):
            run_both(self.d, self.bad)
        pos, neg = _positives(self.d), _negatives(self.d)
        pool = _csv(self.d, PATH_TEMPLATES["candidate_pool"])
        self.assertGreater(len(pos), 0)
        for df in (pos, neg, pool):
            self.assertTrue((df["year"] >= hi).all())
        m = _manifest(self.d)
        for sec in ("positives", "negatives"):
            self.assertEqual(m[sec]["constants"]["YEAR_MIN"], hi)
        for r in regions.REGIONS:
            for s in ("train", "val"):
                n_pos = int(((pos.region == r) & (pos.split == s)).sum())
                n_neg = int(((neg.region == r) & (neg.split == s)).sum())
                self.assertEqual(n_neg, n_pos, (r, s))
                self.assertEqual(m["negatives"]["draw"][r][s]["n"], n_pos)


# ---------------------------------------------------------------------------
# train.filter_by_year_gap: refuses, never drops
# ---------------------------------------------------------------------------
class FakeRD:
    def __init__(self, years):
        self.years = years

    def raster_years(self, feat):
        return self.years[feat]


class FilterByYearGap(unittest.TestCase):
    rd = FakeRD({"evt": [2022, 2023, 2024], "cc": [2020, 2021, 2024]})
    feats = ["evt", "cc"]

    def test_refuses_when_any_row_would_be_excluded(self):
        df = pd.DataFrame({"year": [2020, 2019, 2019, 2024, np.nan],
                           "longitude": range(5)})
        with self.assertRaises(SystemExit) as cm:
            train.filter_by_year_gap(df, self.rd, self.feats, 1,
                                     "val positive", "NH")
        msg = str(cm.exception.code)
        for part in ("NH", "val positive", "3 ", "[2019, 2020]", "+/-1",
                     "--max-year-gap -1", "YEAR_MIN"):
            self.assertIn(part, msg)

    def test_returns_unchanged_otherwise(self):
        df = pd.DataFrame({"year": [2021.0, 2024.0, np.nan, 2022.0],
                           "longitude": [1.0, 2.0, 3.0, 4.0]},
                          index=[0, 1, 2, 3])
        out = train.filter_by_year_gap(df, self.rd, self.feats, 1,
                                       "train negative", "ME")
        pd.testing.assert_frame_equal(out, df)

    def test_minus_one_disables(self):
        df = pd.DataFrame({"year": [2000, 2024]})
        out = train.filter_by_year_gap(df, self.rd, self.feats, -1,
                                       "train positive", "VT")
        self.assertIs(out, df)


if __name__ == "__main__":
    unittest.main()
