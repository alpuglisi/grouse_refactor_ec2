"""
organize_project.py

One-shot project reorganizer. Run from the working directory that holds
all scripts and data files (e.g. right after copying the project to a
new machine).

WHAT IT DOES
  1. Creates a structured data/ tree:
       data/sightings/   raw grouse CSVs ({st}_sightings_{year}.csv)
       data/landfire/    the whole landfire_data/ tree (rasters,
                         attribute_tables/, *_meta/ sidecars)
       data/pipeline/    analyze/prepare outputs (evaluated_sightings,
                         envelope_metrics, nonveg_flagged, thinned/
                         train/val positives, block_assignments,
                         bin_tuning)
       data/negatives/   gbif/ebird candidate downloads + generated
                         negatives (train/val)
       data/maps/        diagnostic map PNGs + map_data/ boundary cache
       data/models/      .pth checkpoints
  2. Moves existing files into that tree (category by category).
  3. Rewrites path references in every *.py and *.sh in the working
     directory to point at the new locations. Replacements are
     QUOTE-ANCHORED (only string literals beginning with the old path
     are touched), applied longest-prefix-first, which also makes the
     rewrite IDEMPOTENT - running this script twice is safe.
  4. Backs up every script it modifies to scripts_backup/ first.

USAGE
    python organize_project.py --dry-run    # show every move/rewrite
    python organize_project.py              # do it

Python scripts stay in the working directory, as requested.
"""
import os
import re
import glob
import shutil
import argparse

# ==========================================
# Target layout
# ==========================================
DIRS = [
    "data/sightings",
    "data/pipeline",
    "data/negatives",
    "data/maps",
    "data/models",
    "scripts_backup",
    # data/landfire and data/maps/map_data are deliberately NOT
    # pre-created: they're produced by whole-directory moves below, and
    # pre-creating them made the move logic see "destination exists" and
    # skip the move entirely (leaving the rasters behind).
]

# ==========================================
# File moves: (matcher, destination). Matchers are checked against
# working-directory entries only (nothing already under data/ is
# touched). Order matters: specific prefixes before general ones, and
# evaluated_* must be claimed before the raw-sightings pattern runs.
# ==========================================
RAW_SIGHTINGS_RE = re.compile(r"^[a-z]{2}_sightings_\d{4}\.csv$")

MOVE_RULES = [
    # (kind, pattern, dest)  kind: 'glob' | 'regex' | 'dir'
    ("glob",  "evaluated_sightings_*.csv",  "data/pipeline"),
    ("glob",  "envelope_metrics_*.csv",     "data/pipeline"),
    ("glob",  "nonveg_flagged_*.csv",       "data/pipeline"),
    ("glob",  "thinned_positives_*.csv",    "data/pipeline"),
    ("glob",  "train_positives_*.csv",      "data/pipeline"),
    ("glob",  "val_positives_*.csv",        "data/pipeline"),
    ("glob",  "block_assignments_*.csv",    "data/pipeline"),
    ("glob",  "bin_tuning_*.csv",           "data/pipeline"),
    ("regex", RAW_SIGHTINGS_RE,             "data/sightings"),
    ("glob",  "gbif_negatives_*.csv",       "data/negatives"),
    ("glob",  "ebird_negatives_*.csv",      "data/negatives"),
    ("glob",  "ebird_checkpoint.json",      "data/negatives"),
    ("glob",  "gbif_checkpoint.json",       "data/negatives"),
    ("glob",  "train_negatives_*.csv",      "data/negatives"),
    ("glob",  "val_negatives_*.csv",        "data/negatives"),
    ("glob",  "negatives_*.csv",            "data/negatives"),
    ("glob",  "grouse_diagnostic_map_*.png", "data/maps"),
    ("glob",  "*.pth",                      "data/models"),
    ("dir",   "landfire_data",              "data/landfire"),
    ("dir",   "map_data",                   "data/maps/map_data"),
]

# ==========================================
# Reference rewrites applied to *.py / *.sh. Each entry is applied for
# both quote characters (" and '); anchoring on the quote means only
# string literals that BEGIN with the old path are rewritten - log
# messages that merely mention a filename mid-sentence are untouched,
# and a second run finds nothing left to rewrite (idempotent).
# Longest-prefix-first so e.g. train_negatives_ is claimed before
# negatives_.
# ==========================================
REWRITES = [
    ("./landfire_data",            "data/landfire"),
    ("landfire_data",              "data/landfire"),
    ("evaluated_sightings_",       "data/pipeline/evaluated_sightings_"),
    ("envelope_metrics_",          "data/pipeline/envelope_metrics_"),
    ("nonveg_flagged_",            "data/pipeline/nonveg_flagged_"),
    ("thinned_positives_",         "data/pipeline/thinned_positives_"),
    ("train_positives_",           "data/pipeline/train_positives_"),
    ("val_positives_",             "data/pipeline/val_positives_"),
    ("block_assignments_",         "data/pipeline/block_assignments_"),
    ("bin_tuning_",                "data/pipeline/bin_tuning_"),
    ("{state_lower}_sightings_",   "data/sightings/{state_lower}_sightings_"),
    ("*_sightings_*.csv",          "data/sightings/*_sightings_*.csv"),
    ("gbif_negatives_",            "data/negatives/gbif_negatives_"),
    ("ebird_negatives_",           "data/negatives/ebird_negatives_"),
    ("ebird_checkpoint.json",      "data/negatives/ebird_checkpoint.json"),
    ("gbif_checkpoint.json",       "data/negatives/gbif_checkpoint.json"),
    ("train_negatives_",           "data/negatives/train_negatives_"),
    ("val_negatives_",             "data/negatives/val_negatives_"),
    ("negatives_",                 "data/negatives/negatives_"),
    ("grouse_diagnostic_map_",     "data/maps/grouse_diagnostic_map_"),
    ("map_data",                   "data/maps/map_data"),
    ("grouse_single_best.pth",     "data/models/grouse_single_best.pth"),
    ("smoke_test_model",           "data/models/smoke_test_model"),
]

SELF = os.path.basename(__file__)


def build_replacements():
    """Expand REWRITES into concrete (old, new) literal pairs for both
    quote styles, longest old-string first."""
    pairs = []
    for old, new in REWRITES:
        for q in ('"', "'"):
            pairs.append((q + old, q + new))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def plan_moves():
    moves = []      # (src, dest_path)
    claimed = set()
    for kind, pattern, dest in MOVE_RULES:
        if kind == "dir":
            if os.path.isdir(pattern):
                moves.append((pattern, dest))
                claimed.add(pattern)
            continue
        if kind == "glob":
            names = [n for n in glob.glob(pattern)
                     if os.path.isfile(n) and n not in claimed]
        else:  # regex
            names = [n for n in os.listdir(".")
                     if os.path.isfile(n) and pattern.match(n)
                     and n not in claimed]
        for n in sorted(names):
            moves.append((n, os.path.join(dest, os.path.basename(n))))
            claimed.add(n)
    return moves


def rewrite_scripts(dry_run):
    pairs = build_replacements()
    targets = sorted(glob.glob("*.py") + glob.glob("*.sh"))
    total_files = 0
    for path in targets:
        if os.path.basename(path) == SELF:
            continue
        with open(path, encoding="utf-8") as f:
            src = f.read()
        out = src
        counts = {}
        for old, new in pairs:
            n = out.count(old)
            if n:
                out = out.replace(old, new)
                counts[old] = n
        if not counts:
            continue
        total_files += 1
        detail = ", ".join(f"{k} x{v}" for k, v in counts.items())
        if dry_run:
            print(f"  [would rewrite] {path}: {detail}")
        else:
            shutil.copy2(path, os.path.join("scripts_backup",
                                            os.path.basename(path)))
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"  [rewrote] {path}: {detail}")
    return total_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show every planned move and rewrite "
                             "without changing anything.")
    args = parser.parse_args()

    print("== 1. Directory tree ==")
    for d in DIRS:
        if args.dry_run:
            print(f"  [would create] {d}/")
        else:
            os.makedirs(d, exist_ok=True)
            print(f"  [ok] {d}/")

    print("\n== 2. Data file moves ==")
    moves = plan_moves()
    if not moves:
        print("  (nothing to move - already organized?)")
    for src, dest in moves:
        if args.dry_run:
            print(f"  [would move] {src} -> {dest}")
        else:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            if os.path.exists(dest):
                if os.path.isdir(dest) and not os.listdir(dest):
                    os.rmdir(dest)   # empty leftover (e.g. from an
                                     # earlier partial run) - replace it
                else:
                    print(f"  [skip] {src} -> {dest} (destination exists "
                         f"and is non-empty)")
                    continue
            shutil.move(src, dest)
            print(f"  [moved] {src} -> {dest}")

    print("\n== 3. Script reference rewrites ==")
    n = rewrite_scripts(args.dry_run)
    if n == 0:
        print("  (no references needed rewriting)")

    print("\nDone." + (" (dry run - nothing changed)" if args.dry_run else ""))
    if not args.dry_run:
        print("Backups of modified scripts: scripts_backup/")
        print("Verify with: python -m py_compile *.py, then run your "
             "normal pipeline commands from this directory as before.")


if __name__ == "__main__":
    main()
