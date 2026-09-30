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

## Versions
| version | change |
|---|---|
| v1 | initial draft (`TRAINING_INPUT_KINDS` in `grouse_data.py`) |
| v2 | list in `acceptance_split.json`; run-time guard on kinds read; pins and record re-issue stated; dispositions above |
