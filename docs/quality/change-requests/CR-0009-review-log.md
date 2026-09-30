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

