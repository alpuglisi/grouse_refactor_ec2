# Round 2: revision brief

All five round-1 designs are in `/tmp/claude-0/-home-user-grouse-refactor-ec2/34ad1987-3cd5-5d35-b0c7-175fff2c6311/scratchpad/designs/round1/`:

- A.md: Covert Yield Model (CYM)
- B.md: Checklist Encounter Model (CEM)
- C.md: FLUSH (Footprint-pooled Learning of Unit-effort Standardised Habitat). Call it **FLUSH-C**.
- D.md: COVERT
- E.md: FLUSH (succession clock, per-pixel MLP). Call it **FLUSH-E**.

## Observed convergence
Four or five of the designs converge on the same core. Because the core is now shared, it no longer distinguishes any design:

- eBird complete checklists with non-detections;
- a separate effort/detection term that is removed at prediction;
- footprint kernels over each checklist's walk;
- NH flush-rate anchoring;
- covert polygons as the output;
- top-k lift as the metric.

Designer C reports that it confirmed via the GBIF API that the current GBIF eBird records carry no checklist ID or effort fields. Verify that claim yourself before relying on it.

## Your task
1. Read all four competitor designs in full, plus your own.
2. Attack each competitor. For each one, give its strongest flaw with a severity: BLOCKING (it would give a wrong result or cannot be built, with a concrete failure scenario), MAJOR, MEDIUM or LOW. Verify claims against the repository and the web where you can. Do not attack strawmen.
3. Steal shamelessly, with credit: adopt any competitor idea that is better than yours, and name the source.
4. Then differentiate. Since the core is shared, win on what is not shared. That includes:
   - which test comes first and whether it truly falsifies;
   - robustness to preferential sampling and to detectability varying with habitat;
   - what can be done **before** eBird EBD access arrives;
   - feasibility for one owner with one EC2 GPU;
   - the hunter end product;
   - the honesty of the gain estimates.
5. Write your FINAL proposal to `/tmp/claude-0/-home-user-grouse-refactor-ec2/34ad1987-3cd5-5d35-b0c7-175fff2c6311/scratchpad/designs/round2/<YOUR LETTER>.md`. It is a complete standalone document with the same 8 sections as the round-1 brief, plus two more:
   - §0 **Changes from round 1**: what you adopted and from whom, what you dropped, and why;
   - §9 **Critique of competitors**: a table of design, flaw, severity and evidence.
6. Keep the brainstorming record short, and add any new technique you used this round.
7. Constraints are unchanged:
   - do not edit any repository file;
   - mark unverified references as unverified;
   - make your final reply a 10-line summary plus the file path.
