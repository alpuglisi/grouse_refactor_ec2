# CR-0019 review log

Verdicts, concern dispositions and revision history for
`CR-0019-common-year-floor.md`. The CR states only current intent
(CR-0011 A4).

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 (`95d7463`) | A: correctness of diagnosis and fix (fresh agent) | pending (report not yet received) | – |
| 1 | v1 (`95d7463`) | B: implementability, composition, acceptance (fresh agent) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR, 3 MEDIUM, 8 LOW) |

## Round 1, reviewer B: concerns and dispositions
Each claim was checked against the code before it was applied (fixture
lines `tests/test_cr0012.py:593-594,835-836`,
`tests/test_acceptance_split.py:227,291,319,1492` confirmed). The lead
accepted the planned dispositions of B1–B5 (2026-09-30).

| id | sev | concern (short) | disposition | where (v2) |
|---|---|---|---|---|
| B1 | MAJOR | Existing fixtures break under the new guards (null-year and 2019 candidates; fixture `REGIONS_PY`; 19-gate pin) | Accepted, revised: pool guard raises only on non-null `year < YEAR_MIN` (null years keep CR-0012's step-7 drop); fixture edits are deliverables 2/3; existing attack rows' existence checks must still pass | §2 pool step 1; §3 "Existing fixtures"; deliverables 2, 3; Risk |
| B2 | MAJOR | E14 one-sided; an upper-end divergence passes | Accepted, revised: E14(b) pooled set equality of P and N years; new attack row | §3 E14 table and notes; attack table; test plan |
| B3 | MEDIUM | §6 warning covers only `calibrate.py` | Accepted, revised: all BUG-0060 entry points and `diagnose_*`/`bench_pipeline.py`; CR-0020 trains from scratch | §6; deliverable 7 |
| B4 | MEDIUM | Envelope metrics fitted on 2016+ vs 2020+ positives (PA-0020(i)) unjustified | Accepted, revised: justification in §2; named sweep item in deliverable 8 (owner: deliverable 8) | §2 "Envelope weights"; deliverable 8 |
| B5 | MEDIUM | "§ Proposed bookkeeping" cited but absent | Accepted: section added below | this log |
| B6 | LOW | MC: no positive order check; added-row columns unchecked | Accepted: `MC1 {R} order` added; limit documented in the docstring (R1 covers) | `check_must_change.py`; §3 |
| B7 | LOW | Pre-registration CSVs not pinned | Accepted: `PRE_SHA` pins (digests unchanged by the re-run) | `check_must_change.py` |
| B8 | LOW | PA-0025 not mechanically enforceable for bare `2020`; `START_YEAR` duplicated | Accepted: stated review-only; `START_YEAR` in the sweep | §2 Constant; deliverable 8 |
| B9 | LOW | Null-year spec vs pre-registration mismatch | Accepted: `preregister.Floored` now raises on any evaluated row; outputs byte-identical | `preregister.py`; §2 |
| B10 | LOW | A5 overstated for the `train.py` refusal | Accepted, revised | § One change per CR |
| B11 | LOW | Stale line `acceptance_split.py:2620` | Accepted: `full_run#0`, `:2795` | § Impact |
| B12 | LOW | `SystemExit` from a library function | Tracked follow-up (tracker, owner: deliverable 3 implementer may use a named `SystemExit` subclass; decided in code review) | – |
| B13 | LOW | Deliverable 2 "suite passes" ambiguous | Accepted, revised | deliverable 2 |

MC self-test after B6/B7: 42/42 PASS on the predicted tree, no-op FAIL
(`mc_selftest.txt`). B's wrong-tree table: `docs/quality/evidence/CR-0019/reviewB/mc_wrongtrees.txt`.

## Proposed bookkeeping (for deliverable 8; the lead files)
- **BUG-0034 §6/status:** corrective action "CR-0019 (floor at selection,
  refusal, E14)"; status FIXED for the root cause (disjoint support);
  consequence (b)'s within-epoch remainder moved to BUG-NEW-a (PA-0024(b)).
- **BUG-NEW-a (proposed; BUG-0073 if allocated):** "Within the common
  epoch 2020–2024, negatives are front-loaded on 2020 (1,861 of 4,809)
  while positives peak in 2022; year predicts the label at AUC 0.6615."
  Cause: untested hypothesis (PA-0016) — `get_negatives.py` pass-1 order
  and positives' latest-visit year. Owner: a future CR after a user
  decision on a GBIF re-fetch (year-matched draw infeasible from today's
  pool: 215 short in 6 of 30 cells).
- **BUG_LOG.md:** update BUG-0034's row; add BUG-NEW-a.
- **PA-0020 Swept? cell:** BUG-0034 live instance FIXED by CR-0019;
  source-axis item resolved (all 43,024 raw sightings carry the negatives'
  dataset key, `preregister.txt`); `ebird.py` path latent; sweep items:
  `train.sample_background_points` fixed vintage, envelope-metric epoch
  (B4), duplicated `START_YEAR`.
- **Tracker:** CR-0020 (retrain/baseline); §6 warning; BUG-NEW-a; B12.
