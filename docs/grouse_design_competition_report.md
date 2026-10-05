# Grouse model design competition: final report

*Compiled 2026-10-05. Five independent designer agents each received `docs/grouse_model_report.md`, the repository and the owner's goal: **locate productive grouse-hunting areas in ME/NH/VT, with as much precision and accuracy as possible.** Each wrote a round-1 design using a different brainstorming technique. All five then read each other's designs, attacked them, borrowed from them and filed a round-2 final proposal. This report compiles and compares those finals and ends with a recommended merged plan. It is a design study: it changes no code or data, and any implementation goes through change control (CLAUDE.md §1).*

The full documents are in `docs/design_competition/`:

| | |
|---|---|
| Briefs | `BRIEF.md`, `ROUND2.md` |
| Round 1 | `round1/A.md` … `round1/E.md` |
| Round 2 finals | `round2/A.md` … `round2/E.md` |

---

## 1. Executive summary

1. **All five designs independently reached the same core.** Replace today's grouse-record vs other-species-record contrast with eBird complete checklists, which carry real non-detections and measured effort. Fit them as a detection-given-effort hazard over each checklist's walking footprint. Use an effort term that is dropped at prediction time. Rank covert polygons by expected October encounters or flushes per hour, judged by top-k lift. Five different methods converging on this is the strongest signal in the exercise. It also matches `grouse_model_report.md` §5.4: the 0.77 AUC ceiling is in the labels, and new labels are the one lever not yet pulled.
2. **The owner already has eBird Basic Dataset (EBD) access, so the decisive test can run in week 1.** The designs differ mainly on which tests can actually falsify the idea. They agree the model should be a **LightGBM cloglog** encounter model run mostly on CPU. A neural model is optional, and every designer gives it about a 25% prior chance of paying off.
3. **The competition surfaced several verified facts that change the plan** (§4):
   - **Wrong season.** About 61% of eBird grouse records are April–June drumming. Only about 15% fall in September–November, the hunting season.
   - **In-sample leak.** Today's CNN was trained on GBIF eBird detections, so scoring it on EBD checklists is partly in-sample.
   - **Unusable without a request.** The Vermont Green Mountain NF recorder data has no site coordinates.
   - **GBIF can't substitute for the EBD.** GBIF eBird records have no checklist ID or effort fields.
4. **No single design wins outright. The best plan is a merge** (§6). It keeps the shared core and the strongest *unique* test from each designer:

   | From | Contribution |
   |---|---|
   | C | Leak-free arena and before/after-harvest panel test |
   | B | Label-swap cross-play |
   | D | Same-observer case-crossover, label-permutation control, heard-vs-seen detection modes, and the owner's blind scorecard |
   | E | Season-contrast term and a fall-only gate |
   | A | A frozen expert prior map you can field-test this October |

5. **Honest expectations.** No designer claims to beat 0.77 on the legacy AUC metric; they argue that metric is the wrong target. Each designer gave prior probabilities that its own core gates pass:
   - the label thesis passes: about 0.6;
   - the succession clock helps: about 0.45;
   - AlphaEarth embeddings help: about 0.35–0.40;
   - a measurable field gain in season 1: about 0.35;
   - a neural model beats the GBM: about 0.25.

   A field gain of 1.2× over today's map needs about 120 hunting hours per arm to detect. That means several seasons, or several hunters.

---

## 2. Round 1: five designs, five techniques

| | Technique | Design | Distinctive round-1 idea |
|---|---|---|---|
| A | First principles + Five Whys | **CYM**, Covert Yield Model | flushes/h = 2·W·v·D. Uses a shape-constrained model of about 40 parameters with literature priors, e.g. a stand-age hump peaking near 10 years. Includes a loop planner. |
| B | Analogical transfer from 11 fields | **CEM**, Checklist Encounter Model | Borrows ad-click position bias, the test-negative design, fisheries CPUE and injection–recovery. A ResNet run fully convolutionally at 120 m. |
| C | Morphological analysis (Zwicky box) | **FLUSH-C** | AlphaEarth 10 m embeddings averaged over multi-radius discs, with features sampled in Earth Engine at point coordinates. LightGBM plus a small neural net. |
| D | Reverse brainstorm + pre-mortem | **COVERT** | 18 ways to fail hunters while keeping a high AUC, turned into 12 requirements. Access classes, a Thompson-sampling recommender with a randomised arm, and a freshness audit. |
| E | SCAMPER + TRIZ | **FLUSH-E** | A 40-year succession clock from LCMS, Hansen and LandTrendr, aged forward to forecast future seasons. A per-pixel MLP. |

The designers did not coordinate, yet four of the five arrived independently at complete checklists plus a separate effort term. The fifth, A, included them as one label stream among three.

---

## 3. Round 2: the final proposals

### 3.1 What all five now share
- **Labels:** EBD complete checklists, filtered to eBird best practice, with Sampling Event Data supplying the non-detections.
- **Likelihood:** cloglog, P(detect) = 1 − exp(−e^{g(effort)} · Σ_footprint e^{f(habitat)}).
- **Effort term:** may use only covariates measured on the checklist itself (B's rule, now adopted by all). That means duration, distance, observers, time, date and an out-of-fold observer-skill index. Nothing location-derived is allowed.
- **Prediction:** a fixed standard walk (about 1 h, 2 km, mid-October morning).
- **Production model:** LightGBM, with the neural model optional and gated.
- **Product:** a covert card per covert, carrying:
  - expected encounters or flushes per hour, with an interval;
  - access class from PAD-US and state lands;
  - freshness and peak window;
  - a daily pick of 4 Thompson-sampled coverts plus 1 randomised covert, which gives an unbiased estimate of lift.
- **Primary metric:** observed/expected top-k lift, with an effort-only expectation as the denominator (D). Legacy AUC is reported but never optimised.

### 3.2 What each final proposal adds

| Design | Unique contribution (what only this design has) | First decisive test | Self-assessed gate priors |
|---|---|---|---|
| **A: CYM** | A **frozen zero-fit prior map** built from literature mechanisms, committed before any label is seen. It enables a blinded field test *this* season: prior map vs CNN vs random accessible forest. A hunt-log "transfer" term models how hunters and birders differ in detecting grouse. | T1, week 1: on real held-out checklists, the prior map vs the CNN vs a one-variable "share of 5–20-yr cuts within 250 m" heuristic. CYM's core dies if the prior map beats neither. | Expects to lose slightly in-sample to the GBM. The bet is the extrapolation subset (+0.02–0.05 AUC). Field lift 1.3–2.5× over random. |
| **B: CEM-X** | **Label-swap cross-play.** The same features and the same GBM are trained once on legacy labels and once on checklist labels. Each is scored on its own test set, on the other's and on an independent field, which cancels home advantage. Also: within-observer AUC, a drop-targeters refit, positive and negative control species, and an achieved-vs-achievable AUC ratio. | T0 (days 2–3): injection–recovery on real checklist geometry. T1 (days 3–5): cross-play. | G1 label thesis 0.6, G2 within-observer 0.6, G3 clock 0.45, G4 AlphaEarth 0.35, G5 neural 0.25, G6 season-1 field 0.35. |
| **C: FLUSH-C** | (1) The **leak-free arena "H"**: checklists inside the current CNN's own validation blocks with a 2.5 km buffer. (2) The **disturbance panel test**: eBird locations birded before *and* after a harvest within 300 m, with a location fixed effect, where the model must predict the within-site change as the cut ages. It is the only within-site, causal-style test. (3) AlphaEarth embeddings with roads, paths, parking and buildings masked out, behind an infrastructure-probe gate, aged forward coherently. | Days 1–2: an injection simulation for the minimum detectable effect. Days 3–5: cross-play on H, with a kill rule. Week 2: the panel test and a v0 covert product (about 20 October). | Cross-play passes 0.65, fall top-5% lift gap ≥ 0.3× 0.60, panel test 0.55, embedding gate 0.40. |
| **D: COVERT-X** | (1) **Same-observer, same-day, first-visit case-crossover** as the primary metric. It cancels observer skill, date, weather, the year's level and seasonal detectability, and drops returns to known grouse spots. (2) A **label-permutation negative control** within observer × month × duration strata, measuring how much "habitat" effort alone can manufacture and gating every feature block. (3) **Detection modes** from eBird breeding/behaviour codes and comments: heard (drumming) vs seen (flushed). If the two rankings diverge, the product ranks by flush mode. (4) The **owner's blind scorecard** of at least 30 past coverts, frozen before any map is seen. | Day 1: counts and the scorecard freeze. Days 2–4: head-to-head on H, with kill rules for both the checklist programme and the current map. | 0.3–0.6 across gates. It does not claim to beat 0.77 legacy AUC. |
| **E: FLUSH-E** | A **season-contrast term**. Detection depends on canopy cover, conifer share and leaf-on status; it is free in spring and summer and fixed at zero in fall, so same-footprint spring/fall contrasts separate audibility from fall density. A fall-only fallback applies if its covert ranking disagrees with the full model (Spearman < 0.7). Also a naive-visit test, and a feature stencil per checklist-year (about 5 GB). | Days 2–5: a fall-only gate. Checklist GBM vs the *recalibrated* CNN on fall checklists in H, within observers. Kill unless fall top-5% lift is ≥ 0.2 higher and within-observer AUC is ≥ 0.015 higher. | Clock about 0.45, neural about 0.25. A 1.2× field gain needs about 120 h per arm. |

### 3.3 Cross-critique matrix (strongest flaw raised against each design)

| Target | Raised by | Flaw | Severity | Status in target's final |
|---|---|---|---|---|
| A | B | Precision is capped by a small model centred on stand age, and stand age added only +0.001 AUC in the tree-model tests (CR-0032 record) | MAJOR | Partly answered: a flexible residual is allowed behind a gate. A concedes it may lose in-sample. |
| A | C | The footprint disc grows with distance walked while the distance term cannot go negative: 29× the area for a 4 km walk against 0.5 km, vs 8× the path length. The fit then down-weights remote big woods. | MAJOR | Open. Raised in round 2 after A's final. |
| A | D | Injection–recovery compares models on different synthetic truths. T1 scores the CNN on its own training positives. | MAJOR | Open (the leak issue in §4) |
| A | E | Rigid priors miss spruce–fir regeneration and wetland cover | MAJOR | Open |
| B | D, C | Negative-control species (chickadee, jay) cannot fail because their maps are nearly flat. All of B's tests are between-site. | MAJOR / MEDIUM | Open |
| B | E | Cannot separate detectability from abundance, so a gain may be spring drumming | MAJOR | Partly answered: B has a fall head |
| C | B | 10 m embeddings can see trails and parking | MAJOR | **Accepted and fixed**: infrastructure mask, a probe gate (AUC > 0.70 fails) and gated status |
| C | A | Its 5-year trajectory holds an embedding that ends in 2024 fixed | MAJOR | **Accepted and fixed**: coherent ageing and a 2019→2024 back-test requiring Kendall τ ≥ 0.80 |
| C | E | AlphaEarth may have been pretrained on GBIF occurrences, which include eBird, so evaluation may leak | MAJOR, possibly BLOCKING | **Unverified.** Must be checked before the embedding gate. |
| D | A, B, C, E | Location-derived effort covariates plus the gradient-reversal adversary erase real remoteness signal and flatten the north woods | MAJOR (all four) | **Accepted and fixed**: both removed |
| E | A, B | Using the species count as the effort proxy carries habitat and counts the grouse itself | MAJOR | **Moot or fixed**: the pseudo-checklist step was dropped once the owner's EBD access was known |
| E | D, C | Its day-1 comparison is not leak-free (CNN in-sample) | MAJOR | Partly answered: E uses the recalibrated CNN on H |

---

## 4. Facts verified or corrected during the competition

| Fact | Verified by | Consequence |
|---|---|---|
| GBIF eBird records have **no checklist ID, start time or effort fields**. They do carry observer ID, date and coordinates. | C, then A, B and D via the GBIF API | Only the EBD with Sampling Event Data supports a checklist model. The owner has it. |
| The **current CNN's positives are GBIF eBird detections** (`sightings.py:20`, `EBIRD_DATASET_KEY`) | D; confirmed in the repository | Any CNN score on EBD checklists outside its validation blocks is partly in-sample. All CNN comparisons must use C's leak-free H set. |
| About **61% of grouse records are April–June and about 15% September–November** (about 43k records, 2016–24). There are 5,774 fall records for 2020–24. | E, B (GBIF API counts) | A model trained on all seasons mostly learns where drumming is audible. Fall-specific handling is required: E's season-contrast term and/or D's detection modes. |
| The **Vermont Green Mountain NF drumming-recorder release (doi:10.5066/P13EFLXX) has no site IDs or coordinates** | D and C (file list downloaded) | Not usable as an independent scorer without a data request to USGS/USFS |
| The **NH flush-rate pages return 403** to automated fetch. ME and VT sub-state flush data are unconfirmed. | A, B, C, D, E | Flush aggregates are a scale and year check only (C's ecological-fallacy point), pending agency requests |
| Whether AlphaEarth was pretrained on eBird/GBIF occurrences | Raised by E; **unverified** | Check before using the embeddings |
| eBird `SPECIES COMMENTS` and behaviour-code columns are present | Assumed from EBD documentation; **unverified** against the owner's file header | Needed for D's heard/seen split. If absent, behaviour codes only. |

---

## 5. Assessment

The final proposals hardly differ in the model; they differ in **evidence design**. Judged on what each adds that survived attack:

1. **C (FLUSH-C)** contributes the two things every other design adopted or has no substitute for. First, the leak-free H arena, which A, B, D and E all adopted. Second, the before/after-harvest panel test, the only test that compares a site with itself and so cancels why birders choose sites. Its embedding block is the only input that is genuinely new information, and it is gated sensibly. One leakage question is open.
2. **D (COVERT-X)** has the strongest robustness tests:
   - the case-crossover cancels most confounds exactly;
   - the permutation control fixes B's controls that cannot fail;
   - the heard/seen split addresses the seasonal problem directly;
   - the owner's scorecard is the only independent check available *today*.

   D lost its round-1 adversary, but every designer agreed it should go.
3. **E (FLUSH-E)** found the most consequential new fact, the 61%/15% seasonal split, and its season-contrast term is the principled response.
4. **B (CEM-X)** supplied the general evaluation machinery that most finals reuse: cross-play, within-observer AUC and drop-targeters. Its own differentiators are weaker now that the others have adopted them.
5. **A (CYM)** is the only design that can put a falsifiable map in the field *this season*. Its main core is the weakest bet, given the +0.001 prior result for stand age, and C's footprint-area critique is unanswered. A is candid about this.

This ranking is the compiler's judgement, not a vote by the designers.

---

## 6. Recommended merged plan

Each phase below is its own change request under CLAUDE.md §1. Acceptance scripts are committed first (CR-0011 A3). Nothing writes to `data/` before approval. CR-0035, the registration repair, finishes first: its evaluation is the legacy baseline every comparison below uses.

**Week 0–1: freeze the evidence before fitting**
1. **The owner's blind scorecard (D).** Rate at least 30 past coverts and commit the file before seeing any map.
2. **Frozen prior map (A).** Build the literature-mechanism map, commit it, and start the randomised blinded field arms for the rest of the 2026 season: prior map / current CNN / random accessible forest. Use one randomised covert in five.
3. **EBD ingest.** One row per complete checklist, filtered to best practice. Record counts by state, season, protocol and detection mode. Verify the column header, including species comments.

**Week 1: the decisive tests, all pre-registered and run on the leak-free H set (C)**

4. **Injection–recovery (B, C)** on real checklist geometry. This sets the minimum detectable effect and tests the season-contrast term (E).
5. **Cross-play (B).** Train the same GBM on legacy labels vs checklist labels and score home, away and independent. The current CNN is recalibrated on the same checklists (E).
6. **Kill rules,** combining E's and D's:
   - the checklist programme stops unless fall top-5% observed/expected lift is ≥ 0.2 higher than the recalibrated CNN;
   - **and** same-observer case-crossover (D) shows a positive gain;
   - **and** the label-permutation control (D) shows the gain is not manufactured by effort.

**Weeks 2–3: build the model if it survives**

7. **Production model.** LightGBM cloglog with footprint features and the checklist-only effort term. Add a **season-contrast** detection term (E) and a **heard/seen detection-mode** split (D). The product ranks by the fall, flush-mode model.
8. **Disturbance panel test (C).** Run it as the causal check on the habitat function and the succession clock.
9. **Feature gates.** Each block (the succession clock; AlphaEarth with infrastructure masking, after the pretraining-leak check) is kept only if it passes the permutation control and improves fall lift on H.
10. **v0 covert product** for the late 2026 season. Each covert card carries:
    - expected flushes per hour with an interval;
    - access class;
    - freshness and peak window;
    - an evidence badge.

    The daily pick is 4 Thompson-sampled coverts plus 1 randomised covert. Every logged hunt becomes a held-out label.

**Later:**
- agency requests for ME/VT flush data and for the GMNF recorder coordinates;
- leaf-off lidar understory metrics;
- a neural model only if it beats the GBM by at least 0.01 on H;
- a multi-season field comparison sized for 1.2× (about 120 h per arm).

---

## 7. Open items
- AlphaEarth pretraining data: does it include eBird/GBIF occurrences? This must be settled before the embedding gate (E, unverified).
- A's footprint-area bias raised by C: the disc area grows quadratically with distance walked. Any footprint kernel in the merged model should scale with path length, not with disc area.
- How many sites qualify for the panel test (eBird locations with checklists before and after a harvest). Its statistical power is unknown until counted (C).
- Agency data: NH flush-rate tables (the pages return 403 to automated fetch), ME and VT flush programmes, and the GMNF recorder coordinates.
- References in the designs marked **unverified** by their authors: several DOIs written from memory, and PDFs seen only through search summaries.
