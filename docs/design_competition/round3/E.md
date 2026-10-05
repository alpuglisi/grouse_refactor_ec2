# Design E, final (round 3): FLUSH-E, a fall-first checklist encounter model that must prove it is not a drumming map

*Designer E. Techniques: SCAMPER and TRIZ (round 1); red-teaming and empirical probing (round 2); and in round 3, a "can this test fail?" audit of every acceptance rule, applying the repository's own PA-0021(a). No repository file was edited. The owner already holds eBird EBD and Sampling Event Data (SED) access.*

---

## 0. Changes from round 2

### 0.1 Adopted from competitors' round-2 revisions (credited)

| Adopted | From | Replaces or adds |
|---|---|---|
| **Disturbance panel test X2.** Uses eBird locations birded before and after a cut within 300 m, with a location fixed effect, and checks that the model predicts the within-site change. | **C** | A within-site test of the habitat function that site-level preferential sampling cannot fake. I add a land-use filter (§6). |
| **Same-observer, same-day case-crossover** concordance (CC), and its **first-visit** restriction. | **D** | Replaces my round-2 "naive-visit" subset. D's version is the same idea done more strongly, because it also cancels date, weather, skill and the year's population level. |
| **Within-stratum label-permutation null band.** | **D** | The effort-leak gate. It cannot pass trivially, unlike raw control-species correlations. |
| **Detection-mode decomposition.** Aural vs visual detections, taken from EBD breeding and behaviour codes and species comments. | **D** | Becomes one of three detectability estimators (§3.4). |
| **The owner's blinded covert scorecard**, frozen before any map is seen. | **D** | The only non-eBird scorer of hunter truth that exists today. |
| **A zero-fit H250 covert layer for the 2026 season, shipped this week.** | **A** (idea), **D** (H250 form) | The owner hunts with something now, and every hunt produces data. |
| **Forest-only partial correlation** for control species, and Eastern Towhee as a positive control that is detected by song. | **C** | Replaces my raw Spearman threshold of 0.6. |
| **Infrastructure-masked disc means, if AlphaEarth is used at all.** | **C** | Applies to the optional embedding block only. |
| **Age-conditional transport and a pre-registered back-test** for forecasts. | **C** | Answers C's critique of my forecast (§3.6). |
| **Cross-play (home/away) matrix**, as a secondary label-effect check. | **B** | Supplements the HH gate. |

### 0.2 Fixed after verification

- **Vermont Green Mountain NF recorder release.** C and D both checked ScienceBase: the release has no site IDs or coordinates. It is now a *requested bonus*, not scorer S1. Any acoustic metric is drums per recorder-day (A's fix, accepted in round 2).
- **CNN baseline in-sample risk.** The CNN's positives come from the GBIF eBird dataset. I verified `sightings.py:20` (`EBIRD_DATASET_KEY = "4fa7b334-…"`). The CNN is therefore scored **only on HH**, the checklists inside its own validation blocks. Training excludes everything within **2.5 km** of HH, which is C's value and exceeds the largest stencil radius.
- **Forecast coherence (C, MEDIUM).** Composition features that age with the stand (canopy height, `mch_*`, canopy cover, EVH) are no longer frozen while the clock advances. Forecast mode uses a clock-only sub-model or age-conditional transport. Neither is trusted until it passes a back-test (§3.6).

### 0.3 Kept: what still differentiates FLUSH-E

1. **A detectability triad with a decision rule that can fail.** Three independent estimates of the "spring tilt":
   - (a) my season-contrast openness term, identified by same-location cross-season visits;
   - (b) D's mode divergence;
   - (c) an **unshrunk, independently fitted fall-only model**.

   Every competitor judges spring vs fall agreement against a heavily shrunk fall head fitted on top of the all-season model. That test agrees by construction (§10, new MAJOR against B, C and D), and PA-0021(a) says a test that cannot fail is not evidence. FLUSH-E's reference model is fitted separately, so the agreement test *can* fail. An injection test (T2) confirms it fails when it should.
2. **Off-trail importance-weighted evaluation.** Every metric is also reported reweighted to the forest population, not the birded population. C and D adopted this.
3. **Forecast back-test** for "rising" coverts, plus a **rule-out layer**.
4. **The lightest buildable stack.** One row per checklist, with stencil-averaged features and a LightGBM cloglog model. The 16-point stencil table is about 5 GB, with no per-pixel cube. The GPU is used only for prediction-grid convolutions and an optional MIL network.

### 0.4 Dropped

- My round-2 "naive-visit" test, superseded by D's case-crossover.
- GMNF as a primary scorer.
- Raw control-species thresholds.
- Any claim that eBird separates detection from density. The season-contrast term identifies only the *habitat-dependent part of spring detection relative to fall*.

---

## 1. Title and pitch

**FLUSH-E ranks this October's huntable coverts by fall grouse encounter rate.** It uses eBird complete checklists, a footprint likelihood and an effort term that sees only event-measured covariates and is dropped at prediction. Its central claim is narrow and testable: the map reflects *where grouse are in fall*, not *where drumming is audible in May* and not *where birders walk*.

The narrowness is deliberate. About 61% of ME/NH/VT eBird grouse records fall in April–June, and only about 15% in September–November. I counted this from GBIF facets; B and D confirmed it. Any checklist model is mostly a drumming model unless something stops it. Every design now has a fall head. FLUSH-E is the one whose spring/fall agreement test can actually fail, and the one that triangulates detectability three ways.

**Week-1 decision on real EBD.** The checklist model must beat the current CNN on HH on three measures:

- same-day case-crossover concordance (D);
- fall top-5% observed/expected lift (TkL₅; D's metric);
- effort-stratified AUC.

It must also clear a label-permutation null band (D). Otherwise the checklist programme stops, and the owner keeps the H250 layer plus the product and field test.

**The product** is a covert card: an encounter index with an interval, peak window, freshness, access class, walk-in distance and badges. Coverts come four by Thompson sampling plus one randomised, so the season itself measures lift. The owner hunts the zero-fit H250 layer this week while the model is built.

---

## 2. Brainstorming record (short)

- **Round 1.** SCAMPER over nine stages and seven TRIZ contradictions. These converged on a single latent fall intensity, honest observation models, a time axis and a hunter-scale output (round1/E.md §2).
- **Round 2.**
  - Red-team review of every competitor.
  - Empirical probing of GBIF facets: the 61%/15% season split.
  - AlphaEarth pretraining included GBIF occurrences.
  - A differentiation matrix led to the season-contrast term and the injection test.
- **Round 3 (new): "can this test fail?" audit.** For every acceptance rule in all five designs, I asked whether a plausible wrong model passes it. This is PA-0021(a) of the repository applied to designs. Findings:
  - Agreement between f and a shrunk f + Δ_fall cannot fail. This hits B, C and D, and my own round-2 guard, which was fitted against the full model. The fix is an independent fall model (§3.4).
  - Raw control-species correlation passes trivially (C's point). Fixed by D's permutation band.
  - A CNN scored outside HH is inflated, so a "CNN ≈ new model" result could not distinguish a working programme from a broken one. Fixed by HH-only scoring.
- **Convergence.** I adopted every competitor test that a cheating model fails, and kept only my pieces that no competitor had made fail-able.

---

## 3. The design

### 3.1 Estimand

For covert C and season t:

$$F(C,t)=\kappa\cdot\tfrac{1}{|C|}\textstyle\sum_{s\in C}\exp\big(h_{\text{fall}}(Z(s,t))\big)$$

This is an expected-encounters index for a standard fall hour on foot. The standard walk is one median-skill observer, traveling, 60 minutes, 2 km, 15 October, 08:00. h_fall is the fall-detection-scale habitat function chosen by §3.4.

- κ is a single scalar, fitted to the owner's logs and checked against NH regional flush rates. It is displayed but never used for ranking.
- D's huntability factor q_C (low in 0–4-year slash) is an expert prior until the logs can fit it.

### 3.2 Data

| Data | Status | Use |
|---|---|---|
| eBird EBD + SED, ME/NH/VT plus 10 km border strips, 2010–2025 | **Owner has it** | Labels and effort. Filters follow Johnston et al. (2021): complete; Stationary/Traveling; 5–300 min; ≤ 5 km; ≤ 10 observers; one per `GROUP IDENTIFIER`. The 2010+ years serve C's panel test; fitting uses 2016+ |
| EBD breeding/behaviour codes and species comments | In the same file (exact column names **to verify in the owner's header**) | Detection mode (D) |
| Existing 15 layers + `mch_*`, after the CR-0035 registration repair | On EC2 | Habitat features (the `diagnose_gbm_baseline.py` design, stencil-averaged) |
| Succession clock, fused: LCMS v2024-10 Change and Land Use (1985–2024), Hansen GFC v1.12 `lossyear`, HF437 Maine harvests 1986–2019 (A), LANDFIRE annual disturbance, OPERA DIST-ALERT 2025–26 (D) | Earth Engine / archives | Age-class shares at 90/250/600 m; diversity; slow-loss flag; source-agreement count. Exported on the template lattice with explicit `crsTransform` and the BUG-0094 offset probe; extraction reuses `diagnose_disturbance_features.py` |
| Openness covariates (TCC, LANDFIRE canopy cover, conifer share) | On EC2 | Season-contrast term only |
| NH regional flush/observation rates | The owner downloads the PDF (403 to this container) | κ and a leave-one-region-out check |
| Owner's blinded scorecard (≥ 30 past coverts, rated 1–5) and 2026 GPS hunt logs | Owner | Independent scorers |
| GMNF recorder data with sites | **Data request** (the public release has no site coordinates; verified by C and D) | Bonus scorer |
| PAD-US 4.x, state WMA layers, OSM/TIGER roads | Public | Product only (access classes A1–A4/X, from D) |

### 3.3 Model

For checklist j with stencil points s_{j1..16}, spread over a Gaussian footprint of σ = √(150² + (0.35·dist_j)²) m truncated at 3σ:

$$P(y_j=1)=1-\exp\!\big(-\exp[\,g(e_j)+\mathbb 1_{\text{spring}}(j)\,\beta^{\top}o_j+H(\bar Z_j)\,]\big),\qquad \bar Z_j=\tfrac1{16}\textstyle\sum_m Z(s_{jm},t_j).$$

**g, the effort term (event-only rule from B).** Inputs:
- log duration and log(1 + distance), both monotone ≥ 0;
- protocol and party size;
- start-time spline and cyclic day-of-year spline;
- year;
- out-of-fold observer skill (Kelling et al. 2015);
- observer random effect for observers with ≥ 20 checklists.

There is **no** location-derived variable and **no** checklist species count. g is fitted as a GAM offset, alternated with H for 3–5 rounds.

**β·o_j, the season-contrast term (spring only; fall is the reference at zero).** This is the habitat-dependent excess of spring detectability. h has no season input, so β is identified only by spring-vs-fall contrasts at the same places in the same year. Grouse are resident, and their home ranges are only 2–16 ha (report §1.5).

**H, the habitat function.** LightGBM with a custom cloglog objective, one row per checklist. Gradient and Hessian are row-wise (C's form), with g + β·o passed as `init_score`. Features are averaged over the stencil, which approximates the mean of exp(H) by exp(H of the mean). The optional stage-2 MIL network removes the approximation, and is kept only if it beats stage 1 on the gate.

**Ensemble.** 5 spatial folds of 25 km blocks (checked against the residual variogram) × 2 seeds. The epistemic interval comes from fold spread. Coverts outside the training envelope are flagged on PCA-20 Mahalanobis distance.

### 3.4 The detectability triad and the ranking rule

Three estimators of the spring tilt, each fitted on HH-excluded training data:

1. **(a) Season contrast.** β above. The tilt map is β·o rendered over forest.
2. **(b) Mode divergence** (D). A competing-risks split Λ = Λ_aural + Λ_visual on mode-labelled detections. The modes come from codes such as `S` → aural and `FL`/`DD`/`NY` → visual, plus keywords in comments; detections with unknown mode enter the sum. FLUSH-E fits the visual head **unshrunk** on its own subset, rather than as a shrunk deviation.
3. **(c) Independent fall-only model** H_fall. The same features and g, fitted *only* on September–December checklists, with no offset from the all-season H and only ordinary regularisation chosen by fall-fold deviance. The fall sample is about 5.8k detections in 2020–24 alone (B's count), more with 2016–19 and 2025.

**Ranking rule (pre-registered).** Compute the covert-ranking Spearman on HH coverts between:
- the all-season H (season term set to fall);
- H_fall;
- the visual-mode model.

1. If all pairs are ≥ 0.8 and the HH fall-subset deviance of H is not worse than H_fall's, then **h_fall = H** (most data, least variance).
2. Otherwise **h_fall = a stack of H and H_fall**. Stack weights are fitted on fall-fold deviance outside HH. Coverts where the components disagree by more than a quintile get an "audible, not flushable?" badge.

**Why this can fail.** H_fall shares no shrinkage with H. If the spring tilt is real, Spearman(H, H_fall) falls below 0.8. T2 checks this on the real checklist geometry: it plants a known tilt and requires the rule to fire. The fall-head tests of B, C and D compare f with f + (depth-3, heavily L2-penalised Δ). Such tests return ≈ 1 whatever the truth, so the "disagree" branch is unreachable (§10).

### 3.5 Preferential sampling and effort leakage (pre-registered acceptance code, CR-0011 A3)

| Test | Source | Cancels | Rule |
|---|---|---|---|
| Same-day case-crossover CC on HH | D | Skill, date, weather, population level, seasonal detectability | Primary in T1 |
| First-visit CC | D | Returning to known grouse spots | < 50% of the gain survives → coverts badged "PS-fragile" |
| Disturbance panel X2 | C | Fixed site traits, including why the site is birded | Slope of observed on predicted within-site change > 0 (lower CI > 0), if powered |
| Drop-targeters | B | Grouse-seeking observers | Covert-rank Spearman ≥ 0.9 with the full model |
| Label-permutation band (20 fits, permuting within observer × month × duration tercile) | D | Effort-manufactured "habitat" | Real CC must exceed the band's 95th percentile; any added feature block (clock, AlphaEarth) must raise real CC more than permuted CC |
| Control species, forest-only partial correlation | C (B's idea) | Shared effort geography | Partial ρ(grouse, negative control) < partial ρ(grouse, Eastern Towhee) − margin, with the margin calibrated in T2 |
| Off-trail importance-weighted TkL | E | Covariate shift from birded to all forest | Reported next to plain TkL; a block that wins on plain TkL and loses on this is dropped |

### 3.6 Forecasting coverts (answers C's critique)

The **current season** uses the current year's features, with fresh cuts from DIST-ALERT 2025–26.

For **future seasons** t′ = t + k, the forecast mode drops age-dependent composition features, namely canopy height, `mch_*`, canopy cover and EVH. It uses a **clock-only sub-model**: clock shares, guild, slow-loss, elevation and SWE. This is the A/C coherent option.

**Back-test (pre-registered).**
1. Freeze features at 2020.
2. Age the clock to 2024.
3. Score 2024–25 HH checklists.

**Pass** if fall TkL₅ is within 0.15× of the same model given true 2024 features, and the Kendall τ of the top-500 covert ranking is ≥ 0.8 (C's threshold). **On failure**, the card shows the peak window from the clock, but the forecast index is withheld.

### 3.7 Feasibility (one owner, one EC2 GPU)

| Step | Size | Time | Hardware |
|---|---|---|---|
| Ingest (pandas or polars streaming) | ~10⁶ checklists (**estimate**; counted on day 1) | < 1 h | CPU |
| Stencil features | 16 points per checklist, own year, ≈ 16 M point reads per layer; ≈ 5 GB | Hours | CPU (patch reader) |
| Clock rasters | Per-year int8, exported once | — | EE + registration gate |
| Fits | LightGBM on 10⁶ rows; 20 permutation fits on a 200k subsample overnight | Minutes per fit | CPU |
| Prediction | Per tile with a 600 m halo; disc means of the clock on the GPU | Hours per state-year | GPU |
| Optional stage 2 | MIL net | Minutes per epoch | GPU |

### 3.8 End product

1. **Week 1: H250 covert layer.** Share of a 250 m radius cut 5–20 years ago, zero-fit (A/D). It carries access classes and walk-in distance. The owner hunts it while T0–T2 run.
2. **Week 3: FLUSH-E covert layer.** Objects come from disturbance patches aged 4–25 years, SLIC on (age, `mch`, deciduous share), and a 25 ha hexagon background, sized 2–40 ha. Each card carries:
   - F with an 80% interval;
   - peak window;
   - freshness;
   - access class A1–A4/X;
   - walk-in distance;
   - top-3 reasons;
   - badges: extrapolated, audible-not-flushable, PS-fragile, evidence-poor.
3. **Rule-out layer.** High effort with confidently low F.
4. **Daily list.** Four coverts by Thompson sampling plus one uniform draw from the accessible top 30% (D). After each logged hunt, a gamma–Poisson covert effect updates. Output is GPX/KML.
5. **Season ledger.** Logs are held out in season 1. After the season, fit κ and the hunter cover multiplier W(s) = W₀e^{ω·understory} (A).

---

## 4. Why it beats the status quo and the other four

**Against the status quo.** The report's diagnosis (§5.4) is that "the data is the ceiling". FLUSH-E answers each part:

| Problem in the report | FLUSH-E's answer |
|---|---|
| Positive–unlabelled background and the 1 − a/2 bound | Real non-detections with effort |
| Effort bias | An event-only effort term dropped at prediction, a permutation band and off-trail evaluation |
| The estimand | A fall encounter rate instead of a reporting contrast |
| Location error | A footprint instead of the centre pixel |
| Stale map | A clock plus fresh cuts, and back-tested forecasts |
| No external truth | Scorecard, randomised arm, NH regions |

**Against the others.** The core is shared, so this compares only the unshared parts:

| Axis | FLUSH-E | Best competitor version |
|---|---|---|
| Detectability (spring tilt) | Triad, with an independent fall model; agreement test can fail; injection-checked | D's mode split, but D's shrunk heads make its divergence test hard to fail |
| Preferential sampling | D's case-crossover + first visit, C's panel, B's targeters | C and D (adopted) |
| Effort leakage | D's permutation band, C's partial-ρ controls, off-trail TkL | D (adopted) |
| CNN comparison | HH only, 2.5 km buffer | B, C, D. A's T1 decision still uses the full set (§10) |
| Forecast | Clock-only forecast mode with a back-test | C (transport with a back-test) |
| Feasibility | One-row LightGBM, ~5 GB stencil table | C is comparable but adds AlphaEarth disc filtering; A needs NUTS |
| Hunting now | H250 this week | A and D |

---

## 5. Expected gains, and how not to fool ourselves

**Arena.** HH (C) with a 2.5 km training buffer. Internal folds are 25 km blocks. A temporal arm trains on ≤ 2023 and tests on 2024–25.

**Metrics, in priority order:**
1. Same-day case-crossover CC on HH.
2. Fall TkL₅ (observed ÷ effort-only-expected).
3. Effort-stratified AUC, plus the oracle ratio (B).
4. Off-trail TkL.
5. Scorers: S0 the owner's scorecard (Spearman, weighted by times hunted); S1 NH leave-one-region-out; S2 the 2026 randomised arm.

**Statistics.** Paired block bootstrap. Ties are anything below the minimum detectable effect from T2, expected around 0.01 AUC, 0.15× TkL and 0.01 CC.

| Quantity | CNN | FLUSH-E | Confidence |
|---|---|---|---|
| Case-crossover CC on HH | 0.53–0.58 | 0.56–0.63 | Low |
| Fall TkL₅ on HH | 1.3–1.8× | 1.6–2.4× | Low |
| Effort-stratified AUC on HH | 0.62–0.70 | 0.67–0.75 | Low–medium (direction per Johnston et al. 2021) |
| Share of CC gain surviving first-visit | — | 50–90% | Low |
| Spearman(H, H_fall) over coverts | — | 0.6–0.85, so the stack branch is a real possibility | Very low |
| Scorecard Spearman (n ≈ 30; SE ≈ 0.18) | 0.1–0.4 | 0.3–0.6 | Very low; only differences ≥ 0.35 are visible |
| Randomised-arm lift, 2026 | — | ≥ 1.4× point estimate; ~40 visits detect only ≥ 2×; 1.2× vs the CNN needs ~120 h per arm (A) | Very low this season |
| Legacy TG AUC | 0.762 / 0.770 | 0.74–0.78, not optimised | Medium |

**Gate priors (probability of passing):**

| Gate | Prior |
|---|---|
| G1: T1 passes | 0.55 |
| G2: ≥ 50% of the gain survives first-visit, given G1 | 0.6 |
| G3: clock adds ≥ 0.005 CC under checklist labels (it added +0.001 AUC under TG labels; verified in CR-0032) | 0.45 |
| G4: the triad fires (spring tilt material) | 0.4 |
| G5: forecast back-test passes | 0.6 |
| G6: X2 is powered and passes | 0.4 |
| G7: AlphaEarth passes all gates | 0.3 |

I do not claim to beat 0.77 on the legacy metric. The claim is better within-landscape ranking of places, net of effort and of spring audibility, and it can be killed in week 1.

---

## 6. Risks, failure modes and falsification, in run order

| When | Test | Kill or change |
|---|---|---|
| Day 1 | **T0.** Ingest and count: checklists; detections by month, state and mode; same-day pairs on HH; first-visit pairs; cross-season repeat locations (power for β); treated panel sites (power for X2). **Scorecard frozen.** **H250 layer shipped.** **T3 freshness audit** (D) | If same-day pairs on HH number < 2,000, CC falls back to stratified AUC. If cross-season repeats are < 500 locations, (a) is dropped from the triad |
| Days 2–4 | **T2. Injection–recovery on real EBD geometry.** Plant: (i) a truth with a spring tilt (audibility ∝ openness; density peaks in dense young cover); (ii) a no-tilt truth; (iii) a preferential-sampling variant (visit odds rise near trails) | The triad must fire on (i) and not on (ii) at > 90% of 50 draws; this calibrates the 0.8 threshold per PA-0021(c). The permutation band and control margin are calibrated here. If the rule cannot separate (i) from (ii), the triad falls back to "always stack H_fall" |
| Days 3–5 | **T1. Decisive gate on HH.** Arms: effort-only, CNN, H250, FLUSH-E stage 1 (legacy features, no clock). Metrics: CC, fall TkL₅, stratified AUC; 20 permutation fits | **Kill the checklist programme** if stage 1 is not above both the CNN and the permutation band on CC by > 1 bootstrap SE, *and* its fall TkL₅ gap over the CNN has a CI that includes 0. **Downgrade the CNN** if its CC sits inside the band |
| Week 2 | **T4.** Clock ablation (G3); triad (§3.4); first-visit and drop-targeters runs; controls; off-trail TkL | Decides h_fall and the badges |
| Week 2 | **X2. Panel test** (C) | See the X2 notes below |
| Week 3 | Forecast back-test (§3.6); product v1 | Forecast shown or withheld |
| Season | Randomised arm; scorecard re-scored; κ and W fitted | Product truth, accumulating over seasons |

**X2 additions to C's design:**
- Treated sites must be **forest → forest** in LCMS Land Use. Otherwise the "cuts" near suburban hotspots are housing developments, and a land-use loss would be scored as a young stand.
- Observer and season effects enter, because post-cut visitor composition changes.
- The 0–4-year bin is reported separately, because a fresh cut changes visibility as well as density.

**Main risks:**

| Risk | Severity | Mitigation |
|---|---|---|
| Spring tilt is real but undetectable (few cross-season repeats, sparse mode labels) | MAJOR | H_fall is always fitted. When the triad is underpowered, the stack is the default, not H |
| Location-level preferential sampling (well-known grouse trails) | MAJOR | X2; first-visit; badges; field arm |
| Partial harvests invisible to the clock | MEDIUM (shared by all designs) | LCMS slow loss; HF437; `mch_f15` |
| Misregistration of new exports | MAJOR (BUG-0094 class) | Template `crsTransform`, `grid_mismatch` and the offset probe as gates |
| Too few fall detections | MEDIUM | ~5.8k in 2020–24 alone; extend to 2016–25 |
| Access errors | MAJOR (ethics) | A4 is never shown as open; personal use only |
| QMS overhead | Process | One CR per phase, gate code first (CR-0011 A3/A5) |

---

## 7. Implementation plan

Each phase is one CR, with acceptance scripts committed first.

| Phase | CR | Content | Effort |
|---|---|---|---|
| P0 | Acceptance | `eval_flush_e.py`: HH, buffer, CC, TkL, stratified AUC, permutation harness, triad rule, back-test, thresholds; scorecard format | 2 d |
| P1 | Data | `ebd_ingest.py`: filters, zero-fill, group dedup, first-visit flags, mode labels, cross-season repeat index, stencil coordinates | 2 d |
| P2 | Generator | Fused clock rasters on the template lattice (registration-gated); H250 layer + product shell (access, walk-in) | 3 d |
| P3 | Model | `flush_e_gbm.py`: event-only GAM g, season term, LightGBM cloglog H, H_fall, mode heads, folds, stack | 5 d |
| P4 | Product | Covert objects, cards, badges, recommender, ledger, GPX/KML | 4 d |
| P5 (optional) | Model | MIL network; AlphaEarth block (masked; evaluated on 2024–25 only, §10 C); lidar understory | 1–2 wk |

**First experiment the owner can run within a day:** T0 counts on the existing EBD/SED files, the HH build from `regions.py` blocks, and the scoring of CNN vs H250 vs effort-only on HH (CC and fall TkL₅). The scorecard is frozen first. This already shows whether today's map ranks places within an observer's day better than chance, before anything is fitted.

---

## 8. References

URLs were checked in rounds 1–3 unless marked **unverified**.

- GBIF eBird Observation Dataset, CC-BY 4.0, `datasetKey 4fa7b334-ce0d-4e88-aaae-2e0c138d049e`. Fields and month facets were checked via the API on 2026-10-05: grouse ME+NH+VT 2016–24 total 43,024; no `eventID` or effort fields. https://api.gbif.org/v1/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e ; repository `sightings.py:20` uses the same key.
- eBird EBD / `auk`: https://docs.ropensci.org/auk/reference/auk_zerofill.html
- Johnston, A. et al. (2021). *Diversity and Distributions* 27:1265–1277. https://doi.org/10.1111/ddi.13271
- Kelling, S. et al. (2015). *PLoS ONE* 10:e0139600. https://doi.org/10.1371/journal.pone.0139600
- Maclure, M. (1991). The case-crossover design. *Am. J. Epidemiol.* 133:144–153 (via D; **unverified**).
- Lipsitch, M. et al. (2010). Negative controls. *Epidemiology* 21:383–388 (via B; **unverified**).
- Lapp, S. et al. (2023). *Wildlife Society Bulletin* 47(1). https://doi.org/10.1002/wsb.1395
- Clarfeld, L.A. et al. (2025). USGS data release doi:10.5066/P13EFLXX ; https://www.sciencebase.gov/catalog/item/679392d5d34e88f5864c50b5 (no site coordinates, per C and D)
- HF437 Maine harvest maps 1986–2019: https://doi.org/10.6073/pasta/20a838c4bd6922685b3d00661d45c414
- LCMS v2024-10: https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10 ; Hansen GFC v1.12: https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12 ; OPERA DIST-ANN: https://developers.google.com/earth-engine/datasets/catalog/OPERA_DIST_L3_DIST-ANN-HLS_V1 (via D)
- AlphaEarth Foundations, arXiv:2507.22291. The paper's training data includes GBIF occurrence records (Animalia, CC-BY/CC0, 2017–2023, ≤ 240 m uncertainty), as summarised by search. https://arxiv.org/abs/2507.22291
- NH Fish & Game wing-and-tail survey: https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey (403; figures **unverified**)
- PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download (via D)
- Repository: `docs/grouse_model_report.md`; `CR-0032-meta-canopy-structure-layers.md:22-25`; `diagnose_disturbance_features.py`; `diagnose_gbm_baseline.py`; `regions.py`; `docs/quality/PREVENTIVE_ACTIONS.md` (PA-0021 a/c; PA-0017/0020/0032).

---

## 9. Responses to critiques

| Critic | Critique | Severity | Accept / rebut | Evidence or fix |
|---|---|---|---|---|
| A | The day-1 test used species count, a habitat-dependent effort proxy | MAJOR | **Accept** | The pseudo-checklist test was removed in round 2. The rule is now permanent: g sees only event-measured covariates and an out-of-fold skill index, never species count (§3.3) |
| A | ARU naive occupancy saturates | MEDIUM | **Accept** | Metric is drums per recorder-day. GMNF is downgraded to a bonus after C and D verified it has no coordinates (§0.2) |
| A | The 36 GB/yr cube contradicts per-year training | MEDIUM | **Accept** | Replaced by a stencil table, own year per checklist, ≈ 5 GB; full-grid features only for the prediction year (§3.7) |
| B | Species-count proxy; and a single-coefficient CNN arm vs a fitted GBM has home advantage | MEDIUM | **Accept both** | Proxy removed. The CNN arm gets the same g and its own fitted spline; scoring is on HH only; B's cross-play added as a secondary check (§0.1) |
| B | ρ/λ separation needs closure | LOW | **Accept** | Claim removed. Only the narrower season-contrast identification remains, and its power is counted on day 1 (T0) |
| C | No leak-free comparison with today's map: B0 scored outside the CNN's split | MAJOR | **Accept (verified)** | `sightings.py:20` confirms the CNN's positives are GBIF eBird. HH-only scoring with a 2.5 km training buffer (§0.2, §5) |
| C | Species-count proxy (moot) | LOW | **Accept** | As above |
| C | Heavy cube; forecasts freeze composition while ageing the clock; no back-test | MEDIUM | **Accept** | Clock-only forecast mode with age-dependent composition excluded, plus a pre-registered 2020→2024 back-test (§3.6) |
| D | The day-1 test scored the CNN at its own training positives | MAJOR | **Accept** | Same fix as C's: HH only |
| D | Closure for ρ/λ | LOW | **Accept** | As above |

No critique of FLUSH-E is rebutted. Each was checked and found correct.

---

## 10. Final critique of competitors (round-2 versions)

| Design | Item | Severity | New / still-open | Evidence and failure scenario |
|---|---|---|---|---|
| **A: CYM** | **The T1 decision rule compares the CNN against the frozen prior map on the full held-out set.** Fall-only and HH are only "also reported" subsets, so the CNN is scored partly at its own training positives | MAJOR | Still-open (raised by D) | A §6 T1 steps 3–4; `sightings.py:20` (verified). Scenario: the inflated CNN beats D₀, the premise is wrongly "falsified", and CYM's structural core is dropped. Fix: make HH the decision set |
| A | **Footprint is a *sum* over a disc of radius 150 m + d/2, with a non-negative distance slope** | MAJOR | Still-open (raised by C) | A §3.4 O1, verified in A's text. Expected count scales with area (29× from 0.5 to 4 km against 8× in length), so the fit must depress D where long walks go, which is remote big woods |
| A | Rigid guild ordering and age-hump prior; the residual δ is ridge-shrunk | MEDIUM (down from MAJOR) | Partly fixed | A now gates the structure by T1/T2 and an extrapolation subset, but the gate inherits the full-set flaw above |
| A | A "blinded" field test cannot blind a hunter who can see young cuts | MEDIUM | Still-open | Expectation affects effort within a covert. Use count endpoints with a randomised arm (D) |
| **B: CEM-X** | Pseudo-checklist phases | — | **Fixed** (EBD) | — |
| B | **The spring/fall agreement test cannot fail.** It compares f with f + Δ_fall, where Δ_fall is depth ≤ 3, strongly L2-penalised and fitted with f frozen | MAJOR | **New** (sharpens my round-2 item) | B §3.3 and R-DT1. Shrinkage pulls Δ → 0, so Spearman(f, f + Δ) ≈ 1 whatever the truth, and the "rank by fall" branch never triggers. Scenario: a spring-tilted map (open mature hardwood beside cuts) ships with no badge. This violates PA-0021(a). Fix: an independently fitted fall model (§3.4), or calibrate the threshold by injection |
| B | Raw-ρ negative-control gate with forest birds | MEDIUM | Still-open (raised by C) | Any correct forest map correlates with chickadee or jay maps. Fix: forest-only partial ρ, or D's permutation band |
| **C: FLUSH-C** | **AlphaEarth pretraining used GBIF occurrences** (Animalia, CC-BY/CC0, 2017–2023). eBird on GBIF is CC-BY 4.0 human observation | MAJOR (BLOCKING for the AlphaEarth gate's H-set evidence if eBird rows passed AlphaEarth's ≤ 240 m filter; eBird rows carry no uncertainty value, so this is **unverified**) | Still-open (not answered in C's §0.2) | Scenario: 2017–23 grouse reports in H blocks shaped the embedding, so it "passes" X4 on H deviance through label leakage. Fix: evaluate the block on 2024–25 checklists only, or on non-eBird scorers |
| C | Infrastructure leakage of the embedding | — | **Fixed** (mask, probe, gate) | — |
| C | Shrunk Δ_fall agreement test (DT2) | MAJOR | **New** | Same mechanism as for B (C §3.6 DT2: depth ≤ 3, strong L2, F frozen) |
| C | **X2 "stand-replacing loss" near hotspots includes land-use conversion** (housing, gravel pits) unless filtered | MEDIUM | **New** | Suburban hotspots are where repeat-visit panels are densest. LCMS fast loss also fires on development, so post-"cut" grouse loss would be read as an age effect. Fix: LCMS Land Use forest → forest filter (adopted in §6) |
| C | X2 power is unknown | LOW | Still-open (C admits it) | Counted on day 1 |
| **D: COVERT-X** | Location-derived effort covariates and adversary | — | **Fixed** (D accepted) | — |
| D | **Mode heads D_m are "shallow, shrunk" deviations**, so ρ_mode ≥ 0.8 is close to guaranteed | MAJOR | **New** | D §3.6 step 2. The same cannot-fail mechanism as for B and C. The visual subset is also road-biased (gravel-picking birds; D notes this). Fix: fit the visual head unshrunk on its own subset and calibrate the 0.8 threshold by injection |
| D | The LSE-stencil custom objective uses a per-row Hessian that ignores cross-row terms | LOW | **New** | The diagonal approximation can slow or destabilise boosting. Stencil-averaged features (C, E) avoid it |
| D | The owner's scorecard has recall bias and n ≈ 30 | LOW | **New** | Adopted anyway, as a weak but independent scorer |
