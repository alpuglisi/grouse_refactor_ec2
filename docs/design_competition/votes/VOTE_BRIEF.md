# Review and vote brief

## Goal (the owner's)
Predict Ruffed Grouse habitat suitability so that **productive grouse-hunting areas (coverts) can be located** in ME, NH and VT, with **as much precision and accuracy as possible**. The owner works alone, on one EC2 GPU host, and already has eBird EBD + Sampling Event Data access.

## Candidates
Five final proposals, written after three adversarial rounds:
- A, CYM-H: `/home/user/grouse_refactor_ec2/docs/design_competition/round3/A.md`
- B, CEM-X: `/home/user/grouse_refactor_ec2/docs/design_competition/round3/B.md`
- C, FLUSH-C: `/home/user/grouse_refactor_ec2/docs/design_competition/round3/C.md`
- D, COVERT-X: `/home/user/grouse_refactor_ec2/docs/design_competition/round3/D.md`
- E, FLUSH-E: `/home/user/grouse_refactor_ec2/docs/design_competition/round3/E.md`

## Background
- `/home/user/grouse_refactor_ec2/docs/grouse_model_report.md`: habitat, data representation, current model maths, and an interpretation.
- The repository at `/home/user/grouse_refactor_ec2`, especially `regions.py`, `grouse_data.py`, `sightings.py`, `prepare_training_data.py`, `train.py`, `diagnose_gbm_baseline.py` and `ARCHITECTURE.md`.

Do NOT read `docs/grouse_design_competition_report.md`. It contains the compiler's own ranking, and your vote must be independent.

## Facts you must check designs against
A design that quietly relies on something that does not exist is a defect. A lesson already learned the hard way: the earlier review missed that rasters on disk only cover **2016–2025**. The current training floor is `YEAR_MIN = 2020` (`regions.py:73`). TreeMap vintages are 2016, 2020 and 2022, and TCC runs 2016–2023. So any habitat feature for a pre-2016 checklist does not exist unless the design builds it.

Verify every data, year, file and API claim you rely on, against the repo or the web.

## Your job
1. Read all five proposals **in full**, through your assigned lens (in your prompt). Also judge them on general merit.
2. Score each design 1–10 on each criterion below:
   - (a) Expected gain toward the owner's goal: hunter-relevant precision and accuracy.
   - (b) Soundness: the statistics, identification, and whether its tests can actually fail.
   - (c) Feasibility for one owner on one EC2 host, given the data that really exists.
   - (d) Honesty and calibration of its claims.
   - (e) Your lens-specific criterion.
3. Find each design's single most serious **unaddressed** flaw, especially anything all five rounds of critique missed. Give a severity: BLOCKING, MAJOR, MEDIUM or LOW.
4. **Vote.** Give a full ranking from 1st to 5th, with one paragraph of justification for your 1st choice and one for your last.
5. Optionally, name up to two elements from other designs that the winner should adopt.

## Output
- Write your review to `/tmp/claude-0/-home-user-grouse-refactor-ec2/34ad1987-3cd5-5d35-b0c7-175fff2c6311/scratchpad/votes/<YOUR ID>.md`.
- Your final reply MUST start with exactly one line: `BALLOT: <1st>,<2nd>,<3rd>,<4th>,<5th>` (letters only, e.g. `BALLOT: C,D,A,E,B`).
- Then give a score table (designs × criteria a–e), then ≤ 8 lines of rationale, including any newly found flaw.
- Do not edit any repository file.
