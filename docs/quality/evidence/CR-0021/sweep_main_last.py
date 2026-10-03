"""PA-0035 sweep (BUG-0077): every git-tracked .py whose top level has a
statement after its `if __name__ == "__main__":` block. Such statements
do not run when the file is executed as a script (a test module run as
`python tests/x.py` silently skips every test defined below the block).
Run from the repository root; 0 hits required."""
import ast, subprocess, sys
files = subprocess.run(["git","ls-files","*.py"],capture_output=True,text=True).stdout.split()
hits=[]
for f in files:
    try: tree=ast.parse(open(f).read())
    except Exception as e: print("PARSE", f, type(e).__name__); continue
    body=tree.body
    for i,n in enumerate(body):
        if isinstance(n,ast.If) and "__name__" in ast.unparse(n.test) and "__main__" in ast.unparse(n.test):
            rest=[m for m in body[i+1:]]
            if rest: hits.append((f,n.lineno,[ (type(m).__name__, m.lineno) for m in rest][:3]))
print(len(files),"files"); [print(h) for h in hits]
