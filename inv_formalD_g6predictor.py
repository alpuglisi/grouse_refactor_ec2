"""FORMAL D / CR-0008 G6 attack: does the FULL rasterio profile dict carry
PREDICTOR?  v5 widened G6 from six fields to "the full rasterio profile dict"
specifically to stop a naive rewrite dropping `compress` and blowing the disk.
Test: perform the CORRECT repair (outside-NLCD -> -9999) on real ME files and
write it two ways -- (A) rasterio.open(..., 'w', **src.profile), which is
exactly what "the full profile dict" means, and (B) the same plus predictor=2,
which is what the files on disk actually carry.  Compare sizes.
READ-ONLY w.r.t. the project: writes only into a scratch dir."""
import os, sys, numpy as np, rasterio
OUT = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad/g6"
FILES = ["data/landfire/ME_2025_balive.tif", "data/landfire/ME_2023_tcc.tif",
         "data/landfire/ME_2025_tsd.tif"]
with rasterio.open("data/landfire/ME_2025_nlcd.tif") as s:
    valid = s.read(1) != -9999
print(f"mask inside={int(valid.sum()):,} outside={int((~valid).sum()):,}\n")
tot = {'orig':0,'A':0,'B':0}
for p in FILES:
    with rasterio.open(p) as s:
        a = s.read(1); prof = dict(s.profile)
        struct = s.tags(ns='IMAGE_STRUCTURE')
    rep = np.where(valid, a, np.int16(-9999)).astype(np.int16)
    print(f"{os.path.basename(p)}  on-disk IMAGE_STRUCTURE={struct}")
    print(f"   rasterio profile keys: {sorted(prof)}")
    print(f"   'predictor' in profile? {'predictor' in prof}")
    res = {}
    for tag, extra in (('A', {}), ('B', {'predictor': 2})):
        q = os.path.join(OUT, f"{tag}_{os.path.basename(p)}")
        with rasterio.open(q, 'w', **prof, **extra) as d:
            d.write(rep, 1)
        res[tag] = os.path.getsize(q)
        with rasterio.open(q) as d:
            assert np.array_equal(d.read(1), rep)
        os.remove(q)
    o = os.path.getsize(p)
    tot['orig'] += o; tot['A'] += res['A']; tot['B'] += res['B']
    print(f"   original (predictor=2, pre-repair)      {o/2**20:9.1f} MiB")
    print(f"   A: **src.profile  (NO predictor)        {res['A']/2**20:9.1f} MiB   x{res['A']/o:.2f} of original")
    print(f"   B: **src.profile + predictor=2          {res['B']/2**20:9.1f} MiB   x{res['B']/o:.2f} of original")
    print(f"   A/B inflation from the dropped predictor: x{res['A']/res['B']:.2f}\n")
    del a, rep
print(f"TOTAL over {len(FILES)} files: orig {tot['orig']/2**20:.1f} MiB  "
      f"A {tot['A']/2**20:.1f} MiB (x{tot['A']/tot['orig']:.2f})  "
      f"B {tot['B']/2**20:.1f} MiB (x{tot['B']/tot['orig']:.2f})")
