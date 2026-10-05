# Design B, final: CEM-X, the cross-examined Checklist Encounter Model

*Designer B, round 3 (final).*

*Techniques:*
- *Round 1: analogical transfer.*
- *Round 2: adversarial cross-play and red-teaming.*
- *Round 3: a "cheater battery" audit of every test in all five designs, asking whether a model that learned birder geography, return-to-known-spots, or drumming audibility could pass it; a leakage audit of every arena, asking whether the comparator is scored in-sample; and adoption from round-2 rivals.*

*No repository file was edited.*

*Facts marked **verified** were checked against the repository, the GBIF API or the web in rounds 2–3. The owner already has eBird EBD and Sampling Event Data (SED) access.*

---

## 0. Changes from round 2

### 0.1 Critiques accepted and fixed

The full table, with evidence, is in §9.

| Fix | Prompted by |
|---|---|
| All decision gates are now evaluated on **fall (Sep–Dec) checklists in HH**. An all-season win that fails in fall counts as a fail. | E (MAJOR) |
| Habitat-dependent detectability is attacked by three independent handles (§3.6) instead of a fall head alone. | E (MAJOR) |
| **The control-species gate is replaced** as the leakage gate by D's within-stratum **label-permutation null**. The control species remain only as a diagnostic, computed as C's forest-only partial correlation with Eastern Towhee in place of American Woodcock. | D (MAJOR), C (MEDIUM) |
| Preferential sampling is now tested **within site and within day**: D's same-day case-crossover is the primary metric, E's/D's first-visit restriction is applied, and C's disturbance panel test is adopted with a cross-fitting fix that C's own version lacks. | C, D (MEDIUM) |
| Fold and footprint geometry is fixed. Evaluation keeps every HH checklist by start point, so no straddling footprint is dropped. Training exclusion is footprint-aware, and a representativeness check confirms that HH keeps its traveling checklists. | A (MAJOR), E (MEDIUM) |
| `road_dist` is removed from the habitat function and kept only as a diagnostic. 2025–26 cuts are added via OPERA DIST-ALERT. | A (MEDIUM) |
| Injection–recovery is now a full **models × truths** grid scored on *unvisited* cells, so it can falsify CEM-X itself, not only the status quo. | A (MEDIUM), and D's critique of A |
| The pseudo-checklist phases are gone (owner has EBD). | C, D (LOW) |

### 0.2 Adopted from round-2 rivals (credited)

| Idea | From | Where |
|---|---|---|
| Same-observer, same-day case-crossover concordance (CC) as the primary preferential-sampling metric | D | §3.5, §5 |
| Within-stratum label-permutation null; a feature block is admitted only if it beats the null band | D | §3.5 |
| Owner's blinded covert scorecard (S0), frozen before any map is shown: the only non-eBird hunter-truth scorer available today | D | §3.7 |
| Detection-mode decomposition from EBD breeding/behaviour codes and comments (aural vs visual) | D | §3.6, as a diagnostic gated on label counts |
| Disturbance panel test with location fixed effects | C | §3.5, made cross-fitted |
| Season-specific footprint radius (drums heard far, flushes close), chosen by held-out deviance | C | §3.3 |
| Season-contrast openness term in the detection tower, kept only if injection-validated | E | §3.6 |
| First-visit ("naive-visit") restriction | E, D | §3.5 |
| A zero-fit covert layer shipped this week so the running 2026 season yields field data. I use D's H250 version, not a 40-parameter prior. | A (idea), D (H250 form) | §7 day 2 |
| Coverage / extrapolation audit | A | §3.7 badge |
| OPERA DIST-ALERT 2025–26 and HF437 in the disturbance fusion | D, A | §3.1 |
| Drum rate per recorder-day, not naive occupancy, if Green Mountain National Forest (GMNF) site data are obtained | A | §3.7 |

### 0.3 Kept as B's own (still unshared or done differently)

1. **Cross-play with calibrated symmetry.** C and E adopted cross-play. Only CEM-X calibrates the home-advantage symmetry assumption with injected truths (§5.1).
2. **Cross-fitted panel test.** C's X2 scores a model trained on the same locations it then evaluates (§10).
3. **Fall-gated decisions.** Every gate passes on fall HH checklists, not just all-season.
4. **Owner's hunts enter the same likelihood** as eBird complete checklists, with a `hunt` protocol level in the effort tower (my round-1 scouting loop). Field data improve the model directly; there is no separate side model.
5. **One gate battery with multiplicity control.** All gates are pre-registered and Holm-adjusted, with a stated prior probability of passing for each.

### 0.4 Dropped

- The control species as a *gate*. They remain a diagnostic only.
- GBIF pseudo-checklists.
- Any claim that detectability can be fully separated from abundance. §3.6 states exactly what each handle identifies.

---

## 1. Title and pitch

**CEM-X: rank this October's huntable coverts by expected grouse encounters per standard hour on foot, learned from eBird complete checklists. Ship only what survives a battery of tests that a birder-geography map, a return-to-known-spots map or a drumming-audibility map would fail.**

All five designs now share a core:
- complete checklists;
- an effort term with no location inputs, dropped at prediction;
- footprints;
- a succession clock;
- coverts;
- effort-expected top-k lift.

What still separates the designs is **whether their first decisive test can be passed by a cheater** and **whether their comparator is scored in-sample**. CEM-X is built so that neither can happen:

- **The decision arena is HH.** HH is the set of complete checklists inside the current CNN's own validation blocks. The CNN's positives are the same eBird detections (`sightings.py:20`), so any other arena scores the CNN in-sample.
- **Every decision metric is computed on fall checklists.** About 61% of grouse records are spring (April–June) and about 15% are September–November (verified by E). A model that wins only on spring checklists may be ranking where drumming is audible.
- **A cheater battery runs before release.** The model must beat:
  - the label-permutation null (it cannot manufacture habitat from effort);
  - same-day case-crossover (not observer skill or date);
  - first-visit pairs (not return to known spots);
  - a cross-fitted within-site panel (not fixed site traits);
  - the fall gate (not drumming).

**What the owner gets:**
- a covert layer for the phone, with access classes, peak windows and artefact badges;
- a daily list of five coverts with one randomised slot, so the season itself measures the lift;
- an H250 layer **this week**, so 2026 hunting already produces held-out truth.

The model itself is deliberately unglamorous: LightGBM with a cloglog footprint objective and a penalised effort GAM, fitted in hours on one EC2 machine.

---

## 2. Brainstorming record (short)

- **Round 1: analogical transfer across 11 fields.**
  - Ad position bias (PAL) gave the separable effort tower.
  - Vaccine test-negative design gave complete checklists as controls.
  - Fisheries CPUE gave the standardised-effort estimand.
  - Multiple-instance learning gave footprints.
  - Astronomy injection–recovery gave the simulation test.
  - Mineral prospectivity gave capture curves.
  - Poaching (iWare-E), fraud, oil-and-gas value of information and recommender exposure supplied supporting tricks.
- **Round 2: cross-play and negative controls.** Cross-play came from sports ratings and cross-dataset evaluation; negative-control outcomes from epidemiology; within-unit estimators from econometrics; survey "mode effects"; and oracle bounds.
- **Round 3, cheater battery (new).** For each test in A–E, I asked which of four cheaters passes it:
  - **C1:** birder skill and route geography;
  - **C2:** return to known grouse spots;
  - **C3:** drumming audibility;
  - **C4:** effort structure leaking through features.

  | Test | Passed by |
  |---|---|
  | Effort-stratified AUC | C1, C2, C3 |
  | Within-observer AUC across days | C2, C3, and partly C1's day/season confounds |
  | Same-day case-crossover | C2 (via hotspot fame), C3 |
  | First-visit | C3 |
  | Fall gate | C1, C2 |
  | Label-permutation null | C1, C2, C3 (it targets C4 only) |
  | Cross-fitted panel | C3 (a cut also changes audibility), partly |

  No single test stops all four, so the battery is the unit of evidence (§6).
- **Round 3, leakage audit (new).** For every arena in every design, I asked: "was the comparator trained on these labels or these locations?" This found three in-sample comparisons:
  - A's T1 on 25 km blocks scores the CNN on its own positives (D's finding);
  - C's panel test scores a model trained on the same locations;
  - E's season-contrast identification assumes site fidelity that the fall shuffle breaks (§10).

---

## 3. The design

### 3.1 Data

| Source | Status | Role |
|---|---|---|
| eBird EBD + SED, ME/NH/VT, 2016–2025 | **Owner has access** | Labels and effort. Filters (Johnston et al. 2021): complete; Stationary/Traveling; 5–300 min; ≤ 5 km; ≤ 10 observers; one per `GROUP IDENTIFIER`. `BREEDING CODE`/`BEHAVIOR CODE` and species comments are retained for mode labels; the comment column name is to be checked in the owner's header. |
| GBIF eBird dataset (`sightings.py` route) | **Verified via the GBIF API:** no `eventID`, time or effort fields | Not a label source. It *is* the CNN's positive set, which is why HH is mandatory. |
| Existing 15 layers + `mch_*`, after the CR-0035 registration repair | On EC2 | Habitat features (`diagnose_gbm_baseline.py` design). **`road_dist` excluded from $F$.** |
| Disturbance fusion: LCMS v2024-10, Hansen GFC v1.12, HF437 (Maine 1986–2019), LANDFIRE annual disturbance, OPERA DIST-ANN 2023–24 / DIST-ALERT 2025–26 | Earth Engine / archives (catalogs verified by A, C, D) | Succession clock aged to season $T$: age-class shares at 90/250/600 m, age-class diversity, severity. Exported on the template lattice with explicit `crsTransform`, with the BUG-0094 offset probe and `grid_mismatch` as acceptance gates. |
| AlphaEarth Satellite Embedding V1 | Earth Engine (verified by C) | **Optional block.** Infrastructure-masked (C's method), admitted only through the permutation gate. Evaluated on 2024–25 checklists only, because AlphaEarth pretraining used GBIF occurrences 2017–2023 (verified this round, arXiv:2507.22291; capped at 1,000 records per taxon tag, so the leakage is probably small). |
| Owner's blinded covert scorecard (S0) | Owner, now | Independent hunter-truth scorer (D) |
| Owner's 2026+ hunts, logged as **eBird complete checklists** (track on, protocol note "hunt", flush count) or as GPX + flush waypoints | Owner | The randomised field arm; then training rows with a `hunt` level in $g$ |
| NH Small Game Summary regional rates | The page returns 403 to automated fetch, so **contents unverified**; the owner downloads it | Scalar κ for flushes per hour; leave-one-region-out check |
| GMNF acoustic recorders (Clarfeld et al. 2025) | Public files **have no site ID or coordinates** (verified by C and D) | Bonus scorer, only after a data request |
| PAD-US 4.x, state lands, NH Current Use, OSM/TIGER | Public | Access classes (D) and walk-in distance; product only |

### 3.2 Estimand

$$
\Lambda^\star_{\text{fall}}(c,T)=e^{g(e^\star)}\cdot\frac{1}{|c|}\sum_{s\in c}\ \overline{\exp\!\big(F(x_{\cdot,T})+\Delta_{\text{fall}}(x_{\cdot,T})\big)}^{\,K^\star_{\text{fall}}(s)},\qquad p^\star=1-e^{-\Lambda^\star}.
$$

- This is the expected number of grouse encounters for one median-skill observer on a standard fall walk (traveling, 60 min, 2 km, 15 October, 08:00) centred in covert $c$.
- The overline is a kernel **mean**. Footprint size enters only through $g$'s monotone distance term; this avoids A's area-inflation problem (§10).
- Ranking depends only on $F+\Delta_{\text{fall}}$ (plus the visual-mode correction if §3.6 admits it).
- Conversion to hunter flushes per hour is a scalar κ. It is fitted on the owner's logs, checked against NH regions and shown as a label; it never changes the ranking.

### 3.3 Model

**Footprint.** Checklist $j$ starts at $s_j$, travelled distance $D_j$, in season $\varsigma_j$. The footprint kernel is a truncated Gaussian with

$$\sigma_j=\sqrt{\rho_{\varsigma_j}^2+(\kappa D_j)^2},\qquad \sigma_j\le1.2\text{ km},$$

truncated at 2σ.
- $\rho_\varsigma$ is chosen per season from {100, 150, 300, 600} m by held-out deviance. This is C's season-specific radius: spring drums carry, fall flushes are close.
- $\kappa\in\{0.25,0.35,0.5\}$.
- The kernel is represented by a 7-point stencil (stationary) or 13-point stencil (traveling) with weights $w_{jm}$.

**Main model: LightGBM with a cloglog footprint objective.**

$$\eta_j=g(e_j)+\operatorname{LSE}_m\!\big(F(x_{t_{jm}})+\log w_{jm}\big)+\Delta_{\text{fall}}\text{-term}\cdot\mathbb 1[\varsigma_j=\text{fall}],\qquad P(y_j{=}1)=1-e^{-e^{\eta_j}}.$$

- The row-$m$ gradient is the checklist gradient times its softmax share. This is exact inside a LightGBM custom objective.
- **Engineering guard** (A's and E's LOW concern that the grouped objective is error-prone): a committed unit test checks the custom gradient against finite differences, and against E's simpler "GBM on kernel-mean features" fit on a 50k subsample. Divergence beyond tolerance blocks the CR. If the grouped objective proves fragile, E's kernel-mean variant ships. It is an approximation, but a stable one.

**$g$ (event-only covariates; a hard rule shared by A, C, D and E).** A penalised GAM fitted by alternation (3–5 rounds), with:
- log duration and log(1+distance), monotone ≥ 0;
- protocol, including a `hunt` level for the owner's checklists;
- party size;
- start-time spline;
- cyclic day-of-year spline;
- year;
- out-of-fold observer skill (Kelling et al. 2015);
- an observer random effect for observers with ≥ 20 checklists.

**$g$ never includes a location-derived variable** (hotspot distance, trail distance, road distance, checklist density) and never the checklist's own species count.

**Features of $F$:**
- footprint-sampled `diagnose_gbm_baseline.py` design (centre codes, 21-px shares, 5/21/64-px means and SDs), minus `road_dist`;
- clock shares and diversity at 90/250/600 m, plus severity;
- `mch_*`;
- elevation and winter snow-water equivalent (Daymet; **asset ID unverified**);
- optionally, the masked AlphaEarth block (gated).

**$\Delta_{\text{fall}}$.** Depth ≤ 3, strong L2, fitted on Sep–Dec checklists with $F$ frozen.

**Uncertainty.** 5 spatial folds × 2 seeds. A Mahalanobis extrapolation flag in PCA-20 space of $F$'s features.

### 3.4 Arenas and splits

- **HH (the decision arena).** Every complete checklist whose **start point** lies in a validation block of the existing 3 km split (`regions.py`, `SPLIT_SEED=42`; verified). Nothing is dropped for straddling.
- **Training exclusion.** Every training checklist whose truncated footprint (≤ 2.4 km) comes within 0.5 km of an HH block is excluded. Labels can then share no footprint cells with HH, and the CNN half-window (0.96 km) is covered.
- **Representativeness check (A's MAJOR).** HH's mix of traveling checklists, distance terciles and hotspot share must lie within 5 percentage points of the full filtered set. If it does not, HH metrics are reweighted to the full-set mix and both versions are reported.
- **Model selection.** 5-fold CV on 25 km blocks outside HH, checked against the residual variogram (report §4.3).

### 3.5 The cheater battery (pre-registered acceptance code, committed before any fit; CR-0011 A3)

All metrics are on HH. Each is reported all-season and **fall-only**; the fall-only number decides.

| ID | Test | Stops cheater | Definition |
|---|---|---|---|
| **B1** | Effort-stratified AUC and fall TkL₅ | (baseline) | AUC within protocol × duration tercile × month × year. TkL₅ = observed ÷ effort-only-expected detections in the top 5% of held-out forest (D). |
| **B2** | **Same-observer, same-day case-crossover CC** (D) | C1 | Observer-days with ≥ 2 checklists ≥ 1 km apart, exactly one detecting grouse. CC = P(habitat score of the detecting checklist > the other), with the frozen $g$ difference as offset. |
| **B3** | **First-visit CC** (E, D) | C2 | B2 restricted to pairs where both locations are first-ever visits by that observer. A hotspot-free variant targets reputational targeting. The share of the B2 gain that survives is reported. |
| **B4** | **Label-permutation null** (D) | C4 | Within observer × month × duration tercile, permute $y$; refit the full pipeline 20× on a 200k subsample. The 95th percentile of the permuted CC and TkL is the null band. **Every gain must exceed the band. Every added feature block must not raise the permuted CC.** |
| **B5** | **Cross-fitted disturbance panel** (C's X2, fixed) | C1, C2 (fixed site traits) | Locations with ≥ 8 checklists before **and** after a stand-replacing loss covering ≥ 10% of the 300 m disc (cut years 2005–2019, checklists 2010–2025). Fixed-effects cloglog: observed within-location change regressed on the model's predicted change $\Delta\hat\eta_\ell$. **$F$ is refit with all treated locations (and a 2.5 km buffer) excluded**, so the prediction is out-of-sample (C's version is not). Pass: slope > 0 with lower CI > 0, weighted toward the 5–25-yr bins. Step 1 counts units; underpowered means "no claim". |
| **B6** | **Fall gate** | C3 | Every gate above must pass on fall-only checklists, Holm-adjusted. |

**Diagnostics** (reported, never gates):
- control-species maps, as forest-only partial Spearman with canopy cover controlled (C). Positive controls: Chestnut-sided Warbler, Eastern Towhee. Negative controls: Black-capped Chickadee, Blue Jay.
- share of top-5% coverts within 300 m of a hotspot or trail;
- R² of $F$ on location-derived effort layers.

### 3.6 Detectability that varies with habitat: three handles, with honest limits

| Handle | What it identifies | What it cannot |
|---|---|---|
| **H-a, fall-only evaluation and $\Delta_{\text{fall}}$** (B, D) | Whether the ranking holds where detection is mostly visual and flush-based, as for a hunter. No assumption is needed beyond "fall checklists resemble hunter detection better than spring ones". | Fall density versus fall detectability. A hunter shares that confound, so it is arguably the correct target. |
| **H-b, detection-mode decomposition** (D) | Aural-coded (`S`/drum comments) versus visual-coded detections, in a competing-risks cloglog with shrunk mode deviations. If the covert-ranking Spearman between modes is < 0.8, rank by the visual-mode function and badge disagreements. **Run only if ≥ 500 labelled detections per mode** (counted on day 1). | Missing-not-at-random coding. Most detections carry no code, so it is a diagnostic first. |
| **H-c, season-contrast openness term** (E) | A spring-specific detection slope on footprint openness (canopy cover, conifer share), with fall as reference (0). | It assumes λ is shared across seasons, but the fall shuffle disperses juveniles (report §1.4). It is admitted only if the injection test T0-c (below) shows it recovers a planted audibility bias **and** it does not hurt a no-bias truth by > 0.02 Spearman. |

At season 2, a hunter detection multiplier $W(s)=W_0e^{\omega\,\text{mch\_f15}(s)}$ is fitted from the owner's `hunt` rows (A's idea). It enters as an interaction of the `hunt` protocol with one structure covariate in $g$, the only habitat-touching term allowed in $g$, and it is fitted only on hunt rows.

### 3.7 End product

1. **This week (day 2): an H250 covert layer** (A's idea, D's form).
   - Disturbance patches aged 4–25 yr (fusion through 2026), SLIC segments and a 25 ha hexagon background, 2–40 ha.
   - Ranked by H250 = share of a 250 m radius cut 5–20 yr ago.
   - With access classes A1–A4/X.
   - Zero fitted parameters, frozen and hashed before any test.
   - It drives this season's daily list, so hunts start producing held-out truth immediately.
2. **Weeks 2–4: the CEM-X layer** replaces it, *only* if the battery passes.
3. **Covert card:**
   - $\Lambda^\star$, shown as "≈ flushes/h" via κ, with an 80% interval;
   - peak window;
   - access class and walk-in distance;
   - top-3 TreeSHAP reasons;
   - badges: **near hotspot**, **mode or season disagreement**, **extrapolated** (A's coverage audit), **PS-fragile** (B3 survival < 50%), **fresh cut 0–4 yr**.
4. **Daily list** (D): 4 coverts by Thompson sampling over the fold ensemble, plus 1 drawn uniformly from the accessible top 30%. Output is GPX/KML for onX, Gaia or Avenza.
5. **Ledger.** Each hunt is logged as an eBird complete checklist (preferred: same schema, same likelihood) or as GPX + flush waypoints.
   - A gamma–Poisson covert effect updates in-season.
   - $F$, $g$ and $W$ are refit after the season.
   - The random slot gives an unbiased realised-lift estimate.
6. **Scorers:**
   - S0: owner scorecard, Spearman weighted by times hunted (D);
   - S1: NH regions, leave-one-region-out;
   - S2: field random slot;
   - S3: GMNF drum rate per recorder-day, if site data arrive (A).

---

## 4. Why it beats the status quo, and the other four

**Against the status quo** (report §5.4: "the data is the ceiling"). Complete checklists replace target-group pseudo-negatives with observed non-detections conditional on effort. That removes:
- the PU contamination (§4.4);
- the $1-a/2$ shared-support bound (§4.1);
- the habitat-structured denominator $q_{\mathrm{TG}}$;
- the envelope double-count (§6).

The clock fixes staleness (§5.6 Q5), and the estimand is in the hunter's units (§5.1).

**Against A–E.** The core is shared, so the comparison is about evidence quality and buildability:

| Axis | CEM-X | Weakest alternative (round 2) |
|---|---|---|
| Comparator leakage | Every decision on HH; B5 cross-fitted | A's T1 scores the CNN in-sample. C's panel test is in-sample. |
| Cheater coverage | B1–B6 cover C1–C4, with a fall gate on every test | E has no permutation null or within-day pairs. A has no permutation null or within-site test. |
| Detectability | Three handles, each with stated limits; injection-gated | E's handle relies on site fidelity across seasons. A's handle waits for hunt logs. |
| Footprint | Kernel mean, truncated, season radius | A sums over an area ∝ distance², with a non-negative distance slope. |
| Field data | Owner hunts enter the same likelihood | Separate side models (A, D) |
| Buildability | LightGBM + GAM, CPU hours; a finite-difference-tested objective with fallback | A: NUTS on convolutions. C: embedding transport. |

---

## 5. Expected gains, measured without fooling ourselves

### 5.1 Cross-play with calibrated symmetry

- **Models:**
  - M_TG: identical features, target-group labels (`diagnose_gbm_baseline.py`);
  - M_CL: identical features, checklist labels;
  - the CNN map as a third row.
- **Arenas:** T_TG (existing validation set) and HH fall checklists.
- **Label thesis passes** if

  $$\Delta^{TG}_{\text{away}}-\Delta^{CL}_{\text{away}}\ \ge\ m^\star,$$

  with lower CI > 0.
- **Calibrating the margin (unique to CEM-X).** The margin $m^\star$ is *not* a guess. T0 runs the same cross-play on injected truths where labels carry *equal* information. The 95th percentile of that symmetric-case difference is $m^\star$, so pure home advantage cannot pass.
- **Oracle ratio:** achieved ÷ oracle AUC, from 200 label simulations from the model's own probabilities.
- **Mandatory baselines in every table:** effort-only, H250 (A), the CNN, M_TG.

### 5.2 Expected values

These are priors and will be replaced by measurements.

| Quantity on HH, fall | CNN | CEM-X | Confidence |
|---|---|---|---|
| Effort-stratified AUC | 0.62–0.69 | 0.66–0.74 | Low–medium. The direction is supported by Johnston et al. (2021); fall n is smaller, so CIs are wider. |
| TkL₅ | 1.3–1.7× | 1.6–2.3× | Low |
| Same-day CC (B2) | 0.53–0.57 | 0.56–0.62 | Low. Within-day pairs test within-landscape ranking, which is the hunter's decision, so the numbers are small. |
| Share of the B2 gain surviving first-visit (B3) | — | 50–85% | Low |
| B5 panel slope | — | > 0 if powered; the power is unknown until the units are counted | Very low |
| S0 scorecard Spearman (n ≈ 30) | 0.1–0.4 | 0.3–0.6 | Very low. SE ≈ 0.18. |
| Field: top-4 vs random slot, one season | — | ≥ 1.4× point estimate; ~40 visits detect only ≥ 2× | Very low |
| Legacy TG AUC | 0.762 / 0.770 | 0.74–0.78, not optimised | Medium |

### 5.3 Gate priors (Holm-adjusted battery)

| Gate | Prior probability of passing |
|---|---|
| G1: B1 + cross-play pass on fall HH | 0.55 |
| G2: B2 passes and beats the B4 null | 0.5 |
| G3: B3 retains ≥ 50% of the gain | 0.6 given G2 |
| G4: B5 positive slope, given power | 0.5 |
| G5: clock adds ≥ 0.1 TkL₅ or ≥ 0.01 AUC | 0.45. It added +0.001 under TG labels (CR-0032 l.22, verified). |
| G6: AlphaEarth block admitted | 0.3 |

If G1 fails, the checklist programme stops. The H250 layer, access classes and field ledger remain, which is still a usable product.

---

## 6. Risks and the falsification ladder

| Step | When | Test | Kill or change |
|---|---|---|---|
| **T-1** | Day 1 | EBD ingest and counts: checklists, detections by month, state and mode; same-day pairs; first-visit pairs; panel units; HH representativeness | < 2,000 informative same-day pairs → B2 is demoted to a diagnostic. < 500 per mode → H-b is diagnostic only. Panel units underpowered → B5 makes no claim. |
| **Ship** | Day 2 | Freeze S0 (owner scorecard). Ship the H250 layer and freeze it. Run D's freshness audit on today's map. | — |
| **T0** | Days 2–4 | Injection–recovery grid on real EBD geometry. **Pipelines:** M_TG, M_CL, M_CL + season-contrast. **Truths:** (a) hazard-shaped; (b) thinned-IPP, where the TG pipeline is correctly specified; (c) spring audibility ∝ openness with density peaking in young dense cover (E); (d) preferential visits that avoid dense young cover (A). Scored on **unvisited** forest cells. | Calibrates $m^\star$ and the B4 band. If M_CL does not beat M_TG on (a) and (d) by more than the noise, the arena has no power, and this is said before any real result. H-c is admitted only if it wins on (c) and does not lose on (b) by > 0.02. |
| **T1** | Days 4–6 | Cross-play + B1–B4 on HH, fall-gated. Legacy features + clock, no embeddings. | **G1 fails → stop the checklist programme.** G2/G3 fail → the product ships with PS-fragile badges, and no precision claim is made. |
| T2 | Week 2 | B5 cross-fitted panel; H-b modes; $\Delta_{\text{fall}}$ | Decides the ranking function and the badges |
| T3 | Week 3 | Optional blocks (AlphaEarth masked, 2024–25 evaluation only) through B4 | Admit or drop |
| T4 | Season | Random-slot field arm; S0 rescoring; κ | Product truth |

| Risk | Severity | Mitigation |
|---|---|---|
| Fall checklists too few for tight CIs | MEDIUM | 2016–2025 pooled; 5.8k Sep–Dec GBIF grouse records for 2020–24 alone (verified). Wider CIs are reported, not hidden. |
| Same-day pairs are mostly hotspot hops | MEDIUM | Hotspot-free B3 variant; demotion rule at T-1 |
| Clock misses partial harvest (Maine shelterwood) | MAJOR (shared by all designs) | LCMS slow loss, HF437, `mch_f15`; the panel test weights the 5–25-yr bins |
| Misregistration in new exports (BUG-0094 class) | MAJOR | Template `crsTransform`, offset probe and `grid_mismatch` as acceptance gates (PREVENTIVE_ACTIONS) |
| Access errors | MAJOR (ethics) | A4 is never shown as open; personal use only |
| Permutation refits cost 20× | LOW | 200k subsample; overnight on CPU |
| QMS overhead | Process | One CR per phase; acceptance code first (CR-0011 A3/A5) |

---

## 7. Implementation plan (one owner, one EC2 GPU; almost all CPU)

| When | Work | CR |
|---|---|---|
| **Day 1** | `ebird_checklists.py` (pandas, chunked): filters, zero-fill, group dedupe, first-visit flags, mode labels, HH flags, footprint-aware exclusion. Write the T-1 count report. Commit `eval_battery.py`: HH, B1–B6, TkL, cross-play, oracle, Holm, frozen thresholds; plus the gradient unit test. | data CR + acceptance CR |
| **Day 2** | Disturbance fusion export through 2026 on the template lattice (registration gates); H250 raster. **Ship the H250 covert layer** with access classes and the daily list. Freeze S0. Run the freshness audit. | generator CR + product-v0 CR |
| Days 2–4 | T0 injection grid (`inv_cem_injection.py`) | acceptance (gate code) |
| Days 3–4 | Stencil feature sampling via the existing patch reader and clock rasters | (generator CR above) |
| **Days 4–6** | GBM-cloglog + GAM alternation; M_TG and M_CL; **T1** | model CR |
| Week 2 | T2: cross-fitted panel, modes, fall head; fold ensemble | model CR |
| Week 3 | CEM-X covert layer (if gates pass); cards, badges, ledger ingest (eBird `hunt` checklists, GPX) | product CR |
| Week 3+ | Optional AlphaEarth masked block (T3); optional PyTorch footprint model if it beats the GBM by more than the B4 band | separate CRs |
| Season end | Refit with `hunt` rows; fit κ and $W$; score S0–S2 | — |

**First experiment within a day:** the Day-1 ingest and count report. On day 2 the owner is already hunting from a frozen H250 list with a randomised slot. T1 decides the checklist programme by day 6.

---

## 8. References

Verified in rounds 1–3 unless marked **unverified**.

1. GBIF eBird Observation Dataset API (fields; seasonal counts), queried 2026-10-05: https://api.gbif.org/v1/occurrence/search?datasetKey=4fa7b334-ce0d-4e88-aaae-2e0c138d049e
2. eBird data products / EBD: https://science.ebird.org/en/use-ebird-data/download-ebird-data-products
3. Johnston, A. et al. (2021). *Diversity and Distributions* 27:1265–1277. https://doi.org/10.1111/ddi.13271
4. Kelling, S. et al. (2015). *PLoS ONE* 10:e0139600. https://doi.org/10.1371/journal.pone.0139600
5. Brown, C.F. et al. (2025). AlphaEarth Foundations. arXiv:2507.22291. https://arxiv.org/abs/2507.22291. Its training data include GBIF Plantae/Animalia/Fungi occurrences 2017–2023, ≤ 240 m uncertainty, ≤ 1,000 per taxon tag (verified via search summary of the paper).
6. Clarfeld, L.A. et al. (2025). USGS data release doi:10.5066/P13EFLXX; ScienceBase item 679392d5d34e88f5864c50b5. No site coordinates in the public files (verified by C and D).
7. Guo, H. et al. (2019). PAL. *RecSys*. https://doi.org/10.1145/3298689.3347033
8. Jackson, M.L., Nelson, J.C. (2013). The test-negative design. *Vaccine* 31:2165–2168 (DOI **unverified**)
9. Lipsitch, M., Tchetgen Tchetgen, E., Cohen, T. (2010). Negative controls. *Epidemiology* 21:383–388 (**unverified**)
10. Maclure, M. (1991). The case-crossover design. *Am. J. Epidemiol.* 133:144–153 (**unverified**; via D)
11. Christiansen, J.L. et al. (2016). Kepler injection–recovery. *ApJ* 828:99. https://ipac.caltech.edu/publication/2016ApJ...828...99C
12. Chung, C.-J.F., Fabbri, A.G. (2003). *Natural Hazards* 30:451–472. https://ideas.repec.org/a/spr/nathaz/v30y2003i3p451-472.html
13. Maunder, M.N., Punt, A.E. (2004). *Fisheries Research* 70:141–159.
14. Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scand. J. Statist.* 6:65–70 (**unverified**)
15. Earth Engine catalogs: LCMS v2024-10, Hansen GFC v1.12, OPERA DIST-ANN-HLS V1, AlphaEarth V1 (verified by A, C and D); HF437, doi:10.6073/pasta/20a838c4bd6922685b3d00661d45c414 (verified by A and E)
16. PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download ; NH Current Use: https://www.wildlife.nh.gov/current-use (via D)
17. NH Fish & Game Small Game Summary / Wing and Tail Survey (403 to automated fetch; **contents unverified**)
18. Repository (all verified):
    - `sightings.py:20` (GBIF dataset key = CNN positive source);
    - `regions.py` (`SPLIT_SEED`, `VAL_FRACTION`);
    - `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md:22-25`;
    - `get_negatives.py` `TARGET_SPECIES`;
    - `diagnose_gbm_baseline.py`;
    - `diagnose_disturbance_features.py`;
    - `docs/grouse_model_report.md` §1.4, §2.3–2.4, §4.1–4.8, §5.

---

## 9. Responses to critiques

| Critic | Critique | Severity | Accept / rebut | Evidence or fix |
|---|---|---|---|---|
| A | Fold geometry discards traveling checklists: 3 km blocks, and footprints straddling folds are dropped | MAJOR | **Accept (fixed)** | This was true of round 1 §3.4. Round 2 already moved internal CV to 25 km blocks. Round 3 defines HH membership by **start point**, so nothing is dropped. Exclusion now applies only to *training* checklists, footprint-aware (§3.4), and footprints are truncated at 2σ ≤ 2.4 km. A pre-registered representativeness check keeps HH's traveling and distance mix within 5 pp of the full set, or reweights. |
| A | The habitat tower keeps `road_dist` and has no clock or 2025–26 cuts, so it is stale | MEDIUM | **Accept (fixed)** | The clock was added in round 2. Round 3 removes `road_dist` from $F$ (diagnostic only) and adds OPERA DIST-ALERT 2025–26 and HF437 (§3.1). |
| A | F0 used a CEM-shaped truth on target-group geometry, so it cannot falsify CEM | MEDIUM | **Accept (fixed)** | T0 is now a pipelines × truths grid on real EBD geometry, scored on unvisited cells. It includes an IPP truth (where TG is correctly specified), an audibility truth and a preferential-sampling truth (§6), so CEM-X can lose. |
| C | The negative-control gate uses raw ρ ≤ 0.3 with forest birds, which misfires; woodcock uses a different detection channel | MEDIUM | **Accept (fixed)** | The controls are no longer a gate. As a diagnostic they use C's forest-only partial Spearman, with Eastern Towhee replacing woodcock. The gate is now D's permutation null (B4). |
| C | The falsification ladder is entirely between-site | MEDIUM | **Accept (fixed)** | B5 adopts C's location-fixed-effects panel test, **cross-fitted** (treated locations excluded from training). B2 (same day) and B3 (first visit) add within-observer-day controls. |
| C | Pseudo-checklist phases are dead weight | LOW | **Accept (fixed)** | Removed in the round-2 patch; the round-3 plan starts with EBD on day 1. |
| D | Negative-control species cannot fail: their near-flat maps correlate weakly with anything | MAJOR | **Accept, with a partial rebuttal** | Partial rebuttal: with an effort tower, chickadee and jay maps need not be flat (feeders, development and edge carry real structure). C's critique runs in the *opposite* direction (they correlate too much), and both cannot be generally true. That shows the statistic's behaviour is unpredictable, which is itself the reason to drop it as a gate. Fix: D's within-stratum label-permutation null (B4), whose null distribution is computed, not assumed. |
| D | Within-observer AUC pairs across days and seasons, so seasonal detectability and year level differ inside pairs | MEDIUM | **Accept (fixed)** | B2 is D's same-observer, same-day case-crossover, and is the primary preferential-sampling metric. The cross-day within-observer AUC is kept only as secondary. |
| D | Week-1 gates were built on pseudo-checklists | LOW | **Accept (fixed)** | As above. |
| E | The decisive test is all-season with only a fall head; there is no identification argument for detectability, so a cross-play win may be a drumming win | MAJOR | **Accept (fixed), with a partial rebuttal of "no identification"** | Fix: **every gate is decided on fall checklists** (B6). A spring-audibility model cannot win fall checklists through spring audibility, and this requires no identification assumption. Three handles are added (§3.6): fall-only evaluation with $\Delta_{\text{fall}}$, D's mode decomposition, and E's own season-contrast term, injection-gated. Partial rebuttal: E's season contrast is not assumption-free either. It needs λ shared across seasons, and the fall shuffle disperses juveniles (report §1.4), so it is admitted only via T0-c. I verified E's 61%/15% split as consistent with my own GBIF counts: Apr–May 13,822 vs Sep–Dec 5,774 for 2020–24. |
| E | 3 km blocks with large footprints drop straddlers, biasing evaluation to short checklists | MEDIUM | **Accept (fixed)** | Same fix as A's MAJOR: HH by start point, footprint-aware training exclusion, representativeness check. |

---

## 10. Final critique of competitors (round-2 versions)

| Design | Flaw | Severity | Status | Evidence / failure scenario |
|---|---|---|---|---|
| **A** | **The footprint is a sum over a disc of radius 150 m + d/2, with distance slope $\alpha_2\ge0$.** The expected count grows with area, not with swept length. | MAJOR | Still open (C's finding; I verified the formula in A §3.4 O1) | A 4 km walk gets a 29× area over a 0.5 km walk, against ~8× in length. The fit can only explain long walks' lower-than-predicted detections by lowering $D$ in long-walk habitat (remote big woods). Fix: kernel mean, or an unconstrained slope. |
| A | **T1 (its decisive zero-tuning test) runs on 25 km blocks, so the CNN is scored on its own positives** | MAJOR | Still open (D's finding) | `sightings.py:20` makes the CNN positives the same eBird detections. The CNN is inflated, and T1 can falsely kill CYM's premise. Fix: run T1 on HH only. |
| A | T2 injection compares recovery of *different* truths by different models | MAJOR | Still open (D's finding) | CYM recovering a CYM-shaped truth proves nothing. Fix: both models on both truths, as in my T0. |
| A | Precision ceiling of ~40 structural parameters | MEDIUM (was MAJOR) | Partly fixed | A now has a gated LightGBM residual $r(s)$ and states that CYM may lose in-sample. That is honest, but the residual is admitted only if it does not hurt the (flawed) T2. |
| A | Disaggregation circularity ($h_g\propto(K*q)^\eta$) | LOW (was MEDIUM) | Fixed in effect | Gradients are stopped into shape parameters, so only level and scale are affected. |
| A | The "blinded" 2026 field test cannot blind a hunter to visible young cuts; ~20 h/arm detects only ≥ 2× | MEDIUM | Still open (C, E) | Effort inside a covert follows its look. A says the power limit itself. |
| **C** | **Panel test X2 scores the model's predicted within-site change using an $F$ trained on those same locations' checklists** | MAJOR | **New** | C §6 X2 step 3 computes $\Delta\hat\eta_\ell$ from the fitted model, with no exclusion of treated locations. The trees have seen post-cut detections at those sites, so a positive slope is partly in-sample, and the one within-site test in C cannot cleanly fail. Fix: cross-fit (my B5). |
| C | AlphaEarth pretraining used GBIF occurrences 2017–2023 | LOW–MEDIUM (E rated MAJOR) | Still open | Verified that the paper uses GBIF Animalia records ≤ 240 m uncertainty, capped at 1,000 per taxon tag. Grouse leakage is therefore small but non-zero. C does not restrict AlphaEarth evaluation to 2024–25. Fix: evaluate the block on 2024–25 checklists only. |
| C | Infrastructure leakage of the embedding | — | **Fixed** | Masked disc means, a trail-visibility probe and a gate (C §3.3, §3.6) answer my round-1 MAJOR. |
| C | Home advantage in the kill test | — | **Fixed** | Cross-play adopted. |
| C | Season-specific radius chosen from a 4-value set by held-out deviance, with one radius per season | LOW | New | A coarse proxy for detection channel. Its interaction with distance is captured only via $L/2$. Acceptable. |
| **D** | **Mode decomposition labels are missing not at random.** Most detections have no breeding code or comment, and unknowns get a month prior, so "visual mode" collapses toward "fall" and "aural" toward "spring". | MEDIUM | New | A mode divergence $\rho_{\text{mode}}<0.8$ may just restate the season split. D then ranks by $F+D_{\text{vis}}$, which is effectively a fall model with noisier labels. Fix: run it only on explicitly coded detections, with a count threshold (as I do). |
| D | Kill rule "> 1 bootstrap SE" | MEDIUM | New | A one-sided 1-SE rule has about a 16% false-pass rate under the null for each test, and D runs several. Fix: Holm-adjusted 95% bounds and the permutation band. |
| D | Location-derived effort covariates and the adversary | — | **Fixed** | Removed (D §0.2) |
| D | ARU as the decisive scorer | — | **Fixed** | Demoted, with coordinates verified absent |
| **E** | **Season-contrast identification assumes λ is shared between spring and fall at a footprint** ("resident and site-faithful within a year") | MAJOR | **New** | Report §1.4: young birds disperse in autumn and broods use openings. Fall density shifts toward young dense cover relative to spring. The openness term then absorbs real habitat change as "spring detectability". The fall map is biased toward wherever spring and fall *use* differ along openness, which is exactly the dense-young-cover axis hunters care about. E's T2 injection plants only a detectability truth, not a use-shift truth, so it cannot catch this. Fix: add a use-shift truth to T2 (included in my T0), or prefer fall-only. |
| E | Control-species gate with a raw Spearman < 0.6 against Ovenbird | MEDIUM | New (inherited from my round 2) | The same flaw C and D found in mine. Replace with a permutation null. |
| E | No permutation null and no within-day pairing | MEDIUM | New | Within-observer AUC across days plus naive-visit still lets C1's date and season confounds through. |
| E | Species-count proxy; feature-cube contradiction; closure overclaim | — | **Fixed** | E §0.1 |
| E | GMNF acoustic recorders still assumed usable ("may need a request") | LOW | Still open | The coordinates are verified absent. The scorer is a bonus only. |
