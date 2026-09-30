"""CR-0012 d6 test plan: the standing checks must refuse the pre-CR backup.

Tree C = copies of /home/ec2-user/grouse_backup/CR-0012/{pipeline,negatives}
plus symlinked rasters. Three variants:
  (a) as backed up (no acceptance record);
  (b) + the real acceptance record copied in (backup restored over
      accepted data);
  (c) + a forged record whose config sha and artifact digests MATCH the
      backup files (so only the E0-E6 content gates can refuse).
Each writes only under tree C.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, "/home/ec2-user/grouse2")
import acceptance_split as a  # noqa: E402

C = "/tmp/claude-1000/-home-ec2-user-grouse2/cr0012-d6/C"
REC = os.path.join(C, "data/pipeline/acceptance_record.json")
assert not os.path.islink(REC) and not os.path.islink(os.path.dirname(REC))


def attempt(tag):
    print(f"--- variant {tag}: standing_checks(64, 0, False, data_root=C)")
    try:
        a.standing_checks(64, 0, False, data_root=C)
        print("RESULT: ACCEPTED (unexpected)")
        return False
    except a.AcceptanceError as e:
        lines = str(e).splitlines()
        print(f"RESULT: REFUSED, {len(lines) - 1} failure line(s)")
        for ln in lines[:40]:
            print("   " + ln)
        if len(lines) > 40:
            print(f"   ... {len(lines) - 40} more")
        return True


ok = []
if os.path.exists(REC):
    os.remove(REC)
ok.append(attempt("(a) backup as-is, no record"))

shutil.copyfile("/home/ec2-user/grouse2/data/pipeline/acceptance_record.json", REC)
ok.append(attempt("(b) backup + real acceptance record"))

cfg = a.load_config(None)
arts = {}
for rel in a.standing_csv_paths(cfg):
    full = os.path.join(C, rel)
    if os.path.exists(full):
        arts[rel] = a.sha256_file(full)
forged = {"cr": "CR-0013", "config_sha256": cfg["_sha256"], "artifacts": arts, "rasters": []}
with open(REC, "w") as f:
    json.dump(forged, f)
print(f"forged record: {len(arts)} artifact digests matching the backup files")
ok.append(attempt("(c) backup + forged record matching its files"))
os.remove(REC)
print("ALL REFUSED" if all(ok) else "SOME ACCEPTED")
