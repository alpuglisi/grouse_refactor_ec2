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
  validation will be carried out manually. The hold was lifted the same
  day (§ Hold lifted).
- v4 text: commit `6bb2e2d`. v5: the working-tree revision after round 4.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1–2 | v1–v2 | (recorded only as revisions; verdicts not preserved) | — | — |
| 3 | v3 | two reviewers | REJECT (both) | see "Known open defects at hold" below |
| 4 | v4 | A (correctness) | REJECT | B1 (recipe/loss mismatch) |
| 4 | v4 | B (implementability) | REJECT | B1 (same) |
| 5 | v5 | A, B | pending | — |

## Known open defects at hold (v3) — v4 dispositions
Verbatim list from v3's header, each with its v4 disposition.

| # | defect (v3) | v4 disposition |
|---|---|---|
| 1 | Item 1's ±5 pp exceedance gate fails the accepted baseline (`gap3.pth` post-fix: ME ≥0.8 = 10.24 %, NH = 4.88 %, gap 5.36 pp) | **Accept** — gate is now on the ME−NH ≥0.8 gap relative to the accepted baseline: ≤ 15 pp (baseline 5.36; constructed bimodal attack 40.1; pre-fix 62.8) — **superseded** by the BUG-0039 amendment (row is OBS; 15 pp is an "investigate if" reference) and v5 (62.9 pp; 40.1 pp sourced as a hypothetical, "P = 0.45" dropped): CR v5 § Symptom acceptance row 1b |
| 2 | Item 2's 500 m and +0.15 gates have 6.2 % / 21.1 % false-fail rates under unchanged truth (bootstrap over the 8 pairs); conformant ≥ 534 m / ≥ 0.195 | **Accept** — gates set to 600 m and +0.20, above the conformant values; the bootstrap is re-run in `symptom_check.py` and its false-fail rate reported — **superseded**: rows are OBS (BUG-0039); v5 reports the bootstrap as pair-sampling spread only, no false-fail rate, and 2a has none (deterministic raster read): CR v5 § Symptom acceptance, PA-0021(f) table rows 2a/2b |
| 3 | Item 4 has no threshold and is not labelled an observation | **Accept** — labelled OBS; its output is the input to the `predict.py` validity-mask decision |
| 4 | Retrain unspecified; "the baseline run" unrecoverable (`bce.pth`/`gap3.pth` identical configs, different results) | **Accept** — exact command pinned (§ The change); compared against **both** checkpoints, neither called "the baseline" — **superseded** by v5: v4's command used defaults (round 4 B1); the recipe is recovered from `~/.bash_history` and pinned; gap3/bce differ by epochs and year gap, which explains their results: CR v5 § The change 1, § Baselines |
| 5 | § Baselines factually wrong: `predict.py` never calls `build_datasets`; the baseline that expires is item 3's point set | **Accept** — § Baselines rewritten |
| 6 | Items 2–3 need source edits to untracked `inv_matched_pairs.py`, `inv_points_auc.py` | **Accept** — replaced by a committed `symptom_check.py` (deliverable, may be written before approval under §1.1) |
| 7 | Catch/blind-to table contradicts the items | **Accept** — table rebuilt from the items — **superseded**: v4's third stated limit was itself wrong (round 4 A-D2); v5 § Stated limits |
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
- NH positives after CR-0007: 1,079 (v3 said 1,116). **Superseded (v5):**
  the training point files change at CR-0012, not CR-0007; counts cited
  from CR-0012 § Impact (6,232).
- `--missing-mask` required (CR-0010/CR-0008 legacy-checkpoint refusal).
  **Superseded (v5):** it is the default (round 4 A-L5); stated as such.
- BUG-0033/PA-0021 dependency removed: item 1 stands on its own
  constructed attack.

## Author sign-off
Pending (v5).

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


## v5 (2026-09-30) — decisions
**Round count (§1.2 A2).** v5 goes to a fifth round. The open BLOCKING
item after round 4 (recipe) was escalated and decided by the user and the
lead author under the user's standing authorisation, which satisfies the
"escalate before a further round" rule. Round 5 is bounded: prior BLOCKING
and MAJOR items, and changed text.

Decisions applied (not re-asked):
- **User (2026-09-30):** retrain for **10 epochs**, not 50, with the shared
  `bce.pth`/`gap3.pth` recipe (`--loss an_full`, `an_pos_weight` 1.0,
  embed-dropout 0.1, dropout 0.4, dynamic dropout step 0.05 max 0.9,
  weight-decay 1e-3, default year gap 2), `--seed 42 --save-path
  grouse_cr0009.pth`. Neither baseline matches on epochs; gap3 (12) is the
  nearer on length. Replaces the lead author's earlier 50-epoch choice.
- **Lead author:** the retrain runs on this machine (L40S); record full
  `vars(args)`, argv and git SHA; compare against both checkpoints.
- **Lead author:** baseline capture (deliverable 2) runs before approval
  as a read-only measurement under `docs/quality/evidence/CR-0009/` —
  an explicit extension of §1.1 A3.
- **Lead author:** disk — no raster-backup deletion; back up
  `data/predictions` and `data/calibration`.
- **Lead author:** stale markers removed per directory only when every
  file is regenerated or deleted.
- **Lead author:** BUG-0029 closure conditional on CR-0015 deliverable 7b.
- **Lead author:** item 3 references by split and side; BUG-0034 as a
  stated limit; cite CR-0013's `acceptance_record.json` and config sha256.

**Verified against the system while revising** (§1.3):
- `~/.bash_history` lines 990–992: the recipe above; `bce.pth` line 990
  (50 epochs, year gap 2), `gap3.pth` line 992 (12 epochs,
  `--max-year-gap 3`); both `--compile`, no `--seed` (default 0).
- `train.py:713` `--an-pos-weight` default auto (1.0 under stratified
  batching); `:655`/`:656`/`:700`/`:701` defaults 0.2/0.0/1e-4/focal;
  `:437` save-path default; `vars(args)` is recorded only in TensorBoard
  text (`:1087–1090`).
- `calibrate.py:356` calls `build_datasets` without `train_year_gap`
  (default 2, `train.py:241`).
- `data/pipeline/{thinned,train,val}_positives_*` and all of
  `data/negatives/` are byte-identical to `/home/ec2-user/grouse_backup/CR-0007/`;
  only `evaluated_sightings`, `envelope_metrics`, `nonveg_flagged` differ.
  So item 3's point set was **not** changed by CR-0007 (reviewer A M1's
  "partly late" does not hold on disk; tracker item 0007 R8 B10 agrees);
  v5 captures both snapshots anyway.
- In-box counts today: NH files 55 pos / 11 neg; ME files 42 / 5; pooled
  97 / 16 (reviewer B M1 confirmed).
- Item 3's 0.7570 / 0.7273 / 0.6918 are `bce.pth` maps
  (`inv_figure.py:11–12`: `inv_before/before_cal.tif`,
  `inv_after/after_cal.tif`).
- "40.1 pp": only source is `inv_reviewG_r2_cr9.py:10`, a stated
  hypothetical (ME 45.0 %, NH 4.9 %); no computation supports "P = 0.45".
- 21 GB free; `data/cache` empty; `data/predictions` 468 KB,
  `data/calibration` 112 KB, `*.pth*` 1.3 GB.
- `data/maps/` PNGs are `analyze_grouse.py` outputs (mtime 11:42, after
  the 10:20 marker), not model outputs.

## v5 dispositions (round 4)
Operative locations are in CR v5 (PA-0024(a)). "Superseded" marks on the
v3/v4 tables above point here.

| id | severity | finding (short) | disposition | operative location |
|---|---|---|---|---|
| A-B1 | BLOCKING | retrain uses defaults, not the baselines' recipe; "recorded in the checkpoint" false | **Accepted, revised** — recipe pinned from `~/.bash_history`; 10 epochs by user decision; argv, `vars(args)`, SHA recorded; false claim removed | § The change 1 |
| B-B1 | BLOCKING | same; loss defaults to focal | **Accepted, revised** — `--loss an_full --an-pos-weight 1.0` pinned | § The change 1 |
| A-M1 | MAJOR | baselines "before CR-0012" not concrete; CR-0007 changed item 3's set; CR-0012 D0 circular | **Accepted, revised** — artefacts, snapshots (S0 backup, S1 current), location and SHA256SUMS named; capture runs before approval, which removes the circularity. "CR-0007 changed item 3's set": checked, not so on disk (log § v5 decisions); both snapshots captured regardless | § Baselines; Deliverables 1–2 |
| A-M2 | MAJOR | 0.6918 is NH-side; all-points 0.7570 → 0.7273; mostly training points | **Accepted, revised** — references by side, split and all points; training-point caveat | § Symptom acceptance row 3, PA-0021(f) row 3, § Stated limits |
| A-M3 | MAJOR | symptom_check.py unspecified; must reproduce 0.5400 / 0.5089 / 5.36 pp / +203 m | **Accepted, revised** — full spec; R is an exact GATE on the instrument | § symptom_check.py |
| A-M4 | MAJOR | map provenance: `predict.py` overwrites `NH_custom_suitability.tif` | **Accepted, revised** — copy + sha256 or in-process scoring, plus a re-score guard; checkpoint sha256 and `model_path` recorded | § symptom_check.py (map provenance); § The change 1–2 |
| A-M5 | MAJOR | PA-0021(f) fields missing | **Accepted, revised** | § Symptom acceptance, PA-0021(f) table |
| A-M6 | MAJOR | BUG-0034 makes "one retrain → comparable numbers" false | **Accepted, revised** — Why now reworded; stated limit; CHANGELOG note | § Why now; § Stated limits; Deliverables 8, 11 |
| A-D1 | MEDIUM | disk estimate; drop backup deletion | **Accepted, revised** | § Disk |
| A-D2 | MEDIUM | stated limit 3 wrong (2a raster-only; road-blind passes 2b) | **Accepted, revised** | § Stated limits |
| A-D3 | MEDIUM | 2a references are NH grid | **Accepted, revised** — NH grid | § Symptom acceptance row 2a; § symptom_check.py |
| A-D4 | MEDIUM | pin `calibrate.py --model`; fixed train_year_gap=2 | **Accepted, revised** | § The change 2 |
| A-L1 | LOW | header stale | **Accepted, revised** | Status line |
| A-L2 | LOW | item 4 command | **Accepted, revised** | § Symptom acceptance (maps) |
| A-L3 | LOW | counts 6,232 | **Accepted, revised** — cited from CR-0012 once | § Impact |
| A-L4 | LOW | back up `data/predictions` | **Accepted, revised** | § Disk |
| A-L5 | LOW | `--missing-mask` is the default | **Accepted, revised** — flag dropped, default stated | § The change 1 |
| B-M1 | MAJOR | item 3 reference NH-side n=52; pooling double-counts (97/16 vs 55/11); deliverable 2 must enumerate, SHA256SUMS, re-verify, post-retrain set, gap3/bce scores, may run before approval; items 1, 2, 4 raster+checkpoint only | **Accepted, revised** | § Baselines 1–4; PA-0021(f) row 3 |
| B-M2 | MAJOR | symptom_check spec: NH grid, matching criteria, calibration source, old_road_dist path, predict output path, item 4 per region, test assertions, 2a raster-only, no false-fail rate | **Accepted, revised** — `old_road_dist/` no longer read (R uses current rasters; pre-fix +4,255 m is quoted, not reproduced); item 4 is the ME region only (others out of scope) | § symptom_check.py; § Out of scope |
| B-M3 | MAJOR | BUG-0029 closure conditional on CR-0015 | **Accepted, revised** | Deliverable 10 |
| B-M4 | MAJOR | stale markers: only when all files regenerated/deleted; list them | **Accepted, revised** — ME/VT custom maps regenerated at their own extent (cheap); `data/maps/` stays flagged, ownership tracked | § Stale markers |
| B-M5 | MAJOR | cite `acceptance_record.json` and config sha256 | **Accepted, revised** | § The change 1 (recorded evidence) |
| B-M6 | MAJOR | v3 dispositions #1, #2, #7 stale; no operative locations | **Accepted, revised** — marked superseded with locations; this table gives locations | v3/v4 table above; this table |
| B-D1 | MEDIUM | disk ~1.5 GB, 21 GB free, drop deletion | **Accepted, revised** | § Disk |
| B-D2 | MEDIUM | stale header/log | **Accepted, revised** | Status line; round table |
| B-D3 | MEDIUM | pin `calibrate.py --model` | **Accepted, revised** (as A-D4) | § The change 2 |
| B-D4 | MEDIUM | bookkeeping: BUG-0039 closure, PA-0021 Swept?, PA-0016 cell content | **Accepted, revised** | Deliverable 10 |
| B-L1 | LOW | `:437` | **Accepted, revised** | § The change 1 |
| B-L2 | LOW | counts 6,232 | **Accepted, revised** (as A-L3) | § Impact |
| B-L3 | LOW | 62.9 pp | **Accepted, revised** | § Why now table |
| B-L4 | LOW | bce ≥0.8 cells | **Accepted, revised** | § Why now table |
| B-L5 | LOW | item 5 GATE or OBS | **Accepted, revised** — OBS, not distributional | § Symptom acceptance row 5 |
| B-L6 | LOW | A5 justification | **Accepted, revised** | § One change per CR |
| B-L7 | LOW | source for "40.1 pp" | **Accepted, revised** — hypothetical, `inv_reviewG_r2_cr9.py:10`; "P = 0.45" removed | § Symptom acceptance row 1b |
| B-L8 | LOW | pipeline/negatives backups irrelevant | **Accepted, revised** — dropped | § Disk |

MEDIUM/LOW items are also listed in `docs/quality/CR-0007-0008-OPEN-ISSUES.md`
(§ CR-0009 v5), owner CR-0009's author, for round-5 confirmation.
