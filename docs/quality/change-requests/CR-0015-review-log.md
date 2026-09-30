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
| BUG-0032 was a deferral with an allocated id and no record ("fixed here or explicitly deferred with a bug id") | CR-0007 log B1-5 (MAJOR) | added in v2: deliverable 2 files it |
| BUG-0032 "allocated" but no document or `BUG_LOG` row; later "resolved — CR-0012 deliverable 8 files BUG-0032" | CR-0007 log E-9 (BLOCKING, resolved by re-pointing) | added in v2: the filer moved from CR-0012 d8 to CR-0015 deliverable 2 (CR-0012 B-2); CR-0007 log's "CR-0012 files BUG-0032" is stale (tracker) |
| Cited-but-unfiled records need a named filer (BUG-0032 → CR-0012) | CR-0007 log FA-Q3 | added in v2: filer is CR-0015 deliverable 2 (same tracker item) |
| geopandas only when `--an-background > 0`; budget unchanged | CR-0012 log B-21 (LOW) | added in v2: §3 reconciliation (holds for `train.py`; `pretrain.py` accepted unconditional); §2 budget unchanged |
| §6 (this function) and the download guards can land separately (A5) | CR-0012 round-1 B MEDIUM 7 | added in v2: the reason this CR exists; "One change per CR" section |
| md5 rule for positive-free blocks: seed and `vf` formula | CR-0012 round-1 A2 (MEDIUM) | added in v2: §1 `regions.block_split` (text identical to CR-0012 §2 conventions, with `.encode()`) |

v1 carried a history paragraph in the CR ("Split out of CR-0012 by user
decision (2026-09-30): the function is live in two entry points that have
nothing to do with the train/val split files, so it gets its own review").
Removed from the CR in v2 (clean document); recorded here.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A — correctness (fresh) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR) |
| 1 | v1 | B — implementability (fresh) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR) |

## Round 1, reviewer A (dispositions: v2 table below)
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

## Round 1, reviewer B (dispositions: v2 table below)
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

## v2 dispositions (2026-09-30)
User decision (2026-09-30), applied in v2: CR-0015 adds one helper,
`regions.block_split(block_ids, assignments)`, implemented after CR-0012
lands, and switches `generate_negatives.py`'s pool step to it. This is a
behaviour-preserving refactor, verified by B1 (byte-identical digests;
CR-0013's acceptance passes unchanged). CR-0012's pinned text (`29f388b`)
is not reopened (tracker).

| id | severity | disposition + where |
|---|---|---|
| A1 | MAJOR | Accept. **U2:** fixture has the four block kinds, with ≥ 1 point required in each train kind (ii)/(iv) and 0 in (i)/(iii). **V3 added:** unassigned-train area-share check (class, subset, null named). The suggested ±3 pp is **not** pinned: PA-0021(c) needs a calibrated threshold, so deliverable 7a calibrates it (100 seeds) against four constructed samplers, including the over-excluding one; V3 is demoted to OBS if they don't separate. |
| A2 | MAJOR | Accept. L1 is now an exact AST rule (a/b/b′/c/d), with a named file set (60 files), an allowlist keyed by statement text, positive controls (A's three patterns among them) and a negative control. Expected result on today's tree: 4 matches, listed in the CR from the author's prototype run. PA-0006 re-sweep scoped by mechanism: deliverable 4. "Extends PA-0006": deliverable 2. |
| A3 | MEDIUM | Accept. §2: lon/lat → 5070 via `generate_negatives.to_albers`, then `regions.block_ids`; never native x/y. U2's fixture is in a non-5070 Albers CRS, so a native-x/y sampler fails it. |
| A4 | MEDIUM | Accept (user decision above). §1 `regions.block_split`; deliverable 5; B1. |
| A5 | MEDIUM | Accept. §2 signature: `region` and `train_blocks_only` are required keyword-only; U6. |
| A6 | MEDIUM | Accept. `GROUSE_REQUIRE_REAL_DATA=1` turns a skip into `pytest.fail`; the evidence records `pytest -rs` with no skips (Acceptance; deliverable 7). |
| A7 | MEDIUM | Accept. New **BUG-0042**, not an amendment of BUG-0027 (reason in deliverable 2). §4 review vs PA-0018: category "too narrow and not enforced"; "extends PA-0018"; producer sweep. Id check: BUG-0041 was filed (split-CR dropped finding) while v2 was written, so BUG-0042 is the next free id (re-checked immediately before writing). |
| A8 | LOW | Accept. §2 Docs: the docstring, the `:135` comment and the `--an-background` help. §3: the `pretrain.py --tiles` help. |
| A9 | LOW | Accept as stance. Out of scope, with reasons: an explicit uniformity gate (rejection sampling is uniform; V3 covers the failure that matters) and `window_in_bounds` for AN points. |
| A10 | LOW | Accept. Tracker item: CR-0012's "CR-0015 … is independent" contradicts CR-0015's dependency on CR-0012. CR-0012 is not reopened; CR-0015 § Order governs. |
| A-numbers | — | Accept. Why now §1 quotes the accepted-point out-of-state shares (ME 36.0 / NH 52.5 / VT 47.3 %). The budget analysis uses the 0.38–0.42 acceptance range. Why now §3 states that explicit `--features` can displace `evt`. |
| B1 | MAJOR | Accept (user decision). `regions.block_ids` on 5070 coordinates; one split helper in `regions.py`, so `train.py` does not import the md5 rule from `generate_negatives`. The assignments come through the `GrouseData` accessor (`PATH_TEMPLATES`, PA-0003). The transform still comes from `generate_negatives.to_albers`, imported lazily on the AN branch only; moving it is CR-0007's item (d), raised to the user. |
| B2 | MAJOR | Accept. Deliverable 4 is a mechanism-scoped sweep over the named files plus `train.py`; each finding gets a BUG or a written not-a-defect. Known sibling `find_tsd_contrast_points.py:121` is listed. L1 is a committed rule with an expected result on today's tree (A2). |
| B3 | MEDIUM | Accept. Deliverable 2 (BUG-0032): prior BUG-0008/0017/0036; category "too narrow (sweeps scoped by file/layer, not mechanism) and not enforced-verifiable"; "extends PA-0006"; L1 is the strengthening; BUG-0017 noted as still OPEN and re-examined in deliverable 4. |
| B4 | MEDIUM | Accept. §3 states the new geopandas/pyogrio/county-file dependency of `pretrain.py` and reconciles it with CR-0012 B-21: B-21 holds for `train.py`; for `pretrain.py` the dependency is unconditional and accepted. |
| B5 | MEDIUM | Accept. §4: the guard sits in `train.main` after `parse_args` (`:882`), before seeding, `GrouseData` or GPU work, and not in the function (so `pretrain.py` is unaffected). §4 lists the recipes it breaks and the ones it doesn't (runs that override with `--an-background 0`); U7 tests both. |
| B6 | MEDIUM | Accept (= A6). |
| B7 | MEDIUM | Accept. §2 adds an `in_state` injectable callable, defaulting to `regions.in_state`; U1 and U2 use it. |
| B8 | MEDIUM | Accept. One closure rule, stated in deliverable 9: FIXED at CR-0015 deliverable 7b (after CR-0012), CLOSED when CR-0009 also closes. CR-0012 d8 is consistent. The wording of CR-0007 v9 d6 ("fixed when CR-0012 lands") conflicts: tracker item for whoever executes CR-0007 d6. |
| B9 | MEDIUM | Accept. Lineage adds CR-0007 log B1-5, E-9 and FA-Q3, and CR-0012 B-21, MEDIUM 7 and A2. The CR-0012 "independent" contradiction is a tracker item (= A10). The CR-0007 log's stale "CR-0012 files BUG-0032" is a tracker item. |
| B10 | LOW | Accept, all parts. History paragraph moved here. A5 justification: CR § "One change per CR". `.encode()` is in §1. The `CHANGELOG.md` note moved to deliverable 6 (same commit). `:290-306`. Budget: not raised, with the rationale in §2. |

**v2 amendment (user decision, 2026-09-30, same version):** the
4326→5070 transform lives in `regions.to_5070(lon, lat)`, added by
CR-0015 next to `regions.block_split`. After CR-0012 lands,
`generate_negatives.to_albers` delegates to it, covered by the same
byte-identical gate B1. `train.py`'s AN path imports only `regions`. This
supersedes the B1 disposition's "transform still from
`generate_negatives.to_albers` … raised to the user" (CR §1, §2, B1,
Impact, deliverable 5, Out of scope).

## Author sign-off
v2 written by the author, 2026-09-30. Awaiting round-2 review (bounded
per CLAUDE.md §1.2: resolution of A1, A2, B1 and B2, plus the text changed
in v2).

## Round 2 (bounded re-review of v2)
| reviewer | verdict |
|---|---|
| B — implementability | **APPROVE WITH FOLLOW-UPS** — B1–B10 resolved; L1's 4 matches confirmed (60 files); BUG-0042 id free and correctly separate |
| A — correctness | **REJECT** — 1 new BLOCKING (below); A1–A10 resolved; L1 prototyped independently: same 4 statements, 8/8 positive controls |

Reviewer B round-2 follow-ups:
- B-R2-1 MAJOR: `tests/test_nodata_zero_lint.py` (L1 + allowlist) is a
  pre-approval deliverable and does not exist yet — approval waits for it
  to be committed and briefly reviewed (rule + 4-match run).
- B-R2-2 LOW: `check_road_dist.py:221` is `:226` in the working tree
  (CR-0016 edit) — harmless, allowlist keyed by statement text.
- B-R2-3 LOW: `data.block_assignments` accessor name — use whatever
  CR-0012 implements (`RegionData` property today, `grouse_data.py:444`).
- B-R2-4 LOW: B1 compares to "the latest CR-0012 deliverable 6 run".

Reviewer A round-2 findings:
- A-R2-1 BLOCKING: the conformance step requires V1 to fail a sampler
  using `VAL_FRACTION` (0.2) instead of `vf` (0.197) — that sampler
  OVER-excludes, so V1 (counts val-block points) is 0 and can never fail
  it; V3 cannot see ~0.3 % of area either. Fix: construct the wrong
  sampler with a fraction below `vf` (e.g. 0.18 → ~85 val-block points of
  5,000), and/or add a fifth U2 block kind (unassigned, hashed in
  [vf, VAL_FRACTION), ≥ 1 point).
- A-R2-2 LOW: L1 must de-duplicate matches per statement (the `BinOp` and
  its nested `{nodata, 0}` set both match → 5, not 4); line numbers
  `:226` and `:144` in the working tree.
- A-R2-3 LOW: the A3/B1 v2 dispositions still name `to_albers`; note they
  are superseded by the `regions.to_5070` decision.


## v2.1 dispositions (2026-09-30)
| id | severity | disposition + where |
|---|---|---|
| A-R2-1 | BLOCKING | Accept, both fixes. **(1)** The V1 conformance sampler now uses md5 fraction 0.18 (< `vf`), so it under-excludes and V1 must fail (Acceptance, PA-0021(a)). **(2)** U2 gains kind **(v)**: an unassigned block hashed in `[vf, VAL_FRACTION)` that must get ≥ 1 point, which catches the `VAL_FRACTION` sampler (it over-excludes, so V1/V3 cannot see it). A "wrong sampler → caught by" table is added to the CR. |
| B-R2-1 | MAJOR | Accept. `tests/test_nodata_zero_lint.py` is written (unittest; uncommitted, per the no-commit instruction). It implements the exact v2 rule (a/b/b′/c/d) over the 60-file set, with an empty statement-keyed allowlist and `EXPECTED_UNCLASSIFIED` pinning today's 4 statements, so any new match fails. It de-duplicates per statement and includes the 8 positive and 3 negative controls. Run: `python -m unittest tests.test_nodata_zero_lint -v` → 6 tests OK; matches `check_road_dist.py:226`, `find_tsd_contrast_points.py:121`, `generate_time_since_disturbance.py:330`, `train.py:144` (working-tree lines). The CR's pytest wording is replaced by unittest (`skipTest`/`self.fail` under `GROUSE_REQUIRE_REAL_DATA=1`; the summary must show no `skipped=`). |
| A-R2-2 | LOW | Accept. One match per statement (the nested match is dropped); stated in the CR's L1 section and tested (`test_one_match_per_statement`). Statements are cited by text, not line. |
| A-R2-3 | LOW | Accept. The A3 and B1 v2 dispositions that name `generate_negatives.to_albers` are **superseded** by the user's `regions.to_5070` decision (v2 amendment note above); the CR text already uses `regions.to_5070`. |
| B-R2-2 | LOW | Accept. The CR cites the four L1 statements (and BUG-0032's) by statement text, not line. |
| B-R2-3 | LOW | Accept. The accessor is "whichever CR-0012 implements (today `RegionData.block_assignments`, `grouse_data.py:444`)" (§1, §3). |
| B-R2-4 | LOW | Accept. B1 compares against the manifest of the latest CR-0012 deliverable 6 run. |

Author: v2.1 signed off, 2026-09-30. Awaiting round 3 (bounded: A-R2-1 and the v2.1 changes, including the L1 test file).
