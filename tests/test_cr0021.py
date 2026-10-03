"""CR-0021 tests, deliverable 1 part: the evidence scripts' logic
(fetch_topup.py with the network replaced by a fake; preregister.py's
strata helpers and its stratified draw on a synthetic pool). Deliverable 3
adds the pipeline tests.

    python -m unittest tests.test_cr0021 -v

No network, no real data. Tests that need a particular row to reach a step
assert that it does (PA-0021(a)).
"""
import csv
import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(ROOT, "docs", "quality", "evidence", "CR-0021")
sys.path.insert(0, ROOT)

import acceptance_split as A  # noqa: E402
from get_negatives import CSV_FIELDS  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(f"cr0021_{name}", os.path.join(EVID, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ft = _load("fetch_topup")
pr = _load("preregister")


def _row(state, common, year, gid, lon=-70.0, lat=44.0, unc=""):
    return {"common_name": common, "scientific_name": "x", "longitude": lon, "latitude": lat,
            "obs_date": f"{year}-06-01", "year": year, "month": 6, "state": state,
            "gbif_id": str(gid), "how_many": 1, "coord_uncertainty_m": unc}


def _write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:          # as get_negatives.py writes
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class FetchTopupTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.live = os.path.join(self.tmp.name, "live")
        self.scr = os.path.join(self.tmp.name, "scratch")
        gid = 1
        for R in ft.REGIONS:
            rows = [_row(R, "Ovenbird", 2023, gid), _row(R, "Ovenbird", 2020, gid + 1)]
            gid += 2
            for tree in (self.live, self.scr):
                _write(os.path.join(tree, ft.RAW.format(R=R)), rows)
        self.pinned = {R: _sha(os.path.join(self.scr, ft.RAW.format(R=R))) for R in ft.REGIONS}

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_scratch_may_run(self):
        self.assertEqual(ft.check_tree(self.scr, self.live, self.pinned, CSV_FIELDS), [])

    def test_refuses_live_root(self):
        probs = ft.check_tree(self.live, self.live, self.pinned, CSV_FIELDS)
        self.assertTrue(any("live repository root" in p for p in probs))

    def test_refuses_file_resolving_into_live(self):
        p = os.path.join(self.scr, ft.RAW.format(R="ME"))
        os.remove(p)
        os.symlink(os.path.join(self.live, ft.RAW.format(R="ME")), p)
        probs = ft.check_tree(self.scr, self.live, self.pinned, CSV_FIELDS)
        self.assertTrue(any("symlink" in x for x in probs))
        self.assertTrue(any("resolves into the live" in x for x in probs))

    def test_refuses_hardlinked_copy(self):
        """Code review S1: cp -al / rsync --link-dest would let the append reach live."""
        p = os.path.join(self.scr, ft.RAW.format(R="ME"))
        os.remove(p)
        os.link(os.path.join(self.live, ft.RAW.format(R="ME")), p)
        self.assertEqual(_sha(p), self.pinned["ME"])     # the sha pin alone would pass
        probs = ft.check_tree(self.scr, self.live, self.pinned, CSV_FIELDS)
        self.assertTrue(any("hardlink" in x for x in probs))

    def test_refuses_already_topped_up(self):
        p = os.path.join(self.scr, ft.RAW.format(R="NH"))
        ft.append_rows(p, [_row("NH", "Ovenbird", 2023, 999)], CSV_FIELDS)
        probs = ft.check_tree(self.scr, self.live, self.pinned, CSV_FIELDS)
        self.assertTrue(any("not the pinned pre-top-up" in x for x in probs))

    def test_refuses_missing_newline_and_bad_header(self):
        p = os.path.join(self.scr, ft.RAW.format(R="VT"))
        with open(p, "w", newline="") as f:
            f.write("a,b\r\n1,2")
        pinned = dict(self.pinned, VT=_sha(p))
        probs = ft.check_tree(self.scr, self.live, pinned, CSV_FIELDS)
        self.assertTrue(any("newline" in x for x in probs))
        self.assertTrue(any("header" in x for x in probs))


class FetchTopupLogic(unittest.TestCase):
    def setUp(self):
        self.rows = {
            "ME": [_row("ME", "Ovenbird", 2023, 1), _row("ME", "Ovenbird", 2023, 2),
                   _row("ME", "Ovenbird", 2024, 3), _row("ME", "Hermit Thrush", 2020, 4)],
            "NH": [_row("NH", "Ovenbird", 2024, 5)],
        }
        self.species = ["Ovenbird", "Hermit Thrush"]
        self.next_id = [100]

    def fake(self, limit=None, stopped=False, bad=None):
        calls = []

        def fetch(R, common, y, quota, seen):
            calls.append((R, common, y, quota))
            n = quota if limit is None else min(quota, limit)
            out = []
            for _ in range(n):
                gid = str(self.next_id[0])
                self.next_id[0] += 1
                seen.add(gid)
                r = _row(R, common, y, gid)
                if bad:
                    r.update(bad)
                out.append(r)
            return out, stopped, limit is not None and n < quota
        return fetch, calls

    def test_quota_is_multiple_of_existing_and_zero_e_skipped(self):
        fetch, calls = self.fake()
        new, table = ft.topup(self.rows, self.species, fetch)
        self.assertIn(("ME", "Ovenbird", 2023, 4), calls)      # e = 2 -> 4
        self.assertIn(("ME", "Ovenbird", 2024, 2), calls)      # e = 1 -> 2
        self.assertIn(("NH", "Ovenbird", 2024, 2), calls)
        self.assertNotIn("Hermit Thrush", [c[1] for c in calls])   # e = 0 in 2023-24
        zero = [t for t in table if t["existing"] == 0]
        self.assertTrue(any(t["species"] == "Hermit Thrush" for t in zero))
        self.assertEqual(len(new["ME"]), 6)
        self.assertEqual(len(new["NH"]), 2)
        self.assertTrue(all(int(r["year"]) in ft.TOPUP_YEARS for rs in new.values() for r in rs))

    def test_stopped_partition_aborts(self):
        fetch, _ = self.fake(stopped=True)
        with self.assertRaises(ft.Abort):
            ft.topup(self.rows, self.species, fetch)

    def test_row_outside_partition_aborts(self):
        for bad in ({"year": 2022}, {"state": "VT"}, {"common_name": "Swamp Sparrow"},
                    {"gbif_id": ""}):
            self.next_id = [100]
            fetch, _ = self.fake(bad=bad)
            with self.assertRaises(ft.Abort, msg=str(bad)):
                ft.topup(self.rows, self.species, fetch)

    def test_exhausted_partition_reported(self):
        fetch, _ = self.fake(limit=1)
        _, table = ft.topup(self.rows, self.species, fetch)
        t = [x for x in table if (x["region"], x["species"], x["year"]) == ("ME", "Ovenbird", 2023)][0]
        self.assertEqual((t["requested"], t["written"], t["exhausted"]), (4, 1, True))

    def test_append_keeps_old_bytes_as_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "g.csv")
            _write(p, self.rows["ME"])
            with open(p, "rb") as f:
                before = f.read()
            ft.append_rows(p, [_row("ME", "Ovenbird", 2024, 77)], CSV_FIELDS)
            with open(p, "rb") as f:
                after = f.read()
            self.assertTrue(after.startswith(before))
            self.assertTrue(after.endswith(b"\r\n"))
            self.assertEqual(len(ft.read_rows(p)), len(self.rows["ME"]) + 1)


class Strata(unittest.TestCase):
    def test_candidates_valid(self):
        for name, s in pr.STRATA_CANDIDATES:
            self.assertEqual(pr.check_strata(s, 2020), [], name)

    def test_invalid_strata(self):
        self.assertTrue(pr.check_strata(((2020,), (2022,)), 2020))          # gap
        self.assertTrue(pr.check_strata(((2020, 2021), (2021,)), 2020))     # overlap
        self.assertTrue(pr.check_strata(((2021,), (2022,)), 2020))          # not from YEAR_MIN
        self.assertTrue(pr.check_strata(((2021,), (2020,)), 2020))          # not increasing

    def test_stratum_of_fails_closed(self):
        s = pr.STRATA_CANDIDATES[1][1]
        self.assertEqual(pr.stratum_of([2020, 2023, 2024], s).tolist(), [0, 3, 3])
        for y in (2019, 2025, np.nan):
            with self.assertRaises(ValueError):
                pr.stratum_of([y], s)


class AucAndNull(unittest.TestCase):
    def test_exact_year_match_gives_half(self):
        years = [2020] * 7 + [2021] * 3 + [2024] * 5
        self.assertEqual(pr.auc(years, list(reversed(years))), 0.5)

    def test_separated(self):
        self.assertEqual(pr.auc([2024] * 3, [2020] * 4), 1.0)

    def test_tvd(self):
        self.assertEqual(pr.tvd(list("aabb"), list("aabb")), 0.0)
        self.assertEqual(pr.tvd(list("aa"), list("bb")), 1.0)

    def test_null_size_and_centre(self):
        rng = np.random.default_rng(1)
        cells = [(rng.choice([2023, 2024], 200), np.r_[np.ones(100), np.zeros(100)])
                 for _ in range(3)]
        null = pr.cell_permutation_null(cells, n_perm=200)
        self.assertEqual(len(null), 200)
        self.assertLess(abs(np.median(null) - 0.5), 0.03)


def _stratified(pos_years, pool_rows, strata):
    rep = pr.Stratified.__new__(pr.Stratified)
    rep.strata = tuple(tuple(s) for s in strata)
    rep.C = {"NEG_RATIO": 1.0, "NONVEG_MAX_FRAC": 0.3, "SPLIT_SEED": 42}
    rep.regions = ["ME"]
    rep.pos = {"ME": pd.DataFrame({"split": ["train"] * len(pos_years), "year": pos_years})}
    rep.pool_full = pd.DataFrame(pool_rows)
    rep.draw_counts = {}
    return rep


def _pool(year, n_hab, n_nv, start=0):
    rows = []
    for i in range(n_hab + n_nv):
        rows.append({"region": "ME", "split": "train", "year": year, "is_nonveg": i >= n_hab,
                     "longitude": -70.0 + (start + i) * 1e-3, "latitude": 44.0,
                     "weight": 1.0})
    return rows


class StratifiedDraw(unittest.TestCase):
    S = ((2020,), (2021,), (2022,), (2023,), (2024,))

    def test_counts_per_stratum_equal_positives(self):
        pos = [2020] * 10 + [2023] * 4 + [2024] * 6
        pool = _pool(2020, 30, 10) + _pool(2023, 10, 5, 100) + _pool(2024, 10, 5, 200) \
            + _pool(2021, 10, 0, 300)
        rep = _stratified(pos, pool, self.S)
        sel = rep.draw_select()
        got = sel["year"].value_counts().to_dict()
        self.assertEqual(got, {2020: 10, 2023: 4, 2024: 6})
        d = rep.draw_counts["ME"]["train"]
        self.assertEqual(d["n"], 20)
        self.assertEqual(d["strata"]["2020"], {"n": 10, "n_nv": 3, "n_hab": 7})
        self.assertEqual(d["strata"]["2021"], {"n": 0, "n_nv": 0, "n_hab": 0})
        self.assertEqual(d["n_nv"], sum(v["n_nv"] for v in d["strata"].values()))
        self.assertEqual(d["n_hab"], sum(v["n_hab"] for v in d["strata"].values()))
        self.assertEqual(sorted(d["strata"]), ["2020", "2021", "2022", "2023", "2024"])

    def test_nonveg_cap_per_stratum_not_per_cell(self):
        # n_k = 4 in five strata: per-stratum cap round(1.2) = 1 each -> 5;
        # a per-cell cap would be round(20 * 0.3) = 6.
        pos = [2020, 2021, 2022, 2023, 2024] * 4
        pool = sum((_pool(y, 10, 10, 100 * i) for i, y in enumerate(range(2020, 2025))), [])
        rep = _stratified(pos, pool, self.S)
        rep.draw_select()
        self.assertEqual(rep.draw_counts["ME"]["train"]["n_nv"], 5)
        self.assertNotEqual(5, A.py_round(20 * 0.3))      # the attack's effect exists

    def test_shortfall_raises_despite_surplus_elsewhere(self):
        pos = [2020] * 5 + [2024] * 5
        pool = _pool(2020, 50, 0) + _pool(2024, 2, 0, 100)
        rep = _stratified(pos, pool, self.S)
        with self.assertRaises(A.ReplayError):
            rep.draw_select()

    def test_year_outside_strata_raises(self):
        rep = _stratified([2020], _pool(2020, 5, 0) + _pool(2025, 1, 0, 50), self.S)
        with self.assertRaises(A.ReplayError):
            rep.draw_select()
        rep = _stratified([2019], _pool(2020, 5, 0), self.S)
        with self.assertRaises(A.ReplayError):
            rep.draw_select()

    def test_feasibility_agrees_with_draw(self):
        pos = [2020] * 10 + [2023] * 4 + [2024] * 6
        pool = _pool(2020, 30, 10) + _pool(2023, 3, 5, 100) + _pool(2024, 10, 5, 200)
        rep = _stratified(pos, pool, self.S)
        t = pr.feasibility(rep.pos, rep.pool_full, self.S, rep.C, ["ME"])
        self.assertEqual(int(t[t.stratum == 2023]["short"].iloc[0]), 0)   # 4 -> n_nv 1, n_hab 3
        rep.draw_select()
        self.assertEqual(int(t[t.split == "val"]["n"].sum()), 0)        # fixture has no val rows
        for r in t[t.split == "train"].itertuples():
            self.assertEqual(rep.draw_counts["ME"]["train"]["strata"][str(r.stratum)],
                             {"n": r.n, "n_nv": r.n_nv, "n_hab": r.n_hab})

    def test_unstratified_draw_would_differ(self):
        """The 'draw not stratified' attack has an effect on this fixture."""
        pos = [2020] * 2 + [2024] * 8
        pool = _pool(2020, 40, 0) + _pool(2024, 10, 0, 100)
        rep = _stratified(pos, pool, self.S)
        strat = rep.draw_select()["year"].value_counts().to_dict()
        flat = rep.es_take(rep.pool_full, 10, 42)["year"].value_counts().to_dict()
        self.assertEqual(strat, {2020: 2, 2024: 8})
        self.assertNotEqual(flat, strat)


if __name__ == "__main__":
    unittest.main()


class FetchCappedWithCollector(unittest.TestCase):
    """The real get_negatives.fetch_capped driving Collector and a shared seen set."""

    def test_pages_dedup_and_quota(self):
        import get_negatives as G
        pages = [{"results": [{"gbifID": i, "decimalLatitude": 44.0, "decimalLongitude": -70.0,
                               "eventDate": "2023-06-01", "year": 2023, "month": 6}
                              for i in ids], "endOfRecords": end}
                 for ids, end in (((1, 2, 3), False), ((4, 5), True))]
        calls = []

        def fake_get(session, path, params=None):
            calls.append(params["offset"])
            return pages[len(calls) - 1]
        orig = G.api_get
        G.api_get = fake_get
        try:
            col = ft.Collector()
            n, stopped, exhausted, _ = G.fetch_capped(None, col, {}, "ME", "Ovenbird", "x",
                                                      4, {"2"})
        finally:
            G.api_get = orig
        self.assertEqual((n, stopped), (4, False))
        self.assertEqual([r["gbif_id"] for r in col.rows], ["1", "3", "4", "5"])   # 2 seen
        self.assertTrue(all(r["state"] == "ME" and r["year"] == 2023 for r in col.rows))


class FetchTopupMain(unittest.TestCase):
    """main() end to end with a fake get_negatives module (no network)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.live = os.path.join(self.tmp.name, "live")
        self.scr = os.path.join(self.tmp.name, "scratch")
        self.ev = os.path.join(self.tmp.name, "evidence")
        os.makedirs(self.ev)
        rows = {R: [_row(R, "Ovenbird", 2023, 10 * i + 1), _row(R, "Ovenbird", 2024, 10 * i + 2)]
                for i, R in enumerate(ft.REGIONS)}
        for tree in (self.live, self.scr):
            for R in ft.REGIONS:
                _write(os.path.join(tree, ft.RAW.format(R=R)), rows[R])
        self.pinned = {R: _sha(os.path.join(self.scr, ft.RAW.format(R=R))) for R in ft.REGIONS}
        self.saved = {k: getattr(ft, k) for k in ("ROOT", "RESULT", "HERE", "pinned_pre_topup",
                                               "DISABLED")}
        ft.DISABLED = False          # the committed script is disabled after its one run
        ft.ROOT, ft.HERE = self.live, self.ev
        ft.RESULT = os.path.join(self.ev, "fetch_topup_result.json")
        ft.pinned_pre_topup = lambda: dict(self.pinned)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(ft, k, v)
        sys.modules.pop("get_negatives_fake", None)
        self.tmp.cleanup()

    def _fake_G(self, stop_on=None):
        import types
        import get_negatives as real
        G = types.SimpleNamespace(CSV_FIELDS=real.CSV_FIELDS, EOD_DATASET_KEY="k",
                                  STATES={"ME": "Maine", "NH": "New Hampshire", "VT": "Vermont"},
                                  TARGET_SPECIES={"Ovenbird": "Seiurus aurocapilla"},
                                  verify_dataset=lambda s: None,
                                  resolve_taxon_keys=lambda s: {"Ovenbird": 1})
        nxt = [1000]

        def fetch_capped(session, writer, params, st, common, sci, cap, seen, start_offset=0):
            if stop_on == (st, params["year"]):
                return 0, True, False, 0
            for _ in range(cap):
                nxt[0] += 1
                seen.add(str(nxt[0]))
                writer.writerow(_row(st, common, params["year"], nxt[0]))
            return cap, False, False, 0
        G.fetch_capped = fetch_capped
        return G

    def _run(self, G):
        import types
        real = sys.modules.get("get_negatives")
        sys.modules["get_negatives"] = G
        try:
            return ft.main(["--tree", self.scr])
        finally:
            if real is not None:
                sys.modules["get_negatives"] = real

    def test_success_appends_and_records(self):
        self.assertEqual(self._run(self._fake_G()), 0)
        for R in ft.REGIONS:
            p = os.path.join(self.scr, ft.RAW.format(R=R))
            self.assertEqual(len(ft.read_rows(p)), 2 + 4)            # 2 x e per year
            with open(os.path.join(self.live, ft.RAW.format(R=R)), "rb") as f:
                live = f.read()
            with open(p, "rb") as f:
                self.assertTrue(f.read().startswith(live))
            self.assertEqual(_sha(os.path.join(self.live, ft.RAW.format(R=R))), self.pinned[R])
        self.assertTrue(os.path.exists(ft.RESULT))
        with self.assertRaises(SystemExit):                         # recorded: never again
            self._run(self._fake_G())

    def test_disabled_script_refuses(self):
        ft.DISABLED = True
        with self.assertRaises(SystemExit):
            self._run(self._fake_G())
        for R in ft.REGIONS:
            self.assertEqual(_sha(os.path.join(self.scr, ft.RAW.format(R=R))), self.pinned[R])

    def test_committed_script_is_disabled(self):
        self.assertTrue(self.saved["DISABLED"])

    def test_abort_writes_nothing_and_allows_retry(self):
        """Code review S2: an aborted attempt leaves a log but does not block a retry."""
        self.assertEqual(self._run(self._fake_G(stop_on=("VT", 2024))), 1)
        for R in ft.REGIONS:
            self.assertEqual(_sha(os.path.join(self.scr, ft.RAW.format(R=R))), self.pinned[R])
        self.assertFalse(os.path.exists(ft.RESULT))
        logs = [f for f in os.listdir(self.ev) if f.startswith("fetch_topup_")]
        self.assertEqual(len(logs), 1)
        self.assertEqual(self._run(self._fake_G()), 0)                # retry runs
