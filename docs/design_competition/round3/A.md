# Design A (final, round 3): CYM-H, the Covert Yield Model as a structured prior plus a trust-region learner

*Designer A. Primary technique: first-principles decomposition plus Five Whys.*
- *Added in round 2:* red-teaming and timeline inversion.
- *Added in round 3:* steelman-and-concede review of every critique, and "where does each parameter get its information?" accounting.

*No repository file was edited. "Verified" means checked this round against the repository, the GBIF API or the web.*

---

## 0. Changes from round 2

**Summary.** Round 2 critics found three real defects in CYM:
- the footprint *sum*;
- an injection test that compared two different truths;
- a T1 test that scored the CNN partly in-sample.

They also argued that a ~40-parameter structure caps precision. All three defects are fixed. The precision argument is accepted, and the answer changes the architecture:

**CYM-H = a mechanistic structural core used as an offset and as an extrapolation anchor + a flexible LightGBM residual whose influence is weighted by checklist support.**

- Where checklists are dense, the flexible learner has full authority. Precision is then the GBM's, not the structure's.
- Where birders never walk, the residual is shrunk toward zero, and the ecology carries the map. That is the dense young off-trail cover hunters want.

Whether that trade is worth it is decided by a corrected test (T2, a 2 × 2 cross) and by the head-to-head set. If it is not worth it, CYM-H collapses to the plain GBM, and that outcome is pre-registered.

**Fixed (critic credited):**

| Change | Critic |
|---|---|
| The footprint is now a kernel **mean**, with a free-sign distance slope, plus a season-specific detection radius (C's idea) | C (MAJOR) |
| T2 is now a full 2 × 2 cross: both models on both truths, scored on unvisited cells | D (MAJOR) |
| T1 is scored only on HH (checklists inside the CNN's own validation blocks), with the CNN read at the start point only | D (MAJOR) |
| T1 and the HH evaluation include the flexible GBM twin as a comparator, with a kill rule against it | B (MAJOR) |
| A trust-region residual replaces the "gated, ridge-shrunk" residual | B, D, E (precision) |
| Cover quality is **additive** in young regeneration and in dense understory under older canopy, so shelterwood with dense regeneration no longer reads as "mature, low" | B (scenario) |
| Guild priors are independent and weak, not ordered. New guilds: alder/shrub wetland, old field, spruce–fir regeneration. A separate age curve for softwood regeneration | E (MAJOR) |
| Hunter-effort weights in the aggregate term no longer use the model's own $q$. They are accessible forest only | B (MEDIUM) |
| The "blinded" field test is dropped. In its place come D's randomised fifth covert and a fixed-effort GPS protocol; the endpoint is flushes per GPS-km | C, E (MEDIUM) |
| The GMNF acoustic data is demoted to "on request, bonus" (no coordinates; verified by C and D) | C (MEDIUM) |

**Adopted from round-2 competitors:**

| Idea | From | Use in CYM-H |
|---|---|---|
| **Disturbance panel test** (location fixed effects before and after a cut) | **C** | Becomes the **within-site estimator of CYM's age curve**: a structural parameter identified free of site selection (T5) |
| **Owner's blinded covert scorecard**, frozen before any map is seen | **D** | Scorer S0, available today |
| Same-observer, same-day, first-visit **case-crossover** concordance | **D** | Primary preferential-sampling metric |
| Within-stratum **label-permutation** null | **D** | Effort-leakage null band and admission gate for any feature block |
| Season-specific footprint radius | **C** | Detectability module |
| Cross-play (home and away) label test; oracle ratio | **B** | The shared-core gate (G0) and the honesty metric |
| Naive-visit (first checklist at a location) subset | **E** | Inside the case-crossover |

**Dropped:**
- The round-2 framing of the prior-map field test as a decisive test. E is right that a null field result from an unfitted prior cannot separate "bad prior" from "bad idea". The prior map is now a **v0 product** for the first two weeks of the season, plus one arm scored by S0 and T1. It is not the verdict on CYM.
- NUTS is dropped. A Laplace approximation plus a fold ensemble are enough.

---

## 1. Title and pitch

**CYM-H predicts expected grouse flushes per hour of walking, per covert, this season.** Grouse ecology is used where birders never walk, and a flexible learner is used where they do.

All five designs now share the core: eBird complete checklists, an effort term that is dropped at prediction, footprints, a succession clock, coverts, and top-k lift. The remaining question is what happens **off the birders' map**.

- The hunter's best coverts are dense, young, off-trail regeneration.
- Every checklist model is trained where birders walk: trails, preserves, roadsides.
- A flexible learner then extrapolates into the hunter's target region from the edge of its support. Tree ensembles hold the boundary value constant.

**What CYM-H changes.**
- **The structure.** Stand-age hump, regeneration guild, understory, interspersion at home-range scale and physics-scaled flush rates are written in as an offset, with literature priors. Its key parameter, the age curve, is estimated *within sites* by C's panel test, so site selection cannot bias it.
- **The residual.** A LightGBM learns everything the structure misses, at full strength where checklists exist, and fades out with support.
- **Season one.** The owner gets a zero-fit v0 covert map this week. D's scorecard of past coverts grades it today. HH-checklist tests grade it within a week. A fitted CYM-H replaces it at a pre-registered date in mid-October.

---

## 2. Brainstorming record (short)

**First principles (rounds 1–2).**
- Flushes/h = $D\cdot 2W\cdot v$.
- $D$ = cover (age × guild × understory) ⊗ food ⊗ interspersion at 100–600 m × regional-year level × depletion.
- Physics check: prime cover gives about 1.5 birds/ha in fall × 6 ha/h swept ≈ 9 flushes/h; average hunted forest gives about 1–2/h. This matches NH's reported 1.3–2.3/h (search-summary figures, **unverified**).

**Five Whys (rounds 1–2).**
1. The label sets the ceiling, so the label must carry effort and absence.
2. Succession moves the map every year, so the clock must be explicit.
3. Nothing grades outputs, so ground truth is needed this season.

**New this round: "where does each parameter get its information?" accounting.** For every quantity the product needs, I asked which data identify it, and whether that data is *free of birder site selection*.

| Quantity | Identified by | Free of site selection? | Consequence for CYM-H |
|---|---|---|---|
| Within-landscape ranking in birded areas | Checklists (between-site) | No; case-crossover and first-visit help | Flexible residual, PS diagnostics |
| **Age response (hump)** | **C's panel: same sites before and after a cut** | **Yes (location fixed effects)** | **Structural $a(\cdot)$ estimated within-site, imported as fixed** |
| Response in unvisited cover (dense young off-trail) | Nothing observed; extrapolation | — | Structure carries it; residual is shrunk; T2 tests whether this beats GBM extrapolation |
| Spring vs fall detectability | Season-specific radius; fall head | Partly | C's radius, a fall head, and the transfer term from hunt logs |
| Hunter vs birder detection | Hunt logs only | Yes (randomised fifth covert) | $W(s)$ and the transfer term, from season 1 |
| Absolute scale, year level | NH rates, hunt logs | Yes | Scalar and τ only |

This table produced the trust-region residual, the within-site age curve and the decision to keep the structure as an anchor rather than the whole model.

**Steelman-and-concede.** For each critique I wrote the strongest version and checked it against the actual round-2 text (§9). Five were correct as stated and are fixed. One (the precision cap) was correct in spirit, and the fix changed the architecture.

---

## 3. The design

### 3.1 Estimand

For covert $c$ in season $T$ (October–December):

$$F(c,T)=2\,W(c)\,v\cdot\overline{D(s,T)}^{\,c}\qquad[\text{flushes/h}]$$

Ranking depends only on $\overline{D}$, plus a hunter transfer term once hunt logs exist (§3.4 O3). The scale has priors $v\sim\mathcal N(2.0,0.4^2)$ km/h and $W\sim\text{LogNormal}(\log 15\text{ m},0.4)$. It is labelled "relative" until NH rates and hunt logs calibrate it.

### 3.2 Habitat-state cube, per year 2016–2026

All layers sit on the per-region LANDFIRE template grid. Every Earth Engine export uses explicit `crs` + `crsTransform`. The gates are `grid_mismatch`, `check_layer_registration.py` and the `diagnose_fetch_tile_offset.py` probe (the PA lessons of BUG-0094/0095/0096).

| Layer | Source |
|---|---|
| `age`: years since the last heavy disturbance (fused: earliest event confirmed by ≥ 1 source within ±1 yr, with an agreement count) | LCMS v2024-10 Tree Removal / fast loss; Hansen GFC v1.12 `lossyear`; Maine HF437 (1986–2019); OPERA DIST-ANN 2023–24 and DIST-ALERT 2025–26 (D); LANDFIRE annual disturbance |
| `sev`: severity | LCMS fast-loss probability; LCMS slow loss (partial cuts) |
| `guild`: pre-cut guild for stands under 15 yr, current guild otherwise | TreeMap 2022 FORTYPCD crosswalk + EVT. Classes: aspen–birch, northern hardwood, mixedwood, oak–pine, pine–hemlock, spruce–fir, **alder/shrub wetland**, **old field/shrubland** |
| `under`: understory density | Leaf-off lidar share of returns 1–6 m (VT QL1 2023; NH GRANIT; ME 3DEP via PDAL). Pixels cut after the flight are set to missing. Fallback: Meta CHM `mch_f15` (CR-0032) |
| `conif`, `hwmature`, `dev`, `open`, `water`, `snow`, `elev` | TreeMap + age; annual NLCD; Daymet V4 (**asset ID unverified**); 3DEP DEM |
| Legacy block (residual only) | `diagnose_gbm_baseline.py` summaries of the 15 layers + `mch_*`, after the CR-0035 repair |
| AlphaEarth (residual only, admission-gated) | C's infrastructure-masked disc means |

To keep storage small, structural inputs are pre-convolved at 60 m on a bandwidth grid {100, 150, 225, 340, 500, 750} m. The learnable bandwidth interpolates between grid values. That is about 50 bands, roughly 4 GB per year for all three states. Checklist features are read at stencil points for the checklist's own year (E's fix).

### 3.3 The model: structural core + trust-region residual

**Cover quality.** This is additive, which fixes B's shelterwood scenario:

$$q(s,T)=m_{\text{guild}}\Big[a_{\text{grp}}\big(\text{age}\big)\,h(\text{sev})\;+\;\gamma_u\,u(\text{under})\,\mathbb 1[\text{age}>25]\Big]$$

- **Age curves.** $a_{\text{grp}}(t)=\exp\{-(\log(t{+}1)-\log(t_p^{\text{grp}}{+}1))^2/2\sigma_{\text{grp}}^2\}$, one for the hardwood regeneration group and one for the softwood group. The prior is $t_p\sim\mathcal N(10,4^2)$. **Each curve is fitted within sites (T5, from C's panel) and then held fixed** in the main fit, unless T5 is underpowered. In that case it is fitted between sites with the prior.
- **Understory.** $u$ is monotone and saturating. The second term lets a thinned or shelterwood stand with dense 1–6 m regeneration score high whatever its age.
- **Guild multipliers.** $\log m_{\text{guild}}\sim\mathcal N(\mu_g,1^2)$, independent and weak. The prior means follow §1.1 of the report. With about 10⁵–10⁶ checklists, the data dominate. Spruce–fir regeneration can rank top if the data say so (E's scenario).

**Structural log-density.** $K_h$ is a Gaussian kernel at home-range bandwidths:

$$\eta^{\text{str}}(s,T)=\beta_0+\tau_{r}(T)+\beta_1\log(\epsilon+K_{h_1}*q)+\beta_2 g_2(K_{h_2}*\text{hwmature})+\beta_3 g_3(K_{h_1}*\text{conif})+\beta_4K_{h_3}*\text{dev}+\beta_5K_{h_1}*\text{open}+\beta_6\text{snow}+\beta_7\text{elev}+\beta_8\text{IJI}_{h_2}$$

That is about 35 parameters. $g_3$ is unimodal ("some conifer is good"); $g_2$ is concave and increasing. IJI is the Shannon index of the three age classes.

**Trust-region residual.**

$$\log D(s,T)=\eta^{\text{str}}(s,T)+\pi(s,T)\cdot r(x_s),\qquad \pi(s,T)=\frac{n_{\text{eff}}(s)}{n_{\text{eff}}(s)+n_0}$$

- $r$ is a LightGBM on the legacy block, the clock shares and the structural features (plus AlphaEarth if admitted). It is trained with $\eta^{\text{str}}$ as `init_score`.
- $n_{\text{eff}}(s)$ is the **support**: the kernel-weighted number of training checklists whose footprint covariates lie near $s$'s covariates. It is computed as a k-NN density ratio in a 10-d PCA of the residual's features, against all forest.
- $n_0$ is chosen on the held-out *extrapolation subset* of HH (§5).
- **Where it matters.** In well-birded covariate space ($\pi\to1$), CYM-H equals a boosted model with a structural init. In covariate space no birder visits ($\pi\to0$), it equals the structure.
- **Fitting.** Train with $\pi\equiv1$, apply $\pi$ at prediction, and tune $n_0$ on the extrapolation subset.

**Fitting procedure.** Alternate:
1. L-BFGS on the structural parameters, with $r$ fixed (PyTorch, CPU or GPU, minutes);
2. LightGBM on $r$, with $\eta^{\text{str}}+g$ as `init_score`;
3. a GAM refit of $g$.

Use 3–5 rounds. The ensemble is 5 spatial folds × 2 seeds. The structural posterior uses a Laplace approximation.

### 3.4 Observation models

**O1. eBird complete checklists (main fit).**
- *Data:* EBD + SED for ME/NH/VT plus 10 km border strips, 2016–2025. Johnston et al. 2021 filters (complete; stationary/traveling; 5–300 min; ≤ 5 km; ≤ 10 observers; one per group). Spatio-temporal cap k = 10 per 3 km cell × week × outcome, with the uncapped fit as a sensitivity run.
- *Footprint* (C's fix: a **mean**, not a sum): $K_i$ is normalised, $\sum_s K_i(s)=1$. It is a Gaussian of $\sigma_i=\sqrt{\rho_{\varsigma(i)}^2+(0.35\,\text{dist}_i)^2}$ truncated at 3σ, evaluated on a 13-point stencil. $\rho_\varsigma$ is a **season-specific detection radius** chosen from {60, 150, 300, 600} m by held-out deviance (C).
- *Likelihood:*

$$P(y_i=1)=1-\exp\Big(-\exp\big[g(e_i)+\Delta_{\text{fall}}\mathbb 1_{\text{fall}}+\log\textstyle\sum_s K_i(s)D(s,T_i)\big]\Big)$$

- *Effort term $g$:* event-only covariates.
  - $\log$ duration (slope ≥ 0);
  - $\log(1+\text{dist})$ (**free sign**, C's fix);
  - protocol and party size;
  - start-time and day-of-year splines;
  - year;
  - out-of-fold skill (Kelling et al. 2015);
  - observer random effect for observers with ≥ 20 checklists.

  **No location-derived variable** (B's rule, which all designs now share). The checklist's own species count is excluded.
- *Fall head $\Delta_{\text{fall}}$:* a depth-≤3, L2-shrunk LightGBM on Sep–Dec checklists (B, D).

**O2. NH regional flush rates (scale and year level only).**

$$\Phi_{gT}\sim\text{NegBin}\big(H_{gT}\,2Wv\,\overline{D}^{\text{acc}}_{g,T},\phi\big)$$

- $\overline D^{\text{acc}}$ is the mean over accessible forest only (within 400 m of drivable or gated roads, or in PAD-US open-access land). It does **not** use the model's own $q$ (B's circularity point).
- Gradients are stopped into all shape parameters.

**O3. GPS hunt logs (the estimand).**
- *Protocol:* the GPX track at 1 Hz, a waypoint per flush (seen or heard), plus dog, weather and the covert ID from the recommender.
- *Model:*

$$\text{flushes}_j\sim\text{NegBin}\Big(\textstyle\sum_s 2W_0e^{\omega\,u(s)}\ell_{js}D(s,T)e^{\delta_1\text{dense}(s)+\xi\,\text{press}(s,t_j)},\phi_3\Big)$$

- **Transfer term.** $\omega$ and $\delta_1$ are the birder-to-hunter correction for habitat-dependent detectability. Only hunt logs identify it. In 2026 the logs are held out as a test; from 2027 they train these 3–4 parameters.

**O4. Acoustic.** The GMNF release has no coordinates (verified by C and D), so it is requested from the USGS VT Cooperative Unit as a bonus. If it arrives, the metric is drums per recorder-day (no occupancy saturation).

### 3.5 End product: Covert Finder

1. **Covert objects** (D): disturbance patches aged 4–25 yr; SLIC segments on (age, `under`, guild); and a 25 ha hexagon background. Size 2–40 ha.
2. **Covert card:**
   - $\hat F$ with an 80% interval;
   - **support badge** ($\pi$: "data-driven" vs "ecology-driven"), which is unique to CYM-H;
   - additive "why" breakdown (structural terms exactly, plus residual SHAP);
   - peak window and a 3-year trajectory. Ageing the clock is coherent here because the structural inputs are all clock-derived; the residual's static inputs are flagged;
   - access class A1–A4/X and walk-in distance (D);
   - badges for fresh cut, spring/fall disagreement (B), and near a hotspot (B).
3. **Daily list** (D): 4 by Thompson sampling plus 1 uniformly random from the accessible top 30%. Outputs: GPX/KML, a 60–120 min loop from parking, and the rule-out layer (E).
4. **Season ledger:** a gamma–Poisson covert update after each hunt (D); the refit and transfer-term fit after the season.

---

## 4. Why it beats the status quo and the other four designs

**Against the status quo.** CYM-H shares the core's answers to the report: new labels with real non-detections, effort modelled and dropped, footprints, the clock, and an absolute estimand. The report's diagnosis, "the data is the ceiling", is answered with new information in both the labels and the covariates.

**Against the other four (unshared points only).**

| Axis | B (CEM-X) | C (FLUSH-C) | D (COVERT-X) | E (FLUSH-E) | **CYM-H** |
|---|---|---|---|---|---|
| Behaviour off the birders' map | GBM boundary extrapolation + extrapolation flag | Same + embedding | Same | Same + importance-weighted *evaluation* | **Prediction itself switches to the structure as support vanishes; tuned on an extrapolation subset; tested by the T2 cross** |
| Age response | Learned between sites | Tested within sites (X2) | Learned between sites | Learned between sites | **Estimated within sites (C's panel) and imposed as structure** |
| Map before any fit | — | — | H250 | — | **Full prior map (v0) this week** |
| Scale | Scalar κ | Scalar | Scalar κ | Scalar | Physics priors on $W$ and $v$ + NH rates + a cover-dependent $W(s)$ |
| Interpretability | SHAP | SHAP | SHAP | — | Exact additive terms with ecological meaning, plus ecological unit tests |

The bet is narrow and testable. **Where checklists exist, CYM-H should tie the best flexible model. Where they do not, it should beat it.** Those unvisited places are disproportionately where hunters find grouse.

---

## 5. Expected gains, and how not to fool ourselves

### 5.1 Arenas

- **HH** (C): EBD checklists whose start point lies in a validation block of the current 3 km split (`regions.py`: `VAL_FRACTION = 0.2`, `SPLIT_SEED = 42`; verified).
  - Training excludes checklists within 5.5 km of an HH block, the maximum 3σ footprint.
  - The CNN is read **at the checklist start point only**, inside its validation block, because its positives are GBIF eBird records (`sightings.py:20`, verified).
- **HH-X, the extrapolation subset:** HH checklists whose footprint covariates have support $\pi<0.3$ under a support model fitted on the training checklists only.
- **HH-fall:** HH checklists from Sep–Dec.
- **Internal model selection:** 25 km blocks outside HH.

### 5.2 Metrics

- **TkL₅** (D): observed ÷ effort-only-expected detections in the top 5% of HH forest.
- **Effort-stratified AUC.**
- **Case-crossover concordance CC** (D), with a first-visit version (E/D).
- **Oracle ratio** (B).
- **Label-permutation null band** (D).

### 5.3 Comparators in every table

- effort-only;
- CNN (start point);
- H250 (zero-parameter);
- prior-mean CYM (zero-fit);
- **GBM twin** (the shared-core model: LightGBM cloglog with the same footprints, clock, legacy features and $g$);
- CYM-H with $\pi\equiv1$;
- CYM-H with support-weighting.

### 5.4 Expectations

| Metric | Expected | Confidence |
|---|---|---|
| Legacy TG AUC | 0.72–0.78; not optimised | high |
| HH effort-stratified AUC: GBM twin vs CNN | +0.02 to +0.06 (shared-core claim) | low–medium |
| HH (full): CYM-H vs GBM twin | −0.005 to +0.01; **a tie is the expected outcome** | medium |
| **HH-X: CYM-H vs GBM twin** | **+0.02 to +0.05 AUC; TkL₅ +0.2 to +0.5×** | **low; this is the bet. Power depends on the HH-X size, which is measured in week 1** |
| HH-fall TkL₅ | 1.6–2.4×, with the CNN at 1.3–1.7× | low |
| Prior-mean CYM vs CNN on HH | −0.01 to +0.04 | low |
| Within-site age peak (T5) | 5–15 yr for hardwood | medium; **power unknown** |
| S0 scorecard Spearman (n ≈ 30) | CNN 0.1–0.4; prior CYM 0.3–0.6 | very low; only a difference ≥ 0.35 is visible |
| 2026 randomised fifth covert: top-4 vs random | ≥ 1.4× point estimate | very low; about 40 visits detect only ≥ 2× |

### 5.5 Guards

- All thresholds, arenas and the prior-map file hash are committed before any fit (CR-0011 A3).
- Paired block bootstrap over 3 km blocks.
- The minimum detectable effect comes from the T2 simulation, and differences below it are ties.
- S0 is frozen before the owner sees any map.
- The scorecard has a known bias: the owner rates coverts partly by visible young cover, which favours structure-based maps (CYM, H250). It is therefore never decisive alone.

---

## 6. Risks, failure modes and falsification, in run order

| Test | When | What | Kill / decision |
|---|---|---|---|
| **S0** | Day 0 | Owner's scorecard (D): at least 30 past coverts rated 1–5 for flushes, frozen | Scorer only |
| **T0** | Days 1–3 | Build and freeze the prior-mean map and coverts (v0 product, live for the season). Freshness audit (D) | No kill |
| **G0** | Days 2–5 | B's cross-play label test (shared core) | If it fails, all checklist designs stop. Ship v0 plus the access and freshness layers |
| **T1** | Days 3–6 | On HH: prior-mean CYM vs H250 vs CNN vs the GBM twin, all with the identical $g$ | **CYM structural premise fails** if the prior-mean CYM beats neither the CNN nor H250 by ≥ 1 SE. **Precision premise:** if the GBM twin beats prior CYM by > 0.03 AUC on HH, the structure is wrong somewhere; inspect the per-term ablation before continuing |
| **T2** | Days 3–6 | **2 × 2 injection–recovery** (D's fix): truths {CYM-shaped, GBM-shaped (a random tree ensemble on legacy features)} × models {CYM-H, GBM twin}. Real EBD geometry; preferential visiting (low in dense young cover, as measured by T4). Score Spearman on **unvisited** cells | **Trust-region claim fails** if, on the GBM-shaped truth, CYM-H is worse than the GBM twin on unvisited cells by more than the GBM twin is worse than CYM-H on the CYM-shaped truth. The structure would then cost more when wrong than it gains when right |
| **T4** | Days 3–6 | Coverage audit: visited/available density ratio by age × understory × road distance. Defines HH-X | Sizes HH-X. If HH-X has fewer than 200 detections, the bet is untestable on checklists, and the field becomes decisive |
| **T5** | Week 2 | **Within-site age curve** (C's panel). Locations with ≥ 8 complete checklists before and after a cut covering ≥ 10% of the 300 m disc. Location and year fixed effects, $g$ as offset. Fit $t_p$ and $\sigma$ | If the within-site peak is outside 3–20 yr with the CI excluding the prior, the prior is wrong: use the within-site estimate. If underpowered, use the between-site fit and flag it |
| **T6** | Week 2 | Fit CYM-H. HH and HH-X head-to-head; case-crossover and first-visit; permutation null; tune $n_0$ | **Ship rule:** CYM-H ships only if it ties or beats the GBM twin on HH (within 1 SE) **and** beats it on HH-X. Otherwise ship the GBM twin, with CYM's structure kept only for the product's "why" and trajectory |
| **Switch** | Pre-registered: 19 Oct 2026 | The recommender moves from v0 to the T6 winner | — |
| **T7** | Season | Randomised fifth covert; flushes per GPS-km; NegBin GLMM with a day effect | Product truth; accumulates across seasons |

**Risks:**

| Risk | Mitigation |
|---|---|
| The support model is badly calibrated, so $\pi$ shrinks the wrong places | $n_0$ is tuned on HH-X; T2 checks it on known truths; the support badge shows it to the user |
| HH-X too small to test the bet | Stated in advance (T4); then field logs and S0 decide |
| Partial harvests missed | `sev`, LCMS slow loss, the additive understory term, lidar |
| Spring audibility dominates | Season radius, fall head, HH-fall reporting, transfer term |
| Preferential sampling at the site level | The age curve comes from T5 (location fixed effects); case-crossover with first-visit |
| Registration bugs in the new exports | Template `crsTransform`; existing probes as acceptance gates |
| eBird terms | Personal use; derived maps only |

---

## 7. Implementation plan (one owner, one EC2 GPU)

Each row is one CR (CR-0011 A5). Acceptance scripts land first (A3). New modules:
- `habitat_cube.py`
- `cym_core.py`
- `ebird_checklists.py`
- `support.py`
- `sim_cross.py`
- `panel_age.py`
- `cym_h_fit.py`
- `eval_hh.py`
- `covert_finder.py`
- `hunt_log.py`

| When | Work | Compute |
|---|---|---|
| **Day 0** | Owner fills in scorecard S0. Commit the acceptance script (HH, HH-X rule, metrics, thresholds). Start the EBD + SED download. Emails: USGS VT Coop (GMNF sites), NH F&G (regional tables), ME IF&W and VT FWD | — |
| **Days 1–3** | `habitat_cube.py` for 2026 (EE exports on the template grid, then 60 m pre-convolutions on the GPU). `cym_core.py` writes the prior-mean map and v0 coverts with access (PAD-US). Freshness audit. **The owner starts hunting the v0 list with the randomised fifth covert** | EE + GPU, hours |
| Days 1–3 (parallel) | `ebird_checklists.py`: polars streaming, filters, zero-fill, stencils, HH and buffer flags, counts by season | CPU |
| Days 3–6 | G0, T1, T2, T4 | CPU |
| Week 2 | `habitat_cube.py` for 2016–2025 at stencil points; `panel_age.py` (T5); `cym_h_fit.py` (T6) | CPU + GPU, hours |
| 19 Oct | Switch the recommender to the T6 winner | — |
| Weeks 3–5 | Lidar `under` (PDAL per region); AlphaEarth admission via the permutation gate; loop planner | CPU |
| Season end | Analyse T7; fit the transfer term; publish the 2027 coverts | — |

**First experiment today:** S0 plus T0. The owner hunts tomorrow with a v0 covert list that includes a randomised slot, and the EBD ingest runs in parallel so G0–T2 complete within the week.

---

## 8. References

All were checked in rounds 1–3 unless marked **unverified**.

1. Pasquarella & Thompson (2023). HF437, Maine harvest maps 1986–2019. https://doi.org/10.6073/pasta/20a838c4bd6922685b3d00661d45c414
2. LCMS v2024-10 (GEE). https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10
3. Hansen GFC v1.12 (GEE). https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12
4. OPERA DIST-ANN-HLS (GEE). https://developers.google.com/earth-engine/datasets/catalog/OPERA_DIST_L3_DIST-ANN-HLS_V1 (verified by D)
5. eBird EBD/SED. https://ebird.org/data/download . GBIF eBird dataset fields were checked by me via the API: no `eventID`, time or effort fields. https://api.gbif.org/v1/occurrence/search?datasetKey=4fa7b334-ce0d-4e88-aaae-2e0c138d049e
6. Johnston et al. (2021). *Diversity and Distributions* 27:1265–1277. doi:10.1111/ddi.13271
7. Kelling et al. (2015). *PLoS ONE* 10:e0139600. doi:10.1371/journal.pone.0139600
8. Royle & Nichols (2003). *Ecology* 84:777–790 (**DOI not re-checked**)
9. Lapp et al. (2023). *Wildlife Society Bulletin* 47(1). doi:10.1002/wsb.1395
10. Clarfeld et al. (2025). USGS data release doi:10.5066/P13EFLXX (no site coordinates in public CSVs, per C and D)
11. Google Satellite Embedding V1. https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL
12. NH Fish & Game (2025). Season and surveys. https://nhfishgame.com/2025/09/22/ruffed-grouse-and-woodcock-seasons-start-october-1/ (flush-rate figures **unverified**)
13. State lidar: VT https://vcgi.vermont.gov/document/2023-vermont-lidar-plan ; NH https://des.nh.gov/news-and-media/milestone-statewide-high-resolution-elevation-data-has-been-reached ; ME https://pubs.usgs.gov/publication/fs20233036/full
14. PAD-US. https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download
15. Angrist & Pischke (2009). *Mostly Harmless Econometrics* (fixed effects/DiD; via C, **unverified**)
16. Maclure (1991). The case-crossover design. *Am. J. Epidemiol.* 133:144–153 (**from memory, unverified**; via D's idea)
17. Repository (verified): `sightings.py:20` (`EBIRD_DATASET_KEY`); `regions.py:55,58` (`VAL_FRACTION`, `SPLIT_SEED`); `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md:22` (harvest +0.001); `docs/grouse_model_report.md` §1–§5; `diagnose_gbm_baseline.py`; `diagnose_disturbance_features.py`.

---

## 9. Responses to critiques

| Critic | Critique | Severity | Accept / rebut | Evidence or fix |
|---|---|---|---|---|
| C | The footprint is a **sum** over a disc growing with distance, while the distance slope is constrained ≥ 0. Expected count ∝ area, so long walks force lower $D$ in big woods | MAJOR | **Accept.** Verified: round-2 O1 had $\sum_{s\in B_i}D\,A_{\text{cell}}$ with $\alpha_2^+$ | The footprint is now a normalised kernel **mean**, the distance slope has a free sign (§3.4 O1), and the radius is season-specific (C) |
| C | The "blinded" field test cannot blind the hunter; 40 h/arm is hard; it detects only ≥ 1.5× | MEDIUM | **Accept** | Blinding claim dropped. D's randomised fifth covert, fixed-effort GPS protocol, endpoint flushes per GPS-km. Power stated: about 40 visits detect only ≥ 2× (§5.4). The field is product truth that accumulates, not the week-1 verdict |
| C | ARU validation unusable as published | MEDIUM | **Accept.** Verified by C and D (no site ID or coordinates); the USGS page lists none | Demoted to "on request, bonus"; drum-rate metric if obtained |
| B | Precision is capped by a 30–40-parameter structure; stand age showed +0.001; partial-harvest shelterwood reads "mature"; the kill test lacked a flexible comparator | MAJOR | **Accept in part, and the architecture changes.** Rebut one premise: +0.001 was measured under TG labels (CR-0032:22), the label all five designs call blind, so it is not evidence against stand age under checklist labels | The trust-region residual gives full GBM authority where data exist (§3.3). Cover is additive in understory under older canopy, so shelterwood with dense regeneration scores high. The GBM twin is in T1 and T6 with an explicit ship rule (§6) |
| B | Hunter effort $\propto(K*q)^\eta$ is circular | MEDIUM | **Accept** | Hunter-effort weights are now accessible forest only, independent of $q$ (§3.4 O2) |
| D | T2 compared recovery of two **different** truths, so it cannot fail for the reason stated | MAJOR | **Accept.** Correct: round-2 T2 compared GBM-on-(ii) with CYM-on-(i) | Full 2 × 2 cross, scored on unvisited cells, with a symmetric failure rule (§6 T2) |
| D | T1 on 25 km blocks scores the CNN on its own training positives (GBIF eBird = EBD detections) | MAJOR | **Accept.** Verified `sightings.py:20` | T1 and all comparisons run on HH. The CNN is read at the start point inside its validation block, and training has a 5.5 km buffer (§5.1) |
| D | Precision cap (as B) | MEDIUM | Accept; same fix as B | §3.3 |
| E | Ordered guild priors and a rigid age hump cannot learn exceptions (spruce–fir regeneration, alder, old fields), and the residual is too shrunk to recover them | MAJOR | **Accept** | Guild priors are independent and weak (N(μ, 1²)), so they are data-dominated. Alder/shrub-wetland and old-field guilds are added. A separate softwood age curve is added. The residual has full authority wherever checklists support it (§3.3) |
| E | A field test of an *unfitted* prior cannot tell "bad prior" from "bad idea" | (MAJOR, bundled) | **Accept** | The prior map is v0 product only. The verdict on CYM comes from T1, T2 and T6 on HH, and the recommender switches to the T6 winner on 19 Oct |
| E | Hunters can see young cuts, so it is not blind | MEDIUM | **Accept** | As for C's critique; outcome is counted on GPS-km with fixed effort |

---

## 10. Final critique of competitors (round-2 versions)

| Design | Item | Severity | New / still open | Evidence and failure scenario |
|---|---|---|---|---|
| **All four** | **Off-support extrapolation is not handled in prediction.** Every model is a tree ensemble (or MLP) fitted where birders walk and applied to all forest. Trees hold the boundary leaf value constant. E's importance weighting changes only *evaluation*; B, C and D only *flag* extrapolation. In northern Maine industrial young regeneration, rarely birded, the map shows whatever the nearest birded covariate cell learned. That cell is often roadside or trail young growth, with different detection and pressure. | MAJOR | Still open (raised in round 2 as R-a; none adopted a prediction-time remedy) | B §3.3 and C §3.5 "extrapolation flag"; E §3.5. CYM-H's T2 cross measures exactly this cost for every design |
| **B** | **The negative-control gate cannot fail.** Chickadee and jay maps are nearly flat, so ρ ≤ 0.3 passes whatever the contamination. | MAJOR | Still open (raised by C and D; B round 2 unchanged) | B §3.5 R-EL. D's label-permutation null fixes it |
| B | **The cross-play symmetry assumption is checked only on synthetic species** whose detection process B itself specifies. | MEDIUM | New | B §5.1. If real home advantage differs because TG labels share CNN-era hotspots, the label-effect estimate is biased in an unknown direction |
| B | The fix to my round-2 fold critique is accepted: HH plus 25 km selection blocks replace the 3 km CV. However, B's 2 km training exclusion around HH is smaller than its own 3σ footprints for 5 km walks (about 5 km), so training and HH share footprint cells. | LOW | New | B §3.4 |
| **C** | Fixed: the trajectory incoherence I raised, via the fresh-cut override, embedding transport and a back-test. | — | Resolved | C §3.4 |
| C | **The X2 panel model check uses a model whose training set contains the treated locations.** $\Delta\hat\eta_\ell$ is then partly fitted to those sites' own pre/post detections, which inflates the slope. | MEDIUM | New | C §6 X2 step 3. Fix: out-of-fold $\hat F$ with treated locations held out. CYM-H's T5 avoids this, because the age curve is estimated *only* within-site and then imposed |
| C | **X2 power is unknown and probably low.** Hotspots sit in preserves and parks, where harvest is rare, and each treated site needs ≥ 8 checklists both before and after. | MEDIUM | New | C §5.2 itself says "power uncertain". Scenario: a few dozen treated sites at 1–4% detection rates give a CI spanning both hump and flat |
| C | The embedding remains the most likely place for unmapped skid trails and log landings to leak. They are not in OSM, so the 30 m mask misses them. Ironically, grouse use them (brood habitat), so the leakage is partly real signal. | LOW | New | C §3.3; report §1.4 |
| **D** | Fixed: location-derived effort covariates and the adversary are removed. | — | Resolved | D §0.2 |
| D | **The flush-mode subset is not a fall-flush sample.** Breeding/behaviour codes are used mainly in the breeding season, and "visual" codes (FL, DD, NY, CF) are brood and nest observations from June–July. Comment keywords such as "on road" capture gravelling birds. $D_{\text{vis}}$ will therefore learn summer brood roads and road edges, not October cover. Ranking by $F+D_{\text{vis}}$ when modes diverge could promote road-edge coverts. | MEDIUM | New | D §3.6 (D notes the gravel artefact but still ranks by $D_{\text{vis}}$). Fix: restrict $D_{\text{vis}}$ to Sep–Dec detections, or use it as a badge only |
| D | **The scorecard S0 is not independent of structure-based maps.** The owner chose and rates coverts by visible young cover, which is what H250 and CYM encode. It also has range restriction, because it holds only coverts worth hunting. | MEDIUM | New (this applies to my use of S0 too, and I state it in §5.5) | D §3.7 |
| D | Same-day case-crossover pairs are scarce: an observer-day needs ≥ 2 checklists ≥ 1 km apart with exactly one detection. D's prior CC of 0.56–0.63 may come with a CI too wide to gate on. | LOW | New | D §5. Report the pair count in week 1 before using it as the primary gate |
| **E** | Fixed: the species-count proxy, naive-occupancy saturation and the feature cube. | — | Resolved | E §0.1 |
| E | **Season-contrast identification assumes the same λ in spring and fall at a footprint.** Fall density is about 2× spring after reproduction, and spatially uneven (brood success). Fall shuffle disperses juveniles into different cover. The spring openness term then absorbs real seasonal *use* differences along the openness axis as "detectability". That is biased toward whichever season dominates, which is spring at 61%. | MEDIUM | New | E §3.4 "λ is shared"; report §1.4 (autumn diet, dispersal) |
| E | **The fall-only kill gate is probably underpowered and may kill a working programme.** About 15% of detections are in fall, and HH holds a minority of checklists. That may leave of the order of 10² detections in the top 5% (estimate), so the SE of TkL₅ is about 0.1–0.15, against a gate of ≥ 0.2. | MEDIUM | New | E §6 T1. Fix: compute the MDE first (B's oracle or injection) and gate on all seasons, with fall as a must-not-disagree check |
