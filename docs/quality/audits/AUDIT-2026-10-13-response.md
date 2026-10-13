# Response to the third-party audit of 2026-10-13

**Audit:** "Skeptical Python and geospatial pipeline audit" of `main` at `472ba5e`. A copy is in `AUDIT-2026-10-13.md`.

**Method.** Four verifiers checked the 22 prioritized findings and the 6 follow-up items. Each read the cited code twice: at the audited commit and at the current branch head (`9b1f741`, which is `main` plus the CR-0032 to CR-0036 work). Each also re-derived the mechanism, and reproduced it with probes that call the project's real functions (by import or AST extraction, never by re-implementation). Each checked the QMS records for existing tracking, and judged exposure under the project's actual workflow. The current recipe is a fresh `train.py --loss an_full --dual-branch unet --early-attn --sched warm_restarts` run, with no `--init-from`, `--resume` or `--distill-from`. Full working notes are in `RESULT_G1.md` to `RESULT_G4.md` in this directory.

**Limits.** torch, the production rasters and EC2 were not available. Anything that needs model inference, GPU memory or real raster content was judged from the code, and is marked as such.

## 1. Summary

- **Accuracy of the audit.** It is careful and largely accurate on mechanism. Every one of the 22 findings describes real code behaviour. Its reproductions were re-run here and matched: AP 1.0 / 0.3655 / 0.5, the all-NaN and all-−9999 validity, the cache casts, the metrics header, ECE 0 on NaN, and the 15 m affine offset.
- **Severity.** It overstates severity. No finding is reached by the current workflow in the way its High rating implies. We rate **0 High, 10 Medium and 12 Low** (see the table).
- **One defect affects output today: #9.** The 2025 `tsd` raster, which prediction uses, cannot see 2025 cuts and is still tagged as covered.
- **Real, reachable defects with small or conditional impact:** #4 (AP ties, through `--select-by rank`), #7 (calibration applied despite a mismatch) and #21 (15 m north-west map offset).
- **Design limitations already known and tracked:** #5 (spatial leakage, D1–D4), #12 (derived-raster source years, planned CR-0038), #1 (BUG-0060) and #8 (BUG-0059).
- **The audit is partly wrong in three places:**
  - **#18:** TreeMap band resolution already refuses unknown bands.
  - **#11:** acceptance is deliberately limited to split inputs (PA-0048). The real gap is that checkpoints carry no raster manifest.
  - **#5:** the background sampler is in `train.py`, not `dataset.py`.
- **Verification found three things the audit missed:**
  - with NaN logits, `calibrate.fit_platt` silently writes an identity calibration;
  - `generate_road_distance.py` also writes its output to the live path;
  - our own QMS records (PA-0027 sweep row, BUG-0071 §7/§8) call the `raster_path` fallback "nearest-year", but it selects the **newest** valid year (`grouse_data.py:390-397`).

## 2. Finding-by-finding

Verdict key:
- **VALID:** real and reachable.
- **LATENT:** real, but not reached by the current workflow.
- **PARTLY:** some claims hold and some do not.
- **TRACKED:** already recorded.

| # | Finding | Verdict | Our severity (audit) | Existing record | Proposed disposition |
|---|---|---|---|---|---|
| 1 | Old checkpoints import validation labels | TRACKED, LATENT | Medium (High) | BUG-0060, PA-0029 | Planned CR for BUG-0060. Add the evaluation-path and SSL points and the #11 raster manifest. |
| 2 | `load()` omits same-shape config checks | PARTLY, LATENT | Low (High) | none | Trivial fix (compare the full stored config) plus a BUG with recurrence review against PA-0008 |
| 3 | Validity accepts missing data; fallback bypasses the year gate | PARTLY, LATENT | Medium (High) | mis-described in PA-0027 / BUG-0071 | Own CR: finite- and sentinel-aware validity, closest valid year, tolerance enforced on the resolved source. Plus a BUG that corrects the records. |
| 4 | AP rewards ties / constant predictor | VALID | Low (High) | none | Trivial fix (threshold-grouped AP) plus a tie-permutation test and a BUG |
| 5 | Split does not isolate patch footprints / selection | TRACKED, VALID | Medium (High) | D1–D4 (open issues 240–243); design-competition V2/V6 | No code change from this audit. Decide D1–D4. Leak measured below. |
| 6 | Resume uses `weights_only=False` | LATENT | Low (High) | none | Trivial fix (`weights_only=True`) plus a resume round-trip test on torch 2.6 and a BUG |
| 7 | Calibration mismatch warned, then applied | VALID | Medium (High) | none | Own CR: bind the calibration to the weight sha256 and `flip_tta`, refuse on mismatch, validate parameters |
| 8 | Missing-mask opt-out makes physical zeros | TRACKED, LATENT | Medium (High) | BUG-0059, PA-0028 | Planned CR for BUG-0059. Add the distillation-teacher guard, negative codes and Inf. |
| 9 | Missing disturbance years read as undisturbed | PARTLY, **VALID for 2025** | Medium (High) | the HYBRID_REPORT trigger fired but was not filed | BUG with recurrence review (BUG-0024, PA-0017, PA-0020), plus a CR to regenerate `tsd` with an honest coverage tag |
| 10 | Outputs written in place before success | VALID | Medium (High) | related: draft BUG-0028, BUG-0016 | Own CR: one staged-publish helper across about 9 writers, plus a BUG and a PA with sweep |
| 11 | Acceptance does not bind the full raster set | PARTLY | Medium (High) | BUG-0060, PA-0048 | Fold into BUG-0060's CR: resolved feature/year/path/sha256 manifest stored in each checkpoint |
| 12 | Derived filenames hide source years | VALID (known) | Medium (Medium) | ARCHITECTURE.md:267; planned CR-0038 | File a BUG now that points to CR-0038's source-year gate |
| 13 | TTA grouping inferred from length | TRACKED, LATENT | Low (Medium) | BUG-0062, PA-0030 | BUG-0062's planned CR; add the shuffle and `-O` points |
| 14 | Metrics CSV schema drift | TRACKED, LATENT | Low (Medium) | BUG-0061, PA-0030 | BUG-0061's trivial fix, also covering an existing empty file |
| 15 | Reliability on NaN gives ECE 0 | LATENT | Low (Medium) | none | Trivial non-finite guard plus a BUG. The sibling `fit_platt` NaN defect gets its own BUG. |
| 16 | Cache cast of non-finite / float values | LATENT | Low (Medium) | none | Trivial guard in `_load_or_build_cache` plus a BUG |
| 17 | Default workers/prefetch could exhaust RAM | PARTLY | Low (Medium) | none | Trivial fix: cap the default workers and print the queue estimate. Plus a BUG. |
| 18 | Unknown band accepted as a different band | PARTLY, LATENT | Low (Medium) | `collection_years` allowlisted in PA-0027 | Trivial fix: raise on an unrecognised band in `download_tcc_nlcd`. TreeMap part invalid. |
| 19 | Incomplete runs exit 0 | LATENT | Low (Medium) | none | Tracker item; optional exit-code fix in `download_rev` |
| 20 | Canadian land outside the template | TRACKED, VALID | Low (Medium) | BUG-0037 §6, CR-0014 | No change; closes when Canadian road data (NRN) is acquired |
| 21 | Output affine vs scored centre pixel | VALID | Medium (Medium) | BUG-0009 / BUG-0094 family, PA-0007 | Small CR (georeferencing change): add the +0.5, plus a pixel-centre test |
| 22 | `--compile` in predict compiles unused `forward` | VALID | Low (Medium) | noted in CHANGELOG, not logged | Trivial fix (compile `model.logits` as `train.py` does) plus a BUG |
| A1 | TreeMap VRT fills outside source with 0 | VALID, tiny exposure | Low | none | Trivial: mask pixels outside the source footprint, plus a BUG |
| A2 | `block_split` accepts empty, duplicate or invalid tables | LATENT | Low | none | Trivial validation plus a BUG |
| A3 | SSL saves with zero optimiser steps | LATENT | Low | none | Trivial refusal |
| A4 | Edge diagnostics treat missing values as edges | TRACKED | Low | BUG-0058 | As planned |
| A5 | Git dirty-state ignores failures | TRACKED | Low | BUG-0068 | As planned; also count untracked `.py` files |
| A6 | Source composition | TRACKED | n/a | CR-0021 residuals, BUG-0073 | No new item |

## 3. Notes on the most consequential items

**#9: 2025 cuts are invisible (affects output today).**
- The LANDFIRE disturbance record on disk runs from 1999 to 2024, 26 rasters with no gaps. The CR-0035 step-2 log confirms this.
- The 2025 `tsd` file therefore ages the 2024 record by one year. A stand cut in 2025 reads as undisturbed (30 years), yet the file is tagged `disturbance-intersection`.
- `predict.py` uses the latest vintage, so current maps understate fresh cuts. That is the opposite of what a grouse map needs.
- Training (2020–2024) is unaffected. The audit's before-record and gap branches are not reached, because all targets are 2016 or later and the record is complete.
- Related: a "2025" prediction actually combines tsd up to 2024, TreeMap 2022 and LANDFIRE 2024. It is effectively a 2022–2024 landscape.

**#5: spatial leakage (known design limitation, now measured).**
- A simulation with the real `block_split` gave these overlaps:

  | Patch set | Share touching the other split | Mean share of pixels in the other split |
  |---|---|---|
  | Training patches | 29.6% touch validation blocks | 6.1% |
  | Validation patches | 76.5% touch training blocks | 23.5% |

  Only 23.5% of validation patches lie wholly inside validation territory.
- The envelope path is now traced. The binners and `Selection_Ratio` are fitted on all sightings before the split (`analyze_grouse.py:880-918`, `:1099-1100`), and the negative draw is weighted by 1/SR whether or not `--use-weights` is set.
- Validation also drives checkpoint selection and Platt fitting.
- Reported validation scores are therefore optimistic relative to an untouched region. This matches tracker items D1–D4 and the design competition's V2/V6; the new information is the measured size.
- The decision belongs to the owner. It is not a code bug.

**#7: calibration binding.**
- Scale and bias are applied before the mismatch check, which only warns.
- The saved `flip_tta` is never compared, and a manual temperature is not validated.
- Because calibration and prediction default to different model paths, and copying refreshes the mtime, the warning fires even on correct use. That trains users to ignore it.

**#21: 15 m map offset.**
- Training sampling, the nodata mask and the centre-feature capture agree on pixel 32. Only the output affine omits the +0.5 pixel.
- Map values sit 15 m north-west of their true location at any stride. That is 1/8 of a 120 m output cell: small, but systematic, and the same class of error as BUG-0094.

**#4: AP ties.**
- Reproduced exactly.
- Validation logits are fp16 under autocast, so ties occur, and `--select-by rank` (the default) uses this AP.
- On realistic logits the bias is about 2.5e-5 and nearly constant across epochs, so it does not change the selected epoch. Only a collapsed model is badly inflated: a constant predictor across 3 regions scores 0.71 instead of 0.5.

## 4. Where the audit is wrong or overstated
- **Severity overall.** Every High assumes a workflow the project does not use (`--resume`, `--init-from`, `--no-missing-mask`, `--distill-from`) or data the project does not have (float model inputs, gaps in the disturbance record).
- **#18.** `download_treemap.resolve_band` already refuses unknown bands. Collections are pinned since CR-0034/0035, and the EC2 logs show a recognised band in use.
- **#11.** PA-0048 deliberately scopes split acceptance to split inputs. Binding every training raster belongs in the checkpoint's provenance (BUG-0060), not the split acceptance record.
- **#2.** In the default position mode (`rel`), a head-count change fails loudly. Production loaders rebuild the model from the full stored config; only `diagnose_training.py` calls the weak `load()`. The audit also missed that an `abs`↔`none` switch is silent.
- **#17.** The arithmetic is right. On GPU instances the queue is about 0.2 GiB per vCPU, against at least 4 GiB of RAM per vCPU.
- **#5 citation.** The background sampler is `train.py:121`, not `dataset.py`.

## 5. What the audit missed
1. **`calibrate.fit_platt` with NaN logits** returns (1.0, 0.0). That passes the `a <= 0` guard, so an identity calibration is written without error. This is a sibling of #15.
2. **`generate_road_distance.py:367`** writes its output to the live path, a further instance of #10.
3. **Our own records are inaccurate.** The PA-0027 sweep row and BUG-0071 describe the `raster_path` fallback as "nearest-year". The code selects the newest valid year. The records must be corrected, and the fix for #3 must make the code match the intended rule.
4. **#9's trigger was missed.** The HYBRID_REPORT/H5 action ("open a BUG if the disturbance record ends before 2025") had already fired but was not filed.

## 6. Proposed remediation order
Each item follows CLAUDE.md. Trivial fixes get a BUG entry. Non-trivial fixes get a CR with independent review. Every new preventive action is followed by a sweep.

1. **#9:** file the BUG now. Mark 2025 `tsd` as censored or uncovered for the missing years, or fill the gap from LCMS 2025 (own CR). This is the only item affecting today's output.
2. **#7 and the `fit_platt` NaN defect:** a calibration-binding CR.
3. **#21:** a georeferencing CR. Small and systematic.
4. **#3, with the records correction:** a validity and closest-year CR.
5. **#10:** a staged-publish CR with a preventive action and sweep.
6. **Trivial fixes batch:** #4, #6, #2, #15, #16, #17, #18, #22, A1, A2, A3. Each with a BUG entry and recurrence review.
7. **Already-planned work, widened with the audit's additions:** BUG-0060 (with #1 and #11), BUG-0059 (#8), BUG-0062 (#13), BUG-0061 (#14), CR-0038 (#12).
8. **Owner decision:** D1–D4 spatial isolation (#5), weighed against the measured overlap. It determines whether reported validation scores can be read as generalisation.

Nothing has been changed in code as a result of this audit. The items above await the owner's go-ahead.
