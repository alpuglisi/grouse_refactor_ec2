"""CR-0021 deliverable 1, part C: one-off top-up of 2023-2024 negative
candidates (CR-0021 section 2 C). Evidence script, written before
approval (CR-0011 A3). Network: GBIF occurrence API, public, no
credentials. Run by the user on the EC2 host, ONCE, against a SCRATCH copy
of the tree; never against the live tree.

What it does, per state R, species s and year y in TOPUP_YEARS:
  e = rows of (R, s, y) already in <tree>/data/negatives/gbif_negatives_R.csv
  fetch up to TOPUP_MULTIPLE x e new records with the same query, dataset,
  species list, CSV_FIELDS and gbif_id de-duplication as get_negatives.py
  (its verify_dataset, resolve_taxon_keys and fetch_capped are reused).
  A partition with e = 0 gets nothing (reported).

Guards (refuse before any network call):
  - DISABLED is True (set after the one run, CR-0021 deliverable 1);
  - the tree is the live repository root, or a target file resolves
    (realpath) into the live data/negatives/, or is a symlink;
  - a target file is a hardlink (link count > 1, or the same file as the
    live one): `cp -al` / `rsync --link-dest` copies would otherwise let
    the append reach the live file;
  - a target file's sha256 differs from the pre-top-up hash pinned in the
    committed CR-0019 live acceptance record (itself pinned by sha256):
    so the script runs once per scratch copy, and never on a file that was
    already topped up;
  - a target file does not end with a newline, or its header is not
    get_negatives.CSV_FIELDS;
  - fetch_topup_result.json already exists (the top-up is recorded).
Each attempt writes its own fetch_topup_<UTC>.log, so an aborted attempt
stays on record and does not block a retry.
Every fetched row is checked (state == R, common_name == s, year == y,
non-empty unique gbif_id) BEFORE anything is written. All rows are
collected in memory and appended only when every partition succeeded; a
partition that stopped on fetch failures aborts the run with nothing
written (re-run: the hashes still match). Rows are appended with
csv.DictWriter(CSV_FIELDS) in append mode, exactly as get_negatives.py
writes (newline="", default "\\r\\n" line terminator), so the old bytes
stay an exact prefix (MC2). If an I/O error interrupts the appends
themselves (after every fetch succeeded), the files no longer match the
pinned hashes and a re-run is refused: re-copy the scratch tree from the
live one and run again.

Usage (repository root, on the EC2 host):
    PYTHONPATH=. python docs/quality/evidence/CR-0021/fetch_topup.py --tree SCRATCH

Writes: the three SCRATCH raw files (append only) and, next to this
script, fetch_topup.log and fetch_topup_result.json (per-file sha256
before/after, appended counts, the per-partition table).
"""
import argparse
import csv
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

# CR-0021 section 2 C: single use. The one top-up ran on 2026-10-03
# (fetch_topup_20261003T071204Z.log, fetch_topup_result.json at 224d3c3).
DISABLED = True

RECORD = os.path.join(HERE, "..", "CR-0019", "live", "acceptance_record.json")
RECORD_SHA = "ed27583beb8b9f95b23ce3c51d18817ee1d9a1a42043b0c773138b028da9c42a"
REGIONS = ("ME", "NH", "VT")
TOPUP_YEARS = (2023, 2024)
TOPUP_MULTIPLE = 2
RAW = "data/negatives/gbif_negatives_{R}.csv"
RESULT = os.path.join(HERE, "fetch_topup_result.json")


def log_path():
    import datetime as dt
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return os.path.join(HERE, f"fetch_topup_{stamp}.log")


class Abort(Exception):
    """Refuse or stop with nothing written."""


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pinned_pre_topup(record=RECORD, record_sha=RECORD_SHA):
    """{R: sha256 of gbif_negatives_R.csv} from the pinned acceptance record."""
    if sha256_file(record) != record_sha:
        raise Abort(f"{record}: sha256 differs from the pinned CR-0019 record")
    with open(record) as f:
        inputs = json.load(f)["inputs"]
    return {R: inputs[RAW.format(R=R)] for R in REGIONS}


def check_tree(tree, live_root, pinned, fields):
    """Problems that forbid the run (empty list = may run)."""
    probs = []
    rt, rl = os.path.realpath(tree), os.path.realpath(live_root)
    if rt == rl:
        probs.append(f"--tree is the live repository root ({rl})")
    live_neg = os.path.realpath(os.path.join(live_root, "data", "negatives"))
    for R in REGIONS:
        p = os.path.join(tree, RAW.format(R=R))
        if not os.path.exists(p):
            probs.append(f"{p}: missing")
            continue
        if os.path.islink(p):
            probs.append(f"{p}: is a symlink (copy the file into the scratch tree)")
        if os.path.dirname(os.path.realpath(p)) == live_neg:
            probs.append(f"{p}: resolves into the live data/negatives/")
        live_p = os.path.join(live_root, RAW.format(R=R))
        if os.path.exists(live_p) and os.path.samefile(p, live_p):
            probs.append(f"{p}: is the same file as the live one (hardlink)")
        if os.stat(p).st_nlink > 1:
            probs.append(f"{p}: has {os.stat(p).st_nlink} hardlinks (make a real copy, "
                         f"not cp -al / rsync --link-dest)")
        got = sha256_file(p)
        if got != pinned[R]:
            probs.append(f"{p}: sha256 {got[:12]}... is not the pinned pre-top-up "
                         f"{pinned[R][:12]}... (already topped up, or not the live copy)")
        with open(p, "rb") as f:
            data = f.read()
        if not data.endswith(b"\n"):
            probs.append(f"{p}: does not end with a newline")
        with open(p, newline="") as f:
            hdr = next(csv.reader(f), None)
        if hdr != list(fields):
            probs.append(f"{p}: header {hdr} != CSV_FIELDS {list(fields)}")
    return probs


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def row_year(row):
    v = row.get("year")
    if v in (None, ""):
        return None
    return int(float(v))


def partition_counts(rows_by_region, years):
    """{(R, common_name, year): existing rows}, for the given years."""
    counts = {}
    for R, rows in rows_by_region.items():
        for r in rows:
            y = row_year(r)
            if y in years:
                k = (R, r["common_name"], y)
                counts[k] = counts.get(k, 0) + 1
    return counts


class Collector:
    """A csv.DictWriter stand-in for fetch_capped: keeps rows in memory."""

    def __init__(self):
        self.rows = []

    def writerow(self, row):
        self.rows.append(dict(row))


def topup(rows_by_region, species, fetch, years=TOPUP_YEARS,
          multiple=TOPUP_MULTIPLE):
    """Plan and fetch every partition; return ({R: [new rows]}, table).

    fetch(R, common, year, quota, seen) -> (rows, stopped, exhausted).
    Raises Abort (nothing to write) on a stopped partition or a bad row."""
    seen = {r["gbif_id"] for rows in rows_by_region.values() for r in rows}
    counts = partition_counts(rows_by_region, set(years))
    new = {R: [] for R in rows_by_region}
    table = []
    for y in years:
        for R in rows_by_region:
            for common in species:
                e = counts.get((R, common, y), 0)
                quota = multiple * e
                if quota == 0:
                    table.append({"region": R, "species": common, "year": y,
                                  "existing": e, "requested": 0, "written": 0,
                                  "exhausted": None, "note": "zero existing (e = 0)"})
                    continue
                got, stopped, exhausted = fetch(R, common, y, quota, seen)
                if stopped:
                    raise Abort(f"{R} {common} {y}: fetches kept failing after "
                                f"retries (rate limit?); nothing written, re-run")
                if len(got) > quota:
                    raise Abort(f"{R} {common} {y}: {len(got)} rows > quota {quota}")
                for r in got:
                    if (r.get("state") != R or r.get("common_name") != common
                            or row_year(r) != y or not r.get("gbif_id")):
                        raise Abort(f"{R} {common} {y}: fetched row violates the "
                                    f"partition (state/species/year/gbif_id): {r}")
                new[R].extend(got)
                table.append({"region": R, "species": common, "year": y,
                              "existing": e, "requested": quota,
                              "written": len(got), "exhausted": bool(exhausted),
                              "note": ""})
    ids = [r["gbif_id"] for rows in new.values() for r in rows]
    if len(ids) != len(set(ids)):
        raise Abort("duplicate gbif_id among the fetched rows")
    return new, table


def append_rows(path, rows, fields):
    """Append exactly as get_negatives.py writes (no header: the file exists)."""
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields))
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tree", required=True, help="scratch copy of the repository tree")
    a = ap.parse_args(argv)
    if DISABLED:
        raise SystemExit("fetch_topup.py is disabled: CR-0021's one-off top-up has run")
    if os.path.exists(RESULT):
        raise SystemExit(f"{RESULT} exists: the top-up is already recorded")
    sys.path.insert(0, ROOT)
    import requests
    import get_negatives as G
    LOG = log_path()

    pinned = pinned_pre_topup()
    probs = check_tree(a.tree, ROOT, pinned, G.CSV_FIELDS)
    if probs:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(probs))

    lines = []

    def log(s=""):
        print(s)
        lines.append(str(s))

    paths = {R: os.path.join(a.tree, RAW.format(R=R)) for R in REGIONS}
    rows = {R: read_rows(paths[R]) for R in REGIONS}
    session = requests.Session()
    G.verify_dataset(session)
    taxa = G.resolve_taxon_keys(session)
    if set(taxa) != set(G.TARGET_SPECIES):
        raise SystemExit("taxon keys do not cover TARGET_SPECIES")

    def fetch(R, common, y, quota, seen):
        col = Collector()
        params = {"datasetKey": G.EOD_DATASET_KEY, "taxonKey": taxa[common],
                  "country": "US", "stateProvince": G.STATES[R],
                  "year": y, "hasCoordinate": "true"}
        n, stopped, exhausted, _ = G.fetch_capped(
            session, col, params, R, common, G.TARGET_SPECIES[common], quota, seen)
        log(f"  [{R}] {common} {y}: requested {quota}, got {n}"
            + (" [exhausted]" if exhausted else "") + (" [STOPPED]" if stopped else ""))
        return col.rows, stopped, exhausted

    log(f"CR-0021 top-up: years {TOPUP_YEARS}, multiple {TOPUP_MULTIPLE}, "
        f"tree {os.path.realpath(a.tree)}")
    try:
        new, table = topup(rows, list(G.TARGET_SPECIES), fetch)
    except Abort as e:
        log(f"ABORTED, nothing written: {e}")
        with open(LOG, "w") as f:
            f.write("\n".join(lines) + "\n")
        return 1

    result = {"record_sha256": RECORD_SHA, "years": list(TOPUP_YEARS),
              "multiple": TOPUP_MULTIPLE, "files": {}, "partitions": table}
    for R in REGIONS:
        append_rows(paths[R], new[R], G.CSV_FIELDS)
        result["files"][RAW.format(R=R)] = {
            "pre_sha256": pinned[R], "post_sha256": sha256_file(paths[R]),
            "rows_before": len(rows[R]), "rows_appended": len(new[R])}
    log("")
    log("partition table: region species year existing requested written exhausted note")
    for t in table:
        log(f"  {t['region']} {t['species']} {t['year']} {t['existing']} {t['requested']} "
            f"{t['written']} {t['exhausted']} {t['note']}")
    for rel, d in result["files"].items():
        log(f"{rel}: {d['rows_before']} + {d['rows_appended']} rows; "
            f"sha256 {d['pre_sha256'][:12]}... -> {d['post_sha256']}")
    with open(RESULT, "w") as f:
        json.dump(result, f, indent=2, sort_keys=True)
    with open(LOG, "w") as f:
        f.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
