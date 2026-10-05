# Middle ground between E (FLUSH-E) and B (CEM-X)

*2026-10-05. Compiled from five independent synthesis proposals.*

Five new agents read the vote report (`VOTE_REPORT.md`), both finalists (`round3/E.md`, `round3/B.md`) and all seven reviews. Each wrote a complete E/B hybrid that addresses flaws V1–V13. Each also took one area in depth:

| Agent | Proposal | Area it worked out in depth |
|---|---|---|
| H1 | **TIER-FALL** | the decision and gating framework |
| H2 | **FOOTPRINT-MM** | the model, objective and features |
| H3 | **FALL-STACK** | seasonality, detectability, and transfer from birders to hunters |
| H4 | **Two Arenas** | the evaluation arena and data reality |
| H5 | **FLOOR-AND-EARN** | delivery, the product and expected value |

The full proposals and their verification scripts are in `hybrid/` (H1–H5).

This document gives the agents' consensus, settles the points where they disagree, and states the single recommended middle-ground design. Where a number comes from one agent's simulation, it is attributed to that agent. Wherever a ranking is given, it is the compiler's judgement.

---

## 1. The middle ground in one paragraph

Build **E's light fall-first model**, then judge it the way **B** would: on fall checklists, failing closed for the *product*. The model is E's, one row per checklist with an event-only effort term and a cloglog LightGBM. It uses H2's majorised objective, so B's pixel-scale footprint model is the same code with more stencil points, not a separate system. Three fitted maps are combined: an all-season map, an unshrunk fall-only map, and a clock-only fall map that can also use 2016–19 data. They are stacked using out-of-fold fall performance.

Decisions follow a pre-registered **four-tier ladder: SHIP / SHIP-WITH-BADGE / HOLD / KILL**. Gates with enough statistical power can kill. Significance gates can only promote. An inconclusive result never kills. The current map (H250, a zero-fit covert layer) stays on the owner's phone until the fitted map earns its place.

Training data loss is avoided by **out-of-fold scoring over 24 km super-blocks** instead of a flat buffer. The comparison against the CNN runs in a **parity arena** where the CNN has no unfair advantage. Because the CNN's own leaks all favour the CNN, that comparison can only veto, never promote.

**This October the owner hunts from H250.** The fitted map arrives in November if it passes, and is mainly a 2027 product.

---

## 2. What all five agents agree on

| Point | Agreement | Source |
|---|---|---|
| Replace the flat 2.5 km HH buffer with **out-of-fold scoring over super-blocks**, buffering only at super-block edges | 5/5. Retention rises from about 24–31% to 73–92% (H2 73%, H4 76%, H1/H5 92%; the spread reflects different edge-buffer assumptions) | R2's fix, simulated independently by H1, H2, H4 and H5 |
| Build HH from **`regions.block_split`**, with a test that fails a CSV-only build | 5/5. H4's simulation: a CSV-only build keeps 64% of HH checklists and inflates the detection rate 1.55× | V6 |
| The habitat model uses **2020+ checklists only**. Prediction uses the **2025 landscape**, because a 2026 feature year breaks the 2-year tolerance and on-disk TCC ends in 2023 | 5/5 | V1 |
| E's **independent, unshrunk fall-only model** sets the fall ranking. B's shrunk fall head is dropped | 5/5 | E |
| **Fall data cannot support a superiority kill on HH.** Fall acts as a harm or non-inferiority veto there, and decides positive questions only out-of-fold over the whole area | 5/5 (§4) | V7 |
| Every gate returns **PASS / FAIL / INCONCLUSIVE**. A gate whose minimum detectable effect (MDE) is worse than the effect that matters is advisory | 5/5 | — |
| **Inconclusive never kills.** H250 stays primary and the fitted map is shown as an overlay or blend | 5/5 | — |
| **The CNN comparison can only veto, never promote** | 5/5. H4 found two more CNN leaks, both in the CNN's favour (§6) | — |
| **Panel test is clock-only**, reported as an advisory | 5/5 | V3 |
| **Drop or demote E's season-contrast term and D's heard/seen modes** | 5/5. Season term: dropped (H2, H5) or recast as a nuisance offset (H3). Modes: a day-1 count and diagnostic only (H3) | R1, R5, B |
| **Not in v1:** AlphaEarth, OPERA DIST-ALERT, Hansen, lidar | 5/5. The CR-0034 download path accepts only north-up 30 m on one CRS (H4). These need their own CR | V5, V9 |
| **H250 ships first**, about 9–19 Oct | 5/5 | B, A, D |

---

## 3. Where the agents differ, and the resolution

| Question | Options | Resolution | Why |
|---|---|---|---|
| **Super-block size** | 24 km (H2, H4) vs 25 km (H1, H5) | **24 km** | 24 km is exactly 8×8 of the 3 km blocks, so no block is split (H4). The retention difference is negligible. |
| **Objective** | Row-wise stencil mean (H1, H3, H5, E) vs B's pixel-scale grouped objective | **H2's majorised Hessian H_m = s_m·ℓ_ηη, implemented once.** Stage 1 runs it with one stencil point per checklist (E's model). Stage 2 adds more points and is kept only if it wins out-of-fold. | **Proof:** for detections, the gap to the exact Hessian is s_m(1−s_m)(ℓ_ηη − ℓ_η) ≥ 0, and it equals the exact Hessian for non-detections. Summed over a checklist, it gives the one-row cloglog Newton step. The compiler checked this algebra. **Simulation (H2):** B's exact Hessian diverges after one tree, and R3's clamp takes steps 7–13× too large. H2's version beats E's model on held-out deviance in all 5 synthetic worlds and ranks coverts best in 4 of 5. **Implementation note (H2):** the intercept must be fitted into `init_score` before boosting. |
| **Fall model** | A single fall-only model (H1, H4, H5) vs a stacked set (H2, H3) | **Stack three models:** all-season H; unshrunk H_fall (2020+); and H3's clock-only H_fall^clk | H_fall^clk uses only `tsd`, `nlcd` and terrain. All of these are on disk for 2016–2025 (CR-0035 inventory), so the clock-only model can legally add 2016–19 fall rows, about 40% more fall data (H3). Stack weights come from out-of-fold Oct–Nov deviance. If the weights are inconclusive, the minimax-regret weight from the injection test is used. |
| **Primary fall metric** | Fall top-5% lift (TkL₅; B, E) vs fall effort-stratified AUC | **Fall effort-stratified AUC** is the binding metric. TkL₂₀ and TkL₅ are reported last in a fixed testing order. | H1's simulation: on HH, fall AUC has MDE 0.024–0.027 against an expected gain of 0.04–0.05. TkL₅ has MDE about 0.58× against an expected gain of about 0.44×, so a TkL₅ kill would stop a working model 40–70% of the time. |
| **Decision framework** | H1's four-tier ladder; H2/H4 non-inferiority veto; H5 pass/inconclusive/fail against H250 | **H1's ladder**, with H4's two arenas as the venues (§4) | It is the most fully specified, and its operating characteristics are simulated (§4.3). |
| **Multiplicity** | Holm (B) vs none (E) vs H1's scheme | **H1:** binding gates form an intersection–union conjunction, each at α = 0.05, with no Holm (R2). Superiority uses a fixed testing order. Holm applies only to admitting optional feature blocks. Two looks, with O'Brien–Fleming spending (z ≥ 1.82 at Look A, z ≥ 1.74 at Look B). | A conjunction of tests already controls false shipping. Adding Holm only costs power (R2). |
| **Randomised fifth covert** | Uniform over accessible coverts (B, E, H5) vs drawn from fall-map quintiles 2–5 (H3) | **H3's stratified draw, with known inclusion probabilities.** Lift is estimated by inverse-probability weighting, so it stays unbiased. | H3: at 40 visits, SE of the calibration slope falls from about 0.48–0.65 to about 0.21–0.28, while lift against a random baseline stays estimable. |
| **Birder-to-hunter transfer** | Not modelled (B) vs H3's ladder | **H3's ladder.** 2026: fit a scalar κ, plus a calibration slope b with an errors-in-variables correction. A cover term ω only after 100 or more logged hunts. The owner's eBird observer ID is excluded from training. The scorecard is an independent scorer, reported as a partial Spearman correlation controlling for H250, and never selects a model. | It answers R5's shared-assumption challenge without assuming the transfer works. |
| **Off-support (unbirded) areas** | A's ecological fallback (H5) vs a badge only | **H5:** blend toward an ecological floor where **geographic** checklist support is low, with support computed from effort only (never detections). Blend weight set by simulation, not tuned on HH. Card badge: "data-driven / ecology-driven". | This answers R1's covariate-space objection and R5's off-trail concern. |
| **Timeline** | Fitted map on 5 Nov (H2), 9 Nov (H3), 9–13 Nov (H4), 13 Nov (H1), 23–30 Nov (H5) | **Plan for mid-to-late November.** Treat the fitted map as a 2027 product with a possible late-2026 preview. | H5 is the only agent that budgets QMS review time at 4 working days per week. CR-0035 still has steps 3–5 to run (H3 assumes it closes about 16 Oct; H4 about 9 Oct). |

---

## 4. Decision framework, from H1 with H4's arenas

### 4.1 Two arenas (H4)
- **Arena P (parity).** Train on every checklist outside HH with no buffer, the same label access the CNN had. Compare against the CNN on HH ∩ out-of-fold, fall only. This arena is used only for the CNN comparison.
- **Arena O (out-of-fold).** Score every 2020+ checklist across the area, out-of-fold over 24 km super-blocks. The edge buffer is footprint + 0.5 km. This arena decides everything that does not involve the CNN: the signal and futility gates, stack weights, and comparison against H250.

### 4.2 Gates (H1)

| Gate | Question | Arena | Role | Effect |
|---|---|---|---|---|
| Integrity | V1 year/source-year, V6 block_split, feature parity, Hessian check, permutation ≥ 50 draws | — | binding, exact | Any failure stops the run (a defect, not a verdict) |
| G-SIGNAL | Is there habitat signal at all? | O, fall | binding | KILL only if a powered futility test holds, i.e. the MDE, computed in T0 on real geometry, is ≤ the pre-registered minimum important effect |
| G-NONINF | Is it no worse than the CNN and H250? | P (CNN) / O (H250), fall AUC, margin 0.01 | binding | KILL-harm only on significant harm |
| G-SUP | Is it better than the CNN? | P, fall, fixed order: AUC → TkL₂₀ → TkL₅ | promotes only | Failure caps the tier at SHIP-WITH-BADGE and never kills |
| Advisory | First-visit, clock-only panel, cross-play, off-trail, detectability check by injection, forecast back-test (clock-only, V10) | O | reported | Shown on cards and in the verdict, not binding |

### 4.3 Tiers and what the owner sees

| Tier | Primary map on the phone | Fitted map |
|---|---|---|
| SHIP | fitted fall map | primary |
| SHIP-WITH-BADGE | fitted map, with a banner: "not worse than the old map in fall; superiority unproven" | primary |
| HOLD | H250 | "unproven" overlay, with one re-look after the 2026 fall data are released. If still inconclusive, it retires to an overlay. |
| KILL | H250 | withdrawn. H250, access classes, the flush ledger and the field arm continue. |

**H1's simulated operating characteristics:**

| True situation | Outcome |
|---|---|
| The model truly works (+0.04 AUC) | SHIP 99.5% |
| The model equals the CNN | SHIP 5.5%, SHIP-WITH-BADGE 16%, HOLD 73%, KILL 5.5% |
| The model is worse (−0.013 AUC) | promoted 3% |
| The model has no habitat signal | KILL 100% |

H2's power analysis is less optimistic. It estimates about a 1-in-3 chance of shipping a "fall-unconfirmed" map. The two analyses use different fall-volume assumptions, and the complete-checklist filter factor is **unverified**. Settle this in T0 on the real EBD before any gate binds.

---

## 5. Phased plan (one owner; CR-0035 first; acceptance code written first)

| CR | Content | Acceptance checks written first | Est. working days |
|---|---|---|---|
| CR-0035 | **Finish:** step 3 gate, step 4 split and acceptance, step 5 before/after evaluation | already written | 2–4 |
| CR-0036 | **H250 v0 product.** Zero-fit covert layer from `tsd` on disk plus PAD-US access. Cards include "freshness: cuts after 2024 not visible". Daily list is 4 coverts plus 1 random. GPX/KML export, a flush ledger, and the owner's scorecard frozen first. | scorecard frozen before any map is shown; ledger schema | 2.5–3 |
| CR-0037 | **Tier harness and injection test T0** (acceptance code only) | MDE on real geometry; cheater cases; ≥ 50 permutation draws; O'Brien–Fleming boundaries | 5–5.5 |
| CR-0038 | **EBD ingest:** complete checklists 2010+, zero-fill, HH from `block_split`, super-block ids, first-visit flags | 2020+ habitat gate; source-year gate (TreeMap and `mch_*` are written for every year but describe one source year, H2); CSV-only HH build fails | 3.5 |
| CR-0039 | **Stencil features:** one shared point-feature function with fixed windows (90 / 270 / 630 / 1950 m), class fractions, parity gate | training ≡ prediction parity; no averaged categorical codes | 4 |
| CR-0040 | **Fit and verdict:** majorised objective, effort GAM, the three-model stack, ecological blend, Look A | Hessian ≥ exact; `init_score` set; gates per §4 | 6–6.5 |
| CR-0041 | **Product v1** for the tier reached | parity of covert scoring with the likelihood kernel | 4 |
| 2027 | LCMS 2025-11 / Hansen v1.13 / OPERA clock under a new download-path CR; TCC v2025-6 migration (to 2025); refit with 2026 fall data and the owner's hunts; κ and W(s) from logs; Look B | each its own CR | ~30 |

**Total for 2026:** about 24–31 working days after CR-0035. H250 reaches the field in mid-October. The Look A verdict comes in early to mid November, and the fitted map follows in mid-to-late November if the tier is SHIP-WITH-BADGE or better.

---

## 6. New facts surfaced during this round

| Fact | Found by | Status |
|---|---|---|
| **GBIF holds no 2025 eBird records**, so every "2016–25" GBIF figure in the competition actually ends in 2024. Oct–Nov 2016–24: 4,484 (VT counted); 2020–24: 3,198; Sep–Dec 2020–24: 5,774. | H1, H3, H4, H5 (GBIF API) | Consistent across four agents. The owner's EBD download will contain 2025. |
| **The disturbance record stops in 2024.** `tsd` for 2025 just ages the 2024 record, so 2025 cuts are invisible. | H5; **confirmed by the owner's step-2 log** ("disturbance years found: 1999–2024"; VT 2024 and 2025 both 10.7% disturbed) | A data-latency limit, not a code defect. H250 cards must say so. LCMS 2025-11 can fill it under a new CR. |
| **The CNN's checkpoint was selected on HH** (`train.py:935`, `--select-by rank`), and **its negative weights use all sightings before the split** (`analyze_grouse.py:1099-1100`) | H4 | Both leaks favour the CNN, so CNN comparisons lean toward a false kill. That is why the CNN comparison can only veto. The compiler confirmed that `--select-by rank` is the default at `train.py:935`. `analyze_grouse.py:1099-1100` writes `envelope_metrics_{region}.csv` from all evaluated sightings. Whether that file feeds the negative weights before the split is **not yet traced**. |
| **The CR-0034 download path accepts only north-up 30 m on one CRS.** Hansen (30.92 m geographic), AlphaEarth (10 m) and OPERA (two UTM zones) need a new path. | H4 | Confirms V5. |
| **Data versions:** LCMS v2025-11 covers 1985–2025 (v2024-10 is deprecated); Hansen v1.13 covers 2001–2025; DIST-ALERT is on LP DAAC/AWS (2022–2026), not in Earth Engine; AlphaEarth covers 2017–2024; **TCC v2025-6 runs to 2025** (only the pinned v2023-5 ends in 2023); HF437 is Maine only, 1986–2019. | H1, H4 | Web-checked by the agents. |
| **TreeMap and `mch_*` pass the year filter while describing another year,** because a file is written for every year | H2 | Hence the source-year gate in CR-0038. |
| **LightGBM custom objectives need the intercept in `init_score`,** or the model silently predicts a constant | H2 (by running it) | Written into CR-0040 acceptance. |

---

## 7. What the middle ground gives up

- **From pure E:**
  - its fast 2026 timeline (the fitted map arrives about 2 weeks later than E claimed);
  - the season-contrast term;
  - AlphaEarth and fresh-cut alerts in v1;
  - E's loose either-test-passes kill rule.
- **From pure B:**
  - "every gate decided on fall HH with Holm" (replaced by powered gates plus fall non-inferiority);
  - B's pixel-scale model as the default (it is now an optional stage 2);
  - B's panel test as a habitat-model test (now a clock-only advisory);
  - the control-species gate.
- **Accepted residual risk:**
  - a drumming-tilted or "fall-unconfirmed" map can reach SHIP-WITH-BADGE or HOLD (H3: about 10–15%; H2: up to about 1 in 3), always badged and never replacing H250 without passing G-NONINF;
  - the transfer from birders to hunters stays largely unvalidated until the owner logs enough hunts.

## 8. Unverified items to settle before relying on them
- **Fall volume and gating:** the complete-checklist retention factor, the design effect and the fall pair counts. These decide whether H1's or H2's operating characteristics apply; measure them in T0.
- **Encodings and versions:** the EVH/EVC code-to-midpoint mapping, and whether TreeMap 2023 has been ingested (the code and `ARCHITECTURE.md` disagree).
- **External data:** NH flush-rate tables, and the fall dispersal and drumming facts (search-summary level only).
- **CNN leak:** the envelope-metrics path from `analyze_grouse.py` into the negative weights (H4's second leak).
