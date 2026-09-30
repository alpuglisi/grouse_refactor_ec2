# BUG-0079: multi-year raster generators write final paths non-atomically, and the training reader's content-validation fallback plus a filename-only year check let a truncated vintage resolve silently to the latest one (future leakage for `tsd`)

> Found by the 2026-09-30 static code review at `3b3e7d1`. The three
> code facts are confirmed; the trigger (an interrupted or failed write)
> has not been observed, so the instance is latent.
> **Status: OPEN (latent); owner: lead; small CR (writer atomicity +
> reader refusal).**

## 1. Description
`generate_time_since_disturbance.py` and `generate_treemap_features.py`
open every output year/feature file for write at its **final** path up
front and fill them stripe by stripe; `generate_road_distance.py` writes
its per-year files directly too. A run killed mid-way (signal, disk full,
Earth Engine or I/O error) leaves truncated files at final paths. On the
training read path, `RegionData.raster_path` (default `validate=True`)
treats a file that fails `_is_valid_raster` as absent and falls back to
**the most recent valid year on disk, whatever the distance**, with one
printed warning. `train.filter_by_year_gap` checks `raster_years`, i.e.
which filenames exist, so it cannot refuse the substitution. For `tsd`
the substituted raster's clock includes disturbances after the record's
year: the channel that must "never leak the future" (ARCHITECTURE.md
invariant) does.

## 2. Where encountered
- Writers: `generate_time_since_disturbance.py:300-303`,
  `generate_treemap_features.py:310-313`,
  `generate_road_distance.py:366-367`.
- Reader fallback: `grouse_data.py:384-408` (`raster_path`,
  `validate=True` branch), used by `dataset.py:125-127` for every
  (feature, record year).
- Check that cannot see it: `train.py:242-248` (`filter_by_year_gap`
  builds `yrs` from `rd.raster_years(f)`).

## 3. What it caused to fail
Latent. Scenario: `python generate_time_since_disturbance.py --years 2020
2021` dies mid-stripe. `ME_2020_tsd.tif` and `ME_2021_tsd.tif` are
truncated; 2022 to 2025 are intact. Every 2020 and 2021 training and
validation record then reads `ME_2025_tsd.tif`: undisturbed pixels read
five years older, and 2021 to 2024 cuts appear as "disturbed N years
ago" in a 2020 sighting's landscape. The values are plausible, the patch
cache stores them, `standing_checks` pins the substituted file's size and
mtime, and E11(b) records the fallback in the manifest without failing.
TreeMap and `road_dist` substitute a copy or a near vintage, so `tsd` is
the feature where the fallback becomes leakage.

## 4. What the defect was
`generate_time_since_disturbance.py:300-303`:
```python
        for y in years:
            path = os.path.join(raster_dir, f"{region}_{y}_tsd.tif")
            outs[y] = rasterio.open(path, "w", **profile)
            outs[y].update_tags(GROUSE_COVERAGE="disturbance-intersection")
```
`generate_treemap_features.py:310-313`:
```python
        for feat in ("balive", "tpa_live", "qmd", "carbon_dwn"):
            path = os.path.join(raster_dir, f"{region}_{year}_{feat}.tif")
            outs[feat] = rasterio.open(path, "w", **profile)
            outs[feat].update_tags(GROUSE_COVERAGE="nlcd")
```
`grouse_data.py:387-408` (fallback):
```python
        # Resolved file exists but is invalid - fall back to the most
        # recent valid year among everything else on disk. Loud, once
        # per (feature, year): ...
        for candidate_year in sorted(years, reverse=True):
            if candidate_year == year:
                continue
            candidate_path = self.path("raster", feature=feature,
                                       year=candidate_year)
            if self._is_valid_raster(candidate_path):
                ...
                return candidate_path
```
`train.py:242-248`:
```python
    yrs = {f: rd.raster_years(f) for f in features}
    yrs = {f: ys for f, ys in yrs.items() if ys}

    def ok(year):
        year = int(year)
        return all(min(abs(y - year) for y in ys) <= tolerance
                   for ys in yrs.values())
```

## 5. Root cause analysis (fault tree)
Top event: a training record is read from a vintage outside the year
tolerance without refusal. It requires all three of:
- **A.** an invalid file at the record's year. Enabled by writers that
  create the final path before the content is complete (no temp +
  `os.replace`), by an interrupted run, or by a placeholder vintage
  (CHANGELOG 2026-09-20, "Empty placeholder vintages: keep them");
- **B.** a reader that substitutes instead of refusing. `raster_path`'s
  fallback was designed so the analysis scripts "never hard-crash on
  sparse vintages"; `dataset.py` calls the same method with the same
  default;
- **C.** no check on the resolved year. `filter_by_year_gap` reads
  filenames, not `raster_path`'s result; E11(b) records but does not
  fail.

**Root cause:** a most-recent-valid-year fallback designed for unfiltered
analysis scripts sits on the training read path, the year-gap check
inspects filenames rather than the resolved file, and the generators'
non-atomic writes make an invalid file at a training year reachable by an
ordinary interruption.

## 6. Corrective action
**None yet.** Proposed (one small CR):
1. writers: open each output at `path + ".tmp"`, and in the `finally`
   `os.replace` on success or `os.unlink` on failure (the pattern
   `download_tcc_nlcd.py:464-465`, `prepare_training_data.py:217-223`
   already use);
2. reader: `GrousePatchDataset` resolves with `raster_path(...,
   max_year_gap=tolerance)` and **raises** when the resolved year differs
   from the nearest-year resolution by more than the tolerance; or
   `filter_by_year_gap` checks the year parsed from `rd.raster_path(f,
   y)` instead of `raster_years`;
3. `standing_checks` fails on any manifest fallback beyond tolerance.
Status: **OPEN (latent)**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0023-atomic-raster-writes-and-fallback-refusal.md` (DRAFT v1, awaiting independent review under CLAUDE.md §1.2; nothing implemented).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md`, `PREVENTIVE_ACTIONS.md`, `CHANGELOG.md` for
"fallback", "empty", "placeholder", "atomic", "replace", "future".

**Matches:** BUG-0015 and BUG-0052 (empty-raster validity checks at
download), BUG-0024 (tsd future-leakage invariant, generator side),
PA-0027's Swept? note ("`grouse_data.py:327`'s fail-closed probe triggers
a silent nearest-year fallback in `raster_path` (designed; recorded in
the manifest by E11(b))"), CR-0019 (`filter_by_year_gap` refuses rather
than drops).

**Prior-preventive-action failure analysis.** PA-0027's sweep saw the
fallback and classed it as designed, delegating to E11(b), which records
without refusing; CR-0019 made the year check refuse but built it on
`raster_years`; no rule requires atomic writes (the download scripts do
it by local convention). Category: accepted design at the wrong layer,
not enforced on the training path.

## 8. Preventive action
**PA-0036**: (a) every generator writes each output file to a temporary
path and `os.replace`s it only after the file is complete and validated,
so an interrupted run leaves nothing at a final path; (b) on the
training and calibration read path, a resolution that differs from the
nearest-year resolution (content-validation fallback) is refused, and
any year-gap check reads the year of the **resolved** path, never the
filenames on disk.

**Sweep (§3.5), writers of files a downstream script reads, by whether
they write the final path directly:** direct: `generate_time_since_
disturbance.py:302`, `generate_treemap_features.py:312`,
`generate_road_distance.py:367`, `download_treemap.py:331` (raw
intermediate), `analyze_grouse.py:551`, `:877`, `:1099-1100`,
`sightings.py:138`, `predict.py:1100` (a product, no reader); temp +
replace: `download_rev.py`, `download_tcc_nlcd.py:464-465`,
`prepare_training_data.py:217-223`, `generate_negatives.py`,
`realign_rasters.py`, `repair_coverage_rasters.py`. Readers with a
substitution fallback: `dataset.py` via `raster_path` (this);
`predict.py` `latest_raster_path` (skips invalid, prediction-time, not a
year match); `analyze_grouse.py` (analysis, warning is adequate).

## Cross-references
ARCHITECTURE.md ("`tsd` is recomputed per vintage", "never leak the
future"); CHANGELOG 2026-09-20 (placeholder vintages); BUG-0015,
BUG-0024, BUG-0052; CR-0019; PA-0027, PA-0036.
