# Design A (final): the Covert Yield Model (CYM), mechanism first and hunt-able this October

*Designer A, round 2. Primary technique: first-principles decomposition plus Five Whys. Added this round: adversarial red-teaming of competitors, and a "what can be true before the data arrives" timeline inversion. No repository file was edited.*

---

## 0. Changes from round 1

**Where the field converged.** Five designs converged on the same core:
- eBird complete checklists;
- a separate effort tower;
- footprint kernels;
- NH flush-rate anchoring;
- coverts as the unit;
- top-k lift as the metric.

I keep that core and do not claim it as mine. CYM v2 competes on six things the others do not share:

1. **A zero-fit, pre-registered prior map.** The model's ecological structure plus literature priors gives a full map *before any label is fitted*. Its first test is therefore a real out-of-sample prediction, not a tuned fit.
2. **Hunt-able this season.** Today is 2026-10-05. The NH grouse season opened on 1 October. The prior map can be built from Earth Engine layers in about two days, and **the owner can run a randomised, blinded field comparison of prior-CYM vs the current CNN vs random accessible forest during the 2026 season**. No other design produces independent ground truth before 2027.
3. **Robustness to preferential sampling, made testable.** Birders under-sample the dense, young, off-trail cover that hunters want. That is a *covariate-shift-into-the-target* problem. Shape-constrained, low-parameter models extrapolate there sanely; flexible models do not. The claim is tested by an injection–recovery simulation built from the real EBD checklist geometry (adapted from B) in week 1.
4. **Habitat-dependent detectability, treated explicitly.** The design does not hope this away. A two-to-three-parameter **birder-to-hunter transfer term** is fitted on hunt logs, where detection happens the way the product needs (a hunter flushing birds on foot). An acoustic drum-*rate* check is added.
5. **The lightest compute.** About 40 parameters in the core, fitted in minutes on CPU or GPU. One EC2 GPU is more than enough. The GPU is used only for kernel convolutions at prediction.
6. **Honest power.** Every gain claim states the sample needed to see it.

**Adopted, with credit:**

| Idea | From | How it is used |
|---|---|---|
| Zero-tuning comparison of map scores on held-out complete checklists, before any model is fitted | **E** (§6 test), run on real EBD | Test T1 |
| Injection–recovery with a known synthetic species | **B** (F0) | Test T2, re-aimed at *preferential sampling* and with two truths, so it does not favour my model |
| Observed/expected top-k lift, TkL (effort-only model in the denominator) | **D** | Primary retrospective metric |
| Freshness audit of the current map | **D** (E2) | Test T3 |
| OPERA DIST-ALERT/DIST-ANN for 2025–2026 cuts | **D** | Disturbance fusion for the current season |
| Access classes (PAD-US OA / NH Current Use / Maine custom-open / unknown) and one randomised recommendation in five | **D** | Product, and the randomised field estimate of lift |
| Vermont GMNF ARU data release (Clarfeld et al. 2025) | **D** | Independent validation (I checked that the release exists; coordinates may need a request) |
| Head-to-head test set H inside the status-quo CNN's own validation blocks | **C** | Retrospective comparison against the CNN |
| AlphaEarth embeddings | **C** | Only inside the *gated* residual term, never in the core |
| "Rule-out map" (high effort, confidently low density) | **E** | Product layer |
| Effort-stratified AUC; drop the top-1% grouse-reporting observers as a sensitivity | **B** | Secondary metric; preferential-sampling sensitivity |

**Dropped or demoted:**
- *Aggregate hunter data as a training term for spatial pattern.* C correctly calls that an ecological fallacy. It now fits only the region × year level τ and the absolute scale.
- *The round-1 F0* (an effort-proxy GBM on the current labels). It did not falsify anything. It is replaced by T1 and T2, which can.
- *GBIF pseudo-checklists* (E's stop-gap, which I adopted in an earlier draft of this round). The owner already has EBD access, so it is dropped. For the record, I verified via the GBIF API (2026-10-05) that GBIF eBird rows carry `recordedBy`, `eventDate` and coordinates but **no `eventID`, `eventTime` or effort fields**. That confirms C's claim and means GBIF cannot replace EBD.
- *Every phase that existed only to wait for EBD access.*
- *Optional presence-only component.* Removed; it is not worth the complexity.

---

## 1. Title and pitch

**CYM: predict flushes per hour of walking, per covert, per season, from the physics of an encounter and the clock of forest succession. Ship a pre-registered expert map this October and let the season grade it.**

The estimand factors exactly as flushes/h = $2W v D$, where $W$ is the strip half-width, $v$ is walking speed and $D$ is fall grouse density. Only $D$ is ecology, and $D$ is dominated by a short list of measurable causes:
- years since a heavy cut;
- the regenerating forest type;
- understory stem density;
- interspersion at home-range scale;
- regional and annual level.

CYM writes those causes into a shape-constrained model of about 40 parameters with literature priors. It then lets three label streams adjust the parameters, never the shape:
- eBird complete checklists (detection given effort);
- GPS hunt logs (the estimand itself);
- state flush-rate aggregates (scale and year level only).

Because the structure *is* the prior, CYM has a usable map at **zero labels**. Fitting, validating and auditing a checklist model properly still takes one to three weeks, while the season is already running. The prior map is ready in about two days, so the first independent field test happens in the season that has already started, and the prior is graded on real complete checklists before it has seen them.

---

## 2. Brainstorming record (short)

**First-principles decomposition** (unchanged from round 1). Hunter value = E[flushes/h in covert c] × reachability.
- E[flushes/h] = D(c,Y) · 2W · v.
- D = carrying capacity (cover × food × interspersion) × regional/annual level × local hunting depletion.

*Physics check.*
- Prime cover: about 0.7 breeding birds/ha in 10–25-year aspen, so roughly 1.5 birds/ha in fall.
- Sweep rate: about 6 ha/h.
- That predicts about 9 flushes/h in prime cover and about 0.6–1.8/h in average hunted forest.
- NH's statewide reported 1.31/h (2019) and 2.27/h (2020) (search-summary figures, **unverified**). The scale is pinned to the right order.

**Five Whys** (the three chains from round 1, condensed):
1. AUC is stuck at 0.77 → the label is a contrast of two recording processes → stand age, the best-supported driver, added +0.001 under that label → the label cannot see 5–20 ha habitat → **the label must carry effort and absence at or below covert scale** (shared with all designs).
2. The map can mislead even at equal AUC → reporting follows trails, and the succession clock moves every year → **the mechanism must be explicit and rolled forward every year** (shared with D and E).
3. Nothing grades outputs against the ground → **the scoreboard must be field flush rates** (shared with D and E). *New this round:* why will no other design be graded in the field this season? Because each gates its first map on fitting, auditing and segmenting, which takes weeks into a season that runs October–December. A mechanistic prior removes that gate.

**Timeline inversion (new).** I listed what can be *true* at each point of the season. EBD access is already in hand, so the binding constraint is the hunting calendar (October–December), not data access:

| Days 1–3 (no fitting) | Week 1 (EBD, no fitting of CYM) | Weeks 2–3 | After the season |
|---|---|---|---|
| The prior-mean CYM map and coverts; the freshness audit; **field test starts** | T1: zero-tuning scores on real held-out checklists; T2: injection–recovery; T4: coverage audit | A fitted CYM; TkL on H; residual gate | Transfer term; posterior; field-graded lift |

The first column was empty in every round-1 design except mine, and I did not exploit it. That is the main revision.

**Red-team (new).** I attacked each competitor's strongest claim (§9). The attacks that land on a *shared* weakness are preferential sampling, habitat-dependent detection, fold design and the effort-proxy choice. I turned each into a CYM requirement:
- R-a: the core must extrapolate sanely into unvisited covariate space;
- R-b: no location-derived variable in the effort tower;
- R-c: fold size must exceed the footprint diameter;
- R-d: no habitat-dependent effort proxy without stratification.

---

## 3. The design

### 3.1 Estimand

For a 30 m cell $s$ and season $Y$ (October–December):

$$F(s,Y)=2W(s)\,v\,D(s,Y)\,\exp\{\delta(s)\}\qquad[\text{flushes/h}]$$

- $D$ is fall density in birds/ha.
- $v\sim\mathcal N(2.0,0.4^2)$ km/h.
- $W\sim\text{LogNormal}(\log 15\text{ m},0.4)$.
- $\delta(s)=\delta_1\,\text{dense}(s)+\delta_2\,\text{open}(s)$ is the **birder-to-hunter transfer term** (§3.4 O3). It is zero until hunt logs exist.

For a covert $c$, $F(c,Y)$ is the area mean. **Ranking within a region depends only on $D\cdot e^{\delta}$.**

### 3.2 Habitat-state cube, rebuilt every season

All layers are written on the existing per-region LANDFIRE template grid. Earth Engine exports use explicit `crs` + `crsTransform` (the BUG-0094/0095 lesson). Acceptance gates are `grid_mismatch`, `check_layer_registration.py` and the `diagnose_fetch_tile_offset.py` probe.

| Layer | Definition | Source |
|---|---|---|
| `age(s,Y)` | $Y-$ year of the last heavy disturbance ≤ $Y$; no event since 1985 → "mature" | Fusion, with a source-agreement count kept as a confidence channel and a ±1 yr tolerance:<br>• LCMS Change, Tree Removal (`USFS/GTAC/LCMS/v2024-10`, 1985–2024)<br>• Hansen `lossyear` (`UMD/hansen/global_forest_change_2024_v1_12`)<br>• Maine HF437 harvest maps 1986–2019 (doi:10.6073/pasta/20a838c4bd6922685b3d00661d45c414)<br>• OPERA DIST-ANN 2023–24 / DIST-ALERT 2025–26 (from D)<br>• LANDFIRE annual disturbance |
| `sev(s)` | Disturbance severity, used to separate clearcut from partial cut | LCMS fast-loss probability, LandTrendr ΔNBR |
| `regen(s)` | Forest guild: aspen–birch / northern hardwood / mixedwood / oak–pine / pine–hemlock / spruce–fir; the pre-cut guild is used for stands under 15 yr | TreeMap 2022 FORTYPCD crosswalk; LANDFIRE EVT fallback |
| `under(s)` | Leaf-off lidar share of returns 1–6 m among returns under 6 m | 3DEP/state LAZ via PDAL (VT 2023 QL1 leaf-off; NH GRANIT statewide; ME 3DEP). Fallback: Meta CHM `mch_f15` (CR-0032). Pixels disturbed after the flight are set to missing and handled by the `age` term |
| `conif`, `hwmature` | Conifer share; mature (≥ 30 yr or never-cut) aspen/birch/hardwood share | TreeMap + `age` |
| `dev`, `open`, `water` | Impervious %, agriculture/open land, water | Annual NLCD (already in the stack) |
| `snow`, `elev` | Days per winter with SWE above the burrow threshold; elevation | Daymet V4 (**asset ID unverified**); 3DEP DEM |
| Access (product only) | Drivable and gated roads, trails; PAD-US access; NH Current Use; Maine unorganised territories | TIGER 2023, OSM, PAD-US 4.x, state layers |

The forecast for $Y+k$ sets `age += k` with no new cuts; the covert record carries a flag saying so.

### 3.3 Density model (the mechanism)

**Cover quality per cell:**

$$q(s,Y)=a(\text{age})\cdot m(\text{regen})\cdot u(\text{under})\cdot h(\text{sev})$$

- $a(t)=\exp\{-(\log(t+1)-\log(t_p+1))^2/2\sigma_a^2\}$ for disturbed cells, with prior $t_p\sim\mathcal N(10,4^2)$ yr. Never-cut cells get a free level $a_\infty\in(0,1)$.
- $m$ has one log-multiplier per guild. The soft ordered prior is aspen–birch ≥ northern hardwood ≥ mixedwood ≥ oak–pine ≥ pine–hemlock ≈ spruce–fir.
- $u(x)=1-e^{-x/x_0}$ is monotone and saturating.
- $h$ is monotone in severity.

**Home-range integration.** $K_h$ is a Gaussian kernel with a learnable bandwidth, initialised at 150, 300 and 600 m.

$$\log D(s,Y)=\beta_0+\tau_{r(s)}(Y)+\beta_1\log(\epsilon+K_{h_1}\!*q)+\beta_2 g_2(K_{h_2}\!*\text{hwmature})+\beta_3 g_3(K_{h_1}\!*\text{conif})+\beta_4 K_{h_3}\!*\text{dev}+\beta_5 K_{h_1}\!*\text{open}+\beta_6\text{snow}+\beta_7\text{elev}+\beta_8\text{IJI}_{h_2}+\rho(s)+r(s)$$

- $g_3$ is unimodal ("some conifer is good"); $g_2$ is concave and increasing.
- IJI is the Shannon diversity of the age classes {0–10, 10–25, >25} (Vermont's three-age-class rule).
- $\rho$ is a low-rank 20–25 km spatial basis with strong shrinkage.
- $\tau_r(Y)$ is a region × year level, informed by aggregates and drumming indices.
- **$r(s)$ is the gated flexible residual.** It is a LightGBM on the 15 legacy layers plus AlphaEarth disc means (from C), with heavy shrinkage. It is admitted **only** if it improves held-out TkL and deviance on H *and* the T2 simulation shows that it does not degrade extrapolation (§6). Otherwise $r\equiv0$.

**The prior-mean map.** Set every parameter to its prior mean, with $\tau\equiv0$, $\rho\equiv0$ and $r\equiv0$. The result is $D_0(s,Y)$, a complete expert-system map with **zero fitted parameters**. It is committed (hash plus parameter file) before any test sees it. Under the QMS this is acceptance-design code (CR-0011 A3).

### 3.4 Observation models (integrated likelihood)

**O1. eBird complete checklists (main fit; EBD + SED for ME/NH/VT plus border strips, 2016–2025).**
- *Filters:* Johnston et al. 2021 (complete; stationary/traveling; ≤ 5 h; ≤ 5 km; ≤ 10 observers; group-deduplicated).
- *Footprint* $B_i$: a disk of radius $150\text{ m}+\tfrac12\text{dist}_i$.
- *Likelihood* (Royle–Nichols on the footprint):

$$P(y_i=1)=1-\exp\Big(-\textstyle\sum_{s\in B_i}D(s,Y_i)A_{\text{cell}}\cdot e^{g(e_i)}\Big)$$
$$g(e_i)=\alpha_0+\alpha_1^+\log\text{dur}+\alpha_2^+\log(1+\text{dist})+\alpha_3\log\text{obs}+f_{\text{doy}}+f_{\text{tod}}+\alpha_4\text{skill}_{o(i)}+u_{o(i)}$$

**Rule R-b.** $g$ contains **no location-derived variable**: no hotspot distance, no trail distance, no checklist density. §9 explains why D's choice here removes real habitat signal. Observer skill is computed out-of-fold from the observer's other checklists (Kelling et al. 2015).

**O2. Aggregate flush rates (scale and year level only).**
- *Data:* the NH small-game and wing-and-tail survey, plus whatever ME IF&W and VT FWD release. For the NY DEC and CT DEEP logs, the method is the analogue.
- *Model:*

$$\Phi_{gY}\sim\text{NegBin}\big(H_{gY}\,2Wv\,\textstyle\sum_s h_g(s)D(s,Y),\phi\big),\qquad h_g\propto \text{acc}(s)\cdot(K*q)^{\eta}$$

- Gradients from O2 are **stopped** into every shape parameter. O2 updates only $\beta_0$, $\tau$, $W$, $v$ and $\eta$. This answers C's ecological-fallacy objection.

**O3. GPS hunt logs (the estimand itself) and the transfer term.**
- *Protocol:* a GPX track at 1 Hz, one waypoint per flush (seen or heard), plus dog yes/no and weather.
- *Model:*

$$\text{flushes}_j\sim\text{NegBin}\Big(\textstyle\sum_s 2W\ell_{js}D(s,Y_j)e^{\delta(s)+\xi\,\text{press}(s,t_j)},\phi_3\Big)$$

- $\delta(s)=\delta_1\,\text{dense}(s)+\delta_2\,\text{open}(s)$, where dense = `under` high or `age` 3–12 yr, and open = mature with low `under`.
- **Why it exists.** eBird detection of grouse is partly auditory (spring drumming) and partly visual (roadside birds). Its habitat dependence differs from a hunter's flush detection. That difference cannot be identified from eBird alone. It *can* be identified from hunt logs, where detection is the product's own detection.
- With two or three parameters, about 60–100 logged hours is enough to estimate it.
- $\xi$ models depletion from hunting pressure (distance to parking × week).
- In season 2026, O3 is **held out** as the test. From 2027, it trains $\delta$ and $\xi$.

**O4. Acoustic drumming (validation only).**
- *Data:* the Vermont GMNF ARU release (Clarfeld et al. 2025; 9,500+ h, 2022–23); optionally the owner's own AudioMoths.
- *Metric:* **drums per recorder-day**, not naive occupancy. Lapp et al. report about 61% 28-day detection, so occupancy saturates (see the E critique in §9).
- *Model:* drum rate ~ $D\cdot p_d$ within about 200 m.

**Joint objective:**

$$\mathcal L=\ell_{O1}+\ell_{O2}^{\text{(level only)}}+\ell_{O3}^{\text{(from 2027)}}+\log p(\theta)$$

- MAP is fitted with L-BFGS in PyTorch.
- The posterior uses a Laplace approximation, or NumPyro NUTS on a bandwidth grid.
- Folds are **25 km blocks**. That is larger than any footprint diameter (≤ 5.3 km) plus the kernel (≤ 1.8 km at 3σ), which satisfies rule R-c.

### 3.5 Inference and end product: Covert Finder

1. **Covert objects** (from D):
   - disturbance patches aged 4–25 yr;
   - shrub-wetland, old-field and aspen stands;
   - a 25 ha hexagon background lattice.
   All are clipped at 2–40 ha.
2. **Per covert:**
   - $\hat F$ in flushes/h with an 80% interval; the scale is labelled "relative" until O2/O3 anchor it;
   - a 3-year trajectory: rising, peak or declining;
   - age, guild and understory class;
   - "why", from the additive term contributions. CYM is additive, so this is exact, not SHAP;
   - access class A1–A4 (from D);
   - walk-in distance and elevation gain;
   - an extrapolation flag (the covert's covariates fall outside the visited-checklist support, §6 T4);
   - an explored flag.
3. **Daily recommender** (from D, with one change). Five coverts within the chosen drive radius:
   - **four by Thompson sampling** from the posterior;
   - **one uniformly random accessible covert from the top 30%**.
   The random slot gives an unbiased estimate of lift on the owner's own hunts.
4. **Loop planner.** A 60–120 min walking loop from a parking point that maximises $\sum \hat F\cdot$ time, solved by beam search on a cost raster.
5. **Rule-out layer** (from E): areas with high checklist effort and confidently low $D$.
6. **Season outlook:** $e^{\tau_r(Y)}$ from spring drumming and brood reports.
7. **Outputs:** GeoPackage, GPX/KML, and a static web map.

---

## 4. Why it beats the status quo and the other four designs

| Problem (report §) | Status quo | Shared core (B–E) | What CYM adds |
|---|---|---|---|
| The data is the ceiling (§5.4) | More capacity | New labels with effort | New labels **plus** a structural prior. Information goes into ~40 parameters, so the scarce detections are not spread over 10⁵–10⁷ weights |
| PU and the 1−a/2 bound (§4.1, §4.4) | TG negatives | Real non-detections | Same |
| Effort bias (§5.3) | Partial cancellation | Effort tower | Same, plus rule R-b (no location-derived effort variables) |
| **Preferential sampling into the target** | Not addressed | Mostly unaddressed. E uses importance weights in evaluation only | Shape constraints keep extrapolation sane in unvisited young off-trail cover. Tested by T2; flagged per covert by T4 |
| **Habitat-dependent detectability** | Not addressed | Acknowledged as a risk (B R3, C R1, D K1) | A transfer term fitted on hunt logs, plus an acoustic drum-rate check |
| Succession clock (§5.6 Q5) | Static | Clock in C, D and E | Clock + severity + 2025–26 DIST-ALERT + an explicit unimodal age curve whose fitted peak is an ecological unit test |
| Estimand (§5.1) | Ratio at 50:50 | Standardised encounter rate | Flushes/h with physics priors on $W$ and $v$, so the scale is meaningful before O2 |
| No external truth (§5.6) | None | ARU and hunt logs in 2027 | **A blinded field test in the 2026 season**, using the zero-fit prior map |
| Feasibility | 12 M parameters | FCN (B), 560 features (C), neural ISDM (D), a 36 GB/yr feature cube (E) | ~40 parameters, minutes per fit; the GPU is used only for convolutions at prediction |
| Interpretability and audit | IG/SHAP | SHAP | Every parameter has an ecological meaning and a literature prior; a fitted peak at 40 yr is visibly wrong |

**On the +0.001 from harvest history.** That figure was measured under the presence-versus-target-group label. T1 tests, on real complete checklists in week 1, whether stand age is visible under a detection label. If it is still invisible there, CYM's core premise fails (§6).

---

## 5. Expected gains, and how not to fool ourselves

### 5.1 Expectations

| Metric | Expected | Confidence | Sample needed to see it |
|---|---|---|---|
| Legacy presence-vs-TG AUC | 0.70–0.77. **Not optimised**; may drop | high | — |
| T1 (real EBD, held-out 25 km blocks): effort-adjusted AUC of prior-mean $D_0$ minus that of the CNN score | −0.01 to +0.04 | low | Detection count unmeasured; at ~10k detections, SE ≈ 0.01 |
| H set, fitted CYM: TkL₅ | 1.5–2.2×; the CNN gives 1.2–1.6× | low | Block bootstrap; ties under 0.15× |
| H set: effort-stratified AUC, CYM vs the best flexible shared-core model (GBM twin) | −0.02 to +0.01. **CYM may lose in-sample** | medium | — |
| **Extrapolation set** (H checklists in support-poor young forest, T4): CYM vs GBM twin | CYM better by 0.02–0.05 AUC | low | This is the bet that differentiates CYM; it may be underpowered (few such checklists) |
| 2026 field test: prior-CYM vs random accessible top-30% | 1.3–2.5× flush rate | medium-low | About 20 h/arm detects only ≥ 2× (SE of log ratio ≈ 0.3) |
| 2026 field test: prior-CYM vs CNN top decile | 0.8–1.5×; **could lose** | low | 1.2× needs about 120 h/arm, so it is a multi-season result |
| ARU drum rate: Spearman with $\hat D$ (GMNF) | 0.25–0.5 | low | Depends on the number of sites (**unknown**) |

### 5.2 Guards

- The prior-mean map, H, the folds, the metrics, $w^\star$ and the kill thresholds are frozen in a committed acceptance script before anything is fitted (CR-0011 A3).
- Every comparison includes:
  - effort-only;
  - the current CNN, re-scored after the CR-0035 registration repair;
  - the zero-parameter heuristic H250 (share of 5–20-year cuts within 250 m);
  - the GBM twin from the shared core;
  - eBird Status & Trends, on post-2023 checklists only.
- Each result is reported on the full H set, the fall-only subset and the extrapolation subset.
- Field test protocol:
  - arms are assigned by the script;
  - the hunter sees only "covert 1–3";
  - 45–60 min per covert;
  - a NegBin GLMM with a day random effect;
  - a one-sided test pre-registered for "prior-CYM vs random".

---

## 6. Risks, failure modes and falsification, in the order they run

**Tier 0, days 1–3, no labels.**
- **T0. Build and freeze the prior-mean map $D_0$ and the covert layer** for ME/NH/VT, season 2026. Effort: about 2 days on EC2, mostly Earth Engine exports and kernel convolutions on the GPU.
- **T3. Freshness audit** (from D). The share of the current CNN's top-5% pixels that were cut in 2023–2026 (LCMS/Hansen/DIST), or that are older than 30 years in 2026.
  - *Reading:* below 3% means freshness is not a material argument against the CNN.

**Tier 1, week 1: real complete checklists, no fitting of CYM.**

**T1. Zero-tuning falsification on real EBD checklists** (E's comparison, made stricter).
1. Ingest EBD + SED for ME/NH/VT 2016–2025 with `ebird_checklists.py`:
   - apply the Johnston et al. 2021 filters;
   - zero-fill grouse;
   - deduplicate shared checklists by group;
   - attach footprints $B_i$ and 25 km-block folds.
   In the same pass, measure the counts of detections and non-detections, overall and for fall only.
2. Fit an **effort-only** detection model on the training folds: $g(e)$ from §3.4, with no habitat term and no location-derived variable (rule R-b).
3. Add one map score at a time as a single offset-plus-slope covariate, evaluated on held-out blocks. Every score is computed before it sees any checklist:
   - (a) the current CNN score, footprint-averaged;
   - (b) H250;
   - (c) the frozen prior-mean $D_0$, footprint-averaged.

   For reference only, also run (d) the GBM twin fitted on the training folds.
4. Report three metrics:
   - effort-adjusted held-out deviance gain;
   - effort-stratified AUC (protocol × duration tercile × month × year);
   - TkL₅.

   Report each on the full set, the fall-only subset and the H subset (from C).

**CYM's premise is falsified if** both:
- the deviance gain and the stratified AUC of (c) are no better than (a) by more than one block-bootstrap SE; and
- (c) is no better than (b), meaning the structure adds nothing over a one-variable heuristic.

*Consequence:* drop the structural core and adopt the shared-core GBM with CYM's product, evaluation and field-test layers.

**T2. Preferential-sampling injection–recovery (B's method, re-aimed).**
1. Take real birder geometry: the EBD checklist start points, footprints and effort vectors from T1.
2. Simulate two synthetic truths:
   - (i) CYM-shaped;
   - (ii) a CNN-like truth: GBM-learned on random features, so it is not CYM-shaped.
3. Add **preferential sampling**: visit probability is low in dense young cover and high near trails, as measured by T4.
4. Fit both CYM and the GBM twin on the visited points, and score recovery on *unvisited* young-forest cells.

**Reading:**
- *Falsified for CYM* if the GBM twin recovers truth (ii) in unvisited cells as well as CYM recovers truth (i), within 0.02 Spearman. Shape constraints would then buy no robustness.
- Under truth (ii), CYM *should* lose. That is reported, and it bounds the cost of a wrong prior.

**T4. Coverage audit.** The density ratio between visited and available area by age class × understory class × distance to road. Its outputs are the extrapolation subset of H and the per-covert extrapolation flag.

**Tier 2, weeks 2–3: fitted CYM, the H-set head-to-head.**
- Fitted CYM vs the GBM twin vs the CNN on TkL and effort-stratified AUC (full, fall-only and extrapolation subsets).
- **Kill rule for the residual $r$:** it is admitted only if it improves held-out TkL and deviance on H *and* does not degrade the T2 unvisited-cell recovery.

**Tier 3, the 2026 season: the field test.**
- Arms: prior-CYM / CNN / random, with each day's arm assignment randomised and blinded.
- With one hunter and about 20 h per arm, only differences of 2× or more are detectable. That is stated in advance.
- The data then trains $\delta$ and $\xi$ for 2027.

**Risk table:**

| Risk | Mitigation |
|---|---|
| Partial harvests are missed (Maine shelterwood) | Severity term, lidar understory, HF437, DIST |
| Grouse rarely reported in fall checklists | Season enters $g$; the transfer term fixes fall detection; fall-only reporting |
| The prior is wrong | Soft priors; fitted parameters audited against ecology; T2 bounds the cost |
| Grouse-targeted visits in EBD (preferential sampling beyond $x$) | Observer random effect; a sensitivity run dropping the top-1% grouse-reporting observers (from B); T1 is a gate, not the final answer |
| Access errors | Class A4 is never shown as open; product is for personal use |
| Registration bugs in new exports | Template `crsTransform` plus existing probes; kernel smoothing at 150–600 m dampens sub-pixel shifts |
| The hunt-log sample is small | Power stated; logs accumulate across seasons; only 2–3 transfer parameters |

---

## 7. Implementation plan

Each phase is one CR (CR-0011 A5). Acceptance scripts land before approval (A3). New modules:
- `habitat_cube.py`
- `cym_prior.py`
- `sim_prefsampling.py`
- `ebird_checklists.py`
- `cym_fit.py`
- `eval_h.py`
- `covert_finder.py`
- `hunt_log.py`

| Phase | Work | Effort | Gate |
|---|---|---|---|
| **Day 0** | Start the EBD + SED download (access already held). Email NH F&G, ME IF&W and VT FWD (flush/hour tables by unit and year; drumming stops) and USGS VT Coop (GMNF ARU sites). Commit the acceptance script (H set, folds, metrics, thresholds) | 0.5 d | — |
| **Days 1–3** | `habitat_cube.py` for 2026 (`age`, `sev`, `regen`, `conif`, `dev`, NLCD, `snow`; Meta-CHM `under` fallback). `cym_prior.py` → frozen $D_0$ and covert layer with access. T3 freshness audit | 2–3 d | Registration probes pass. **The owner starts hunting the blinded three-arm test** |
| Days 2–7 (in parallel with T0) | `ebird_checklists.py` ingest; T1 on real checklists; T2 (injection–recovery on EBD geometry); T4 (coverage) | 4–5 d | T1 falsification rule |
| Weeks 2–3 | `cym_fit.py` (O1 + O2 level), GBM twin, `eval_h.py` | 1.5 wk | Kill rules for the core and the residual |
| Weeks 3–5 | Lidar `under` from LAZ (PDAL, per region); AlphaEarth residual test; NumPyro posterior; recommender and loop planner | 2 wk | — |
| Season end | Analyse the field test; fit $\delta$ and $\xi$; publish season-2027 coverts | 1 wk | Pre-registered field endpoints |

**First experiments the owner can run on EC2 today:** T0 plus T3, with the EBD download and `ebird_checklists.py` ingest running in parallel so T1 runs on real complete checklists within the week. The disturbance fusion and NLCD exports go through Earth Engine on the template grid. Kernel convolutions run in PyTorch. With prior-mean parameters, the result is a covert GeoPackage ready for tomorrow's hunt. The freshness audit uses the same exports.

---

## 8. References

URLs were checked in rounds 1–2 unless marked **unverified**.

1. Pasquarella & Thompson (2023). Annual maps of forest harvest events in Maine 1986–2019, HF437. https://doi.org/10.6073/pasta/20a838c4bd6922685b3d00661d45c414
2. LCMS v2024-10 (GEE). https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10
3. Hansen GFC v1.12 (GEE). https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12
4. OPERA DIST-ANN-HLS (GEE). https://developers.google.com/earth-engine/datasets/catalog/OPERA_DIST_L3_DIST-ANN-HLS_V1 (verified by D, not by me)
5. eBird Basic Dataset. https://ebird.org/data/download . GBIF eBird dataset key `4fa7b334-ce0d-4e88-aaae-2e0c138d049e`; I queried the API on 2026-10-05: no eventID or effort fields, while `recordedBy`, `eventDate` and coordinates are present. https://api.gbif.org/v1/occurrence/search?datasetKey=4fa7b334-ce0d-4e88-aaae-2e0c138d049e
6. Johnston et al. (2021). *Diversity and Distributions* 27:1265–1277. doi:10.1111/ddi.13271 (**not re-checked**)
7. Kelling et al. (2015). *PLoS ONE* 10:e0139600. doi:10.1371/journal.pone.0139600 (from B)
8. Royle & Nichols (2003). *Ecology* 84:777–790 (**DOI not re-checked**)
9. Lucas/Nandi et al. (2023). disaggregation. *J. Stat. Softw.* 106(11). https://jstatsoft.org/index.php/jss/article/view/v106i11/4476
10. Lapp et al. (2023). *Wildlife Society Bulletin* 47(1). doi:10.1002/wsb.1395
11. Clarfeld et al. (2025). Ruffed Grouse ARU, GMNF Vermont 2022–23, USGS data release. doi:10.5066/P13EFLXX. https://www.usgs.gov/data/two-stage-models-improve-machine-learning-classifiers-wildlife-research-a-case-study (verified; site coordinates not on the page)
12. Google Satellite Embedding V1 (AlphaEarth). https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL
13. NH Fish & Game (2025). Season opening (1 October) and survey programmes. https://nhfishgame.com/2025/09/22/ruffed-grouse-and-woodcock-seasons-start-october-1/ . The flush rates of 2.27/h and 1.31/h are search-summary figures (**unverified**). ME and VT season dates are **unverified**.
14. NY DEC grouse report (drumming does not consistently predict WMU flush rates). https://extapps.dec.ny.gov/docs/wildlife_pdf/grousedrumrpt22.pdf (**search summary only**)
15. Vermont lidar: https://vcgi.vermont.gov/document/2023-vermont-lidar-plan ; NH: https://des.nh.gov/news-and-media/milestone-statewide-high-resolution-elevation-data-has-been-reached ; ME: https://pubs.usgs.gov/publication/fs20233036/full
16. PAD-US. https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download (verified by D); NH Current Use: https://www.wildlife.nh.gov/current-use (verified by D)
17. Diggle, Menezes & Su (2010). Geostatistical inference under preferential sampling. *JRSS C* 59:191–232 (**from memory, unverified**)
18. Guo et al. (2019). PAL. doi:10.1145/3298689.3347033 (the two-tower idea, via B)
19. Repository: `docs/grouse_model_report.md` §1–§6; `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md` (harvest history +0.001); `diagnose_disturbance_features.py`; `diagnose_gbm_baseline.py`; `generate_negatives.py`.

---

## 9. Critique of competitors

Each row gives the strongest flaw I could find.

| Design | Flaw | Severity | Evidence / failure scenario |
|---|---|---|---|
| **B (CEM)** | **Fold geometry discards the traveling checklists it was built for.** CV reuses 3 km blocks, and any footprint that straddles a fold boundary is excluded. A 2 km traveling list has σ = √(150² + 700²) ≈ 0.72 km, so its 3σ disk is about 4.3 km across, wider than a 3 km block. It almost always touches another fold and is dropped, so held-out evaluation becomes mostly stationary and short checklists. That is the population where the footprint MIL adds least, and it is biased toward hotspots | MAJOR | B §3.3 kernel and §3.4 "footprints that straddle a fold boundary go to a buffer". B says the variogram sets the final size, so this is not BLOCKING |
| B | The habitat tower keeps `road_dist` and the legacy lens, with no succession clock or 2025–26 disturbance. Its map is stale by the same 1–4 years as the status quo, and `road_dist` in $f$ can still carry residual preferential sampling that a location-free $g$ cannot remove | MEDIUM | B §3.3 "Inputs … unchanged"; report §2.4.2 |
| B | F0 injection–recovery uses a CEM-shaped truth (B concedes this) and the TG pool as checklist starts. It cannot falsify CEM, only the status quo | MEDIUM | B §6 caveat |
| **C (FLUSH-C)** | **The trajectory is incoherent and the inputs are stale for 2026.** The "5-year trajectory" shifts the age fractions while holding the AlphaEarth embedding fixed. The embedding is the primary representation and already encodes current structure, so the model sees combinations that never occur in training ("embedding says open clearcut, age says 12 years"). The embedding also ends in 2024, so 2025–26 cuts appear as intact forest in the main input for the 2026 season | MAJOR | C §3.7 step 3 ("embedding is held fixed"); the AlphaEarth catalog (2017–2024) |
| C | The H set excludes checklists within 1 km of H blocks, but features use discs up to 2.4 km, so training and H share inputs. This is minor next to label independence | LOW | C §3.3–3.4 |
| C | "Balancing affects variance, not bias, because the target is conditional" holds only under correct specification; under misspecification, a reweighting changes the fitted function | LOW | Standard result |
| **D (COVERT)** | **Location-derived effort variables remove real habitat signal.** Distance to hotspot, distance to trail and 1 km checklist density go into $g$ and are set to "median non-hotspot forest" at prediction. A gradient-reversal adversary also stops $f$ from predicting checklist density. Grouse are plausibly denser in remote, low-effort industrial forest (NH reports the highest densities in the North Country, where effort is lowest). These covariates are then collinear with true density. $g$ absorbs the remoteness effect, which is deleted at prediction, and the adversary penalises $f$ for learning it. The map is flattened exactly in the north woods | MAJOR (close to BLOCKING for northern Maine/NH ranking) | D §3.2.1 "Effort and birder-ness nuisance", "gradient-reversal adversary"; NH F&G 2025 ("most abundant in the northern part of the state") |
| D | The E1 probe ($R^2$ of the CNN logit on effort layers) is confounded for the same reason. A high $R^2$ may mean grouse habitat correlates with remoteness, not that the map is an effort map, so it cannot falsify | MEDIUM | D §6 E1 |
| D | The LightGBM custom objective with a 7-row disk stencil aggregated by log-sum-exp is feasible through the chain rule, but non-standard and easy to get wrong | LOW | D §3.4(a) |
| **E (FLUSH-E)** | **The day-1 test regresses on an effort proxy that depends on habitat.** (This is moot now that EBD is in hand, but it still applies to any GBIF stop-gap.) It uses species count as the effort proxy in both arms. Richness rises at edges and in young or mixed cover, which is grouse habitat, so `n_species` carries habitat signal into both models. That shrinks the habitat-feature advantage and can produce a false "(a) ≈ (b)" reading, which would wrongly kill the design | MAJOR | E §7 step 5 ("n_species (effort proxy)"). CYM T1 uses EBD effort fields and within-stratum AUC instead |
| E | The ARU criterion uses naive occupancy (top quintile ≥ 2× bottom). With 28-day detection near 61% of sites (Lapp et al.), occupancy saturates: if the bottom quintile is at 40%, a 2× ratio is nearly unreachable. Use drum rate per day | MEDIUM | E §3.7 M4; Lapp et al. 2023 |
| E | Feasibility: the feature cube is about 36 GB/yr, while training wants each checklist's own year for 2010–2025 (about 0.5 TB) yet stores only 3–4 key years. These contradict each other | MEDIUM | E §3.5 and §7 Phase 2 |
| **All, including round-1 A** | Detectability depends on habitat (drumming audibility, visual cover) and none can identify it from eBird. The others accept it as a risk; CYM v2 adds the hunt-log transfer term and the drum-rate check | — | B R3, C R1, D K1, E pre-mortem |
