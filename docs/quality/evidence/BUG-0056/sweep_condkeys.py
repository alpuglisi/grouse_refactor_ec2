"""PA-0030 sweep (BUG-0056 §8): string keys stored under a condition
(If/For/While/Try/except/IfExp/match branch, within the innermost
function), including keys stored through a loop variable bound over a
literal tuple (`for src, dst in (("a", "b"), ...): d[dst] = ...`), and
loaded by plain subscript anywhere in the swept files.

Prints, per conditionally stored key, the store sites and every plain
`X['key']` load site (repo-wide), each tagged:
  GUARDED         an enclosing if/while/IfExp test or boolean expression
                  mentions the key string;
  CO-CONDITIONAL  same function, and the key is stored there
                  unconditionally, or every condition enclosing some store
                  also encloses the load;
  UNGUARDED       anything else -> read in context and classify by hand.
Heuristic, not a proof: it matches keys by name, not by object, so most
UNGUARDED rows are a different dict/DataFrame that shares a key name.
Not covered: keys built at runtime (f-strings), `.update()`/`**` merges,
`setdefault`. The companion sweep_returns.py covers dict literals returned
with differing key sets.

Usage (repo root): python docs/quality/evidence/BUG-0056/sweep_condkeys.py
                   [FILELIST]   (default: `git ls-files '*.py'`)"""
import ast
import collections
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
COND = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
        ast.IfExp, ast.Match)
stores = collections.defaultdict(list)
loads = collections.defaultdict(list)
sinfo = collections.defaultdict(list)
uncond = collections.defaultdict(set)


def key_of(sub):
    s = sub.slice
    if isinstance(s, ast.Constant) and isinstance(s.value, str):
        return s.value
    return None


def loop_keys(sub, stack):
    """Variable key bound by an enclosing `for ... in <literal of str
    constants or tuples of them>` loop: return every constant it takes."""
    s = sub.slice
    if not isinstance(s, ast.Name):
        return []
    out = []
    for a in stack:
        if isinstance(a, (ast.For, ast.comprehension)) and isinstance(
                a.iter, (ast.Tuple, ast.List)):
            names = [n.id for n in ast.walk(a.target) if isinstance(n, ast.Name)]
            if s.id not in names:
                continue
            for elt in a.iter.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    out.append(elt.value)
                elif isinstance(elt, ast.Tuple) and isinstance(a.target, ast.Tuple):
                    pos = [i for i, n in enumerate(a.target.elts)
                           if isinstance(n, ast.Name) and n.id == s.id]
                    for i in pos:
                        if i < len(elt.elts) and isinstance(elt.elts[i], ast.Constant):
                            out.append(elt.elts[i].value)
    return [k for k in out if isinstance(k, str)]


def walk(node, stack, fname):
    for ch in ast.iter_child_nodes(node):
        if isinstance(ch, ast.Subscript) and isinstance(ch.ctx, ast.Store):
            for k in loop_keys(ch, stack):
                stores[k].append(f"{fname}:{ch.lineno}(loopvar)")
                fn = next((a for a in reversed(stack) if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))), None)
                sinfo[k].append((id(fn), {id(a) for a in stack if isinstance(a, COND)}))
        if isinstance(ch, ast.Subscript):
            k = key_of(ch)
            if k is not None:
                anc = []
                for a in reversed(stack):
                    if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.Module, ast.Lambda)):
                        break
                    anc.append(a)
                if isinstance(ch.ctx, ast.Store):
                    if any(isinstance(a, COND) for a in anc):
                        stores[k].append(f"{fname}:{ch.lineno}")
                        fn = next((a for a in reversed(stack) if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))), None)
                        sinfo[k].append((id(fn), {id(a) for a in anc if isinstance(a, COND)}))
                    else:
                        fn = next((a for a in reversed(stack) if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))), None)
                        uncond[k].add(id(fn))
                elif isinstance(ch.ctx, ast.Load):
                    guarded = False
                    for a in stack:
                        if (isinstance(a, (ast.If, ast.IfExp, ast.While))
                                and repr(k)[1:-1] in ast.unparse(a.test)):
                            guarded = True
                        if isinstance(a, ast.BoolOp) and k in ast.unparse(a):
                            guarded = True
                    fn = next((a for a in reversed(stack) if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))), None)
                    loads[k].append((f"{fname}:{ch.lineno}", guarded,
                                     ast.unparse(ch.value), id(fn), {id(a) for a in stack}))
        walk(ch, stack + [ch], fname)


for f in files:
    try:
        tree = ast.parse(open(f).read(), f)
    except SyntaxError as e:
        print("SYNTAXERR", f, e)
        continue
    walk(tree, [tree], f)
def cocond(k, l):
    """True if, within the load's function, the key is stored
    unconditionally, or some store's conditions all enclose the load."""
    if l[3] in uncond[k]:
        return True
    return any(f == l[3] and conds <= l[4] for f, conds in sinfo[k])


n = 0
for k in sorted(stores):
    loads[k] = [l[:3] + (l[3], l[4], cocond(k, l)) for l in loads.get(k, [])]
    un = [l for l in loads[k] if not l[1] and not l[5]]
    if not un:
        continue
    n += 1
    print(f"KEY {k!r}: cond-stored at {', '.join(stores[k][:8])}"
          f"{' ...(+%d)' % (len(stores[k]) - 8) if len(stores[k]) > 8 else ''}")
    for site, g, obj, _f, _a, cc in loads[k]:
        print(f"    load {site} {obj}[{k!r}] "
              f"{'GUARDED' if g else 'CO-CONDITIONAL' if cc else 'UNGUARDED'}")
print("keys with unguarded loads:", n, "| files swept:", len(files))
