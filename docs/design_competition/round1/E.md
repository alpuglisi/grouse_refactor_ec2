# Design E — FLUSH: a succession-clocked, multi-likelihood intensity model that predicts flushes per hour, not "grouse record vs other-bird record"

*Designer E, round 1. Primary technique: SCAMPER over all nine pipeline stages, plus TRIZ contradiction resolution. Secondary techniques: a weighted convergence matrix and a "pre-mortem" (§6).*

---

## 1. Pitch

The current model is very good at one question: does a 1.9 km landscape look more like where eBird users report grouse than like where they report ten other species? The report shows that this question is capped at an AUC of about 0.77. Three things set the cap: the labels (target-group background, positive–unlabelled contamination, the 1 − a/2 bound), the effort process, and the static estimand. The network is not the limit. **FLUSH changes the question.** It replaces the classifier with one latent field, λ(s, t): the relative density of grouse in 30 m cell *s* during hunting season *t*.

That field is fitted jointly to four kinds of observation, each through its own observation model:

1. **Zero-filled eBird complete checklists** (detections *and* non-detections, with effort). These enter through a Poisson–Bernoulli multiple-instance likelihood over each checklist's spatial footprint.
2. The **existing presence-only records**, modelled as a thinned point process with an explicit effort tower.
3. **State hunter flush-rate indices** (flushes per hour by region and year). These enter as a disaggregation-regression likelihood, so the map is anchored to the quantity a hunter actually experiences.
4. **Spring drumming detections** from cheap acoustic recorders, which are an independent, design-based test set.

The covariates gain a time axis. Each pixel carries its full 1985–2024 Landsat disturbance and recovery history (LCMS, Hansen GFC, LandTrendr), so stand age is a clock that can be advanced to next October. The end product is no longer a suitability raster. It is a ranked list of **huntable covert polygons**, each with expected flushes per hour, an uncertainty band, a "peak years" window and access status. The design is judged on hunter-relevant metrics: held-out flush-rate rank correlation, top-decile enrichment of held-out detections and drumming, and a prospective field test. The 0.77 presence-vs-background AUC is still reported, but the design argues that it is the wrong target.

---

## 2. Brainstorming record

### 2.1 SCAMPER over every pipeline stage (raw ideas, unfiltered)

| Stage | S – Substitute | C – Combine | A – Adapt | M – Modify/Magnify | P – Put to other use | E – Eliminate | R – Reverse |
|---|---|---|---|---|---|---|---|
| **1 Records** | eBird *complete checklists* (EBD) instead of GBIF detections only | Combine eBird + iNat + hunter logs + ARU in one likelihood | Adapt eBird Status & Trends practice (effort covariates, spatio-temporal subsampling) | Magnify the time span from 2020–24 to 2010–25 by letting covariates vary by year (removes the reason for YEAR_MIN) | Use other species' *checklist completeness* as evidence of grouse **non-detection** | Eliminate the "collapse repeat visits to latest year" step: repeats are information (closure) | Start from hunters: where do hunters flush birds, and work backwards to habitat |
| **2 Negatives** | Non-detections on complete checklists replace target-group background | Combine non-detections with a detection-probability model | Adapt the occupancy/Royle–Nichols idea that heterogeneity in detection = heterogeneity in abundance | Magnify negatives ~100× (every complete checklist without grouse) | Use the TG pool as an *effort* map, not as labels | **Eliminate the 300 m buffer, envelope weights and NONVEG quota**: these are design hacks for a missing likelihood | Reverse: model where grouse are *not detected despite effort* ("rule-out map") |
| **3 Rasters** | LCMS/GFC/LandTrendr annual history for the single-year `tsd` | Combine leaf-on and leaf-off Landsat/S2 to see deciduous understory under conifer | Adapt forestry growth-and-yield logic: age advances one year per year | Magnify temporal depth (40 years) more than spatial resolution | Use 3DEP lidar (VT statewide; NH/ME partial) as *privileged information* at training time only | Eliminate the categorical code soup (10,000-row EVT embeddings) in favour of physically meaningful continuous traits | Reverse the time direction: forecast the map to future seasons |
| **4 Window** | Footprint kernel derived from checklist effort replaces a fixed 64×64 window around a pin | Combine pixel scale, home-range scale (250 m) and landscape scale (1 km) as separate tokens | Adapt MIL "bags" from pathology (slide = bag, tile = instance) | Make the window variable per record (traveling distance) | Use the window as a location-error integral, not just as context | Eliminate the centre-skip assumption that the label belongs to the centre cell | Reverse: predict per pixel and aggregate to the record, instead of predicting the record from a window |
| **5 CNN** | Per-pixel habitat tower (small receptive field ~600 m) + separate effort tower | Combine NN tower with a GBM baseline through stacking | Adapt neural hierarchical models (Joseph 2020) | Make the network *smaller*: capacity is not the bottleneck | Use the current CNN as a teacher or feature for the new tower | Eliminate ImageNet ResNet-18 (91% of parameters, irrelevant prior) | Reverse: the network outputs an intensity that is integrated, not a probability |
| **6 Loss** | Poisson–Bernoulli (cloglog) MIL likelihood replaces AN-full/focal | Sum of likelihoods across data types (integrated SDM) | Adapt disaggregation regression (malaria mapping) to flush-rate indices | Magnify weight on design-based data | Use the loss to *identify* the intercept (absolute scale) through flush rates | Eliminate label smoothing and focal loss (improper scoring rules) | Loss on aggregates (region-year) back-propagates to pixels |
| **7 Validation** | Held-out checklists, held-out regions' flush rates, held-out ARU stations | Combine spatial-block CV with a prospective field test | Adapt design-based map accuracy (Wadoux 2021) | Magnify blocks to ≥ residual variogram range (likely 10–30 km) | Use the validation set as an *effort-standardised* benchmark | Eliminate AUC on TG background as the selection metric | Validate forward in time (train ≤2022, test 2023–25) |
| **8 Calibration** | Calibrate to flushes per hour, not 50:50 prevalence | Combine Platt-free proper likelihood with year random effects | Adapt Elkan–Noto only where needed | Make calibration per state/region | Use calibration residuals to diagnose effort leakage | Eliminate `--prior` scenario guessing | Calibrate the map *to hunters* |
| **9 Map** | Covert polygons with E[flushes/hr] replace a pixel raster | Combine habitat with access (PAD-US, OSM gated roads) | Adapt route-planning (orienteering) for a hunt day | Magnify forward: 2026, 2027, 2028 maps | Use the map for ARU placement (active learning) | Eliminate pixels below forest/access thresholds | Reverse: show "rising" coverts (cuts entering peak) as well as "current" ones |

### 2.2 TRIZ contradictions and their resolutions

| # | Contradiction (improving X worsens Y) | TRIZ principle(s) | Resolution adopted |
|---|---|---|---|
| T1 | **More context ↔ more label noise.** A bigger window sees the home range and absorbs location error, but blurs which pixel the label belongs to and lets the network latch onto effort proxies anywhere in the window. | **#1 Segmentation**, **#24 Intermediary** | Split "context" into two parts. (a) *Ecological context*: a habitat tower with a bounded receptive field of about 600 m (home-range scale, §1.5 of the report). (b) *Location uncertainty*: an explicit footprint kernel K_j per checklist. The label attaches to the kernel-integrated intensity, never to one pixel (§3.3). |
| T2 | **Fine resolution ↔ data availability.** 1 m lidar and understory metrics exist only in parts of the region and at single epochs; 30 m annual products exist everywhere. | **#37 Another dimension (time)**, **#26 Copying**, **#10 Prior action** | Gain resolution *in time*, not space. Forty annual Landsat-derived disturbance and recovery layers are available everywhere at 30 m. Where 3DEP lidar exists, use it as *privileged information*: an auxiliary head predicts lidar understory metrics from Landsat-history features at training time, so it is not needed at inference (§3.4). |
| T3 | **More negatives ↔ more false negatives.** Adding background raises PU contamination (the report's 1 − a/2 bound). | **#22 Convert harm into benefit**, **#23 Feedback** | Replace "negatives" with *non-detections with known effort*. A non-detection on a 5-minute stationary count at a hotspot is weak evidence. One on a 3-hour, 6 km walk is strong evidence. The likelihood weights each automatically through ρ_j and K_j. False negatives are now modelled, not suppressed. |
| T4 | **Static map ↔ succession dynamics.** A static map is simple to train and use, but the habitat clock runs at 5–25 years and the map is stale on arrival. | **#15 Dynamics**, **#10 Prior action**, **#37 Another dimension** | Make every covariate a function of (s, t). Stand age advances deterministically. Predict t = next season, and t+1 and t+2 for forward-looking coverts. Training uses each record's own year, which removes the vintage-leak problem that forced year matching. |
| T5 | **Effort correction ↔ habitat signal.** Removing road distance removes effort bias but also real forest-road selection by broods. | **#2 Taking out**, **#3 Local quality** | Give effort its own tower, ρ(effort, access, observer), which is dropped at prediction. Complete checklists *condition on an observer being present*, so the "where birders go" part of the bias is absorbed by the denominator of visited places. What remains in λ is habitat given presence. |
| T6 | **Hunter-relevant truth ↔ spatial resolution of that truth.** Flush rates are what hunters care about, but they come aggregated to regions and years. | **#24 Intermediary**, **#17 Another dimension (aggregation level)** | Use disaggregation regression. The coarse flush index constrains the *sum* of the fine λ, and the fine data constrain its *allocation*. |
| T7 | **Precision of evaluation ↔ independence of evaluation data.** Internal block-CV is precise but self-referential; field data are independent but scarce. | **#11 Beforehand cushioning**, **#25 Self-service** | Pre-register a small, power-calculated prospective test (ARU drumming plus hunt logs) stratified by predicted decile. The map chooses where to sample (self-service), and the sampling is design-based. |

### 2.3 Convergence

I scored 23 distinct candidate ideas from the two tables on four criteria (1–5 each). The criteria were: **new information** (does it add bits the current data lacks, the only lever the report says works), **hunter relevance**, **feasibility on the owner's stack within weeks**, and **falsifiability**. Ideas scoring 15 or more formed the core. Ideas scoring 11–14 became options. The rest were dropped.

| Idea | Info | Hunter | Feasible | Falsifiable | Σ | Fate |
|---|---|---|---|---|---|---|
| Zero-filled complete checklists + effort | 5 | 4 | 4 | 5 | **18** | Core |
| MIL footprint kernel (T1) | 4 | 3 | 4 | 4 | **15** | Core |
| Effort tower dropped at prediction (T5) | 3 | 4 | 5 | 4 | **16** | Core |
| Annual disturbance-history clock (T4) | 3 | 5 | 4 | 4 | **16** | Core |
| Covert polygon product with access | 1 | 5 | 4 | 5 | **15** | Core (product) |
| Flush-rate disaggregation (T6) | 4 | 5 | 3 | 3 | **15** | Core, but weak weight (few region-years) |
| Prospective ARU + hunt-log test (T7) | 5 | 5 | 3 | 5 | **18** | Core (evaluation) |
| Lidar as privileged information (T2) | 3 | 3 | 3 | 3 | 12 | Option, phase 4 |
| eBird S&T 3 km abundance as a coarse offset | 3 | 3 | 4 | 2 | 12 | Option; contaminates CV (§3.8) |
| Leaf-off/leaf-on spectral understory | 3 | 3 | 3 | 3 | 12 | Option |
| Stacking with GBM | 1 | 2 | 5 | 4 | 12 | Option (baseline anyway) |
| Orienteering route planner | 0 | 4 | 3 | 2 | 9 | Dropped (nice-to-have UI) |
| Reverse "rule-out map" | 1 | 3 | 5 | 3 | 12 | Free by-product: low-λ, high-effort areas |
| Keep ResNet-18 trunk | 0 | 0 | 5 | 2 | 7 | Dropped |
| nnPU on TG background | 1 | 1 | 5 | 3 | 10 | Superseded by T3 resolution |
| Bigger window / more attention | 0 | 1 | 5 | 2 | 8 | Dropped: the report shows capacity is not binding |

The core is one idea seen from several sides: **fit one latent, time-indexed intensity to every observation process we can get, each with its own honest observation model, and report it on the hunter's scale.**

---

## 3. The design

### 3.1 Estimand

Let λ(s, t) ≥ 0 be the **expected autumn density of ruffed grouse in 30 m cell *s* in year *t*, up to one global scale**. Habitat use is treated as approximately stationary within a year for a resident species, and a seasonal adjustment is carried in the detection model (§3.3).

The hunter-facing quantity for a covert polygon C, hunted in season t with a dog and a typical walking pattern, is

$$F(C,t)\;=\;\kappa_t\cdot\frac{1}{|C|}\sum_{s\in C}a(s)\,\lambda(s,t)\quad\text{[expected flushes per hour]},$$

The terms are:

- a(s) ∈ [0, 1] is a walkability weight. It is 0 on open water and closed-canopy conifer swamp, and lower in dense blowdown. It is optional and defaults to 1 on forest.
- κ_t is a year factor that absorbs population cycles, weather, WNV and similar effects. It is shared across the region and estimated from flush-rate indices. For ranking within a season it cancels, so the **ranking of coverts depends only on λ**.

This is a demographic-adjacent quantity (relative abundance). It is neither "probability of being reported" nor occupancy. Occupancy of a polygon follows as ψ(C) = 1 − exp(−Σ_{s∈C} λ(s, t)·c) once c is anchored.

### 3.2 Data

| ID | Source | What it gives | Access | Notes |
|---|---|---|---|---|
| D1 | **eBird Basic Dataset (EBD) + Sampling Event Data**, ME/NH/VT, 2010–2025, complete checklists only | Grouse detection/non-detection per checklist, with protocol, duration, distance, observer count, start time, date, observer ID, locality type (hotspot vs personal) | Request at https://ebird.org/data/download (usually a few days); extract with `auk` (https://docs.ropensci.org/auk/) or a Python AWK equivalent | Count in Phase 0. Expected order 10⁵–10⁶ checklists, with grouse on a few percent, i.e. **several times the current 4,809 positives** plus all non-detections (estimate; **unverified**) |
| D2 | Existing GBIF grouse presence-only records (current `sightings.py`) plus iNaturalist research-grade | Presence-only | Already on disk | Lower weight; mainly for regions where checklists are sparse |
| D3 | **Hunter flush-rate indices**: NH Fish & Game ruffed grouse hunter survey (statewide and by 5 regions, flushes per hour, multi-year) [NHFG]. Request ME IF&W and VT F&W cooperator/hunter-log data if they exist (not found online; **unverified**) | Region-year flushes per hour, hours hunted | NH reports are public (wildlife.nh.gov small-game summary); others by request | Small n (about 5 regions × about 20 years in NH). It is a *constraint*, not a training engine |
| D4 | **Prospective acoustic drumming survey**: about 40 AudioMoth-class ARUs, April–May, stratified by predicted λ decile; the open-source drumming recogniser (Lapp et al. 2023, OpenSoundscape) | Design-based detection/non-detection with 28-day effort | Owner-collected; ~$100/unit (**unverified price**) | Lapp et al. found 28-day automated detection at 61% of sites vs 16% for field surveys, so detection is high |
| D5 | **Owner and friends' GPS hunt logs** (tracks + flush waypoints) | True hunter flushes per hour per covert | Owner app export (e.g. GPX) | Gold-standard product metric |
| D6 | **Disturbance history**: LCMS v2024-10 annual Change (fast loss / slow loss / gain), Land Cover, Land Use, and raw probabilities, 1985–2024 (`USFS/GTAC/LCMS/v2024-10`); Hansen GFC v1.12 `lossyear` 2001–2024 (`UMD/hansen/global_forest_change_2024_v1_12`); LandTrendr segmentation of Landsat NBR via the `LT-GEE` API | Year of last stand-replacing loss, magnitude, partial (slow) loss, recovery slope, number of disturbances in 40 y | Earth Engine | Pull on the template grid with an explicit `crsTransform` aligned to the template's pixel *corners*. This is the BUG-0094 lesson; see the PA list |
| D7 | Leaf-on (Jul–Aug) and leaf-off (Apr, Nov) Landsat/HLS medians for the latest 3 years | Deciduous fraction, understory greenness under leaf-off conifer gaps | Earth Engine (`NASA/HLS/HLSL30/v002`) | — |
| D8 | Existing layers: LANDFIRE EVT/EVH/EVC/SClass, TreeMap, Meta canopy height bins, TCC, NLCD | Composition and structure | On disk (after CR-0035 repair) | Kept, re-encoded as continuous traits where possible |
| D9 | 3DEP lidar (VT statewide QL2 2019 and QL1 plan; NH and ME partial) via USGS 3DEP / Microsoft Planetary Computer | Understory return fraction 1–5 m, canopy height variability | Public | Privileged-information head only (option) |
| D10 | Access: PAD-US 4.x (public and easement land), OSM tracks/gated roads, state WMA polygons | Product layer only; never a model input | Public | — |
| D11 | Daymet v4 winter snow-water equivalent, elevation (3DEP 30 m) | Climate/topography covariates | Earth Engine | — |

### 3.3 Observation models (the core)

**Latent field.**

$$\log\lambda(s,t)=h_\theta\big(Z(s,t)\big),$$

Here Z(s, t) is the feature vector of pixel s in year t (§3.4) and h_θ is the **habitat tower**.

**Checklist likelihood (D1): Poisson–Bernoulli multiple-instance learning.** Checklist *j* has reported location x_j, year t_j, protocol, distance d_j, duration τ_j, n_obs, observer o_j, day-of-year and start time. Its detection outcome is y_j ∈ {0, 1}.

Define the **footprint kernel** K_j(s) ≥ 0 with Σ_s K_j(s) = 1:

- *Stationary count:* an isotropic Gaussian with σ_j² = σ_det² + σ_loc,j². Here σ_det ≈ 150 m reflects drumming and flush audibility and visibility (**to be fitted**: σ_det is a learnable scalar with a weak prior). σ_loc,j is larger for hotspot pins (fit one value for hotspots and one for personal locations).
- *Traveling count:* the direction is unknown, so use a uniform disc of radius r_j = min(d_j/2, 2.5 km) convolved with the Gaussian above. Discard checklists with d_j > 5 km, as in the eBird best-practice guidelines.

Then

$$P(y_j=1)\;=\;1-\exp\!\Big(-\rho_j\sum_s K_j(s)\,\lambda(s,t_j)\Big),\qquad \log\rho_j=g_\phi(e_j).$$

This is the noisy-OR over instances of a multiple-instance bag, written on the Poisson scale. It is equivalent to a Royle–Nichols model in which the "site" is the footprint. Grouse anywhere in the bag can produce a detection, so the label never has to be pinned to a centre cell.

g_φ is the **effort/detection tower**. It takes:

- log τ_j, log(1 + d_j), n_obs and protocol;
- a cyclic encoding of day-of-year (drumming peaks in April–May; October flushes);
- time of day;
- an observer skill effect. Following Johnston et al. (2018), use an observer random effect or the checklist calibration index computed from all species. This is the "use other species for other purposes" move.
- the hotspot flag.

**Prediction drops g_φ entirely.** Maps show λ, not ρλ.

*Identifiability.* Within-location repeat visits (hotspots, and personal locations visited more than once in a season) provide the closure information that separates ρ from λ, as in N-mixture and Royle–Nichols models. Effort covariates vary independently of habitat within a location, which identifies g's slopes. Visit selection (which places get visited) is a covariate-shift problem, not a label problem: it biases the *training distribution* but not P(y | visit, Z). It is handled at evaluation with importance weights (§3.7).

**Presence-only likelihood (D2): thinned point process.** For incidental records, use a downweighted Poisson regression (Warton & Shepherd 2010) with intensity λ(s, t)·b(s), where log b(s) = u(s)ᵀγ is a bias model on road distance, trail density, population density and eBird checklist density. This shares nothing with g_φ except the observer-skill machinery, is weighted at w_PO ≤ 0.3, and is dropped at prediction.

**Flush-rate likelihood (D3): disaggregation regression.** For region r and year t, with H_rt hunter-hours and F_rt flushes (or a reported rate with an SE):

$$F_{rt}\sim\mathrm{NegBin}\Big(\mu_{rt}=H_{rt}\,\kappa_t\,\bar\Lambda_{rt},\ \text{size }\phi\Big),\qquad \bar\Lambda_{rt}=\frac{\sum_{s\in r}w^{\text{hunt}}(s)\,\lambda(s,t)}{\sum_{s\in r}w^{\text{hunt}}(s)}.$$

- w^hunt(s) is the probability that hunters walk cell *s*. A simple fixed model is forest within 400 m of a drivable or gated road, up-weighted on public land.
- If only the rate is published, use log F̂_rt ~ N(log μ_rt/H_rt, se²).
- log κ_t is a year random effect; a statewide effect is enough given the data.

This term constrains **between-region relative abundance**, which is exactly what presence data distort through effort (the report notes that NH grouse are densest in the north, where eBird effort is lowest). Gradients flow from the regional sum to every pixel, which is the defining trick of disaggregation regression (Lucas et al. 2021, `disaggregation` R package).

**ARU likelihood (D4), used for validation first and then optionally for training:**

$$P(\text{drumming detected at station }k\text{ in }T_k\text{ days})=1-\exp\!\big(-\rho^{\text{ARU}}T_k\textstyle\sum_sK^{\text{ARU}}_k(s)\lambda(s,t)\big),$$

with K^ARU a Gaussian of σ ≈ 200 m (**assumed** drumming audibility; to be checked against Lapp et al.).

**Total objective.**

$$\mathcal L(\theta,\phi,\gamma,\kappa)=-\sum_j\ell^{\text{CL}}_j-w_{\text{PO}}\,\ell^{\text{PO}}-w_{\text{F}}\sum_{r,t}\ell^{\text{F}}_{rt}\;[-\ell^{\text{ARU}}]\;+\;\mathcal R(\theta)+\tfrac{1}{2\sigma_\kappa^2}\sum_t(\log\kappa_t)^2 .$$

R is weight decay plus an optional smoothness penalty on the stand-age partial effect (§3.4). w_F is chosen so that the flush term contributes about 5–10% of the gradient norm; it should steer, not dominate. All terms are proper likelihoods: no focal loss, no label smoothing, no assumed negatives.

### 3.4 Features Z(s, t): the succession clock

All features are computed per pixel per year on the template grid, then summarised at three radii (90 m, 250 m and 600 m) by GPU box/disc filters. These match the 1 ha, about 20 ha and about 110 ha scales of §1.5 of the report.

1. **Clock features** from D6, computed as of year t (never using information after t):
   - A_t = years since last LCMS fast loss or GFC loss (capped at 40), and its magnitude (ΔNBR from LandTrendr);
   - years since last *slow loss* or partial disturbance;
   - number of disturbances in 40 years;
   - NBR recovery slope over the 5 years after the disturbance;
   - pre-disturbance forest type (LCMS land cover and the EVT majority in the year before loss).

   The age-class shares at each radius are {0–4, 5–15, 15–25, 25–40, > 40} years, which are exactly the bins of the report's §1.2 table. The model also gets the Shannon diversity of these classes and the edge density between "young" (5–25) and "mature" (> 40) at 250 m. That last feature is Vermont's three-age-class rule turned into a variable.
2. **Composition traits**: deciduous fraction (leaf-on minus leaf-off NDVI, D7), aspen/birch EVT share, conifer share (with a hump-shaped prior), TreeMap basal area, stem count and QMD, Meta canopy-height bin shares (1–5 m and 5–12 m), and canopy cover.
3. **Topography and climate**: elevation, Daymet mean Jan–Mar SWE, and GDD.
4. **Within-forest road and trail density** (OSM tracks) at 250 m. This is a habitat feature, because brood use of forest roads is established. Distance to *paved* roads is **not** a habitat feature; it lives only in the bias model.

The categorical codes enter as small embeddings (EVT is collapsed to about 60 physiognomic groups) or as one-hot shares within radii. The 10,000-row tables are eliminated.

**Forecast.** For a future season t′ > t_last, set A_{t′} = A_{t_last} + (t′ − t_last). Assume no new disturbance and flag the uncertainty. Composition features are held at t_last.

**Privileged lidar (option).** On pixels with 3DEP coverage, an auxiliary head predicts the lidar 1–5 m return fraction from h_θ's penultimate layer, with an MSE loss weighted at 0.1. This shapes the representation toward understory density without needing lidar at inference (learning using privileged information; Vapnik & Vashist 2009).

### 3.5 Model architecture

- **Habitat tower h_θ:** an FT-Transformer or a 4-layer MLP (width 256, SiLU, dropout 0.1) over about 120 tabular features per pixel, which include the multi-radius summaries. That gives an effective receptive field of about 600 m. About 0.5 M parameters. There is deliberately **no ImageNet trunk**: the report shows capacity is not binding, and a small per-pixel model can be applied to every pixel at prediction cost of about 1 μs/pixel.
  - *Variant h_θ^CNN:* a 21×21 (630 m) patch convnet on the raw layers. It is used only if the MLP is beaten in Phase 2 ablation.
- **Effort tower g_φ:** an MLP of width 64 plus an observer embedding (dimension 4, with a strong L2 penalty, observers with fewer than 5 checklists pooled).
- **MIL integration:** for each checklist in each minibatch, draw M = 32 pixels s_{j,m} ~ K_j and estimate Σ_s K_j λ ≈ (1/M) Σ_m λ(s_{j,m}). The estimator is unbiased inside the exp. The bias from Jensen's inequality is small at M = 32, and M can be raised to 128 for final epochs. Pixel features are gathered from a memory-mapped feature cube (§7).
- **Disaggregation:** each region-year mean Λ̄_rt is estimated per step from a stratified random sample of 4,096 pixels of the region (fresh each step), so it is an unbiased stochastic estimate.

**Training.** AdamW (lr 1e-3, wd 1e-4), batch 2,048 checklists, 30–60 epochs, early stopping on held-out-fold checklist deviance. There are 5 spatial folds (§3.7) and a 5-seed ensemble per fold. The epistemic spread of the ensemble is reported in the product.

**Spatio-temporal subsampling.** Following Johnston et al. (2021), sample at most k = 3 checklists per (3 km hex × week × detection status) per epoch, resampled every epoch. This de-weights hotspot hammering without throwing data away.

### 3.6 Inference and end product

1. **Pixel map:** λ̂(s, t) for t ∈ {2026, 2027, 2028} on the 30 m template grid, plus ensemble standard deviation. Prediction uses Z only; g_φ and b are dropped.
2. **Covert polygons:**
   - Segment forest into stand objects by connected components of (same disturbance year ± 1, same LCMS cover class), merged to 2–40 ha. These sizes match Gullion's ≤ 10 ha cuts and the 2.4–16 ha home ranges.
   - Clip to D10 public land and access.
   - Attach F̂(C, t) on the flushes-per-hour scale using κ̂ for an average year, with an 80% interval from the ensemble × κ uncertainty.
   - Add a **peak window**: the years in which the A_t of most of the polygon will sit in 5–20.
   - Add access attributes: drive-to distance, public or easement status, gated-road walk-in distance.
3. **Hunter view:** a GeoPackage/KML layer plus a small HTML/Leaflet viewer with the top-N coverts within a drive radius, filters for access type and "rising" coverts, and the rule-out map (high effort and confidently low λ).

### 3.7 Evaluation protocol (designed not to fool ourselves)

Pre-register before any model is fitted (commit the script and the thresholds; this is CR-0011 A3 practice):

- **Folds.** Five spatial folds of **25 km hexagons**. Phase 0 checks this choice against the residual variogram range of a GBM fit. If the range is longer than 25 km, use the larger size. All checklists, PO records and pixels of the held-out hexes are excluded from training. Flush regions are held out by leave-one-region-out in a separate loop.
- **M1 — checklist deviance and AUC with effort standardised.** On held-out checklists, compute the AUC of λ alone and of ρλ, as both PR-AUC and Brier. Evaluate with importance weights w = p_target(Z) / p_visited(Z), clipped to [0.2, 5], from a domain classifier (visited vs uniform forest pixels). This estimates performance over the *whole forest*, not over birding hotspots.
- **M2 — top-decile enrichment.** E10 = (share of effort-weighted held-out detections falling in the top 10% of held-out forest by λ) / 0.10. Also report the continuous Boyce index on held-out ARU and PO data.
- **M3 — flush-rate concordance.** Spearman correlation and log-ratio RMSE between predicted Λ̄_rt and observed NH regional flush rates, leaving one region out. With year effects removed this is about 5 × 20 points, so report it with bootstrap CIs and treat it as directional.
- **M4 — prospective field test (the decisive one).**
  - ARU drumming occupancy at 40 stations stratified by predicted-λ quintile (8 per quintile) in public forest. Pre-registered success criterion: top-quintile naive occupancy ≥ 2× bottom-quintile, one-sided p < 0.05, Cochran–Armitage trend test.
  - Hunt logs from 30–60 hours per stratum in top-decile vs median coverts. A Poisson power calculation gives z ≈ 2.1 for a 1.5× rate ratio at 1.5 flushes/hr base and 30 h per arm. The design therefore asks for 60 h per arm to absorb overdispersion.
- **M5 — legacy comparability.** Score the current validation set (grouse records vs TG negatives) with λ̂ and report its AUC next to 0.762/0.770. This is *reported, not optimised*, because the 1 − a/2 bound caps it.
- **M6 — temporal forward check.** Train on t ≤ 2022 and test M1/M2 on 2023–2025 checklists, using clock features advanced as in §3.4. This tests the forecast.

**Baselines on identical folds:**

- B0: the current CNN score, used as one feature in a checklist model with the same effort tower. This asks how much of held-out detection the current map already explains.
- B1: an eBird best-practice GBM (encounter-rate model on footprint-averaged features plus effort covariates; Johnston et al. 2021).
- B2: FLUSH without D3.
- B3: FLUSH without clock features (current `tsd` only).

---

## 4. Why it beats the status quo

The report's central diagnosis (§5.4) is that "the data is the ceiling": GBM equals CNN at about 0.77, more capacity only fits noise, and only new information has moved the number. FLUSH answers each named cause with *new information or a corrected likelihood*. It does not answer them with capacity.

| Cause named in the report | Current treatment | FLUSH treatment | Why it should matter |
|---|---|---|---|
| **PU label noise** ("many negatives are unlabelled presences", §5.4; AUC ≤ 1 − a/2, §4.1) | TG background buffered 300 m and assumed negative (AN-full) | Non-detections with effort and a detection model; the false-negative probability exp(−ρλ) is *in* the likelihood | The structural 1 − a/2 cap exists because background points cannot be absences. Effort-weighted non-detections *can* be informative absences, because long, repeated searches with no grouse carry evidence. This is the report's own #1 recommendation (§4, "Most promising next steps"), turned into a concrete model |
| **Effort bias** (road_dist encodes birding behaviour, §5.3) | TG cancellation, which is "not exact, direction surprising" | Conditioning on visits (complete checklists) + explicit ρ tower dropped at prediction + importance-weighted evaluation | Separates "who walked there" from "what lives there"; the map no longer inherits birders' trail choices |
| **Location error** (59–76% hotspot pins; travelling counts span km; the centre-skip assumes a centre label, §2.4) | 64×64 context and attention pooling partly compensate | Explicit footprint kernel by protocol and distance (MIL) | The label is assigned to where the bird could have been, not to a pin |
| **Estimand** (log density ratio of reporting processes, §5.1) | Interpreted with caveats | Relative abundance λ, anchored on the flush-per-hour scale by D3 | It is the quantity the owner wants; calibration means something |
| **Static map vs a 10–20-year clock** (open question 5, §5.6) | `tsd` capped at 30, one vintage at prediction, year matching to kill the vintage leak | Per-record-year features from a 40-year annual history; forecasts | Removes the need for YEAR_MIN = 2020 (more years usable) and gives hunters next season's map, not 2022's |
| **Data volume** (4,809 positives, 2020–2024) | — | All complete checklists 2010–2025 | Several times more detections plus about 10–50× more informative non-detections (Phase 0 confirms the counts) |
| **No external truth** (§5.6) | None | NH flush indices, ARU drumming, hunt logs | Turns "trust" into a measurable, pre-registered test |

**Why this can break the ceiling rather than just move it.** The 0.77 is AUC of grouse records vs TG records. FLUSH is scored on a different and better-posed question (M1/M2/M4), and there the 1 − a/2 bound does not apply, because absences are partially observed. On the legacy question (M5), I expect only a modest gain. If FLUSH's λ beat the CNN by a lot *on TG contrast*, that would itself be suspicious, because λ is not trained to mimic the TG reporting contrast.

**Why the ceiling becomes irrelevant to hunting.** A hunter's value is roughly Σ over chosen coverts of F(C, t). That depends on (i) the top of the ranking, measured by M2/M4, not on global AUC; (ii) the correct between-region scale (D3), which presence-vs-TG cannot give; (iii) the current-season state of a fast-changing habitat (the clock); and (iv) access (product layer). A model with an AUC of 0.77 on the TG task can still be a poor covert finder if its top decile is birding-trail forest in a low-density region, and that is exactly the failure FLUSH is built to avoid.

---

## 5. Expected gains, with honest uncertainty

These are estimates. Each comes with the measurement that would confirm or refute it.

| Metric | Status quo (est.) | FLUSH expected | Confidence | Basis |
|---|---|---|---|---|
| M1 held-out checklist AUC of λ (effort-standardised) | B0: unknown, guess 0.70–0.78 | B0 + 0.03 to + 0.08 | Medium-low | Johnston et al. (2021) report that complete checklists and effort covariates gave the largest gains among data treatments (magnitude in our region **unverified**); MIL and the clock add on top |
| M2 top-decile enrichment E10 | Unknown (B0) | 1.2–1.5× B0's E10 | Low-medium | Effort removal should most affect the top of the ranking, where trail and hotspot forest currently concentrates |
| M3 regional flush Spearman | B0 likely ≤ 0.3 (presence data under-rank the low-effort north) | ≥ 0.6 | Low (n is small) | Disaggregation directly constrains this; partly circular in-sample, so leave-one-region-out is mandatory |
| M4 ARU top/bottom-quintile occupancy ratio | Not measured | ≥ 2× | Medium | Lapp et al. 2023 show high detectability with 28-day ARUs; the contrast between young-forest mosaics and closed mature forest is large in the literature (§1.2 of the report) |
| M5 legacy TG-contrast AUC | 0.762 (CNN), 0.770 (GBM) | 0.76–0.80 | Medium | Not optimised; any gain comes from more data and the clock |
| M6 forward-in-time M1 drop | — | ≤ 0.02 AUC drop vs in-period | Low | Tests the clock; a large drop means the age dynamics are wrong |

**Specific ways we could fool ourselves, with guards:**

1. *Hotspot leakage.* The same hotspot appears in train and validation. Guard: 25 km hex folds, and hotspot IDs assigned to one fold.
2. *Effort leakage into λ.* λ learns trail density as a proxy for observer presence. Guard: M1 is reported with ρ dropped, and an integrated-gradients audit checks λ's dependence on paved-road distance and population density, which should be ≈ 0 because they are not inputs. A "placebo" test fits λ on *other* forest birds' detections with the same pipeline: if grouse λ and placebo λ correlate above 0.8, effort is driving both.
3. *Circularity in M3.* Always leave one region out. Report D3-trained and D3-free models separately.
4. *Garden of forking paths.* Pre-register M1–M4, folds and the success thresholds in a committed script before Phase 2 (repo policy CR-0011 A3).
5. *eBird S&T contamination.* If S&T abundance is used as an offset (option), it was fitted on all eBird data, including our held-out blocks. It is therefore allowed only in models evaluated by M4 and M5, never by M1 or M2.

---

## 6. Risks, failure modes and the cheapest falsification

**Pre-mortem: "It is October 2027 and FLUSH failed. Why?"**

| Failure mode | Likelihood | Detection | Mitigation |
|---|---|---|---|
| Grouse checklist detections are dominated by spring drumming and roadside incidentals, so ρ and λ are confounded | Medium | g_φ's day-of-year effect absorbs most variance; λ is flat | Fit separate ρ by season; restrict λ-informative training to Sep–Nov and Apr–May; rely more on D4 |
| Too few repeat visits to identify ρ vs λ | Low-medium | Posterior/ensemble spread on the ρ slopes is wide | Ranking needs only λ's *shape*, not the ρ/λ split; ρ covariates are checklist-level and vary within locations |
| Footprint kernel misspecified (travelling direction unknown) | High that it is imperfect, low that it matters | M1 sensitivity to r_j scaling (0.5×, 1×, 2×) | Learn σ_det and the hotspot σ_loc; ablate |
| LCMS/GFC miss partial harvests (shelterwood is common in Maine, §1.8.7) | High | Clock features weak in Maine industrial forest | Slow-loss and magnitude features; LandTrendr low-magnitude segments; privileged-lidar head; validate on the Maine Forest Service silvicultural reports (town-level harvest acres) as an aggregate check |
| NH flush data are too coarse to help | Medium | B2 ≈ FLUSH on M1/M2 | Acceptable: D3 is a steering term. Its main value is M3 and absolute scale |
| EBD access delayed | Low | — | GBIF eBird pseudo-checklists (§7, Day 1) as a stop-gap |
| Engineering scope creep | Medium | Phases slip | Phase 1 is a GBM with no new modelling code; each phase has a go/no-go |
| eBird ToS restrict redistributing derived products | Low-medium | — | The product is for the owner's personal use; check eBird data terms before sharing maps |

**Cheapest falsification experiment (one day, on EC2).** The core premise is that *non-detections with effort carry habitat information that the current TG-contrast map does not already capture*. If that is false, FLUSH collapses into a re-skinned version of the current model.

- **Test.** On held-out spatial folds of complete checklists, compare:
  - (a) logit P(y_j) = g(effort) + β·CNN_score(x_j), against
  - (b) g(effort) + LightGBM on footprint-averaged features (existing 15 layers + simple LCMS age-class shares).

  Use the same folds and effort covariates for both.
- **Falsified if** (b) − (a) < 0.01 in held-out AUC *and* top-decile enrichment does not differ (bootstrap over folds). The current map would then already contain everything the checklists add, and the right next move is field validation only, not a new model.
- **Supported if** (b) beats (a) by ≥ 0.02, or if the CNN score's coefficient collapses once effort enters. The latter would mean the current map is partly an effort map.

---

## 7. Implementation plan

All work happens on a branch, under the repository's change-control rules. **Each phase below is one CR** (CR-0011 A5: one independently landable change per CR). Acceptance scripts are committed before approval (A3).

| Phase | Content | Effort | Go/no-go |
|---|---|---|---|
| **0. Data and day-1 falsification** (CR-a) | Request EBD (both files, ME/NH/VT). Meanwhile build GBIF pseudo-checklists: group GBIF eBird records for *all* species in the three states by (observer/recordedBy, eventDate, rounded lat/lon), keeping groups with ≥ 10 species as a "likely complete" proxy (whether GBIF eBird rows carry a checklist/event ID is **unverified**; fall back to grouping). Run the §6 falsification with existing features. Compute the residual variogram for fold size. | 1–3 days | §6 criterion |
| **1. Succession clock layers** (CR-b) | EE export of LCMS v2024-10, GFC v1.12 and LandTrendr NBR on the template grid, with explicit `crsTransform` corner alignment and a registration check against a LANDFIRE edge (reuse `diagnose_layer_registration.py` style tests, per BUG-0094/0095 lessons). Derive A_t, magnitude, slow-loss and recovery features per year, 2010–2025. | 4–6 days | Registration checks pass; A_t matches `tsd` where both exist |
| **2. Encounter-rate GBM (B1) + feature cube** (CR-c) | Feature cube: per year, per pixel, about 120 float16 features at 3 radii, memory-mapped by tile (~150 M forest pixels × 120 × 2 B ≈ 36 GB/year; store 3–4 key years plus the clock deltas). LightGBM on footprint-averaged features plus effort. Pre-registered M1/M2/M5. | 1 week | B1 beats B0 on M1 or M2 |
| **3. FLUSH neural model** (CR-d) | PyTorch: h_θ, g_φ, MIL sampler, PO term, disaggregation term; 5 folds × 5 seeds; ablations B2/B3; M3, M6. | 2 weeks | FLUSH ≥ B1 on M1 and M2, and M3 > B0 |
| **4. Product** (CR-e) | Stand segmentation, PAD-US/OSM access, F̂ with intervals, peak windows, GeoPackage + Leaflet viewer. | 1 week | Owner usability check |
| **5. Prospective test** (field, spring + October 2027) | 40 ARUs stratified by quintile; hunt logs; pre-registered M4 analysis. | Field season | M4 criteria |
| **6. Options** | Privileged lidar head; leaf-off spectral understory; S&T offset (M4/M5-only); stacking with B1 | as needed | Each must beat Phase 3 on M1/M2 |

**First experiment the owner can run on EC2 within a day:**

```text
1. Submit the EBD request (ME, NH, VT; Ruffed Grouse + Sampling Event Data).
2. GBIF download: all Aves occurrences, datasetKey = eBird EOD, ME/NH/VT, 2016–2025
   (pygbif occurrence download; a few GB).
3. Build pseudo-checklists (group by recordedBy, eventDate, round(lat,4), round(lon,4));
   keep groups with ≥10 species; y = grouse present.
4. For each pseudo-checklist, sample 32 points in a 300 m Gaussian (no effort info yet).
   Average the existing 15 layers plus the current CNN's predict.py score at those points.
5. 5-fold 25 km-hex CV:
   (a) LightGBM on [n_species (effort proxy), day-of-year, CNN_score]
   (b) LightGBM on [n_species, day-of-year, footprint features]
   Report held-out AUC, PR-AUC and top-decile enrichment.
```

Number of species is a known proxy for checklist effort and completeness. If (b) ≫ (a), the TG-contrast map leaves recoverable habitat information on the table. If (a) ≈ (b), the CNN map already holds it, and the remaining lever is external validation (Phase 5) plus the product layer.

---

## 8. References

URLs were checked by web search during this round unless marked **unverified**.

- eBird Basic Dataset download and access request: https://ebird.org/data/download (page not fetched; **unverified** URL path)
- `auk` R package (EBD extraction, zero-filling): https://docs.ropensci.org/auk/reference/auk_zerofill.html
- Johnston, A., Hochachka, W.M., Strimas-Mackey, M.E., et al. (2021). Analytical guidelines to increase the value of community science data: an example using eBird data to estimate species distributions. *Diversity and Distributions* 27:1265–1277. https://doi.org/10.1111/ddi.13271
- eBird best practices book/code: https://github.com/cornelllabofornithology/ebird-best-practices
- Johnston, A. et al. (2018). Estimates of observer expertise improve species distributions from citizen science data. *Methods Ecol. Evol.* 9:88–97. https://doi.org/10.1111/2041-210X.12838 (**unverified** DOI)
- eBird Status & Trends data products and `ebirdst`: https://science.ebird.org/en/status-and-trends/download-data ; https://ebird.r-universe.dev/ebirdst/doc/status.html
- Royle, J.A. & Nichols, J.D. (2003). Estimating abundance from repeated presence–absence data or point counts. *Ecology* 84(3):777–790. https://pubs.usgs.gov/publication/5224229
- Lucas, T.C.D., Nandi, A.K., Chestnutt, E.G., et al. (2023). disaggregation: an R package for Bayesian spatial disaggregation modelling. *J. Stat. Softw.* 106(11). https://jstatsoft.org/index.php/jss/article/view/v106i11 ; preprint https://arxiv.org/abs/2001.04847
- Lapp, S., Larkin, J.L., Parker, H.A., et al. (2023). Automated recognition of ruffed grouse drumming in field recordings. *Wildlife Society Bulletin* 47(1). https://doi.org/10.1002/wsb.1395 ; OpenSoundscape tutorial: https://opensoundscape.readthedocs.io/en/latest/tutorials/ruffed_grouse_detector.html ; data: https://datadryad.org/dataset/doi:10.5061/dryad.hdr7sqvmc
- Koleck et al. (2026), PA acoustic + LiDAR grouse occurrence data: https://doi.org/10.5061/dryad.hmgqnk9xh (cited in the report)
- NH Fish & Game, Ruffed Grouse Wing and Tail Survey (flush rate per hour, e.g. 2.27 in 2020 vs 1.31 in 2019): https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey ; Small Game Summary (regional rates): https://www.wildlife.nh.gov/sites/g/files/ehbemt746/files/inline-documents/sonh/small-game-summary.pdf (403 to automated fetch; content seen only via search summary) ; NH Ruffed Grouse Assessment 2015: https://www.wildlife.nh.gov/sites/g/files/ehbemt746/files/inline-documents/sonh/nh-ruffed-grouse-assessment-2015.pdf
- Maine and Vermont hunter flush-rate surveys: **none found online**. Request from ME IF&W and VT F&W. Comparable programmes elsewhere include NY DEC grouse & woodcock hunting log (https://dec.ny.gov/nature/animals-fish-plants/biodiversity-species-conservation/citizen-science/grouse-and-woodcock-hunting-log) and CT DEEP hunter log (https://portal.ct.gov/deep/hunting/ruffed-grouse-hunter-log).
- LCMS on Earth Engine: https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2022-8 (superseded by `USFS/GTAC/LCMS/v2024-10` per that page)
- Hansen GFC v1.12: https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12
- Kennedy, R.E. et al. (2018). Implementation of the LandTrendr algorithm on Google Earth Engine. *Remote Sensing* 10(5):691. https://doi.org/10.3390/rs10050691 (**unverified** in this round)
- HLS on Earth Engine: `NASA/HLS/HLSL30/v002` (**unverified** asset ID)
- Maine Forest Service silvicultural activities reports (harvest acres by method): https://lldc.mainelegislature.org/Open/Rpts/sd566_m2s5_2019.pdf
- USGS 3DEP summary for Vermont: https://pubs.usgs.gov/publication/fs20153002 ; VT lidar plan: https://vcgi.vermont.gov/sites/vcgiupdate/files/doc_library/2023%20Vermont%20Lidar%20Plan%20v1.3.pdf ; NH: https://pubs.usgs.gov/publication/fs20143110
- Warton, D.I. & Shepherd, L.C. (2010). Poisson point process models solve the "pseudo-absence problem". *Ann. Appl. Stat.* 4:1383–1402. https://doi.org/10.1214/10-AOAS331 (cited in the report)
- Joseph, M.B. (2020). Neural hierarchical models of ecological populations. *Ecology Letters* 23:734–747. https://doi.org/10.1111/ele.13462 (cited in the report)
- Vapnik, V. & Vashist, A. (2009). A new learning paradigm: learning using privileged information. *Neural Networks* 22:544–557. https://doi.org/10.1016/j.neunet.2009.06.042 (**unverified**)
- Ilse, M., Tomczak, J., Welling, M. (2018). Attention-based deep multiple instance learning. ICML. https://arxiv.org/abs/1802.04712 (**unverified** in this round; MIL background)
- Wadoux, A.M.J.-C. et al. (2021). Spatial cross-validation is not the right way to evaluate map accuracy. *Ecol. Model.* 457:109692. https://doi.org/10.1016/j.ecolmodel.2021.109692 (cited in the report)
- Gorishniy, Y. et al. (2021). Revisiting deep learning models for tabular data (FT-Transformer). NeurIPS. https://arxiv.org/abs/2106.11959 (**unverified** in this round)
- PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview (**unverified** URL)
- Repository report: `/home/user/grouse_refactor_ec2/docs/grouse_model_report.md` (§§1.2, 1.5, 1.8, 2.3–2.4, 4.1–4.2, 4.8, 5.3–5.6).
