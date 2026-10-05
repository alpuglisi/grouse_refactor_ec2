# Design E, round 2 (final): FLUSH-E, a fall-first, detectability-aware checklist model with a succession clock

*Designer E. The design is called FLUSH-E from here on. Primary technique in round 1: SCAMPER plus TRIZ. Added this round: red-team review, empirical probing of public APIs, and a differentiation matrix. No repository file was edited.*

**Fact basis for this round.** The owner already has eBird EBD and Sampling Event Data (SED) access. Every phase that existed only to wait for access has been removed, including my round-1 GBIF pseudo-checklist bridge. The first experiments run on real complete checklists.

---

## 0. Changes from round 1

### 0.1 Dropped

| Dropped | Why |
|---|---|
| GBIF pseudo-checklist day-1 test | The owner has EBD. A and B also rated its effort proxy (species count) **MAJOR**, and I accept that. Species count is post-treatment: it depends on the habitat being scored, and it counts the grouse itself. The same lesson carries into the production design: **nothing derived from a checklist's own species list enters the effort tower** except an observer-skill index computed out-of-fold from that observer's *other* checklists (Kelling et al. 2015, as B proposes). |
| NH flush-rate *disaggregation likelihood in training* | There are only about 4–5 NH regions × years, and the year effect absorbs most of the variance. It carries almost no within-region ranking information, so it was complexity without signal. It is kept as a **scalar calibration** (birder encounter → hunter flushes/h, the way C uses it) and as a leave-one-region-out **check**. |
| Presence-only point-process term | Complete checklists dominate it. It also re-imports effort bias. |
| Claim that repeat visits separate ρ from λ | B was right (LOW): that needs within-season closure, which eBird does not provide. Ranking never needed the split. A narrower and defensible version survives as **season-contrast identification** of *how detectability depends on habitat* (§3.4). |
| A precomputed 30 m feature cube for every year | A was right (MEDIUM): round 1 contradicted itself (36 GB/yr, yet every checklist year was needed). Now features are computed **at footprint sample points for the checklist's own year** during ingest, and full-grid features only for the prediction year (§3.6). |
| Lidar privileged-information head, FT-Transformer | Not needed for the first decision. Each stays an optional, gated phase. |
| ARU criterion based on naive occupancy | A was right (MEDIUM): with 28-day automated detection near 61% of sites (Lapp et al. 2023), occupancy saturates. The metric is now **drums detected per recorder-day** (§5). |

### 0.2 Adopted, with credit

| Idea | Source | Where |
|---|---|---|
| Observed/expected top-k lift with an effort-only expected denominator (TkL) | D | Primary metric, §5 |
| Head-to-head test set HH: checklists inside the status-quo CNN's own validation blocks | C (with B's 2 km exclusion buffer) | §5 |
| Within-observer AUC as the preferential-sampling guard | B | §3.5, §5 |
| Control-species leakage test (R-EL) | B | §3.5 |
| "Achieved ÷ oracle" AUC, so the new task's ceiling is explicit | B | §5 |
| Injection–recovery on real checklist geometry | B (method). I re-aim it at *habitat-dependent detectability*, which no one else tests | §6 T2 |
| Zero-parameter heuristic H (share of a 250 m radius in 5–20-year post-cut forest), reported everywhere | A | §5 baselines |
| Mechanism audits (age peak should land at 5–20 years; bandwidths at 100–600 m) | A | §5 |
| HF437 Maine harvest maps 1986–2019 (F1 0.72 at ≥ 30% basal-area removal) in the clock fusion | A (I re-verified the dataset) | §3.3 |
| Freshness audit of today's map (share of the top 5% cut in 2023–24 or aged past 30 years) | D (E2) | §6 T3 |
| Access classes A1–A4/X, and a randomised 5th covert per hunt day for an unbiased product-lift estimate | D | §3.7, §5 |
| GMNF acoustic recorder data (Clarfeld et al. 2025, USGS data release 10.5066/P13EFLXX; >9,500 h, 2022–2023) as an independent scorer | D (I re-verified the release; whether it includes site coordinates is **unverified**) | §5 |
| Fall-only vs all-season covert-ranking Spearman check | C | §3.4 |
| Power statement: a 1.2× field difference needs about 120 h per arm | A | §5 |

### 0.3 What stays, and is now the differentiator

1. **Fall-first estimand with season-contrast detectability.** The design is built around the empirical fact that most grouse checklist detections come from the wrong season for hunters. It keeps spring data without importing a spring-audibility map into the October product (§3.4).
2. **Naive-visit preferential-sampling test**, added on top of B's within-observer AUC (§3.5).
3. **A tabular-first, one-GPU-sized pipeline.** It is decisive within the first week on real EBD data (§6–7).
4. **A succession clock and a forward forecast**, judged honestly: under the old labels it measured +0.001 (verified in `CR-0032`), so it is *tested* under checklist labels, not assumed (§3.3).

---

## 1. Title and pitch

**FLUSH-E ranks this October's coverts by fall grouse density.** The density is learned from eBird complete checklists through a footprint likelihood with a separate, dropped effort tower. A **season-contrast term** stops the model from mistaking "grouse are easy to hear here in May" for "grouse are abundant here in October". Covariates carry a 40-year **succession clock**, aged to the hunting season.

Verified in the GBIF API on 2026-10-05: of about 43,000 eBird grouse records in ME/NH/VT for 2016–2024, roughly 61% fall in April–June and only about 15% in September–November. (B counted 5,774 fall records for 2020–24 alone.) Every checklist design trained on all seasons is therefore mostly a *drumming-audibility* model. FLUSH-E is the design that confronts this directly, and that is where it differentiates now that the core is shared.

The first decision comes within the first week on real EBD data. One gate, pre-registered and committed before fitting, asks whether checklist labels plus footprint habitat features beat the current CNN score in **fall** checklists, **within observers**, on **HH**. If they do not, the checklist programme stops, and the remaining value is the product layer and field validation.

The output is a covert list for the hunter. Each covert carries an expected flushes-per-hour index, an interval, an evidence-density badge, a peak window, freshness, access class and walk-in distance. One randomised covert per day yields an unbiased measure of lift.

---

## 2. Brainstorming record (short)

**Round 1.** SCAMPER over the nine stages, plus seven TRIZ contradictions. These converged on a single latent intensity, multiple honest observation models, a time axis and a hunter-scale output. See round1/E.md §2.

**Round 2 techniques:**

- **Red-team (attack every competitor's strongest claim; §9).** The attacks that hit *all five* designs are:
  - season and detectability confounding;
  - preferential sampling;
  - home advantage in comparisons;
  - stale covariates.
- **Empirical probing.** GBIF API facets (counts by month and state) and dataset metadata. Two results came out of it: the 61%/15% season split, and the finding that AlphaEarth's pretraining used GBIF occurrences (§9, C).
- **Differentiation matrix.** I listed the non-shared axes from ROUND2.md and scored each design 0–2 per axis. I then invested only where FLUSH-E was ≤ 1 and could reach 2 cheaply:
  - detectability → season-contrast term + injection test;
  - preferential sampling → naive-visit test;
  - first test → fall/HH/within-observer gate with a recalibrated-CNN arm.

**TRIZ, re-applied to the new contradiction** "use spring data (volume) vs avoid spring bias (validity)". Two principles resolve it:

- **#1 Segmentation:** split detection by season.
- **#23 Feedback:** let the cross-season repeats at the same places estimate the habitat dependence of spring detection.

---

## 3. The design

### 3.1 Estimand

λ(s, t) is the **relative fall (October) density of ruffed grouse in 30 m cell s, season t**. The hunter quantity for covert C is

$$F(C,t)=\kappa\cdot\tfrac{1}{|C|}\textstyle\sum_{s\in C}\lambda(s,t)\quad[\text{flushes per hour, index}].$$

- κ is a single scalar (birder fall encounter → hunter-with-dog flush rate), fitted to NH regional rates. It is shown only as a secondary label, and ranking does not depend on it.
- D's huntability factor q_C (lower in 0–4-year slash) is applied as an expert prior and is learned from hunt logs only.

### 3.2 Data

| Data | Status | Use |
|---|---|---|
| **eBird EBD + SED**, US-ME/NH/VT, 2010–present | **Owner has access** | Labels and effort. Filters follow Johnston et al. (2021): complete; Stationary or Traveling; 5–300 min; ≤ 5 km; ≤ 10 observers; one per `GROUP IDENTIFIER`. Year range: see §3.3 |
| Existing 15 layers + `mch_*`, after the CR-0035 registration repair | On EC2 | Habitat features (GBM design of `diagnose_gbm_baseline.py`, footprint-averaged) |
| Succession clock: LCMS v2024-10 (`USFS/GTAC/LCMS/v2024-10`) Change, from 1985; Hansen GFC v1.12 `lossyear` 2001–2024; HF437 Maine harvest maps 1986–2019 (doi:10.6073/pasta/20a838c4bd6922685b3d00661d45c414); LANDFIRE annual disturbance | Earth Engine / Harvard Forest archive | Age since last heavy loss (fused, with an agreement count), slow-loss/partial-cut flags, age-class shares at 90/250/600 m, age-class diversity. **Reuses the extraction code in `diagnose_disturbance_features.py`**, which already computes `lcms_ys_removal`, `lcms_rm20_r250`, `gfc_ys_loss` and similar features at points |
| "Openness" covariates for the detection-season term: TCC, LANDFIRE canopy cover, conifer share, all at the footprint | On EC2 | §3.4 |
| NH Fish & Game regional flush/observation rates | Public PDF (403 to this container; the owner downloads it) | κ and the leave-one-region-out check |
| GMNF acoustic recorder data (Clarfeld et al. 2025) | Public data release; coordinates may need a request | Independent scorer S1 |
| PAD-US 4.x, OSM tracks/gates, TIGER | Public | Product only |
| Owner GPS hunt logs (track + flush waypoints) | Owner | Held out in season 1; gold-standard scorer |

### 3.3 Checklist footprint likelihood

For checklist j at start point x_j, year t_j, day-of-year d_j, outcome y_j:

$$P(y_j=1)=1-\exp\!\Big(-\exp\big[g(e_j)+\beta_{\text{seas}(j)}^{\top}o_j\big]\cdot\textstyle\sum_s K_j(s)\,\lambda(s,t_j)\Big).$$

The terms are:

- **K_j, the footprint.** A Gaussian of σ = √(150² + (0.35·dist_j)²) m, truncated at 3σ (B's form). Hotspot pins get an extra location-error term fitted on held-out deviance.
- **g(e_j), the effort tower.** It takes log duration, log(1 + distance), number of observers, protocol, a time-of-day spline, a year factor and the out-of-fold observer-skill index. It has a cyclic day-of-year spline. **It includes no location-derived variable**: no hotspot distance, trail distance or checklist density. That is the lesson from my critique of D (§9). It is monotone (softplus slopes) in duration and distance.
- **β_seas·o_j, the season-contrast detectability term.** See §3.4.
- **log λ(s, t) = h(Z(s, t)), the habitat function**, where Z contains the clock, composition and structure features *as of year t*. This is the only part kept at prediction.

**Years.** Checklists from 2016 onwards. The clock layers are annual, so every year is usable. For non-annual layers (LANDFIRE, TreeMap), the nearest vintage is used and the vintage gap is recorded as a feature *of the effort tower only*. Sensitivity run: 2020+ only.

**Implementation, stage 1 (CPU, days).** A cloglog GBM with an offset, using LightGBM's custom objective. The gradient and Hessian are closed-form in η, as D derives in §3.4(a).

- g and the season term are fitted as a GLM/GAM offset, alternated with boosting h, for 3–5 rounds.
- **The footprint average is handled before fitting**: features are averaged over 16 stencil points per checklist, on the GBM-on-kernel-mean approximation. This avoids D's non-standard grouped-row objective. Stage 2 removes the approximation.

**Implementation, stage 2 (one GPU, only if it beats stage 1 on the gate).** A PyTorch MIL model:

- the habitat MLP h is evaluated at M = 32 points sampled from K_j;
- Σ K λ is the Monte-Carlo mean inside the exp;
- g and the season term are small linear/spline modules.

### 3.4 Season-contrast identification of habitat-dependent detectability

**Problem.** In April–May, drumming is heard at roughly 100–300 m (**unverified range**). It carries farther through open, leaf-off hardwood than through dense conifer. In October, detection is mostly visual or flush-based within tens of metres. If the model fits all seasons with a single detection-habitat structure, h absorbs "drumming carries well here" as "grouse abundant here". The result is a ranking tilted toward open mature hardwood beside young cover, which is a different covert from the dense young stand a hunter wants.

**Mechanism.** Ruffed grouse are resident and site-faithful within a year (report §1.5). So for a footprint visited in both spring and fall of the same year, λ is shared, and any *habitat-dependent* difference in detection rates across seasons belongs to detection.

Model this as a season-specific linear term on a small vector of openness covariates o_j: footprint canopy cover, conifer share and the leaf-on flag. Fall is the reference season, β_fall ≡ 0, and spring and summer get free β. This term is identified only by the season contrast. h cannot absorb it, because h has no season input. At prediction, the term is set to fall (zero), so the map is the fall-detection-scale density.

**What this does not identify.** It does not separate fall detectability from fall density. A hunter's flushes share that confound, since hunters also detect by flush, so this is arguably the right target.

**Guards:**

1. *Fall-only model.* A model fitted only on September–November checklists (about 5.8k detections for 2020–24 per B's count, plus 2016–19 and 2025) must agree with the full model's covert ranking at Spearman ≥ 0.7 (C's check). If it does not, **ship the fall-only model**.
2. *Injection–recovery test T2* (§6). Plant a synthetic species whose spring detectability rises with openness while its density peaks in dense young stands. Show that the naive all-season model inverts the ranking and that the season-contrast model recovers it, on the real checklist geometry.
3. *Hunt logs* (§5) are the final arbiter.

### 3.5 Preferential sampling and effort leakage

Three tests are pre-registered and committed as acceptance code before any fit (CR-0011 A3):

- **R-PS1, within-observer AUC** (B). Pairs of HH checklists from the same observer, same protocol and same effort tercile.
- **R-PS2, naive-visit subset (new).** Keep only the **first** checklist each observer ever submits within 500 m of a location. That observer could not have been drawn there by their own earlier grouse experience at that place. If the habitat model's advantage on naive visits is less than half its advantage on all visits, observer-level targeting is inflating the gain, and the product is badged accordingly.
  - Residual risk: location-level selection, such as a known "grouse trail" that is popular because of grouse. R-PS3 addresses it.
- **R-PS3, drop-targeters plus a hotspot vs personal-location split.** Exclude observers whose out-of-fold grouse rate is in the top 1% (B). Compare a model fitted on personal locations only with one fitted on hotspots only.
- **R-EL, control species** (B). Run the identical pipeline for two non-grouse forest birds with different habitats (e.g. Ovenbird, a mature-forest species, and Chestnut-sided Warbler, an early-successional species). Grouse λ must not correlate more strongly with *either* control's λ than the published habitat overlap implies. A pre-registered threshold is that the Spearman with the mature-forest control must be below 0.6.
  - The early-successional control is expected to correlate. It is a *positive* control: if it does not correlate, the clock features are broken.

### 3.6 Feasibility (one owner, one EC2 GPU)

- **Ingest.** The EBD for ME/NH/VT, filtered, is about 10⁶ checklists (**estimate**). Filter with pandas in chunks to Parquet. CPU, under an hour.
- **Features.** 16 stencil points × about 1M checklists = 16M point reads per feature, for the checklist's own year:
  - existing rasters: windowed rasterio reads on EC2;
  - clock: per-year int8/int16 rasters exported once on the template lattice, with an explicit `crsTransform` and the BUG-0094 offset probe, per the PA list.

  This takes hours on CPU and stores about 16M × 150 features × 2 B ≈ 5 GB. There is no full cube.
- **Prediction.** One year at a time over forest pixels: features are computed per tile with a 600 m halo, then h is applied. Hours.
- **GPU.** Used only in stage 2. Minutes per epoch.

### 3.7 End product: the covert card

1. **Polygons.** Connected components of the fused disturbance stack (age 4–25 years at season t), plus SLIC on shrub-wetland and aspen-birch cover, plus a 25 ha hex lattice over remaining forest (D). Size range 2–40 ha.
2. **Per-covert attributes:**
   - F index and 80% ensemble interval;
   - **evidence density** (held-out-style count of checklist hours within 2 km). Low evidence means the ranking relies on extrapolation, and the card says so;
   - **peak window** (the years in which most of the polygon is 5–20 years old);
   - **freshness** (last disturbance-product year);
   - access class A1–A4/X (D);
   - walk-in distance;
   - the top-3 TreeSHAP reasons.
3. **Daily recommender.** Four coverts by Thompson sampling plus one randomised covert drawn from the accessible top 30% (D). Logged hunts are held out in season 1 and become training data afterwards.
4. **Formats.** GeoPackage and KML/GPX for phone apps, plus a static Leaflet page.
5. **Refresh.** Every September, with new loss years.

---

## 4. Why it beats the status quo, and the other four

**Against the status quo**, see the round-1 table, which still holds:

- Non-detections with effort remove the positive–unlabelled problem and the 1 − a/2 bound.
- Effort is modelled and dropped.
- The footprint replaces the centre-pixel label.
- The estimand is fall density, not a reporting contrast.
- The clock replaces the stale vintage.

**Against A, B, C and D** (the shared core is equal), FLUSH-E wins on the axes ROUND2.md names:

| Axis | FLUSH-E | Others |
|---|---|---|
| First test truly falsifies | Real EBD, day 2–5. HH, fall only, within-observer. The CNN arm gets the *same* checklist recalibration (a spline of its score plus the same g), so it has no home disadvantage (§6 T1) | B's cross-play is strong but was built on pseudo-checklists; A's first act is a field test of an un-fitted prior map |
| Habitat-dependent detectability | Identified across seasons; injection-tested; fall-only fallback | A, B, C, D accept it as a risk, or use a fall head with no identification argument |
| Preferential sampling | Within-observer + **naive-visit** + drop-targeters + hotspot/personal split | B has the first and third; the others are weaker |
| Effort tower purity | No location-derived inputs | D puts hotspot, trail and density distances into effort (§9) |
| Feasibility | GBM first, MIL net only if it wins; no cube | B dropped its FCN; A's NUTS on convolutions is heavy; C's 560-feature AEF disc means are EE-expensive |
| Honesty | Gate probabilities given (§5); the clock's +0.001 history stated | — |

---

## 5. Expected gains, and how not to fool ourselves

### 5.1 Evaluation set-up

**Folds.** Five spatial folds of 25 km hexagons. The size is checked against the residual variogram. Also HH (C, with B's 2 km exclusion) and a temporal hold-out (train ≤ 2023, test 2024–25).

**Arms, all with the same g and season term:**

- effort-only;
- recalibrated CNN score (spline);
- A's heuristic H;
- FLUSH-E stage 1 without the clock;
- FLUSH-E stage 1 with the clock;
- stage 2.

**Metrics:**

1. **TkL₅ in fall checklists (primary).** Observed ÷ effort-only-expected detections among checklists whose footprint lies in the top 5% of forest (D's form).
2. Effort-stratified AUC and within-observer AUC, all seasons and fall only, with achieved ÷ oracle (B).
3. Naive-visit AUC (R-PS2).
4. Independent scorers:
   - S1 GMNF recorders: Spearman of the site drum rate per day against λ;
   - S2 NH leave-one-region-out;
   - S3 the owner's hunt logs, comparing the randomised 5th covert with the recommended 4.
5. Mechanism audits (A): the age effect peaks at 5–20 years; the 250 m age-class shares matter more than the centre cell.
6. Legacy TG AUC, for continuity only.

### 5.2 Expected values (priors, to be replaced by measurements)

| Quantity | Expected | Confidence |
|---|---|---|
| Fall TkL₅: recalibrated CNN → FLUSH-E stage 1 | 1.3–1.8× → 1.6–2.4× | Low |
| Effort-stratified AUC on HH (all seasons) | 0.62–0.70 → 0.67–0.75 | Low–medium (direction per Johnston et al. 2021) |
| Share of the gain surviving within-observer / naive-visit | 50–80% / 40–70% | Low |
| Clock adds ≥ 0.01 AUC or ≥ 0.1 TkL₅ under checklist labels | Probability 0.45 (it added +0.001 under target-group labels, verified in `CR-0032`) | — |
| Stage 2 beats stage 1 by ≥ 0.01 | Probability 0.25 | — |
| Fall-only vs all-season covert Spearman | 0.6–0.85. Below 0.7, the fall-only model ships | Low |
| Field lift, recommended vs randomised covert | 1.3–2×. Detecting 1.5× needs about 40 h per arm; detecting 1.2× vs the CNN needs about 120 h per arm (A), i.e. 2+ seasons | Medium for direction, low for size |
| Legacy target-group AUC | 0.74–0.79, not optimised | — |

**Guards:**

- metrics, folds, HH and thresholds are committed before fitting;
- paired block bootstrap;
- differences below 0.015 AUC or 0.1 TkL are ties;
- the CNN is re-scored with the same `predict.py` at the points, after the CR-0035 repair, for both arms.

---

## 6. Risks, failure modes and falsification, in run order

| Test | When | What | Kill / decision |
|---|---|---|---|
| **T1, the label-and-habitat gate** | Days 2–5 | On HH and fall checklists: FLUSH-E stage 1 (no clock) vs recalibrated CNN vs H, all with the identical g and season term. Within-observer and naive-visit versions included | **Kill the checklist programme** if stage 1's fall TkL₅ is not ≥ 0.2 above the recalibrated CNN's (CI excludes 0) *and* within-observer AUC is not ≥ 0.015 higher. A pass on all-season but a fail on fall means the gain is drumming; ship nothing until the fall-only model passes |
| **T2, detectability injection–recovery** | Days 2–4, in parallel | On the real EBD geometry and effort, plant (i) a species with spring audibility ∝ openness and density peaking in young dense cover, and (ii) a no-detectability-bias control | The season-contrast term must recover truth (i) at Spearman ≥ 0.15 better than the naive model, and must not hurt (ii) by more than 0.02. Otherwise drop the term and use the fall-only model |
| **T3, freshness audit** (D's E2) | Day 1 | Share of today's top 5% cut in 2023–24 or older than 30 years in 2026 | No kill. Sizes the value of the clock to the product |
| **T4, clock ablation** | Week 2 | Stage 1 with vs without the clock on HH and fall | If below the §5.2 tie thresholds, the clock stays in the *product* (freshness, peak window) but is not claimed as a precision gain |
| **T5, R-EL and R-PS** | Week 2 | Control species; naive visits; targeters | Fails → coverts badged "effort-sensitive" and the issue investigated before release |
| **T6, independent scorers** | When obtained | S1, S2 | Decisive for any public claim |
| **T7, field season** | Oct–Nov | Randomised 5th covert | Product truth |

**Main risks:**

| Risk | Severity | Response |
|---|---|---|
| Fall detections are too few for a stable fall model | MEDIUM | About 5.8k in 2020–24 alone, plus other years. Shrink the fall-only model toward the full model |
| The season term is mis-specified (an openness proxy that misses audibility) | MEDIUM | T2; fall-only fallback |
| Location-level preferential sampling (grouse trails) | MAJOR | R-PS3; hunt logs decide |
| Partial harvests are invisible to the clock | MEDIUM | LCMS slow loss; HF437 in Maine; Meta CHM 1–5 m share |
| Misregistration in new exports | MAJOR (repeat of BUG-0094) | Template `crsTransform`; offset probe; acceptance gate |
| QMS overhead | Process | One CR per phase, gate code first (CR-0011 A3/A5) |

---

## 7. Implementation plan

| When | Work | Compute |
|---|---|---|
| **Day 0** | Commit the acceptance CR: `eval_flush_e.py` (HH, folds, TkL, within-observer, naive-visit, control-species, thresholds). Email the USGS VT Coop Unit (GMNF coordinates), NH F&G, ME IF&W, VT F&W | — |
| **Day 1** | `ebird_checklists.py`: EBD + SED to Parquet, filters, zero-fill, group dedup, out-of-fold skill index, footprints. Volume report (checklists, detections by month). T3 freshness audit | CPU, about 2 h |
| **Days 1–3** | Stencil features (existing layers via the patch reader; clock via `diagnose_disturbance_features.py`-style export on the template lattice) | CPU, hours |
| **Days 2–5** | Stage-1 cloglog GBM with the g/season offset; **T1** and **T2** | CPU |
| **Week 2** | T4, T5; fall-only model; variogram check | CPU |
| **Week 3** | Covert polygons, access, recommender, cards; season-2026 product with badges | CPU |
| **Weeks 4–6 (gated)** | Stage-2 MIL net; optional AlphaEarth *with* the leakage guard (§9 C); lidar understory | GPU |
| **Oct–Nov** | Field season with the randomised arm; hunt logs held out | — |

**The first experiment the owner can run within a day** is the Day-1 ingest plus the T1 gate on a 200k-checklist subsample (all detections plus a random 1:10 sample of non-detections, with case-control weights). It uses the existing 15 layers only, and returns a go/no-go for the whole checklist programme by about day 3.

---

## 8. References

URLs were checked this session unless marked **unverified**.

- GBIF eBird Observation Dataset (EOD), CC-BY 4.0, `datasetKey 4fa7b334-ce0d-4e88-aaae-2e0c138d049e`. API checked 2026-10-05: no `eventID` or effort fields. Grouse (`taxonKey 2473702`) month facets ME+NH+VT 2016–2024 total 43,024. https://api.gbif.org/v1/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e
- Johnston, A. et al. (2021). Analytical guidelines to increase the value of community science data. *Diversity and Distributions* 27:1265–1277. https://doi.org/10.1111/ddi.13271
- Kelling, S. et al. (2015). Can observation skills of citizen scientists be estimated using species accumulation curves? *PLoS ONE* 10:e0139600. https://doi.org/10.1371/journal.pone.0139600 (via B)
- `auk` / zero-filling: https://docs.ropensci.org/auk/reference/auk_zerofill.html
- Royle, J.A. & Nichols, J.D. (2003). *Ecology* 84:777–790. https://pubs.usgs.gov/publication/5224229
- Lapp, S. et al. (2023). Automated recognition of ruffed grouse drumming in field recordings. *Wildlife Society Bulletin* 47(1). https://doi.org/10.1002/wsb.1395
- Clarfeld, L.A. et al. (2025). Two-stage models … Ruffed Grouse, GMNF Vermont 2022–2023. USGS data release, doi:10.5066/P13EFLXX. https://www.usgs.gov/data/two-stage-models-improve-machine-learning-classifiers-wildlife-research-a-case-study
- Pasquarella, V., Thompson, J. et al. (2023). HF437 Annual Maps of Forest Harvest Events in Maine 1986–2019. https://doi.org/10.6073/pasta/20a838c4bd6922685b3d00661d45c414
- LCMS: https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2022-8 (the page points to v2024-10); Hansen GFC v1.12: https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12
- AlphaEarth Foundations, arXiv:2507.22291. Its training data includes GBIF occurrence records (Animalia, CC-BY/CC0, 2017–2023, ≤ 240 m uncertainty) per the paper as summarised in search results. https://arxiv.org/abs/2507.22291
- NH Fish & Game, Ruffed Grouse Wing and Tail Survey: https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey (403 on fetch; figures from search snippets, **unverified**)
- Lucas/Nandi et al. (2023), `disaggregation`, *J. Stat. Softw.* 106(11). https://jstatsoft.org/index.php/jss/article/view/v106i11 (kept for the κ calibration rationale)
- PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview (**unverified** URL)
- Repository: `docs/grouse_model_report.md`; `docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md:22-25` (harvest history +0.001, GEDI +0.000, Meta CHM +0.009); `diagnose_disturbance_features.py`; `diagnose_gbm_baseline.py`; `docs/quality/PREVENTIVE_ACTIONS.md` (PA-0017, PA-0020, PA-0032 on acquisition, domain and registration).

---

## 9. Critique of competitors

| Design | Strongest flaw | Severity | Evidence / failure scenario |
|---|---|---|---|
| **A: CYM** | **The core is a roughly 30-parameter mechanistic density with ordered guild priors and a log-normal age hump.** Where the ecology departs from the prior, the structure cannot learn it from about 10⁶ checklists. Examples: north-Maine spruce–fir regeneration, alder and shrub wetlands, old fields. | MAJOR | The guild ordering puts spruce–fir and pine–hemlock at the bottom (A round 1 §3.3). Scenario: dense spruce–fir regeneration after budworm salvage holds birds, but the multiplier is penalised toward the bottom, so those coverts rank low. A's round-2 residual δ is gated and ridge-shrunk, so it is unlikely to recover the miss. A's first field test also scores an *unfitted* prior map, so a null result cannot tell "bad prior" apart from "bad idea". |
| A (second) | A blinded three-arm field test is not really blind. Hunters can see young cuts. | MEDIUM | Expectation effects on effort and attention. Use D's randomised arm and count-based endpoints instead. |
| **B: CEM-X** | **Its decisive first test (label-swap cross-play T1) was built on pseudo-checklists.** Now that the owner has EBD, T1 moves to the EBD stage, but its habitat models stay all-season, with only a "fall head". There is no identification argument for habitat-dependent detectability, so a cross-play win may be a drumming-audibility win. | MAJOR | Verified: about 61% of grouse records fall in April–June and about 15% in September–November (GBIF facets 2016–24). Scenario: CEM wins HH on spring checklists and ranks open mature hardwood next to cuts above the dense young stand. B's own R3 says detectability is "not separable", which FLUSH-E disputes via the season contrast. |
| B (second) | 3 km blocks, with footprints up to σ ≈ 1.8 km at 5 km distance, cause many straddling footprints to be dropped. That biases evaluation toward short checklists. | MEDIUM | B round 1 §3.4. Mitigated by its variogram check. |
| **C: FLUSH-C** | **AlphaEarth embeddings, C's primary habitat input, were pretrained with GBIF occurrence records** (Animalia, CC-BY/CC0, 2017–2023). eBird's GBIF dataset is CC-BY 4.0 human observation (checked via the GBIF API). The embeddings may therefore encode where birds, including grouse, were *reported*. | MAJOR. It would be BLOCKING for C's H-set comparison if eBird rows passed AEF's ≤ 240 m uncertainty filter. eBird rows carry no `coordinateUncertaintyInMeters`, so whether they passed is **unverified** | Scenario: held-out-block grouse checklists from 2017–2023 informed the embedding, so H-set AUC is inflated and AEF wins the ablation spuriously. Fix: evaluate AEF only on 2024–25 checklists, or on independent scorers. |
| C (second) | It pruned acoustic recorders ("no ARU network exists in ME/NH/VT"). | MEDIUM | Wrong: the GMNF VT release (Clarfeld et al. 2025, >9,500 h) exists, as D found. |
| **D: COVERT** | **The effort tower takes location-derived variables (distance to hotspot, distance to trail, checklist density within 1 km) and fixes them to "non-hotspot forest" at prediction.** A gradient-reversal adversary also stops f from predicting checklist density. | MAJOR | These variables are constant across all checklists at a location, so they are identified only by *between-location* contrasts, which are confounded with habitat. Scenario: managed young-forest WMAs attract birders (high checklist density, trails). Their habitat signal is credited to "effort" and then removed, or suppressed by the adversary. The best public coverts then rank down. |
| D (second) | The LightGBM grouped-row disk objective is non-standard. | LOW | Chain rule works, but it is error-prone. FLUSH-E averages features over the stencil in stage 1 instead. |
| **All (including E round 1)** | All-season training without a detectability identification argument; preferential sampling only partly tested | — | Addressed in FLUSH-E by §3.4–3.5, T1 (fall and naive-visit) and T2 |

**Responses to critiques of FLUSH-E:**

| Critique | Verdict |
|---|---|
| Species-count effort proxy (A and B, MAJOR) | Accepted. The test is dropped, and the lesson is carried into the effort tower (§0.1) |
| Naive-occupancy saturation of the acoustic metric (A, MEDIUM) | Accepted. Drum rate per recorder-day is used instead |
| Feature cube contradiction (A, MEDIUM) | Accepted. Features are computed at stencil points (§3.6) |
| ρ/λ closure overclaim (B, LOW) | Accepted. Replaced by the narrower season-contrast claim |
