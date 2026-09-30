# CR-0015 review log

## Lineage
Split out of CR-0012 at v2 by user decision (2026-09-30). Carried items:

| item | source | in CR-0015 v1 |
|---|---|---|
| `sample_background_points` out-of-state draw (BUG-0029 remainder) | CR-0007 v7 §7; CR-0012 v1 §6 | §1 in-state |
| 0/nodata conflation at `:143` (BUG-0032, allocated, never filed) | CR-0007 v7 §7; CR-0012 round-1 B LOW ("file BUG-0032 now") | §1 validity; deliverable 2 |
| Oversample budget must absorb the rejection rate | CR-0007 v7 §7 | §1 budget |
| Function is live, not dormant (`pretrain.py:63,179`; sweep `--an-background 1.0`) | CR-0012 round-1 B MAJOR 2 | Why now; §2 |
| AN points must be restricted to training blocks (~20 % land in val) | CR-0012 round-1 A1 (MAJOR) | §1 training blocks; U2; V1 |
| An interim guard until the fix lands | CR-0012 round-1 A1 alternative | §3; deliverable 1 |

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A — correctness (fresh) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR) |
| 1 | v1 | B — implementability (fresh) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR) |

## Round 1, reviewer A — dispositions pending (v2 after reviewer B)
Measured (200k draws/region): features[0] = `evt`, evt==0 0.0000 %;
in-state share of the box ME 0.501 / NH 0.473 / VT 0.527; out-of-state
share of today's accepted points ME 36.0 / NH 52.5 / VT 47.3 %; val-block
share of in-state draws 19.3 / 19.6 / 20.5 %; acceptance rate 0.404 /
0.381 / 0.419 (budget ample); rejection sampling uniform and
deterministic; excluding only val blocks is right for AN; SSL tiles in val
blocks leak no labels.
- A1 MAJOR: U2/V1 can't fail over-exclusion (treating unassigned blocks as
  excluded keeps only positive-occupied blocks). Fixture needs four block
  kinds; add an unassigned-train-block share check (±3 pp of area share).
- A2 MAJOR: L1 unspecified (pattern, file set, allowlist) and too narrow
  for the mechanism (`& (x != 0)`, `(arr > 0) & ~sentinel`, `nodata or 0`);
  third PA-0006 miss (BUG-0008 → 0017 → 0032) → PA-0006 re-sweep and
  "extends PA-0006".
- A3 MEDIUM: rasters are per-region Albers, not 5070 — transform lon/lat
  to 5070 with CR-0012's helper; call its block-id function.
- A4 MEDIUM: expose one `regions.block_split(block_ids, assignments)` used
  by CR-0012's pool step and this sampler (file lookup + `vf` + md5).
- A5 MEDIUM: make `region` and `train_blocks_only` required keywords.
- A6 MEDIUM: V1 must fail, not skip, at deliverable 4.
- A7 MEDIUM: file a BUG (or amend BUG-0027) for the val-block leak; §4
  review vs PA-0018.
- A8–A10 LOW: stale help/docstrings; uniformity check and `window_in_bounds`
  stance; CR-0012 "independent" wording.
- Also: "~47 % of ME's box" → quote accepted-point shares; "40–50 %"
  acceptance → 38–42 %; `evt` can be displaced by explicit `--features`
  (defect 3 live then).

## Round 1, reviewer B — dispositions pending (v2)
- B1 MAJOR: CR-0012 v2.1 has no block-split helper in `regions.py`; the md5
  rule stays `generate_negatives.split_for_unassigned` (`:110-115`), `vf` is
  prose; "compute the block id as CR-0012 §2" re-types `regions.block_ids`
  (PA-0001). Fix: `regions.block_ids` on lon/lat→5070; one split helper
  (importing `generate_negatives` pulls in scipy/analyze_grouse) — moving
  it to `regions.py` touches CR-0012's code surface; read the file via
  `PATH_TEMPLATES`.
- B2 MAJOR: no §3.5 sweep; L1's first result unpredictable — known sibling
  `find_tsd_contrast_points.py:121` (`& (nlcd_arr != 0)`); sweep the 9
  tracked files using `NODATA_SENTINELS`; committed regex + exemptions;
  expected result on today's tree.
- B3 MEDIUM: recurrence — third PA-0006 miss; name the failure category
  (sweeps scoped by file/layer, not mechanism, and unenforced); state L1 as
  the §4.3 strengthening or extend PA-0006; BUG-0017 still OPEN.
- B4 MEDIUM: `pretrain.py` gains geopandas/pyogrio/county-file
  dependencies — contradicts CR-0012 B-21's AN-only stance.
- B5 MEDIUM: guard placement (after `parse_args`, before data/GPU; not in
  the function); list the broken recipes (`sweep/launch*.sh`, Run B).
- B6 MEDIUM: V1 must not pass by skipping (= A6).
- B7 MEDIUM: `in_state` has no injection point for the synthetic tests.
- B8 MEDIUM: BUG-0029 closure path conflicts across CR-0007/0012/0015.
- B9 MEDIUM: lineage misses CR-0007 log B1-5, E-9, FA-Q3 and CR-0012 B-21,
  MEDIUM 7, A2; CR-0012 "CR-0015 is independent" contradiction.
- B10 LOW: history paragraph; A5 line for the guard; `.encode()`;
  CHANGELOG with deliverable 3; `:306`; budget raise not needed at ~42 %.
- Unverified by B: evt 0.0 % zeros (verified by A).

## Author sign-off
Pending.
