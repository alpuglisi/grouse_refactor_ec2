"""CR-0033: the split window mask reads a pinned feature list, not the live
models.FEATURE_SPEC. Synthetic rasters only; no data/ access.

Written before approval (CR-0011 A3). T1 and T2 fail until CR-0033
deliverable 2 lands; T2 is the pre-CR code's failure (wrong
implementation = today's window_mask).

Run with
    python -m unittest tests.test_cr0033
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import models  # noqa: E402
import prepare_training_data as ptd  # noqa: E402
from grouse_data import DataConfig, RegionData  # noqa: E402

LOCAL_ALBERS = ("+proj=aea +lat_0=44 +lon_0=-71.5 +lat_1=43 +lat_2=45 "
                "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
ACCEPTANCE = os.path.join(REPO, "docs", "quality", "acceptance_split.json")
EXTRA = "zz_cr0033_extra"


class T1Pinned(unittest.TestCase):
    def test_equals_acceptance_feature_spec_keys(self):
        with open(ACCEPTANCE) as f:
            keys = json.load(f)["feature_spec_keys"]
        self.assertEqual(list(ptd.SPLIT_WINDOW_FEATURES), keys)

    def test_subset_of_feature_spec(self):
        self.assertTrue(set(ptd.SPLIT_WINDOW_FEATURES) <= set(models.FEATURE_SPEC))


class T2ExtraFeatureIgnored(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        d = os.path.join(self.tmp, "data", "landfire")
        os.makedirs(d)
        with open(ACCEPTANCE) as f:
            feats = json.load(f)["feature_spec_keys"]
        for feat in feats:
            with rasterio.open(os.path.join(d, f"NH_2022_{feat}.tif"), "w",
                               driver="GTiff", height=200, width=200,
                               count=1, dtype="int16", crs=LOCAL_ALBERS,
                               transform=from_origin(-3000, 3000, 30, 30),
                               nodata=-9999) as dst:
                dst.write(np.ones((200, 200), np.int16), 1)
        with mock.patch("builtins.print"):
            self.rd = RegionData("NH", DataConfig(base_dir=self.tmp))
        # one point at the grid centre (window inside), one 10 px from the
        # west edge (window outside)
        t = Transformer.from_crs(LOCAL_ALBERS, "EPSG:4326", always_xy=True)
        lon, lat = t.transform([0.0, -3000 + 10 * 30 + 15], [0.0, 0.0])
        self.df = pd.DataFrame({"longitude": lon, "latitude": lat,
                                "year": [2022, 2022]})

    def test_mask_unchanged_and_extra_never_opened(self):
        base = ptd.window_mask(self.df, self.rd)
        self.assertEqual(base.tolist(), [True, False])
        opened = []
        real_open = rasterio.open

        def spy(path, *a, **k):
            opened.append(str(path))
            return real_open(path, *a, **k)

        extra = {EXTRA: {"kind": "continuous", "scale": 1.0}}
        with mock.patch.dict(models.FEATURE_SPEC, extra), \
             mock.patch.object(rasterio, "open", spy):
            got = ptd.window_mask(self.df, self.rd)
        self.assertEqual(got.tolist(), base.tolist())
        self.assertFalse([p for p in opened if EXTRA in p])


if __name__ == "__main__":
    unittest.main()
