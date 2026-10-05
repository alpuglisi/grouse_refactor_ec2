# Design competition: independent review and vote

*2026-10-05.*

Seven independent reviewers each read the five round-3 final proposals (`round3/A.md`–`E.md`) in full. Each reviewed through an assigned lens, scored every design on five criteria, named each design's most serious unaddressed flaw, and ranked all five. The reviewers were told not to read the compiler's comparison report, so the votes would stay independent. Each was required to check data, year, file and API claims against the repository or the web. The brief is in `votes/VOTE_BRIEF.md` and the full reviews are in `votes/R1.md`–`R7.md`.

## 1. Result

**Winner: E (FLUSH-E).** It wins on every count:
- most first-place votes (3);
- highest points (31 of a possible 35);
- the **Condorcet winner**: it beats every other design head-to-head (B 5–2, D 6–1, A 6–1, C 7–0).

E is ranked first or second by all seven reviewers.

**Final order:** E (31) › B (25) › D (19) › C (18) › A (12).

### 1.1 Ballots

| Reviewer | Lens | 1st | 2nd | 3rd | 4th | 5th |
|---|---|---|---|---|---|---|
| R1 | Hunter / grouse ecologist | E | B | D | A | C |
| R2 | Spatial statistician / causal inference | B | E | C | D | A |
| R3 | ML engineer (GBM, geospatial) | B | E | D | C | A |
| R4 | Feasibility and data-reality auditor | D | E | B | C | A |
| R5 | Red-team skeptic (shared assumptions) | A | E | C | B | D |
| R6 | QMS / process compliance | E | B | C | D | A |
| R7 | Decision analyst / product owner | E | C | D | B | A |

### 1.2 Tally

Points are Borda points: 5 for a 1st-place ranking, down to 1 for 5th.

| Design | Points | 1st-place votes | Head-to-head wins (out of 4) |
|---|---|---|---|
| **E: FLUSH-E** | **31** | **3** | **4** |
| B: CEM-X | 25 | 2 | 3 (loses only to E) |
| D: COVERT-X | 19 | 1 | 1 |
| C: FLUSH-C | 18 | 0 | 2 |
| A: CYM-H | 12 | 1 | 0 |

Head-to-head matrix (row beats column on *n* of 7 ballots):

| | A | B | C | D | E |
|---|---|---|---|---|---|
| A | – | 1 | 2 | 1 | 1 |
| B | 6 | – | 5 | 5 | 2 |
| C | 5 | 2 | – | 4 | 0 |
| D | 6 | 2 | 3 | – | 1 |
| E | 6 | 5 | 7 | 6 | – |

### 1.3 Why the reviewers voted as they did
- **E.** Reviewers cited:
  - the only spring/fall agreement test that can actually fail: an independently fitted, unshrunk fall-only model, calibrated by injection;
  - the lightest build;
  - the best expected value per unit of effort;
  - the closest fit to the repository's own rule that a gate must be able to fail (PA-0021(a));
  - a usable product.
- **B.** R2 and R3 ranked it first for its rigour. Every decision is made on fall checklists in HH, its margins are calibrated by simulation, and its gate errors lean toward a wrong stop rather than a wrong ship. R3 also valued its pixel-scale habitat model with real leakage controls. Its weakness: gating every decision on fall data with a Holm correction is likely underpowered, so it may stop a programme that works (R4, R5, R7).
- **A.** It was polarising. R5 ranked it first: it is the only design that falls back on ecology where birders never walk, which is the hunter's target. Five reviewers ranked it last, on its 5.5 km buffer (about 2% of data left), its age curve that cannot be identified, tuning on its own decision set, and the heaviest build.
- **D** won R4's vote on deliverability and honest effort estimates. Several reviewers found that its mode-divergence check cannot fail.
- **C** received no first-place vote. Reviewers agreed its headline panel test cannot run as described (see §2).

---

## 2. Flaws found in the vote that all three design rounds missed

These were found independently by two or more reviewers, or verified by the compiler, unless noted otherwise. They apply to the winner as much as to the others.

| # | Flaw | Designs | Severity | Found by | Verified | Required fix |
|---|---|---|---|---|---|---|
| V1 | **Year coverage.** LANDFIRE structure layers have no vintage before 2022, and `YEAR_MATCH_TOLERANCE` is 2 (`grouse_data.py:174, 373-375`). Every design fits 2016–2025 checklists "at their own year" with the legacy block, so 2016–2019 rows would read later, post-cut landscapes. TCC ends in 2023. `mch_*` is one static epoch, roughly 2018–20. | all | MAJOR | R1, R4, R5, R6, R7 | compiler (code) | The habitat model uses **2020+ checklists only**. The ingest CR asserts every feature is within tolerance. Already corrected in `docs/grouse_design_competition_report.md` §7. |
| V2 | **Training buffer removes most data.** HH is a random 20% of 3 km blocks. Excluding checklists within 2.5 km keeps only about 24–31% of non-HH checklists. A 2.9 km buffer keeps about 22%. A's 5.5 km buffer keeps about 2%. No critique estimated this. | all (A blocking) | MAJOR | R2, R3, R4 (three independent simulations) | compiler (geometry: 1 − 0.8⁸ ≈ 83% of a block's interior is within 2.5 km of an HH neighbour) | Score HH **out-of-fold within 25 km super-blocks**, buffering only at super-block edges (R2). Alternatively, mask the stencil points that overlap HH rather than dropping whole checklists (R4). |
| V3 | **Panel test cannot test the habitat model.** Pre-cut windows before 2020 have no legacy features (V1), and checklists start in 2010. Usable cuts run roughly 2014–2019, and post-cut ages reach only about 5–11 years. A's T5, built from 2016–2025 data, sees at most about 8 years, so it cannot locate the ~10-year peak. | B, C, D, E; A's T5 | MAJOR | R2, R3, R4, R5, R7 | compiler (follows from V1) | Restate the panel as a check of the **disturbance-clock component only**, using Hansen/LCMS, plus location fixed effects. Report the age range it actually identifies. |
| V4 | **B's grouped cloglog Hessian is negative.** For a detection row, ∂²L/∂f_m² = λ_m/(e^Λ−1)·[λ_m e^Λ/(e^Λ−1) − 1]. When Λ is small this is ≈ λ_m/Λ − 1 < 0 whenever the footprint spans more than one stencil point. LightGBM leaf values then flip sign or blow up. B's unit test checks gradients only. | B (and any grouped objective, including D's optional stage 2) | MAJOR | R3 | compiler (derivation) | Clamp to the H·λ² term (a Gauss–Newton approximation) and add a Hessian check, or use the one-row stencil-mean objective. |
| V5 | **Earth Engine export route.** All five export new layers "on the template lattice with explicit crsTransform". That makes Earth Engine resample, the route CR-0034 removed after BUG-0094. | all | MAJOR | R6 | not yet verified | Fetch on the source lattice, then warp locally with an exact warp (PA-0049(a)). Pass the registration gate before use. |
| V6 | **HH must come from `regions.block_split`.** `block_assignments.csv` lists only blocks with 2020+ grouse records, so building HH from it alone selects the arena on the outcome. | all (unspecified) | MAJOR | R3 | compiler (code): `prepare_training_data.assign_spatial_blocks` lists only blocks that hold records; `regions.block_split` (`regions.py:270`) assigns unlisted blocks by an md5 hash of `SPLIT_SEED` | State the source in the ingest CR and test it. |
| V7 | **Fall data is thin.** There are about 4,000 October–November grouse records across the three states for 2016–25 (VT extrapolated). The held-out fall top-5% then holds about 100 detections, and fall same-day pairs in HH number in the tens to low hundreds. | all, worst for B | MAJOR (B) / MEDIUM | R4, R5, R7 | GBIF counts reported by R5; not re-checked | Compute the minimum detectable effect before any gate becomes binding (injection). Prefer gates that fail toward the H250 fallback. |
| V8 | **Permutation band from 20 refits.** PA-0021(c) requires at least 50 draws. | B, C, D, E | MAJOR (rule) | R6 | — | Use ≥ 50 refits. |
| V9 | **Data sources overstated.** Reported by R4 from web checks: <br>– OPERA DIST-ALERT is not in the Earth Engine catalog (only DIST-ANN 2023–24 is), so it needs an LP DAAC path through the registration gates. <br>– AlphaEarth in Earth Engine covers 2017–2024 at about 90 GB/yr at 10 m, which breaks C's 2024–25 gate and the storage budget. <br>– LCMS v2024-10 has been superseded by v2025-11. <br>– HF437 covers Maine only, 1986–2019, so a fused clock is biased by state (R6). | A, B, C, D, E (varies) | MAJOR / MEDIUM | R4, R6 | reviewer web checks; not re-checked by compiler | Re-scope fresh-cut and embedding plans. Use per-state clocks or drop HF437 from the fused clock. |
| V10 | **E's forecast back-test leaks.** "Freeze features at 2020" reads 2022 rasters that already show later cuts, so the test leans toward passing. | E | MAJOR | R4 | follows from V1 | Back-test using the clock only, or with vintages strictly before the forecast origin. |
| V11 | **Feature construction errors.** <br>– C and D read features at the disc radius nearest ρ+L/2, so one column mixes 60 m and 2,400 m discs. <br>– D and E average categorical codes across stencil points. <br>– E trains on footprint means but predicts single pixels, which is off-support for the dense young cover hunters want. | C, D, E | MEDIUM | R3 | — | Use fixed multi-radius columns. Use class fractions, not averaged codes. Predict at the same footprint scale as training. |
| V12 | **Top-k lift is defined only where birders walk.** It penalises maps that correctly rank off-trail regeneration highly. | all but A | MEDIUM | R5 | — | Report A's extrapolation subset (HH-X) with tuning done outside HH, and add a support badge to the product. |
| V13 | **Kill margins.** A 1 SE one-sided margin gives about a 16% false pass per comparison (D, E). The either-test-passes kill rules in C and E are loose. | C, D, E | MEDIUM / LOW | R2, R5 | — | Use a pre-registered, simulation-calibrated margin with multiplicity correction. |

---

## 3. What the winner should adopt

The reviewers' recommended adoptions, grouped by how many named each:

1. **The design already has the right core.** Six reviewers named E's independently fitted, unshrunk fall-only model as the element any winner should keep or adopt.
2. **Ecological fallback where birders don't walk** (R4, R7; R3 names A's HH-X extrapolation subset; R1 names A's zero-fit ecological v0 map). Take A's support-weighted ecological residual and its "data-driven / ecology-driven" badge. Use a geographic support measure, not covariate space (R1): a logging-road checklist looks identical in covariates to the off-trail cut beside it.
3. **Stacked event-study panel test** (R5, R7; R2 also names C's pre-trend checks). Take C's design, restated as a clock-only check (V3).
4. **B's fall-decided gate battery** (R1, R6). Use a calibrated margin and at least 50 permutation refits, and compute the minimum detectable effect first, so the battery cannot kill a working programme by being underpowered (V7).

## 4. Status
- V1 is already fixed in `docs/grouse_design_competition_report.md` §7 step 3.
- V2–V13 must be written into the first change requests (EBD ingest and the decisive-test harness) as explicit acceptance checks before any fitting.
- V5 and V9 are reviewer findings not yet re-verified by the compiler. Verify each before relying on it.
