# Design B, round 2: CEM-X, the cross-examined Checklist Encounter Model

*Designer B, final proposal. Techniques:*

- *primary (round 1): analogical transfer;*
- *added this round: adversarial cross-play ("home and away" evaluation, borrowed from sports ratings and from epidemiology's negative-control designs) and a red-team pass over all five round-1 designs.*

*No repository file was edited. Every fact marked "verified" was checked this round against the GBIF API, the repository or the web.*

---

## 0. Changes from round 1

### 0.1 What stays

The shared core stays:

- eBird complete checklists as test-negative controls;
- a cloglog hazard with a separable effort tower that is dropped at prediction;
- footprint pooling;
- a standardised encounter-rate estimand.

All five designs now share this core, so this document competes on what they do not share.

### 0.2 Adopted from competitors (credited)

| Adopted | From | Why it is better than what I had |
|---|---|---|
| **Verified that the existing GBIF route cannot produce checklists** (no `eventID`, time or effort fields; checked via the GBIF API, §3.1) | C (claim) | Confirms that EBD + Sampling Event Data, which the owner already has, is the only label source. The pseudo-checklist workaround (E) is unnecessary and is not used. |
| **Effort-expected denominator in top-k lift** (TkL = observed / effort-only-expected detections) | D | My round-1 M3 divided by a raw mean, so hotspot effort could inflate it. D's form cannot be gamed by effort. |
| **Zero-parameter heuristic baseline H** (share of a 250 m radius in 5–20-year post-cut forest), reported everywhere | A | If a learned model cannot beat H, the learning added nothing. This is the cheapest guard against self-deception. |
| **Succession clock** (LCMS / Hansen year-of-loss, aged to the target season) and a "peak window" per covert | A, D, E | The hunter needs this season's map, and the clock is deterministic. I had kept the stale LANDFIRE `tsd` only. |
| **Head-to-head test set inside the status-quo validation blocks, with a training buffer** | C (the H set) | It is the only way to score the old CNN and the new model on locations neither model trained on. |
| **Independent drumming acoustic data from the Green Mountain National Forest** (Clarfeld et al. 2025, USGS data release doi:10.5066/P13EFLXX; verified to exist, but coordinate release is unverified) | D | This is an independent scorer the model never trains on. |
| **Randomised exploration arm in the recommender** (1 of 5 coverts drawn at random) | D | Turns the owner's season into an unbiased estimate of lift, not an anecdote. |
| **Placebo-species test** | E | Recast and strengthened as pre-registered *positive and negative control species* (§3.5). |
| **AlphaEarth embeddings** as a gated, optional input | C | It is cheap, annual, at 10 m and new information. It is gated because it may encode trail infrastructure (C's own risk R2). |
| **Fall-specific habitat head with shrinkage** | D | GBIF data show that fall records are numerous enough. I verified 5,774 Sep–Dec grouse records for 2020–24 (§3.1). |

### 0.3 Dropped

| Dropped | Why |
|---|---|
| A fully convolutional ResNet as the main habitat model | The report shows GBM ≈ CNN. One owner with one GPU should not spend weeks on a trunk whose prior chance of beating a tuned GBM by ≥ 0.01 I put at about 25%. It survives only as an optional last phase. |
| Round-1 F0 run on the target-group pool geometry | Superseded: the injection–recovery test now runs on real EBD complete-checklist geometry. |
| Any step that existed only to wait for EBD access | The owner already has EBD + SED access, so every first experiment uses real complete checklists from day 1. |
| Using the hotspot flag as anything but an effort covariate | See the critique of D in §9. Nothing derived from *location* enters the effort tower. |

---

## 1. Title and pitch

**CEM-X: the checklist encounter model, made to prove itself. It predicts grouse encounters per standard October hunting hour per covert, and it is built around one test that can kill it in week 1, on real complete checklists.**

Five designers independently reached the same core, and that agreement is evidence the core is right. The remaining open question is the one the owner actually faces: *will a map trained on effort-explicit checklists send me to more grouse than today's map, and how would I know before I have spent a season finding out?*

CEM-X answers it with three things the other designs lack.

1. **A label-swap cross-play test that runs in week 1 on real EBD complete checklists.**
   - Train the *same* features and the *same* GBM twice: once on today's target-group labels and once on EBD complete-checklist labels (detection/non-detection, with the effort tower).
   - Score both at home, away and on an independent field.
   - Training labels are the only difference, and home advantage is cancelled by design (§5.1).
   - If checklist labels do not win, the core thesis dies in week 1, for all five designs, at the cost of one CPU day.
2. **Robustness checks that keep the map from tracking where people bird.** Each one is pre-registered:
   - *Preferential sampling:* within-observer AUC, observer effects, drop-targeters sensitivity.
   - *Effort leakage:* positive and negative control species (epidemiology's negative-control outcomes, used here as a confound detector).
   - *Habitat-dependent detectability:* a fall head separate from the spring drumming head, with their disagreement shown on the map rather than averaged away.
3. **Plans sized to one owner with one GPU.**
   - The production model is a GBM with a custom cloglog footprint objective. A neural model is optional.
   - Every phase has a stop rule with an honest prior probability of passing (§5.3).
   - The product is a covert card that tells the hunter both the expected flushes per hour and how confident the model is that this number is not a birding artefact.

---

## 2. Brainstorming record (short)

**Round 1 (analogical transfer).** I listed 11 fields, each with its best trick. Ad click-through (PAL), recommender systems (ExpoMF), vaccine studies (test-negative design), under-reported disease (capture–recapture), fisheries (catch per unit effort), astronomy (injection–recovery), mineral prospectivity (success-rate curves), poaching prediction (iWare-E), fraud (top-k), oil and gas (risk segments and value of information), and multiple-instance learning. These converged on the checklist hazard model.

**Round 2, technique A: red-team cross-reading.** For every design, including mine, I asked: "what is the single result this design would report as a win that could be produced by an artefact?" Four answers recur:

- **Home advantage.** A checklist-trained model scored on held-out checklists. This affects all five designs.
- **Effort leaking into habitat.** Location-derived effort covariates, or embeddings that see trailheads. This affects D and C.
- **Preferential sampling.** Birders seek grouse spots. All five designs acknowledge it; none tests it directly.
- **Detectability confound.** Spring drumming is audible; fall birds are found by flushing. All five designs acknowledge it; none separates the two in the product.

**Round 2, technique B: analogical transfer again, aimed at these four artefacts.**

| Artefact | Field that already solved it | Trick transferred |
|---|---|---|
| Home advantage | Sports ratings, and cross-dataset evaluation in ML (train on A, test on B, and the reverse) | **Cross-play matrix**: each model plays home and away. The comparison is the *away deficit*, not the home score. |
| Effort leaking into habitat | Epidemiology: **negative-control outcomes** (Lipsitch, Tchetgen Tchetgen & Cohen 2010) | Control species with a known habitat relation run through the same pipeline. A habitat signal that also "predicts" a species living elsewhere is a confound. |
| Preferential sampling | Econometrics: **within-unit (fixed-effects) estimators**; epidemiology: case-crossover | **Within-observer AUC**. Compare only checklists of the same observer, so between-observer targeting and skill cancel. |
| Detectability that depends on habitat | Survey sampling: **mode effects** (phone and web surveys measure the same quantity differently) | Separate spring and fall "modes" with a shared core. Disagreement is reported as uncertainty, not averaged. |
| Unknown ceiling of the new task | Astronomy: injection–recovery; ML: **oracle / Bayes-rate bounds** | Simulate labels from the fitted model to obtain the *achievable* AUC on the test set, and report achieved ÷ achievable. |

**Convergence.** The core model is shared, so differentiation comes from these five transfers. Together they make a pre-registered evidence ladder (§6). That ladder is the main deliverable.

---

## 3. The design

### 3.1 Data (all access routes checked this round)

| Source | Status | Role |
|---|---|---|
| **GBIF eBird Observation Dataset** (`datasetKey 4fa7b334-…`, the project's existing `sightings.py` route) | **Verified via the GBIF API, 2026-10-05.** Records carry `recordedBy` (e.g. `obsr934582`), `eventDate` (date only), coordinates, `locality` and `individualCount`. `eventID`, `eventTime`, `samplingProtocol` and `samplingEffort` are all **absent**, so C's claim holds. 2020–24 bird records: VT 5.08 M, NH 4.73 M, ME 8.49 M. 2020–24 grouse records: VT 10,524, NH 5,941, ME 13,108 (29.6 k in total, before the pipeline collapses them to 6,232 positives). Grouse records by season: Apr–May 13,822; Jun–Aug 6,850; **Sep–Dec 5,774**; Jan–Mar 3,127. | Context only: confirms the existing pipeline cannot build checklists; seasonal counts size the fall head. |
| **eBird EBD + Sampling Event Data**, ME/NH/VT, 2016–present | **The owner already has access**; download now | Labels from day 1: true checklists with duration, distance, protocol, observers, time and the `ALL SPECIES REPORTED` flag. |
| Existing 15 layers + `mch_*`, **after the CR-0035 registration repair** | On EC2 | Habitat features (GBM design of `diagnose_gbm_baseline.py`, footprint-averaged). |
| LCMS v2024-10 fast/slow loss, Hansen GFC v1.12 `lossyear` | Earth Engine (catalog pages verified by A, C and D) | Succession clock: age since last loss, capped at 40 years, aged to the season. Exported on the template lattice with an explicit `crsTransform`; registration gate as in BUG-0094. |
| AlphaEarth Satellite Embedding V1 (2017–2024, 10 m, 64-d) | Earth Engine (verified by C) | **Optional, gated** input (§3.3). |
| Clarfeld et al. 2025, GMNF drumming acoustic recordings 2022–23, >9,500 h (doi:10.5066/P13EFLXX) | Verified to exist (USGS page). **Site coordinates unverified**: ask the USGS VT Cooperative Unit | Independent scorer S1. |
| NH Fish & Game regional grouse flush and observation rates (Small Game Summary; e.g. 143 grouse per 100 h with a dog, North Region 2018) | Seen in search results; the page returns 403 to automated fetch, so the **contents are unverified**. The owner can download it. | Independent scorer S2 (weak, small n). |
| The owner's GPS hunt logs (GPX + flush waypoints) | Collected in season | Independent scorer S3 (the hunter's own estimand), then training data from season 2. |
| PAD-US 4.x and state lands | Public | Access classes (adopted from D's A1–A4/X scheme). |

**Checklist filtering** (Johnston et al. 2021):

- complete checklists only;
- Stationary or Traveling protocol;
- duration 5–300 min; distance ≤ 5 km; ≤ 10 observers;
- one checklist per `GROUP IDENTIFIER`;
- $y=1$ if Ruffed Grouse is reported (including "X").

The checklist's own species count is **not** used as an effort covariate. It depends on the habitat being scored and it counts the grouse itself (see §9, E).

### 3.2 Estimand

The **fall standardised encounter rate** for covert or cell $s$ in season $T$:

$$
\Lambda^\star_{\text{fall}}(s,T)=e^{g(e^\star)}\sum_t K^\star(t-s)\,e^{f(x_t,T)+\Delta_{\text{fall}}(x_t,T)},\qquad \mathrm{SER}=1-e^{-\Lambda^\star}.
$$

- $e^\star$ = one median-skill observer, traveling, 60 min, 2 km, 15 October, 08:00.
- $K^\star$ is a 2 km-walk kernel.
- $f$ is the shared habitat log-rate and $\Delta_{\text{fall}}$ is the fall deviation, shrunk toward 0 (§3.3).
- The ranking depends only on $f+\Delta_{\text{fall}}$, convolved with $K^\star$. The absolute scale is identified by non-detections, and is mapped to *hunter* flushes per hour only through the owner's logs (S3) and the NH rates (S2), as a reported scalar.

### 3.3 Model

**Main model: GBM with a cloglog footprint objective** (D's custom-objective idea, with my effort-tower rule). For checklist $j$ with footprint stencil points $t_{j1..M}$ ($M=7$ for stationary, 13 for traveling):

$$
\eta_j=g(e_j)+\operatorname{LSE}_m\big(F(x_{t_{jm}})+\log w_{jm}\big),\qquad P(y_j=1)=1-\exp(-e^{\eta_j}),
$$

- $F$ is a LightGBM ensemble trained with a custom objective. For each prediction step, the objective computes the group log-sum-exp across a checklist's stencil rows. The gradient for row $m$ is the checklist gradient times the row's softmax share. All predictions are available inside a custom objective, so this is exact.
- $g$ is fitted as an offset by alternation (3–5 rounds). It is a small penalised GAM.

**Effort tower rule (a hard constraint).** $g$ sees *only covariates measured on the checklist event itself*:

- log duration and log(1+distance), monotone ≥ 0;
- protocol and party size;
- start-time spline and day-of-year cyclic spline;
- year;
- observer random effect $u_o\sim\mathcal N(0,\tau^2)$, for observers with ≥ 20 checklists;
- out-of-fold skill index (Kelling et al. 2015).

**Never** location-derived covariates: hotspot distance, checklist density, trail distance or road distance.

*Reason.* Any location-derived covariate is itself correlated with habitat. Big forest has low checklist density and is far from hotspots. Such a covariate lets $g$ absorb habitat signal, which is then deleted at prediction. That is the exact failure PAL avoids by giving the bias tower only the position. Location-derived effort measures are used **only** as diagnostics (§3.5).

**Features of $F$.** Footprint-averaged versions of:

- the `diagnose_gbm_baseline.py` design (centre codes, 21-px shares, 5/21/64-px means and SDs);
- succession-clock shares at 90/250/600 m in the age bins {0–4, 5–15, 15–25, 25–40, >40}, plus age-class Shannon diversity (from A, D and E);
- `mch_*`.

Optionally, AlphaEarth disc means at 60/300/1200 m (C). These are admitted only if they pass both the ablation *and* the negative-control test (§3.5). An embedding that resolves trailheads must not leak birding infrastructure.

**Fall head.** $\Delta_{\text{fall}}$ is a second, shallow LightGBM (depth ≤ 3, strong L2). It is fitted on Sep–Dec checklists only, with $F$ frozen as an offset. This is D's idea. The GBIF data give about 5.8 k fall detections for 2020–24, so the head is supported.

**Optional phase: per-pixel MLP habitat tower** (E's architecture) over the same multi-radius features, trained with the same likelihood in PyTorch. The fully convolutional ResNet is a last resort. Each is kept only if it beats the GBM by ≥ 0.01 effort-stratified AUC on the head-to-head set.

**Uncertainty.**

- 5 spatial-fold models × 2 seeds, giving the epistemic spread.
- An "extrapolation" flag where a covert's features fall outside the training envelope (Mahalanobis distance in PCA-20 space above the 99th percentile; from C and D).

### 3.4 Splits

- **Head-to-head set HH** (C's idea): all checklists whose start point is in a *validation* block of the existing 3 km split (`SPLIT_SEED=42`).
- **Training exclusions:** all CEM training excludes checklists within 2 km of an HH block, since the CNN window reaches 0.96 km and footprints reach about 1 km.
- **Internal model selection:** 5-fold CV on 25 km blocks (A and E) over the remaining area.
- **Block-size check:** a residual variogram (report §4.3).

### 3.5 Robustness module (pre-registered, committed as acceptance code before any fit; CR-0011 A3)

**R-PS: preferential sampling** (birders or hunters walking *to* known grouse).

1. **Within-observer AUC.** AUC over pairs of HH checklists from the *same observer*, with the same protocol and effort tercile. Between-observer targeting and skill cancel exactly. If CEM's advantage over the target-group model holds within observers, it is not an observer-selection artefact.
2. **Drop-targeters.** Refit without the observers in the top 2% of out-of-fold grouse reporting rate. Pre-registered pass: Spearman rank correlation of the covert ranking ≥ 0.9 against the full model.
3. **Repeat-visit stability.** At personal locations visited ≥ 5 times, the detection rate should be explained by $g$ (season, duration) with no residual trend in visit order. A rising trend means "returning because grouse were found". That is evidence of preferential sampling, and it is down-weighted by capping each location-observer's count.

**R-EL: effort leaking into habitat** (control species run through the identical pipeline, with the same features, $g$ and footprints).

| Control | Habitat relation to grouse | Pre-registered expectation |
|---|---|---|
| Chestnut-sided Warbler, American Woodcock | **Positive controls** (young forest and shrubland) | Habitat maps correlate with grouse $f$ at ρ ≥ 0.4 |
| Wild Turkey | Partial (edge and field; game bird, detected from roads) | Intermediate |
| Black-capped Chickadee, Blue Jay | **Negative controls**: ubiquitous, feeders and trails; detection is mostly effort | ρ with grouse $f$ ≤ 0.3, **and** the grouse–negative-control correlation must be lower than the grouse–positive-control correlation |

If the grouse map correlates with the negative controls as strongly as with the positive controls, the habitat function is tracking *birding*, not grouse. This test runs on both the target-group model and CEM, which gives a quantitative "effort contamination index" for today's map as a by-product.

Diagnostics only:

- D's effort probe: R² of $f$ on hotspot distance, trail distance and checklist density;
- the share of top-5% coverts within 300 m of an eBird hotspot.

**R-DT: detectability that depends on habitat** (spring drumming versus fall flushing).

1. Report the covert-ranking Spearman between $f$ (all-season) and $f+\Delta_{\text{fall}}$. If it is < 0.8, the product ranks by the fall model, and the card shows a "spring/fall disagree" badge.
2. **Hunter detectability.** From season 2, the owner's logs fit a cover-dependent hunter detection multiplier $W(s)=W_0e^{\omega\,u(s)}$ (A's line-transect idea), where $u$ is the `mch_f15` understory share. This corrects "birders hear grouse in open mature woods; hunters flush them in thickets" with the hunter's own data.

### 3.6 Inference and end product: the covert card

1. **Coverts.** Disturbance patches aged 4–25 years, SLIC segments on (age, `mch`, deciduous share) and a 25 ha hexagon background (D's three-source scheme). Size 2–40 ha.
2. **Each covert card shows:**
   - **expected fall encounters per standard hour** with an 80% interval;
   - **an artefact-risk badge**, which no other design has. It is set if *any* of the following holds:
     - within 300 m of an eBird hotspot;
     - the spring and fall heads disagree by more than one quintile;
     - extrapolation;
     - AlphaEarth-driven, meaning the feature attribution comes > 50% from embedding features;
   - **peak window** from the succession clock (A, C, E);
   - **access class** (A1 public open … A4 unknown private, X excluded; D) and walk-in distance;
   - the **top 3 reasons** (TreeSHAP).
3. **Daily recommender** (D): within a chosen drive radius, 4 coverts by Thompson sampling over the fold ensemble, plus 1 drawn uniformly from the accessible top 30%. That fifth covert makes realised lift an unbiased estimate.
4. **Season ledger.** Each logged hunt records predicted versus realised flushes. A gamma–Poisson covert effect updates immediately (D), and $F$, $g$ and $W$ are refit after the season.
5. **Output formats:** a GeoPackage, PMTiles/KML for onX, Gaia or Avenza, and a static Leaflet page.

---

## 4. Why it beats the status quo, and why it beats the other four

**Against the status quo.** The report says the ceiling is the data and the labels (§5.4). CEM-X replaces target-group "negatives" with observed non-detections conditional on effort, which removes:

- the PU contamination;
- the $1-a/2$ shared-support bound;
- the habitat-structured denominator $q_{\mathrm{TG}}$;
- the envelope double-count.

It also adds a time-correct succession clock and a hunter-scale estimand. This is common to all five designs.

**Against the other four.** The shared core can still fail for four reasons that all five designs name:

- home advantage;
- effort leaking into habitat;
- preferential sampling;
- detectability.

Each could make a checklist-trained map *look* better on checklist metrics while sending a hunter to trailside woods. CEM-X is the only design that:

1. tests the *label* effect with features and model held fixed, home and away, in week 1;
2. measures effort contamination of *today's* map and the new map with pre-registered control species;
3. evaluates within observers;
4. keeps location-derived effort out of the effort tower by rule;
5. surfaces residual artefact risk to the hunter, covert by covert.

It is also deliberately the cheapest: a GBM in production, CPU-only falsification, and neural work only on evidence.

---

## 5. Expected gains, measured without fooling ourselves

### 5.1 The cross-play matrix: the primary comparison

| | Scored on T_TG: existing target-group validation set (TG's home) | Scored on HH: checklists in the same validation blocks (CEM's home) | Scored on S1–S3: independent (nobody's home) |
|---|---|---|---|
| **M_TG**: same GBM features, target-group labels (`diagnose_gbm_baseline.py`), plus the CNN logit as a second entry | home: AUC ≈ 0.770 (known) | away | neutral |
| **M_CL**: same features, footprint-averaged, EBD complete-checklist labels | away | home | neutral |

**The label effect.** If labels do not matter, M_CL's away deficit on T_TG should be about as large as M_TG's away deficit on HH. If checklist labels carry more grouse information, M_CL loses *less* away than M_TG does.

**Decision rule (pre-registered).** Write $\Delta_{\text{away}}^{CL}$ for M_CL's away deficit on T_TG and $\Delta_{\text{away}}^{TG}$ for M_TG's away deficit on HH, the latter measured by effort-stratified AUC. Paired block-bootstrap CIs are taken over the shared 3 km blocks. **The label thesis passes** if

$$\Delta_{\text{away}}^{TG}-\Delta_{\text{away}}^{CL}\ \ge\ 0.02\quad\text{(lower CI} > 0\text{)},$$

and M_CL is not worse on any independent scorer that is available. **It fails** if the difference is ≤ 0.005, or if M_CL loses on S1. This cancels home advantage under one stated assumption: home advantage is roughly symmetric across the two label types. The assumption is checked by running the same matrix on the **injection–recovery** synthetic species, where the truth is known.

**Other HH metrics:**

- effort-stratified AUC (protocol × duration tercile × month);
- **within-observer AUC** (R-PS);
- **TkL₁/₅/₁₀** with an effort-only expected denominator (D);
- calibration;
- the same metrics restricted to Sep–Dec.

**Achieved ÷ achievable.** For each HH metric, simulate labels 200× from the final model's own probabilities on HH to get the oracle AUC distribution. Report achieved ÷ oracle. This is the honest ceiling of the new task, the analogue of $1-a/2$, so nobody mistakes a correct 0.74 for a failure.

Reported throughout: the zero-parameter heuristic H (A) and eBird Status & Trends (as an upper-biased benchmark, because it trains on the same checklists).

### 5.2 Expected values

These are priors and will be replaced by measurements.

| Quantity | Expected | Confidence |
|---|---|---|
| Label-swap gap $\Delta_{\text{away}}^{TG}-\Delta_{\text{away}}^{CL}$ on EBD checklists | +0.01 to +0.05 | Low |
| Effort-stratified AUC on HH: M_TG / CNN → M_CL-EBD + clock | 0.62–0.70 → 0.68–0.76 | Low–medium. The direction is supported by Johnston et al. (2021); the magnitude is a guess. |
| Within-observer AUC gain (CL − TG) | about 60% of the stratified-AUC gain survives | Low. If < 30% survives, preferential sampling is a large share of the gain, and I will say so. |
| TkL₅ on HH (effort-expected denominator) | TG 1.3–1.7×; CEM-X 1.6–2.4× | Low |
| Negative-control correlation of today's TG map | 0.3–0.5. Today's map partly tracks birding | Low (as D's E1 also expects) |
| Owner's realised flush ratio, Thompson top-4 vs randomised arm, one season | ≥ 1.4× point estimate; 80% power only if the true lift ≥ 1.6× | Very low at n ≈ 40 visits. Two seasons are needed for a reliable answer. |

### 5.3 Gate probabilities (my honest priors)

| Gate | Prior probability of passing |
|---|---|
| G1: label thesis passes on EBD checklists (week 1) | 0.6 |
| G2: at least 30% of the HH gain survives within observers (R-PS) | 0.6 |
| G3: succession clock adds ≥ 0.01 on HH | 0.45. It added +0.001 under TG labels (CR-0032, verified in the repository); under checklist labels it could matter, but that is unproven. |
| G4: AlphaEarth passes the ablation and the negative-control test | 0.35 |
| G5: neural tower beats the GBM by ≥ 0.01 | 0.25 |
| G6: season-1 field lift is significant | 0.35 |

The expected value of the project rests on G1 and G2. Everything else is optional upside.

---

## 6. Risks and the falsification ladder

All first steps run on CPU on EC2, using the EBD/SED download plus data already present. Every step is read-only with respect to `data/` and writes to scratch.

| Step | When | Test | Kills or changes |
|---|---|---|---|
| **T0: injection–recovery on real checklist geometry** | Day 2–3 | Plant two synthetic species into real EBD checklists (real locations, effort and observers): (i) a CEM-shaped hazard truth; (ii) a pure thinned-IPP truth, which is where the target-group pipeline is correctly specified. Run both pipelines and the cross-play matrix. | If the target-group pipeline recovers truth (i) within 0.02 Spearman of CEM, the estimand argument is weak and the gain must come from volume. This also **calibrates the home-advantage symmetry assumption** of §5.1. |
| **T1: label-swap cross-play** (the decisive one) | Day 3–5 | The §5.1 matrix with EBD checklists, plus R-PS within-observer AUC | **Fails → stop the checklist programme for all designs.** The remaining value is field validation and the product layer on today's map. |
| T2: effort-contamination audit of today's map | Day 3–5 (parallel) | Control species (R-EL) + D's effort probe + share of the top 5% near hotspots | No kill. It quantifies how much of today's map is birding; a high index strengthens G1's motivation. |
| T3: freshness audit (D's E2) | Day 3 | Share of today's top 5% cut in 2023–24 or older than 30 years by 2026 | No kill. It sizes the value of the clock. |
| T4: full stage-1 | Week 2–3 | GBM-cloglog with per-checklist footprints and observer effects vs M_TG and the CNN on HH, plus R-PS and R-EL | Gate G2. If within-observer AUC shows no gain, the product ships with all coverts badged "unverified". |
| T5: independent scorers | When obtained | S1 GMNF acoustic site detection rates (Spearman vs covert $\Lambda^\star$); S2 NH regions (leave-one-region-out) | Decisive for any public claim. |
| T6: field season | Oct–Nov | Randomised fifth-covert arm | Product-level truth |

**Main risks:**

| Risk | Severity | Mitigation |
|---|---|---|
| Home-advantage symmetry fails | MAJOR | Checked by T0; independent scorers S1–S3 decide |
| EBD schema differs from expectations (column or protocol names change between releases) | LOW | Schema assertions in the ingest acceptance script |
| Preferential sampling | MAJOR | R-PS: within-observer AUC, drop-targeters, repeat-visit check |
| Detectability depends on habitat | MAJOR | Fall head; spring/fall badge; hunter $W(s)$ from the owner's logs |
| Embedding or infrastructure leakage | MEDIUM | AlphaEarth admitted only if it passes R-EL |
| GMNF coordinates unavailable | MEDIUM | S2, S3; out-of-region PA acoustic data are unusable because their coordinates are obscured (C) |
| Registration bugs in new GEE layers | MAJOR (repo history) | Template-lattice `crsTransform` and the BUG-0094 offset probe as acceptance gates |
| eBird data terms | LOW | Personal use; publish only derived maps after re-reading the terms |

---

## 7. Implementation plan (one owner, one EC2 GPU, mostly CPU)

Each item is its own CR under `CLAUDE.md` §1, following A5 (one independently landable change per CR). Acceptance scripts and pre-registered thresholds are committed before approval (A3).

| When | Work | Compute |
|---|---|---|
| **Day 1** | Download the EBD (Ruffed Grouse, ME/NH/VT) and the SED. Build `checklists.parquet` with `ebird_checklists.py` (pandas, chunked): filter, zero-fill, dedupe groups, attach blocks and HH flags, and report volumes and the grouse rate. Commit `eval_crossplay.py` with HH, metrics and gates (acceptance CR). Email the USGS VT Coop Unit (GMNF coordinates), NH F&G (regional tables), and ME IF&W / VT F&W. | CPU, a few hours |
| **Day 2–3** | Footprint-averaged features through the existing patch reader (`diagnose_gbm_baseline.py` design, 7- or 13-point stencil). T0 injection–recovery (`inv_cem_injection.py`). | CPU |
| **Day 3–5** | **T1 cross-play** (simple effort GAM + GBM habitat), with **T2** and **T3** in parallel | CPU |
| **Week 2–3** | Full GBM-cloglog custom objective with observer effects; R-PS, R-EL; **T4** | CPU/GPU, hours |
| **Week 3–4** | Succession-clock export (GEE, registration-gated); fall head; gate G3; optional AlphaEarth (G4) | GEE + CPU |
| **Week 5** | Covert generation, access classes, cards, recommender, ledger (`covert_cards.py`) | CPU |
| **Season** | Field use with the randomised arm; log ingestion | — |
| **Optional** | Per-pixel MLP (E), then the FCN ResNet (round-1 B) on the single GPU; G5 | GPU, days |

**First experiment within a day:** the Day-1 EBD/SED ingest, with checklist volume and grouse-rate counts. T0 follows on days 2–3, and the decisive cross-play result (T1) by day 5.

---

## 8. References

Verified this round unless marked **unverified**.

1. GBIF occurrence API, eBird Observation Dataset fields and counts (queried 2026-10-05): https://api.gbif.org/v1/occurrence/search?datasetKey=4fa7b334-ce0d-4e88-aaae-2e0c138d049e
2. eBird data products and EBD request process: https://science.ebird.org/en/use-ebird-data/download-ebird-data-products
3. Johnston, A. et al. (2021). Analytical guidelines to increase the value of community science data. *Diversity and Distributions* 27:1265–1277. https://doi.org/10.1111/ddi.13271
4. Kelling, S. et al. (2015). Can observation skills of citizen scientists be estimated using species accumulation curves? *PLoS ONE* 10:e0139600. https://doi.org/10.1371/journal.pone.0139600
5. Clarfeld, L.A. et al. (2025). Two-stage models improve machine learning classifiers in wildlife research (GMNF Ruffed Grouse acoustic recordings, 2022–23). USGS data release, doi:10.5066/P13EFLXX. https://www.usgs.gov/data/two-stage-models-improve-machine-learning-classifiers-wildlife-research-a-case-study (site coordinates **unverified**)
6. Lipsitch, M., Tchetgen Tchetgen, E., Cohen, T. (2010). Negative controls: a tool for detecting confounding and bias in observational studies. *Epidemiology* 21:383–388. https://doi.org/10.1097/EDE.0b013e3181d61eeb (**unverified**, from memory)
7. Jackson, M.L., Nelson, J.C. (2013). The test-negative design for estimating influenza vaccine effectiveness. *Vaccine* 31:2165–2168 (confirmed via search; DOI **unverified**)
8. Guo, H. et al. (2019). PAL: position-bias aware learning for CTR prediction. *RecSys '19*. https://doi.org/10.1145/3298689.3347033
9. Joachims, T., Swaminathan, A., Schnabel, T. (2017). Unbiased learning-to-rank with biased feedback. *WSDM*. https://arxiv.org/abs/1608.04468
10. Maunder, M.N., Punt, A.E. (2004). Standardizing catch and effort data: a review of recent approaches. *Fisheries Research* 70:141–159.
11. Christiansen, J.L. et al. (2016). Kepler injection–recovery completeness. *ApJ* 828:99. https://ipac.caltech.edu/publication/2016ApJ...828...99C
12. Chung, C.-J.F., Fabbri, A.G. (2003). Validation of spatial prediction models for landslide hazard mapping. *Natural Hazards* 30:451–472. https://ideas.repec.org/a/spr/nathaz/v30y2003i3p451-472.html
13. Gholami, S. et al. (2018). Adversary models account for imperfect crime data (iWare-E). AAMAS. https://www.cais.usc.edu/wp-content/uploads/2018/01/sgholami_aamas18.pdf
14. Dorazio, R.M. (2014). Accounting for imperfect detection and survey bias in presence-only data. *Global Ecology and Biogeography* 23:1472–1484. https://doi.org/10.1111/geb.12216
15. NH Fish & Game, Ruffed Grouse Wing and Tail Survey / Small Game Summary: https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey (contents **unverified**; 403 to automated fetch)
16. Earth Engine catalogs: LCMS v2024-10, Hansen GFC v1.12, AlphaEarth Satellite Embedding V1 (as cited and verified by designs A, C and D)
17. PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview
18. Royle, J.A., Nichols, J.D. (2003). *Ecology* 84:777–790 (**unverified** DOI)
19. Repository: `docs/grouse_model_report.md` §2.3, §4.1, §4.8, §5.3–5.4; `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md` lines 22–25 (harvest +0.001, GEDI +0.000, Meta CHM +0.009 to +0.012; verified); `get_negatives.py` `TARGET_SPECIES` (10 species in a mature-upland guild and a wetland guild; verified); `diagnose_gbm_baseline.py`; `sightings.py` (GBIF route).

---

## 9. Critique of competitors

Each entry names the strongest flaw I could substantiate. I have tried not to attack strawmen.

| Design | Strongest flaw | Severity | Evidence and concrete failure scenario | What I took from it anyway |
|---|---|---|---|---|
| **A: CYM** | **Precision is capped by a 30–40-parameter mechanistic density model whose main driver (stand age) has so far shown no signal.** The owner's goal is "as much precision as possible". Habitat enters through a few prior-shaped terms ($a(\text{age})\cdot m(\text{guild})\cdot u(\text{under})$ and kernels). The flexible residual is optional and ridge-shrunk. | MAJOR | Stand age from LCMS/Hansen added +0.001 AUC in the repository's own test (CR-0032 l.22, verified). If age-since-cut is poorly measured where partial harvests dominate, which is common in Maine and admitted in A's R1, the age-centred structure has nothing to fall back on. Scenario: northern Maine shelterwood stands with dense regeneration score low because $a(\cdot)$ reads "mature", and a GBM on the same checklists would have learned them from `mch_f15`/`evh`. A's F1 kill test compares H and the prior-mean model against the CNN logit, but not against a *flexible* model on checklists, so this loss of precision is never measured. | Zero-parameter heuristic H; hunter strip-width $W(s)$ fitted from hunt logs; 25 km blocks; field-test power calculation |
| A (second) | The disaggregation term models hunter effort as $\propto (K\ast q)^\eta$, using the model's *own* habitat estimate | MEDIUM | This is circular. It lets the regional anchor confirm whatever $q$ already says. | — |
| **C: FLUSH-C** | **The primary habitat representation is a 10 m embedding that can see birding infrastructure, and nothing pre-registered stops it from becoming the main signal.** C's own R2 test (AUC of the hotspot flag from $f$ > 0.65) checks only the hotspot *type*, not trails or parking. | MAJOR | Every training checklist sits at birding infrastructure, so non-detections cancel infrastructure only *within the visited distribution*. At prediction the map is applied to all forest, most of which has no trails, and that is covariate shift. Scenario: AlphaEarth dimensions that encode "maintained trail through hardwood" correlate with longer forest walks that report grouse. Those trail-adjacent coverts rank top, and the hunter is sent to hiking corridors. C's ablation "FLUSH-noAEF" measures accuracy on checklists, which share the same infrastructure, so it cannot reveal this. | The HH test set in the status-quo validation blocks; AlphaEarth as a *gated* input; Experiment A; multi-radius gate idea |
| C (second) | The kill test "FLUSH-LF ≤ CNN + 0.01 on H" is scored only on checklists, so it has home advantage | MEDIUM | M_CL is trained on the label process it is scored on, while the CNN is scored away. That favours FLUSH by an unknown amount. CEM-X's cross-play matrix fixes this. | — |
| **D: COVERT** | **Location-derived "birder-ness" covariates are placed in the effort/detection term $g$:** distance to hotspot, distance to marked trail, checklist density within 1 km. They are set to "median non-hotspot forest" at prediction. A gradient-reversal adversary also pushes $f$ to be uninformative about log checklist density. | MAJOR (D sweeps $\lambda_{adv}$ including 0, and selects using independent data, so it is not BLOCKING) | Checklist density and hotspot distance are habitat-correlated. Big, remote forest has low checklist density, and NH F&G and the report (§1.7) say grouse densities are highest in the north, where eBird effort is lowest. Scenario: $g$ learns "low checklist density → higher detection" (it is really habitat). $f$ loses that signal, and fixing $w^\star$ at a single median puts it back only as a constant. The adversary actively removes a true habitat–effort correlation and down-ranks remote north-woods coverts. PAL works precisely because its bias tower sees *only* position. | Effort-expected TkL; GMNF acoustic scorer; randomised 5th covert; access classes A1–A4/X; fall head; custom LightGBM cloglog objective; E1/E2 audits |
| D (second) | A Royle–Nichols disk average with radius $\max(150, \ell/2)$ and spatial subsampling to 1 checklist per 3 km × week | LOW | The subsampling throws away most non-detections. That is defensible for variance but costly at the 3-state scale; C and E use a cap of k > 1. | — |
| **E: FLUSH-E** | **Its day-1 experiment uses the checklist's own species count as the effort proxy.** EBD access makes its pseudo-checklist route unnecessary, but the proxy problem carries over if species count is kept as an effort covariate. | MEDIUM (first test only; the production design is sound) | Species count is post-treatment: it depends on the very habitat being scored (edges and wetlands yield more species than closed forest) and it counts the grouse itself. Scenario: conditioning on it makes footprint habitat features look *more* predictive in closed forest, where low species counts co-occur with grouse. That inflates arm (b) and can produce a false "supported" result on day 1. Its comparison of (a) a CNN score with one coefficient against (b) a GBM fitted on checklists also has home advantage. I verified that GBIF lacks `eventID` and time. | Placebo species, recast as positive and negative controls; succession-clock bins; per-pixel MLP option; importance-weighted evaluation; 25 km hexagons |
| E (second) | The claim that within-location repeat visits identify ρ separately from λ needs closure across visits | LOW | It is irrelevant to ranking, which E itself says, but it overstates what the checklist data can identify. | — |
| **B round 1 (self-critique)** | The main model was a fully convolutional ResNet on tiles, which costs weeks of GPU work for a prior gain I now put at about 25%. Day-1 F0 ran on target-group geometry. The M3 lift denominator could be gamed by effort. | MAJOR (self) | Fixed in §0: GBM main model, F0 replaced by T0/T1 on real EBD checklists, D's TkL adopted. | — |
