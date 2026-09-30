"""Build a scratch data tree: copied CSV/JSON, symlinked rasters and county zip.
Usage: python mk_scratch.py <dest>"""
import glob
import os
import shutil
import sys

M = "/home/ec2-user/grouse2/data"
S = sys.argv[1]
assert S.startswith("/tmp/claude-1000/"), S
if os.path.exists(S):
    shutil.rmtree(S)
for d in ("pipeline", "negatives", "sightings", "landfire", "roads"):
    os.makedirs(os.path.join(S, "data", d))
for d in ("pipeline", "negatives", "sightings"):
    for f in glob.glob(os.path.join(M, d, "*")):
        if os.path.isfile(f) and f.endswith((".csv", ".json")):
            shutil.copy2(f, os.path.join(S, "data", d))
for f in os.listdir(os.path.join(M, "landfire")):
    os.symlink(os.path.join(M, "landfire", f), os.path.join(S, "data", "landfire", f))
os.symlink(os.path.join(M, "roads", "tl_2023_us_county.zip"),
           os.path.join(S, "data", "roads", "tl_2023_us_county.zip"))
bad = []
for d in ("pipeline", "negatives", "sightings"):
    p = os.path.join(S, "data", d)
    if os.path.islink(p):
        bad.append(p)
    for f in os.listdir(p):
        if os.path.islink(os.path.join(p, f)):
            bad.append(f)
for d in ("", "data"):
    if os.path.islink(os.path.join(S, d)):
        bad.append(d)
assert not bad, bad
print("scratch tree", S, "ok; output dirs hold no symlinks;",
      len(os.listdir(os.path.join(S, "data", "landfire"))), "raster links")
