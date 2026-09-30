# CR-0029 review log

## Lineage
From BUG-0090 (2026-09-30 static review). Reviewers: two fresh agents
(CLAUDE.md §1.2, §1.4); review logs not read by them.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | REVISE | 2 |
| 1 | v1 | B (agent, fresh) | APPROVE WITH FOLLOW-UPS | 0 |
| 2 | v2 | A (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS | 0 |
| 2 | v2 | B (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS (conditional on N1 text) | 0 |

## Round 1, reviewer A
- **A1 BLOCKING:** the rebuild omits `prepare_training_data.py`;
  `env_zone` (`:955-966`, written `:1099`) is a positives column
  (`prepare_training_data.py:81-86`), so S changes and R1/E11 fail on the
  §4 sequence.
- **A2 BLOCKING:** normative referents do not exist: `sample_availability`
  (the draw is `in_state_background_points` `:355-372`, also called by
  `background_nonveg_rate` `:384`, seed 0); `availability.seed` is a
  keyword default (`seed=1`, `:472`), invisible to `literal_assignments`;
  `analyze_grouse.py` writes no manifest.
- A3 MAJOR: "P5b" exists (`check_partition.py:500-512`);
  `check_partition.py` reads module literals, not the JSON; the replay
  must reproduce `default_rng(seed)`, x-then-y batch order,
  `MAX_BG_BATCHES`, `in_state`.
- A4 MEDIUM: O12 null (equal counts per band) fails the correct pipeline;
  use expected ∝ in-state area per band.
- A5 MEDIUM: P5a asserts every row in the lon/lat box (`:490-496`);
  rectangle ∩ state can exceed the box.
- A6 MEDIUM: A4 self-question in §2; MC named but undefined; O12 id
  space; pins for a new section.
- A7 LOW: inverse transformer literal (BUG-0047); `float_rel_tol`.

## Round 1, reviewer B
- B1 MAJOR: same as A3 (P5b not implementable from the CR; host it in
  `check_partition.py` under a new id).
- B2 MAJOR: same as A1 (rebuild must include `prepare_training_data.py`;
  E11 last-wins weakness noted for the tracker).
- B3 MEDIUM: same as A2 (function name, both callers).
- B4 MEDIUM: same as A6 (drafting question; manifest claim).
- B5 MEDIUM: same as A4 (O12 null).
- B6 MEDIUM: MC from the pipeline's own scratch run (PA-0021(e)).
- B7 LOW: corner-only bounding rectangle valid for these boxes (state
  it); efficiency; "either order with CR-0020" holds only after CR-0020's
  availability-schema fix.

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location) |
|---|---|---|
| A1 / B2 | BLOCKING | **Accept** — §4 rebuild order analyze → prepare → generate → acceptance; "positives unchanged" removed; not-comparable statement; E11 last-wins note to the tracker (deliverable 5) |
| A2 / B3 | BLOCKING | **Accept** — §2 names `in_state_background_points` and both callers; seeds promoted to module constants `AVAILABILITY_SEED = 1`, `NONVEG_RATE_SEED = 0`, plus `AVAILABILITY_DRAW_CRS = "EPSG:5070"`, all readable by `check_partition.literal_assignments`; manifest claim removed; provenance = the constants + the replay gate |
| A3 / B1 | MAJOR | **Accept** — §3: gate lives in `check_partition.py` as **P9** (exact replay of the draw from the module constants: `default_rng(AVAILABILITY_SEED)`, batch loop, x-then-y, `MAX_BG_BATCHES`, inverse transform, `in_state`, box clip); attack row: degree-uniform draw with the same seed FAILs |
| A4 / B5 | MEDIUM | **Accept** — O12 null: expected counts ∝ in-state area per band from the county polygons |
| A5 | MEDIUM | **Accept** — §2: points outside `BOXES[region]` after the inverse transform are rejected, so P5a holds unchanged and the box keeps its meaning |
| A6 / B4 / B6 | MEDIUM | **Accept** — drafting question removed; MC dropped (P9 is exact and the whole sample changes by design); pins for the new `availability` constants listed |
| A7 / B7 | LOW | **Accept** — `regions.from_5070` beside `to_5070` (no new EPSG literal outside `regions.py`); `float_rel_tol`; corner-bounding assumption stated; `background_nonveg_rate` baseline change noted in § Impact |

## Round 2 (v2), reviewer A (bounded, CR-0011 A2)
A1/B2 and A2/B3 (BLOCKING) and A3/B1 (MAJOR) verified RESOLVED
(`env_zone` at `analyze_grouse.py:964-973`, S written `:1099`, positives
column `prepare_training_data.py:81-86`; draw at `:360-380`, callers
`:488` and `:392`, seeds `:468`/`:383`; P1–P8 exist, P9 free; the
corner-bounding claim re-derived).
- A-N1 MEDIUM: `AVAILABILITY_DRAW_CRS = "EPSG:5070"` contradicts the
  CR's own BUG-0047 clause and can drift from `regions.to_5070`'s
  hard-coded CRS (`regions.py:243`); derive from `regions._ANALYSIS_EPSG`
  (`:88`).
- A-N2 LOW: `MAX_BG_BATCHES`/`AVAILABILITY_SEED` not in `ANALYZE_CONSTS`
  (`check_partition.py:77-79`); the test stub (`tests/test_check_partition.py:120-125`)
  and fixture `availability()` (`:182-199`) must change; the tolerance
  must be a `check_partition.py` literal; O12 lives in `acceptance_split.py`
  and needs `paths.availability_sample`; cites `:360-380`, `:383`/`:392`,
  `:468`.
- A-N3 LOW: O12 band wording.
- A-N4 LOW: P9 exactness on rejected points (measure-zero).
- A-N5 LOW (A4): "(exact; new id, "P5b" exists)" is a revision note.

## Round 2 (v2), reviewer B (bounded, CR-0011 A2)
Same RESOLVED table.
- **B-N1 MAJOR:** same as A-N1 (a 17th `EPSG:5070` literal while
  BUG-0047 is open is a PA violation, CLAUDE.md §3.2).
- B-N2 MEDIUM: P9 under-specified: (a) it must build its own
  `pyproj.Transformer` (never imports `regions`); (b)
  `comparison.float_rel_tol` is not readable by `check_partition.py`;
  (c) no PROJ pin in the check, so a PROJ change can fail P9 on correct
  data; `MAX_BG_BATCHES` "already reads" → "will read".
- B-N3 MEDIUM: O12's home needs `paths.availability_sample` (absent) and
  the 5070 county polygons (`acquisition_domain`, `:831`); the `obs`
  section is unpinned; `OBS_IDS` presumes CR-0030's O11.
- B-N4 LOW: bands defined once.
- B-N5 LOW: stub and fixture builder; deliverable 4 names both scripts;
  cites off by a few lines.

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-N1 / B-N1 | MEDIUM / MAJOR | **Accept** — §2 first bullet: no new literal; §3 P9 derives the CRS from `regions._ANALYSIS_EPSG` (added to `REGION_CONSTS`) |
| A-N2 / B-N2 / B-N5 | LOW / MEDIUM / LOW | **Accept** — §3 P9: own `Transformer` from `LONLAT_EPSG`; `ANALYZE_CONSTS` gains `MAX_BG_BATCHES`, `AVAILABILITY_SEED`; `P9_RTOL` literal; versions printed and the accepted PROJ dependence in § Risk; stub and fixture builder bullet; cites corrected |
| B-N3 | MEDIUM | **Accept** — §3 O12: in `acceptance_split.py`, needs `paths.availability_sample` (whichever of CR-0020/CR-0029 lands first adds it), `acquisition_domain`; pins name `paths` and `OBS_IDS`; O11 caveat |
| A-N3 / B-N4 | LOW | **Accept** — §3 O12: bands are equal-area cuts of the projected box; null ∝ in-state area |
| A-N4 | LOW | **Accept** — §3 P9: rejected draws, measure-zero |
| A-N5 | LOW | **Accept** — note removed (kept here) |

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
| v2 | round-1 dispositions |
| v3 | round-2 dispositions above; approved by agent quorum |
