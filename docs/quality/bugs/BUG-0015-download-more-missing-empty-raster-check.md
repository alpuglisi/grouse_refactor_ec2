# BUG-0015: `download_more.py` lacks the empty-raster validity check fixed in `download_rev.py`

## 1. Description
`download_rev.py` validates that a downloaded raster actually contains
data (not just that the LFPS job reported "Succeeded") via
`_raster_valid_fraction`/`MIN_VALID_PIXEL_FRAC`. `download_more.py`, an
otherwise near-identical sibling script, lacks this check entirely — same
"fix landed in one copy, never backported to a duplicate" mechanism as
BUG-0002/0003/0004.

## 2. Where encountered
`download_more.py` (whole file, missing what `download_rev.py:74-82,
94-107, 211-230` has).

## 3. What it caused to fail
LFPS can report a job "Succeeded" and deliver a well-formed, correctly-
georeferenced GeoTIFF that is nonetheless entirely nodata — this happens
when a product/vintage isn't populated yet for a requested region (e.g.
LANDFIRE's staggered per-GeoArea rollout). Job status alone can't detect
this; only inspecting the actual pixel content can. `download_more.py`
accepted such a raster as a successful download with no validation,
silently corrupting the downstream dataset with an empty `.tif` presented
as valid data.

## 4. What the defect was
`download_rev.py` (fixed) reads the downloaded raster's first band after
extraction and rejects it if fewer than `MIN_VALID_PIXEL_FRAC` (1%) of
pixels are non-nodata, deleting the bad file and returning a clear
diagnostic instead of `"ok"`. `download_more.py` (before this fix) went
straight from `shutil.copyfileobj(zf, f)` to `return task, "ok"` with no
equivalent check.

## 5. Root cause analysis (Five Whys)
1. Why did `download_more.py` accept an empty raster as valid? Because it
   never inspects the downloaded raster's actual pixel content.
2. Why does it not inspect the content when `download_rev.py` does? Because
   the content-validation fix was added only to `download_rev.py`.
3. Why wasn't it backported to `download_more.py`? Same mechanism as
   BUG-0002/0003/0004: `download_more.py` is a stale duplicate script that
   didn't receive a fix applied to its sibling.
4. Why does this keep happening across so many unrelated files (LandFire
   downloads, negative sampling, now a second LandFire download pair)?
   Because PA-0002 (written for the first three instances) is a rule
   that has to be actively checked at every review pass, not something
   that, once written, prevents new instances on its own — each new file
   pair still has to be found and swept.

**Root cause:** same as BUG-0002/0003/0004 — a duplicate script exists
alongside its fixed/maintained sibling with no marker distinguishing them,
so a fix applied to one doesn't reach the other.

## 6. Corrective action
Backported directly (mechanically portable — same paradigm, same request/
response contract as `download_rev.py`, unlike the ArcGIS-vs-REST paradigm
mismatch that blocked backporting BUG-0002/0003's fix): added `import
rasterio`, the `MIN_VALID_PIXEL_FRAC` constant, `_raster_valid_fraction`,
and the validation call before `return task, "ok"` to `download_more.py`,
diffed character-for-character against `download_rev.py`'s equivalent
block to confirm an exact match. Verified: file parses. No CR required —
this is a same-paradigm, mechanically verified port matching the
precedent CR-0003-B set for `gen_negs.py`, not a new design decision.
**Status: CLOSED.**

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: **matches BUG-0002/
BUG-0003/BUG-0004** exactly — same root cause and mechanism (stale
superseded/duplicate script not receiving a backported fix), fourth
instance, in yet another subsystem (LandFire downloads, a second time,
independently of the `download_landfire*.py` cluster already fixed).

**Prior-preventive-action failure analysis:** PA-0002 already states the
rule at the mechanism level ("delete or explicitly mark deprecated... when
a script is copied or version-numbered"), and PA-0012 already called for
"a dedicated future sweep... before treating the set as closed." This
recurrence is not a failure of the rule's wording — it's evidence PA-0012's
recommended sweep had not yet been executed. Classified as **not yet
enforced**: the rule and the sweep obligation both existed, but the sweep
itself hadn't been run against files outside the originally-flagged
cluster (`download_landfire*.py`, `gen_negs.py`) until this follow-up
review pass found `download_more.py`/`download_rev.py` independently.

## 8. Preventive action
No new PA needed — this is covered by the existing PA-0002 (mechanism) and
PA-0012 (sweep obligation). This bug is recorded as the evidence that
PA-0012's sweep is not a one-time action: **PA-0012's text already says
this ("the sweep is not optional"), and this recurrence confirms it must
be re-run on every review pass, not just the one that introduced it.**
