# CR-0028: One sightings schema for both acquisition scripts; readers select coordinate columns by name

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented. Latent defect; may be bundled with CR-0022's review since both touch acquisition.** Review log: `CR-0028-review-log.md`, to be created by the first reviewer.

## Scope
Define the columns every `data/sightings/{state}_sightings_{year}.csv` must carry, make `ebird.py` write them, and make the readers select them by exact name (BUG-0089; PA-0045).

## Why now
BUG-0089: `ebird.py` writes `lat`/`lng`; `analyze_grouse.py:174-177` and `check_partition.py:169-172` find coordinates by the substring "lon", so an eBird-API file is skipped with one print line, and both scripts write the same filename, so an eBird run silently displaces a GBIF file for that state and year. Latent today (all 43,024 raw rows are GBIF), which makes it cheap to fix before the eBird path is ever used.

## The change
### 1. Root cause
As BUG-0089 §5: two writers of one `PATH_TEMPLATES` entry emit different schemas, and the readers select columns by substring instead of by a shared column list.

### 2. Code (normative)
- `grouse_data.py`: `SIGHTINGS_REQUIRED_COLUMNS = ("decimalLongitude", "decimalLatitude")` (the GBIF names, which `sightings.py` already writes) with a comment naming both writers and both readers.
- `ebird.py`: writes `decimalLongitude`/`decimalLatitude` (renamed from `lng`/`lat`) in addition to its other columns, and a `source` column `"ebird-api"`; `sightings.py` adds `source = "gbif"`. No other column changes.
- `analyze_grouse.load_all_sightings` and `check_partition.load_raw`: select `SIGHTINGS_REQUIRED_COLUMNS` by exact name; a file lacking either raises `MissingDataError` naming the file and the missing column (fail closed, PA-0027) instead of being skipped.
- `tests/test_cr0028.py`: both writers' header lists (parsed from the source with `ast`, or from a one-row dry run where `requests` is stubbed) contain `SIGHTINGS_REQUIRED_COLUMNS`; a reader given a `lat`/`lng` file raises naming the columns.

### 3. Acceptance
None: no split file changes. E1p (raw CSV row comparison) is unaffected by the added `source` column (it compares the columns it names; verified in review).

## Impact
- No change for GBIF files (already conformant).
- An eBird-API file becomes loadable; mixing sources in one state/year remains a separate design question (§ Out of scope).
- A malformed sightings file now stops the run instead of vanishing.

## One change per CR (CR-0011 A5)
Acquisition and reader code with one shared constant and a test; no data change.

## Risk: LOW
| risk | mitigation |
|---|---|
| A stray non-sightings CSV in `data/sightings/` now raises instead of being skipped | The filename regex still filters; only files matching `{xx}_sightings_{yyyy}.csv` are read, and one of those lacking coordinates is a defect to surface |

## Test plan
**Validatable here:** the `ast`-based header test.
**Not validatable here:** a dry run of `ebird.py` (network).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0028.py` on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. Bookkeeping: BUG-0089 → FIXED; `BUG_LOG.md`; PA-0045 Swept? cell; BUG-0034's source-axis note updated; CHANGELOG.
- [ ] 4. Close-out.

## Out of scope
- Whether GBIF and eBird-API records may be mixed for one state and year (PA-0020 source axis; BUG-0034's note); a `source`-aware dedup is its own CR.
- `START_YEAR` duplication (BUG-0075).
