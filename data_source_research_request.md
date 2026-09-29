# Research request: geospatial data sources for a 30 m habitat-suitability CNN

**How to use this file:** paste it whole into a Claude chat that has web access.
It is written to be self-contained — the answering model has no other context.

---

## Answering instructions (please follow these strictly)

1. **Cite a URL for every factual claim.** Not a search-result title — the page
   you actually read.
2. **Say "could not verify" explicitly** when you could not open a page or find
   an answer. A gap is useful; a plausible-sounding guess is worse than useless
   here, because it will be acted on.
3. **Mark anything answered from training memory rather than a fetched page**,
   e.g. `[from memory, unverified]`. Several past decisions on this project were
   derailed by confident answers that turned out to be recalled rather than read.
4. **Do not infer a URL pattern from a single example.** If you report a
   download-URL template, confirm it against at least two different
   attributes/years and say which two you checked.
5. Answer in the numbered order below. Skip nothing — write "could not verify"
   rather than omitting a question.
6. Where a question asks for exact strings (service names, field names, file
   names), reproduce them **verbatim**, including case and underscores. Do not
   normalize or tidy them.
7. Prefer primary sources (agency metadata, FGDC/ISO XML, REST service JSON,
   DOI landing pages) over blog posts and tutorials.

---

## Project context (enough to answer well; no more)

A convolutional neural network predicts ruffed grouse (*Bonasa umbellus*)
habitat suitability for **Maine, New Hampshire and Vermont**. Presence points
come from eBird/GBIF; predictors are stacked 30 m rasters read as 64x64 pixel
patches centred on each point.

**Current predictor stack** (one raster per feature *per year*):

| Feature | Source | Type |
|---|---|---|
| `evt` Existing Vegetation Type | LANDFIRE | categorical |
| `evh` Existing Vegetation Height | LANDFIRE | categorical |
| `evc` Existing Vegetation Cover | LANDFIRE | categorical |
| `sclass` Succession Class | LANDFIRE | categorical |
| `fdist` Fuel Disturbance | LANDFIRE | categorical |
| `ch` Forest Canopy Height | LANDFIRE | continuous |
| `cc` Forest Canopy Cover | LANDFIRE | continuous |
| `slope`, `gradient` (aspect) | LANDFIRE | continuous (treated as static) |
| `tcc` USFS Tree Canopy Cover | Earth Engine | continuous |
| `nlcd` Annual NLCD land cover | Earth Engine | categorical |
| `road_dist` distance to nearest paved road | TIGER/Line, self-generated | continuous |

**Four constraints that decide whether a dataset is usable at all:**

- **A. Multi-vintage is mandatory.** Each sighting is matched to raster vintages
  within **±2 years** of the sighting date, and the record is discarded unless
  **every** feature in the stack has a vintage within ±2 years. A single-vintage
  dataset therefore does not merely add nothing — it *deletes* every training
  record more than 2 years from its one vintage. Please always report the
  **complete list of available vintage years** for any dataset you describe.
- **B. 30 m or finer**, and ideally on or alignable to the LANDFIRE CONUS grid
  (NAD83 / Albers Equal Area, standard parallels 29.5 / 45.5, central meridian
  −96, latitude of origin 23.0).
- **C. Programmatic bulk download**, no interactive portal, no login, ideally no
  API key. Existing downloaders use plain HTTPS against USGS/USFS endpoints.
- **D. Free and redistributable-ish** (public domain / open licence).

---

# TIER 1 — Archived pre-2022 LANDFIRE (highest priority)

**Why this matters most:** sightings from **2016–2019** are currently discarded
(~1,571 positive records, ~23.5% of the presence data) because the project only
holds LANDFIRE vintages 2022, 2023, 2024 and 2025. The LANDFIRE Product Service
(LFPS) **job API** retired its pre-2022 products in December 2025, which is why
they were never downloaded. Recovering a 2016 and a 2020 vintage would restore
those records **without changing the model's input geometry** — by far the
cheapest available improvement. Everything else in this document is secondary
to answering Tier 1 well.

### 1.1 — Which pre-2022 versions are still served?
Fetch `https://lfps.usgs.gov/arcgis/rest/services?f=pjson` and list **every
folder name verbatim**. I specifically need to know whether folders exist for:
- LF 2.0.0 / "2016 Remap" (expected name something like `Landfire_LF200`)
- LF 2.1.0 / 2019
- LF 2.2.0 / 2020
State the exact folder names found. If a folder I named does not exist, say so.

### 1.2 — Which layers are in each pre-2022 folder?
For each pre-2022 folder found in 1.1, fetch
`https://lfps.usgs.gov/arcgis/rest/services/<FOLDER>?f=pjson` and list **every
CONUS service name verbatim** (these begin `US_`, e.g. `US_200EVT`,
`US_200FVT_20` — note the trailing version/date suffixes, reproduce them).

Then answer, per version, **yes/no for each**: is there a service for
**EVT, EVC, EVH, SClass, CH (canopy height), CC (canopy cover), FDist (fuel
disturbance)**?

This is the decisive question. Because of constraint A, missing even one of
those seven for a given vintage makes that whole vintage worthless to us.

### 1.3 — Can those services be clipped programmatically?
For one representative service (e.g. the 2016 EVT one), fetch its ImageServer
JSON and report:
- Does it expose the `exportImage` operation? Does it require authentication or
  a token?
- The values of `maxImageWidth` / `maxImageHeight`.
- `pixelType`, `bandCount`, `extent`, `spatialReference.wkid` (or the WKT).
- Whether `exportImage` accepts `bboxSR=4326` and `format=tiff`.

Context for the tiling answer: Maine at 30 m is roughly 20,000 × 25,000 pixels,
so I need to know how many tiles a statewide clip implies.

### 1.4 — Raw class codes or rendered colours?
When `exportImage` is called with `format=tiff&f=image` on a **categorical**
LANDFIRE layer (EVT, SClass, FDist), does it return the **raw integer class
codes**, or an RGB rendering of the symbology? If rendered by default, what
parameter (`renderingRule`, `noDataInterpretation`, `adjustAspectRatio`, a
`format=lerc`, …) returns raw values? **If these services only return symbolised
imagery, they are unusable for this project and I need to know immediately.**

### 1.5 — Full-extent downloads as a fallback
From `https://landfire.gov/data/FullExtentDownloads` (and the LF 2016 Remap
page `https://www.landfire.gov/data/lf2016`):
- The **direct download URL** and file size for CONUS LF 2016 Remap.
- The **complete list of layers inside that archive.** Does it contain SClass,
  CH, CC and FDist, or only a core vegetation subset (EVT/EVC/EVH)?
- Whether an equivalent full-extent download exists for **LF 2020**, and if so
  its URL, size and layer list.

### 1.6 — Is FDist comparable across LANDFIRE versions?
LANDFIRE Fuel Disturbance codes encode disturbance type, severity and
time-since-disturbance as a composite integer.
- What FDist products exist for the 2016 and 2020 vintages (exact product
  names)?
- **Is the code scheme identical to LF 2022 / 2023 FDist?** If the code space
  or the composite encoding changed between versions, say so explicitly and
  describe the change. Mixing two incompatible code schemes into one categorical
  channel would silently teach the model to identify the vintage rather than the
  habitat — so this is a go/no-go question, not a detail.
- Same question for **SClass**: did the succession-class definition or code set
  change between LF 2.0.0 and LF 2.3.0?

### 1.7 — Mirrors with bulk access
Is pre-2022 LANDFIRE mirrored anywhere with programmatic bulk access?
Check at minimum: **Google Earth Engine public catalog, AWS Open Data Registry,
Microsoft Planetary Computer, USGS ScienceBase, USFS Data Archive.**

For Google Earth Engine specifically: list the **exact asset IDs** of every
LANDFIRE collection in the public catalog, and state which LANDFIRE version and
year each corresponds to. (I am aware of `LANDFIRE/Vegetation/EVT/v1_4_0`-style
IDs; I need the full current list and their version mapping, including whether
any LF Remap 2016 or LF 2020 assets exist.)

### 1.8 — Grid continuity across versions
Did the LANDFIRE CONUS grid change between LF 2.0.0 (2016) and LF 2.3.0+ (2022)?
Same projection, same extent, same pixel origin, same 30 m cell size? If the
grids differ even by a sub-pixel offset, vintages must be resampled to align
before they can be stacked as time steps of one feature.

---

# TIER 2 — USFS TreeMap

TreeMap imputes a best-matching FIA plot to every forested 30 m pixel. Vintages
2016, 2020, 2022, 2023. Product pages:
- https://data.fs.usda.gov/geodata/rastergateway/treemap/index.php
- 2016: https://doi.org/10.2737/RDS-2021-0074
- 2020: https://doi.org/10.2737/RDS-2025-0031
- 2022: https://doi.org/10.2737/RDS-2025-0032
- 2023: https://doi.org/10.2737/RDS-2026-0038

Intended use: add **BALIVE** (basal area), **TPA_LIVE** (stems/acre), **QMD**
(quadratic mean diameter) and **CARBON_DWN** (down dead carbon) — attributes
LANDFIRE does not carry. Not to replace anything.

### 2.1 — Scriptable download URLs
Give **working direct download URLs** for the per-attribute rasters. Provide a
concrete example for **BALIVE** and for **TPA_LIVE**, for both the **2016** and
the **2022** vintage (four URLs). Is there a predictable URL template suitable
for a download script, or is the rastergateway form-POST only? Per instruction
4, confirm any template against at least two attributes and say which.

### 2.2 — Per-attribute raster form and size
Is each per-attribute download a single CONUS-wide GeoTIFF? Give the compressed
download size and the uncompressed GeoTIFF size for one representative
continuous attribute. Is there any per-state or per-region subsetting offered?

### 2.3 — The tree-list CSV
`TreeMap{year}_CONUS_Tree_Table.csv` (one row per tree per imputed plot) is the
highest-value part of this dataset for us — it permits per-species and
per-diameter-class stem counts that no published raster isolates.
- Is it downloadable **separately**, or only inside the full RDS zip (~4.5 GB)?
- Direct URL, file size and approximate row count, for each of 2016, 2020, 2022,
  2023.

### 2.4 — The raster attribute table
How is the RAT distributed — an ArcGIS `.tif.vat.dbf` beside the GeoTIFF, a
standalone CSV, or embedded in the GeoTIFF? Give the exact filename(s). Confirm
whether `PLT_CN` is stored as text (it is reported to corrupt if cast to
numeric) and whether the `Count` field (pixels-per-plot) is present.

### 2.5 — Grid alignment with LANDFIRE
Report TreeMap's exact CRS (full WKT if available) and geotransform — origin X,
origin Y, pixel size. **Does it align pixel-for-pixel with the LANDFIRE CONUS
grid**, or is there an offset? This decides whether ingestion is a clip or a
resample. Please answer from actual metadata, not from "both are NAD83 Albers"
— that is necessary but not sufficient.

### 2.6 — NoData
TreeMap NoData is reported as `4.2949673e+09` (R's default), which GDAL
reportedly will not auto-detect.
- Is that the actual stored value on the attribute rasters?
- What is the pixel type (Float32 / UInt32 / Int32)?
- Is NoData declared in the **GeoTIFF header**, or only in the sidecar metadata?
- Does the value differ between the 2016 vintage and the 2020+ vintages?

### 2.7 — 2016 attribute availability
Confirm or correct the following for **TreeMap 2016** specifically:
- `QMD` and `SDIsum` are **absent**; the 2016 analogues are `QMD_RMRS` and
  `SDIPCT_RMRS`.
- `SDIPCT_RMRS` is *percent of maximum SDI*, while `SDIsum` is an *absolute*
  sum — i.e. not interchangeable.
- `QMD_RMRS` — what exactly is its definition and unit, and is it numerically
  comparable to the 2020+ `QMD` (inches)?
- `BALIVE` and `TPA_LIVE` **are** available for 2016 (needed, because we intend
  to reconstruct 2016 QMD from them via QMD = sqrt(BALIVE / (0.005454 ×
  TPA_LIVE)) rather than use `QMD_RMRS`).

### 2.8 — Pre-derived stand-structure products
Has anyone already published TreeMap-derived rasters of **small-stem density**
(stems 1–5 in DBH), **species-specific stems per acre** (especially *Populus
tremuloides* / *grandidentata*), or **diameter-distribution shape**? If such
products exist, we would rather download them than redo the tree-table
aggregation.

---

# TIER 3 — Other candidate datasets

For **each** dataset below, always report: (a) complete list of vintage years,
(b) native resolution, (c) CRS, (d) NoData value, (e) how to download it
programmatically, (f) total size for a ME/NH/VT subset or for CONUS if no
subsetting exists, (g) licence.

Constraint A is the usual killer here — a single-vintage dataset costs us
training records rather than adding information, so the vintage list is the
first thing I need for every one of these.

### 3.1 — FuelMap 2020 / 2022 (https://doi.org/10.2737/RDS-2026-0016)
Imputed litter, duff, fine woody debris and coarse woody debris loadings, same
imputation framework as TreeMap. Beyond (a)–(g): is CWD loading **measured**
from FIA down-woody-material transects or **modelled** from forest type? Is it
forested-pixels-only like TreeMap, or full extent? Only two vintages are listed
(2020, 2022) — confirm whether more exist or are planned.

### 3.2 — TreeMap-based SDI / SDImax / Relative Density
https://doi.org/10.5281/zenodo.19509367 (methodology:
https://doi.org/10.1038/s41597-025-06012-6). Which TreeMap vintages are covered?
Direct file URLs and sizes, licence.

### 3.3 — FIA database (FIADB) for ME, NH, VT
Joinable to TreeMap via `PLT_CN`. Wanted tables: `COND` (for `STDAGE`,
`DSTRBCD1-3`, `TRTCD1-3`, `TRTYR1-3`, `PHYSCLCD`, `SITECLCD`),
`P2VEG_SUBPLOT_SPP` (understory shrub/forb cover by height layer), `DWM_*`
(down woody material transects), `SEEDLING`.
- Direct bulk download URLs for per-state CSV and/or SQLite for ME, NH, VT.
- **What fraction of ME/NH/VT FIA plots actually carry `P2VEG_SUBPLOT_SPP`
  records?** Phase 2 vegetation is reportedly not collected on all plots, and if
  coverage is sparse this becomes an imputation on top of an imputation.
- Same coverage question for the `DWM_*` transect tables.
- Are plot coordinates public, fuzzed, or withheld? (Relevant to whether
  anything can be rasterized directly rather than only via TreeMap's `TM_ID`.)

### 3.4 — LCMS (USFS Landscape Change Monitoring System)
- Complete product list (Change, Land Cover, Land Use, and any others) with the
  full list of years for each.
- Is there a **"time since disturbance"** product as a distinct raster, or must
  it be derived by walking an annual change stack?
- Resolution, CRS, and bulk download mechanism (direct HTTPS? Earth Engine asset
  IDs? If EE, give the exact asset IDs).
- Does it cover the full 1985-present Landsat era, or a shorter window?

### 3.5 — FIA BIGMAP
https://data.fs.usda.gov/geodata/rastergateway/biomass/
- **Confirm the native resolution.** I have seen both 30 m and ~250 m claimed
  and I need this settled from primary metadata.
- What vintage(s)? **Is it a single snapshot or a time series?** (Single-vintage
  would disqualify it under constraint A.)
- Species list and units (biomass? basal area? both?).
- Download mechanism and CRS.

### 3.6 — National Wetlands Inventory
TreeMap is NoData on non-forest, so wetland/shrub openings need their own
source. Specifically wanted: **alder swales and shrub wetlands**, which are
documented ruffed grouse cover.
- Bulk download for ME, NH, VT — vector or raster, direct URLs.
- **Per-state imagery vintage** (NWI source imagery age varies enormously by
  state, and a 1980s-vintage polygon set is a different proposition from a
  recent one). Is it versioned/updated on any schedule, or effectively static?
- Which **Cowardin classification codes** correspond to alder / shrub-scrub
  wetland?

---

# TIER 4 — Open-ended search

### 4.1 — What are we missing?
Identify free, 30 m-or-finer, **multi-vintage**, programmatically downloadable
rasters covering New England that are **not** derived from LANDFIRE
EVT/EVC/EVH and **not** another Landsat land-cover classification. We already
have the stack listed in the context section, so anything that is essentially a
re-derivation of it is of no interest.

Genuinely useful directions, roughly in order of interest:
- soil moisture / topographic wetness / hydric soil (SSURGO-derived rasters?)
- snow depth or snow-season duration (grouse use snow roosts)
- growing-season phenology metrics (green-up date, season length)
- forest ownership and parcelization (small private parcels → different harvest
  regimes → different age-class structure)
- historical land use / time since agricultural abandonment

### 4.2 — Timber harvest specifically
Is there a national or Northeast-regional, multi-year, 30 m **timber harvest**
layer that is distinct from LANDFIRE disturbance and LCMS change? Early
successional habitat in this region is largely harvest-created, so a harvest
layer with a date would be high value. Name it, or state clearly that none
exists.

### 4.3 — Forest stand age
Is there a national **forest age / stand age** raster at 30 m with **more than
one vintage**? (I am aware of single-vintage forest-age products; under
constraint A a single vintage is actively harmful, so please report the vintage
count explicitly rather than just naming the product.)

### 4.4 — Catalogue check
https://geospatialcatalog.com/ was suggested as an aggregator. Is it a useful
index for this kind of search, and does it surface anything relevant to 4.1–4.3
that is not already named in this document?

---

## Finally

If any question above rests on a **false premise** — a product that does not
exist, a URL pattern that is wrong, a constraint I have misunderstood — say so
plainly rather than answering around it. That is more valuable than a complete-
looking set of answers.
