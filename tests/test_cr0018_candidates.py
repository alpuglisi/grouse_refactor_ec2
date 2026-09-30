"""Fixes of CR-0018's PA-0027 lint candidates (BUG-0065..0071).

    python -m unittest tests.test_cr0018_candidates -v

Synthetic inputs only (temp directories, fake modules/objects); no
network, nothing under data/. BUG-0068 and the acceptance_split.py site
of BUG-0069 are pending (CR-0017 owns that file) and not tested here.
"""
import io
import os
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import analyze_grouse  # noqa: E402
import check_exotic  # noqa: E402
import check_raster  # noqa: E402
import diagnose_water_bias  # noqa: E402
import download_rev  # noqa: E402
import download_tcc_nlcd  # noqa: E402
import download_treemap  # noqa: E402
import generate_treemap_features as gtf  # noqa: E402
from grouse_data import MissingDataError  # noqa: E402


class TmpDir(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)

    def garbage(self, name="garbage.tif"):
        p = os.path.join(self.d, name)
        with open(p, "wb") as f:
            f.write(b"not a raster at all" * 10)
        return p


# ---------------------------------------------------------------- BUG-0065
class Bug0065PublishedProducts(unittest.TestCase):
    def call(self, session):
        with redirect_stdout(io.StringIO()) as out:
            v = download_rev.published_products("2024", session=session)
        return v, out.getvalue()

    def test_parse_error_printed_with_type(self):
        res = mock.Mock(status_code=200)
        res.json.side_effect = ValueError("Expecting value")
        v, out = self.call(mock.Mock(get=mock.Mock(return_value=res)))
        self.assertIsNone(v)
        self.assertIn("ValueError: Expecting value", out)

    def test_network_error_printed_with_type(self):
        s = mock.Mock(get=mock.Mock(
            side_effect=requests.exceptions.ConnectionError("refused")))
        v, out = self.call(s)
        self.assertIsNone(v)
        self.assertIn("ConnectionError: refused", out)

    def test_listing_parsed(self):
        res = mock.Mock(status_code=200)
        res.json.return_value = {"services": [
            {"name": "Landfire_LF2024/LF2024_EVT_CONUS"}]}
        v, _ = self.call(mock.Mock(get=mock.Mock(return_value=res)))
        self.assertEqual(v, {"EVT"})


# ---------------------------------------------------------------- BUG-0066
class _EE(Exception):
    pass


def fake_ee():
    return types.SimpleNamespace(
        EEException=_EE,
        Geometry=types.SimpleNamespace(Rectangle=lambda *a, **k: None))


class Bug0066FetchTileRetry(TmpDir):
    MODULES = (download_tcc_nlcd, download_treemap)

    def run_fetch(self, mod, exc, retries=2):
        image = mock.Mock()
        image.getDownloadURL.side_effect = exc
        err = io.StringIO()
        with mock.patch.object(mod.time, "sleep"), redirect_stderr(err), \
                self.assertRaises(Exception) as cm:   # type checked by caller
            mod.fetch_tile(fake_ee(), image, (0, 0, 30, 30),
                           os.path.join(self.d, "t.tif"), retries=retries)
        return cm.exception, image.getDownloadURL.call_count, err.getvalue()

    def test_programming_error_not_retried(self):
        for mod in self.MODULES:
            with self.subTest(mod=mod.__name__):
                e, calls, _ = self.run_fetch(mod, TypeError("bad param"))
                self.assertIsInstance(e, TypeError)
                self.assertEqual(calls, 1)

    def test_transient_retried_logged_then_raises(self):
        for mod in self.MODULES:
            for exc in (requests.exceptions.ConnectionError("reset"),
                        _EE("Too many concurrent aggregations")):
                with self.subTest(mod=mod.__name__, exc=type(exc).__name__):
                    e, calls, err = self.run_fetch(mod, exc, retries=2)
                    self.assertIsInstance(e, RuntimeError)
                    self.assertIn(type(exc).__name__, str(e))
                    self.assertIs(e.__cause__, exc)
                    self.assertEqual(calls, 3)
                    self.assertEqual(err.count("[retry "), 2)
                    self.assertIn("Traceback", err)

    def test_truncated_download_is_transient(self):
        for mod in self.MODULES:
            with self.subTest(mod=mod.__name__):
                image = mock.Mock()
                image.getDownloadURL.return_value = "http://x"
                resp = mock.Mock(content=b"truncated")
                with mock.patch.object(mod.requests, "get",
                                       return_value=resp), \
                        mock.patch.object(mod.time, "sleep"), \
                        redirect_stderr(io.StringIO()):
                    with self.assertRaises(RuntimeError) as cm:
                        mod.fetch_tile(fake_ee(), image, (0, 0, 30, 30),
                                       os.path.join(self.d, "t.tif"),
                                       retries=1)
                self.assertIn("RasterioIOError", str(cm.exception))
                self.assertEqual(image.getDownloadURL.call_count, 2)


# ---------------------------------------------------------------- BUG-0067
class Bug0067EeInit(unittest.TestCase):
    def test_both_paths_fail_names_both_errors(self):
        ee = types.ModuleType("ee")
        ee.Initialize = mock.Mock(side_effect=RuntimeError("no stored creds"))
        auth = types.ModuleType("google.auth")
        auth.default = mock.Mock(side_effect=ValueError("no ADC"))
        google = types.ModuleType("google")
        google.auth = auth
        for mod in (download_tcc_nlcd, download_treemap):
            with self.subTest(mod=mod.__name__), \
                    mock.patch.dict(sys.modules, {"ee": ee, "google": google,
                                                  "google.auth": auth}):
                with self.assertRaises(SystemExit) as cm:
                    mod.ee_init("proj")
                msg = str(cm.exception.code)
                self.assertIn("RuntimeError: no stored creds", msg)
                self.assertIn("ValueError: no ADC", msg)

    def test_first_path_success(self):
        ee = types.ModuleType("ee")
        ee.Initialize = mock.Mock()
        for mod in (download_tcc_nlcd, download_treemap):
            with self.subTest(mod=mod.__name__), \
                    mock.patch.dict(sys.modules, {"ee": ee}):
                self.assertIs(mod.ee_init("proj"), ee)


# ---------------------------------------------------------------- BUG-0069
class Bug0069VisibleUnknownType(TmpDir):
    def test_check_raster_prints_type(self):
        p = self.garbage()
        with redirect_stdout(io.StringIO()) as out:
            check_raster.check_one(p)
        self.assertRegex(out.getvalue(), r"COULD NOT OPEN: \w*Error")

    def test_check_exotic_prints_type(self):
        os.makedirs(os.path.join(self.d, "attribute_tables",
                                 "LF2020_SClass.csv"))    # a directory
        with redirect_stdout(io.StringIO()) as out:
            check_exotic.check_sclass_meaning(self.d)
        self.assertIn("IsADirectoryError", out.getvalue())
        self.assertIn("not done", out.getvalue())

    def test_state_boundaries_read_failure_prints_type(self):
        self.garbage("states.geojson")
        with mock.patch.object(analyze_grouse, "MAP_DATA_DIR", self.d), \
                mock.patch.object(analyze_grouse, "_state_boundaries_cache",
                                  analyze_grouse._BOUNDARY_UNLOADED), \
                redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(analyze_grouse.load_state_boundaries())
        self.assertRegex(out.getvalue(),
                         r"Could not read boundary file .*\(\w+: ")

    def test_state_boundaries_download_failure_prints_type(self):
        with mock.patch.object(analyze_grouse, "MAP_DATA_DIR", self.d), \
                mock.patch.object(analyze_grouse, "_state_boundaries_cache",
                                  analyze_grouse._BOUNDARY_UNLOADED), \
                mock.patch("urllib.request.urlretrieve",
                           side_effect=OSError("offline")), \
                redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(analyze_grouse.load_state_boundaries())
        self.assertIn("(OSError: offline)", out.getvalue())


# ---------------------------------------------------------------- BUG-0070
class FakeRD:
    def __init__(self, exc):
        self.exc = exc

    def latest_raster_path(self, feature):
        raise self.exc


class Bug0070WaterBiasRegionSkip(unittest.TestCase):
    def test_missing_raster_skipped_loudly(self):
        data = {"ME": FakeRD(MissingDataError("[ME] no rasters"))}
        with redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(diagnose_water_bias.process_region("ME", data))
        self.assertIn("MissingDataError: [ME] no rasters", out.getvalue())
        self.assertIn("absent from the VERDICT", out.getvalue())

    def test_other_error_propagates(self):
        data = {"ME": FakeRD(TypeError("bug"))}
        with redirect_stdout(io.StringIO()), self.assertRaises(TypeError):
            diagnose_water_bias.process_region("ME", data)


class _Stop(Exception):
    """Ends diagnose_training.main after section 1."""


class FakeTrainRD:
    def __init__(self, exc=None):
        self.exc = exc

    def positives(self, split):
        if self.exc:
            raise self.exc
        return [0] * 10

    def negatives(self, split):
        return [0] * 20

    def available_features(self):
        raise _Stop()


class Bug0070DiagnoseTrainingRegionSkip(unittest.TestCase):
    def run_main(self, regions):
        import diagnose_training
        argv = ["diagnose_training.py", "--regions"] + list(regions)
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(diagnose_training, "GrouseData",
                                  return_value=regions), \
                redirect_stdout(io.StringIO()) as out:
            try:
                diagnose_training.main()
            except _Stop:
                pass
        return out.getvalue()

    def test_skip_marks_totals_incomplete(self):
        out = self.run_main({"ME": FakeTrainRD(),
                             "NH": FakeTrainRD(MissingDataError("no file"))})
        self.assertIn("NH: SKIPPED", out)
        self.assertIn("MissingDataError: no file", out)
        self.assertIn("INCOMPLETE", out)
        self.assertIn("['NH']", out)

    def test_complete_run_not_marked(self):
        out = self.run_main({"ME": FakeTrainRD()})
        self.assertNotIn("INCOMPLETE", out)

    def test_other_error_propagates(self):
        with self.assertRaises(TypeError):
            self.run_main({"ME": FakeTrainRD(TypeError("bug"))})


# ---------------------------------------------------------------- BUG-0071
class Bug0071SourceIsValid(TmpDir):
    def setUp(self):
        super().setUp()
        gtf._source_is_valid.cache_clear()
        self.addCleanup(gtf._source_is_valid.cache_clear)

    def test_unreadable_file_invalid_with_type(self):
        p = self.garbage()
        with redirect_stdout(io.StringIO()) as out:
            self.assertFalse(gtf._source_is_valid(p))
        self.assertIn("RasterioIOError", out.getvalue())

    def test_vanished_file_invalid(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertFalse(gtf._source_is_valid(
                os.path.join(self.d, "gone.tif")))
        self.assertIn("FileNotFoundError", out.getvalue())

    def test_other_error_propagates(self):
        p = self.garbage()
        with mock.patch.object(gtf.rasterio, "open",
                               side_effect=TypeError("bug")):
            with self.assertRaises(TypeError):
                gtf._source_is_valid(p)


if __name__ == "__main__":
    unittest.main()
