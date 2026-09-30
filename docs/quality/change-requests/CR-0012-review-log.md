# CR-0012 review log

History, verdicts and dispositions for CR-0012. The CR itself states only
current intent (`CLAUDE.md` §1.1, CR-0011 A4).

## Lineage
Split from CR-0007 v7 (commit `bb170ea`) on 2026-09-30. The user decided
the split after seven rejected rounds (§1.2 A2: split or escalate).

| v7 part | now in |
|---|---|
| §3 `prepare_training_data.py` (one grid, one pooled thin, one draw) | CR-0012 §1–§3 |
| §4 duplicate scripts: `clean.py`, `legacy/gen_negs.py`, `legacy/download.py`, `legacy/download_more.py` | CR-0012 §7 (`legacy/audit.py` → CR-0007 §3) |
| §5 `generate_negatives.py` (pooled pass, global ids, buffer, thin, window drop, `:153`) | CR-0012 §2–§3 |
| §6 standing assertions, `GATE_REGIONS`, R4/R5 | CR-0012 §5 (definitions in CR-0013) |
| §7 `sample_background_points` | CR-0012 §6 |
| Known exceptions (negatives) | CR-0012 §2 pool step 4 |
| Persisted candidate pool and manifest | CR-0012 §2 steps 11 and manifest |

**Carried through every CR-0007 round without a break:** the global block
grid, the pooled thin, the pooled draw, and `ignore_index` discipline.
Reviewers reproduced the positive counts in rounds 2–7. The legacy
per-region-seeded thinner gives 6,230 (ME 3,659 / NH 1,079 / VT 1,492);
CR-0012's hash-ordered thinner gives 6,232 on the same files, measured by
the author on 2026-09-30.

**Design changes relative to v7** (author, v1):
- The thinner, the block draw and the negative draw are hash-ordered and
  deterministic. The negative draw uses Efraimidis–Spirakis keys. This
  makes exact replay possible (CR-0013) and resolves B-11 and B-17.
- Habitat-pool shortfall raises. It no longer tops up from NonVeg (10C).
- All five run-parameter flags are removed (F2-C5, C7-11).
- Standing checks read the CSVs directly (R5 hazard removed) and require
  CR-0013's acceptance record. There is no escape mode (user decision).

Every round 1–7 concern about v7 is dispositioned in
`CR-0007-review-log.md` § v8 dispositions. The table below lists those
whose resolution lives in this CR.

## Dispositions of CR-0007 concerns resolved here
| id (CR-0007 log) | sev | where in CR-0012 |
|---|---|---|
| B1-1 | BLOCKING | §2 Draw: `ignore_index=True`; `weighted_take` replaced by key selection |
| B1-7 | LOW | §3 ownership; §2 pool step 10 (global share, 0.197 today) |
| B1-11 | positive | §4 template removed; §7 guard on `legacy/gen_negs.py` |
| D1-4 | MAJOR | §2 pool step 4 |
| D1-5, C7-8, FA-C7 | MAJOR/LOW | §2 positives step 3 and pool step 8; counts in the manifest |
| F2-C5, C7-11, D1-2 | MAJOR/LOW | §1 `VAL_FRACTION`, `SPLIT_SEED`; §3 flags removed |
| F2-C10, B-10, A-15 | MAJOR/MEDIUM/LOW | §3 `--regions` dry run; §2 Writes (raise before any write, atomic replace) |
| F2-C13 | LOW | Kept-set semantics fixed by §2; implementation free (checked by CR-0013 R1/R3) |
| F2-C15 | LOW | Out of scope states the real reason (pre-reorganisation paths) |
| FA-C6 | MAJOR | No "no effect" claim; pooled thinning changes the kept set (manifest counts) |
| FA-C9, B-11 | MAJOR/MEDIUM | Hash ordering and flag removal adopted. Stratification not adopted. `draw_val_blocks` not adopted: CR-0013 R2 replay fails any tampering in the sampler, so the structural control adds nothing. |
| FC-C12, A-13, C7-6 | MAJOR/MEDIUM | §2 pool step 4: drop all 6 (F's ruling), with the reason for not relabelling |
| FC-C15 | LOW | Deliverable 8: BUG-0027/0029 fixed here, closed after CR-0009 |
| E-9 | BLOCKING | Deliverable 8: BUG-0032 filed |
| E-20 | LOW | Deliverable 8 (two-stage closure) |
| A-7 | MAJOR | §2 step 11 persists `weight`, `weight_basis`, `evt_phys`, `common_name`, `envelope_id`, `year`; all checks computed in CR-0013's script |
| A-8, B-2, E-16 | MAJOR/BLOCKING | No escape; deliverable 0 (CR-0009 baselines first) |
| A-11, B-15 | MEDIUM | Claim withdrawn (verified: VT val 452 selected, 136 NonVeg = round(452 × 0.3), no top-up). The shortfall raise rests on 10C, not on this claim. |
| B-12 | MEDIUM | §1 `WINDOW_PX`; §2 year rule; §5 refuses a larger `img_size + 2·jitter` |
| B-13 | MEDIUM | §4 |
| B-18 (`:153`) | MEDIUM | §3; deliverable 8 new BUG |
| B-19 (part) | LOW | Citations re-verified: `calibrate.py:355` (was `:351` before `ec1470a`), `:143`, `:105-111`, `:278-286`. Five guards in total (CR-0007: 1; CR-0012: 4). |
| B-21 | LOW | §6: geopandas only when `--an-background > 0`; budget unchanged; "SystemExit reachable" withdrawn |
| B-R (part) | unrated | Risk rows: partial writes; shared misreading with CR-0013; library drift |
| FC-C10 (range) | BLOCKING | `build_datasets` is `train.py:238-317` (def `:238`, return `:316-317`), verified on the current file |

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| — | v1 | not yet reviewed | — | — |

## Versions
| version | date | change |
|---|---|---|
| v1 | 2026-09-30 | Split from CR-0007 v7; deterministic specification for replay |

## Round 1 (fresh first review, 2026-09-30) — dispositions pending
| reviewer | verdict | blocking |
|---|---|---|
| B — implementability + §1 | REJECT | 1 |
| A — correctness | **APPROVE WITH FOLLOW-UPS** | 0 (1 MAJOR) |

Reviewer B findings:
- **BLOCKING 1:** negative output columns (`generate_negatives.py:304-308`)
  have `state` but no `region`; CR-0013 E1 requires `region` on every
  row → acceptance can never pass. Fix: add `region` (schema change in
  Impact), or relax E1 for selected — one or the other.
- MAJOR 2: `pretrain.py:63,179` calls `sample_background_points`
  unconditionally, so §6 changes SSL tiles; the "dormant" claim is false —
  `sweep/launch.sh`, sweep logs and Run B use `--an-background 1.0`
  (BUG-0029/0032 live). Fix: AN-only in-state parameter, or list pretrain
  in Impact; better, move §6 to its own CR.
- MAJOR 3: `split_manifest.json` writer(s), merge rule, atomic replace,
  dirty-tree flag unspecified.
- MAJOR 4: "full WINDOW_PX window" undefined — recommends: centre
  `rowcol` floor, window `[r-32,r+32)×[c-32,c+32)` inside `[0,h)×[0,w)`,
  nodata not considered; say whether a CR-0014-after run needs a full
  pipeline re-run.
- MAJOR 5: deliverable 0 not executable (CR-0009 v4 uncommitted; list the
  measurements, paths, verification; backup + old-commit worktree as
  fallback).
- MEDIUM 6: review log omits A-2, B-6, B-7, B-17, C7-9, E-12, E-21,
  E-17/FA-Q3, F2-N; E-16 mislabelled.
- MEDIUM 7: A5 — §6 and the download-script guards can land separately.
- MEDIUM 8: leftover duplicates `VAL_FRACTION_DEFAULT`,
  `RANDOM_SEED_DEFAULT`, `REGIONS_DEFAULT`; manifest constant list
  incomplete vs CR-0013's config.
- MEDIUM 9–11: `--regions` semantics and reorder test mechanism; `:153`
  handler must re-raise; rollback and partial-run recovery.
- LOW 12: selection tie-break; stable sort; same-dir temp; `legacy/gen_negs.py`
  guard first statement; `standing_checks(img_size, jitter)`; Impact
  readers list; guard count; one-sentence Scope; `:19-28`; 6,230 vs 6,232
  vs CR-0009; file BUG-0032 now.
- Verified: citations; leakage 522/1,674 and 882 mixed blocks; the
  hash-ordered thin reproduces 6,232 (3,660/1,079/1,493), 3,861 blocks,
  759 val blocks, 1,246 records; pool 265,212 → 35,678; 6 partition drops.


## Pending for v2 (from CR-0013 round 1) — all folded into CR-0012 v2
| item | source | where in v2 |
|---|---|---|
| Order-free dedup: smallest `gbif_id` per key. Verified non-null and unique on 265,212 rows; 6,492 keys carry more than one `year`. | CR-0013 R1 A-B3 | §2 pool step 3 |
| `region` column in negative outputs | CR-0012 R1 B BLOCKING 1 / CR-0013 E1 | §2 Draw, Impact |
| Window predicate: in-bounds, rounded down, nodata ignored | CR-0013 R1 B-C2 / CR-0012 R1 B-4 | §1 `window_in_bounds` |
| `split_for_unassigned` spec; `SPLIT_SEED` as the only seed source | CR-0013 R1 A-M, B-C2 | §1, §2 pool step 10, §3 |
| Manifest constant list equals CR-0013's config list; input digests including rasters | CR-0013 R1 A-M, CR-0012 R1 B-8 | §2 Split manifest |

## v2 dispositions (author, 2026-09-30) — reviewer B, round 1
Reviewer A (correctness) is still reviewing v1. Its findings will be
dispositioned against v2 as amendments.

| id | sev | disposition |
|---|---|---|
| B-1 | BLOCKING | Accept. `region` is added to every negative output (§2 Draw; Impact schemas). CR-0013's E1 is kept strict. |
| B-2 | MAJOR | Accept, and moved to a new CR under A5. Verified: `pretrain.py:63,179` calls `sample_background_points` unconditionally, and `sweep/launch.sh` uses `--an-background 1.0`, so the function is live and the "dormant" claim is withdrawn. §6 of v1 moves to **CR-0015** (not yet written; tracker), together with the BUG-0029 remainder and BUG-0032, which CR-0015 files. So BUG-0032 is **not** filed by CR-0012. |
| B-3 | MAJOR | Accept. §2 Split manifest: two sections and their writers; delete-on-rebuild; positive-digest check; atomic replace; `dirty` flag. |
| B-4 | MAJOR | Accept. §1 `window_in_bounds`, matching the reviewer's definition. If CR-0014 lands after deliverable 6, deliverable 6 is repeated. |
| B-5 | MAJOR | Accept. Deliverable 0 lists the measurements, the output path with `SHA256SUMS`, the verification, and the backup + worktree fallback. It also requires CR-0009 v4 to be committed. |
| B-6 | MEDIUM | Accept. The rows below add A-2, B-6, B-7, B-17, C7-9, E-12, E-21, E-17/FA-Q3 and F2-N. E-16 is MAJOR (v1 grouped it under BLOCKING by mistake). |
| B-7 | MEDIUM | Accept. §6 moves to CR-0015. The `legacy/download*.py` guards move out too (tracker). Two guards remain (§6). |
| B-8 | MEDIUM | Accept. §1 deletes `REGIONS_DEFAULT`, `VAL_FRACTION_DEFAULT` and `RANDOM_SEED_DEFAULT`. The manifest list equals CR-0013's config. |
| B-9 | MEDIUM | Accept. `--regions` is removed from both scripts. The order test mechanism is defined in the test plan. |
| B-10 | MEDIUM | Accept. §3: `:153` has no skip path; every exception is re-raised. |
| B-11 | MEDIUM | Accept. Rollback paragraph; partial-run risk row; delete-on-rebuild. |
| B-12 | LOW | Accept, all parts: <br>• key tie-break and stable sorts (§2); <br>• same-directory temp (§2 Writes); <br>• guard is the first statement (§6); <br>• `standing_checks(img_size, jitter)` (§5); <br>• readers list extended; <br>• 2 guards; <br>• one-sentence Scope; <br>• `:19-28`; <br>• 6,232 vs 6,230 stated, and CR-0009 to update (tracker); <br>• BUG-0032 → CR-0015 (see B-2). |

**CR-0007 rows resolved here but missing from the v1 table:**
| id | where in CR-0012 v2 |
|---|---|
| A-2 | §2 pool step 6 (buffer on pooled sightings; count in the manifest) |
| B-6 | §6: evidence scripts run from a worktree at `05d788d` |
| B-7 | §2 steps 3/8 (window), 4 (`verify_partition`), Draw (`ignore_index`, no `.loc`) |
| B-17 | Impact: 6,232 is an expectation; the target is CR-0013 R1 |
| C7-9 | §2 Split manifest (sha256 of inputs and outputs) |
| E-12 | Deliverable 0 (baselines before the rebuild) |
| E-21 | Deliverable 1 verifies CR-0007's backup |
| E-17 / FA-Q3 | Deliverable 8 names this CR's records (new BUG for `:153`) |
| F2-N | 35,678; 0.197; `:238-317`; re-verified |

| version | date | change |
|---|---|---|
| v2 | 2026-09-30 | Reviewer B round 1 and the CR-0013 round-1 pending items: <br>• `region` on negatives; <br>• order-free dedup; window predicate; md5 spec; <br>• two-section manifest; all flags removed; <br>• §6 moved to CR-0015; download guards moved out; <br>• deliverable 0 made executable; rollback. |

Reviewer A (correctness, reviewed v1; to be folded into v2 as amendments).
Reproduced independently: 6,411 → 6,232 positives (3,660/1,079/1,493),
3,861 blocks, 759 val blocks, 1,246 val records, val share 0.19658;
candidates 265,212 → 35,678 → 6 partition drops → thin 31,912 → buffer
−9,720 → nodata −2 → windowless −3 (NH) → pool 22,187; no habitat
shortfall (worst ratio 1.57); NonVeg cap binds in all 6 cells.
- A1 MAJOR: `sample_background_points` restricted to state but not split —
  ~20 % of AN-background points land in val blocks (BUG-0027 leak reopened
  through an ungated path). **Moves with §6 to CR-0015** (user decision);
  tracker item carries it.
- A2 MEDIUM: md5 split for positive-free blocks — seed and `vf` formula
  (already folded into v2 from CR-0013; verify wording matches A's).
- A3 MEDIUM: rounding rule ambiguous (half-even vs half-up; n ≡ 15 mod 20);
  name it.
- A4 MEDIUM: full-window definition — already in v2 (in-bounds).
- A5 LOW: canonical output row order for digests.
- A6 LOW: pin float parsing (`float_precision="round_trip"`).
- A7 LOW: §5 jitter refusal must use the effective pad (`augment`).
- A8 LOW: `diagnose_road_bias.py:132`, `diagnose_water_bias.py:123` readers.
- A9 LOW: `filter_by_year_gap` drops 23.1 % of positives after the split
  (effective neg:pos ≈ 1.3) — BUG-0034's scope; tracker.
- A10 LOW: "882 blocks" counts positives + negatives (541 positives only).


## v2 dispositions — reviewer A, round 1 (APPROVE WITH FOLLOW-UPS on v1), folded into v2 as amendments
| id | sev | disposition |
|---|---|---|
| A1 | MAJOR | Accept, moved to CR-0015 along with `sample_background_points` (user decision). CR-0012 v2 Out of scope says CR-0015 must restrict the points to training blocks. Tracker item exists. |
| A2 | MEDIUM | Accept. Verified against the reviewer's formula and `generate_negatives.py:110-115`. §2 conventions: `int(md5(f"{SPLIT_SEED}:{block_id}").hexdigest(), 16) % 10000 < vf × 10000`, with `vf = (block_assignments.split == "val").mean()` over positive-occupied blocks. The same text is in CR-0013 § Normative definitions. |
| A3 | MEDIUM | Accept. Python `round()` on the float64 product (half to even), named for all three `round` uses. Also in CR-0013's config. |
| A4 | MEDIUM | Already in v2 (`window_in_bounds`). |
| A5 | LOW | Accept. §2 conventions: canonical, stable row order for every output; digests taken on those bytes. |
| A6 | LOW | Accept. Reads use `float_precision="round_trip"`; writes use pandas' default repr (CR-0012 §2 and CR-0013 config). |
| A7 | LOW | Accept. `standing_checks(img_size, jitter, augment)`; the effective pad is `jitter` if `augment` else 0 (`dataset.py:75`). Same in CR-0013. |
| A8 | LOW | Accept. `diagnose_road_bias.py:132` and `diagnose_water_bias.py:123` added to the Impact readers. |
| A9 | LOW | Tracked under BUG-0034 (tracker item added by the coordinator). CR-0013 O9 reports per-class support. |
| A10 | LOW | Accept. Why now: "882 blocks, counting positives and negatives (541 counting positives only)". |

## Round 2 (bounded re-review of v2, commit 5d51682)
| reviewer | verdict |
|---|---|
| A — correctness | **APPROVE WITH FOLLOW-UPS** — A1–A10 resolved; positive counts still reproduce (6,232; 3,861; 759; 1,246); dedup by min `gbif_id` changes 3,294 kept candidates' `year` vs file order (pool counts after dedup may shift; supply ≥ 1.57× target) |
| B — implementability | **APPROVE WITH FOLLOW-UPS** — all findings resolved except the rollback part of B-11 |

Follow-ups applied in **v2.1** (text-only):
| # | sev | concern | disposition |
|---|---|---|---|
| B-11r | MEDIUM | Rollback restored CR-0007's outputs too | **Accept** — restore only this CR's outputs, named |
| A-R2-1 | LOW | Step 4 "within" vs "closer than" at exactly 30 m | **Accept** — keep iff squared distance ≥ `MIN_SPACING_M²` |
| A-R2-2 | LOW | "Ties broken by key" — which key | **Accept** — `order_key("neg:" + coord)` |
| A-R2-3 | LOW | Year-fill column max over which frame | **Accept** — the region's habitat rows (step 2) |
| B-R2-L | LOW | `tune.py` listed as a reader; OBS readers `check_raster_repair.py`, `check_road_dist.py` not listed | **Tracked** — Impact wording, fold into the next edit |

## Quorum (§1.4)
Reviewer A: APPROVE WITH FOLLOW-UPS (v2). Reviewer B: APPROVE WITH
FOLLOW-UPS (v2). Author: pending user. Implementation also waits for
CR-0007 and CR-0013 (acceptance) per the landing order.

