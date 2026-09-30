"""CR-0015 U1-U6: train.sample_background_points on synthetic rasters.

    python -m unittest tests.test_cr0015_sampler -v

No county file or real data is needed: `in_state` is injected (U1, U2).
Every block id and split in these tests is recomputed with the test's own
pyproj transformer, floor formula and md5 rule (not regions.to_5070,
regions.block_ids or regions.block_split), so a sampler that shares a
mistake with those helpers is still caught (PA-0021(e)).
"""
import hashlib
import math
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
import rasterio
from pyproj import CRS, Transformer
from rasterio.transform import from_origin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import train  # noqa: E402
from grouse_data import NODATA_SENTINELS  # noqa: E402

SEED_TEXT = "42"          # regions.SPLIT_SEED, re-typed
BLOCK_M = 3000.0          # regions.BLOCK_SIZE_M, re-typed; origin (0, 0)
VAL_FRACTION = 0.2        # regions.VAL_FRACTION, re-typed

# A per-region-style Albers that is NOT EPSG:5070 (different lon_0 and
# false origin), so native x/y block ids differ from 5070 block ids.
ALBERS_OTHER = CRS.from_proj4(
    "+proj=aea +lat_0=40 +lon_0=-71 +lat_1=42 +lat_2=46 +x_0=100000 "
    "+y_0=50000 +ellps=GRS80 +units=m +no_defs")
_LL_TO_5070 = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)


def oracle_ids(lon, lat):
    x, y = _LL_TO_5070.transform(np.asarray(lon, float), np.asarray(lat, float))
    return [f"{math.floor(a / BLOCK_M)}_{math.floor(b / BLOCK_M)}"
            for a, b in zip(np.atleast_1d(x), np.atleast_1d(y))]


def md5_frac(block_id):
    return int(hashlib.md5(f"{SEED_TEXT}:{block_id}".encode()).hexdigest(),
               16) % 10_000 / 10_000


class FakeRegion:
    """The two RegionData methods the sampler uses."""

    def __init__(self, path, year=2024):
        self._path, self._year = path, year

    def latest_raster_path(self, feature):
        return self._path

    def raster_years(self, feature):
        return [self._year]


def write_raster(path, arr, crs, transform, nodata):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0],
                       width=arr.shape[1], count=1, dtype=arr.dtype,
                       crs=crs, transform=transform, nodata=nodata) as dst:
        dst.write(arr, 1)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cr0015_sampler_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lonlat_raster(self, name, arr, nodata=-9999, west=-71.0, north=44.5,
                      res=0.01):
        path = os.path.join(self.tmp, name)
        write_raster(path, arr, "EPSG:4326", from_origin(west, north, res, res),
                     nodata)
        return FakeRegion(path)


class U1InState(Base):
    def test_every_point_in_state_and_region_passed(self):
        rd = self.lonlat_raster("u1.tif", np.full((100, 100), 7, np.int16))
        calls = []

        def in_state(lon, lat, region):
            calls.append(region)
            return np.asarray(lon) < -70.5      # "state" west of a line

        df = train.sample_background_points(
            rd, ["evt"], 500, seed=1, region="AA", train_blocks_only=False,
            in_state=in_state)
        self.assertEqual(len(df), 500)
        self.assertTrue((df["longitude"] < -70.5).all())
        self.assertTrue(calls)
        self.assertEqual(set(calls), {"AA"})


class U2TrainBlocks(Base):
    """Five block kinds: (i) listed val, md5 train; (ii) listed train, md5
    val; (iii) unassigned, md5 val; (iv) unassigned, md5 train; (v)
    unassigned, hashed in [vf, VAL_FRACTION)."""
    N = 30_000

    def setUp(self):
        super().setUp()
        # ~30 km x 30 km raster in a non-5070 Albers CRS near (-71, 44.3).
        tf_ll = Transformer.from_crs("EPSG:4326", ALBERS_OTHER, always_xy=True)
        x0, y0 = tf_ll.transform(-71.2, 44.4)
        res = 50.0
        arr = np.full((600, 600), 3, np.int16)
        path = os.path.join(self.tmp, "u2.tif")
        write_raster(path, arr, ALBERS_OTHER, from_origin(x0, y0, res, res),
                     -9999)
        self.rd = FakeRegion(path)
        # Footprint blocks, from a dense pixel-centre enumeration.
        with rasterio.open(path) as src:
            rr, cc = np.meshgrid(np.arange(0, 600, 5), np.arange(0, 600, 5),
                                 indexing="ij")
            xs, ys = rasterio.transform.xy(src.transform, rr.ravel(), cc.ravel())
            to_ll = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
            lon, lat = to_ll.transform(np.asarray(xs), np.asarray(ys))
        ids = pd.Series(oracle_ids(lon, lat))
        share = ids.value_counts(normalize=True)
        # Only blocks well inside the footprint are given a listed kind.
        big = sorted(b for b, s in share.items() if s > 0.004)
        self.vf = 0.10
        md5_val = [b for b in big if md5_frac(b) < self.vf]
        md5_train = [b for b in big if md5_frac(b) >= VAL_FRACTION]
        self.kind_i = md5_train[:3]            # listed val, md5 train
        self.kind_ii = md5_val[:3]             # listed train, md5 val
        assert len(self.kind_i) == 3 and len(self.kind_ii) == 3
        # vf = 10 / 100 exactly: pad with blocks far from the footprint.
        pad_val = [f"9999{k}_9999" for k in range(10 - len(self.kind_i))]
        n_pad_train = 100 - 10 - len(self.kind_ii)
        pad_train = [f"8888{k}_8888" for k in range(n_pad_train)]
        self.assign = pd.DataFrame({
            "block_id": self.kind_i + pad_val + self.kind_ii + pad_train,
            "split": ["val"] * 10 + ["train"] * 90})
        assert abs((self.assign.split == "val").mean() - self.vf) < 1e-12
        self.listed = set(self.assign.block_id)
        self.share = share
        self.kind_of = {b: self.kind(b) for b in share.index}
        # The fixture is only valid if native-x/y block ids differ from
        # the 5070 ids, and every kind (v) block expects >= 50 points.
        nat = [f"{math.floor(a / BLOCK_M)}_{math.floor(b / BLOCK_M)}"
               for a, b in zip(xs, ys)]
        assert np.mean(np.asarray(nat) == ids.to_numpy()) < 0.01
        for kind in ("ii", "iv", "v"):
            exp = self.N * share[[b for b, k in self.kind_of.items()
                                  if k == kind]].sum()
            assert exp >= 50, (kind, exp)

    def kind(self, b):
        if b in self.kind_i:
            return "i"
        if b in self.kind_ii:
            return "ii"
        if b in self.listed:
            return "listed-other"
        if md5_frac(b) < self.vf:
            return "iii"
        if md5_frac(b) < VAL_FRACTION:
            return "v"
        return "iv"

    def kinds(self, df):
        ids = oracle_ids(df["longitude"], df["latitude"])
        return pd.Series([self.kind(b) for b in ids])

    def draw(self, **kw):
        return train.sample_background_points(
            self.rd, ["evt"], self.N, seed=3, region="AA",
            train_blocks_only=True, assignments=self.assign,
            in_state=lambda lon, lat, r: np.ones(len(lon), bool), **kw)

    def violations(self, df):
        """The U2 conditions a sample breaks (empty = U2 passes)."""
        counts = self.kinds(df).value_counts()
        bad = [f"{k}>0" for k in ("i", "iii", "listed-other")
               if int(counts.get(k, 0)) > 0]
        bad += [f"{k}==0" for k in ("ii", "iv", "v")
                if int(counts.get(k, 0)) == 0]
        if len(df) != self.N:
            bad.append(f"n={len(df)}")
        return bad, counts

    def test_kinds(self):
        bad, counts = self.violations(self.draw())
        self.assertEqual(bad, [], counts)

    def test_wrong_samplers_fail_u2(self):
        """PA-0021(a): U2 fails on the constructed wrong samplers the CR's
        table assigns to it (tests/cr0015_wrong_samplers.py, built by an
        independent agent)."""
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import cr0015_wrong_samplers as W
        for name in ("todays_sampler", "unassigned_excluded",
                     "unassigned_train", "val_fraction_constant",
                     "native_xy"):
            try:
                df = W.WRONG_SAMPLERS[name](
                    self.rd, ["evt"], self.N, seed=3, region="AA",
                    train_blocks_only=True, assignments=self.assign,
                    in_state=lambda lon, lat, r: np.ones(len(lon), bool))
            except SystemExit as e:        # cannot deliver n: U2/U4 fail
                bad = [f"shortfall: {e.code}"]
            else:
                bad, counts = self.violations(df)
            print(f"U2 on {name}: violations {bad}")
            self.assertNotEqual(bad, [], name)
        # The over-excluding sampler at a size it can deliver: U2 still
        # fails, on kinds (iv) and (v) (the CR's "U2 (iv)"); n = 50 so it can deliver.
        df = W.WRONG_SAMPLERS["unassigned_excluded"](
            self.rd, ["evt"], 50, seed=3, region="AA",
            train_blocks_only=True, assignments=self.assign,
            in_state=lambda lon, lat, r: np.ones(len(lon), bool))
        counts = self.kinds(df).value_counts()
        print(f"U2 on unassigned_excluded, n=50: {counts.to_dict()}")
        self.assertEqual(int(counts.get("iv", 0)), 0)
        self.assertEqual(int(counts.get("v", 0)), 0)

    def test_kind_v_exists_under_this_vf(self):
        self.assertIn("v", set(self.kind_of.values()))
        self.assertLess(self.vf, VAL_FRACTION)


class U1OnWrongSampler(Base):
    def test_todays_sampler_fails_u1(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import cr0015_wrong_samplers as W
        rd = self.lonlat_raster("u1w.tif", np.full((100, 100), 7, np.int16))
        df = W.WRONG_SAMPLERS["todays_sampler"](
            rd, ["evt"], 500, seed=1, region="AA", train_blocks_only=False,
            in_state=lambda lon, lat, r: np.asarray(lon) < -70.5)
        self.assertFalse((df["longitude"] < -70.5).all())


class U3Validity(Base):
    def test_zero_eligible_nodata_not(self):
        # Float raster: a 0 band, each sentinel, the declared nodata
        # (-5555, not a sentinel) and NaN; one real value 9.
        readings = [0.0, 9.0]
        sentinel_vals = [float(s) for s in NODATA_SENTINELS]
        vals = readings + sentinel_vals + [-5555.0, float("nan")]
        arr = np.repeat(np.array(vals, np.float32), 20)[None, :].repeat(40, 0)
        rd = self.lonlat_raster("u3.tif", arr, nodata=-5555.0)
        df = train.sample_background_points(
            rd, ["tcc"], 2000, seed=5, region="AA", train_blocks_only=False,
            in_state=lambda lon, lat, r: np.ones(len(lon), bool))
        with rasterio.open(rd.latest_raster_path("tcc")) as src:
            v = np.array([x[0] for x in src.sample(zip(df.longitude,
                                                       df.latitude))])
        self.assertEqual(set(np.unique(v).tolist()), {0.0, 9.0})
        self.assertGreater(int((v == 0.0).sum()), 500)


class U4CountAndDeterminism(Base):
    def test_exact_n_and_same_seed_same_points(self):
        rd = self.lonlat_raster("u4.tif", np.full((80, 80), 4, np.int16))
        kw = dict(region="AA", train_blocks_only=False,
                  in_state=lambda lon, lat, r: np.asarray(lat) > 44.2)
        a = train.sample_background_points(rd, ["evt"], 777, seed=9, **kw)
        b = train.sample_background_points(rd, ["evt"], 777, seed=9, **kw)
        c = train.sample_background_points(rd, ["evt"], 777, seed=10, **kw)
        self.assertEqual(len(a), 777)
        pd.testing.assert_frame_equal(a, b)
        self.assertFalse(a[["longitude", "latitude"]].equals(
            c[["longitude", "latitude"]]))


class U5Shortfall(Base):
    def test_shortfall_names_acceptance_rate(self):
        rd = self.lonlat_raster("u5.tif", np.full((50, 50), 4, np.int16))
        with self.assertRaises(SystemExit) as cm:
            train.sample_background_points(
                rd, ["evt"], 100, seed=0, region="AA",
                train_blocks_only=False,
                in_state=lambda lon, lat, r: np.zeros(len(lon), bool))
        self.assertIn("acceptance rate", str(cm.exception.code))
        self.assertIn("AA", str(cm.exception.code))


class U6Signature(Base):
    def setUp(self):
        super().setUp()
        self.rd = self.lonlat_raster("u6.tif", np.full((20, 20), 4, np.int16))

    def test_region_required(self):
        with self.assertRaises(TypeError):
            train.sample_background_points(self.rd, ["evt"], 5,
                                           train_blocks_only=False)

    def test_train_blocks_only_required(self):
        with self.assertRaises(TypeError):
            train.sample_background_points(self.rd, ["evt"], 5, region="AA")

    def test_assignments_required_when_train_blocks_only(self):
        with self.assertRaises(ValueError):
            train.sample_background_points(self.rd, ["evt"], 5, region="AA",
                                           train_blocks_only=True)

    def test_assignments_refused_when_not_train_blocks_only(self):
        with self.assertRaises(ValueError):
            train.sample_background_points(
                self.rd, ["evt"], 5, region="AA", train_blocks_only=False,
                assignments=pd.DataFrame({"block_id": [], "split": []}))


if __name__ == "__main__":
    unittest.main()
