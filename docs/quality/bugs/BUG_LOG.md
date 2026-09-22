# Bug Log (running, newest first)

Flat quick-scan index. Full investigations live in `BUG-XXXX-slug.md` in
this directory. See `CLAUDE.md` §2 for what a full investigation must
contain.

Entries were found during the 2026-09-22 repository-wide bug review of all
33 root-level `.py` files. Trivial (single-function, no-CR-required) fixes
were implemented immediately; everything else went through a CR under
`docs/quality/change-requests/`, an independent review (which caught a
real scope gap in CR-0002 — see BUG-0001), and implementation. Newest-first
by discovery within that pass; ties broken by ID order.

| ID | Date | Symptom | Root cause | Remediation | Status |
|----|------|---------|------------|-------------|--------|
| BUG-0013 | 2026-09-22 | Broad `except Exception` in download submit/poll loops masks real bugs as transient network errors | Blanket exception handling copied across download scripts | Deferred (low priority, 20 call sites across 6 files) — narrow to specific exception types, log traceback | OPEN |
| BUG-0012 | 2026-09-22 | `fit()` can crash with `KeyError: 'tta_auc'` for non-multiple-of-4 validation sets | `evaluate()` conditionally populates `tta_auc`; `fit()` consumes it unconditionally | Trivial fix applied directly — `fit()` now uses `.get('tta_auc', float('-inf'))` | CLOSED |
| BUG-0011 | 2026-09-22 | `diagnose_training.py` crashes on real checkpoints instead of diagnosing them | Diagnostic script's handler defaults don't match `train.py`'s real defaults; exception handling too narrow | CR-0005 — mirrors train.py defaults, widened except | CLOSED |
| BUG-0010 | 2026-09-22 | A checkpoint can silently load into the wrong pooling architecture (mean/center/gauss) | Checkpoint's stored `config` is saved but never validated on `load()` | CR-0005 — validates config on load, raises on mismatch | CLOSED |
| BUG-0009 | 2026-09-22 | Exported prediction GeoTIFF/KMZ is spatially offset by half an output pixel | Patch-center coordinate used directly as Affine transform's corner constant | Trivial fix applied directly — subtracts half-pixel offset when building transform | CLOSED |
| BUG-0008 | 2026-09-22 | Prediction map can drop valid land (value 0) or fail to mask true nodata (when raster's nodata==0) | Sentinel nodata and legitimate zero values both collapsed to `0` in `predict.py` | CR-0004 — dedicated invalid-data mask from raw values | CLOSED |
| BUG-0007 | 2026-09-22 | Dead/no-op `.round(5)`→`.columns` dedup call gives false impression of rounding-based coordinate dedup | Misapplied chained call extracts column names, not rounded values | Trivial fix applied directly — deleted the no-op call | CLOSED |
| BUG-0006 | 2026-09-22 | Real-looking GBIF password/email and eBird API key committed in plaintext | No secrets-management convention in the codebase | CR-0001 — env-var loading | Code fix CLOSED; **credential rotation still OPEN, owner action required** |
| BUG-0005 | 2026-09-22 | `sighting_years()` always returns `[]` after project files are organized into `data/sightings/` | Glob pattern hardcoded independently of `PATH_TEMPLATES`, drifted from sibling method | Trivial fix applied directly — derives glob from `PATH_TEMPLATES["sightings"]` | CLOSED |
| BUG-0004 | 2026-09-22 | `gen_negs.py` produces degraded (non-veg-dominated) negative training samples if run instead of its sibling | Non-vegetated sampling cap fixed in `generate_negatives.py`, never backported to `gen_negs.py` (stale duplicate script) | CR-0003 — cap backported verbatim | CLOSED |
| BUG-0003 | 2026-09-22 | `download_landfire.py`/`_2`/`_3` download rasters for Montana/N. California, not the actual ME/NH/VT project area | Placeholder AOI fixed in `download.py`, never backported to superseded siblings | CR-0003 — deprecation banner (full backport blocked by unverifiable API rewrite; see CR) | CLOSED (as deprecation) |
| BUG-0002 | 2026-09-22 | `download_landfire.py`/`_2`/`_3` fail all job submissions | Retired API endpoint fixed in `download.py`, never backported to superseded siblings | CR-0003 — deprecation banner (full backport blocked by unverifiable API rewrite; see CR) | CLOSED (as deprecation) |
| BUG-0001 | 2026-09-22 | `clean.py`'s spatial block assignment vs. `audit.py`/`analyze_grouse.py`'s NH extent silently disagree by ~1.5km; same split between `download.py` vs. `download_more.py`/`download_rev.py` | NH bounding-box constant duplicated by copy-paste, actually across **7** files (initial sweep missed `prepare_training_data.py`, caught by CR-0002's independent review) | CR-0002 — extracted to shared `regions.py` module | CLOSED, with standing follow-up: NH value needs domain confirmation |
