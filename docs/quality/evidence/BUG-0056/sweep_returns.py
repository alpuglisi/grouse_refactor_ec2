"""PA-0030 sweep, second form (BUG-0056 §8): functions whose
`return {...}` dict literals carry different key sets on different paths
(a conditionally present key produced by path choice rather than by a
guarded store). Prints each for manual review of its consumers.

Usage (repo root): python docs/quality/evidence/BUG-0056/sweep_returns.py
                   [FILELIST]   (default: `git ls-files '*.py'`)"""
import ast
import subprocess
import sys

if len(sys.argv) > 1:
    files = [l.strip() for l in open(sys.argv[1]) if l.strip()]
else:
    files = subprocess.check_output(["git", "ls-files", "*.py"],
                                    text=True).split()
files = [f for f in files
         if not f.split("/")[-1].startswith(("inv_", "res_"))
         and not f.startswith("docs/")]
for f in files:
    tree = ast.parse(open(f).read(), f)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        sets = []
        for n in ast.walk(fn):
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict):
                ks = [k.value for k in n.value.keys
                      if isinstance(k, ast.Constant)]
                if len(ks) == len(n.value.keys):
                    sets.append((n.lineno, frozenset(ks)))
        if len({s for _, s in sets}) > 1:
            allk = frozenset().union(*[s for _, s in sets])
            print(f"{f}:{fn.lineno} {fn.name}: returns dicts with differing "
                  f"keys; optional keys "
                  f"{sorted(allk - frozenset.intersection(*[s for _, s in sets]))}"
                  f" at lines {[l for l, _ in sets]}")
