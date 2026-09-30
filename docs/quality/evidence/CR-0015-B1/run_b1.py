"""B1: re-run the pipeline in the scratch tree and compare output digests to
the main tree's split_manifest.json (the latest CR-0012 deliverable 6 run)."""
import hashlib
import json
import os
import subprocess
import sys
import time

W = "/home/ec2-user/grouse2/.claude/worktrees/agent-a74570e35615ea5e3"
S = "/tmp/claude-1000/cr0015-b1"
REF = "/home/ec2-user/grouse2/data/pipeline/split_manifest.json"
os.chdir(S)
assert os.path.realpath(os.getcwd()) == S


def run(args, log):
    t = time.time()
    with open(log, "w") as f:
        r = subprocess.run(["nice", "-n", "10", sys.executable] + args,
                           stdout=f, stderr=subprocess.STDOUT, cwd=S)
    print(f"{' '.join(args[:1])} rc={r.returncode} {time.time() - t:.0f}s")
    return r.returncode


steps = sys.argv[1:] or ["prepare", "negatives", "compare", "accept"]
if "prepare" in steps:
    assert run([f"{W}/prepare_training_data.py"], "prepare.log") == 0
if "negatives" in steps:
    assert run([f"{W}/generate_negatives.py"], "negatives.log") == 0
if "compare" in steps:
    ref = json.load(open(REF))
    new = json.load(open("data/pipeline/split_manifest.json"))
    lines = []
    ok = True
    for sec in ("positives", "negatives"):
        for rel, want in sorted(ref[sec]["outputs"].items()):
            got = hashlib.sha256(open(os.path.join(S, rel), "rb").read()).hexdigest()
            same = got == want
            ok &= same
            lines.append(f"{'IDENTICAL' if same else 'DIFFERS  '} {rel} {got}"
                         + ("" if same else f" (ref {want})"))
        m_same = new[sec]["outputs"] == ref[sec]["outputs"]
        ok &= m_same
        lines.append(f"manifest {sec}.outputs equal to reference: {m_same}")
        lines.append(f"new manifest {sec}: commit {new[sec]['commit']} dirty {new[sec]['dirty']}"
                     f" (reference commit {ref[sec]['commit']})")
    lines.append("B1 digests: " + ("PASS" if ok else "FAIL"))
    print("\n".join(lines))
    open("b1_compare.txt", "w").write("\n".join(lines) + "\n")
if "accept" in steps:
    rc = run([f"{W}/acceptance_split.py", "--data-root", S], "acceptance.log")
    print("acceptance_split rc", rc)
