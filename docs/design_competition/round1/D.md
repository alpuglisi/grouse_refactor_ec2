# Design D: COVERT, a flush-yield ranker for huntable cover

*Designer D, round 1. Primary technique: reverse brainstorming plus pre-mortem. Supporting techniques: assumption reversal and "inversion to requirements". No repository file was edited.*

---

## 1. Title and pitch

**COVERT: Counterfactual-effort, Object-level, Versioned, Effort-standardised Ranking of Territory.**

The current model answers this question: "Does this 1.9 km window look more like places where birders report grouse than places where birders report other birds?" A hunter asks a different one: **"If I walk this cover for an hour this October, how many grouse will I flush, and am I allowed to be there?"**

COVERT changes the estimand, the labels, the unit of prediction and the scoring metric so that all four match the hunter's question:

- **Estimand:** expected flushes per standardised hour of hunting, $\mu_{c,T}$, for each candidate covert $c$ in hunting season $T$.
- **Labels:** eBird *complete checklists*, so true non-detections and per-checklist effort are known. They are fitted jointly with three regional abundance anchors: state drumming indices, hunter flush-rate surveys and wing/tail returns. This is an integrated SDM with a *disaggregation* likelihood.
- **Detection:** effort is modelled explicitly, then fixed at a hunter-standard counterfactual for prediction ("an October hour, walking, off pavement").
- **Unit:** polygons a hunter can walk, about 5–60 ha. Mostly these are harvest patches 4–25 years old from a disturbance stack refreshed every season. The unit is not a 30 m pixel.
- **Access:** a legal-access and reachability gate built from PAD-US, state lands, NH Current Use recreation-adjustment parcels and woods roads.
- **Metric:** effort-standardised **top-k flush lift**, not AUC. It is validated on data the model never touches: Vermont Green Mountain National Forest drumming ARUs and the owner's own GPS-logged hunts.
- **Learning loop:** the season itself feeds back. A Thompson-sampling recommender sends the owner partly to the best-known coverts and partly to the coverts whose uncertainty is most worth resolving, and every logged hunt becomes a gold-standard label.

The report says "the data is the ceiling". COVERT does not try to beat that ceiling with architecture. It **replaces the data and the question** that set it.

---

## 2. Brainstorming record

### 2.1 Reverse brainstorm: "How do we build a map that sends hunters to the WORST places while still scoring a high AUC?"

Raw ideas, not filtered. Each is tagged with whether the *current pipeline* already does it (Y), might (?), or does not (N).

| # | Sabotage idea | Current pipeline? | Mechanism (repo evidence) |
|---|---|---|---|
| R1 | Learn where **birders** walk, not where grouse are | ? | Positives sit 2–5× *farther* from roads than target-group negatives (`diagnose_road_bias.py`, report §5.3). The model can win AUC by learning "hiking-trail woods" against "feeder/lake/roadside birding". A hunter is then sent to popular trails where grouse are educated, crowded or absent. |
| R2 | Make the negatives easy | Y | Up to 30% of negatives are non-vegetated (`NONVEG_MAX_FRAC`). Rejecting water and urban land earns AUC but tells a hunter nothing, because a hunter never considers a lake. |
| R3 | Make the negatives a different habitat guild | Y | The target group is mature-upland plus a wetland guild (`get_negatives.py`). "Not mature forest, not marsh" earns AUC but does not separate a 12-year-old aspen cut from a 40-year-old one, which is the decision a hunter actually makes. |
| R4 | Use stale disturbance data | Y | LANDFIRE has nothing before 2022 (§2.4). `predict.py` uses the latest vintage. Fall 2026 hunting needs the 2025–2026 cuts (too open, value 0–4 yrs) and the stands that aged past 25 yrs. TIGER roads are frozen at 2023. |
| R5 | Predict at the wrong scale | Y | 30 m pixels and a 120 m output stride. A hunter walks 10–50 ha coverts. A bright speckle in a 3 ha woodlot next to a house wins on AUC and loses in the field. |
| R6 | Ignore access | Y | Nothing masks posted, developed or unreachable land. The top-ranked pixel may sit in a backyard, a no-hunting town park, a Canadian border strip or a 6 km bushwhack. |
| R7 | Optimise a metric the hunter does not use | Y | AUC weighs every positive–negative pair equally. A hunter only uses the top ~1% of the map. AUC 0.77 is compatible with top-1% precision anywhere from poor to excellent. |
| R8 | Collapse abundance to presence | Y | Repeat visits are collapsed (59–76% are pins). A cover with 1 bird and a cover with 12 birds are both "1". Hunters care about density. |
| R9 | Train on the wrong season | ? | eBird grouse reports peak in the drumming season (April–May) and on summer brood roads. Hunting is October–December, when birds use mast and food cover, and fall shuffle has dispersed the young. |
| R10 | Let positional error define the label | Y | Traveling checklists span kilometres. The 2×2 centre-skip assumes the label belongs to the centre pixel. |
| R11 | Bake the prior map into the labels | Y | Envelope weights $1/\mathrm{SR}$ shape the negatives using an earlier selection-ratio map (report §5.6 Q2). The model then re-learns its own prior. |
| R12 | Ignore population cycles and WNV years | Y | Per-year 1:1 matching removes year signal by design. Fine for AUC, but a hunter's expected flush rate depends on whether 2026 is a high year in that region. |
| R13 | Reward "near a known grouse record" | Y | The 300 m buffer around every grouse record removes negatives near positives. "Near known birding-grouse spots" becomes positive by construction. |
| R14 | Exploit a misregistration artefact | Y (open) | BUG-0094, 0095, 0096: six channels are shifted about 21 m. |
| R15 | Rank by score, ignoring uncertainty | Y | Mean-only maps send the hunter confidently into extrapolated EVT combinations. |
| R16 | Recommend the same 20 coverts to everyone | N/A | Crowding pressure. Relevant only if the product is shared. |
| R17 | Treat "too thick to hunt" as top habitat | ? | Stands 0–5 yrs old with 30k stems/ha are unwalkable. Flushes per hour fall even if density is high. |
| R18 | Learn detectability (open hardwood, birders hear drumming 300 m away) as if it were abundance | Y | Drumming is detected far better in open mature woods next to young cover. Presence-only labels confound the two. |

### 2.2 Pre-mortem: "It is October 2027. The model failed hunters. Why?"

I wrote the failure stories as headlines, then grouped them.

1. *"The top 50 coverts were trailheads."* (R1, R13) The map was a birding-effort map. The owner flushed 0.3 birds/hr there against 1.5/hr in an unranked clearcut 4 km away.
2. *"Half the bright spots were posted or were someone's back forty."* (R6) NH and VT especially. Wasted mornings and one angry landowner.
3. *"The 2025 cuts were still dark and the 1998 cuts were still bright."* (R4) Disturbance was 2–3 years stale.
4. *"We were right about habitat but 2027 was a bust year in the south."* (R12) There was no regional/annual expectation, so the hunter could not tell whether a poor day meant a bad map or a bad year.
5. *"The model was fine at AUC, terrible at the top."* (R7) Nobody measured top-k, and the selected checkpoint maximised mean AUC+AP.
6. *"We could not tell whether it worked."* The only evaluation was held-out eBird presence-background AUC, which measures how well the *recording process* is reproduced (report §5.6). There was no independent signal.
7. *"It recommended thickets you can't walk."* (R17)
8. *"Everything got re-trained after the BUG-0094 fix, and the top-100 list changed by 40%."* The ranking was unstable, so trust collapsed.
9. *"The pixel speckle was unusable on a phone."* (R5)

### 2.3 Inversion: failure mode to requirement

| Req | Requirement (inverted failure) | Sources |
|---|---|---|
| Q1 | Labels must carry **known effort and true non-detection**, and effort must be modelled and then *fixed to a counterfactual* at prediction | R1, R8, R13, R18, PM1 |
| Q2 | No hand-shaped background. Remove envelope weights, buffers and non-vegetated "easy negatives" from the estimand | R2, R3, R11, R13 |
| Q3 | Disturbance must be **as fresh as the hunting season**: near-real-time harvest detection and analytic aging of every stand to year $T$ | R4, PM3 |
| Q4 | The prediction unit must be a **walkable covert** (5–60 ha object), with the pixel model only as a feature extractor | R5, R10, PM9 |
| Q5 | Every recommendation passes a **legal-access and reachability gate**, with an explicit confidence class | R6, PM2 |
| Q6 | Primary metric must be **top-k effort-standardised yield**, with AUC kept only for continuity | R7, PM5 |
| Q7 | At least two **independent validation streams** the model never trains on | PM6 |
| Q8 | **Regional-year abundance offsets** from state surveys, so the product states an expected flush rate and not only a rank | R12, PM4 |
| Q9 | Target the **hunting season** (Oct–Dec) through a season-specific detection and use head | R9 |
| Q10 | Penalise unwalkable thickets: a "huntability" term on stem density or age 0–4 years | R17, PM7 |
| Q11 | Rankings must report **uncertainty** and must be **stable** (rank-correlation gate across seeds and data repairs) | R14, R15, PM8 |
| Q12 | The product must **learn from its own use**: logged hunts become labels | PM6 |

### 2.4 Other ideas generated and rejected (convergence)

- *Bigger CNN, ViT, foundation-model embeddings.* Rejected as the **primary** lever. The report shows GBM ≈ CNN, so capacity is not binding. These are allowed later as feature extractors inside COVERT.
- *nnPU on the current labels.* This is a better loss for the wrong labels. Q1 makes it unnecessary, because complete checklists have real zeros.
- *Pure occupancy model (MacKenzie).* Occupancy is binary and a hunter wants density. Royle–Nichols (abundance-induced heterogeneity in detection) gives a density-like intensity from the same detection/non-detection data, so it was chosen instead.
- *Scraping hunting-app data (onX etc.).* Rejected: terms of service, privacy and provenance.
- *Crowd hunter-log platform.* Deferred. Only the owner's own logs (plus any consenting cooperators) are in scope.
- *Use eBird Status & Trends abundance as the label.* Rejected as a label, because it would be circular with the eBird stream and is coarse at 3 km. It is kept as a **sanity comparator** and as a coarse covariate check.

**Convergence rule.** I scored each candidate architecture on how many of Q1–Q12 it satisfies. An integrated detection model plus an object-level ranker plus a fresh disturbance stack plus an access gate plus a bandit loop satisfies all twelve. Any subset that drops the integrated detection model fails Q1, Q2, Q6 and Q8 together. That model is therefore the non-negotiable core, and the rest are thin, independently landable layers.

---

## 3. The design

### 3.1 Estimand

For covert $c$ (a polygon) in hunting season $T$, let $N_{c,T}$ be the mean fall grouse density in $c$, in birds/ha. A hunter walking at the standard pace covers an effective encounter strip of $A$ ha/hr, and flushes a bird within the strip with probability $q_c$ (huntability: lower in unwalkable 0–4-year slash). The quantity we want is

$$
\mu_{c,T} \;=\; \mathbb E[\text{flushes per hour}] \;=\; A\,q_c\,N_{c,T}.
$$

We cannot observe $N$ in absolute terms from eBird. We model it as a **latent log-intensity**

$$
\log N(s,T) \;=\; f_\theta\big(X(s,T)\big) \;+\; \alpha_{r(s),T},
$$

where:

- $f_\theta$ is the habitat function, shared across all data streams;
- $X(s,T)$ is the feature stack *as of season $T$* (§3.3);
- $\alpha_{r,T}$ is a region-by-year offset that carries cycles and WNV years. The regions are NH's four survey regions, Maine's WMD groups and Vermont's WMUs, collapsed to about 8–12 units.

At the covert level, $\log \mu_{c,T} = \log A + \log q_c + \log \overline{N}_{c,T}$, where $\overline N_{c,T}$ is the area mean of $N(s,T)$ over $c$.

The product **ranks by $\hat\mu_{c,T}$**. It shows $\hat\mu$ in flushes/hr only where the regional anchor (§3.2.3) identifies the scale; otherwise it shows a relative index.

### 3.2 Data streams and observation models (the integrated likelihood)

All streams share $f_\theta$. Each has its own detection or observation model.

#### 3.2.1 eBird complete checklists (primary label; effort known)

- **Source.** eBird Basic Dataset (EBD) plus the Sampling Event Data (SED) for US-ME, US-NH, US-VT, 2016–present. Request: https://ebird.org/data/download. Note that `ebird.py` uses the observations API and therefore cannot see non-detections (report §6).
- **Filters.** Follow Johnston et al. (2021):
  - complete checklists only;
  - stationary or traveling protocol;
  - duration ≤ 5 h;
  - distance ≤ 5 km;
  - observers ≤ 10.
- **Spatial subsampling.** Subsample 1 checklist per 3 km cell per week, separately for detections and non-detections, to limit the effect of effort hotspots.
- **Size.** About $10^5$–$10^6$ checklists (**estimate, unverified**).

**Observation model: Royle–Nichols with spatial support.** Checklist $j$ has start point $s_j$, protocol, duration $d_j$, distance $\ell_j$, observers $o_j$, time of day $h_j$ and day of year $t_j$. Its sampled area is a disk $D_j$ of radius $\rho_j=\max(150\,\text{m},\ \ell_j/2)$. This is a deliberate, honest admission of location error (R10): the latent intensity is *averaged over the disk*, not read at a pixel:

$$
\Lambda_j \;=\; \frac{1}{|D_j|}\int_{D_j} e^{\,f_\theta(X(s,T_j))}\,ds \;\cdot\; e^{\alpha_{r,T_j}}.
$$

$$
P(y_j=1) \;=\; 1-\exp\!\big(-\Lambda_j \; e^{\,g_\phi(w_j)}\big),\qquad
w_j = (\log d_j,\ \log(1+\ell_j),\ o_j,\ \text{protocol},\ \text{spline}(h_j),\ \text{spline}(t_j),\ \text{observer-expertise score}).
$$

This is the complementary log-log link of a Poisson count thinned by per-individual detection, i.e. the Royle–Nichols form. $g_\phi$ is a small MLP or GAM. The seasonal spline in $t_j$ absorbs the drumming peak (R9, R18).

The loss is the Bernoulli NLL, which is a **proper** scoring rule (unlike focal loss). There are no buffers, no envelope weights and no artificial 1:1 balance (Q2).

**Effort and "birder-ness" nuisance (Q1).** $w_j$ also includes the covariates that make *birders* detect grouse and that a hunter would not reproduce:

- distance to the nearest eBird hotspot;
- distance to a marked hiking trail (OSM `highway=path|footway` with `sac_scale` or route relations);
- checklist density within 1 km.

These enter **only** $g_\phi$, never $f_\theta$. At prediction they are fixed to a **hunter-standard counterfactual** $w^\star$:

- traveling, 60 min, 2 km, 1 observer;
- mid-October ($t$ = day 290), 09:00;
- distance-to-hotspot and trail set to the population median of *non-hotspot forest*.

That is the bias-covariate method of Warton et al. (2013), with a specific counterfactual for hunters rather than "the mean".

**Identifiability guard.** Habitat features $X$ and effort features $w$ are correlated, for example road density with trail density. To stop $f_\theta$ from absorbing effort, $f_\theta$ never sees trail or hotspot layers, and road distance is restricted to *woods/forest roads* (a hunter-relevant access feature) inside $f_\theta$. A gradient-reversal adversary $a_\psi(f_\theta\text{-embedding}) \to$ log checklist density is trained with weight $\lambda_{adv}$ and swept over {0, 0.1, 0.3}. Selection uses the independent validation streams (§3.6), not the eBird loss.

#### 3.2.2 Presence-only incidental records (secondary)

eBird incidental records and iNaturalist research-grade records (GBIF) enter as a thinned point process:

$$
\lambda_{\text{PO}}(s) = e^{f_\theta(X(s))}\,e^{\,b_\gamma(u(s))},
$$

where $u$ is the *known* eBird effort surface built from the SED (checklist-hours per 1 km cell). The likelihood uses Berman–Turner quadrature, i.e. DWPR (report §4.1). The weight is $\le 0.25$ of the checklist term. The stream is dropped entirely if the falsification test in §6 shows it hurts.

#### 3.2.3 Regional abundance anchors (disaggregation likelihood; Q8)

Two kinds of state data come only as region-by-year aggregates. They enter through a **disaggregation regression** (in the style of the malaria-mapping literature; see Nandi et al. 2023). The aggregate count is modelled as the integral of the fine-scale intensity over the area that was actually surveyed or hunted.

1. **Hunter cooperator flush-rate surveys.** NH Fish & Game publishes flushes per hour hunted, statewide and by region, in its Small Game Summary Report. One example: the 2018 North Region figure was 143 grouse per 100 hours with a dog. Maine and Vermont data are to be requested from the agencies (**availability unverified**). Model:

   $$
   F_{r,T} \sim \text{NegBin}\Big(H_{r,T}\;A\,\bar q\;e^{\alpha_{r,T}}\;\textstyle\sum_{s\in \mathcal H_r} \pi_r(s)\,e^{f_\theta(X(s,T))},\ \kappa\Big).
   $$

   - $F$ is total flushes and $H$ total hours.
   - $\pi_r(s)$ is the **hunted-area weighting**: uniform over the accessible-forest mask of region $r$ (§3.5), as a proxy for where cooperators hunt. A future refinement uses the owner's own GPS logs.
   - This term **pins the absolute scale** of $A\bar q\,e^{\alpha}$. It is what lets the product say "about 1.4 flushes/hr expected".

2. **Spring roadside drumming indices** (NH, VT and ME where available; NY DEC publishes route-level reports as a methodological analogue). These are modelled the same way, with the drumming-route buffers (about 0.5 km either side of each route) as $\pi_r$. They mainly inform $\alpha_{r,T}$ (cycle/WNV), with a separate scale parameter for the spring index.

3. **Wing and tail survey** (NH): the juvenile-to-adult-female ratio by region and year. It enters as a *covariate* on $\alpha_{r,T}$ (a productivity signal), not as a likelihood term.

These terms carry few observations (about 10 regions × about 8 years), so they barely move $f_\theta$. Their job is the **intercept and the year offsets**. Presence-background data cannot identify these (Ward et al. 2009; report §4.2).

#### 3.2.4 Owner and cooperator GPS hunt logs (gold labels; Phase 4)

Logs are kept with a phone GPX tracker plus a one-tap "flush" waypoint (any GPX app: OsmAnd, Gaia, Avenza). Each track $\tau$ is buffered by the encounter half-width $\omega$ (about 25 m). Flushes are an inhomogeneous Poisson process along the track:

$$
\#\text{flush}_\tau \sim \text{Poisson}\Big(A' \!\int_{\tau\oplus\omega} q(s)\,e^{f_\theta(X(s,T))+\alpha_{r,T}}\,ds\Big),
$$

with flush locations as marks. This is the only stream that measures exactly the hunter's estimand. It is **held out from training for the first season**, as the cleanest possible validation (§3.6). After that it is used for training with a time-split.

### 3.3 Features, with freshness as a first-class requirement (Q3)

The existing 15 accepted layers are kept as a base (after the CR-0035 registration repair; see risk K4). COVERT adds:

| Layer | Source (URL) | Why (inverted failure) |
|---|---|---|
| **Disturbance year stack 1985–2026** | LCMS v2024-10 fast/slow loss (GEE `USFS/GTAC/LCMS/v2024-10`); Hansen GFC v1.12 `lossyear` 2001–2024 (GEE `UMD/hansen/global_forest_change_2024_v1_12`); OPERA DIST-ANN-HLS 2023–2024 (GEE `OPERA/DIST/L3_DIST-ANN-HLS/V1`) and DIST-ALERT-HLS for 2025–2026 (NASA LP DAAC); LANDFIRE Annual Disturbance (existing) | R4: catch cuts up to the season. Ensemble vote: a pixel's last-disturbance year is the median of the products that fire, with a source-agreement count kept as a confidence channel |
| **Disturbance severity** | LCMS fast-loss probability; dNBR from annual leaf-on HLS composites | Separate clearcut from shelterwood and partial cut (report §1.8 caveat) |
| **Aged stand clock** $\text{tsd}(s,T) = T - \text{lastdist}(s)$, uncapped up to 40 yrs, plus an explicit hump basis | derived | Literature-shaped response: peak 5–15 yrs, good to 25, declining to 40 (report §1.2). Fed as B-spline basis functions with a **shape constraint** (unimodal) in the GBM path, via LightGBM monotone constraints on two split features $\min(\text{tsd},12)$ ↑ and $\max(\text{tsd},12)$ ↓ |
| **Leaf-off lidar understory metrics** | USGS 3DEP point clouds (all three states have statewide or near-statewide QL2 coverage; **vintage per tile varies, unverified per state**), https://www.usgs.gov/3d-elevation-program; Microsoft Planetary Computer `3dep-lidar-*` COGs | Share of returns 1–5 m and 2–6 m, P90 height (Koleck et al. 2026 used these). Leaf-off vintage dates are stamped so `tsd` can age them forward |
| **Meta 1 m canopy height** `mch_*` | existing CR-0032 | already shows +0.009 |
| **Phenology / spectral embedding** | annual HLS leaf-on and leaf-off medians, or frozen Prithvi-EO-2.0 embeddings (optional, Phase 5) | aspen and birch vs conifer signal missing from categorical LANDFIRE |
| **Woods roads and gated roads** | OSM `highway=track|unclassified` + TIGER S1500 (4WD) + state forest road layers | Inside $f_\theta$ this is *hunter access and brood habitat*, not birder effort (report §1.6) |
| **Climate and terrain** | 3DEP DEM; Daymet v4 snow-water-equivalent Dec–Mar means (GEE `NASA/ORNL/DAYMET_V4`) | Snow roosting (report §1.4) and WNV gradient |
| **Multi-scale summaries** | derived | Per covert: composition at 0 (inside), 250 m, 500 m and 1,000 m rings, per §1.5 home-range scales. Replaces the single 1.9 km window |

All features are **year-indexed**. A training record in year $t$ reads the stack as of $t$. Prediction for season $T$ reads the stack as of $T$. This needs no vintage-matching tolerance hack, because the disturbance clock is computed per year from a continuous 1985–2026 record. LANDFIRE categorical layers that are *not* annual keep the current nearest-vintage rule.

### 3.4 The model: two-level, pixel encoder plus covert ranker

**Level 1, the habitat intensity $f_\theta(s)$ at 30 m.** There are two interchangeable implementations, run in this order:

- **(a) LightGBM with a custom cloglog-offset objective.** For the checklist term with the Royle–Nichols link, the per-checklist gradient and Hessian with respect to $\eta_j=\log\Lambda_j+g_j$ are closed-form:
  - with $p=1-e^{-e^{\eta}}$, the gradient is $\partial\ell/\partial\eta = e^{\eta}\,(1 - y/p)$;
  - the Hessian is $e^{\eta}(1-y/p) + y\,e^{2\eta}(1-p)/p^{2}$, clipped to ≥1e-6.

  $g_\phi$ is first fitted as a GAM offset (pyGAM or `statsmodels` GLM with splines), then the two are alternated: boost $f$ with $g$ as an offset, refit $g$ with $f$ as an offset, for 3–5 rounds. The disk average $\Lambda_j$ is approximated by evaluating features on a 7-point disk stencil and averaging $e^{f}$ (the tree outputs are additive in $\eta$, so a 7-copy expansion with log-sum-exp aggregation is done in a custom objective via grouped rows). This reuses the feature extraction pattern of `diagnose_gbm_baseline.py`.
- **(b) Neural ISDM (Phase 3).** The existing `GrouseResNet` trunk, minus the centre skip, is the encoder $E(X)\to h\in\mathbb R^{512}$, and $f_\theta=\text{Lin}(h)$. $g_\phi$ is an MLP on $w$. Training uses the summed likelihoods of §3.2 with stream weights $\beta_{\text{chk}}=1$, $\beta_{\text{PO}}\le0.25$ and $\beta_{\text{disagg}}=1$; the disaggregation sums are approximated by a 2,000-cell stratified sample per region per step. The disk integral uses the existing D4-invariant patch reader at 7 offsets. Labels are about 50× more numerous than now, so a pretrained trunk should benefit, which is the one place the "capacity" argument might reopen.

**Level 2, the covert ranker.** Candidate coverts come from object generation (Q4):

1. **Harvest/disturbance patches.** Connected components of `lastdist ∈ [T−25, T−4]` from the fused stack, after a 1-pixel morphological open. Patches < 2 ha are merged into neighbours, and patches > 60 ha are split by SLIC superpixels on (tsd, ch, deciduous share).
2. **Non-disturbance cover types.** Alder/shrub wetlands (NLCD 90 with EVH shrub), old fields reverting (NLCD 52 with rising TCC), and aspen/birch EVT stands. These are segmented by SLIC on the same channels.
3. **A background lattice** of 25 ha hexagons over remaining forest, so ranking stays complete and no stand type is omitted by construction.

For each covert $c$, the ranker computes $\overline N_c = \operatorname{mean}_{s\in c} e^{f_\theta(s)}$, the predictive uncertainty (§3.7), huntability $q_c$, and access class $a_c$ (§3.5). Then

$$
\hat\mu_{c,T} = A\,\bar q\,e^{\hat\alpha_{r,T}}\;q_c\;\overline N_c ,\qquad
q_c=\sigma\big(\beta_0+\beta_1\,\mathbb 1[\text{tsd}<4]+\beta_2\,\text{share returns 0.5–2 m}\big).
$$

$q_c$ starts from an expert prior ($q\approx0.5$ for stands under 4 years old, $\approx1$ otherwise) and is **learned** from GPS logs in Phase 4, where unwalkable slash shows as low flushes per buffered metre despite high $N$.

### 3.5 Access and reachability gate (Q5)

Each covert gets an **access class**:

| Class | Rule | Sources |
|---|---|---|
| A1 open public | intersects PAD-US 4.1 with `Pub_Access = OA` and hunting not prohibited (Federal: WMNF, GMNF; State WMAs, Maine Public Reserved Lands, NH/VT state forests) | https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download; state WMA layers (ME GeoLibrary, NH GRANIT, VCGI) |
| A2 open by program | NH Current Use parcels with the 20% recreation adjustment (land must be open to hunting); NH Fish & Game's Current Use page. Parcel GIS needs town assessor data or NH DRA (**availability unverified**) | https://www.wildlife.nh.gov/current-use |
| A3 open by custom | Maine large industrial ownership / unorganized territories (customarily open; some behind North Maine Woods or KI-Jo Mary gate fees). Flag "gate fee / check rules" | PAD-US easements; Maine Land Use Planning Commission jurisdiction layer |
| A4 unknown private | default for other private parcels. Shown but grey-hatched, with "ask permission" | — |
| X excluded | developed (NLCD 21–24 within 150 m, which keeps state safety-zone setbacks conservatively), town parks closed to hunting, PAD-US `Pub_Access = XA` | PAD-US, NLCD |

**Reachability** is the walking distance from the nearest drivable road (TIGER S1100–S1400 plus OSM tracks without `access=no`) over a cost surface with slope penalty. Coverts more than 3 km walk in are flagged "remote" (this is a preference, not exclusion).

There is no statewide posted-land layer for ME, NH or VT that I could find (**unverified absence**), so class A4 is honest about uncertainty rather than pretending.

### 3.6 Evaluation (Q6, Q7): how we avoid fooling ourselves

**Splits.**

- Spatial blocks of **10 km**, not 3 km. The block size is checked against the variogram of residuals from the Phase 1 model (report §4.3). Everything is 5-fold blocked CV, with folds shared across all model families so stacking is legal.
- A **temporal hold-out**: train on seasons ≤2023 and test on 2024–2025 checklists. This tests the freshness machinery directly.

**Metrics, in priority order:**

1. **Top-k effort-standardised detection lift (TkL).** On held-out checklists, take the checklists whose disk falls in the model's top $k$% of forest (k = 1, 5, 10). Then
   $$\text{TkL}_k=\frac{\sum_{j\in\text{top}k}y_j\,/\,\sum_{j\in\text{top}k}\hat P_0(w_j)}{\sum_{j}y_j\,/\,\sum_j \hat P_0(w_j)},$$
   where $\hat P_0(w_j)$ is the detection probability from an **effort-only** model (habitat-blind). TkL is an observed/expected ratio: it asks how many more grouse are detected in top-ranked places *than effort alone predicts*. It cannot be gamed by sending checklists to hotspots, because effort is in the denominator.
2. **ARU drumming occupancy (independent, VT).** USGS/VT Cooperative Unit ARU data in the Green Mountain NF, 2022–2023, 9,500+ hours, with model-verified detections (Clarfeld et al. 2025, data release DOI 10.5066/P13EFLXX). Metrics: Spearman correlation of site detection rate against $\hat N$, and the mean detection rate in the model's top versus bottom tercile. The model **never trains on it**. Site coordinates may be withheld, so a data request may be needed (**unverified**).
3. **Owner GPS hunt logs (independent, the hunter's own estimand).** Season 1 is purely held out. Metrics: Spearman correlation of flushes/hr per covert visit against $\hat\mu_c$, and the realised flushes/hr in coverts ranked top-20 versus a random sample of coverts the owner was sent to for exploration (§3.8 makes this a randomised comparison by construction).
4. **Regional anchors (weak, coarse).** Leave-one-region-out prediction of NH regional flush rates (rank correlation over region-years).
5. **Continuity.** Legacy presence-background AUC on the existing validation split, computed by scoring the existing positives and negatives with $f_\theta$. It is reported so nobody can say COVERT "lost accuracy". It is **not** a selection criterion.

**Rank stability gate (Q11).** Across 5 seeds, and before versus after any data repair (BUG-0094 class), the top-500 covert list must have Kendall τ ≥ 0.8 and top-100 overlap ≥ 70%. Otherwise the product ships the ensemble mean with an "unstable" flag on the affected coverts.

**Leakage and self-fooling guards.**

- Effort-confound probe: on the final map, fit a GBM to predict $f_\theta$ from effort-only layers (hotspot distance, trail distance, checklist density). It must have $R^2 < 0.10$; above that, $\lambda_{adv}$ is raised. Run the same probe on the current CNN map as a baseline (Experiment E1, §7).
- Home-advantage caveat: COVERT is trained on checklists, so it has a home advantage on metric 1. Metrics 2 and 3 are therefore **decisive** for any claim of beating the status quo, and metric 1 is used for model selection only.

### 3.7 Uncertainty

- **Phase 1 (GBM):** 10-member bootstrap-by-block ensemble, giving the per-covert sd of $\log\overline N_c$.
- **Phase 3 (neural):** a deep ensemble of 5, giving the epistemic mutual information (report §4.7).
- **Map display:** the posterior mean together with an "exploration value" (§3.8). Coverts whose features fall outside the training envelope (Mahalanobis distance in embedding space beyond the 99th percentile) are flagged "extrapolated".

### 3.8 End product and learning loop (Q12)

1. **A season-$T$ covert layer** (GeoPackage plus PMTiles for phone display, e.g. in onX/Gaia/Avenza via KML import). It is rebuilt every September after the DIST-ALERT/LCMS refresh. Per-covert attributes:
   - $\hat\mu$, as flushes/hr where anchored, otherwise a percentile;
   - 80% interval;
   - access class and walk-in distance;
   - age since cut, area, dominant type;
   - "why" attributions (TreeSHAP top 3);
   - huntability flag.
2. **A regional season outlook:** $e^{\hat\alpha_{r,T}}$ from the spring drumming index, giving "expect about X% of the long-term average in region r". This answers "bad map or bad year?" (PM4).
3. **A recommender.** Each hunting day the owner gets 5 coverts within a chosen drive radius:
   - **4 by Thompson sampling.** Draw $\tilde\mu_c$ from the per-covert posterior (ensemble member or Laplace sample) and take the top 4 accessible ones.
   - **1 uniformly random accessible covert** from the top 30%. This gives a small, deliberate randomised sample, so realised flush rates in recommended against random coverts are an unbiased estimate of the product's lift (metric 3).
4. **Update.** After each logged hunt, the GPS-log likelihood (§3.2.4) updates a **covert-level random effect** $u_c \sim N(0,\sigma_u^2)$ in closed form. A gamma–Poisson conjugate update on $e^{u_c}$ needs no retraining. $f_\theta$ is refit at season end.

---

## 4. Why this beats the status quo

The report's diagnosis has five parts. COVERT answers each with *new information* or a *different question*, never with more capacity.

1. **"The data is the ceiling" (report §5.4).** The ceiling exists because labels are presence vs target-group background, with unlabelled presences among negatives and no effort information. Complete checklists add **true zeros with effort**, about 10–100× more labelled sites than the 6,232 positives now used (**order-of-magnitude estimate**), and a detection model. This is item 1 of the report's own ranked list, which no one has yet built. COVERT makes it the core and wraps it in what a hunter needs.
2. **The PU problem (report §4.4).** It disappears for the main stream. Non-detections are real non-detections, and the detection sub-model explains why a non-detection in occupied habitat is likely (short checklist, wrong month, mid-day). nnPU and the AUC bound $1-a/2$ apply to the presence-only side stream only, which is down-weighted.
3. **Effort bias (report §4.8, §5.3).** Today it is cancelled implicitly and imperfectly by the target-group choice, and the road-distance surprise shows it is not cancelled. COVERT **measures** effort per checklist, models it in a separate head, fixes it to a hunter counterfactual at prediction, and checks with a probe that the habitat function does not encode it.
4. **The estimand (report §5.1, §5.5).** The current score is a log density ratio tied to a 50:50 artificial prevalence and to design choices (buffer, envelope, non-vegetated share). COVERT's $f_\theta$ is a log *relative density*, and the disaggregation anchors give it an absolute scale in the hunter's units. The `--prior π` scenario hack becomes unnecessary.
5. **Stale and mis-scaled inputs (report §2.4, §1.8).** These are fixed by the annual disturbance clock aged to season $T$ and by covert-level objects at home-range scale.

The current model can win AUC through R1–R3 and R13 without improving any hunter decision. COVERT's selection metric (TkL) and its decisive validation (ARU plus GPS logs) cannot be won that way.

---

## 5. Expected gains, with honest uncertainty

These are priors, not results. Each comes with the measurement that would confirm or refute it.

| Claim | Expected | Uncertainty | Measured by |
|---|---|---|---|
| Effort-confound in the current map | Probe $R^2$ of current CNN logit on effort-only layers is 0.15–0.40 | Wide. Could be under 0.1, in which case R1 is overstated | E1 (§7), hours |
| Freshness error in the current map for season 2026 | 5–15% of top-5% pixels either cut 2023–2026 (now 0–3 yrs) or aged past 30 yrs | Moderate. Depends on Maine harvest rate (about 1–2%/yr of forest is harvested in ME per LCMS-type estimates, **unverified**) | E2, hours |
| TkL$_{5}$ on held-out 10 km blocks, COVERT-GBM vs current CNN scored on the same checklists | 1.6–2.2× vs 1.2–1.6× | High. eBird grouse detection is noisy. The ratio may be closer | Phase 1 |
| Spearman correlation with VT GMNF ARU site detection rates | COVERT 0.35–0.5, current CNN 0.15–0.35 | High. n (sites) is unknown and possibly < 100, so differences under about 0.15 will not be significant | Phase 2 |
| Owner's realised flushes/hr: Thompson top-4 vs randomised 5th covert | ≥1.5× | Very high. One hunter, about 30–60 covert-visits per season. Detectable only if the true lift ≥ about 1.6× (two-sided, power 0.8, CV of visit counts about 1.0; **back-of-envelope**) | Season 1 |
| Legacy AUC | 0.74–0.80. Not optimised, and could drop slightly | — | continuity only |

The honest summary: I **expect** COVERT to be clearly better on what a hunter experiences and only marginal on legacy AUC. If metrics 2 and 3 do not move, COVERT has failed, whatever metric 1 says.

---

## 6. Risks, failure modes and the cheapest falsification

| # | Risk | Severity | Mitigation / accepted risk |
|---|---|---|---|
| K1 | eBird grouse detections in October are rare. Most detection information is spring drumming or summer broods, so $f_\theta$ learns breeding habitat, not fall habitat | MAJOR | The seasonal spline in $g$ absorbs *detectability*. Habitat *use* differences are absorbed by a small season-interaction head $f_\theta + \Delta_{\text{fall}}(X)$ with strong L2 that is fitted only on Sept–Dec checklists. If Sept–Dec detections are under about 500, $\Delta$ is dropped and the risk is accepted. Breeding cover is still the best available proxy, since the literature (§1.4–1.5) puts fall birds within the same home ranges |
| K2 | EBD access takes days to weeks | MEDIUM | Phase 0 experiments (E1, E2) need no EBD |
| K3 | $f$ and $g$ are confounded: effort correlates with habitat | MAJOR | Disjoint feature sets, the adversary, the probe (§3.6), and decisive independent validation |
| K4 | BUG-0094/0095/0096 misregistered layers | MAJOR | COVERT consumes layers only after the CR-0035 repair. The rank-stability gate makes any residual artefact visible. COVERT's new layers come from GEE, so they must be fetched **on the template grid with an explicit `crsTransform`** and checked with `grid_mismatch` plus the BUG-0094 offset probe (`diagnose_fetch_tile_offset.py`). This is called out because it is exactly the bug class of PA rules in `docs/quality/PREVENTIVE_ACTIONS.md` |
| K5 | Regional survey data are not obtainable for ME/VT | MEDIUM | The product falls back to a relative index for those states. The NH anchor alone still tests the scale model |
| K6 | ARU site coordinates are unavailable | MEDIUM | Ask USGS VT Coop Unit / VT F&W. Fallback: the Koleck et al. 2026 PA dataset as an *out-of-region* transfer test (weaker), plus GPS logs |
| K7 | The access gate is wrong (posted land) | MAJOR (ethical/legal) | Classes are explicit. A4 is never presented as open. The product carries a disclaimer and is for the owner's own use; no public release |
| K8 | Thompson exploration wastes hunting days | LOW | Only 1 of 5 recommendations is random, and it is drawn from the top 30% |
| K9 | Covert segmentation errors (merged stands) | MEDIUM | The hex background lattice guarantees coverage, and segmentation parameters are tuned on TkL |
| K10 | The project's quality system (CLAUDE.md) requires a CR for each change | process | §8 is already split into independently landable CRs (CR-0011 A5) |

**Cheapest falsification experiment (E1 + E2, under one day, no new labels).** Can the *current* map be shown to fail hunters in the specific ways COVERT claims to fix?

- **E1, effort probe.** On a 50k-pixel random sample of forested pixels from the current best map, regress the CNN logit on effort-only layers with a 5-fold spatially blocked LightGBM. The layers are:
  - target-group record density at 1 and 5 km, from the negatives pool already on EC2;
  - distance to eBird hotspots (public hotspot list via API `ref/hotspot/US-ME` etc.);
  - distance to OSM hiking paths.

  If $R^2 < 0.05$, then R1 (birder-tracking) is **not** a material problem, and COVERT's main motivation weakens to freshness, scale and access.
- **E2, freshness audit.** Using GEE (LCMS v2024-10 fast loss, Hansen 2023–2024 loss, OPERA DIST-ANN 2023–2024), compute the share of the current map's top-5% pixels that were cut in 2023–2024. Using `tsd`, compute the share that will be older than 30 years in 2026. If both are under 3%, freshness is not a material problem.

If E1 and E2 both come back null, COVERT's case rests on scale, access and the estimand alone. I would then shrink it to Phases 1 and 3 (the checklist ISDM plus covert ranking).

**Falsification of COVERT itself (Phase 1 gate).** On 10 km held-out blocks, if COVERT-GBM's TkL$_5$ is not at least 10% (relative) above the current CNN's TkL$_5$ on the same checklists, *and* the ARU Spearman is not higher, stop and report that complete checklists do not add hunter-relevant signal.

---

## 7. Implementation plan

Each phase is a separate CR under the repository's quality system. Gate code is written first (CR-0011 A3), and phases are split by A5.

| Phase | Content | Effort | Exit criterion |
|---|---|---|---|
| **0 (day 1)** | E1 effort probe; E2 freshness audit; request EBD + SED; email NH F&G / ME IF&W / VT F&W for survey tables and the USGS VT Coop Unit for ARU site data | 1 day compute, plus emails | Numbers for §5 rows 1–2 |
| **1** | Checklist ISDM, GBM path: EBD ingest (`auk`-equivalent filtering in Python/pandas: complete, protocol, duration, distance), spatiotemporal subsampling, disk-stencil feature extraction reusing the existing patch reader, alternating GAM-$g$ / LightGBM-$f$ with the RN cloglog objective, effort-only reference model $\hat P_0$, TkL evaluation on 10 km blocks | 1–2 weeks | Phase-1 falsification gate (§6) |
| **2** | Freshness layers: fused disturbance stack 1985–2026 on the template grid (GEE `crsTransform`, BUG-0094 offset probe), tsd aged to $T$, hump-constrained basis; 3DEP understory metrics | 1–2 weeks (parallel to 1) | Grid checks pass; TkL gain from layers measured by ablation |
| **3** | Covert generation (patch + SLIC + hex lattice), access gate (PAD-US, state layers, NH current-use where obtainable), reachability; disaggregation anchors for $\alpha_{r,T}$ where data arrived | 1–2 weeks | Product v0 for season 2026 (or 2027 if late) |
| **4** | Recommender and GPS-log ingest (GPX → buffered track likelihood, conjugate covert effects); season-1 randomised evaluation | 3–5 days of code, then a season | Metric 3 |
| **5** | Neural ISDM (existing trunk as encoder, joint likelihood, adversary), deep ensemble; stack with the GBM via block-OOF | 2–3 weeks GPU | Beats GBM on TkL and ARU; else ship GBM |

### First experiment the owner can run on EC2 within a day (E2 + E1, sketched)

```python
# E2 freshness audit (Earth Engine, Python API)
import ee, rasterio, numpy as np
ee.Initialize()
lcms  = ee.ImageCollection("USFS/GTAC/LCMS/v2024-10") \
          .filter(ee.Filter.calendarRange(2023, 2024, "year")) \
          .select("Change").map(lambda i: i.eq(3))        # fast loss class (check code table)
fast  = lcms.max()
gfc   = ee.Image("UMD/hansen/global_forest_change_2024_v1_12").select("lossyear")
gfc_r = gfc.gte(23)                                       # 2023-2024
dist  = ee.ImageCollection("OPERA/DIST/L3_DIST-ANN-HLS/V1")  # band names: check catalog
recent = fast.Or(gfc_r)
# Export `recent` with crs + crsTransform = the region's template (EVT clip) affine,
# NOT a scale/region request (BUG-0094 class), then run check_layer_registration.py on it.
# Locally: top5 = map >= np.nanpercentile(map, 95); share = recent[top5].mean()
# Also: share of top5 with tsd(2026) > 30 using the existing tsd raster + (2026 - vintage).
```

```python
# E1 effort probe (LightGBM, 5-fold spatial blocks of 10 km)
# X_eff = [tg_density_1km, tg_density_5km, log1p(dist_hotspot), log1p(dist_osm_path)]
# y     = CNN logit at 50k random forested pixels of the current map
# report blocked-CV R^2; also repeat with road_dist added to see how much it explains.
```

---

## 8. Mapping to the repository's quality system

Proposed CR split (one landable change each, per CR-0011 A5):

1. **CR-a: Phase-0 diagnostics** (E1, E2). Read-only scripts, so they qualify as gate/test code.
2. **CR-b: EBD ingest plus checklist dataset.** Data pipeline only; writes a new `data/ebd/` tree after approval.
3. **CR-c: RN-cloglog GBM and TkL evaluator.** Model plus acceptance design; the TkL script is committed before approval.
4. **CR-d: Fused disturbance stack.** Generator code, which must pass `grid_mismatch` and the offset probe.
5. **CR-e: Covert objects plus access gate.** End-product code.
6. **CR-f: Recommender plus GPS-log ingest.**

None changes the existing CNN pipeline, so the current model stays as the baseline and comparator throughout.

---

## 9. References

Status key:
- **[V]**: verified this session by web search or fetch.
- **[R]**: cited by the project report (not re-verified here).
- **[unverified]**: from memory.

**Data**
- eBird Basic Dataset download (EBD + Sampling Event Data). https://ebird.org/data/download **[unverified this session]**
- eBird Status & Trends data access (`ebirdst`, Ruffed Grouse code `rugr`, 3 km weekly abundance). https://science.ebird.org/status-and-trends/download-data **[V]**
- LCMS v2024-10, Earth Engine catalog. https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_LCMS_v2024-10 **[V]**
- Hansen Global Forest Change v1.12 (2000–2024), Earth Engine catalog. https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12 **[V]**
- OPERA DIST-ANN-HLS V1, Earth Engine catalog (2023–2024). https://developers.google.com/earth-engine/datasets/catalog/OPERA_DIST_L3_DIST-ANN-HLS_V1 **[V]**
- OPERA DIST-ALERT-HLS V1 (data.gov record). https://catalog-beta.data.gov/dataset/opera-land-surface-disturbance-alert-from-harmonized-landsat-sentinel-2-product-version-1 **[V]**
- PAD-US data download (4.1, by state; public-access codes OA/RA/XA/UK). https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download **[V]**
- PAD-US 4.1 lookup tables. https://data.source.coop/cboettig/padus/padus-4-1/lookup/README.md **[V]**
- NH Fish & Game, Current Use (20% recreation adjustment requires land open to hunting). https://www.wildlife.nh.gov/current-use **[V]** (the parcel GIS availability is **unverified**)
- NH Fish & Game (2025). Ruffed grouse and woodcock seasons start October 1 (drumming survey, wing & tail survey, small game survey). https://nhfishgame.com/2025/09/22/ruffed-grouse-and-woodcock-seasons-start-october-1/ **[V]**
- NH Fish & Game, Small Game Summary Report (flush rates per hour by region). https://www.wildlife.nh.gov/sites/g/files/ehbemt746/files/inline-documents/sonh/small-game-summary.pdf **[V exists via search; contents not retrieved, 403 to this container]**
- NH Fish & Game, Ruffed Grouse Wing and Tail Survey. https://www.wildlife.nh.gov/hunting-nh/small-game-and-upland-bird-hunting/ruffed-grouse-wing-and-tail-survey **[V exists; 403 on fetch]**
- NY DEC ruffed grouse drumming survey report (methodological analogue). https://extapps.dec.ny.gov/docs/wildlife_pdf/grousedrumrpt22.pdf **[V exists]**
- Maine Forest Service, FOResT online Forest Operations Notifications (harvest notifications with maps; public GIS release **unverified**). https://www.maine.gov/dacf/mfs/newsarticle.html?id=2663369 **[V]**
- Clarfeld, L.A., Gieder, K., Abrams, R.H., Bernier, C., Cahill, J., Staats, S., Wixsom, S., Donovan, T.M. (2025). Two-stage models improve machine learning classifiers in wildlife research: a case study in identifying false positive detections of Ruffed Grouse (GMNF, Vermont, 2022–2023, >9,500 h ARU). USGS data release, doi:10.5066/P13EFLXX. https://www.usgs.gov/data/two-stage-models-improve-machine-learning-classifiers-wildlife-research-a-case-study **[V]**
- Lapp, S. et al. (2022). Automated recognition of ruffed grouse drumming in field recordings. *Wildlife Society Bulletin*. https://scholars.uky.edu/en/publications/automated-recognition-of-ruffed-grouse-drumming-in-field-recordin/ **[V]**
- Koleck, R. et al. (2026). Data from: Using passive acoustic monitoring and LiDAR to conduct a statewide assessment of ruffed grouse occurrence in Pennsylvania. Dryad, doi:10.5061/dryad.hmgqnk9xh **[V][R]**
- USGS 3D Elevation Program. https://www.usgs.gov/3d-elevation-program **[unverified this session]**
- Daymet V4 in Earth Engine (`NASA/ORNL/DAYMET_V4`). **[unverified this session]**

**Methods**
- Royle, J.A. & Nichols, J.D. (2003). Estimating abundance from repeated presence–absence data or point counts. *Ecology* 84:777–790. doi:10.1890/0012-9658(2003)084[0777:EAFRPA]2.0.CO;2 **[unverified]**
- Johnston, A. et al. (2021). Analytical guidelines to increase the value of community science data: an example using eBird data to estimate species distributions. *Diversity and Distributions* 27:1265–1277. doi:10.1111/ddi.13271 **[unverified]**
- Warton, D.I., Renner, I.W. & Ramp, D. (2013). Model-based control of observer bias for the analysis of presence-only data in ecology. *PLoS ONE* 8:e79168. doi:10.1371/journal.pone.0079168 **[R]**
- Fithian, W. et al. (2015). Bias correction in species distribution models: pooling survey and collection data for multiple species. *MEE* 6:424–438. doi:10.1111/2041-210X.12242 **[R]**
- Koshkina, V. et al. (2017). Integrated species distribution models. *MEE* 8:420–430. doi:10.1111/2041-210X.12738 **[R]**
- Ward, G. et al. (2009). Presence-only data and the EM algorithm. *Biometrics* 65:554–563. **[R]**
- Nandi, A.K. et al. (2023). disaggregation: an R package for Bayesian spatial disaggregation modeling. *Journal of Statistical Software* 106(11). doi:10.18637/jss.v106.i11 **[unverified]**
- Ganin, Y. & Lempitsky, V. (2015). Unsupervised domain adaptation by backpropagation (gradient reversal). ICML. https://arxiv.org/abs/1409.7495 **[unverified]**
- Russo, D. et al. (2018). A tutorial on Thompson sampling. https://arxiv.org/abs/1707.02038 **[unverified]**
- Achanta, R. et al. (2012). SLIC superpixels compared to state-of-the-art superpixel methods. *IEEE TPAMI* 34:2274–2282. doi:10.1109/TPAMI.2012.120 **[unverified]**
- Report sections cited throughout: `/home/user/grouse_refactor_ec2/docs/grouse_model_report.md` §1.2–1.8, §2.3–2.4, §4.1–4.8, §5.1–5.6.
