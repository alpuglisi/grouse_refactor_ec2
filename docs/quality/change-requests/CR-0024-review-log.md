# CR-0024 review log

## Lineage
From BUG-0080 (2026-09-30 static review). Author: the review session
that filed BUG-0080. Two fresh agents were spawned for round 1
(CLAUDE.md §1.2, §1.4 agent-only quorum); only one report (B) reached the
session before its context was reset, and the other could not be
recovered. Round 2 therefore pairs a bounded re-review of v2 (CR-0011 A2)
with an unrestricted first review of v2 by a second fresh agent, so that
two independent verdicts are recorded before approval. Review logs were
not read by the reviewer.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | report not received | — |
| 1 | v1 | B (agent, fresh) | REVISE | 1 |
| 2 | v2 | B2 (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS | 0 |
| 2 | v2 | A (agent, fresh; unrestricted first review, fills the round-1 slot) | REVISE | 0 |
| 3 | v3 | C (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS | 0 |

## Round 1, reviewer B
- **B1 BLOCKING:** §2 places `TRAINING_INPUT_KINDS` in `grouse_data.py`
  and derives `standing_csv_paths` from it; `grouse_data.py` imports
  pandas and rasterio at module level (`:36-37`). Two committed tests
  fail: `tests/test_acceptance_split.py:2264-2268` (AST) forbids
  `acceptance_split.py` importing `grouse_data`, and `:1960-1969` asserts
  `rasterio` is absent from `sys.modules` after `standing_checks`
  (CR-0013's design, review log B-C12). Remedy: the list in
  `acceptance_split.json` (`standing.kinds`) or in `acceptance_split.py`,
  with `train.py` asserting against it; a JSON change alters the config
  sha and the `standing` pin at `:2039`.
- B2 MAJOR: PA-0037's second clause unaddressed: CR-0015's V1 gate on
  what `sample_background_points` produces runs once; binding B covers
  the input, not the producer. Acceptable as a tracked follow-up.
- B3 MAJOR: the recording test can pass vacuously: B is read only when
  `background_per_pos > 0` (`train.py:365-374`), and a subset assertion
  cannot detect a future unbound consumer unless every consumer path is
  exercised; no real `build_datasets` fixture exists
  (`tests/test_cr0012.py:385-396` mocks), so the test needs the data host.
- B4 MEDIUM: the risk row ("missing digest") cannot occur (the record
  already digests all 20, `:2782`), and "config sha changes" is false
  unless the list moves into the JSON.
- B5 MEDIUM: `thinned_positives` and `negatives` are in the constant but
  `build_datasets` never reads them; they are standing because E6/E14
  read them. Define the list as consumer inputs ∪ standing-gate inputs
  and pin both directions.
- B6 LOW: E6 `include_B=True` is redundant with the digest (fine as
  defence); label the digest as the GATE; add a source pin for the E6
  tuple like `test_e14_in_standing_subset_without_C` (`:1870-1872`).
- Checked and sound: E6's B branch uses only pandas/numpy paths already
  exercised standing; `standing_checks` compares `arts.get(rel)` so B
  works against the existing record; the relabel test is an exact
  predicate; 18→19 pin at `:2239`; `candidate_pool` correctly out of scope.

## v2 dispositions
| # | sev | disposition (operative location) |
|---|---|---|
| B1 | BLOCKING | **Accept** — §2 first bullet: the list is `cfg["standing"]["kinds"]` in `acceptance_split.json`; `standing_csv_paths` derives from it; `grouse_data.py` holds no list; the `standing` pin and config sha change are named in §2 and § Impact |
| B2 | MAJOR | **Accept as tracked follow-up** — § Impact last bullet and deliverable 4: tracker item naming `sample_background_points`' output as unbound, with BUG-0074 |
| B3 | MAJOR | **Accept** — §2 fourth bullet replaces the recording test with a run-time guard on `GrouseData.csv_kinds_read` (checked on every build, so no consumer path can be unexercised); § 3 gives the harness unit test (fake `GrouseData`) and the data-host run with `background_per_pos=0.05` |
| B4 | MEDIUM | **Accept** — § Risk and § Impact rewritten: the record already carries B's digest; the config sha changes because the `standing` section changes |
| B5 | MEDIUM | **Accept** — §2 first bullet defines the list as consumer inputs ∪ standing-gate inputs; the guard pins consumer ⊆ list, the paths test pins list == standing paths |
| B6 | LOW | **Accept** — § 3 labels the digest GATE and E6-with-B as defence; §2 last bullet adds the source pin |

## Round 2 (v2), reviewer B2 (bounded, CR-0011 A2)
B1 (BLOCKING), B2 and B3 (MAJOR) verified RESOLVED; the config-sha,
`rpath`, 19/20 counts and PA-0021(a) rows re-derived.
- B2-N1 MEDIUM: the guard is blind to `path()`-based reads (`rd.path(kind)`
  + `pd.read_csv`); record in `path()` or state the limit.
- B2-N2 MEDIUM: two kind namespaces compared by name (`PATH_TEMPLATES`
  keys vs config `paths` keys: `thinned` vs `thinned_positives`, raw vs
  evaluated `sightings`); compare resolved relative paths instead.
- B2-N3 LOW: the cited harness (`tests/test_cr0012.py:385-396`) stops at
  `split_features`; the guard test needs `regions=[]` and the guard
  before the `return` at `train.py:394`; `standing_checks` returns
  `True`, not `cfg`.
- B2-N4 LOW: the data-host row exercises the BUG-0074-forbidden path.
- B2-N5 LOW: A5 sentence inaccurate.
- B2-N6 LOW: keep `digested_paths`' region-outer order (record bytes).

## Round 2 (v2), reviewer A (unrestricted first review)
Diagnosis re-derived and confirmed; every §2–3 / Impact citation
verified; import constraints, `rpath` derivation, the digest row's
ability to fail, the record-already-digests-B claim and the PA-0037
third-clause tracker item all confirmed.
- **A-1 MAJOR:** a config-owned standing list is a downgrade vector
  (CR-0013 design rule 3; `load_config` floors `:101-110`): editing
  `standing.kinds` shrinks the digest set unseen by the guard. Remedy: a
  code floor, or keep the list in `acceptance_split.py` (no `grouse_data`
  import needed), which also removes the config-sha change and the
  record re-issue.
- **A-2 MAJOR:** the guard checks accessor-mediated reads, not "what was
  actually read" (`RegionData.path()` `:267-284`, `GrouseData.path()`
  `:557-567` resolve without recording; `sample_background_points`
  takes `assignments` as an argument). Remedy: record in `path()`.
- A-3 MEDIUM: "E6 with B" cannot fail on the header-swap scenario
  (`gate_E6` skips silently when the columns are absent, `:1787-1790`;
  standing E0 runs with `("P", "N")`, `:2836`).
- A-4 MEDIUM: `cfg` is not available in `build_datasets`
  (`standing_checks` returns `True`); the cited harness never reaches
  the guard.
- A-5 MEDIUM: nothing pins that the files the standing gates read are in
  the list (`Context.csv`, `:1495-1500`).
- A-6 LOW: A5 "cannot be separated" is not true.
- A-7 LOW (A4): counts repeated.
- A-8 LOW: the re-issue's E11 environment-equality risk (moot if the
  list lives in code).

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-1 | MAJOR | **Accept** — §2 first bullet: `STANDING_KINDS` in `acceptance_split.py`; no config change, no re-issue; § Impact and deliverable 3 |
| A-2 / B2-N1 | MAJOR / MEDIUM | **Accept** — §2 fourth bullet: recording in `RegionData.path` and `GrouseData.path` for every `.csv` kind regardless of `must_exist` |
| B2-N2 | MEDIUM | **Accept** — §2 fourth bullet: `csv_paths_read` holds relative paths compared with `standing_csv_paths(cfg)` |
| A-3 | MEDIUM | **Accept** — §2 third bullet: standing E0 with `("P", "N", "B")`; E6 reports a B without the columns; § 3 header-swap case |
| A-4 / B2-N3 | MEDIUM / LOW | **Accept** — §2: `standing_checks` returns `cfg`; guard placed after the region loop before `:394`; § 3 harness test with `regions=[]` and a fake `GrouseData` |
| A-5 | MEDIUM | **Accept** — §2 third bullet: post-gate assertion on `ctx._csv`; § 3 gate-side row |
| A-6 / B2-N5 | LOW | **Accept** — § One change per CR reworded |
| A-7 | LOW | **Accept** — counts stated in §2, § 3 refers |
| A-8 | LOW | moot (list in code); noted |
| B2-N4 | LOW | **Accept** — § 3 consumer-guard row: guard exercise only, no checkpoint |
| B2-N6 | LOW | **Accept** — §2 second bullet: today's order kept |

## Round 3 (v3), reviewer C (bounded, CR-0011 A2)
B1–B3, A-1 and A-2/B2-N1 verified RESOLVED against the code (the
config `standing` section and its pin unchanged; `gate_E0` accepts "B",
`:1548`, `:1576-1577`; `gate_E6` skips silently at `:1790`; `Context._csv`
keys are `rpath` rels; path namespaces identical; the guard cannot refuse
a correct run). No BLOCKING or MAJOR.
- C-N3-1 MEDIUM: "every CSV load in the module goes through `path()`" is
  false: `GrouseData.evt_crosswalk` (`grouse_data.py:598-606`) reads from
  a glob (a PA-0003 residual; not read at training time).
- C-N3-2 LOW: E0 reads headers through `read_header(ctx.full(rel))`
  (`:1556`), bypassing `_csv`.
- C-N3-3 LOW: `digested_paths` is `:119-123`; `write_json_atomic` sorts
  keys, so list order is not load-bearing.
- C-N3-4 LOW (A4): 19/20 repeated.
- C-N3-5 LOW: a region outside `cfg["constants"]["REGIONS"]` is now
  refused by the guard; state it.
- C-N3-6 LOW: BUG-0080 §3's restored file may or may not differ in
  header; soften.
- C-N3-7 LOW: `RegionData` has no back-reference to its `GrouseData`
  (`:255-258`, `:588-592`).

## v4 dispositions (round 3)
| # | sev | disposition (operative location) |
|---|---|---|
| C-N3-1 | MEDIUM | **Accept** — §2 fourth bullet names the `evt_crosswalk` exception |
| C-N3-2 | LOW | **Accept** — §2 third bullet: E0 bound by its tuple's source pin |
| C-N3-3 | LOW | **Accept** — §2 second bullet: `:119-123`; order kept for readability only |
| C-N3-4 | LOW | **Accept** — § 3 must-change row refers to §2 |
| C-N3-5 | LOW | **Accept** — § Impact first bullet |
| C-N3-6 | LOW | **Accept** — § 3 E0/E6 row softened |
| C-N3-7 | LOW | **Accept** — §2 fourth bullet: `_data` back-reference set in `__getitem__` |

## Versions
| version | change |
|---|---|
| v1 | initial draft (`TRAINING_INPUT_KINDS` in `grouse_data.py`) |
| v2 | list in `acceptance_split.json`; run-time guard on kinds read; pins and record re-issue stated; round-1 dispositions |
| v3 | list code-owned (`STANDING_KINDS`); path recording in `path()`; guard on relative paths; E0/E6 with B; gate-side assertion; no re-issue; round-2 dispositions |
| v4 | `evt_crosswalk` exception; E0 header reads; back-reference; round-3 dispositions above; approved by agent quorum |
