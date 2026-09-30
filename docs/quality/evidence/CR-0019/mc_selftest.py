"""CR-0019 MC self-test (author's; PA-0021(a) runs by a reviewer are
separate). Builds, in a scratch directory given as argv[1], the tree the
pre-registration predicts, by emitting preregister.Floored (CR-0013's
replay with CR-0019's positives step 2) there, and copies nothing else.
Then MC must PASS with --old = the live tree and --new = that tree, and
FAIL with --new = the live tree (a no-op).

    PYTHONPATH=. nice -n 10 python docs/quality/evidence/CR-0019/mc_selftest.py SCRATCH
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acceptance_split as A      # noqa: E402
import preregister as pr          # noqa: E402

ROOT = pr.ROOT


def main():
    out = os.path.abspath(sys.argv[1])
    if os.path.realpath(out).startswith(os.path.realpath(os.path.join(ROOT, "data"))):
        sys.exit("refusing to write under data/")
    cfg = A.load_config()
    rep = pr.Floored(ROOT, cfg).run(stop_on_error=True)
    rep.emit(out)
    mc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_must_change.py")
    for label, new, want in (("predicted tree", out, 0), ("no-op (live as NEW)", ROOT, 1)):
        r = subprocess.run([sys.executable, mc, "--old", ROOT, "--new", new],
                           capture_output=True, text=True)
        print(f"== {label}: exit {r.returncode} (expected {want})")
        print(r.stdout.strip().splitlines()[-1])
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
