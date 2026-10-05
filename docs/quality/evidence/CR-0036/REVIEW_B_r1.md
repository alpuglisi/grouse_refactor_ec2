# CR-0036 v1, Reviewer B (ecologist and data-reality auditor)

Date: 2026-10-05. I edited no repository file. My scratch work is in `scratchpad/cr0036b/`: the WESM.csv download, the EPT index `res.geojson` and `ept_probe.py`.

**VERDICT: REVISE.** There are 2 BLOCKING concerns, 6 MAJOR, 9 MEDIUM and 3 LOW.

The route is sound. Point binning on the template lattice is the right answer to BUG-0094/0095. The two BLOCKING items are both cheap to fix:
- the CRS and units assumption for the non-EPT sources;
- the stale-mask rule.

---

## 0. What I verified independently (web and repository)

### EPT bucket: region, cost and contents

**Region and cost.** `s3://usgs-lidar-public` answers anonymous ListObjectsV2 at `s3-us-west-2.amazonaws.com`, so it is public and free to read. The BANDWIDTH report reports the header `x-amz-bucket-region: us-west-2` (BANDWIDTH.md:33); I did not re-check that header.

**NNE prefixes that exist in EPT** (listing with `prefix=NH|VT|ME|USGS_LPC_NH`, plus `boundaries/resources.geojson` from hobuinc/usgs-lidar):

| State | Projects in EPT |
|---|---|
| NH | `NH_Coastal_1_2019` (81.2 G pts), `NH_Coastal_2_2019`, `NH_Umbagog_2016`, `USGS_LPC_NH_Umbagog_QL1_2016_LAS_2019`, `USGS_LPC_CT_River_Lot6_Winnipesaulee_2015_LAS_2017` (97.2 G; bbox −72.58…−70.92, 42.69…45.32) |
| VT | `VT_Statewide_1_A23` (227 G), `VT_Statewide_2_A23` (274 G). **No `VT_Statewide_3_A23`.** |
| ME | `ME_MidCentral_1_B23` (242 G), `ME_SouthCentral_1_B22`, `ME_MidCoast_1/2/3_2021`, `ME_SouthCoastal_1/2_2020`, `ME_CrownofMaine_B2_2018`, `ME_Eastern_TL_2017` and older. **No `ME_CrownofMaine_B1`, `ME_Eastern_B1/B2` or `ME_WesternMtns`.** |

This agrees with the CR's list of projects missing from EPT. The NH CT River 2015 collection *is* in EPT, under a name that does not match WESM (B36-11). BANDWIDTH.md:41-42 says it is missing, which contradicts ROUTE.md:9.

**Pilot point in EPT, units.** The deepest EPT node over (−71.17, 43.08) in `NH_Coastal_1_2019` has ground at Z ≈ 100. The USGS EPQS 1 m DEM gives 103.9 m there (340.8 ft). So EPT Z is in **metres**, although the native project CRS is EPSG:6525/6360 (US survey feet; WESM).

**EPT schema.** It carries a `ClassFlags` extra dimension. In nodes `8-140-140-129` and `5-17-17-16`, `ClassFlags == 4` (withheld) on 25 and 33 points, which coincide with the class 7/18 noise points.

### Rockyweb

- The paths exist:
  - `.../Projects/ME_WesternMtns_B24/ME_WesternMtns_1_B24/` contains `LAZ/`, `0_file_download_links.txt` and `ME_WesternMtns_1_B24.vpc`.
  - `VT_Statewide_A23/VT_Statewide_3_A23/`, `NY_NH_Gaps_D24/NY_NHGaps_{1,2}_D24/`, `ME_CrownofMaine_2018_A18/ME_CrownofMaine_B1_2018/` and `NH_Connecticut_River_2015/{NH_CT_RiverNorthL6_P1_2015, CT_River_Lot6_Winnipesaulee_2015}/` all exist.
- The `.vpc` is STAC with `pc:count`, `proj:bbox` and `proj:wkt2`. **The tiles are in the native CRS**, for example `NAD83(2011) / UTM zone 19N + NAVD88 (m)` (EPSG:6348). They are not in EPSG:3857.
- The `pc:schemas` list separate `Withheld` and `Overlap` dimensions.
- The `.vpc` `datetime` is the publication date (2025-09-04), not the acquisition date.

### WESM

`WESM.csv` has `collect_start`, `collect_end`, `ql`, `horiz_crs`, `vert_crs` and `lpc_category` **per work unit**. It gives a date range, not a per-flight or per-cell date, and **has no leaf-state field**. NNE dates as published:

| Work unit | Collection | Leaf-state reading (mine) |
|---|---|---|
| VT_Statewide_1/2/3_A23 | 2023-03-23 … 05-13 | leaf-off canopy. Early-May lowland understory shrubs can be leafing; March snow possible |
| NH_CT_RiverNorthL6_P1/P3 | 2015-10-24 … 2016-04-29 | leaf-off. Late-Oct swaths: oak and beech still leaved |
| NH_Coastal_1/2_2019 | 2019-11-16/23 … 2020-04-23 | leaf-off. **SE NH oak and beech are marcescent in Nov** |
| NH_Umbagog_2016 | 2016-04-06 … 2018-05-24 | mixed |
| NY_NHGaps_1/2_D24 | 2024-05-07/21 … 06-16 | **leaf-on** |
| ME_WesternMtns_1_B24 | 2024-10-17 … 11-15 | mostly off; mid-Oct lowland hardwood partly on |
| ME_MidCentral_1_B23 | 2023-04-28 … 05-18 | partial late |
| ME_SouthCentral_1_B22 | 2022-04-07 … 04-21 | leaf-off |
| ME_MidCoast_1/2/3_2021 | 2021-05-09 … 2022-05-11 | **partial/on (May)** |
| ME_SouthCoastal_1/2_2020 | 2020-05-17 … 06-10 | **leaf-on** |
| ME_CrownofMaine_B1/B2_2018 | 2018-05-12 … 2019-06-08 | **partial/on** |
| ME_Eastern_B1/B2_2017 | 2017-04-30 … 12-04 | **includes summer** |

### Arithmetic, re-derived

| Claim | Check | Result |
|---|---|---|
| Newest-wins points (ROUTE.md:54-61) | 761 + 205 + 687 = 1,653 G; ×7 B = 11.6 TB; not in EPT 332 + 13 + 210 = 555 G | ✓. I could not re-derive the inputs, because `newest_points.txt` is not committed (B36-15) |
| ROUTE compute time | 1.65e12 / (16 × 0.5–0.8 M/s) = 36–57 h; 8 cores: 72–115 h; NH 205 G / (16 × 0.5–0.8 M) = 4.4–7.1 h | ✓ |
| BANDWIDTH compute time | 2.0e12 / 0.5e6 / 3600 = 1,111 vCPU-h; / (192 × 0.85) = 6.8 h; × $1.70 = $11.6 | ✓ |
| Pilot points | 100 km² × 22 pts/m² = 2.2 G; × 7 B = 15.4 GB (18 GB at BANDWIDTH's measured 8.24 B/pt). Run time 2.2e9 / 4–8 M/s = 4.6–9 min | ✓ (LOW B36-20) |
| Pilot transfer cost "$0.30" | The EPT bucket is not requester-pays, so cross-region egress is paid by the bucket owner. A NAT gateway in us-east-2 would add about $0.045/GB ≈ $0.70 | Immaterial |
| Block size | A 256² block = 7.68 km square = 59 km² → **1.3 G points** at 22 pts/m², **2.4 G** at the 41 pts/m² measured on VT A23 (BANDWIDTH.md:408) | Not the 81 M per tile quoted in the CR risk table (B36-13) |
| Rockyweb transfer | 555 G × 5.5 B ≈ 3.0 TB. At the measured 170 KB/s per stream × 32 streams = 5.4 MB/s → **6.4 days**. At 5 MB/s per stream × 32 → 5.2 h | The range spans about 30×, and the pilot measures one stream (B36-12) |

---

## 1. Concerns

### B36-1: BLOCKING. Non-EPT sources are not in EPSG:3857, and units are never checked

**Evidence.**
- CR:23 says "A block is read from the 3857 bounding box".
- CR:30 says "Each point's (X, Y) is transformed from EPSG:3857 to the template CRS", for EPT and rockyweb alike.
- The rockyweb `.vpc` shows EPSG:6348 (UTM 19N, metres) for ME_WesternMtns. WESM gives 6589 for VT_Statewide_3 and 6347/6348 for NY_NHGaps.
- BANDWIDTH.md:314 and :387-389 warn that some projects are in US survey feet, and that raw tiles keep the native CRS.
- NH_Coastal is natively 6525/6360 (ftUS). EPT happens to deliver metres, but the rockyweb or requester-pays copy of the same project would be in feet.

**Failure scenario.** In the full build (CR-0037), every rockyweb tile is treated as Mercator:
- `ME_WesternMtns`, `ME_CrownofMaine_B1`, `ME_Eastern_B1/B2`, `VT_Statewide_3` and `NY_NHGaps_2` together hold about 555 G points: 1/3 of the workload, about 44% of Maine's points and 1/3 of Vermont's.
- UTM eastings and northings read as Mercator metres land hundreds of kilometres away, so those blocks are written as **NODATA**.
- The region still passes the "<1% valid" refusal gate (CR:54).
- No test catches it, because the tests use synthetic arrays in one CRS. The pilot never processes a rockyweb tile: it only "downloads one … and logs its throughput" (CR:99).

The ftUS variant is worse. HAG values are ×3.28, so `lid_f05_5` actually measures 0.15–1.5 m, and `lid_p95` saturates at its clip. Spearman check (c) is **invariant** to that scaling (see B36-5).

**Fix.**
- Read the SRS per source: `ept.json` `srs`, the LAS header WKT or the `.vpc` `proj:wkt2`.
- Assert that the horizontal and vertical units are metres, or convert (ftUS ×1200/3937) before HAG thresholds.
- Build one pinned transformer per source CRS, and record each in `GROUSE_PROJ`.
- Select rockyweb tiles by the `.vpc` lon/lat geometry.
- Tests:
  - a synthetic UTM-sourced block and a synthetic ftUS block must produce the same cells and metrics as the 3857/metre case;
  - the lint forbids a literal `3857` outside the EPT branch.
- Pilot: process at least one full rockyweb tile (for example `ME_WesternMtns_1_B24`) end to end through checks (a), (b) and (d).
- Add the WESM-expected coverage gate (B36-5 item 5).

### B36-2: BLOCKING. The stale-cell mask cannot see disturbances between vintage Y and lidar year L when Y < L, so the layer leaks the future

**Evidence.**
- CR:59 defines the rule: "in vintage Y, a cell is NODATA when the `tsd` raster for Y records a disturbance after the cell's acquisition year".
- `tsd` for Y is computed only from disturbances up to and including Y (`generate_time_since_disturbance.py:30-36`: "never later, or the feature would leak the future"; and `_emit`, :354-364).
- Lidar years: VT 2023 (99% of VT), ME 2022/2023/2024 (`SouthCentral_B22`, `MidCentral_B23`, `WesternMtns_B24`), NH gaps 2024. These are later than the 2020–2022 vintages they are copied into (CR:58).

**Failure scenario.**
1. A VT stand is clearcut in 2021 and flown in 2023.
2. The 2020 copy shows `lid_p95` ≈ 0 and a high `lid_u1_3`.
3. A 2020 checklist in that mature stand is described by its future clearcut.
4. `tsd_2020` cannot record the 2021 cut, so the mask passes the cell.

CR test 5 (CR:82), as specified, would pin this wrong rule. This is the V10-class leak (VOTE_REPORT.md:81) built into a feature.

**Fix.** Mask in vintage Y when the most recent disturbance year d, read from `tsd` of vintage `min(max(Y, L), 2024)`, satisfies `min(Y, L) < d ≤ max(Y, L)`. Decode d as `Y' − round(tsd_decode(tsd_Y'))`, after checking that the decoded value is within 1e-6 of an integer (PA-0034); otherwise refuse.

Extend test 5 with:
- Y < L with a disturbance in (Y, L], which must be masked;
- Y < L with a disturbance ≤ Y, which must not be masked;
- multiple disturbances.

Also state the L > 2024 residual next to the existing post-2024 residual (CR:60).

### B36-3: MAJOR. The static-layer policy understates a V1-class problem: succession, not just disturbance, makes stale understory metrics wrong

**Evidence.**
- VOTE_REPORT V1 (:72) and HYBRID_REPORT (:39, :114, :133) require every feature to be within tolerance, or to pass CR-0038's source-year gate.
- Per WESM and ROUTE.md:115-116, `NH_CT_River_North_L6` 2015 is 54% of NH, which is 5–10 years before the 2020–2025 checklists. `ME_Eastern_2017` and `CrownofMaine_2018` are about 45% of ME, 2–8 years before.

**Why the mask is not enough.** Ruffed grouse use 6–20-year-old regeneration.
- In those stands the 1–3 m stem layer is the fastest-changing structure. A 3-year-old aspen or birch cut flown in 2015, with saplings at 1–3 m, is a 10–15 m pole stand with a closed canopy and a shaded-out 1–3 m layer by 2023.
- The stale mask catches only *new* disturbances after L. It cannot catch growth of stands disturbed *before* L.
- So the cells where the layer is most stale are exactly the grouse-relevant ones.
- `lid_p95` and `lid_cov5` in mature, undisturbed stands change slowly (a few dm per year), so the static treatment is defensible for them, but not for `lid_f*`/`lid_u*` in young stands.

**Fix (in this CR, because it is generator policy):**
- Add a second mask, or a separate flag band, for the understory metrics. Where `|Y − L| > YEAR_MATCH_TOLERANCE` and `tsd` at L shows a disturbance within N years before L (N ≈ 20, pinned, reviewed), write the understory features as NODATA.
- State explicitly that the lidar layers are a **declared exception** to V1, and register them for CR-0038's source-year gate.
- Bind CR-0037, through a tracker row, to report gain on the year-matched subset (`|Y − L| ≤ 2`) as the primary result.

### B36-4: MAJOR. Project, leaf-state and density offsets: the generator fixes the selection rule, while the guard is deferred to an unwritten CR-0037

**Evidence.**
- CR:22 fixes "newest covering project".
- The CR risk table (CR:112) lists four leaf-on projects. WESM dates (§0) add `ME_MidCoast_1/2/3_2021` (May), `ME_SouthCoastal_2_2020`, `ME_MidCentral_1_B23` (to 18 May), `NH_Umbagog_2016`, `NY_NHGaps_1_D24` and the October start of `ME_WesternMtns`. BANDWIDTH.md:395-402 itself lists six projects, two of which the CR drops.
- Together these are about 60% of Maine.
- Marcescent red oak and American beech hold leaves through Nov–Dec. That affects the leaf-off November flights in the oak-pine SE NH pilot area itself.
- Campbell et al. 2018 (RSE 215:330) found pulse density to be the strongest effect on lidar's ability to resolve understory density. "Fractions are density-robust" (CR:113, ROUTE.md:133) is therefore overstated: QL1 at 22–41 pts/m² against QL2 at about 2–8 pts/m² gives systematically different understory fractions, not just noisier ones.

**Failure scenario.**
- Project boundaries follow state and county lines and flight blocks, which also correlate with eBird effort and with the region.
- A GBM learns "`lid_u1_3` is high" as "Eastern 2017 summer flight" or "VT QL1".
- CR-0037's pooled, spatial-block AUC can rise from this.
- Per-project *normalisation*, which is CR-0037's stated remedy, would also remove the real between-landscape differences.
- The pilot window lies entirely in one project (CR:95), so nothing in CR-0036 measures an offset.

**Fix:**
1. Make the project-selection rule a pinned, tested parameter (`newest` or `newest_leaf_off`), so CR-0037 can change it without reopening the generator.
2. Add a **per-cell acquisition day-of-year band** to the meta raster: the median `GpsTime` converted to a date. Both EPT and LAS 1.4 carry adjusted standard GPS time. This gives leaf state and snow state at swath level, which WESM ranges cannot.
3. Add a **dual-coverage offset diagnostic** to `check_lidar_structure.py`. Where two projects cover the same undisturbed (`tsd` cap) forest cells, compute each metric from both and report the per-pair median offset by EVT forest group. This is the only measurement that separates instrument and leaf-state offset from geography.
4. Add a second pilot window that straddles a seam between a leaf-off and a leaf-on or QL2 project. Candidates: `NY_NHGaps_2_D24` against the 2015 CT River collection, or `NH_Coastal_1` (QL1) against `NH_Coastal_2` (QL2).
5. Add a tracker row binding CR-0037 to **within-project** evaluation (gain must hold within each project, or with project-held-out folds), and to a project-offset tolerance gate before inclusion.

### B36-5: MAJOR. Pilot acceptance (c) and (d) cannot fail on the defects that matter; no negative controls (PA-0021)

**Evidence.**
- CR:90 gives Spearman(`lid_p95`, LANDFIRE `ch`) ≥ 0.5. ROUTE.md:187 said > 0.6. Neither gives a justification.
- Spearman is rank-invariant, so a ×3.28 unit error (B36-1) passes. A one-cell shift of a spatially autocorrelated canopy also passes.
- LANDFIRE `ch` is a modelled product (Landsat-based, binned). In a 100 km² forest window with restricted height range, a *correct* layer can fall below 0.5, which is a false fail.
- The four understory metrics, the reason for the CR (CR:9), are not validated at all.
- Check (d), < 1% of forest cells below 50 returns, cannot fail at QL1: about 20,000 returns per 900 m² cell.
- No constructed-wrong pipeline is specified, against PA-0021(a).
- The only "may-do" gate is "≥ 1% valid" (CR:54), which a deletion of 1/3 of the data passes, against PA-0021(b).

**Fix.** Pre-register the following in `check_lidar_structure.py`:
1. **An absolute height check against an independent lidar reference.** Use NH GRANIT nDSM (2 m), aggregated to the template by pixel centre, which ROUTE.md:147 already proposes. Alternatively use ORNL 1854. Require the median difference ≤ 2 m and a Theil–Sen slope of 0.8–1.2 on undisturbed forest. Keep Spearman as a secondary check, with a threshold derived in the script.
2. **A falsifiable understory contrast.** Within the same EVT forest group, `lid_u1_3` must be higher in cells with a `tsd`-recorded disturbance 5–20 years before L than in undisturbed (cap) cells. Pre-register the direction, a minimum effect and a minimum n. If Pawtuckaway lacks enough disturbed cells, choose the window for that.
3. **A HAG sanity check.** On open non-forest EVT cells (grass, ag, wetland herbaceous), the median `lid_f1_3` must be ≤ a small bound in every slope class (also used by B36-7).
4. **Negative controls**, constructed by someone other than the author: a 1-cell shift, Z × 3.28, cells shuffled within the window, and HAG with ground replaced by min Z. Each must fail at least one check, and this is recorded.
5. **A coverage may-do gate.** Valid share ≥ WESM-expected share minus a tolerance, per project.

### B36-6: MAJOR. The 10 km pilot window cannot power the road registration sweep, and the sweep cannot read the pilot output

**Evidence.**
- `diagnose_layer_registration.py:44-48` sets `SWEEP_WINDOW_PX = 256`, `MIN_ROAD_CELLS = 500` and `N_WINDOWS = 8`. It reads the latest raster from `data/landfire` through `GrouseData`.
- The pilot is 334 × 334 cells, written to `/tmp` (CR:96). At most **one** 256-px window fits.
- Even with 8 windows, the CR-0032 sweep reported VT `tsd` as "tie (noise)" (`layer_registration_sweep.txt`).
- Pawtuckaway is rural parkland, so meeting the 500 road-cell minimum in one window is uncertain.
- "No usable windows" is the only fail-closed case. One noisy window can pass or fail by chance.

**Fix.**
- Use a pilot area of about 25 × 25 km (about 14 G points; about 1 h on 16 cores at 0.5 M/s), or at least 4 disjoint road-rich 256-px windows.
- Add a `--raster PATH` option to the diagnostic. This is acceptance code under A3.
- Require (0, 0) to beat every neighbouring offset by a pinned margin.
- Include the 1-cell-shift negative control (B36-5 item 4).

### B36-7: MAJOR. `filters.hag_nn` at its defaults (count = 1, no `max_distance`) gives slope-correlated errors in exactly the 0.5–5 m bins

**Evidence.**
- CR:29 pins `filters.hag_nn` without options. The PDAL documentation gives the defaults `count=1` and `max_distance=None`.
- ROUTE.md:70 recommends `hag_delaunay` on steep terrain.
- BANDWIDTH benchmarked 3-NN IDW.

**Failure scenario.**
- On a 30° slope (tan = 0.58), under dense spruce-fir where ground returns are 3–5 m apart, nearest-ground HAG errs by ±1.7–2.9 m.
- Low vegetation is pushed into or out of the 1–3 m and 0.5–5 m bins as a function of slope and aspect.
- The White Mountains, the Green Mountains and western ME are where this lands.
- The model then sees an understory artifact that is collinear with terrain.
- The pilot window is low relief, so it cannot reveal this.

**Fix.**
- Use `filters.hag_delaunay`, or `hag_nn` with `count ≥ 3` and `max_distance` = the pad.
- Pin the choice with a short pilot comparison on a steep window.
- Add the B36-5 item 3 slope-class check to the gate.

### B36-8: MEDIUM. Ecological validity of the metric set

**Will leaf-off all-return fractions measure stem density or understory foliage?**
- Mostly woody and conifer material.
- Small-footprint leaf-off returns from 1–3 cm deciduous sapling stems are sparse.
- Conifer regeneration (balsam fir, spruce, hemlock) and **marcescent beech** (common beech-bark-disease root-sprout thickets) and oak saplings return densely.
- So `lid_u1_3` is partly a conifer and beech index, not a pure stem-density index. That is still useful, since grouse use conifer for winter cover, but CR-0037's interpretation and partial-dependence reading must say so.

**Is "cover above 5 m" meaningful leaf-off?** It is meaningful as woody plus conifer cover. Branches still intercept many first returns. It is not canopy closure. It is the metric most sensitive to leaf state, so it is the first to show project offsets (B36-4).

**ORD versus NRD.**
- `lid_f05_5` and `lid_f1_3` are all-return fractions (ORD), which canopy occlusion and pulse density dominate.
- Campbell et al. 2018 found NRD clearly better than ORD for understory density (R² 0.44 against 0.14).
- `lid_u1_3` is the NRD form.

**Fix:**
- Replace `lid_f05_5` and `lid_f1_3` with NRD forms, or keep them only as QA. NRD here means n(bin) / n(HAG < bin top).
- Add NRD 0.5–2 m (brood and shrub cover).
- Add NRD 3–5 m and 5–10 m. The 6–20-year sapling-to-pole stage that grouse select spans 2–10 m, and `lid_p95` alone cannot separate a 6 m sapling stand from a two-storey stand.
- Keep `lid_p95` and `lid_sd`.
- The 0.5 m floor is right: QL2 vertical error and ground misclassification under shrubs make lower bins unreliable.

### B36-9: MEDIUM. The classification filter rests on a false mechanism, and keeps non-vegetation classes

**Evidence.**
- CR:28 and ROUTE.md:69 say withheld points are "stored as 128 and above".
- EPT `NH_Coastal_1_2019` stores withheld in a separate `ClassFlags` dimension (value 4, verified).
- The rockyweb LAS 1.4 schema has a separate `Withheld` dimension.
- PDAL's `Classification` therefore never carries the withheld bit.
- In the nodes I sampled, withheld points coincided with class 7/18, so the impact here is small, but this is not guaranteed for other projects.
- `[0:6],[8:17]` also keeps:
  - class 6 (building);
  - classes 13–16 (wire guard, wire conductor, transmission tower, wire connector);
  - class 17 (bridge deck).

  These inflate `lid_cov5` and `lid_p95` along power-line corridors, which are shrubby, grouse-relevant habitat, and on bridges over road cells used by check (b).

**Fix.**
- Filter `Withheld == 0` (or the `ClassFlags` bit) explicitly.
- Compute the vegetation metrics from classes {1, 2, 3, 4, 5}, plus 9 as ground-level if that is wanted.
- Pin the class set and add a test.

### B36-10: MEDIUM. The nodata rule "no ground return within the block" is ambiguous

**Evidence.** CR:50.
- Read per block, the rule almost never fires.
- Read per cell, it NODATAs cells under dense conifer and over water. That is habitat-correlated missingness, and conifer cover is itself a grouse covariate.

**Fix.** Define the rule as "no ground point within `max_distance` of the cell", consistent with B36-7, and test it.

### B36-11: MEDIUM. WESM work units do not map to EPT or rockyweb names, and the evidence contradicts itself

**Evidence.**
- WESM work units `NH_CT_RiverNorthL6_P1/P2`, `NH_CT_River_North_L6_P3` correspond to the EPT resource `USGS_LPC_CT_River_Lot6_Winnipesaulee_2015_LAS_2017`.
- On rockyweb, `CT_River_Lot6_Winnipesaulee_2015` and `NH_CT_RiverNorthL6_P1_2015` are separate folders.
- BANDWIDTH.md:42 says NH CT River is missing from EPT; ROUTE.md:9 says 97% of NH is in EPT.
- CR:22 assigns "from WESM" and then reads `s3://usgs-lidar-public/<project>/`, which assumes the names match.

**Fix.**
- Commit a pinned `LIDAR_SOURCES` table: WESM work unit → {EPT prefix | rockyweb `.vpc` | absent}.
- Add a test that every WESM work unit intersecting a template maps to exactly one source.
- Resolve the CT River footprint question with an EPT-bounds against WESM-polygon check.

### B36-12: MEDIUM. The rockyweb throughput test measures one stream; requester-pays is not checked

**Evidence.**
- CR:99.
- BANDWIDTH.md:41-45 says the requester-pays bucket `s3://usgs-lidar` is unchecked.
- The arithmetic in §0 shows 5 h to 6.4 days for about 3 TB.

**Fix.** The pilot should:
- measure aggregate throughput with 32 parallel streams for at least 10 minutes;
- run `aws s3 ls s3://usgs-lidar/Projects/ --request-payer requester` for the five missing projects;
- record both, so CR-0037's plan rests on measured figures.

### B36-13: MEDIUM. Memory: blocks are 1.3–2.4 G points, and the split must be decided before reading

**Evidence.**
- CR:26 says "A block whose point count exceeds `LIDAR_MAX_BLOCK_POINTS` is split".
- CR:114 says "dense tiles reach about 81 M points", which is a tile figure.
- A QL1 256² block holds 1.3–2.4 G points (§0). At 50–100 B/pt (BANDWIDTH.md:274), that is 65–240 GB per worker.

**Fix.** Specify that the count comes from the EPT hierarchy or `.vpc` `pc:count` before any read. Pin the default (for example 100 M), and test the recursion on a synthetic hierarchy.

### B36-14: MEDIUM. Acceptance code is not committed; thresholds are restated in prose (CR-0011 A3)

**Evidence.**
- `tests/test_cr0036.py` and `check_lidar_structure.py` do not exist on the branch at `d90304b`.
- The CR restates `MIN_RHO_CH = 0.5`, 50 returns and 1% (CR:49, 90-91).

**Fix.** Commit both before the round-2 review, and have the CR cite the constants by name only. Reviewers cannot approve an acceptance design they cannot read.

### B36-15: MEDIUM. Evidence files cited by ROUTE are absent

**Evidence.** ROUTE.md:4 lists `wesm_summary.txt`, `newest_points.txt`, `resources.geojson`, `wesm_nne.gpkg` and `nodes/` as "in this directory". `docs/quality/evidence/CR-0036/` holds only the two `.md` files. The newest-wins shares and point totals cannot be re-derived.

**Fix.** Commit the text outputs and the script that produced them; omit the 3.7 GB gpkg.

### B36-16: MEDIUM. Paths and registries

**Evidence.**
- `data/landfire/{R}_lidar_meta.tif` (CR:63) has no `PATH_TEMPLATES` entry (`grouse_data.py:107-131`), against PA-0003/PA-0025.
- Registering six names and scales in `FEATURE_SPEC`/`RASTER_FEATURES` now (CR:72) pre-commits a metric set that the pilot and B36-8 may change.

**Fix.**
- Add a `lidar_meta` template.
- Move the `models.py` registration to CR-0037, or accept that it will churn and say so.
- Add the day-of-year band from B36-4.

### B36-17: MEDIUM. Conflict with the HYBRID_REPORT plan and numbering

**Evidence.** HYBRID_REPORT.md:47 says "Not in v1: … lidar". Its §5 table (:110-115) reserves CR-0036 for the H250 v0 product, CR-0037 for the tier harness, and CR-0038 for the EBD ingest with the source-year gate.

**Fix.**
- State the owner's decision that supersedes or sequences the hybrid plan.
- Renumber the follow-up (CR-0037 is already allocated in that plan), or record the reallocation.
- Declare how the lidar layers satisfy CR-0038's source-year gate (the meta year band).

### B36-18: LOW. Snow during early-spring flights

**Evidence.** VT_Statewide_1 starts 2023-03-23, and the NH 2015/16 and 2019/20 projects run through April. Residual snowpack at elevation raises the "ground" surface and compresses saplings, which pushes understory returns down and out of the bins.

**Fix.** Use the meta day-of-year band (B36-4), and spot-check SNODAS for high-elevation blocks in CR-0037. Add this to the out-of-scope list as tracked.

### B36-19: LOW. Seam exactness is conditional

**Evidence.** CR:32. HAG at a point equals the whole-block value only if its nearest ground points lie within the 90 m pad.

**Fix.** Set `max_distance` ≤ the pad (B36-7). Make test 3 include sparse-ground and water cases.

### B36-20: LOW. Minor figure and cost inconsistencies

**Evidence.**
- ROUTE uses 7 B/pt; BANDWIDTH measured 8.24 B/pt. That gives 15 GB against 18 GB for the pilot.
- The "$0.30" pilot transfer is borne by the bucket owner, not the reader. NAT processing applies if the pilot runs in a private subnet.

**Fix.** State a single figure.

---

## 2. Answers to the specific questions

**Data reality.**
- NH: the EPT coverage is real, under mismatched names (B36-11).
- VT: Statewide_3 is rockyweb-only.
- ME: about 44% of points are rockyweb-only.
- The bucket is public, in us-west-2, and free to read.
- Rockyweb paths and `.vpc` files exist, but the tiles are in the native CRS (B36-1).
- WESM gives per-work-unit date *ranges*, with no leaf-state field.
- The arithmetic holds (§0), except the per-block memory figure.

**Ecological validity.** The six metrics are a reasonable start, with these changes (B36-8):
- leaf-off fractions measure woody stems plus conifer and marcescent foliage;
- `lid_cov5` is woody and conifer cover;
- replace the ORD fractions with NRD;
- add 0.5–2 m and 3–5 / 5–10 m bins for brood cover and 6–20-year stands.

**Mixed projects.** The CR does not guard against the model learning the lidar project. It defers that to CR-0037 with nothing binding it, and fixes the selection rule in this CR (B36-4).

**Static policy.** As written, the stale mask is wrong for Y < L (B36-2). Even when corrected, it misses succession in young stands, which are the grouse-relevant cells. This is a V1-class problem (B36-3).

**Pilot.**
- The Spearman ≥ 0.5 check is unjustified, can fail on a correct layer, and cannot fail on a unit or shift error.
- The understory metrics are untested.
- One 10 km window gives at most one registration window, so the road sweep is underpowered (B36-5, B36-6).

**Process.**
- The split into the generator plus acceptance (CR-0036) and the build plus evaluation (CR-0037) is correct under A5.
- Missing deliverables:
  - the `PATH_TEMPLATES` entry;
  - committed gate code;
  - committed evidence;
  - tracker rows binding CR-0037 to within-project and year-matched evaluation;
  - a pinned conda environment (a lock file, so PDAL and PROJ versions are reproducible).
- Missing out-of-scope items: snow, steep-terrain HAG validation at scale, and the arm64 build.

## 3. Sources
- EPT bucket: https://s3-us-west-2.amazonaws.com/usgs-lidar-public/ (listing, `NH_Coastal_1_2019/ept.json`, `ept-hierarchy`, `ept-data` nodes)
- EPT index: https://github.com/hobuinc/usgs-lidar (`boundaries/resources.geojson`)
- Rockyweb: https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/ (including `ME_WesternMtns_B24/ME_WesternMtns_1_B24/ME_WesternMtns_1_B24.vpc`)
- WESM: https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/metadata/WESM.csv
- USGS EPQS: https://epqs.nationalmap.gov/v1/json?x=-71.17&y=43.08&wkid=4326&units=Meters
- PDAL `filters.hag_nn`: https://pdal.io/en/stable/stages/filters.hag_nn.html
- Campbell, Dennison, Hudak, Parham & Butler (2018), "Quantifying understory vegetation density using small-footprint airborne lidar", *Remote Sensing of Environment* 215:330–342. https://research.fs.usda.gov/treesearch/56418
