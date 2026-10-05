# CR-0033 review log

Companion to `CR-0033-split-window-feature-list.md` (CR-0011 A4).

## Rounds
| round | text | reviewer | verdict | BLOCKING |
|---|---|---|---|---|
| 1 | v1 (`fa8bbc7`) | A: correctness (agent that raised CR-0032 A5; did not write this CR; read-only; re-derived the defect, swept producer-side feature readers) | APPROVE WITH FOLLOW-UPS | 0 (2 LOW) |
| 1 | v1 (`fa8bbc7`) | B: implementability, composition (read-only; ran the five existing suites: 214 tests, only failure the CR-0032 lint item B2-1) | APPROVE WITH FOLLOW-UPS | 0 (1 MEDIUM, 2 LOW) |

Quorum (CLAUDE.md §1.4): both reviewers and the author sign off. Approved
2026-10-05.

## Concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A33-1 | LOW | T2 spies `rasterio.open` only; the manifest coupling runs through `rd.rasters_touched` | accepted: T2 also asserts no `rasters_touched` entry names the extra feature | T2 |
| A33-2 | LOW | constant tied to the acceptance config only by a unit test (no CI) | tracked follow-up (tracker, owner: next split-pipeline CR): move it to `regions.py` and map it in `regions_py` so acceptance checks it at run time | Out of scope; tracker |
| B33-1 | MEDIUM | a wrong fix iterating `FEATURE_SPEC` ∩ available passes T1/T2 | accepted: second T2 variant with the extra raster on disk (corner extent); author verified that wrong fix fails it, the CR's fix passes, today's body fails both variants | T2 |
| B33-2 | LOW | "subset of `FEATURE_SPEC`" re-couples split to model | accepted: assertion removed; T1 says why | T1 |
| B33-3 | LOW | byte-unchanged claim rests on checks worth citing | accepted as stated by the reviewer (no change needed): `list(FEATURE_SPEC)` equals the 15 names in order; `rasters_touched` is filled only via `raster_path`; no other split-path reader of `FEATURE_SPEC` (A's sweep: `ENVELOPE_FEATURES`, `analyze_grouse.FEATURES`, `year_filled` use their own lists) | this log |
