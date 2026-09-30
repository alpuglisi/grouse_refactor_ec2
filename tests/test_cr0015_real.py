"""CR-0015 V1-V3 on real data (deliverable 7b), plus V1 on the constructed
wrong samplers (PA-0021(a)).

Run with cwd = a data root (a directory holding data/):
    GROUSE_REQUIRE_REAL_DATA=1 python -m unittest tests.test_cr0015_real -v
(with the repository on PYTHONPATH). Without the variable, a missing input
(block_assignments.csv, the county file) skips; with it, a missing input is
a failure, so the run cannot pass by skipping.

V1: n = 5,000 per region, AN path (train_blocks_only=True), seed 0; the
independent re-check (tests/cr0015_background_check.py) finds 0
out-of-state and 0 validation-block points.
V2: acceptance rate per region, split in-state x validity x train-block
(OBS, printed).
V3: per region, |unassigned-train share of the accepted points - the
reference pixel-centre share| <= the calibrated bound in
docs/quality/cr0015_v3_calibration.json (deliverable 7a). If the
calibration recorded a demotion, V3 is reported, not asserted.
"""
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))

REQUIRE = os.environ.get("GROUSE_REQUIRE_REAL_DATA") == "1"

_STATE = {}


def _setup(case):
    if "err" in _STATE:
        raise _STATE["err"]
    if "chk" in _STATE:
        return _STATE
    import cr0015_background_check as C
    try:
        chk = C.Checker()
        data, feats, assign = C.real_inputs()
    except Exception as e:                 # missing file or package
        msg = f"real data unavailable from cwd {os.getcwd()}: {type(e).__name__}: {e}"
        _STATE["err"] = (case.failureException(msg) if REQUIRE
                         else unittest.SkipTest(msg))
        raise _STATE["err"]
    _STATE.update(C=C, chk=chk, data=data, feats=feats, assign=assign)
    return _STATE


def _fair(region):
    key = ("fair", region)
    if key not in _STATE:
        import train
        S = _STATE
        _STATE[key] = S["C"].draw(train.sample_background_points, S["data"],
                                  S["feats"], S["assign"], region, 0)
    return _STATE[key]


class V1(unittest.TestCase):
    def test_v1_zero_out_of_state_zero_val_block(self):
        S = _setup(self)
        for region in S["C"].V_REGIONS:
            df = _fair(region)
            c = S["C"].v1_counts(S["chk"], df, region)
            print(f"V1 {region}: {c}")
            self.assertEqual(c["n"], S["C"].V_N)
            self.assertEqual(c["out_of_state"], 0, (region, c))
            self.assertEqual(c["val_block"], 0, (region, c))


class V2(unittest.TestCase):
    def test_v2_acceptance_report(self):
        S = _setup(self)
        for region in S["C"].V_REGIONS:
            a = _fair(region).attrs["acceptance"]
            d = a["drawn"]
            print(f"V2 {region} (OBS): drawn {d:,}; valid {a['valid'] / d:.4f}; "
                  f"in-state | valid {a['in_state'] / max(a['valid'], 1):.4f}; "
                  f"train-block | in-state {a['accepted'] / max(a['in_state'], 1):.4f}; "
                  f"overall acceptance {a['accepted'] / d:.4f}; rounds {a['rounds']}")


class V3(unittest.TestCase):
    def test_v3_unassigned_train_share(self):
        S = _setup(self)
        C = S["C"]
        if not os.path.exists(C.CALIBRATION_JSON):
            msg = f"no V3 calibration at {C.CALIBRATION_JSON} (deliverable 7a)"
            if REQUIRE:
                self.fail(msg)
            self.skipTest(msg)
        with open(C.CALIBRATION_JSON) as f:
            cal = json.load(f)
        gate = cal.get("v3_status") == "GATE"
        for region in C.V_REGIONS:
            path = S["data"][region].latest_raster_path(S["feats"][0])
            ref = C.reference_share(S["chk"], path, region)
            stat = abs(C.v3_share(S["chk"], _fair(region)) - ref["share"])
            bound = cal["regions"][region]["bound"]
            print(f"V3 {region} ({'GATE' if gate else 'OBS'}): |share - ref| = "
                  f"{stat:.5f}, bound {bound:.5f}; reference {ref}")
            if gate:
                self.assertLessEqual(stat, bound, region)


class V1OnWrongSamplers(unittest.TestCase):
    """PA-0021(a): V1 must FAIL on today's sampler (both counts), on the
    sampler treating unassigned blocks as train, and on the md5-fraction-0.18
    sampler (points in unassigned blocks hashed in [0.18, vf))."""

    def counts(self, name):
        S = _setup(self)
        import cr0015_wrong_samplers as W
        out = {}
        for region in S["C"].V_REGIONS:
            df = S["C"].draw(W.WRONG_SAMPLERS[name], S["data"], S["feats"],
                             S["assign"], region, 0)
            out[region] = S["C"].v1_counts(S["chk"], df, region)
            print(f"V1 on {name} {region}: {out[region]}")
        return out

    def test_todays_sampler_fails_both_counts(self):
        c = self.counts("todays_sampler")
        self.assertGreater(sum(v["out_of_state"] for v in c.values()), 0)
        self.assertGreater(sum(v["val_block"] for v in c.values()), 0)
        for v in c.values():
            self.assertGreater(v["out_of_state"], 0)
            self.assertGreater(v["val_block"], 0)

    def test_unassigned_train_fails(self):
        c = self.counts("unassigned_train")
        for v in c.values():
            self.assertGreater(v["val_block_unassigned"], 0)

    def test_md5_fraction_018_fails(self):
        c = self.counts("md5_fraction_018")
        self.assertGreater(sum(v["val_block_unassigned"] for v in c.values()), 0)


if __name__ == "__main__":
    unittest.main()
