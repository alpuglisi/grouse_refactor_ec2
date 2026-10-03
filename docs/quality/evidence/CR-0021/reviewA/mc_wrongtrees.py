"""CR-0021 deliverable 1: reviewer A's PA-0021(a) wrong-tree runs of the
must-change gate MC (check_must_change.py). Written by reviewer A, who did
not write MC.

Builds, under OUT_BASE, the tree the pre-registration predicts (exactly as
mc_selftest.py: preregister.Stratified on SCRATCH with the strata of
preregister_draw.json, emitted, then the LIVE P and B files and SCRATCH's
three topped-up raw files copied in), plus a set of trees that are wrong in
one way each. Runs

    check_must_change.py --old <live ROOT> --new <tree>

on every tree and prints the expected and actual exit code (0 = PASS,
1 = FAIL) and the MC lines that failed. Ends "WRONGTREES PASS" (exit 0)
only if every correct tree passes, every wrong tree fails, and every
mutation is shown to have changed the bytes MC reads (a mutation that
changed nothing is reported INEFFECTIVE and fails the run).

Run on the EC2 host, from the repository root, after PRE_SHA is pinned and
with the live tree still the pre-CR (CR-0019) tree:

    PYTHONPATH=. nice -n 10 python docs/quality/evidence/CR-0021/reviewA/mc_wrongtrees.py \
        /home/ec2-user/cr0021_scratch /home/ec2-user/cr0021_wrongtrees \
        2>&1 | tee docs/quality/evidence/CR-0021/reviewA/mc_wrongtrees.txt

Writes only under OUT_BASE (refused if OUT_BASE is the live tree, under its
data/, or inside the repository). Reads SCRATCH and the live tree; writes
neither. Does not call preregister.finish (preregister.txt is untouched).

Trees (name: what is wrong -> the MC check it must trip):
  correct            the predicted tree                         -> PASS
  noop               live tree as NEW                           -> MC2, MC3, MC4
  unstratified       today's draw (plain replay) on SCRATCH     -> MC4
  raw_not_topped_up  live raw files over the predicted tree     -> MC2
  raw_append_dropped one appended raw row removed               -> MC2
  raw_old_altered    one old (pre-top-up) raw row altered       -> MC2
  p_altered          one thinned positive's longitude altered   -> MC1
  n_year_swap        one N row replaced by a pool row of the
                     same cell and NonVeg class, other year     -> MC4
  n_nonveg_flip      one N row's is_nonveg flipped              -> MC4
  nonveg_cap_cell    NonVeg cap per cell (rounding remainder
                     moved between strata)                      -> MC4
  trainval_desync    one line dropped from a train_negatives    -> MC5
  c_split_flip       one candidate_pool row's split flipped     -> MC3
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.dirname(HERE)
sys.path.insert(0, EVID)
import preregister as pr          # noqa: E402  (inserts ROOT on sys.path)
import acceptance_split as A      # noqa: E402

ROOT = pr.ROOT
MC = os.path.join(EVID, "check_must_change.py")


# ---------------------------------------------------------------------------
# Text-level helpers (mutations keep every other byte as written)
# ---------------------------------------------------------------------------
def read_lines(path):
    """Lines with their own terminators, so a rewrite is byte-exact."""
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().splitlines(keepends=True)


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))


def eol(line):
    return "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")


def parse(line):
    return next(csv.reader([line.rstrip("\r\n")]))


def unparse(fields, terminator):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(fields)
    return buf.getvalue() + terminator


def header(lines):
    return parse(lines[0])


def truthy(v):
    return str(v).strip().lower() == "true"


def ffloat(v):
    return float(str(v).strip())


def iyear(v):
    return int(float(str(v).strip()))


def bump_last_digit(text):
    """Change the last digit of a numeric text value (keeps it parseable)."""
    for i in range(len(text) - 1, -1, -1):
        if text[i].isdigit():
            d = "1" if text[i] != "1" else "2"
            return text[:i] + d + text[i + 1:]
    raise ValueError(f"no digit in {text!r}")


def sha(path):
    return A.sha256_file(path)


# ---------------------------------------------------------------------------
# Tree construction
# ---------------------------------------------------------------------------
def rel_lists(cfg):
    regions = cfg["constants"]["REGIONS"]
    p_rels = []
    for R in regions:
        p_rels += [A.rpath(cfg, k, R) for k in ("thinned_positives", "train_positives",
                                                "val_positives")]
    p_rels.append(A.rpath(cfg, "block_assignments"))
    raw_rels = [pr.RAW.format(R=R) for R in regions]
    return regions, p_rels, raw_rels


def finish_tree(rep, out, scratch, cfg):
    """emit, then live P/B and SCRATCH raw files, as mc_selftest.py does."""
    rep.emit(out)
    _, p_rels, raw_rels = rel_lists(cfg)
    for rel in p_rels:
        shutil.copyfile(os.path.join(ROOT, rel), os.path.join(out, rel))
    for rel in raw_rels:
        os.makedirs(os.path.dirname(os.path.join(out, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(scratch, rel), os.path.join(out, rel))


class CellCap(pr.Stratified):
    """WRONG on purpose: the NonVeg cap is applied per (region, split) cell,
    round(n_cell x NONVEG_MAX_FRAC), and the rounding remainder against the
    per-stratum sum is moved onto the first (if positive) or last (if
    negative) stratum that can take it. Same ES sampling otherwise."""

    def draw_select(self, seed=None, record=True):
        import pandas as pd
        seed = self.seed() if seed is None else seed
        pool = self.pool_full
        nv_all = A.bool_array(pool["is_nonveg"])
        pk = pr.stratum_of(pool["year"], self.strata)
        picked = []
        for R in self.regions:
            for s in A.SPLITS:
                P = self.pos[R][self.pos[R]["split"] == s]
                ppk = pr.stratum_of(P["year"], self.strata)
                cell = ((pool["region"] == R) & (pool["split"] == s)).to_numpy()
                ns, nvs, subs = [], [], []
                for k, _ in enumerate(self.strata):
                    n = A.py_round(int((ppk == k).sum()) * self.C["NEG_RATIO"])
                    m = cell & (pk == k)
                    nv, hab = pool[m & nv_all], pool[m & ~nv_all]
                    ns.append(n)
                    nvs.append(min(A.py_round(n * self.C["NONVEG_MAX_FRAC"]), len(nv)))
                    subs.append((nv, hab))
                diff = A.py_round(sum(ns) * self.C["NONVEG_MAX_FRAC"]) - sum(nvs)
                order = range(len(ns)) if diff > 0 else range(len(ns) - 1, -1, -1)
                for k in order:
                    if diff == 0:
                        break
                    nv, _ = subs[k]
                    step = 1 if diff > 0 else -1
                    while diff != 0 and 0 <= nvs[k] + step <= min(len(nv), ns[k]):
                        nvs[k] += step
                        diff -= step
                tot = {"n": 0, "n_nv": 0, "n_hab": 0}
                per = {}
                for k, st in enumerate(self.strata):
                    nv, hab = subs[k]
                    n_hab = ns[k] - nvs[k]
                    if len(hab) < n_hab:
                        raise A.ReplayError(f"[{R}/{s}/{st[0]}] habitat short (cell cap)")
                    picked.extend([self.es_take(hab, n_hab, seed),
                                   self.es_take(nv, nvs[k], seed)])
                    per[str(st[0])] = {"n": int(ns[k]), "n_nv": int(nvs[k]),
                                       "n_hab": int(n_hab)}
                    for key, v in (("n", ns[k]), ("n_nv", nvs[k]), ("n_hab", n_hab)):
                        tot[key] += int(v)
                if record:
                    self.draw_counts.setdefault(R, {})[s] = {**tot, "strata": per}
        return pd.concat(picked, ignore_index=True)


# ---------------------------------------------------------------------------
# Mutations of a copy of the correct tree (each returns a description)
# ---------------------------------------------------------------------------
def regen_splits(tree, cfg, R):
    """Rewrite train_/val_negatives_R from the combined file's lines."""
    lines = read_lines(os.path.join(tree, A.rpath(cfg, "negatives", R)))
    hdr = header(lines)
    si = hdr.index("split")
    for s in A.SPLITS:
        keep = [lines[0]] + [ln for ln in lines[1:] if parse(ln)[si] == s]
        write_lines(os.path.join(tree, A.rpath(cfg, f"{s}_negatives", R)), keep)


def m_raw_not_topped_up(tree, cfg, scratch):
    _, _, raw_rels = rel_lists(cfg)
    for rel in raw_rels:
        shutil.copyfile(os.path.join(ROOT, rel), os.path.join(tree, rel))
    return "live raw files copied over the topped-up ones"


def m_raw_append_dropped(tree, cfg, scratch):
    _, _, raw_rels = rel_lists(cfg)
    rel = raw_rels[0]
    n_old = len(read_lines(os.path.join(ROOT, rel)))
    lines = read_lines(os.path.join(tree, rel))
    if len(lines) <= n_old:
        raise RuntimeError(f"{rel}: no appended rows to drop")
    del lines[-1]
    write_lines(os.path.join(tree, rel), lines)
    return f"{rel}: last appended row removed ({len(lines)} lines left)"


def m_raw_old_altered(tree, cfg, scratch):
    _, _, raw_rels = rel_lists(cfg)
    rel = raw_rels[0]
    lines = read_lines(os.path.join(tree, rel))
    hdr = header(lines)
    f = parse(lines[1])
    col = "longitude" if "longitude" in hdr else hdr[0]
    i = hdr.index(col)
    f[i] = bump_last_digit(f[i])
    lines[1] = unparse(f, eol(lines[1]))
    write_lines(os.path.join(tree, rel), lines)
    return f"{rel}: first old row's {col} altered"


def m_p_altered(tree, cfg, scratch):
    R = cfg["constants"]["REGIONS"][0]
    rel = A.rpath(cfg, "thinned_positives", R)
    lines = read_lines(os.path.join(tree, rel))
    hdr = header(lines)
    i = hdr.index("longitude")
    f = parse(lines[1])
    f[i] = bump_last_digit(f[i])
    lines[1] = unparse(f, eol(lines[1]))
    write_lines(os.path.join(tree, rel), lines)
    return f"{rel}: first row's longitude altered"


def raw_row(tree, cfg, gbif_id):
    """The raw candidate row (text) with this gbif_id, {} if none."""
    want = str(int(float(gbif_id))) if str(gbif_id).strip() else ""
    for R in cfg["constants"]["REGIONS"]:
        path = os.path.join(tree, pr.RAW.format(R=R))
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                g = row.get("gbif_id", "")
                try:
                    g = str(int(float(g)))
                except ValueError:
                    pass
                if g == want:
                    return row
    return {}


def m_n_year_swap(tree, cfg, scratch):
    """Replace one N row by a pool row of the same (region, split, is_nonveg)
    with a different year, not already in N; keep canonical order and the
    train/val files consistent, so only the N content changes."""
    pool_lines = read_lines(os.path.join(tree, A.rpath(cfg, "candidate_pool")))
    ph = header(pool_lines)
    for R in cfg["constants"]["REGIONS"]:
        rel = A.rpath(cfg, "negatives", R)
        lines = read_lines(os.path.join(tree, rel))
        nh = header(lines)
        rows = [parse(ln) for ln in lines[1:]]
        ix = {c: nh.index(c) for c in ("longitude", "latitude", "split", "year", "is_nonveg")}
        in_n = {(ffloat(r[ix["longitude"]]), ffloat(r[ix["latitude"]])) for r in rows}
        pidx = {c: ph.index(c) for c in ("region", "longitude", "latitude", "split", "year",
                                        "is_nonveg")}
        cands = {}
        for ln in pool_lines[1:]:
            p = parse(ln)
            if p[pidx["region"]] != R:
                continue
            k = (ffloat(p[pidx["longitude"]]), ffloat(p[pidx["latitude"]]))
            if k in in_n:
                continue
            cands.setdefault((p[pidx["split"]], truthy(p[pidx["is_nonveg"]]),
                              iyear(p[pidx["year"]])), []).append(p)
        for j, r in enumerate(rows):
            s, nv, y = r[ix["split"]], truthy(r[ix["is_nonveg"]]), iyear(r[ix["year"]])
            alt = sorted(yy for (ss, nn, yy) in cands if ss == s and nn == nv and yy != y)
            if not alt:
                continue
            p = cands[(s, nv, alt[0])][0]
            raw = raw_row(tree, cfg, p[ph.index("gbif_id")]) if "gbif_id" in ph else {}
            new = []
            for c in nh:
                if c == "label":
                    new.append(r[nh.index("label")])
                elif c in ph:
                    new.append(p[ph.index(c)])
                else:   # N columns the pool does not carry (obs_date, ...): from raw
                    new.append(raw.get(c, ""))
            term = eol(lines[1 + j])
            body = [ln for i, ln in enumerate(lines[1:]) if i != j]
            body.append(unparse(new, term))
            body.sort(key=lambda ln: (ffloat(parse(ln)[ix["longitude"]]),
                                      ffloat(parse(ln)[ix["latitude"]])))
            # every line keeps a terminator (the old last line may have had one)
            body = [ln if eol(ln) else ln + term for ln in body]
            write_lines(os.path.join(tree, rel), [lines[0]] + body)
            regen_splits(tree, cfg, R)
            return (f"{rel}: row ({r[ix['longitude']]}, {r[ix['latitude']]}) {s} {y} "
                    f"nonveg={nv} replaced by pool row of year {alt[0]}")
    raise RuntimeError("no N row with a same-cell, same-class pool row of another year")


def m_n_nonveg_flip(tree, cfg, scratch):
    R = cfg["constants"]["REGIONS"][0]
    rel = A.rpath(cfg, "negatives", R)
    lines = read_lines(os.path.join(tree, rel))
    hdr = header(lines)
    i = hdr.index("is_nonveg")
    f = parse(lines[1])
    old = f[i]
    f[i] = "False" if truthy(old) else "True"
    lines[1] = unparse(f, eol(lines[1]))
    write_lines(os.path.join(tree, rel), lines)
    regen_splits(tree, cfg, R)
    return f"{rel}: first row's is_nonveg {old} -> {f[i]}"


def m_trainval_desync(tree, cfg, scratch):
    R = cfg["constants"]["REGIONS"][0]
    rel = A.rpath(cfg, "train_negatives", R)
    lines = read_lines(os.path.join(tree, rel))
    if len(lines) < 2:
        raise RuntimeError(f"{rel}: no data rows")
    del lines[1]
    write_lines(os.path.join(tree, rel), lines)
    return f"{rel}: first data line dropped"


def m_c_split_flip(tree, cfg, scratch):
    rel = A.rpath(cfg, "candidate_pool")
    lines = read_lines(os.path.join(tree, rel))
    hdr = header(lines)
    i = hdr.index("split")
    f = parse(lines[1])
    old = f[i]
    f[i] = "val" if old == "train" else "train"
    lines[1] = unparse(f, eol(lines[1]))
    write_lines(os.path.join(tree, rel), lines)
    return f"{rel}: first row's split {old} -> {f[i]}"


MUTATIONS = (
    ("raw_not_topped_up", m_raw_not_topped_up, "MC2"),
    ("raw_append_dropped", m_raw_append_dropped, "MC2"),
    ("raw_old_altered", m_raw_old_altered, "MC2"),
    ("p_altered", m_p_altered, "MC1"),
    ("n_year_swap", m_n_year_swap, "MC4"),
    ("n_nonveg_flip", m_n_nonveg_flip, "MC4"),
    ("trainval_desync", m_trainval_desync, "MC5"),
    ("c_split_flip", m_c_split_flip, "MC3"),
)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def tree_digest(tree):
    """{relpath: sha256} of every CSV under tree (for the effect check; the
    manifest is left out because it carries run metadata)."""
    d = {}
    for base, _, files in os.walk(tree):
        for fn in files:
            if not fn.endswith(".csv"):
                continue
            p = os.path.join(base, fn)
            d[os.path.relpath(p, tree)] = sha(p)
    return d


def run_mc(new):
    r = subprocess.run([sys.executable, MC, "--old", ROOT, "--new", new],
                       capture_output=True, text=True, cwd=ROOT)
    failed = [ln for ln in r.stdout.splitlines()
              if " FAIL" in ln and not ln.startswith("MC:")]
    tail = r.stdout.strip().splitlines()
    return r.returncode, failed, (tail[-1] if tail else r.stderr.strip()[-500:])


def refuse(path):
    rp = os.path.realpath(path)
    repo = os.path.realpath(ROOT)
    live_data = os.path.realpath(os.path.join(ROOT, "data"))
    if rp == repo or rp.startswith(repo + os.sep) or rp == live_data \
            or rp.startswith(live_data + os.sep):
        sys.exit(f"refusing: {path} is the live tree, under its data/, or inside the repository")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        sys.exit(__doc__)
    scratch, out_base = (os.path.abspath(p) for p in argv)
    refuse(out_base)
    if os.path.realpath(scratch) == os.path.realpath(ROOT):
        sys.exit("refusing: SCRATCH is the live tree")
    if os.path.exists(out_base) and os.listdir(out_base):
        sys.exit(f"refusing: {out_base} exists and is not empty")
    os.makedirs(out_base, exist_ok=True)
    os.chdir(ROOT)
    cfg = A.load_config()
    with open(os.path.join(EVID, "preregister_draw.json")) as f:
        draw = json.load(f)
    strata = draw["strata"]
    print(f"CR-0021 MC wrong-tree runs (reviewer A); live {ROOT}; scratch {scratch}; "
          f"strata {draw.get('strata_id')} {strata}")

    results = []   # (name, expected exit, actual, want_check, failed lines, note)

    def record(name, tree, want, want_check, note=""):
        code, failed, last = run_mc(tree)
        hit = (want == 0) or any(ln.startswith(want_check) for ln in failed)
        results.append((name, want, code, want_check, failed, last, note, hit))

    # 1. the predicted (correct) tree
    correct = os.path.join(out_base, "correct")
    finish_tree(pr.Stratified(scratch, cfg, strata).run(stop_on_error=True),
                correct, scratch, cfg)
    base_digest = tree_digest(correct)
    record("correct", correct, 0, "")

    # 2. no-op: the live tree itself
    record("noop", ROOT, 1, "MC2")

    # 3. unstratified draw: today's replay on SCRATCH
    unstr = os.path.join(out_base, "unstratified")
    finish_tree(pr.Capture(scratch, cfg).run(stop_on_error=True), unstr, scratch, cfg)
    eff = tree_digest(unstr) != base_digest
    record("unstratified", unstr, 1, "MC4", "" if eff else "INEFFECTIVE")

    # 4. NonVeg cap per cell
    cellcap = os.path.join(out_base, "nonveg_cap_cell")
    rep = CellCap(scratch, cfg, strata).run(stop_on_error=True)
    finish_tree(rep, cellcap, scratch, cfg)
    eff = tree_digest(cellcap) != base_digest
    record("nonveg_cap_cell", cellcap, 1, "MC4",
           "" if eff else "INEFFECTIVE (no cell where the per-cell cap differs)")

    # 5. text mutations of copies of the correct tree
    for name, fn, want_check in MUTATIONS:
        tree = os.path.join(out_base, name)
        shutil.copytree(correct, tree)
        try:
            desc = fn(tree, cfg, scratch)
        except Exception as e:   # a mutation that cannot be built is a failure of this run
            results.append((name, 1, None, want_check, [], f"mutation not built: {e}",
                            "INEFFECTIVE", False))
            continue
        eff = tree_digest(tree) != base_digest
        record(name, tree, 1, want_check, desc if eff else f"INEFFECTIVE: {desc}")

    ok_all = True
    print()
    for name, want, code, want_check, failed, last, note, hit in results:
        ok = code == want and hit and not note.startswith("INEFFECTIVE")
        ok_all &= ok
        print(f"== {name}: expected exit {want}"
              + (f" (via {want_check})" if want else "")
              + f", actual {code} -> {'OK' if ok else 'WRONG'}")
        if note:
            print(f"   {note}")
        print(f"   {last}")
        for ln in failed[:12]:
            print(f"     {ln}")
        if len(failed) > 12:
            print(f"     ... {len(failed) - 12} more FAIL lines")
    print()
    print("WRONGTREES " + ("PASS" if ok_all else "FAIL"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
