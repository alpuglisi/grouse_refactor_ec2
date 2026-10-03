"""CR-0007 P6: the shared spatial/domain constants have one definition.

Standing check for PA-0001 as extended by CR-0007. Run with
    python -m unittest tests.test_shared_constants

EXPECTED_REGIONS and EXPECTED_PATH_TEMPLATES are the acceptance pins
(CR-0007 section 1). They live here, under tests/, which the scan does not
cover, so they are not a second definition. check_partition.py's P6 reads
them from this file.

`test_repository_tree` fails until CR-0007 deliverable 2 is implemented;
it is marked expectedFailure until then, and deliverable 2 removes the
marker (an unexpected success is reported as a failure).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import check_partition as cp  # noqa: E402

EXPECTED_REGIONS = {
    "REGIONS": ("ME", "NH", "VT"),
    "STATE_FIPS": {"ME": "23", "NH": "33", "VT": "50"},
    "STATE_NAMES": {"ME": "Maine", "NH": "New Hampshire", "VT": "Vermont"},
    "TIGER_YEAR": 2023,
    "COUNTY_POLYGONS_YEAR": 2023,
    "MIN_SPACING_M": 30,
    "BLOCK_SIZE_M": 3000,
    "BUFFER_M": 300,
    # CR-0012 section 1
    "BLOCK_ORIGIN_5070": (0.0, 0.0),
    "VAL_FRACTION": 0.2,
    "SPLIT_SEED": 42,
    "WINDOW_PX": 64,
    # CR-0019 section 2
    "YEAR_MIN": 2020,
    # CR-0021 section 2 B (the pre-registration's S1)
    "YEAR_STRATA": ((2020,), (2021,), (2022,), (2023,), (2024,)),
    "BOXES": {
        "ME": (-71.158, 42.889, -66.852, 47.555),
        "NH": (-72.626, 42.605, -70.600, 45.398),
        "VT": (-73.510, 42.632, -71.422, 45.112),
    },
}
EXPECTED_PATH_TEMPLATES = {
    "tiger_county": "data/roads/tl_{year}_us_county.zip",
    "availability_sample": "data/pipeline/availability_sample_{region}.csv",
    # CR-0012 section 4
    "block_assignments": "data/pipeline/block_assignments.csv",
    "candidate_pool": "data/negatives/candidate_pool.csv",
    "split_manifest": "data/pipeline/split_manifest.json",
    "acceptance_record": "data/pipeline/acceptance_record.json",
}
# The only exemptions CR-0007 names; growth of this set is a review item.
EXPECTED_EXEMPT = {"regions.py", "clean.py", "legacy/gen_negs.py",
                   "legacy/audit.py", "legacy/download.py",
                   "legacy/download_more.py"}   # road files re-pointed (d7)

CODES = EXPECTED_REGIONS["REGIONS"]


def scan(text):
    return [w for _, _, w in cp.scan_source(textwrap.dedent(text), "x.py", CODES)]


class ScannerRules(unittest.TestCase):
    def test_literal_assignment_flagged(self):
        self.assertEqual(scan("BUFFER_M = 300\n"), ["literal assigned to BUFFER_M"])

    def test_default_alias_flagged(self):
        self.assertTrue(scan("MIN_SPACING_M_DEFAULT = 30\n"))
        self.assertTrue(scan("TIGER_YEAR = int(os.environ.get('Y', '2025'))\n"))

    def test_attribute_and_annotated_targets_flagged(self):
        self.assertTrue(scan("cfg.TIGER_YEAR = 2025\n"))
        self.assertTrue(scan("BLOCK_SIZE_M: int = 3000\n"))

    def test_import_bindings_accepted(self):
        self.assertEqual(scan("""
            from regions import BUFFER_M, MIN_SPACING_M, REGIONS
            MIN_SPACING_M_DEFAULT = MIN_SPACING_M
            REGIONS_DEFAULT = list(REGIONS)
            STATES = {r.lower(): f"US-{r}" for r in REGIONS}
        """), [])

    def test_region_sequences_flagged(self):
        self.assertTrue(scan('ap.add_argument("--r", default=["ME", "NH", "VT"])\n'))
        self.assertTrue(scan('for r in ("vt", "me", "nh"): pass\n'))
        self.assertEqual(scan('x = ["ME", "NH"]\n'), [])

    def test_region_dicts_flagged(self):
        self.assertTrue(scan('F = {"ME": "23", "NH": "33", "VT": "50"}\n'))
        self.assertTrue(scan('m = {"Maine": "me", "New Hampshire": "nh", "Vermont": "vt"}\n'))
        self.assertTrue(scan('S = {"me": "US-ME", "nh": "US-NH", "vt": "US-VT"}\n'))
        self.assertEqual(scan('BW = {"ME": 3000, "NH": 3000, "VT": 3000}\n'), [])

    def test_exemptions_are_the_named_set(self):
        self.assertEqual(set(cp.P6_EXEMPT), EXPECTED_EXEMPT)


class SyntheticTree(unittest.TestCase):
    """p6_problems on a throwaway git tree: correct -> [], each defect named."""

    def make(self, files):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        os.makedirs(os.path.join(d, "tests"))
        with open(os.path.join(REPO, "tests", "test_shared_constants.py")) as f:
            pins = f.read()
        files = dict(files)
        files["tests/test_shared_constants.py"] = pins
        for p, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(d, p)) or d, exist_ok=True)
            with open(os.path.join(d, p), "w") as f:
                f.write(text)
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        return d

    def good(self):
        regions = "".join(f"{k} = {v!r}\n" for k, v in EXPECTED_REGIONS.items())
        gd = f"PATH_TEMPLATES = {EXPECTED_PATH_TEMPLATES!r}\n"
        user = "from regions import BUFFER_M, REGIONS\nR = list(REGIONS)\n"
        return {"regions.py": regions, "grouse_data.py": gd, "user.py": user}

    def test_correct_tree_has_no_problems(self):
        self.assertEqual(cp.p6_problems(self.make(self.good())), [])

    def test_each_defect_reported(self):
        f = self.good()
        f["user.py"] += "BUFFER_M = 300\n"
        f["inv_scratch.py"] = "BUFFER_M = 300\n"           # excluded by name
        f["clean.py"] = "BUFFER_M = 300\n"                 # named exemption
        f["regions.py"] = f["regions.py"].replace("TIGER_YEAR = 2023",
                                                  "TIGER_YEAR = 2025")
        probs = cp.p6_problems(self.make(f))
        self.assertEqual(len(probs), 2, probs)
        self.assertIn("regions.TIGER_YEAR = 2025", probs[0])
        self.assertTrue(probs[1].startswith("user.py:3:"), probs)

    def test_missing_constant_and_template_reported(self):
        f = self.good()
        f["regions.py"] = f["regions.py"].replace("BUFFER_M = 300\n", "")
        f["grouse_data.py"] = "PATH_TEMPLATES = {}\n"
        probs = cp.p6_problems(self.make(f))
        self.assertIn("regions.BUFFER_M not defined as a literal", probs)
        self.assertEqual(sum("PATH_TEMPLATES" in p for p in probs),
                         len(EXPECTED_PATH_TEMPLATES))

    def test_untracked_file_not_scanned(self):
        d = self.make(self.good())
        with open(os.path.join(d, "later.py"), "w") as fh:
            fh.write("BUFFER_M = 300\n")
        self.assertEqual(cp.p6_problems(d), [])


    def test_evidence_dir_skipped_other_docs_scanned(self):
        """CR-0007 v9.2: only docs/quality/evidence/ is outside the scan."""
        f = self.good()
        f["docs/quality/evidence/x.py"] = "BUFFER_M = 300\n"
        f["docs/other/x.py"] = "BUFFER_M = 300\n"
        d = self.make(f)
        scanned = cp.p6_scanned_files(d)
        self.assertNotIn("docs/quality/evidence/x.py", scanned)
        self.assertIn("docs/other/x.py", scanned)
        probs = cp.p6_problems(d)
        self.assertEqual(len(probs), 1, probs)
        self.assertTrue(probs[0].startswith("docs/other/x.py:1:"), probs)


class DocsImports(unittest.TestCase):
    """CR-0007 v9.2: no scanned module loads code from docs/ (P7)."""

    def problems(self, text, path="user.py"):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        with open(os.path.join(d, path), "w") as fh:
            fh.write(textwrap.dedent(text))
        return cp.docs_import_problems(d, files=[path])

    def test_clean_module_passes(self):
        self.assertEqual(self.problems("""
            import os, sys
            sys.path.insert(0, os.path.dirname(__file__))
            from regions import REGIONS
            DOC = "see docs/quality/x.md"
        """), [])

    def test_each_way_of_loading_docs_code_flagged(self):
        for src in ("import docs.quality.evidence.lib\n",
                    "from docs.quality.evidence import lib\n",
                    "import sys\nsys.path.insert(0, 'docs/quality/evidence/CR-0007-r7')\n",
                    "import sys, os\nsys.path.append(os.path.join(HERE, 'docs'))\n",
                    "import importlib.util as u\nu.spec_from_file_location('m', 'docs/x.py')\n",
                    "import runpy\nrunpy.run_path('docs/quality/evidence/x.py')\n"):
            with self.subTest(src=src):
                self.assertEqual(len(self.problems(src)), 1, src)

    def test_repository_has_none(self):
        self.assertEqual(cp.docs_import_problems(REPO), [])


class RepositoryTree(unittest.TestCase):
    def test_repository_tree(self):
        probs = cp.p6_problems(REPO)
        self.assertEqual(probs, [], "\n" + "\n".join(probs))


if __name__ == "__main__":
    unittest.main()
