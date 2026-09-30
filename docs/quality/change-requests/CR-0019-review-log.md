# CR-0019 review log

Verdicts, concern dispositions and revision history for
`CR-0019-common-year-floor.md`. The CR states only current intent
(CR-0011 A4).

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 (`95d7463`) | A (first attempt, fresh agent) | none: stopped by the lead before reporting; partial scratch kept as evidence (`reviewA/analyse.*`, `pipeline_floor_run.py`, `wrong_tree*`) | – |
| 1 | v1 (`95d7463`) | B: implementability, composition, acceptance (fresh agent) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR, 3 MEDIUM, 8 LOW) |
| 1 (A's first review, unrestricted) | v2 (`a89151f`) | A: correctness of diagnosis and fix (fresh agent, replacing the stopped one; run by the lead) | APPROVE WITH FOLLOW-UPS | 0 (0 MAJOR, 2 MEDIUM, 4 LOW); `reviewA/review_round1_v2.md` |
| 2 (bounded, A2) | v2 (`a89151f`) | B (run by the lead) | APPROVE WITH FOLLOW-UPS | 0 (3 LOW); B1, B2 resolved; `reviewB/review_round2.md`, `mc_wrongtrees_round2.txt` |

**Approval (v3).**
- Author and reviewers approved; user pre-authorised (2026-09-30).
- Quorum (CLAUDE.md §1.4): the author and both reviewers who commented.
  A: APPROVE WITH FOLLOW-UPS (first review, v2). B: APPROVE WITH
  FOLLOW-UPS (round 2, v2).
- No BLOCKING concern in any round. The only MAJOR concerns (B1, B2) were
  resolved in v2 and confirmed resolved by B in round 2.
- v3 applies the MEDIUM/LOW dispositions below (lead decisions,
  2026-09-30, each verified against the code by the author). Per CR-0011
  A1 MEDIUM/LOW changes do not reopen the CR, so no further round was run.

Both reviewers re-derived from code and data, not the CR:
- **A** reproduced the pre-registration byte for byte, ran the **real**
  `prepare_training_data`/`generate_negatives` on a scratch tree with the
  floor (MC 42/42 vs live), measured the train-time filter at tolerances
  2/3/−1/1 (0/0/0/928 P, 1,861 N), and every number in §4.
- **B** built 23 wrong and correct trees (PA-0021(a)) in rounds 1 and 2;
  every no-op, deletion, wrong floor and rewritten covered value fails MC.

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

## Reviewer A (first review of v2): concerns and dispositions
Checked by the author before applying: 99,744 raw candidates are year
2020 (A1); 98.9 % of selected N carry their key's earliest year, 11.4 %
have a later one, and AUC 0.6615 / 0.5584 / 0.6125 (A2), all re-measured;
`tests/test_cr0012.py:593` is `rng.choice([2023, 2024, 2025])` (A3).

| id | sev | concern (short) | disposition | where (v3) |
|---|---|---|---|---|
| A1 | MEDIUM | `YEAR_MIN` filters positives but only guards negatives; raising it (the refusal's remedy) crashes pool step 1 | Accepted (lead decision): pool step 1 is a filter (non-null `year < YEAR_MIN` dropped; nulls still at step 7); no-op today, pre-registration and MC unchanged; new test with `YEAR_MIN` above the lowest candidate year; new attack row "No pool floor" | Scope; §2 pool step 1; §3 attacks; test plan |
| A2 | MEDIUM | §5 misattributes the residual: two different representative-year rules; a re-fetch is not the only route | Accepted: §5 and BUG-NEW-a list both rules (latest visit vs smallest `gbif_id` ≈ earliest) with the measured AUCs as candidate causes; both rules in deliverable 8's sweep; residual stays out of scope | §5; deliverable 8; Out of scope; § Proposed bookkeeping |
| A3 | LOW | `test_cr0012.py` fixture edit is a no-op | Accepted (= B2-1): no change to that file; dropped from deliverable 3 | §3 "Existing fixtures"; deliverable 3 |
| A4 | LOW | E14(b) exact on the small fixture can fail the correct tree by chance | Accepted: fixture years set deterministically so the correct tree's P/N year sets are equal by construction, asserted by a test | §3 "Existing fixtures" |
| A5 | LOW | "revert the merge" leaves a revert-of-merge on `main` | Accepted: live steps run with the CR-0019 branch checked out in the live tree; merge only after acceptance passes; failure = restore + checkout `main`. Checked against the refusal logic: the record binds the config's content sha256 and the digests, not the commit, so it stays valid across the merge; `--standing` re-run after the merge | § Impact "Refusal window"; deliverable 6 |
| A6 | LOW | §6 warning is prose only | Tracked follow-up, owner BUG-0060 (tracker) | – |

## Reviewer B round 2: findings and dispositions
| id | sev | finding | disposition | where (v3) |
|---|---|---|---|---|
| B2-1 | LOW | `test_cr0012.py` edit is a no-op | Accepted (= A3) | §3; deliverable 3 |
| B2-2 | LOW | "Positives later than every negative" row lacks the surviving-habitat-positive wording | Accepted: reworded like "No floor" | §3 attack table |
| B2-3 | LOW | committed `__pycache__/*.pyc` | Accepted: `git rm --cached` in the v3 commit | – |

## Proposed bookkeeping (for deliverable 8; the lead files)
- **BUG-0034 §6/status:** corrective action "CR-0019 (floor at selection,
  refusal, E14)"; status FIXED for the root cause (disjoint support);
  consequence (b)'s within-epoch remainder moved to BUG-NEW-a (PA-0024(b)).
- **BUG-NEW-a (proposed; the lead allocates, next free BUG-0073):**
  "Within the common epoch 2020–2024, negatives are front-loaded on 2020
  (1,861 of 4,809) while positives peak in 2022; year predicts the label
  at AUC 0.6615." Candidate causes, each an untested hypothesis until its
  own check (PA-0016): (1) positives' representative year is the latest
  visit, negatives' is the smallest `gbif_id` (≈ earliest year, 98.9 %) —
  AUC 0.5584 with positives at `max(first_year, 2020)`, 0.6125 with
  negatives at their latest year; (2) `get_negatives.py` acquisition order
  (pass-1 quotas, rollover). Remedies: harmonise the rule (no network), a
  year-matched draw (215 short in 6 of 30 cells today), or a re-fetch
  (user decision). Owner: a future CR.
- **BUG_LOG.md:** update BUG-0034's row; add BUG-NEW-a.
- **PA-0020 Swept? cell:** BUG-0034 live instance FIXED by CR-0019;
  source-axis item resolved (all 43,024 raw sightings carry the negatives'
  dataset key, `preregister.txt`); `ebird.py` path latent; sweep items:
  `train.sample_background_points` fixed vintage, envelope-metric epoch
  (B4), the two representative-year rules (A2), duplicated `START_YEAR`.
- **Tracker:** CR-0020 (retrain/baseline); §6 warning; BUG-NEW-a; B12;
  A6 (BUG-0060).
