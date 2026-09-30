"""CR-0019 reviewer B: derived wrong trees (text edits of the `correct`
tree built by build_trees.py) and the MC verdict table for every tree.

    PYTHONPATH=. nice -n 10 python docs/quality/evidence/CR-0019/reviewB/edit_trees_and_run_mc.py OUT

Edits operate on CSV text lines so untouched lines stay byte-identical.
Writes only under OUT (outside the repository); prints the table.
"""
import csv
import io
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", "..", ".."))
MC = os.path.join(ROOT, "docs/quality/evidence/CR-0019/check_must_change.py")
PP = "data/pipeline/{k}_positives_{R}.csv"
NN = "data/negatives/{k}negatives_{R}.csv"
POOL = "data/negatives/candidate_pool.csv"


def rl(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def wl(p, lines):
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def fields(line):
    return next(csv.reader([line]))


def join(fs):
    b = io.StringIO()
    csv.writer(b, lineterminator="").writerow(fs)
    return b.getvalue()


def rebuild_splits(root, combined, kind):
    """Regenerate train_/val_ files from the combined file (kept consistent,
    so MC5 cannot be what catches the edit)."""
    L = rl(os.path.join(root, combined))
    si = fields(L[0]).index("split")
    for s in ("train", "val"):
        out = [L[0]] + [x for x in L[1:] if fields(x)[si] == s]
        if kind == "P":
            R = combined.split("_")[-1][:2]
            wl(os.path.join(root, PP.format(k=s, R=R)), out)
        else:
            R = combined.split("_")[-1][:2]
            wl(os.path.join(root, NN.format(k=s + "_", R=R)), out)


def clone(out, name):
    d = os.path.join(out, name)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(os.path.join(out, "correct"), d)
    return d


def edit_rows(root, rel, fn):
    L = rl(os.path.join(root, rel))
    hdr = fields(L[0])
    L = [L[0]] + fn(hdr, L[1:])
    wl(os.path.join(root, rel), L)


def old_keys(rel):
    L = rl(os.path.join(ROOT, rel))
    h = fields(L[0])
    return {(fields(x)[h.index("longitude")], fields(x)[h.index("latitude")]) for x in L[1:]}


def derived(out):
    trees = {}
    # deletions
    d = clone(out, "del_pos5")
    edit_rows(d, PP.format(k="thinned", R="ME"), lambda h, rows: rows[5:])
    rebuild_splits(d, PP.format(k="thinned", R="ME"), "P")
    trees["del_pos5"] = "FAIL"
    d = clone(out, "del_neg5")
    edit_rows(d, NN.format(k="", R="ME"), lambda h, rows: rows[5:])
    rebuild_splits(d, NN.format(k="", R="ME"), "N")
    trees["del_neg5"] = "FAIL"

    def drop_train(n):
        def f(h, rows):
            si, out_, k = h.index("split"), [], 0
            for x in rows:
                if fields(x)[si] == "train" and k < n:
                    k += 1
                    continue
                out_.append(x)
            return out_
        return f
    d = clone(out, "del_pos_and_neg_matched")
    edit_rows(d, PP.format(k="thinned", R="NH"), drop_train(10))
    rebuild_splits(d, PP.format(k="thinned", R="NH"), "P")
    edit_rows(d, NN.format(k="", R="NH"), drop_train(10))
    rebuild_splits(d, NN.format(k="", R="NH"), "N")
    trees["del_pos_and_neg_matched"] = "FAIL"
    # duplicate a positive row
    d = clone(out, "dup_pos")
    edit_rows(d, PP.format(k="thinned", R="VT"), lambda h, rows: rows[:1] + rows[:1] + rows[1:])
    rebuild_splits(d, PP.format(k="thinned", R="VT"), "P")
    trees["dup_pos"] = "FAIL"

    # rewritten values
    def set_col(col, val, pick):
        def f(h, rows):
            ci = h.index(col)
            rows = list(rows)
            i = pick(h, rows)
            fs = fields(rows[i])
            fs[ci] = val(fs[ci])
            rows[i] = join(fs)
            return rows
        return f
    first = lambda h, rows: 0
    oldP = old_keys(PP.format(k="thinned", R="ME"))

    def added(h, rows):
        lo, la = h.index("longitude"), h.index("latitude")
        for i, x in enumerate(rows):
            fs = fields(x)
            if (fs[lo], fs[la]) not in oldP:
                return i
        raise SystemExit("no added ME positive")
    d = clone(out, "edit_kept_pos_evh")
    edit_rows(d, PP.format(k="thinned", R="ME"), set_col("evh", lambda v: str(float(v) + 1), first))
    rebuild_splits(d, PP.format(k="thinned", R="ME"), "P")
    trees["edit_kept_pos_evh"] = "FAIL"
    d = clone(out, "edit_added_pos_evh")
    edit_rows(d, PP.format(k="thinned", R="ME"), set_col("evh", lambda v: str(float(v) + 1), added))
    rebuild_splits(d, PP.format(k="thinned", R="ME"), "P")
    trees["edit_added_pos_evh"] = "FAIL (R1 catches if MC does not)"
    d = clone(out, "edit_pos_year")
    edit_rows(d, PP.format(k="thinned", R="ME"), set_col("year", lambda v: str(int(v) - 1), first))
    rebuild_splits(d, PP.format(k="thinned", R="ME"), "P")
    trees["edit_pos_year"] = "FAIL"
    d = clone(out, "edit_neg_weight_N_only")
    edit_rows(d, NN.format(k="", R="ME"), set_col("weight", lambda v: str(float(v) * 2), first))
    rebuild_splits(d, NN.format(k="", R="ME"), "N")
    trees["edit_neg_weight_N_only"] = "FAIL"
    d = clone(out, "edit_neg_obs_date")
    edit_rows(d, NN.format(k="", R="ME"), set_col("obs_date", lambda v: "1999-01-01", first))
    rebuild_splits(d, NN.format(k="", R="ME"), "N")
    trees["edit_neg_obs_date"] = "FAIL (documented MC gap; R4 catches)"
    d = clone(out, "edit_pool_weight")
    edit_rows(d, POOL, set_col("weight", lambda v: str(float(v) * 2), lambda h, r: len(r) - 1))
    trees["edit_pool_weight"] = "FAIL"
    # order
    d = clone(out, "pos_order_reversed")
    edit_rows(d, PP.format(k="thinned", R="NH"), lambda h, rows: rows[::-1])
    rebuild_splits(d, PP.format(k="thinned", R="NH"), "P")
    trees["pos_order_reversed"] = "FAIL (R1 order catches if MC does not)"
    d = clone(out, "pool_two_rows_swapped")
    edit_rows(d, POOL, lambda h, rows: [rows[1], rows[0]] + rows[2:])
    trees["pool_two_rows_swapped"] = "FAIL"
    # MC5
    d = clone(out, "train_file_stale")
    shutil.copyfile(os.path.join(ROOT, PP.format(k="train", R="VT")),
                    os.path.join(d, PP.format(k="train", R="VT")))
    trees["train_file_stale"] = "FAIL"
    return trees


def run(old, new):
    r = subprocess.run([sys.executable, MC, "--old", old, "--new", new],
                       capture_output=True, text=True)
    fails = [ln.split(":")[0] for ln in r.stdout.splitlines()
             if ": FAIL" in ln and not ln.startswith("MC:")]
    last = (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]
    return r.returncode, last, fails


def main():
    out = os.path.abspath(sys.argv[1])
    base = {"correct": "PASS", "noop_replay": "FAIL", "off_by_one": "FAIL",
            "floor_2019": "FAIL", "after_thin": "FAIL", "source_all": "FAIL",
            "source_buffer": "FAIL", "train_only": "FAIL", "stale_blocks": "FAIL"}
    trees = {k: v for k, v in base.items() if os.path.isdir(os.path.join(out, k))}
    trees.update(derived(out))
    rows = [("live tree as NEW (no-op)", ROOT, ROOT, "FAIL"),
            ("MC0: OLD = correct tree", os.path.join(out, "correct"), os.path.join(out, "correct"), "FAIL")]
    rows += [(k, ROOT, os.path.join(out, k), v) for k, v in trees.items()]
    print("| tree | expected | MC exit | MC summary | failing checks |")
    print("|---|---|---|---|---|")
    for name, old, new, exp in rows:
        code, last, fails = run(old, new)
        print(f"| {name} | {exp} | {code} | {last} | {', '.join(fails) or '-'} |", flush=True)


if __name__ == "__main__":
    main()
