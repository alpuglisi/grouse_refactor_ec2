# Design B: Checklist Encounter Model (CEM)

**Ad-tech exposure towers, epidemiology's test-negative controls and fisheries CPUE standardisation, applied to eBird complete checklists, to map grouse encounters per hour hunted**

*Designer B, round 1. Primary technique: analogical transfer. No repository file was edited.*

---

## 1. Title and pitch

**Pitch.** Today the model answers a question no hunter asks: "does this landscape look more like places where grouse get reported than places where birders report other birds?" (report §5.1). Its ~0.77 AUC ceiling comes from that framing (§5.4). The negatives are unverified. Effort is unobserved. The denominator, $q_{\mathrm{TG}}$, has its own habitat structure. And the label sits on a point, even though the observation was a walk. At least four other fields have solved this same structural problem, and each was solved the same way:

- online advertising (position bias);
- recommender systems (implicit feedback);
- vaccine epidemiology (care-seeking bias);
- fisheries (catch per unit effort).

The common fix: **record the exposure event itself, including the events where nothing was found. Model exposure in its own factor. Delete that factor at inference.**

For grouse, the exposure event is the **eBird complete checklist**: a walk of known start point, duration, distance, time of day, date, party size and observer, on which grouse were or were not reported. CEM is trained on those checklists. It uses a complementary log-log hazard link with two separable towers:

- a **habitat tower** $f(x)$, which is today's GrouseResNet trunk run fully convolutionally over the landscape;
- an **effort tower** $g(e)$, the analogue of PAL's position tower.

A **footprint integral** spreads each checklist's label over the cells the walk could have covered; this is multiple-instance pooling. At inference, $g$ is fixed to "one average hunter, 60 minutes, 2 km, a mid-October morning". The output is a **standardised encounter rate**: the probability, and the expected number, of grouse encountered per standard hour on foot in each covert. That is the quantity a hunter cares about, and it can be checked against the state agencies' flushes-per-hour figures.

Two more transfers protect the claim from self-deception:

- an **injection–recovery test** from astronomy proves that the pipeline recovers a known synthetic species under the real effort geometry;
- **capture-efficiency curves** from mineral prospectivity score the map on hunter terms: the share of held-out encounters found in the top k% of huntable forest.

---

## 2. Brainstorming record

### 2.1 Technique 1: analogical transfer (primary)

**Step A: abstract the problem.** First I removed everything grouse-specific. The structural problem is this:

> A rare, cryptic "event" (a grouse report) is observed only where and when an uncontrolled, self-selected agent (a birder) chose to look, with variable intensity (effort, skill). Non-observations are not recorded as such in our pipeline. We want a ranking of *locations* by true event propensity, robust to where the agents chose to look.

**Step B: list fields with the same structure, and take the best trick from each.** I list 11 fields, more than the 8 required.

| # | Field | Their version of the problem | Best trick (real method) | Direct transfer to grouse |
|---|---|---|---|---|
| 1 | **Ad click-through with position bias** | A click happens only if the ad is *seen* (position) and *liked* (relevance) | **PAL** (Guo et al., RecSys 2019): $p(\text{click})=p(\text{seen}\mid\text{pos})\cdot p(\text{click}\mid\text{seen},\text{item})$. The two towers are trained jointly and the position tower is **dropped at serving**. They report +3–35% CTR/CVR online. **IPS/unbiased LTR** (Joachims et al., WSDM 2017) re-weights by examination propensity. | $p(\text{report})=$ effort/detection tower × habitat tower. Drop the effort tower at prediction. This is the neural form of the report's §4.8 "nuisance covariate set to a constant", with a hard architectural guarantee that habitat and effort cannot interact. |
| 2 | **Recommender systems, implicit feedback** | A non-click is not dislike; the user may never have been *exposed* | **ExpoMF** (Liang, Charlin, McInerney & Blei, WWW 2016) makes exposure a latent variable. | Our TG negatives are "non-clicks" with *unknown* exposure to grouse. Replace them with records whose exposure is *observed*: complete checklists. |
| 3 | **Epidemiology: vaccine effectiveness** | Cases are found only among people who seek care; care-seeking is confounded with exposure | **Test-negative design** (Jackson & Nelson 2013): controls are care-seekers who *tested negative*, so care-seeking behaviour cancels by design. | The controls are **checklists that did not report grouse**. They are walks by the same people, on the same platform, with the same "test" (a birding session), so birding behaviour cancels. Today's controls are *other-species records*, whose locations are habitat-structured by those species' habitats (report §2.3: "$q_{\mathrm{TG}}$ is itself habitat-structured"). |
| 4 | **Epidemiology of under-reported disease** | Surveillance captures a varying fraction of cases | Multi-source capture–recapture; hierarchical models in which a small planned survey anchors a large opportunistic one (Dorazio 2014). | Optional third component: incomplete-checklist and GBIF presence-only records as a thinned point process, sharing $f$ (integrated SDM, report §4.2). |
| 5 | **Fisheries stock assessment** | Catch depends on fish abundance *and* on fishing effort, vessel and gear | **CPUE standardisation** (Maunder & Punt 2004): GLM/GAM with effort offsets and vessel effects, predicted at a *standard* vessel and effort. | **Standardised encounter rate.** Duration and distance enter as exposure offsets and the observer acts as a "vessel effect". Predict at a standard hunter-hour. Agency **flush rates per hour** (NH Fish & Game wing-and-tail survey) are literally grouse CPUE, which gives an external check. |
| 6 | **Astronomy, selection-biased catalogues** | Faint objects are missed; catalogue completeness varies across the sky | **Injection–recovery** (Christiansen et al., Kepler): inject synthetic signals into real data, run the real pipeline, measure the recovered fraction. | Inject a **synthetic species** with a known habitat function $f^\*$ into the *real* checklist effort geometry. Run both today's TG pipeline and CEM, and measure which one recovers $f^\*$. This tests the estimand claim before any real-data argument. |
| 7 | **Mineral prospectivity mapping** | Known deposits are positives and everything else is unlabelled (PU); exploration budgets go to the top-ranked area | **Success-rate / prediction-rate curves** (Chung & Fabbri 2003): cumulative share of held-out deposits captured against cumulative share of area, ranked by the map. PU learning is now standard in MPM. | **Hunter-relevant evaluation**: the share of held-out encounters, and the encounter rate per standard hour, inside the top 1/5/10% of *huntable forest area*. This is better aligned with "find productive covers" than AUC. |
| 8 | **Poaching prediction (PAWS, conservation security games)** | Snares are found only where rangers patrolled; a "no snare" in a lightly patrolled cell is unreliable | **iWare-E** (Gholami et al., AAMAS 2018): an ensemble of learners trained on data filtered at increasing patrol-effort thresholds, weighted by effort. Up to +34% AUC over the prior state of the art. Patrol effort is also a model input. | **Effort-threshold ensemble** as a robustness variant (stage 1). Checklists below 10/30/60 minutes are progressively excluded from the negatives. Effort is an explicit input. |
| 9 | **Fraud detection (PU, delayed labels)** | Only investigated transactions get verified labels; uninvestigated ones are unlabelled | Train on the *investigated* population, and evaluate at a top-k investigation budget (precision@k). | A complete checklist is the "investigated cell". Evaluate at a hunter's budget: precision and lift in the top-k coverts. |
| 10 | **Oil and gas exploration** | Drill where the chance of success is highest; each well updates the map | **Common-risk-segment / play-fairway mapping** (chance of success as a product of independent factors) and **value-of-information** drilling | (a) The multiplicative decomposition (intensity × detection) is itself a chance-of-success product. (b) A **scouting loop**: the owner's own hunts, logged as eBird checklists, are "wells" that update the posterior. Choose the next covert by Thompson sampling. |
| 11 | **Weakly supervised remote sensing / drug-activity MIL** | The label is known for a bag (a molecule or a scene), not for each instance | **Multiple-instance learning** (Dietterich et al. 1997) with noisy-OR / sum pooling | A traveling checklist is a **bag of 30 m cells** along an unknown route. A Poisson-sum pooling over a footprint kernel is the MIL noisy-OR. This fixes the report's §2.4.1 problem ("label attached to a pixel whose error radius is often many pixels"). |

**Step C: converge.** I scored each transfer 1–5 on four criteria. "Novel vs report" means not already in the report's §4 list, or a materially new implementation of it.

- **Gain**: expected gain on the owner's goal.
- **Evidence**: strength of evidence that it works in its home field.
- **Feasibility**: implementation cost on EC2 with this stack.
- **Novel vs report**: as defined above.

| Transfer | Gain | Evidence | Feasibility | Novel vs report | Total |
|---|---|---|---|---|---|
| 3 Test-negative controls (complete checklists) | 5 | 5 (Johnston et al. 2021: complete checklists gave the largest gain) | 4 (one data request) | 2 (report §4.2 names the data) | 16 |
| 1 PAL two-tower, drop at inference | 4 | 4 | 5 | 4 | 17 |
| 5 CPUE standardised-effort estimand | 4 | 4 | 5 | 5 | 18 |
| 11 MIL footprint pooling | 3 | 3 | 4 | 5 | 15 |
| 6 Injection–recovery | 2 (indirect: prevents a wrong turn) | 5 | 5 | 5 | 17 |
| 7 Capture-efficiency curves | 2 (evaluation) | 4 | 5 | 4 | 15 |
| 8 iWare-E | 2 | 3 | 5 | 4 | 14 |
| 10 Scouting loop / Thompson sampling | 2 (personal-scale data) | 3 | 3 | 5 | 13 |
| 4 Integrated PO component | 2 | 4 | 2 | 1 | 9 |
| 9 Fraud top-k | 1 | 3 | 5 | 2 | 11 |
| 2 ExpoMF latent exposure | 1 (superseded: exposure is observed here) | 4 | 3 | 3 | 11 |

**Convergence.** The top five transfers are not five separate ideas. Together they are one model:

- **3** supplies the data (complete checklists as test-negative controls);
- **5** fixes the estimand (encounters per standard hunter-hour);
- **1** fixes the architecture (separable effort tower, dropped at inference);
- **11** fixes the geometry (footprint MIL);
- **6** and **7** fix the evaluation (injection–recovery, capture curves).

8 and 10 become cheap add-ons. 4 is deferred.

**Why not plain "occupancy model on eBird" (the report's §4.2 #1)?** The occupancy model is the obvious rival, and other designers will probably propose it. It needs repeat visits to a closed site, but eBird sites are not closed and traveling checklists are not sites. Johnston et al. (2021) found that encounter-rate models with effort covariates match or beat occupancy on eBird data, with fewer assumptions. The PAL/CPUE framing keeps every checklist, with no closure assumption, and its estimand is closer to the hunter's experience. That estimand is the encounter rate, not $\psi$, which is "a bird is somewhere in the site". A hunter is paid in flushes per hour, not in occupancy.

### 2.2 Technique 2: assumption reversal (secondary)

I reversed each assumption the current pipeline encodes:

| Current assumption | Reversal | Kept? |
|---|---|---|
| "The negative is a place" | The negative is an **event** (a walk with an effort vector) | Yes: this is the core |
| "The label belongs to the centre pixel" | The label belongs to a **footprint** | Yes (MIL) |
| "Effort bias must be cancelled by choosing the right background" | Effort is **measured** and **modelled**, then deleted | Yes |
| "Output a relative ratio, then calibrate to a 50:50 prior" | Output an **absolute** rate. Non-detections identify the intercept (Phillips & Elith 2013) | Yes |
| "One model per pixel" | One model per **covert** (standard 2 km walk) | Yes, as the end product |
| "Labels are fixed; the model adapts" | The owner's **own hunts** become labels (active learning) | Yes, as stage 4 |
| "AUC on held-out points is the target" | **Capture efficiency** at a hunter's budget is the target; AUC is secondary | Yes |

### 2.3 Raw ideas generated and discarded

Each was discarded for the stated reason.

- SatCLIP or other location encoders. They encode effort geographically (the report's own warning).
- Using eBird S&T relative abundance as an input feature. S&T is trained on the same checklists, so it leaks into held-out blocks. It is kept as an **external benchmark** only.
- Click models with a cascade assumption, where the observer stops after the first detection. Encounter counts are rarely reliable for grouse, so CEM uses a binary any-detection outcome.
- Bandit-only data collection. It is too slow alone, so it is kept as stage 4.
- iNaturalist as additional controls. It is not complete-list data, so a non-report there is uninformative.

---

## 3. The design

### 3.1 Data

| Source | Use | URL |
|---|---|---|
| **eBird Basic Dataset (EBD) + Sampling Event Data (SED)**, custom download for US-ME, US-NH and US-VT, 2016–present. Free; request form; approval "typically within 7 days" | Checklist-level detection/non-detection and effort | https://science.ebird.org/en/use-ebird-data/download-ebird-data-products |
| Existing 15 rasters plus CR-0032 `mch_*` (after the CR-0035 registration repair) | Habitat tower inputs, unchanged | repo `data/` |
| eBird Status & Trends, Ruffed Grouse relative abundance (2023 version; for S&T the standard is a 1 h, 2 km traveling checklist) | **External benchmark only** | https://science.ebird.org/en/status-and-trends ; R `ebirdst` https://github.com/ebird/ebirdst |
| NH Fish & Game Ruffed Grouse Wing and Tail Survey: annual flush rate per hour hunted (e.g. 2.27 in 2020, 1.31 in 2019), regional observation rates | Coarse **independent CPUE validation** | https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey |
| Maine IF&W and Vermont F&W grouse hunter or cooperator data | Same; availability **unverified**, so request from the agencies | https://www.maine.gov/ifw ; https://vtfishandwildlife.com |
| PAD-US (protected and public lands, including access) | Mask for "huntable" area in the end product | https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview |
| The owner's own hunts, logged as eBird complete checklists (with tracks) or as a GPS+flush CSV | Stage 4 labels | — |

**Checklist filtering** follows Johnston et al. (2021), the eBird best-practice guide, with these settings:

- *Include:*
  - complete checklists only (`ALL SPECIES REPORTED = 1`);
  - protocols Stationary, Traveling and Area;
  - duration 5–300 min;
  - distance ≤ 8 km;
  - observers ≤ 10;
  - years 2020 to the latest LANDFIRE vintage + 2 (matching `YEAR_MATCH_TOLERANCE`).
- *Year-gap sensitivity run:* 2016–2019 checklists, with `tsd` per year and other layers at the nearest vintage, flagged.
- *Shared checklists:* deduplicate with `GROUP IDENTIFIER`, keeping one per group.
- *Outcome:* $y_j=1$ if Ruffed Grouse appears on checklist $j$ (any count, including "X"), else 0.

**Expected volume.** This is **unverified** and must be measured first. Vermont alone logged about 40–110k checklists/year in 2016–2021 (Vermont Center for Ecostudies County Quest posts). ME+NH+VT 2020–2025 is plausibly about 0.8–1.5 M complete checklists. If the grouse reporting rate is 1–3% of forest checklists, that gives **roughly 10–40k detection checklists plus ~1 M non-detection checklists**. Today's set is 6,232 positives against 6,232 TG negatives.

**Effort vector $e_j$:**

- $\log$ duration and $\log(1+\text{distance})$;
- protocol;
- number of observers;
- start-time spline;
- day-of-year cyclic spline: drumming peak in April–May and fall flush season, so the effort tower absorbs seasonal detectability;
- year (as a factor);
- hotspot flag;
- observer skill: Kelling et al. (2015) species-accumulation index, computed **out-of-fold** from the observer's other checklists;
- observer random effect $u_{o}$, for observers with ≥ 20 checklists.

Nothing in $e_j$ is derived from the checklist's own species list beyond the out-of-fold skill index. This avoids a post-treatment habitat proxy.

### 3.2 Estimand

For a landscape location $s$, define the **standardised encounter rate**:

$$
\mathrm{SER}(s)=1-\exp\!\Big(-\,e^{g(e^\star)}\sum_{t}K^\star(t-s)\,e^{f(x_t)}\Big),
$$

the probability that **one average-skill observer**, walking a **standard 60 min / 2 km** route centred at $s$ on a **mid-October morning**, encounters at least one grouse. The companion quantity

$$\Lambda^\star(s)=e^{g(e^\star)}\sum_t K^\star(t-s)e^{f(x_t)}$$

is the expected number of encounter events per standard hour. It is the model analogue of the agencies' "flushes per hour".

How the estimand compares with today's:

- **Today:** a log density ratio of reported-grouse locations to other-species record locations. It has no intercept and is tied to a 50:50 artificial prior.
- **CEM:** an absolute rate. Ranking it is invariant to $g(e^\star)$, because $1-e^{-c\,a}$ is monotone in $a$. The *values* are interpretable because non-detections identify the intercept (Phillips & Elith 2013).

**Assumption (stated, testable).** This is the test-negative "no preferential sampling" assumption: given $x$ and $e$, a birder's choice of where to walk is independent of grouse presence beyond $x$. Grouse-targeted visits (hunters, guided walks) violate it. Mitigations:

- observer random effects, which absorb "this person finds grouse";
- a sensitivity run that excludes observers with an out-of-fold grouse reporting rate in the top 1%;
- the stage-4 hunter checklists carry their own protocol level in $g$.

### 3.3 Model

**Footprint kernel (MIL bag).** Checklist $j$ has a start point $s_j$. eBird routes are generally not in the EBD (**unverified**: tracks may be available on request). The footprint is therefore an isotropic kernel:

$$
K_j(t)\propto\exp\!\Big(-\tfrac{\|t-s_j\|^2}{2\sigma_j^2}\Big)\mathbb 1[\|t-s_j\|\le 3\sigma_j],\qquad \sigma_j=\sqrt{\sigma_0^2+(\kappa\,D_j)^2},
$$

where:

- $D_j$ is the distance travelled;
- $\sigma_0=150$ m is the detection radius for a drumming or flushing grouse; a drum is audible further, so tune it in $\{100,150,250\}$;
- $\kappa=0.35$ approximates the half-width of a loop or out-and-back walk; tune it in $\{0.25,0.35,0.5\}$;
- $\sum_t K_j(t)=1$, so footprint size enters only through $g$ via $\log D$ and does not double-count.

**Habitat tower $f_\phi$.** This is the existing `GrouseResNet` trunk (stem, layer1–4, CBAM, plus the dilated Branch B), run **fully convolutionally**. The global attention pool and centre skip are removed, and `conv_out` is kept as a per-cell logit map.

- Overall stride is 8 (conv1 /2, maxpool /2, layer2 /2; layer3/4 are already stride 1). A 2× bilinear upsample with one 3×3 conv gives an $f$ map at **120 m**, which matches today's predict stride.
- The receptive field (~227 px) still covers the 1.9 km neighbourhood that the current lens uses.
- Inputs, embeddings, validity channels and D4 augmentation are unchanged. D4 is applied to the tile *and* the checklist coordinates together.
- Weights can be initialised from the current best checkpoint, as a warm start. The old model becomes a prior, not a competitor.

**Effort tower $g_\theta$.** This is a deliberately **small** generalised additive model:

$$
g(e_j)=\beta_0+\beta_1^{+}\log \mathrm{dur}_j+\beta_2^{+}\log(1+D_j)+\textstyle\sum_k h_k(e_{jk})+u_{o(j)},\qquad u_o\sim\mathcal N(0,\tau^2),
$$

- $\beta^{+}=\operatorname{softplus}(\cdot)\ge 0$ enforces monotone effort, as fisheries CPUE practice does.
- The $h_k$ are low-dimensional splines (B-spline bases with a ridge penalty) on time of day, day of year, observers and the skill index. Protocol and year are embeddings.
- **Why small:** PAL works because the bias tower cannot absorb relevance. A large $g$ could learn "checklists in the north woods in October" and steal habitat signal through correlated effort. $g$ sees no location and no raster input. That is the structural guarantee.

**Hazard link and loss.** The two towers combine by a complementary log-log (Poisson-thinning) link:

$$
\Lambda_j=\exp\big(g(e_j)\big)\sum_t K_j(t)\exp\big(f(x_t)\big),\qquad P(y_j=1)=1-e^{-\Lambda_j}.
$$

The negative log-likelihood is

$$
\mathcal L=-\sum_j w_j\Big[y_j\log\big(1-e^{-\Lambda_j}\big)-(1-y_j)\Lambda_j\Big]+\lambda_u\|u\|^2+\lambda_h\textstyle\sum_k\|D^2h_k\|^2 .
$$

Implementation notes:

- Use `log1mexp` for stability: $\log(1-e^{-\Lambda})$ = `torch.log(-torch.expm1(-Λ))`, with the `log1p(-exp(-Λ))` branch for large Λ.
- Compute $\log\Lambda_j$ by `logsumexp` over footprint cells, so $e^f$ never overflows.
- **No focal loss and no label smoothing.** A proper likelihood is needed for the absolute rate. The ranking-level regularisation comes from EMA, weight decay and early stopping on block-CV deviance.
- **Pin weighting:** $w_j=1/\sqrt{n_{\text{pin-year}}(j)}$, so heavily birded hotspots (59–76% of records are repeat pins, report §2.4) do not dominate.
- **Identifiability:** $f$ and $\beta_0$ share a constant. Fix it by centring $f$ on a fixed random sample of 10k forest cells per epoch, i.e. subtracting the mean. Otherwise it is harmless for ranking.

**Why this is the right MIL pooling.** If grouse "encounter units" are a Poisson process with intensity $e^{f}$, an observer's detection is Poisson-thinned with probability that scales with effort. The count of encounters on a walk is then Poisson with mean $\Lambda_j$, and $P(\geq1)=1-e^{-\Lambda_j}$. The noisy-OR / sum pooling is not a heuristic; it is that likelihood. It is the same structure as the Royle–Nichols abundance-induced heterogeneity model and as the report's §4.1 IPP. It differs from the IPP in having observed exposure.

### 3.4 Training

**Tiled training.** Checklists cluster spatially, so each batch is built from tiles:

1. Sample $B=8$ tiles of $512\times512$ px (15.4 km) from the training blocks. Sample with probability ∝ the number of checklists in the tile, and add a uniform 20% mix.
2. Run $f$ once per tile, producing a 128×128 map at 120 m.
3. For each checklist in the tile whose 3σ footprint lies inside the tile minus a 1 km margin, gather $f$ over the footprint at 120 m (precomputed index lists) and compute $\Lambda_j$.
4. Footprints crossing the margin are deferred to the tile where they fit.

**Throughput estimate (unverified).** One forward pass of a 512² FCN ResNet-18 at batch 8 takes ~0.2 s on an A10G-class GPU. With ~1 M checklists over about 60k km² of the three states and roughly 250 km² per tile, an epoch is about 240 tiles of new area × oversampling, so minutes per epoch. Most compute is in $f$, which is shared across thousands of checklists. That shared computation is the efficiency gain of whole-image weak supervision over the current 64×64 per-record windows.

**Spatial block CV.**

- Reuse the 3 km EPSG:5070 block grid (`regions.py`), with **5 folds** (block → fold by md5, as today).
- Every checklist inherits its start-point block.
- Footprints that straddle a fold boundary go to a *buffer* and are excluded from both sides in that fold.
- Pins never straddle folds.
- The report's §4.3 variogram check on residual deviance sets the final block size.

**Optimiser.** AdamW with the existing parameter groups (backbone at 0.1×), EMA 0.999, cosine schedule. Select on held-out deviance plus capture-efficiency at 5% area (§5).

### 3.5 Stage-1 tabular CEM (the fast path, before any CNN work)

sklearn's `HistGradientBoostingClassifier`, already used in `diagnose_gbm_baseline.py`, supports **`interaction_cst`** and **`monotonic_cst`**. LightGBM has the equivalent `interaction_constraints`. The stage-1 recipe:

1. **Habitat features per checklist:** footprint-kernel-weighted means of the existing GBM design features. These are the centre codes, `_share21`, and `_m5/_m21/_m64` means and SDs, evaluated on a 120 m sub-lattice of the footprint.
2. **Effort features:** $e_j$ as in §3.1, with no observer RE; use the skill index instead.
3. **Fit:** `interaction_cst=[habitat_idx, effort_idx]` and `monotonic_cst=+1` on log-duration and log-distance, with log loss. The logit is then exactly additive, $f(x)+g(e)$, which is the PAL factorisation with trees.
4. **Predict:** set effort to $e^\star$ and score every 120 m cell with the $K^\star$ footprint.
5. **iWare-E variant:** fit with checklists filtered at duration ≥ {5, 15, 30, 60} min, and average the habitat parts weighted by held-out deviance.

This needs **no GPU** and reuses the existing patch reader. It is the first real-data experiment (§7).

### 3.6 Inference and end product

1. **Habitat intensity raster** $e^{f}$ at 120 m (GeoTIFF), and **SER** / $\Lambda^\star$ with a 2 km standard walk (σ ≈ 0.74 km), for ME/NH/VT on the latest vintage. Both are standard `predict.py`-style outputs.
2. **Uncertainty.**
   - A 5-member deep ensemble from the 5 CV folds gives the epistemic map (mutual information, report §4.7).
   - A block bootstrap of stage-1 gives intervals on $\Lambda^\star$.
3. **Covert list (the hunter product).**
   - Take connected components of the top decile of $\Lambda^\star$ within PAD-US open-access lands.
   - Maine's large open private forests need a separate access layer; the owner decides.
   - For each covert, output: area, mean and 10th-percentile $\Lambda^\star$ ("expected flushes per hour"), uncertainty, distance to the nearest road, and dominant cover (the `evt` mode and `tsd` class).
   - Format: CSV + GeoJSON, loadable in onX/Gaia/CalTopo.
4. **Common-risk-segment view** (oil-and-gas transfer). Three traffic-light layers, so the owner sees *why* a covert ranks:
   - habitat intensity;
   - model confidence;
   - recent-disturbance freshness (`tsd` 5–20 yr share).

### 3.7 Stage 4: the scouting loop (VOI / Thompson sampling)

Each season, the owner (and any hunting partners) submit **complete eBird checklists while hunting**, with tracks on, plus a protocol note "grouse hunt". These enter training as checklists with a `hunter` protocol level in $g$, which absorbs dogs, flushing-based detection and targeting.

Before each outing, draw one ensemble member per candidate covert (Thompson sampling) and rank by the drawn $\Lambda^\star$. This balances exploiting known-good covers against exploring high-uncertainty ones. Each hunt then updates the map, like an infill well updating a reservoir model.

The gain is personal-scale; it is honest to expect it to matter only for the owner's own coverts.

---

## 4. Why it beats the status quo

The report's diagnosis (§5.4) is that **"the data is the ceiling"**: GBM ≈ CNN, and only new information moved AUC. CEM is a data-and-estimand change, not an architecture tweak. It attacks each named cap directly.

| Report's ceiling cause | Status quo | CEM |
|---|---|---|
| **Label noise in negatives** (PU; §5.4 bullet 1, §4.4). "A birder's other-species location 300 m from any grouse record can still hold grouse." | Unverified TG points labelled 0 | Every 0 is a *measured non-detection given known effort*. A 0 on a 5-minute roadside stop is cheap evidence; a 0 on a 3-hour forest walk is strong evidence. The likelihood weighs them by $\Lambda_j$ automatically, as iWare-E does by hand. |
| **Effort bias / access** (§5.3: grouse positives 2–5× *farther* from roads than TG negatives, which the model cannot interpret) | Hoped to cancel through $q_{\mathrm{TG}}$, which is habitat-structured | Effort is measured ($e_j$), modelled ($g$) and removed. Controls come from the *same* sampling process (the test-negative design). The road-distance confound is explained: grouse checklists are longer forest walks, and $g$ absorbs duration and distance. |
| **Estimand mismatch** (§5.1, §5.5: a ratio tied to a 50:50 prior; `--prior` is "a scenario assumption") | Relative contrast | Absolute standardised encounter rate in hunter units, identified by non-detections |
| **The $1-a/2$ structural AUC bound** (§4.1) | Applies: TG background overlaps the species' support | Does not apply in the same form. The model is no longer separating presence from background. It predicts detection probability per walk, and its errors are the irreducible Bernoulli noise of each walk, not overlap of supports. (Held-out ranking is still bounded by detection stochasticity; §5 explains how to measure it honestly.) |
| **Location error** (§2.4.1: traveling counts span km; the centre skip assumes the label is at the centre) | Point label, 2×2 centre head | The footprint MIL spreads the label over plausible cells, with a kernel width set by distance travelled |
| **Sample size** | 6,232 positives, one per pin (repeat visits collapsed) | Plausibly 10–40k detection checklists plus ~1 M non-detections (to be measured). Repeat visits become *information* (repeated trials), not duplicates. |
| **Envelope weighting double-counts selection** (§4.1, §6) | 1/SR-shaped background | Gone. No background is drawn at all. |
| **Year/vintage leakage machinery** (CR-0019/21) | Per-stratum 1:1 matching | Year is an effort-tower factor. Detection-rate drift across years is absorbed there, and habitat is read from each year's vintage. |

**What CEM keeps.** All the input engineering (15+4 layers, registration fixes, nodata validity channels) and the trunk architecture are kept. This is a new head, loss, label stream and evaluation on the same lens. No completed work is thrown away.

**Why not just add checklists as more positives to the current pipeline?** That would add positives and keep the broken negatives. The test-negative logic only works if cases and controls come from the same exposure process.

---

## 5. Expected gains, and how to measure them without fooling ourselves

### 5.1 Comparison protocol: one test set, one metric, all models

AUC on today's validation set (GBIF positives vs TG negatives) **cannot** compare an encounter model with a contrast model. Each would be scored on the other's estimand. The common yardstick is **held-out complete checklists** in held-out blocks, with effort controlled. A model is reduced to a habitat score $h(s)$:

- the old CNN's logit at the checklist start;
- the old GBM's logit there;
- CEM's footprint-pooled $f$;
- eBird S&T relative abundance at the start point (external benchmark; caveat below).

Each score is then evaluated three ways.

**M1, effort-adjusted deviance gain.** On held-out checklists, fit a *fixed* small GLM

$$\operatorname{cloglog}P(y_j)=\gamma_0+\gamma_1\,\mathrm{spline}(h(s_j))+\text{effort terms}.$$

Report the deviance explained relative to effort-only. All models share the same effort terms, so the difference is the habitat information. The GLM is fitted on the held-out fold by internal cross-fitting (5 sub-folds), to avoid optimism.

**M2, effort-stratified AUC.** Use the test-negative "conditional" analysis. Compute AUC within strata of (protocol × duration tercile × month × year) and average, weighted by the number of pairs in each stratum. This compares a grouse walk only with a comparable non-grouse walk.

**M3, hunter capture efficiency** (prospectivity success-rate curve).

- Rank all 120 m forest cells within the held-out blocks by $h$.
- For the top $k\in\{1,5,10,20\}\%$ of area, report the **observed encounter rate per effort-hour** of held-out checklists starting there, divided by the held-out average. This is a **lift**.
- Report the full curve and its area.
- Report it for October checklists separately, the hunting season.

**M4, independent CPUE check.**

- Aggregate $\Lambda^\star$ over the NH Fish & Game reporting regions (and ME/VT units if obtained).
- Compute the Spearman correlation with region-level flush rates, averaged over years, and the within-region year-to-year correlation with $g$'s year effect.
- With few units this is weak evidence. It is reported, never optimised.

**M5, legacy metric.** CEM's $h$ is also scored on today's validation set (TG AUC/AP), to show it does not *lose* the old signal. It is not optimised.

**Guards against self-deception:**

- one pre-registered fold assignment;
- the stage-1 effort tower is frozen before the habitat comparisons are run;
- the M3 area denominator is fixed (forest cells, `nlcd` 41/42/43/90, in held-out blocks);
- the CR-0035 registration repair is applied to *both* old and new models before any comparison;
- S&T is used only as a benchmark. It is trained on many of the same checklists, so it has partial leakage into held-out blocks, and its score is an *upper-bias* benchmark.

### 5.2 Quantified expectations, with honest uncertainty

These are prior estimates. Each will be replaced by the stage-0/1 measurements.

| Quantity | Current pipeline (expected on the new test set) | CEM stage 1 (GBM) | CEM stage 3 (CNN FCN) | Confidence |
|---|---|---|---|---|
| M2 effort-stratified AUC of the habitat score | 0.62–0.68 | 0.68–0.74 | 0.70–0.77 | Low–medium. The direction is well supported (Johnston et al. 2021: complete checklists + effort covariates gave the largest gains among processing choices); the magnitude is guesswork. |
| M3 lift in top 5% forest area (encounters per hour vs mean) | 1.6–2.2× | 2.0–2.8× | 2.2–3.2× | Low |
| Full-model AUC (habitat + effort) on held-out checklists | n/a | 0.80–0.88, **mostly effort and season; not a habitat skill claim** | similar | Medium |
| M4 Spearman with NH regional flush rates | unknown | positive; n is tiny | positive | Very low (small n) |
| Absolute calibration (held-out reliability of SER) | not defined | ECE < 0.01 at base rates of 1–3% | same | Medium |

**The single number to watch is M3 lift at 5%.** It directly measures how many more grouse per hour the owner should find by hunting where the map points, compared with hunting at random in forest. A gain of +0.4× or more in lift over the current model at matched area would be practically meaningful.

**Statistical power.** With about 200k held-out checklists and about 4k held-out detections, the block-bootstrap SE of M2 AUC is about ±0.01. Use paired bootstraps over blocks, with the same resamples for every model. Differences under 0.015 are treated as ties.

---

## 6. Risks, failure modes and the cheapest falsification experiments

| Risk | Mechanism | Detection | Mitigation |
|---|---|---|---|
| **R1 Preferential sampling** | Birders or hunters go *to* known grouse spots, so $y$ depends on $s$ beyond $x$ | Observer RE variance; residual variogram of deviance; drop-top-observers sensitivity | Observer RE; sensitivity run; `hunter` protocol level; report both runs |
| **R2 Effort tower leaks habitat** | $g$ uses day of year × year, which correlates with region | Fit $g$ alone on shuffled habitat; check that $g$ has no spatial residual pattern | $g$ has no location inputs; small GAM; interaction-free by construction |
| **R3 Habitat-dependent detectability** | Dense young forest hides birds visually (drumming is audible), so $f$ mixes abundance and detectability | Not separable without repeat-visit designs | Accept and state it. The *hunter's* encounter rate shares the same confound (hunters also detect by flush and sound), so this is arguably the right target. Acoustic-season vs fall split in $g$ via day of year. |
| **R4 Footprint misspecification** | Kernel too wide blurs; too narrow mislocates | Tune σ₀ and κ on held-out deviance; sensitivity on the subset with ≤ 1 km distance | Johnston et al. (2021)-style filtering as a fallback |
| **R5 Data volume smaller than hoped** | Grouse rarely reported | Measured at stage 0 (one pandas pass) | Extend to 2016–2019 with the year-gap flag; add incomplete checklists as a PO component (transfer 4) |
| **R6 Data terms** | EBD terms of use restrict redistribution | — | Use internally; publish derived maps only (check the EBD terms; **unverified** for derived products) |
| **R7 QMS overhead** | New data stream + model + evaluation | — | Split into the CRs listed in §7 (CR-0011 A5: one change per CR) |
| **R8 No improvement** | The data ceiling is also the detection ceiling | M1–M3 show ties | Falsified cheaply at stage 1, before any CNN work (below) |

### Falsification experiment F0 (≤ 1 day, no new data; can run while the EBD request is pending)

**Injection–recovery** (astronomy transfer). This uses only data already on EC2.

1. **Synthetic truth.** Define $f^\*(x)$ as a known function of existing features. For example: hump-shaped in `tsd` (peak 5–20 yr), positive in deciduous `evt` share within 21 px, negative in `road_dist` < 100 m. Scale it so the implied base rate matches about 2%.
2. **Real effort geometry.** Use the existing **TG candidate pool** (other-species record locations and years, already built by `generate_negatives.py`) as a stand-in for checklist start points. Draw a synthetic effort vector for each:
   - duration ~ the empirical eBird distribution, approximated as log-normal(median 45 min);
   - a distance correlated with duration;
   - a road-proximity–effort link: short stops near roads.
3. **Simulate** $y_j\sim\mathrm{Bern}(1-e^{-\Lambda_j})$ with the CEM generative model.
4. **Pipeline A (today).** Positives are the simulated detections, thinned and collapsed per pin. Negatives are the TG pool with the 300 m buffer and envelope weights. Fit the existing HistGBM.
5. **Pipeline B (CEM stage 1).** Fit all simulated checklists with the interaction-constrained GBM.
6. **Score.** Compute the Spearman correlation of each recovered map with $f^\*$ on a 50k-cell random forest sample, and compute M3 lift against the true $\Lambda^\star$.

**The result falsifies the transfer** if Pipeline A recovers $f^\*$ within 0.02 Spearman of Pipeline B under the realistic road–effort link. That would mean today's estimand is not materially biased under this effort geometry, and the gain must come from data volume alone.

**Cost:** about 150 lines reusing `diagnose_gbm_baseline.py`'s design matrix; CPU only.

Caveat: the simulation's truth is CEM-shaped, which favours B. To be fair to A, also run a second truth in which records arise from a pure thinned IPP. Pipeline A is specified for that case.

### Falsification experiment F1 (first real-data experiment, about 1 day once the EBD is approved)

Stage-1 tabular CEM against the current GBM, both scored by M1–M3 on held-out checklist blocks.

**Kill criterion:** if the stage-1 habitat score's M2 is not ≥ 0.015 above the current GBM's (paired block bootstrap), and the M3 lift at 5% is not ≥ 0.2× higher, stop. Do not build the FCN.

---

## 7. Implementation plan

New files only. Each phase is its own CR under `CLAUDE.md` §1 (A5 split: data / pipeline / acceptance). Acceptance scripts are committed before approval, as A3 allows.

| Phase | Work | Effort | CR scope | Output |
|---|---|---|---|---|
| **0a** (day 0) | Submit the EBD custom-download request (ME, NH, VT; Ruffed Grouse + SED). Email NH F&G / ME IF&W / VT F&W for regional flush-rate tables. | 1 h | none (no code) | pending access |
| **0b** (day 1) | **F0 injection–recovery** on existing data (`inv_cem_injection.py`) | 1 day | acceptance-design CR | go/no-go on the estimand claim |
| **1** (days 2–5 after access) | `ebird_checklists.py`: stream-parse EBD+SED with pandas `chunksize`, filter (§3.1), zero-fill, dedupe groups, attach blocks. Measure volumes and grouse rate (resolves R5). | 2 days | data CR | `data/checklists/*.parquet` |
| **2** (week 2) | `cem_features.py`: footprint kernels on a 120 m sub-lattice; kernel-weighted GBM features; effort features + out-of-fold skill index. `cem_gbm.py`: interaction- and monotonic-constrained HistGBM, iWare-E variant. `cem_eval.py`: M1–M5 and capture curves for the old CNN/GBM, CEM and S&T. **F1 kill/go.** | 4–5 days | pipeline CR + acceptance CR | first CEM map; comparison table |
| **3** (weeks 3–5) | `models.py`: `GrouseFCN(GrouseResNet)` wrapper (per-cell logit map, no pooling). `losses.py`: `CloglogFootprintNLL`. `train_cem.py`: tiled sampler, effort GAM tower, observer RE, 5-fold ensemble. Warm start from the best checkpoint. | 2–3 weeks | pipeline CR | CEM-CNN; ensemble uncertainty |
| **4** (week 6) | `predict_cem.py`: Λ\*, SER, uncertainty GeoTIFFs; covert extraction on PAD-US; CSV/GeoJSON. | 3–4 days | pipeline CR | **hunter product** |
| **5** (season) | Scouting loop: owner's eBird hunt checklists, Thompson-sampled covert ranking, end-of-season refit | ongoing | small CR | personal-scale updates |
| 6 (optional) | Integrated PO component (incomplete checklists, iNat) sharing $f$ | 1–2 weeks | separate CR | only if R5 bites |

**The first EC2 experiment within a day** is F0 (§6). It needs only the existing TG pool, rasters and the GBM design code, and it answers "is the current estimand materially biased under realistic effort geometry?" before any new data arrives. Since F1 cannot start until the EBD request is approved, submit it on day 0.

---

## 8. References

URLs were checked by web search on 2026-10-05 unless marked **unverified**.

**Analogical sources**

1. Guo, H., Yu, J., Liu, Q., Tang, R., Zhang, Y. (2019). PAL: a position-bias aware learning framework for CTR prediction in live recommender systems. *RecSys '19*. https://doi.org/10.1145/3298689.3347033
2. Joachims, T., Swaminathan, A., Schnabel, T. (2017). Unbiased learning-to-rank with biased feedback. *WSDM '17*, 781–789. https://arxiv.org/abs/1608.04468
3. Liang, D., Charlin, L., McInerney, J., Blei, D.M. (2016). Modeling user exposure in recommendation. *WWW '16*, 951–961. https://doi.org/10.1145/2872427.2883090 ; https://arxiv.org/abs/1510.07025
4. Jackson, M.L., Nelson, J.C. (2013). The test-negative design for estimating influenza vaccine effectiveness. *Vaccine* 31(17):2165–2168. https://doi.org/10.1016/j.vaccine.2013.02.053 (DOI **unverified**; paper confirmed via search)
5. Maunder, M.N., Punt, A.E. (2004). Standardizing catch and effort data: a review of recent approaches. *Fisheries Research* 70(2–3):141–159. https://doi.org/10.1016/j.fishres.2004.08.002 (DOI **unverified**)
6. Christiansen, J.L. et al. (2016). Measuring transit signal recovery in the Kepler pipeline III: completeness of the Q1–Q17 DR24 planet candidate catalogue. *ApJ* 828:99. https://ipac.caltech.edu/publication/2016ApJ...828...99C ; see also DR25 completeness, https://arxiv.org/abs/2010.04796
7. Chung, C.-J.F., Fabbri, A.G. (2003). Validation of spatial prediction models for landslide hazard mapping. *Natural Hazards* 30:451–472. https://ideas.repec.org/a/spr/nathaz/v30y2003i3p451-472.html
8. Gholami, S. et al. (2018). Adversary models account for imperfect crime data: forecasting and planning against real-world poachers. *AAMAS 2018*. https://www.cais.usc.edu/wp-content/uploads/2018/01/sgholami_aamas18.pdf ; Xu, L. et al. (2020) Stay ahead of poachers, https://arxiv.org/abs/1903.06669
9. PU learning in mineral prospectivity, for example the EarthByte copper prospectivity study: https://www.earthbyte.org/spatio-temporal-copper-prospectivity-in-the-american-cordillera-predicted-by-positive-unlabeled-machine-learning/ ; GFM4MPM, https://arxiv.org/abs/2406.12756
10. Common risk segment / play fairway mapping, industry description: https://www.tgs.com/play-fairway-analysis
11. Dietterich, T.G., Lathrop, R.H., Lozano-Pérez, T. (1997). Solving the multiple instance problem with axis-parallel rectangles. *Artificial Intelligence* 89:31–71. https://doi.org/10.1016/S0004-3702(96)00034-3 (from memory; **unverified**)

**eBird and ecology**

12. Johnston, A. et al. (2021). Analytical guidelines to increase the value of community science data: an example using eBird data to estimate species distributions. *Diversity and Distributions* 27:1265–1277. https://doi.org/10.1111/ddi.13271 ; open copy https://par.nsf.gov/servlets/purl/10332329
13. Kelling, S. et al. (2015). Can observation skills of citizen scientists be estimated using species accumulation curves? *PLoS ONE* 10(10):e0139600. https://doi.org/10.1371/journal.pone.0139600
14. eBird Basic Dataset and Sampling Event Data, download and request process: https://science.ebird.org/en/use-ebird-data/download-ebird-data-products ; `auk` R package: https://docs.ropensci.org/auk/articles/auk.html
15. eBird Status & Trends / `ebirdst`: https://github.com/ebird/ebirdst ; https://science.ebird.org/en/status-and-trends
16. Dorazio, R.M. (2014). Accounting for imperfect detection and survey bias in statistical analysis of presence-only data. *Global Ecology and Biogeography* 23:1472–1484. https://doi.org/10.1111/geb.12216
17. Phillips, S.J., Elith, J. (2013). On estimating probability of presence from use–availability or presence–background data. *Ecology* 94:1409–1419. https://doi.org/10.1890/12-1520.1 (cited in the repository report)
18. Royle, J.A., Nichols, J.D. (2003). Estimating abundance from repeated presence–absence data or point counts. *Ecology* 84:777–790. https://doi.org/10.1890/0012-9658(2003)084[0777:EAFRPA]2.0.CO;2 (from memory; **unverified**)
19. Fithian, W. et al. (2015); Koshkina, V. et al. (2017): integrated SDMs, as cited in the report §4.2.

**Agency and land data**

20. NH Fish & Game, Ruffed Grouse Wing and Tail Survey (flush rate per hour hunted): https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey
21. Maine IF&W / UMaine grouse research: https://www.maine.gov/ifw/blogs/mdifw-blog/ruffed-grouse-targeted-ifw-umaine-research-project ; https://umaine.edu/news/?p=61877. Hunter flush-rate data for ME and VT were **not found online (unverified)**; request them from the agencies.
22. Vermont Center for Ecostudies, Vermont eBird checklist volumes: https://vtecostudies.org/blog/vermont-ebirders-gather-big-bird-data-during-county-quest
23. USGS PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview
24. sklearn `HistGradientBoostingClassifier` (`interaction_cst`, `monotonic_cst`): https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html (parameter names from memory; **verify against the installed version**)

**Repository**

25. `docs/grouse_model_report.md` (§2.3, §2.4, §4.1–4.8, §5); `diagnose_gbm_baseline.py`; `generate_negatives.py`; `models.py`; `regions.py`; `CLAUDE.md`.
