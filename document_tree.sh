#!/usr/bin/env bash
#
# document_tree.sh
#
# Writes a full inventory of the project directory - EVERY file, with
# size and date - to a markdown file, and stages it in git so it can be
# pushed and reviewed.
#
# WHY THIS EXISTS
# ---------------
# The repo and the live working directory are not the same place. Data
# files (rasters, checkpoints, caches) are gitignored and never reach a
# clone, so anyone reviewing this project from the repo alone cannot see
# which features exist for which years - and that is exactly what every
# question about training-record retention depends on, because the
# year-gap filter (train.py) keeps a record only if EVERY feature has a
# raster within tolerance of the sighting year.
#
# So this does more than run `tree`: it builds a feature x year coverage
# matrix per region from the raster filenames, which is the single most
# useful thing to read before deciding whether a feature is missing a
# vintage.
#
# Contents are never read - only names, sizes and timestamps - so this
# cannot leak the contents of a credentials file into the repo. It does
# list filenames, so a file whose NAME is sensitive would be recorded.
#
# Usage:
#     ./document_tree.sh                      # writes PROJECT_TREE.md
#     ./document_tree.sh -o inventory.md      # different output name
#     ./document_tree.sh -r ~/grouse2         # document another directory
#     ./document_tree.sh -m 100               # collapse dirs over 100 files
#     ./document_tree.sh -a                   # include __pycache__ etc.
#     ./document_tree.sh -n                   # don't stage in git
#
set -euo pipefail

OUT="PROJECT_TREE.md"
ROOT=""
MAX_PER_DIR=500
INCLUDE_NOISE=0
DO_GIT_ADD=1

usage() { sed -n '3,30p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while getopts ":o:r:m:anh" opt; do
  case "$opt" in
    o) OUT="$OPTARG" ;;
    r) ROOT="$OPTARG" ;;
    m) MAX_PER_DIR="$OPTARG" ;;
    a) INCLUDE_NOISE=1 ;;
    n) DO_GIT_ADD=0 ;;
    h) usage 0 ;;
    \?) echo "unknown option -$OPTARG" >&2; usage 1 ;;
    :)  echo "option -$OPTARG needs a value" >&2; usage 1 ;;
  esac
done

# Document the directory we were pointed at (or the current one), but
# STAGE into whichever git repo contains the OUTPUT FILE. Those are
# legitimately different whenever the live working directory is not the
# clone you push from - which is the normal case here: the rasters live
# on the training box and the repo is a separate checkout. So:
#     ./document_tree.sh -r ~/grouse2 -o ~/repo/PROJECT_TREE.md
# inventories the box and stages the result in the repo.
[ -n "$ROOT" ] || ROOT="$(pwd)"
cd "$ROOT"
ROOT="$(pwd -P)"

case "$OUT" in /*) OUT_ABS="$OUT" ;; *) OUT_ABS="$ROOT/$OUT" ;; esac
OUT_DIR="$(cd "$(dirname "$OUT_ABS")" 2>/dev/null && pwd -P)" || {
  echo "Output directory does not exist: $(dirname "$OUT_ABS")" >&2; exit 1; }
OUT_ABS="$OUT_DIR/$(basename "$OUT_ABS")"

command -v find >/dev/null || { echo "find not found" >&2; exit 1; }
if ! find . -maxdepth 0 -printf '' 2>/dev/null; then
  echo "This script needs GNU find (for -printf). On macOS: brew install findutils" >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LIST="$TMP/files.tsv"

# One pass over the tree: relative path, bytes, mtime. Pruned rather
# than filtered so we never descend into .git at all.
PRUNE=( -path ./.git -o -path '*/.git' )
if [ "$INCLUDE_NOISE" -eq 0 ]; then
  PRUNE+=( -o -name __pycache__ -o -name .ipynb_checkpoints
           -o -name .mypy_cache -o -name .pytest_cache )
fi
find . \( "${PRUNE[@]}" \) -prune -o -type f -printf '%P\t%s\t%TY-%Tm-%Td\n' \
  2>/dev/null | LC_ALL=C sort > "$LIST"

TOTAL_FILES=$(wc -l < "$LIST" | tr -d ' ')
TOTAL_BYTES=$(awk -F'\t' '{s+=$2} END{printf "%.0f", s+0}' "$LIST")

human() {
  awk -v b="$1" 'BEGIN{
    split("B KB MB GB TB PB", u, " "); i=1
    while (b >= 1024 && i < 6) { b /= 1024; i++ }
    printf (i==1 ? "%d %s" : "%.1f %s"), b, u[i]
  }'
}

# Every git call here is guarded: a repository with no commits yet has
# no HEAD to resolve, and under `set -e` an unguarded rev-parse aborts
# the whole script before anything is written.
GIT_DESC="not a git repository"
if git rev-parse --git-dir >/dev/null 2>&1; then
  # symbolic-ref, not rev-parse --abbrev-ref: on an unborn branch the
  # latter prints "HEAD" AND exits non-zero, so a `||` fallback ends up
  # concatenated onto its output instead of replacing it.
  BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null \
           || git rev-parse --abbrev-ref HEAD 2>/dev/null \
           || echo "?")
  if COMMIT=$(git rev-parse --short HEAD 2>/dev/null); then
    GIT_DESC="branch \`$BRANCH\` at \`$COMMIT\`"
  else
    GIT_DESC="branch \`$BRANCH\` (no commits yet)"
  fi
  DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  [ "${DIRTY:-0}" -gt 0 ] && GIT_DESC="$GIT_DESC, $DIRTY uncommitted change(s)"
fi

{
  echo "# Project inventory"
  echo
  echo "Generated \`$(date -u '+%Y-%m-%d %H:%M UTC')\` on \`$(hostname)\`"
  echo
  echo "- Directory: \`$ROOT\`"
  echo "- Git: $GIT_DESC"
  echo "- $TOTAL_FILES files, $(human "$TOTAL_BYTES") total"
  [ "$INCLUDE_NOISE" -eq 0 ] && echo "- Excluded: \`.git\`, \`__pycache__\`, \`.ipynb_checkpoints\`, \`.mypy_cache\`, \`.pytest_cache\`"
  echo
  echo "Names, sizes and dates only - no file contents are read."
  echo

  # ---------------------------------------------------------------
  echo "## Directory sizes"
  echo
  echo '```'
  awk -F'\t' '{
      n = split($1, a, "/")
      top = (n == 1 ? "(root)" : a[1])
      bytes[top] += $2; files[top]++
    }
    END {
      for (d in bytes) printf "%15.0f\t%s\t%d\n", bytes[d], d, files[d]
    }' "$LIST" | LC_ALL=C sort -rn | awk '{
      b = $1; split("B KB MB GB TB PB", u, " "); i = 1
      while (b >= 1024 && i < 6) { b /= 1024; i++ }
      printf "  %-28s %10.1f %-3s  %6d file%s\n", $2, b, u[i], $3, ($3==1?"":"s")
    }'
  echo '```'
  echo

  # ---------------------------------------------------------------
  # The point of the whole script: which feature exists for which year.
  # Filenames follow grouse_data.PATH_TEMPLATES: {REGION}_{YEAR}_{feature}.tif
  echo "## Raster coverage: feature x year"
  echo
  echo "Parsed from \`{REGION}_{YEAR}_{feature}.tif\` filenames. This is what"
  echo "the year-gap filter reads: a training record survives only if EVERY"
  echo "feature has a vintage within tolerance of its sighting year, so a"
  echo "gap in any single row caps retention for the whole stack."
  echo
  if ! grep -qE '(^|/)[A-Z]{2}_[0-9]{4}_[A-Za-z0-9_]+\.tif' "$LIST"; then
    echo "_No rasters matching that pattern were found._"
    echo
  else
    grep -oE '(^|/)[A-Z]{2}_[0-9]{4}_[A-Za-z0-9_]+\.tif' "$LIST" \
      | sed 's|^/||; s|\.tif$||' | LC_ALL=C sort -u \
      | awk -F'_' '{
          region = $1; year = $2
          feat = $3
          for (i = 4; i <= NF; i++) feat = feat "_" $i
          seen[region "\t" feat "\t" year] = 1
          regions[region] = 1; feats[region "\t" feat] = 1
          years[region "\t" year] = 1
        }
        END {
          nr = 0
          for (r in regions) rlist[++nr] = r
          asort_simple(rlist, nr)
          for (ri = 1; ri <= nr; ri++) {
            r = rlist[ri]
            ny = 0; nf = 0
            for (k in years) { split(k, p, "\t"); if (p[1] == r) ylist[++ny] = p[2] }
            for (k in feats) { split(k, p, "\t"); if (p[1] == r) flist[++nf] = p[2] }
            asort_simple(ylist, ny); asort_simple(flist, nf)

            printf "### %s\n\n", r
            printf "| feature |"
            for (i = 1; i <= ny; i++) printf " %s |", ylist[i]
            printf " missing |\n|---|"
            for (i = 1; i <= ny; i++) printf ":--:|"
            printf "---|\n"
            for (i = 1; i <= nf; i++) {
              printf "| `%s` |", flist[i]
              gaps = ""
              for (j = 1; j <= ny; j++) {
                if ((r "\t" flist[i] "\t" ylist[j]) in seen) printf " x |"
                else { printf " . |"; gaps = gaps (gaps == "" ? "" : " ") ylist[j] }
              }
              printf " %s |\n", (gaps == "" ? "-" : "**" gaps "**")
            }
            printf "\n%d features x %d years.", nf, ny
            printf " `x` present, `.` absent.\n\n"
            delete ylist; delete flist
          }
        }
        # gawk-free ascending sort, so this runs on mawk/busybox too.
        function asort_simple(arr, n,   i, j, t) {
          for (i = 2; i <= n; i++) {
            t = arr[i]
            for (j = i - 1; j >= 1 && arr[j] > t; j--) arr[j+1] = arr[j]
            arr[j+1] = t
          }
        }'
  fi

  # ---------------------------------------------------------------
  echo "## Checkpoints"
  echo
  # Filtered with awk on field 1, not grep: LIST is tab-separated, and
  # GNU grep -E does not read \t as a tab - so an extension anchored
  # with $ tests the end of the LINE (the date), and one written as
  # [^\t]*\t matches a literal backslash-t. Both silently find nothing.
  CKPT="$TMP/ckpt.tsv"
  awk -F'\t' '$1 ~ /\.(pth|pt|ckpt)$/' "$LIST" \
    | LC_ALL=C sort -t$'\t' -k3,3r > "$CKPT"
  if [ -s "$CKPT" ]; then
    echo '```'
    awk -F'\t' '{
        b = $2; split("B KB MB GB TB", u, " "); i = 1
        while (b >= 1024 && i < 5) { b /= 1024; i++ }
        printf "  %-52s %8.1f %-3s  %s\n", $1, b, u[i], $3
      }' "$CKPT"
    echo '```'
  else
    echo "_None found._"
  fi
  echo

  # ---------------------------------------------------------------
  echo "## Full tree"
  echo
  echo "Every file, grouped by directory, newest-modified date on the right."
  echo "Directories over $MAX_PER_DIR files are truncated with a count."
  echo
  echo '```'
  awk -F'\t' -v MAX="$MAX_PER_DIR" '
    function hs(b,   u, i) {
      split("B KB MB GB TB", u, " "); i = 1
      while (b >= 1024 && i < 5) { b /= 1024; i++ }
      return sprintf("%.1f %s", b, u[i])
    }
    {
      path = $1
      n = split(path, a, "/")
      if (n == 1) { dir = "."; file = path }
      else { file = a[n]; dir = substr(path, 1, length(path) - length(file) - 1) }
      if (!(dir in count)) { order[++ndirs] = dir }
      count[dir]++; bytes[dir] += $2
      if (count[dir] <= MAX)
        body[dir] = body[dir] sprintf("    %-50s %10s  %s\n", file, hs($2), $3)
    }
    END {
      for (i = 1; i <= ndirs; i++) {
        d = order[i]
        printf "%s/  (%d file%s, %s)\n", d, count[d],
               (count[d] == 1 ? "" : "s"), hs(bytes[d])
        printf "%s", body[d]
        if (count[d] > MAX)
          printf "    ... and %d more file(s) not listed\n", count[d] - MAX
        printf "\n"
      }
    }' "$LIST"
  echo '```'
} > "$OUT_ABS"

echo "Wrote $OUT_ABS  ($TOTAL_FILES files, $(human "$TOTAL_BYTES"))"

if [ "$DO_GIT_ADD" -eq 1 ]; then
  if git -C "$OUT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    # -f because an inventory can be swallowed by a broad .gitignore rule
    # (a repo that ignores *.md, or ignores the whole data tree this
    # file happens to sit beside) and then be staged silently never.
    git -C "$OUT_DIR" add -f -- "$OUT_ABS"
    OUT_BRANCH=$(git -C "$OUT_DIR" symbolic-ref --short HEAD 2>/dev/null || echo '<branch>')
    echo "Staged in $(git -C "$OUT_DIR" rev-parse --show-toplevel). To publish it:"
    echo "    git commit -m 'Add project inventory'"
    echo "    git push -u origin $OUT_BRANCH"
  else
    echo "$OUT_DIR is not a git repository - file written but not staged." >&2
  fi
fi
