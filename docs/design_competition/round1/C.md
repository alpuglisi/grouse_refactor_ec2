# Design C: FLUSH, an effort-standardised grouse encounter-rate model for finding coverts

**FLUSH** stands for *Footprint-pooled Learning of Unit-effort Standardised Habitat*.

Designer C, round 1. Primary technique: morphological analysis (Zwicky box). Secondary techniques: constraint inversion and a pre-mortem.

---

## 1. Title and pitch

**FLUSH: change the label rather than the network. The model predicts expected grouse encounters per standard hour on foot in each 10–40 ha covert.**

The report shows that the 0.76–0.77 AUC ceiling comes from the labels and estimand: GBM ≈ CNN. Harvest history added +0.001 and GEDI added +0.000. FLUSH therefore makes three changes:

1. **Labels.** It stops contrasting grouse records against other-species records. Instead it trains on eBird **complete checklists**: detection/non-detection, with duration, distance, protocol, time, date and observer-skill covariates.
2. **Model structure.** The model has two additive parts:
   - a habitat log-rate *f(s, t)* that is pooled over the checklist's own spatial footprint;
   - a separate log-effort/detectability term *g(w)*. At prediction, *g(w)* is fixed to "one hunter, one hour, 2 km on foot, mid-October, morning".
3. **Inputs.** Habitat is read mainly through **AlphaEarth Satellite Embeddings**: 64-d, 10 m, annual 2017–2024, CC-BY. A Landsat **succession clock** (Hansen loss year / LCMS) adds stand age, the existing LANDFIRE summaries are kept, and 3DEP airborne lidar is a phase-3 add-on.

The loss is a proper cloglog Bernoulli likelihood with an effort offset. The estimand is therefore an absolute, effort-standardised encounter rate, not a density ratio.

Evaluation uses held-out **complete checklists inside the status-quo CNN's own validation blocks**. This gives an apples-to-apples, effort-stratified comparison with the current map. Hunter-relevant metrics (Lift@5% of coverts) and independent hunter flush-rate data back it up. Last, a pre-registered prospective test uses the owner's own GPS-logged hunts.

The end product is a ranked **covert map** for the hunter. Each covert carries:
- an encounter rate with an interval;
- a 5-year succession trajectory (rising / peak / declining);
- access flags.

---

## 2. Brainstorming record

### 2.1 Technique 1: morphological analysis (Zwicky box)

**Step 1: dimensions and options.** There are 10 dimensions with 5–7 options each. Codes are used in the scoring below.

| # | Dimension | Options |
|---|---|---|
| D1 | **Label source** | L1 eBird/GBIF incidental presences (status quo) · L2 eBird EBD **complete checklists** (detection/non-detection + effort) · L3 L2 with repeat-visit closure (occupancy structure) · L4 state hunter flush logs (NH/ME/VT, aggregated) · L5 integrated L2 + presence-only (iNat/GBIF non-eBird) + L4 · L6 acoustic recorder (ARU) drumming detections · L7 owner's own GPS-logged hunts |
| D2 | **Estimand** | E1 presence / target-group density ratio (status quo) · E2 relative intensity with bias covariates (IPP) · E3 **effort-standardised encounter rate** · E4 occupancy ψ · E5 hunter flushes per hour · E6 abundance/density |
| D3 | **Negative / background design** | N1 buffered target-group draw (status quo) · N2 uniform quadrature background · N3 observed non-detections, effort-modelled · N4 nnPU unlabelled background · N5 N3 + spatio-temporal **balancing** of checklists (Johnston et al. 2021) |
| D4 | **Modalities** | I1 LANDFIRE/TreeMap/NLCD stack (30 m) · I2 **AlphaEarth embeddings** (10 m, annual) · I3 raw Sentinel-1/2 / HLS time series, or Prithvi-EO-2.0 / Clay embeddings · I4 3DEP airborne lidar structure (1 m CHM / point-cloud metrics) · I5 GEDI / ICESat-2 sparse footprints · I6 **succession clock** (Hansen GFC loss year, LCMS fast/slow loss) · I7 climate, snow and topography (Daymet / SNODAS / 3DEP DEM) |
| D4b | **Spatial scale** | S1 30 m pixel · S2 1.92 km window (status quo) · S3 **multi-radius discs 60 m–2.4 km pooled by a learned, footprint-aware gate** · S4 S3 + regional 10–25 km context |
| D5 | **Model family** | M1 ResNet CNN (status quo) · M2 LightGBM · M3 **structured additive neural net** (habitat MLP ⊕ effort net) · M4 fine-tuned foundation model (Prithvi/Clay, end-to-end) · M5 Bayesian hierarchical occupancy (spOccupancy / INLA) · M6 **stack of M2 + M3** |
| D6 | **Loss** | Lo1 focal / AN-full BCE · Lo2 **cloglog Bernoulli with log-effort offset** · Lo3 occupancy marginal likelihood · Lo4 Poisson/NB on counts · Lo5 nnPU |
| D7 | **Spatio-temporal structure** | T1 static window, ±2 yr vintage matching (status quo) · T2 **per-year annual features matched to checklist year** (2017–2024) · T3 T2 + **age-forward succession forecast** · T4 + spatial random effect (SPDE / Fourier basis) · T5 before/after disturbance pairs |
| D8 | **Evaluation** | V1 3 km block validation AUC on presence vs target group (status quo) · V2 spatial-block CV on held-out complete checklists: effort-stratified AUC, log-loss, Brier · V3 **Lift@k over coverts** · V4 external aggregates: NH/ME/VT hunter flush rates · V5 **pre-registered prospective hunts** · V6 out-of-region structured data (PA ARUs) |
| D9 | **End product** | P1 30 m suitability raster · P2 **covert polygons with encounter rate ± interval** · P3 + succession trajectory · P4 + access layer (PAD-US, trails, roads) · P5 adaptive loop: the map proposes informative coverts, and logs feed back |

The matrix holds 7·6·5·7·4·6·5·5·6·5 ≈ 2.6 × 10⁷ cells, so not every one can be scored. The search therefore ran in two passes: a consistency filter (Step 2), then scoring of named configurations (Step 3).

**Step 2: pruning rules (cross-consistency matrix).** A combination is pruned when any of these pairs appears:

| Inconsistent pair | Why |
|---|---|
| L1 × {E3, E4, E5} | Presence-only data cannot identify an absolute rate or occupancy, because it has no non-detections (report §4.1–4.2; Ward 2009). |
| L1 × Lo2 / Lo3 | There is no effort variable to offset, and no non-detection to contribute a (1−p) term. |
| L2 × N1 | This would discard true non-detections in favour of a proxy background. It is strictly dominated. |
| L4 as the sole training label × S1–S3 | Hunter logs exist only as region/WMU aggregates (n ≈ 4 NH regions × years). Training a 30 m model on them is an ecological fallacy, so they are evaluation data only (V4). |
| L6 | No ARU network exists in ME/NH/VT. The PA dataset (Koleck et al.) obscures its coordinates "to prevent the misuse of this data for hunting", so it cannot be used for point-level evaluation either. Pruned except as a later field-campaign idea. |
| I4 (single-epoch lidar) × T1 | The ±2-year rule deletes records outside each lidar flight's window. Lidar is only consistent with **I6** ageing, i.e. masking or ageing pixels disturbed after the flight. |
| I5 (GEDI) as primary | It is sparse along tracks and already measured at +0.000 AUC. It is an auxiliary at most. |
| M1 (CNN) × S3 tabular footprint features | This is an architectural mismatch. A CNN only makes sense with S2 rasters. |
| M4 × a 6-week budget | Pixel-level fine-tuning of a 300–600 M-parameter model across 3 states is costly. GBM ≈ CNN also says spatial pattern capacity is not the bottleneck. |
| V1 × any L2 design | Presence-versus-target-group AUC and detection AUC are not on the same scale, so they are not comparable. |
| E5 × Lo2 trained on L2 | Allowed only through the standardisation step (birder-to-hunter calibration is a scalar, checked against V4). It is not a separate model. |

**Step 3: scoring.** Each surviving named configuration is scored 1–5 on four criteria. Weights are in brackets:
- **G**: expected gain in the owner's goal of precise covert ranking (0.40);
- **I**: identifiability and defensibility of the estimand (0.25);
- **F**: feasibility on EC2 within about 6 weeks (0.20);
- **R**: robustness to adversarial review, i.e. leakage, effort confounding and registration bugs (0.15).

| ID | Configuration (D1 · D2 · D3 · D4/S · D5 · D6 · D7 · D8 · D9) | G | I | F | R | **Score** |
|---|---|---|---|---|---|---|
| C0 | Status quo: L1·E1·N1·I1/S2·M1·Lo1·T1·V1·P1 | 1 | 1 | 5 | 2 | 1.95 |
| C1 | Status quo + AlphaEarth: L1·E1·N1·I1+I2/S3·M2·Lo1·T2·V1·P1 | 2 | 1 | 5 | 3 | 2.50 |
| C2 | PU fix: L1·E1·N4·I1/S2·M1·Lo5·T1·V1·P1 | 1.5 | 2 | 5 | 2 | 2.40 |
| C3 | Bias-covariate IPP: L1·E2·N2·I1+I2/S3·M2·Lo4·T2·V1·P1 | 2 | 2.5 | 4 | 3 | 2.68 |
| C4 | Lidar-centred status quo: L1·E1·N1·I1+I4+I6/S2·M1·Lo1·T1·V1·P1 | 2 | 1 | 2 | 3 | 1.90 |
| C5 | Foundation-model fine-tune: L2·E3·N5·I3/S2·M4·Lo2·T2·V2·P1 | 3.5 | 4 | 1.5 | 3 | 3.15 |
| **C6** | **FLUSH: L2·E3·N5·I2+I6+I1+I7/S3·M6·Lo2·T3·V2+V3+V4+V5·P2+P3+P4** | **4.5** | **4.5** | **3.5** | **4** | **4.23** |
| C7 | Neural occupancy: L3·E4·N3·I2+I6/S3·M3·Lo3·T2·V2·P2 | 3.5 | 4.5 | 3 | 3 | 3.58 |
| C8 | Full integrated SDM: L5·E3/E4·N3+N2·I2+I6/S3·M5·Lo2+Lo4·T4·V2+V4·P2 | 4 | 5 | 1.5 | 3.5 | 3.68 |
| C9 | C6 + 3DEP lidar: L2·E3·N5·I2+I4+I6/S3·M6·Lo2·T3·…·P2+P3 | 4.6 | 4.5 | 2.5 | 3.5 | 3.99 |
| C10 | C6 + adaptive loop: …·V5·P5 | 4.6 | 4.5 | 3 | 4 | 4.17 (long run) |
| C11 | C6 trained on spring-only checklists (drumming) | 3.5 | 3.5 | 3.5 | 3.5 | 3.50 |

**Convergence.** C6 has the best score that is feasible now. C9 (lidar) and C10 (adaptive loop) are add-ons to C6, not competitors, so they go into phases 3–4. C7 (occupancy) has the strongest theory, but its closure assumption is hard to defend for traveling eBird checklists. It is kept as a sensitivity model in phase 3 so that the encounter-rate ranking can be cross-checked against ψ. C8 is the gold standard but is too slow at three-state scale. Its useful parts, effort offsets and hunter aggregates used for checking, are already in C6.

### 2.2 Technique 2: constraint inversion ("what if the opposite of each status-quo assumption held?")

| Status-quo assumption | Inversion | Idea kept? |
|---|---|---|
| "Negatives must be manufactured" | Negatives already exist: millions of complete checklists without grouse | **Yes**: the core of FLUSH |
| "Effort bias must be cancelled through the background" | Effort should be *modelled* explicitly and then *set* at prediction | **Yes**: the g(w) term |
| "The label belongs to the centre pixel" | The label belongs to the observer's *path* | **Yes**: footprint gating by distance travelled |
| "Inputs must be ±2-yr LANDFIRE vintages" | Use an annual product with 2017–2024 coverage | **Yes**: AlphaEarth + Hansen are annual. This also recovers the 2017–2019 records the project currently discards |
| "Evaluate on our own validation split" | Evaluate on someone else's data | **Yes**: hunter flush aggregates, prospective hunts |
| "Output a pixel map" | Output the unit a hunter actually walks: a covert | **Yes** |
| "Habitat is static" | Habitat has a 10–20-year clock | **Yes**: age-forward forecast |
| "More capacity" | Less capacity, with a strong pretrained representation | **Yes**: GBM + small MLP on frozen embeddings |

### 2.3 Technique 3: pre-mortem ("it is 2027 and FLUSH failed. Why?")

Each failure story maps to a risk and a falsification test in §6:

1. eBird grouse detections are mostly spring drumming heard from roadsides, so the habitat term learned roadside acoustics → §6 R1.
2. AlphaEarth embeddings encode birder infrastructure (trailheads, parking) → §6 R2.
3. EBD access was slow, or the license blocked the product → §6 R5.
4. Effort and habitat were confounded, so standardisation extrapolated badly → §6 R3.
5. The covert ranking was right on average but wrong in the top 1% that hunters actually visit → V3 / V5 metrics.

---

## 3. The design

### 3.1 Data sources

| Role | Dataset | Access | Verified |
|---|---|---|---|
| Labels + effort | eBird Basic Dataset (EBD) + Sampling Event Data (SED), US-ME/NH/VT, 2017–2024 (2025 when released) | Free; requires an access request at https://ebird.org/data/download ; parse with Python (pandas/polars) or R `auk` | Yes (auk docs) |
| Why not GBIF | GBIF eBird Observation Dataset records have **no eventID or sampling effort**, so complete checklists cannot be rebuilt from the project's existing GBIF path | — | Yes, checked via the GBIF API on 2026-10-05 (fields absent) |
| Primary habitat representation | Google **Satellite Embedding V1** (AlphaEarth Foundations), `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, 10 m, bands A00–A63, unit-length, 2017–2024, CC-BY 4.0 | Earth Engine (already used by the repo) | Yes (catalog page) |
| Succession clock | Hansen GFC `UMD/hansen/global_forest_change_2024_v1_12` (`lossyear` 2001–2024); USFS LCMS v2024-10 (`USFS/GTAC/LCMS/v2024-10`, annual fast/slow loss and gain since 1985) | Earth Engine | Yes (catalog pages) |
| Status-quo stack | The existing 15 layers, as GBM neighbourhood summaries | On EC2 | — |
| Structure (phase 3) | USGS 3DEP lidar point clouds / 1 m DEM. Statewide QL2 in VT, NH complete in 2025, ME near-statewide, with mixed vintages (~2010s–2024) | AWS Entwine / LidarExplorer | Yes for VT/NH coverage; **ME vintages unverified** |
| Climate / snow / terrain | Daymet V4 (`NASA/ORNL/DAYMET_V4`) SWE and Tmin; 3DEP 10 m DEM | Earth Engine | From memory, **unverified** asset IDs |
| Access layer | PAD-US 4.x; OSM trails | USGS / OSM | From memory, **unverified** version |
| External evaluation | NH Fish & Game Small Game Summary: hunter grouse observation rates per 100 h by region (North / White Mtn / Central / SW), 2013–2022+; equivalent ME/VT hunter-cooperator data on request | NHFG PDF (403 to this agent; the owner can download it); ME/VT on request | Partial: figures seen in search snippets (e.g. 143 grouse/100 h with dog, North Region 2018); **ME/VT availability unverified** |
| Optional comparators | Prithvi-EO-2.0 (HF `ibm-nasa-geospatial`), Clay v1.5 S2 embeddings (Source Cooperative / AWS) | Open | Yes |

### 3.2 Estimand

For a location *s* (a covert or pixel) and year *t*, define the **standardised encounter rate**

$$
\mu^{*}(s,t)=\mathbb E\big[\#\text{grouse detections}\mid \text{habitat at } s,t;\ w=w^{*}\big],
$$

where $w^{*}$ = {one observer of median skill, 60 min, 2 km on foot, 15 October, 07:30–10:30}. The hunter-facing probability is

$$
p^{*}(s,t)=1-\exp\!\big(-\mu^{*}(s,t)\big),
$$

the probability that a standard one-hour walk produces at least one grouse encounter.

This is an observational *rate*, not occupancy or density. It is, however, what a hunter cares about, and complete checklists **identify** it, including the intercept, because non-detections are real data (report §4.2). Effort no longer has to be cancelled by hoping that the target group shares grouse's observation process (report §4.8). Effort is *conditioned on and then fixed*.

### 3.3 Data preparation

**Checklist filter**, following Johnston et al. (2021) and the eBird best-practice guide:
- complete checklists only;
- protocol ∈ {Stationary, Traveling};
- duration ≤ 5 h; distance ≤ 5 km; observers ≤ 10;
- years 2017–2024;
- shared checklists collapsed to one by `GROUP IDENTIFIER`.

The label is $y_j = 1$ if grouse are reported (count "X" counts as 1), else 0. The count $c_j$ is kept for an auxiliary head.

**Effort and detectability covariates $w_j$:**
- log duration and log(1 + distance);
- protocol;
- number of observers;
- day of year (cyclic spline);
- start time (hours since sunrise);
- observer skill index from species-accumulation curves (Kelling et al. 2015), fitted on the observer's *other* checklists so that it never sees grouse outcomes;
- a hotspot flag (`LOCALITY TYPE == H`).

Road distance is **not** in $w$; see R3.

**Spatio-temporal balancing.** Use a 3 km × 3 km × year × {det, non-det} grid. Each cell is capped at *k* checklists (k tuned; Johnston uses one per cell, here a cap of about 10). This flattens birding hotspots without changing the conditional target $P(y\mid x,w)$. Because the target is conditional, balancing affects variance and focus, not bias.

**Splits.** Use **10 km spatial blocks** on EPSG:5070 for 5-fold CV. Block size is then checked against the residual variogram, as recommended in report §4.3. A separate **head-to-head test set H** covers checklists from 2020–2024 whose start point lies in a *validation* block of the status-quo split (`prepare_training_data.py` block ids, `SPLIT_SEED=42`). FLUSH is trained without any checklist within 1 km of an H block, so the status-quo CNN and FLUSH are both scored on locations neither trained on.

### 3.4 Features: the multi-radius footprint

Radii are $\mathcal R=\{60,150,300,600,1200,2400\}$ m, spanning the 2–100+ ha home-range range in report §1.5. For every radius $r$ and year $t$:

- **Embedding mean:** $A_r(s,t)=\frac1{|B_r|}\sum_{u\in B_r(s)}a(u,t)\in\mathbb R^{64}$, where $a$ is the AlphaEarth vector. The vectors are unit-length, so linear averaging is the documented composition.
- **Embedding heterogeneity:** $H_r(s,t)=1-\lVert A_r(s,t)\rVert_2\in[0,1]$. This is 0 for a uniform disc and grows with landscape mixing, a cheap **interspersion index** (report §1.5).
- **Embedding change:** $\Delta_r(s,t)=1-\langle A_r(s,t),A_r(s,t-1)\rangle/(\lVert\cdot\rVert\lVert\cdot\rVert)$, recent-change intensity at radius $r$. It catches partial harvests that Hansen misses (report §1.8 caveat 7).
- **Succession clock:** age $\alpha(u,t)=t-\text{lossyear}(u)$ (Hansen; LCMS fast loss fills pre-2001 back to 1985). Fractions $F_{r,k}$ of the disc in age classes $k\in\{0\text{–}4, 5\text{–}10, 11\text{–}15, 16\text{–}25, 26\text{–}40, >40/\text{never}\}$ follow report §1.2. Add the **age-class Shannon diversity** at each $r$ (Vermont's "three age classes per home range").
- **Status-quo features:** the `diagnose_gbm_baseline.py` neighbourhood summaries of the 15 layers, at the vintage nearest $t$ and within 2 yr where available, otherwise missing (LightGBM handles NaN).
- **Context:** elevation, mean Dec–Mar SWE (Daymet), and growing degree days at 1 km.

This gives about 6 × (64 + 3 + 7) + ~120 ≈ 560 features per checklist.

**Registration safety (PA lessons from BUG-0094/0095).** All disc means are computed **in Earth Engine in the native 10 m projection** with `ee.Kernel.circle(r, 'meters')` and sampled at checklist coordinates. Nothing is resampled locally for training. Prediction rasters are exported with an explicit `crsTransform` copied from the LANDFIRE template. A committed check samples 1,000 random points two ways (EE point sampling against the exported raster) and asserts a match (`check_layer_registration.py` pattern).

### 3.5 Model

**Structured additive cloglog model** for checklist *j*, with the footprint gate learned from distance:

$$
\eta_j=\underbrace{f_\theta\!\Big(\textstyle\sum_{r\in\mathcal R}\gamma_r(L_j,\pi_j)\,\phi(x_{r}(s_j,t_j)) \;\oplus\; z(s_j,t_j)\Big)}_{\text{habitat log-rate}}+\underbrace{g_\varphi(w_j)}_{\text{log effort/detectability}},\qquad P(y_j{=}1)=1-e^{-e^{\eta_j}} .
$$

- $\phi$ is a per-radius shared encoder: a 2-layer MLP, 74 → 64.
- $\gamma(L,\pi)=\operatorname{softmax}(\text{MLP}(\log(1+L),\pi))$ over radii. Long traveling checklists put weight on large discs and stationary ones on small discs. This is a principled answer to report §2.4.1 (location error of traveling counts).
- $z$ holds the scale-free context features, and $f_\theta$ is a 3-layer MLP with dropout.
- $g_\varphi(w)=\beta_D\log D+\beta_L\log(1+L)+h(\text{doy},\text{tod},n_{obs},\pi,\text{skill})$, with $\beta_D,\beta_L\ge0$ (softplus) for monotonicity.
- **Separability**: $g$ never sees habitat and $f$ never sees effort. This is what makes setting $w=w^{*}$ meaningful.
- A seasonal interaction $f\times\text{season}$ is *tested*, not assumed away (R1).

**GBM twin (M2).** LightGBM binary on [habitat features ∥ $w$]:
- monotone constraints +1 on duration and distance;
- prediction made with $w:=w^{*}$, the eBird Status & Trends standardisation approach;
- `interaction_constraints` keep effort features in their own group, so trees cannot mix effort and habitat. This approximates separability.

**Stack (M6).** Logit-average the two models' $p^{*}$, with a weight fitted on out-of-fold block-CV log-loss. The fit is on the same spatial folds (report §4.5).

**Ensembling and uncertainty.** Use 5 fold-models × 2 families. The between-member spread of $\log\mu^{*}$ is the epistemic interval. Pixels whose feature vector falls outside the training convex hull (Mahalanobis in PCA-20 space above the 99th percentile) are flagged **"extrapolation"**.

### 3.6 Loss and training

$$
\mathcal L(\theta,\varphi)=-\sum_j \omega_j\big[y_j\log p_j+(1-y_j)\log(1-p_j)\big]+\lambda_1\lVert\theta\rVert^2+\lambda_2\,\mathcal L_{\text{count}} ,
$$

- $\omega_j$ = balancing weights.
- $\mathcal L_{\text{count}}$ is an optional negative-binomial head on $c_j\mid y_j=1$, sharing $\eta$.
- This is a **proper** scoring rule: no focal loss, no label smoothing, no 50/50 batches. Calibration is therefore built in, and Platt scaling becomes a diagnostic, not a necessity.
- Optimiser: AdamW, cosine schedule, early stopping on block-CV log-loss.
- Compute: about 2 M rows × 560 float16 features ≈ 2.2 GB, so it fits in GPU memory.
- Expected run time is minutes per fold for both families (estimate).

### 3.7 Inference and end product

1. **Prediction grid.** A 30 m grid on the LANDFIRE template is too large: 141k km² × 560 features is about 175 GB. The habitat model is therefore evaluated on a **60 m grid** (≈ 3.9 × 10⁷ cells). Disc means are computed on EC2 from a 30 m export of the 64 AlphaEarth bands (int8-quantised, ~10 GB/year) with GPU FFT convolutions, chunked with a 2.4 km halo. A side-by-side sample of 10⁴ points checks them against EE `reduceRegion` (tolerance 1e-3).
2. **Standardise.** Set $w=w^{*}$ and $L=2$ km in the gate, giving $\mu^{*}$ and $p^{*}$ maps.
3. **Coverts.** Run SLIC superpixels on [AlphaEarth PCA-8 + age-class fractions], with a target size of about 15 ha and bounds of 5–40 ha, matching Gullion's cut size and the home-range scale. Each covert gets:
   - mean $\mu^{*}$ and its 80% ensemble interval;
   - **trajectory**: $\mu^{*}$ re-predicted with ages shifted by +1…+5 years (age fractions only; the embedding is held fixed, which makes this a labelled scenario rather than a forecast). Classes: *rising* (stands entering 5–15 yr), *peak*, *declining* (>25 yr);
   - access: PAD-US public / easement, distance to nearest road or trail;
   - extrapolation flag.
4. **Deliverables:**
   - a GeoPackage of coverts;
   - COG rasters of $p^{*}$ and the interval;
   - a static HTML/Leaflet map with the "top 50 coverts within X km of me" view;
   - a model card stating the estimand in one sentence.
5. **Hunter calibration (optional).** One scalar $\kappa$ maps birder encounters to hunter-with-dog flushes per hour: $\text{flush}_{\text{region,yr}}\approx\kappa\cdot\overline{\mu^{*}}_{\text{forest, region, yr}}$. It is fitted on NH regions and shown only as a secondary label. Ranking does not depend on it.

---

## 4. Why it beats the status quo

| Report diagnosis | Status quo | FLUSH |
|---|---|---|
| "The data is the ceiling" (§5.4: GBM ≈ CNN; GEDI +0.000; harvest +0.001) | Adds layers under the same labels | Changes the **labels**, the only lever the report says has never been pulled (§4 next step #1), *and* adds a representation that is learned from multi-sensor time series rather than hand-built LANDFIRE codes |
| PU problem (§4.4): negatives are unlabelled presences | 300 m buffer + target group | Non-detections are *observed* and carry effort. A short checklist with no grouse is weak evidence; a 3 h walk with no grouse is strong evidence. The likelihood weights them accordingly, which PU methods cannot do |
| Structural AUC bound $1-a/2$ (§4.1) | Binding: the target group shares grouse's forest | Does not apply. The comparison is detection vs non-detection *given effort*, with no shared-support tie |
| Effort bias (§4.8, §5.3: road distance learned as birding behaviour) | Partial cancellation, unknown sign | Effort is explicit, separable and **fixed at prediction**. Road distance is excluded from both terms by design and audited (R3) |
| Estimand (§5.1: log density ratio, prevalence unknown, `--prior` is a scenario) | Relative score, 50:50 calibration | Absolute probability of ≥1 encounter per standard hour, with the intercept identified |
| Location error (§2.4.1: traveling counts span km; centre-skip assumes centre) | Centre-pixel label, 64-px window | Footprint gate keyed to distance travelled |
| Temporal mismatch (§2.4.2: LANDFIRE starts 2022; 2016–2019 records discarded) | ±2-yr rule deletes ~23.5% of positives | Annual inputs 2017–2024 match each checklist's own year. No deletion |
| Succession clock (§5.6 Q5) | Static map | Explicit age classes plus a 5-year trajectory per covert |
| Misregistration (BUG-0094/95/96) | 6 of 15 channels shifted ~21 m | Primary features are computed in EE native projection at point coordinates, with no local warps. The legacy stack is a minor input group whose ablation is reported |
| Epistemic status (§5.6: no external check of outputs) | None | Held-out checklists in the CNN's own validation blocks, hunter aggregates, and prospective hunts |

**Why embeddings may succeed where GEDI and harvest layers failed.** Those layers were tested *under presence-vs-target-group labels*. Their information was partly redundant with LANDFIRE, and the label noise floor absorbed the rest. AlphaEarth adds two new things: annual phenology and texture from S1/S2/Landsat, and a 10 m grain that resolves the 0.1–10 ha patch mosaic. FLUSH tests the embeddings under *both* label regimes (experiment A in §7), which separates "new input" from "new label" effects.

---

## 5. Expected gains, with honest uncertainty

AUC under the new labels is **not** on the same scale as the 0.77 presence-versus-target-group AUC. Comparisons are therefore only made on the shared test set **H** (§3.3).

| Metric on H (complete checklists in status-quo validation blocks) | Status-quo CNN map score | FLUSH (expected) | Confidence |
|---|---|---|---|
| **Effort-stratified AUC** (AUC within protocol × duration-tercile × season strata, n₊n₋-weighted). This is the habitat-only ranking | 0.62–0.70 (guess) | **0.70–0.78** | Low–medium. The size of the gap is the uncertain part |
| Total AUC with effort included (FLUSH only) | n/a | 0.80–0.88 | Medium. Effort alone is strongly predictive, so this number is reported but **not** used as a claim |
| Log-loss / Brier (calibrated) | Needs a re-fit Platt on H-train | Better by construction | High |
| **Lift@5%**: detections per checklist-hour among H checklists in the top-5% coverts ÷ overall rate | 1.5–2.5× (guess) | **2.5–4×** | Low |
| Spearman with NH regional hunter rates (4 regions, ≥8 years) | Unknown | ρ > 0.5 hoped | Low (tiny n). Supportive only |

**Where the gain comes from, in decreasing expected order:**
1. real non-detections plus effort, which removes PU noise and the TG shared-support bound;
2. annual 10 m embeddings and the succession clock;
3. footprint gating;
4. recovered 2017–2019 data.

Each has an ablation on H:
- (1) **FLUSH-LF**: same labels, status-quo features only;
- (2) **FLUSH-noAEF**: drop the AlphaEarth features;
- (3) **fixed-radius**: replace the gate with one fixed radius;
- (4) **2020+ only**: train on 2020–2024 only.

**How not to fool ourselves:**
- Block-bootstrap CIs over H blocks (1,000 resamples).
- Results are "real" only if the CI on the effort-stratified ΔAUC excludes 0 *and* Lift@5% improves.
- The status-quo map is re-scored at H locations with the **same** prediction code (`predict.py`, stride 1 at the points).
- H, $w^{*}$, the metrics and the kill criteria are frozen in a committed script **before** FLUSH is fitted (per CR-0011 A3: gate code first).
- Report results separately for the hunting season (Sep–Nov checklists). A model that wins only in spring is a drumming model, not a hunting model.

---

## 6. Risks, failure modes and the cheapest falsification

| # | Risk | Mechanism | Mitigation / test | Cheapest falsification |
|---|---|---|---|---|
| R1 | **Season confound**: most detections are spring drumming heard, possibly near roads | Habitat term learns "audible from a road in May" | `doy` sits in $g$; fit $f\times$season and compare Sep–Nov vs Apr–Jun maps (Spearman over coverts); train and test on fall only (C11) | If the fall-only vs all-season covert Spearman is < 0.7, ship the fall model |
| R2 | **Embeddings encode birding infrastructure** | Trailheads, parking lots and feeders are visible at 10 m | Non-detections from the *same* infrastructure largely cancel this (every checklist sits at infrastructure). Integrated-gradients/SHAP audit on hotspot vs non-hotspot checklists | AUC of the hotspot flag predicted from $f$'s output > 0.65 ⇒ leakage of locality type into habitat |
| R3 | **Effort–habitat confounding** (long walks happen in big woods) | Standardisation extrapolates | Separability; check overlap of $w$ distributions across habitat deciles; report $p^{*}$ at three standards (0.5 h, 1 h, 2 h). Ranking should be invariant: identical by construction in M3, and checked in M2 | Kendall τ between maps at different $w^{*}$ < 0.95 in the GBM ⇒ use M3 only |
| R4 | **Sparse detections** (grouse on maybe 1–4% of checklists; **unverified**) | Few positives per block | Balancing, block CV, NB counts. If the count of detection checklists in ME/NH/VT 2017–2024 is < 5k, merge occupancy closure (C7) | Phase-0 count (one `auk`/polars filter) |
| R5 | **EBD access / license** | Request delay; terms restrict redistributing *raw* data | Request on day 0 (usually days). Products are derived maps, which the terms allow (**unverified**: re-read the terms). Raw EBD is never published | — |
| R6 | **AlphaEarth version drift / 2025 gap** | Catalog says 2017–2024 at time of writing | Pin the asset version in config. Predict 2026 from 2024 embeddings + Hansen 2024 + age-forward; label as such | — |
| R7 | **Covert segmentation artefacts** | SLIC boundaries cross roads or ownership | Constrain SLIC by road/water masks; also publish the 60 m raster | — |
| R8 | **Birder ≠ hunter detection** | Dogs flush birds that birders miss | Ranking is unchanged by a scalar κ. Prospective test V5 checks the ranking directly | Pre-registered fall 2026 hunts: Spearman between predicted $p^{*}$ and observed flushes/h over ≥ 20 coverts |
| R9 | **QMS overhead** | One-change-per-CR rule | Four small CRs (§7). Acceptance scripts are committed before approval | — |

**The single cheapest falsification of FLUSH's central claim** takes about 1 day after EBD arrives. Fit only the **GBM twin** with LANDFIRE-summary features (the existing `diagnose_gbm_baseline.py` features) on complete checklists, and score H.
- If **effort-stratified AUC(FLUSH-LF) ≤ AUC(CNN map) + 0.01**, changing the labels did not help, and the thesis is falsified.
- If it is > +0.02, the label thesis holds before any new input is added.

---

## 7. Implementation plan

Each phase is one CR under the project's QMS, with one independently landable change. Acceptance scripts land first.

| Phase | Work | Effort | CR |
|---|---|---|---|
| 0 (day 0) | Submit the EBD access request. Freeze the H-set definition and metrics script (`eval_flush_h.py`, gate code). | 0.5 d | CR-A (acceptance design) |
| 1 (day 1, **no EBD needed**) | **Experiment A: AlphaEarth under the current labels.** | 1 d | diagnostic only |
| 2 (week 1–2) | EBD/SED ingestion → `checklists.parquet` (filters, skill index, balancing). Phase-0 counts. **Cheapest falsification** run (GBM-LF on H). | 3–4 d | CR-B (data pipeline) |
| 3 (week 2–3) | EE feature extraction: AlphaEarth disc means / heterogeneity / change, Hansen/LCMS age fractions, context. Registration check. | 3 d | CR-C |
| 4 (week 3–4) | M2 + M3 + stack, 5-fold block CV, ablations, R1–R3 audits, H scoring | 4–5 d | CR-D (model) |
| 5 (week 5) | 60 m prediction, coverts, trajectories, access, HTML map, model card | 3–4 d | CR-E (product) |
| 6 (later) | 3DEP lidar structure (C9): per-tile PDAL metrics (fraction of returns 1–5 m, 2–6 m, p95, rumple) at 30 m, aged and masked by Hansen post-flight loss. Occupancy sensitivity model (C7). Pre-registered fall hunts (V5) and the adaptive loop (P5) | 2–4 wk | separate CRs |

Experiment A procedure:
1. For every existing train/val point (`train.build_datasets`, as in `diagnose_gbm_baseline.py`), sample in EE the AlphaEarth disc means at radii {60, 300, 1200} m and $H_r$ for the record's year.
2. Fit HistGB on (a) the existing features, (b) AlphaEarth only and (c) both, with the same split and 3 seeds.
3. Interpretation:
   - **(c) − (a) ≥ +0.01 AUC**: the embeddings carry new habitat information even under noisy labels.
   - **≈ 0**: this confirms the labels are the ceiling and raises the priority of phase 2.
   - Either way the result is informative.

**First command the owner could run on EC2 within a day.** Pseudocode sketch for a new read-only diagnostic, mirroring `diagnose_lidar_features.py`:

```python
# diagnose_alphaearth_features.py (read-only; writes only /tmp cache)
import ee, numpy as np
ee.Initialize(project=PROJECT)
AEF = ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL")
def aef_year(y):
    img = AEF.filterDate(f"{y}-01-01", f"{y+1}-01-01").mosaic()
    out = []
    for r in (60, 300, 1200):
        m = img.reduceNeighborhood(ee.Reducer.mean(), ee.Kernel.circle(r, "meters"))
        m = m.rename([f"a{r}_{i:02d}" for i in range(64)])
        norm = m.pow(2).reduce(ee.Reducer.sum()).sqrt()
        out += [m, ee.Image(1).subtract(norm).rename(f"het{r}")]
    return ee.Image.cat(out)
# sampleRegions per year on the train/val points (batched as in ddf.reduce_batches),
# scale=10, then HistGradientBoosting exactly as diagnose_gbm_baseline.fit_eval.
```

`reduceNeighborhood` at 1,200 m on 10 m pixels is costly. If EE times out, compute it at `scale=30` with `reproject`, or use a 300 m `reduceResolution` pyramid. This is noted as an engineering risk, not a blocker.

---

## 8. References

URLs were fetched or seen in search results on 2026-10-05 unless marked **unverified**.

- AlphaEarth Foundations / Satellite Embedding V1 (Earth Engine catalog): https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL. The page states 2017–2024, 10 m, A00–A63, unit length, CC-BY 4.0.
- Brown, C.F. et al. (2025). AlphaEarth Foundations: an embedding field model for accurate and efficient global mapping from sparse label data. arXiv:2507.22291. **Unverified arXiv id**.
- eBird Basic Dataset and `auk` (complete checklists, Sampling Event Data): https://docs.ropensci.org/auk/articles/auk.html ; request at https://ebird.org/data/download
- Johnston, A. et al. (2021). Analytical guidelines to increase the value of community science data: an example using eBird data to estimate species distributions. *Diversity and Distributions* 27:1265–1277. https://doi.org/10.1111/ddi.13271 (preprint seen: https://www.biorxiv.org/content/10.1101/574392v1). **DOI unverified**.
- Kelling, S. et al. (2015). Can observation skills of citizen scientists be estimated using species accumulation curves? *PLOS ONE* 10:e0139600. https://doi.org/10.1371/journal.pone.0139600
- Fink, D. et al. eBird Status & Trends (standardised relative abundance, 1 h / 2 km traveling checklist): https://science.ebird.org/status-and-trends ; `ebirdst` https://github.com/ebird/ebirdst
- Teng, M. et al. (2023). SatBird: a dataset for bird species distribution modeling using remote sensing and citizen science data. NeurIPS Datasets & Benchmarks. https://arxiv.org/abs/2311.00936
- Hansen, M.C. et al. (2013) *Science* 342:850. Global Forest Change v1.12: https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12
- USFS LCMS v2024-10: https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10 ; methods https://data.fs.usda.gov/geodata/rastergateway/LCMS/LCMS_v2024-10_Methods.pdf
- USGS 3DEP state fact sheets: Vermont https://pubs.usgs.gov/publication/fs20253033 ; New Hampshire https://pubs.usgs.gov/publication/fs20243056 ; Maine https://pubs.usgs.gov/publication/fs20233036
- Prithvi-EO-2.0: Szwarcman, D. et al. (2024) https://arxiv.org/abs/2412.02732
- Clay v1.5 Sentinel-2 embeddings: https://source.coop/clay/clay-v1-5-sentinel2 ; https://registry.opendata.aws/lgnd-clay-v1-5-sentinel2/
- NH Fish & Game Small Game Summary (hunter grouse observation rates by region): https://www.wildlife.nh.gov/sites/g/files/ehbemt746/files/inline-documents/sonh/small-game-summary.pdf. This returned 403 to the agent; the figures come from search snippets, so the contents are **unverified**.
- NH Ruffed Grouse Wing and Tail Survey: https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey (403; **unverified** contents)
- Koleck et al. (2026), PA ARU + LiDAR grouse occurrence, Dryad: https://doi.org/10.5061/dryad.hmgqnk9xh. Coordinates are obscured, so the dataset cannot be used for point validation (verified).
- Maine Bird Atlas 2018–2022: https://www.maine.gov/ifw/fish-wildlife/maine-bird-atlas/index.html. The atlas was collected *through eBird*, so it is **not** independent of EBD and is not used as external validation.
- MacKenzie, D.I. et al. (2002). *Ecology* 83:2248. https://doi.org/10.1890/0012-9658(2002)083[2248:ESORWD]2.0.CO;2 (occupancy, C7)
- Repository report: `/home/user/grouse_refactor_ec2/docs/grouse_model_report.md` §1.2, §1.5, §2.4, §4.1–4.4, §4.8, §5.1–5.6
- Daymet V4 and PAD-US 4.x asset identifiers: **unverified** (from memory).
