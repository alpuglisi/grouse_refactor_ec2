# Ruffed Grouse habitat and the grouse suitability model: a research report

*Compiled 2026-10-05 from five independent research passes over the literature and this repository (`grouse_refactor_ec2`, branch `claude/nice-cori-creqpb`). This is background reading. It is not a change request and nothing in it changes code or data.*

## Executive summary

- **Habitat (§1).** Ruffed Grouse depend on young, dense, mostly deciduous regenerating forest (roughly 5–25 years after disturbance, with aspen especially valuable), mixed within a few tens of hectares with older forest and conifer cover. Stem density and interspersion matter more than any one forest type.
- **Representation (§2).** Each record becomes a 64×64 window of fifteen 30 m raster layers (LANDFIRE, NLCD/TCC, TreeMap, roads, years since disturbance). The labels contrast eBird grouse records with a target-group background of other-species records. That background is buffered, thinned, year-matched and envelope-weighted.
- **Current model (§3).** The model is a ResNet-18-style CNN with CBAM attention, attention pooling, a centre skip and a dilated second branch. It is trained with the AN-full/focal loss, AdamW with warm restarts, and EMA, and is evaluated with D4 test-time augmentation on spatial-block validation. Platt calibration follows.
- **Unused methods (§4).** The report covers MaxEnt and point-process models, occupancy and integrated SDMs, spatial random effects, PU learning, tree ensembles and stacking, newer deep architectures, uncertainty quantification, bias correction and attribution. Section 4 ends with a ranked list of eight next steps. The top one is eBird complete-checklist detection/non-detection data, used in an occupancy model or integrated SDM.
- **Interpretation (§5).** The score is a log density ratio of "where grouse get reported" against "where birders report other birds". It is not occupancy, abundance or demographic habitat quality. On the same inputs, a gradient-boosted tree matches the CNN's leak-free AUC (about 0.76–0.77). So the ceiling comes from the data and labels, not from the network, and only new information has moved it.

## Contents

1. [Ruffed Grouse habitat](#1-ruffed-grouse-habitat)
2. [How habitat is represented in the data](#2-how-habitat-is-represented-in-the-data-mathematical-view)
3. [The mathematics of the current model](#3-the-mathematics-of-the-current-model)
4. [Mathematics of machine-learning methods not yet used](#4-mathematics-of-machine-learning-methods-not-yet-used)
5. [An abstract interpretation of the current model](#5-an-abstract-interpretation-of-the-current-model)
6. [Notes on sources and open items](#6-notes-on-sources-and-open-items)

---

## 1. Ruffed Grouse habitat

The Ruffed Grouse (*Bonasa umbellus*) lives year-round in forest and does not migrate. Across its range, and in Maine, New Hampshire and Vermont in particular, it depends on **young, dense, mostly deciduous forest** next to older forest and some conifer cover. Habitat quality depends less on any one forest type than on three things: (a) how much regenerating forest there is, (b) how dense its stems are, and (c) how closely young stands, older stands and conifer cover are mixed within a few tens of hectares [1][2][4].

### 1.1 Forest type and composition

- **Aspen and poplar are the best cover type.** Quaking and bigtooth aspen of different ages can meet every year-round need in the northern part of the range [1]. Aspen supports more grouse than other forest types. New Hampshire Fish & Game says directly that aspen forests "can support many more ruffed grouse than other types of forests" [3]. In Minnesota, grouse densities in young aspen were higher than in conifer forest, and populations in aspen-dominated landscapes are predicted to reach higher densities and to rise and fall more sharply [11]. In Michigan, the risk of grouse death fell as the amount of aspen younger than 30 years rose, on 3 of 4 study sites [1].
- **Other early-successional hardwoods.** Paper birch, willow, alder, cherry and young northern hardwood are also used. Vermont Fish & Wildlife names aspen and paper birch as the most preferred [4], and NH Audubon describes "dense clumps of young aspen, willow, or birch" [16]. Maine IF&W lists hardwood-dominated and softwood-dominated mixedwood, upland and lowland hardwoods, old fields and orchards as grouse cover [2].
- **Mixed deciduous–conifer forest.** This type is selected in New England. In Rhode Island, grouse selected early-successional forest, mixed deciduous–conifer stands, deciduous forest and forested roads [9]. The Rhode Island landscape model found deciduous and mixed-conifer cover to be the strongest predictors at the 25 ha scale [10].
- **Conifer has two sides.** Some conifer is useful for winter and thermal cover (see 1.4). Large, closed conifer stands are poorer habitat, however:
  - Rhode Island grouse avoided evergreen forest [9].
  - In Minnesota, survival in closed-canopy pine averaged 12.6 months, compared with 19.3 months in hardwoods [1].
  - In Alberta, density of large conifers (>20 cm DBH) was negatively associated with grouse abundance [1].
  - In central Maine, nesting females chose sites with more conifer stems, but females at sites with more conifer stems were *less* likely to survive nesting. The authors recommend keeping conifer stem density below about 4,000 stems/ha at nest-site scale [5].
  - The likely best mix is mostly hardwood with scattered or patchy softwood, not pure stands of either. A Pennsylvania LiDAR and acoustic study likewise found the highest occurrence in "hardwood forests with some conifers and well-developed understories" [14].

### 1.2 Stand age, successional stage and disturbance

- **Core age window: about 5–25 years after disturbance.**
  - NH Fish & Game: grouse are "abundant only where young forests, those from 5 to 20 years of age, are common" [3].
  - Across the range, peak densities occur in stands 5–10 years old and remain high until about 25 years. Broods use the youngest stands. Stands older than 25 years are used mainly for feeding and occasionally for breeding [1].
  - In Minnesota hardwoods, winter survival was best in 12–25-year stands (average survival 22.3 months) and worst in stands younger than 7 years (less than 5 months) [1].
  - Gullion's well-known Cloquet Forest (Minnesota) figure for 10–25-year aspen is about one pair per 7 acres (about 2.8 ha) [1].
- **How habitat value changes with age (summarised from [1][3][4]):**

  | Years since disturbance | Value to grouse |
  |---|---|
  | 0–4 | Brood foraging if herbaceous, but too open for adult cover |
  | ~5–15 | Peak cover. Very high stem density; drumming and brood use |
  | ~15–25 | Still good. Overwinter survival is best here |
  | ~25–40 | Declining. Stems thin out and the canopy closes. Mature aspen still provides winter buds |
  | >40–60 | Mostly feeding and winter budding. Breeding density is low unless the understory has been reopened |

  The exact breakpoints differ between studies and site productivity, so treat them as approximate.
- **Disturbance and harvest.**
  - Even-aged harvest that removes all or most trees at once is described by NH Fish & Game as the best tool for creating grouse habitat [3]. Today, harvest has largely replaced fire as the main disturbance.
  - Gullion recommended aspen clearcuts **no larger than about 10 ha (25 acres)**, so that no single age class covers too large an area [1].
  - The usual Lake States aspen prescription is small blocks cut on a staggered schedule, giving about four age classes about 10 years apart on a roughly 40-year rotation. This is widely cited but could not be confirmed from a primary source in this search, so treat it as **uncertain**.
  - Openings used for brood foraging are typically about 0.1–0.4 ha (0.25–1 acre). Operational cut sizes of about 1–16 ha (2–40 acres) are reported, and the presence of early-successional habitat matters more than the exact size [1].
  - Vermont recommends that every home range contain three age classes: **0–10, 10–25 and >25 years** [4].
- **Long-term regional context.** Early-successional habitat is shrinking across the eastern US because forests are maturing, parcels are being broken up, and harvest on public land has fallen. This shrinkage is the main proposed cause of long-term grouse declines [13][3][16].

### 1.3 Vertical structure, canopy height and stem density

The defining feature of grouse cover is **dense woody stems roughly 1.5–6 m tall**. These hide the birds from hawks and owls while leaving the ground clear enough to walk on.

- **Stem density thresholds** (converted to per-hectare figures, 1 acre = 0.405 ha):
  - Minimum for useful cover: about 2,000 stems/acre (about 4,900/ha) at least 5 ft (1.5 m) tall [1].
  - Optimal: about 6,000–8,000 stems/acre (about 14,800–19,800/ha). Hardwood stands with 6,000–25,000 stems/acre (about 15,000–62,000/ha) give excellent cover [1].
  - Understory stem density at drumming sites ranges from about 3,000–5,000/ha (Alberta, Ontario) to 30,000–33,000/ha in the Great Lakes states [1].
  - Regenerating aspen typically has about 12,000–14,000 suckers/acre at age 2, falling to about 6,000–8,000/acre by age 10. This comes from Ruffed Grouse Society material seen only in search snippets, so treat it as **uncertain** and confirm it in Gullion's work.
- **Structure measures that predict use.**
  - Brood sites have more herbaceous ground cover, more vertical cover between 0 and 2 m, more midstory stems and more invertebrates than random sites [15].
  - Activity centres are driven by vegetation cover above about 1 m [14 (secondary summary)].
  - Maine nest sites had more horizontal visual obstruction than nearby available sites [5].
- **Overstory.** In Maine, female survival while nesting fell as basal area rose. Each increase of 9.3 m²/ha (one standard deviation) cut survival by about 13.6%, and the authors recommend basal area below about **24 m²/ha** [5]. More generally, closed, tall canopies with sparse understory are poor habitat. They score well only where the understory has been opened up, for example after thinning or partial harvest [14].
- **Implied canopy-height window.** The literature supports a dense stratum about **1–10 m tall** with little tall overstory as the main signal of high-value habitat. No published 30 m-pixel canopy-height threshold was found, so this is **inferred** from the stem-height and stand-age figures above.

### 1.4 Seasonal needs

**Spring: drumming (males).**
- Males drum from a raised platform, usually a log about **20–40 cm in diameter** [1], or sometimes a stump, rock or stone wall [4].
- What matters is the dense stem cover *around* the log, which hides the male from raptors. Shrub or sapling density is the strongest predictor of which logs get used [1].
- Neighbouring drumming sites are usually more than **150 m apart** [1].
- Males hold small ranges: about 2.4–4 ha (6–10 acres) in Vermont [4] and about 9 ha in Minnesota in spring [1].

**Nesting.**
- Females nest on the ground, usually at the base of a tree, stump or sapling, in fairly open pole or mature stands near brood cover.
- In the central Maine study [5]:
  - 45 nests were monitored, from 37 females, in 2015–2017.
  - 49% of nests were at live trees, 20% at saplings and 13% under logs or brush piles.
  - Cumulative nest success was about 43%.
  - First clutches averaged about 9.8 eggs.
  - Coarse woody debris at the nest *lowered* both nest success (44% → 30%) and female survival. This is probably because it gives predators cover.
- Incubation lasts 23–24 days [1].

**Broods (June–August).**
- Chicks need **insects for protein**, found in herbaceous openings, forest roads, skid trails, log landings, edges of wildlife openings and young stands, all with overhead woody cover nearby [15][1].
- Use of roads and edges increases where young forest is scarce [15].
- Brood ranges are larger than other ranges: about 5–16 ha (12.9 ha in Minnesota, up to 40 acres in Vermont) to 43–59 ha in Tennessee and Pennsylvania [1][4].

**Autumn.** Birds eat soft and hard mast and green leaves, and young birds disperse. In Maine, October survival is lowest, mainly because of hunting [6].

**Winter.**
- *Food.* Mainly buds and catkins, especially the flower buds of **mature male aspen**, plus birch, hophornbeam, cherry and others. Before breeding, aspen flower buds made up 46% of crop contents in aspen forests [1]. In Maine, Heinrich found that feeding was concentrated into short sessions at dawn and dusk [7]. Older aspen (roughly 25+ years) is therefore needed *within* the landscape alongside young cover.
- *Snow roosting.* Grouse spend up to about 80% of winter roosting [8].
  - They dive into soft snow to make insulated burrows. This needs about **15–20 cm of snow**, and use rises sharply above about 30 cm [8].
  - In Maine mixed forest, birds switched from roosting 2–4 m up in dense conifers (when snow was about 15 cm) to diving into snow in open deciduous forest once fluffy snow reached about 40 cm. When the snow crusted over, they went back to shallow roosts under conifers [7].
  - In Wisconsin, birds that chose deeper snow survived better [8].
- *Conifer cover.* Conifers act as fallback thermal cover when snow is shallow or crusted [7][4]. Vermont notes that hardwood stands are still generally preferred because predators are a greater risk in conifer [4].
- *Winter survival.* In Maine, winter (January–March) has the lowest non-hunting survival [6].

### 1.5 Spatial scale, home range and interspersion

- **Home range.**
  - Annual ranges are about 2.4–16 ha (6–40 acres) in Vermont [4]. Maine IF&W says all needs are typically met within less than about 12 ha (30 acres) [2].
  - Females outside the brood season use about 2–14 ha [1].
  - Annual ranges are larger in poorer or southern habitat. In Rhode Island oak–hickory forest the mean was **103 ± 25 ha**, with no difference by age or sex [9].
  - Across 1,054 Appalachian seasonal ranges, smaller ranges contained more clearcuts and forest roads [17].
- **Interspersion.** The most important landscape feature is having the needed age classes and cover types *within one home range* [4][2]. In Minnesota, grouse density was highest in landscapes where forest types were evenly mixed [11].
- **Patch size and shape.** Males chose young aspen stands that were **large and round or square** over long, narrow stands with much edge [11][12]. In the Minnesota survey, mean stand size was 3.4 ha (range 0.1–122 ha) [12]. Edge is therefore valuable as interspersion between young and older forest, not as long, thin strips.
- **Landscape models (closest analogues for this project).**
  - Rhode Island model [10]:
    - Built at 1 ha and 25 ha scales.
    - Early-successional forest was the most consistent predictor, even though it covered less than 1% of the landscape. Riparian corridors and mixed conifer also mattered at the 1 ha scale.
    - Classification accuracy was 81–83%.
  - Pennsylvania model [14]:
    - LiDAR metrics measured within 50, 100, 250 and 500 m radii.
    - Metrics: 75th, 90th and 99th percentile heights, canopy-height variability, the share of returns at 1–5 m and 2–6 m, and the interquartile range of return heights.

### 1.6 Avoided or low-value habitats

- **Mature closed-canopy forest with a sparse understory.** It is poor for breeding cover but is used for feeding (mast, aspen buds). Some studies report selection of 40–80+ year stands for feeding, so mature forest is low value rather than strictly avoided [1].
- **Large conifer stands and evergreen forest** (see 1.1) [9][1].
- **Open fields and agricultural land.** Grouse live in forest-dominated landscapes. Old fields and orchards growing back to shrubs are used, but open, mowed or cropped land is not core habitat [2][1]. (In one Missouri release study, birds used open land more than expected. This is atypical and probably reflects the release context [1].)
- **Development.** Rhode Island grouse avoided developed land [9], and development and fragmentation are listed as threats in New Hampshire [16]. Low-density rural housing probably lowers suitability by removing habitat and stopping forest management. Direct dose–response estimates for grouse are sparse, so this is **uncertain**.
- **Wetlands.** The picture is mixed. Open marsh and bog are not used, but shrub wetlands, alder thickets, riparian corridors and lowland hardwoods are used and can predict presence [1][10][2].
- **Roads.** Low-traffic forest roads and skid trails are *selected* as brood and feeding habitat [9][15][17]. No ruffed grouse study was found showing avoidance of paved roads specifically. Any negative effect of major roads probably works through development and loss of forest rather than avoidance of the road itself (**uncertain**).

### 1.7 Population drivers

- **Habitat loss through forest maturation** is the long-term driver across the Northeast [13][3]. In Maine's industrial forest, regenerating stands remain more common than in southern New England. New Hampshire reports its highest grouse densities in the north [3].
- **West Nile virus (WNV).**
  - In Pennsylvania, grouse that occupied atlas blocks were less likely to stay there where WNV infection rates in mosquitoes were high. The authors concluded that "managing habitat may be insufficient" where WNV is intense. The link is correlational and does not show that WNV directly caused the decline [12a].
  - In Vermont, 16.7% of 30 hunter-collected samples (2019) had flavivirus antibodies, from Addison, Caledonia, Chittenden, Essex and Windsor counties [18].
  - In the Great Lakes, 12.5–29% of birds were exposed in 2018. Exposed birds can survive, and populations in high-quality young forest recovered more strongly [19].
  - Exposure risk is thought to be higher in warmer, lower-elevation and more fragmented areas (**partly inferred**; NH Audubon links WNV declines to fragmented habitat [16]).
- **Predation.** Raptors (especially goshawk and great horned owl) and mammals cause most deaths. Avian predators account for about 44–77% of mortality in some studies, and predation causes about 80% of nest losses [1]. Dense stem cover works mainly as protection from predators.
- **Cycles.** Populations in Canada, Alaska and the Great Lakes cycle roughly every 10 years, with lows often about 80% below peak and some links to snowshoe hare cycles. Cycles are generally **weak or absent elsewhere**, including most of New England [1][12]. A model trained on a few years of data from northern New England may still pick up year-to-year swings in abundance.
- **Climate.** Shorter seasons of snow cover and more rain-on-snow and crust events reduce opportunities to snow-roost. In Wisconsin, projected mid-winter snow depths of 8–15 cm would fall below the burrowing threshold [8]. Wet, cold weather during hatching (June) lowers chick survival (widely reported; not quantified in the sources gathered here). For northern New England this suggests a gradient in suitability with elevation and latitude.
- **Hunting.** Hunting causes most October deaths in Maine. Even so, a University of Maine study found current seasons, including late-season hunting, consistent with sustainable populations [6].

### 1.8 Implications for a 30 m species distribution model

The variables below are inferred from the evidence above; their ranking is a judgement.

1. **Time since disturbance / stand age.** This is probably the strongest single predictor. Use a forest-disturbance history product (for example Landsat-based LandTrendr, Global Forest Change loss year, or LCMS) to get years since last harvest or loss. Expect suitability to peak at about 5–20 years and decline after about 25–30 years [1][3]. Model it as a non-linear (hump-shaped) response, not a linear one.
2. **Canopy height and vertical structure.**
   - Share of the neighbourhood with canopy about 2–10 m tall.
   - LiDAR understory density, for example the share of returns at 1–5 m or 2–6 m [14].
   - Mean and maximum height and height variability.
   - Expect *low* suitability for both very short (<1–2 m, open) and tall closed (>15–20 m) canopy, unless the understory is dense.
3. **Forest type and composition.**
   - Deciduous or aspen-birch share. Aspen is the highest value if it can be mapped, for example with LANDFIRE EVT or a forest-type group raster.
   - Conifer share, expected to have a hump-shaped response: some is good, dominance is bad [5][9][11].
4. **Interspersion, edge and patch configuration, measured at home-range scale.**
   - Use moving windows of about 100–600 m radius (about 3–100 ha), covering the 2–100 ha range of home ranges [1][9][10].
   - Measures: Shannon diversity of age classes, edge density between young and mature forest, and the share of young forest within 250 m.
   - Combine more than one scale, as the Rhode Island (1 ha and 25 ha) and Pennsylvania (50–500 m) models did [10][14].
   - Patch compactness of young stands may add information [11].
5. **Anthropogenic variables.** Impervious surface or housing density (expected negative) [9]. Distance to forest roads may be *positive* at fine scale [9][15][17]. Distance to major roads may be negative, mainly as a stand-in for development.
6. **Climate and topography.** Snow-cover duration or mean winter snow depth, elevation, and growing-degree days, used as proxies for winter roosting and WNV risk [8][12a]. Wetland type should separate shrub and forested wetland (neutral or positive) from open emergent wetland and water (negative) [10].
7. **Caveats.**
   - A 30 m pixel is close to the size of a drumming log's surrounding cover patch. Pixel-level variables will be noisy, so neighbourhood summaries should carry most of the signal.
   - Partial harvests (shelterwood, selection cuts) are common in Maine and leave a tall residual canopy that hides a dense understory from optical canopy-height products. Leaf-off LiDAR or disturbance-intensity measures are needed to detect them.
   - Detections are concentrated along roads (drumming routes, eBird, hunter data), so sampling bias needs correcting.
   - Year-to-year population swings, including WNV years, will add noise unrelated to habitat.

### References (section 1)

1. Meyer, R. (2011). *Bonasa umbellus*. In: Fire Effects Information System. USDA Forest Service, Rocky Mountain Research Station. https://www.fs.usda.gov/database/feis/animals/bird/boum/all.html
2. Maine Department of Inland Fisheries and Wildlife (n.d.). Ruffed Grouse – species information. https://www.maine.gov/ifw/fish-wildlife/wildlife/species-information/birds/ruffed-grouse.html
3. New Hampshire Fish and Game Department (2025). Ruffed Grouse and Woodcock Seasons Start October 1 (habitat and drumming-survey summary). https://nhfishgame.com/2025/09/22/ruffed-grouse-and-woodcock-seasons-start-october-1/
4. Vermont Fish & Wildlife Department (n.d.). Ruffed Grouse. https://www.vtfishandwildlife.com/node/626 (see also: A Landowner's Guide – Wildlife Habitat Management for Lands in Vermont, 2014, https://youngforest.org/sites/default/files/2023-12/landowners-guide-wildlife-habitat-mgmt-vermont.pdf)
5. Mangelinckx, J.M., Brown, S.R., Allen, R.B., Sullivan, K., Blomberg, E.J. (2020). Effects of forest characteristics on ruffed grouse nesting ecology in central Maine, USA. *Wildlife Biology* 2020(1): wlb.00598. https://bioone.org/journals/wildlife-biology/volume-2020/issue-1/wlb.00598/Effects-of-forest-characteristics-on-ruffed-grouse-nesting-ecology-in/10.2981/wlb.00598.full
6. University of Maine (2018). Study supports Maine's current management practices for ruffed grouse hunting (Davis, Mangelinckx, Blomberg). https://umaine.edu/news/?p=61877
7. Heinrich, B. (2017). Winter strategies of Ruffed Grouse in a mixed northern forest. *Northeastern Naturalist* 24 (Special Issue 7): B55–B71. https://www.eaglehill.us/NENAonline/articles/NENA-sp-7/14-Heinrich.shtml
8. Shipley, A.A., Zuckerberg, B. (2023). Snow cover constrains the behavioural flexibility of a winter-adapted bird. *Ibis*, doi:10.1111/ibi.13211. Summary: https://bou.org.uk/blog-shipley-ruffed-grouse-snow/ ; data: https://datadryad.org/dataset/doi:10.5061/dryad.g1jwstqnz
9. Endrulat, E.G., McWilliams, S.R., Tefft, B.C. (2005). Habitat selection and home range size of Ruffed Grouse in Rhode Island. *Northeastern Naturalist* 12(4): 411–424. https://digitalcommons.uri.edu/nrs_facpubs/126
10. Blomberg, E.J., Tefft, B.C., Endrulat, E.G., McWilliams, S.R. (2009). Predicting landscape-scale habitat distribution for Ruffed Grouse *Bonasa umbellus* using presence-only data. *Wildlife Biology* 15(4). https://bioone.org/journals/wildlife-biology/volume-15/issue-4/08-012/Predicting-Landscape-Scale-Habitat-Distribution-for-Ruffed-Grouse-Bonasa-umbellus/10.2981/08-012.full
11. Zimmerman, G.S., Gutiérrez, R.J., Thogmartin, W.E., Banerjee, S. (2009). Multiscale habitat selection by Ruffed Grouse at low population densities. *The Condor* 111(2): 294–304. https://pubs.usgs.gov/publication/70037002
12. USGS Upper Midwest Environmental Sciences Center (n.d.). Ruffed grouse habitat (summary of Zimmerman et al. 2009). https://www.umesc.usgs.gov/terrestrial/ruffed_grouse_habitat.html
12a. Stauffer, G.E., Miller, D.A.W., Williams, L.M., Brown, J. (2018). Ruffed grouse population declines after introduction of West Nile virus. *Journal of Wildlife Management* 82(1): 165–172. https://pure.psu.edu/en/publications/ruffed-grouse-population-declines-after-introduction-of-west-nile/ (press summary: https://wildlife.org/jwm-study-west-nile-could-be-impacting-pennsylvania-grouse/)
13. Dessecker, D.R., McAuley, D.G. (2001). Importance of early successional habitat to ruffed grouse and American woodcock. *Wildlife Society Bulletin* 29(2): 456–465. https://pubs.usgs.gov/publication/5224069
14. Koleck, R., McNeil, D., Chronister, L., et al. (2026). Data from: Using passive acoustic monitoring and LiDAR to conduct a statewide assessment of ruffed grouse occurrence in Pennsylvania. Dryad. https://doi.org/10.5061/dryad.hmgqnk9xh
15. Jones, B.C., Harper, C.A., Buehler, D.A., Warburton, G.S. (2008). Ruffed grouse brood habitat use in a mixed hardwood forest: implications for forest management in the Appalachians. *Forest Ecology and Management*. https://fwf.tennessee.edu/wp-content/uploads/sites/24/2020/07/Grouse-brood-habitat-use-FEM.pdf (finding text taken from a search summary; full PDF not read)
16. NH Audubon (n.d.). State of the Birds – Ruffed Grouse. https://stateofthebirds.nhaudubon.org/bird_database/ruffed-grouse/
17. Appalachian Cooperative Grouse Research Project home-range analysis (1,054 seasonal ranges; 1996–2001), via USDA Forest Service Treesearch. https://research.fs.usda.gov/treesearch/31636 (seen via search summary only; exact author list not verified)
18. Mountain Times (2020, Oct 7). Vermont hunters contribute to ruffed grouse research (VT Fish & Wildlife / SCWDS WNV results). https://mountaintimes.info/?p=27083
19. Wildlife Management Institute (2019). States release first year results of Ruffed Grouse West Nile virus study in Great Lakes states. https://wildlifemanagement.institute/node/1461

*Source limitations:* the PDFs of the Maine IF&W 2001 and NH F&G 2015 grouse assessments and several agency guides could not be read as text; the Cornell Birds of the World account is paywalled and is cited only through FEIS; the Ruffed Grouse Society site returned errors. Figures marked **uncertain** above should be verified before use.

---

## 2. How habitat is represented in the data (mathematical view)

All constants below are quoted from the code at the current working tree. Paths are relative to `/home/user/grouse_refactor_ec2`.

### 2.1 The sample

**Records.** Each training or validation record is a tuple $(\lambda_i,\varphi_i, y_i, \ell_i, w_i)$:

- $(\lambda_i,\varphi_i)$ is the WGS84 longitude and latitude.
- $y_i$ is the record year.
- $\ell_i\in\{0,1\}$ is the label.
- $w_i$ is the record weight. Positives have no `weight` column and get $1.0$ (`dataset.py:87-89`).

**From coordinates to a pixel.** Every feature raster of a region must sit on one pixel grid: the region's *template*, which is its latest LANDFIRE EVT clip in a local Albers projection (`ARCHITECTURE.md:166-178`). The test is `grid_mismatch` (`grouse_data.py:182-212`). It requires the same CRS, the same pixel size and no rotation, both within `tol=1e-3`, and pixel edges offset by an integer number of pixels. `dataset._check_grid_alignment` refuses any mixed set (`dataset.py:212-253`).

The pixel index is computed separately for each raster $c$:

$$
(r_i,s_i)=\Big\lfloor A_c^{-1}\,T_c(\lambda_i,\varphi_i)\Big\rfloor ,
$$

where $T_c$ is the EPSG:4326 → CRS($R_c$) transform and $A_c$ is the raster's affine (`src.index`, which floors; `dataset.py:318-321`). Because all grids coincide, $(r_i,s_i)$ is the same ground cell in every channel.

**Vintage matching.** Let $\mathcal Y_c$ be the years on disk for feature $c$. The vintage used for a record of year $y$ is

$$
v(c,y)=\arg\min_{t\in\mathcal Y_c}\big(|t-y|,\;t\big)\quad\text{(lexicographic; ties go to the earlier year)},
$$

(`grouse_data.py:368`). Two further rules apply:

- If the chosen file fails content validation (less than 1% non-nodata pixels), it falls back to the most recent valid year (`grouse_data.py:312-334, 391-412`).
- Training *refuses* (it does not drop) any record with $\exists c:\ |v(c,y_i)-y_i|>2$. This is `YEAR_MATCH_TOLERANCE = 2` (`grouse_data.py:174`) and `--max-year-gap` default 2 (`train.py:287-326, 617`).

**The 64×64 window.** With $n=$ `IMG_SIZE` $=$ `WINDOW_PX` $=64$ (`train.py:71`, `regions.py:62`) and $h=n/2=32$, the raw window is

$$
\tilde X_i[c,a,b]=R_{c,\,v(c,y_i)}\big[r_i-32+a,\;s_i-32+b\big],\qquad a,b\in\{0,\dots,63\}
$$

(`dataset.py:322-334`). Some properties of this window:

- It spans $64\times30\text{ m}=1.92$ km, about $3.7\ \text{km}^2$ (`models.py:1020-1022`).
- The record's own cell sits at index $(32,32)$, the lower-right cell of the central $2\times2$ block.
- The model's centre-skip path averages exactly that block, rows and columns 31–32 (`models.py:1269-1291`). Every D4 rotation or flip keeps the record cell inside that block.

**Nodata handling in the window.** Let $\mathcal N_c=$ `NODATA_SENTINELS` $\cup\{\text{declared nodata of }R_c\}$, with `NODATA_SENTINELS = (-9999, -32768, 32767, -1111)` (`grouse_data.py:72`). Any value in $\mathcal N_c$ becomes NaN (`dataset.py:344-347`). It is then stored in the int16 patch cache as `MISSING_CODE = -32768` (`grouse_data.py:84`; `dataset.py:186-196`).

**Tensorisation.** The categorical stack keeps integer codes with $M=-32768$ for nodata. The continuous stack is divided by its scale and nodata becomes NaN (`dataset.py:69-71, 393-416`):

$$
Z^{\text{cont}}_i[c]=\begin{cases}\tilde X_i[c]/\kappa_c & \tilde X_i[c]\neq M\\ \text{NaN}&\text{otherwise.}\end{cases}
$$

**Embedding into the network input.** `GrouseResNet.embed` (`models.py:1156-1195`) builds the tensor the network actually sees.

For each categorical feature $c$, with vocabulary size $V_c$, embedding dimension $d_c$ and table $E_c\in\mathbb R^{V_c\times d_c}$ (row 0 is the padding row, fixed at zero):

$$
m_c=\mathbb 1[z\neq M\ \wedge\ z<V_c],\qquad e_c=E_c\big[m_c\cdot\operatorname{clamp}(z,0,V_c-1)\big]\in\mathbb R^{d_c}.
$$

For each continuous feature: $m_c=\mathbb 1[\neg\text{isnan}]$ and $e_c=m_c\cdot z$.

With `--missing-mask` (default True, `train.py:792`), the validity bits $m_c$ are appended as extra channels. The input tensor is therefore

$$
X_i=\Phi(\tilde X_i)\in\mathbb R^{C\times64\times64},\qquad C=\sum_{c\in\text{cat}}d_c+|\text{cont}|+\big(|\text{cat}|+|\text{cont}|\big)
$$

(`models.py:1063-1068`).

For the 15 accepted features (`SPLIT_WINDOW_FEATURES`, `prepare_training_data.py:166-168`):

- 6 categorical features: evt (32), evh, evc, sclass, fdist, nlcd (16 each) give $112$ embedding channels.
- 9 continuous channels.
- 15 validity channels.
- Total $C=136$. With the four optional `mch_*` layers it becomes $C=144$.
- The "(B, 98, 64, 64)" in the comment at `models.py:1279` is the older 7-LANDFIRE-feature, no-mask geometry.

**Output.** The model's logit is

$$
f(X)=\sum_{p}\operatorname{softmax}(s(X))_p\,g_p(X)\;+\;h\Big(\tfrac14\!\!\sum_{(a,b)\in\{31,32\}^2}\!\!X_{\cdot ab}\Big),
$$

That is, an attention-pooled logit map (`--pool attn` default, `train.py:703`; `models.py:1293-1299`) plus the centre-skip head (`--center-skip` default True, `train.py:803`; `models.py:1257-1267`). The returned score is $\sigma(f)$.

**Augmentation.** Training applies a random D4 orientation per access (`--augment` default True, `train.py:632`; `dataset.py:418-443`). Jitter defaults to 0 (`train.py:614`). Validation uses the 4 fixed rotations (`train.py:459-467`).

### 2.2 Features: physical meaning, encoding, scaling and nodata

`FEATURE_SPEC` is at `models.py:517-607`. Channel order follows `FEATURE_SPEC` order (`train.py:107-118`). The raster list is `RASTER_FEATURES` (`grouse_data.py:135-164`).

**Categorical features (embedding lookup, no ordering between codes)**

| Feature | Physical meaning | vocab, dim | Notes |
|---|---|---|---|
| `evt` | LANDFIRE Existing Vegetation Type | 10000, 32 | Domain 4401–9994. |
| `evh` | LANDFIRE Existing Vegetation Height, in life-form blocks | 512, 16 | Tree 101–199 (1 m steps), shrub 201–230, herb 301–310 (0.1 m steps). Vocab was 300 until 2026-09-20, so herb codes were clamped. |
| `evc` | LANDFIRE Existing Vegetation Cover | 512, 16 | Tree 110–199, shrub 210–299, herb 310–399. |
| `sclass` | LANDFIRE Succession Class | 300, 16 | Codes 1–7 plus 111/112/120/132/180 land-cover fills. `-1111` is a nodata sentinel. |
| `fdist` | LANDFIRE fuel disturbance, year/type/severity composite codes | 10000, 16 | — |
| `nlcd` | Annual NLCD Anderson Level II class | 256, 16 | 250 and out-of-range values are mapped to −9999 at download (`download_tcc_nlcd.py:27-29, 107-108, 245-248`). |

A code at or above $V_c$ is treated as missing under the mask (`models.py:1171-1177`).

**Continuous features.** Each has a storage encoding $u=\mathcal E_c(\text{physical})$ in int16, followed by the network scale $x=u/\kappa_c$. The two must be undone in that order to recover physical units (`ARCHITECTURE.md:205-210`).

| Feature | Physical meaning | Encoding $\mathcal E_c$ | $\kappa_c$ | Resulting $x$ |
|---|---|---|---|---|
| `ch` | LANDFIRE canopy height, "coded units (~0-510)" | as stored | 100 | ≈0–5.1 |
| `cc` | LANDFIRE canopy cover (%) | as stored | 100 | 0–1 |
| `tcc` | USFS Tree Canopy Cover (%); nodata where NLCD is nodata | as stored | 100 | 0–1 |
| `road_dist` | Metres to the nearest TIGER `TIGER_YEAR=2023` road (S1100, S1200, S1400, S1630, S1640) | $\operatorname{rint}(1000\ln(1+\min(d,50000)))$ (`models.py:630-652`; `generate_road_distance.py:129`) | 10000 | $\approx\ln(1+d)/10\in[0,1.082]$ |
| `tsd` | Years since last LANDFIRE Annual Disturbance; undisturbed $=30$ | $\operatorname{rint}(1000\ln(1+\min(t,30)))$ (`models.py:677-686`; `generate_time_since_disturbance.py:359-361`) | 4000 | $\in[0,0.859]$ |
| `balive` | TreeMap live basal area (ft²/acre) | $\operatorname{rint}(10\min(BA,400))$ | 1000 | $BA/100\le4$ |
| `tpa_live` | TreeMap live stems/acre | $\operatorname{rint}(1000\ln(1+\min(T,30000)))$ (`models.py:756-791`) | 10000 | $\le1.031$ |
| `qmd` | Quadratic mean diameter (in), derived as $\sqrt{BA/(0.005454\,T)}$, and $0$ if $T=0$ (`models.py:769-782`) | $\operatorname{rint}(100\min(Q,40))$ | 1000 | $Q/10\le4$ |
| `carbon_dwn` | TreeMap down-wood carbon (tons/acre) | $\operatorname{rint}(100\min(C,20))$ | 500 | $C/5\le4$ |
| `mch_mean` | Meta 1 m canopy height, 30 m mean | decimetres $\operatorname{rint}(10h)$; refused outside 0–60 m | 300 | $h/30\le2$ |
| `mch_f01`, `mch_f15`, `mch_f512` | Share of 1 m pixels in the bins <1, 1–5 and 5–12 m (`MCH_BIN_EDGES_M`) | per mille $\operatorname{rint}(1000p)$ | 1000 | $p\in[0,1]$ |

Fixed-point multipliers and caps for the TreeMap features are in `TREEMAP_FIXED` (`models.py:751-755`); `treemap_encode` is at `models.py:801-808`. The `mch_*` encoders are at `models.py:705-732`.

The log encodings deliberately compress the far field. For roads, 0 m, 100 m, 500 m and 1 km map to 0.00, 0.46, 0.62 and 0.69, while 5–50 km all fall in 0.85–1.08 (`models.py:620-625`). The `tsd` cap is fixed, so an undisturbed pixel encodes the same in every vintage (`models.py:671-676`).

**Nodata by feature**

- All encoders refuse non-finite input. Nodata is written by mask *after* encoding (`models.py:634-645`).
- TreeMap non-forest is stored as **0**, not as nodata. A joint `qmd=0` and `tpa_live=0` is the non-forest signature (`models.py:744-750`).
- `road_dist` is nodata outside US counties (Canada and ocean; `ARCHITECTURE.md:222-232`).
- An `mch_*` cell is nodata if less than `MCH_MIN_VALID_FRAC=0.5` of its 1 m pixels are valid, or if its mean exceeds 60 m.
- `fdist` nodata reaches the network as $M$ with a validity bit of 0. In the envelope analysis, by contrast, it is filled with `FDIST_NONE=-1` (`analyze_grouse.py:99-105, 777-778`).

### 2.3 Labels and the sampling design

**Positives** (`prepare_training_data.py:373-432`) come from eBird Ruffed Grouse records obtained through GBIF (`sightings.py:19-23`, `START_YEAR=2016`). The pipeline:

1. Repeat visits to a 5-decimal-place coordinate are collapsed to one record, which takes its **most recent** year (`analyze_grouse.py:257-282`).
2. Records whose centre pixel has nodata in any of evt, evh, evc, sclass, ch or cc are dropped (`REQUIRED_FEATURES`, `analyze_grouse.py:104, 775-776`).
3. Non-vegetated records are flagged and removed. Non-vegetated means $\text{sclass}\in\{111,112,120,132,180\}$ or the EVT_PHYS name contains Developed, Open Water, Barren, Agriculture, Quarries, Snow or Ice (`analyze_grouse.py:109, 126-134, 840-842`; `prepare_training_data.py:398-399`).
4. Records with year below `YEAR_MIN = 2020` are dropped (`regions.py:73`).
5. Records whose 64-pixel window is not in-bounds on all 15 rasters are dropped (`regions.py:302-320`). Nodata inside the window is allowed.
6. Pooled greedy thinning is applied in seeded-hash order: keep $i$ iff $\|x_i-x_j\|_2^2\ge 30^2$ for every kept $j$ in EPSG:5070 (`MIN_SPACING_M=30`, `regions.py:40`; `prepare_training_data.py:113-150`). This is one pixel, so thinning removes same-pixel duplicates, not spatial clustering.

**Spatial-block split** (`prepare_training_data.py:344-367`):

- Block ids are $\big(\lfloor x/3000\rfloor,\lfloor y/3000\rfloor\big)$ on EPSG:5070 with origin $(0,0)$ (`regions.py:44, 52, 239-249`).
- Occupied blocks are visited in `order_key` order (`SPLIT_SEED=42`). Whole blocks go to validation until the count reaches $\operatorname{round}(0.2\,N)$ (`VAL_FRACTION`, `regions.py:55`).
- A negative takes the split of its block. A positive-free block is validation iff $\text{md5}(42{:}b)\bmod 10^4<v_f\cdot10^4$ (`regions.py:270-286`).
- Note that windows (1.92 km) are smaller than blocks (3 km), but a window near a block edge overlaps a neighbouring block. Neighbouring train and validation records can therefore share large parts of their *inputs*, though never their labels.

**Negatives** are a target-group background, not a random background (`generate_negatives.py:1-49, 380-534`). Candidates are eBird/GBIF records of 10 other species, a mature-upland-forest guild plus a wetland guild (`get_negatives.py` `TARGET_SPECIES`). The pool is built as follows:

1. Drop records with year < 2020.
2. Drop records with `coord_uncertainty_m > 1000`; NaN uncertainty is kept.
3. Deduplicate on a 5-decimal-place key.
4. Drop records outside their own state's county polygons.
5. Thin at 30 m.
6. Drop any candidate within $\|x-s\|^2\le300^2$ of **any** grouse sighting, of any year, including non-vegetated ones (`BUFFER_M=300`, `regions.py:48`; `generate_negatives.py:187-209`). Also drop any candidate within 300 m of the acquisition-domain edge.
7. Require non-NaN centre values for evh, evt and sclass (`ENVELOPE_FEATURES`, `:119-121, 479`).
8. Apply the same window-in-bounds mask as the positives.

**Envelope weight.** Each candidate gets an envelope $e(x)=$ EVT_PHYS × SCLASS × EVH-split-at-the-sighting-median (`ENVELOPE_SCHEME`, `analyze_grouse.py:67-71`; edges from `fit_scheme_binners`, `:418-432`). The selection ratio is

$$
\mathrm{SR}(e)=\frac{n_{\text{sight}}(e)/\sum n_{\text{sight}}}{n_{\text{bg}}(e)/\sum n_{\text{bg}}},
$$

computed with `BACKGROUND_N=20000` uniform in-state points (`analyze_grouse.py:81, 917-923`). The weight is (`generate_negatives.py:98-102, 146-158`):

$$
\omega(e)=\begin{cases}10 & \text{non-vegetated (NONVEG\_WEIGHT)}\\ 1 & \text{Landscape-Rare }(n_{\text{bg}}<15)\text{ or unseen envelope}\\ 1/10 & \text{SR undefined}\\ 1/\operatorname{clip}(\mathrm{SR}(e),0.1,10) & \text{otherwise.}\end{cases}
$$

**Draw.** For each (region, split, single-year stratum $k$) with `YEAR_STRATA=((2020,),…,(2024,))` (`regions.py:82`), the draw takes $n_k=\operatorname{round}(n^{+}_k\cdot 1.0)$ negatives (`NEG_RATIO`). At most $\operatorname{round}(0.30\,n_k)$ may be non-vegetated (`NONVEG_MAX_FRAC`); the rest come from the habitat pool, and a shortfall raises. Selection uses Efraimidis–Spirakis weighted sampling without replacement, with keys $\log u/\omega$ (`generate_negatives.py:282-353`). For a small sampling fraction, inclusion probability is approximately proportional to $\omega$.

**Optional random background.** `--an-background R` adds uniform, in-state, training-block-only, **unbuffered** label-0 points. They are year-matched to the training positives, $\operatorname{round}(c_y R)$ per year (`train.py:121-284`). The default is $R=0$ (`train.py:893`).

**Class balance and weights**

- Classes are 1:1 per (region, split, year), and every point is expanded ×4 by rotation (`train.py:412-423`).
- Batches alternate 25/75 and 75/25 positive fractions, netting 50/50 (`dataset.py:485-535`).
- Focal loss uses $\alpha=0.5$ unless `--pos-neg-ratio` is set ($\alpha=R/(1+R)$) and $\gamma=2$ (`train.py:1170-1177, 911`; `losses.py:13-34`).
- Label smoothing $\varepsilon=0.05$ makes the targets $0.975$ and $0.025$ (`train.py:832`; `model_handler.py:442-444`).
- Envelope weights enter the *loss* only with `--use-weights`, which is off by default (`train.py:561`; `model_handler.py:445-447`). By default they act only through the negative draw.

**Effective estimand.** Let $p_+(X)$ be the distribution of windows at processed grouse records and $p_-(X)$ the distribution of the negative draw. With the effective class prior $\pi=\tfrac12$, the population minimiser of a calibrated binary loss satisfies

$$
\operatorname{logit}P(\ell=1\mid X)\;=\;\log\frac{p_+(X)}{p_-(X)},
$$

and for small sampling fractions

$$
p_-(x)\;\propto\;q_{\mathrm{TG}}(x)\;\mathbb 1\!\big[d(x,\mathcal S)>300\text{ m}\big]\;\mathbb 1\!\big[d(x,\partial D)>300\text{ m}\big]\;\omega(e(x)).
$$

Here $q_{\mathrm{TG}}$ is the 10-species eBird record density. Within habitat envelopes this gives approximately

$$
\operatorname{logit}P\approx\log\frac{p_+(X)}{q_{\mathrm{TG}}(X)}+\log\operatorname{clip}\big(\mathrm{SR}(e),0.1,10\big)+\text{const}.
$$

The envelope selection signal is thus added on top of whatever $X$ already reveals about it.

What this means in practice:

- **It is not occupancy.** $P(\ell=1\mid X)$ is a presence-versus-target-group contrast, conditioned on several things:
  - The positive's centre pixel is vegetated, while about 30% or less of negatives may be non-vegetated, so a non-vegetated centre implies $\ell=0$ by construction.
  - The negative is more than 300 m from any grouse report.
  - Year, region and split carry no label information by design: per-stratum 1:1 matching gives $P(\ell=1\mid y)=P(\ell=1\mid\text{region})=\tfrac12$.
- **Observer effort cancels only partly.** It cancels to the extent the target group shares the grouse records' effort bias. But the target species have their own habitats, so $q_{\mathrm{TG}}$ is itself habitat-structured.
- **Calibration and focal loss.** Focal loss is not a proper scoring rule, and smoothing compresses outputs into $[0.025,0.975]$. `calibrate.py` fits a Platt transform, and `predict.py --prior f` shifts logits by $\operatorname{logit}f-\operatorname{logit}\pi_{\text{val}}$. Validation prevalence is $\approx0.5$ (`predict.py:38-48, 994-999`; `ARCHITECTURE.md:290-297`).

### 2.4 Limitations of the representation

1. **Resolution versus location error.**
   - One pixel is 30 m, but positives are eBird checklist locations. Repeat-visit pins made up 59–76% of records (`analyze_grouse.py:258-260`), and traveling counts can span kilometres.
   - Positives get **no** coordinate-uncertainty filter, while negatives are filtered at 1000 m with NaN kept. The label is therefore attached to a pixel whose error radius is often many pixels.
   - The 64-pixel context and attention pooling partly compensate. But the centre-skip head, a 2×2 average, assumes the label belongs to the centre.
   - Narrow linear features are unresolved: a road can read `nlcd=90` (`ARCHITECTURE.md:304-308`).
   - Edge-of-coverage records are possible because nodata inside the window is allowed (2.2).

2. **Temporal mismatch.**
   - Record years are 2020–2024, but LANDFIRE has nothing before 2022 (`grouse_data.py:373-375`). So $v(c,2020)=2022$ for LANDFIRE layers, exactly at the tolerance of 2.
   - `road_dist` (TIGER 2023) and `mch_*` (one imagery epoch) are static copies written for every year (`grouse_data.py:140-146, 161-164`).
   - TreeMap uses the nearest of {2016, 2020, 2022, 2023} (`generate_treemap_features.py:131, 143-146`).
   - `tsd` is truly per-year.
   - Positives take their *latest* visit year, not the year of each observation.
   - Prediction maps every feature at its latest vintage (`predict.py:165`).

3. **Coverage, nodata and design asymmetry.**
   - Missing data is carried by validity channels, so "absent" never becomes 0 (`ARCHITECTURE.md:278-285`). For `fdist`, missing conflates undisturbed with outside coverage.
   - Positives require valid centre values for evt, evh, evc, sclass, ch and cc; negatives only for evt, evh and sclass. A centre-pixel ch/cc validity bit of 0 can therefore occur only among negatives. Whether this actually happens was not measured.
   - TreeMap boundaries are imputation switches, not mapped edges (`ARCHITECTURE.md:240-249`). That section describes a `--smooth` (3×3) default, but `generate_treemap_features.py` contains no smoothing code. The documentation appears stale.

4. **Half-cell misregistration (BUG-0094, OPEN).**
   - **Mechanism.** The Earth Engine layers $\mathcal E=\{$nlcd, tcc, balive, tpa_live, qmd, carbon_dwn$\}$ were requested on a 30 m lattice offset by exactly 15 m from their sources. Every nearest-neighbour choice was a four-way tie, broken toward the SE pixel in 1,400 of 1,400 cases (`docs/quality/bugs/BUG-0094-ee-downloads-half-pixel-tie-shift.md` §4–5).
   - **Effect on the input.** For $c\in\mathcal E$,
     $$
     \tilde X_i[c,a,b]\approx R^{\text{true}}_c\big(g(r_i-32+a,\,s_i-32+b)+\delta\big),\qquad \delta\approx(+15\text{ m E},\,-15\text{ m N}),\ \|\delta\|\approx21\text{ m}\approx0.71\text{ px},
     $$
     while the LANDFIRE-derived channels have $\delta=0$. Six of the 15 channels therefore describe the ground about 21 m SE of the cell they are stacked with, including the record cell.
   - **Evidence.** Measured against `road_dist`, the layers peak at offset (1,0) or (1,1); NLCD scores 0.532 when fetched on-grid versus 0.459 for the on-disk copy.
   - **Consequences.** Cross-channel co-occurrences, for example the evt/nlcd boundaries and the centre 2×2 vector, are blurred along a roughly one-pixel band at every class edge. D4 augmentation rotates $\delta$ with the patch, so the network cannot learn a fixed compensating shift. Training and prediction read the same rasters, so this is a semantic and accuracy defect, not train/serve skew. The accuracy impact is unmeasured (CR-0034/CR-0035).
   - **Related warp defect (BUG-0095, BUG-0096).** Local nearest-neighbour warps used GDAL's approximate transformer, with error up to 0.125 px. On a rotated 60 km grid, 6.8% of cells took a neighbouring source pixel (synthetic test). Write this as an additional random swap,
     $$
     \tilde X_i[c,u]=R_c(u+\eta_u),\quad P(\eta_u\neq0)\approx0.07,
     $$
     concentrated where a source boundary lies within 0.125 px of a cell centre. It affects nlcd, tcc, the TreeMap layers and `tsd` (`BUG-0095-approximate-warp-transformer.md` §3; `BUG-0096-tsd-approximate-warp.md`). Both are open: the code is fixed in CR-0034 and the data repair is pending in CR-0035.
   - **Earlier, already fixed.** An 11-pixel corner misregistration between EPSG:5070 layers and the local-Albers LFPS clips is now blocked by `grid_mismatch` (`grouse_data.py:188-198`). `grid_mismatch` checks only the declared grid, which is why it could not catch BUG-0094/0095.

---

## 3. The mathematics of the current model

This section covers the code as it stands in `/home/user/grouse_refactor_ec2`. Defaults are the **`train.py` CLI defaults**. The `GrouseModelHandler.__init__` defaults are different (`pool='mean'`, `sched='warm_restarts'`), and `train.py` always overrides them. The module docstring at `model_handler.py:9-10` ("AdamW(lr=3e-4, weight_decay=1e-2) | FocalLoss(alpha=0.25 …)") is stale; the live values are at `model_handler.py:225-246` and `train.py:832-935`.

**The current best model.** The repository does not record the exact command or the file for `grouse_cr0031_wd3e3_wr.pth`; no `.pth` is checked in.
- What is documented: CR-0032 §Evaluation (`docs/quality/change-requests/CR-0032-meta-canopy-structure-layers.md:212`) names the recipe as "`--sched warm_restarts`, wd 3e-3, the `grouse_cr0031_wd3e3_wr` command". It also gives its validation AUC (CNN 0.762, line 21).
- What is inferred: the lineage recipe in CR-0009 (`docs/quality/evidence/CR-0009/retrain/argv.txt`) is `--loss an_full --an-pos-weight 1.0 --embed-dropout 0.1 --dropout 0.4 --dynamic-dropout --dynamic-dropout-step 0.05 --dynamic-dropout-max 0.9 --weight-decay 1e-3`. The "cr0031" in the name suggests `--an-background > 0` (CR-0031 re-enabled it).
- So the loss and background settings below are **inferred, not confirmed**. The checkpoint's own `config` (`model_handler.py:472-524`) records `loss`, `an_pos_weight` and `focal_alpha` and would settle it.

---

### 3.1 Input encoding

**Inputs.** Each sample is a 64×64 window at 30 m/px (`train.py:71`), centred on the labelled point (`dataset.py:318-348`). The default feature set is the 15 rasters in `prepare_training_data.py:166`:
- **6 categorical:** evt, evh, evc, sclass, fdist, nlcd.
- **9 continuous:** ch, cc, tcc, road_dist, tsd, balive, tpa_live, qmd, carbon_dwn.

**Continuous channels.** Each is stored as int16 and divided by its `FEATURE_SPEC` scale $s_j$ (`models.py:517-607`, `dataset.py:407-413`):

$$x_j(u) = r_j(u)/s_j,\qquad s_j\in\{100,100,100,10^4,4000,1000,10^4,1000,500\}.$$

Several are already log-encoded before storage:
- road_dist: $r=\mathrm{round}(1000\,\log(1+d_{\text{m}}))$ (`models.py:648-652`).
- tsd: same form in years, capped at 30 (`models.py:681-686`).
- tpa_live: same form, capped at 30,000 (`models.py:785-791`).
- qmd is derived as $\sqrt{BA/(0.005454\cdot TPA)}$ (`models.py:772-782`).

Nodata becomes NaN, and is then filled with 0 (`models.py:1187-1189`).

**Categorical embeddings** (`models.py:1045-1048, 1167-1186`). Each feature $f$ has a table $E_f\in\mathbb{R}^{V_f\times d_f}$ with `padding_idx=0`, so row 0 is fixed at zero and gets no gradient. With `--missing-mask` (default True, `train.py:792`), a code that is missing or at/above the vocab is sent to row 0 and flagged:

$$\tilde c = \begin{cases}0 & c=\texttt{MISSING}\ (-32768)\ \text{or}\ c\ge V_f\\ \mathrm{clamp}(c,0,V_f-1) & \text{otherwise}\end{cases},\qquad e_f(u)=E_f[\tilde c_f(u)]\in\mathbb{R}^{d_f}.$$

| feature | $(V_f, d_f)$ |
|---|---|
| evt | (10000, 32) |
| evh, evc | (512, 16) |
| sclass | (300, 16) |
| fdist | (10000, 16) |
| nlcd | (256, 16) |

**Stem input.** One validity bit $m_f(u)\in\{0,1\}$ is appended per feature. The input tensor is the channel concatenation

$$X(u)=\big[e_{1}(u);\dots;e_{6}(u);\,x_1(u);\dots;x_9(u);\,m_1(u);\dots;m_{15}(u)\big]\in\mathbb{R}^{C_0},$$

$$C_0=(32+5\cdot16)+9+15=136 \quad (\texttt{models.py:1063-1068}).$$

**Embedding dropout** (default 0; 0.1 in the CR-0009 recipe, `models.py:1179-1185`). Each embedding *plane* of each sample is dropped as a whole: $e_f\leftarrow e_f\cdot\xi/(1-p_e)$ with $\xi\sim\mathrm{Bernoulli}(1-p_e)$.

**Loading old checkpoints.** `spec_with_checkpoint_vocab` (`models.py:933-963`) rebuilds $V_f$ from the checkpoint's own `embeddings.<f>.weight` row count. Older checkpoints (for example evh/evc with $V=300$) therefore reload with their original clamp.

### 3.2 Trunk (Branch A): stem, residual blocks, CBAM

**Convolution.** As in PyTorch, convolution is cross-correlation. For kernel $W\in\mathbb{R}^{C_o\times C_i\times k\times k}$, stride $s$, padding $p$ and dilation $r$:

$$(W\star X)_o(u)=\sum_{c=1}^{C_i}\sum_{\delta\in\{0..k-1\}^2} W_{o,c,\delta}\;X_c(s\,u+r\,\delta-p).$$

**Stem.** `conv1` is a new 7×7 convolution with stride 2, padding 3, no bias, $136\to64$, trained from scratch (`models.py:1069`). It is followed by the ImageNet-pretrained `bn1`, ReLU and a 3×3/2 max-pool (`models.py:1071-1073, 1210-1213`).

**Batch norm.** In training mode, using batch statistics $\mu_B,\sigma_B^2$:

$$\mathrm{BN}(x)=\gamma\frac{x-\mu_B}{\sqrt{\sigma_B^2+\epsilon}}+\beta.$$

In evaluation mode, running estimates replace $\mu_B,\sigma_B^2$. These are updated as $\hat\mu\leftarrow0.9\hat\mu+0.1\mu_B$ (PyTorch defaults, $\epsilon=10^{-5}$).

**Residual blocks.** The trunk uses ResNet-18 `layer1`…`layer4` (ImageNet weights), two BasicBlocks each:

$$\mathcal F(x)=\mathrm{BN}_2\!\big(W_2\star \mathrm{ReLU}(\mathrm{BN}_1(W_1\star x))\big),\qquad y=\mathrm{ReLU}\big(\mathcal F(x)+P x\big),$$

where $P$ is the identity, or a 1×1 conv + BN where the channel count changes. The entry strides of `layer3` and `layer4` (and their shortcut convs) are set to 1 (`models.py:1055-1058`).

**Spatial sizes** (default `keep_early_resolution=False`):

| stage | size |
|---|---|
| input | $64^2$ |
| conv1 | $32^2$ |
| maxpool | $16^2$ |
| layer1 | $16^2\times64$ |
| layer2 | $8^2\times128$ |
| layer3 | $8^2\times256$ |
| layer4 | $8^2\times512$ |

The CHANGELOG (§"Nodata validity channels…", line ~424) gives the trunk's receptive field as about 227 px. Every cell of the final 8×8 map therefore sees the whole patch.

**CBAM** after every stage (`blocks.py:17-57`, reduction 16, 7×7 spatial kernel):

$$M_c=\sigma\big(\mathrm{MLP}(\mathrm{avg}_{u}x)+\mathrm{MLP}(\max_u x)\big),\quad x'=x\odot M_c,$$

$$M_s=\sigma\big(k_7\star[\mathrm{mean}_c x';\max_c x']\big),\quad x''=x'\odot M_s.$$

**Head.** `Dropout2d(p)` (default $p=0.2$, `train.py:808`) zeroes whole channels of the 512×8×8 map with scaling $1/(1-p)$. A 1×1 `conv_out` then produces **two** maps under `pool='attn'` (`models.py:1113-1118`): a logit map $L\in\mathbb{R}^{8\times8}$ and a score map $S\in\mathbb{R}^{8\times8}$.

**Pooling.** `train.py` defaults to `--pool attn` (`models.py:1293-1315`):

$$z_A=\sum_{u}\frac{e^{S_u}}{\sum_{v}e^{S_v}}\,L_u .$$

The alternatives:
- `mean`: $\frac1{64}\sum_u L_u$.
- `center`: the mean of the 2×2 centre cells.
- `gauss`: $\sum_u g_u L_u$ with $g_u\propto\exp(-\|u-c\|^2/2\sigma^2)$, $\sigma=\max(h,w)/4$ (`models.py:976-985`).

The optional `early_attn` transformer block (RoPE plus relative bias, `models.py:157-395`) is **off** by default (`train.py:715`).

### 3.3 Centre skip and Branch B; final logit

**Centre skip** (default on, `train.py:803`; `models.py:1126-1130, 1269-1291`). This is a wide-and-deep path on the 2×2 centre of the *embedded input*, rows/cols 31–32:

$$v=\tfrac14\sum_{u\in\mathcal C}X(u)\in\mathbb{R}^{136},\qquad z_C=w_2^\top\,\mathrm{Drop}_p\big(\mathrm{ReLU}(W_1v+b_1)\big)+b_2,\quad W_1\in\mathbb{R}^{128\times136}.$$

**Branch B** (default `--dual-branch dilated --dual-branch-channels 32`, `train.py:766, 802`; `models.py:404-506`). It keeps full resolution:

$$h_0=\mathrm{CBR}_{3\times3}(X),\qquad h_k=h_{k-1}+\mathrm{CBR}_{3\times3,\,\text{dil}=d_k}(h_{k-1}),\quad d_k\in\{1,2,4,8\}.$$

- CBR is conv-BN-ReLU; the receptive field is $3+2(1+2+4+8)=33$ px.
- It is pooled to $\bar h\in\mathbb{R}^{32}$ with its own softmax score map.
- Its scorer is $z_B=\mathrm{Lin}_{32\to1}(\mathrm{Drop}(\mathrm{ReLU}(\mathrm{Lin}_{32\to32}\bar h)))$. The last layer is **zero-initialised**, so $z_B\equiv0$ at the start (`models.py:1150-1154`).

**Final logit and probability** (`models.py:1257-1267`):

$$z = z_A+z_C+z_B,\qquad p=\sigma(z)=\frac{1}{1+e^{-z}}.$$

### 3.4 Losses

**Label smoothing.** Default $\varepsilon=0.05$ (`train.py:832`), applied to training targets only (`model_handler.py:442-444`):

$$y'=y(1-\varepsilon)+\varepsilon/2\in\{0.025,\,0.975\}.$$

Validation loss uses $\varepsilon=0$ (`model_handler.py:1847-1858`).

**Focal loss** (the default `--loss focal`; `losses.py:13-34`). With $\mathrm{BCE}(z,y')=-[y'\log\sigma(z)+(1-y')\log\sigma(-z)]$:

$$p_t=e^{-\mathrm{BCE}},\qquad \alpha_t=\begin{cases}\alpha & y'>0.5\\1-\alpha&\text{else}\end{cases},\qquad \mathcal L_{\text{focal}}=\frac1B\sum_i \alpha_t(1-p_t)^{\gamma}\,\mathrm{BCE}_i .$$

- Defaults: $\alpha=0.5$ (or $R/(1+R)$ from `--pos-neg-ratio`, `train.py:1172-1178`) and $\gamma=2$.
- For the first `--warmup-epochs 3` epochs, $\gamma=0$, which is plain $\alpha$-weighted BCE (`model_handler.py:1025-1037, 1153`).
- This "warmup" is a change of loss, not a learning-rate warmup.

**L_AN-full** (Cole et al. 2023, `--loss an_full`; `losses.py:37-76`), computed with `logsigmoid`:

$$\mathcal L_{\text{AN}}=-\frac1B\sum_i\Big[\lambda\,y'_i\log\sigma(z_i)+(1-y'_i)\log\sigma(-z_i)\Big].$$

- $\lambda=1$ under stratified batching (the auto rule, `train.py:1180-1195`); at $\lambda=1$ this is exactly BCE.
- "Assumed negative" means the negatives are never verified. With `--an-background R`, the training set also gets $\mathrm{round}(c_y R)$ uniformly random, in-state, training-block background pixels per positive-year $y$, all labelled 0 (`train.py:121-284, 438-466`). Validation is untouched.
- For a true conditional probability $q$, the pointwise minimiser is $\sigma(z^*)=\lambda q'/(\lambda q'+1-q')$ with $q'=q(1-\varepsilon)+\varepsilon/2$. Hence $z^*=\mathrm{logit}(q')+\log\lambda$: a constant $\log\lambda$ offset (`losses.py:80-114`). Smoothing bounds $|z^*|\le\mathrm{logit}(0.975)\approx3.66$.

**Optional terms** (off in the default and lineage recipes):
- Per-sample weights $w_i$ multiply the loss before the mean (`--use-weights`).
- The strict-margin objective $z\leftarrow z-m_{y}$, $m_{\pm}=\mathrm{logit}(0.75/0.25)=\pm1.0986$, applies only with `--select-by strict`.
- Distillation, $\alpha\mathcal L+(1-\alpha)\mathrm{BCE}(z,p_{\text{teacher}})$ (`model_handler.py:419-462`).

**Batch composition.** `StratifiedBatchSampler` alternates 25%/75% and 75%/25% positive batches, giving exactly 50/50 per pair (`dataset.py:485-555`). This fixes the *training* prior at 0.5 whatever the dataset's class ratio.

**Augmentation.** Each training point appears 4 times per epoch (`expand_rotations=True`). Each appearance is a random element of the dihedral group D4 (rotation $k\in\{0..3\}$ and flip $\in\{0,1\}$), with optional jitter (`--jitter`, default 0) (`dataset.py:363-444`).

### 3.5 Optimiser, regularisation, schedules

**AdamW** (fused on CUDA; `model_handler.py:985-991`) with PyTorch defaults $\beta=(0.9,0.999)$, $\epsilon=10^{-8}$ and decoupled weight decay $\lambda_{wd}$:

$$m_t=\beta_1m_{t-1}+(1-\beta_1)g_t,\quad v_t=\beta_2v_{t-1}+(1-\beta_2)g_t^2,$$

$$\theta_t=\theta_{t-1}(1-\eta_t\lambda_{wd})-\eta_t\frac{\hat m_t}{\sqrt{\hat v_t}+\epsilon}.$$

- The decay is applied to the weights directly, not added to the gradient, so it is not rescaled by $\sqrt{\hat v}$.
- `--weight-decay`: default $10^{-4}$; best model $3\times10^{-3}$.
- It applies to **all** parameters, including BN and embeddings; there is no exclusion group.
- Because the decay is multiplied by the group's $\eta$, the backbone group decays 10× more slowly per step.

**Learning rates.**
- Base rate: $\eta_0=3\times10^{-4}\sqrt{B/32}$ (`--lr-scaling sqrt`, `train.py:1196-1209`).
- Backbone group (`bn1`, `layer1-4`): $0.1\,\eta_0$ (`model_handler.py:925-983`).
- "Fresh" group (embeddings, `conv1`, CBAM, `conv_out`, `center_head`, Branch B): full $\eta_0$.

**Gradient clipping.** Global L2 norm at 1.0: $g\leftarrow g\cdot\min(1,\,1/\|g\|_2)$ (`model_handler.py:1206-1218`), under AMP with GradScaler.

**LR schedule.** The `train.py` default is `--sched cosine`, i.e. `CosineAnnealingLR(T_max=epochs)`. The best model uses `warm_restarts`, `CosineAnnealingWarmRestarts(T_0=10, T_mult=2)`, $\eta_{\min}=0$ (`model_handler.py:1040-1048`). `sched_t0`/`sched_tmult` have no CLI flag. The scheduler steps **once per epoch** (`model_handler.py:1255`):

$$\eta_t=\eta_{\min}+\tfrac12(\eta_{\max}-\eta_{\min})\Big(1+\cos\frac{\pi T_{\text{cur}}}{T_i}\Big),\qquad T_i=10\cdot2^i .$$

- Restarts fall at epochs 10, 30 and 70.
- Each parameter group follows the curve with its own $\eta_{\max}$.

**Weight EMA** (default decay 0.999, `train.py:833`; `model_handler.py:93-191`). After each optimiser step, $\bar\theta\leftarrow0.999\,\bar\theta+0.001\,\theta$. Validation, selection and saved checkpoints all use $\bar\theta$.

**Dynamic dropout** (`--dynamic-dropout`, used in the lineage recipe; `model_handler.py:1298-1314, 564-579`). With $g_e=\mathcal L^{\text{val}}_e-\mathcal L^{\text{train}}_e$:

$$p_{e+1}=\mathrm{clip}\big(p_e+\delta\,\mathrm{sign}(g_e-g_{e-1}),\;p_{\min},\;p_{\max}\big).$$

- Defaults: $p_{\min}=0.3p_0$, $p_{\max}=\min(0.6,1.6p_0)$.
- The lineage recipe sets $p_0=0.4$, $\delta=0.05$, $p_{\max}=0.9$.
- Embedding dropout follows as $p_e\cdot p_{e,0}^{\text{emb}}/p_0$.

**Checkpoint selection.** There is **no patience-based early stopping**. All epochs run. A checkpoint is saved when

$$\text{rank}=\tfrac12(\text{AUC}_{\text{TTA}}+\text{AP}_{\text{TTA}})$$

exceeds the *last saved* value by more than `--select-min-delta 1e-3` (`model_handler.py:620-638, 1345`). `DivergenceGuard` stops a run only with `--on-divergence stop` (`model_handler.py:194-221`).

### 3.6 Evaluation

**TTA.** The validation set stores each point under the 4 fixed rotations $\rho^k$. `--flip-tta` (default on) averages each rotation with its mirror in one batch (`model_handler.py:397-417`). The per-point score is therefore the mean logit over all 8 elements of D4, averaged **before** the sigmoid (`model_handler.py:1889-1896`):

$$\bar z(x)=\frac18\sum_{k=0}^{3}\sum_{f\in\{0,1\}} z\big(\phi^f\rho^k x\big).$$

So the "TTA AUC" is over 8 views, not 4.

**ROC-AUC** (`model_handler.py:55-75`) uses the Mann-Whitney form with tie-averaged ranks $R_i$:

$$\mathrm{AUC}=\frac{\sum_{i:y_i=1}R_i-\frac{n_+(n_++1)}2}{n_+n_-}=\Pr(\bar z_+>\bar z_-)+\tfrac12\Pr(\bar z_+=\bar z_-).$$

**Average precision** (`model_handler.py:78-90`) is the non-interpolated sum over positives in descending-score order:

$$\mathrm{AP}=\frac1{n_+}\sum_{k}y_{(k)}\,\frac{\sum_{j\le k}y_{(j)}}{k}.$$

**Brier score and calibration** (`calibrate.py`):
- Brier: $\mathrm{BS}=\frac1N\sum(p_i-y_i)^2$ (`calibrate.py:239-240`).
- Reliability: 15 equal-width bins, $\mathrm{ECE}=\sum_b\frac{n_b}{N}|\bar p_b-\bar y_b|$, MCE $=\max_b$ (`calibrate.py:218-237`).
- **Platt scaling** (`calibrate.py:173-202`) fits $p=\sigma(a\bar z+b)$ by minimising $\mathrm{NLL}(a,b)=\frac1N\sum[\log(1+e^{a\bar z_i+b})-y_i(a\bar z_i+b)]$. It uses Newton's method, $w\leftarrow w-tH^{-1}\nabla$ with $H=X^\top\mathrm{diag}(p(1-p))X/N$ and step halving. Here $a$ is $1/T$ and $b$ absorbs the constant logit offsets from $\lambda$, $\alpha$, smoothing and 50/50 batches.
- A temperature-only fit is also reported: golden-section search on $s\in[0.02,20]$ (`calibrate.py:142-163`).
- The fit refuses to proceed if $a\le0$. Because $a>0$ makes the map monotone, AUC and AP are unchanged.
- **Out-of-sample** Brier, ECE and NLL use 5-fold cross-fitting: each point is calibrated by $(a,b)$ fitted on the other 4 folds (`calibrate.py:204-216`).
- Everything is fitted on the same validation set that selected the checkpoint.

### 3.7 Map prediction

`predict.py:264-432`:
- A 64×64 window is slid over the reference grid with stride $s$ (`--stride`, default 4).
- The output grid is $\lfloor(H-64)/s\rfloor+1$ by $\lfloor(W-64)/s\rfloor+1$ cells of $30s$ m, i.e. 120 m.
- Output cell $(g_y,g_x)$ holds the score of the window centred at source pixel $(r_0+32+s\,g_y,\;c_0+32+s\,g_x)$.
- A window is skipped (NaN) if its centre pixel is nodata on the first feature.

Each window is scored with the shared D4 scorer `d4_tta_logits` (`models.py:851-891`): $\bar z$ as above, but applying `torch.rot90` in code. The calibrated, prior-shifted probability is (`predict.py:923-1000, 388-393`):

$$p=\sigma\Big(a\,\bar z+b+\underbrace{\mathrm{logit}(\pi)-\mathrm{logit}(\pi_{\text{val}})}_{\text{only with }--\texttt{prior }\pi}\Big).$$

There is no aggregation across overlapping windows: each output pixel is exactly one window's centre score. The GeoTIFF transform shifts by $-s/2$ pixels to convert centre to corner coordinates (BUG-0009, `predict.py:419-428`).

### 3.8 Self-supervised warm start (optional)

`pretrain.py` implements SimSiam on unlabelled tiles (`pretrain.py:73-111, 222-262`):
- Two augmented views per tile (jitter 8 plus random D4).
- Encoder $f$ = global-average-pooled backbone (`models.py:1249-1255`); projector $g$ ($512\to512\to512$, BN); predictor $h$ ($512\to128\to512$).
- Loss:

$$\mathcal L=-\tfrac12\Big[\cos\big(h(g(f(x_1))),\,\mathrm{sg}[g(f(x_2))]\big)+\cos\big(h(g(f(x_2))),\,\mathrm{sg}[g(f(x_1))]\big)\Big].$$

- Optimiser: AdamW ($\eta=10^{-3}$, wd $10^{-4}$), cosine schedule, 50 epochs.
- `--init-from` loads tensors that match by name and shape into the reduced-LR backbone group. Head tensors stay in the fresh group (`model_handler.py:640-683, 963`).

### 3.9 Parameter count (default `train.py` geometry, 15 features)

PyTorch is not installed in this environment, so these are counted by hand from the layer shapes.

| block | parameters |
|---|---|
| Embeddings (320,000 + 8,192 + 8,192 + 4,800 + 160,000 + 4,096) | 505,280 |
| Stem `conv1` (136·64·7·7) + `bn1` | 426,624 |
| ResNet-18 layer1–4 (147,968 + 525,568 + 2,099,712 + 8,393,728) | 11,166,976 |
| CBAM ×4 ($C^2/8+98$: 610 + 2,146 + 8,290 + 32,866) | 43,912 |
| `conv_out` (512→2) | 1,026 |
| Centre head (136→128→1) | 17,665 |
| Branch B dilated/32 (76,385) + its head (1,089) | 77,474 |
| **Total** | **≈ 12.24 M** |

This matches the code's own "~12M parameters" comment (`models.py:1111`) and the "+0.08M" for Branch B (`train.py:766-791`). Of the total, about 91% (11.17 M) are pretrained backbone weights trained at 0.1×LR, and about 4% are embedding rows. Most of the evt and fdist rows (10,000 each) belong to codes that never occur in the data.

---

## 4. Mathematics of machine-learning methods not yet used

**Baseline: what the code already does.** I read `models.py`, `model_handler.py`, `train.py`, `losses.py`, `pretrain.py`, `calibrate.py`, `generate_negatives.py` and `CHANGELOG.md`. The model already uses all of the following, so none of it is listed as "unused" below:

- **Architecture:** a ResNet-18-style trunk with CBAM attention after each stage. An optional transformer block (`EarlyAttentionBlock`, with RoPE or a relative-position bias) runs over CNN tokens. A dilated U-Net-lite `DualSpatialBranch` keeps full resolution. Pooling can be mean, centre, Gaussian or attention.
- **Losses:** focal loss, and the "assume-negative" `ANFullLoss` from Cole et al. (2023). The latter uses uniform in-state training-block background points as assumed negatives (CR-0015, CR-0031).
- **Training:** AdamW with cosine warm restarts, EMA weights, label smoothing, Dropout2d and embedding dropout.
- **Pretraining:** SimSiam self-supervised pretraining on unlabelled tiles (`pretrain.py`, using D4 rotations/flips plus jitter-crop augmentations).
- **Evaluation and post-processing:** D4 test-time augmentation; a 4-member heterogeneous ensemble (`ENSEMBLE_MEMBERS`) whose predictions are averaged at scoring time; distillation of that ensemble into one model (`--distill-from`); Platt scaling with a bias term and prior re-anchoring (`calibrate.py`).
- **Data design:** the negatives are year-matched GBIF other-species records with a 300 m buffer and 30 m thinning. That is effectively target-group background. Each also carries an optional envelope weight equal to the inverse of the grouse selection ratio (`use_sample_weights`, off by default). Validation uses spatial blocks.
- **Diagnostics:** a sklearn HistGradientBoosting baseline; permutation importance appears only in the GBM-style diagnostics.

The best leak-free single model reached TTA AUC 0.7783 (CR-0009). The methods below are judged against that ceiling.

---

### 4.1 MaxEnt, inhomogeneous Poisson processes, and why they matter here

**MaxEnt** (Phillips et al. 2006) chooses a distribution $\pi$ over $N$ grid cells. It maximises entropy $H(\pi)=-\sum_z \pi(z)\ln\pi(z)$ subject to the model's feature means being close to the empirical means:
$$|\mathbb E_\pi[f_j]-\bar f_j|\le\beta_j .$$
The dual problem is an $\ell_1$-regularised Gibbs model:
$$\pi_\lambda(z)=\frac{\exp(\lambda^\top f(z))}{\sum_{z'}\exp(\lambda^\top f(z'))},\qquad \max_\lambda \sum_{i=1}^n \ln\pi_\lambda(z_i)-n\sum_j\beta_j|\lambda_j| ,$$
where $f$ expands each covariate into linear, quadratic, product, hinge and threshold features.

**The IPP model.** An inhomogeneous Poisson process has intensity $\lambda(s)=\exp(\alpha+x(s)^\top\beta)$ and log-likelihood
$$\ell(\alpha,\beta)=\sum_{i=1}^n\log\lambda(s_i)-\int_A\lambda(s)\,ds .$$
Conditioning on $n$ gives $\pi(s)=\lambda(s)/\int_A\lambda$. That is exactly the Gibbs form above, with the intercept absorbed into the normaliser. So MaxEnt *is* an IPP fitted with a lasso penalty (Renner & Warton 2013; Fithian & Hastie 2013).

**Downweighted Poisson regression (DWPR).** Berman–Turner quadrature approximates the integral as $\int_A\lambda\approx\sum_j w_j\lambda(s_j)$, using presences plus $m$ quadrature points with weight $w_j=|A|/m$. Set $z_j=\mathbb 1[\text{presence}]/w_j$. Then
$$\ell\approx\sum_j w_j\big(z_j\log\lambda_j-\lambda_j\big),$$
which is a weighted Poisson GLM. As $m\to\infty$ it converges to the IPP MLE (Warton & Shepherd 2010).

**Infinitely weighted logistic regression (IWLR).** Fit logistic regression of presence ($y=1$) against background ($y=0$), with background weight $W$. As $W\to\infty$ the slopes converge to the IPP $\beta$ (Fithian & Hastie 2013).

**What this means for the CNN.** For a model class flexible enough, the Bayes-optimal logit of presence-vs-background classification is
$$\operatorname{logit}P(y{=}1\mid x)=\log\frac{n}{m}+\log\frac{\lambda_{\text{obs}}(x)}{b(x)} ,$$
where $b$ is the density the background was drawn from. Two consequences follow.

- **The class ratio is not the lever.** The 1:1 ratio, focal $\alpha$ and the AN-full $\lambda$ only move the intercept and change optimisation. The **background density $b(x)$** is what defines the estimand.
- **The current estimand is a relative intensity.** With GBIF other-species negatives, $b\approx$ the target-group sampling intensity. The network therefore estimates $\log\lambda_{\text{grouse}}-\log\lambda_{\text{TG}}$, i.e. grouse intensity relative to observer effort. When envelope weights $w(x)$ are switched on, the effective background becomes $b(x)w(x)$. With $w=1/\text{SR}$, the target gains $+\log \text{SR}(\text{envelope})$, which double-counts habitat selection that the labels already carry. That is worth checking explicitly whenever weights are enabled.

**The structural AUC bound.** If the species truly occupies a fraction $a$ of the background's support, even a perfect model ties on those background points. The AUC is then bounded by
$$\text{AUC}_{\max}=1-a/2$$
(Phillips et al. 2006). Ruffed grouse is a forest generalist, and target-group negatives share its observers' access, so $a$ is large. A substantial part of the 0.77 "ceiling" may therefore be structural, not a modelling failure. This is consistent with the GBM matching the CNN.

**Cost and benefit.** A `maxnet`/`elapid` fit on the GBM's tabular features takes seconds. It gives smooth, interpretable response curves and a cloglog output $1-\exp(-e^{\eta})$ for each 30 m cell. It is unlikely to beat the GBM on AUC; its value is as a transparent, statistically grounded baseline and a stacking input.

### 4.2 Occupancy/detection models and integrated SDMs

**MacKenzie occupancy model** (MacKenzie et al. 2002). Site $i$ is occupied with $z_i\sim\text{Bern}(\psi_i)$. On visit $j$, the detection is $y_{ij}\mid z_i\sim\text{Bern}(z_ip_{ij})$, with $\operatorname{logit}\psi_i=x_i^\top\beta$ and $\operatorname{logit}p_{ij}=w_{ij}^\top\alpha$. The site likelihood marginalises over $z_i$:
$$L_i=\psi_i\prod_j p_{ij}^{y_{ij}}(1-p_{ij})^{1-y_{ij}}+(1-\psi_i)\,\mathbb 1\!\left[\textstyle\sum_jy_{ij}=0\right].$$

- *Assumption relaxed:* "not recorded = absent". The model separates detectability (season, time of day, checklist duration, observer count, noise) from habitat.
- *Why it matters here:* ruffed grouse are cryptic and acoustically seasonal (drumming), so $p\ll1$ and it varies with effort.
- *Neural version:* covariates of $\psi$ and $p$ can be neural networks. The CNN's 512-d embedding can parameterise $\operatorname{logit}\psi$ (Joseph 2020).

**Integrated SDMs** (Fithian et al. 2015; Koshkina et al. 2017; Isaac et al. 2020). These share one latent intensity $\lambda(s)=e^{x^\top\beta}$ across data types:

- Presence-only records follow a thinned IPP with intensity $\lambda(s)\,e^{u(s)^\top\gamma}$, where $u$ are bias covariates.
- Presence/absence or detection data follow $P(y=1)=1-\exp(-\lambda(s)A_i)$, or the occupancy likelihood above.
- The joint log-likelihood is $\ell=\ell_{\text{PO}}(\beta,\gamma)+\ell_{\text{PA}}(\beta,\alpha)$.

The PA component identifies the **intercept**, which presence-background data cannot (Ward et al. 2009; Phillips & Elith 2013). That makes absolute occupancy probability estimable, and the bias-thinning component absorbs effort.

**Data source and cost.** The data path is eBird *complete checklists* from the EBD bulk download. Note that `ebird.py` uses the observations API, which does not give non-detections. Those checklists provide detection/non-detection with effort covariates, and state drumming-count routes could add more. Engineering cost is high (new data stream, site/visit definition, closure assumptions); compute is modest. This is the only family here that changes the **estimand**, not just the fit.

### 4.3 Spatial random effects and spatial cross-validation

**Gaussian processes / log-Gaussian Cox process.** Model $\log\lambda(s)=x(s)^\top\beta+w(s)$ with $w\sim\mathcal{GP}(0,C)$ and a Matérn covariance
$$C(h)=\sigma^2\frac{2^{1-\nu}}{\Gamma(\nu)}(\kappa h)^\nu K_\nu(\kappa h) .$$
The effective range is about $\sqrt{8\nu}/\kappa$.

**INLA-SPDE.** A Matérn field is the solution of
$$(\kappa^2-\Delta)^{\alpha/2}(\tau w)=\mathcal W,\qquad \alpha=\nu+d/2$$
(Lindgren et al. 2011). A finite-element mesh turns it into a Gaussian Markov random field with sparse precision. For $\alpha=2$:
$$Q=\tau^2\big(\kappa^4C+2\kappa^2G+GC^{-1}G\big).$$
INLA (Rue et al. 2009) then approximates posterior marginals with nested Laplace approximations, with no MCMC.

**CAR/BYM on areal units.** The conditional form is
$$w_i\mid w_{-i}\sim N\!\left(\rho\frac{\sum_j a_{ij}w_j}{n_i},\frac{\tau^2}{n_i}\right),$$
with joint precision $\tau^{-2}(D-\rho A)$. BYM adds an iid term (Besag et al. 1991).

**What this adds:** residual spatial structure from unmeasured covariates, regional observer effort or dispersal. It also gives honest standard errors under autocorrelation.

**Why it may not raise block-CV AUC.** In a held-out block, the posterior mean of $w$ shrinks to 0 beyond the range, so prediction reverts to $x^\top\beta$. The practical use is different: fit an LGCP with the **CNN logit as an offset**, $\log\lambda=\eta_{\text{CNN}}(s)+w(s)$. Mapping $\hat w$ then shows where the CNN is systematically wrong; such patterns are often effort artefacts. Beware spatial confounding: $w$ can absorb covariate effects.

Cost: about 10k points and a mesh of about 5–10k nodes over three states in R-INLA/inlabru takes minutes on a CPU.

**Spatial cross-validation theory.** Random $k$-fold estimates $\mathbb E[L\mid\text{test point within the correlation range of training points}]$. That is interpolation error, and it is optimistic for mapping new areas. Block CV with block size at least the residual-variogram range targets extrapolation error (Roberts et al. 2017; Valavi et al. 2019; Ploton et al. 2020).

Two caveats:

- If the deployment region is the same three states, a design-based estimate (a probability sample of the map) is the unbiased target. Block CV can then be *pessimistic* (Wadoux et al. 2021).
- Recommended check: compute the empirical variogram of block-CV residuals. Confirm the current block size exceeds its range and is not much larger, because over-large blocks also inflate error through covariate extrapolation.

### 4.4 Positive-unlabelled (PU) learning

**Why presence-background is PU.** Background points are drawn from the mixture
$$p_U(x)=\pi p_+(x)+(1-\pi)p_-(x),$$
where $\pi$ is the fraction of background where grouse are present. The GBIF other-species points are also unlabelled for grouse, not verified absences, even after the 300 m buffer.

**Elkan–Noto under SCAR** (selected completely at random, $P(s{=}1\mid x,y{=}1)=c$). A labelled-vs-unlabelled classifier satisfies $g(x)=c\,f(x)$, where $f(x)=P(y{=}1\mid x)$. Estimate $\hat c=\mathbb E[g(x)\mid s=1]$ on held-out positives and set $f=g/\hat c$ (Elkan & Noto 2008). This is monotone, so **AUC is unchanged**; it only fixes calibration, and only if $c$ is identifiable.

**Unbiased and non-negative PU risk.** The risk can be written using only P and U data (du Plessis et al. 2015):
$$R(f)=\pi\,\mathbb E_{P}[\ell(f,+1)]+\underbrace{\mathbb E_U[\ell(f,-1)]-\pi\,\mathbb E_P[\ell(f,-1)]}_{\hat R^-}$$
With deep nets the bracketed term goes negative, which signals overfitting. nnPU clamps it (Kiryo et al. 2017):
$$\tilde R=\pi\hat R_P^+ +\max(0,\hat R^-) ,$$
and takes a gradient step on $-\nabla\hat R^-$ when it is violated.

**How this differs from what is used.** The current AN-full loss treats U as N. That is biased toward pushing true-habitat background points down, which is the memorisation that EMA and label smoothing are currently fighting. nnPU is the principled replacement for the *uniform-background* term.

**Limits:**

- $\pi$ is not identifiable from presence-background data alone (Ward et al. 2009; Hastie & Fithian 2013). It must be swept (e.g. 0.1–0.5) and selected by block-CV AP.
- SCAR is violated, because selection depends on roads and access. "SAR" PU methods model $c(x)$ (Bekker & Davis 2020); that converges with the bias-covariate idea in §4.8.

Cost: a roughly 20-line loss change; training cost is unchanged. Expected gain is small to moderate in AP and calibration, and uncertain in AUC.

### 4.5 Boosting, forests, stacking, BART

**XGBoost** (Chen & Guestrin 2016) minimises
$$\sum_i\ell(y_i,\hat y_i)+\sum_k\big(\gamma T_k+\tfrac12\lambda\|w_k\|^2\big)$$
using a second-order expansion with $g_i=\partial\ell$ and $h_i=\partial^2\ell$. The optimal leaf weight and split gain are
$$w_j^*=-G_j/(H_j+\lambda),\qquad \text{gain}=\tfrac12\left[\frac{G_L^2}{H_L+\lambda}+\frac{G_R^2}{H_R+\lambda}-\frac{G^2}{H+\lambda}\right]-\gamma .$$

**LightGBM** (Ke et al. 2017) adds gradient-based one-side sampling (keep the top-$a$ $|g|$, sample $b$ of the rest, reweight by $(1-a)/b$), exclusive feature bundling, and leaf-wise growth. sklearn's HistGradientBoosting is already LightGBM-like, so a switch alone gains little. What would add something:

- **(a) Boosted IPP.** A Poisson objective with DWPR weights (§4.1) gives a properly specified presence-background model.
- **(b) Monotone and interaction constraints**, e.g. no effect of `road_dist` beyond a few km.
- **(c) CatBoost ordered target statistics** (Prokhorenkova et al. 2018) for the high-cardinality EVT codes. The current baseline truncates them to 254 levels plus "other", which discards information.

**Random forests** (Breiman 2001). The ensemble variance is $\rho\sigma^2+(1-\rho)\sigma^2/B$, so decorrelating trees helps. For presence-background data, *down-sampled balanced* RF (each tree sees an equal number of presences and background points) is among the strongest presence-only methods in benchmarks (Valavi et al. 2021).

**Stacking / super learner** (Wolpert 1992; van der Laan et al. 2007). Fit
$$\hat f=\sum_k\hat w_k f_k^{(-v)}$$
with $\hat w=\arg\min_{w\ge0,\,\sum w=1}\sum_i\ell(y_i,\sum_kw_kf_k^{(-v(i))}(x_i))$, where the out-of-fold predictions $f^{(-v)}$ **must** use the same spatial blocks. CNN + GBM + MaxEnt is the natural stack. The CNN sees spatial pattern and the trees see centre/neighbourhood summaries, so their errors are probably less correlated than those of the four CNN recipes.

**BART** (Chipman et al. 2010). Probit form:
$$P(y{=}1\mid x)=\Phi\!\big(\textstyle\sum_{j=1}^mg(x;T_j,M_j)\big).$$
The tree prior is $P(\text{split at depth }d)=\alpha(1+d)^{-\beta}$ with $\alpha=0.95$ and $\beta=2$. Leaves are $\mu\sim N(0,(3/(k\sqrt m))^2)$. Fitting uses Bayesian backfitting MCMC. It gives posterior uncertainty for each cell and partial-dependence curves with credible bands (Carlson 2020, `embarcadero`). Cost for 10k points × about 100 features is minutes to an hour. Expect AUC similar to the GBM; the value is the uncertainty.

### 4.6 Deep-learning variants

**ViT** (Dosovitskiy et al. 2021). Split the 64×64 patch into $P{\times}P$ tiles, e.g. $P=8$ for 64 tokens:
$$z_0=[x_{\text{cls}};x_pE]+E_{\text{pos}},\quad \text{MSA}(Q,K,V)=\operatorname{softmax}(QK^\top/\sqrt d)V .$$
The repository already runs a hybrid: transformer attention over CNN tokens. A pure ViT has weaker inductive bias, and with about 10k labels it underperforms CNNs unless pretrained, so it is not recommended on its own.

**Multi-scale / multi-resolution.** The current window is 64×30 m ≈ 1.9 km, and `DualSpatialBranch` already does multi-scale within that window. What is missing is a **wider context**. A second input at, say, 240 m resolution over 15 km (still 64×64) would capture landscape composition and forest-age mosaic at the scale grouse populations respond to. It enters through a separate encoder fused before the head:
$$h=\phi_{30}(X_{30})\oplus\phi_{240}(X_{240}).$$
Cost: one more raster-read pass and about 1.3× compute.

**Earth-observation foundation models.** Masked autoencoders minimise
$$\mathcal L=\tfrac{1}{|M|}\sum_{p\in M}\|x_p-\hat x_p\|^2$$
over masked patches (He et al. 2022). SatMAE (Cong et al. 2022) and Prithvi (Jakubik et al. 2023, trained on HLS) apply this to multispectral time series. SSL4EO-S12 (Wang et al. 2022) provides Sentinel-2 encoders.

The key mismatch is that this model's inputs are LANDFIRE/TreeMap *categorical and derived products*, not spectra. These encoders would therefore add a **new data stream**: frozen image embeddings of HLS or Sentinel-2 composites, concatenated to $h$. That could add phenology and understory signal absent from LANDFIRE.

Location encoders are a lighter alternative: SatCLIP (Klemmer et al. 2023), or the SINR approach (Cole et al. 2023), whose loss the project already adopted. They give $e(\text{lon},\text{lat})$ embeddings, but they also risk encoding observer effort geographically.

**Self-supervised pretraining.** SimSiam is already used:
$$\mathcal D=-\tfrac12\cos(p_1,\operatorname{sg}z_2)-\tfrac12\cos(p_2,\operatorname{sg}z_1).$$
The alternatives are:

- SimCLR's InfoNCE, which needs large batches:
$$\ell_{ij}=-\log\frac{e^{\operatorname{sim}(z_i,z_j)/\tau}}{\sum_{k\ne i}e^{\operatorname{sim}(z_i,z_k)/\tau}} .$$
- BYOL's momentum target, $\|q_\theta(z)-\operatorname{sg}z'_\xi\|^2$ with $\xi\leftarrow m\xi+(1-m)\theta$.

Neither changes the *invariance* learned. The more promising change is the **positive-pair definition**. Tile2Vec-style geographic positives treat spatially adjacent tiles as positives and distant tiles as negatives, via the triplet loss
$$\max(0,\|z_a-z_n\|-\|z_a-z_p\|+m)$$
in the form $\max(0,\|z_a-z_n\|^2-\|z_a-z_p\|^2+m)$ (Jean et al. 2019). This builds in Tobler's law, i.e. landscape similarity at the km scale, rather than mere D4 invariance, which the network already gets from TTA. Cost: same as the current pretraining.

### 4.7 Uncertainty quantification

**Deep ensembles** (Lakshminarayanan et al. 2017). Average $\bar p=\frac1M\sum_mp_m$ and decompose the predictive entropy:
$$\mathcal H[\bar p]=\underbrace{\tfrac1M\textstyle\sum_m\mathcal H[p_m]}_{\text{aleatoric}}+\underbrace{\mathcal I}_{\text{epistemic (mutual information)}} .$$
The 4-member ensemble already exists but is used only for averaging. Mapping $\mathcal I$ costs nothing extra and flags extrapolation, for example into novel EVT combinations.

**MC dropout** (Gal & Ghahramani 2016). Average $\frac1T\sum_tp(y\mid x,\hat W_t)$ over masks $\hat W_t\sim q$. The Dropout2d and embedding-dropout layers make this nearly free at inference ($T\approx20$ passes), but the uncertainty it gives is usually under-dispersed relative to ensembles.

**Bayesian neural networks.** Variational inference maximises the ELBO (Blundell et al. 2015):
$$\mathbb E_q[\log p(\mathcal D\mid w)]-\mathrm{KL}(q\|p) .$$
The cheapest useful variant is a **last-layer Laplace approximation** with $\Sigma=(\nabla^2_w\mathcal L)^{-1}$ on the head only, plus a probit approximation $\bar p\approx\sigma\big(\mu/\sqrt{1+\pi\sigma^2/8}\big)$ (Daxberger et al. 2021).

**Conformal prediction.** Split conformal uses scores $s_i=1-\hat p_{y_i}(x_i)$ on a calibration set and $\hat q$ = the $\lceil(n+1)(1-\alpha)\rceil/n$ empirical quantile. The prediction set is $C(x)=\{y:s(x,y)\le\hat q\}$, with $P(Y\in C)\ge1-\alpha$ under exchangeability (Angelopoulos & Bates 2021).

Two cautions apply:

- *Spatial dependence breaks exchangeability.* Use weighted conformal with $w(x)=dP_{\text{test}}/dP_{\text{cal}}$ (Tibshirani et al. 2019), or local spatial conformal (Mao et al. 2024).
- *The labels are presence-vs-background*, so coverage guarantees concern "grouse record vs background record", not occupancy. Conformal becomes much more meaningful once §4.2 data exist.

### 4.8 Covariate shift and sampling-bias correction

**Importance weighting.** Under covariate shift ($p_{\text{tr}}(x)\ne p_{\text{te}}(x)$, same $p(y\mid x)$), the test risk is
$$R_{\text{te}}=\mathbb E_{\text{tr}}[w(x)\ell],\qquad w=p_{\text{te}}/p_{\text{tr}}$$
(Shimodaira 2000). Estimate $w$ with a domain classifier: $\hat w=\frac{n_{\text{tr}}}{n_{\text{te}}}\frac{P(\text{te}\mid x)}{P(\text{tr}\mid x)}$. Clip or flatten it as $w^\gamma$ to control variance.

**Sampling bias as thinning.** Observed records arise from $\lambda_{\text{obs}}(s)=\lambda(s)b(s)$. Target-group background drawn proportional to $b$ makes $b$ cancel in the case-control logit (§4.1; Phillips et al. 2009). This holds **only if** the target group shares grouse's observation process: same taxa class (birds), same platforms (eBird/iNaturalist), same season. The GBIF other-species pool should be audited against that. The 300 m buffer also changes $b$ near grouse, which slightly biases toward "near grouse = positive".

**The bias-covariate alternative** (Warton et al. 2013). Model effort explicitly:
$$\log\lambda_{\text{obs}}=x^\top\beta+u^\top\gamma ,$$
where $u$ is road distance, distance to towns, eBird checklist density and so on. At prediction, fix $u$ at a constant, e.g. $u=\bar u$ or "near a road", so the map reflects habitat only.

This project already has `road_dist` as an input and a `diagnose_road_bias.py` diagnostic. Making it explicitly a *nuisance* covariate, set to a constant at prediction, is the principled version of what those diagnostics are circling. In the CNN it is a separate additive logit term, $\eta=\eta_{\text{habitat}}(X_{\setminus u})+g(u)$, with $g$ dropped at predict time.

### 4.9 Interpretability

**SHAP** (Lundberg & Lee 2017). The attribution for feature $j$ is
$$\phi_j=\sum_{S\subseteq F\setminus\{j\}}\frac{|S|!(|F|-|S|-1)!}{|F|!}\big[v(S\cup\{j\})-v(S)\big] .$$
TreeSHAP computes it exactly in polynomial time for the GBM baseline, giving per-point, additive attributions plus interaction values. Unlike permutation importance, it is not distorted as badly by correlated features.

**Integrated gradients** (Sundararajan et al. 2017) for the CNN:
$$\text{IG}_j(x)=(x_j-x'_j)\int_0^1\frac{\partial F(x'+\alpha(x-x'))}{\partial x_j}d\alpha ,$$
which satisfies completeness, $\sum_j\text{IG}_j=F(x)-F(x')$. Categorical layers are attributed in embedding space and summed over embedding dimensions. A sensible baseline $x'$ is the padding embedding plus channel means. The result is a 64×64 map per feature, showing whether the network uses the centre cell or the context, and whether it leans on `road_dist`/`nlcd` edges, i.e. effort proxies. Cost: about 32–64 forward-backward passes per point.

**Partial dependence and ALE.** Partial dependence is
$$\bar f_S(x_S)=\frac1n\sum_if(x_S,x_C^{(i)})$$
(Friedman 2001). It is biased under correlated covariates, which is the norm for LANDFIRE stacks. ALE integrates local derivatives within the conditional distribution instead (Apley & Zhu 2020). Given this project's history of leakage and registration bugs, these tools are best used as **audits**: they reveal reliance on artefacts, rather than raising AUC.

---

### Most promising next steps for this project

1. **Get eBird complete-checklist detection/non-detection data and fit an occupancy model or integrated SDM (§4.2).** It is the only option that breaks the presence-background identifiability limits and the $1-a/2$ AUC bound. Even used purely as an independent presence/absence test set, it would show whether 0.77 is a real ceiling.
2. **Use bias-covariate modelling with a nuisance effort term set to a constant at prediction, and audit the target-group pool and envelope weights against the IPP estimand (§4.1, §4.8).** This is cheap and corrects what the map means, not just its score.
3. **Stack the CNN, GBM (CatBoost for EVT codes) and MaxEnt/DWPR using spatial-block out-of-fold predictions (§4.5).** The model families are heterogeneous and the GBM already matches the CNN, so this is the cheapest plausible AUC gain.
4. **Replace AN-full's uniform-background term with nnPU and sweep the class prior $\pi$ (§4.4).** It is a small code change that removes the "background = absent" bias the regularisers are compensating for.
5. **Fit an INLA-SPDE log-Gaussian Cox process with the CNN logit as an offset, and run a residual variogram against the block size (§4.3).** This shows residual spatial structure and checks the block-CV design, in minutes on a CPU.
6. **Run integrated-gradients attribution audits on the CNN and TreeSHAP on the GBM (§4.9).** These catch effort proxies and artefacts, which is where this codebase's history says the risk lies.
7. **Produce epistemic-uncertainty maps from the existing 4-member ensemble, adding a last-layer Laplace approximation (§4.7).** This is essentially free and flags extrapolation.
8. **Add a wider-context 240 m branch and/or frozen EO-foundation-model embeddings (§4.6).** These would add new signal, but cost the most (new data streams, more compute).

### References (section 4)

- Apley, D.W. & Zhu, J. (2020). Visualizing the effects of predictor variables in black box supervised learning models. *JRSS-B* 82:1059–1086. https://doi.org/10.1111/rssb.12377
- Angelopoulos, A.N. & Bates, S. (2021). A gentle introduction to conformal prediction and distribution-free uncertainty quantification. https://arxiv.org/abs/2107.07511
- Bekker, J. & Davis, J. (2020). Learning from positive and unlabeled data: a survey. *Machine Learning* 109:719–760. https://doi.org/10.1007/s10994-020-05877-5
- Besag, J., York, J. & Mollié, A. (1991). Bayesian image restoration, with two applications in spatial statistics. *AISM* 43:1–20. https://doi.org/10.1007/BF00116466
- Blundell, C. et al. (2015). Weight uncertainty in neural networks. ICML. https://arxiv.org/abs/1505.05424
- Breiman, L. (2001). Random forests. *Machine Learning* 45:5–32. https://doi.org/10.1023/A:1010933404324
- Carlson, C.J. (2020). embarcadero: species distribution modelling with Bayesian additive regression trees in R. *MEE* 11:850–858. https://doi.org/10.1111/2041-210X.13389
- Chen, T. & Guestrin, C. (2016). XGBoost: a scalable tree boosting system. KDD. https://doi.org/10.1145/2939672.2939785
- Chen, X. & He, K. (2021). Exploring simple Siamese representation learning. CVPR. https://arxiv.org/abs/2011.10566
- Chen, T. et al. (2020). A simple framework for contrastive learning of visual representations (SimCLR). ICML. https://arxiv.org/abs/2002.05709
- Chipman, H.A., George, E.I. & McCulloch, R.E. (2010). BART: Bayesian additive regression trees. *Ann. Appl. Stat.* 4:266–298. https://doi.org/10.1214/09-AOAS285
- Cole, E. et al. (2023). Spatial implicit neural representations for global-scale species mapping. ICML. https://arxiv.org/abs/2306.02564
- Cong, Y. et al. (2022). SatMAE: pre-training transformers for temporal and multi-spectral satellite imagery. NeurIPS. https://arxiv.org/abs/2207.08051
- Daxberger, E. et al. (2021). Laplace Redux: effortless Bayesian deep learning. NeurIPS. https://arxiv.org/abs/2106.14806
- Dosovitskiy, A. et al. (2021). An image is worth 16x16 words: transformers for image recognition at scale. ICLR. https://arxiv.org/abs/2010.11929
- du Plessis, M.C., Niu, G. & Sugiyama, M. (2015). Convex formulation for learning from positive and unlabeled data. ICML, PMLR 37. https://proceedings.mlr.press/v37/plessis15.html
- Elkan, C. & Noto, K. (2008). Learning classifiers from only positive and unlabeled data. KDD. https://doi.org/10.1145/1401890.1401920
- Fithian, W. & Hastie, T. (2013). Finite-sample equivalence in statistical models for presence-only data. *Ann. Appl. Stat.* 7:1917–1939. https://doi.org/10.1214/13-AOAS667
- Fithian, W. et al. (2015). Bias correction in species distribution models: pooling survey and collection data for multiple species. *MEE* 6:424–438. https://doi.org/10.1111/2041-210X.12242
- Friedman, J.H. (2001). Greedy function approximation: a gradient boosting machine. *Ann. Stat.* 29:1189–1232. https://doi.org/10.1214/aos/1013203451
- Gal, Y. & Ghahramani, Z. (2016). Dropout as a Bayesian approximation. ICML. https://arxiv.org/abs/1506.02142
- Grill, J.-B. et al. (2020). Bootstrap your own latent (BYOL). NeurIPS. https://arxiv.org/abs/2006.07733
- Hastie, T. & Fithian, W. (2013). Inference from presence-only data; the ongoing controversy. *Ecography* 36:864–867. https://doi.org/10.1111/j.1600-0587.2013.00321.x
- He, K. et al. (2022). Masked autoencoders are scalable vision learners. CVPR. https://arxiv.org/abs/2111.06377
- Hefley, T.J. et al. (2014). Correction of location errors for presence-only species distribution models. *MEE* 5:207–214. https://doi.org/10.1111/2041-210X.12144
- Hefley, T.J., Brost, B.M. & Hooten, M.B. (2017). Bias correction of bounded location errors in presence-only data. *MEE* 8:1566–1573. https://doi.org/10.1111/2041-210X.12793
- Isaac, N.J.B. et al. (2020). Data integration for large-scale models of species distributions. *TREE* 35:56–67. https://doi.org/10.1016/j.tree.2019.08.006
- Jakubik, J. et al. (2023). Foundation models for generalist geospatial AI (Prithvi). https://arxiv.org/abs/2310.18660
- Jean, N. et al. (2019). Tile2Vec: unsupervised representation learning for spatially distributed data. AAAI. https://arxiv.org/abs/1805.02855
- Joseph, M.B. (2020). Neural hierarchical models of ecological populations. *Ecology Letters* 23:734–747. https://doi.org/10.1111/ele.13462
- Ke, G. et al. (2017). LightGBM: a highly efficient gradient boosting decision tree. NeurIPS. https://papers.nips.cc/paper/6907
- Kiryo, R. et al. (2017). Positive-unlabeled learning with non-negative risk estimator. NeurIPS. https://arxiv.org/abs/1703.00593
- Klemmer, K. et al. (2023). SatCLIP: global, general-purpose location embeddings with satellite imagery. https://arxiv.org/abs/2311.17179
- Koshkina, V. et al. (2017). Integrated species distribution models: combining presence-background data and site-occupancy data with imperfect detection. *MEE* 8:420–430. https://doi.org/10.1111/2041-210X.12738
- Lakshminarayanan, B., Pritzel, A. & Blundell, C. (2017). Simple and scalable predictive uncertainty estimation using deep ensembles. NeurIPS. https://arxiv.org/abs/1612.01474
- Lindgren, F., Rue, H. & Lindström, J. (2011). An explicit link between Gaussian fields and Gaussian Markov random fields: the SPDE approach. *JRSS-B* 73:423–498. https://doi.org/10.1111/j.1467-9868.2011.00777.x
- Lundberg, S.M. & Lee, S.-I. (2017). A unified approach to interpreting model predictions. NeurIPS. https://arxiv.org/abs/1705.07874
- MacKenzie, D.I. et al. (2002). Estimating site occupancy rates when detection probabilities are less than one. *Ecology* 83:2248–2255. https://doi.org/10.1890/0012-9658(2002)083[2248:ESORWD]2.0.CO;2
- Mao, H., Martin, R. & Reich, B.J. (2024). Valid model-free spatial prediction. *JASA* 119:904–914. https://doi.org/10.1080/01621459.2022.2147531
- Phillips, S.J., Anderson, R.P. & Schapire, R.E. (2006). Maximum entropy modeling of species geographic distributions. *Ecol. Model.* 190:231–259. https://doi.org/10.1016/j.ecolmodel.2005.03.026
- Phillips, S.J. et al. (2009). Sample selection bias and presence-only distribution models: implications for background and pseudo-absence data. *Ecol. Appl.* 19:181–197. https://doi.org/10.1890/07-2153.1
- Phillips, S.J. & Elith, J. (2013). On estimating probability of presence from use–availability or presence–background data. *Ecology* 94:1409–1419. https://doi.org/10.1890/12-1520.1
- Ploton, P. et al. (2020). Spatial validation reveals poor predictive performance of large-scale ecological mapping models. *Nat. Commun.* 11:4540. https://doi.org/10.1038/s41467-020-18321-y
- Prokhorenkova, L. et al. (2018). CatBoost: unbiased boosting with categorical features. NeurIPS. https://arxiv.org/abs/1706.09516
- Renner, I.W. & Warton, D.I. (2013). Equivalence of MAXENT and Poisson point process models for species distribution modeling in ecology. *Biometrics* 69:274–281. https://doi.org/10.1111/j.1541-0420.2012.01824.x
- Roberts, D.R. et al. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography* 40:913–929. https://doi.org/10.1111/ecog.02881
- Rue, H., Martino, S. & Chopin, N. (2009). Approximate Bayesian inference for latent Gaussian models using INLA. *JRSS-B* 71:319–392. https://doi.org/10.1111/j.1467-9868.2008.00700.x
- Shimodaira, H. (2000). Improving predictive inference under covariate shift by weighting the log-likelihood function. *J. Stat. Plan. Inference* 90:227–244. https://doi.org/10.1016/S0378-3758(00)00115-4
- Sundararajan, M., Taly, A. & Yan, Q. (2017). Axiomatic attribution for deep networks. ICML. https://arxiv.org/abs/1703.01365
- Tibshirani, R.J. et al. (2019). Conformal prediction under covariate shift. NeurIPS. https://arxiv.org/abs/1904.06019
- Valavi, R. et al. (2019). blockCV: an R package for generating spatially or environmentally separated folds. *MEE* 10:225–232. https://doi.org/10.1111/2041-210X.13107
- Valavi, R. et al. (2021). Modelling species presence-only data with random forests. *Ecography* 44:1731–1742. https://doi.org/10.1111/ecog.05615
- van der Laan, M.J., Polley, E.C. & Hubbard, A.E. (2007). Super learner. *Stat. Appl. Genet. Mol. Biol.* 6(1). https://doi.org/10.2202/1544-6115.1309
- Wadoux, A.M.J.-C. et al. (2021). Spatial cross-validation is not the right way to evaluate map accuracy. *Ecol. Model.* 457:109692. https://doi.org/10.1016/j.ecolmodel.2021.109692
- Wang, Y. et al. (2022). SSL4EO-S12: a large-scale multi-modal, multi-temporal dataset for self-supervised learning in Earth observation. https://arxiv.org/abs/2211.07044
- Ward, G. et al. (2009). Presence-only data and the EM algorithm. *Biometrics* 65:554–563. https://doi.org/10.1111/j.1541-0420.2008.01116.x
- Warton, D.I. & Shepherd, L.C. (2010). Poisson point process models solve the "pseudo-absence problem" for presence-only data in ecology. *Ann. Appl. Stat.* 4:1383–1402. https://doi.org/10.1214/10-AOAS331
- Warton, D.I., Renner, I.W. & Ramp, D. (2013). Model-based control of observer bias for the analysis of presence-only data in ecology. *PLoS ONE* 8:e79168. https://doi.org/10.1371/journal.pone.0079168
- Wolpert, D.H. (1992). Stacked generalization. *Neural Networks* 5:241–259. https://doi.org/10.1016/S0893-6080(05)80023-1


---

## 5. An abstract interpretation of the current model

### 5.1 What question the model actually answers

People tend to read a suitability map like this one as an answer to "where do grouse live?", "how many grouse are there?", or "how good is this habitat?". The model is not trained to answer any of those. Its training labels come from two sets of points. Positives are eBird grouse records from GBIF (`sightings.py`), with each reused coordinate collapsed to one record. `analyze_grouse.py` reports that 59–76 % of records were repeat visits to the same pin. Negatives are not absences. They are locations where birders recorded *other* species (`get_negatives.py`), which is a target-group background. Before use, the negatives are:

- buffered 300 m away from any known grouse record;
- thinned the same way as the positives;
- drawn 1:1 with the positives in every region, split and year (`generate_negatives.py`, CR-0021).

The draw is also shaped in two ways. A habitat-envelope weight (the inverse of the grouse selection ratio) makes envelopes that grouse favour less likely to supply negatives. And up to 30 % of each draw is "hard" non-vegetated negatives (water, urban), which are deliberately easy to reject.

With a balanced, assume-negative loss (`ANFullLoss`, `losses.py`), the network's logit therefore estimates a log-ratio of two sampling densities, up to a constant:

$$ s(x) \;\approx\; \log \frac{f_{\text{grouse records}}(x)}{f_{\text{background, as drawn}}(x)} + c $$

Here *x* is the landscape window around a point. The numerator is "where grouse get reported". The denominator is "where birders report other birds, filtered and weighted as the pipeline specifies". So the precise question is a contrast: **given the landscape around a point, how much more typical is it of places where grouse are recorded than of places where birders record other species?** The sampling design is part of the definition, not a nuisance around it. If the background rules changed (no envelope weighting, a different buffer, a different share of non-vegetated negatives), the meaning of a score would change too.

This is not occupancy, because nothing in the data separates "absent" from "present but not detected". It is not abundance, because duplicate visits are collapsed and each location counts once. It is not habitat quality in a demographic sense, because nothing links a score to survival or reproduction.

### 5.2 The model as a learned habitat lens

`GrouseResNet` (`models.py`) sees a 64 × 64 window of 30 m cells, about 1.9 km across and about 3.7 km², centred on the record. The 15 current channels (`FEATURE_SPEC`) are:

| Group | Channels |
|---|---|
| LANDFIRE vegetation type, height, cover, succession class and disturbance | `evt`, `evh`, `evc`, `sclass`, `fdist` |
| LANDFIRE canopy height and cover | `ch`, `cc` |
| Tree canopy cover and land cover | `tcc`, `nlcd` |
| Log-distance to roads (TIGER) | `road_dist` |
| Years since disturbance | `tsd` |
| Stand attributes imputed by TreeMap | `balive`, `tpa_live`, `qmd`, `carbon_dwn` |

The useful way to think about this is as a lens. At this grain and extent the network can perceive:

- **neighbourhood composition**: how much of the surrounding ~2 km is young forest, mixed wood, wetland, field or development;
- **configuration and edges**: the diagnostics in `CHANGELOG.md` found vegetation-type boundary density to be the strongest positive correlate (+0.40) and disturbance and infrastructure boundaries a strong negative one (−0.51);
- **disturbance history**: via `fdist` and `tsd`, the latter capped at a fixed value so that it carries no vintage information;
- **access**: via `road_dist`.

That is roughly the scale of a grouse home range, and of the young-forest and edge mosaics that the species' literature emphasises.

What the lens cannot see matters just as much:

- **Understory and stem density**, which are the actual cover grouse use. A 30 m canopy product says little about what is under the canopy.
- **Food**: aspen buds, catkins, soft mast.
- **Predators, snow depth and snow quality** (snow roosting), and weather.
- **Linear features narrower than a pixel**. `ARCHITECTURE.md` documents a two-lane road reading as "woody wetland" where it is narrow.
- **Fine structure blurred by 30 m aggregation or by imputation**. TreeMap "edges" are switches between imputed plots, not mapped transitions, which is why they are smoothed on purpose.

CR-0032's proposed 1 m canopy-structure layers are a direct attempt to widen the lens. Their measured gain is small but real: about +0.009 AUC in gradient-boosted-tree tests.

A further point about the lens's own optics. BUG-0094 found that six of the fifteen channels (the Earth Engine downloads) sit about 21 m north-west of their true position. That distance is small against a 1.9 km window, and small against location error in the records, but every model so far has learned from it. Fixing it is CR-0034/0035.

### 5.3 How the data-generating process shapes what is learned

Each step of the pipeline is a modelling decision.

- **Observer effort and access.** eBird records come from where people go. Using a target-group background is meant to cancel the shared part of that bias: birders' habits appear in both the numerator and the denominator. The cancellation is not exact, and its direction was a surprise. `diagnose_road_bias.py` found grouse positives a median of 2–5× *farther* from roads than the other-species negatives. One plausible reading is that grouse are detected on trails and in woods, while general birding concentrates near roads, feeders and water. Whatever the cause, `road_dist` can partly encode birding behaviour as well as grouse ecology, and the model cannot tell the two apart.
- **Thinning.** `MIN_SPACING_M` = 30 m only removes duplicate pixels. It is not an ecological declustering. Effort hotspots still contribute many nearby records.
- **Spatial-block validation.** Validation uses whole 3 km blocks on one global grid, about 20 % of positives (`prepare_training_data.py`, CR-0012). This stops neighbouring records leaking across splits. Before this split was introduced, validation AUC was about 0.82–0.89. The leak-free figure is about 0.76–0.78. Most of that gap was spatial autocorrelation rather than skill.
- **Year matching.** Both classes are restricted to 2020–2024 and matched count-for-count per year (CR-0019, CR-0021). A record's year selects which raster vintage is read, so without matching the vintage itself predicted the label (year-only AUC 0.66, now 0.50). The model therefore learns landscape differences *within* years, not changes between vintages.
- **Selection rules.** Records on non-vegetated land cover are excluded from the positives, records near the edge of the acquisition domain are excluded from the negatives, and so on. Each rule removes a shortcut, and each also narrows the population the model describes.

### 5.4 What the ~0.76–0.77 AUC ceiling means

On the current split the CNN reaches about 0.762 validation AUC. A gradient-boosted tree on the *same inputs* reaches about 0.770 (`diagnose_gbm_baseline.py`). The tree sees only centre-pixel codes and neighbourhood summary statistics. Earlier, wider architectures did not open a gap on leak-free data either: dual-branch U-Net, early attention, ensembles. That agreement is the central diagnostic result. **The limit is in the data, not the network.** In the diagnostic's own terms, "GBM ≈ CNN → the data is the ceiling."

Conceptually, AUC is the probability that a random positive outranks a random negative. Several things cap it below 1 regardless of model capacity:

- **Label noise in the negatives.** A birder's other-species location 300 m from any grouse record can still hold grouse. Grouse are cryptic, and detection depends on season, drumming activity and luck. Many "negatives" are unlabelled presences, and this alone caps achievable AUC.
- **Location uncertainty.** Hotspot pins, track-based checklists and coordinate uncertainty of up to 1 km among negatives mean the labelled cell is often not where the bird was.
- **Irreducible stochasticity of detection.** Two identical landscapes do not produce identical records. Whether a grouse is reported somewhere depends on who walked there and when.
- **Missing causal variables.** Section 5.2 lists what no input carries: understory, food, predators, snow.

More capacity cannot recover information that is not in either the inputs or the labels. It can only fit noise. That is consistent with the training record: train accuracy keeps rising after the selected epoch while validation ranking falls (CR-0009 selected epoch 3 of 10). The only measured routes past the ceiling have been new information: new input layers, or cleaner labels. Even those have been modest. Harvest history added +0.001 and GEDI lidar +0.000 in the tree tests; fine-scale canopy structure added about +0.009.

### 5.5 How to read the output map

`predict.py` produces, for each 30 m pixel, a score for the window centred there. `calibrate.py` then applies a Platt transform, which is monotonic. A calibrated score of 0.7 means that among validation points scoring about 0.7, about 70 % were grouse records, **under the validation set's 50 : 50 class mix**. Two consequences follow:

1. Calibration never changes *where* the map is bright. Spatial pattern is fixed by the logits (`ARCHITECTURE.md`, "Calibration cannot change a map's spatial pattern").
2. The absolute value is tied to an artificial prevalence. `predict.py --prior π` shifts the calibrated logit by the standard prior correction:

$$ \operatorname{logit} p' = a\,s + b + \operatorname{logit}\pi - \operatorname{logit}\pi_{\text{val}} $$

This only helps if π is meaningful. For this data, the true prevalence of "grouse recorded here" is unknown and depends on effort, so the shift is a scenario assumption, not an estimate.

**Appropriate uses:**
- ranking places within ME/NH/VT by how much they resemble recorded-grouse landscapes;
- screening candidate areas for field survey;
- comparing landscape configurations in relative terms;
- generating hypotheses about what scale and composition matter, such as young-forest mosaics and edge density.

**Inappropriate uses:**
- reading scores as occupancy probabilities or densities;
- setting harvest limits or making stand-level management decisions from pixel values;
- judging fine features below 30 m;
- comparing absolute values across differently calibrated models;
- extrapolating outside the training domain: beyond the three states (outside US counties, inputs such as `road_dist` are missing), outside 2020–2024 conditions, or into landscapes absent from the training data;
- treating a fall in score after a harvest as an effect of management. The model was not trained on change.

### 5.6 Epistemic status

At present the evidence is almost entirely internal. Validation AUC measures how well the model reproduces held-out draws of the *same recording process*. It is not agreement with grouse on the ground. `inspect_point.py` is the only tool that checks inputs against external truth, and nothing yet checks *outputs* against external truth.

**Evidence that would increase trust:**
- agreement with independent, design-based data the model never saw, such as state drumming-count routes, roadside or ruffed-grouse survey transects, occupancy surveys with repeat visits that estimate detection, or telemetry home ranges;
- stable rankings across model seeds and across reasonable alternative background designs (no envelope weighting, different buffers);
- the map's high-scoring landscapes matching independent knowledge of young-forest and edge habitat;
- scores tracking known disturbance events forward in time in later vintages.

**Evidence that would decrease trust:**
- weak or no correlation with drumming counts or occupancy estimates;
- high scores that turn out to follow birding effort, for example trailheads and popular hiking areas;
- rankings that change materially after the BUG-0094 registration fix or after adding the CR-0032 canopy layers. That would mean the map rests on input artefacts rather than robust landscape signal;
- strong sensitivity to the share of non-vegetated negatives or to the envelope weighting.

**Open conceptual questions:**
1. How much of the learned contrast is grouse ecology, and how much is the difference in effort between grouse-reporting and general birding? Can the two be separated without independent survey data?
2. Is the envelope weighting the right estimand? It uses an earlier analysis's selection ratios to shape the background, and so partly builds a prior view of grouse habitat into the contrast the model learns.
3. Is a 1.9 km window the right scale, or would a multi-scale or explicitly home-range-weighted context answer the ecological question better?
4. Would a model that estimates detection (an occupancy or integrated-SDM framework combining eBird with structured surveys) be a better use of the same data than a contrast classifier?
5. How should a map built from static 2020–2024 landscapes be read for a species whose habitat is defined by succession and changes on a 10–20-year clock?

---

## 6. Notes on sources and open items

- **Citations.** Section 1 was researched on the web. In section 4 only a few DOIs were checked on the web (Mao et al. 2024; Hefley 2014/2017); the rest of its citations were written from memory. The Ward et al. 2009 page numbers and DOI, and the LightGBM proceedings link, are the most worth checking. Treat every reference in this report as a lead to confirm, not as a verified citation.
- **Code facts are a snapshot.** Constants and line numbers in §2–§3 come from the working tree on 2026-10-05, before the CR-0035 data repair finished. Every quoted metric (AUC 0.762/0.770, the GBM layer gains) comes from layers that BUG-0094 shows are misregistered, and may move once CR-0035 lands.
- **Possible issue (not confirmed).** Section 4 argues that turning on `use_sample_weights` would weight negatives by 1/selection-ratio. That would add log SR to the learned target and double-count habitat selection. The flag is off by default. This is a reasoned observation, not a logged bug. Before it becomes a BUG entry, someone needs to check it against `generate_negatives.py` and `train.py`.
- **Data gap.** `ebird.py` uses the eBird observations API, which returns detections only. The occupancy and integrated-SDM work in §4.2 would need the eBird Basic Dataset bulk download of complete checklists.
