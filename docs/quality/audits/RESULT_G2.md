# G2 verification results (findings #3, #9, #12, #16, #18, #19)

The audited commit is `472ba5e`. HEAD is `9b1f741` (`claude/nice-cori-creqpb`). No repository file was edited. Probes are in `probes/`:

- `g2_f3_validity.py`: extracts `RegionData._is_valid_raster` and `raster_path` from HEAD with the AST and runs them on real GeoTIFFs written with rasterio.
- `g2_f9_tsd.py`: extracts `process_region` and `_emit` from HEAD `generate_time_since_disturbance.py`, plus `_finite`, `tsd_encode` and `tsd_decode` from `models.py`. It runs them on synthetic disturbance stacks with real WarpedVRT warping.
- `g2_f16_cache.py`: the cache-write and live-read expressions copied verbatim. They are inline expressions, not functions, so they could not be extracted.

I could not inspect the production rasters on EC2 (none are in this container) or call Earth Engine. Statements about what is on disk come from the committed manifests (`docs/quality/evidence/CR-0010-manifest-*.tsv`, `CR-0014-manifest.tsv`), the CR-0035 evidence logs, `CHANGELOG.md`, and the writer code's declared dtype and nodata.

Summary table:

| # | Verdict | Severity (auditor) | Tracked | Disposition |
|---|---|---|---|---|
| 3 | PARTLY VALID; validity holes VALID-LATENT, latest-not-closest fallback VALID-LATENT | Medium (High) | Partly: PA-0027 sweep row and BUG-0071 §7/§8 call the fallback "designed, recorded by E11(b)" but misdescribe it as "nearest-year". No BUG | Own CR (~1 day) |
| 9 | PARTLY VALID | Medium (High) | Partly: HYBRID_REPORT §6 and H5 §1 note the record ends in 2024. H5's "open a BUG" action is not done | BUG plus own CR (~0.5–1 day) |
| 12 | VALID (known) | Medium (Medium) | Design note ARCHITECTURE.md:267; planned CR-0038 source-year gate (HYBRID_REPORT §6, H2/V1). No BUG | Covered by CR-0038; file a BUG entry |
| 16 | VALID-LATENT | Low (Medium) | none | Trivial fix plus BUG (~1 h) |
| 18 | PARTLY VALID / VALID-LATENT | Low (Medium) | `collection_years` fallback allowlisted in the PA-0027 sweep; analysis vintage duplication related to BUG-0075. No BUG for `bands[0]` | Trivial fix plus BUG for `bands[0]` (~30 min); rest no change |
| 19 | VALID-LATENT | Low (Medium) | Neighbouring sites covered by PA-0027 family (BUG-0049/0070); these sites none | Tracker item; optional trivial fix plus BUG for `download_rev` |

---

## #3 Raster validity accepts missing data; fallback bypasses the year gate

**Code (unchanged 472ba5e → HEAD apart from the RASTER_FEATURES list):**
- `grouse_data.py:312-334` (`_is_valid_raster`):
  ```python
  if src.nodata is None:
      valid = True
  else:
      frac = (data != src.nodata).sum() / data.size if data.size else 0.0
  ...
  except Exception:
      valid = False
  ```
- `grouse_data.py:336-412` (`raster_path`): `chosen = min(years, key=lambda y: (abs(y - year), y))` at :368. When the chosen file is invalid, the fallback at `:397` is `for candidate_year in sorted(years, reverse=True):`, which returns the **newest** valid year, not the closest. The docstring at :350-354 says so explicitly ("MOST RECENT valid year overall, regardless of numeric distance").
- `train.py:287-326` (`filter_by_year_gap`) gates on `rd.raster_years(f)`, which is a filename scan (`grouse_data.py:300-310`), not on the resolved path.
- `dataset.py:131-134` resolves through `raster_path(feat, yr)` with `validate=True`.

**Reproduction (rasterio, real functions):**

| Raster | `_is_valid_raster` |
|---|---|
| all-NaN float32, nodata=NaN | **True** |
| all −9999 int16, nodata=None | **True** |
| all −9999 int16, nodata=−9999 | False (correct) |
| corrupt bytes | False |

Fallback test: files for 2016, 2018, 2019, 2020, 2021 and 2025, with the 2020 file empty. `raster_path("evt", 2020)` returns **`ME_2025_evt.tif`**, a 5-year gap, although valid 2019 and 2021 files exist. The year gate would have passed 2020 because `ME_2020_evt.tif` exists. The mechanism is confirmed.

**Exposure:**
- *NaN/no-nodata holes.* Every model-input writer declares integer dtype and nodata:
  - `generate_treemap_features.py:399` (int16, −9999)
  - `generate_time_since_disturbance.py:278` (int16, −9999)
  - `generate_road_distance.py:369`
  - `download_tcc_nlcd.py:554`
  - `generate_canopy_structure.py:401,430`
  - `generate_lidar_structure.py:714`

  The only float32 or nodata=None writer is `download_treemap.py:300`. Its output is the raw TreeMap source (`TreeMap{v}_{region}_{attr}.tif`), which `raster_path` never reads. The `--refetch-empty` history in CHANGELOG.md:649-680 shows the real LANDFIRE placeholders *were* caught, so they carry declared nodata. No on-disk input reaches either hole: **latent**.
- *Latest vs closest.* The only known invalid files are the LF2025 placeholders. CHANGELOG.md:590-596 and :652 cover EVC 2025, and the NE GeoArea is unpublished until Nov 2026. Because 2025 is the newest year, the "newest valid" year (2024) equals the closest valid year. A wrong-year substitution needs an invalid file in a *middle* year (for example, a corrupt `balive` 2018 would resolve to 2025). That has not occurred. Training years are 2020-2024 (`regions.YEAR_MIN = 2020`; CR-0031 smoke log), so no 2025 row resolves a placeholder. **Latent.**
- The broad `except Exception → False` is allowlisted under PA-0027 as fail-closed. Its downstream effect is a silent cross-year substitution on any transient I/O error, so the "fail-closed" label is debatable. Today it only redirects within existing vintages.

**Tracking:** the PA-0027 sweep row (`PREVENTIVE_ACTIONS.md`, PA-0027 sweep note) and BUG-0071 §7/§8 say: "`grouse_data.py:327`'s fail-closed probe triggers a silent nearest-year fallback in raster_path (designed; recorded in the manifest by E11(b))". **That description is wrong**: the fallback is newest-year, not nearest-year. E11 (`acceptance_split.py:2309`) only digests the rasters actually read. It does not enforce the tolerance on the resolved year. The NaN and no-nodata validity holes are not tracked anywhere.

**Verdict:** PARTLY VALID.
- Every mechanism the auditor names is real and reproduced.
- Real-world exposure today is nil (VALID-LATENT).
- The auditor's "silently introduces future landscapes" has not happened on the current data.
- The auditor's "do not cache validity indefinitely" is overstated: the cache is per `RegionData` instance (per process).

**Severity:** Medium (auditor: High). The defect is real and reachable by a single corrupt middle-year file, but it is not reached on current data. The existing QMS record misstates the behaviour.

**Disposition:** own CR. It touches the `raster_path` semantics used by training, prediction and `acceptance_split.Rasters.is_valid` (the replay). The fix:
- finite- and sentinel-aware validity, applying `NODATA_SENTINELS` when nodata is None;
- fallback to the closest valid year;
- refusal when the resolved year exceeds `YEAR_MATCH_TOLERANCE` in the training path;
- a BUG entry that also corrects the PA-0027/BUG-0071 description.

Estimate: ~1 day including the matching replay change in `acceptance_split`.

---

## #9 Missing disturbance years become evidence of undisturbed land

**Code (HEAD differs from 472ba5e only by `tolerance=WARP_TOLERANCE_PX`, BUG-0096):**
- `generate_time_since_disturbance.py:221-228`: gaps only `print("[warn] gaps ...")`.
- `:305`: every output tagged `GROUSE_COVERAGE="disturbance-intersection"`.
- `:316`: `cov = np.ones(...)`.
- `:359`: `years_since = np.where(last >= 0, year - last, TSD_MAX_YEARS)`.

**Reproduction (real `process_region`/`_emit`):**
- *Record 1999-2024 (26 rasters, the user's EC2 shape), targets 2016/2020/2024/2025:*
  - A pixel cut only in **2025** reads **30.0** ("never disturbed") in `ME_2025_tsd.tif`, tagged `disturbance-intersection`.
  - A pixel cut in 1995 reads 30.0 in every target. This is designed left-censoring; see the module docstring at :40-45 and `models.py:670-676`.
  - A 2010 cut reads 6/10/14/15, which is correct.
- *Auditor scenarios, with a gap at 2010 and a target of 1998 before the record:*
  - A pixel cut only in 2010 reads 30.0 in the 2012 output.
  - The 1998 target is written fully covered with 30.0 everywhere.

Both mechanisms are confirmed.

**Which target years are actually affected (user log "1999-2024 (26 rasters)"):** 2024 − 1999 + 1 = 26, so the record has **no interior gaps**. The output targets are 2016-2025 (CR-0035 step-2 inventory: `tsd 2016-2025`). No target precedes 1999. The gap branch and the empty-source branch are therefore **not reached**.

The **2025 target is affected**. It is past the record end, so 2025 disturbances are invisible while the file claims intersection coverage. Probe-confirmed. The owner's log in HYBRID_REPORT §6 shows VT 2024 and 2025 both at 10.7% disturbed.
- **Training is not affected**: years run 2020-2024.
- **Prediction is affected**: `predict.py:165` uses `rd.latest_raster_path(f)`, which picks `*_2025_tsd.tif`. Fresh 2025 cuts render as old forest on the map.
- The left-censoring (pre-1999 disturbance encodes as 30, since record length is 17-26 years against a 30-year cap) affects every target. It is a documented design choice, not this finding.

**Tracking:**
- `docs/design_competition/hybrid/H5.md:49-53` named this the "temporal analogue of BUG-0024". Its action reads: "If the record ends before 2025, open a BUG ... tag the files with the record end year". The condition is now met (record ends 2024), but no BUG was opened (BUG_LOG has only BUG-0024 and BUG-0096 for tsd).
- HYBRID_REPORT.md:129 reclassified it as "a data-latency limit, not a code defect". I disagree in part. The data latency is external, but writing a 2025 file tagged as covered, with no record-end marker, is code behaviour that matches PA-0017/PA-0020 (an "absent" default written where the source has no coverage on the time axis).

**Verdict:** PARTLY VALID.
- The gap and pre-record branches are real but unreachable on the actual record (VALID-LATENT).
- The right-edge case (2025 output beyond the 2024 record) is VALID and reached by prediction.

**Severity:** Medium (auditor: High). Training is unaffected. The prediction-map impact is limited to 0-1-year cuts.

**Disposition:** file a BUG with a recurrence review against BUG-0024/PA-0017/PA-0020, as H5 already prescribed. Then an own CR:
- refuse or mark nodata for targets beyond `max(found)`, or write a `GROUSE_DIST_RECORD_END` tag that predict/acceptance checks;
- refuse interior gaps and pre-record targets.

Small (~0.5-1 day). It regenerates `tsd`, which is a data change and needs approval.

---

## #12 Derived feature filenames hide their source years

**Code (HEAD: 3-line diff unrelated):**
- `generate_treemap_features.py:388` maps each target year with `nearest_vintage` (:143, ties go earlier).
- `:390-395` only *warns* for gaps over 2 years and says itself that "the year-gap filter will NOT catch it".
- The output tags (:315) record coverage only, not the source vintage.
- `generate_canopy_structure.py:13-15,35` writes one static `mch_*` layer under every year (it does tag `GROUSE_SOURCE=MCH_ASSET` but no source year).
- `train.py:287-326` gates on filenames.

**Actual mapping on EC2:** from `docs/quality/evidence/CR-0035/step2_redownload_and_inventory.txt:12-13`, the year-to-vintage map is {2016-18:2016, 2019-21:2020, **2022-25:2022**}, with a `[warn] {2025: 2022}` (no TreeMap 2023 in EE).
- Training years 2020-2024 have a true source gap of at most 2 years (2024 maps to 2022), which is within `YEAR_MATCH_TOLERANCE = 2`.
- **Prediction** uses the 2025 files, with a true gap of 3 years for TreeMap features. That exceeds the tolerance, and nothing enforces it.
- The auditor's "future source for older target" case is real for 2019, which maps to 2020, but 2019 is below `YEAR_MIN`.
- The auditor's example (TreeMap 2022 written as `ME_2025_balive.tif`) is exactly what is on disk.

**Tracking:**
- ARCHITECTURE.md:267-278 documents the nearest-vintage design and says outright that the filter "cannot warn when a mapping is stale".
- The design-competition vote and hybrid reports flagged it: V1 (year/source-year integrity) and H2 ("TreeMap and `mch_*` pass the year filter while describing another year", HYBRID_REPORT.md:79,114,133). The planned fix is the **CR-0038 source-year gate**, which is not yet written: there is no `CR-0038*` in `docs/quality/change-requests/`.
- No BUG ID.

**Verdict:** VALID, already known by design note and planned CR-0038. It does not affect training under the current tolerance. It does affect the 2025 prediction landscape.

**Severity:** Medium (auditor: Medium). Agree.

**Disposition:** no separate CR. Fold it into CR-0038 as planned (write `GROUSE_SOURCE_YEAR` into TreeMap and `mch_*` outputs, and gate on resolved source year). Because it is a confirmed defect, file a BUG entry now under CLAUDE.md §2 that points to CR-0038 as the corrective action. The CR scope is already sized in the hybrid plan; the BUG entry alone is ~30 min.

---

## #16 Cache coercion of non-finite/float inputs

**Code (`dataset.py` unchanged 472ba5e → HEAD):**
- `:195-196` cache write: `arr[i, k] = np.nan_to_num(patch, nan=MISSING_CODE).astype(np.int16)`.
- `:360-361` live read: `np.nan_to_num(...)` with default ±inf handling.
- `_read_patch` (:340-348) builds a float32 buffer, then NaN-masks declared nodata and `NODATA_SENTINELS`.
- `:102` year cast: `df['year'].fillna(...).astype(int)`.
- `--cache-dir` defaults to `data/cache` (`train.py:611`), so the cache path *is* exercised by the recipe.

**Reproduction (verbatim expressions):**
- Input `[1.75, 40000, NaN, inf, −inf, −5, 32767, 255]`:
  - cache gives `[1, −25536, −32768, 0, 0, −5, 32767, 255]`;
  - live gives `[1.75, 40000, −32768, 3.4e38, −3.4e38, …]`.
- The auditor's numbers are confirmed.
- Every int16 value and every uint8 value round-trips exactly through the float32 buffer.

**Which on-disk rasters are float:** none of the model inputs.
- Writers: tsd, treemap-derived, road_dist, tcc/nlcd, `mch_*` and lidar are all int16 (or nlcd int16 via `mask_to_valid`). LANDFIRE LFPS clips are integer products.
- The only float32 GeoTIFF the project writes is the raw TreeMap source (`download_treemap.py:287-302`, float32, nodata=None), which is consumed only by `generate_treemap_features` (`_clean`, then int16 encode). It never reaches `dataset.py`.
- `lidar_meta` is int32 with nodata=None (`generate_lidar_structure.py:726`), but it is not a feature in `FEATURE_SPEC`.
- Integer GeoTIFFs cannot hold Inf or fractions, and 32767 is a sentinel masked before the cast.
- The only mechanism reachable in principle is an integer value outside int16 (uint16 or int32 sources). None exist among the inputs.
- Negative non-sentinel categorical codes are clamped to row 0 without a miss flag (`models.py` `embed`). No such codes are known on disk (the LANDFIRE negatives −9999 and −1111 are sentinels).

**Tracking:** none. BUG-0036 covers the write-side *encoders* rejecting NaN, not the dataset cache cast.

**Verdict:** VALID-LATENT. The mechanism is exact, but no current input is float or out of range.

**Severity:** Low (auditor: Medium). It needs an out-of-contract raster, which no writer produces. It would become Medium if a float feature were ever added.

**Disposition:** trivial fix plus a BUG entry, inside one function (`_load_or_build_cache`):
- assert finite-or-missing, integral and int16-range before the cast, raising otherwise;
- optionally bump the cache-format key.

~1 hour. The year-cast hardening at `:102` can go in the same entry or a separate trivial fix.

---

## #18 Unknown API schema accepted as a different band

**Code:**
- `download_tcc_nlcd.py:234` (same at 472ba5e:234): `band = next((b for b in band_prefs if b in bands), bands[0])`. Mosaic without ordering at `:241`.
- `collection_years` `:202-221`: `except Exception: pass`, then a regex scan of `system:index`.
- **TreeMap is different from the audit's description.** `download_treemap.resolve_band` (`:217-228`) raises `SystemExit` on an unknown band. There is no `bands[0]` fallback. Only `resolve_vintage_image`'s unordered `col.mosaic()` and the Collection-then-Image broad fallback (472ba5e:188-207) apply.
- Analysis has its own resolver: `analyze_grouse.py:288-300` (`available_years`, `pick_raster_year`, closest year with no validity check) and `:769-773`.

**Exposure:**
- Collections are now pinned per run (CR-0035 `--collection-*`; step-2.1 evidence). The recognised bands are actually selected: the log shows `band=b1` for NLCD, which is in `band_prefs`. So the `bands[0]` fallback has not fired.
- `GROUSE_SOURCE` records the collection and year (`download_tcc_nlcd.py:572-574`), not the band.
- The mosaic-order concern needs overlapping images within one year over NE. That does not hold for Annual NLCD (one CONUS image per year) or for TCC, whose per-year images are disjoint CONUS/AK/HI/PR footprints.
- Analysis/training divergence happens only when the closest file is invalid. That means the EVC 2025 placeholder, which affects analysis only for 2025 sightings, and GBIF has none (HYBRID_REPORT §6). Latent.

**Tracking:** the `collection_years` fallback is classed "Fallback between equals: `download_tcc_nlcd.py:209`" in the PA-0027 sweep (allowlisted). The duplicated resolver in analysis falls under the "duplicated truth" theme (BUG-0075 for START_YEAR) but has no own ID. `bands[0]` is untracked.

**Verdict:** PARTLY VALID.
- `bands[0]` is VALID-LATENT.
- The mosaic order is VALID-LATENT and practically moot for these products.
- The TreeMap part of the claim does not hold: it fails loud on unknown bands.
- `collection_years` is ALREADY TRACKED (PA-0027 allowlist).
- Analysis divergence is VALID-LATENT.

**Severity:** Low (auditor: Medium). Collections are pinned, the band is logged, a `valid_range` check is applied, and `<1% valid` raises.

**Disposition:** trivial fix plus a BUG entry for `bands[0]` (raise on no recognised band, as `download_treemap.resolve_band` already does; one line, one function). No change for mosaic order or `collection_years`, with written justification. Analysis resolver unification goes to the tracker (LOW). It would change `analyze_grouse` behaviour, so it needs its own CR if pursued.

---

## #19 Incomplete runs exit successfully

**Code (unchanged):**
- `download_rev.py:460-485`: `results["failed"]` is collected (:470), printed (:480-485), and `main` returns 0. The missing topo baseline only logs (:422).
- `analyze_grouse.py:1117-1126`: `analyze_region` returns `None` and the summary prints "skipped (see log above)", exit 0.
- `generate_time_since_disturbance.py:252-273`: region skips, exit 0.

**Exposure:**
- The workflow is interactive: the owner runs each step on EC2 and reads its summary (CR-0035 evidence). No orchestrator gates on exit status; the only `set -e` scripts are review scratch tooling.
- `download_rev`'s failure list legitimately includes unpublished LANDFIRE vintages ("Invalid products"; see `KNOWN_UNAVAILABLE`). Nonzero-on-any-failure would fire routinely unless expected and required failures are separated, which the auditor's mitigation does propose.
- Stale-output risk is low. `download_rev` never overwrites, and failed jobs leave no new file. `raster_path` content-validates what is there.
- Topo (slope/gradient) is not a model feature.
- The tsd skips are reached only when a region has no rasters at all (nothing to build) or no disturbance year at or before `max(years)` (impossible with 1999).
- `analyze_grouse` prints the skip in its summary, so the incompleteness is visible to a human, though not machine-readable.

**Tracking:** PA-0027 says broad handlers must not "let the run exit 0 with outputs that claim completeness" (BUG-0049, BUG-0070). These sites are not broad handlers, so they fall outside PA-0027 and its lint. No BUG covers them.

**Verdict:** VALID-LATENT. The success-exit behaviour is real. No current consumer reads exit status, and summaries print what was skipped.

**Severity:** Low (auditor: Medium).

**Disposition:** no immediate change. Add a LOW item to `docs/quality/CR-0007-0008-OPEN-ISSUES.md` covering "required vs expected failures; nonzero exit on required failures" for `download_rev` and `analyze_grouse`. Optionally make the trivial `download_rev.main` change: `SystemExit(1)` when any failure is not an "Invalid products" response, with a BUG entry (~30 min). Make it a CR if the exit-status contract is generalised across scripts.
