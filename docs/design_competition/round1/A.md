# Design A: the Covert Yield Model (CYM)

*Designer A, round 1. Primary technique: first-principles decomposition plus Five Whys.*

## 1. Title and pitch

**Covert Yield Model: predict flushes per hour of walking, per covert, per season, from the physics of an encounter and the clock of forest succession.**

A hunter does not need "places that resemble eBird grouse records". A hunter needs to know where an hour of walking produces the most flushes this October, among coverts they can reach. That number factors exactly:

flushes/hour = grouse density in the covert × width of the strip the hunter sweeps × walking speed.

Only density is ecological. Density in turn is driven by a short list of measurable causes. The main one is *years since a stand was cut*, and it changes every year. CYM rebuilds the project around that factorisation:

- **The model** is a low-parameter, shape-constrained, kernel-integrated density model (about 30–40 parameters, each with an ecological meaning and a literature prior). It replaces the 12M-parameter CNN.
- **The habitat data** is a stand-age cube rebuilt every year from Landsat (LCMS, Hansen, the Maine harvest maps) plus leaf-off lidar understory. So the map knows about cuts made in 2019–2025 that are now entering the prime window.
- **The labels** are fitted jointly in an integrated likelihood:
  - eBird complete checklists, which are *detection/non-detection with effort* (a Royle–Nichols abundance–detection model);
  - state hunter flush-rate surveys, which are *aggregate* labels and are fitted by disaggregation regression;
  - GPS hunt logs with flush waypoints, the *gold-standard label* because they measure the estimand itself, line-transect style.
- **The end product** is a ranked list of covert polygons, with expected flushes/hour, credible intervals, a three-year forecast and walking access from parking. It is also a loop planner.
- **The evaluation** is a pre-registered, blinded, paired field test of flush rates in the field. It replaces presence-versus-target-group AUC, which the report itself shows measures birding geography.

---

## 2. Brainstorming record

### 2.1 First-principles decomposition (what a hunter actually consumes)

```
Hunter value V(covert c, season Y)
├── E[flushes / hour walked in c]                       ← the estimand
│   ├── D(c,Y): fall grouse density (birds/ha)          ← ecology
│   │   ├── carrying capacity K(c,Y) of the home-range neighbourhood
│   │   │   ├── cover: stem density 1.5–6 m             ← stand age since heavy cut × regen type × site
│   │   │   ├── food: mature aspen/birch buds within ~500 m, soft mast
│   │   │   ├── interspersion: young + mature + some conifer within 3–100 ha
│   │   │   └── negatives: closed conifer, development, open/agric land
│   │   ├── regional/annual level τ_r(Y): spring breeders × nest/brood success (June weather),
│   │   │   WNV, snow-roost winters, cycle (weak in NE)
│   │   └── local depletion: hunting pressure near parking, late season
│   └── encounter: strip half-width W (cover-dependent) × walking speed v (≈1.5–2.5 km/h)
├── reachability: drive time, legal access (public / unposted / easement / gated roads), walking cost
└── uncertainty: how sure are we (the hunter will tolerate exploring a few unknown coverts)
```

**Physical sanity check (it constrains the absolute scale):**
- Gullion's prime 10–25-year aspen holds about 1 pair per 2.8 ha in spring, about 0.7 birds/ha (report §1.2).
- With about 9.8 eggs, about 43% nest success and partial chick survival, the fall population is roughly 2–2.5× the spring population. That gives about 1.5 birds/ha in prime cover and perhaps 0.1–0.3 birds/ha averaged over hunted forest.
- A hunter sweeps about 2 km/h × 2 × 15 m ≈ 6 ha/h.
- Predicted rate: about 0.6–1.8 flushes/h for average hunted forest, and up to about 9/h in prime cover.
- NH reported 1.31 (2019) and 2.27 (2020) flushes/h statewide. The order of magnitude matches.

So the estimand is physically pinned, and an aggregate flush rate tells us about the *scale* of D directly.

### 2.2 Five Whys

**Chain 1: why is precision capped at AUC ≈ 0.77?**
1. *Why?* The leak-free CNN and a GBM on the same inputs both stall at 0.76–0.77, so capacity is not the limit (report §5.4).
2. *Why does the data stall?* The label is "grouse record vs other-species record". That is a contrast of two *recording processes* (§5.1) with km-scale location error, unlabelled presences among the negatives, and effort that does not cancel (grouse records sit 2–5× farther from roads, §5.3).
3. *Why do new habitat layers barely move it?* LCMS/Hansen harvest history added **+0.001** (CR-0032). The literature calls stand age the strongest driver (§1.8). There are two readings: the variable doesn't matter, or the label cannot see it. The label is pinned to hotspots and trails, with km error, and contrasted against other forest birds whose birders walk the same trails. Variation in stand age at the 5–20 ha scale is invisible to it. (Testing which reading is right is the cheapest falsification experiment, §6.)
4. *Why can't a better network see through the label?* There is no information to recover. Without effort and non-detections, the intercept and the effort–habitat split are not identifiable (§4.2, Ward 2009).
5. *Why do we need that information?* The hunter's decision is a **within-region ranking of coverts at 5–20 ha scale, for this year**. It is not a statewide ranking of 2020–2024 recording sites.

→ **Root constraint 1:** the label must measure grouse *conditional on effort*, at or below covert scale, ideally the estimand itself (flushes per unit walking). The present label can never deliver that precision.

**Chain 2: why might the current map be *inaccurate* for hunters even at the same AUC?**
1. *Why?* It ranks landscapes that look like places grouse got *reported*.
2. *Why is that different?* Reporting follows trail networks, hotspots and birder demography. `road_dist` encodes birding behaviour as well as ecology (§5.3).
3. *Why does time matter?* Prime cover lasts about 5–20 years after a cut. LANDFIRE vintages start in 2022, prediction uses the latest vintage, and `tsd` comes from LANDFIRE disturbance and is capped. Every year a few % of the landscape enters or leaves the prime window. A static map decays at the rate of succession.
4. *Why is stand age not better measured?* Annual Landsat disturbance products exist back to 1985 (LCMS; Hansen 2001+; Maine HF437 1986–2019 with FIA-validated harvest detection, F1 0.72). They have not been made the *core* of the model.
5. *Why not?* The modelling frame was "image classification of windows", not "process model of a succession-driven population".

→ **Root constraint 2:** grouse density is dominated by a known, measurable, *time-varying* mechanism. The model must carry that mechanism explicitly and roll it forward each year. It cannot learn it implicitly from a few thousand noisy labels.

**Chain 3: why does the evaluation not tell us whether hunters would do better?**
Validation AUC measures reproduction of held-out draws of the same recording process (§5.6). Nothing checks outputs against grouse on the ground. → **Root constraint 3:** the scoreboard must be flushes per hour in the field, or something with a demonstrated link to it.

### 2.3 Raw idea list (unfiltered)

1. Make flushes/hour the estimand: D × 2W × v.
2. Use state hunter flush-rate surveys (NH wing-and-tail/small-game survey, ME/VT equivalents, NY grouse log) as aggregate labels via disaggregation regression.
3. Use eBird complete checklists (EBD + sampling-event file) in an effort-explicit Royle–Nichols abundance–detection likelihood.
4. Use GPS hunt logs with flush waypoints as line-transect labels: the estimand itself.
5. Deploy AudioMoth ARUs stratified by model score and detect drumming automatically (Lapp et al. 2023) for independent occupancy validation.
6. Build an annual stand-age cube by fusing LCMS Tree Removal, Hansen loss year, HF437 (ME) and LANDFIRE disturbance, and forecast succession forward 1–3 years.
7. Add leaf-off airborne-lidar understory density (returns 1–6 m), since VT, NH and ME all have near-statewide coverage.
8. Map aspen with Sentinel-2 phenology (early leaf-out, autumn yellow).
9. Use a mechanistic, shape-constrained, low-parameter model with literature priors.
10. Rank covert polygons, not pixels; plan walking loops from parking.
11. Take the year/region effect from spring drumming and summer brood reports to make a "fall forecast".
12. Choose coverts to explore by Thompson sampling, which is active learning that is also good hunting.
13. Reuse the current CNN as an *effort/bias* model (it learned birding geography) in a presence-only thinning term.
14. Add regional modifiers for snow-roost days, elevation and WNV risk.
15. Model local depletion from hunting pressure near parking and later in the season.
16. Train a CNN on hunt-log labels.
17. Add a residual term on AlphaEarth satellite embeddings (`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`).
18. Exploit seasonal detectability (drumming April–May) in the checklist model.
19. Fit a spatial random effect at 10–25 km to absorb regional unmodelled level.
20. Crowdsource hunt logs from Ruffed Grouse Society chapters, with privacy-preserving pooling.

### 2.4 Convergence

Each idea was scored 0–3 on four criteria: (I) new *information* about grouse rather than birders, (F) feasibility on the owner's stack within weeks, (H) hunter relevance (covert scale, this year), and (X) falsifiability.

| Idea | I | F | H | X | Decision |
|---|---|---|---|---|---|
| 1 estimand | 3 | 3 | 3 | 3 | **core** |
| 3 checklists RN | 3 | 2 | 2 | 3 | **core** (main training signal) |
| 6 stand-age cube + forecast | 2 | 3 | 3 | 3 | **core** |
| 9 low-param mechanistic | 2 | 3 | 3 | 3 | **core** |
| 10 coverts + loops | 0 | 2 | 3 | 1 | **core product** |
| 4 hunt logs | 3 | 2 | 3 | 3 | **core** (validation, then training) |
| 2 aggregate hunter data | 2 | 1 | 2 | 2 | include; survives if unavailable |
| 7 lidar understory | 2 | 2 | 3 | 2 | include (phase 3) |
| 11 annual level | 1 | 2 | 2 | 2 | include |
| 14 snow/elev | 1 | 3 | 1 | 2 | include as covariates |
| 15 depletion | 1 | 2 | 2 | 2 | include, fitted on hunt logs only |
| 19 spatial RE | 1 | 2 | 2 | 2 | include (low rank) |
| 12 Thompson | 1 | 3 | 2 | 1 | include in product |
| 5 ARUs | 3 | 1 | 2 | 3 | optional validation (costs money) |
| 17 embeddings residual | 1 | 3 | 1 | 2 | optional residual, gated by held-out likelihood |
| 13 CNN as bias model | 1 | 3 | 0 | 1 | optional comparator |
| 8 S2 aspen | 1 | 1 | 2 | 1 | deferred |
| 16 CNN on hunt logs | 0 | 1 | 2 | 1 | **rejected**: far too few labels |
| 20 crowdsourcing | 2 | 1 | 2 | 1 | later; privacy risk |

**Convergence logic.** The root constraints say that information, not capacity, is short. So the design (a) adds the two label streams that carry effort and absence, (b) spends the scarce label information on a few interpretable parameters and puts the rest of the knowledge into structure and priors, and (c) moves the scoreboard to the hunter's outcome.

---

## 3. The design

### 3.1 Estimand

For a 30 m cell $s$ and hunting season $Y$ (October–November):

$$F(s,Y)=2\,W(s)\,v\;D(s,Y)\qquad[\text{flushes per hour}]$$

For a covert polygon $c$, $F(c,Y)=2Wv\,\bar D_c$. The ecological target is $D$ (fall birds/ha). $W$ and $v$ are observation constants, with priors $v\sim\mathcal N(2.0,0.4^2)$ km/h and $W\sim$ log-normal centred on 15 m. $W$ may depend on cover density, and it is learnable only from hunt logs.

### 3.2 Habitat-state cube (covariates), rebuilt each year

Everything is computed on the existing per-region template grid. Downloads must use explicit `crsTransform` on the template lattice, to avoid repeating BUG-0094/0095; `grid_mismatch` plus a content-registration check like `check_layer_registration.py` are acceptance gates.

| Layer | Definition | Source |
|---|---|---|
| `age(s,Y)` | $Y-$ year of last heavy disturbance (≥ ~30% BA removed) up to and including $Y$. NONE → "mature" bin | Fusion: LCMS `Change` = Tree Removal (class 9) and other vegetation loss (GEE `USFS/GTAC/LCMS/v2024-10` or the 2025-11 asset already used in `diagnose_disturbance_features.py`); Hansen `lossyear` (`UMD/hansen/global_forest_change_2024_v1_12`); Maine HF437 annual harvest maps 1986–2019 (doi:10.6073/pasta/20a838c4bd6922685b3d00661d45c414); LANDFIRE annual disturbance. Fusion rule: earliest-confirmed event within ±1 yr across sources; product agreement count kept as a confidence band |
| `regen(s)` | Pre-disturbance and current forest guild: {aspen–birch, northern hardwood, oak–pine, mixedwood, spruce–fir, pine–hemlock} | TreeMap 2022 FORTYPCD (already downloaded via `download_treemap.py`) cross-walked to guilds; LANDFIRE EVT as fallback |
| `under(s)` | Understory stem-density proxy: share of leaf-off returns 1–6 m above ground among returns < 6 m | 3DEP/state lidar (VT QL1 2023 leaf-off statewide; NH GRANIT statewide; ME 3DEP near-statewide), via PDAL `filters.hag_nn` + 30 m binning. Fallback: Meta CHM 1–5 m share (`mch_f15`, CR-0032) |
| `conif(s)`, `hwmature(s)` | Conifer share; mature (age ≥ 30 or NONE) aspen/birch/hardwood share | TreeMap + age |
| `dev(s)`, `open(s)`, `water(s)` | NLCD impervious %, ag/open, water | Annual NLCD (already in stack) |
| `snow(s)` | Mean winter days with SWE implying > 15–20 cm soft snow | Daymet V4 (`NASA/ORNL/DAYMET_V4`, `swe`) |
| `elev(s)` | Elevation | 3DEP DEM |
| access layers (product only) | Drivable road graph, gates, trails; protected/public status | TIGER 2023 (already used), OSM, PAD-US (https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview) |

The **succession forecast** for $Y+k$ is trivial and deterministic: `age += k`, and no new cuts are assumed. It is optionally adjusted by an expected annual cut rate. This lets the product say "this covert will peak in 2028".

### 3.3 Density model (the "habitat lens", rebuilt from the mechanism)

**Cell-level cover quality.** Each term is shape-constrained with an informative prior:

$$q(s,Y)=\underbrace{a\big(\text{age}(s,Y)\big)}_{\text{unimodal}}\cdot\underbrace{m\big(\text{regen}(s)\big)}_{\text{guild multiplier}}\cdot\underbrace{u\big(\text{under}(s)\big)}_{\text{monotone, saturating}}$$

- $a(t)=\exp\!\big(-\tfrac{(\log(t+1)-\log(t_p+1))^2}{2\sigma_a^2}\big)$, with peak prior $t_p\sim\mathcal N(10,4^2)$ years and $\sigma_a$ chosen so that the curve falls to about 0.3 by 35 years. The "NONE/mature" level is a separate free value $a_\infty\in(0,1)$, because a thinned mature stand with dense understory is handled through $u$.
- $m$: one free log-multiplier per guild, with an ordered prior aspen–birch ≥ northern hardwood ≥ mixedwood ≥ oak–pine ≥ pine–hemlock ≈ spruce–fir (§1.1). It is soft, implemented as a penalty on violations.
- $u(x)=1-\exp(-x/x_0)$, or an I-spline monotone fit.

**Home-range integration.** Here $K_h$ is an isotropic Gaussian kernel with learnable bandwidth $h$ (initialised at 150, 300 and 600 m, covering 3–100 ha home ranges) and $\ast$ is convolution:

$$\log D(s,Y)=\beta_0+\tau_{r(s)}(Y)+\beta_1\log\big(\epsilon+K_{h_1}\!\ast q\big)+\beta_2\,g_2\big(K_{h_2}\!\ast \text{hwmature}\big)+\beta_3\,g_3\big(K_{h_1}\!\ast\text{conif}\big)$$
$$\qquad+\beta_4\,K_{h_3}\!\ast\text{dev}+\beta_5\,K_{h_1}\!\ast\text{open}+\beta_6\,\text{snow}+\beta_7\,\text{elev}+\beta_8\,\text{IJI}_{h_2}(s,Y)+\rho(s)$$

- $g_3$ is a unimodal "some conifer is good" basis (§1.1, §1.4). $g_2$ is concave increasing.
- $\text{IJI}_{h_2}$ is an interspersion index: the Shannon entropy of the age classes {0–10, 10–25, >25} in the kernel (VT's three-age-class guidance).
- $\rho(s)$ is a low-rank spatial random effect (a 20–25 km basis, e.g. 60 thin-plate or SPDE basis functions) with a strong shrinkage prior.
- $\tau_r(Y)$ is a region × year effect for about 6 biophysical regions × years. It is informed by aggregate hunter data and drumming indices.
- **Optional residual** $\delta(s)=\gamma^\top z(s)$ on AlphaEarth embeddings or the CNN logit, with a ridge prior. It is kept only if it improves held-out checklist log-likelihood (§5).

Total free parameters: about 30 + 60 (basis) + about 6×|Y| level effects. Everything is a differentiable convolution, so it is implemented in PyTorch (`torch.nn.functional.conv2d` with separable Gaussians, `softplus` reparameterisations). Full posteriors use NumPyro NUTS, or a Laplace approximation when NUTS is too slow.

### 3.4 Observation models (integrated likelihood)

All components share $D(s,Y)$.

**(O1) eBird complete checklists. Main training signal.**
- *Data.* The eBird Basic Dataset plus the Sampling Event Data (https://ebird.org/data/download) for ME, NH, VT and buffers into NY and QC, 2016–2025.
- *Filters* (Johnston et al. 2021): complete checklists only; stationary or traveling protocol; duration ≤ 5 h; distance ≤ 5 km; ≤ 10 observers; one checklist per group event.
- *Detection.* $y_i=1$ if Ruffed Grouse is reported (any count, including "X").
- *Sampled area $B_i$.* A disk at the start point with radius $r_i=150\text{ m}+\tfrac12\text{dist}_i$, so location error is represented explicitly rather than attached to one pixel. This also fixes report §2.4.1.
- *Likelihood.* Royle–Nichols (2003), the abundance-induced heterogeneity model:
  $$N_i\sim\text{Poisson}\Big(\Lambda_i\Big),\ \ \Lambda_i=\sum_{s\in B_i}D(s,Y_i)\,A_{\text{cell}}\cdot\kappa,\qquad P(y_i=1)=1-\exp\!\big(-\Lambda_i\,r_i^{\text{det}}\big)$$
  $$\log r_i^{\text{det}}=\alpha_0+\alpha_1\log\text{dur}_i+\alpha_2\log(1+\text{dist}_i)+\alpha_3\log\text{obs}_i+f_{\text{doy}}(\text{doy}_i)+f_{\text{tod}}(\text{time}_i)+\alpha_4\,\text{skill}_{o(i)}$$
  - $f_{\text{doy}}$ is a cyclic spline. It captures the drumming peak in April–May, when detection is mostly auditory.
  - $\text{skill}$ is an observer expertise score, either the eBird S&T-style checklist calibration index or an observer random effect with ≥ 20 checklists.
  - $\kappa$ (fall to spring density) is fixed to 1 here because season enters detection. The *product* of density scale and detection is what O1 identifies. The absolute scale comes from O2/O3 and the physics prior.
- *Why this breaks the ceiling.* Non-detections conditional on effort are real information about *low* density. The model is estimated at the locations birders visit, but conditional on the visit there is no effort bias in $y_i$. Preferential site selection affects only *coverage*, which the shape-constrained structure and uncertainty maps handle.

**(O2) Aggregate hunter flush rates. Disaggregation regression.**
- *Data.* For unit $g$ (state, region, WMU or county, whatever the agencies release) and year $Y$: total flushes $\Phi_{gY}$ and hours $H_{gY}$.
- *Sources.* The NH Fish & Game small-game hunter survey and wing-and-tail survey, which report statewide flushes/h; the Maine IF&W and VT FWD equivalents (**unverified** whether these exist at sub-state resolution, so request them); and the NY DEC grouse log as an out-of-area comparison.
- *Model.* Hunter effort density inside $g$ is unknown. It is modelled as $h_g(s)\propto \text{acc}(s)\cdot(K\ast q)(s)^{\eta}$, with $\eta\sim\mathcal N(1,0.5^2)$, because hunters target cover:
  $$\Phi_{gY}\sim\text{NegBin}\Big(H_{gY}\cdot 2Wv\textstyle\sum_s h_g(s)D(s,Y),\ \phi\Big)$$
- *What it identifies.* Mainly $\tau_r(Y)$ and the absolute scale $\beta_0$ (through the $W,v$ priors). It says little about within-region ranking, and the design does not pretend otherwise. If the data cannot be obtained, CYM still works. The level then comes from the priors and the drumming index only.

**(O3) GPS hunt logs. The estimand itself.**
- *Protocol.*
  - Phone GPS track at 1 Hz (any app that exports GPX: Gaia, onX, OsmAnd).
  - A waypoint per flush, seen or heard, with a count.
  - Dog yes/no, weather, start and end time.
  - The owner and a few partners initially.
- *Discretise.* Track $j$ is cut into 30 m cell crossings, with lengths $\ell_{js}$.
- *Likelihood* (a line-transect Poisson process):
  $$\text{flushes}_j\sim\text{NegBin}\Big(\textstyle\sum_s 2W(s)\,\ell_{js}\,D(s,Y_j)\,e^{\xi\,\text{press}(s,t_j)},\ \phi_3\Big),\qquad W(s)=W_0\,e^{\omega\,u(\text{under}(s))}$$
  Here $\text{press}$ is a depletion covariate: distance to the nearest parking point × week of season. Using flush *locations* (a point process along the line) is a refinement. The count form is enough to start.
- *Role.* In season 1, O3 is **held out entirely** as the prospective test set (§5.3). From season 2, it joins training with the highest weight per observation.

**(O4) Drumming routes.** State roadside drumming counts per stop, *if* agencies release stop-level data:
$$c_{k}\sim\text{Poisson}\big(p_d\sum_{s\in 400\text{ m of stop }k}D(s,Y)\big)$$
These are used for validation first. NY DEC reports that drumming rates do not consistently predict flush rates at WMU scale, so this is weak evidence and is down-weighted.

**(O5) Presence-only eBird/GBIF records. Optional, low weight.** A thinned point process, $\lambda_{\text{obs}}=D\cdot b(u)$, with bias covariates $u$: road distance, hotspot density, population, and optionally the current CNN logit as a "birding geography" covariate. $b$ is dropped at prediction (§4.8 of the report). It is included only if it improves held-out O1 likelihood.

**Joint objective:**
$$\mathcal L=\ell_{O1}+w_2\ell_{O2}+w_3\ell_{O3}+w_4\ell_{O4}+w_5\ell_{O5}+\log p(\theta)$$
- $w_k=1$ is the principled default for correctly specified components.
- $w_4$ and $w_5$ are tempered (0.3–0.5) because those likelihoods are known to be misspecified.
- The tempering weights are chosen by spatial-block CV on O1, never on O3.

### 3.5 Training

- **Optimisation.** MAP by L-BFGS in PyTorch on GPU. A convolution over about 300k checklist footprints and three state-wide grids takes minutes. NUTS in NumPyro gives full posteriors: precompute the kernel-convolved covariate stacks on a coarse grid of bandwidths, interpolate in $h$, then run about 4 chains × 1,000 draws.
- **Spatial cross-validation.** 25 km blocks. This is larger than the largest kernel (about 1 km), than checklist footprints and than the 3 km blocks used now. Fold assignment is by block, stratified by state.
- **No-future rule.** `age(s,Y)` uses only disturbance up to $Y$. The existing `tsd` discipline is reused.

### 3.6 Inference and end product: "Covert Finder"

1. **Covert segmentation.** Polygons are the connected components of $q(s,Y)>q_{0.8}$, merged with LCMS removal patches by year and EVT boundaries. The minimum is 2 ha and the maximum is split at 40 ha.
2. **Per-covert record:**
   - $\widehat F(c,Y)$ in flushes/h with an 80% credible interval;
   - a forecast for $Y+1$ and $Y+2$;
   - age class and guild;
   - walking distance and elevation gain from the nearest drivable point;
   - access class (PAD-US public / easement / large industrial forest / other, with posting unknown);
   - an "explored?" flag.
3. **Loop planner.** From a chosen parking point, choose a walking loop of 60–120 min that maximises $\sum_c \widehat F(c)\cdot\text{time in }c$. This is an orienteering problem on a cost raster, solved by beam search. An optional Thompson-sampling mode draws $F$ from the posterior, so uncertain coverts sometimes win. That is exploration which also collects O3 data.
4. **Outputs.** A GeoPackage and GPX for phone apps, a web map, and a season "forecast note" (regional level $\tau$).
5. **Annual refresh:**
   - each spring, a new LCMS/Hansen year;
   - each summer, $\tau$ updated from drumming and brood reports;
   - after each season, hunt logs are ingested and the posterior is updated.

---

## 4. Why it beats the status quo

| Report diagnosis | Status quo | CYM |
|---|---|---|
| "The data is the ceiling" (§5.4): GBM ≈ CNN at 0.77 | More capacity on the same labels | **New information**: effort-explicit non-detections (O1), the estimand measured directly (O3), aggregate scale (O2). Fresh annual stand age plus lidar understory on the covariate side |
| Estimand is a log density ratio of recording processes (§5.1) | Map = "resembles grouse-recording landscapes" | Map = **fall density and flushes/h**, with a physical scale checked against state flush rates |
| PU problem: negatives are unlabelled presences (§5.4) | Buffered target-group negatives, AN-full | Detection/non-detection with a detection model: "not reported" is modelled as $1-p$, not as "absent" |
| Effort bias only partly cancels; `road_dist` encodes birding (§5.3) | Road distance used as a habitat input | Effort enters only the *detection* side (O1) or a dropped bias term (O5). Road distance enters the *product* only as access, never as habitat |
| Location error: km-scale pins labelled as one 30 m pixel (§2.4.1) | Centre-skip assumes the label is at the centre | Each checklist footprint $B_i$ integrates over its plausible sampled area |
| Temporal mismatch; static 2020–24 map; succession clock (§2.4.2, §5.6 Q5) | Latest-vintage prediction | Annual stand-age cube with a forward forecast |
| Label noise means a 12M-parameter model fits noise (CR-0009 picked epoch 3/10) | Heavy regularisation tricks | About 30 interpretable parameters with literature priors. Overfitting is structurally limited, and every parameter can be checked against ecology |
| Nothing checks outputs against the ground (§5.6) | Internal validation AUC | Pre-registered field flush-rate test, plus held-out checklists and drumming routes |
| Misregistration bugs (BUG-0094/95/96) | 15 aligned rasters, 6 shifted | Kernel-integrated covariates at 150–600 m are insensitive to sub-pixel shifts. The new downloads are gated on the template lattice anyway |

**On the +0.001 for harvest history.** I read this as the strongest evidence *for* the design, not against it. If stand age, the best-supported driver in the grouse literature, carries no signal for the current label, then either the label cannot see covert-scale habitat or `sclass` already encodes it. Either way a hunter needs a label that does see it. The cheapest experiment (§6) tells the two readings apart.

---

## 5. Expected gains, and how to measure them without fooling ourselves

### 5.1 Expectations (honest)

| Metric | Expected | Confidence |
|---|---|---|
| Presence-vs-target-group validation AUC (current scoreboard) | **No gain; possibly lower (0.70–0.77).** This scoreboard measures the recording contrast and CYM does not optimise it | high |
| Held-out (25 km block) complete-checklist detection: deviance explained beyond an effort-only model | effort-only AUC ≈ 0.70 (season and duration dominate). Adding CYM habitat gives **+0.02–0.06 AUC** and a significant log-likelihood gain. The CNN logit used as a covariate adds less than CYM, by a margin I guess at 0.01–0.03 AUC | medium-low |
| Within-region concordance (C-index of $\Lambda_i$ vs $y_i$ within 25 km regions, effort-matched) | 0.55–0.65. This is the hunter-relevant ranking power, and it is modest because grouse detection on checklists is noisy | low |
| Field flush rate, CYM top-decile accessible coverts vs random accessible forest | **1.5–3×.** Anchor: treated vs untreated areas differed by 1.75× in fall flush rates (0.61 vs 0.35 per 1.61 km), so top-decile selection should exceed that contrast | medium |
| Field flush rate, CYM top decile vs current-CNN top decile | **1.2–1.5×.** The mechanisms are the CNN's pull toward birding-accessible landscapes and its staleness about post-2019 cuts | low (this is the bet) |
| Calibration of absolute flushes/h | Within a factor of about 1.5 of state survey rates, statewide | medium |

### 5.2 Retrospective evaluation (weeks 2–4, no fieldwork)

- **E1. Checklist detection.** Held-out 25 km blocks; also temporal holdout (train ≤ 2023, test 2024–25). Report log-likelihood, Brier score and AUC, conditional on effort. Comparators:
  - (i) effort-only;
  - (ii) effort + current CNN logit;
  - (iii) effort + **zero-parameter heuristic** H = share of a 250 m radius in 5–20-year post-cut forest;
  - (iv) effort + eBird Status & Trends relative abundance, tested only on post-2023 checklists to avoid leakage;
  - (v) the full CYM.
- **E2. Within-region ranking.** Stratified C-index within 25 km regions and within effort strata. Regional level is removed, so this isolates what a hunter uses.
- **E3. Aggregate fit.** Leave-one-year-out prediction of state or regional flush rates (O2), and correlation with drumming indices.
- **E4. Mechanism audits.**
  - Posterior of $t_p$: the age peak should land at 5–20 years. If it lands at 40, something is wrong.
  - Guild ordering.
  - Kernel bandwidths should fall in the 100–600 m home-range scale.
  - These are *ecological unit tests*. A black box cannot fail them, so it also cannot pass them.

**Anti-self-deception rules:**
- Pre-register metrics and comparators in a CR before seeing E1 results (the QMS already requires acceptance gates; CR-0011 A3).
- Report the zero-parameter heuristic H everywhere. If CYM does not beat H, the learning added nothing.
- Keep fold blocks fixed by hash.
- No hyper-parameter is chosen on the test folds.

### 5.3 Prospective field test (hunting season 2026 or 2027)

**Design.**
1. Freeze the model before the season.
2. In each hunting day's area (≤ 30 min drive), draw three coverts:
   - one from CYM's top decile;
   - one from the current CNN's top decile, among cells not in CYM's top decile and vice versa;
   - one random accessible forest polygon of matched size.
3. Hunt each for a fixed 45–60 min, in random order. The hunter is blind to arm labels, which a helper script hides.
4. Log with the O3 protocol.

**Primary endpoint.** The flush-rate ratio CYM:random and CYM:CNN, from a NegBin GLMM with a day random effect.

**Power.** Baseline about 1.5 flushes/h with overdispersion $\phi\approx 2$. About 40 hours per arm (about 13 days of three 1-h coverts each) gives an SE of the log-ratio of about 0.2. That detects 1.5× at about 2 SE but not 1.2×. **CYM:CNN at 1.2× needs about 120 h/arm (two seasons or several hunters).** I state this up front so nobody over-reads a single-season result.

**Optional ARU validation.** Spring 2027: 40 AudioMoths stratified across CYM score deciles, 3 weeks each in April–May, with drumming detected by the OpenSoundscape model (Lapp et al. 2023). Fit occupancy per site with daily repeat surveys. This is design-based and independent of both eBird and hunters. Hardware cost about USD 5–6k.

---

## 6. Risks, failure modes and the cheapest falsification

| Risk | Failure mode | Mitigation |
|---|---|---|
| R1 Partial harvest invisible | Shelterwood and selection cuts (common in ME) leave a canopy; HF437 F1 0.72 at ≥ 30% BA. Young understory is missed | Lidar `under`; LCMS slow-loss; multiple-source agreement; uncertainty grows where products disagree |
| R2 Checklists too sparse in industrial north woods | Extrapolation where the most grouse are | Mechanistic structure transfers; spatial RE shrinks to 0; uncertainty map; ARUs targeted at gaps |
| R3 Grouse rarely reported on checklists (cryptic) | Weak O1 signal, wide posteriors | The spring drumming season raises detection; priors carry shape; this is a *quantified* weakness, not a hidden one |
| R4 Royle–Nichols misspecification (birders' detection is not Poisson-thinned) | Biased scale | Scale comes from O2/O3; O1 mainly ranks; posterior predictive checks |
| R5 Hunter data unavailable or coarse | No absolute scale or year effect | Physics prior plus drumming; the product shows relative ranks with a "scale uncertain" flag |
| R6 Priors wrong (e.g. spruce–fir regeneration in N Maine is good cover) | Bias | Priors are soft; the guild multipliers are free; E4 audits show when data disagree |
| R7 Field test underpowered | False "no difference" | Power stated in advance; multi-season accumulation; ARU complement |
| R8 Privacy and land access | Hunters will not share secret coverts; posted land is unmapped | Logs stay local to the owner; only parameters are pooled; access class is labelled "unknown, verify" |
| R9 New download pipelines repeat misregistration bugs | Shifted covariates | Template-lattice `crsTransform`; existing registration checks as acceptance gates; kernel smoothing reduces sensitivity |

### Cheapest falsification experiments

**F0 (one day on EC2, no new labels).** This reuses `diagnose_disturbance_features.py` and `diagnose_gbm_baseline.py` infrastructure. It is read-only and writes nothing under `data/`.
1. Compute the zero-parameter heuristic H (share of a 250 m radius with LCMS Tree Removal or Hansen loss at 5–20 years before the record year) and the mechanistic composite $K_{300}\ast q$ with prior-mean parameters, at the ~9,600 existing points.
2. Fit the GBM with **effort proxies only**: `road_dist`, NLCD developed share within 1 km, distance to the nearest eBird hotspot, county population density. Compare its AUC with the 0.770 from all 15 layers.
3. Fit the GBM with `sclass` removed, then with `sclass` removed and H added.

**Reading of F0:**
- If effort proxies alone reach ≥ 0.70, the current label is mostly birding geography. That supports root constraint 1.
- If H substitutes for `sclass` (the AUC drop from removing `sclass` is recovered by H), stand age *is* visible and simply redundant with `sclass`. If H stays near 0.5 alone, the current labels are blind to it.
- Neither outcome falsifies CYM by itself. F0 decides how much weight the argument in §4 can bear.

**F1 (the decisive one; about one week, after the EBD access request is granted).**
1. Fit effort-only versus effort + H versus effort + CNN-logit logistic models of grouse detection on complete checklists, with 25 km block CV.
2. **CYM's premise is falsified if:**
   - H, and $K\ast q$ under prior means, improve held-out checklist log-likelihood by less than the CNN logit does, *and*
   - neither improves the within-region C-index above 0.52.

   That would mean covert-scale stand age is not visible even in effort-explicit data. The design would then retreat to its estimand, evaluation and product layers (O2/O3 + field test), with the CNN as the density surface.

---

## 7. Implementation plan

Each phase is one CR under the QMS (`CLAUDE.md` §1), with acceptance scripts committed before approval (CR-0011 A3). New modules, with existing ones untouched except as noted:
- `habitat_cube.py`
- `ebird_checklists.py`
- `cym_model.py`, `cym_fit.py`
- `eval_checklists.py`
- `covert_finder.py`
- `hunt_log.py`

| Phase | Work | Effort |
|---|---|---|
| **P0, day 1** | Submit the eBird EBD + SED request and the S&T key request. Email ME IF&W, NH F&G and VT FWD for hunter-survey (flushes, hours, unit, year) and drumming-stop data. Run **F0** on EC2 | 1 day |
| P1 | `habitat_cube.py`: annual age-since-cut fusion (LCMS, Hansen, HF437, LANDFIRE), guild cross-walk, Daymet snow, NLCD; on template grids with registration gates. Meta-CHM `under` fallback | 1–1.5 weeks |
| P2 | `ebird_checklists.py`: filter EBD (streaming pandas over the TSV), zero-fill, footprints $B_i$. Run **F1**. Then `cym_model.py` with O1 only; E1/E2/E4 vs baselines | 1.5–2 weeks |
| P3 | Add O2 (disaggregation) and O4; NumPyro posterior; spatial RE; region × year τ | 1–2 weeks |
| P4 | Lidar `under` from 3DEP/state LAZ (PDAL; the most I/O-heavy step, run per region on EC2) | 1–2 weeks |
| P5 | `covert_finder.py`: segmentation, access (PAD-US, OSM), loop planner, GeoPackage/GPX/web map. `hunt_log.py`: GPX + waypoint ingestion and the blinded field-test scheduler | 2 weeks |
| P6 | Season: blinded paired field test (O3 held out); post-season update | Oct–Dec |
| P7 (optional) | Spring ARU deployment; occupancy validation | spring |

**First experiment the owner can run on EC2 today:** F0 above. It reuses the existing Earth Engine sampling and GBM harness, takes about 2–4 hours including EE sampling, and writes only to `/tmp`. Run the EBD request the same morning, since it gates F1.

---

## 8. References

Web-checked during this round unless marked.

1. Pasquarella, V., Thompson, J. (2023). Annual Maps of Forest Harvest Events in Maine from LANDSAT Imagery 1986–2019. Harvard Forest Data Archive HF437. https://doi.org/10.6073/pasta/20a838c4bd6922685b3d00661d45c414 ; https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF437
2. USFS Landscape Change Monitoring System, GEE `USFS/GTAC/LCMS/v2024-10`. https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10
3. Hansen, M.C. et al. (2013). High-resolution global maps of 21st-century forest cover change. *Science* 342:850–853. doi:10.1126/science.1244693 (DOI from memory, **not re-checked**). GEE `UMD/hansen/global_forest_change_2024_v1_12`.
4. eBird Basic Dataset download. https://ebird.org/data/download . eBird Status & Trends products (3 km, weekly, effort-standardised): https://ebird.r-universe.dev/ebirdst/doc/status.html
5. Johnston, A. et al. (2021). Analytical guidelines to increase the value of community science data: an example using eBird data to estimate species distributions. *Diversity and Distributions* 27:1265–1277. doi:10.1111/ddi.13271 (**not re-checked**).
6. Royle, J.A., Nichols, J.D. (2003). Estimating abundance from repeated presence–absence data or point counts. *Ecology* 84:777–790. doi:10.1890/0012-9658(2003)084[0777:EAFRPA]2.0.CO;2 (**not re-checked**).
7. Fithian, W., Elith, J., Hastie, T., Keith, D.A. (2015). Bias correction in species distribution models: pooling survey and collection data for multiple species. *Methods in Ecology and Evolution* 6:424–438. doi:10.1111/2041-210X.12242 (**not re-checked**).
8. Law, H.C.L. et al. (2018). Variational learning on aggregate outputs with Gaussian processes. NeurIPS. https://arxiv.org/abs/1805.08463
9. Nandi, A.K. et al. (2023). disaggregation: an R package for Bayesian spatial disaggregation modelling. *Journal of Statistical Software* 106(11). https://jstatsoft.org/index.php/jss/article/view/v106i11/4476
10. Lapp, S. et al. (2023). Automated recognition of ruffed grouse drumming in field recordings. *Wildlife Society Bulletin* 47(1). doi:10.1002/wsb.1395 ; OpenSoundscape tutorial: https://opensoundscape.readthedocs.io/en/latest/tutorials/ruffed_grouse_detector.html
11. Koleck, R. et al. (2026). Data from: Using passive acoustic monitoring and LiDAR to conduct a statewide assessment of ruffed grouse occurrence in Pennsylvania. Dryad. https://doi.org/10.5061/dryad.hmgqnk9xh
12. NH Fish & Game (2025). Ruffed Grouse and Woodcock Seasons Start October 1 (drumming counts, small-game hunter survey, effort concentrated in the North Country). https://nhfishgame.com/2025/09/22/ruffed-grouse-and-woodcock-seasons-start-october-1/ . NH flush rates of 2.27/h (2020) and 1.31/h (2019) are from a search summary of NH F&G pages (https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey). The page returned 403 to direct fetch, so the figures are **unverified**.
13. NY DEC Ruffed Grouse drumming/grouse-log report 2022. https://extapps.dec.ny.gov/docs/wildlife_pdf/grousedrumrpt22.pdf . The claim that drumming does not consistently predict flush rates at WMU scale comes from a search summary. The PDF was not parsed, so it is **unverified in detail**.
14. Fall flushing-rate contrast on treated vs control areas (0.61 vs 0.35 per 1.61 km). From a search summary of SORA *Journal of Field Ornithology* 69(3):474–485, https://sora.unm.edu/sites/default/files/journals/jfo/v069n03/p0474-p0485.pdf (**unverified**: the PDF was not read).
15. Google Satellite Embedding V1 Annual (AlphaEarth), 10 m, 64-d, 2017–2024. https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL
16. Vermont 2023 statewide QL1 leaf-off lidar: https://vcgi.vermont.gov/document/2023-vermont-lidar-plan . NH statewide lidar: https://des.nh.gov/news-and-media/milestone-statewide-high-resolution-elevation-data-has-been-reached . Maine 3DEP: https://pubs.usgs.gov/publication/fs20233036/full
17. Daymet V4 on GEE: `NASA/ORNL/DAYMET_V4` (**catalog ID from memory**).
18. PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview (**URL from memory**).
19. Maine Forest Service FOResT / Forest Operations Notifications (harvest notices since 2021 online; possible future cut-polygon source, access **unverified**). https://www.maine.gov/dacf/mfs/rules_regs/fons.html
20. Repository and report facts: `docs/grouse_model_report.md` §1–§5; `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md` (harvest history +0.001, GEDI +0.000, Meta CHM +0.009); `diagnose_disturbance_features.py`.
21. Ecological facts (Gullion density, age windows, home ranges, nest data): report §1, refs [1]–[19] there (FEIS, Mangelinckx et al. 2020, etc.).
