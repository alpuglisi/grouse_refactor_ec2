# Quality Management System — read first, every session

This repository (`grouse_refactor_ec2`) is a Python codebase for grouse
habitat/sighting data processing, model training, and prediction (dataset
prep, calibration, training, tuning, prediction, and various one-off
download/cleaning scripts). It has no bash scripts at present, but this
policy applies equally to any bash scripts added later.

This file defines four linked mechanisms. **Do not skip the bookkeeping
below** — it is part of every change, not optional cleanup.

1. **Change control** — nothing non-trivial is implemented without a
   reviewed, approved proposal first.
2. **Bug logs** — every defect gets a structured root-cause investigation,
   not just a fix.
3. **Corrective actions as enforced policy** — the lesson from a bug becomes
   a standing rule that is read and followed on every subsequent change.
4. **Recurrence review** — every new bug is checked against prior bugs and
   prior corrective actions before a new one is written.

## Where things live

- `docs/quality/change-requests/CR-XXXX-slug.md` — change control records.
- `docs/quality/bugs/BUG-XXXX-slug.md` — full bug investigations.
- `docs/quality/bugs/BUG_LOG.md` — flat, newest-first running log of all
  bugs (quick-scan index; cross-references the full investigation docs).
- `docs/quality/PREVENTIVE_ACTIONS.md` — the single distilled, mandatory
  rule list. Read this before making any change.

IDs are per-project flat counters, zero-padded to 4 digits, assigned in
discovery/creation order and never reused or renumbered:
- `CR-0001`, `CR-0002`, ... for change requests.
- `BUG-0001`, `BUG-0002`, ... for bug investigations.
- `PA-0001`, `PA-0002`, ... for preventive actions.

## 1. Change control (approval before implementation)

**Rule: propose, then get independent review, then implement — in that
order, every time, for any change beyond a trivial/obvious fix.** A
trivial/obvious fix is a change confined to a single function, with no
behavior change beyond the bug being fixed, and no change to a public
function signature, file format, or data schema — anything else requires
a change request.

1. Write `docs/quality/change-requests/CR-XXXX-slug.md` **before** touching
   code. It must state: scope (one sentence), why now, the change itself in
   enough detail to review without re-deriving it (root cause if fixing a
   bug, concrete before/after), impact on other parts of the system, a risk
   level with mitigation or accepted-risk justification, a test plan
   (including what can't be validated in this environment and why), an
   explicit deliverables checklist (each item starts pending), and explicit
   out-of-scope items.
2. Get independent review: at minimum one reviewer who did not write the
   proposal re-derives the diagnosis and fix from the current state of the
   thing being changed, not from the proposal's prose. Two independent
   reviewers is stronger than one.
3. Every reviewer concern gets a disposition recorded in the CR: accepted
   and revised, or explicitly justified as not applicable. Never silently
   drop a finding. Verify a reviewer's claimed correction against the real
   system before applying it.
4. **Approval quorum for this project: all reviewers who commented, plus
   the author, must sign off.** For AI-agent-only workflows (no human
   reviewer available), a second independent agent review satisfies this;
   record both verdicts in the CR. Record each reviewer's verdict and each
   concern's disposition in the CR itself.
5. Only after approval: implement, validate against the test plan, and
   close out the deliverables checklist. The CR stays open until every
   deliverable — including the bug log and preventive-action bookkeeping
   below — is checked off.

## 2. Bug logs (root cause, not just a fix)

**Rule: every code defect — a failing test, a wrong result, a crash, a
regression, a security-relevant flaw — gets
`docs/quality/bugs/BUG-XXXX-slug.md`, not just a patch.** A defect found in
review counts, even if never observed running.

Each investigation contains, at minimum:

1. **Description** — brief description of the defect.
2. **Where encountered** — file/tool/test/context (`path:line`).
3. **What it caused to fail** — the observable impact.
4. **What the defect was** — quote the actual faulty code/logic verbatim,
   not a paraphrase.
5. **Root cause analysis** — a named method (Five Whys, fault-tree,
   differential analysis), with steps shown, ending in one stated root
   cause.
6. **Corrective action** — what was actually changed, referencing the CR
   that delivered it. Verify the fix addresses the root cause, not just the
   symptom.
7. **Recurrence review** (§4 below) — done *before* deciding the preventive
   action.
8. **Preventive action** — the standing rule derived from the root cause,
   added to `PREVENTIVE_ACTIONS.md` (§3).

Also append a one-line entry (date, symptom, root cause, remediation,
status) to `docs/quality/bugs/BUG_LOG.md`, newest first, cross-referencing
the full BUG-XXXX doc.

Numbering is append-only: never renumber or delete a prior BUG entry, even
if it's later found to be a duplicate (mark it "duplicate of BUG-000N"
instead).

## 3. Corrective actions as enforced policy

**Rule: a preventive action is a rule that must be read and followed on
every subsequent change, not a note filed with the bug that produced it.**

1. `docs/quality/PREVENTIVE_ACTIONS.md` is the single, distilled,
   no-background rule list — every preventive action ever derived, terse
   and actionable, each with a back-reference to the BUG-XXXX that produced
   it. No prose justification lives there — that's the bug doc's job.
2. This list is mandatory, not advisory — consult it before every change;
   a violation is a defect.
3. A rule must target the **mechanism**, not the symptom or the specific
   trigger that first surfaced it.
4. When a rule can't be trusted to be followed by memory alone, add
   mechanical enforcement (a hook, a lint rule, a CI check, a test) where
   feasible in this environment; note explicitly when it isn't feasible yet.
5. **Sweep the codebase for other instances of the same bug class**
   whenever a new preventive action is added, scoped by the mechanism, not
   the narrower trigger — and remediate what the sweep finds (each
   remediation gets its own BUG-XXXX entry, cross-referencing the sweep).
6. This list only grows — never delete or water down a rule; a superseded
   rule says so explicitly and points to its replacement.

## 4. Recurrence review (retrospective check before the new preventive action)

**Rule: before writing a new preventive action, check whether this is
actually a second occurrence of something already supposedly prevented.**

1. Search `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for a previous instance
   of the same bug, or a different bug with the same root cause. State
   plainly what was checked and the result — a specific prior ID, or "none
   found."
2. If a match is found, before deciding the new preventive action, write a
   **prior-preventive-action failure analysis** in the new BUG-XXXX doc:
   why didn't the earlier rule prevent this recurrence? (Too narrow / wrong
   layer / not actually followed / not enforced-verifiable.) Name the prior
   bug and prior preventive action explicitly.
3. The new preventive action must strengthen or supersede the prior one,
   cross-referencing it explicitly ("extends PA-000N", "supersedes
   PA-000N") — never just restate the old rule with a new example appended.
4. Apply this review to every new bug, every time.

## 5. How the pieces fit together

1. Defect found (review, testing, or the field).
2. If non-trivial: write the CR (§1), get it independently reviewed, revise,
   reach approval.
3. Implement the approved fix.
4. Write the full bug investigation (§2), including recurrence review (§4)
   before finalizing the preventive action.
5. Add the resulting rule to `PREVENTIVE_ACTIONS.md` (§3), sweep for sibling
   instances, remediate what's found.
6. Cross-reference the CR ID, BUG ID, and PA ID in all three artifacts.

None of the three bookkeeping artifacts substitutes for the others.

## Project-specific notes

- Language: Python (this repo currently has no shell scripts; if any are
  added, review them under the same policy).
- "Trivial enough to skip a CR": a fix confined to one function, no public
  API/schema/CLI-flag change, no behavior change beyond the defect itself.
  Bug logging (§2) is still required even for trivial fixes — only the CR
  is skippable.
- No CI is configured in this repository yet; mechanical enforcement of
  `PREVENTIVE_ACTIONS.md` rules (§3.4) is currently manual review only.
  Adding CI/lint enforcement is itself a candidate change (open a CR).
