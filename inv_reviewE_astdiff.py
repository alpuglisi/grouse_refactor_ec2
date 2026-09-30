"""Independent AST-normalised comparison of the three alleged duplicate
pairs, plus a docstring-aware executable diff. Read-only."""
import ast, difflib, sys

PAIRS = [("legacy/gen_negs.py", "generate_negatives.py"),
         ("clean.py", "prepare_training_data.py"),
         ("legacy/audit.py", "analyze_grouse.py")]

def norm(path):
    src = open(path).read()
    tree = ast.parse(src)
    # strip docstrings so only executable content remains
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant) and \
                    isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree)).splitlines()

for a, b in PAIRS:
    A, B = norm(a), norm(b)
    d = [l for l in difflib.unified_diff(A, B, a, b, n=0)
         if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))]
    print(f"\n=== {a}  vs  {b} ===")
    print(f"  ast-unparsed lines: {len(A)} vs {len(B)};  diff lines: {len(d)}")
    for l in d[:40]:
        print("   ", l)
