"""CR-0022: background assumed-negatives take the training positives' years
(BUG-0074). Synthetic rasters only; no data/ access.

Written before approval (CR-0011 A3) and reviewed with the CR. Every test
except the pinned pre-CR digests' fixture fails until CR-0022 deliverable 2
lands (`sample_background_points(year=...)`, `background_for_positives`,
the build_datasets check).

Run with
    python -m unittest tests.test_cr0022
"""
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import train  # noqa: E402
from grouse_data import DataConfig, RegionData  # noqa: E402

W, N, RES, SIZE = -71.5, 44.6, 0.001, 100
NODATA = -9999
# Digests of sample_background_points' output at 9bb1636 (before CR-0022)
# on build_fixture(), in_state=everywhere: {(train_blocks_only, seed, n):
# sha256 of digest_frame(df)}. CR-0022 §2 A: year="latest" must reproduce
# them exactly (pretrain.py's behaviour).
PRE_CR_DIGESTS = {
    (False, 0, 40): "c8f84c95e6e08f860faf4229cfd003024006ede339b6fcd1f76f3f0d7bf574c6",
    (False, 7, 25): "32a74c5c1d5c93984cd02d8549324f849b7e3bcb645565f4ed1620d2994720dd",
    (True, 0, 40): "c8f84c95e6e08f860faf4229cfd003024006ede339b6fcd1f76f3f0d7bf574c6",
    (True, 7, 25): "32a74c5c1d5c93984cd02d8549324f849b7e3bcb645565f4ed1620d2994720dd",
}
ASSIGN = pd.DataFrame({"block_id": ["none"], "split": ["train"]})  # vf 0: all train


def everywhere(lon, lat, region):
    return np.ones(len(np.atleast_1d(lon)), dtype=bool)


def digest_frame(df):
    return hashlib.sha256(df.to_csv(index=False, float_format="%.12f")
                          .encode()).hexdigest()


def _write(base, year, valid):
    d = os.path.join(base, "data", "landfire")
    os.makedirs(d, exist_ok=True)
    arr = np.full((SIZE, SIZE), NODATA, np.int16)
    arr[valid] = 7
    with rasterio.open(os.path.join(d, f"NH_{year}_evt.tif"), "w",
                       driver="GTiff", height=SIZE, width=SIZE, count=1,
                       dtype="int16", crs="EPSG:4326",
                       transform=from_origin(W, N, RES, RES),
                       nodata=NODATA) as dst:
        dst.write(arr, 1)


def build_fixture(base):
    """evt rasters whose valid halves differ by year, so a point's year
    can be read off its location: 2020 west half, 2022 east half, 2023 an
    empty placeholder (fails content validation; raster_path falls back to
    2024), 2024 north half. No 2021 raster: raster_path resolves 2021 to
    2020 (tie, earlier year)."""
    r = np.arange(SIZE)[:, None]
    c = np.arange(SIZE)[None, :]
    _write(base, 2020, np.broadcast_to(c < 50, (SIZE, SIZE)))
    _write(base, 2022, np.broadcast_to(c >= 50, (SIZE, SIZE)))
    _write(base, 2023, np.zeros((SIZE, SIZE), bool))
    _write(base, 2024, np.broadcast_to(r < 50, (SIZE, SIZE)))
    return RegionData("NH", DataConfig(base_dir=base))


def valid_at(path, lons, lats):
    with rasterio.open(path) as src:
        vals = np.array([v[0] for v in src.sample(zip(lons, lats))])
    return vals != NODATA


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        with mock.patch("builtins.print"):
            self.rd = build_fixture(self.tmp)

    def helper(self, pos_years, ratio=1.0, seed=0, region_i=0, **kw):
        with mock.patch("builtins.print"):
            return train.background_for_positives(
                self.rd, ["evt"], pos_years, ratio, seed=seed,
                region_i=region_i, region="NH", assignments=ASSIGN,
                in_state=everywhere, **kw)


class U1Histogram(Base):
    def test_ratio_one_matches_positives_exactly(self):
        pos = pd.Series([2020] * 3 + [2022] * 5 + [2024] * 2, dtype="int64")
        bg = self.helper(pos)                      # np.int64 years (B5)
        self.assertEqual(bg["year"].value_counts().to_dict(),
                         {2020: 3, 2022: 5, 2024: 2})
        self.assertTrue((bg["label"] == 0.0).all())

    def test_ratio_one_and_a_half_rounds_per_year(self):
        bg = self.helper([2020] * 3 + [2022] * 5 + [2024] * 2, ratio=1.5)
        # round(4.5) = 4, round(7.5) = 8, round(3.0) = 3; total = the sum
        self.assertEqual(bg["year"].value_counts().to_dict(),
                         {2020: 4, 2022: 8, 2024: 3})
        self.assertEqual(len(bg), 15)


class U2ValidatedOnReadRaster(Base):
    """B1 / A2: through the helper, every row is valid on the raster
    GrousePatchDataset will read it from, including a year with no raster
    (2021 -> 2020) and an empty placeholder vintage (2023 -> 2024)."""

    def test_each_row_valid_on_its_years_resolved_raster(self):
        from dataset import GrousePatchDataset
        years = [2020, 2021, 2022, 2023, 2024]
        bg = self.helper([y for y in years for _ in range(12)])
        with mock.patch("builtins.print"):
            ds = GrousePatchDataset(bg, self.rd, ["evt"], [], img_size=64,
                                    expand_rotations=False, label=0.0)
        for y in years:
            rows = bg[bg["year"] == y]
            self.assertEqual(len(rows), 12, y)
            with mock.patch("builtins.print"):
                path = self.rd.raster_path("evt", y)
            self.assertEqual(path, ds._path_for[("evt", y)], y)
            ok = valid_at(path, rows["longitude"], rows["latitude"])
            self.assertTrue(ok.all(), f"{y}: {int((~ok).sum())} rows invalid "
                                      f"on {os.path.basename(path)}")
        # the halves really differ: 2020's rows lie west, 2022's east
        self.assertTrue((bg[bg.year == 2020].longitude < W + 50 * RES).all())
        self.assertTrue((bg[bg.year == 2022].longitude >= W + 50 * RES).all())


class U3YearKeyword(Base):
    def call(self, **kw):
        return train.sample_background_points(
            self.rd, ["evt"], 5, seed=0, region="NH",
            train_blocks_only=False, in_state=everywhere, **kw)

    def test_missing_year_is_a_type_error(self):
        with self.assertRaises(TypeError):
            self.call()

    def test_bad_year_values_refused_before_any_raster_is_opened(self):
        for bad in (None, 2020.5, 2020.0, True, "newest", "2020"):
            with self.subTest(year=bad), \
                 mock.patch("rasterio.open", side_effect=AssertionError("opened")):
                with self.assertRaises(ValueError):
                    self.call(year=bad)

    def test_numpy_integer_year_accepted(self):
        with mock.patch("builtins.print"):
            df = self.call(year=np.int64(2022))
        self.assertEqual(set(df["year"]), {2022})
        self.assertEqual(df.attrs["acceptance"]["year"], 2022)


class U4LatestUnchanged(Base):
    def test_latest_reproduces_pre_cr_digests(self):
        for (tbo, seed, n), want in PRE_CR_DIGESTS.items():
            kw = dict(train_blocks_only=tbo)
            if tbo:
                kw["assignments"] = ASSIGN
            with self.subTest(train_blocks_only=tbo, seed=seed, n=n):
                df = train.sample_background_points(
                    self.rd, ["evt"], n, seed=seed, region="NH",
                    year="latest", in_state=everywhere, **kw)
                self.assertEqual(digest_frame(df), want)


class U5Determinism(Base):
    def test_same_inputs_same_frame_other_seed_or_region_differs(self):
        pos = [2020] * 6 + [2024] * 6
        a = self.helper(pos, seed=3, region_i=1)
        b = self.helper(pos, seed=3, region_i=1)
        pd.testing.assert_frame_equal(a, b)
        self.assertFalse(a.equals(self.helper(pos, seed=4, region_i=1)))
        self.assertFalse(a.equals(self.helper(pos, seed=3, region_i=2)))

    def test_acceptance_attrs_one_entry_per_year(self):
        bg = self.helper([2020] * 4 + [2024] * 4)
        acc = bg.attrs["acceptance"]
        self.assertEqual([a["year"] for a in acc], [2020, 2024])


class U6PositiveYearsRefused(Base):
    def test_null_or_non_integral_year_raises(self):
        for bad in ([2020, np.nan], [2020, 2020.5]):
            with self.subTest(pos=bad):
                with self.assertRaises(ValueError):
                    self.helper(bad)

    def test_integral_float_accepted(self):
        bg = self.helper([2020.0, 2020.0])        # a CSV column with a null upstream
        self.assertEqual(bg["year"].tolist(), [2020, 2020])


class U7HelperCheck(Base):
    def test_sampler_ignoring_year_makes_helper_raise(self):
        real = train.sample_background_points

        def latest_only(*a, **kw):                # wrong sampler: one vintage
            kw["year"] = "latest"
            return real(*a, **kw)
        with mock.patch.object(train, "sample_background_points", latest_only):
            with self.assertRaises(RuntimeError):
                self.helper([2020] * 3 + [2022] * 3)


# ---- build_datasets wiring (A3): the check reads the TRAINING POSITIVES ----

class _StubDS:
    def __init__(self, df, rd, cat_f, cont_f, label=0.0, **kw):
        self.df, self.label = df, label
        self.labels = np.full(len(df), label, np.float32)

    def __len__(self):
        return len(self.df)


class _FakeRD:
    def __init__(self, frames):
        self.frames = frames

    def positives(self, split):
        return self.frames[("pos", split)]

    def negatives(self, split):
        return self.frames[("neg", split)]


def _frame(years):
    return pd.DataFrame({"longitude": -71.4, "latitude": 44.5,
                         "year": years})


class _FakeData:
    def __init__(self, rd):
        self.rd = rd
        self.config = DataConfig(base_dir="/nonexistent")
        self.block_assignments = ASSIGN

    def __getitem__(self, region):
        return self.rd


class BuildDatasetsWiring(unittest.TestCase):
    """Training positives {2020: 3, 2022: 2}; training negatives, val
    positives and val negatives deliberately carry other years, so wiring
    the wrong frame into the background draw is visible."""

    def setUp(self):
        self.rd = _FakeRD({("pos", "train"): _frame([2020] * 3 + [2022] * 2),
                           ("neg", "train"): _frame([2021] * 5),
                           ("pos", "val"): _frame([2024] * 4),
                           ("neg", "val"): _frame([2023] * 4)})
        self.calls = []

        def fake_sampler(rd, features, n, seed=0, *, region,
                         train_blocks_only, year, assignments=None,
                         in_state=None):
            self.calls.append((int(year), n, seed, train_blocks_only))
            df = _frame([int(year)] * n)
            df["label"], df["weight"] = 0.0, 1.0
            df.attrs["acceptance"] = {"year": int(year)}
            return df
        patches = [mock.patch("acceptance_split.standing_checks"),
                   mock.patch.object(train, "filter_by_year_gap",
                                     lambda df, *a, **k: df),
                   mock.patch.object(train, "GrousePatchDataset", _StubDS),
                   mock.patch.object(train, "sample_background_points",
                                     fake_sampler),
                   mock.patch("builtins.print")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_build(self, ratio):
        return train.build_datasets(_FakeData(self.rd), ["NH"], ["evt"], 64,
                                    background_per_pos=ratio, seed=5)

    def test_background_follows_training_positives(self):
        self.run_build(1.0)
        self.assertEqual(sorted(c[:2] for c in self.calls),
                         [(2020, 3), (2022, 2)])
        self.assertTrue(all(c[3] for c in self.calls))       # training blocks
        self.assertEqual({c[2] for c in self.calls},
                         {(5, 0, 2020), (5, 0, 2022)})

    def test_off_by_default(self):
        self.run_build(0.0)
        self.assertEqual(self.calls, [])

    def test_wrong_frame_wired_into_helper_is_caught(self):
        real = train.background_for_positives

        def wired_to_negatives(rd, features, pos_years, ratio, **kw):
            return real(rd, features, rd.negatives("train")["year"], ratio, **kw)
        with mock.patch.object(train, "background_for_positives",
                               wired_to_negatives):
            with self.assertRaises(RuntimeError):
                self.run_build(1.0)


if __name__ == "__main__":
    unittest.main()
