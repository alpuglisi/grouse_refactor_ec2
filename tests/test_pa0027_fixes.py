"""PA-0027 sweep fixes BUG-0052..BUG-0055: a broad handler never resolves to
a success/continue branch.

    python -m unittest tests.test_pa0027_fixes -v

Synthetic inputs only (temp directories, fake region objects); no network,
nothing under data/.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import analyze_grouse  # noqa: E402
import diagnose_wetland  # noqa: E402
import download_rev  # noqa: E402
import download_tcc_nlcd  # noqa: E402
from grouse_data import MissingDataError  # noqa: E402


def write_tif(path, data, nodata, crs="EPSG:4326",
              transform=from_origin(-70.0, 45.0, 0.01, 0.01)):
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[0],
                       width=data.shape[1], count=1, dtype=data.dtype,
                       crs=crs, transform=transform, nodata=nodata) as dst:
        dst.write(data, 1)


class TmpDir(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)


class Bug0052RasterValidFraction(TmpDir):
    def frac(self, path):
        with redirect_stdout(io.StringIO()) as out:
            v = download_rev._raster_valid_fraction(path)
        return v, out.getvalue()

    def test_readable_raster_fraction(self):
        p = os.path.join(self.d, "ok.tif")
        a = np.full((10, 10), -9999, dtype=np.int16)
        a[:5] = 7
        write_tif(p, a, -9999)
        self.assertEqual(self.frac(p)[0], 0.5)

    def test_unopenable_file_is_invalid_not_none(self):
        p = os.path.join(self.d, "garbage.tif")
        with open(p, "wb") as f:
            f.write(b"not a tiff at all" * 10)
        v, out = self.frac(p)
        self.assertEqual(v, 0.0)
        self.assertLess(v, download_rev.MIN_VALID_PIXEL_FRAC)
        self.assertIn("cannot be read as a raster", out)

    def test_truncated_tif_is_invalid(self):
        p = os.path.join(self.d, "trunc.tif")
        write_tif(p, np.ones((200, 200), dtype=np.int16), -9999)
        size = os.path.getsize(p)
        with open(p, "r+b") as f:
            f.truncate(size // 2)
        self.assertEqual(self.frac(p)[0], 0.0)

    def test_missing_file_is_invalid(self):
        self.assertEqual(self.frac(os.path.join(self.d, "nope.tif"))[0], 0.0)

    def test_other_error_propagates(self):
        with mock.patch.object(download_rev.rasterio, "open",
                               side_effect=RuntimeError("bug")):
            with self.assertRaises(RuntimeError):
                download_rev._raster_valid_fraction("x.tif")


class Bug0053EvtCrosswalk(TmpDir):
    def table_dir(self):
        d = os.path.join(self.d, "attribute_tables")
        os.makedirs(d)
        return d

    def test_missing_table_raises(self):
        with self.assertRaises(FileNotFoundError):
            analyze_grouse.load_evt_crosswalk(self.d)

    def test_unreadable_table_raises(self):
        d = self.table_dir()
        open(os.path.join(d, "LF2024_EVT.csv"), "w").close()   # empty file
        with self.assertRaises(pd.errors.EmptyDataError):
            analyze_grouse.load_evt_crosswalk(self.d)

    def test_read_error_propagates(self):
        d = self.table_dir()
        pd.DataFrame({"VALUE": [1], "EVT_PHYS": ["Conifer"]}).to_csv(
            os.path.join(d, "LF2024_EVT.csv"), index=False)
        with mock.patch.object(analyze_grouse.pd, "read_csv",
                               side_effect=RuntimeError("bug")):
            with self.assertRaises(RuntimeError):
                analyze_grouse.load_evt_crosswalk(self.d)

    def test_malformed_table_raises(self):
        d = self.table_dir()
        pd.DataFrame({"VALUE": [1], "OTHER": ["x"]}).to_csv(
            os.path.join(d, "LF2024_EVT.csv"), index=False)
        with self.assertRaises(ValueError):
            analyze_grouse.load_evt_crosswalk(self.d)

    def test_newest_valid_table_loads(self):
        d = self.table_dir()
        pd.DataFrame({"VALUE": [1], "EVT_PHYS": ["Old"]}).to_csv(
            os.path.join(d, "LF2020_EVT.csv"), index=False)
        pd.DataFrame({"VALUE": [1, 2], "EVT_PHYS": ["Conifer", "Hardwood"],
                      "EVT_GP_N": ["G1", "G2"]}).to_csv(
            os.path.join(d, "LF2024_EVT.csv"), index=False)
        xw = analyze_grouse.load_evt_crosswalk(self.d)
        self.assertEqual(xw["phys"], {1: "Conifer", 2: "Hardwood"})
        self.assertEqual(xw["group"], {1: "G1", 2: "G2"})
        self.assertEqual(xw["source"], "LF2024_EVT.csv")


class FakeRegion:
    region = "ZZ"

    def __init__(self, pos, neg):
        self._pos, self._neg = pos, neg

    @staticmethod
    def _get(v):
        if isinstance(v, BaseException):
            raise v
        return v

    def positives(self, split="all"):
        return self._get(self._pos)

    def negatives(self, split="all"):
        return self._get(self._neg)


class Bug0054SightingYears(unittest.TestCase):
    def years(self, rd):
        with redirect_stdout(io.StringIO()) as out:
            ys = download_tcc_nlcd.sighting_years(rd)
        return ys, out.getvalue()

    def test_both_classes(self):
        rd = FakeRegion(pd.DataFrame({"year": [2019, 2021]}),
                        pd.DataFrame({"year": [2022.0, np.nan]}))
        self.assertEqual(self.years(rd)[0], {2019, 2021, 2022})

    def test_missing_class_skipped_loudly(self):
        rd = FakeRegion(pd.DataFrame({"year": [2019]}),
                        MissingDataError("no 'negatives' file"))
        ys, out = self.years(rd)
        self.assertEqual(ys, {2019})
        self.assertIn("negatives not on disk", out)

    def test_other_error_propagates(self):
        rd = FakeRegion(pd.DataFrame({"year": [2019]}),
                        pd.errors.ParserError("corrupt"))
        with self.assertRaises(pd.errors.ParserError):
            self.years(rd)
        rd = FakeRegion(RuntimeError("bug"), pd.DataFrame({"year": [2019]}))
        with self.assertRaises(RuntimeError):
            self.years(rd)


class Bug0055CenterCodes(TmpDir):
    def setUp(self):
        super().setUp()
        self.tif = os.path.join(self.d, "nlcd.tif")
        write_tif(self.tif, np.full((10, 10), 42, dtype=np.int16), -9999)
        self.df = pd.DataFrame({"longitude": [-69.95, -69.95, -69.95],
                                "latitude": [44.95, 44.95, 44.95],
                                "year": [2020, 2021, 2021]})

    def rd(self, err):
        tif = self.tif

        class RD:
            region = "ZZ"

            def raster_path(self, feature, year):
                if year == 2021:
                    raise err
                return tif
        return RD()

    def test_missing_raster_year_skipped_loudly(self):
        with redirect_stdout(io.StringIO()) as out:
            codes = diagnose_wetland.center_codes(
                self.rd(MissingDataError("none")), self.df)
        self.assertEqual(codes.tolist(), [42, -1, -1])
        self.assertIn("nlcd 2021", out.getvalue())
        self.assertIn("2 record(s) left uncoded", out.getvalue())

    def test_other_error_propagates(self):
        with self.assertRaises(RuntimeError):
            diagnose_wetland.center_codes(self.rd(RuntimeError("bug")),
                                          self.df)


if __name__ == "__main__":
    unittest.main()
