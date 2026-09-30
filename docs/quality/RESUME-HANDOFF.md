> **SUPERSEDED (2026-09-30, ~16:00 UTC).** The programme this handoff describes is complete: CR-0009, CR-0012, CR-0013, CR-0015, CR-0017 and CR-0018 are IMPLEMENTED (with CR-0008, CR-0010, CR-0014, CR-0016 earlier; CR-0007 CLOSED). The CR-0009 retrain ran on the 16-vCPU instance (saved epoch 3, rank 0.7317); the Errol map symptom is absent on the regenerated maps (BUG-0022 CLOSED). Open work lives in `docs/quality/CR-0007-0008-OPEN-ISSUES.md` and the OPEN rows of `docs/quality/bugs/BUG_LOG.md` (e.g. BUG-0034, BUG-0051, BUG-0059..0062, BUG-0068, BUG-0072). The snapshot below is kept for history only.

# Resume handoff — change-control programme (snapshot 2026-09-30 ~13:25 UTC)

Read this first when work resumes. Then read `CLAUDE.md`, and
`docs/quality/PREVENTIVE_ACTIONS.md` before any change. This file is a
point-in-time snapshot. Where it disagrees with the CRs, the CRs win.

## 0. Why work stopped, and what that means
The user stopped the EC2 instance to change its instance type, to get faster
training. Before the stop:
- Every background agent was stopped deliberately. None of them had
  committed work or left a partial edit in the main tree.
- The CR-0009 retrain was stopped (SIGINT) partway through epoch 1. It
  wrote no checkpoint (`grouse_cr0009.pth*` does not exist) and no
  `metrics.csv`.
- The EBS root volume survives a stop or type change. The repo, `data/`,
  `/home/ec2-user/grouse_backup/` and `data/cache/` (1.3 GB patch cache,
  reusable) are all intact.
- `/tmp` is tmpfs, so it is **gone**. That includes the session
  scratchpad, agent transcripts and the dry-run outputs. Nothing needed
  lives there.
- Old agent IDs cannot be resumed. Start fresh agents.

**Performance note.** Epoch 1 ran at about 2–3 batches/s, with 1,248
batches per epoch. The L40S sat at about 10 % utilisation. Training was
**CPU/data-loading bound** on 4 vCPUs, with 4 agents sharing them. More
vCPUs helps more than a faster GPU.

## 1. Where the repository is
- Branch: `claude/quality-records-cr0006-0009`. The last commit before the
  handoff is `62f74db`, followed by this file's commit. The tracked tree is
  clean. Untracked `inv_*`/`res_*` files are investigation scratch and are
  deliberately not committed.
- Not pushed: there are no credentials on the box. The user runs
  `git push -u origin claude/quality-records-cr0006-0009`.
- Worktrees under `.claude/worktrees/`, both safe to remove with
  `git worktree remove --force <path>` and to delete their branches:
  - `agent-aee090313522fc4b9` (CR-0012 code, **already merged** at `4eb10dd`);
  - `agent-a76d961e8325661ab` (CR-0015 attempt; **no commits, no useful
    work**).
- Hardware before the stop: NVIDIA L40S, driver 560.35.03, torch
  2.6.0+cu124, 4 vCPU, 30 GB RAM, about 20 GB disk free.

## 2. Status of every CR
| CR | status | what remains |
|---|---|---|
| CR-0007 | CLOSED | — |
| CR-0008 | implemented | — |
| CR-0010 | implemented | — |
| CR-0011 | applied (CLAUDE.md §1 amendments) | — |
| CR-0014 | implemented | — |
| CR-0016 | implemented | — |
| **CR-0012** | code merged (`4eb10dd`, follow-ups `df83c27`); **deliverable 6 real run done** (`1bc2df6`): 6,232 positives (ME 3,660 / NH 1,079 / VT 1,493), 18/18 CR-0013 GATEs pass | **Deliverable 6 test plan** (§3.1); **deliverable 7** (delete `data/pipeline/block_assignments_{ME,NH,VT}.csv`; backed up in `grouse_backup/CR-0012/`); **deliverable 8** bookkeeping (§3.2); tick 6–8; status → IMPLEMENTED |
| **CR-0013** | deliverables 2–6 done; OBS calibrated (`docs/quality/acceptance_split_obs.json`) | Deliverables **0** (BUG-0033 and PA-0021 exist; verify and tick), **1** (evidence scripts; `docs/quality/evidence/CR-0007-r7/` has 9 files; verify against § Attacks and tick), **2a** (PA-0021 sweep; may file BUGs) |
| **CR-0009** | APPROVED v5.2; deliverables 1, 2, 3, 5 done; 4 satisfied (CR-0012 deliverable 6 passed, CR-0014 landed) | **Retrain from scratch** (§3.3), then deliverables 7–12 |
| **CR-0015** | APPROVED v2.2; deliverable 1 (interim guard, U7) done | Deliverables 2–9. Nothing was kept from the stopped attempt (§3.4) |

Open-issue tracker: `docs/quality/CR-0007-0008-OPEN-ISSUES.md`. Several
LOW items have owners there. None of them block.

## 3. Next steps, in order (run independent ones in parallel)

### 3.1 CR-0012 deliverable 6 test plan (scratch only)
See CR-0012 § Test plan:
- a second run is byte-identical;
- the order test (permuted input CSVs, rasters symlinked);
- the standing checks refuse the pre-CR backup and `(64, 8, True)`;
- a positives-only run is refused;
- both guards fire;
- import smoke;
- `smoke_test_training.py`.

**Never write to the real `data/`.** Use a scratch tree whose `data/`
holds copied CSVs and symlinked rasters and county zip, run the scripts
with cwd set to that tree, and first check that no output path is a
symlink. Write `docs/quality/evidence/CR-0012-d6/test_plan.txt`, then
commit it with `git add -f`, because `.gitignore` is `*`.

### 3.2 CR-0012 deliverable 8 bookkeeping (docs only)
- **New BUG-0049** for pre-CR `generate_negatives.py:153`. Quote it from
  `git show 3230262:generate_negatives.py`. Include the recurrence review
  against PA-0011. If a new PA follows, it is **PA-0027**.
- **BUG-0027:** FIXED, closing after CR-0009.
- **BUG-0029:** the positive side is fixed and the bug stays open for
  CR-0015.
- **Swept? cells:** PA-0018 (enforced by CR-0013's gates plus the standing
  check) and PA-0023 (300 m buffer against all sightings, pool step 6).
- **BUG-0031:** check its status now that the guards exist.
- **Tracker** items.
- Edit `BUG_LOG.md` rows only by exact whole-line replacement, because
  rows contain `\|`. Only one agent edits `BUG_LOG.md` or
  `PREVENTIVE_ACTIONS.md` at a time.

### 3.3 CR-0009 retrain (the long pole)
Preconditions, checked on the new instance:
```
cd /home/ec2-user/grouse2
git status --short | grep -v '^??'          # must be empty
python -c "import acceptance_split as a; a.standing_checks(64,0,False)"   # must not raise
ls grouse_cr0009.pth* 2>/dev/null           # must be empty
test ! -e docs/quality/evidence/CR-0009/retrain/metrics.csv
nvidia-smi; nproc
```
The standing check re-verifies the acceptance record,
`data/pipeline/acceptance_record.json`. Its sha256 at the handoff was
`66d63e1d…`, written by `--calibrate` at 13:11:59 UTC.

Record the evidence, then run the pinned command in
`docs/quality/evidence/CR-0009/retrain/argv.txt`. That is CR-0009 § The
change 1, `--seed 0`, 10 epochs, per the user: **do not run 50 epochs**.
```
E=docs/quality/evidence/CR-0009/retrain
git rev-parse HEAD > $E/git_head.txt; git status --porcelain > $E/git_status_porcelain.txt
sha256sum data/pipeline/acceptance_record.json docs/quality/acceptance_split.json > $E/acceptance_at_start.sha256
nvidia-smi --query-gpu=name,driver_version --format=csv > $E/hardware.txt; nproc >> $E/hardware.txt
date -u +%FT%TZ > $E/started_utc.txt
setsid nohup $(cat $E/argv.txt) > $E/train.log 2>&1 < /dev/null &
```
Keep other CPU-heavy work light while it runs.

Add one line to the CR-0009 review log: the retrain ran on the new
instance type. That is a hardware change, not a recipe change. The L40S
run was aborted at epoch 1, with evidence under
`retrain/aborted_*` and `retrain/train_aborted_instance_change.log`.
`retrain/acceptance_record_note.txt` describes the aborted start; it is
superseded by the new `acceptance_at_start.sha256`.

After training (CR-0009 deliverables 6–12):
1. **Evidence (deliverable 6):**
   - `sha256sum grouse_cr0009.pth`;
   - copy TensorBoard's `run/command` and `run/args` text from
     `runs/<timestamp>_grouse_cr0009/` into `$E`.
2. **Calibration (deliverable 7):** `python calibrate.py --model
   grouse_cr0009.pth`, then confirm `model_path` in
   `data/calibration/calibration.json`.
3. **Validation baseline (deliverable 8):** record it, with the
   not-comparable statement.
4. **Maps (deliverable 9):** see § Symptom acceptance and § Stale markers.
   - Run `symptom_check.py`, in-process, on the new model and calibration
     against `docs/quality/evidence/CR-0009/baseline/`.
   - Regenerate the NH, ME and VT maps with `predict.py` at their existing
     extent and stride. This is allowed now: `data/predictions` is backed
     up in `grouse_backup/CR-0009/`.
   - Item 4 is the whole-ME map, about 36 min in-process.
5. **Bookkeeping (deliverable 10):**
   - BUG-0022 and BUG-0027 close.
   - BUG-0029 closes only after CR-0015 deliverable 7b.
6. **Changelog (deliverable 11):** the `CHANGELOG.md` entry, which says
   pre-CR metrics are not comparable and adds the BUG-0034 note.
7. **Stale markers (deliverable 12):** remove a marker only where every
   file in its directory has been regenerated. `data/maps` stays.

### 3.4 CR-0015 remainder (separate worktree, then review and merge)
Deliverables 2–9 as written in the CR:
- BUG-0032 and BUG-0042;
- the PA-0006 re-sweep by mechanism;
- `regions.to_5070` and `block_split`, which must stay byte-identical,
  proven in a scratch tree against `split_manifest.json`;
- the sampler changes (§2–§3), with U1–U6 and L1 clean;
- V1–V3 with `GROUSE_REQUIRE_REAL_DATA=1`;
- remove the guard and U7, only after 7b.

Two rules for the implementer:
- It must not write to the main tree's `data/`.
- It writes proposed `BUG_LOG` and PA rows to
  `docs/quality/evidence/CR-0015-bookkeeping-rows.md` for the lead to
  apply.

Then run an independent code review with 2 reviewers, merge, re-run
`generate_negatives.py` and `acceptance_split.py` if deliverable 5
requires it, and check that B1 still passes.

If the retrain has already started when CR-0015 merges, merging does not
affect it. Re-running the pipeline rewrites the acceptance record,
though, so do it after the retrain has started or finished, never while
a retrain is recording its start evidence.

### 3.5 CR-0013 close-out
Verify deliverables 0 and 1, and run deliverable 2a, the PA-0021 sweep.
The sweep covers the acceptance tables of CR-0007..0013 and live-code
thresholds; each instance found gets its own BUG. Serialise it with
§3.2, since both edit `BUG_LOG` and PA. Then set status → IMPLEMENTED.

## 4. Reserved IDs
- **BUGs:**
  - BUG-0049: CR-0012 deliverable 8.
  - BUG-0032 and BUG-0042: CR-0015.
  - BUG-0050 and up: CR-0015 sweep findings, then CR-0013's 2a sweep
    (allocate in filing order; check `BUG_LOG.md` for the highest id
    first).
- **PAs:**
  - PA-0027: CR-0012 deliverable 8, if needed.
  - PA-0028 and PA-0029: CR-0015.
  - Next free after that: PA-0030.

## 5. Backups and evidence (do not delete)
| backup | contents |
|---|---|
| `/home/ec2-user/grouse_backup/CR-0010/` | 174 rasters |
| `/home/ec2-user/grouse_backup/CR-0014/` | 30 `road_dist` rasters |
| `/home/ec2-user/grouse_backup/CR-0007/` | pre-CR-0007 pipeline and negatives; manifest `docs/quality/evidence/CR-0007-backup-manifest.txt` |
| `/home/ec2-user/grouse_backup/CR-0012/` | pipeline and negatives just before the CR-0012 rebuild; manifest `docs/quality/evidence/CR-0012-backup-manifest.txt` |
| `/home/ec2-user/grouse_backup/CR-0009/` | predictions, calibration, all `*.pth*`; manifest `docs/quality/evidence/CR-0009/backup_SHA256SUMS` |

The CR-0009 baselines are in `docs/quality/evidence/CR-0009/baseline/` and
are verified with `sha256sum -c SHA256SUMS`.

## 6. Standing instructions from the user (also in auto-memory)
- **Run the cycle autonomously:** review → revise → approve → implement
  until every CR is implemented. Author plus two reviewer approvals
  counts as the user's sign-off. At a decision point, choose the option
  you would have recommended. Keep as many parallel workers running as
  possible.
- **Retrain at 10 epochs, not 50.**
- **Still surface to the user:** anything destructive, irreversible or
  outward-facing, such as pushing, deleting backups, or large compute
  beyond what a CR specifies.
- **Git practice:**
  - Commit messages end with
    `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - Evidence files need `git add -f`.
  - Never `git commit -a` while other agents edit shared files.
