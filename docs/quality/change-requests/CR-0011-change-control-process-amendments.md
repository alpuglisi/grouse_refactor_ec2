# CR-0011: Amend `CLAUDE.md` §1 to bound review rounds and allow gate code before approval

**Status: APPROVED by user 2026-09-30 (all of A1–A5); applied to `CLAUDE.md`.** Originally proposed with `CLAUDE.md`
unchanged. Each amendment below is independent; the user may accept any
subset.

## Scope
Change the change-control process in `CLAUDE.md` §1 so that CRs converge
in fewer rounds, without weakening the review-before-merge guarantee.

## Why now
CR-0007 and CR-0008 each went through 7+ review rounds without approval
(about 16 reviews in total). The core analysis in both was repeatedly
confirmed; rejections came from:
1. **Unbounded rounds.** Each round was an open-ended "try to break it",
   so every round found new MEDIUM/LOW items and the CR stayed open.
2. **Acceptance gates written as prose.** Statistical gates were specified
   in words, reviewers broke them on paper, and each fix was more prose.
3. **Documents that accumulate history.** Revision notes and corrections
   were layered on the body; withdrawn claims survived in operative text
   four times in CR-0008 alone.
4. **Oversized CRs.** Any flaw in any part rejected the whole package.

## Amendments

### A1 — Severity-gated approval (§1.3/§1.4)
Add to §1.3:
> Each reviewer concern carries a severity: **BLOCKING** (the change as
> written would produce a wrong result, lose data, or cannot be
> implemented), **MAJOR**, **MEDIUM** or **LOW**. Only BLOCKING concerns
> prevent approval. MAJOR concerns must be dispositioned in the CR before
> approval but may be dispositioned as a tracked follow-up. MEDIUM/LOW
> concerns are recorded in the CR's review log and in an open-issues file
> with an owner; they do not reopen the CR.

Add to §1.4:
> A reviewer may sign off with open non-blocking concerns
> ("APPROVE WITH FOLLOW-UPS").

### A2 — Bounded re-review (§1.2)
Add to §1.2:
> A re-review of a revised CR examines (a) whether each prior BLOCKING
> and MAJOR concern is resolved in the operative text, and (b) the text
> that changed since the last round. New findings outside the changed text
> are raised only if BLOCKING. The first review of a CR remains
> unrestricted. After three rounds without approval, the author must
> split the CR or escalate the open blocking items to the user for a
> decision before a fourth round.

### A3 — Gate and test code before approval (§1.1/§1.5)
Add to §1.1:
> Acceptance checks for a CR (verification scripts, tests, pinned
> constants) may be written and committed on an unmerged branch **before**
> approval, and reviewed as part of the CR. Production code, data changes
> and anything that writes to `data/` still wait for approval. A CR whose
> acceptance depends on a statistical threshold must reference the
> committed script that computes it rather than restate its numbers in
> prose.

### A4 — Clean-document rule (§1.1)
Add to §1.1:
> A CR states only current intent. Revision notes, superseded text,
> verdicts and dispositions go in a companion `CR-XXXX-review-log.md`.
> Each fact (a count, threshold, citation) appears once in the CR; other
> sections refer to it. On revision, superseded text is deleted from the
> CR, not annotated.

### A5 — Size limit (§1.1)
Add to §1.1:
> A CR should cover one independently landable change. If a CR's
> deliverables span more than one of {data repair, generator/pipeline
> code, acceptance design, bookkeeping}, split it unless the parts cannot
> land separately, and say why.

## Impact
- Applies to all future CRs and to revisions of open CRs (CR-0007,
  CR-0008, CR-0009, CR-0010).
- A1 and A2 reduce the rigour of later rounds by design; A3 compensates
  by making acceptance executable and testable.
- A3 relaxes "nothing implemented before approval" for check code only.

## Risk: LOW–MEDIUM
| risk | mitigation |
|---|---|
| A real defect is filed as MEDIUM and never fixed | Open-issues file with owner; any reviewer may escalate to BLOCKING with a stated failure scenario |
| Bounded re-review misses a defect in unchanged text | First review is unrestricted; BLOCKING findings anywhere still count |
| Gate code written before approval biases the design | Reviewers review the gate code as part of the CR |

## Test plan
Apply to CR-0010 (the first CR written in this style) and to CR-0007/0008
v8. Success measure: CR-0010 reaches approval in ≤ 2 rounds.

## Deliverables
- [x] User decision on each of A1–A5 (all accepted, 2026-09-30).
- [x] Edit `CLAUDE.md` §1 with the accepted amendments.
- [x] Note in `CLAUDE.md` project-specific notes that the open-issues file
      (`docs/quality/CR-0007-0008-OPEN-ISSUES.md`) is the follow-up tracker.

## Out of scope
- §2–§4 (bug logs, preventive actions, recurrence review).
- Adding CI.
