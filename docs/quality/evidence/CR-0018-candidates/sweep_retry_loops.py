"""BUG-0066 sweep: every broad exception handler (PA-0027's definition,
as implemented by tests/test_pa0027_lint.py) that sits inside a
for/while loop in the same scope, with whether it conforms mechanically
(aborts on every path). A retry loop that does not abort on every path
must follow PA-0027's retry clause.

Run: python docs/quality/evidence/CR-0018-candidates/sweep_retry_loops.py
"""
import ast
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, REPO)
from tests import test_pa0027_lint as L  # noqa: E402

SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def loop_handlers(tree):
    out = []

    def walk(node, loops, scope):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, SCOPES):
                walk(child, 0, getattr(child, "name", "<lambda>"))
                continue
            n = loops + isinstance(child, (ast.For, ast.AsyncFor, ast.While))
            if isinstance(child, ast.ExceptHandler) and L.is_broad(child) \
                    and loops:
                out.append((child.lineno, scope, L._conforms(child)))
            walk(child, n, scope)
    walk(tree, 0, "<module>")
    return out


if __name__ == "__main__":
    os.chdir(REPO)
    scanned, _ = L.file_sets()
    n = 0
    for f in scanned:
        with open(f, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for ln, q, ok in loop_handlers(tree):
            n += 1
            print(f"{f}:{ln} {q}: broad handler in a loop, "
                  f"{'aborts on every path' if ok else 'NON-CONFORMING'}")
    print(f"{len(scanned)} files; {n} broad handler(s) inside loops")
