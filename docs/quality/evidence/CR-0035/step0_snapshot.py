"""CR-0035 step 0: snapshot, checksum, 'before' worktree, inventory; and
(separately, with --clear) delete the in-scope files.

Run from the repository root on the EC2 host:
    python docs/quality/evidence/CR-0035/step0_snapshot.py          # 0.1-0.3
    python docs/quality/evidence/CR-0035/step0_snapshot.py --verify # re-check
    python docs/quality/evidence/CR-0035/step0_snapshot.py --clear  # 0.4

0.1  cp -al data data_before_bug0094 (hard links: no extra space; sizes and
     mtimes preserved) and snapshot.sha256 (sha256 of every snapshot file).
0.2  git worktree add ../grouse2_before HEAD, with data -> the snapshot.
0.3  inventory_before.txt: per region, the years on disk of every in-scope
     feature, and the raw TreeMap files, with their tags.
0.4  (--clear) delete the in-scope files from data/landfire and
     data/treemap_raw; tsd is NOT deleted (its generator always rewrites).
     Refuses unless the snapshot and snapshot.sha256 exist and verify.
Evidence is written next to this script.
"""
import argparse
import glob
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = "data_before_bug0094"
SHA = os.path.join(HERE, "snapshot.sha256")
INV = os.path.join(HERE, "inventory_before.txt")
CLEARED = ("nlcd", "tcc", "balive", "tpa_live", "qmd", "carbon_dwn")
INVENTORIED = CLEARED + ("tsd",)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_files():
    out = []
    for root, _, files in os.walk(SNAP):
        out += [os.path.join(root, f) for f in files]
    return sorted(out)


def write_sha():
    files = snapshot_files()
    with open(SHA, "w") as f:
        for i, p in enumerate(files, 1):
            f.write(f"{sha256(p)}  {p}\n")
            if i % 200 == 0:
                print(f"   hashed {i}/{len(files)}", flush=True)
    print(f"0.1 snapshot.sha256: {len(files)} files")


def verify_sha():
    bad = 0
    with open(SHA) as f:
        for line in f:
            h, p = line.rstrip("\n").split("  ", 1)
            if not os.path.exists(p) or sha256(p) != h:
                print(f"   CHANGED OR MISSING: {p}")
                bad += 1
    print(f"snapshot.sha256 verify: {'OK' if not bad else f'{bad} FAILED'}")
    return bad == 0


def inventory():
    sys.path.insert(0, os.getcwd())
    import rasterio
    from grouse_data import GrouseData
    from regions import REGIONS
    data = GrouseData()
    lines = []
    for R in REGIONS:
        rd = data[R]
        for f in INVENTORIED:
            lines.append(f"{R} {f} {' '.join(map(str, rd.raster_years(f)))}")
    for p in sorted(glob.glob("data/treemap_raw/TreeMap*.tif")):
        with rasterio.open(p) as s:
            lines.append(f"raw {os.path.basename(p)} crs={s.crs.to_epsg()} "
                         f"origin=({s.transform.c},{s.transform.f}) "
                         f"tags={dict(s.tags())}")
    for R in REGIONS:
        for f in ("nlcd", "tcc"):
            for p in sorted(glob.glob(f"data/landfire/{R}_*_{f}.tif")):
                with rasterio.open(p) as s:
                    lines.append(f"tags {os.path.basename(p)} {dict(s.tags())}")
    with open(INV, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"0.3 inventory_before.txt:\n   " + "\n   ".join(
        l for l in lines if not l.startswith(("raw ", "tags "))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--clear", action="store_true")
    args = ap.parse_args()
    if not os.path.isdir("data") or not os.path.isfile("train.py"):
        sys.exit("Run from the repository root (data/ and train.py here).")
    if args.verify:
        sys.exit(0 if verify_sha() else 1)
    if args.clear:
        if not (os.path.isdir(SNAP) and os.path.isfile(SHA) and
                os.path.isfile(INV)):
            sys.exit("No snapshot/checksums/inventory - run step 0 first.")
        if not verify_sha():
            sys.exit("Snapshot does not verify - not clearing.")
        gone = []
        for f in CLEARED:
            gone += glob.glob(f"data/landfire/*_{f}.tif")
        gone += glob.glob("data/treemap_raw/TreeMap*.tif")
        for p in gone:
            os.remove(p)
        print(f"0.4 deleted {len(gone)} in-scope files (kept in {SNAP}/)")
        return
    if os.path.exists(SNAP):
        sys.exit(f"{SNAP} already exists - step 0 has run; use --verify.")
    print("0.1 cp -al data", SNAP)
    subprocess.run(["cp", "-al", "data", SNAP], check=True)
    write_sha()
    before = os.path.join(os.path.dirname(os.getcwd()), "grouse2_before")
    print(f"0.2 git worktree add {before} HEAD; data -> {SNAP}")
    subprocess.run(["git", "worktree", "add", "--detach", before, "HEAD"],
                   check=True)
    link = os.path.join(before, "data")
    if os.path.lexists(link):
        sys.exit(f"{link} exists in the new worktree - remove it and link "
                 f"it to {os.path.abspath(SNAP)} by hand")
    os.symlink(os.path.abspath(SNAP), link)
    inventory()
    print("\nStep 0.1-0.3 done. Next: 0.4 is a separate, deliberate run:\n"
          "   python docs/quality/evidence/CR-0035/step0_snapshot.py --clear")


if __name__ == "__main__":
    main()
