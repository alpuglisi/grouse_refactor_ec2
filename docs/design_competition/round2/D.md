# Design D, final: COVERT-X, a checklist encounter model that must survive matched-walk tests before it ranks a single covert

*Designer D, round 2. Primary technique: reverse brainstorming plus pre-mortem (round 1). Added this round:*
- *steelman-then-attack red-teaming of A–E;*
- *value-of-information ordering of experiments;*
- *a "make the cheater win" exercise, which built a test by asking how a cheating model would pass it.*

*Status: no repository file was edited. Facts marked **verified** were checked this round against the repository, the GBIF API, ScienceBase or the web.*

---

## 0. Changes from round 1

### 0.1 New fact
The owner already has the eBird Basic Dataset (EBD) and the Sampling Event Data (SED). Every phase of mine that existed only to wait for access is gone. The first experiments run on real complete checklists in week 1. GBIF pseudo-checklists are not used.

For the record, I checked the GBIF fields myself (GBIF API, 2026-10-05, eBird dataset `4fa7b334-…`). Rows carry `recordedBy` (an obsr ID), `eventDate` and coordinates, but `eventID`, `eventTime` and `samplingEffort` are all null. That confirms C's claim.

### 0.2 Accepted criticism, and what I dropped

| Dropped or changed | Raised by | Why I accept it |
|---|---|---|
| **Location-derived "birder-ness" covariates in the effort term** (hotspot distance, trail distance, 1 km checklist density) and the **gradient-reversal adversary** | A (MAJOR), B (MAJOR) | Correct. Remote forest has low checklist density, and grouse are densest in the north. Effort covariates tied to location would absorb real habitat signal and then delete it at prediction. The adversary would actively flatten the north woods. The effort term now sees **only covariates measured on the checklist event itself** (B's rule). Location-derived effort measures survive only as *diagnostics*. |
| My round-1 effort probe (E1, R² of the CNN logit on effort layers) as evidence | A (MEDIUM) | Correct for the same reason: a high R² can mean "habitat correlates with remoteness". It is replaced by a label-permutation negative control (§3.5), which cannot be confounded that way. |
| Subsampling to 1 checklist per 3 km × week | B (LOW) | It threw away most non-detections. I now use a cap of k = 10 per cell-week through weights (C's setting). |
| Royle–Nichols "density" language | self | eBird cannot separate density from habitat-dependent detectability, so I call the target an **encounter rate**. §3.6 then attacks the detectability problem directly instead of renaming it. |
| Presence-only stream; the disaggregation likelihood as a training term | C, self | There are too few region-years for it to shape spatial pattern, and this avoids the ecological-fallacy and circularity problems that B raised against A. NH regional rates become a held-out scorer, plus a post-hoc scalar for flushes per hour. |
| Vermont Green Mountain National Forest ARU data as a "decisive" scorer | self, verified | **I downloaded the public release** (ScienceBase item `679392d5d34e88f5864c50b5`, doi:10.5066/P13EFLXX). Its files are `drumming_model_data.csv`, `birdnet_data.csv`, `effort_data_date.csv`, `effort_data_time.csv`, an R script and metadata. They hold detections by date and time, with **no site identifier and no coordinates**. Only a bounding box is given (−73.23 to −72.74, 42.73 to 44.16). A and B both adopted this scorer from my round 1 as "coordinates unverified". It is now verified that it cannot be used without a data-sharing request to the USGS Vermont Cooperative Unit (T. Donovan). It moves from "decisive" to "requested, bonus". |
| Neural integrated SDM as phase 5 | self | One owner with one GPU. GBM ≈ CNN says capacity is not binding. A neural tower is optional and gated. |

### 0.3 Adopted, with credit

| Idea | From |
|---|---|
| Head-to-head test set HH: checklists in the status-quo CNN's own validation blocks, with a training buffer around them | **C** (B and A also adopted it) |
| Hard rule: the effort term sees only event-measured covariates | **B** |
| Within-observer AUC; drop-targeters sensitivity; repeat-visit trend check | **B** (I extend the first into a same-day, first-visit case-crossover, §3.5) |
| Cross-play ("home and away") check of home advantage | **B** |
| Zero-parameter heuristic H250 (share of a 250 m radius cut 5–20 years ago) as a mandatory baseline; ecological unit tests (fitted age peak must land at 5–20 yr) | **A** |
| Maine harvest maps HF437 (1986–2019, ≥30% basal-area removal, F1 0.72; verified by search) in the disturbance fusion | **A** |
| Building a zero-fit map *now* so the 2026 season produces field data | **A** (I do it with H250, not a 40-parameter prior; §6) |
| Importance-weighted evaluation toward all forest; rule-out map; peak window | **E** |
| AlphaEarth embeddings as a gated optional input only | **C** (gated as B proposes) |
| Fall head with shrinkage | my own; B confirmed fall detections are numerous (5,774 Sep–Dec GBIF grouse records, 2020–24) |

### 0.4 What is new in this round and not shared by any design
1. **Detection-mode decomposition.** EBD breeding/behaviour codes and species comments are parsed into *heard/drumming* versus *seen/flushed* detections. A *flush-mode* habitat function is fitted, together with a mode-divergence test that measures habitat-dependent detectability from the data instead of assuming it away (§3.6).
2. **Same-observer, same-day, first-visit case-crossover**, the primary decision metric. It cancels skill, date, weather, the year's population level and seasonal detectability exactly, and it removes preferential return to known grouse spots (§3.5).
3. **Within-stratum label-permutation negative control.** It measures how much "habitat" signal the pipeline can manufacture from effort structure alone (§3.5).
4. **Owner's blinded covert scorecard.** This is an independent, non-eBird, hunter-truth scorer that exists today. Before seeing any map, the owner (and partners) rate coverts they have hunted in past seasons (§3.7).

---

## 1. Title and pitch

**COVERT-X: rank huntable coverts by expected October flushes per hour, using eBird complete checklists. Every claimed gain must survive tests a cheating model would fail.**

All five designs now share the same core: eBird complete checklists, a separable effort term dropped at prediction, footprint pooling, a succession clock, coverts as the unit, and top-k lift as the metric. The question that separates designs is no longer *what to fit*. It is **how we would know that the fit is about grouse rather than birders, and about flushes rather than drumming**.

COVERT-X answers with four tests that a birder-geography map or a drumming-audibility map would fail:
- matched-walk case-crossover;
- label-permutation negative control;
- detection-mode divergence;
- the owner's blinded scorecard.

The model is deliberately boring: a LightGBM cloglog encounter model with a footprint stencil, fitted on one machine in hours. The product is the covert layer, with access classes and a recommender that includes a randomised arm.

---

## 2. Brainstorming record (short)

- **Round 1:** reverse brainstorm, "how could a map send hunters to the worst places with a high AUC?" (18 sabotage modes: R1 birder tracking, R2 easy negatives, R4 stale cuts, R5 pixel scale, R6 no access, R7 AUC vs top-k, R9 wrong season, R18 detectability-as-abundance, and others). Pre-mortem: 9 failure stories. These were inverted into requirements Q1–Q12. That record stands; see round1/D.md.
- **Round 2, "make the cheater win".** I listed four cheating models and the test each passes or fails:
  - **Cheater 1** learns where *good birders* walk (long forest walks by skilled observers). It passes effort-stratified AUC, because skill varies between observers. It **fails** same-observer pairs.
  - **Cheater 2** learns where people *return to known grouse spots*. It passes within-observer AUC across days. It **fails** first-visit pairs.
  - **Cheater 3** learns *where grouse are audible* (open mature woods next to young cover, roadside drumming). It passes everything on spring-heavy data. It **fails** the flush-mode subset and the mode-divergence check.
  - **Cheater 4** learns *effort geography through features* (trailhead texture in embeddings). It **fails** the label-permutation control, which shows how much structure the features can extract from effort alone.

  Every primary metric in §5 is chosen so that at least one cheater fails it.
- **Value-of-information ordering.** I ranked candidate experiments by P(result changes the next decision) ÷ cost. The cheapest decision-changing tests come first (§6).
- **Steelman-then-attack** on A–E (§9). Each idea I attacked I first restated in its strongest form, and adopted where it beat mine (§0.3).

---

## 3. The design

### 3.1 Data

| Stream | Role | Source |
|---|---|---|
| EBD + SED, ME/NH/VT, 2016–2025 | Training labels and effort | Owner's existing download. Filter (Johnston et al. 2021): complete; stationary or traveling; duration 5–300 min; distance ≤ 5 km; observers ≤ 10; one checklist per `GROUP IDENTIFIER` |
| EBD `BREEDING CODE` / `BEHAVIOR CODE` (verified to exist) and species comments (column name **to verify in the owner's header**) | Detection mode (§3.6) | Same file |
| Disturbance fusion, 1985–2026 | Succession clock | LCMS v2024-10 (GEE `USFS/GTAC/LCMS/v2024-10`); Hansen GFC v1.12 `lossyear` (GEE `UMD/hansen/global_forest_change_2024_v1_12`); HF437 Maine harvest maps (A); LANDFIRE annual disturbance (on disk); OPERA DIST-ANN-HLS (GEE `OPERA/DIST/L3_DIST-ANN-HLS/V1`, 2023–24) and DIST-ALERT for 2025–26 cuts |
| Existing 15 layers + `mch_*` | Habitat features | On EC2 (after the CR-0035 registration repair) |
| AlphaEarth annual embeddings (C) | Optional, gated (§3.5) | GEE `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`. 2025 layers are being added on a rolling basis (verified via catalog search) |
| PAD-US 4.1, state WMA/forest layers, NH Current Use recreation-adjustment parcels where obtainable, OSM/TIGER roads | Access classes, product only | https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download ; https://www.wildlife.nh.gov/current-use |
| NH Small Game Summary regional flush rates | Held-out scorer; flushes/h scalar | Owner downloads the PDF (it returned 403 to this container) |
| Owner's blinded covert scorecard and past GPX/flush waypoints, if any | Independent scorer, available now | Owner |
| Owner's 2026 hunt logs (GPX + flush waypoints) | Randomised field truth | Owner, starting this week |
| GMNF ARU site-level data | Bonus scorer | Data request (public release has no coordinates; verified) |

### 3.2 Estimand

$$
\Lambda^\star_{\text{fall}}(c,T)=e^{g(e^\star)}\;\frac{1}{|c|}\sum_{s\in c}\exp\!\big(f(x_{s,T})+\Delta_{\text{fall}}(x_{s,T})\big)
$$

This is the expected number of grouse encounters on a standard walk in covert $c$ in season $T$. The standard walk $e^\star$ is: one median-skill observer, traveling, 60 min, 2 km, 15 October, 08:00.

- Ranking depends only on $f+\Delta_{\text{fall}}$ (plus the flush-mode correction of §3.6 when it is admitted).
- Conversion to flushes per hour is a single scalar $\kappa$, fitted on the owner's logs and checked against NH regional rates. It is displayed, but it never changes the ranking.

### 3.3 Model

**Main model: LightGBM with a cloglog footprint objective.** For checklist $j$ with stencil points $t_{j1..M}$ (7 for stationary, 13 for traveling) spread over a disk of radius $\max(150\,\text{m},\ \ell_j/2)$, with stencil weights $w_{jm}$:

$$
\eta_j=g(e_j)+\operatorname{LSE}_m\big(F(x_{t_{jm}})+\log w_{jm}\big),\qquad P(y_j=1)=1-\exp(-e^{\eta_j}).
$$

- In the custom objective, the gradient for row $m$ is the checklist gradient times that row's softmax share. B checked that this is exact inside a LightGBM custom objective.
- $g$ is a penalised GAM, fitted as an offset by alternation over 3–5 rounds. **$g$ sees only:**
  - log duration and log(1 + distance), monotone ≥ 0;
  - protocol and party size;
  - start-time spline and day-of-year cyclic spline;
  - year;
  - an out-of-fold observer skill index (Kelling et al. 2015);
  - an observer random effect (≥ 20 checklists).
- **Features of $F$** (footprint-averaged at each stencil point):
  - the `diagnose_gbm_baseline.py` design (centre codes, 21-px shares, 5/21/64-px means and SDs);
  - succession-clock shares at 90/250/600 m in bins {0–4, 5–15, 15–25, 25–40, >40 yr};
  - age-class Shannon diversity;
  - disturbance severity (LCMS fast-loss probability);
  - `mch_*`;
  - elevation and Daymet winter SWE.

  All are on the template grid, with explicit `crsTransform` exports and the BUG-0094 offset probe as an acceptance gate.
- **Fall head $\Delta_{\text{fall}}$:** a depth-≤3, heavily L2-penalised LightGBM fitted on Sep–Dec checklists, with $F$ frozen as an offset.
- **Uncertainty:** 5 spatial folds × 2 seeds. Mahalanobis extrapolation flag on PCA-20 of $F$'s features (C/D).

Compute is CPU-dominant. Feature sampling for about 10⁶ checklists × 13 stencil points reuses the existing patch reader. The GPU is needed only for prediction-grid convolutions.

### 3.4 Splits

- **HH:** every EBD checklist whose start point lies in a *validation* block of the current 3 km split (`regions.py`, `SPLIT_SEED=42`, `VAL_FRACTION=0.2`; verified in the repository). Model training excludes checklists within 2.5 km of an HH block. That is the maximum stencil radius, which exceeds the CNN half-window of 0.96 km.
- **Why HH is non-negotiable (verified).** The CNN's positives are the GBIF eBird Observation Dataset (`sightings.py:20`, dataset key `4fa7b334-…`). Those are *the same detection events* as EBD detections. Scoring the CNN at an EBD checklist outside HH scores it on its own training positives. This error appears in A's T1 and E's day-1 test (§9).
- **Model selection:** 5 folds of 25 km blocks over the non-HH area (A/E). Block size is checked against the residual variogram.

### 3.5 Robustness module (pre-registered acceptance code, committed before any fit; CR-0011 A3)

**PS: preferential sampling.** There are three layers, each strictly stronger than the last.

1. **Effort-stratified AUC** on HH, within protocol × duration tercile × month × year (B, C).
2. **Same-observer, same-day case-crossover (primary decision metric).**
   - Take every HH-eligible observer-day with ≥ 2 complete checklists at locations ≥ 1 km apart, at least one of which detected grouse.
   - Conditional logit: $P(\text{detection is on checklist } j \mid \text{exactly one of the pair detected}) = \sigma\big((h_j-h_k)+(g_j-g_k)\big)$, where $h$ is the candidate habitat score and $g$ is from the frozen effort GAM.
   - Report the matched-pair concordance $\text{CC}=P(h_{\text{det}}>h_{\text{non}})$ with a block bootstrap.
   - Observer skill, date, weather, the region-year population level and seasonal detectability all cancel *exactly*. This is the case-crossover idea from epidemiology, and it extends B's within-observer AUC (which pairs across days and seasons).
3. **First-visit restriction.** Repeat CC on pairs where *both* locations are the observer's first-ever checklist at that location (personal locations; hotspots excluded in a sensitivity run). An observer cannot be returning to a spot where they already found grouse. Reputational targeting through hotspot fame is removed by the hotspot-free sensitivity run.
   - Report the share of the CC gain that survives. If less than 50% survives, preferential sampling is a large share of the gain. I will say so, and the product will badge coverts "unverified".
4. **Drop-targeters** (B): refit without observers in the top 2% of out-of-fold grouse reporting rate. Pass if the covert-ranking Spearman with the full model is ≥ 0.9.

**EL: effort leaking into habitat.**
- **Label-permutation negative control (new).** Within each stratum of observer × month × duration tercile, permute $y$ across checklists. This keeps every effort–label association and destroys any habitat–label association beyond what effort carries. Fit the full pipeline 20 times. Report:
  - the HH case-crossover CC of the permuted fits (should be 0.5; the 95th percentile is the null band);
  - the covert-ranking Spearman between permuted fits and the real fit.

  This is the *capacity of the pipeline to manufacture "habitat" from effort*. Unlike B's chickadee/jay negative controls, it cannot pass trivially. A ubiquitous species has a near-flat map and correlates with nothing, whatever the contamination.
- **Gate for AlphaEarth (C) and any added feature block:** admitted only if it raises real-fit CC on HH by more than the 95th percentile of the permuted-fit CC distribution, *and* does not raise the permuted-fit CC.
- **Diagnostics only:** share of top-5% coverts within 300 m of a hotspot or marked trail; R² of $F$ on location-derived effort layers. These are reported and never optimised, per A's objection.

### 3.6 Detectability that varies with habitat: detection-mode decomposition (new)

The unshared problem is this. Birders mostly *hear* grouse: drumming carries for hundreds of metres, and audibility is high in open mature woods next to young cover. Hunters *flush* them, and a flush is a close-range encounter whose rate depends on density in thick cover. A model fitted on spring-heavy detections can rank "where drumming is audible" (round-1 R18, cheater 3).

1. **Mode labels.** Each grouse detection gets a mode $m\in\{\text{aural},\text{visual},\text{unknown}\}$ from:
   - breeding/behaviour codes, e.g. `S`/`S7` (singing/drumming male) → aural; `FL`, `DD`, `NY`, `CF` (fledglings, distraction display, nest, carrying food) → visual;
   - a keyword rule on species comments (`drum*` → aural; `flush*`, `seen`, `on road`, `crossing` → visual; `heard` → aural);
   - month as the prior for *unknown* (Apr–May → aural).

   The size of the labelled subset is measured in week 1. I expect a few thousand labelled detections, but this is **unverified**.
2. **Mode-specific fits.** A competing-risks cloglog: $\Lambda_j=\Lambda_j^{\text{aur}}+\Lambda_j^{\text{vis}}$ with $\Lambda_j^{m}=e^{g_m(e_j)}\sum_t K_j(t)e^{F(x_t)+D_m(x_t)}$. Here $D_m$ is a shallow, shrunk mode deviation fitted on mode-labelled detections, and unknown-mode detections enter through the sum.
3. **Divergence test.** Report the covert-ranking Spearman $\rho_{\text{mode}}$ between $F+D_{\text{aur}}$ and $F+D_{\text{vis}}$ on HH coverts.
   - If $\rho_{\text{mode}}\ge0.8$, habitat-dependent detectability is small at covert scale, and $F+\Delta_{\text{fall}}$ ships.
   - If $\rho_{\text{mode}}<0.8$, the product ranks by **$F+D_{\text{vis}}+\Delta_{\text{fall}}$** (the flush-mode function). Coverts where the two disagree get an "audible, not flushable?" badge.
4. **Hunter-side check.** From the owner's logs, fit a cover-dependent hunter detection multiplier $W(s)=W_0e^{\omega\,\text{mch\_f15}(s)}$ (A's line-transect idea, B's adoption). The first season gives only a direction for $\omega$, honestly.

The visual subset carries its own artefact: grouse picking gravel on roads. A distance-to-road diagnostic is reported for $D_{\text{vis}}$. Road distance is never a feature of $F$.

### 3.7 Independent scorers available now (not eBird)

- **S0, owner's blinded covert scorecard (new).** Before any map is shown, the owner and willing partners draw ≥ 30 coverts they have hunted in past seasons and rate each on a 1–5 flush scale, plus "times hunted". The list is frozen in a committed file. Each candidate map (CNN, H250, COVERT-X) is scored by Spearman correlation with the ratings, weighted by times hunted.
  - It is small, and biased toward the owner's access patterns, but it is the only hunter-truth scorer that exists before the season ends and that no model has seen.
  - Past GPX tracks with flush waypoints, if they exist, upgrade it to a line-transect scorer.
- **S1, NH regional flush rates.** Leave-one-region-out Spearman over region-years (tiny n, directional only).
- **S2, the 2026 season** (§3.8).
- **S3, GMNF ARU sites,** if the request succeeds.

### 3.8 End product

1. **Covert layer** (GeoPackage + KML/GPX for onX, Gaia or Avenza):
   - *Objects* from three sources: disturbance patches aged 4–25 yr; SLIC segments on (age, `mch`, deciduous share); and a 25 ha hexagon background. Size 2–40 ha.
   - *Per covert:* $\hat\Lambda^\star_{\text{fall}}$ (shown as flushes/h via $\kappa$, with an 80% interval); peak window (E); access class A1 public-open / A2 open by program / A3 open by custom (Maine industrial, gate fees) / A4 unknown private / X excluded; walk-in distance; and badges for extrapolation, mode disagreement and PS-fragile ranking.
2. **Rule-out layer** (E): high effort with confidently low $\Lambda^\star$.
3. **Daily recommender:** 4 coverts by Thompson sampling over the fold ensemble, plus 1 drawn uniformly from the accessible top 30%. The randomised fifth covert gives an unbiased estimate of realised lift. A gamma–Poisson covert effect updates after each logged hunt.
4. **Regional outlook:** an NH spring drumming index where published ("bad map or bad year?").

---

## 4. Why it beats the status quo and the other designs

| Report diagnosis | Status quo | Shared core | What COVERT-X adds |
|---|---|---|---|
| The data is the ceiling (§5.4) | More capacity on TG labels | Complete checklists with effort | Same, plus proof that the new signal is not effort or targeting: case-crossover, first-visit, permutation null |
| PU and the 1−a/2 bound (§4.1, §4.4) | TG negatives | Real non-detections | Same |
| Effort bias (§5.3) | Partial cancellation | Separable effort term | Same rule (B), plus a quantified *capacity to cheat* (permutation control) |
| Preferential sampling | Not addressed | B: within-observer; A: shape priors; E: importance weights | **Same-day, first-visit case-crossover** removes skill, date, level and return-to-known-spot effects exactly |
| Detectability varies with habitat (§1.4 drumming vs flushing) | Not addressed | Spring/fall split (B, C, D-r1); hunter $W(s)$ (A) | **Mode decomposition** from EBD codes and comments; a flush-mode ranking where modes diverge |
| Stale cuts (§2.4, §5.6 Q5) | Latest LANDFIRE | Clock in A–E | Clock + HF437 + DIST-ALERT 2025–26 |
| No external truth (§5.6) | None | Field logs, ARU in 2027 | **Owner scorecard today**, randomised fifth covert this season, honest ARU status |
| Feasibility | 12 M-parameter CNN | Ranges from about 40 parameters (A) to an FCN or neural tower | LightGBM + GAM, CPU-dominant, hours per fit |

The report says that only *new information* moved the ceiling. COVERT-X adds the information *and* the tests that show it is grouse information.

---

## 5. Expected gains, with honest uncertainty

These are priors. Each number has the test that replaces it.

| Quantity | CNN (status quo) | COVERT-X | Confidence | Measured by |
|---|---|---|---|---|
| Same-day case-crossover CC on HH | 0.53–0.58 | 0.56–0.63 | Low. Pairs within one day share a region, so only within-landscape ranking is tested; that is exactly the hunter's decision, and exactly why the numbers are small | §3.5 |
| Share of the CC gain surviving first-visit restriction | — | 50–90% | Low | §3.5 |
| Effort-stratified AUC on HH | 0.62–0.70 | 0.67–0.75 | Low–medium | §3.5 |
| TkL₅ on HH (effort-expected denominator) | 1.3–1.7× | 1.6–2.3× | Low | §5.1 of round 1 |
| Permutation-null CC band (95th pct) | — | ≤ 0.52 expected | Medium | §3.5 |
| $\rho_{\text{mode}}$ (aural vs visual covert ranking) | — | 0.6–0.85, could go either way | Very low | §3.6 |
| Owner scorecard Spearman (≥ 30 coverts) | 0.1–0.4 | 0.3–0.6 | Very low. n = 30 gives SE ≈ 0.18, so only a difference ≥ 0.35 is visible | §3.7 |
| 2026 randomised arm: top-4 vs random fifth covert | — | ≥ 1.4× point estimate | Very low. About 40 visits detect only ≥ 2× (SE of log ratio ≈ 0.3); two seasons are needed | §3.8 |
| Legacy TG AUC | 0.762 / 0.770 | 0.74–0.78, not optimised | Medium | M5 |

**Gate priors** (B's practice). Each line is my probability that the gate passes:

| Gate | Prior |
|---|---|
| G1: checklist GBM beats the CNN on HH case-crossover by > 1 bootstrap SE | 0.55 |
| G2: ≥ 50% of that gain survives first-visit restriction | 0.6 given G1 |
| G3: succession clock adds ≥ 0.005 CC over the legacy features | 0.45 |
| G4: modes diverge ($\rho_{\text{mode}}$ < 0.8) | 0.4 |
| G5: AlphaEarth passes the permutation-gated admission | 0.3 |

I do **not** claim to beat the 0.77 legacy AUC. I claim a better *within-landscape* ranking of places, net of effort, which is the hunter's decision. That claim can be killed in week 1.

---

## 6. Risks, failure modes and the falsification ladder (VOI order)

| Day | Test | Data | Kill or change |
|---|---|---|---|
| 1 | **T0: ingest and count.** Filtered checklists; grouse detections by month, state and mode; same-day multi-checklist observer-days; first-visit pairs | EBD/SED | If there are < 2,000 informative same-day pairs on HH, the primary metric falls back to effort-stratified AUC, and §5 widens |
| 1 | **T1: freshness audit + H250 map + scorecard freeze** | GEE, owner | Ships a zero-fit H250 covert layer for this week's hunting (A's insight that the season is running, with the simplest possible map). The owner's scorecard is frozen *before* any map is seen |
| 2–4 | **T2: the decisive test.** Score on HH: effort-only, CNN, H250, legacy-feature checklist GBM ($F$ without the clock), using case-crossover CC, effort-stratified AUC and TkL₅. 20 permutation fits give the null band | EBD + existing features | **Kill the checklist programme** if the checklist GBM's CC is not above both the CNN's and the permutation band by > 1 bootstrap SE. What remains is H250 + product + field test. **Kill the status quo** if the CNN's CC is inside the permutation band |
| 4–6 | **T3: PS ladder.** First-visit, hotspot-free and drop-targeters runs | EBD | < 50% of the gain survives → badge as "PS-fragile"; ranking still ships |
| 5–8 | **T4: clock and mode.** Clock ablation (G3), mode decomposition (G4), fall head | EBD + GEE | Decides the ranking function |
| 6–10 | **T5: product.** Coverts, access, recommender | — | — |
| Season | **T6: field.** Randomised fifth covert; scorecard rescoring; κ fit | Owner | Product truth |
| Request | **T7:** GMNF site data; ME/VT flush tables | Agencies | Bonus |

**Risks.**

| Risk | Severity | Mitigation |
|---|---|---|
| Same-day pairs are few, or mostly hotspot hops | MAJOR | T0 measures it. Fallback to stratified AUC. Hotspot-free sensitivity run |
| Mode labels are sparse or noisy (most detections have no code or comment) | MEDIUM | Month prior; mode results are reported only above ~500 labelled detections per mode |
| The case-crossover tests within-day contrasts only, so regional ranking is untested | MEDIUM | Effort-stratified AUC, TkL and NH regions cover between-region ranking |
| Permutation fits cost 20× | LOW | GBM only, subsampled to 200k checklists; run overnight |
| Access errors | MAJOR (ethics) | A4 is never shown as open; the product is for personal use |
| New EE exports misregistered (BUG-0094 class) | MAJOR | Template `crsTransform`; `grid_mismatch`; offset probe as an acceptance gate |
| The owner's scorecard is biased toward accessible coverts | MEDIUM | Scored as a within-list ranking only; weighted by times hunted |

**Cheapest true falsification:** T2, days 2–4 on the owner's EBD.

---

## 7. Implementation plan

Each phase is one CR under `CLAUDE.md` §1. Acceptance scripts (HH definition, CC, permutation band, kill thresholds) are committed before approval (CR-0011 A3). The split follows A5: data, generator, acceptance and product are separate.

| Phase | CR | Content | Effort |
|---|---|---|---|
| P0 | CR-a acceptance | `eval_hh.py`: HH, case-crossover CC, stratified AUC, TkL, permutation harness, frozen thresholds; scorecard file format | 2 d |
| P1 | CR-b data | `ebd_ingest.py` (pandas chunked TSV; filters; zero-fill; group dedupe; first-visit flags; mode labels) → `data/checklists/*.parquet` | 2 d |
| P2 | CR-c generator | Disturbance fusion + clock shares on the template grid (GEE `crsTransform`, offset probe); H250 raster | 3–4 d |
| P3 | CR-d model | `covert_gbm.py`: custom cloglog-stencil objective, GAM alternation, fall head, mode heads, folds | 5 d |
| P4 | CR-e product | `covert_layer.py`: objects, access classes, recommender, ledger, KML/GPX | 4 d |
| P5 (optional) | CR-f | AlphaEarth block through the permutation gate; MLP tower if it beats the GBM by > 1 SE of CC | 1–2 wk |

**First experiment within a day on EC2:**
1. Run T0 counts on the existing EBD/SED files.
2. Build the HH set from `regions.py` blocks.
3. Score the current CNN (`predict.py` at checklist start points, stride 1) and H250 on HH same-day pairs and effort strata, using effort-only as the reference.
4. That alone answers whether today's map ranks places better than chance *within an observer's day*.

---

## 8. References

**Data**

- eBird Basic Dataset / Sampling Event Data: https://ebird.org/data/download ; `auk`: https://docs.ropensci.org/auk/ (breeding/behaviour code columns: verified via auk documentation; species-comments column: **unverified**)
- GBIF eBird Observation Dataset fields (no eventID, eventTime or samplingEffort): GBIF API, dataset `4fa7b334-ce0d-4e88-aaae-2e0c138d049e` (**verified**, 2026-10-05)
- Clarfeld, L.A. et al. (2025). Two-stage models improve machine learning classifiers in wildlife research: a case study in identifying false positive detections of Ruffed Grouse. USGS data release, doi:10.5066/P13EFLXX ; https://www.sciencebase.gov/catalog/item/679392d5d34e88f5864c50b5 (**verified**: files contain no site coordinates)
- LCMS v2024-10: https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10 (verified)
- Hansen GFC v1.12: https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12 (verified)
- OPERA DIST-ANN-HLS V1: https://developers.google.com/earth-engine/datasets/catalog/OPERA_DIST_L3_DIST-ANN-HLS_V1 ; DIST-ALERT: https://catalog-beta.data.gov/dataset/opera-land-surface-disturbance-alert-from-harmonized-landsat-sentinel-2-product-version-1 (verified)
- Pasquarella, V., Thompson, J. (2023). Annual Maps of Forest Harvest Events in Maine from LANDSAT Imagery 1986–2019. Harvard Forest HF437. https://harvardforest1.fas.harvard.edu/exist/apps/datasets/showData.html?id=HF437 (verified by search)
- AlphaEarth Satellite Embedding V1: https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL (verified; 2025 rolling)
- PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download (verified)
- NH Current Use: https://www.wildlife.nh.gov/current-use (verified; parcel GIS **unverified**)
- NH Fish & Game 2025 season notice: https://nhfishgame.com/2025/09/22/ruffed-grouse-and-woodcock-seasons-start-october-1/ (verified). NH Small Game Summary: https://www.wildlife.nh.gov/sites/g/files/ehbemt746/files/inline-documents/sonh/small-game-summary.pdf (exists; contents **unverified**, 403)

**Methods**

- Johnston, A. et al. (2021). *Diversity and Distributions* 27:1265–1277. doi:10.1111/ddi.13271 (**unverified** DOI)
- Kelling, S. et al. (2015). *PLoS ONE* 10:e0139600. doi:10.1371/journal.pone.0139600 (**unverified** this round)
- Maclure, M. (1991). The case-crossover design. *Am. J. Epidemiol.* 133:144–153. doi:10.1093/oxfordjournals.aje.a115853 (**unverified**)
- Guo, H. et al. (2019). PAL. RecSys. doi:10.1145/3298689.3347033 (via B; **unverified** by me)
- Lapp, S. et al. (2023). Automated recognition of ruffed grouse drumming. *Wildlife Society Bulletin* 47(1). doi:10.1002/wsb.1395 (verified by search, round 1)
- Achanta, R. et al. (2012). SLIC superpixels. *IEEE TPAMI* 34:2274–2282 (**unverified**)

**Repository:**
- `sightings.py:20` (GBIF eBird dataset key; verified);
- `regions.py:55,58` (`VAL_FRACTION`, `SPLIT_SEED`; verified);
- `diagnose_gbm_baseline.py`;
- `docs/grouse_model_report.md` §1.4, §2.3–2.4, §4.1–4.8, §5.

---

## 9. Critique of competitors

I steelmanned each design first. Each design is critiqued in its latest available version (A and B round 2; C and E round 1).

| Design | Flaw | Severity | Evidence and concrete failure scenario |
|---|---|---|---|
| **A (r2)** | **T2, the preferential-sampling injection–recovery, compares recovery of two *different* truths.** "Falsified if the GBM twin recovers truth (ii) as well as CYM recovers truth (i)." CYM recovering its own functional form proves nothing about robustness, so the test cannot fail for the reason stated | MAJOR | A §6 T2. Scenario: CYM recovers CYM-shaped truth at ρ = 0.95 and the GBM recovers GBM-shaped truth at 0.90. A reads this as "shape constraints buy robustness", when it only shows that each model fits its own family. Fix: both models on *both* truths, scored on unvisited cells |
| A (r2) | T1 runs on 25 km blocks (and on GBIF pseudo-checklists, now moot) instead of the CNN's validation blocks. The CNN is then scored on its own training positives, because GBIF EOD = EBD detections (`sightings.py:20`). That inflates the CNN | MAJOR (for the test) | Biased against CYM. It could falsely kill the premise. A uses HH only in tier 2 |
| A (r2) | Precision is capped by about 40 structural parameters, and stand age carried +0.001 under TG labels | MEDIUM (B rated it MAJOR) | A's own table expects CYM may lose in-sample to the GBM twin |
| **B (r2)** | **The negative-control species (Black-capped Chickadee, Blue Jay) cannot fail.** These species are on most checklists, so their habitat maps are nearly flat. A near-flat map correlates weakly with *any* grouse map, contaminated or not, so "ρ ≤ 0.3" passes trivially | MAJOR (the effort-leak gate is not a gate) | B §3.5 R-EL. Scenario: the grouse $f$ is 50% trail-proximity. The chickadee map is flat noise, ρ = 0.1, and B passes. Fix: within-stratum label permutation (§3.5 here) |
| B (r2) | Within-observer AUC pairs checklists across days and seasons, so seasonal detectability and year level still differ inside pairs unless $g$ is perfectly specified | MEDIUM | Same-day case-crossover removes this (§3.5) |
| B (r2) | Week-1 gates G1/T0/T1 are built on GBIF pseudo-checklists | LOW (moot now that EBD is in hand) | — |
| **C (r1)** | **AlphaEarth is the primary habitat representation, with no gate that measures infrastructure leakage** | MAJOR (B's finding; I concur) | Any 10 m embedding resolves trails. Non-detections cancel infrastructure only within the visited distribution, and prediction applies to unvisited forest |
| C (r1) | The covert "trajectory" ages the age fractions while holding the embedding fixed. The embedding already encodes the stand's current regrowth state, so +5 yr inputs are internally inconsistent and out of distribution | MEDIUM | C §3.7 item 3 admits it is a "scenario". Scenario: a 3-yr cut keeps its open-slash embedding while age says 8 yr, and the "rising" class is driven by an impossible input |
| C (r1) | "No ARU network exists in ME/NH/VT" | LOW | False: GMNF 2022–23, >9,500 h (verified). The practical conclusion still holds, because the public release has no coordinates (verified) |
| **E (r1)** | **The day-1 test scores the CNN on 25 km hex folds, so at its own training positives.** EBD detections = GBIF EOD positives (`sightings.py:20`) | MAJOR | The CNN is inflated, (a) ≈ (b), and E concludes "the current map already holds it" and kills a working programme. B also found the species-count proxy problem (MAJOR) |
| E (r1) | ρ and λ separation via repeat visits needs closure | LOW | Irrelevant to ranking |
| **D (self, r1)** | Location-derived effort covariates and the adversary; ARU scorer assumed usable | MAJOR | Fixed in §0.2 |
