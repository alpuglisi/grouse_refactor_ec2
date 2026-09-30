# CR-0006: Partition records by state, split train/val once globally, rebuild every defective raster, and retrain once

**Status: SUPERSEDED (2026-09-30) — split into CR-0007, CR-0008 and
CR-0009. Not implemented. Retained per `CLAUDE.md`: IDs are never reused
or renumbered.**

Why it was split: this CR reached revision 3 and was reviewed five
times, producing over 100 concerns. Both reviewers who came to v3 cold
returned REJECT. The record-partition design in it survived every attack
across all five reviews; its acceptance criteria failed three times in
three different ways, and its raster half carried two spec defects that
would have corrupted four channels. Two reviewers independently traced a
concrete defect to the bundling itself — the attribution argument
existed only because one retrain spanned both halves, and it was
anchored on the coverage reference the other half forbade.

The successors:
- **CR-0007** — record partition and global train/val split (BUG-0027,
  BUG-0029).
- **CR-0008** — raster coverage nodata (BUG-0023 ME/VT, BUG-0024,
  BUG-0025, BUG-0030).
- **CR-0009** — the single retrain, the disk plan, and the end-to-end
  re-measurement of the reported map symptom.

Everything below is the v3 text as reviewed, kept unchanged as the
record of what was proposed and what the five reviews found. Its
§ Review section holds the dispositions for all 62 round-1 and round-2
concerns; the round-3 concerns are carried into the successor CRs.

---

# CR-0006: Partition records by state, split train/val once globally, rebuild every defective raster, and retrain once

**Status: REVISED (v3) after three independent reviews — awaiting
re-review.** v2 was returned APPROVE WITH CHANGES / APPROVE WITH CHANGES
/ **REJECT**, with 8 blocking concerns. Nothing has been committed.

**This document is self-contained.** v2's Impact, Risk and Deliverables
sections incorporated "v1's list" by reference while v1's text was not in
the file, which silently reinstated four retracted items — including the
acceptance criterion the revision existed to remove (A-R2-2, blocking).
No section below references a version that is not present here.

## Revision note (v2 → v3)
The third reviewer recommended **splitting this into three CRs**. The
user has decided to hold it as one. That decision is recorded here
because it is the reason the document is long: the partition work
survived every attack all three reviewers made, while the raster work
needed two blocking spec defects repaired, and both now travel together.

Material changes in v3:

1. **The acceptance invariants are replaced again** (blocking: A-R2-1,
   B-§4, C-3). v2's set passed on pipelines that violate this CR's own
   requirements — twice over, for two independent reasons. The new set
   is measured to fail today and pass after (§ Acceptance).
2. **The raster specs are rewritten** (blocking: B-N1/N2, C-1/C-2). v2's
   one-line specs were, read literally, destructive: they would have
   nodata'd legitimate in-CONUS non-forest across four channels.
   `generate_treemap_features.py` — which v2 never mentioned and which
   owns the 7.6 GB the model actually reads — is now in scope.
3. **"Outside coverage" is given one explicit definition** (blocking:
   C-4). v2 used LANDFIRE `evt` nodata, which is wrong (32.8 % of
   evt-*valid* ME pixels are outside the US) and **vacuous for VT**
   (VT's evt nodata fraction is 0.0000).
4. **A domain decision is posed rather than assumed** (§ Decision
   required): is `balive == 0` a reading or a gap? v2 assumed an answer
   implicitly. It blocks step 4 only.
5. **The disk plan is reordered and completed** (C-11, B-C7): the cache
   purge moves *before* the raster step, and the ~9.9 GB of rasters
   step 4 destroys are added to the backup.
6. **§1's justification is corrected** — it was factually wrong, and the
   correction exposes a real sequencing hazard (B-N4, C-7).
7. **BUG-0031's premise is withdrawn** (C-14). v2 claimed PA-0014's
   sweep record was wrong. It is not; the files are executably
   identical, exactly as PA-0014 said.

### Where v2's author was wrong, recorded
`CLAUDE.md` §1.3 requires verifying a reviewer's claim before applying
it. It cuts both ways, and three v2 claims failed that test:
- **"`regions.py` is imported by `predict.py`, `download_rev.py`,
  `download_treemap.py`, `download_tcc_nlcd.py`"** — false. Only
  `download_rev.py:22` imports `regions`. `predict.py:91`,
  `download_treemap.py:110`, `download_tcc_nlcd.py:73` and
  `diagnose_road_bias.py:68` do `from prepare_training_data import
  BOXES`. Asserted without checking, in the section justifying a design
  change (§1).
- **"`legacy/gen_negs.py` differs by 7 non-comment lines"** — false, and
  two reviewers confirmed it using the same flawed method (`grep -v
  '^\s*#'`, which strips `#` comments but not docstrings). AST-normalised
  diff: `legacy/gen_negs.py` vs `generate_negatives.py` = **0** executable
  diff lines; `clean.py` vs `prepare_training_data.py` = **0**;
  `legacy/audit.py` vs `analyze_grouse.py` = **2** (a literal moved to a
  shared import). Three agreeing checks meant nothing because all three
  shared a method error.
- **§8's availability figures** were the raw box sample;
  `background_envelope_sample` applies `dropna` and a non-veg drop
  first. Corrected in §8.

## Scope
Fix BUG-0027 (cross-region train/val leakage) and BUG-0029 (mismatched
positive/negative spatial support) by making region membership a **state
partition** and running the spatial block holdout **once over the pooled
records**; regenerate every raster that writes a legitimate-looking value
where its source has no coverage (BUG-0023 ME/VT, BUG-0024 `tsd`,
BUG-0025 TreeMap, BUG-0030 `tcc`); add dataset-build assertions that make
these classes detectable; retrain once.

## Why now
Unchanged from v2 and not repeated at length: five confirmed defects
share one root mistake — writing or selecting data for an extent the
source does not cover — and all five invalidate the same artifacts.
Confirmed magnitudes: **522 of 1,674 pooled validation positives (31.2 %)
are also pooled training positives at the identical coordinate**
(reproduced independently by all three reviewers); 1,128 of the NH
region's 2,244 positives lie outside New Hampshire against **1** of 2,244
negatives; `road_dist` median error on the Maine side of the NH grid
**16,086 m before `bf8d31a`, 10 m after** (reviewer A, 400 ground-truthed
points).

**Corrected fabricated-value figures.** v2 reported these against evt
nodata. Against the correct reference (§ Coverage) the fabricated area is
roughly twice as large — about **47 %** of the ME grid, consistent with
the independently measured 47.1 % NODATA that regenerating ME
`road_dist` produces. Over that area `tsd` reads a constant 3434
("undisturbed 30 years"), `balive`/`tpa_live`/`qmd`/`carbon_dwn` read 0
("non-forest"), `tcc` reads 0, and ME `road_dist` reads a saturated
10820. `nlcd` is correct there — but only incidentally (§9.3).

**One thing is better than v2 claimed** (B-N5): **0 of 6,702 training
records have a single nodata `evt` pixel anywhere in their 64×64
window.** If § Decision resolves to "coverage = product footprint", the
six regenerations change **no training input at all**, and the retrain's
metric movement is attributable to the split/membership change alone.
That converts v2's hand-waved attribution risk into a measured one.

## § Decision — RESOLVED (user, 2026-09-30)

**Branch A. `balive == 0` is a reading, not a gap.** In-CONUS non-forest
stays `0`; only outside-US becomes nodata. **TIGER vintage: 2023.**
Both are settled; nothing in §8 or §9 is blocked on a further answer.

The question, and the evidence it was decided on:

TreeMap's Earth Engine mask is *non-forest ∪ outside-CONUS* — one mask,
not two (`download_treemap.py:58,64,293`: "NON-FOREST: unmask(0) AT
DOWNLOAD TIME, NOT LEFT AS A SENTINEL"). So "stop filling outside
coverage" cannot be implemented without saying which zeros are data:

```
balive == 0, share of the evt-valid grid:      ME 50.2%  NH 30.4%  VT 29.2%
  ... of those ME zeros, inside the US:        35%   (~17.6% of the evt-valid grid)
balive == 0 at the CENTRE pixel of a record:   ME 25.4%  NH 26.3%  VT 25.3%
tcc == 0, share of the evt-valid grid:         ME 40.1%  NH 12.5%  VT  7.2%
```

- **Branch A — coverage = product footprint. CHOSEN.** In-CONUS
  non-forest stays `0`; only outside-US becomes nodata. Preserves
  `generate_treemap_features.py`'s documented contract (`:157-161`,
  "qmd=0 AND tpa_live=0 is exactly the non-forest signature, so the joint
  pattern carries forest/non-forest without a mask channel"), and changes
  **no training patch** (B-N5). Fixes the defect where it actually is.
- **Branch B — `0` is not a reading.** In-CONUS non-forest also becomes
  nodata. ~25 % of every training patch's centre pixel in four channels
  flips to `MISSING_CODE`, the retrain is no longer attributable to the
  split change, and `generate_treemap_features.py`'s design is
  invalidated. This is a modelling change and arguably needs its own CR.

**Consequence of Branch A, and an open implementation question for
round 3.** Because Branch A keeps the in-CONUS `0` and only needs
out-of-US pixels marked nodata, the correction may not require an Earth
Engine re-export at all: the reference mask (§ Coverage) is NLCD's valid
footprint, and per-region NLCD rasters are already on disk on the same
grid. Post-processing the existing TreeMap and `tcc` rasters against that
mask would avoid the 6.6 GB `data/treemap_raw` re-fetch and the GCP
dependency entirely. **This is not asserted as settled** — it is offered
to round 3 to validate or reject, and § Disk below still budgets the
Earth Engine path as the fallback. Under Branch B no such shortcut
exists, which is a further argument for A.

Branch A also preserves the attribution argument: it changes **no
training patch**, so the retrain's metric movement is attributable to the
split/membership change alone.

## Coverage: one definition, used everywhere
(blocking: C-4.) "Outside coverage" means **outside the US land
footprint**, and the reference mask is **NLCD's valid footprint** —
verified to be exactly that: of sampled ME-grid points, `evt valid &
nlcd valid` is 100 % inside the US and `evt valid & nlcd NODATA` is
0.0 % inside the US. The TIGER county union is an acceptable equivalent.

**LANDFIRE `evt` nodata is NOT the reference.** 32.8 % of evt-*valid*
ME pixels lie outside the US, and VT's evt nodata fraction is **0.0000**,
so any check anchored on it is both under-inclusive and, for VT,
vacuous. v2's acceptance gate
(`inv_verify_nodata_consistency.py`) is anchored on evt nodata **and
loops only `("ME","NH")`** — it never examined VT at all. Both are fixed.

## The change

### 1. `regions.py` — membership key, and the corrected justification
v1 proposed a TIGER-polygon `region_of()`. v2 replaced it with the
existing **`state` column** and justified that partly by a false claim
about the import chain (see Revision note). The design decision stands on
its true merits; the justification is restated:

- `state` is the partition key. For **positives** it is evidential, not
  circular: `analyze_grouse.load_all_sightings:167` reads it from the
  filename, those files come from `sightings.py:132`
  (`groupby(['stateProvince','year'])` over a GBIF export), so it is
  GBIF's per-record `stateProvince`. Verified: `state` == dissolved TIGER
  polygon for **43,024 of 43,024** records, and reviewer C measured
  **max distance-to-own-polygon 0.0 m** — not one record is near a
  boundary.
- For **negatives it IS circular** (C-9): `get_negatives.py:268` passes
  `stateProvince` as a *query parameter* and `generate_negatives.py:302`
  carries it into the column, so `state == region` is true by
  definition and carries no evidential weight. Two negatives contradict
  geography: one NH-filed at (−70.92538, 43.3258) whose polygon is ME,
  and one ME-filed at (−67.10082, 44.501766) outside all polygons. v2
  implied the partition verified both classes; it does not. Recorded,
  and the polygon check is run over the negatives (§ Acceptance).
- **The real coupling v2's false claim hid** (B-N4, C-7): `predict.py`,
  `download_treemap.py`, `download_tcc_nlcd.py` and
  `diagnose_road_bias.py` import `BOXES` from **`prepare_training_data`**
  — the module §3 restructures. Two of the raster generators step 4 must
  run, plus `predict.py`, depend on it. They are re-pointed at
  `regions`, and an **import-smoke gate runs between steps 3 and 4**.
- **`verify_partition()` becomes mandatory, not optional** (A, C-8). v2
  made it skippable when geopandas or the shapefile is absent — exactly
  the condition under which a new environment ingests new data — while
  the acceptance gate read "`state` == polygon for every record", so
  *not having run* satisfied the gate. It now runs in `analyze_grouse.py`,
  **fails** on disagreement, and requires an explicit
  `--skip-partition-verify` with a loud banner to bypass. Source named:
  `data/roads/tl_2023_us_county.zip` dissolved by `STATEFP`; the
  generalized `cb_*_20m` boundaries are explicitly forbidden (they
  generate false disagreements).
- An unknown `state` value is an **error**, not a silent 0-row drop: a
  `ma_sightings_2026.csv` matches the filename regex today and would
  vanish with only a printed count (A).
- **Centralised here** (PA-0001): `STATE_FIPS` (currently duplicated in
  `generate_road_distance.py:115` *and* `diagnose_road_bias.py:71`),
  `TIGER_YEAR` (**already drifted**: 2025 vs 2023 — C-10/C-16), and the
  30 m thinning constant (`prepare_training_data.py:49` vs
  `generate_negatives.py:71`), which §5 fuses and which therefore must
  not be able to drift.
- **`BOXES` is documented as raster-extent-only — and NH's is too small
  for membership** (C-15): the NH polygon reaches **−70.5751**, east of
  the box's −70.600, leaving **0.0299 %** of NH outside (ME and VT:
  0.0000 %). v2 resolved `regions.py`'s standing NOTE against the
  *sighting* extent (−70.71444), which is the wrong criterion now that
  membership is a state. The NOTE is re-resolved against polygon + patch
  margin, and whether to widen NH's box is called out for the reviewer.

### 2. `analyze_grouse.py` — partition, and consistent availability
- `clip_to_region` (`:198-203`) selects on `state == region`, writes an
  explicit `region` column, and calls `verify_partition()`.
- **§1-vs-§8 conflict resolved** (C-7): v2 justified its design partly by
  "removing geopandas from the import chain" while §8 required a
  polygon-based clip of the availability sample. Since that
  justification was false anyway, the conflict resolves cleanly:
  **geopandas becomes a declared dependency of the analysis/dataset-build
  path** (not of `predict.py` or the downloaders, which are re-pointed at
  `regions` in §1). An optional clip is not acceptable here, because §8
  exists precisely because the bias it fixes is invisible.
- `background_envelope_sample` (`:411`), `background_nonveg_rate`
  (`:324`) and the KDE fit set are clipped to the partition.
  **Corrected figures** (A-R2-3): v2 quoted the raw box sample. After the
  `dropna` and non-veg drop those functions actually apply, the in-state
  share is **ME 95.9 %, NH 53.2 %, VT 55.2 %** — so the Selection_Ratio
  bias is severe for NH and VT and near-nil for ME. The fix stands; the
  evidence is restated. That asymmetry matters because Selection_Ratio
  drives per-region negative weighting.

### 3. `prepare_training_data.py` — one global grid, one draw
As v2: global EPSG:5070 origin, `box` leaves `assign_spatial_blocks`
(`:85-114`), `main()` pools → dedups (a guard, not a benefit) → **thins
once** → assigns and draws once → writes per-region files plus one global
`block_assignments.csv`. `--regions` subset runs become diagnostic-only
and refuse to write. Dead `--habitat-only` (`:133`) and dead `rng`
(`:102`) removed.

**Expected pooled positive count: ~6,230** (A). v2 called reviewer A's
~6,230 and reviewer B's 6,508 a "bracket"; they are not (A-R2-5).
6,508 takes the habitat flag from whichever region's file happened to
say "habitat", but under the partition it must come from the record's
**own** state's grid — the grid that will supply its training patch — and
291 coordinates are habitat only in a foreign region's file. **Landing
near 6,508 is therefore a diagnostic that the habitat flag was taken
from the wrong grid.** Neither number is pass/fail (§ Acceptance).

### 4. Duplicate scripts — PA-0002, and BUG-0031's premise withdrawn
`clean.py`, `legacy/gen_negs.py` and `legacy/audit.py` are all
**executably identical** to their live counterparts (0 / 0 / 2 diff
lines, the 2 being a literal moved to a shared import). All three get
runtime `SystemExit` guards.

The hazard is real and unchanged: `legacy/gen_negs.py` writes the *same*
`data/negatives/*.csv` paths, reads `block_assignments` and computes
region-local ids. After this CR it would read the **global** file while
emitting **local** ids — the id ranges do not overlap at all, so 100 % of
candidates fall through to hash splitting, **silently reintroducing
BUG-0027's leakage into the files `train.py` reads, with no error.**

**But v2's framing was wrong** (C-14). PA-0014's sweep record said those
pairs are "content-identical" — **that is correct.** Its actual failure
is an **omission**: `legacy/audit.py` vs `analyze_grouse.py` was never
listed as a pair at all, despite sharing
`evaluated_sightings_*.csv`/`envelope_metrics_*.csv`. And the governing
rule is **PA-0002** (a stale runnable copy that will diverge *because of
this CR*), not PA-0014. BUG-0031 is rewritten accordingly; v2's version
would have put a fabricated quote in a bug doc, against `CLAUDE.md` §2.4.

### 5. `generate_negatives.py`
Global block ids (`compute_block_ids`, `:98-107`, loses `box`); reads the
global `block_assignments.csv`; **300 m buffer queries pooled** grouse
locations; **thinning pooled**. `--regions` gets the same write-guard as
§3 (C-13) — with a pooled buffer and pooled thinning, a subset run is
itself the per-region-subset spatial computation PA-0018 forbids.
**`:153`'s bare `except Exception` is narrowed to re-raise
`MissingDataError`** (B): it is what turns a half-finished rebuild into
"Skipping" over stale negatives, and it is a live PA-0011 instance.

### 6. `train.py` — assertions
v2's 5 pp class-composition threshold is replaced. It was **looser than a
defect it must catch**: ME today has 137 out-of-state positives against 0
out-of-state negatives and scores **3.55 pp — it passes** (C-5). It was
also under-specified across four admissible readings, two of which never
fire and one of which fails the wrong way (C-6).

- **(a) Exact partition assertion:** every positive and every negative in
  region R has `state == R`. Exact, cheap, no threshold, no geopandas.
- **(b) Polygon share comparison**, strict (≤0.5 pp), per region, keys =
  union of both classes' with zero fill. Uses the polygon, so it has real
  power (≤0.04 pp after) rather than being a tautology on the column.
- **(c) Per-region occupied-block support**, 30 km, pos-only fraction,
  **threshold 0.035**. Reviewer A proposed ≤0.05; measured, defective ME
  is **0.048** and would pass, so 0.05 is wrong. The usable window is
  0.026 (max after) to 0.048 (min before).
- **The check must be per-region. Pooled is provably inert** — measured
  identical before and after at every block size (30 km: 0.927/0.927
  Jaccard, 0.011/0.011 pos-only), because the partition relabels records
  without moving any. This resolves a direct contradiction between
  reviewers A and B, who measured per-region and pooled respectively.
- **Placement** (B-C2, B-N6): all assertions run pooled and **before**
  `filter_by_year_gap`, which drops 22–24 % of positives and **0 %** of
  negatives and would otherwise guarantee divergence on correct data.
  `build_datasets` (`train.py:253-315`) is currently a single per-region
  loop calling `filter_by_year_gap` at the top of each iteration, so this
  **requires splitting it into a load pass and a construct pass**. The
  failing path must raise before any `GrousePatchDataset` is constructed.
- Three callers: `train.py:980`, `calibrate.py:351`,
  `bench_pipeline.py:95`.

### 7. `train.py` — `sample_background_points`
`:120-165` draws assumed-negatives uniformly over the region's **box**,
in any state — BUG-0029's mechanism inside the file this CR edits.
Dormant at the `--an-background 0.0` default (`:739`); brought under the
partition.

### 8. Raster regeneration
**All four defects confirmed on real files by two reviewers and the
author.** The specs, corrected:

- **9.1 `road_dist` (BUG-0023):** regenerate **ME and VT only**, at
  **TIGER 2023** (decided). `generate_road_distance.py` is already fixed
  and ground-truthed. **NH needs no regeneration** — it was rebuilt at
  2023 with the fixed code (`inv_regen_road_dist.log`), so the three
  regions end up on one vintage. `TIGER_YEAR` must be pinned to 2023 in
  `regions.py` (§1): it currently defaults to **2025** in
  `generate_road_distance.py:114` while `diagnose_road_bias.py:72` says
  2023 and every cached file is 2023, so a defaults run would silently
  mix vintages (C-10).
  **Download cost, measured** (`inv_verify_tiger2023.py`, using the
  script's own `counties_for_grid`): ME 23 counties (**0 uncached**),
  NH 31 (**0 uncached**), VT 34 (**8 uncached** — MA 25003, 25015 and
  NY 36019, 36031, 36083, 36091, 36113, 36115). The national county file
  is cached. So step 5 needs **8 county road files**, not the 52 a 2025
  run would re-fetch.
- **9.2 `tsd` (BUG-0024):** `:339` is `np.where(last >= 0, year - last,
  TSD_MAX_YEARS)`, conflating "no disturbance recorded" with "not
  covered". **Do not nodata where the max is currently written** —
  `tsd == TSD_MAX_YEARS` at 81–93 % of training centre pixels is
  legitimate saturation, and a naive implementation destroys the channel
  with no test that would notice (B-N2). Carry a boolean
  "any source tile covered this pixel" accumulator alongside `last` (the
  per-tile nodata is already read at `:313-314`; the source rasters carry
  `nodata=32767`, verified) and write nodata **only** where nothing
  covered it.
- **9.3 `tcc` (BUG-0030):** the fix **cannot** live at
  `download_tcc_nlcd.py:366` (`(arr>=lo)&(arr<=hi)` with `lo=0`), because
  18.4 % of tcc's zeros are real 0 % canopy inside the US. It must be an
  explicit `unmask(<sentinel outside valid_range>)` at the Earth Engine
  stage. **`nlcd` is correct only incidentally** — its `valid_range`
  starts at 11, so the mask's 0 is rejected by accident. v2 said "do not
  change it"; PA-0017 and `CLAUDE.md` §3.3 require fixing the
  **mechanism**, so both products get the explicit unmask (C-2).
- **9.4 TreeMap (BUG-0025):** gated on § Decision. Under Branch A, only
  outside-US becomes nodata; in-CONUS non-forest stays 0.
  **`generate_treemap_features.py` is in scope** (C-1) — v2 omitted it
  entirely although it owns the 7.6 GB of per-region rasters the model
  reads, and its `:257-260` (`a[a >= NODATA_FLOOR] = 0.0`) would pass a
  negative sentinel straight through into its encoders, manufacturing a
  *new* fabricated-value defect. `download_treemap.py` writes only
  `data/treemap_raw` (6.6 GB); the rasters come from
  `generate_treemap_features.py`, which must be re-run.

### 9. Retrain once, to a new path
From scratch, not `--resume`. `--save-path` must be a **new** file (its
default is `grouse_single_best.pth`, `train.py:436`). Refit calibration.

### 10. `bf8d31a` — retroactive coverage
All three reviewers re-derived it as correct. Two residuals fixed here
because step 4 re-runs it at scale: **`_download` (`:124-130`) has no
temp file, atomic rename or size check**, so an interrupted download
poisons the cache permanently (`if os.path.exists(path): return path`
never re-fetches a truncated zip) — and `verify_partition()` now depends
on that same cache, so this is a **hard ordering constraint, fixed
first**; and `counties_for_grid` reprojects an undensified footprint
(densification added; `pad_px` derived from the x resolution alone is
documented as safe only because every grid is 30 × 30 m).

## § Acceptance — invariants, measured
v2's invariant set was blocking-defective twice over: it passed on a
per-region-thinned pipeline (37 pairs under 30 m), and it was
**positives-only**, so the negatives' block holdout could be destroyed
entirely with every invariant green. Both holes are closed, and the set
is measured rather than asserted:

```
                                             CURRENT   COMPLIANT   require
I1  pooled positive pairs < 30 m                1690           0         0
I2  blocks holding train AND val, either class   882           0         0
I3  val negatives sharing a block with train    37.2%        0.0%        0%
I4  train/val coordinate collisions, per class   522           0         0
```

Every invariant fails today and passes on the compliant pipeline. I1 is
the only one that encodes PA-0018's pooled-thinning requirement; I2/I3
are the only ones that can see the negative side — the exact relapse
`legacy/gen_negs.py` and a partial rebuild would cause.

Also required:
- **Geometric membership** (restored; v2 dropped it exactly as membership
  became metadata-driven — B): every record inside its region's `BOXES`
  entry with a full 64×64 window in every feature raster it will be read
  from. 0-violation today, dependency-free, and the one check that does
  not trust the `state` column.
- **`verify_partition()` must have RUN**, over both classes, with its
  output recorded here. "Did not run" must not satisfy the gate.
- **Coverage, both directions** (B-N3, C-4): against the **NLCD valid
  footprint** (§ Coverage), for **all three regions**: no feature
  fabricates a value outside coverage, **and** no feature is nodata
  inside coverage where it was not before. v2 checked only the first
  direction — which is not the failure mode §8's rewrite risks.
- **0 training records with a nodata centre pixel** in any regenerated
  channel.
- Validation fraction 20 % ± 1 pp. The 300 m rate against a **recomputed**
  same-region baseline, not the frozen 1.4 % — ME 1.55 % and NH 1.56 %
  already exceed it, and re-anchoring the grid moves block edges.

Informational, never pass/fail: the expected pooled positive count
~6,230 (§3).

## Impact
- **Every existing checkpoint and every recorded metric** (~0.82 AUC /
  ~0.79 AP, the `0.811` rank) stops being comparable. Calibration must be
  refit.
- **Reassigned records change feature VALUES, not just membership.**
  **1,012 unique habitat positives** change region (v2 said "1,982
  positives" without stating the denominator — that is rows, not unique
  habitat coordinates; B-N7). Each moves to a different **local Albers
  grid**: across coordinates present in more than one region's file, the
  same ground point already disagrees on `evt` for 29.5 %, `evh` 36.3 %,
  `evc` 41.0 %, `nonveg_landcover` 12.2 %. So `envelope_metrics_*`,
  `bin_tuning_*`, `spatial_zone`/`env_zone`, the KDE surfaces and the
  negative weighting all change, and **the habitat filter's own output
  changes** — which is why no exact post-rebuild count is promised.
  Verified positive (B-N8): every reassigned record has a full 64×64
  window and a valid centre pixel for all 15 features in its new region.
- **ME `road_dist` becomes 47.1 % NODATA** (NH 9.8 %, VT 4.0 %). The ME
  *prediction map* loses that channel over nearly half its extent.
- **`predict.py` masks its output on `evt` alone** (`:332`; C-17). After
  §8, the ~33 % of the ME grid that is outside the US but has valid evt
  will still **render predictions from a degraded channel set** instead
  of being blanked. Given this CR exists because of a wrong ME map, the
  mask should become "any required channel missing". In scope.
- **Consumers** (all verified at `path:line`): `get_negatives.py:128`,
  `organize_project.py:70,73,104,107`, `tune.py:215`,
  `smoke_test_training.py`, `diagnose_training.py`,
  `diagnose_water_bias.py`, `diagnose_wetland.py`,
  `diagnose_road_bias.py`, `calibrate.py:351`, `bench_pipeline.py:95`,
  `generate_treemap_features.py`, plus `predict.py:91`,
  `download_treemap.py:110`, `download_tcc_nlcd.py:73` (the
  `prepare_training_data` import, §1).
- **Docs**: `ARCHITECTURE.md:59`, `grouse_data.py:20`, `PROJECT_TREE.md`,
  and the module docstrings of `prepare_training_data.py:22-28` and
  `generate_negatives.py:24,36`.
- `RegionData.block_assignments` moves to `GrouseData`. Nothing parses
  `block_id`, so no code depends on it being region-local. The patch
  cache invalidates correctly (`dataset.py:151-172`).

## Risk level: **HIGH**

| risk | mitigation |
|---|---|
| **Validation numbers will get worse, and that is correct.** Removing a 31 % leak removes inflation. | Stated in advance. The honest baseline is this CR's "after". **A lower metric is never a rollback trigger.** |
| §8 read literally destroys four channels. | **Resolved: Branch A** (user) — in-CONUS non-forest stays `0`, so no training patch changes. The two-direction coverage invariant catches over-masking regardless, which v2's gate could not see. |
| A naive `tsd` fix destroys 81–93 % of the channel. | §9.2 specifies the coverage accumulator; the inside-coverage invariant catches it. |
| An interrupted TIGER download poisons the cache permanently, and `verify_partition()` now depends on that cache. | §10 fixes `_download` atomicity **first**, as a hard ordering constraint. |
| A partial rebuild trains on stale negatives silently. | Narrowed exception at `generate_negatives.py:153` (a code fix, not a procedure), plus the all-or-nothing gate in § Disk. |
| Six channels change at once, so a bad retrain is hard to attribute. | Under Branch A, **measured to change no training input at all** (0 of 6,702 records have a nodata evt pixel in-window). Under Branch B, attribution is genuinely lost — which is an argument for Branch A. |
| TIGER vintage drift (2025 default vs 2023 on disk and in the shipped NH raster). | **Resolved: 2023** (user). Pinned in `regions.py` (§1); NH already matches, so no NH regeneration and only 8 county files to fetch (§9.1). |
| The rebuild is irreversible without a complete backup. | § Disk, reordered so a complete backup is affordable. |

## § Disk, backup and rollback
```
/                  150 GB total, 135 GB used, 16 GB FREE (90%)
data/cache          28 GB = 206 patches_*.npy + 1 orphan .tmp6337 (361.9 MiB)
rasters step 4 overwrites, NOT in v2's backup:
   tsd 148M  balive 1.9G  tpa_live 2.0G  qmd 1.9G  carbon_dwn 1.8G  tcc 1.3G = 9.05 GB
   + road_dist (ME+VT+NH) 698M                                    = 9.75 GB
checkpoints  *.pth + *.pth.resume = 1.09 GB, but 12 files = 1.35 GB
   (the glob misses grouse_single_best.pth.member0[.resume]; use *.pth*)
pipeline 24M + negatives 27M + calibration 108K
```

**v2's plan was wrong twice**: it omitted the 9.05 GB of non-`road_dist`
rasters step 4 destroys, so "rollback restores the pre-CR state exactly"
was **false** (recovering TreeMap needs Earth Engine, a GCP project and a
6.6 GB re-download); and with those included, its ordering left only
~5.1 GB free *during* the riskiest step.

**The cache purge moves first.** Every key dies the moment step 4 touches
a raster mtime (`_cache_key` hashes paths **and mtimes**), and nothing
between the purge and the retrain reads the cache — steps 4–6 sample
rasters and CSVs directly. Purging first makes a complete backup
affordable.

1. Delete the orphan `.tmp` (361.9 MiB).
2. **Purge `data/cache/` (28 GB).** Verified safe: 206 files, all
   `patches_*`, nothing else. (Note: this also discards `pretrain.py`'s
   patch cache; SSL re-pretraining would pay a rebuild.) → ~44 GB free.
3. Back up (~11.1 GB) to `pre_cr0006/`, verified by checksum:
   `data/pipeline/`, `data/negatives/`, `data/calibration/`, **every
   raster step 4 will touch**, and `*.pth*`. → ~33 GB free.
4. Fix `_download` atomicity (§10). Land code. Import-smoke gate (§1).
5. Answer § Decision. Regenerate rasters; re-run
   `generate_treemap_features.py`. Record the two-direction coverage
   table before proceeding.
6. Rebuild splits; run the § Acceptance invariants and the assertions.
7. Retrain to a **new** `--save-path`; refit calibration.

**Network for step 5**, with both decisions applied:
- **TIGER: 8 county road files** (VT's padded grid only; ME and NH are
  fully cached at 2023, national county file cached). A 2025 run would
  instead have re-fetched 52 unique counties plus the 83 MB national
  file — that alternative is now closed.
- **Earth Engine: budgeted, possibly avoidable.** The fallback path is
  GCP auth plus a 6.6 GB `data/treemap_raw` re-fetch and tcc ~1.3 GB.
  Under Branch A this may reduce to a local post-process against the
  NLCD footprint (§ Decision) — round 3 decides. § Disk's free-space
  arithmetic below assumes the **fallback** (worst case), so a cheaper
  outcome only creates headroom.

**Rollback:** restore the four trees from `pre_cr0006/`, purge the cache
again, `git checkout`. With step 3 complete this genuinely restores the
pre-CR state.

## Deliverables
- [x] **§ Decision answered: Branch A** (user, 2026-09-30) — in-CONUS
      non-forest stays `0`.
- [x] **TIGER vintage: 2023** (user, 2026-09-30) — matches NH; ME and VT
      only; 8 county files to fetch.
- [ ] Round 3 to rule on whether Branch A permits a local post-process
      instead of an Earth Engine re-export (§ Decision).
- [ ] `regions.py`: pin `TIGER_YEAR = 2023`; `state` membership; mandatory `verify_partition()`
      with named source and `--skip-partition-verify` escape; unknown
      state = error; centralise `STATE_FIPS`, `TIGER_YEAR`,
      `MIN_SPACING_M`; `BOXES` documented raster-only; NH NOTE
      re-resolved against polygon + margin (0.0299 % currently outside).
- [ ] Re-point `predict.py`, `download_treemap.py`,
      `download_tcc_nlcd.py`, `diagnose_road_bias.py` at `regions`.
- [ ] `analyze_grouse.py`: partition, `region` column, availability /
      nonveg / KDE clipped to the partition.
- [ ] `prepare_training_data.py`: global origin, pooled pipeline,
      `--regions` write-guard, dead flag and dead `rng` removed.
- [ ] Runtime guards on `clean.py`, `legacy/gen_negs.py`,
      `legacy/audit.py`.
- [ ] `generate_negatives.py`: global ids, global `block_assignments`,
      pooled buffer, pooled thinning, `--regions` guard, `:153` narrowed.
- [ ] `train.py`: `build_datasets` split into load and construct passes;
      assertions (a)(b)(c) pooled and pre-`filter_by_year_gap`;
      `sample_background_points` partitioned.
- [ ] `grouse_data.py`: `block_assignments` global on `GrouseData`;
      `PATH_TEMPLATES` updated.
- [ ] `predict.py`: validity mask on any required channel, not `evt`
      alone.
- [ ] `generate_road_distance.py`: atomic `_download`; densified
      footprint.
- [ ] `generate_time_since_disturbance.py`: coverage accumulator.
- [ ] `download_tcc_nlcd.py`: explicit EE `unmask` for tcc **and** nlcd.
- [ ] `download_treemap.py` + **`generate_treemap_features.py`**:
      Branch A — nodata only outside the NLCD footprint; in-CONUS
      non-forest stays `0`; `generate_treemap_features.py` re-run (or
      post-processed, pending the round-3 ruling).
- [ ] Rewrite `inv_verify_nodata_consistency.py`: NLCD-footprint
      reference, all three regions, **both** directions.
- [ ] All 14 consumers + 5 docs updated.
- [ ] § Disk executed in order, with checksums.
- [ ] § Acceptance invariants recorded; assertions demonstrated failing
      on current data and passing on rebuilt data.
- [ ] **User go-ahead for compute**, then retrain; refit calibration.
- [ ] Bug records: BUG-0030 (`tcc`) created; **BUG-0031 rewritten as
      PA-0014's omission of `legacy/audit.py`, under PA-0002**;
      BUG-0023/0024/0025/0027/0029 updated; BUG-0022 closed.
- [ ] `PREVENTIVE_ACTIONS.md`: PA-0020 + sweep (extended to acquisition
      queries, `sample_background_points`, and polygon vintage);
      PA-0017 Swept? updated with the `tcc` result and the corrected
      coverage reference; PA-0018 Swept? updated; PA-0014 Swept?
      corrected to record the **omission**; PA-0001 sweep re-run for
      `TIGER_YEAR` and `MIN_SPACING_M`.
- [ ] `CHANGELOG.md`: pre-CR metrics not comparable to post-CR.
- [ ] **Round-3 review**, with every new concern dispositioned.

## Out of scope
- **BUG-0028** (prediction outputs carry no provenance). PA-0019 is
  proposed there, which is why this CR adds PA-0020 and leaves a
  numbering gap.
- `scripts_backup/` holds an untracked pre-CR-0002 copy of
  `prepare_training_data.py` with the stale `-70.614` box. Untracked, so
  outside this CR, but it sits on the machine that runs step 5.
- The 24–41 % inter-region disagreement in categorical features at
  identical coordinates. Measured, not diagnosed; may be nearest-pixel
  grid offset or a BUG-0009-class alignment error. **Needs its own
  investigation.**
- Model architecture, loss, hyperparameters. Adding CI.
- **Splitting this CR into three** (recommended by reviewer C; the user
  decided to hold it as one — Revision note).

## § Review

### Round 1 (v1) and Round 2 (v2)
| | R1 | R2 |
|---|---|---|
| Reviewer A (diagnosis/data) | APPROVE WITH CHANGES (2 blocking, 19 total) | APPROVE WITH CHANGES (2 blocking) |
| Reviewer B (implementation) | APPROVE WITH CHANGES (3 blocking, 16 total) | APPROVE WITH CHANGES (2 blocking) |
| Reviewer C (fresh, cold, v2 only) | — | **REJECT** (4 blocking, 19 total) |

**Round-1 dispositions, all 35 concerns** (inlined; this document must
not reference a version that is not in it):

| # | Sev | Disposition |
|---|---|---|
| A-1, B-C1 | BLOCKING | Accepted — count criterion replaced by invariants (superseded again in v3). |
| A-2, B-C2 | BLOCKING | Accepted — 3 km support check abandoned (redefined again in v3 §6). |
| A-5, B-C3 | BLOCKING | Accepted — `legacy/gen_negs.py` + `legacy/audit.py` in scope (§4). |
| A-3 | MAJOR | Accepted — reassigned records change feature values (Impact). |
| A-4, B-C5, B-C16 | MAJOR | Accepted — ten consumers + docs enumerated (Impact). |
| A-6, B-C14 | MAJOR | Accepted — `sample_background_points` (§7). |
| A-7 | MAJOR | Accepted — pooled negative thinning (§5). |
| A-8, B-C8, B-C12 | MAJOR | Accepted, design changed — `state` key, polygon as assertion (§1). |
| A-9 | MAJOR | Accepted — ME 47.1 % NODATA (Impact). |
| A-10, B-item-6 | MAJOR | Accepted — BUG-0024/0025 pulled in; BUG-0030 created (§8). |
| B-C4 | MAJOR | Accepted — used-vs-available (§2). |
| B-C6 | MAJOR | Accepted — `--regions` write-guard (§3). |
| B-C7 | MAJOR | Accepted — § Disk created (reordered again in v3). |
| A-11, B-C10 | MINOR | Accepted — v1's buffer claim withdrawn; buffer pooled (§5). |
| A-12, B-C9 | MINOR | Accepted — pooling justification corrected (§3). |
| A-13 | MINOR | Accepted — dead `--habitat-only` and dead `rng` removed (§3). |
| A-14 | MINOR | **Partially rejected** — `compute_block_ids` `:98-107` corrected; `assign_spatial_blocks` `:85-114` upheld. A accepted the rejection in round 2. |
| A-15 | MINOR | Accepted — NH NOTE resolved (re-resolved in v3 §1 per C-15). |
| A-16 | MINOR | Accepted — `scripts_backup/` flagged (Out of scope). |
| A-17 | MINOR | Accepted — PA-0019 gap explained (Out of scope). |
| A-18 | MINOR | Accepted — PA-0018 enforcement row (Deliverables). |
| A-19, B-C15 | MINOR | Accepted — `_download` atomicity + densification (§10). |
| B-C11 | MINOR | Accepted — `STATE_FIPS` centralised (§1). |
| B-C13 | MINOR | Accepted — `block_assignments` on `GrouseData` (Impact). |
| B PA-0014 sweep | MAJOR | Accepted in v2 as "sweep record wrong" — **superseded in v3 by C-14**: the record was correct; its failure is an omission. |

**Round-2 dispositions, all 27 concerns:**

| # | Sev | Disposition |
|---|---|---|
| A-R2-1 | BLOCKING | **Accepted.** New invariant set, § Acceptance. Author reproduced the failure independently (37 pairs, all v2 invariants green). |
| A-R2-2 | BLOCKING | **Accepted.** Document made self-contained; verified by grep that all four retracted items were absent. |
| B-N1, C-1 | BLOCKING | **Accepted.** § Decision posed; `generate_treemap_features.py` in scope; §9.4. |
| B-N2 | BLOCKING | **Accepted.** §9.2 coverage accumulator + inside-coverage invariant. |
| C-2 | BLOCKING | **Accepted.** §9.3 moves the fix to the EE stage for **both** products; nlcd's correctness recorded as incidental. |
| C-3, B-§4 | BLOCKING | **Accepted.** I2/I3 added; measured 882 and 37.2 % today, 0 after. |
| C-4 | BLOCKING | **Accepted.** § Coverage; author verified VT's evt nodata = 0.0000 and that the v2 script looped only ("ME","NH"). |
| A-R2-3 | MAJOR | **Accepted.** §8 figures corrected to post-`dropna`. |
| A-R2-4, C-5, C-6 | MAJOR | **Accepted, threshold corrected.** A proposed ≤0.05; author measured defective ME at 0.048, which would pass. §6 uses 0.035, per-region, with the statistic and key-union specified. |
| A-R2-5 | MAJOR | **Accepted.** ~6,230 as the expectation; 6,508 reframed as a wrong-grid diagnostic. |
| B-N3 | MAJOR | **Accepted.** Two-direction coverage invariant. |
| B-N4, C-7 | MAJOR | **Accepted.** §1's false claim corrected; import-smoke gate; geopandas conflict resolved. |
| B-N5 | MAJOR | **Accepted.** Attribution argument replaced with the measurement. |
| B-N6 | MAJOR | **Accepted.** §6 requires splitting `build_datasets`; author verified the per-region loop at `:253-315`. |
| C-8 | MAJOR | **Accepted.** `verify_partition()` mandatory, source named, `cb_*_20m` forbidden, `_download` ordering hard. |
| C-9 | MAJOR | **Accepted.** §1 records that the key is evidential for positives and **definitional** for negatives, and names the two contradicting records. |
| C-10, C-16 | MAJOR/MINOR | **Accepted.** Author verified `TIGER_YEAR` 2025 vs 2023 drift and the duplicated 30 m constant; both centralised. |
| C-11, B-C7 | MAJOR | **Accepted.** Purge moved first; 9.75 GB of rasters added; `*.pth*`; "restores exactly" now true. |
| C-12 | MAJOR | **Accepted.** Earth Engine + 6.6 GB in § Disk. |
| C-13 | MAJOR | **Accepted.** §5 write-guard. |
| C-14 | MINOR (policy) | **Accepted.** Author AST-verified: 0/0/2 executable diff lines. BUG-0031's premise withdrawn and rewritten as PA-0014's *omission*, under PA-0002. v2's version would have quoted a divergence that does not exist. |
| C-15 | MINOR | **Accepted.** Author verified NH polygon −70.5751 vs box −70.600, 0.0299 % outside. NOTE re-resolved; box widening raised for the reviewer. |
| C-17 | MINOR | **Accepted.** `predict.py` mask in scope. |
| C-18 | MINOR | **Accepted.** Test items sequenced into § Disk. |
| C-19, A-R2-6..10 | MINOR | **Accepted.** 206+1 cache files; `{NH 1171}` removed as unsourced; 52 counties; nodata table re-referenced and per-region; `_cache_key` `:151-172`. |
| A-R2 on `state` design | — | **Accepted with strengthening** — A's three hardening requirements are in §1. |
| B-C8 "relocates the guarantee" | — | **Accepted.** Geometric invariant restored (§ Acceptance). |

**Reviewer A's round-1 A-14 remains correctly rejected**, and A accepted
the rejection in round 2 after re-checking: `assign_spatial_blocks` ends
at `:114`.

### Round 3 — **not yet performed**
Eight blocking concerns were raised against v2 and the raster half was
rewritten. Per `CLAUDE.md` §1.2–1.4 this version requires fresh
independent review before implementation.

**Author sign-off:** withheld pending round-3 review.
