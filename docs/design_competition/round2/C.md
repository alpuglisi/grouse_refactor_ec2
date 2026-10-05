# Design C (final): FLUSH-C, effort-standardised covert encounter rates from complete checklists, with a disturbance panel test and an infrastructure-blind embedding

*Designer C, round 2. Primary technique: morphological analysis (Zwicky box). Added this round: a red-team pass over all four competitors, a "what is left unshared?" differentiation matrix, and the natural-experiment (difference-in-differences) lens borrowed from econometrics. No repository file was edited.*

---

## 0. Changes from round 1

### 0.1 Fact updates that change the plan

- **The owner already has eBird EBD and Sampling Event Data (SED) access.** Every waiting phase is gone, and so are GBIF pseudo-checklists. Day 1 is EBD ingest, and the first decisive test runs in the first week on real complete checklists.
- **My round-1 GBIF claim needs one correction.** I re-checked the GBIF API on 2026-10-05:
  - GBIF eBird (EOD) rows carry `recordedBy` (the obsr ID), `eventDate` and coordinates;
  - they have **no** `eventID`, `eventTime`, `samplingProtocol` or `samplingEffort`.
  - Round 1 said complete checklists "cannot be rebuilt" from GBIF. That is true of *complete checklists with effort*. Location-day bags *can* be rebuilt, as E proposed and A and B verified. The point is now moot.
- **The Vermont GMNF acoustic release (Clarfeld et al. 2025) cannot be used for site-level validation as published.** I downloaded its file list and metadata from ScienceBase:
  - 50 sites in 2022 and 60 sites in 2023 (stated in the metadata);
  - the CSVs contain `pk_modeloutputid`, `start_date`, `start_time` and model scores;
  - they contain **no site ID and no coordinates**.
  - A, B and D all list it as an independent scorer. It is usable only after a data request to the USGS VT Cooperative Unit.

### 0.2 Answers to critiques of FLUSH-C

| Critique | From | Severity given | My disposition |
|---|---|---|---|
| The trajectory is incoherent. Ages are shifted while the AlphaEarth embedding is held fixed, and the embedding ends in 2024, so 2025–26 cuts look like intact forest | A | MAJOR | **Accepted and fixed** (§3.4). (1) **Fresh-cut override:** pixels disturbed after the embedding year (LCMS/Hansen 2025, OPERA DIST-ALERT 2025–26, adopted from D) get their embedding replaced by an age-conditional prototype. (2) **Age-conditional embedding transport:** for forecasts, each pixel's embedding is moved along the mean embedding trajectory of its stratum and age. A pre-registered back-test (2019 → 2024) decides whether the transport is trusted. If it fails, trajectories come from the clock-only sub-model. (3) The aef-loader documentation says the GCS / Source Cooperative copies cover **2017–2025**. That would remove one stale year. The Earth Engine catalog page still says 2017–2024, so 2025 availability is **unverified** until the owner lists the bucket. |
| The 10 m embedding can see birding infrastructure, and nothing pre-registered stops it becoming the main signal. An ablation on checklists cannot reveal covariate shift to off-trail forest | B | MAJOR | **Accepted and fixed** with three measures, all pre-registered (§3.3, §3.6). (1) **Infrastructure-masked disc means.** Pixels within 30 m of any mapped road, track, path, parking area or building are excluded from every embedding average, so trails and parking never enter the representation. (2) **An infrastructure-visibility probe.** If a classifier can tell "within 100 m of a trail" from the masked embedding features with AUC > 0.70, the embedding fails its gate. (3) **Importance-weighted evaluation to off-trail forest** (adopted from E) and B's control species. AlphaEarth is now a gated block, not the primary representation. |
| The kill test is scored only on checklists, so it has home advantage | B | MEDIUM | **Accepted.** I adopt B's cross-play matrix (§5.1). My H set stays the arena. |
| The training buffer around H (1 km) is smaller than the largest disc (2.4 km), so training and H share inputs | A | LOW | **Accepted.** The buffer is now 2.5 km. |
| "Balancing changes variance, not bias" holds only under correct specification | A | LOW | **Accepted.** The text is corrected. Balancing is reported as a sensitivity run (capped vs uncapped). |

### 0.3 Adopted from competitors (credited)

| Adopted | From | Use in FLUSH-C |
|---|---|---|
| Cross-play ("home and away") matrix | B | Primary label-effect comparison (§5.1) |
| Within-observer AUC; drop the top-2% grouse-reporting observers | B | Preferential-sampling module (§3.6) |
| Positive and negative control species (B's recasting of E's placebo test) | B, E | Effort-leak module. I change the statistic to *forest-only partial correlation*; see §9 for why B's raw ρ threshold misfires |
| Oracle-ratio honesty metric (achieved ÷ achievable AUC) | B | §5 |
| Observed/expected top-k lift TkL, with an effort-only model in the denominator | D | Primary hunter metric |
| OPERA DIST-ANN / DIST-ALERT for 2023–26 cuts; freshness audit of today's map | D | Fresh-cut override; experiment X3 |
| Access classes A1–A4/X; recommender with 1-in-5 random covert; gamma–Poisson covert update | D | Product (§3.7) |
| Zero-parameter heuristic baseline H₀ (share of a 250 m disc 5–20 yr post-cut) | A | Mandatory baseline in every table |
| Rule that **no location-derived covariate enters the effort term** | A, B | Hard constraint (§3.5). My round-1 hotspot flag in $g$ is **removed** |
| Royle–Nichols-style mean-normalised footprint; season-specific fall head Δ_fall | B, D, E | §3.5 |
| GPS hunt-log protocol and hunter-detectability multiplier fitted from logs | A | Season ledger (§3.7) |
| Importance weighting of evaluation to the forest population; forward-in-time test | E | §5 |
| "Hunt-able this October": a v0 product in time for the remaining 2026 season | A | Phase 2 (§7) |

### 0.4 Dropped

- Experiment A of round 1 (AlphaEarth under target-group labels). The project already measured the clock at +0.001 under those labels (CR-0032). An input test under the old labels says little about inputs under new labels.
- The raw Lift@5% metric. TkL replaces it.
- The hunter-κ calibration on NH regions as a headline number. It is shown only as a secondary label.
- The neural footprint gate as the main model. It becomes an optional phase. The main model is a one-row-per-checklist LightGBM (§3.5), which is cheaper and avoids the grouped custom objective.

---

## 1. Title and pitch

**FLUSH-C: a covert map of expected grouse encounters per standard hour, trained on eBird complete checklists, and tested by what happens to the same birding locations after the forest around them is cut.**

All five designs now share the core:
- complete checklists with non-detections;
- a separable effort term dropped at prediction;
- footprints;
- coverts;
- top-k lift.

FLUSH-C competes on what is not shared.

1. **A falsification test that preferential sampling cannot fake.** The **disturbance panel test** (X2) uses eBird locations that were birded repeatedly *before and after* a harvest within 300 m. A location fixed effect cancels three confounds:
   - everything constant about the site, including why birders chose it;
   - its fixed detectability;
   - its access.

   What remains is the within-site change in grouse encounter as the stand ages. The model must predict that change. A model that merely learned "where birders who find grouse go" fails it. No other design has a within-site causal-style test of the habitat function. The age response is also the exact quantity behind the "rising covert" product.
2. **The leak-free arena.** The H set lies inside the status-quo CNN's own validation blocks, with a 2.5 km training buffer. B and A adopted it. Combined with B's cross-play, it is the only fair comparison with today's map.
3. **A representation that adds new information without seeing infrastructure.** AlphaEarth embeddings are averaged *with roads, paths, parking and buildings masked out*, compressed by a PCA that commutes with averaging, and aged forward coherently. They enter only through a pre-registered gate.
4. **The lightest pipeline that still uses footprints.** There is one row per checklist with footprint-matched, precomputed multi-radius features and a LightGBM cloglog objective. One GPU is used only for disc filtering. Phase 1 runs in a week on real EBD.
5. **A product for this season.** v0 is out by about 20 October 2026. It ranks coverts within a drive radius. The recommender includes a randomised slot, and every logged hunt becomes a test label.

---

## 2. Brainstorming record (short)

**Round-1 Zwicky box (summary).** I used 10 dimensions:
- label source;
- estimand;
- negative design;
- modalities;
- scale;
- model family;
- loss;
- spatio-temporal structure;
- evaluation;
- product.

Each had 5–7 options. Eleven cross-consistency rules pruned the space; for example, presence-only × occupancy estimand, single-epoch lidar × the ±2-yr rule, and hunter aggregates as a 30 m label. I scored 12 configurations on gain, identifiability, feasibility and robustness. The winner was:
- labels: complete checklists;
- estimand: effort-standardised encounter rate;
- inputs: embeddings, clock and legacy layers;
- model: a GBM + MLP stack with a cloglog-offset loss;
- product: coverts.

That core is now shared by all five designs.

**Round-2 technique 1: red-team matrix.** For each competitor I asked three questions: what is its strongest claim, what concrete scenario breaks it, and can I verify the break? The findings are in §9. Two verified facts came out of it:
- the ARU release has no site coordinates;
- A's footprint *sum* with a non-negative distance slope cannot correct an area ∝ distance² scaling.

**Round-2 technique 2: the "unshared dimensions" Zwicky box.** I re-ran the box on only the dimensions where designs still differ. A design wins by owning cells nobody else occupies.

| Dimension | Options seen across A, B, D, E | Unoccupied or weakly occupied option → FLUSH-C |
|---|---|---|
| Falsification logic | Simulation (B), cross-play (B), zero-fit prior map (A), field test (A, D, E) | **Within-site natural experiment (DiD on harvest events)** |
| Preferential-sampling control | Within-observer AUC (B), drop targeters (B), shape constraints (A), importance weights (E) | **Location fixed effects** via the panel test, plus **first-visit sensitivity** |
| Habitat-dependent detectability | Fall head (B, D), hunter transfer term (A), season-split ranking (B) | **Season-conditioned footprint radius**: spring drums are heard far, fall flushes are close. Fitted, not assumed |
| New information in inputs | Clock (all), lidar (A, D), optional embeddings (A, B) | **Infrastructure-masked embeddings with coherent ageing** |
| Feasibility | NUTS posterior (A), grouped custom objective (B, D), 36 GB/yr cube (E) | **One-row-per-checklist footprint matching; a PCA-before-mean storage trick** |
| Honesty | Oracle ratio (B), power statements (A) | **Pre-registered probability of success per claim** and a published minimum detectable effect |

**Round-2 technique 3: econometric analogy.** A logged forest stand is a "treatment". An eBird hotspot is a "panel unit". Effort per visit is a "time-varying control". This gives the panel test with almost no new code, because LCMS/Hansen sampling already exists in `diagnose_disturbance_features.py`.

---

## 3. The design

### 3.1 Data sources

| Role | Dataset | Access | Status |
|---|---|---|---|
| Labels + effort | eBird EBD + SED, US-ME/NH/VT plus 10 km border strips, **2010–2025** (2010+ only for the panel test) | Owner has access | — |
| Succession clock | LCMS v2024-10 Change (Tree Removal, other loss, 1985–2024); Hansen GFC v1.12 `lossyear` 2001–2024; OPERA DIST-ANN 2023–24 / DIST-ALERT 2025–26 | Earth Engine; LP DAAC | LCMS and Hansen catalogs verified (round 1). OPERA from D, verified by D |
| Embeddings (gated) | AlphaEarth Satellite Embedding V1, 10 m, 64-d, unit length, CC-BY 4.0 | EE `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` (2017–2024 on the catalog page); COGs on GCS (requester pays) and Source Cooperative (free), with the `aef-loader` index | Catalog verified. The **2025 layer on Source Cooperative is unverified** (aef-loader docs say 2017–2025) |
| Infrastructure mask | OSM `highway=*` (all, including track/path/footway), `amenity=parking`; Microsoft US Building Footprints; NLCD developed classes; TIGER 2023 roads (already in the repo) | Geofabrik extracts | OSM and NLCD are standard. **The building footprint URL is unverified** |
| Legacy features | The 15 layers + `mch_*`, after the CR-0035 registration repair | On EC2 | — |
| Context | Elevation (3DEP 10 m); Daymet V4 winter SWE | EE | **Daymet asset ID unverified** |
| Access | PAD-US 4.x; state WMA layers; NH Current Use (D) | Public | From D |
| External | NH regional flush/observation rates (Small Game Summary; 403 to automated fetch, so **contents unverified**); owner GPS hunt logs; VT GMNF ARU (**needs a site-coordinate request**, verified absent from the public CSVs) | — | — |

### 3.2 Estimand

For a covert or cell $s$ in hunting season $T$:

$$\mu^{*}_{\text{fall}}(s,T)=\exp\big(g(w^{*})\big)\cdot\overline{\exp\big(f(x,T)+\Delta_{\text{fall}}(x,T)\big)}^{\,K^{*}(s)},\qquad p^{*}=1-e^{-\mu^{*}},$$

where:
- $w^{*}$ = one median-skill observer, traveling, 60 min, 2 km, 15 October, 08:00;
- $K^{*}$ = the 2-km-walk fall footprint (§3.5);
- the overline denotes a mean, not a sum, over the footprint.

This is the expected number of grouse encounters on a standard fall hour on foot, and $p^{*}$ is the chance of at least one. Rankings depend only on $f+\Delta_{\text{fall}}$ pooled over $K^{*}$. Absolute values are identified by non-detections. A *hunter* flush rate is a scalar multiple that only hunt logs and NH rates can estimate. It is displayed, never used for ranking.

### 3.3 Features (all year-indexed, no future information)

Radii are $r\in\{60,150,300,600,1200,2400\}$ m.

1. **Clock.** Fused last-disturbance year: the median of the products that fire within ±1 yr, with a source-agreement count kept. From it:
   - age-class shares {0–4, 5–10, 11–15, 16–25, 26–40, >40/never} at each $r$;
   - age-class Shannon diversity;
   - young/mature edge density at 300 m.

   Partial-cut evidence comes from LCMS slow loss.
2. **Legacy.** `diagnose_gbm_baseline.py` neighbourhood summaries of the 15 layers + `mch_*`. These exist only up to 960 m, the 64-px window.
3. **Gated embedding block.**
   - **Masked mean:** $\bar a_r(s,t)=\sum_{u\in B_r(s)}m(u)\,a(u,t)\big/\sum_{u\in B_r(s)}m(u)$, where $m(u)=0$ within 30 m of any mapped road, track, path, parking area or building, or on NLCD developed.
   - **PCA before averaging:** $\bar a$ is stored as $P\bar a$ with $P$ the top-16 principal axes, fitted on 10⁶ random forest pixels. Averaging is linear, so $\overline{Pa}=P\bar a$, and the disc filter runs on 16 bands instead of 64.
   - **Heterogeneity:** $H_r=1-\lVert\bar a_r\rVert$, a cheap interspersion index, computed from a 17th band holding the masked unit vectors' norm accumulator.
   - **Year-on-year change:** $1-\cos(\bar a_r(t),\bar a_r(t-1))$.
   - Storage is about 16 × 6 + 12 ≈ 110 bands at 60 m ≈ 8 GB/year as float16.
4. **Context.** Elevation, winter SWE and growing degree days at 1 km.

Grid discipline follows the PA lessons from BUG-0094/0095/0096:
- all rasters go on the LANDFIRE template lattice with explicit `crsTransform`;
- AlphaEarth COGs are reprojected with an exact (non-approximate) transformer;
- the `grid_mismatch` and `check_layer_registration.py` gates run before use.

### 3.4 Freshness and coherent forecasting of the embedding (answers A)

**Strata.** Let $k(u)$ = forest guild (TreeMap/EVT crosswalk) × biophysical region, and $\alpha(u,t)$ = fused age. From all forest pixels in 2017–2025 (hundreds of millions), estimate the stratum-age mean embedding $\mu_{k,\alpha}$ and its sample count.

- **Fresh-cut override.** Let $y_e$ be the last embedding year, and suppose a pixel was disturbed after $y_e$ (LCMS/Hansen, or OPERA DIST-ALERT for 2025–26). Then $a_T(u)=\mu_{k(u),\,T-y_d}$, where $y_d$ is the disturbance year and $k$ is the pre-cut guild.
- **Transport for forecasts** ($T>y_e$, undisturbed since $y_e$):
  $$a_T(u)=\operatorname{normalize}\big(a_{y_e}(u)+\mu_{k,\alpha+T-y_e}-\mu_{k,\alpha}\big).$$
  The pixel keeps its own deviation from its stratum and moves along the stratum's average ageing path.
- **Back-test (pre-registered).** Transport the 2019 embeddings to 2024 and compare with the real 2024 embeddings. Two measures:
  - per-pixel cosine;
  - Kendall τ of the top-500 covert ranking, transported vs real.

  **Pass if τ ≥ 0.80.** If it fails, the product's trajectories (+1…+5 yr) come from a **clock-only sub-model**, which has no embedding block and so cannot be incoherent. The current-season map still uses the override.

### 3.5 Model

**Footprint matching (one row per checklist).** Checklist $j$ has distance $L_j$, season $\varsigma_j$ ∈ {spring Apr–Jun, summer Jul–Aug, fall Sep–Dec, winter} and protocol $\pi_j$. It reads features at the radius

$$r_j=\text{nearest in }\mathcal R\ \text{to}\ \rho_{\varsigma}+L_j/2 .$$

- $\rho_{\varsigma}$ is the **season-specific detection radius**.
- It is chosen from {60, 150, 300, 600} m by held-out deviance, separately for each season.
- The hypothesis, which is fitted rather than assumed: spring $\rho$ is large because drums carry, and fall $\rho$ is small because flushes are close.

This is how FLUSH-C handles the main mechanism of habitat-dependent detectability. The spatial support of the evidence differs by detection channel, and the hunter map uses the fall support. Every feature is the masked *mean* over the disc, so footprint size never inflates the expected count. (A's sum-based footprint does; see §9.)

**Likelihood.**

$$\eta_j=F\big(x_{r_j}(s_j,t_j)\big)+\Delta_{\text{fall}}\big(x_{r_j}\big)\,\mathbb 1[\varsigma_j=\text{fall}]+g(w_j),\qquad P(y_j=1)=1-\exp(-e^{\eta_j}).$$

- **$F$**: LightGBM with a custom cloglog objective. There is one row per checklist, so the gradient $e^{\eta}(1-y/p)$ and Hessian are row-wise, and no grouped objective is needed. $g$ enters as `init_score` and is alternated with a GAM refit, 3–5 rounds (D's alternation).
- **$\Delta_{\text{fall}}$** (B, D): depth ≤ 3, strong L2, fitted on Sep–Dec checklists with $F$ frozen.
- **$g$**: a penalised GAM in **event-only** covariates:
  - log duration and log(1+distance), monotone non-negative;
  - protocol and party size;
  - start-time spline and cyclic day-of-year spline;
  - year;
  - out-of-fold observer skill (Kelling et al. 2015);
  - observer random effect for observers with ≥ 20 checklists.

  **No location-derived variable** is allowed (A, B rule): no hotspot flag, no road distance, no checklist density.
- **Spatio-temporal capping.** At most 10 checklists per (3 km cell × week × detection status), resampled per boosting run (Johnston et al. 2021). This is a variance and focus device. Under misspecification it also changes the fitted function, so the uncapped fit is reported alongside (A's LOW).
- **Ensemble.** 5 spatial folds × 2 seeds. The spread of $\log\mu^{*}$ is the epistemic interval. Coverts outside the training envelope (PCA-20 Mahalanobis > 99th percentile) are flagged.
- **Optional phase.** A small PyTorch model with a learned soft gate over radii, conditioned on season and distance (my round-1 gate). It is kept only if it beats the GBM by ≥ 0.01 effort-stratified AUC on H.

### 3.6 Robustness modules (pre-registered, committed as acceptance code; CR-0011 A3)

**PS: preferential sampling.**
1. **Panel test X2** (§6). Location fixed effects remove site-level selection. This is the decisive test.
2. **Within-observer AUC** (B).
3. **First-visit sensitivity.** Refit on each observer's first checklist at each location. "Returned because I found grouse here" cannot act on a first visit. Pass if covert-rank Spearman ≥ 0.9 against the full model.
4. **Drop targeters** (B): remove the top 2% of observers by out-of-fold grouse reporting rate.

**EL: effort leakage into habitat.**
1. **Control species** (B, E) through the identical pipeline:
   - positive controls: Chestnut-sided Warbler, Eastern Towhee, both young-forest birds detected by song at the same times as drumming;
   - negative controls: Black-capped Chickadee, Blue Jay.

   I prefer Eastern Towhee to B's woodcock, because woodcock are detected at dusk in open fields, a different channel. *Statistic:* the **partial** Spearman correlation between maps over **forest pixels only**, controlling for tree canopy cover. *Pass:* partial ρ(grouse, negative) < partial ρ(grouse, positive) − 0.15, with the margin calibrated in the injection simulation (§6, X0).
2. **Infrastructure probe** for the embedding block: masked-feature AUC for "within 100 m of a trail or road" must be ≤ 0.70.
3. **Effort probe** (D): the R² of the final $f$ map regressed on hotspot distance, trail distance and checklist density, over random forest pixels. It must not exceed the clock-only model's R² by more than 0.02.

**DT: habitat-dependent detectability.**
1. **Season-specific radius** $\rho_\varsigma$ (above).
2. **Spring vs fall ranking agreement.** If covert Spearman between $F$ and $F+\Delta_{\text{fall}}$ is < 0.8, rank by fall and badge the covert.
3. **Hunter multiplier** from logs from season 2 (A, B): $W(s)=W_0e^{\omega\,\text{under}(s)}$.
4. **Panel caveat.** A fresh cut changes visibility as well as abundance. X2 reports the 0–4-yr bin separately, because detectability changes most there, and puts its weight on the 5–25-yr bins.

**AEF gate.** The embedding block is kept only if all of the following hold:
- (i) it improves H-set deviance and fall TkL₅ (block-bootstrap lower CI > 0);
- (ii) it passes EL1–EL3;
- (iii) it passes the transport back-test, or else trajectories use the clock-only model;
- (iv) its importance-weighted (off-trail) TkL is not worse than without it.

### 3.7 Inference and end product

1. **Prediction grid.** A 60 m grid on the template lattice. Features come from the same masked disc filters, at the fall radius matched to a 2 km walk. Run time is GPU FFT disc filtering plus LightGBM prediction, a few hours per state-year.
2. **Coverts** (D's three-source scheme, kept):
   - disturbance patches aged 4–25 yr;
   - SLIC segments on (age, PCA-4 embedding, `mch`);
   - a 25 ha hexagon background.

   Sizes run 2–40 ha.
3. **Covert card:**
   - $p^{*}$ and $\mu^{*}$ with an 80% interval;
   - a **peak window** from the clock, with trajectory +1…+5 yr (transport or clock-only, per §3.4);
   - access class A1–A4/X (D) and walk-in distance;
   - top-3 reasons (TreeSHAP);
   - badges for **fresh cut** (0–4 yr), **spring/fall disagree**, **extrapolated** and **near hotspot** (B's artefact badge).
4. **Daily list** (D). Five coverts within a drive radius: four by Thompson sampling over the fold ensemble, plus one uniformly random from the accessible top 30%. Output is GPX/KML for onX, Gaia or Avenza, and an optional 60–120-min loop from parking (A's planner, simplified to a greedy path).
5. **Season ledger.**
   - *Protocol:* the owner logs each hunt as a GPX track plus flush waypoints, or as an eBird checklist with a "hunt" note.
   - *Within season:* a gamma–Poisson covert effect updates immediately.
   - *After the season:* $F$, $g$ and $W$ are refit.
   - The random-slot hunts give an unbiased realised-lift estimate.
6. **Season outlook.** Regional year level from NH drumming and brood reports, where published.

---

## 4. Why it beats the status quo and the other four

**Against the status quo.** These tie to the report's diagnosis.

| Report diagnosis | FLUSH-C |
|---|---|
| "The data is the ceiling" (GBM ≈ CNN; clock +0.001, GEDI +0.000 under target-group labels) | It changes the labels, the only unpulled lever, and only then adds new inputs. Inputs are gated on the new labels, never the old |
| PU contamination and the $1-a/2$ bound | Observed non-detections with effort; no background is drawn |
| Effort bias (`road_dist` encodes birding, §5.3) | Effort is modelled by event-only covariates and fixed at prediction. Road distance is in neither term. Infrastructure is masked from the embedding |
| The estimand is a density ratio tied to 50:50 | An absolute fall encounter rate per standard hour |
| Location error (§2.4.1) | Season-specific footprint radius matched to distance |
| Static 2020–24 map and the ±2-yr rule | Annual inputs from 2017 (2010 for the panel), fresh-cut override to 2026, coherent forecasts |
| No external check (§5.6) | Panel test, cross-play, and randomised hunt logs |

**Against the other designs.** I name only the unshared points.

- **A (CYM)** stakes everything on a mechanistic form being right. FLUSH-C tests that form's central claim (the age response) inside a flexible model with X2. The shape constraints are then a fallback, not an article of faith. A's sum-footprint also under-ranks big woods (§9).
- **B (CEM-X)** has the best evaluation machinery, and I adopted most of it. Its inputs are the legacy lens plus the clock, and its falsification is still between-site. X2 is within-site, and FLUSH-C's gated embedding is the only input that adds information neither the clock nor LANDFIRE carries: annual 10 m phenology and texture.
- **D (COVERT)** puts location-derived variables in the effort term, which deletes real habitat signal, and relies on validation streams that are not available as published (§9).
- **E (FLUSH-E)** has a heavy 36 GB/yr per-pixel cube, and no leak-free comparison with the CNN map.

---

## 5. Expected gains, measured without fooling ourselves

### 5.1 Arenas and metrics

**Arenas.**
- **H set:** all complete checklists whose start lies in a *validation* block of the existing 3 km split (`SPLIT_SEED=42`). All FLUSH-C training excludes checklists within **2.5 km** of any H block.
- **Internal CV:** 25 km blocks over the rest, checked against the residual variogram.

**Cross-play** (B). There are two models with the same features:
- M_TG: target-group labels (`diagnose_gbm_baseline.py`);
- M_CL: checklist labels.

Each is scored at home and away: on T_TG (the existing validation set) and on H (checklists). The CNN map is scored on both as a third row. **The label thesis passes** if M_TG's away deficit on H exceeds M_CL's away deficit on T_TG by ≥ 0.02 effort-stratified AUC (lower CI > 0).

**Metrics on H.**
- **Primary:** fall TkL₅, the ratio of observed to effort-only-expected detections among Sep–Dec checklists in the top 5% of held-out forest.
- **Secondary:**
  - effort-stratified AUC;
  - within-observer AUC;
  - log-loss;
  - **oracle ratio** = achieved AUC ÷ AUC under labels simulated from the model's own probabilities (B);
  - importance-weighted (off-trail forest) TkL (E).

**Baselines in every table:**
- H₀ (zero-parameter clock heuristic, A);
- the CNN map;
- M_TG;
- clock-only M_CL;
- full M_CL with and without the embedding block.

**Statistics.** Paired block bootstrap over 3 km blocks with 1,000 resamples. Differences under the **minimum detectable effect** are ties. The MDE comes from the injection simulation X0; I expect about 0.01 AUC and about 0.15× TkL. All decision thresholds are committed before any fit.

### 5.2 Expected values and probability of success

These are priors, written so they can be scored later.

| Claim | Expected | P(true) |
|---|---|---|
| Label thesis passes cross-play (≥ 0.02) | M_CL away deficit 0.02–0.06 smaller | 0.65 |
| Fall TkL₅ on H: M_CL (clock + legacy) vs CNN map | 2.0–2.8× vs 1.4–2.0× | 0.60 that the gap is ≥ 0.3× |
| Effort-stratified AUC on H, M_CL vs CNN map | +0.02 to +0.06 (0.68–0.75 vs 0.64–0.70) | 0.60 |
| Oracle ratio of M_CL | 0.85–0.95; the achievable ceiling itself is probably only 0.72–0.80 because detections are Bernoulli-noisy | — |
| Embedding block passes the full gate | ΔTkL₅ +0.1 to +0.4× when it passes | **0.40** (honestly uncertain; B puts it at 0.35) |
| Panel test X2 shows the predicted hump (5–15 yr above 0–4 and >25 yr), with model-predicted Δ slope > 0 | — | 0.55; **power uncertain** until treated-site counts are known (X2 step 1) |
| Full-model AUC with effort | 0.80–0.88, mostly effort and season; **never claimed as habitat skill** | — |
| Owner's random-slot lift, 2026 remainder | Not decisive this season: about 20–40 h is underpowered for < 1.6× (A's power arithmetic) | — |

---

## 6. Risks, failure modes and the falsification ladder

| ID | When | Experiment | Kill / pass rule |
|---|---|---|---|
| **X0** | Days 1–2 | **Injection–recovery on real EBD geometry** (B's method). Plant (i) a hazard-shaped truth and (ii) a thinned-IPP truth into the real checklist locations, years and efforts, with a preferential-sampling variant in which visit probability falls in dense young cover (A's re-aim). Run M_TG, M_CL and the cross-play | Calibrates the MDE, the cross-play symmetry assumption and the EL margin. If M_CL cannot beat M_TG on truth (i) by more than the MDE, the arena has no power, and that is reported before any real result |
| **X1** | Days 3–5 | **Cross-play + H set**, clock + legacy features, no embeddings | **Fail** (difference ≤ 0.005, or TkL₅ gap CI includes 0): stop the checklist model, ship today's map with access and freshness layers only, and say so |
| **X2** | Week 2 | **Disturbance panel test** (below) | **Fail** (predicted-Δ slope ≤ 0 with CI excluding the pass value, given adequate power): the habitat function is between-site confounded, and coverts get an "unvalidated" badge. Underpowered: reported as such, no claim |
| X3 | Week 1, parallel | Freshness audit of today's map (D): the share of top-5% pixels cut 2023–26, or aged past 30 yr by 2026 | No kill; quantifies stale-map error |
| X4 | Week 3 | AlphaEarth gate (§3.6) | Block dropped if any gate fails |
| X5 | Season | Randomised hunt-log lift | Accumulates across seasons |

**X2: disturbance panel test (unique to FLUSH-C).**
1. *Units.* eBird locations (`LOCALITY ID`) with ≥ 8 complete checklists in a pre window (before the cut) **and** ≥ 8 in a post window. "Treated" means a fused stand-replacing loss covering ≥ 10% of the 300 m disc in year $y_0$, with $2005\le y_0\le 2019$ and checklists 2010–2025. Controls are locations with no loss within 600 m. Step 1 is simply to count treated units and compute power. Thousands of forest locations with repeat visits plausibly exist, but this is **unverified**.
2. *Model.*
   $$\text{cloglog}\,P(y_{j})=\gamma_{\ell(j)}+\tau_{\text{year}}+g(w_j)+\sum_{b}\beta_b\,\mathbb 1[\text{age bin of the cut at }t_j=b]\cdot\text{share}_{300}$$
   - $\gamma_\ell$ is a location fixed effect. It removes site choice, fixed detectability and access.
   - Bins are 0–4, 5–15, 16–25 and > 25 yr.
3. *Model check.* For each treated location, compute FLUSH-C's predicted change $\Delta\hat\eta_\ell=\hat F(x_{\text{post}})-\hat F(x_{\text{pre}})$. Then regress the within-location observed change on $\Delta\hat\eta_\ell$ in a fixed-effects GLM. **Pass:** slope > 0, with lower CI > 0. A slope near 1 means the model's habitat contrasts are the right size.
4. *Reading.* This is the only test in any design where a model that learned "places birders who find grouse go to" **cannot** pass, because those places' fixed traits are differenced out. The DT caveat (visibility changes after a cut) is handled by weighting the 5–25-yr bins.

**Main risks.**

| Risk | Severity | Mitigation |
|---|---|---|
| Few fall detections | MEDIUM | B counted about 5.8k Sep–Dec GBIF grouse records for 2020–24, so EBD fall detections should be enough for a shallow Δ_fall |
| The embedding leaks infrastructure that the mask misses (unmapped skid trails) | MEDIUM | Probe EL2; off-trail importance-weighted TkL; the gate drops the block |
| Clock misses partial harvest (Maine shelterwood) | MAJOR (shared by all designs) | LCMS slow loss; the embedding change band; the lidar `under` metric deferred to phase 4 |
| X2 underpowered | MEDIUM | Reported honestly. Pooling more years (2005+ cuts with Hansen) or 600 m discs raises the treated-unit count |
| EBD terms forbid redistributing raw data | LOW | Product is for personal use; no raw EBD published |
| QMS overhead | process | One CR per phase; acceptance scripts (X0–X4 thresholds) committed first |

---

## 7. Implementation plan (one owner, one EC2 GPU)

| Phase | Work | Effort | CR scope |
|---|---|---|---|
| **Day 1** | EBD/SED ingest with polars streaming. Filters: complete; stationary/traveling; ≤ 5 h; ≤ 5 km; ≤ 10 observers; group-deduplicated; 2010–2025. Zero-fill grouse. Attach the H flag and the 2.5 km buffer. Report counts by state, season and year. Commit X0–X2 acceptance thresholds | 1 d | acceptance-design CR (thresholds) + data CR |
| **Days 1–2** | Clock rasters: LCMS/Hansen/OPERA fused on the template lattice (EE export with `crsTransform`; registration gate). Multi-radius age shares on the GPU. Legacy footprint features through the existing patch reader | 1–2 d | generator CR |
| Days 1–2 | **X0** injection simulation | 1 d | gate code |
| **Days 3–5** | M_TG and M_CL (LightGBM cloglog, $g$ GAM alternation), **X1** cross-play on H, **X3** | 2–3 d | model CR |
| **Week 2** | **X2** panel test. **v0 product** (clock + legacy M_CL), coverts, access, daily list, GPX, live for the rest of the 2026 season (about 20 Oct) | 4–5 d | product CR |
| Week 3 | AlphaEarth: Source Cooperative / GCS COGs → masked, PCA-16 disc means (GPU FFT), override and transport, back-test, **X4** gate | 4–5 d | generator CR |
| Week 4 | PS/EL/DT modules complete; v1 product if the embedding passes | 3 d | — |
| Season and later | Ledger, refit, lidar `under` (phase 4), optional neural gate | ongoing | separate CRs |

**Compute budget.**
- The checklist table is about 1–2 M rows × about 400 features, roughly 3 GB as float32. LightGBM fits on CPU in minutes.
- Disc filters: about 110 bands × 6 radii per year on the GPU, chunked with a 2.4 km halo, about 1 h per state-year.
- Storage: about 8 GB/year (embeddings) plus about 2 GB (clock).
- Nothing needs NUTS, a grouped objective or a per-pixel cube.

**The first experiment the owner can run today:** Day 1 ingest plus the counts. X1 is ready by day 5.

---

## 8. References

These were verified during rounds 1–2 unless marked.

- eBird EBD / SED; `auk`: https://docs.ropensci.org/auk/articles/auk.html
- GBIF eBird Observation Dataset API fields (`recordedBy`, `eventDate` present; `eventID`, effort absent), checked 2026-10-05: https://api.gbif.org/v1/occurrence/search?datasetKey=4fa7b334-ce0d-4e88-aaae-2e0c138d049e
- AlphaEarth Satellite Embedding V1 catalog: https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL ; GCS copy readme: https://developers.google.com/earth-engine/guides/aef_on_gcs_readme ; `aef-loader` (GCS requester-pays and free Source Cooperative copies; "2017 to 2025"): https://aef-loader.readthedocs.io/en/latest/ (the 2025 layer is **unverified**)
- LCMS v2024-10: https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10
- Hansen GFC v1.12: https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12
- OPERA DIST-ANN-HLS V1 (via D): https://developers.google.com/earth-engine/datasets/catalog/OPERA_DIST_L3_DIST-ANN-HLS_V1
- Clarfeld, L.A. et al. (2025), Ruffed Grouse two-stage ML, GMNF VT. USGS data release doi:10.5066/P13EFLXX ; ScienceBase item https://www.sciencebase.gov/catalog/item/679392d5d34e88f5864c50b5 . The files and metadata were inspected: 50/60 sites, **no site ID or coordinates in the CSVs**.
- Johnston, A. et al. (2021). *Diversity and Distributions* 27:1265–1277. doi:10.1111/ddi.13271 (open copy https://par.nsf.gov/servlets/purl/10332329)
- Kelling, S. et al. (2015). *PLOS ONE* 10:e0139600. doi:10.1371/journal.pone.0139600
- Lipsitch, M., Tchetgen Tchetgen, E., Cohen, T. (2010). Negative controls. *Epidemiology* 21:383–388 (**from memory, unverified**; via B)
- Angrist, J.D., Pischke, J.-S. (2009). *Mostly Harmless Econometrics*, ch. 5, on fixed effects and DiD (**from memory**)
- Koleck et al. (2026). PA ARU + LiDAR, Dryad doi:10.5061/dryad.hmgqnk9xh (coordinates obscured, verified round 1)
- NH Fish & Game Small Game Summary: https://www.wildlife.nh.gov/sites/g/files/ehbemt746/files/inline-documents/sonh/small-game-summary.pdf (403 to automated fetch; **contents unverified**)
- USGS 3DEP state fact sheets (VT, NH, ME): https://pubs.usgs.gov/publication/fs20253033 ; https://pubs.usgs.gov/publication/fs20243056 ; https://pubs.usgs.gov/publication/fs20233036
- Microsoft US Building Footprints: https://github.com/microsoft/USBuildingFootprints (**URL from memory, unverified**)
- PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview
- LightGBM custom objective / `init_score`; sklearn HistGradientBoosting `interaction_cst` (**parameter names from memory**)
- Repository: `docs/grouse_model_report.md` §1–§5; `diagnose_disturbance_features.py`; `diagnose_gbm_baseline.py`; `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md` (clock +0.001, GEDI +0.000, Meta CHM +0.009 under target-group labels)

---

## 9. Critique of competitors

| Design | Flaw | Severity | Evidence / failure scenario |
|---|---|---|---|
| **A (CYM, round 2)** | **The footprint is a *sum* over a disc whose radius grows with distance, while the distance slope in $g$ is constrained non-negative.** The expected count therefore scales with area ∝ (150 m + d/2)², not with a walk's swept length ∝ d. The model cannot correct this. To explain why long walks detect fewer grouse than predicted, it must lower $D$ in the habitat long walks traverse, which is remote big woods: the hunter's target | **MAJOR** | A §3.4 O1: $\sum_{s\in B_i}D\,A_{\text{cell}}$ with $\alpha_2^{+}\log(1+\text{dist})$. Worked example: d = 4 km gives disc area 14.5 km²; d = 0.5 km gives 0.50 km². That is a 29× ratio against about 8× in swept length. With $\alpha_2\ge0$ the excess cannot be absorbed. Fix: use the disc mean (as B, C, E do) or let $\alpha_2$ be negative |
| A | The 2026 "blinded" field test cannot blind the hunter: young cuts are visible, and effort inside a covert follows what it looks like. The season opened on 1 Oct, so about 40 h/arm is hard to reach, and A's own arithmetic says that detects only ≥ 1.5× | MEDIUM | A §5.3 and §3.4 |
| A | Its independent ARU validation is not usable as published | MEDIUM | Verified: ScienceBase CSVs have no site ID or coordinates |
| **B (CEM-X, round 2)** | **The negative-control gate uses a raw map correlation ρ ≤ 0.3 between grouse and Black-capped Chickadee / Blue Jay.** Both are forest birds. Any correct grouse map shares their forest-vs-nonforest contrast, so ρ > 0.3 for legitimate reasons. The gate can then falsely reject a real habitat input (for example the embedding) or misreport contamination. The positive control American Woodcock is detected at dusk in open singing grounds, a different detection channel, so it can fail for detectability reasons | MEDIUM | B §3.5 R-EL table. Fix (adopted in C §3.6): forest-only partial correlation, a song-detected young-forest control (Eastern Towhee), and a margin calibrated by injection |
| B | The falsification ladder is still entirely *between-site*. Within-observer AUC cancels observer selection but not *site* selection by the same observer; B's repeat-visit trend check is the only within-site element. No test differences out fixed site traits | MEDIUM | B §3.5 R-PS. Addressed by C's X2 |
| B | The phases built around GBIF pseudo-checklists are now moot (the owner has EBD). Not a flaw of the design, just dead weight in the plan | LOW | Fact update |
| **D (COVERT, round 1)** | **Location-derived covariates in the effort term** (hotspot distance, trail distance, checklist density within 1 km), which are then set to the "non-hotspot forest median". These covariates correlate with remoteness, which correlates with grouse (positives 2–5× farther from roads; report §5.3). $g$ absorbs that habitat signal, and the signal is deleted at prediction, flattening the remote-forest contrast the hunter needs. The gradient-reversal adversary removes more. Its strength is chosen on "independent validation" that is not available: the ARU CSVs lack coordinates, and the GPS logs need a season | **MAJOR** | D §3.2.1 and §3.6. ARU check verified (ScienceBase file list and metadata). A and B independently reached the same conclusion about location-derived $g$ |
| D | Its own Phase-1 falsification gate needs the ARU Spearman, which cannot be computed without a data request | MEDIUM | Same evidence |
| **E (FLUSH-E, round 1)** | **No leak-free comparison with today's map.** B0 scores the CNN at checklist locations inside 25 km hexes unrelated to the CNN's split, so most test checklists sit in the CNN's *training* blocks, often at the very hotspots whose grouse records were its positives. The report shows how big that inflation is: random-split AUC was 0.82–0.89 against 0.76–0.78 with blocks. The CNN baseline is inflated, which biases E's falsification toward "the current map already captures it" | **MAJOR** | E §3.7 baselines and §6. Report §5.3. Fix: the H set |
| E | Day-1 pseudo-checklist test conditions on the bag's own species count, which is habitat-dependent and post-treatment (B's point). Now moot with EBD | LOW (moot) | E §7 |
| E | A per-pixel feature cube of about 36 GB/year over a 2010–2025 span is heavy for one owner. Forecasts hold composition fixed while ageing the clock (the same incoherence A raised against me), and E has no back-test | MEDIUM | E §3.4 and §7 |
