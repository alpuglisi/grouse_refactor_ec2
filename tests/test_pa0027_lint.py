"""CR-0018: mechanical enforcement of PA-0027 (broad handlers fail closed).

Committed before approval as CR-0018's acceptance/gate code (CLAUDE.md
section 1 / CR-0011 A3). Run with
    python -m unittest tests.test_pa0027_lint -v

File set: `git ls-files '*.py'` minus `inv_*`, `res_*` and `docs/**` (the
evidence scripts), the same set as tests/test_nodata_zero_lint.py. Files
whose first statement after the docstring is `raise SystemExit(...)`
(PA-0026 guard, `check_partition.guard_first`) cannot run and are not
scanned; that set is pinned in EXPECTED_GUARDED.

Rule (CR-0018 section "Lint rule"):
  * A handler is BROAD if its type is absent (bare `except:`), or names
    `Exception` / `BaseException` (bare or as an attribute, e.g.
    `builtins.Exception`), or is a tuple containing one of those.
    `except*` handlers are included, and so is a call
    `suppress(<broad type>)` (contextlib), which never conforms.
  * A broad handler CONFORMS MECHANICALLY if its body always ends the
    operation abnormally. Statements are taken in order: the first one
    that can leave the handler normally (a `return` anywhere in it, or a
    `break`/`continue` not inside a loop nested in it; nested def/class/
    lambda ignored, `finally` included) makes it non-conforming; the
    first one that always aborts makes it conform. Always aborts: a
    `raise` (a `SystemExit` only with a non-falsy constant or f-string
    argument), a `sys.exit` / `os._exit` / `exit` / `quit` call with such
    an argument, an `if` whose body and `else` both abort, a `with` (not
    `suppress(...)`) whose body aborts, a `try` whose `finally` aborts or
    whose body and every handler abort. Anything else (pass, falling off
    the end, a conditional raise without an else, `exit(var)`) does not
    conform mechanically.
  * Every other broad handler must be classified by review, keyed by
    (path, enclosing qualname, ordinal of the broad handler within that
    scope) and pinned by a digest of the handler's AST and of its whole
    enclosing scope (innermost def/class, or the module-level statement;
    no line numbers). A classified handler whose code, or whose
    enclosing function, changes no longer matches its digest and fails
    the test until it is re-reviewed.

Three classified sets, disjoint:
  ALLOWLIST             conforming by PA-0027's fail-closed / visible-
                        unknown / cleanup / fallback clauses (reason cites
                        the PA-0027 sweep, BUG-0049 section 8);
  KNOWN_OPEN            known defects with an owning open BUG;
  EXPECTED_UNCLASSIFIED today's handlers the PA-0027 sweep did not
                        classify or that depart from its retry clause -
                        CR-0018's BUG candidates, pinned until each is
                        filed and either fixed or moved to ALLOWLIST.
The repository test passes only if the non-conforming set equals the
union of the three exactly, so any NEW non-conforming broad handler, any
edit to a classified one, and any fix that leaves a stale entry fails.
"""
import ast
import hashlib
import os
import re
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from check_partition import guard_first  # noqa: E402

EXCLUDE = re.compile(r"^(inv_|res_|docs/)")
BROAD_NAMES = {"Exception", "BaseException"}
EXIT_CALLS = {("sys", "exit"), ("os", "_exit"), (None, "exit"),
              (None, "quit")}

# Classes used in ALLOWLIST (PA-0027 wording).
FAIL_CLOSED = "fail-closed"          # resolves to refuse/invalid/FAIL/abort
VISIBLE_UNKNOWN = "visible-unknown"  # diagnostic/OBS; reason printed/recorded
CLEANUP = "cleanup"                  # best-effort release of a resource
FALLBACK = "fallback"                # falls back to an equivalent source,
                                     # or to a path that aborts naming the error

# key -> (digest, class, justification). Reviewed as part of CR-0018.
# Each justification cites the PA-0027 sweep (BUG-0049 section 8), whose
# line numbers predate 4683e3c; current lines are printed by the test.
# A VISIBLE_UNKNOWN entry must record or print the exception type
# (PA-0027 text); entries that do not are candidate C5 instead.
ALLOWLIST = {
    ('acceptance_split.py', 'Rasters.is_valid', 0): (
        '0cc887bcc1ab', FAIL_CLOSED,
        'validity probe -> invalid; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:454'),
    ('acceptance_split.py', 'Replay.run', 0): (
        'f351b68afde2', FAIL_CLOSED,
        "error stored per stage and reported as the R gates' FAIL; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:852"),
    ('acceptance_split.py', 'gate_E0', 0): (
        '2da8dc93d34f', FAIL_CLOSED,
        "unreadable JSON appended to the gate's problems -> FAIL; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:1417"),
    ('acceptance_split.py', 'gate_E8', 0): (
        '2693e8caeee5', FAIL_CLOSED,
        'predicate not evaluable appended to problems -> FAIL; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:1675'),
    ('acceptance_split.py', 'gate_E10', 0): (
        '9e412c9a3046', FAIL_CLOSED,
        'recomputation failure appended to problems -> FAIL; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:1749'),
    ('acceptance_split.py', 'parse_regions_py', 0): (
        '7366d2d3dfea', FAIL_CLOSED,
        "non-literal recorded as '<not a literal>' -> E11(e) mismatch; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:1782"),
    ('acceptance_split.py', 'gate_E12', 0): (
        'cec413cccbe8', FAIL_CLOSED,
        'recomputation failure appended to problems -> FAIL; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:1928'),
    ('acceptance_split.py', 'evaluate', 0): (
        '07b1ccdefa8a', FAIL_CLOSED,
        "'gate not evaluable' problem with type -> FAIL; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:2067"),
    ('acceptance_split.py', 'compute_obs', 0): (
        'd10749a7a802', VISIBLE_UNKNOWN,
        'OBS note records type and message, row n/a; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:2370'),
    ('acceptance_split.py', 'compute_obs', 1): (
        '903eeb293b3c', VISIBLE_UNKNOWN,
        'OBS note records type and message, row n/a; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:2376'),
    ('acceptance_split.py', 'compute_obs', 2): (
        '2192cc902d51', VISIBLE_UNKNOWN,
        'OBS note records type and message, row n/a; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:2382'),
    ('acceptance_split.py', 'full_run', 1): (
        'f05faa9e642f', VISIBLE_UNKNOWN,
        'OBS failure printed with type, every O-row n/a; PA-0027 sweep (BUG-0049 s.8) acceptance_split.py:2625'),
    ('dataset.py', 'GrousePatchDataset._close_handles', 0): (
        '9966262b9480', CLEANUP,
        'best-effort close() of read handles; PA-0027 sweep (BUG-0049 s.8) dataset.py:208'),
    ('download_tcc_nlcd.py', 'resolve_collection', 0): (
        'a787e2e7fd57', FALLBACK,
        'next candidate, skipped ids printed with type; none readable -> SystemExit; PA-0027 sweep (BUG-0049 s.8) download_tcc_nlcd.py:189'),
    ('download_tcc_nlcd.py', 'collection_years', 0): (
        '8b990e09b590', FALLBACK,
        'year parse falls back to system:index; empty result -> SystemExit in the caller (download_tcc_nlcd.py:507); PA-0027 sweep (BUG-0049 s.8) download_tcc_nlcd.py:209'),
    ('download_treemap.py', 'resolve_vintage_image', 0): (
        'b16648021b2b', FALLBACK,
        'ImageCollection -> Image; that failing raises SystemExit with the error; PA-0027 sweep (BUG-0049 s.8) download_treemap.py:194/200'),
    ('grouse_data.py', 'RegionData._is_valid_raster', 0): (
        '7aa534a313f5', FAIL_CLOSED,
        "validity probe -> invalid (the caller's nearest-year fallback is designed and recorded by E11(b)); PA-0027 sweep (BUG-0049 s.8) grouse_data.py:327"),
}

# key -> (digest, owning BUG). Open defects; removing the entry is part
# of the owning BUG's fix.
KNOWN_OPEN = {
    ('download_rev.py', 'download_one', 0): ('714a04258470', 'BUG-0013'),
    ('download_rev.py', 'download_one', 1): ('11306fa01b42', 'BUG-0013'),
    ('ebird.py', 'main', 0): ('8bc7ec3f45b2', 'BUG-0013'),
}

# key -> (digest, candidate id). CR-0018's BUG candidates (CR section 4),
# pinned until each is filed and fixed or moved to ALLOWLIST by review;
# the lead may replace a CR-0018-Cn id by the BUG id it is filed under.
EXPECTED_UNCLASSIFIED = {
    ('download_rev.py', 'published_products', 0): ('c64736437d46', 'CR-0018-C1'),
    ('download_tcc_nlcd.py', 'fetch_tile', 0): ('9408667ddb10', 'CR-0018-C2'),
    ('download_treemap.py', 'fetch_tile', 0): ('5bdafe0db0cf', 'CR-0018-C2'),
    ('download_tcc_nlcd.py', 'ee_init', 0): ('f30ab3d84bc7', 'CR-0018-C3'),
    ('download_treemap.py', 'ee_init', 0): ('f30ab3d84bc7', 'CR-0018-C3'),
    ('acceptance_split.py', 'git_commit', 0): ('1bef1b004199', 'CR-0018-C4'),
    ('acceptance_split.py', 'full_run', 0): ('5c01e691829a', 'CR-0018-C5'),
    ('analyze_grouse.py', 'load_state_boundaries', 0): ('f60ef2b09228', 'CR-0018-C5'),
    ('analyze_grouse.py', 'load_state_boundaries', 1): ('0d27d8305b05', 'CR-0018-C5'),
    ('check_exotic.py', 'check_sclass_meaning', 0): ('52841f9f918f', 'CR-0018-C5'),
    ('check_raster.py', 'check_one', 0): ('cab80fa34317', 'CR-0018-C5'),
    ('check_road_dist.py', 'cmd_check', 0): ('6245b58398e9', 'CR-0018-C5'),
    ('symptom_check.py', 'region_point_frames', 0): ('27faa6cca98a', 'CR-0018-C5'),
    ('diagnose_training.py', 'main', 0): ('2139181fae8b', 'CR-0018-C6'),
    ('diagnose_water_bias.py', 'process_region', 0): ('b97acb340971', 'CR-0018-C6'),
    ('generate_treemap_features.py', '_source_is_valid', 0): ('7ce950d3d7c4', 'CR-0018-C7'),
}

# PA-0026 guarded files (not scanned). Growth is a review item.
EXPECTED_GUARDED = {"clean.py", "legacy/audit.py", "legacy/download.py",
                    "legacy/download_landfire.py",
                    "legacy/download_landfire_2.py",
                    "legacy/download_landfire_3.py",
                    "legacy/download_more.py", "legacy/gen_negs.py"}

# Files that must always be in scope (homes of PA-0027 sweep handlers).
MUST_SCAN = {"acceptance_split.py", "download_rev.py", "ebird.py",
             "download_tcc_nlcd.py", "download_treemap.py",
             "generate_negatives.py", "grouse_data.py", "analyze_grouse.py",
             "diagnose_wetland.py", "dataset.py",
             "tests/test_pa0027_lint.py"}


# ---------------------------------------------------------------- rule
def _exc_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def is_broad(handler):
    t = handler.type
    if t is None:
        return True
    elts = t.elts if isinstance(t, ast.Tuple) else [t]
    return any(_exc_name(e) in BROAD_NAMES for e in elts)


def _exit_arg_fails(args):
    """True only if an exit call / SystemExit with these args certainly
    exits non-zero: a non-falsy constant (1, "message") or an f-string.
    Absent, 0/None/False, or any non-constant (may be 0) is not."""
    if not args:
        return False
    a = args[0]
    if isinstance(a, ast.JoinedStr):
        return True
    return isinstance(a, ast.Constant) and a.value not in (0, None, False)


def _is_abort_raise(stmt):
    exc = stmt.exc
    if exc is None:                               # bare re-raise
        return True
    fn = exc.func if isinstance(exc, ast.Call) else exc
    if _exc_name(fn) == "SystemExit":
        return isinstance(exc, ast.Call) and _exit_arg_fails(exc.args)
    return True


def _is_exit_call(stmt):
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return False
    f = stmt.value.func
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        name = (f.value.id, f.attr)
    elif isinstance(f, ast.Name):
        name = (None, f.id)
    else:
        return False
    return name in EXIT_CALLS and _exit_arg_fails(stmt.value.args)


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
_LOOPS = (ast.For, ast.AsyncFor, ast.While)


def _escapes(node, in_loop=False):
    """`node` can leave the handler normally: a `return` anywhere, or a
    `break`/`continue` not inside a loop that is itself inside `node`
    (nested def/class/lambda ignored; `finally` blocks included)."""
    if isinstance(node, ast.Return):
        return True
    if isinstance(node, (ast.Break, ast.Continue)):
        return not in_loop
    if isinstance(node, _SCOPES):
        return False
    if isinstance(node, _LOOPS):
        return (any(_escapes(c, True) for c in node.body)
                or any(_escapes(c, in_loop) for c in node.orelse)
                or _escapes(getattr(node, "test", None) or
                            getattr(node, "iter", None), in_loop))
    return any(_escapes(c, in_loop) for c in ast.iter_child_nodes(node))


def _suppresses(withnode):
    return any(isinstance(i.context_expr, ast.Call)
               and _exc_name(i.context_expr.func) == "suppress"
               for i in withnode.items)


def _stmt_aborts(s):
    if isinstance(s, ast.Raise):
        return _is_abort_raise(s)
    if _is_exit_call(s):
        return True
    if isinstance(s, ast.If):
        return always_aborts(s.body) and always_aborts(s.orelse)
    if isinstance(s, (ast.With, ast.AsyncWith)):
        return not _suppresses(s) and always_aborts(s.body)
    if isinstance(s, (ast.Try, getattr(ast, "TryStar", ast.Try))):
        if always_aborts(s.finalbody):
            return True
        return always_aborts(s.body + s.orelse) and all(
            always_aborts(h.body) for h in s.handlers)
    return False


def always_aborts(stmts):
    """Every path through `stmts` ends in a re-raise or failing exit:
    statements are taken in order; the first that can leave normally
    (`_escapes`) fails the block, the first that always aborts passes it."""
    for s in stmts:
        if _escapes(s):
            return False
        if _stmt_aborts(s):
            return True
    return False


def _dump(node):
    kw = {"annotate_fields": False, "include_attributes": False}
    if sys.version_info >= (3, 13):
        kw["show_empty"] = True      # 3.12-compatible output (CR-0018 R-A6)
    return ast.dump(node, **kw)


def handler_digest(handler, scope):
    """Digest of the handler AND its enclosing scope (the innermost
    def/class, or the module-level statement): a classified handler's
    meaning can depend on code after it in the same function (a
    fallback, a final check), so any edit there is a re-review too."""
    dump = _dump(handler) + "\n" + _dump(scope)
    return hashlib.sha256(dump.encode()).hexdigest()[:12]


class _Collector(ast.NodeVisitor):
    def __init__(self):
        self.stack, self.nodes, self.counts, self.out = [], [], {}, []

    def visit_Module(self, node):
        for stmt in node.body:            # module scope: digest the stmt
            self.nodes.append(stmt)
            self.visit(stmt)
            self.nodes.pop()

    def _scope(self, node):
        self.stack.append(node.name)
        self.nodes.append(node)
        self.generic_visit(node)
        self.nodes.pop()
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope

    def _add(self, node):
        q = ".".join(self.stack) or "<module>"
        i = self.counts.get(q, 0)
        self.counts[q] = i + 1
        self.out.append((q, i, node, self.nodes[-1]))

    def visit_ExceptHandler(self, node):
        if is_broad(node):
            self._add(node)
        self.generic_visit(node)

    def visit_Call(self, node):
        # `contextlib.suppress(Exception)` is `except Exception: pass`.
        if _exc_name(node.func) == "suppress" and any(
                _exc_name(a) in BROAD_NAMES for a in node.args):
            self._add(node)
        self.generic_visit(node)


def _conforms(node):
    return isinstance(node, ast.ExceptHandler) and always_aborts(node.body)


def broad_handlers(source):
    """[(qualname, ordinal, lineno, conforms, digest)] in source order,
    for broad `except` handlers and `suppress(<broad>)` calls."""
    c = _Collector()
    c.visit(ast.parse(source))
    return [(q, i, h.lineno, _conforms(h), handler_digest(h, scope))
            for q, i, h, scope in c.out]


def violations(source):
    """{(qualname, ordinal): (lineno, digest)} for non-conforming handlers."""
    return {(q, i): (ln, d) for q, i, ln, ok, d in broad_handlers(source)
            if not ok}


# ---------------------------------------------------------- repository
def _tracked():
    return subprocess.check_output(["git", "ls-files", "*.py"], cwd=REPO,
                                   text=True).split()


def file_sets():
    """(scanned, guarded) over the file set."""
    scanned, guarded = [], []
    for f in _tracked():
        if EXCLUDE.match(f):
            continue
        (guarded if guard_first(os.path.join(REPO, f)) else scanned).append(f)
    return scanned, guarded


def scan_repo():
    """{(path, qualname, ordinal): (lineno, digest)} of non-conforming
    broad handlers in the scanned file set."""
    found = {}
    for path in file_sets()[0]:
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            for (q, i), v in violations(fh.read()).items():
                found[(path, q, i)] = v
    return found


def classified():
    """{key: digest} over the three classified sets."""
    out = {}
    for table in (ALLOWLIST, KNOWN_OPEN, EXPECTED_UNCLASSIFIED):
        for k, v in table.items():
            out[k] = v[0]
    return out


def git_show(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"],
                                   cwd=REPO, text=True)


# ------------------------------------------------------------ controls
POSITIVE_CONTROLS = {       # each must yield exactly one violation
    "log_and_continue": "for r in rs:\n try: f(r)\n except Exception as e:\n"
                        "  print(e)\n  continue\n",
    "bare_pass": "try: f()\nexcept: pass\n",
    "return_none": "def g():\n try: return f()\n except Exception:\n"
                   "  return None\n",
    "tuple": "try: f()\nexcept (ValueError, Exception): x = 1\n",
    "base_exception": "try: f()\nexcept BaseException as e: log(e)\n",
    "attribute": "try: f()\nexcept builtins.Exception: pass\n",
    "systemexit_zero": "try: f()\nexcept Exception: raise SystemExit(0)\n",
    "systemexit_empty": "try: f()\nexcept Exception: raise SystemExit\n",
    "sys_exit_no_arg": "try: f()\nexcept Exception: sys.exit()\n",
    "conditional_raise": "try: f()\nexcept Exception as e:\n"
                         " if fatal(e): raise\n",
    "raise_in_nested_def": "try: f()\nexcept Exception:\n"
                           " def h(): raise\n",
    "inner_swallow": "try: f()\nexcept Exception:\n try: raise\n"
                     " except ValueError: pass\n",
    "retry_no_raise": "for a in range(3):\n try: return f()\n"
                      " except Exception: time.sleep(1)\n",
    "except_star": "try: f()\nexcept* Exception: pass\n",
    # CR-0018 review round 1 (R-A1/B1, R-A5b, B7): early exit before
    # the raise, dead raise, finally-return, suppressed raise, exit(var)
    "cond_return_then_raise": "try: f()\nexcept Exception:\n"
                              " if lenient: return\n raise\n",
    "return_then_dead_raise": "def g():\n try: f()\n except Exception:\n"
                              "  return\n  raise\n",
    "loop_cond_continue": "for r in rs:\n try: f(r)\n except Exception:\n"
                          "  if r not in REQUIRED:\n   continue\n  raise\n",
    "continue_in_with": "for r in rs:\n try: f(r)\n except Exception:\n"
                        "  with lock:\n   continue\n  raise\n",
    "try_return_finally": "def g():\n try: f()\n except Exception:\n"
                          "  try: return None\n  finally: pass\n  raise\n",
    "finally_return": "def g():\n try: f()\n except Exception:\n"
                      "  try: raise\n  finally: return\n",
    "suppressed_raise": "try: f()\nexcept Exception:\n"
                        " with suppress(RuntimeError):\n  raise\n",
    "systemexit_var": "try: f()\nexcept Exception: raise SystemExit(rc)\n",
    "sys_exit_var": "try: f()\nexcept Exception: sys.exit(rc)\n",
    "suppress": "with contextlib.suppress(Exception):\n f()\n",
    "suppress_base": "with suppress(OSError, BaseException):\n f()\n",
}
NEGATIVE_CONTROLS = {      # each must yield no violation
    "reraise": "try: f()\nexcept Exception:\n log()\n raise\n",
    "raise_from": "try: f()\nexcept Exception as e:\n"
                  " raise RuntimeError('x') from e\n",
    "narrow": "try: f()\nexcept ValueError: pass\n",
    "suppress_narrow": "with suppress(FileNotFoundError):\n f()\n",
    "inner_loop_break": "try: f()\nexcept Exception:\n for x in xs:\n"
                        "  if x: break\n raise\n",
    "nested_def_return": "try: f()\nexcept Exception:\n"
                         " def h(): return 1\n raise\n",
    "systemexit_fstring": "try: f()\nexcept Exception as e:\n"
                          " raise SystemExit(f'bad {e}')\n",
    "sys_exit_1": "try: f()\nexcept Exception:\n print('x')\n sys.exit(1)\n",
    "systemexit_msg": "try: f()\nexcept Exception as e:\n"
                      " raise SystemExit(f'failed: {e}')\n",
    "if_else_raise": "try: f()\nexcept Exception as e:\n"
                     " if a: raise\n else: raise X() from e\n",
    "with_raise": "try: f()\nexcept Exception:\n with lock:\n  raise\n",
    "finally_raise": "try: f()\nexcept Exception:\n try: g()\n"
                     " finally: raise\n",
}


class TestRuleControls(unittest.TestCase):
    def test_positive_controls_flagged(self):
        for name, src in POSITIVE_CONTROLS.items():
            with self.subTest(name=name):
                self.assertEqual(len(violations(src)), 1, src)

    def test_negative_controls_pass(self):
        for name, src in NEGATIVE_CONTROLS.items():
            with self.subTest(name=name):
                self.assertEqual(violations(src), {}, src)

    def test_key_is_scope_and_ordinal_not_line(self):
        src = ("def a():\n try: f()\n except Exception: pass\n"
               " try: g()\n except: pass\n")
        self.assertEqual(set(violations(src)), {("a", 0), ("a", 1)})
        moved = "\n\n\n" + src
        self.assertEqual(
            {k: v[1] for k, v in violations(src).items()},
            {k: v[1] for k, v in violations(moved).items()})

    def test_digest_changes_with_body(self):
        a = violations("try: f()\nexcept Exception:\n print(1)\n")
        b = violations("try: f()\nexcept Exception:\n print(2)\n")
        self.assertNotEqual(a[("<module>", 0)][1], b[("<module>", 0)][1])


class TestHistoricalDefects(unittest.TestCase):
    """PA-0021(a): the lint must flag the real pre-fix code of every bug
    PA-0027 was derived from or found by its sweep, and none of those
    handlers may match a classified entry."""
    CASES = [
        # (bug, rev, path, qualname)
        ("BUG-0049", "3230262", "generate_negatives.py", "process_region"),
        ("BUG-0052", "4683e3c^", "download_rev.py",
         "_raster_valid_fraction"),
        ("BUG-0053", "4683e3c^", "analyze_grouse.py", "load_evt_crosswalk"),
        ("BUG-0054", "4683e3c^", "download_tcc_nlcd.py", "sighting_years"),
        ("BUG-0055", "4683e3c^", "diagnose_wetland.py", "center_codes"),
    ]

    def test_prefix_code_flagged_and_unclassified(self):
        known = classified()
        for bug, rev, path, qual in self.CASES:
            with self.subTest(bug=bug):
                v = violations(git_show(rev, path))
                hits = [(q, i, d) for (q, i), (_, d) in v.items()
                        if q == qual]
                self.assertTrue(hits, f"{bug}: {path}:{qual} not flagged")
                for q, i, d in hits:
                    self.assertNotEqual(known.get((path, q, i)), d,
                                        f"{bug} handler is classified")


class TestMutations(unittest.TestCase):
    """Mutating a conforming or classified handler on today's tree must
    change the repository result."""

    def _read(self, path):
        with open(os.path.join(REPO, path), encoding="utf-8") as fh:
            return fh.read()

    def test_reraise_to_skip_flagged(self):
        # generate_negatives.main's BUG-0049 fix, reverted to a skip
        src = self._read("generate_negatives.py")
        self.assertEqual(violations(src).get(("main", 0)), None)
        old = ("        traceback.print_exc()\n        raise\n")
        self.assertEqual(src.count(old), 1)
        mutated = src.replace(old, "        traceback.print_exc()\n"
                                   "        return\n")
        self.assertIn(("main", 0), violations(mutated))
        # and scan_repo would report it as NEW (not classified)
        self.assertNotIn(("generate_negatives.py", "main", 0), classified())

    def test_edit_to_classified_handler_detected(self):
        known = classified()
        path, q, i = ("grouse_data.py", "RegionData._is_valid_raster", 0)
        self.assertIn((path, q, i), known)
        src = self._read(path)
        old = "        except Exception:\n            valid = False\n"
        self.assertEqual(src.count(old), 1)
        mutated = src.replace(old, "        except Exception:\n"
                                   "            valid = True\n")
        v = violations(mutated)
        self.assertIn((q, i), v)
        self.assertNotEqual(v[(q, i)][1], known[(path, q, i)])


    def test_edit_after_handler_in_same_scope_detected(self):
        # CR-0018 R-A4/B6: a FALLBACK entry's meaning depends on code
        # after the handler; deleting that fallback must change the digest
        known = classified()
        path, q, i = ("download_tcc_nlcd.py", "collection_years", 0)
        src = self._read(path)
        old = "    if not years:\n        for idx in"
        self.assertEqual(src.count(old), 1)
        mutated = src.replace(old, "    if False:\n        for idx in")
        v = violations(mutated)
        self.assertIn((q, i), v)
        self.assertNotEqual(v[(q, i)][1], known[(path, q, i)])


class TestRepository(unittest.TestCase):
    def test_file_set_scope(self):
        scanned, guarded = file_sets()
        self.assertTrue(MUST_SCAN <= set(scanned), MUST_SCAN - set(scanned))
        self.assertEqual(set(guarded), EXPECTED_GUARDED)
        excluded = [f for f in _tracked() if EXCLUDE.match(f)]
        self.assertTrue(excluded)                     # tracked inv_*.py
        self.assertFalse(set(excluded) & set(scanned))
        self.assertGreaterEqual(len(scanned), 60)     # 60 when written

    def test_classified_sets_disjoint(self):
        a, k, u = set(ALLOWLIST), set(KNOWN_OPEN), set(EXPECTED_UNCLASSIFIED)
        self.assertFalse(a & k or a & u or k & u)
        for key, (_, cls, why) in ALLOWLIST.items():
            with self.subTest(key=key):
                self.assertIn(cls, {FAIL_CLOSED, VISIBLE_UNKNOWN, CLEANUP,
                                    FALLBACK})
                self.assertRegex(why, r"PA-0027|BUG-\d{4}")
        for key, (_, owner) in KNOWN_OPEN.items():
            self.assertRegex(owner, r"^BUG-\d{4}$")
        for key, (_, cand) in EXPECTED_UNCLASSIFIED.items():
            self.assertRegex(cand, r"^(CR-0018-C\d+|BUG-\d{4})$")

    def test_no_unclassified_violation(self):
        found = scan_repo()
        known = classified()
        for (path, q, i), (ln, d) in sorted(found.items()):
            tag = ("ALLOW" if (path, q, i) in ALLOWLIST else
                   "OPEN" if (path, q, i) in KNOWN_OPEN else
                   "CAND" if (path, q, i) in EXPECTED_UNCLASSIFIED else
                   "NEW")
            print(f"PA-0027 {tag:5} {path}:{ln} {q}#{i} {d}",
                  file=sys.stderr)
        new = {k: v for k, v in found.items() if k not in known}
        changed = {k: v for k, v in found.items()
                   if k in known and known[k] != v[1]}
        stale = set(known) - set(found)
        shifted = sorted({(p, q) for p, q, _ in new}
                         & {(p, q) for p, q, _ in changed})
        if shifted:     # CR-0018 B8
            print("PA-0027 hint: new AND changed handlers in the same scope "
                  f"{shifted} - an inserted handler may have shifted the "
                  "ordinals; re-key the classified entries", file=sys.stderr)
        self.assertEqual(
            (new, changed, stale), ({}, {}, set()),
            "PA-0027 lint: new non-conforming broad handler(s), classified "
            "handler(s) edited since review (digest), or stale entries")


if __name__ == "__main__":
    unittest.main()
