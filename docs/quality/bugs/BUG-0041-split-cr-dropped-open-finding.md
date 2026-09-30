# BUG-0041: A finding marked "resolved" in a split CR was dropped — its subject had moved to another CR

## 1. Description
When CR-0008 was split (v8), its `road_dist` acceptance gates (G7,
RD1–RD5) moved to CR-0014. Round-7 finding R7-12 had flagged those gates'
thresholds as fitted without a null distribution. CR-0008's v8 log marked
R7-12 "Resolved — v8 has no statistical thresholds", which was true of the
text left in CR-0008 but not of the finding: its subject had left with the
scope. CR-0014's lineage table carried the gates but not R7-12, so the
finding reached no reviewer and CR-0014 implemented RD1 and RD4 uncalibrated
(BUG-0040). A process defect under `CLAUDE.md` §1.3 ("never silently drop
a finding").

## 2. Where encountered
- `docs/quality/change-requests/CR-0008-review-log.md:196` (R7-12's v8
  disposition).
- `docs/quality/change-requests/CR-0014-review-log.md`, § Lineage (carries
  "G7 RD1–RD4, strata, 60 m derivation", not R7-12).
- Found by CR-0013's PA-0021 sweep (deliverable 2a), recorded in BUG-0040.

## 3. What it caused to fail
RD1 and RD4 shipped in `check_road_dist.py` without calibration (BUG-0040).
Two independent reviewers per round, two rounds on CR-0014, did not catch
it, because nothing in CR-0014 pointed at the concern.

## 4. What the defect was
`CR-0008-review-log.md`, verbatim:
```
| R7-12 PA-0021 exemptions / fitted thresholds | **Resolved** — v8 has no statistical thresholds; every gate is exact equality |
```
and `CR-0014-review-log.md`'s lineage row, verbatim:
```
| G7 RD1–RD4, strata, 60 m derivation | v7 G7 | Acceptance |
```

## 5. Root cause analysis (Five Whys)
1. *Why did RD1/RD4 ship uncalibrated?* No CR-0014 reviewer was told they
   had been challenged.
2. *Why not?* CR-0014's lineage table listed the gates, not the open
   findings against them.
3. *Why was R7-12 not open in CR-0008 any more?* Its disposition judged the
   finding against the text remaining in CR-0008, and "no statistical
   thresholds remain here" read as "resolved".
4. *Why was that accepted?* The split was done by moving scope and then
   dispositioning findings per CR; nothing required a finding whose subject
   moved to be moved with it.
5. *Why no check?* Neither a disposition's claim nor a split's lineage is
   verified against the other CR — the disposition cited no location in
   CR-0014.

**Root cause:** a disposition may say "resolved" by pointing at the absence
of its subject, and a split CR's lineage lists moved scope but not the open
findings attached to it.

## 6. Corrective action
- R7-12 is re-attached to CR-0014's scope as BUG-0040, with its own CR
  (CR-0016: demote RD1 and RD4 to observations).
- PA-0024 (below).
- CR-0008's log row is annotated to point at BUG-0040.

Status: **FIXED** (process: PA-0024; the dropped finding re-owned by
BUG-0040 / CR-0016).

## 7. Recurrence review
Searched `BUG_LOG.md`, `PREVENTIVE_ACTIONS.md` and the review logs for
dispositions that did not hold:
- **CR-0008 v5** recorded a fix "Accepted — §9.2 rewritten" against a
  section that did not exist (round 6, #1); logged in CR-0008's history,
  no BUG filed then.
- **CR-0007 v8** recorded E-1 as resolved in CR-0013 deliverable 0, which
  did not contain it (round 8, B2); corrected in v9, no BUG filed.
- **BUG-0019 / PA-0015**: sweeps not run — a different step (sweeps, not
  dispositions), but the same shape: a required action recorded as done
  without a check that it was.
- **This is at least the third false disposition.** No PA covered it: the
  CR-0008 v6 note said it was "PA-0021's territory", but PA-0021 governs
  acceptance criteria, not dispositions.

**Prior-preventive-action failure analysis.** `CLAUDE.md` §1.3 already
forbids dropping a finding. It failed because it is **not
enforced-verifiable**: nothing requires a disposition to name the
operative location of its fix, so neither author nor reviewer has
anything to check. PA-0015 made sweep status visible; nothing did the same
for dispositions.

## 8. Preventive action
**PA-0024** (new; strengthens `CLAUDE.md` §1.3):
(a) Every "resolved"/"accepted" disposition names the operative location
of the fix (CR, section or file:line); a reviewer checks that the location
exists and contains the fix. "Resolved because the subject is no longer in
this CR" is not a disposition — it is a move.
(b) When a CR is split, each new CR's lineage table lists every open
finding (from the source CR's review log and the tracker) whose subject
moved with the scope, and the source CR's log marks each "moved to
CR-XXXX" — never "resolved".

**Sweep (§3.5)** — the four splits so far:
- CR-0008 → CR-0014: this bug (R7-12). Fixed via BUG-0040.
- CR-0012 → CR-0015: CR-0015's round-1 reviewer B found six lineage items
  missing (B9); being fixed in CR-0015 v2.
- CR-0008 → CR-0010 and CR-0007 → CR-0012/CR-0013: their reviewers
  checked lineage coverage explicitly (CR-0012 round-1 B6, CR-0013 round-1
  C7) and the missing rows were added. No further instance.

**Mechanical enforcement:** not yet feasible (no CI, logs are prose). A
candidate: a test that parses every review log for "moved to CR-XXXX" and
checks the id appears in CR-XXXX's lineage table.
