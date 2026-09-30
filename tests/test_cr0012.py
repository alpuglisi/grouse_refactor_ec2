"""CR-0012 implementation tests (pooled thin, global block split, pooled
negative draw, split manifest, standing-check call sites, guards).

    python -m unittest tests.test_cr0012 -v

Written from CR-0012 v2.2.1 and CR-0013's config only (CR-0013 design
rule 4): nothing here reads acceptance_split.py or its tests. The
end-to-end tests run both scripts on a small synthetic data tree built
in a temp directory (rasters included); regions.verify_partition is
patched there, because it reads the real TIGER county file.
"""
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import regions  # noqa: E402
import prepare_training_data as ptd  # noqa: E402
import generate_negatives as gn  # noqa: E402
from grouse_data import PATH_TEMPLATES, MissingDataError  # noqa: E402



def _read(path, mode="rb"):
    with open(path, mode) as f:
        return f.read()


CONFIG = json.loads(_read(os.path.join(ROOT, "docs", "quality",
                                       "acceptance_split.json"), "r"))


def identity_5070(lon, lat):
    return (np.atleast_1d(np.asarray(lon, dtype=np.float64)),
            np.atleast_1d(np.asarray(lat, dtype=np.float64)))


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------
class Constants(unittest.TestCase):
    def test_regions_constants(self):
        self.assertEqual(regions.BLOCK_ORIGIN_5070, (0.0, 0.0))
        self.assertEqual(regions.VAL_FRACTION, 0.2)
        self.assertEqual(regions.SPLIT_SEED, 42)
        self.assertEqual(regions.WINDOW_PX, 64)

    def test_columns_equal_config(self):
        cols = CONFIG["columns"]
        self.assertEqual(ptd.POSITIVE_COLUMNS, cols["positives"])
        self.assertEqual(ptd.BLOCK_COLUMNS, cols["block_assignments"])
        self.assertEqual(gn.NEGATIVE_COLUMNS, cols["negatives"])
        self.assertEqual(gn.POOL_COLUMNS, cols["pool"])
        self.assertEqual(gn.ENVELOPE_FEATURES,
                         CONFIG["envelope"]["envelope_features"])

    def test_row_order_equal_config(self):
        ro = CONFIG["row_order"]
        self.assertEqual(ptd.POSITIVE_ORDER, ro["positives"])
        self.assertEqual(gn.NEGATIVE_ORDER, ro["negatives"])
        self.assertEqual(gn.POOL_ORDER, ro["pool"])

    def test_measured_constants_and_environment(self):
        self.assertEqual(ptd.measured_constants(), CONFIG["constants"])
        env = ptd.measured_environment()
        want = {k: v for k, v in CONFIG["environment"].items()
                if k != "op_rule"}
        self.assertEqual(set(env), set(want))
        self.assertEqual(env, want)
        self.assertEqual(ptd.hash_spec(), CONFIG["hash_spec"])

    def test_path_templates(self):
        for k in ("block_assignments", "candidate_pool", "split_manifest",
                  "acceptance_record"):
            self.assertEqual(PATH_TEMPLATES[k], CONFIG["paths"][k])
        for k in ("thinned_positives", "train_positives", "val_positives",
                  "negatives", "train_negatives", "val_negatives",
                  "gbif_candidates", "envelope_metrics"):
            ours = {"thinned_positives": "thinned"}.get(k, k)
            self.assertEqual(PATH_TEMPLATES[ours], CONFIG["paths"][k])
        self.assertEqual(PATH_TEMPLATES["evaluated"],
                         CONFIG["paths"]["sightings"])

    def test_removed_defaults_and_flags(self):
        for name in ("REGIONS_DEFAULT", "MIN_SPACING_M_DEFAULT",
                     "BLOCK_SIZE_M_DEFAULT", "VAL_FRACTION_DEFAULT",
                     "RANDOM_SEED_DEFAULT"):
            self.assertFalse(hasattr(ptd, name), name)
        for mod, flag in ((ptd, "--regions"), (ptd, "--seed"),
                          (ptd, "--min-spacing-m"), (ptd, "--block-size-m"),
                          (ptd, "--val-fraction"), (ptd, "--habitat-only"),
                          (gn, "--regions"), (gn, "--seed")):
            with self.subTest(mod=mod.__name__, flag=flag), \
                    mock.patch.object(sys, "argv", ["x", flag, "1"]), \
                    mock.patch.object(mod, "run",
                                      side_effect=AssertionError("ran")), \
                    redirect_stdout(io.StringIO()), \
                    mock.patch("sys.stderr", io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    mod.main()
                self.assertEqual(cm.exception.code, 2)


class Helpers(unittest.TestCase):
    def test_order_key(self):
        text = "-69.500000,45.000000"
        want = int.from_bytes(hashlib.blake2b(
            f"42:{text}".encode(), digest_size=8).digest(), "big")
        self.assertEqual(regions.order_key(text), want)
        self.assertEqual(regions.coord_text(-69.5, 45.0), text)

    def test_block_ids(self):
        self.assertEqual(regions.block_ids([0.0, 2999.999, 3000.0, -0.001],
                                           [0.0, -1.0, 6000.0, 3000.0]),
                         ["0_0", "0_-1", "1_2", "-1_1"])

    def test_window_in_bounds(self):
        import rasterio
        from rasterio.transform import from_origin
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "r.tif")
        with rasterio.open(p, "w", driver="GTiff", width=100, height=80,
                           count=1, dtype="int16", crs="EPSG:5070",
                           transform=from_origin(1000.0, 5000.0, 30.0, 30.0),
                           nodata=-9999) as dst:
            dst.write(np.full((1, 80, 100), -9999, dtype=np.int16))
        h = regions.WINDOW_PX // 2

        def xy(row, col):   # pixel centre
            return 1000.0 + (col + 0.5) * 30.0, 5000.0 - (row + 0.5) * 30.0
        cases = [((h, h), True), ((h - 1, h), False), ((h, h - 1), False),
                 ((80 - (64 - h), 100 - (64 - h)), True),
                 ((80 - (64 - h) + 1, h), False),
                 ((h, 100 - (64 - h) + 1), False)]
        with rasterio.open(p) as src:
            for (row, col), want in cases:
                x, y = xy(row, col)
                self.assertEqual(src.index(x, y), (row, col))
                self.assertEqual(bool(regions.window_in_bounds(src, x, y)[0]),
                                 want, (row, col))
            # all-nodata window still counts: nodata is not considered
            self.assertTrue(regions.window_in_bounds(src, *xy(h, h))[0])


class Thinning(unittest.TestCase):
    def frame(self, xs, ys):
        return pd.DataFrame({"longitude": xs, "latitude": ys,
                             "tag": range(len(xs))})

    def test_exactly_min_spacing_is_kept(self):
        with mock.patch.object(ptd, "to_5070", identity_5070):
            out = ptd.thin_by_min_distance(self.frame([0.0, 30.0], [0.0, 0.0]))
            self.assertEqual(len(out), 2)
            out = ptd.thin_by_min_distance(self.frame([0.0, 18.0], [0.0, 24.0]))
            self.assertEqual(len(out), 2)                       # 3-4-5: d2 = 900
            out = ptd.thin_by_min_distance(
                self.frame([0.0, 29.999999], [0.0, 0.0]))
            self.assertEqual(len(out), 1)

    def test_visit_order_is_hash_order(self):
        xs, ys = [0.0, 20.0, 40.0], [0.0, 0.0, 0.0]
        keys = [regions.order_key(regions.coord_text(x, y))
                for x, y in zip(xs, ys)]
        with mock.patch.object(ptd, "to_5070", identity_5070):
            out = ptd.thin_by_min_distance(self.frame(xs, ys))
        # independent greedy in ascending key order
        kept = []
        for i in sorted(range(3), key=lambda i: (keys[i], xs[i], ys[i])):
            if all((xs[i] - xs[j]) ** 2 + (ys[i] - ys[j]) ** 2 >= 900
                   for j in kept):
                kept.append(i)
        self.assertEqual(sorted(out["tag"]), sorted(kept))

    def test_permutation_invariant(self):
        rng = np.random.default_rng(0)
        xs = rng.uniform(-69.01, -69.0, 400)
        ys = rng.uniform(45.0, 45.01, 400)
        df = self.frame(xs, ys)
        a = ptd.thin_by_min_distance(df)
        b = ptd.thin_by_min_distance(df.sample(frac=1, random_state=3))
        self.assertLess(len(a), 400)
        self.assertEqual(sorted(a["tag"]), sorted(b["tag"]))
        # the result honours the spacing
        x, y = ptd.to_5070(a["longitude"], a["latitude"])
        d2 = (x[:, None] - x[None]) ** 2 + (y[:, None] - y[None]) ** 2
        np.fill_diagonal(d2, np.inf)
        self.assertTrue((d2 >= 900).all())


class BlockSplit(unittest.TestCase):
    def test_rule(self):
        rng = np.random.default_rng(1)
        lon = rng.uniform(-70.5, -69.5, 300)
        lat = rng.uniform(44.5, 45.5, 300)
        df = pd.DataFrame({"longitude": lon, "latitude": lat})
        bid, split, table = ptd.assign_spatial_blocks(df)
        x, y = ptd.to_5070(lon, lat)
        self.assertEqual(list(bid), regions.block_ids(x, y))
        counts = pd.Series(list(bid)).value_counts()
        order = sorted(counts.index, key=lambda b: (regions.order_key(b), b))
        target = int(round(0.2 * 300))
        val, run = set(), 0
        for b in order:
            if run >= target:
                break
            val.add(b)
            run += counts[b]
        self.assertEqual(set(table.loc[table.split == "val", "block_id"]), val)
        self.assertEqual(list(table.columns), ["block_id", "split", "n"])
        self.assertEqual(list(table["block_id"]), sorted(table["block_id"]))
        self.assertEqual(int(table["n"].sum()), 300)
        self.assertTrue(((split == "val") == bid.isin(val)).all())


class Dedup(unittest.TestCase):
    def pool(self):
        return pd.DataFrame({
            "longitude": [-70.000001, -70.000004, -71.0, -70.0000011],
            "latitude": [44.0, 44.000002, 44.5, 44.0],
            "gbif_id": [30, 10, 20, 5],
            "year": [2020, 2021, 2022, 2023],
            "state": ["NH", "NH", "VT", "NH"],
            "region": ["NH", "NH", "VT", "NH"]})

    def test_min_gbif_id_kept_order_free(self):
        p = self.pool()
        a = gn.dedup_min_gbif_id(p)
        b = gn.dedup_min_gbif_id(p.iloc[::-1].reset_index(drop=True))
        self.assertEqual(sorted(a["gbif_id"]), [5, 20])
        pd.testing.assert_frame_equal(
            a.sort_values("gbif_id").reset_index(drop=True),
            b.sort_values("gbif_id").reset_index(drop=True))

    def test_raises(self):
        p = self.pool()
        p.loc[1, "state"] = "VT"
        with self.assertRaises(ValueError):
            gn.dedup_min_gbif_id(p)
        p = self.pool()
        p.loc[1, "gbif_id"] = 30
        with self.assertRaises(ValueError):
            gn.dedup_min_gbif_id(p)
        p = self.pool()
        p["gbif_id"] = p["gbif_id"].astype(float)
        p.loc[0, "gbif_id"] = np.nan
        with self.assertRaises(ValueError):
            gn.dedup_min_gbif_id(p)


class Buffer(unittest.TestCase):
    def test_boundary(self):
        with mock.patch.object(gn, "to_5070", identity_5070):
            drop = gn.buffer_drop_mask(
                np.array([300.0, 180.0, 300.000001, -1000.0]),
                np.array([0.0, 240.0, 0.0, 0.0]),
                np.array([0.0, -5000.0]), np.array([0.0, 0.0]))
        self.assertEqual(drop.tolist(), [True, True, False, False])


class SplitForUnassigned(unittest.TestCase):
    def test_md5_rule(self):
        # The rule lives in regions.block_split since CR-0015 section 1;
        # vf is the val share of the assignment rows.
        for n_val, n_all in ((0, 4), (197, 1000), (2, 4), (4, 4)):
            vf = n_val / n_all
            assign = pd.DataFrame({
                "block_id": [f"z{i}" for i in range(n_all)],
                "split": ["val"] * n_val + ["train"] * (n_all - n_val)})
            ids = ["0_0", "-12_345", "600_1500", "7_-3"]
            want = []
            for b in ids:
                h = int(hashlib.md5(f"42:{b}".encode()).hexdigest(), 16)
                want.append("val" if h % 10000 < vf * 10000 else "train")
            self.assertEqual(list(regions.block_split(ids, assign)), want)

    def test_assign_split(self):
        blocks = pd.DataFrame({"block_id": ["a", "b", "c", "d", "e"],
                               "split": ["val", "train", "train", "train",
                                         "train"], "n": 1})
        cand = pd.DataFrame({"longitude": [-70.0, -69.0],
                             "latitude": [44.0, 45.0]})
        x, y = ptd.to_5070(cand.longitude, cand.latitude)
        ids = regions.block_ids(x, y)
        blocks.loc[4, "block_id"] = ids[0]
        blocks.loc[4, "split"] = "val"
        out = gn.assign_split(cand, blocks)
        self.assertEqual(list(out["block_id"]), ids)
        self.assertEqual(out["split"].iloc[0], "val")
        vf = 2 / 5
        h = int(hashlib.md5(f"42:{ids[1]}".encode()).hexdigest(), 16)
        self.assertEqual(out["split"].iloc[1],
                         "val" if h % 10000 < vf * 10000 else "train")


class Draw(unittest.TestCase):
    def sub(self, n, seed=0, nonveg_frac=0.3):
        rng = np.random.default_rng(seed)
        return pd.DataFrame({
            "longitude": np.round(rng.uniform(-70, -69, n), 6),
            "latitude": np.round(rng.uniform(44, 45, n), 6),
            "weight": rng.choice([0.1, 1.0, 2.5, 10.0], n),
            "is_nonveg": rng.uniform(size=n) < nonveg_frac},
            index=[7] * n)       # duplicate labels: selection is positional

    def reference(self, sub, n):
        rows = []
        for i, (lo, la, w) in enumerate(zip(sub.longitude, sub.latitude,
                                            sub.weight)):
            k = int.from_bytes(hashlib.blake2b(
                f"42:neg:{lo:.6f},{la:.6f}".encode(),
                digest_size=8).digest(), "big")
            rows.append((math.log((k + 0.5) / 2 ** 64) / w, k, i))
        rows.sort(key=lambda t: (-t[0], t[1]))
        return sorted(i for _, _, i in rows[:n])

    def test_es_select_matches_reference(self):
        sub = self.sub(200)
        got = gn.es_select(sub, 50)
        want = sub.iloc[self.reference(sub, 50)]
        pd.testing.assert_frame_equal(got, want)
        perm = sub.sample(frac=1, random_state=5)
        a = gn.es_select(perm, 50)
        self.assertEqual(
            sorted(zip(a.longitude, a.latitude)),
            sorted(zip(want.longitude, want.latitude)))

    def test_counts_and_cap(self):
        sub = self.sub(400, seed=2)
        got, d = gn.draw_region_split(sub, 101)
        n = int(round(101 * 1.0))
        n_nv = min(int(round(n * 0.3)), int(sub.is_nonveg.sum()))
        self.assertEqual(d, {"n": n, "n_nv": n_nv, "n_hab": n - n_nv})
        self.assertEqual(len(got), n)
        self.assertEqual(int(got.is_nonveg.sum()), n_nv)
        # NonVeg pool smaller than the cap: the rest comes from habitat
        sub2 = self.sub(400, seed=3, nonveg_frac=0.02)
        got, d = gn.draw_region_split(sub2, 100)
        self.assertEqual(d["n_nv"], int(sub2.is_nonveg.sum()))
        self.assertEqual(d["n_hab"], 100 - d["n_nv"])

    def test_habitat_shortfall_raises(self):
        sub = self.sub(40, seed=4, nonveg_frac=0.5)
        with self.assertRaises(RuntimeError):
            gn.draw_region_split(sub, 100)


class StandingCheckCallSites(unittest.TestCase):
    def test_build_datasets_calls_standing_checks_first(self):
        import acceptance_split
        import train
        stop = RuntimeError("standing")
        with mock.patch.object(acceptance_split, "standing_checks",
                               side_effect=stop) as sc, \
                mock.patch.object(train, "split_features",
                                  side_effect=AssertionError("past check")):
            data = mock.Mock()
            data.config.base_dir = "/some/tree"
            with self.assertRaises(RuntimeError) as cm:
                train.build_datasets(data, ["ME"], ["evt"], 48, jitter=8,
                                     augment=True)
        self.assertIs(cm.exception, stop)
        # The tree training reads is the tree checked (code review F1).
        sc.assert_called_once_with(48, 8, True, data_root="/some/tree")

    def test_entry_points_use_build_datasets(self):
        import ast
        for f in ("train.py", "calibrate.py", "bench_pipeline.py"):
            tree = ast.parse(_read(os.path.join(ROOT, f), "r"))
            calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and getattr(n.func, "id", None) == "build_datasets"]
            self.assertTrue(calls, f)
            # no other dataset construction bypasses the check
            direct = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                      and getattr(n.func, "id", None) == "GrousePatchDataset"]
            if f != "train.py":
                self.assertEqual(direct, [], f)


class Guards(unittest.TestCase):
    def test_stale_copies_exit_first(self):
        import check_partition as cp
        for p in ("clean.py", "legacy/gen_negs.py"):
            with self.subTest(p=p):
                path = os.path.join(ROOT, p)
                self.assertTrue(cp.guard_first(path))
                with open(path) as f:
                    self.assertTrue(f.readline().startswith("raise SystemExit("))
                # A scratch cwd: a regressed guard must not reach real data/.
                with tempfile.TemporaryDirectory() as cwd:
                    r = subprocess.run([sys.executable, path], cwd=cwd,
                                       capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("BUG-0031", r.stderr)


class ExceptionsPropagate(unittest.TestCase):
    def run_main(self, exc):
        with mock.patch.object(sys, "argv", ["generate_negatives.py"]), \
                mock.patch.object(gn, "run", side_effect=exc), \
                redirect_stdout(io.StringIO()) as out, \
                mock.patch("sys.stderr", io.StringIO()) as err:
            with self.assertRaises(type(exc)) as cm:
                gn.main()
        return cm.exception, out.getvalue(), err.getvalue()

    def test_missing_data_propagates(self):
        e = MissingDataError("no file")
        got, _, _ = self.run_main(e)
        self.assertIs(got, e)

    def test_other_logged_and_reraised(self):
        e = KeyError("boom")
        got, out, err = self.run_main(e)
        self.assertIs(got, e)
        self.assertIn("KeyError", out)
        self.assertIn("Traceback", err)


class AtomicWrite(unittest.TestCase):
    def test_replace_and_no_temp_left(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "f.csv")
        with open(p, "w") as f:
            f.write("old")
        ptd.atomic_write(p, b"new")
        self.assertEqual(_read(p), b"new")
        self.assertEqual(os.listdir(d), ["f.csv"])


# ---------------------------------------------------------------------------
# End to end on a synthetic data tree
# ---------------------------------------------------------------------------
CENTERS = {"ME": (-69.5, 45.0), "NH": (-71.5, 44.0)}   # VT: NH + 6 km east
HALF = 9000.0          # raster half-width, m
PX = 30.0
NPX = int(2 * HALF / PX)
YEAR = 2024
EVT = {7001: "Hardwood", 7002: "Developed-Low Intensity", 7003: "Conifer"}


def _to_lonlat(x, y):
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)
    return t.transform(x, y)


def region_centres_5070():
    out = {}
    for r, (lo, la) in CENTERS.items():
        x, y = ptd.to_5070([lo], [la])
        out[r] = (float(x[0]), float(y[0]))
    out["VT"] = (out["NH"][0] + 6000.0, out["NH"][1])
    return out


def write_raster(path, x0, ytop, arr, nodata=-9999):
    import rasterio
    from rasterio.transform import from_origin
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1],
                       height=arr.shape[0], count=1, dtype=str(arr.dtype),
                       crs="EPSG:5070", transform=from_origin(x0, ytop, PX, PX),
                       nodata=nodata) as dst:
        dst.write(arr[None])


def build_tree(d, seed=0):
    """Synthetic data tree for all REGIONS under d. Returns the set of
    [lon, lat] (5 dp) the patched verify_partition reports."""
    from models import FEATURE_SPEC
    from analyze_grouse import (ENVELOPE_SCHEME, build_envelope_id,
                                fit_scheme_binners)
    rng = np.random.default_rng(seed)
    for sub in ("data/landfire/attribute_tables", "data/pipeline",
                "data/negatives", "data/roads"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    pd.DataFrame({"VALUE": list(EVT), "EVT_PHYS": list(EVT.values()),
                  "EVT_GP_N": list(EVT.values())}).to_csv(
        os.path.join(d, "data/landfire/attribute_tables/LF2024_EVT.csv"),
        index=False)
    with open(os.path.join(d, "data/roads/tl_2023_us_county.zip"), "wb") as f:
        f.write(b"placeholder (verify_partition is patched in these tests)")

    cent = region_centres_5070()
    cols = np.arange(NPX)[None, :].repeat(NPX, 0)
    rows = np.arange(NPX)[:, None].repeat(NPX, 1)
    bad = set()
    gid = 1000
    for r in regions.REGIONS:
        cx, cy = cent[r]
        x0, ytop = cx - HALF, cy + HALF
        for feat in FEATURE_SPEC:
            if feat == "evt":
                arr = np.where(cols < 100, 7002,
                               np.where(rows < 300, 7001, 7003)).astype(np.int16)
            elif feat == "sclass":
                arr = np.where(rows < 50, 120, 5).astype(np.int16)
            elif feat == "evh":
                arr = (100 + cols // 10).astype(np.int16)
            else:
                arr = np.ones((NPX, NPX), dtype=np.int16)
            write_raster(os.path.join(d, f"data/landfire/{r}_{YEAR}_{feat}.tif"),
                         x0, ytop, arr)
        if r == "ME":   # empty placeholder vintage: validation falls back
            write_raster(os.path.join(d, "data/landfire/ME_2025_cc.tif"),
                         x0, ytop, np.full((NPX, NPX), -9999, dtype=np.int16))

        # --- evaluated sightings ---------------------------------------
        n = 160
        px = cx + rng.uniform(-7000, 7000, n)
        py = cy + rng.uniform(-7000, 7000, n)
        px = np.concatenate([px, cx + np.array([8700.0, -8800.0, 0.0]),
                             px[:12] + rng.uniform(-8, 8, 12)])
        py = np.concatenate([py, cy + np.array([0.0, 0.0, 8900.0]),
                             py[:12] + rng.uniform(-8, 8, 12)])
        lon, lat = _to_lonlat(px, py)
        m = len(px)
        years = rng.choice([2023, 2024, 2025], m, p=[0.2, 0.7, 0.1])
        ev = pd.DataFrame({
            "longitude": np.round(lon, 6), "latitude": np.round(lat, 6),
            "state": r, "year": years, "n_visits": 1, "first_year": years,
            "last_year": years, "x_5070": px, "y_5070": py,
            "evt": rng.choice([7001, 7003], m), "evh": rng.integers(100, 160, m),
            "evc": 1, "sclass": rng.choice([5, 6], m), "fdist": -1, "ch": 1.5,
            "cc": 2.0, "evt_group": "g",
            "nonveg_landcover": rng.uniform(size=m) < 0.1,
            "spatial_density": rng.uniform(size=m), "spatial_zone": "z",
            "region": r, "env_zone": "e", "extra_col": 7})
        ev["evt_phys"] = ev["evt"].map(EVT)
        hab = ev[~ev["nonveg_landcover"]]
        binners = fit_scheme_binners(hab, ENVELOPE_SCHEME)
        ev["envelope_id"] = build_envelope_id(ev, ENVELOPE_SCHEME,
                                              binners=binners)
        ev.to_csv(os.path.join(d, PATH_TEMPLATES["evaluated"].format(region=r)),
                  index=False)
        # candidate envelopes too, so the metrics table covers them
        probe = pd.DataFrame({"evt_phys": ["Hardwood", "Conifer"] * 2,
                              "sclass": [5, 5, 5, 5],
                              "evh": [100, 100, 250, 250]})
        ids = sorted(set(ev["envelope_id"]) | set(
            build_envelope_id(probe, ENVELOPE_SCHEME, binners=binners)))
        classes = ["Selected", "Avoided", "Neutral",
                   "Landscape-Rare (low availability)", "Selected"]
        ratios = [3.0, 0.05, 1.0, 0.5, np.nan]
        pd.DataFrame({"Envelope": ids,
                      "Classification": [classes[i % 5] for i in range(len(ids))],
                      "Selection_Ratio": [ratios[i % 5] for i in range(len(ids))]
                      }).to_csv(os.path.join(
                          d, PATH_TEMPLATES["envelope_metrics"].format(region=r)),
                          index=False)

        # --- GBIF candidates -------------------------------------------
        k = 1100
        qx = cx + rng.uniform(-8950, 8950, k)
        qy = cy + rng.uniform(-8950, 8950, k)
        # 25 near sightings (inside the buffer)
        qx[:25] = px[:25] + rng.uniform(-150, 150, 25)
        qy[:25] = py[:25] + rng.uniform(-150, 150, 25)
        qlon, qlat = _to_lonlat(qx, qy)
        cyears = rng.choice([2023, 2024, 2025], k, p=[0.2, 0.7, 0.1]).astype(float)
        cyears[25:27] = np.nan
        unc = rng.uniform(1, 900, k)
        unc[rng.uniform(size=k) < 0.05] = 5000.0
        unc[rng.uniform(size=k) < 0.03] = np.nan
        cand = pd.DataFrame({
            "longitude": np.round(qlon, 6), "latitude": np.round(qlat, 6),
            "common_name": rng.choice(["Blue Jay", "Crow"], k),
            "obs_date": "2024-05-01", "year": cyears, "state": r,
            "gbif_id": np.arange(gid, gid + k), "coord_uncertainty_m": unc})
        cand.loc[[300, 301], "coord_uncertainty_m"] = 10.0   # reach step 4
        gid += k + 100
        # duplicates on the 5 dp key: different gbif_id and year
        dup = cand.iloc[100:140].copy()
        dup["longitude"] = dup["longitude"] + 1e-6
        dup["year"] = 2023.0
        dup["coord_uncertainty_m"] = 10.0
        dup["gbif_id"] = np.arange(gid, gid + len(dup))[::-1] - 5000
        gid += 200
        cand = pd.concat([cand, dup], ignore_index=True)
        cand.to_csv(os.path.join(
            d, PATH_TEMPLATES["gbif_candidates"].format(region=r)), index=False)
        for i in (300, 301):
            bad.add(key5(cand.longitude[i], cand.latitude[i]))
    return bad


def key5(lon, lat):
    """The 5 dp key as pandas/numpy round it (not Python's round())."""
    return (float(np.round(np.float64(lon), 5)),
            float(np.round(np.float64(lat), 5)))


def fake_verify_partition(bad):
    def vp(lon, lat, state):
        lon = np.asarray(lon, dtype=float)
        lat = np.asarray(lat, dtype=float)
        idx = [i for i in range(len(lon)) if key5(lon[i], lat[i]) in bad]
        return pd.DataFrame({"longitude": lon[idx], "latitude": lat[idx],
                             "state": np.asarray(state)[idx],
                             "polygon_state": None}, index=idx)
    return vp


def run_both(d, bad):
    with mock.patch.object(gn, "verify_partition", fake_verify_partition(bad)), \
            redirect_stdout(io.StringIO()):
        ptd.run(d)
        gn.run(d)


def output_bytes(d):
    out = {}
    for base, _, files in os.walk(os.path.join(d, "data")):
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, d)
            if rel.startswith(("data/pipeline/", "data/negatives/")) and not (
                    "evaluated_sightings" in rel or "envelope_metrics" in rel
                    or "gbif_negatives" in rel):
                out[rel] = _read(p)
    return out


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        cls.bad = build_tree(cls.d)
        run_both(cls.d, cls.bad)
        cls.out = output_bytes(cls.d)
        cls.manifest = json.loads(cls.out["data/pipeline/split_manifest.json"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d)

    def csv(self, rel):
        return pd.read_csv(io.BytesIO(self.out[rel]), float_precision="round_trip")

    def test_outputs_present(self):
        want = {"data/pipeline/block_assignments.csv",
                "data/negatives/candidate_pool.csv",
                "data/pipeline/split_manifest.json"}
        for r in regions.REGIONS:
            for k in ("thinned", "train_positives", "val_positives",
                      "negatives", "train_negatives", "val_negatives"):
                want.add(PATH_TEMPLATES[k].format(region=r))
        self.assertEqual(set(self.out), want)

    def test_second_run_byte_identical(self):
        run_both(self.d, self.bad)
        self.assertEqual(output_bytes(self.d), self.out)

    def test_permuted_inputs_byte_identical(self):
        d2 = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d2)
        shutil.copytree(os.path.join(self.d, "data"), os.path.join(d2, "data"))
        for base, _, files in os.walk(os.path.join(d2, "data")):
            for f in files:
                p = os.path.join(base, f)
                if any(s in f for s in ("evaluated_sightings", "gbif_negatives",
                                        "envelope_metrics")):
                    df = pd.read_csv(p, float_precision="round_trip")
                    df.sample(frac=1, random_state=11).to_csv(p, index=False)
                elif f.endswith((".csv", ".json")) and "attribute_tables" not in p:
                    os.remove(p)       # outputs: start clean
        run_both(d2, self.bad)
        out2 = output_bytes(d2)
        m2 = json.loads(out2.pop("data/pipeline/split_manifest.json"))
        out1 = dict(self.out)
        m1 = json.loads(out1.pop("data/pipeline/split_manifest.json"))
        self.assertEqual(set(out2), set(out1))
        for k in out1:
            self.assertEqual(out2[k], out1[k], k)
        for sec in ("positives", "negatives"):
            a, b = dict(m1[sec]), dict(m2[sec])
            ia, ib = a.pop("inputs"), b.pop("inputs")
            self.assertEqual(set(ia), set(ib))
            self.assertEqual(a, b, sec)

    def test_manifest_schema(self):
        schema = CONFIG["manifest_schema"]
        common = {k for k in schema if not k.startswith("_")} - {"draw", "dropped"}
        m = self.manifest
        self.assertEqual(sorted(m), sorted(CONFIG["columns"]["split_manifest_sections"]))
        self.assertEqual(set(m["positives"]), common)
        self.assertEqual(set(m["negatives"]), common | {"draw", "dropped"})
        env = {k: v for k, v in CONFIG["environment"].items() if k != "op_rule"}
        for sec, steps in (("positives", 6), ("negatives", 11)):
            s = m[sec]
            self.assertEqual(s["constants"], CONFIG["constants"])
            self.assertEqual(s["hash_spec"], CONFIG["hash_spec"])
            self.assertEqual(s["environment"], env)
            self.assertIsInstance(s["commit"], str)
            self.assertEqual(len(s["commit"]), 40)
            self.assertIsInstance(s["dirty"], bool)
            self.assertEqual(sorted(s["counts"]), sorted(regions.REGIONS))
            for r in regions.REGIONS:
                self.assertEqual(sorted(s["counts"][r], key=int),
                                 [str(i) for i in range(1, steps + 1)])
            for rel, h in s["inputs"].items():
                self.assertFalse(os.path.isabs(rel))
                self.assertEqual(h, hashlib.sha256(
                    _read(os.path.join(self.d, rel))).hexdigest())
        # outputs: exactly the files each script wrote, with their digests
        pos_out = {PATH_TEMPLATES[k].format(region=r)
                   for r in regions.REGIONS
                   for k in ("thinned", "train_positives", "val_positives")}
        pos_out.add("data/pipeline/block_assignments.csv")
        neg_out = {PATH_TEMPLATES[k].format(region=r)
                   for r in regions.REGIONS
                   for k in ("negatives", "train_negatives", "val_negatives")}
        neg_out.add("data/negatives/candidate_pool.csv")
        self.assertEqual(set(m["positives"]["outputs"]), pos_out)
        self.assertEqual(set(m["negatives"]["outputs"]), neg_out)
        for sec in ("positives", "negatives"):
            for rel, h in m[sec]["outputs"].items():
                self.assertEqual(h, hashlib.sha256(self.out[rel]).hexdigest())
        # every raster touched is an input, the rejected placeholder included
        pin = m["positives"]["inputs"]
        self.assertIn("data/landfire/ME_2025_cc.tif", pin)
        self.assertIn("data/landfire/VT_2024_road_dist.tif", pin)
        nin = m["negatives"]["inputs"]
        for r in regions.REGIONS:
            self.assertIn(PATH_TEMPLATES["evaluated"].format(region=r), pin)
            for k in ("evaluated", "gbif_candidates", "envelope_metrics"):
                self.assertIn(PATH_TEMPLATES[k].format(region=r), nin)
        self.assertIn("data/landfire/attribute_tables/LF2024_EVT.csv", nin)
        self.assertIn("data/landfire/ME_2025_cc.tif", nin)
        # dropped: sorted [lon, lat] pairs, the patched partition exceptions
        dropped = m["negatives"]["dropped"]
        self.assertEqual(dropped, sorted(dropped))
        self.assertEqual({key5(a, b) for a, b in dropped}, self.bad)
        # draw object
        for r in regions.REGIONS:
            for s in ("train", "val"):
                dd = m["negatives"]["draw"][r][s]
                self.assertEqual(set(dd), {"n", "n_nv", "n_hab"})
                self.assertEqual(dd["n"], dd["n_nv"] + dd["n_hab"])

    def test_canonical_order_and_columns(self):
        for r in regions.REGIONS:
            for kind, cols in (("thinned", ptd.POSITIVE_COLUMNS),
                               ("negatives", gn.NEGATIVE_COLUMNS)):
                df = self.csv(PATH_TEMPLATES[kind].format(region=r))
                self.assertEqual(list(df.columns), cols)
                s = df.sort_values(["longitude", "latitude"], kind="mergesort")
                self.assertTrue((s.index == df.index).all(), (r, kind))
                self.assertTrue((df["region"] == r).all())
                self.assertTrue((df["state"] == r).all())
                for sp in ("train", "val"):
                    part = self.csv(PATH_TEMPLATES[f"{sp}_{kind if kind == 'negatives' else 'positives'}"].format(region=r))
                    want = df[df["split"] == sp].reset_index(drop=True)
                    pd.testing.assert_frame_equal(part, want)
        pool = self.csv("data/negatives/candidate_pool.csv")
        self.assertEqual(list(pool.columns), gn.POOL_COLUMNS)
        s = pool.sort_values(["region", "longitude", "latitude"], kind="mergesort")
        self.assertTrue((s.index == pool.index).all())
        b = self.csv("data/pipeline/block_assignments.csv")
        self.assertEqual(list(b["block_id"]), sorted(b["block_id"]))

    def test_invariants(self):
        pos = pd.concat([self.csv(PATH_TEMPLATES["thinned"].format(region=r))
                         for r in regions.REGIONS], ignore_index=True)
        neg = pd.concat([self.csv(PATH_TEMPLATES["negatives"].format(region=r))
                         for r in regions.REGIONS], ignore_index=True)
        pool = self.csv("data/negatives/candidate_pool.csv")
        blocks = self.csv("data/pipeline/block_assignments.csv")
        # pooled spacing, pooled over regions
        for df in (pos, pool):
            x, y = ptd.to_5070(df.longitude, df.latitude)
            d2 = (x[:, None] - x[None]) ** 2 + (y[:, None] - y[None]) ** 2
            np.fill_diagonal(d2, np.inf)
            self.assertGreaterEqual(d2.min(), 900.0)
        # no block holds both train and val, across classes
        both = pd.concat([pos[["block_id", "split"]], neg[["block_id", "split"]]])
        self.assertEqual(int((both.groupby("block_id")["split"].nunique() > 1).sum()), 0)
        # block table matches the positives
        grp = pos.groupby("block_id")
        self.assertEqual(sorted(blocks["block_id"]), sorted(grp.groups))
        self.assertEqual(dict(zip(blocks.block_id, blocks.n)),
                         grp.size().to_dict())
        self.assertEqual(int(round(0.2 * len(pos))) <= int((pos.split == "val").sum()), True)
        # buffer: every pool row > 300 m from every sighting
        ev = pd.concat([pd.read_csv(os.path.join(
            self.d, PATH_TEMPLATES["evaluated"].format(region=r)))
            for r in regions.REGIONS])
        sx, sy = ptd.to_5070(ev.longitude, ev.latitude)
        px, py = ptd.to_5070(pool.longitude, pool.latitude)
        d2 = (px[:, None] - sx[None]) ** 2 + (py[:, None] - sy[None]) ** 2
        self.assertGreater(d2.min(), 300.0 ** 2)
        # dedup: duplicated keys resolved to the smallest gbif_id
        raw = pd.concat([pd.read_csv(os.path.join(
            self.d, PATH_TEMPLATES["gbif_candidates"].format(region=r)))
            for r in regions.REGIONS])
        raw = raw[~(raw.coord_uncertainty_m > 1000)]
        key = raw[["longitude", "latitude"]].round(5)
        mins = raw.groupby([key.longitude, key.latitude])["gbif_id"].min()
        pk = pool[["longitude", "latitude"]].round(5)
        for (a, b), g in zip(zip(pk.longitude, pk.latitude), pool.gbif_id):
            self.assertEqual(g, mins[(a, b)])
        # windowless rows dropped; NaN-year candidates dropped
        self.assertTrue(pool["year"].notna().all())
        c = self.manifest["positives"]["counts"]
        self.assertTrue(all(c[r]["3"] < c[r]["2"] for r in regions.REGIONS))
        # the negatives are a subset of the pool, per split quotas met
        pk2 = set(zip(pool.longitude, pool.latitude))
        self.assertTrue(set(zip(neg.longitude, neg.latitude)) <= pk2)
        for r in regions.REGIONS:
            for s in ("train", "val"):
                n_pos = len(self.csv(PATH_TEMPLATES[f"{s}_positives"].format(region=r)))
                got = neg[(neg.region == r) & (neg.split == s)]
                self.assertEqual(len(got), n_pos)
                self.assertLessEqual(int(got.is_nonveg.sum()),
                                     int(round(n_pos * 0.3)))
        self.assertTrue((neg["label"] == 0).all())

    def test_draw_reproduced_independently(self):
        pool = self.csv("data/negatives/candidate_pool.csv")
        neg = pd.concat([self.csv(PATH_TEMPLATES["negatives"].format(region=r))
                         for r in regions.REGIONS], ignore_index=True)
        ref = Draw().reference
        for r in regions.REGIONS:
            for s in ("train", "val"):
                sub = pool[(pool.region == r) & (pool.split == s)]
                d = self.manifest["negatives"]["draw"][r][s]
                want = set()
                for flag, n in ((True, d["n_nv"]), (False, d["n_hab"])):
                    part = sub[sub.is_nonveg == flag]
                    want |= set(zip(part.longitude.iloc[ref(part, n)],
                                    part.latitude.iloc[ref(part, n)]))
                got = neg[(neg.region == r) & (neg.split == s)]
                self.assertEqual(set(zip(got.longitude, got.latitude)), want)


class RunOrdering(unittest.TestCase):
    """Delete-on-rebuild, partial-run refusal, raise-before-write."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.bad = build_tree(self.d, seed=1)
        run_both(self.d, self.bad)
        self.mpath = os.path.join(self.d, "data/pipeline/split_manifest.json")

    def test_prepare_drops_negatives_section_and_record(self):
        rec = os.path.join(self.d, "data/pipeline/acceptance_record.json")
        with open(rec, "w") as f:
            f.write("{}")
        with redirect_stdout(io.StringIO()):
            ptd.run(self.d)
        self.assertFalse(os.path.exists(rec))
        self.assertEqual(list(json.loads(_read(self.mpath, "r"))), ["positives"])

    def test_partial_run_refused(self):
        p = os.path.join(self.d, "data/pipeline/val_positives_NH.csv")
        with open(p, "a") as f:
            f.write("\n")
        with mock.patch.object(gn, "verify_partition",
                               fake_verify_partition(self.bad)), \
                redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError) as cm:
                gn.run(self.d)
        self.assertIn("val_positives_NH", str(cm.exception))

    def test_shortfall_raises_before_any_write(self):
        before = output_bytes(self.d)
        with mock.patch.object(gn, "NEG_RATIO", 50.0), \
                mock.patch.object(gn, "verify_partition",
                                  fake_verify_partition(self.bad)), \
                redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError) as cm:
                gn.run(self.d)
        self.assertIn("habitat pool undersupplied", str(cm.exception))
        self.assertEqual(output_bytes(self.d), before)

    def test_state_mismatch_raises(self):
        p = os.path.join(self.d, PATH_TEMPLATES["evaluated"].format(region="VT"))
        df = pd.read_csv(p)
        df.loc[0, "region"] = "NH"
        df.to_csv(p, index=False)
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                ptd.run(self.d)


if __name__ == "__main__":
    unittest.main()
