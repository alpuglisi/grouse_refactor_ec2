# CR-0021 review log

## Lineage
From BUG-0078 (2026-09-30 static review; spelling verified against the
LF2022/2023/2024 EVT attribute tables). Reviewers: two fresh agents
(CLAUDE.md §1.2, §1.4); review logs not read by them.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | REVISE | 1 |
| 1 | v1 | B (agent, fresh) | APPROVE WITH FOLLOW-UPS | 0 |
| 2 | v2 | A (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1 text) | 0 |
| 2 | v2 | B (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1 text) | 0 |

## Round 1, reviewer A
- **A1 BLOCKING:** §4's decision rule and MC omit the availability sample:
  the same filter sets `used` for background points (`:541`), so a
  rebuild flips Agricultural background rows → `avail_total`, every
  `Avail_Pct`/`Selection_Ratio` (`:915-921`), `env_zone` (`:955-966`) and
  many candidates' `weight` change; "MC requires exactly those rows to
  change" fails on the correct pipeline. A "0 flips → no rebuild" branch
  would leave the sample under the old filter while closing the BUG.
- A2 MEDIUM: positives' `nonveg_landcover` is taken from S as given
  (`:1000-1001`); E10 replays only C's flag; a stale `analyze_grouse` run
  passes every gate.
- A3 MEDIUM: live pinned crosswalk is LF2025 (`acceptance_split.json:208`);
  evidence covers LF2022–2024.
- A4 MEDIUM: fixture `nonveg_landcover` is random (`tests:241`); flipping
  7007 changes candidate counts; existence asserts to re-check; garbled
  fixture sentence (A4).
- A5 LOW: `SCLASS_NAMES` → `NON_VEG_SCLASS_LABELS` (`:110-113`); E1p/E9
  mis-cited (E10 replays the flag); `GATE_SECTION_SHA256["envelope"]`;
  `legacy/audit.py:128` duplicate (guarded); PA-0042 list absent.

## Round 1, reviewer B
- B1 MAJOR: same as A1 (MC contradicts §6; specify per file what is
  pinned exact and what is pre-registered, via replay subclass + control).
- B2 MEDIUM: same as A2 (add an exact check recomputing
  `nonveg_landcover` over S from `evt_phys`/`sclass` and the config).
- B3 MEDIUM: §3 test's no-dependency path: `analyze_grouse` imports
  rasterio etc. at module level; use AST extraction.
- B4 MAJOR: PA-0042 consumer list for `nonveg_landcover`/`is_nonveg`/
  `weight_basis`: `prepare_training_data.py:388`, `check_partition.py:463`,
  `check_exotic.py:121`, `dupe_check.py:72-121`, `clean.py` (guarded),
  E9/E10/O6.
- B5 LOW: `SCLASS_NAMES` name; garbled fixture sentence; availability
  `used` flips not pre-registrable from the recorded file (CR-0020 A1);
  `GATE_SECTION_SHA256` pin.

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location) |
|---|---|---|
| A1 / B1 | BLOCKING | **Accept** — §4 measures S, C and the availability sample; rebuild if any count > 0; MC replaced by pre-registration via a `Replay` subclass with a control (exact pins on the flipped S rows and availability rows by key; downstream outputs pre-registered), never "exactly those rows" |
| A2 / B2 | MEDIUM | **Accept** — §5 new exact gate E16: `nonveg_landcover` over S recomputed from `evt_phys`/`sclass` and the config equals S's column |
| A3 | MEDIUM | **Accept** — deliverable 1 runs the §3 test on the live LF2025 table and records its EVT_PHYS set in the evidence file |
| A4 / B5 | MEDIUM | **Accept** — §5: fixture derives `nonveg_landcover` from `evt_phys`/`sclass`; existence asserts re-checked (deliverable 2); garbled sentence replaced |
| B3 | MEDIUM | **Accept** — §3 test extracts the tuple by AST (`tests/test_shared_constants.py` pattern) and applies the regex with `re`; the pandas path is optional |
| B4 / A5 | MAJOR / LOW | **Accept** — § Impact PA-0042 consumer table |
| A5 / B5 | LOW | **Accept** — `NON_VEG_SCLASS_LABELS`; E10 cited; `GATE_SECTION_SHA256["envelope"]` in deliverable 2; `legacy/audit.py` noted as guarded |

## Round 2 (v2), reviewer A (bounded, CR-0011 A2)
A1 (BLOCKING), B1 and B4 (MAJOR) verified RESOLVED (the (c) predicate is
exact: `used` set at `analyze_grouse.py:541`, ids at `:548-549`;
pre-registered counts computable without weights).
- **A-N1 MAJOR:** the control "shows the unmodified replay reproduces
  today's files" fails by construction when a rebuild is needed: the
  config pin (deliverable 2) precedes the pre-registration (deliverable
  4) and the unmodified replay reads C's flag from the loaded config
  (`acceptance_split.py:731-732`).
- A-N2 MEDIUM: E16 trusts S's `evt_phys`; recompute it from `evt`
  through the pinned crosswalk first (as E10 does for C, `:727`).
- A-N3 LOW: PA-0042 list misses `legacy/gen_negs.py` (guarded) and
  `tune.py` (banner; BUG-0016).
- A-N4 LOW: fixture flag is at `:254` not `:241`; the AST extractor is
  `check_partition.literal_assignments`; the evidence `PHYS values:` list
  spans four lines; the expected set must be re-derived from LF2025.
- A-N5 LOW: prefixes verified regex-safe against the pinned vocabulary.

## Round 2 (v2), reviewer B (bounded, CR-0011 A2)
Same RESOLVED table (A1/B1, B4/A5, A2/B2).
- **B-N1 MAJOR:** the fixture change cannot exercise E16 and breaks a
  test: S's `evt` draw is `[7001..7004]` (`tests/test_acceptance_split.py:253`),
  so a derived `nonveg_landcover` is all-False; `test_null_year_sighting_raises`
  (`:1784`) then raises IndexError, and E16's attack differs from the
  reference only through the random flag; "~4 %" is the candidates'
  `EVT_P`, not S's.
- B-N2 LOW: `:241` → `:254`.
- B-N3 LOW: same as A-N2 (optional strengthening).
- B-N4 LOW: name `check_partition.py` among the post-rebuild checks; the
  pre-registration subclass runs under the amended config.

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-N1 | MAJOR | **Accept** — §4 last sentence: control = pre-CR replay under the pre-CR config (prefix list overridden), prediction under the new config; deliverable 4 |
| B-N1 | MAJOR | **Accept** — §5 fixture bullet: `evt` draw gains 7005–7007, border/near pairs kept on habitat codes as `evt` assignments, existence assertions for an Agricultural habitat-sclass row and a non-vegetated row per region; the "~4 %" figure removed |
| A-N2 / B-N3 | MEDIUM / LOW | **Accept** — §5 E16 recomputes `evt_phys` from `evt` through the pinned crosswalk; second attack row |
| A-N3 | LOW | **Accept** — § Impact PA-0042 list |
| A-N4 / B-N2 | LOW | **Accept** — §3 (`literal_assignments`, four-line list, LF2025 re-derivation), §5 cites `:253-256` |
| A-N5 | LOW | noted in §2 |
| B-N4 | LOW | **Accept** — §6 ends with `check_partition.py`; deliverable 4 names the configs |

## Versions
| version | change |
|---|---|
| v1 | initial draft |
| v2 | round-1 dispositions |
| v3 | round-2 dispositions above; approved by agent quorum |
