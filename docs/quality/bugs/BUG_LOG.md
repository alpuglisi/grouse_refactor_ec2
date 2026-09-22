# Bug Log (running, newest first)

Flat quick-scan index. Full investigations live in `BUG-XXXX-slug.md` in
this directory. See `CLAUDE.md` §2 for what a full investigation must
contain.

All entries below were found during the 2026-09-22 repository-wide bug
review of all 33 root-level `.py` files (a documentation-only pass — no
code changes were made; each entry's Corrective Action is "None yet,"
pending a CR per `CLAUDE.md` §1). Newest-first by discovery within that
pass; ties broken by ID order.

| ID | Date | Symptom | Root cause | Remediation | Status |
|----|------|---------|------------|-------------|--------|
| BUG-0013 | 2026-09-22 | Broad `except Exception` in download submit/poll loops masks real bugs as transient network errors | Blanket exception handling copied across download scripts | None yet (low priority) — narrow to specific exception types, log traceback | OPEN |
| BUG-0012 | 2026-09-22 | `fit()` can crash with `KeyError: 'tta_auc'` for non-multiple-of-4 validation sets | `evaluate()` conditionally populates `tta_auc`; `fit()` consumes it unconditionally | None yet — use `.get()` consistently in `fit()` | OPEN |
| BUG-0011 | 2026-09-22 | `diagnose_training.py` crashes on real checkpoints instead of diagnosing them | Diagnostic script's handler defaults don't match `train.py`'s real defaults; exception handling too narrow | None yet — mirror train.py defaults, widen except | OPEN |
| BUG-0010 | 2026-09-22 | A checkpoint can silently load into the wrong pooling architecture (mean/center/gauss) | Checkpoint's stored `config` is saved but never validated on `load()` | None yet — validate/use config on load | OPEN |
| BUG-0009 | 2026-09-22 | Exported prediction GeoTIFF/KMZ is spatially offset by half an output pixel | Patch-center coordinate used directly as Affine transform's corner constant | None yet — subtract half-pixel offset when building transform | OPEN |
| BUG-0008 | 2026-09-22 | Prediction map can drop valid land (value 0) or fail to mask true nodata (when raster's nodata==0) | Sentinel nodata and legitimate zero values both collapsed to `0` in `predict.py` | None yet — use dedicated nodata mask array | OPEN |
| BUG-0007 | 2026-09-22 | Dead/no-op `.round(5)`→`.columns` dedup call gives false impression of rounding-based coordinate dedup | Misapplied chained call extracts column names, not rounded values | None yet — delete no-op call | OPEN |
| BUG-0006 | 2026-09-22 | Real-looking GBIF password/email and eBird API key committed in plaintext | No secrets-management convention in the codebase | None yet — **recommend immediate credential rotation** + env-var loading | OPEN |
| BUG-0005 | 2026-09-22 | `sighting_years()` always returns `[]` after project files are organized into `data/sightings/` | Glob pattern hardcoded independently of `PATH_TEMPLATES`, drifted from sibling method | None yet — derive glob from `PATH_TEMPLATES["sightings"]` | OPEN |
| BUG-0004 | 2026-09-22 | `gen_negs.py` produces degraded (non-veg-dominated) negative training samples if run instead of its sibling | Non-vegetated sampling cap fixed in `generate_negatives.py`, never backported to `gen_negs.py` (stale duplicate script) | None yet — delete or backport cap | OPEN |
| BUG-0003 | 2026-09-22 | `download_landfire.py`/`_2`/`_3` download rasters for Montana/N. California, not the actual ME/NH/VT project area | Placeholder AOI fixed in `download.py`, never backported to superseded siblings | None yet — delete or backport AOI fix | OPEN |
| BUG-0002 | 2026-09-22 | `download_landfire.py`/`_2`/`_3` fail all job submissions | Retired API endpoint fixed in `download.py`, never backported to superseded siblings | None yet — delete or backport endpoint fix | OPEN |
| BUG-0001 | 2026-09-22 | `clean.py`'s spatial block assignment vs. `audit.py`/`analyze_grouse.py`'s NH extent silently disagree by ~1.5km; same split between `download.py` vs. `download_more.py`/`download_rev.py` | NH bounding-box constant duplicated by copy-paste across 6 files, edited inconsistently | None yet — extract to shared `regions.py` module | OPEN |
