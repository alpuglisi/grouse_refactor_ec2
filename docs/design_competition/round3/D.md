# Design D, final (round 3): COVERT-X, a checklist encounter model that must pass matched-walk, within-site and detection-mode tests before it ranks a covert

*Designer D, round 3 (final).*

*Techniques used across the rounds:*
- *round 1: reverse brainstorming plus pre-mortem;*
- *round 2: "make the cheater win", value-of-information ordering, and steelman-then-attack;*
- *round 3: identification-route triangulation, in which every threat to validity must be met by at least two tests that identify it through independent routes.*

*No repository file was edited. **Verified** means checked this session against the repository, the GBIF API, ScienceBase or the web.*

---

## 0. Changes from round 2

### 0.1 Responses that changed the design (details in §9)

All six critiques aimed at me in `CRITIQUES_ROUND2.md` target my **round-1** document:
- location-derived effort covariates and the adversary (A, B, C, E);
- the confounded effort probe (A);
- the ARU-dependent gate (C);
- the 1-per-cell subsampling (B);
- the non-standard grouped objective (A, E).

The first four were already fixed in round 2. The grouped objective (LOW) is now also fixed: **stage 1 uses one row per checklist**, with features averaged over a season-specific disc, exactly as C and E do. The grouped log-sum-exp objective survives only as an optional stage-2 refinement, protected by a finite-difference gradient unit test.

### 0.2 Adopted in round 3, with credit

| Idea | From | Why it beats what I had | Where |
|---|---|---|---|
| **Disturbance panel test (X2).** eBird locations birded before and after a nearby harvest, with location fixed effects | **C** | My case-crossover cancels observer and day, not fixed site traits. C's location fixed effects cancel site choice, fixed detectability and access. The two are complementary, so both are kept as independent routes against preferential sampling | §3.5, T4 |
| **Season-contrast detectability term**, with fall as reference: $\beta_{\text{seas}}^\top o_j$ on openness covariates | **E** | It gives a model-based correction where my mode decomposition only diagnosed. My mode labels now serve as an independent check on E's term | §3.6 |
| **Season-specific footprint radius** $\rho_\varsigma$ (spring drums carry far, fall flushes are close) | **C** | Cheap, fitted rather than assumed, and it sets the fall support for the product | §3.3 |
| One row per checklist; features averaged over the stencil | **C, E** | Answers the LOW critique; standard LightGBM | §3.3 |
| Fall TkL₅ as a co-primary hunter metric; "an all-season pass with a fall fail is a drumming win" | **E** | Makes the first gate hunter-relevant, not just statistically valid | T2 |
| Forest-only partial correlation for control species; Eastern Towhee as a song-detected young-forest control | **C** | Fixes the trivially passing raw-ρ control I attacked in B | §3.5 EL |
| Infrastructure-masked embedding means; AlphaEarth evaluated only on 2024–25 checklists | **C** (mask), **E** (pretraining-leak concern) | The embedding block stays optional; these are its gate conditions | §3.5 |
| AlphaEarth fresh-cut override (prototype embedding for pixels cut after the embedding year) | **C** | Coherent freshness for the optional block | §3.3 |

### 0.3 Kept as my differentiators
1. **Same-observer, same-day, first-visit case-crossover**, the primary decision metric.
2. **Within-stratum label-permutation null.** It is reinterpreted honestly in §3.5: it preserves observer geography as well as effort.
3. **Detection-mode decomposition** from EBD breeding/behaviour codes and species comments. It is now one of three independent routes on detectability.
4. **The owner's blinded covert scorecard**, an independent hunter-truth scorer that exists today.

Three items are shared, and were adopted by others from my rounds 1–2:
- effort-expected top-k lift TkL;
- access classes A1–A4/X;
- the randomised fifth covert and freshness audit.

---

## 1. Title and pitch

**COVERT-X: rank huntable coverts by expected October grouse encounters per standard hour, learned from eBird complete checklists. Every claimed gain must be confirmed by at least two independent tests that a birder-geography map or a drumming-audibility map would fail.**

All five designs share the same core: complete checklists, an event-only effort term, footprints, a succession clock, coverts and TkL. They now differ on *how they would know* the fitted habitat function is about grouse a hunter can flush, and not about where skilled birders walk, where people return to known birds, or where drumming is audible.

COVERT-X triangulates each threat:

| Threat | Route 1 | Route 2 | Route 3 |
|---|---|---|---|
| Preferential sampling | Same-day, first-visit case-crossover (mine) | Location-fixed-effect harvest panel (C) | Drop-targeters (B) |
| Effort leakage | Within-stratum label permutation null (mine) | Forest-only partial-ρ control species (C/B/E) | — |
| Habitat-dependent detectability | Detection-mode decomposition (mine) | Season-contrast term (E) | Season-specific radius (C) |

The model is deliberately plain: a LightGBM cloglog encounter model plus a GAM effort offset, fitted in hours on CPU. It produces a covert layer with access classes and a recommender that includes a randomised slot.

---

## 2. Brainstorming record (short)

- **Round 1.** Reverse brainstorm: 18 ways to send hunters to bad places with a high AUC. A pre-mortem produced 9 failure stories, which were inverted into requirements Q1–Q12 (see round1/D.md).
- **Round 2. "Make the cheater win."** Four cheating models are defined, and each test is kept only if some cheater fails it:
  - **C1** learns skilled-birder routes. It fails same-observer pairs.
  - **C2** learns return-to-known-spot behaviour. It fails first-visit pairs.
  - **C3** learns drumming audibility. It fails the flush-mode and fall checks.
  - **C4** learns effort geography through features. It fails the permutation null.
- **Round 3. Identification-route triangulation.**
  - For each threat, I listed every test in all five designs, grouped by *what it differences out*. For example, observer × day for mine, site for C's panel, observer for B's, and detection channel for E's.
  - Two tests that difference out the same thing are one route, not two.
  - I kept a threat "covered" only with ≥ 2 distinct routes. That is why C's panel and E's season term were adopted: each added a route I lacked. B's within-observer AUC was not adopted, because my same-day pairs strictly contain its route.
  - Ideas rejected this round:
    - C's embedding as a primary input: its leakage risks are unresolved (§10);
    - A's mechanistic core: precision cap and a footprint-scaling flaw (§10);
    - B's raw-ρ controls: they cannot fail (§10).

---

## 3. The design

### 3.1 Data

| Stream | Role | Source / status |
|---|---|---|
| EBD + SED, ME/NH/VT plus 10 km border strips, 2010–2025 | Labels and effort | Owner holds access. Filters (Johnston et al. 2021): complete; stationary or traveling; 5–300 min; ≤ 5 km; ≤ 10 observers; one per `GROUP IDENTIFIER`. 2010–15 is used only for the panel test |
| EBD `BREEDING CODE` / `BEHAVIOR CODE` (exist, per auk docs) and species comments (column name **to verify in the owner's header**) | Detection-mode labels | Same file |
| Disturbance fusion, 1985–2026 | Succession clock | LCMS v2024-10; Hansen GFC v1.12 `lossyear`; HF437 Maine harvests 1986–2019 (A); LANDFIRE annual disturbance; OPERA DIST-ANN 2023–24 and DIST-ALERT 2025–26 |
| Existing 15 layers + `mch_*` (after CR-0035) | Habitat features | On EC2 |
| AlphaEarth V1 annual embeddings | Optional gated block | GEE / Source Cooperative. 2025 is rolling (catalog search) |
| PAD-US 4.1, state lands, NH Current Use recreation-adjustment parcels (GIS **unverified**), OSM/TIGER | Access classes (product only) | Public |
| NH Small Game Summary regional rates | Held-out scorer; κ scalar | Owner downloads it (403 here) |
| Owner's blinded scorecard; past GPX, if any; 2026 hunt logs | Independent scorers | Owner |
| GMNF ARU site data | Bonus only | Requires a request. The public release has no site IDs or coordinates (verified) |

### 3.2 Estimand

$$
\Lambda^\star_{\text{fall}}(c,T)=e^{g(e^\star)}\,\frac1{|c|}\sum_{s\in c}\exp\!\big(F(\bar x^{\rho_{\text{fall}}}_{s,T})+\Delta_{\text{fall}}(\bar x^{\rho_{\text{fall}}}_{s,T})\big)
$$

This is the expected number of grouse encounters on a standard fall walk in covert $c$, season $T$. The standard walk $e^\star$ is one median-skill observer, traveling, 60 min, 2 km, 15 October, 08:00. $\bar x^{\rho}$ denotes features averaged over a disc of the fall detection radius plus the half walk length.

- Ranking depends only on $F+\Delta_{\text{fall}}$.
- A single scalar $\kappa$ (owner logs, checked against NH regions) converts encounters to flushes/h for display only.
- The detection-mode check (§3.6) can switch ranking to a flush-mode function.

### 3.3 Model

**Stage 1 (CPU, the decision model): one row per checklist.**
- **Season-specific footprint** (C). Checklist $j$ in season $\varsigma_j$ with distance $\ell_j$ reads features averaged over a disc of radius $r_j=\rho_{\varsigma_j}+\ell_j/2$, snapped to {60, 150, 300, 600, 1200, 2400} m. Each $\rho_\varsigma\in\{60,150,300,600\}$ is chosen by held-out deviance, per season.
- Features are computed at 13 stencil points for the checklist's own year and averaged. They include:
  - the `diagnose_gbm_baseline.py` design;
  - clock shares at 90/250/600 m in bins {0–4, 5–15, 15–25, 25–40, >40};
  - age-class Shannon diversity;
  - LCMS fast-loss probability;
  - `mch_*`;
  - elevation and Daymet winter SWE.

  Clock exports use explicit `crsTransform` on the template grid and pass the BUG-0094 offset probe as an acceptance gate.

**Likelihood:**
$$
\eta_j=F(\bar x_j)+\Delta_{\text{fall}}(\bar x_j)\mathbb 1[\varsigma_j=\text{fall}]+\beta_{\varsigma_j}^\top o_j+g(e_j),\qquad P(y_j=1)=1-e^{-e^{\eta_j}}.
$$

- **$F$:** LightGBM with a row-wise custom cloglog objective. The gradient is $e^\eta(1-y/p)$ and the Hessian is clipped. $g+\beta^\top o$ is passed as `init_score` and alternated with a GAM refit for 3–5 rounds.
- **$g$ (event-only; B's rule):**
  - log duration and log(1 + distance), monotone ≥ 0;
  - protocol and party size;
  - start-time spline and cyclic day-of-year spline;
  - year;
  - out-of-fold skill index (Kelling et al. 2015);
  - an observer random effect (≥ 20 checklists).

  **No location-derived variable** is allowed.
- **$\beta_\varsigma^\top o_j$ (E):** a season × openness interaction on footprint canopy cover, conifer share and a leaf-on flag. Fall is the reference ($\beta_{\text{fall}}\equiv0$), and the term is dropped at prediction.
- **$\Delta_{\text{fall}}$:** depth ≤ 3, strong L2, fitted on Sep–Dec checklists with $F$ frozen.
- **Capping:** ≤ 10 checklists per 3 km cell × week × detection status, applied through weights. The uncapped fit is reported alongside.
- **Uncertainty:** 5 spatial folds (25 km blocks) × 2 seeds. A Mahalanobis extrapolation flag on PCA-20 of the features.

**Stage 2 (optional, GPU).** A MIL model with the grouped log-sum-exp over stencil points, or a per-pixel MLP (E). It is kept only if it beats stage 1 by more than 1 bootstrap SE of the case-crossover concordance (§3.5) on HH. Any custom gradient must pass a finite-difference unit test before use (answering A and E, LOW).

**Optional AlphaEarth block.** It uses C's infrastructure-masked, PCA-16 disc means and C's fresh-cut override. It is admitted only through the gate in §3.5.

### 3.4 Splits

- **HH:** checklists whose start lies in a validation block of the current 3 km split (`regions.py:55,58`, `VAL_FRACTION=0.2`, `SPLIT_SEED=42`; verified).
- Training excludes checklists within 2.5 km of an HH block, which exceeds both the largest stencil radius and the CNN half-window.
- This is required because the CNN's positives are GBIF eBird detections (`sightings.py:20`, verified), i.e. the same events as EBD detections.
- Model selection uses 25 km blocks over the rest of the area. Block size is checked against the residual variogram.

### 3.5 Robustness: preferential sampling and effort leakage (pre-registered acceptance code, CR-0011 A3)

**PS route 1: same-observer, same-day, first-visit case-crossover (primary decision metric).**
- *Unit:* HH observer-days with ≥ 2 complete checklists at start points ≥ 1 km apart, of which exactly one detected grouse.
- *Statistic:* matched-pair concordance $\text{CC}=P(h_{\text{det}}>h_{\text{non}})$ of a habitat score $h$, after removing the frozen $g$ difference. It is computed as conditional-logit concordance with $g$ as an offset, with a block bootstrap.
- *What it cancels exactly:* observer skill, date, weather, the region-year population level, and the season (both sides share the season, so habitat-independent seasonal detectability cancels).
- *First-visit version:* both locations must be the observer's first-ever checklist there, so the observer cannot be returning to a spot where they already found grouse. A hotspot-free sensitivity run removes reputational targeting.

**PS route 2: harvest panel with location fixed effects (C's X2).**
- *Units:* `LOCALITY ID`s with ≥ 8 checklists before and ≥ 8 after a fused stand-replacing loss covering ≥ 10% of the 300 m disc (cut years 2005–2019).
- *Model:* cloglog with a location FE, a year FE, $g$, and age-bin × share terms.
- *Check:* within-location observed change regressed on the model-predicted change $\hat F(x_{\text{post}})-\hat F(x_{\text{pre}})$. **Pass:** slope lower CI > 0.
- *Weighting:* the 5–25-yr bins carry the weight, because a fresh cut changes visibility (C's caveat).
- Step 1 is a power count of treated units.

**PS route 3:** drop-targeters (B). Refit without the top 2% of observers by out-of-fold grouse reporting rate. Pass if covert Spearman ≥ 0.9.

**EL route 1: within-stratum label-permutation null (mine).**
- Within strata of observer × month × duration tercile, permute $y$; repeat 20 times on a 200k subsample; refit stage 1 each time.
- *Honest reading.* Permutation keeps everything the stratum carries: effort level, season and **observer geography**. An observer who birds in grouse-rich country keeps a high rate across their own checklists. So:
  - (a) on CC, permuted fits *must* sit at 0.5, because geography and observer level cancel within an observer-day. Their 95th percentile is the null band for every CC claim;
  - (b) the covert-ranking Spearman between permuted fits and the real fit measures the **"observer-geography + effort" share** of the map. It is reported, not used as a gate, because observer geography can legitimately carry regional habitat.
- **Feature-block gate.** An added block, such as AlphaEarth, must raise real-fit CC by more than the permutation band and must not raise permuted-fit CC.

**EL route 2: control species (B, E), as fixed by C.**
- Forest-only partial Spearman, controlling for TCC.
- Positive controls: Chestnut-sided Warbler and Eastern Towhee. Negative controls: Black-capped Chickadee and Blue Jay.
- Pass if partial ρ(grouse, negative) < partial ρ(grouse, positive) − margin. The margin is calibrated by a B-style injection simulation on the real EBD geometry.

**AlphaEarth gate.** All of the following must hold:
- the EL route-1 condition above;
- C's infrastructure probe: masked features predicting "within 100 m of a trail" at AUC ≤ 0.70;
- evaluation restricted to **2024–25 checklists**. E reports that AlphaEarth pretraining used GBIF occurrences from 2017–2023 (**unverified**; eBird rows may or may not have passed its uncertainty filter);
- off-trail importance-weighted TkL not worse (E).

### 3.6 Habitat-dependent detectability: three routes

The problem, with the verified figures: about 61% of eBird grouse records in ME/NH/VT fall in April–June and about 15% in September–November. Birders mostly *hear* drumming, which is audible far through open woods. Hunters *flush* birds at close range in thick cover.

1. **Season-contrast term** (E): $\beta_\varsigma^\top o$ in §3.3. Any season × openness difference, whether detection or a seasonal shift in habitat use, is pushed into spring and summer $\beta$. $F$ is anchored to fall.
2. **Season-specific radius** (C): the fall map uses the fall support $\rho_{\text{fall}}$.
3. **Detection-mode decomposition (mine).** This is an independent route, because it uses *how* the bird was detected, not *when*.
   - *Labels:*
     - breeding/behaviour codes: `S`/`S7` (drumming male) → aural; `FL`, `DD`, `NY`, `CF` → visual;
     - comment keywords: `drum*`/`heard` → aural; `flush*`/`seen`/`on road`/`crossing` → visual.

     The size of the labelled subset is counted on day 1.
   - *Fits:* mode deviations $D_{\text{aur}}, D_{\text{vis}}$ (shallow, shrunk) are fitted on mode-labelled detections against all non-detections, with $F$ frozen.
   - *Divergence:* $\rho_{\text{mode}}$ = covert-ranking Spearman between $F+D_{\text{aur}}$ and $F+D_{\text{vis}}$.
   - *Triangulation check:* if E's season term is doing its job, $F$ (fall-anchored) should agree with $F+D_{\text{vis}}$ better than with $F+D_{\text{aur}}$. **Pre-registered:** $\rho(F,F{+}D_{\text{vis}}) \ge \rho(F,F{+}D_{\text{aur}})$.
     - If it fails, the season term is not capturing the detection channel, and the product ranks by $F+D_{\text{vis}}+\Delta_{\text{fall}}$ with an "audible, not flushable?" badge.
     - Visual detections include grouse picking gravel on roads, so a distance-to-road diagnostic on $D_{\text{vis}}$ is reported. Road distance is never a feature of $F$.
4. **Hunter side.** From the owner's logs, a cover-dependent multiplier $W(s)=W_0e^{\omega\,\text{mch\_f15}(s)}$ (A). One season gives a direction only.

### 3.7 Independent scorers available now

- **S0, the owner's blinded scorecard.** Before any map is shown, the owner and partners list ≥ 30 coverts hunted in past seasons and give each a 1–5 flush rating plus times hunted. The list is committed.
  - Every candidate map is scored by weighted Spearman: CNN, H250, stage 1, and stage 1 + mode.
  - n = 30 gives SE ≈ 0.18, so only large differences show. It is the only non-eBird hunter truth available before the season ends.
  - Past GPX tracks with flush waypoints, if they exist, upgrade it to a line-transect scorer.
- **S1:** NH regions, leave-one-region-out (directional).
- **S2:** 2026 randomised slot (§3.8).
- **S3:** GMNF sites, if the request succeeds.

### 3.8 End product

1. **Covert layer** (GeoPackage + KML/GPX).
   - *Objects:* disturbance patches aged 4–25 yr, SLIC segments on (age, `mch`, deciduous share), and a 25 ha hexagon background; 2–40 ha.
   - *Per covert:*
     - $\hat\Lambda^\star_{\text{fall}}$, shown as flushes/h via κ, with an 80% interval;
     - peak window (E);
     - freshness date;
     - access class: A1 public-open, A2 open-by-program, A3 custom-open (Maine industrial; gate fees), A4 unknown private, X excluded;
     - walk-in distance;
     - top-3 TreeSHAP reasons;
     - badges: extrapolated, evidence-thin (E), PS-fragile (route 1 or 2 failed locally), and audible-not-flushable.
2. **Rule-out layer** (E): high effort with confidently low $\Lambda^\star$.
3. **Daily recommender.** Four coverts by Thompson sampling over the ensemble, plus one drawn uniformly from the accessible top 30%. The random fifth gives an unbiased realised lift.
   - A gamma–Poisson covert effect updates after each logged hunt.
   - The fit is refit after the season.
4. **Regional outlook**, from the NH drumming index where published.

---

## 4. Why it beats the status quo and the other designs

| Report diagnosis | Status quo | Shared core (A–E) | COVERT-X adds |
|---|---|---|---|
| Data is the ceiling (§5.4) | Capacity on TG labels | Checklists with effort | Proof that the new signal is grouse, via the triangulated routes in §1 |
| PU and 1−a/2 (§4.1, §4.4) | TG negatives | Real non-detections | Same |
| Effort bias (§5.3) | Partial cancellation | Event-only $g$ | Permutation null (a bound on cheating capacity) + fixed controls |
| Preferential sampling | — | B: within-observer; C: panel; E: naive-visit | Same-day, first-visit CC **and** C's panel: two routes that difference out different things |
| Detectability (§1.4) | — | E: season term; C: radius; B, D: fall head | **Detection-mode route**, which checks E's term through a different identification path |
| Stale cuts (§2.4) | Latest LANDFIRE | Clock | Clock + HF437 + DIST-ALERT 2025–26 |
| No external truth (§5.6) | None | Logs, ARU later | Owner scorecard today; honest ARU status; randomised slot |
| Feasibility | 12 M parameters | 40-parameter core to MIL nets | LightGBM + GAM on CPU in hours; GPU optional |

Why this matters for a hunter: a model that wins on effort-stratified AUC but fails same-day pairs is a skilled-birder map. One that fails the mode check is a drumming map. Either would send the owner to the wrong cover. Only COVERT-X makes both failures visible before a covert is ranked.

---

## 5. Expected gains, with honest uncertainty

| Quantity | CNN | COVERT-X stage 1 | Confidence | Test |
|---|---|---|---|---|
| Same-day case-crossover CC (HH, all seasons) | 0.52–0.57 | 0.56–0.62 | Low. Within-day contrasts are within-landscape, which is the hunter's decision, and the effects are small | T2 |
| Share of the CC gain surviving first-visit | — | 50–90% | Low | T3 |
| Permutation-null 95th pct of CC | — | ≤ 0.52 | Medium | T2 |
| Fall TkL₅ on HH | 1.3–1.8× | 1.6–2.4× | Low | T2 |
| Effort-stratified AUC on HH | 0.62–0.70 | 0.67–0.75 | Low–medium | T2 |
| Panel slope (observed vs predicted within-site change) | n/a | > 0 with P ≈ 0.55; power unknown until the count | Very low | T4 |
| $\rho_{\text{mode}}$ | — | 0.55–0.85 | Very low | T5 |
| Owner scorecard Spearman | 0.1–0.4 | 0.3–0.6 | Very low (SE ≈ 0.18) | T1/T6 |
| 2026 randomised lift (top-4 vs random) | — | ≥ 1.4× point estimate; detects only ≥ 2× in one season | Very low | T7 |
| Legacy TG AUC | 0.762/0.770 | 0.74–0.78, not optimised | Medium | — |

**Gate priors:**

| Gate | Prior |
|---|---|
| G1: CC beats CNN and the permutation band by > 1 SE | 0.55 |
| G2: ≥ 50% of that gain survives first-visit | 0.6, given G1 |
| G3: fall TkL₅ gap ≥ 0.2× | 0.5 |
| G4: panel slope > 0 with adequate power | 0.4 (joint) |
| G5: season term passes the mode triangulation | 0.55 |
| G6: AlphaEarth passes its gate | 0.3 |

**Not claimed:** beating the 0.77 legacy AUC; absolute flushes/h beyond a scalar κ; any public accuracy claim before an independent scorer (S0, S2 or S3) agrees.

---

## 6. Risks and the falsification ladder (VOI order)

| When | Test | Kill / decision |
|---|---|---|
| Day 1 | **T0.** Ingest and counts:<br>- detections by month and state;<br>- informative same-day pairs in HH (first-visit and hotspot-free);<br>- mode-labelled detections;<br>- panel treated units. | Fewer than 1,000 informative HH pairs → stratified AUC becomes primary and §5 widens. Panel underpowered → report "no claim" |
| Day 1 | **T1.** Freeze the owner scorecard. Freshness audit. H250 covert layer | The zero-fit H250 layer goes out for this week's hunts (A's insight that the season is running) |
| Days 2–4 | **T2, decisive.** On HH, score effort-only, CNN, H250 and stage 1 (legacy features, then plus clock). Metrics: CC, fall TkL₅, effort-stratified AUC. 20 permutation fits | **Kill the checklist programme** if stage 1's CC is not above both the CNN and the permutation band by > 1 SE. **Drumming-win rule (E):** if CC passes but fall TkL₅ does not beat the CNN, ship only the fall-only model, badged. **Status-quo verdict:** if the CNN's CC sits inside the permutation band, today's map has no within-landscape skill |
| Week 2 | **T3.** First-visit, hotspot-free, drop-targeters | < 50% of the gain survives → PS-fragile badges |
| Week 2–3 | **T4.** Harvest panel (C) | Slope CI ≤ 0 with adequate power → the habitat function is between-site confounded, and all coverts are badged "unvalidated" |
| Week 2–3 | **T5.** Season term, radius and mode triangulation; clock ablation | Decides the ranking function |
| Week 3 | **T6.** Product + scorecard rescoring | — |
| Season | **T7.** Randomised slot; κ fit | Product truth, accumulated across seasons |

**Risks:**

| Risk | Severity | Mitigation |
|---|---|---|
| Few same-day discordant pairs in HH | MAJOR | T0 counts them; stratified AUC as fallback; pairs pooled across all three states |
| Mode labels sparse, especially visual | MEDIUM | Report only above about 500 labelled detections per mode. The month prior is used **only** for E's term, never for mode labels (that would collapse route 3 into route 1) |
| Panel visibility change after a cut | MEDIUM | Weight on the 5–25-yr bins (C) |
| Permutation fits cost 20× | LOW | 200k subsample, CPU overnight |
| Access errors | MAJOR (ethics) | A4 is never shown as open; personal use only |
| New exports misregistered (BUG-0094 class) | MAJOR | Template `crsTransform`, `grid_mismatch` and the offset probe as acceptance gates |
| Scorecard bias toward accessible coverts | MEDIUM | Within-list ranking only |

**Cheapest true falsification:** T2, days 2–4, on the owner's EBD.

---

## 7. Implementation plan (one owner, one EC2 GPU)

Each phase is one CR, with acceptance code first (CR-0011 A3) and an A5 split.

| Phase | CR | Content | Effort |
|---|---|---|---|
| P0 | CR-a, acceptance | `eval_hh.py`: HH set, CC (plain and first-visit), stratified AUC, fall TkL₅, permutation harness, control-species partial ρ, panel harness, thresholds; scorecard schema | 2 d |
| P1 | CR-b, data | `ebd_ingest.py`: chunked pandas/polars; filters; zero-fill; group dedupe; first-visit flags; mode labels; locality panel table → `data/checklists/*.parquet` | 2 d |
| P2 | CR-c, generator | Disturbance fusion and clock shares on the template grid; H250; season-radius disc features | 3–4 d |
| P3 | CR-d, model | `covert_gbm.py`: row-wise cloglog, GAM/season-term alternation, fall head, mode heads, folds | 4 d |
| P4 | CR-e, product | `covert_layer.py`: objects, access, recommender, ledger, KML/GPX | 4 d |
| P5 | CR-f, optional | AlphaEarth via the gate; stage-2 MIL/MLP | 1–2 wk |

**First experiment on EC2 within a day:**
1. Run the P1 ingest on the existing EBD/SED files.
2. Run the T0 counts.
3. Score the current CNN (`predict.py` at checklist start points) and H250 on HH same-day pairs and on effort strata.

This answers, before any new model is fitted, whether today's map ranks places within an observer's day better than the effort-structure null.

---

## 8. References

**Data**

- eBird Basic Dataset / SED: https://ebird.org/data/download ; `auk`: https://docs.ropensci.org/auk/ (breeding/behaviour code columns verified via the docs; species-comments column **unverified**)
- GBIF eBird Observation Dataset fields (no eventID, eventTime or effort), API dataset `4fa7b334-ce0d-4e88-aaae-2e0c138d049e` (**verified** 2026-10-05). Season shares of about 61% Apr–Jun and 15% Sep–Nov were verified by E (GBIF facets) and are listed by the coordinator as established.
- Clarfeld, L.A. et al. (2025). USGS data release doi:10.5066/P13EFLXX ; https://www.sciencebase.gov/catalog/item/679392d5d34e88f5864c50b5 (**verified**: no site IDs or coordinates)
- LCMS v2024-10: https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10 (verified)
- Hansen GFC v1.12: https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12 (verified)
- OPERA DIST-ANN-HLS: https://developers.google.com/earth-engine/datasets/catalog/OPERA_DIST_L3_DIST-ANN-HLS_V1 ; DIST-ALERT: https://catalog-beta.data.gov/dataset/opera-land-surface-disturbance-alert-from-harmonized-landsat-sentinel-2-product-version-1 (verified)
- HF437 Maine harvest maps: https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF437 (verified by search)
- AlphaEarth V1: https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL (verified; 2025 rolling). The pretraining-on-GBIF claim is from E via arXiv:2507.22291 (**unverified** by me)
- PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download (verified)
- NH Current Use: https://www.wildlife.nh.gov/current-use (verified; parcel GIS **unverified**)
- NH F&G 2025 season notice: https://nhfishgame.com/2025/09/22/ruffed-grouse-and-woodcock-seasons-start-october-1/ (verified)
- NH Small Game Summary: https://www.wildlife.nh.gov/sites/g/files/ehbemt746/files/inline-documents/sonh/small-game-summary.pdf (contents **unverified**, 403)

**Methods**

- Johnston, A. et al. (2021). *Diversity and Distributions* 27:1265–1277. doi:10.1111/ddi.13271 (**unverified** DOI)
- Kelling, S. et al. (2015). *PLoS ONE* 10:e0139600 (**unverified** this session)
- Maclure, M. (1991). The case-crossover design. *Am. J. Epidemiol.* 133:144–153 (**unverified**)
- Angrist & Pischke (2009). *Mostly Harmless Econometrics*, ch. 5 (via C; **unverified**)
- Lapp, S. et al. (2023). *Wildlife Society Bulletin* 47(1). doi:10.1002/wsb.1395
- Achanta, R. et al. (2012). SLIC. *IEEE TPAMI* 34:2274–2282 (**unverified**)

**Repository**

- `sightings.py:20` (verified);
- `regions.py:55,58` (verified);
- `diagnose_gbm_baseline.py`; `diagnose_disturbance_features.py`;
- `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md` (clock +0.001 under TG labels, as cited by A, B, C and E);
- `docs/grouse_model_report.md` §1.4, §2.3–2.4, §4, §5.

---

## 9. Responses to critiques

All six critiques of D in `CRITIQUES_ROUND2.md` target my round-1 text. I verified each one before accepting it.

| Critic | Critique | Severity | Accept/rebut | Evidence or fix |
|---|---|---|---|---|
| A, B, C, E | Location-derived effort covariates (hotspot distance, trail distance, checklist density) in $g$, plus the gradient-reversal adversary, delete real habitat signal (remote north woods; E: managed WMAs) | MAJOR | **Accept** (since round 2) | These variables are constant within a location, so they are identified only by between-location contrasts, which are confounded with habitat. Fix: $g$ is event-only (§3.3); the adversary is removed; location-derived measures appear only as diagnostics. Preferential sampling is handled by within-observer-day and within-site routes (§3.5), which need no location covariate |
| A | The round-1 effort probe (R² of the CNN logit on effort layers) cannot falsify, because remoteness is habitat | MEDIUM | **Accept** | Replaced by the within-stratum permutation null evaluated on same-day CC (§3.5), where remoteness cancels within an observer-day. The map-level permutation Spearman is labelled "observer geography + effort", not "effort" |
| C | The round-1 Phase-1 gate needed the ARU Spearman, which cannot be computed | MEDIUM | **Accept** | I verified the ScienceBase files myself: no site IDs or coordinates. ARU is now a bonus scorer (S3) in no gate. The gates use HH, permutation, panel and the owner scorecard |
| B | 1 checklist per 3 km × week subsampling throws away non-detections | LOW | **Accept** | A cap of ≤ 10 per cell-week through weights; uncapped fit reported (§3.3) |
| A, E | The grouped-row log-sum-exp custom objective is non-standard and error-prone | LOW | **Accept** | Stage 1 is one row per checklist with stencil-averaged features (C, E). The grouped objective is only an optional stage 2, guarded by a finite-difference gradient unit test (§3.3) |
| (Coordinator fact) | ARU has no coordinates; the CNN is partly in-sample outside its validation blocks; 61%/15% seasonality | — | Incorporated | HH is mandatory (§3.4); detectability gets three routes (§3.6) |

---

## 10. Final critique of competitors (round-2 versions)

| Design | Flaw | Severity | New / still open | Evidence and failure scenario |
|---|---|---|---|---|
| **A** | **Footprint as a *sum* over a disc of radius 150 m + d/2, with a non-negative distance slope** (C's finding, re-verified in A r2 §3.4 O1). The expected count scales with area (29× from d = 0.5 to 4 km), while swept length scales only 8×. The model can fit long walks only by lowering $D$ where long walks go: remote big woods | MAJOR | Still open (C) | A r2 still has $\sum_{s\in B_i}D A_{\text{cell}}$ and $\alpha_2^+$. Fix: use the disc mean, or a free-sign slope |
| A | **T2 compares two different truths.** "Falsified if the GBM twin recovers truth (ii) as well as CYM recovers truth (i)." Each model recovering its own family says nothing about robustness under preferential sampling | MAJOR | Still open (mine, round 2) | A r2 §6 T2 is unchanged. Fix: both models on both truths, scored on unvisited cells |
| A | T1's falsification rule is evaluated on 25 km held-out blocks. The H subset is now *reported*, a partial fix, but the decision rule is not tied to it, so the CNN is scored partly on its own training positives | MEDIUM (down from MAJOR) | Partly fixed | A r2 §6 T1 steps 3–4 |
| A | O4 still lists the GMNF ARU release as validation data without noting it lacks coordinates | LOW | Still open | A r2 §3.4 O4 vs ScienceBase files (verified) |
| A | A blinded arm is not blind, because cuts are visible (C, E) | MEDIUM | Still open | — |
| **B** | **Negative controls (chickadee, jay) use raw ρ ≤ 0.3.** Near-flat ubiquitous-species maps pass trivially (mine). Forest-vs-nonforest contrast can also fail them spuriously (C). Either way it is not a reliable gate | MAJOR | Still open | B r2 §3.5 R-EL table unchanged. Fix: forest-only partial ρ plus a permutation null |
| B | Within-observer AUC pairs checklists across days and seasons, so seasonal detectability and the year's population level sit inside the pairs. Everything is between-site (C) | MEDIUM | Still open | B r2 §3.5 R-PS1 |
| B | All-season habitat function with only a fall head, and no detectability route. With 61% of records in Apr–Jun, a cross-play win can be a drumming win (E) | MAJOR | Still open | B r2 §3.3 |
| **C** | **Infrastructure masking at 30 m does not make AlphaEarth infrastructure-blind.** The embedding model encodes spatial context beyond the pixel, so a pixel 40 m from a trail can still carry the trail. Unmapped skid trails and log landings are not masked at all | MEDIUM | New | C r2 §3.3 item 3. The probe (AUC ≤ 0.70 for "within 100 m of a trail") is only as good as the trail map. Scenario: the block passes the probe on mapped trails while encoding unmapped logging roads, which are also where birders walk in big woods. Mitigation (adopted here): the permutation-null gate, which does not need a trail map |
| C | AlphaEarth pretraining may include GBIF eBird occurrences from 2017–2023 (E). If so, H-set gains from the block are inflated | MAJOR if true (**unverified**) | Still open (E) | Fix (adopted here): evaluate the block only on 2024–25 checklists |
| C | **The panel test can be confounded by time-varying birder behaviour.** After a cut, observers' routes change: new skid roads and log landings become walkable openings. Post-cut checklists then sample a different part of the 300 m disc, while the location FE assumes a fixed sampling footprint | MEDIUM | New | Scenario: post-cut walks follow the new haul road, where grouse feed on gravel in fall. The within-site detection rise is then partly route change and road gravel, and the slope test passes for a mixed reason. Fix: restrict to stationary checklists, or include log distance travelled × post as an effort interaction; report both |
| C | The AlphaEarth transport back-test (2019→2024, τ ≥ 0.8) checks ranking agreement, not age-response correctness | LOW | New | — |
| **E** | **The season-contrast term is linear in three openness covariates only.** Any other season × habitat interaction goes into $h$, weighted by the 61% spring majority. An example is drumming males on logs in 10–25-yr stands versus fall birds in 5–15-yr food cover, which is an age-class interaction | MEDIUM | New | E r2 §3.4. Scenario: spring-heavy fitting makes the age response peak at about 15–20 yr, while fall birds peak at about 8–12, and nothing in the openness term absorbs that. Fix (adopted here): the fall head $\Delta_{\text{fall}}$ on all features plus the mode triangulation check |
| E | The mature-forest control gate (Spearman with Ovenbird < 0.6) uses a raw correlation, so it can fail because of the legitimate forest-vs-nonforest contrast (C's point about B applies) | MEDIUM | New | E r2 §3.5 R-EL |
| E | It still lists the GMNF ARU as scorer S1 with "coordinates may need a request" | LOW | Still open | Verified: they are absent from the public files |
| E | Naive-visit (500 m) and my first-visit are the same route. I credit E with independent convergence | — | Note | — |
