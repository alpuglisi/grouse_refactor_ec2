# Design C, final (round 3): FLUSH-C

**FLUSH-C ranks coverts by effort-standardised fall encounter rate, learned from complete checklists. A within-site disturbance panel test checks it, and a gated, infrastructure-blind embedding block can add to it.**

*Designer C. Primary technique: morphological analysis (Zwicky box). Added in round 2: red-team review, an unshared-dimension Zwicky box and an econometric (difference-in-differences) analogy. Added in round 3: an **assumption ledger**, which lists every identifying assumption next to the test that checks it, and a steelman audit of every critique aimed at me. No repository file was edited.*

---

## 0. Changes from round 2

### 0.1 New facts verified this round

**AlphaEarth Foundations used GBIF occurrences in pretraining (E's critique; verified).** I read the AEF paper (arXiv:2507.22291, supplement S15.10–S15.12 and Table S1):
- GBIF species occurrence records were used as **text-contrastive training targets**.
- The selection was Plantae, Animalia and Fungi, 2017–2023, licensed CC-BY 4.0 or CC0. Records had to be human or machine observations with "a maximum spatial uncertainty of 240 meters". Sampling was capped at "a maximum of 1000 observations per unique family, genus, species observation tags".
- Table S1 says: "All data sources were used as targets, only input data sources are required at inference-time".

So the published embeddings are computed from imagery, radar, climate and so on. GBIF rows are not inputs at inference. But the encoder *was trained* to align imagery with the text of species reported nearby, so leakage of reporting geography into the embedding is possible. I accept this as MAJOR, and the fixes are in §3.6 (gate G-AEF) and §9.

**Competitor fixes since my round-2 critique:**
- E now uses the HH set, which fixes the in-sample CNN baseline I raised. That item is closed.
- D dropped its location-derived effort covariates and its adversary. Closed.
- A still has a footprint *sum* with a non-negative distance slope (A §3.4 O1, unchanged). Still open.

### 0.2 Adopted this round, with credit

| Adopted | From | Use in FLUSH-C |
|---|---|---|
| **Same-observer, same-day case-crossover concordance (CC)**, plus a first-visit restriction | D | A primary preferential-sampling metric next to my panel test (§3.6 PS). It cancels skill, date, weather and year level exactly |
| **Within-stratum label-permutation null** | D | Replaces B's chickadee/jay correlation as the effort-geography null. I add the blind spot D's version has (§10) and close it with infrastructure masking and the probe |
| **Owner's blinded covert scorecard (S0)** | D | The only hunter-truth scorer that exists today. It is frozen before any map is shown |
| **Detection-mode decomposition**: aural vs visual detections from EBD breeding/behaviour codes and species comments | D | One of three detectability variants. The injection test chooses among them (§3.6 DT) |
| **Season-contrast openness term** | E | The second detectability variant, judged by the same injection test |
| **Detectability injection–recovery** | E (re-aim of B's method) | Chooses among the three detectability variants on real EBD geometry |
| **Coverage audit** (visited vs available density by age × understory × road distance) | A | Builds the extrapolation subset of HH and the per-covert flag |
| **Ship a zero-fit map this week** | A, D | v0 is a covert layer from the zero-parameter heuristic H₀. v1 is the fitted model, about 20 Oct |

### 0.3 Strengthened (my own)

- **The panel test (X2) is now a proper event study:**
  - leads as a pre-trend placebo;
  - stacked never-/not-yet-treated controls, to avoid the known bias of two-way fixed effects under staggered timing;
  - region × year effects;
  - the model whose predictions are checked is refitted **without** the panel sites and a 2.5 km buffer, so the check is out-of-sample.
- **Gate G-AEF:**
  - decided on **2024–2025 checklists only**, after AEF's GBIF pretraining window (E's fix);
  - plus a record-proximity sensitivity run: the embedding gain must not be concentrated within 1 km of 2017–2023 GBIF grouse records.
- **Time-split evaluation.** All headline metrics are also reported on 2024–25 checklists, trained on ≤ 2023.

### 0.4 Dropped

- B's raw-correlation negative-control gate. It is replaced by D's permutation null; the control species stay as a descriptive positive check only.
- Two round-2 claims, now superseded:
  - "AlphaEarth adds only satellite information": wrong (see 0.1);
  - the ARU network: corrected to "exists, but the public release has no coordinates".

---

## 1. Title and pitch

**FLUSH-C: a covert map of expected grouse encounters per standard fall hour on foot.** It is trained on eBird complete checklists. Its ranking must pass a test that a birder-geography map cannot pass: what happens at the *same* birding locations after the forest around them is cut.

All five designs share the core:
- complete checklists with non-detections;
- a separable effort term built only from event covariates and dropped at prediction;
- footprints;
- coverts;
- observed/expected top-k lift.

FLUSH-C differs in four ways.

1. **Within-site causal-style validation (X2).** Some eBird locations are birded repeatedly before and after a harvest within 300 m. Comparing each location with itself (location fixed effects, in an event-study design) cancels three things:
   - why the birder chose the site;
   - the site's fixed detectability;
   - its access.

   The out-of-sample model must predict the within-site change in encounters as the stand ages. A map that learned "where grouse-finding birders go" cannot pass. X2 is also a direct check of the product's "rising covert" claim.
2. **Information the other designs lack, but only through a gate.** Annual 10 m AlphaEarth embeddings are averaged *with all mapped roads, tracks, paths, parking and buildings masked out*. They are aged forward coherently (fresh-cut override and transport, back-tested). They are admitted only if they win on post-2023 checklists, survive the permutation null, the infrastructure probe and the off-trail weighting, and show no gain concentrated near past GBIF grouse records.
3. **Detectability chosen by experiment.** Spring drumming is heard from far away; fall flushes are close. Three detectability models compete in an injection–recovery test on the real EBD geometry, and the winner ranks the coverts:
   - season-specific footprint radius (mine);
   - aural/visual mode decomposition (D);
   - season-contrast openness term (E).
4. **The leanest buildable pipeline.** One row per checklist with footprint-matched, precomputed multi-radius features, and a LightGBM cloglog objective with an effort offset. A GPU does the disc filtering. The decisive test is ready on day 5. A zero-fit v0 ships this week, and the fitted v1 ships by about 20 October, in time for the rest of the 2026 season.

---

## 2. Brainstorming record (short)

**Round 1, Zwicky box.**
- Ten dimensions: label, estimand, negatives, modalities, scale, model, loss, spatio-temporal structure, evaluation, product. Each had 5–7 options.
- Eleven pruning rules, for example presence-only × occupancy, and hunter aggregates as a 30 m label.
- Twelve configurations were scored. The winner (checklist labels, encounter-rate estimand, cloglog with an effort offset, coverts) became the shared core.

**Round 2.**
- **Red team:** verified that A's sum footprint mis-scales, and that the ARU release has no coordinates.
- **"Unshared dimensions" box:** the empty cells were the within-site test, the infrastructure-blind embedding, and season-specific support.
- **Econometric analogy:** a harvest is a treatment and a hotspot is a panel unit, which gives the panel test.

**Round 3, assumption ledger (new).** Every number FLUSH-C will report rests on an identifying assumption. Each assumption is paired with a test, and a failed test changes a specific decision.

| # | Assumption | Test | If it fails |
|---|---|---|---|
| L1 | Given event effort, where a birder goes is unrelated to grouse beyond the habitat features (no preferential sampling) | X2 panel (site FE); case-crossover first-visit (D); drop-targeters (B) | Badge "PS-fragile"; product ranks by the panel-validated clock component |
| L2 | Effort is captured by event covariates | Permutation null (D); within-observer AUC (B) | Coverts badged "effort-sensitive" |
| L3 | Detectability does not vary with habitat in a way that differs between birders and hunters | Detectability injection; mode divergence (D); fall-only agreement | Rank by the injection-chosen variant, or fall-only |
| L4 | The embedding carries habitat, not infrastructure or reporting history | Mask + probe; off-trail weighting; post-2023 evaluation; record-proximity check | Embedding block dropped |
| L5 | Forecast inputs are coherent | Transport back-test 2019 → 2024 | Clock-only trajectories |
| L6 | The comparison with today's map is fair | HH set + cross-play (B) | Report as non-comparable |
| L7 | Birder encounter rank ≈ hunter flush rank | Owner scorecard S0; randomised fifth covert; hunt-log $W(s)$ | Hunter multiplier; badge |

---

## 3. The design

### 3.1 Data

| Role | Dataset | Status |
|---|---|---|
| Labels + effort | eBird EBD + SED, ME/NH/VT + 10 km border strips, 2010–2025 (2016+ for fitting; 2010+ for the panel) | **Owner has access** |
| Detection mode | EBD `BREEDING CODE` / `BEHAVIOR CODE`; species comments (column name to confirm against the owner's header) | Code columns verified by D via `auk`. **Comments column unverified** |
| Succession clock | LCMS v2024-10 (Tree Removal, slow loss); Hansen GFC v1.12 `lossyear`; HF437 Maine harvest maps 1986–2019 (A); OPERA DIST-ANN 2023–24 / DIST-ALERT 2025–26 (D); LANDFIRE annual disturbance | Catalogs verified by A, C and D |
| Gated embedding | AlphaEarth Satellite Embedding V1, 10 m, 64-d. EE `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`; COGs on GCS (requester pays) or Source Cooperative (free) via `aef-loader` | Catalog page says 2017–2024. aef-loader docs say 2017–2025; **2025 unverified** |
| Infrastructure mask | OSM `highway=*` (all classes, including track/path/footway), `amenity=parking`, buildings; TIGER 2023 (in the repo); NLCD developed | OSM standard; Microsoft building footprints URL **unverified** |
| Legacy features | 15 layers + `mch_*`, after the CR-0035 registration repair | On EC2 |
| Context | 3DEP 10 m elevation; Daymet V4 winter SWE | **Daymet asset ID unverified** |
| Access | PAD-US 4.x, state lands, NH Current Use (D) | Public |
| Independent scorers | S0 owner scorecard (now); S1 NH regional rates (PDF, 403 to automated fetch, so **contents unverified**); S2 randomised hunts (season); S3 GMNF ARU sites (on request; public CSVs have **no coordinates**, verified) | — |

### 3.2 Estimand

$$\mu^{*}_{\text{fall}}(c,T)=e^{g(w^{*})}\cdot\frac1{|c|}\sum_{s\in c}\exp\big(F(x_{s,T})+\Delta_{\text{fall}}(x_{s,T})+D^{*}(x_{s,T})\big),\qquad p^{*}=1-e^{-\mu^{*}} .$$

- $w^{*}$ is the standard walk: one median-skill observer, traveling, 60 min, 2 km, 15 October, 08:00.
- $D^{*}$ is the detectability adjustment chosen by the DT module. It is zero unless that module admits one.
- $\mu^*$ is the expected grouse encounters per standard fall hour on foot. Ranking depends only on $F+\Delta_{\text{fall}}+D^{*}$, pooled over the covert.
- A flushes-per-hour scalar κ is fitted from hunt logs and checked against S1. It is displayed but never ranks.

### 3.3 Features (year-indexed, no future information)

Radii are $\mathcal R=\{60,150,300,600,1200,2400\}$ m.

1. **Clock.** The fused last-disturbance year is the median of the sources that fire within ±1 yr, with a source-agreement count kept. From it:
   - age-class shares {0–4, 5–10, 11–15, 16–25, 26–40, >40/never} at each radius;
   - Shannon diversity of age classes;
   - young/mature edge density at 300 m;
   - a slow-loss (partial cut) share.

   The point extraction reuses `diagnose_disturbance_features.py` logic. Prediction uses rasters exported on the template lattice with explicit `crsTransform` and the registration gates (`grid_mismatch`, `check_layer_registration.py`, the `diagnose_fetch_tile_offset.py` probe). This is the BUG-0094/0095/0096 lesson.
2. **Legacy.** The `diagnose_gbm_baseline.py` neighbourhood design + `mch_*`, up to 960 m.
3. **Gated embedding block:**
   - **masked disc mean:** $\bar a_r=\sum_{u\in B_r}m(u)a(u)/\sum m(u)$, with $m=0$ within 30 m of any mapped road, track, path, parking area or building, or on NLCD developed;
   - **PCA-16 before averaging.** This is exact, because averaging is linear;
   - heterogeneity $1-\lVert\bar a_r\rVert$;
   - year-on-year change.

   Storage is about 8 GB/yr at 60 m in float16.
4. **Context.** Elevation, winter SWE and growing degree days at 1 km.

### 3.4 Freshness and coherent forecasts

- **Fresh-cut override.** A pixel disturbed after the last embedding year $y_e$ takes $\mu_{k,T-y_d}$. That is the mean embedding of stratum $k$ (pre-cut guild × biophysical region) at age $T-y_d$, estimated over all forest pixels in 2017–2025.
- **Transport.** For forecasts $T>y_e$: $a_T=\operatorname{normalize}(a_{y_e}+\mu_{k,\alpha+T-y_e}-\mu_{k,\alpha})$.
- **Back-test (pre-registered).** Transport the 2019 embeddings to 2024 and compare with the real 2024 embeddings. Pass if top-500 covert Kendall τ ≥ 0.80. Otherwise trajectories come from the **clock-only** model.

### 3.5 Model

**Footprint matching.** There is one row per checklist. Checklist $j$ (distance $L_j$, season $\varsigma_j$) reads its features at the radius nearest to $\rho_{\varsigma}+L_j/2$.
- $\rho_\varsigma\in\{60,150,300,600\}$ m is selected per season by held-out deviance.
- Every feature is a disc **mean**, so footprint size never inflates the expected count.

**Likelihood.**

$$\eta_j=F(x_j)+\Delta_{\text{fall}}(x_j)\mathbb 1[\text{fall}]+D_{\varsigma/m}(x_j)+g(w_j),\qquad P(y_j=1)=1-\exp(-e^{\eta_j}).$$

- **$F$:** LightGBM with a custom cloglog objective. Gradient and Hessian are row-wise. $g$ enters as `init_score`, alternated with a GAM refit over 3–5 rounds.
- **$\Delta_{\text{fall}}$:** depth ≤ 3, strong L2, fitted on Sep–Dec with $F$ frozen.
- **$D_{\varsigma/m}$:** the detectability term of the variant the DT module selects (§3.6).
- **$g$ uses event covariates only:**
  - log duration and log(1+distance), monotone ≥ 0;
  - protocol and party size;
  - time-of-day spline and cyclic day-of-year spline;
  - year;
  - out-of-fold observer skill (Kelling et al. 2015);
  - observer random effect (≥ 20 checklists).

  No location-derived variable is allowed (the A/B rule).
- **Capping and ensemble:**
  - at most 10 checklists per 3 km cell × week × status, with the uncapped fit reported alongside;
  - 5 spatial folds (25 km blocks) × 2 seeds;
  - a PCA-20 Mahalanobis extrapolation flag, combined with A's coverage audit.

### 3.6 Robustness modules (acceptance code, committed before any fit; CR-0011 A3)

**PS: preferential sampling.**
1. **Panel test X2** (§6), the within-site test.
2. **Same-day case-crossover CC on HH** (D).
   - Pairs are same-observer, same-day checklists ≥ 1 km apart, exactly one with a detection.
   - CC is computed by conditional logit on the habitat score with $g$ frozen.
   - It is also reported **first-visit only** (both locations new to that observer) and hotspot-free.
3. **Within-observer AUC** (B).
4. **Drop-targeters** (B). Pass if covert Spearman ≥ 0.9.

**EL: effort leakage.**
1. **Within-stratum label-permutation null** (D). Labels are permuted within observer × month × duration tercile, and the pipeline is fitted 20 times on a 200k subsample. Any added feature block must raise real CC above the null 95th percentile and must not raise the null CC.
2. **Infrastructure probe.** This covers the case the permutation null cannot see (§10). A classifier predicting "within 100 m of a road or trail" from the masked embedding features must have AUC ≤ 0.70.
3. **Off-trail importance-weighted TkL** (E). Weights are $p_{\text{forest}}(x)/p_{\text{visited}}(x)$ from a domain classifier, clipped to [0.2, 5].
4. **Control species** (B, E) as a descriptive check only: Chestnut-sided Warbler and Eastern Towhee as positive controls, Ovenbird as a mature-forest contrast. Results are reported as forest-only partial correlations. They are not a gate.

**DT: habitat-dependent detectability.** Three variants:
- **(a)** season-specific radius $\rho_\varsigma$ (mine);
- **(b)** aural/visual mode decomposition (D);
- **(c)** season × openness contrast (E).

All three are run on the **detectability injection** (E's T2) on the real EBD geometry: a synthetic species whose spring audibility rises with openness while its density peaks in dense young cover. The variant that best recovers the fall-density ranking of unvisited forest cells becomes $D^{*}$. Ties go to the simplest variant, (a).

Guards:
- fall-only vs selected-variant covert Spearman must be ≥ 0.7, otherwise the fall-only model ships;
- the hunter multiplier $W(s)=W_0e^{\omega\,\text{under}(s)}$ is fitted from logs from season 2 (A).

**G-AEF, the gate for the embedding block.** All of the following must hold:
1. It improves fall TkL₅ and deviance on **2024–25** HH checklists, with block-bootstrap lower CI > 0. A model trained on ≤ 2023 must show the gain in 2024–25 (E's fix).
2. It passes EL1–EL3.
3. Its gain is not concentrated near prior reports. Split HH checklists by distance (< 1 km vs ≥ 1 km) to any 2017–2023 GBIF grouse record. The gain in the ≥ 1 km group must be at least 50% of the gain in the < 1 km group.
4. It passes the transport back-test, or else only current-season use is allowed.

### 3.7 End product

1. **v0 this week.** Covert polygons ranked by H₀ (zero-parameter: share of 250 m in 5–20-yr post-cut forest, from A), with access classes. No fitting, so it can be used for hunts now.
2. **v1, about 20 Oct.** The fitted model on a 60 m grid; coverts from three sources (D): 4–25-yr disturbance patches, SLIC segments and a 25 ha hex background, sized 2–40 ha. Each covert card shows:
   - $p^{*}$ and $\mu^*$ with an 80% interval;
   - peak window;
   - trajectory +1…+5 yr;
   - access class A1–A4/X and walk-in distance;
   - top-3 reasons (TreeSHAP);
   - badges: fresh cut, PS-fragile, effort-sensitive, audible-not-flushable, extrapolated, near hotspot.
3. **Daily list** (D): 4 coverts by Thompson sampling plus 1 random covert from the accessible top 30%. Output is GPX/KML with an optional greedy loop from parking (A).
4. **Ledger.**
   - Each hunt is logged as GPX + flush waypoints.
   - A gamma–Poisson covert update runs immediately.
   - $F$, $g$ and $W$ are refit after the season.
   - The random fifth covert gives an unbiased realised-lift estimate.
5. **Rule-out layer** (E) and **season outlook** from NH drumming where published.

---

## 4. Why it beats the status quo and the other four

| Report diagnosis | Status quo | FLUSH-C |
|---|---|---|
| "The data is the ceiling" (GBM ≈ CNN; clock +0.001, GEDI +0.000 under TG labels, CR-0032) | More capacity | Changes the labels first. New inputs are judged only under the new labels, on post-pretraining years |
| PU noise; $1-a/2$ bound | TG background | Observed non-detections with effort |
| Effort bias (`road_dist` learned birding, §5.3) | Partial cancellation | Event-only $g$, fixed at prediction; infrastructure masked; permutation null |
| Estimand (§5.1) | Density ratio at 50:50 | Absolute fall encounter rate per standard hour |
| Location error (§2.4.1) | Centre-pixel label | Season- and distance-matched footprint mean |
| Static map, ±2-yr rule (§2.4.2, §5.6 Q5) | Latest vintage | Annual clock to 2026; fresh-cut override; back-tested forecasts |
| No external check (§5.6) | None | Panel test, scorecard, randomised hunts |

**Against the other designs (unshared points only):**
- **A** relies on a mechanistic form and a mis-scaled footprint sum (§10). X2 tests the age response A assumes, without assuming it.
- **B** has strong between-site evaluation. FLUSH-C adds the within-site test, and its only new information source beyond the clock is gated.
- **D** has the strongest preferential-sampling metric (adopted). Its permutation gate cannot see infrastructure leakage (§10). FLUSH-C closes that gap with masking and the probe.
- **E** proposes one detectability variant. FLUSH-C makes that variant compete with two others in E's own injection test.

---

## 5. Expected gains, measured without fooling ourselves

### 5.1 Arenas and metrics

- **HH.** All checklists starting in a *validation* block of the existing 3 km split (`SPLIT_SEED=42`), with a 2.5 km training buffer. This is the only place where the CNN is not scored on its own positives (GBIF EOD = EBD detections, `sightings.py:20`).
- **Cross-play** (B). M_TG and M_CL use the same features. Each is scored at home and away; the CNN is a third row.
- **Time split.** Train ≤ 2023, test 2024–25.
- **Primary metric:** fall TkL₅ on HH (D).
- **Secondary metrics:**
  - same-day CC (D);
  - effort-stratified AUC;
  - within-observer AUC;
  - log-loss;
  - oracle ratio (B);
  - off-trail-weighted TkL (E).
- **Baselines in every table:** H₀, the CNN, M_TG, clock-only M_CL, and full M_CL with and without the embedding.
- **Statistics:** paired block bootstrap. Differences below the X0-calibrated minimum detectable effect (MDE) are ties.

### 5.2 Priors, with probability of success

| Claim | Expected | P(true) |
|---|---|---|
| Label thesis passes cross-play (≥ 0.02) | M_CL away deficit 0.02–0.06 smaller | 0.65 |
| Fall TkL₅ on HH: M_CL vs CNN | 1.9–2.6× vs 1.3–1.8× | 0.55 for a gap ≥ 0.3× |
| Same-day CC on HH | 0.56–0.62 vs CNN 0.53–0.57 | 0.55 |
| ≥ 50% of the CC gain survives first-visit restriction | — | 0.6 given a gain |
| Clock adds ≥ 0.1× TkL₅ under checklist labels | — | 0.45 |
| X2 passes (slope > 0, no pre-trend) | — | 0.5. **Power unknown** until treated sites are counted |
| G-AEF passes all four conditions | ΔTkL₅ +0.1 to +0.3× | **0.30**. Down from 0.40 after the pretraining finding |
| Detectability variants disagree (Spearman < 0.8) | — | 0.4 |
| Owner scorecard Spearman, v1 vs CNN | 0.3–0.6 vs 0.1–0.4 | Very low power (n ≈ 30, SE ≈ 0.18) |
| Full-model AUC with effort | 0.80–0.88. **Not claimed as habitat skill** | — |

The honest ceiling: detections are Bernoulli-noisy, so even a perfect habitat model probably reaches only about 0.72–0.80 effort-stratified AUC. The oracle ratio makes this explicit.

---

## 6. Risks, failure modes and the falsification ladder

| ID | When | Test | Kill or change |
|---|---|---|---|
| X0 | Days 1–2 | **Injection–recovery** on real EBD geometry. Two truths (hazard-shaped and thinned-IPP), each with and without preferential sampling (A's re-aim) and with habitat-dependent detectability (E's re-aim). **Both models are scored on both truths** (§10 explains why A's version fails this) | Sets the MDE, checks cross-play symmetry, and selects the DT variant. If M_CL cannot beat M_TG on truth (i) by the MDE, the arena has no power, and that is reported first |
| X1 | Days 3–5 | **Cross-play + HH + same-day CC**, clock + legacy features, no embedding | **Kill** the checklist model if the TkL₅ gap CI includes 0 **and** CC does not beat both the CNN and the permutation band. In that case ship H₀/v0 with access and freshness layers only |
| X2 | Week 2 | **Disturbance panel event study** (below) | **Fail** (slope ≤ 0 with adequate power, or a significant pre-trend): coverts are badged "between-site only". If underpowered: reported as such, no claim |
| X3 | Day 1 | Freshness audit of today's map (D) | No kill; quantifies stale-map error |
| X4 | Week 3 | G-AEF (§3.6) | Embedding dropped if any condition fails |
| X5 | Season | S0 scorecard; randomised hunt lift | Accumulates across seasons |

**X2 in detail.**
1. **Units.** EBD `LOCALITY ID`s with ≥ 8 complete checklists in both the pre and post windows. "Treated" means fused stand-replacing loss covering ≥ 10% of the 300 m disc in year $y_0\in[2005,2019]$, with checklists 2010–2025. Never-treated controls have no loss within 600 m. Step 1 counts treated units and computes power, and the count is **unverified** until then.
2. **Stacked event study.**
   $$\text{cloglog}\,P(y_j)=\gamma_{\ell(j)\times\text{stack}}+\tau_{\text{region}\times\text{year}\times\text{stack}}+g(w_j)+\sum_{k=-4}^{-1}\theta_k\,\text{lead}_k+\sum_b\beta_b\,\mathbb 1[\text{age bin } b]\cdot\text{share}_{300}$$
   - Each treatment cohort is stacked with its own never- or not-yet-treated controls. This avoids the staggered-adoption bias of two-way fixed effects (Goodman-Bacon 2021; Callaway & Sant'Anna 2021; both **from memory, unverified**).
   - Leads $\theta_k$ must be jointly ≈ 0. This is the pre-trend placebo.
3. **Model check.**
   - Refit FLUSH-C **excluding panel sites plus a 2.5 km buffer**.
   - Predict $\Delta\hat\eta_\ell=\hat F(x_{\text{post}})-\hat F(x_{\text{pre}})$ for each treated site.
   - Regress the within-site observed change on $\Delta\hat\eta_\ell$ with site FE.
   - **Pass:** slope > 0 (lower CI > 0). A slope near 1 means the effect size is right.
   - The 0–4-yr bin, where visibility changes most, is reported but excluded from the pass rule (L3).

**Risks.**

| Risk | Severity | Mitigation |
|---|---|---|
| Spring-dominated detections (61% Apr–Jun, 15% Sep–Nov; verified by E) | MAJOR (shared) | Fall head; DT variant selection; fall-only guard; fall-only primary metric |
| Partial harvest invisible to the clock | MAJOR (shared) | LCMS slow loss; HF437; embedding change band; lidar `under` later |
| AEF reporting-geography leakage | MAJOR | G-AEF conditions 1 and 3; the X1 kill decision uses no embedding |
| X2 underpowered, or new logging roads change access | MEDIUM | Report power; access change is a time-varying covariate (new OSM tracks within 300 m, where dated) and a sensitivity run without sites with new roads |
| Too few same-day pairs | MEDIUM | D's fallback to stratified AUC |
| Misregistration of new exports | MAJOR (repeat of BUG-0094) | Template `crsTransform` and registration gates |
| QMS overhead | Process | One CR per phase; X0–X4 thresholds committed first (CR-0011 A3/A5) |

---

## 7. Implementation plan (one owner, one EC2 GPU)

| When | Work | Compute | CR |
|---|---|---|---|
| **Day 1** | EBD/SED ingest (polars streaming; Johnston filters; zero-fill; group dedupe; first-visit and mode flags; HH flag + 2.5 km buffer); counts by state, season, mode, same-day pairs and panel units. **S0 scorecard frozen.** X3 freshness audit. Commit X0–X4 thresholds | CPU, under 1 h | acceptance CR + data CR |
| **Days 1–3** | Clock rasters (fused, template lattice, registration gates); multi-radius shares on GPU. **v0 H₀ covert layer + access classes to the owner** | EE export + GPU, hours | generator CR |
| Days 1–2 | X0 injection (both truths × PS × DT) | CPU | gate code |
| **Days 3–5** | M_TG and M_CL (LightGBM cloglog + GAM alternation); **X1**; permutation band (20 fits on 200k, overnight) | CPU | model CR |
| **Week 2** | **X2** panel; DT variant fitted; **v1 product** (about 20 Oct) | CPU | product CR |
| Week 3 | Embeddings: COGs → masked PCA-16 disc means (GPU FFT, 2.4 km halo); override and transport; back-test; **X4** | GPU, about 1 h per state-year | generator CR |
| Season and later | Ledger, refit, lidar `under`, optional neural gate | — | separate CRs |

**Budget.**
- The checklist table is about 1–2 M rows × about 400 features, roughly 3 GB. LightGBM fits in minutes.
- Storage is about 10 GB per year.
- Nothing needs NUTS, a grouped objective or a per-pixel cube.

**The first experiment the owner runs today:** the Day-1 ingest and counts. X1 follows on day 5.

---

## 8. References

These were verified in rounds 1–3 unless marked.

- AlphaEarth Foundations paper: Brown, C.F. et al. (2025), arXiv:2507.22291, https://arxiv.org/abs/2507.22291 (HTML read: S15.10–S15.12 GBIF text targets, Table S1 targets vs inputs)
- Satellite Embedding V1 catalog: https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL ; GCS readme: https://developers.google.com/earth-engine/guides/aef_on_gcs_readme ; aef-loader: https://aef-loader.readthedocs.io/en/latest/ (the 2025 layer is **unverified**)
- GBIF EOD API fields (`recordedBy`, `eventDate` present; `eventID`, effort, `coordinateUncertaintyInMeters` absent in the sample): https://api.gbif.org/v1/occurrence/search?datasetKey=4fa7b334-ce0d-4e88-aaae-2e0c138d049e
- Clarfeld, L.A. et al. (2025), USGS data release doi:10.5066/P13EFLXX ; https://www.sciencebase.gov/catalog/item/679392d5d34e88f5864c50b5 (no site ID or coordinates; verified)
- LCMS v2024-10: https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10 ; Hansen GFC v1.12: https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12 ; OPERA DIST-ANN: https://developers.google.com/earth-engine/datasets/catalog/OPERA_DIST_L3_DIST-ANN-HLS_V1 (via D)
- HF437 Maine harvest maps: https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF437 (via A and D)
- Johnston, A. et al. (2021). *Diversity and Distributions* 27:1265–1277. doi:10.1111/ddi.13271
- Kelling, S. et al. (2015). *PLOS ONE* 10:e0139600. doi:10.1371/journal.pone.0139600
- Maclure, M. (1991). The case-crossover design. *Am. J. Epidemiol.* 133:144–153 (via D; **unverified**)
- Goodman-Bacon, A. (2021). Difference-in-differences with variation in treatment timing. *J. Econometrics* 225:254–277 (**from memory, unverified**)
- Callaway, B., Sant'Anna, P.H.C. (2021). Difference-in-differences with multiple time periods. *J. Econometrics* 225:200–230 (**from memory, unverified**)
- Lapp, S. et al. (2023). *Wildlife Society Bulletin* 47(1). doi:10.1002/wsb.1395
- NH Fish & Game Small Game Summary: https://www.wildlife.nh.gov/sites/g/files/ehbemt746/files/inline-documents/sonh/small-game-summary.pdf (**contents unverified**, 403)
- PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview
- Repository: `docs/grouse_model_report.md`; `sightings.py:20`; `regions.py`; `diagnose_gbm_baseline.py`; `diagnose_disturbance_features.py`; `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md`

---

## 9. Responses to critiques

| Critic | Critique | Severity | Accept / rebut | Evidence or fix |
|---|---|---|---|---|
| A | Trajectory incoherent (age shifted, embedding fixed); the embedding ends in 2024, so 2025–26 cuts look intact | MAJOR | **Accept** (fixed in round 2, kept) | §3.4: fresh-cut override (OPERA DIST-ALERT 2025–26, LCMS/Hansen); age-conditional transport; 2019 → 2024 back-test with τ ≥ 0.80, otherwise clock-only trajectories |
| A | H buffer 1 km < 2.4 km discs, so inputs are shared | LOW | **Accept** | Buffer is 2.5 km (§5.1) |
| A | "Balancing changes variance, not bias" holds only under correct specification | LOW | **Accept** | Text corrected; the uncapped fit is reported alongside (§3.5) |
| B | The 10 m embedding can see birding infrastructure; nothing pre-registered stops it; the round-1 test checked only hotspot type | MAJOR | **Accept** | §3.3 masked disc means (roads, tracks, paths, parking, buildings, developed); EL2 probe AUC ≤ 0.70; off-trail importance-weighted TkL; G-AEF; the embedding is a gated block, not primary. I also tightened the gate with D's permutation null |
| B | The round-1 kill test has home advantage | MEDIUM | **Accept** | B's cross-play adopted (§5.1). X1's kill rule also uses same-day CC, which has no home advantage on effort |
| D | Embedding primary with no infrastructure gate (round 1) | MAJOR | **Accept** | Same fix as B's item |
| D | Covert trajectory internally inconsistent (round 1) | MEDIUM | **Accept** | Same fix as A's item |
| D | "No ARU network exists in ME/NH/VT" is false | LOW | **Accept** | Corrected. The GMNF network exists; its public release has no coordinates (verified); site data are requested as S3 |
| E | AlphaEarth was pretrained with GBIF occurrences, so it may encode where grouse were *reported*. That could make the H-set comparison BLOCKING | MAJOR (BLOCKING if eBird rows passed the 240 m filter) | **Accept MAJOR; rebut BLOCKING** | *Verified* in the AEF paper: GBIF 2017–2023, ≤ 240 m uncertainty, ≤ 1000 obs per taxon tag, used as **training targets only**, not inference inputs. *Why not BLOCKING:* (1) the decisive H-set test X1 uses **no embedding**, so it cannot be inflated by it; (2) the embedding enters only through G-AEF, now decided on **2024–25** checklists with a ≤ 2023-trained model, plus a record-proximity check (gain ≥ 1 km from past GBIF grouse records must be ≥ 50% of the gain near them); (3) the cap of ≤ 1000 records per species tag, range-wide, limits grouse-specific memorisation. GBIF eBird rows in my API sample lacked `coordinateUncertaintyInMeters`, so whether they passed the filter is **unverified**. I lowered P(G-AEF passes) from 0.40 to 0.30 |
| E | Pruning ARUs on a false premise | MEDIUM | **Accept** | Corrected. The owner's own AudioMoth deployment (A, E) stays an option for spring 2027, with drum rate per recorder-day as the metric |

---

## 10. Final critique of competitors (round-2 versions)

| Design | Flaw | Severity | Status | Evidence / failure scenario |
|---|---|---|---|---|
| **A** | The footprint is a **sum** over a disc of radius 150 m + d/2, with a non-negative distance slope ($\alpha_2^{+}$). The expected count scales with area (∝ d²), not with swept length (∝ d). Long walks are over-predicted, so the fit lowers $D$ where long walks go, which is big remote woods | MAJOR | **Still open** | A round 2 §3.4 O1 (unchanged). Worked example: d = 4 km → 14.5 km²; d = 0.5 km → 0.50 km². That is 29× in area against 8× in path length. Fix: disc mean, or a free-sign slope |
| A | T1's falsification rule is evaluated on 25 km held-out blocks, where most checklists lie in the CNN's training blocks. The CNN is inflated (GBIF EOD = EBD detections), which biases the test toward falsely killing CYM. HH is only a reported subset | MAJOR (for the test) | **Still open** (D raised it too) | A §6 T1 step 4 vs the "falsified if" rule |
| A | T2 scores CYM on its own truth and the GBM on a different truth, so it cannot show robustness | MEDIUM | **Still open** (D's finding; I concur) | A §6 T2 "reading". Fix: both models on both truths (as in my X0) |
| **B** | The negative-control gate (chickadee/jay ρ ≤ 0.3) is not diagnostic in either direction. A near-flat map from a ubiquitous species passes trivially (D's point). A forest-structured control map fails for legitimate forest-vs-open reasons (mine). It is also B's only gate for embedding admission | MEDIUM | **Still open** | B §3.5 R-EL. Fix: within-stratum permutation null + infrastructure probe |
| B | Every falsification is between-site. Within-observer AUC pairs across days and seasons, so site selection by the same observer survives | MEDIUM | **Still open** | B §3.5 R-PS. My X2 and D's same-day first-visit CC address it |
| B | Earlier GBIF pseudo-checklist plan | — | **Fixed** (patched for EBD) | B §0 |
| **D** | **The label-permutation null cannot detect infrastructure leakage, contrary to its "Cheater 4 fails" claim.** Suppose trail-texture features truly co-vary with grouse reports *within* a stratum, because birders find grouse on forest trails. Permuting labels destroys that association, so permuted fits show no signal, the real fit shows a gain, and the gate admits the block. The null bounds effort-*geography* manufacture, not feature–label confounding by infrastructure | MAJOR (it is D's only embedding gate) | **New** | D §2 "Cheater 4" and §3.5 gate. Fix: masking + a probe that predicts infrastructure from features (my EL2), plus off-trail weighting |
| D | Same-day pairs ≥ 1 km apart are mostly spring roadside hotspot hops (61% of detections are Apr–Jun). CC therefore mostly ranks spring audibility contrasts unless restricted to fall | MEDIUM | **New** | D §3.5. Fix: report fall-only CC; weight by mode |
| D | Location-derived effort covariates and the adversary | — | **Fixed** | D §0.2 |
| **E** | **The season-contrast term assumes λ is the same in spring and fall at a footprint**, but grouse shift seasonal use (fall food cover, mature aspen buds, conifer thermal cover; report §1.4). Only the openness covariates absorb a season difference. Every other seasonal-use difference lands in $h$, which is fitted 61% on spring detections. "Fall map" is then partly a spring-use map along non-openness dimensions | MEDIUM | **New** | E §3.4. Fix: let the injection test choose among detectability variants (adopted here), and use E's own fall-only guard |
| E | In-sample CNN baseline | — | **Fixed** (HH adopted) | E §0.2 |
| E | Over-large per-pixel feature cube | — | **Fixed** (point features + prediction-year grid) | E §3.6 |
