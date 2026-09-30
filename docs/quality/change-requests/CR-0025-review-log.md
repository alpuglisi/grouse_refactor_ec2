# CR-0025 review log

## Lineage
From BUG-0081 (2026-09-30 static review). Author: the review session
that filed BUG-0081. Reviewers: two fresh agents, each re-deriving from
the code before reading the CR (CLAUDE.md §1.2, §1.4 agent-only quorum).
Review logs were not read by the reviewers. Both found the fifth skip
path that BUG-0081 §2 also omitted; BUG-0081 §1–2 corrected the same day.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | REVISE | 1 |
| 1 | v1 | B (agent, fresh) | REVISE | 0 |
| 2 | v2 | A (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS | 0 |
| 2 | v2 | B (agent, fresh; bounded) | APPROVE WITH FOLLOW-UPS | 0 |

## Round 1, reviewer A
- **A1 BLOCKING:** §2 lists four skip paths; the code has a fifth at
  `analyze_grouse.py:836-837` ("No {region} records survived
  extraction"). Scenario: no `nh_sightings_*.csv` on disk, the NH box
  still holds ME/VT records → `:837` → the previous
  `evaluated_sightings_NH.csv` / `envelope_metrics_NH.csv` remain and
  are digested (PA-0038(a) unmet).
- A2 MAJOR: the `:884` path returns `(valid, None)`, so `__main__`
  (`:1123-1130`) prints it as complete and exits 0 while the metrics file
  is removed (PA-0038(b) unmet).
- A3 MAJOR (PA-0021(a)): the fixture test as written passes on today's
  code if no files pre-exist; it must pre-seed stale files and assert
  removal and exit 1, plus a `:884` case.
- A4 MEDIUM: "the map keeps its own `try` (BUG-0069 handlers)" is false;
  the only handlers are in `load_state_boundaries` (`:653-672`).
- A5 MEDIUM: the writes stay non-atomic (`:551`, `:876`, `:1099-1100`);
  adopt temp+`os.replace` or record against BUG-0079/CR-0023.
- A6 LOW: the helper derives paths from `PATH_TEMPLATES` while `:876` and
  `:1099-1100` remain literals (PA-0003).

## Round 1, reviewer B
- B1 MAJOR: same as A1 (`:836-837`; BUG-0081 §2 has the same omission).
- B2 MAJOR: the `:882` provision is wrong on three counts: (a) today that
  path writes only `nonveg_flagged` (`:877`), not `evaluated`; (b)
  `valid` at `:884` lacks `env_zone`/`envelope_id` (added at ~`:1011`),
  so writing it creates a second schema for the `evaluated` entry
  (PA-0045) that `prepare_training_data.py:395-398` cannot see on the
  pooled concat; (c) `__main__` counts only `r is None` as skipped.
- B3 MEDIUM: same as A4 (an implementer citing the sentence could add a
  swallow-all handler, PA-0027).
- B4 LOW: `:251` is inside `clip_to_region` (the call is `:741`); an
  unhandled exception mid-region leaves the same stale files; removal at
  region start covers both.
- B5 LOW: test-plan honesty confirmed (module-level rasterio); no action.

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location) |
|---|---|---|
| A1 / B1 | BLOCKING / MAJOR | **Accept** — §2 second bullet lists `:837`; § 3 has its case; BUG-0081 §1–2 corrected |
| A2 / B2 | MAJOR | **Accept** — §2 third bullet: `:884` becomes a full skip (returns `None`, removes the four outputs including the just-written `nonveg_flagged`); no second `evaluated` schema; `__main__`'s `r is None` now covers it |
| A3 | MAJOR | **Accept** — § 3: pre-seeded stale files in every case; exit code and `INCOMPLETE` asserted; `:884` case; injected map exception case |
| A4 / B3 | MEDIUM | **Accept** — sentence removed; §2 fifth bullet states that a plotting exception propagates after the CSVs are complete and what that leaves |
| A5 | MEDIUM | **Accept** — §2 fourth bullet: `write_csv_atomic` for all four writes (PA-0036(a)); Scope and deliverable 4 updated |
| A6 | LOW | **Accept** — §2 fourth bullet: paths from `PATH_TEMPLATES` |
| B4 | LOW | **Accept** — §2 second bullet: `remove_region_outputs` is the first statement of `analyze_region`, so exceptions are covered too; `:251` cited as reached via `:741` |
| B5 | LOW | noted; no change |

## Round 2 (v2), reviewer A (bounded, CR-0011 A2)
A1/B1 (BLOCKING/MAJOR), A2/B2 and A3 (MAJOR) verified RESOLVED against
the code (five non-final exits; `:884` writes only `nonveg_flagged`;
`env_zone` joins at `:1010-1012`; every § 3 row fails today).
- A-N1 MEDIUM: "ahead of the map block (`:1010-1097`)" — the map block
  is `:1015-1097`; `:1010-1012` is the `env_zone`/`envelope_id` join;
  taken literally the writes would precede the join and produce the
  PA-0045 second schema.
- A-N2 LOW: cites (`:877-878`; handlers `:641-645`, `:654-663`,
  `:666-676`; `grouse_data.py:281-283`).
- A-N3 LOW: `check_partition.py:382`/`:477` report FAIL lines through
  `Missing`, they do not raise.
- A-N4 LOW: PA-0042 readers of `evaluated_sightings_{R}.csv` with
  print-and-skip (`tune.py`, `tune_bins.py`, `clean.py`, `dupe_check.py`,
  `check_exotic.py`).
- A-N5 LOW: `PATH_TEMPLATES["diagnostic_map"]` is a fifth per-region
  output left stale.
- A-N6 LOW: bullet 3's write-then-remove is reached after a write
  (PA-0038(c) wording); move the check ahead of the write.
- A-N7 LOW: test mechanics (subprocess, cwd, `MPLBACKEND=Agg`);
  byte-identity scoped to the CSVs.

## Round 2 (v2), reviewer B (bounded, CR-0011 A2)
Same RESOLVED table; the return-type change reaches one caller
(`:1118`); `write_csv_atomic` byte-identical; no concurrent readers;
PA-0027 lint pins of `load_state_boundaries` untouched.
- B-L1 LOW: "an unhandled exception leaves no output" overstates (a
  complete `nonveg_flagged` of this run can remain); say "no output of a
  previous run".
- B-L2 LOW: same as A-N5.
- B-L3 LOW: cites (`:877-878`; `__main__` `:1108`).
- B-L4 LOW: the test table covers 3 of 5 skip paths.
- B-L5 LOW: `background_envelope_sample`'s `return None` (`:546`) is a
  designed in-region fallback that a previous file no longer masks;
  record in Impact.

## v3 dispositions (round 2)
| # | sev | disposition (operative location) |
|---|---|---|
| A-N1 | MEDIUM | **Accept** — §2 fifth bullet: writes after the join (`:1010-1012`), before the map (`:1015-1097`) |
| A-N2 / B-L3 | LOW | **Accept** — cites corrected |
| A-N3 | LOW | **Accept** — §2 last bullet: FAIL lines through `Missing` |
| A-N4 | LOW | **Accept** — § Impact fourth bullet; tracker items in deliverable 4 |
| A-N5 / B-L2 | LOW | **Accept** — §2 first bullet: five outputs including `diagnostic_map` |
| A-N6 | LOW | **Accept** — §2 third bullet: the check moves ahead of the write; no second removal |
| A-N7 | LOW | **Accept** — § 3 mechanics; deliverable 3 scoped to the CSVs |
| B-L1 | LOW | **Accept** — §2 second bullet wording |
| B-L4 | LOW | **Accept** — § 3 table covers all five paths |
| B-L5 | LOW | **Accept** — §2 last bullet |

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
| v1 | initial draft (removal at each of four skip paths) |
| v2 | removal at region start; fifth path; `:884` full skip; atomic writes; pre-seeded fixture test; round-1 dispositions |
| v3 | writes after the `env_zone` join; five outputs; check ahead of the `nonveg_flagged` write; all five skip cases; round-2 dispositions above; approved by agent quorum |
