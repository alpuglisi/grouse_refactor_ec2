"""CR-0021 MC self-test (author's; a reviewer's PA-0021(a) wrong-tree runs
are separate). Builds, in OUT, the tree the pre-registration predicts: the
replay with the stratified draw (preregister.Stratified) on the topped-up
SCRATCH tree, emitted to OUT, plus SCRATCH's three raw files. Then MC must
PASS with --old = the live tree and --new = OUT, and FAIL with --new = the
live tree (a no-op). Run after PRE_SHA is pinned.

    PYTHONPATH=. nice -n 10 python docs/quality/evidence/CR-0021/mc_selftest.py SCRATCH OUT
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preregister as pr          # noqa: E402
import acceptance_split as A      # noqa: E402

ROOT = pr.ROOT
HERE = pr.HERE


def main():
    scratch, out = (os.path.abspath(p) for p in sys.argv[1:3])
    live_data = os.path.realpath(os.path.join(ROOT, "data"))
    for p in (scratch, out):
        if os.path.realpath(p) in (os.path.realpath(ROOT), live_data) or \
                os.path.realpath(p).startswith(live_data + os.sep):
            sys.exit(f"refusing: {p} is the live tree or under its data/")
    os.chdir(ROOT)
    cfg = A.load_config()
    with open(os.path.join(HERE, "preregister_draw.json")) as f:
        strata = json.load(f)["strata"]
    rep = pr.Stratified(scratch, cfg, strata).run(stop_on_error=True)
    rep.emit(out)
    # The live run regenerates only C and N (generate_negatives.py); P and B
    # stay the live files, so copy them rather than rely on emit's bytes
    # (code review S4). The raw files are SCRATCH's (topped up).
    keep = []
    for R in cfg["constants"]["REGIONS"]:
        keep += [A.rpath(cfg, k, R) for k in ("thinned_positives", "train_positives",
                                              "val_positives")]
    keep.append(A.rpath(cfg, "block_assignments"))
    for rel in keep:
        shutil.copyfile(os.path.join(ROOT, rel), os.path.join(out, rel))
    for R in cfg["constants"]["REGIONS"]:
        rel = pr.RAW.format(R=R)
        os.makedirs(os.path.dirname(os.path.join(out, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(scratch, rel), os.path.join(out, rel))
    mc = os.path.join(HERE, "check_must_change.py")
    for label, new, want in (("predicted tree", out, 0), ("no-op (live as NEW)", ROOT, 1)):
        r = subprocess.run([sys.executable, mc, "--old", ROOT, "--new", new],
                           capture_output=True, text=True)
        print(f"== {label}: exit {r.returncode} (expected {want})")
        tail = r.stdout.strip().splitlines()
        print(tail[-1] if tail else r.stderr.strip())
        for line in r.stdout.splitlines():
            if "FAIL" in line and not line.startswith("MC:"):
                print("   ", line)
        if r.returncode != want:
            print("SELFTEST FAIL")
            return 1
    print("SELFTEST PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
