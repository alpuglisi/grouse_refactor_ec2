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
