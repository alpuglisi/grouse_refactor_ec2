# Middle-ground brief: combining E (FLUSH-E) and B (CEM-X)

## Background
Five designs competed over three adversarial rounds. Seven independent reviewers then voted:

| Design | Points |
|---|---|
| E (FLUSH-E) | 31 (Condorcet winner) |
| B (CEM-X) | 25 |
| D | 19 |
| C | 18 |
| A | 12 |

The reviewers also found 13 flaws (V1–V13) that every design round had missed.

Read these in full, in this order:
1. `/home/user/grouse_refactor_ec2/docs/design_competition/VOTE_REPORT.md`: the tally, why the reviewers voted as they did, flaws V1–V13 and recommended adoptions.
2. `/home/user/grouse_refactor_ec2/docs/design_competition/round3/E.md` and `round3/B.md`: the two finalists.
3. The seven reviews in `/home/user/grouse_refactor_ec2/docs/design_competition/votes/R1.md`–`R7.md`.
4. The other finalists, `round3/A.md`, `C.md` and `D.md`, as needed for adopted elements.
5. Repository code as needed, for example `regions.py`, `grouse_data.py`, `prepare_training_data.py`, `diagnose_gbm_baseline.py`, `CLAUDE.md` and `docs/quality/PREVENTIVE_ACTIONS.md`.

## The owner's goal
Locate productive Ruffed Grouse hunting coverts in ME, NH and VT, with the most precision and accuracy achievable.

The owner's constraints:
- one person, with one EC2 GPU host;
- eBird EBD + Sampling Event Data access is already in hand;
- a strict QMS applies (CLAUDE.md);
- the CR-0035 data repair is still in progress;
- the 2026 hunting season is under way.

## Hard facts (verified)
- **V1, year coverage.** LANDFIRE has no layer before 2022 and `YEAR_MATCH_TOLERANCE` = 2, so the habitat model can use **2020+ checklists only**. TCC ends in 2023, `mch_*` is static, and TreeMap vintages are 2016, 2020 and 2022.
- **V2, buffer cost.** A 2.5 km buffer around HH keeps only about 24–31% of non-HH checklists.
- **V3, panel test scope.** The panel test can check only the disturbance-clock component.
- **V4, B's objective.** B's grouped cloglog Hessian is negative on detection rows.
- **V6, HH construction.** HH must be built from `regions.block_split`, not from `block_assignments.csv` alone.
- **V7, fall data is thin.** There are about 4,000 Oct–Nov grouse records across the three states for 2016–25; reviewer-reported, not re-checked. That leaves about 100 detections in the held-out fall top-5%.

## The tension to resolve
- **E** is the light, buildable, high-expected-value design. Its spring/fall agreement test can actually fail, and it ships a usable product fast. Its kill rules are looser, and it has some feature-construction and back-test flaws (V10, V11, V13).
- **B** is the rigorous, fail-closed design. Every gate is decided on fall checklists in HH, with simulation-calibrated margins, Holm correction, cross-play and a cheater battery, and it models at pixel scale. Reviewers fear it is underpowered on thin fall data (V7) and could stop a working programme. Its custom objective is broken (V4).

Find the **middle ground**: one design that keeps the strengths of each, drops the weaknesses, and fixes every applicable item in V1–V13.

## Your task
1. **Write a complete hybrid proposal.** Your assigned emphasis, given in your prompt, is the part you must work out most deeply, but the proposal must still be whole.
2. **Account for every element.** For each element, say whether it comes from E, from B, is a compromise between them, or is new, and give the reason.
3. **Resolve the power-vs-rigour conflict explicitly and quantitatively.** For example: which gates are binding versus advisory; what the minimum detectable effect is, given about 100 fall top-5% detections; which errors you accept; and what happens when a gate is inconclusive rather than failed.
4. **Address V1–V13 one by one** in a table with the columns *flaw*, *how the hybrid handles it* and *residual risk*.
5. **Give a phased plan** for one owner, with honest effort and dates. CR-0035 finishes first. Split the work into independently landable change requests, per CLAUDE.md (CR-0011 A5), and say which acceptance checks are written first (CR-0011 A3).
6. **State what the hybrid gives up** relative to pure E and to pure B, and why that is acceptable.
7. **Verify every data, year, file and API claim** against the repository or the web. The project has already been burned twice by unchecked year-coverage claims. Mark anything you could not verify as **unverified**.

## Output
- Write your proposal to `/tmp/claude-0/-home-user-grouse-refactor-ec2/34ad1987-3cd5-5d35-b0c7-175fff2c6311/scratchpad/hybrid/<YOUR ID>.md`.
- Your final reply is a summary of at most 12 lines plus the file path. The first line must be: `HYBRID: <one-line name and thesis>`.
- Do not edit any repository file.
