# Preventive Actions (enforced policy)

Single, distilled, no-background rule list. Every entry here is mandatory
to consult before making a change — not advisory. See `CLAUDE.md` §3 for
how entries are added and superseded. No prose justification here; each
entry links back to its bug investigation for the full story.

Append-only: never delete or water down a rule. A superseded rule stays
listed and says what replaced it.

| ID | Rule | Source |
|----|------|--------|
| PA-0001 | Never duplicate a geographic/spatial constant (bounding box, CRS, buffer distance) across files. Extract it to one shared, imported module (e.g. `regions.py`). | BUG-0001 |
| PA-0002 | When a script is copied or version-numbered (`foo_2.py`, `foo_rev.py`) to apply a fix or add a feature, delete or explicitly mark the superseded original as deprecated in the same change — never leave a stale runnable copy carrying the old defect. Applies repository-wide, not just to one pipeline's scripts (confirmed by BUG-0002/0003 in the download scripts and BUG-0004 in the negative-sampling scripts — three independent instances of this mechanism across unrelated subsystems). | BUG-0002; confirmed/generalized by BUG-0003, BUG-0004 |
| PA-0003 | Any path/glob pattern that should describe the same location as an existing `PATH_TEMPLATES` (or equivalent) entry must be derived from that template, never re-hardcoded as an independent string. | BUG-0005 |
| PA-0004 | Never commit literal credentials (passwords, API keys, tokens) in source. Read them from environment variables or a git-ignored local secrets file. | BUG-0006 |
| PA-0005 | When deduplicating on rounded/normalized values, build the dedup key as its own variable first (e.g. `key = df[cols].round(n)`) and dedupe on that key directly — never chain `.round()` into `.columns` expecting it to carry the rounding into a `subset=` argument. | BUG-0007 |
| PA-0006 | Raster nodata/mask handling must use a dedicated mask array (or NaN for continuous layers) to distinguish sentinel nodata from a legitimate value of `0`, never overload `0` for both, and must not gate masking on a comparison (`nodata != 0`) that is defeated when the dataset's true nodata value is itself `0`. | BUG-0008 |
| PA-0007 | When building an output raster's Affine transform from patch/tile center coordinates, explicitly convert center to corner convention (subtract half a pixel in each axis) — never assign a center coordinate directly as the transform's corner constant. | BUG-0009 |
| PA-0008 | A model checkpoint's stored config/metadata must be validated against (or used to reconstruct) the loading handler on every `load()` call, not merely saved — a loader that discards it and trusts the caller's own constructor defaults can silently run architecture variants that share parameter shapes with the checkpoint's true training configuration. | BUG-0010 |
| PA-0009 | Extends PA-0008. Diagnostic/tooling scripts that load a real checkpoint must construct the model with the same defaults the training entrypoint uses (or, once available, read them from the checkpoint per PA-0008), and must not narrow their exception handling to only the error they expect — an unexpected `RuntimeError` from a mismatched load should be caught and reported, not left to crash the whole diagnostic. | BUG-0011 |
| PA-0010 | A function that conditionally populates a dict key must have every downstream consumer either guard on the same condition or use `.get()` with an explicit default — never mix unconditional indexing with conditional population of the same key in the same code path. | BUG-0012 |
| PA-0011 | Prefer narrow exception types (e.g. `requests.exceptions.RequestException`) over bare `except Exception` in retry/polling loops; if a broad catch is necessary, log the exception type and traceback before continuing so a programming error isn't silently treated as a transient failure. | BUG-0013 |
| PA-0012 | Whenever a new "stale superseded copy" instance is found (per PA-0002), sweep the repository for other file-name-similarity clusters (numbered/`_rev`/`_more`-style siblings) and diff them for un-backported fixes — do not assume a single review pass has found every instance. This review's pass covered all 33 root-level `.py` files and found three clusters (BUG-0001's `audit.py`/`analyze_grouse.py`, BUG-0002/0003's `download_landfire*.py` trio, BUG-0004's `gen_negs.py`/`generate_negatives.py` pair); a dedicated future sweep is still recommended before treating the set as closed. | BUG-0004 |
