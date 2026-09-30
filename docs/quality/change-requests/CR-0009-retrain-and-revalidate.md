# CR-0009: Retrain once on the rebuilt data, and prove the Errol map is still right

**Status: ON HOLD (2026-09-30, user decision) — the retrain and its
validation will be carried out manually. No further revision by this
session.** Nothing committed. All deliverables pending.
**Still gated on CR-0007 and CR-0008 both landing.**

> **Held with known open defects.** Two reviewers rejected the v3 text
> and their findings are NOT fixed. Anyone executing this manually should
> read them first — they are listed under "Known open defects at hold"
> immediately below. Several items in this document are wrong as written.

### Known open defects at hold
1. **Item 1's ±5 pp exceedance gate fails the accepted known-good
   baseline.** `gap3.pth` after the road_dist fix measures ME ≥0.8 =
   10.24 % vs NH ≥0.8 = 4.88 % — a **5.36 pp** gap. The gate as written
   rejects an outcome the project calls correct. Gate the gap *relative
   to that baseline*, not ME against NH in absolute terms.
2. **Item 2's gates are statistically unsound.** Bootstrapped from the
   8 recorded pairs: the 500 m road_dist gate has a **6.2 %** false-fail
   rate and the +0.15 probability gate **21.1 %**, under an unchanged
   truth. Conformant values would be ≥534 m and ≥0.195, and both should
   be re-derived over ≥50 seeds.
3. **Item 4 has no threshold and is not labelled an observation**, while
   being the only item covering the programme's largest user-visible
   change (47.23 % of the ME grid becoming NODATA).
4. **The retrain is unspecified** — no command, `--save-path`, seed,
   epochs or `--an-background`, and "the baseline run" is unrecoverable:
   `bce.pth` and `gap3.pth` carry byte-identical stored configs yet give
   post-fix `P(ME>NH)` of 0.5089 vs 0.5400.
5. **`§ Baselines` is factually wrong.** It claims `predict.py` cannot be
   run after CR-0007 lands; `predict.py` never calls `build_datasets`.
   The baseline that genuinely expires is item 3's point set.
6. **Items 2 and 3 require source edits** to `inv_matched_pairs.py`
   (hardcodes NH, `bce.pth`, `old_road_dist/`) and `inv_points_auc.py`
   (hardcodes `GrouseData()["NH"]`). Neither edit is a deliverable in any
   CR.
7. **The catch/blind-to table contradicts the items above it** — stale
   band, stale item-3 framing, stale 47.1 %.
8. **Whole-ME map cost is unbudgeted**: ~36 min at stride 8, ~38 h at
   stride 1. No stride is named.
9. **A uniform level shift still passes every gate** — a model scoring
   both sides high keeps the shares equal.

### Revision note (v1 → v2)
v1 was written during the CR-0006 split. v2 applies the rule this work
converged on after four acceptance-set failures:

> **Every acceptance invariant must be measured on at least one
> constructed pipeline that is wrong in the way that invariant exists to
> catch — not only on the current data and the intended pipeline.**

For this CR that means saying, for each check, **what wrong outcome it
would catch**. v1 listed the right measurements but never stated what
any of them would fail on, which is how a check that cannot fail gets
shipped as a gate. v2 also fixes a sequencing defect: v1 required
pre-CR baselines that CR-0007's assertions make unobtainable.

**Supersedes part of CR-0006** (see CR-0007's header). This CR carries
the single retrain, the disk plan, and — the item CR-0006 lost between
revisions — the end-to-end check that the originally reported symptom is
still fixed.

## Scope
Retrain once from scratch on the data rebuilt by CR-0007 and CR-0008,
refit calibration, and record both the new validation baseline and a
direct re-measurement of the user-reported map symptom.

## Why now
One retrain, after both data CRs, so there is one set of comparable
numbers. Retraining after either one alone would produce metrics that
cannot be compared with anything, which is the whole reason the three
CRs share a single retrain.

**The reported symptom is already fixed, and this CR's job is to prove
it stays fixed.** The user reported that a suitability map around Errol
ranked the Maine side far above the New Hampshire side. `bf8d31a` fixed
it, measured with the unmodified checkpoints on the user's exact box:

| map | ME mean | NH mean | P(ME pixel > NH pixel) |
|---|---|---|---|
| `gap3.pth` before | 0.7949 | 0.6289 | **0.8513** |
| `gap3.pth` after | 0.6333 | 0.6277 | **0.5400** |
| `bce.pth` before | 0.6887 | 0.4228 | **0.8235** |
| `bce.pth` after | 0.4217 | 0.4220 | **0.5089** |

Everything CR-0007 and CR-0008 change can move those numbers: the
retrain replaces the model; CR-0007 partitions the background
assumed-negatives, changes negative weighting through the availability
clip, and **halves NH's positives (2,244 → 1,116)**; CR-0008 makes ME
`road_dist` 47.1 % NODATA. None of CR-0007's or CR-0008's acceptance
criteria look at the map. Without this CR, the record would read
"CR-0006 fixed the Errol map" — unverified, and closing BUG-0022 that
way would close the bug that produced PA-0016 by doing what PA-0016
forbids.

## The change
1. **Retrain from scratch**, not `--resume`. **`--save-path` must be a
   new file**: its default is `grouse_single_best.pth`
   (`train.py:436`), so accepting the default overwrites an existing
   checkpoint. Same architecture, loss and hyperparameters as the
   baseline run — this CR changes data only, and mixing in a model
   change would make the metrics uninterpretable.
2. **Refit calibration** (`calibrate.py`) for the new checkpoint.
   `data/calibration/calibration.json` currently records
   `model_path: gap3.pth`; after the retrain it belongs to nothing.
   Note `calibrate.py:351` calls `build_datasets`, so it executes
   CR-0007's assertions.
3. **Record the new validation baseline** and state plainly that it is
   not comparable to any pre-CR number.
4. **Re-measure the reported symptom** (§ Symptom acceptance).

## Baselines must be captured BEFORE CR-0007 lands
A sequencing defect in v1. CR-0007's assertions (a)–(d) hard-fail on
pre-CR data, so `predict.py`, `calibrate.py` and `bench_pipeline.py`
cannot be run against it afterwards without CR-0007's pre-CR escape
mode. Two consequences:

1. **The baselines this CR compares against are already recorded** in
   `INVESTIGATION_REPORT_errol_map.md` and reproduced below. They were
   measured on the unmodified checkpoints and do not need re-taking.
2. **Any additional pre-CR measurement must be taken before CR-0007
   lands, or through its escape mode with the escape recorded in the
   artifact.** An escaped run must never be mistaken for a clean one.

## § Symptom acceptance — the check CR-0006 dropped
Each item below states **what wrong outcome it catches**. A check that
cannot fail is not a gate.

Re-run the user's exact command on the retrained checkpoint:

```
python predict.py --region NH --model <new>.pth --bounds -71.25 44.70 -70.95 44.90
```

and record, in this CR:

1. **`inv_state_split.py`** — ME mean, NH mean, ME−NH,
   `P(ME pixel > NH pixel)`, **and the per-state ≥0.8 exceedance shares**.
   Gates: `P(ME>NH)` in **[0.44, 0.56]**, **and** `ME ≥0.8` share within
   **±5 pp of `NH ≥0.8`**.

   v2 banded only the rank statistic. A reviewer constructed a retrain
   with a bimodal Maine side — 45 % of ME pixels at 0.95, the rest below
   NH's minimum — giving `P(ME>NH) = 0.45`, **inside v2's band**, with a
   *negative* ME−NH mean that reads better than the accepted baseline,
   while `ME ≥0.8` = 45 % against `NH ≥0.8` ≈ 4.9 %. That is visually the
   reported complaint (67.9 % vs 5.1 % before the fix), passing every
   item. `P(ME>NH)` is Mann–Whitney and is blind to tail mass; the ≥0.8
   shares are the statistic closest to what the user actually sees, and
   `inv_state_split.py:41-43` already prints them.

   The band widened from [0.45, 0.55] because the **accepted** baseline
   sits at 0.5400 — one hundredth from failing. A gate that the known-good
   outcome barely passes is a gate that gets waived on first run.
2. **`inv_matched_pairs.py`** — ME−NH `road_dist` on matched-habitat
   pairs, gate **|ME−NH| ≤ 500 m** (was +4,255 m pre-fix, +203 m after);
   and ME−NH mean probability, gate **≤ +0.15** (currently +0.1078).

   **The script must be re-pointed first.** As written it hardcodes
   `GrouseData()["NH"]` (`:25`), `"bce.pth"` (`:29`) and
   `old_road_dist/NH_2025_road_dist.tif` (`:77`) — and CR-0008 does not
   regenerate NH `road_dist`. So v2's item 2 read two files nothing in
   this programme touches and would have reproduced +203 m regardless of
   the retrain. It must run on the **ME grid** and the **new
   checkpoint**. v2's claim that it "catches a retrain that silently
   reused the old rasters" was false.
3. **`inv_points_auc.py`** — **reported, not gated.** NH-side in-box
   AUC alongside **0.6918**.

   v2 made this a gate. It cannot be one: the baseline rests on 41
   positives and **11** negatives, and the investigation records it as
   **identical to four decimals before and after** the fix that mattered
   — no power and no direction. v2 also said CR-0007 "fixes that
   asymmetry": it does not. CR-0007 *removes* the box's 14 ME positives
   from the NH region rather than supplying ME negatives, after which the
   all-points and NH-side AUCs coincide and "report both" is vacuous. The
   asymmetry is BUG-0029's, and fixing support globally cannot guarantee
   negatives land in one 0.3°×0.2° box. The script also hardcodes
   `GrouseData()["NH"]` (`:15`) and must be re-pointed to pool all three
   regions.
4. **A whole-ME-region map**, not the Errol box. Report the score
   distribution, the ≥0.8 share and the blanked/degraded pixel fraction
   **separately inside and outside US coverage**, per region.

   v2 asked for "the same three statistics" on the Errol box. Measured:
   that box contains **0 pixels** outside TIGER-2023 coverage and **0**
   NLCD-invalid pixels, in *both* the ME and NH grids. So v2's item 4 —
   whose entire stated purpose was to measure the consequence of ME
   `road_dist` becoming **47.23 %** NODATA — observed none of it, and
   neither did items 1–3, which use the same box. This is the measurement
   CR-0008 §"Impact" defers to "a future decision" about `predict.py`'s
   validity mask; **it is owned here**, and its output is that decision's
   input.
5. **A statement, in the record, that BUG-0023's symptom was already
   fixed by `bf8d31a`** and that this CR verifies it survived the
   rebuild. BUG-0022 is closed only after 1–4 are recorded.

**What each catches, and what it does not:**

| check | catches | blind to |
|---|---|---|
| 1. `P(ME>NH)` in [0.45, 0.55] | any return of the reported symptom — the pre-fix values were 0.8235 / 0.8513, so the band has ~6× separation | a uniform level shift affecting both sides equally |
| 2. matched-pair `road_dist` ≈ +203 m | a `road_dist` regression from CR-0008's ME/VT regeneration or a vintage mismatch; pre-fix was +4,255 m | anything not expressed through `road_dist` |
| 3. NH-side in-box AUC vs 0.6918 | degradation from NH's halved dataset (CR-0007 drops NH positives 2,244 → 1,116) | ME-side quality, which had no negatives in-box pre-CR |
| 4. ME-region map statistics | the consequence of ME `road_dist` becoming 47.1 % NODATA — currently asserted, never measured | — |
| 5. provenance statement | the record reading "CR-0009 fixed the Errol map" when `bf8d31a` did | — |

**Deliberately-broken cases these were calibrated against:** a model
that ignores `road_dist` entirely would still pass 1 (both sides move
together) but fail 2; a model trained on a leaking split would pass 1–4
and is caught only by CR-0007's assertions, not here; and a retrain that
silently reused the old rasters would pass 1 and 3 but fail 2 and 4.
**No check here can detect a bad split** — that is CR-0007's job, and
this CR does not claim otherwise.

## § Disk
Measured. **The retrain does not fit without a purge.**

```
/                150 GB total, 135 GB used, 16 GB FREE (90%)
data/cache        28 GB = 206 patches_*.npy + 1 orphan .tmp6337 (361.9 MiB)
checkpoints       *.pth* = 12 files, 1.3 GB
```

`dataset._cache_key` (`:151-172`) hashes each resolved raster path **and
its mtime**, so CR-0008's regeneration kills every cache key; a new
cache is otherwise built alongside the dead 28 GB.

Ordered procedure:
1. **Back up first**, with checksums: `data/pipeline/` (24M),
   `data/negatives/` (27M), `data/calibration/` (108K), `*.pth*`
   (1.3G). CR-0008 owns the raster backup (9.75 GB).
2. **Then purge `data/cache/` entirely** (28 GB) — verified safe: it
   holds nothing but `patches_*` files, every writer is a patch cache
   (`train.py:459`, `calibrate.py:316`, `bench_pipeline.py:69`,
   `pretrain.py:137`, `diagnose_wetland.py:202`), and every key is dead
   once CR-0008 changes a raster mtime. This also discards
   `pretrain.py`'s cache, so SSL re-pretraining would pay a rebuild.
3. Retrain to a new `--save-path`. Refit calibration.
4. Run § Symptom acceptance. Record everything.

**Backup before purge, not after.** The reverse order frees space
earlier but destroys 28 GB before anything irreversible has happened, so
any abort pays a full rebuild for nothing. Backing up first leaves
~4.9 GB free during a checksum copy that writes nothing else, then
~32.9 GB after the purge.

**Rollback:** restore the backed-up trees, purge the cache again,
`git checkout`. With CR-0008's raster backup this restores the pre-CR
state exactly. **A lower validation number is never a rollback
trigger** — it is the expected, correct consequence of removing a 31 %
leak. Rollback is for a broken pipeline.

## Impact
- Every pre-CR metric — ~0.82 AUC, ~0.79 AP, the `0.811` best-rank
  figure — stops being comparable. `CHANGELOG.md` comparisons resting on
  them need a note.
- The new validation number **will be lower**, by construction.
- Existing checkpoints remain on disk and still run, provided
  `--save-path` is new.
- The training set is smaller and differently shaped: ≈6,230 pooled
  positives (from 8,365 rows), NH roughly halved.

## Risk level: **MEDIUM**
The code risk lives in CR-0007 and CR-0008; this CR's risk is compute,
disk and interpretation.

| risk | mitigation |
|---|---|
| A lower metric is read as a regression. | Stated in advance, in this CR and in `CHANGELOG.md`. The honest baseline is this CR's "after". |
| The retrain overwrites a checkpoint. | New `--save-path`, checked before launch; `*.pth*` backed up. |
| Disk exhaustion mid-run. | § Disk, measured, backup-then-purge. |
| The symptom regresses and nobody notices. | § Symptom acceptance, with a hard [0.45, 0.55] band and four baseline rows. |
| NH's halved dataset degrades NH predictions specifically. | Measured by § Symptom acceptance item 1 (NH mean) and item 3 (NH-side AUC), not assumed. |

## Test plan
**Validatable here, after the retrain:** everything in § Symptom
acceptance; the new validation AUC/AP with CR-0007's assertions passing;
`smoke_test_training.py`; a calibration reliability curve.

**Cannot be validated here, and why:**
- **Whether the model is genuinely better than the pre-CR one.** There
  is no trustworthy pre-CR number to compare against — that is the point
  of BUG-0027. The new number is a new baseline, not an improvement
  claim, and this CR must not present it as one.
- **Field accuracy.** No independent ground truth beyond the sightings
  already in training.
- **Long-run stability** of the new split across seeds; one seed is run.

## Deliverables
- [ ] Confirm CR-0007 and CR-0008 are both landed and their acceptance
      tables recorded.
- [ ] **User go-ahead for compute.**
- [ ] Back up `data/pipeline/`, `data/negatives/`, `data/calibration/`,
      `*.pth*` with checksums.
- [ ] Purge `data/cache/`; record free space before and after.
- [ ] Retrain from scratch to a new `--save-path`.
- [ ] Refit calibration; confirm `calibration.json`'s `model_path`
      matches the new checkpoint.
- [ ] Record the new validation baseline, with an explicit
      not-comparable note.
- [ ] Run § Symptom acceptance items 1–5; record every number.
- [ ] Update BUG-0027 and BUG-0029 to closed; **close BUG-0022** citing
      § Symptom acceptance.
- [ ] `CHANGELOG.md`: pre-CR metrics not comparable to post-CR.
- [ ] Confirm **BUG-0033** and **PA-0021** are filed by CR-0007. This
      CR's item 1 exists because of PA-0021(a) — a reviewer constructed a
      retrain that passed every v2 item while reproducing the user's
      complaint.
- [ ] Update **PA-0016**'s Swept? cell: the symptom re-measurement was
      executed, and by which CR. Closing BUG-0022 without it discharges
      nothing.
- [ ] Independent review with every concern dispositioned.

## Out of scope
- Model architecture, loss, hyperparameters, and any tuning. Data only.
- SSL re-pretraining.
- **BUG-0028** (prediction outputs carry no provenance) — which is why
  § Symptom acceptance records the checkpoint by hand. The investigation
  that produced this work had to brute-force which checkpoint made the
  reported map, because the artifact carries none.

## § Review
Not yet reviewed. Author sign-off withheld.
