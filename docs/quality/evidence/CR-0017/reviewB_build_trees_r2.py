"""Round 2: derive wrong trees from W2_correct by editing only N-side content."""
import os, shutil
import pandas as pd
T = "/tmp/claude-1000/-home-ec2-user-grouse2/491a150a-d26d-456d-b9b4-036cd4a6478b/scratchpad/reviewB/trees"
LIVE = "/home/ec2-user/grouse2"
def clone(name):
    d = os.path.join(T, name)
    if os.path.exists(d): shutil.rmtree(d)
    shutil.copytree(os.path.join(T, "W2_correct"), d)
    return d
def rewrite(d, r, fn):
    p = f"{d}/data/negatives/negatives_{r}.csv"
    ls = open(p).read().splitlines()
    hdr, body = ls[0], fn(ls[0], ls[1:])
    open(p, "w").write("\n".join([hdr] + body) + "\n")
    cols = hdr.split(",")
    si = cols.index("split")
    for s in ("train", "val"):
        # naive split parse is fine: no quoted commas in these files? check below
        part = [l for l in body if l.split(",")[si] == s]
        open(f"{d}/data/negatives/{s}_negatives_{r}.csv", "w").write("\n".join([hdr] + part) + "\n")
old = {r: set(open(f"{LIVE}/data/negatives/negatives_{r}.csv").read().splitlines()[1:]) for r in ("ME","NH","VT")}
# W6: every ADDED row gets label=1 and a bogus obs_date / coord_uncertainty_m (N-only columns)
d = clone("W6_added_rows_label1")
for r in ("ME","NH","VT"):
    def f(hdr, body, r=r):
        c = hdr.split(","); li, oi, ui = c.index("label"), c.index("obs_date"), c.index("coord_uncertainty_m")
        out = []
        for l in body:
            if l not in old[r]:
                v = l.split(","); v[li] = "1"; v[oi] = "1900-01-01"; v[ui] = "99999.0"; l = ",".join(v)
            out.append(l)
        return out
    rewrite(d, r, f)
# W7: combined N files in reverse (non-canonical) order; parts consistent
d = clone("W7_reordered")
for r in ("ME","NH","VT"):
    rewrite(d, r, lambda h, b: b[::-1])
print("built W6, W7")
