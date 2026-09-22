# Bug Log (running, newest first)

Flat quick-scan index. Full investigations live in `BUG-XXXX-slug.md` in
this directory. See `CLAUDE.md` §2 for what a full investigation must
contain.

Entries BUG-0001..0013 were found during the 2026-09-22 repository-wide
bug review of all 33 root-level `.py` files. Trivial (single-function,
no-CR-required) fixes were implemented immediately; everything else went
through a CR under `docs/quality/change-requests/`, an independent review
(which caught a real scope gap in CR-0002 — see BUG-0001), and
implementation. Entries BUG-0014..0018 were found during a same-day
follow-up review pass across all 34 files (regions.py now included),
specifically checking the prior fixes for regressions and re-running the
PA-0012 duplicate-script sweep — it found one incomplete fix (BUG-0014,
a missed BUG-0012 call site) and one un-swept duplicate-script instance
(BUG-0015). Newest-first by discovery within each pass; ties broken by ID
order. Entries BUG-0019..0021 were found in a third pass, triggered by the
user directly asking whether `CLAUDE.md` §3.5's mandatory sweep step was
actually being followed — it wasn't, for most preventive actions (see
BUG-0019). Running the five outstanding sweeps found two more real
findings (BUG-0020, BUG-0021) and confirmed three PAs clean.

| ID | Date | Symptom | Root cause | Remediation | Status |
|----|------|---------|------------|-------------|--------|
| BUG-0021 | 2026-09-22 | `predict.py`/`calibrate.py` reimplement checkpoint-config handling instead of using the shared `check_checkpoint_config` (PA-0009 sweep) | Two independent, both-correct mechanisms solve the same problem (BUG-0010's concern) without sharing code | None — verified not a live risk (both already reconstruct from the checkpoint's config); recommend a future CR to unify | OPEN, low priority |
| BUG-0020 | 2026-09-22 | 13 files independently hardcode paths duplicating `PATH_TEMPLATES`, worst in `organize_project.py` (PA-0003 sweep) | `PATH_TEMPLATES` introduced as single source of truth, but no migration swept pre-existing/independent hardcodings onto it | None — deferred, scope too large for this pass; recommend a future CR (path-derivation helpers) | OPEN |
| BUG-0019 | 2026-09-22 | Preventive-action sweeps (`CLAUDE.md` §3.5) were not consistently run when new PAs were added — 5 of 14 had zero documented sweep activity | The sweep step depends on the implementing session remembering to run and record it, with no structural checkpoint forcing that or making its absence visible | Ran the 5 outstanding sweeps (this pass); added a **Swept?** column to `PREVENTIVE_ACTIONS.md` (PA-0015) so an unswept rule is visible without grepping every bug doc | CLOSED |
| BUG-0018 | 2026-09-22 | `check_exotic.py` carries a dead, misleading `ROUND_DECIMALS` constant | Leftover from a superseded coordinate-rounding approach, never removed | Trivial fix applied directly — deleted the unused constant | CLOSED |
| BUG-0017 | 2026-09-22 | `dataset.py`'s training patches may conflate nodata sentinels with a legitimate value of 0 (unconfirmed) | Same mechanism as BUG-0008, in the training-data path instead of inference masking — not yet verified against real attribute tables | None — deliberately deferred pending domain confirmation; would need a CR if confirmed (touches cache format) | OPEN, unconfirmed |
| BUG-0016 | 2026-09-22 | `tune.py` and `tune_bins.py` silently overwrite each other's `bin_tuning_{region}.csv` output | Diverged (non-overlapping) duplicate scripts share one mutable output path with no marker for which produced it | Trivial fix applied directly — warning banner in `tune.py`; full resolution (reconcile scripts or disambiguate paths) needs a domain-owner call + CR | OPEN, stopgap in place |
| BUG-0015 | 2026-09-22 | `download_more.py` can silently accept an empty (all-nodata) raster as a successful download | Empty-raster validity check fixed in `download_rev.py`, never backported to `download_more.py` (a 4th instance of the stale-duplicate-script mechanism, found by re-running PA-0012's sweep) | Backported directly — `_raster_valid_fraction`/`MIN_VALID_PIXEL_FRAC` ported verbatim | CLOSED |
| BUG-0014 | 2026-09-22 | `fit()`'s divergence-guard call could still crash with `KeyError: 'tta_auc'` — BUG-0012 recurrence, one call site missed | Original BUG-0012 fix targeted only the call sites its investigation quoted, not a full sweep of every `tta_auc` consumer in the function | Trivial fix applied directly — `guard.update(...)` now uses `.get('tta_auc', float('-inf'))` | CLOSED |
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
