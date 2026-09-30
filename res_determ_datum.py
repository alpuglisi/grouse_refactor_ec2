"""res_determ_datum.py -- quantify the datum/PROJ-version risk concretely, and
check the remaining environment-dependence suspects.  Read-only.
"""
import hashlib, os, subprocess, sys
import numpy as np, pandas as pd, pyproj
from pyproj import Transformer

BLOCK = 3000.0; ORIGIN = (0.0, 0.0)
REGIONS = ("ME", "NH", "VT")

fr = []
for r in REGIONS:
    d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    fr.append(d[d["state"] == r])
p = pd.concat(fr, ignore_index=True)
p = p[~p["nonveg_landcover"].astype(bool)].drop_duplicates(
    subset=["longitude", "latitude", "year"]).reset_index(drop=True)
lon, lat = p["longitude"].values, p["latitude"].values

tf = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
X, Y = tf.transform(lon, lat)

print("=" * 78)
print("D1  what the currently-selected operation actually does about the datum")
print("=" * 78)
print("  chosen:", tf.description)
print("  accuracy (m):", tf.accuracy)
# EPSG:4269 is NAD83 geographic; 4326 -> 4269 with only built-in data:
t2 = Transformer.from_crs("EPSG:4326", "EPSG:4269", always_xy=True)
lo2, la2 = t2.transform(lon, lat)
print(f"  4326->4269 offered here: {t2.description!r}, accuracy {t2.accuracy} m,"
      f" max |dlon| {np.abs(lo2-lon).max():.3e} deg -> it is a NULL transform")

print("\n" + "=" * 78)
print("D2  magnitude of a real datum-realisation change (ITRF2014 -> NAD83(2011),")
print("    EPSG:8365 Helmert) -- what PROJ would apply if a higher-accuracy")
print("    operation became available (grids installed, or network enabled)")
print("=" * 78)
helmert = ("+proj=pipeline "
           "+step +proj=unitconvert +xy_in=deg +xy_out=rad "
           "+step +proj=cart +ellps=GRS80 "
           "+step +proj=helmert +x=1.0053 +y=-1.90921 +z=-0.54157 "
           "+rx=-0.02678138 +ry=0.00042027 +rz=-0.01093206 +s=0.00036891 "
           "+convention=coordinate_frame "
           "+step +inv +proj=cart +ellps=GRS80 "
           "+step +proj=unitconvert +xy_in=rad +xy_out=deg")
try:
    th = Transformer.from_pipeline(helmert)
    lo3, la3 = th.transform(lon, lat)
    X3, Y3 = tf.transform(lo3, la3)
    d = np.hypot(X3 - X, Y3 - Y)
    print(f"  planar displacement: min {d.min():.4f} m  median {np.median(d):.4f} m"
          f"  max {d.max():.4f} m")
except Exception as exc:
    print("  pipeline failed:", exc)

print("\n" + "=" * 78)
print("D3  how many records a displacement of magnitude s flips to another block")
print("=" * 78)
def edge(v, o):
    m = np.mod(v - o, BLOCK)
    return np.minimum(m, BLOCK - m)
e = np.minimum(edge(X, ORIGIN[0]), edge(Y, ORIGIN[1]))
for s in (0.1, 0.33, 0.5, 1.0, 1.5, 2.0, 3.0):
    print(f"  |displacement| = {s:4.2f} m -> at most {int((e < s).sum()):4d} of "
          f"{len(p):,} records can change block "
          f"({100*(e < s).mean():.4f}%)")

print("\n" + "=" * 78)
print("D4  PYTHONHASHSEED: does any output depend on str/set hashing?")
print("=" * 78)
code = (
    "import hashlib,os\n"
    "print('seed',os.environ.get('PYTHONHASHSEED'))\n"
    "s={'12_34','56_78','90_12','3_4','5_6'}\n"
    "print('set iteration order:',list(s))\n"
    "print('md5 of block key:',hashlib.md5('42:12_34'.encode()).hexdigest()[:12])\n"
    "print('blake2b of coord :',hashlib.blake2b(b'42:-69.55151,45.97633',"
    "digest_size=16).hexdigest()[:12])\n"
    "print('builtin hash     :',hash('12_34'))\n")
for seed in ("0", "1", "12345"):
    env = dict(os.environ, PYTHONHASHSEED=seed)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, env=env).stdout
    print("  " + out.replace("\n", "\n  ").rstrip())

print("\n" + "=" * 78)
print("D5  dict-keyed lookups in the negative path")
print("=" * 78)
for r in REGIONS:
    f = f"data/pipeline/envelope_metrics_{r}.csv"
    if os.path.exists(f):
        m = pd.read_csv(f)
        print(f"  {f}: {len(m):,} rows, {m['Envelope'].nunique():,} unique "
              f"Envelope -> dict(last-wins) collisions: "
              f"{len(m) - m['Envelope'].nunique()}")
    else:
        print(f"  {f} missing")
for r in REGIONS:
    f = f"data/pipeline/block_assignments_{r}.csv"
    if os.path.exists(f):
        b = pd.read_csv(f)
        print(f"  {f}: {len(b):,} rows, {b['block_id'].nunique():,} unique "
              f"block_id -> collisions {len(b) - b['block_id'].nunique()}, "
              f"val share {100*(b['split']=='val').mean():.2f}%")

print("\n" + "=" * 78)
print("D6  numpy Generator vs RandomState stream policy")
print("=" * 78)
print("  numpy", np.__version__, "| pandas", pd.__version__,
      "| scipy", __import__("scipy").__version__,
      "| pyproj", pyproj.__version__, "| PROJ", pyproj.proj_version_str)
print("  np.random.default_rng(42).permutation(10) =",
      np.random.default_rng(42).permutation(10))
print("  np.random.RandomState(42).permutation(10) =",
      np.random.RandomState(42).permutation(10))
print("  default_rng bit generator:", np.random.default_rng(42).bit_generator.__class__.__name__)
