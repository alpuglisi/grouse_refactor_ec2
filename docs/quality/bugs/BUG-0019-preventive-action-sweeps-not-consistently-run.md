# BUG-0019: Preventive-action sweeps (`CLAUDE.md` §3.5) were not consistently run when new preventive actions were added

## 1. Description
`CLAUDE.md` §3.5 states sweeping the codebase for sibling instances of a
bug class "is not optional" whenever a new preventive action is added. An
audit of this session's own bug docs shows this step was skipped for most
of PA-0001 through PA-0011: several preventive actions have zero
documented sweep activity anywhere in the bug log, and two (PA-0010,
PA-0012) are directly proven to have gone unswept by the fact that later
bugs (BUG-0014, BUG-0015) were found only because a *separate*, later
review pass happened to re-check the same ground.

## 2. Where encountered
Process defect in this session's own execution of the QMS, not in the
target repository's Python code. Evidenced by:
- `grep -rn "PA-0003\|PA-0004\|PA-0005\|PA-0007\|PA-0009" docs/quality/bugs/*.md`
  (excluding `PREVENTIVE_ACTIONS.md` itself) returns **zero matches** for
  all five — no bug doc anywhere records a sweep having been run for these
  preventive actions.
- `BUG-0014`'s own root-cause analysis: the BUG-0012 fix "targeted only
  the call sites its investigation quoted... not a full sweep."
- `BUG-0015`'s own root-cause analysis: PA-0012's sweep obligation
  "existed, but the sweep itself hadn't been run against files outside
  the originally-flagged cluster" until a later, separate pass found it.

## 3. What it caused to fail
The mechanism §3.5 exists to prevent — a fix landing for one instance of a
bug class while siblings of the same class remain broken — happened twice
in this session's own work (BUG-0014, BUG-0015) before anyone asked
whether the process was actually being followed. For PA-0003, PA-0004,
PA-0005, PA-0007, and PA-0009 specifically, no sweep has been run at all,
so it is unknown (not "confirmed absent") whether sibling instances of
those five bug classes exist elsewhere in the 34 reviewed files.

## 4. What the defect was
The QMS's own written rule (`CLAUDE.md` §3.5):
```
Sweep the codebase for other instances of the same bug class whenever
a new preventive action is added, and remediate what the sweep finds.
A preventive action that only fixes the one instance found leaves every
sibling instance of the same class in place; the sweep is not optional...
```
was not executed as a discrete, verifiable step at the time each PA-0001
through PA-0011 was written. In practice, "sweep coverage" for the ones
that did get some was incidental — the original bug hunt happened to use
parallel agents covering many files at once (PA-0001/PA-0002), or a later,
unrelated review pass happened to re-check the same ground (PA-0006,
PA-0008, PA-0010, PA-0012) — not because the PA's own creation triggered a
dedicated sweep.

## 5. Root cause analysis (Five Whys)
1. Why did five preventive actions go unswept entirely? Because writing
   the preventive-action list entry was treated as the deliverable, and
   the sweep was treated as optional follow-up rather than a required
   step in the same unit of work.
2. Why was the sweep treated as optional in practice, when the policy
   text says otherwise? Because nothing checked, at the moment each PA
   was written, whether a sweep had actually been run and its result
   recorded — there was no mechanical or even a manual checklist gate.
3. Why did the two PAs that *did* eventually get swept (PA-0006, PA-0010,
   PA-0012) only get it via a later, separately-motivated review pass
   rather than at PA-creation time? Because the sweep step, as written,
   depends entirely on the same session/agent remembering and choosing to
   do it immediately after writing the PA — a "remember to check" process
   with no structural enforcement.
4. Why does that matter, given the rule is stated clearly in `CLAUDE.md`?
   Because a written rule that depends on memory alone is exactly the
   failure mode `CLAUDE.md` §3.4 itself warns about: "When a rule
   genuinely can't be trusted to be followed by memory alone... add
   mechanical enforcement." No mechanical enforcement was ever added for
   the sweep step specifically.
5. Why wasn't that gap noticed until the user asked directly? Because
   nothing surfaces "N preventive actions exist, M have a documented
   sweep" as a status a session would see without being asked — it's
   discoverable only by manually grepping the bug docs, which nothing
   prompts a session to do proactively.

**Root cause:** the sweep step is a written policy that depends on the
implementing session remembering to perform and record it at PA-creation
time, with no structural checkpoint (a checklist field, a required section
in the PA table, or an explicit verification step) forcing that to happen
or making its absence visible without a manual audit.

## 6. Corrective action
1. Ran the five outstanding sweeps (PA-0003, PA-0004, PA-0005, PA-0007,
   PA-0009) in this same change — see their own results, logged as new
   BUG-00XX entries where anything was found, or recorded as "swept, none
   found" in `PREVENTIVE_ACTIONS.md` otherwise.
2. Added a **Swept?** column to `PREVENTIVE_ACTIONS.md`'s table (see §8
   below) so the absence of a sweep is visible at a glance in the artifact
   itself, not only discoverable by grepping bug docs.
Status: **CLOSED for the five named PAs' sweeps** (this change); the
structural gap this bug is actually about (§7-8) is what's newly enforced
going forward.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: this is not a new
mechanism so much as a **name for a pattern already visible in BUG-0014
and BUG-0015's own root-cause analyses** — both already identified "the
sweep obligation existed but wasn't executed" as their root cause. This
bug generalizes that observation from two specific instances to the
process itself, and closes the remaining gap (the sweeps that were never
run at all, not just the ones later found to be incomplete).

**Prior-preventive-action failure analysis:** PA-0012 ("re-run this sweep
on every review pass") and PA-0013 ("verify a key-consumption fix via
grep before closing the bug") both already state pieces of the fix, but
neither makes the *absence* of a sweep visible before a defect is found
downstream — both are still "remember to do X" rules, the same failure
mode `CLAUDE.md` §3.4 warns about. This bug's preventive action (§8)
supersedes that gap by adding a checkable field to the PA table itself.

## 8. Preventive action
**PA-0015** (new, see `PREVENTIVE_ACTIONS.md`) — supersedes/extends
PA-0012's "not optional" wording with mechanical visibility: every
`PREVENTIVE_ACTIONS.md` entry must carry a **Swept?** status (`yes -
<what was checked>`, `no - not yet run`, or `n/a - single-instance,
no bug class to sweep`, per `CLAUDE.md` §3.6's exception for cosmetic
single-instance findings like BUG-0018). A PA row reading "no" is a
visible, standing to-do, not something that requires re-grepping every
bug doc to discover — the next session/reviewer touching this table sees
unswept rows immediately.
