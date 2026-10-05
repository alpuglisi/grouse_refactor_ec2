"""check_split_unchanged.py - CR-0035 gate 4.3: the split files are
byte-identical after the Earth Engine layers are re-downloaded and the
split pipeline re-run.

Compares the `outputs` digests of a saved (pre-repair) split_manifest.json
with (a) the current split_manifest.json's and (b) sha256 of the files on
disk, over acceptance_split.digested_paths (the 20 digested artifacts).
Exit 1 on any difference, missing artifact or missing digest. Read-only.

Usage (repository root):
    python check_split_unchanged.py --old data_before_bug0094/split_manifest.json
"""
import argparse
import json
import os
import sys

import acceptance_split as acc


def manifest_outputs(path, sections):
    with open(path, encoding="utf-8") as f:
        m = json.load(f)
    out = {}
    for sec in sections:
        out.update((m.get(sec) or {}).get("outputs") or {})
    return out


def compare(old, new, disk, paths):
    """old/new: {rel: sha256} from the manifests; disk: {rel: sha256 or
    None}. Returns a list of problems (empty = identical)."""
    problems = []
    for rel in paths:
        o, n, d = old.get(rel), new.get(rel), disk.get(rel)
        if o is None:
            problems.append(f"{rel}: no digest in the old manifest")
        elif d is None:
            problems.append(f"{rel}: missing on disk")
        elif d != o:
            problems.append(f"{rel}: file differs from the old manifest")
        if n is not None and o is not None and n != o:
            problems.append(f"{rel}: new manifest digest differs from the old")
        if n is None:
            problems.append(f"{rel}: no digest in the new manifest")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--old", required=True, help="pre-repair split_manifest.json")
    ap.add_argument("--root", default=acc.REPO_ROOT)
    args = ap.parse_args()
    cfg = acc.load_config()
    sections = cfg["columns"]["split_manifest_sections"]
    paths = acc.digested_paths(cfg)
    old = manifest_outputs(args.old, sections)
    new = manifest_outputs(os.path.join(args.root, acc.rpath(cfg, "split_manifest")),
                           sections)
    disk = {}
    for rel in paths:
        full = os.path.join(args.root, rel)
        disk[rel] = acc.sha256_file(full) if os.path.exists(full) else None
    problems = compare(old, new, disk, paths)
    print(f"{len(paths)} digested split artifacts compared")
    for p in problems:
        print(f"   {p}")
    print(f"Gate (split byte-identical): {'PASS' if not problems else 'FAIL'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
