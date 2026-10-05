# Grouse model design competition: final report

*Compiled 2026-10-05 and updated after round 3.*

Five independent designer agents each received `docs/grouse_model_report.md`, the repository, and the owner's goal: **locate productive grouse-hunting areas in ME/NH/VT, with as much precision and accuracy as possible.** The competition ran in three rounds:

1. **Round 1.** Each designer wrote an initial design using a different brainstorming technique.
2. **Round 2.** All five read each other's designs, attacked them and borrowed from them, then filed revisions.
3. **Round 3.** All five read every revision and every critique, answered each critique aimed at them, and filed a final proposal.

This report compiles the three rounds and ends with a recommended merged plan. It is a design study: it changes no code or data. Any implementation goes through change control (CLAUDE.md §1).

All files are in `docs/design_competition/`:

| File | Contents |
|---|---|
| `BRIEF.md`, `ROUND2.md`, `ROUND3.md` | the briefs for each round |
| `CRITIQUES_ROUND2.md` | every round-2 critique, compiled |
| `round1/` | the five initial designs |
| `round2/` | the five revisions |
| `round3/` | **the five final proposals** |

---

## 1. Executive summary

1. **One shared core.** All five final proposals now share an identical core:
   - **Labels:** eBird complete checklists, with real non-detections.
   - **Likelihood:** a cloglog detection-given-effort likelihood over each checklist's walking footprint.
   - **Model:** LightGBM, fitted mostly on CPU in hours. No design needs a neural trunk.
   - **Effort term:** built only from covariates measured on the checklist, and dropped at prediction.
   - **Unit:** covert polygons ranked by expected October encounters or flushes per hour.
   - **Main metric:** observed/expected top-k lift on **fall** checklists, scored in the leak-free arena **HH**, the checklists inside the current CNN's own validation blocks.
2. **Convergence on tests, not just the model.** In round 3 the designs also converged on most of the falsification battery:

   | Test | Proposed by |
   |---|---|
   | Same-observer, same-day, first-visit case-crossover | D |
   | Label-permutation null | D |
   | Before/after-harvest panel test, as an event study | C |
   | Label-swap cross-play | B |
   | Season-aware detectability, with an injection test that can fail | E, C, D |
   | Owner's frozen blind scorecard | D |
   | Zero-fit covert map for this season | A |

   The designs now differ mainly in **which tests decide** and **how the map behaves where birders never walk**.
3. **The biggest round-3 move was A's.** CYM-H turns A's ecological model into an offset and fallback under a LightGBM residual. The residual has full authority where checklists exist and fades out where they don't. This is A's answer to a problem it says the others leave open: tree models extend the edge value into dense off-trail regeneration, which is exactly where hunters go. Its other three outstanding MAJOR issues were fixed, as detailed in §4.2.
4. **Verified facts that shape the plan** (§5):
   - About 61% of grouse records are spring drumming; only about 15% fall in September–November.
   - The CNN's positives are the same eBird detections, so it must be scored only on HH.
   - GBIF has no checklist or effort fields.
   - The Vermont recorder data has no coordinates.
   - AlphaEarth used GBIF occurrences as a training target. This is now partly verified, and every design treats it as manageable.
5. **Recommendation.** Adopt the shared core and the shared test battery (§7). Take **A's support-weighted ecological offset** as the off-support safeguard, and **E's failable injection test** to choose the detectability model. The decision rule is pre-registered: the checklist programme proceeds only if it beats the CNN on fall HH lift *and* on the case-crossover, outside the permutation band.
6. **Honest expectations.** No design claims to beat the legacy 0.77 AUC; all argue it is the wrong target. The designers' own probabilities:

   | Outcome | Probability |
   |---|---|
   | Label thesis passes | 0.55–0.65 |
   | Succession clock adds signal | about 0.45 |
   | AlphaEarth gate passes | 0.30–0.35 |
   | Measurable field gain in season 1 | about 0.35 |

   A single season can detect only differences of about 2× or more. A 1.2× gain over the CNN needs about 120 hours per arm.

---

## 2. Round 1: five designs, five techniques

| | Technique | Design | Distinctive round-1 idea |
|---|---|---|---|
| A | First principles + Five Whys | **CYM**, Covert Yield Model | flushes/h = 2·W·v·D. A shape-constrained model of about 40 parameters with literature priors (stand-age hump near 10 yr), plus a loop planner. |
| B | Analogical transfer from 11 fields | **CEM**, Checklist Encounter Model | Borrowed ad-click position bias, test-negative design, fisheries CPUE and injection–recovery. The ResNet runs fully convolutionally at 120 m. |
| C | Morphological analysis (Zwicky box) | **FLUSH-C** | AlphaEarth 10 m embeddings over multi-radius discs. Features sampled in Earth Engine at points. |
| D | Reverse brainstorm + pre-mortem | **COVERT** | 18 ways to fail hunters with a high AUC. Access classes, a Thompson-sampling recommender with a randomised arm, and a freshness audit. |
| E | SCAMPER + TRIZ | **FLUSH-E** | A 40-year succession clock (LCMS/Hansen/LandTrendr), aged forward to future seasons. |

Four of the five reached complete checklists plus a separate effort term without coordinating. A included them as one label stream among three.

## 3. Round 2: what changed

- **Effort covariates.** Every design dropped location-derived effort covariates. D also dropped its gradient-reversal adversary: all four critics showed it would erase real remoteness signal.
- **Production model.** Every design moved to a LightGBM production model, with the neural part optional.
- **Distinctive contributions that emerged:**
  - C: the leak-free arena HH and the before/after-harvest panel test.
  - B: label-swap cross-play.
  - D: case-crossover, the permutation null, heard/seen detection modes and the owner's scorecard.
  - E: the season-contrast term.
  - A: the frozen zero-fit prior map.
- The round-2 critiques are in `CRITIQUES_ROUND2.md`.

---

## 4. Round 3: the final proposals

### 4.1 Final designs at a glance

| Design | Final positioning | Unique contribution kept | Decisive test and kill rule | Critiques received → answered |
|---|---|---|---|---|
| **A: CYM-H** | Ecology where birders never walk, a learner where they do | A ~35-parameter ecological offset (stand-age hump, regeneration guild, understory under canopy, home-range kernels, physics-scaled flushes/h). A LightGBM residual is weighted by checklist support and fades out off-support. The age curve is estimated *within sites* from C's panel, then imposed. A support badge ("data-driven" vs "ecology-driven") and an exact additive "why" appear on each card. | Days 2–6 on HH: prior map vs stand-age heuristic vs CNN vs GBM. A full 2×2 injection cross scored on unvisited cells. A tie with the GBM on HH is the expected outcome. The off-support bet (+0.02–0.05 AUC) is untestable on checklists if fewer than 200 detections fall there; the scorecard and the field decide it instead. | All accepted and fixed: footprint normalised to a mean with a free-sign distance slope; CNN scored only on HH; injection made a 2×2; priors weakened with shrub wetland/old field added; blinding claim dropped. |
| **B: CEM-X** | Ship only what survives a cheater battery | Pre-registered battery B1–B6 with multiple-testing correction. Every gate is decided on **fall** checklists. HH membership is by checklist start point and training exclusion accounts for footprint size, so no footprint is lost. A pipelines × truths injection test on real EBD geometry, scored on unvisited cells. `road_dist` removed from the habitat model. 2025–26 cuts added (OPERA DIST, HF437). | G1, the label thesis on fall HH, decided by day 6. If it fails, the programme stops and H250 plus the access layer and field ledger remain. | 11 accepted. The control-species gate was replaced by D's permutation null. |
| **C: FLUSH-C** | A map that must predict what happens after a cut | Panel test upgraded to a **stacked event study**: pre-trend placebo leads, not-yet-treated controls, region × year effects, and the model refit without the panel sites plus a 2.5 km buffer. Gated AlphaEarth with infrastructure masking, evaluated only on 2024–25 checklists. Gains must not concentrate within 1 km of past GBIF grouse records. Three detectability models compete in an injection test. An **assumption ledger** pairs 7 identifying assumptions each with a test and a decision. | Days 3–5: cross-play plus HH plus case-crossover, with a kill rule. Week 2: panel test and fitted v1 (about 20 Oct). Week 3: embedding gate (P = 0.30). | 9 accepted, 1 partly. AlphaEarth leak accepted as MAJOR but rebutted as BLOCKING: the decisive test uses no embedding. |
| **D: COVERT-X** | Every gain confirmed by two independent routes | **Triangulation table:** each threat (preferential sampling, effort leakage, detectability) needs at least two tests that difference out different things. Kept: case-crossover as the primary metric; permutation null, now honestly scoped to the matched-pair score; heard/seen modes; owner scorecard. Training excludes everything within 2.5 km of the CNN's validation blocks. | Days 2–4: the programme is killed unless the matched-pair score beats both the CNN and the permutation band by more than 1 bootstrap SE. The status-quo map gets its own verdict from the same test. | 6 accepted, all against round-1 text. The grouped objective became optional stage 2 behind a gradient unit test. |
| **E: FLUSH-E** | The map reflects where grouse are in fall, not where drumming is audible | A **detectability triad**: season-contrast term, D's modes, and an unshrunk, separately fitted fall-only model. An **injection test that can fail** (planted spring tilt vs none) proves the agreement rule fires. Clock-only forecast mode with a 2020→2024 back-test. | Days 3–5 on HH: case-crossover concordance, fall TkL₅ and effort-stratified AUC must all beat the CNN and the permutation band. | 10 accepted, 0 rebutted. |

### 4.2 Status of the main critiques after round 3

| Critique | Raised by | Status |
|---|---|---|
| A's footprint sum grows with disc area, penalising remote big woods | C, then B, D, E | **Fixed** (A): normalised mean, free-sign distance slope |
| A's T1 scores the CNN in-sample | D, then B, C, E | **Fixed** (A): all comparisons on HH |
| A's injection test compares different truths | D, B, C | **Fixed** (A): 2×2 cross on unvisited cells |
| A's small structural model caps precision | B, D, E | **Fixed by architecture change** (CYM-H residual) |
| B's control-species gate cannot fail | D, C, A | **Fixed** (B): replaced by permutation null. A still lists it as open, since A's critique targeted the round-2 text. |
| Agreement tests compare a model with a heavily shrunk version of itself, so agreement is near-certain (breaks PA-0021(a)) | **E (new MAJOR, against B, C, D)** | **Open.** E's unshrunk fall model plus injection test is the only answer offered. Adopted in §7. |
| None of the designs changes *prediction* off the birders' map; trees extend the edge value | **A (new MAJOR, against all four)** | **Open** for B, C, D and E. Answered only by CYM-H's support-weighted offset. Adopted in §7. |
| C's panel test is fitted on the treated sites | B, A | **Fixed** (C): refit without panel sites plus buffer |
| C's panel test needs a forest→forest filter, or development near hotspots reads as young stands | E (new) | **Open.** Cheap to add; adopted in §7. |
| C's panel can be confounded by birders changing routes after a cut | D (new MEDIUM) | **Open.** Mitigated by first-visit and footprint-change checks. |
| C's AlphaEarth pretraining leak | E | **Accepted as MAJOR, not BLOCKING** (C, B). Gate evaluates only 2024–25 checklists. |
| D's permutation null cannot see infrastructure leakage within a stratum | C (new MAJOR) | **Open.** Covered in §7 by C's infrastructure probe. |
| D's mode labels are missing not at random, so the split may just restate season | B (new MEDIUM) | **Open.** B requires at least 500 coded detections per mode. |
| D's kill margin of 1 bootstrap SE (about 16% false pass per test) | B (new MEDIUM) | **Open.** §7 uses a multiplicity-corrected margin. |
| D's same-day pairs are mostly spring roadside contrasts | C (new MEDIUM) | **Open.** §7 decides on fall pairs only. |
| E's season contrast assumes the same habitat use and density in spring and fall, but fall density is about 2× and dispersal shifts it | B (MAJOR), A and C (MEDIUM) | **Open.** This is why §7 keeps the unshrunk fall-only model as the arbiter rather than trusting the contrast term alone. |
| E's fall-only kill gate may be underpowered and kill a working programme | A (new MEDIUM) | **Open.** §7 requires a pre-run power check (injection minimum detectable effect) before the gate is binding. |

---

## 5. Facts verified during the competition

| Fact | Verified by | Consequence |
|---|---|---|
| GBIF eBird records have **no checklist ID, start time or effort**. They do have observer ID, date and coordinates. | C, A, B, D (GBIF API) | Only the EBD with Sampling Event Data supports the model. The owner has it. |
| **The CNN's positives are GBIF eBird detections** (`sightings.py:20`, `EBIRD_DATASET_KEY`) | D; confirmed in the repository | The CNN may be scored only on HH (inside its validation blocks, 2.5 km buffer). `regions.py:55,58`: `VAL_FRACTION` 0.2, `SPLIT_SEED` 42 (A). |
| **About 61% of grouse records are April–June, about 15% September–November** (about 43k, 2016–24). There are 5,774 fall records for 2020–24. | E, B, D (GBIF counts) | Every decision is made on fall checklists, and detectability must be season-aware. |
| The **Vermont GMNF recorder release has no site coordinates** (doi:10.5066/P13EFLXX) | D, C | Usable only after a data request. |
| **AlphaEarth Foundations (arXiv:2507.22291) uses GBIF species occurrence records as a training target** (text alignment), not as an input | B, C; compiler confirmed against the paper's HTML | The leak risk is real but indirect. Evaluate embeddings only on post-training-period checklists. B and C report 2017–2023, ≤240 m uncertainty and ≤1,000 per taxon; the compiler **could not verify** those filter details. |
| NH flush-rate pages return 403 to automated fetch; ME and VT sub-state flush data are unconfirmed | all | Flush data are used for absolute scale and year checks only, pending agency requests. |
| eBird species-comments and breeding/behaviour-code columns | **Unverified** against the owner's file | Needed for D's mode split. If absent, use behaviour codes only. |

---

## 6. Assessment

By round 3 the designs differ less in *what to fit* than in *what each one alone protects against*. Ranked on contributions that survived three rounds of attack:

1. **C (FLUSH-C)** supplied the two pieces every design now depends on: the leak-free HH arena, and the only within-site test, now a proper event study refit out-of-sample. Its assumption ledger is the clearest map of what could still go wrong. Its embedding block is new information, gated, with leakage handled.
2. **D (COVERT-X)** supplied most of the shared falsification battery (case-crossover, permutation null, modes, scorecard). Its triangulation rule, that each threat needs two independent tests, is the right governing principle. It has three open MEDIUM issues and one open MAJOR.
3. **A (CYM-H)** made the largest final-round improvement. It fixed all three outstanding MAJOR issues and raised the one critique nobody else answers: off-support extrapolation. Hunters care about off-trail young cover, so this matters directly for the product. Its main claim, a +0.02–0.05 off-support gain, may be untestable on checklists and rests on the field and the scorecard.
4. **E (FLUSH-E)** contributed the seasonal fact and the only agreement test designed to be able to fail, a direct application of the repository's own PA-0021(a). Its season-contrast term rests on an assumption three critics dispute, so in the merged plan the fall-only model, not the contrast term, is the arbiter.
5. **B (CEM-X)** has the most disciplined decision procedure: fall-only gates, multiple-testing correction, and fold geometry that keeps every footprint. Most of its unique machinery has now been adopted by the others, so it differentiates least.

This ranking is the compiler's judgement, not a vote by the designers.

---

## 7. Recommended merged plan

Each phase is its own change request under CLAUDE.md §1. Acceptance and test scripts are committed first (CR-0011 A3), and nothing writes to `data/` before approval. **CR-0035 finishes first**; its evaluation is the legacy baseline.

**Day 0–1: freeze evidence before fitting**
1. **Owner scorecard (D).** Blind-rate at least 30 past coverts. Commit before seeing any map.
2. **Zero-fit covert layer (A/B/E's "H250").** Share of 5–20-year cuts within 250 m, plus access classes from PAD-US and state lands. Ship it for the rest of the 2026 season with one randomised covert in five, so hunts become held-out labels.
3. **Checklist years** (corrected after the vote review; R1, R6 and R7 independently found this). The binding limit is LANDFIRE. The structure layers (`evt`, `evh`, `evc`, `sclass`, `fdist`, `ch`, `cc`) have **no vintage before 2022** (`grouse_data.py:373-375`), and `YEAR_MATCH_TOLERANCE` is 2 (`grouse_data.py:174`). That is why the pipeline floor is `YEAR_MIN = 2020` (`regions.py:73`). `train.filter_by_year_gap` refuses, rather than drops, rows outside the tolerance. Other coverage limits:
   - TCC ends in 2023, so the 2026 prediction year is 3 years past it;
   - TreeMap vintages are 2016, 2020 and 2022;
   - `mch_*` is one static epoch.

   Consequences:
   - **The habitat model trains and is scored on 2020+ checklists only**, the same years as the legacy baseline.
   - **Panel test pre-cut windows before 2020 have no legacy-layer features.** Panel checks therefore test the **clock (disturbance-age) component only**. Its inputs are Hansen and LCMS (back to 2000 and 1985) plus location fixed effects. This is what A's T5 within-site age curve does.
   - **Checklists from 2010–2019 are used only for** clock-only panel checks, pre-trend placebo leads, and out-of-fold observer-skill indices.
   - **Using pre-2020 checklists in the full habitat model** would need older LANDFIRE vintages back-filled under a separate CR.
   - **The ingest CR's acceptance check** asserts that every row entering the habitat model has every feature within tolerance, and fails the run otherwise.
4. **EBD ingest.** One row per complete checklist, filtered to best practice. Record counts by state, season, protocol and detection mode, and check the column header.

**Days 2–6: decisive tests, pre-registered, multiplicity-corrected, on fall checklists in HH**
5. **Injection–recovery.** Pipelines × truths on real EBD geometry, scored on unvisited cells (B). Include a planted spring tilt and a null (E). This sets the minimum detectable effect, so a gate is binding only if it is powered (A's concern). It also chooses among the three detectability models (C's radius, D's modes, E's contrast). The arbiter is the unshrunk fall-only model.
6. **Cross-play (B).** The same GBM trained on legacy vs checklist labels, scored at home, away and on independent data. The CNN is recalibrated on the same checklists.
7. **Kill rule.** The checklist programme continues only if all of these hold:
   - fall TkL₅ beats the recalibrated CNN by the pre-registered margin;
   - **and** the fall same-observer, first-visit case-crossover is positive (D);
   - **and** both clear the within-stratum label-permutation band (D);
   - **and** the infrastructure probe passes (C).

   The current map gets its own verdict from the same tests.

**Weeks 2–3: build what survived**

8. **Production model.** A LightGBM cloglog footprint model:
   - footprint as a normalised mean with a free-sign distance slope (A, fixed after C's critique);
   - event-only effort GAM (B);
   - the winning detectability model from step 5.

   Add **A's support-weighted ecological offset**: the stand-age curve estimated within sites from the panel, with the residual fading off-support. Each covert card carries a "data-driven / ecology-driven" badge.
9. **Panel event study (C).** Use a forest→forest land-use filter (E) and first-visit plus footprint-change checks (D). This validates the habitat function and supplies A's age curve.
10. **Feature gates.** Each block is kept only if it passes the permutation null and improves fall TkL on HH:
   - succession clock;
   - AlphaEarth with infrastructure masking, evaluated only on 2024–25 checklists from a model trained on data up to 2023, with no gain concentrated near past GBIF grouse records (C).
11. **v1 covert product (about 19–20 October).** Each card shows:
    - flushes/h with interval;
    - support badge;
    - access class and walk-in distance;
    - peak window and freshness;
    - artefact badges (near-hotspot, season/mode disagreement, extrapolation).

    The daily list has 4 Thompson-sampled coverts plus 1 randomised. The owner's hunts enter the likelihood as hunt-protocol checklists.

**Later:**
- agency requests: ME/VT flush data, NH tables, GMNF recorder coordinates;
- leaf-off lidar understory metrics;
- a neural model only if it beats the GBM by at least 0.01 on HH;
- a multi-season field comparison sized for 1.2× (about 120 h per arm).

---

## 8. Open items
- **Off-support extrapolation:** whether A's offset helps can only be judged by the field and the scorecard if fewer than 200 HH detections fall off-support.
- **Seasonal assumptions:** spring/fall density and habitat-use differences (about 2× in fall, plus dispersal). The fall-only model is the arbiter until resolved.
- **Pre-2020 checklists:** LANDFIRE has nothing before 2022 and the tolerance is 2 years, so these checklists enter only the clock-only panel checks and the observer-skill indices (§7 step 3). Extending the habitat model earlier needs back-filled LANDFIRE vintages under a separate CR.
- **Panel test power:** unknown until treated eBird locations near harvests are counted.
- **AlphaEarth filters:** the GBIF year range and filter details are unverified by the compiler.
- **Agency data:** NH flush tables (403 to automated fetch), ME/VT programmes, GMNF coordinates.
- **Citations:** references marked **unverified** by their authors (DOIs from memory, PDFs seen only via search summaries).
