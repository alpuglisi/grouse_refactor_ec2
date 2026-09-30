# CR-0028 review log

## Lineage
From BUG-0089 (2026-09-30 static review). Author: the review session
that filed BUG-0089. Reviewers: two fresh agents, each re-deriving from
the code before reading the CR (CLAUDE.md §1.2, §1.4 agent-only quorum).
Review logs were not read by the reviewers.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | REVISE | 0 |
| 1 | v1 | B (agent, fresh) | REVISE | 1 |
| 2 | v2 | A (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1, N2 text) | 0 |
| 2 | v2 | B (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1 text) | 0 |

## Round 1, reviewer A
- A1 MAJOR: the `ast` header test cannot apply to `sightings.py`, which
  writes GBIF's whole frame and has no header literal; PA-0045's "pinned
  by a test" would hold for `ebird.py` only. Fix: a runtime check after
  `read_csv` (`:118`) that the required columns are present.
- A2 MAJOR: "renamed from `lng`/`lat`" is under-specified: renaming only
  `csv_headers` makes `extrasaction='ignore'` write empty coordinate
  columns; the exact-name reader accepts the header and `dropna` (`:188`)
  drops every row silently.
- A3 MEDIUM: `check_partition.load_raw` cannot raise `MissingDataError`
  (no `grouse_data` import, CR-0007 P3); use `c.get(...)` and `Missing`.
- A4 MEDIUM: E1p (`acceptance_split.py:1643-1673`) compares split files,
  not raw columns; it is unaffected because `load_all_sightings` keeps
  four columns (`:181`). "verified in review" is a verdict (A4).
- A5 MEDIUM (PA-0042): the `source` column has no reader and is absent
  from today's rows; list the sightings-file consumers and drop or
  justify it.
- A6 LOW: writers emit the basename into the CWD and
  `organize_project.py` relocates; say the shared list is a required
  subset and why that satisfies PA-0045; the bundling note is process.

## Round 1, reviewer B
- **B1 BLOCKING:** same mechanism as A2 with the failure made concrete:
  the v1 test (header via `ast`) passes on the wrong implementation, so
  the acceptance cannot fail (PA-0021(a)); required: a normative row
  remap, a row-level test, and a reader that raises on a matching file
  with zero non-null coordinates.
- B2 MAJOR: same as A1 (runtime check in `process_and_split_data`).
- B3 MEDIUM: same as A4; also `evidence/CR-0019/preregister.py:253` reads
  raw files with `usecols=["datasetKey", "year"]`.
- B4 MEDIUM: PA-0045 says "one schema, defined once as a shared column
  list"; state the deviation (two required columns; writers keep ~50 vs
  17) and why.
- B5 LOW: `MissingDataError` is a `FileNotFoundError`; a present file
  with a wrong header is a different error; `check_partition` reads
  constants by `ast` (`Consts`, `:114-130`) and its docstring `:158-160`
  changes.
- B6 LOW: same as A6 (CWD).

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location) |
|---|---|---|
| B1 / A2 | BLOCKING / MAJOR | **Accept** — §2 `ebird.py` bullet: module-level `CSV_HEADERS` and pure `to_row(obs)` with the value remap; § 3 row-level case; reader raises on rows without a coordinate pair, header-only file loads empty |
| A1 / B2 | MAJOR | **Accept** — §2 `sightings.py` bullet: runtime check after `read_csv`, `SystemExit` before any split file is written; § 3 fixture-zip case |
| A3 / B5 | MEDIUM / LOW | **Accept** — §2 `check_partition` bullet: `c.get("regions", ...)`, `Missing`, docstring; `analyze_grouse` raises `SystemExit` (its convention at `:186`), not `MissingDataError` |
| A4 / B3 | MEDIUM | **Accept** — § 3 first paragraph gives the real reason (no raw-file reader in `acceptance_split.py`; projection at `:181`) and notes `preregister.py:253`; "verified in review" removed |
| A5 | MEDIUM | **Accept** — `source` column dropped (§2 penultimate bullet); § Impact lists the PA-0042 consumers |
| A6 / B4 / B6 | LOW / MEDIUM / LOW | **Accept** — §2 second bullet states the required-subset reading of PA-0045 and why; last bullet states the CWD write and `organize_project.py`; bundling note removed |
| (author) | — | constant placed in `regions.py`, not `grouse_data.py`, so the acquisition scripts do not import rasterio; `Consts` already parses `regions.py` |

## Round 2 (v2), reviewer A (bounded, CR-0011 A2)
B1/A2 (BLOCKING/MAJOR) and A1/B2 (MAJOR) verified RESOLVED against the
code (`extrasaction='ignore'`, `dropna` at `:188`; the check precedes
every `to_csv`).
- **A-N1 MAJOR:** `tests/test_check_partition.py` writes a synthetic
  `regions.py` (`:118-119`) without the new literal; after §2 `Consts.get`
  raises `Missing` for every `x.raw()` caller (P3 `:409`, P4 `:445`,
  `box_source` `:363`) and the suite fails; the CR does not touch it.
- A-N2 MEDIUM: "`regions.py` is the dependency-free leaf" is false
  (`regions.py:24` imports numpy), so `to_row` cannot run here without
  a stub; the test-plan sentence is wrong.
- A-N3 LOW: `download_tcc_nlcd.sighting_years` reads positives/negatives;
  the filename-only reader is `RegionData.sighting_years`.
- A-N4 LOW: cites (`:120`, `:157-187`, `:158-161`, `preregister.py:252`).
- A-N5 LOW: `check_partition.P6_NAMES` (`:602-606`) should gain the name.
- A-N6 LOW: record the required-subset reading in PA-0045's rule cell.

## Round 2 (v2), reviewer B (bounded, CR-0011 A2)
Same RESOLVED table; `regions.py` as home confirmed allowed (`P6_EXEMPT`;
`p6_problems` pins only expected keys); `EXPECTED_REGIONS` pin is the
right enforcement.
- **B-N1 MAJOR:** the PA-0027 lint pin for `ebird.main`
  (`tests/test_pa0027_lint.py:169`) breaks when `main()` changes; absent
  from §2 and deliverables.
- B-N2 MEDIUM: same as A-N2 (stub numpy; import `ebird`; read
  `CSV_HEADERS` directly).
- B-N3 LOW: same as A-N3; `sightings.py` write is `:138`.
- B-N4 LOW: the zero-coordinate raise is per file, before
  `check_partition.load_raw`'s concat (`:177-178`); the harness fixture
  already uses the GBIF names (`:110-113`).

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-N1 | MAJOR | **Accept** — §2 `check_partition` bullet: the fixture `regions.py` gains the literal; § 3 last row; deliverable 1 |
| B-N1 | MAJOR | **Accept** — §2 `ebird.py` bullet: re-pin with owner unchanged; deliverable 2; § 3 last row |
| A-N2 / B-N2 | MEDIUM | **Accept** — §2 first bullet reworded; § 3 first row and § Test plan: numpy stub, `ebird` imported |
| A-N3 / B-N3 | LOW | **Accept** — § Impact consumer list; `:138` |
| A-N4 | LOW | **Accept** — cites corrected |
| A-N5 | LOW | **Accept** — deliverable 3: `P6_NAMES`; § Impact enforcement note |
| A-N6 | LOW | **Accept** — §2 second bullet and deliverable 3: rule-cell clarification (not a weakening) |
| B-N4 | LOW | **Accept** — §2 reader bullets: per file, before the concat; fixture note |

## Approval
| party | verdict | date |
|---|---|---|
| reviewer quorum (CLAUDE.md §1.4, agent-only) | APPROVE WITH FOLLOW-UPS (see Rounds) | 2026-09-30 |
| lead | APPROVE ("if the CR has passed the review process, I approve"; recorded by the author from the session) | 2026-09-30 |
| author | sign-off | 2026-09-30 |
Open MEDIUM/LOW follow-ups above go to the tracker at close-out.

## Versions
| version | change |
|---|---|
| v1 | initial draft |
| v2 | row remap and `to_row`; runtime check in `sightings.py`; constant in `regions.py`; `source` dropped; fail-closed readers; round-1 dispositions |
| v3 | harness fixture and lint re-pin; numpy stub; per-file checks; `P6_NAMES`; round-2 dispositions above; approved by agent quorum |
