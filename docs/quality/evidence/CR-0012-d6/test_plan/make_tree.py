"""CR-0012 deliverable 6 test plan: build a scratch data tree.

usage: python make_tree.py DEST [--permute SEED] [--from-backup DIR]

DEST/data/ gets COPIES of the pipeline's input CSVs (optionally with rows
randomly permuted), SYMLINKS to every raster file under data/landfire
(directories recreated as real dirs) and a symlink to the county zip.
Nothing under the real data/ is written.
"""
import os
import shutil
import sys

import numpy as np
import pandas as pd

REAL = "/home/ec2-user/grouse2/data"
REGIONS = ("ME", "NH", "VT")
INPUT_CSVS = ([f"pipeline/evaluated_sightings_{r}.csv" for r in REGIONS]
              + [f"pipeline/envelope_metrics_{r}.csv" for r in REGIONS]
              + [f"negatives/gbif_negatives_{r}.csv" for r in REGIONS])


def copy_csv(src, dst, seed):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if seed is None:
        shutil.copyfile(src, dst)
        return
    # Permute rows only; keep every field's text exactly as on disk
    # (read as str so no float is re-rendered).
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    rng = np.random.default_rng(seed)
    df = df.iloc[rng.permutation(len(df))]
    with open(src, "rb") as f:
        crlf = b"\r\n" in f.read(65536)
    df.to_csv(dst, index=False, lineterminator="\r\n" if crlf else "\n")


def main():
    dest = os.path.abspath(sys.argv[1])
    seed = None
    backup = None
    if "--permute" in sys.argv:
        seed = int(sys.argv[sys.argv.index("--permute") + 1])
    if "--from-backup" in sys.argv:
        backup = sys.argv[sys.argv.index("--from-backup") + 1]
    if os.path.exists(dest):
        raise SystemExit(f"{dest} exists")
    d = os.path.join(dest, "data")
    if backup:
        for sub in ("pipeline", "negatives"):
            shutil.copytree(os.path.join(backup, sub), os.path.join(d, sub))
    else:
        for i, rel in enumerate(INPUT_CSVS):
            copy_csv(os.path.join(REAL, rel), os.path.join(d, rel),
                     None if seed is None else seed + i)
    # attribute tables: copied (crosswalk is a CSV input); permuted too
    at = "landfire/attribute_tables"
    for f in sorted(os.listdir(os.path.join(REAL, at))):
        copy_csv(os.path.join(REAL, at, f), os.path.join(d, at, f),
                 None if seed is None else seed + 100 + len(f))
    # rasters and sidecars: symlinked file by file
    for dirpath, dirnames, filenames in os.walk(os.path.join(REAL, "landfire")):
        rel = os.path.relpath(dirpath, REAL)
        if rel.startswith(at):
            continue
        os.makedirs(os.path.join(d, rel), exist_ok=True)
        for f in filenames:
            os.symlink(os.path.join(dirpath, f), os.path.join(d, rel, f))
    os.makedirs(os.path.join(d, "roads"), exist_ok=True)
    os.symlink(os.path.join(REAL, "roads", "tl_2023_us_county.zip"),
               os.path.join(d, "roads", "tl_2023_us_county.zip"))
    os.makedirs(os.path.join(d, "models"), exist_ok=True)
    print(f"built {dest} (permute={seed}, backup={backup})")


if __name__ == "__main__":
    main()
