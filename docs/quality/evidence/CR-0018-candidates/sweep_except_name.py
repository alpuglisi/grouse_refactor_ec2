"""PA-0031 sweep (BUG-0067, CR-0018 C3): a name bound by
`except E as NAME` is deleted when the clause ends (Python 3), so any
read of NAME outside that clause, in the same scope, is either an
UnboundLocalError/NameError or reads a different binding.

Flags every Load of an except-target name that is outside every handler
binding that name in the same scope (function, class body or module;
nested def/lambda/comprehension scopes are separate). Also reports
whether the scope binds the name anywhere else (assignment, parameter,
for/with/import target), so a reviewer can tell "always unbound" from
"reads another binding".

File set: git ls-files '*.py' minus inv_*, res_*, docs/ (as
tests/test_pa0027_lint.py), plus this directory's own repro when --all.

Run: python docs/quality/evidence/CR-0018-candidates/sweep_except_name.py [rev]
With a git revision, the files are read from that revision (git show).
"""
import ast
import re
import subprocess
import sys

EXCLUDE = re.compile(r"^(inv_|res_|docs/)")
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _own_nodes(scope):
    """Nodes in `scope`'s own body, not descending into nested scopes."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, SCOPES) or isinstance(
                n, (ast.ListComp, ast.SetComp, ast.DictComp,
                    ast.GeneratorExp)):
            continue
        stack.extend(ast.iter_child_nodes(n))


def _inside(node, handler):
    return any(node is n for n in ast.walk(handler))


def check_scope(scope):
    nodes = list(_own_nodes(scope))
    handlers = [n for n in nodes if isinstance(n, ast.ExceptHandler)
                and n.name]
    out = []
    for name in sorted({h.name for h in handlers}):
        hs = [h for h in handlers if h.name == name]
        other_bind = any(
            (isinstance(n, ast.Name) and n.id == name
             and isinstance(n.ctx, (ast.Store, ast.Del)))
            or (isinstance(n, ast.arg) and n.arg == name)
            or (isinstance(n, ast.alias)
                and (n.asname or n.name.split(".")[0]) == name)
            for n in nodes)
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.Lambda)):
            a = scope.args
            other_bind = other_bind or any(
                p.arg == name for p in a.posonlyargs + a.args + a.kwonlyargs
                + [x for x in (a.vararg, a.kwarg) if x])
        for n in nodes:
            if (isinstance(n, ast.Name) and n.id == name
                    and isinstance(n.ctx, ast.Load)
                    and not any(_inside(n, h) for h in hs)):
                out.append((n.lineno, name, other_bind))
    return out


def scan(source):
    tree = ast.parse(source)
    found = []
    for scope in [tree] + [n for n in ast.walk(tree)
                           if isinstance(n, SCOPES)]:
        for ln, name, other in check_scope(scope):
            q = getattr(scope, "name", "<module>")
            found.append((ln, q, name, other))
    return sorted(found)


def files(rev=None):
    cmd = (["git", "ls-tree", "-r", "--name-only", rev] if rev
           else ["git", "ls-files", "*.py"])
    names = subprocess.run(cmd, capture_output=True, text=True,
                           check=True).stdout.split()
    return [f for f in names if f.endswith(".py") and not EXCLUDE.match(f)]


def read(path, rev=None):
    if rev:
        return subprocess.run(["git", "show", f"{rev}:{path}"],
                              capture_output=True, text=True,
                              check=True).stdout
    with open(path, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    rev = sys.argv[1] if len(sys.argv) > 1 else None
    fs = files(rev)
    n = 0
    for f in fs:
        try:
            hits = scan(read(f, rev))
        except SyntaxError as e:
            print(f"{f}: SyntaxError {e}")
            continue
        for ln, q, name, other in hits:
            n += 1
            print(f"{f}:{ln} {q}: reads except-target '{name}' outside its "
                  f"clause ({'other binding exists' if other else 'NO other binding -> always unbound'})")
    print(f"{len(fs)} files scanned at {rev or 'working tree'}; {n} hit(s)")
