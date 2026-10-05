"""CR-0015 L1: no validity/nodata mask may treat a literal 0 as nodata.

Mechanical enforcement of PA-0006's reader side (CR-0015 deliverable 3,
committed before approval under CLAUDE.md section 1 / CR-0011 A3). Run with
    python -m unittest tests.test_nodata_zero_lint -v

File set: `git ls-files '*.py'` minus `inv_*`, `res_*` and `docs/**`
(the evidence scripts). Rule: CR-0015 section "L1 rule", parts (a), (b),
(b'), (c), (d). Matches are de-duplicated per statement: a matched node
nested inside another matched node is not reported separately, and each
match is keyed by (path, ast.unparse(outermost matched node)) - never by
line number.

CR-0015 deliverables 4 (PA-0006 re-sweep) and 6 (the train.py fix) are
done: every match must be in ALLOWLIST, each entry with its reviewed
not-a-defect justification, and EXPECTED_UNCLASSIFIED is empty, so any new
match fails. This is PA-0028's mechanical enforcement (extends PA-0006).
"""
import ast
import os
import re
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE = re.compile(r"^(inv_|res_|docs/)")
BEARING = re.compile(r"nodata|sentinel", re.IGNORECASE)
EXCLUDES_ZERO = (ast.NotEq, ast.Gt, ast.Lt)     # under `&` / `and`
INCLUDES_ZERO = (ast.Eq, ast.LtE, ast.GtE)      # under `|` / `or`
DISPLAYS = (ast.Set, ast.List, ast.Tuple)

# (path, statement text) -> justification citing the deliverable-4 sweep
# (CR-0015 deliverable 4, 2026-09-30; BUG-0032 section 8). Reviewed as part
# of CR-0015.
ALLOWLIST = {
    ("find_tsd_contrast_points.py",
     "~np.isin(nlcd_arr, NODATA_SENTINELS) & (nlcd_arr != 0)"):
        "CR-0015 d4 sweep: NLCD 0 is not a land-cover class (codes 11-95; "
        "download_tcc_nlcd.py maps 0/250 to -9999, and 0 occurs in no pixel "
        "of the ME/NH/VT 2025 rasters), so != 0 only rejects a WarpedVRT "
        "0-fill; diagnostic script that writes nothing.",
    ("generate_time_since_disturbance.py", "(arr > 0) & ~sentinel"):
        "CR-0015 d4 sweep: 0 is the disturbance VAT's 'Background' class "
        "(covered, undisturbed); it stays in cov (only NODATA_SENTINELS are "
        "removed at cov &= ~sentinel), and hit is the disturbance predicate, "
        "not a validity mask.",
    ("check_road_dist.py", "(state != 0) & ~home"):
        "CR-0015 d4 sweep: state is a rasterised county STATEFP with fill=0; "
        "FIPS codes are >= 1, so 0 is 'no US county', not a raster reading, "
        "and other is a zone mask, not a nodata mask.",
    ("tests/cr0015_wrong_samplers.py", "set(NODATA_SENTINELS) | {nodata, 0}"):
        "CR-0015 PA-0021(a): todays_sampler is a deliberate verbatim copy of "
        "the pre-CR sampler (BUG-0032 included), used only to show the "
        "CR-0015 checks fail on it; never called by production code.",
    ("check_canopy_structure.py", "(shares > 0) & (shares < 1000)"):
        "CR-0032 review B2-1: interior-share test (a share strictly inside "
        "(0, 1000) per mille), not a validity mask; NODATA cells are "
        "excluded by the separate `valid` mask it is indexed with, and 0 is "
        "a real reading (PA-0028) that the test deliberately counts as a "
        "boundary value.",
    ("generate_canopy_structure.py", "(valid > 0) & (valid < 1)"):
        "CR-0032 deliverable 2 (A2-1): pilot diagnostic counting cells whose "
        "raw validity FRACTION lies strictly inside (0, 1) - the evidence "
        "that the validity band was aggregated; a printed statistic, not a "
        "mask, and `valid` is a 0-1 fraction where 0 means 'no source "
        "pixel', not an encoded reading.",
    ("tests/test_cr0032.py", "[123, 0, NODATA, NODATA, NODATA]"):
        "CR-0032 review B2-1: expected encoder output in a test, where 0 is "
        "the encoded reading of a 0 m cell (PA-0028: 0 is a valid reading) "
        "and NODATA the encoded invalid cells; no mask is built from it.",
}

# Unclassified matches. Empty since CR-0015 deliverables 4 (the three
# statements above classified) and 6 (train.py's
# "set(NODATA_SENTINELS) | {nodata, 0}", BUG-0032, fixed): any match not in
# ALLOWLIST fails the test.
EXPECTED_UNCLASSIFIED = set()

# Files that must always be in scope (the mechanism's known homes). The
# set grows as code is added, so there is no exact count to pin.
MUST_SCAN = {"train.py", "dataset.py", "predict.py", "analyze_grouse.py",
             "generate_time_since_disturbance.py", "generate_road_distance.py",
             "check_road_dist.py", "check_raster_repair.py",
             "find_tsd_contrast_points.py", "legacy/audit.py"}


def _ident(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _bearing(node):
    """Subtree names something matching (?i)nodata|sentinel."""
    return any(_ident(n) is not None and BEARING.search(_ident(n))
               for n in ast.walk(node))


def _zero(node):
    return (isinstance(node, ast.Constant)
            and type(node.value) in (int, float) and node.value == 0)


def _strip(node):
    while (isinstance(node, ast.UnaryOp)
           and isinstance(node.op, (ast.Invert, ast.Not))):
        node = node.operand
    return node


def _flatten(node, op_type):
    if isinstance(node, ast.BinOp) and isinstance(node.op, op_type):
        return _flatten(node.left, op_type) + _flatten(node.right, op_type)
    return [node]


def _zero_compare(node, conjunctive):
    """Single-op Compare against 0 whose op excludes 0 under a conjunction
    or includes 0 under a disjunction (conjunctive=None: any op)."""
    node = _strip(node)
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1
            and (_zero(node.left) or _zero(node.comparators[0]))):
        return False
    if conjunctive is None:          # any single-op compare against 0
        return True
    return isinstance(node.ops[0],
                      EXCLUDES_ZERO if conjunctive else INCLUDES_ZERO)


def _display_with_zero(node):
    return isinstance(node, DISPLAYS) and any(_zero(e) for e in node.elts)


def matches_node(node):
    """Return the rule part ('a', 'b', "b'", 'c', 'd') matched, or None."""
    # (a) display holding 0 and a nodata-bearing element
    if isinstance(node, DISPLAYS) and _display_with_zero(node) and any(
            _bearing(e) for e in node.elts if not _zero(e)):
        return "a"
    # (a) `|` or `+` joining a nodata-bearing operand and a display with 0
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr,
                                                            ast.Add)):
        sides = (node.left, node.right)
        for s, other in (sides, sides[::-1]):
            if _display_with_zero(s) and _bearing(other):
                return "a"
    # (b) `&` / `|` chain with a 0-excluding / 0-including comparison
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd,
                                                            ast.BitOr)):
        conj = isinstance(node.op, ast.BitAnd)
        if any(_zero_compare(o, conj) for o in _flatten(node, type(node.op))):
            return "b"
    if isinstance(node, ast.BoolOp):
        conj = isinstance(node.op, ast.And)
        ops = node.values
        # (b') same, only next to a nodata-bearing operand
        if any(_zero_compare(o, conj) for o in ops) and any(
                _bearing(_strip(o)) and not _zero_compare(o, None)
                for o in ops):
            return "b'"
        # (d) `nodata or 0`
        if (isinstance(node.op, ast.Or) and any(_zero(o) for o in ops)
                and any(_bearing(o) for o in ops)):
            return "d"
    # (c) nodata-bearing operand compared with 0
    if isinstance(node, ast.Compare):
        operands = [node.left] + node.comparators
        if any(_zero(o) for o in operands) and any(
                _bearing(o) for o in operands if not _zero(o)):
            return "c"
    return None


def scan_source(source):
    """Outermost matched expressions in `source`, de-duplicated per
    statement: a match nested inside another match is dropped. Returns
    sorted [(lineno, rule, ast.unparse(node))]."""
    tree = ast.parse(source)
    hits = [n for n in ast.walk(tree) if matches_node(n)]
    inner = set()
    for h in hits:
        for sub in ast.walk(h):
            if sub is not h:
                inner.add(id(sub))
    out = {(h.lineno, matches_node(h), ast.unparse(h))
           for h in hits if id(h) not in inner}
    return sorted(out)


def file_set():
    files = subprocess.check_output(["git", "ls-files", "*.py"], cwd=REPO,
                                    text=True).split()
    return [f for f in files if not EXCLUDE.match(f)]


def scan_repo():
    """{(path, statement text): [lineno, rule]} over the file set."""
    found = {}
    for path in file_set():
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            for lineno, rule, text in scan_source(fh.read()):
                found.setdefault((path, text), [lineno, rule])
    return found


POSITIVE_CONTROLS = [
    "m & (x != 0)",
    "(arr > 0) & ~sentinel",
    "nodata or 0",
    "set(NODATA_SENTINELS) | {nodata, 0}",
    "src.nodata != 0",
    "~np.isin(v, NODATA_SENTINELS) & (v != 0.0)",
    "(v == 0) | (v == nodata)",
    "list(NODATA_SENTINELS) + [0]",
]
NEGATIVE_CONTROLS = [
    "(a < 0) | ~np.isfinite(a)",
    "n == 0 and declared == nodata",
    "vals[vals == src.nodata] = np.nan",
]


class TestRuleControls(unittest.TestCase):
    def test_positive_controls_match(self):
        for snippet in POSITIVE_CONTROLS:
            with self.subTest(snippet=snippet):
                self.assertTrue(scan_source(snippet), snippet)

    def test_negative_controls_do_not_match(self):
        for snippet in NEGATIVE_CONTROLS:
            with self.subTest(snippet=snippet):
                self.assertEqual(scan_source(snippet), [], snippet)

    def test_one_match_per_statement(self):
        # the BinOp and its nested `{nodata, 0}` both match; report one
        hits = scan_source("bad = set(NODATA_SENTINELS) | {nodata, 0}")
        self.assertEqual(len(hits), 1, hits)
        self.assertEqual(hits[0][2], "set(NODATA_SENTINELS) | {nodata, 0}")


class TestRepository(unittest.TestCase):
    def test_file_set_scope(self):
        fs = set(file_set())
        self.assertTrue(MUST_SCAN <= fs, MUST_SCAN - fs)
        raw = subprocess.check_output(["git", "ls-files", "*.py"], cwd=REPO,
                                      text=True).split()
        excluded = [f for f in raw if EXCLUDE.match(f)]
        self.assertTrue(excluded)                  # e.g. tracked inv_*.py
        self.assertFalse(set(excluded) & fs)       # and none is scanned
        self.assertGreaterEqual(len(fs), 60)   # 60 when written; grows

    def test_no_unclassified_match(self):
        found = scan_repo()
        for key, (lineno, rule) in sorted(found.items()):
            print(f"L1 match: {key[0]}:{lineno} ({rule}) {key[1]}",
                  file=sys.stderr)
        unexplained = set(found) - set(ALLOWLIST)
        self.assertEqual(
            unexplained, EXPECTED_UNCLASSIFIED,
            "L1 match set changed. New: "
            f"{sorted(unexplained - EXPECTED_UNCLASSIFIED)}; gone: "
            f"{sorted(EXPECTED_UNCLASSIFIED - unexplained)}")

    def test_allowlist_entries_still_exist(self):
        stale = set(ALLOWLIST) - set(scan_repo())
        self.assertEqual(stale, set(), f"stale allowlist entries: {stale}")


if __name__ == "__main__":
    unittest.main()
