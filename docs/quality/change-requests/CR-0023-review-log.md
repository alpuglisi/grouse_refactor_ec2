# CR-0023 review log

## Lineage
From BUG-0079 (2026-09-30 static review). Author: the review session
that filed BUG-0079. Two fresh agents were spawned for round 1
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
| 1 | v1 | B (agent, fresh) | REVISE | 2 |
| 2 | v2 | B2 (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1 text) | 0 |
| 2 | v2 | A (agent, fresh; unrestricted first review, fills the round-1 slot) | REVISE | 0 |

## Round 1, reviewer B
- **B1 BLOCKING:** §4 cannot be implemented: there are no "E11(b)
  fallback records" (feature, year → resolved year) anywhere;
  `manifest_schema.inputs` is a digest map, `prepare_training_data.py:323-326`
  records `rasters_touched` digests only, `standing_checks` (`:2798-2848`)
  reads the record, never the manifest. Also the wrong artifact: a
  truncation after acceptance changes the raster fingerprint (`:2830-2836`);
  one before acceptance makes `Rasters.raster_path` (`:479-496`) fall back
  silently too. Remedy: drop §4; the refusal in `GrousePatchDataset.__init__`
  is the standing gate.
- **B2 BLOCKING:** §3's tolerance-conditioned refusal weakens PA-0036(b)
  (CLAUDE.md §3.6). Scenario: `NH_2023_tsd.tif` invalid; 2022/2024/2025
  valid; `raster_path` picks 2025 (most recent, `:392-397`), gap 2 ≤ tol,
  accepted with a warning: every 2023 record trains on the 2025
  disturbance clock, the invariant BUG-0079 was filed for. Remedy:
  `on_fallback="raise"` refuses unconditionally on the training path.
- B3 MAJOR: `max_year_gap=-1` sets `tol=-1` (`grouse_data.py:367-368`),
  so with `on_fallback="raise"` everything is refused while the CR says
  "-1 disables".
- B4 MAJOR: `_is_valid_raster` (`:308-330`) accepts any openable file
  with ≥ 1 % non-nodata; an interrupted run whose `finally` closed the
  handle leaves a well-formed partial file that passes validation. Only
  §2 prevents it; the test plan must assert `_is_valid_raster` is False
  for the truncation it uses and exercise the `finally` path with an
  injected exception (SIGTERM bypasses `finally`).
- B5 MEDIUM: `_score_teacher_probs` (`train.py:257-283`) builds its own
  dataset without the refusal and runs before `p_tr`.
- B6 MEDIUM (A5): writers, reader and acceptance are three independently
  landable parts; at minimum split §4 out.
- B7 MEDIUM (PA-0021(d)): no GATE/OBS labels; "a 1-year fallback passes"
  describes a row that should not exist under PA-0036(b).
- B8 LOW: citations: treemap `finally` at `:359` not `:345`; "PA-0020
  Swept?" left with a question mark; `document_tree.sh` has no `.tmp`
  handling; `_source_is_valid` lives in `generate_treemap_features.py:149`.
- B9 LOW: sweep gaps for PA-0036's Swept? cell: `download_tcc_nlcd.py:467`
  no-template branch copies the final path directly;
  `train.sample_background_points` (`:166-167`) labels rows with
  `max(raster_years)` while validity comes from `latest_raster_path`.
- B10 LOW: state the patch-cache argument in Impact.
- Checked and sound: `.tmp` invisible to `raster_years`; `os.replace`
  same directory; `calibrate.py:343` unaffected; `smoke_test_training.py`
  default preserved; `_raster_validity_cache` shared through
  `GrouseData.__getitem__`.

## v2 dispositions
| # | sev | disposition (operative location) |
|---|---|---|
| B1 | BLOCKING | **Accept** — §4 (v1) removed; § Out of scope records why; § 4 (v2) G1 makes the dataset refusal the gate |
| B2 | BLOCKING | **Accept** — §3 first bullet: unconditional refusal, `max_year_gap` not involved; § Impact states the placeholder consequence as intended |
| B3 | MAJOR | **Accept, resolved by B2** — §3: `max_year_gap` is not passed by the refusing callers; the `-1` semantics stay `filter_by_year_gap`'s alone |
| B4 | MAJOR | **Accept** — § 4 G1 asserts `_is_valid_raster` is False for the truncation used; G4 injects an exception into the stripe loop and keeps the SIGTERM case; the paragraph after the table states the partial-well-formed case |
| B5 | MEDIUM | **Accept** — §3 third bullet: six constructions including `_score_teacher_probs` |
| B6 | MEDIUM | **Accept in part** — §4 split out (dropped); writers and reader kept together with the justification in § One change per CR; the two-CR alternative recorded here |
| B7 | MEDIUM | **Accept** — § 4 table with GATE labels and a must-change row; the 1-year row is gone |
| B8 | LOW | **Accept** — `:359-363`; `document_tree.sh` sentence removed; `_source_is_valid` cited at `generate_treemap_features.py:149`; PA-0020 reference removed |
| B9 | LOW | **Accept** — `download_tcc_nlcd.py:467-468` added to §2; `sample_background_points` recorded in § Impact for PA-0036's Swept? cell and § Out of scope (BUG-0074) |
| B10 | LOW | **Accept** — §3 last bullet |

## Round 2 (v2), reviewer B2 (bounded, CR-0011 A2)
B1–B4 verified RESOLVED against the code (fallback loop `grouse_data.py:392-407`;
`tol=-1` unreachable by the refusing callers; `_emit` at
`generate_time_since_disturbance.py:352`); healthy-tree verdict of
`filter_by_year_gap` shown unchanged; `on_fallback` threading at
`dataset.py:126` feasible; A5 justification adequate; Swept? items
verified.
- **B2-N1 MAJOR (PA-0021(a)):** G3 cannot fail for the defect it exists
  to catch: `filter_by_year_gap` runs at `train.py:339-350` before
  `soft_labels_for` (`:356`), so with the default tolerance G3 passes
  even if `_score_teacher_probs` never received `on_fallback`.
- B2-N2 MEDIUM: G4 has an injection for one of five writers only.
- B2-N3 MEDIUM: §2 does not fix the order of close vs replace; an
  `else: os.replace` inside the existing `try/finally` runs before the
  handles close and can publish a truncated file on a close-time error.
- B2-N4 LOW: the must-change row needs a pin (`_path_for`/`_cache_key`
  equality between warn and raise).
- B2-N5 LOW: G2's message; whether the `if ys` skip (`:243`) is kept.
- B2-N6 LOW: cites (`:324-327`, `:336-342`).
- B2-N7 LOW: tie rule; invalid `on_fallback` value.

## Round 2 (v2), reviewer A (unrestricted first review)
Diagnosis re-derived and confirmed; six constructions confirmed to be
all; `.tmp` invisibility verified across every raster glob; `--an-background`
patch reads covered by the dataset refusal; PA-0027 lint digest untouched.
- **A-1 MAJOR:** same mechanism as B2-N3, with the remedy: success flag,
  close in `finally`, then validate (`rasterio.open(tmp)`, shape, one
  window) and replace after the statement; `with` sites need an explicit
  unlink on exception.
- **A-2 MAJOR:** PA-0036(a) not fully met: two direct final-path writers
  of the same call shape missed: `generate_treemap_features.py:518-522`
  (sibling-year `shutil.copy2` fan-out) and `download_rev.py:416-431`
  (`copy_topo_baselines`, `shutil.copy`); PA-0044 requires the search to
  be recorded; CSV direct writers to be listed with an owner.
- A-3 MEDIUM: §3 raises `MissingDataError` where G2 asserts `SystemExit`;
  § Impact says `filter_by_year_gap` gains a keyword while §3 always
  passes `"raise"`; `tests/test_cr0019.py:328-332` `FakeRD` breaks.
- A-4 MEDIUM: G4 per site.
- A-5 MEDIUM: the pipeline producers (`prepare_training_data.window_mask:177`,
  `generate_negatives.extract_envelope:229`) and the acceptance
  `Rasters.raster_path` (`acceptance_split.py:479-493`) keep the fallback;
  state the pre-acceptance consequence.
- A-6 LOW: the "must-change" row is the must-not-change side.
- A-7 LOW: cites (CHANGELOG `:502` not ARCHITECTURE.md; `dataset.py:125-127`;
  `train.py:226-265`; `predict.open_aligned_sources:177-180`).
- A-8 LOW: `nearest=False` still falls through to the fallback
  (`generate_road_distance.py:334`).
- A-9 LOW: return the resolved year rather than regex-parse the filename.

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| B2-N1 | MAJOR | **Accept** — § 4 G3: `train_year_gap=-1`, `standing_checks` mocked, `MissingDataError` from the `_score_teacher_probs` construction |
| A-1 / B2-N3 | MAJOR / MEDIUM | **Accept** — §2 ordering rule: success flag, close in `finally`, validate and replace after the statement; `with` sites unlink on exception |
| A-2 | MAJOR | **Accept** — §2 table: seven sites including the fan-out and `copy_topo_baselines`; the search recorded; CSV writers listed with owners; deliverable 5 corrects the Swept? cell |
| A-3 | MEDIUM | **Accept** — §3 `filter_by_year_gap` bullet: catches `MissingDataError`, re-raises `SystemExit`; gains no keyword; `FakeRD` change in § 4 and deliverable 1 |
| A-4 / B2-N2 | MEDIUM | **Accept** — § 4 G4: one row per site with the injection named |
| A-5 | MEDIUM | **Accept** — § Impact third bullet; § Out of scope |
| A-6 / B2-N4 | LOW | **Accept** — § 4 pin row relabelled and pinned |
| A-7 / B2-N6 | LOW | **Accept** — cites corrected throughout |
| A-8 | LOW | **Accept** — § Impact and Swept? cell; out of scope |
| A-9 | LOW | **Accept** — §3 `resolve_raster` returns `(path, resolved_year)` |
| B2-N5 | LOW | **Accept** — §3: message carries the resolver's remedy; `if ys` kept |
| B2-N7 | LOW | **Accept** — §3 first bullet |

## Versions
| version | change |
|---|---|
| v1 | initial draft (tolerance-conditioned refusal; manifest fallback records) |
| v2 | unconditional refusal; §4 dropped; six dataset constructions; `download_tcc_nlcd.py` writer; GATE table; round-1 dispositions |
| v3 | ordering rule; seven writer sites; `resolve_raster`; G3/G4 per site; producers' fallback stated; round-2 dispositions above |
