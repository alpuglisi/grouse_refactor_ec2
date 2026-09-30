import ast, sys, difflib
def norm(p):
    t=ast.parse(open(p).read())
    for n in ast.walk(t):
        if isinstance(n,(ast.Module,ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            b=n.body
            if b and isinstance(b[0],ast.Expr) and isinstance(b[0].value,ast.Constant) and isinstance(b[0].value.value,str):
                n.body=b[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(t)).splitlines()
pairs=[("clean.py","prepare_training_data.py"),("legacy/gen_negs.py","generate_negatives.py"),
       ("legacy/audit.py","analyze_grouse.py"),("legacy/download.py","download_rev.py"),
       ("legacy/download_more.py","download_rev.py"),("legacy/download.py","legacy/download_more.py")]
for a,b in pairs:
    A,B=norm(a),norm(b)
    d=[l for l in difflib.unified_diff(A,B,lineterm='') if l[:1] in '+-' and l[:3] not in ('+++','---')]
    print(f"{a} vs {b}: {len(d)} differing lines (A={len(A)}, B={len(B)})")
    if 0<len(d)<=12:
        for l in d: print("   ",l)
