# CR-0009 review log

History, verdicts and dispositions for CR-0009. The CR states only current
intent (`CLAUDE.md` §1.1).

## Where the history is
- v1–v3 text: v3 is the version in commit `52f8fb5` and earlier
  (`git show 52f8fb5:docs/quality/change-requests/CR-0009-retrain-and-revalidate.md`).
- v1 was written during the CR-0006 split. v2 added "what each check
  catches" and the pre-CR baseline sequencing; v3 revised § Symptom
  acceptance after review.
- v3 was put ON HOLD by the user (2026-09-30): the retrain and its
  validation will be carried out manually.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1–2 | v1–v2 | (recorded only as revisions; verdicts not preserved) | — | — |
| 3 | v3 | two reviewers | REJECT (both) | see "Known open defects at hold" below |
| 4 | v4 | — | not yet reviewed | — |

## Known open defects at hold (v3) — v4 dispositions
Verbatim list from v3's header, each with its v4 disposition.

| # | defect (v3) | v4 disposition |
|---|---|---|
| 1 | Item 1's ±5 pp exceedance gate fails the accepted baseline (`gap3.pth` post-fix: ME ≥0.8 = 10.24 %, NH = 4.88 %, gap 5.36 pp) | **Accept** — gate is now on the ME−NH ≥0.8 gap relative to the accepted baseline: ≤ 15 pp (baseline 5.36; constructed bimodal attack 40.1; pre-fix 62.8) |
| 2 | Item 2's 500 m and +0.15 gates have 6.2 % / 21.1 % false-fail rates under unchanged truth (bootstrap over the 8 pairs); conformant ≥ 534 m / ≥ 0.195 | **Accept** — gates set to 600 m and +0.20, above the conformant values; the bootstrap is re-run in `symptom_check.py` and its false-fail rate reported |
| 3 | Item 4 has no threshold and is not labelled an observation | **Accept** — labelled OBS; its output is the input to the `predict.py` validity-mask decision |
| 4 | Retrain unspecified; "the baseline run" unrecoverable (`bce.pth`/`gap3.pth` identical configs, different results) | **Accept** — exact command pinned (§ The change); compared against **both** checkpoints, neither called "the baseline" |
| 5 | § Baselines factually wrong: `predict.py` never calls `build_datasets`; the baseline that expires is item 3's point set | **Accept** — § Baselines rewritten |
| 6 | Items 2–3 need source edits to untracked `inv_matched_pairs.py`, `inv_points_auc.py` | **Accept** — replaced by a committed `symptom_check.py` (deliverable, may be written before approval under §1.1) |
| 7 | Catch/blind-to table contradicts the items | **Accept** — table rebuilt from the items |
| 8 | Whole-ME map cost unbudgeted | **Accept** — stride 8 named (~36 min) |
| 9 | A uniform level shift passes every gate | **Accept as stated limit** — NH and ME means reported beside the pre-fix and post-fix values; no gate can distinguish a legitimate level change from a shift without ground truth |

## Other changes in v4 (not from review)
- Dependencies updated for the CR-0007 split (CR-0007 / CR-0012 /
  CR-0013), CR-0010 and CR-0008 (implemented), CR-0014 (road_dist).
- No escape mode (user decision 2026-09-30): extra baselines are captured
  before CR-0012 lands.
- Disk: CR-0010 already purged the patch cache and owns the raster
  backup (9.46 GB, not "9.75 GB owned by CR-0008"); CR-0014 owns the
  `road_dist` backup.
- NH positives after CR-0007: 1,079 (v3 said 1,116).
- `--missing-mask` required (CR-0010/CR-0008 legacy-checkpoint refusal).
- BUG-0033/PA-0021 dependency removed: item 1 stands on its own
  constructed attack.

## Author sign-off
Pending.

## v4 amendment (2026-09-30, uncommitted with v4)
BUG-0039 (CR-0013's PA-0021 sweep): symptom items 1a/1b/2a/2b were GATEs
with thresholds from one or two observed runs or an 8-pair bootstrap and
no retrain-seed null. **User decision: demoted to OBS.** Promotion needs
≥ 50 retrain seeds and a CR.

## Hold lifted (2026-09-30)
The user pre-authorised carrying every CR through review and
implementation (author + two reviewer approvals count as sign-off). This
machine has an NVIDIA L40S (46 GB), so the retrain runs here rather than
manually. v4 committed at `6bb2e2d` for its first review; symptom_check.py
(deliverable 1) being written in parallel.

## Round 4 (v4, first review) — reviewer A (correctness): REJECT
- **B1 BLOCKING:** the pinned command uses train.py defaults (focal loss,
  30 epochs, dropout 0.2, wd 1e-4, no dynamic dropout, year gap 2), but
  the baselines were trained with (`~/.bash_history`) gap3: `--epochs 12
  --loss an_full --embed-dropout 0.1 --dropout 0.4 --dynamic-dropout
  --dynamic-dropout-step 0.05 --dynamic-dropout-max 0.9 --weight-decay 1e-3
  --max-year-gap 3`, seed 0; bce: same with `--epochs 50`, year gap 2. ~8
  hyperparameters differ → recipe confounded with data. Checkpoint config
  holds architecture + loss only (the "recorded in the checkpoint" claim is
  false); gap3/bce differ by epochs and year gap (explicable). Fix: pin the
  bce recipe + seed + save-path; record full argv in evidence.
- M1 MAJOR: baselines "before CR-0012" not concrete and partly late (CR-0007
  changed item 3's point set); name artefacts, snapshot (CR-0007 backup
  and/or current), location; CR-0012 D0 circular.
- M2 MAJOR: item 3's 0.6918 is NH-side (41 pos / 11 neg); all-points AUC
  0.7570 → 0.7273; mostly training points — report by split and side.
- M3 MAJOR: symptom_check.py unspecified (side assignment via TIGER 2023
  counties, nodata, calibrated vs raw, frozen pairs); require it to
  reproduce 0.5400 / 0.5089 / 5.36 pp / +203 m on current rasters (feasible:
  NH-box pixels unchanged vs backups).
- M4 MAJOR: map provenance — predict.py always overwrites
  `data/predictions/NH_custom_suitability.tif`; score in-process or copy+hash;
  record checkpoint sha256 and calibration model_path.
- M5 MAJOR: PA-0021(f) fields missing on OBS rows.
- M6 MAJOR: BUG-0034 (open acquisition-year asymmetry) makes "one retrain →
  comparable numbers" false; stated limit.
- D1–D4 MEDIUM: disk estimate (~2 GB per run; drop the backup-deletion
  step); stated limit 3 wrong (2a is a raster property; road-blind model
  passes 2b); 2a references are NH grid; pin `calibrate.py --model`, note
  its fixed train_year_gap=2.
- L1–L5 LOW: header; item 4 command; counts 6,232; back up data/predictions;
  --missing-mask already default.

## Round 4 (v4, first review) — reviewer B (implementability): REJECT
- **B1 BLOCKING** (same as A's B1): `--loss` defaults to focal; both
  baselines are `an_full`, `an_pos_weight=1.0`; checkpoint config holds
  architecture + loss only. Pin the loss; record `vars(args)` + git SHA.
- M1: item 3's reference is NH-side (n=52); pooling regions today
  double-counts overlap records (97/16 vs 55/11); deliverable 2 must
  enumerate measurements, location + SHA256SUMS + re-verify (CR-0012 D0),
  which point set post-retrain uses, whether gap3/bce scores are captured,
  and that capture may run before approval; items 1, 2, 4 depend only on
  rasters + checkpoints (CR-0012 doesn't change them).
- M2: symptom_check.py spec — NH grid for item 2; matching criteria
  (identical evt/evh/evc/sclass/nlcd; |dch|≤2, |dcc|≤5, |dtcc|≤5; NPAIRS 8;
  SEED 0); calibration from the new calibration.json; old_road_dist path;
  predict output path; item 4 "per region"; unit-test assertions; 2a is
  raster-only; drop "false-fail rate" for OBS.
- M3: BUG-0029 closure must be conditional on CR-0015 (its d9 rule).
- M4: stale markers: remove only when every file in the directory is
  regenerated or deleted; list them (VT_custom_suitability, data/maps).
- M5: cite CR-0013's acceptance_record.json and its config sha256.
- M6: v3 dispositions #1, #2, #7 not landed / stale; no operative
  locations (PA-0024(a)).
- MEDIUM: disk (~1.5 GB per run; drop the backup-deletion step; 21 GB
  free); stale header/log; pin `calibrate.py --model`; bookkeeping
  (BUG-0039 closure, PA-0021 Swept?, PA-0016 cell content).
- LOW: `:437`; counts 6,232; 62.9 pp; bce ≥0.8 cells (45.68/0.11,
  0.18/0.10 %); item 5 must be GATE or OBS; A5 justification; source for
  "40.1 pp"; backups of pipeline/negatives irrelevant.

