# CR-0036 v1 — Independent Review A (round 1, unrestricted)

Reviewer A, 2026-10-05. HEAD `d90304b` (branch `claude/nice-cori-creqpb`). No repository file was edited.

**VERDICT: REVISE.** There are 3 BLOCKING, 10 MAJOR, 4 MEDIUM and 2 LOW concerns.

## 0. What I re-derived or verified independently

| Claim | Result | How |
|---|---|---|
| `usgs-lidar-public` is in us-west-2 and public | **True** | `curl -sI https://usgs-lidar-public.s3.amazonaws.com/` returns `x-amz-bucket-region: us-west-2` |
| EPT points are in EPSG:3857 | **True** | `NH_Coastal_1_2019/ept.json` `srs.horizontal = 3857`; no vertical SRS |
| EPT Z is in metres | **True for the sampled source** | `ept-sources/USGS_LPC_NH_Coastal_2019_B19_00000650.json`: the source header is `NAD83(2011) / New Hampshire (ftUS) + NAVD88 height (ftUS)`, minz 244.85 ft. The EPT bound is 74.63 = 244.85 × 0.3048006. Entwine converted Z with `filters.reprojection out_srs EPSG:3857`. |
| EPT schema has `Classification` and `ReturnNumber` | True; it also has **`ClassFlags`, `ScanChannel` and `GpsTime`** | same `ept.json`. These come from LAS 1.4 format 6 (`dataformat_id 6`), not "LAS 1.2 format 1" as `ROUTE.md` §2 says |
| `filters.range` ORs ranges on the same dimension | **True**, and bounds are inclusive | https://pdal.io/en/latest/stages/filters.range.html: "If more than one range is specified for a dimension, the criteria are treated as being logically ORed together … all values are inclusive". `[0:6],[8:17]` keeps {0..6, 8..17}. |
| `readers.ept` `requests` option | True: "[Minimum: 4] [Default: 15]". It also has `ignore_unreadable` (default false) and `polygon` | https://pdal.io/en/latest/stages/readers.ept.html |
| `filters.hag_nn` defaults | `count` = 1, `max_distance` = None, **`allow_extrapolation` = false**: "If false and a non-ground point lies outside of the bounding box of all ground points, its HeightAboveGround is set to 0" | https://pdal.io/en/latest/stages/filters.hag_nn.html |
| Withheld points are "stored as 128 and above" (`ROUTE.md` §2), so the class ranges drop them | **False** under PDAL | see A36-6 |
| Rockyweb `NY_NHGaps_2_D24` | UTM 19N NAD83(2011), metres, flown 2024-05-21 to 06-16 | rockyweb `metadata/USGS_LPC_NY_NH_Gaps_D24_w2580n48750.xml` |
| tsd encoding | `years_since = Y − last` (`generate_time_since_disturbance.py:359`), clipped to 30, stored as `rint(log1p(y)·1000)` (`models.py:681-692`). `tsd_decode` is **not exact**: maximum error 0.011 y; `rint(decode)` recovers y exactly for 0..30 | computed |
| Vintage years are 2020–2025 (CR §2) | **False**: they are 2016–2025 | `evidence/CR-0035/step2_redownload_and_inventory.txt:17-18` (tsd, nlcd and TreeMap 2016–2025) |
| `STATIC_FEATURES` and `RASTER_FEATURES` live in `models.py` (CR §4) | **False** | `STATIC_FEATURES` is at `generate_canopy_structure.py:73` and is pinned by `tests/test_cr0032.py:163`. `RASTER_FEATURES` is at `grouse_data.py:135` |
| Gate and test code are committed before approval (CR §5, A3) | **False** | `git show --stat HEAD` lists only the CR, the review log and two evidence files. There is no `tests/test_cr0036.py` and no `check_lidar_structure.py` |
| Pilot centre (−71.17, 43.08) lies inside `NH_Coastal_1_2019` | Inside its `boundsConforming` bbox (x = −7 922 608, y = 5 324 157). I did not verify the footprint polygon. | computed |
| Default `pyproj` 3857 → NAD83 Albers operation | **Not pinned.** `TransformerGroup` lists 4 candidates: null "NAD83 to WGS 84 (1)" (4 m), a Helmert (−1, −1, +1) m, a Helmert (+2, 0, −4) m, and ballpark. `Transformer.from_crs` reports "unavailable until proj_trans is called", meaning it picks per point. NAD83(2011) → NAD83 warns that the NADCON5 grid is missing, so the result depends on the environment. | pyproj 3.7.2 / PROJ 9.5.1, here |

The following hold as the CR states them: binning on the template's own transform with an exact per-point transform is the right design (BUG-0094/0095 lessons). The 90 m pad, in 3857 units, is about 61–66 m on the ground. The 30-year cap is never reached for Y ≤ 2025, because the record starts in 1999.

---

## 1. Concerns

### A36-1 — BLOCKING — The rockyweb / `readers.las` path is specified as if its points were EPSG:3857 metres
**Evidence.**
- CR:15 and CR:24 bring rockyweb LAZ into scope through `readers.las`.
- CR:23 reads "from the 3857 bounding box".
- CR:30 says "Each point's (X, Y) is transformed from EPSG:3857". It is the only transform rule in the CR.
- Raw tiles keep their native CRS: `BANDWIDTH.md` §1 says "The raw tiles keep the native project CRS", and `NY_NHGaps_2_D24` is UTM 19N (verified above).
- `BANDWIDTH.md` §4 step 4.4 warns that "some older projects are in **US survey feet** … convert before applying the 0.5/5 m thresholds". The CR dropped that warning.
- Feet are live in this region: the NH_Coastal 2019 source tiles are ftUS both horizontally and vertically (verified above).

**Failure scenario.**
1. As written, a `VT_Statewide_3_A23` tile in EPSG:6589 metres is treated as 3857. Every point lands far outside the template, every cell becomes NODATA, and the region still passes the 1% floor (§1.8) because the EPT cells are valid. About 210 G points of VT silently become "no lidar".
2. An implementer who does read the header CRS still meets no rule for Z units. A ftUS project then gives HAG in feet, so `lid_f05_5` actually measures 0.15–1.5 m.
3. No acceptance check catches this. Spearman ρ in (c) is invariant to scale, and every test uses synthetic metric arrays.

**Fix.** Preferred: take the rockyweb reader out of CR-0036, so the generator handles EPT only and the pilot still measures rockyweb throughput, and specify it in CR-0037. This also helps A5. Otherwise:
- Specify per-source horizontal CRS from the header.
- Pin one transformer per source CRS (A36-14).
- Convert Z to metres, with the unit read from the header and refused when absent.
- Add a test with a synthetic ftUS source.
- Add a gate on absolute height level (A36-12).

### A36-2 — BLOCKING — Project assignment is contradictory between block level and cell level
**Evidence.** CR:22 says "Each block is assigned its newest covering project" and, in the same item, "A cell … is assigned to … the newest that covers the cell centre". The cache key is "(region, block, project, recipe)" (CR:53), so it holds one project per block. Blocks are 7.68 km square. `NY_NHGaps_2_D24` exists to fill gaps (6% of NH, `ROUTE.md` §4).

**Failure scenario.** The block-level reading, which the cache key implies, makes every block that touches an NHGaps polygon read NHGaps only. Every cell in those blocks outside the gaps then falls below 50 returns and becomes NODATA, even though `NH_CT_River`/`NH_Coastal` cover them. The same happens along every newer/older project boundary, which removes a band up to 7.68 km wide. Nothing gates on coverage loss beyond the 1% region floor.

**Fix.**
1. Rasterise a per-cell project-assignment grid on the template first, using the cell-centre rule (WESM footprints → template; band 4 of the metadata raster).
2. Have each block read every project assigned to at least one of its cells. Compute HAG within each project, so ground comes only from the same project (`BANDWIDTH.md` §5.3/§5.7).
3. Keep a point only if its cell's assigned project equals the point's project.
4. Key the cache on the sorted project set.

Add a test: a two-project synthetic block where cells of the older project keep their values.

### A36-3 — BLOCKING — The stale-cell mask ignores vintages earlier than the acquisition (Y < A), the majority case for VT and ME
**Evidence.** CR:59 masks only when "the `tsd` raster for Y records a disturbance after the cell's acquisition year". `tsd_Y` holds only disturbances ≤ Y: the generator builds year Y "from the disturbance record up to and including Y - never later" (`generate_time_since_disturbance.py:34-36`). Vintages run 2016–2025, not "2020–2025" (CR:57; see §0).
- `VT_Statewide_*_A23` (2023) is copied to 2016–2022, which is 7 of 10 vintages earlier than acquisition.
- `ME_WesternMtns_B24` (2024) is copied to 2016–2023.

**Failure scenario.** A VT stand is clearcut in 2020. A 2018 record falls in it. The 2023 lidar shows 3-year regeneration with a dense 0.5–5 m layer. `tsd_2018` has no disturbance after 2023, so the mask does nothing, and the 2018 record gets post-harvest structure. That is a wrong value labelled valid. It is also future information about the landscape, which the tsd generator explicitly forbids.

**Fix.** For Y < A, mask when `D_A > Y`, where `D_A = A − rint(tsd_decode(tsd_A))` is the latest disturbance ≤ A. `tsd_A` exists for A ∈ 2016–2025; for A = 2015, Y > A always holds. The general rule: mask if any disturbance lies in (min(Y, A), max(Y, A)]. Add both directions to test §5.5 and correct the vintage range.

### A36-4 — MAJOR — The mask arithmetic is not well defined: rounding, the equal-year case, acquisition year and tsd nodata
**Evidence.**
- CR:59 gives `Y − tsd_decode(tsd_Y)` with no rounding. `tsd_decode` is inexact (§0). With Y = 2020 and A = 2017:
  - years_since = 3 decodes to D = 2017.0012, so `D > A` holds and the cell is **masked**, although D = A;
  - years_since = 2 decodes to 2017.9988, which is correct only by luck.
- The behaviour at D = A therefore depends on the float error for each value of y.
- The CR states "after" (`>`), but test §5.5 includes "equal" with no expected value.
- Spring leaf-off flights (VT: 23 Mar – 13 May 2023) followed by same-year harvest make D = A stale, so `D ≥ A` is the conservative rule.
- "Acquisition year" is undefined for multi-year projects: `NH_CT_River` Oct 2015–Apr 2016, `Umbagog` 2016–2018, `MidCoast_2` 2021–2022. Using the end year under-masks.
- tsd NODATA (−9999) decodes to about −1, so D ≈ Y + 1 and the cell is masked by accident. That is unspecified.

**Fix.**
- Define `D = Y − int(rint(tsd_decode(t)))` and mask `D ≥ A`.
- Define A per cell from `GpsTime` (present in the EPT schema), or else as the project start year.
- Make tsd NODATA give lid NODATA explicitly (PA-0017).
- State every case in the CR, and have the test assert each one.

### A36-5 — MAJOR — The static policy breaks the year-match intent beyond disturbance, and the CR does not admit it
**Evidence.** `YEAR_MATCH_TOLERANCE` exists because "data that far from the sighting date describes a different landscape" (`grouse_data.py:166-174`). The CR's only residual risk (CR:60) is post-2024 disturbance. Gaps reach 10 years (NH 2015 lidar for 2025 records) in both directions.

The 0.5–5 m layer in young stands is the fastest-changing structure in the forest, and it is the very signal this CR exists for: a 5-year cut at A is pole-stage 8 years later. This is not covered by the mask and is not stated.

**Fix.**
- Admit it in Risk. Carry `|Y − A|` as a metadata band, or record it per vintage.
- Require CR-0037 to evaluate gain stratified by `|Y − A|`.
- Optionally mask young stands (tsd_A < 15) when `|Y − A| > k`.

A tracked follow-up into CR-0037 is acceptable if it is stated here.

### A36-6 — MAJOR — The withheld filter contract is false, and bridge decks are kept
**Evidence.** The CR (CR:28) and `ROUTE.md` §2 claim the class ranges drop "withheld points (stored as 128 and above)". In PDAL, withheld is not part of `Classification`:
- The EPT schema carries a separate `ClassFlags` dimension (verified), and its sources are LAS 1.4 format 6 with a full-byte classification.
- `readers.las` splits the flag bits out of the LAS 1.2 classification byte.
- So `Classification` is never ≥ 32 for formats 0–5, and `[0:6],[8:17]` keeps withheld points.

Class 17 (bridge deck) is kept, so a deck 5–30 m above the ground or water below reads as canopy. That bias lands on road cells, which are the registration reference.

**Fix.**
- Drop `ClassFlags & 4` for EPT and `Withheld == 1` for `readers.las` in numpy after the read.
- Use `[0:6],[8:16]`, or justify keeping 17.
- Add a test with withheld-flagged points.
- Correct the ROUTE claim in the CR text.

### A36-7 — MAJOR — Clipping `lid_p95` to [0, 600] violates PA-0034 and the `mch_*` precedent
**Evidence.** CR:43 says "clipped to [0, 600]". PA-0034 requires refusing an unrepresentable value rather than coercing it. `mch_height_encode` refuses rather than clips (`models.py:710-719`), and the generator writes NODATA, counted, with a region refusal above `MCH_MAX_OVER_FRAC` (`generate_canopy_structure.py:34,194`). A field cell with a few unclassified tower or wire returns above 60 m becomes a fabricated "60 m forest". `lid_sd` has no stated bound.

**Fix.**
- Over 60 m becomes NODATA, counted, with a refusal fraction.
- The encoders refuse out-of-range values; there is no clipping.
- State `lid_sd`'s bound.
- Reuse `mch_*_encode` if the semantics are identical, rather than adding near-duplicates.

### A36-8 — MAJOR — Several metric edge cases are undefined, so the brute-force tests have no specification to test against
**Evidence (CR:38-52):**
- `lid_u1_3` with n(HAG < 3) = 0 has no value given, although test §5.2 tests that case. It occurs in dense canopy cells whose ground comes from neighbouring cells.
- `lid_cov5` with no first returns has no value. `ReturnNumber` = 0 occurs in legacy data, and a cell with ≥ 50 returns and no `ReturnNumber == 1` gives NaN. The encoder then raises, and the whole region aborts.
- The `lid_sd` ddof is unstated.
- The p95 method is "pinned" only in the test, not in the definition.
- "No ground return within the block" (CR:50) reads as block-level. Per cell or per block?
- Cells cut by a footprint edge are computed from part of the cell. That conflicts with PA-0017: an output pixel must be covered by its source.

**Fix.**
- Put every edge-case value in the table, preferably as NODATA.
- Name the percentile method and ddof.
- Define "first return" as `ReturnNumber == 1`, with NODATA when the denominator is 0.
- Make the ground rule per cell or per block explicitly.
- Add a coverage rule, for example returns present in all 4 quadrants of the cell, else NODATA.

### A36-9 — MAJOR — Seam exactness is not guaranteed by the stated design, and its test cannot fail here
**Evidence.**
- CR:32 says seams are "therefore exact". With `hag_nn` defaults (`max_distance` = None, `allow_extrapolation` = false; §0), a point's ground neighbour can lie beyond the pad, for example on lakes or under sparse ground in dense conifer.
- Whole-block and sub-block results then differ, and points outside the ground bbox get HAG = 0 silently.
- Sub-block splitting is data-driven (`LIDAR_MAX_BLOCK_POINTS`), so the outputs depend on the partition.
- k-NN ties can also be broken differently when the point sets differ.
- Test §5.3 needs PDAL, and PDAL is not installed here (`ModuleNotFoundError: pdal`), so CR:102/119 say it will be **skipped**. A skipped test cannot fail, which fails PA-0021(a).

**Fix.**
- Pin `count` and `allow_extrapolation`, and set `max_distance` ≤ pad, in the same 3857 units. With that, exactness is provable: every ground point within `max_distance` of an in-block point lies in the padded read.
- Write NODATA (or count) points with no ground within `max_distance`.
- Build the synthetic test so that a no-pad implementation fails: ground sparse near the edges, sloped terrain.
- Either compute HAG in a numpy/scipy kernel that the test can exercise without PDAL, or require the PDAL test to run on EC2, with the output committed as evidence.

### A36-10 — MAJOR — The memory and split design is infeasible as stated
**Evidence.**
- A 256 × 256-cell block is 59 km². At 22 pts/m² (the pilot) that is 1.3 G points, and at 41 pts/m² (the measured VT A23 tile, `BANDWIDTH.md` §5.5) it is 2.4 G points, before the pad.
- At about 40–60 B/pt (PDAL table plus numpy XYZ, HAG, cell index and lexsort index), that is 50–145 GB per block. With one process per core, that is one block per core.
- CR:26 splits when a block "exceeds `LIDAR_MAX_BLOCK_POINTS`", but gives no way to know the count before the read.
- The Risk row (CR:114) cites tile sizes of 81 M, not block sizes.
- For `readers.las`, every sub-block re-downloads whole intersecting tiles over the slowest link.

**Fix.**
- Estimate counts before reading, from the EPT hierarchy or the `.vpc` `pc:count`.
- Size blocks from a per-worker memory budget (384 GB / 192 workers ≈ 2 GB, about 30 M points, about 1 km²).
- Show the arithmetic in Risk.
- For tile sources, process per tile into additive per-cell partials (`BANDWIDTH.md` §4.4–4.6), or defer with A36-1.

### A36-11 — MAJOR — The resume cache key omits the grid identity, which is a BUG-0094-class registration risk
**Evidence.** The key is "(region, block, project, recipe)" (CR:53). The CR-0032 precedent keys on `(wkt, transform, width, height, tile_px, asset, RECIPE_VERSION)` (`generate_canopy_structure.py:344-346`) and re-checks each tile's transform.

**Failure scenario.** The template EVT is re-downloaded with a different origin or extent (it is "its latest EVT clip"). Block (i, j) cached under the old grid is then pasted at the new block (i, j). Content shifts by whole or partial blocks while `grid_mismatch` stays `None`, because the output is written with the new T.

**Fix.**
- Key on template WKT, transform, shape, block size, the sorted project set, the WESM snapshot digest, the pinned PROJ pipeline strings, and the PDAL/HAG constants.
- Re-verify each cached block's origin.
- Apply the tsd mask at assembly from the current tsd files, never cached, and record the tsd digest in the tags.

### A36-12 — MAJOR — The acceptance set does not meet PA-0021
**Evidence (CR:87-92):**
- **(a) No constructed broken pipeline is named for any gate,** which PA-0021(a) requires. Each needs one: a layer shifted by 1 cell and by ½ cell; Z in feet; withheld points included; wrong project.
- **Check (a), `grid_mismatch`, is true "by construction"** (CR:34), so every correct and every incorrect binning passes it. Under PA-0021(e) it is not a gate. Label it OBS, or replace it with an independent exact gate: recompute a seeded sample of cells by polygon containment in the template CRS, using a second transform path such as PDAL `filters.reprojection`, and require equal counts.
- **Check (b) cannot run on the pilot as written.**
  - `diagnose_layer_registration.py` reads `rd.latest_raster_path(f)` for features on disk (`:100-120`). The pilot is written to `/tmp`.
  - It picks 8 seeded 256-px windows region-wide (`pick_windows`, `:73-86`). A 334-px pilot holds at most one stride position (r, c = 2), and only if that window has ≥ 500 road cells. Pawtuckaway is a state park.
  - It is undemonstrated whether a ½-cell error fails the gate.
- **Check (c)** uses ρ ≥ 0.5 with no calibration, which fails PA-0021(c); `ROUTE.md` §6 proposed 0.6 "to be set by the CR's committed script". Spearman is blind to feet versus metres and to 1-cell shifts. The `mch_mean` arm is conditional on a file being on disk.
- **GATE/OBS labels and class/subset/null fields are missing,** which PA-0021(d)/(f) require.

**Fix.**
- In `check_lidar_structure.py`, re-bin the pilot points with x + 30 m and x + 15 m and require (b) to FAIL on the 1-cell case. Record the ½-cell result.
- Use pilot-local windows, with stride and road-cell minimum stated as constants.
- Add an absolute-level row: the median of `lid_p95 − ch` in metres within a calibrated band, or the slope against `mch_mean`.
- Calibrate or demote (c).
- Label every row.

### A36-13 — MAJOR — Process (CR-0011 A3): the gate and test code are not committed, and thresholds are restated in prose
**Evidence.**
- CR §5 heading: "written before approval (CR-0011 A3)". Deliverable 1 lists both files, but neither is in the commit (§0).
- A3 says these are "reviewed as part of the CR" and that a statistical threshold must be referenced from "the committed script … rather than restate its numbers in prose".
- The CR restates `MIN_RHO_CH = 0.5` (CR:90), the 1% thresholds (CR:54 and CR:91) and `LIDAR_MIN_RETURNS` 50 (CR:49 and CR:81).

A12 and A9 cannot be fully reviewed without the code.

**Fix.** Commit `tests/test_cr0036.py` and `check_lidar_structure.py` before round 2, and reference their constants by name only.

### A36-14 — MEDIUM — The datum and PROJ operation are "pinned" in name only (the BUG-0095 root-cause class: an accuracy-relevant choice left to library defaults)
**Evidence.** CR:30 and CR:116 say "one pinned `pyproj.Transformer(always_xy=True)`". `from_crs(3857, template)` has four candidate operations, from null to a (+2, 0, −4) m Helmert, chosen per point. NAD83(2011) sources use NADCON5 when the grid is present, which conda's `proj-data` package or `PROJ_NETWORK` provide. So the EPT path and the native path can differ by about 1–2 m depending on the host. The magnitude is small (under 7% of a cell), but the "pinned / recorded" claim is false, and the two paths may be inconsistent.

**Fix.**
- Use `Transformer.from_pipeline(<explicit string>)` per source CRS, chosen to invert Entwine's own forward operation (null WGS84↔NAD83).
- Assert the pipeline string in a test, and include it in the cache key.

### A36-15 — MEDIUM — The static-feature list and registry edits target the wrong files and break a pinned test
**Evidence.**
- CR:72 says to add the features "to `RASTER_FEATURES` and to the static-feature list" under `models.py`. Neither list lives there.
- `STATIC_FEATURES` is at `generate_canopy_structure.py:73`, and `tests/test_cr0032.py:163` asserts `set(g.STATIC_FEATURES) == {"road_dist", *FEATS}`.
- A separate lid list would let a stale `lid_*` file keep a vintage alive in `vintage_years` (`generate_canopy_structure.py:71-72,175-177`), which is the exact hazard its comment names. That would duplicate a constant (PA-0001/PA-0025).
- `generate_time_since_disturbance.py:253` and `generate_road_distance.py:311` take years from all other features, including static ones.
- None of this is in Impact.

**Fix.** Use one shared `STATIC_FEATURES` in a shared module, update `test_cr0032`, and list these files in Impact.

### A36-16 — MEDIUM — Source selection is live, not pinned (PA-0048/PA-0020)
**Evidence.** Newest-wins is decided from the live WESM gpkg/csv (CR:16-17), which USGS updates. The WESM workunit ↔ EPT prefix mapping is unspecified: for example `NH_Coastal_1_2019` against `NH_Coastal_2019_B19`. The selected project set is an input of the accepted artifact.

**Fix.** Pin a WESM snapshot (date and sha256) and the `LIDAR_PROJECTS` list and mapping as constants, tied by a test to the check's copy. Changing it then requires an explicit edit.

### A36-17 — MEDIUM — A5 scope
**Evidence.** Deliverables span generator code, acceptance design, bookkeeping and registry edits to `FEATURE_SPEC`/`RASTER_FEATURES`. The registry edits are for features whose keep/remove decision is CR-0037's. The CR does not say why the parts cannot land separately.

**Fix.** Move the `FEATURE_SPEC`/`RASTER_FEATURES`/`STATIC_FEATURES` registration to CR-0037. Drop rockyweb (A36-1). State the A5 justification for keeping the generator and its checks together.

### A36-18 — LOW — A4 and factual hygiene
- Vintages are 2016–2025, not "2020–2025" (CR:57).
- The pad unit is ambiguous: 90 is in 3857 units, about 61–66 m on the ground (CR:23). `ROUTE.md` says 60 m.
- `LIDAR_MIN_RETURNS` appears twice (CR:49, CR:81).
- The leaf-on risk list (CR:112) omits `ME_MidCoast_2021` and `NH_Umbagog_2016`, which `ROUTE.md` §4 and `BANDWIDTH.md` §5.4 flag.
- The pilot cost of "$0.30" assumes the reader pays transfer. EPT is not requester-pays, and `BANDWIDTH.md` says the owner bears it, but NAT costs apply.
- A "synthetic rotated template" (CR:77) cannot mean a rotated Affine, because `grid_mismatch` rejects any rotation term (`grouse_data.py:202-203`). Clarify that the rotation is CRS-to-CRS.
- "Edges go to the higher cell" is ambiguous for rows, where e < 0.
- `~T·(x, y)` evaluates as `x·(1/a) − c/a`. That can floor an exact edge point into the lower cell. Compute `(x − c)/a` directly, or let the test tolerate it.

### A36-19 — LOW — Metadata and lint details
- The int16 return-count band caps at 32767. QL1 at 41 pts/m² gives about 36.9 k returns per cell, and overlap strips double that, so the band is routinely capped. Use int32 or uint16 plus a flag.
- Lint (§5.7) should also forbid thinning by other routes (`filters.sample`, `filters.voxel*`, `filters.decimation`) and `ignore_unreadable: true` (PA-0027 fail-closed).
- Pin `requests` per process with the total concurrency in mind: 192 workers × 16 is about 3 k in flight, which risks S3 SlowDown.

---

## 2. Summary table

| id | sev | summary |
|---|---|---|
| A36-1 | BLOCKING | Rockyweb/readers.las tiles are not in 3857 and may be in ftUS (H and V); the CR's only transform rule is from 3857 and no Z-unit rule exists |
| A36-2 | BLOCKING | Block-level and cell-level project assignment contradict each other; the block reading drops coverage near every newer-project boundary (for example NHGaps) |
| A36-3 | BLOCKING | The stale mask misses Y < A (VT 2023 → 2016–2022, ME 2024 → 2016–2023); vintage range misstated |
| A36-4 | MAJOR | Mask arithmetic: no rint (y = 3 → D = 2017.0012), D = A rule unspecified (use ≥), acquisition year for multi-year projects, tsd nodata |
| A36-5 | MAJOR | Static layer: unadmitted succession staleness and future data up to 10 y; stratify or mask in CR-0037 |
| A36-6 | MAJOR | Withheld is not in `Classification` under PDAL (ClassFlags/Withheld); bridge class 17 kept |
| A36-7 | MAJOR | p95 clipping violates PA-0034 and the mch precedent; lid_sd unbounded |
| A36-8 | MAJOR | Edge cases undefined (u1_3 empty denominator, zero first returns, ddof, percentile method, ground rule, partial-coverage cells) |
| A36-9 | MAJOR | Seam exactness needs pinned hag_nn max_distance ≤ pad and allow_extrapolation; the PDAL test is skipped here |
| A36-10 | MAJOR | 256² blocks hold 1.3–2.4 G points (50–145 GB); split needs a pre-read count; tile re-reads |
| A36-11 | MAJOR | Cache key lacks template grid, WESM and PROJ identity, so a block can be pasted on the wrong grid |
| A36-12 | MAJOR | Gates fail PA-0021: no broken-pipeline runs; (a) by construction; (b) not runnable on the pilot; (c) uncalibrated and unit-blind; no labels |
| A36-13 | MAJOR | A3: test and gate scripts not committed; thresholds restated in prose |
| A36-14 | MEDIUM | PROJ operation not truly pinned (4 candidate ops, grid-dependent); use from_pipeline |
| A36-15 | MEDIUM | Static list and registries are not in models.py; test_cr0032 pins STATIC_FEATURES; risk of a split list |
| A36-16 | MEDIUM | WESM/project selection is live and the mapping unspecified; pin per PA-0048 |
| A36-17 | MEDIUM | A5: registry edits and rockyweb belong in CR-0037; no stated justification for combining |
| A36-18 | LOW | Factual/A4 hygiene (vintages, pad units, duplicates, leaf-on list, rotated template, edge rule) |
| A36-19 | LOW | int16 return-count cap; lint gaps; request concurrency |
