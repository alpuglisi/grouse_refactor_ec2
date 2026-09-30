# CR-0029 review log

## Lineage
From BUG-0090 (2026-09-30 static review). Reviewers: two fresh agents
(CLAUDE.md §1.2, §1.4); review logs not read by them.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | REVISE | 2 |
| 1 | v1 | B (agent, fresh) | APPROVE WITH FOLLOW-UPS | 0 |

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

## Versions
| version | change |
|---|---|
| v1 | initial draft |
| v2 | dispositions above |
