# CR-0028: One sightings schema for both acquisition scripts; readers select coordinate columns by exact name

**Status: v3, 2026-09-30 — APPROVED by agent quorum and signed off by the lead on 2026-09-30 (CLAUDE.md §1.4; round 2: reviewers A and B both APPROVE WITH FOLLOW-UPS, conditional on the `check_partition` fixture and the PA-0027 lint re-pin being in the operative text; met in v3 §2/§3 and deliverables 1–2). Nothing has been implemented; the lead has signed off; implementation may begin (deliverables that need the data host wait for one).** Review log: `CR-0028-review-log.md`.

## Scope
Define, once, the columns every file at `PATH_TEMPLATES["sightings"]` must carry; make `ebird.py` write them with the values, make `sightings.py` refuse a download that lacks them, and make both readers select them by exact name and fail closed (BUG-0089; PA-0045). Latent defect (every raw row today is GBIF); no data change.

## Why now
BUG-0089: `ebird.py` writes `lat`/`lng` (`:35-40`); `analyze_grouse.py:174-177` and `check_partition.py:169-172` find coordinates by the substring "lon", so an eBird-API file is skipped with one print line, and both scripts write the same filename, so an eBird run silently displaces a GBIF file for that state and year. Cheap to fix before the eBird path is ever used.

## The change
### 1. Root cause
As BUG-0089 §5: two writers of one `PATH_TEMPLATES` entry emit different schemas, and the readers select columns by substring instead of by a shared column list.

### 2. Code (normative)
- `regions.py`: `SIGHTINGS_REQUIRED_COLUMNS = ("decimalLongitude", "decimalLatitude")` — the GBIF names, which `sightings.py` already writes — with a comment naming both writers and both readers. `regions.py` is the leaf both acquisition scripts already import (`sightings.py:7`, `ebird.py:7`) and `check_partition.Consts` already parses (`:120`); its only module-level third-party import is numpy (`:24`, used inside functions), whereas `grouse_data.py` would make the acquisition scripts import rasterio.
- The shared list is the **required subset**, not the full row: GBIF SIMPLE_CSV rows keep their ~50 columns and eBird rows their 16, because the readers use only the two coordinates plus the state and year parsed from the filename (`analyze_grouse.py:181`, `check_partition.py:174-176`). Deliverable 3 records this reading in PA-0045's rule cell as a clarification, not a weakening: the rule's mechanism, exact-name selection from one pinned list, is what this CR implements; a writer may carry more columns than the list.
- `ebird.py`: the header list becomes module-level `CSV_HEADERS`, with `lat`, `lng` replaced by the two GBIF names; a module-level pure `to_row(obs)` returns `dict(obs)` plus `decimalLatitude = obs["lat"]` and `decimalLongitude = obs["lng"]` (a missing key raises, fail closed); the loop writes `writer.writerow(to_row(s))`. A header-only rename would leave the two columns empty under `extrasaction='ignore'` (`:65`) and the reader's `dropna` (`analyze_grouse.py:188`) would then discard every row silently; the row remap is therefore normative and tested at row level. `main()` changes, so its PA-0027 lint pin (`tests/test_pa0027_lint.py:169`, `('ebird.py', 'main', 0)`, owner BUG-0013) is re-pinned in the same change with the owner unchanged.
- `sightings.py`, `process_and_split_data`: after `read_csv` (`:118`) and before the split loop (`:130`) writes anything (`:138`), `missing = [c for c in SIGHTINGS_REQUIRED_COLUMNS if c not in df.columns]`; if any, `raise SystemExit(...)` naming the file and the missing columns. (`sightings.py` writes GBIF's whole frame and has no header list to pin; the runtime check is its writer-side guarantee.)
- `analyze_grouse.load_all_sightings` (`:160-186`): select `SIGHTINGS_REQUIRED_COLUMNS` by exact name and rename to `longitude`/`latitude`; per file, a matching file lacking either column raises `SystemExit` naming the file and the column (the script's fail-closed convention, `:186`; PA-0027), replacing the print-and-skip at `:176-177`; a matching file with rows but no non-null coordinate pair raises likewise (a schema mismatch), while a header-only file loads as zero rows (an eBird year with no grouse record is legitimately empty).
- `check_partition.load_raw` (`:157-187`): the same per-file selection and checks, before its concat and filter (`:177-178`), via `c.get("regions", "SIGHTINGS_REQUIRED_COLUMNS")` (a tuple literal, `literal_eval`-able) and `raise Missing(...)` (its own exception; it may not import `grouse_data` or `regions`, CR-0007 P3); docstring `:158-161` updated. `tests/test_check_partition.py` writes a synthetic `regions.py` into its fixture root (`:118-119`) that `Consts` parses; it gains the new literal (its raw fixture files already use the GBIF names, `:110-113`), otherwise `Consts.get` raises `Missing` for every `x.raw()` caller (P3, P4, `box_source`) and the suite fails.
- No `source` column (v1 had one): it would have no reader (`load_all_sightings` keeps four columns, `:181`) and is absent from today's 43,024 rows; a source-aware dedup is § Out of scope.
- Both writers emit the template's basename into the working directory (`sightings.py:138`, `ebird.py:48`) and `organize_project.py:63-76` moves the files under `data/sightings/`. Unchanged.

### 3. Acceptance
None on the split files: `acceptance_split.py` never reads the raw files (its `paths.sightings` is `evaluated_sightings_{region}.csv`, `acceptance_split.json`), and `load_all_sightings` projects every raw row to four columns (`:181`), so no raw-column change reaches a digested artifact. (`docs/quality/evidence/CR-0019/preregister.py:252` reads raw files with `usecols=["datasetKey", "year"]`; historical evidence, not re-run.)
`tests/test_cr0028.py` (PA-0021(a): each row fails on today's code):
| case | assertion |
|---|---|
| `ebird.to_row` on a fixture observation with `lat`/`lng` | the row carries the same values under `decimalLatitude`/`decimalLongitude`; `ebird.CSV_HEADERS` contains `SIGHTINGS_REQUIRED_COLUMNS`. The test stubs `sys.modules["numpy"]` (`regions.py:24`) and imports `ebird` (`requests` is present here) |
| `sightings.process_and_split_data` on a fixture zip whose TSV lacks `decimalLongitude` | `SystemExit`; no split file written (needs pandas) |
| `check_partition.load_raw` on a directory with one `lat`/`lng` file | `Missing` naming the file and column; a file with rows and empty coordinates: `Missing`; a header-only file: zero rows, no error |
| `analyze_grouse.load_all_sightings` | the same three cases (needs rasterio; data host) |
| `tests/test_pa0027_lint.py` and `tests/test_check_partition.py` | pass after the change (the former re-pinned, the latter's fixture extended) |

## Impact
- No change for GBIF files (already conformant).
- An eBird-API file becomes loadable; mixing sources in one state/year remains a separate design question (§ Out of scope).
- A malformed sightings file stops the run instead of vanishing.
- PA-0042 consumers of the sightings files: `analyze_grouse.load_all_sightings` and `check_partition.load_raw` (both change here), `RegionData.sightings()` (`grouse_data.py:521-523`; no tracked caller), `RegionData.sighting_years` (`:525-539`; filename only), `organize_project.py` (moves files). `download_tcc_nlcd.sighting_years` reads the positives and negatives files, not the raw ones.
- PA-0045's mechanical enforcement: the `EXPECTED_REGIONS` pin makes `check_partition.scan_source` flag any other file assigning a literal to `SIGHTINGS_REQUIRED_COLUMNS` once the name is in `P6_NAMES`.

## One change per CR (CR-0011 A5)
Acquisition and reader code with one shared constant and a test; no data change.

## Risk: LOW
| risk | mitigation |
|---|---|
| A stray non-sightings CSV in `data/sightings/` now raises instead of being skipped | The filename regex still filters (`analyze_grouse.py:163`, `check_partition.py:154`); only files matching `{xx}_sightings_{yyyy}.csv` are read, and one of those lacking coordinates is a defect to surface |

## Test plan
**Validatable here:** the `to_row`/`CSV_HEADERS` case (numpy stubbed) and `tests/test_pa0027_lint.py` (pure Python); the `check_partition.load_raw` cases and `tests/test_check_partition.py` need pandas (absent here).
**Not validatable here:** the `sightings.py` fixture-zip case (pandas), the `analyze_grouse` cases (rasterio), a dry run of `ebird.py` (network).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0028.py` and the `tests/test_check_partition.py` fixture extension on an unmerged branch.
- [ ] 2. Code (§2); `tests/test_pa0027_lint.py` `ebird.main` entry re-pinned (owner BUG-0013 unchanged); the lint run here.
- [ ] 3. Bookkeeping: BUG-0089 → FIXED; `BUG_LOG.md`; PA-0045 rule cell clarification and Swept? cell; `tests/test_shared_constants.py` `EXPECTED_REGIONS` and `check_partition.P6_NAMES` (`:602-606`) gain the new literal (PA-0001/PA-0025 pins); BUG-0034's source-axis note updated; CHANGELOG.
- [ ] 4. Close-out.

## Out of scope
- Whether GBIF and eBird-API records may be mixed for one state and year (PA-0020 source axis; BUG-0034's note); a `source`-aware dedup is its own CR.
- `START_YEAR` duplication (BUG-0075).
