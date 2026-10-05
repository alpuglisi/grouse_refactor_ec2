# Round 3: last revision brief

This is the last round. What you write now is your final proposal.

## Inputs
Everything is in `/tmp/claude-0/-home-user-grouse-refactor-ec2/34ad1987-3cd5-5d35-b0c7-175fff2c6311/scratchpad/designs/`:

- `round2/A.md` … `round2/E.md`: every designer's revised round-2 proposal. Read all five in full. Some contain changes made after round 2's initial filing; for example, A and B patched theirs for EBD access.
- `CRITIQUES_ROUND2.md`: every designer's round-2 critique table (§9), compiled in one file. Find every critique aimed at **you**.

The original brief (`BRIEF.md`) and the round-2 brief (`ROUND2.md`) still apply. The owner already has eBird EBD and Sampling Event Data access.

## Facts established in round 2, verified by at least one designer
- GBIF eBird records carry no checklist ID, start time or effort fields. They do carry observer ID, date and coordinates.
- The current CNN's positives are GBIF eBird detections (`sightings.py:20`). Scoring the CNN on EBD checklists outside its own validation blocks is therefore partly in-sample.
- About 61% of eBird grouse records in ME/NH/VT fall in April–June, and about 15% in September–November.
- The Vermont Green Mountain National Forest recorder release (doi:10.5066/P13EFLXX) has no site IDs or coordinates.

## Your task
1. **Respond to every critique aimed at you.** For each one, either:
   - **accept** it and show the fix in the design, or
   - **rebut** it with evidence (repository, web, or mathematics).

   Do not leave any critique without a response. Verify a critic's claim before accepting it.
2. **Re-examine your competitors' round-2 revisions.**
   - Where a revision fixed something you attacked, say so.
   - Where it introduced a new flaw, raise it, with a severity and a concrete failure scenario.
   - Adopt, with credit, any round-2 idea that beats yours.
3. **Make your final proposal as strong, honest and buildable as possible**, for one owner with one EC2 GPU. The goal is still to locate productive grouse-hunting coverts with maximum precision and accuracy. Keep what differentiates you, unless a competitor's version is better.
4. **Write the FINAL proposal** to `round3/<YOUR LETTER>.md`. It must be a complete standalone document with:
   - §0 **Changes from round 2**;
   - §1–§8 as in `BRIEF.md`;
   - §9 **Responses to critiques**: a table with columns critic, critique, severity, accept/rebut, and evidence or fix;
   - §10 **Final critique of competitors**: the round-2 versions only, with each item marked new or still-open.
5. Write the file early and refine it in place, so the work survives an interruption.
6. Do not edit any repository file. Mark unverified references as unverified. Your final reply should be a 10-line summary plus the file path.
