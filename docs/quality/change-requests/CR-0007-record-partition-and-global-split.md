# CR-0007: Partition sighting records by state and centralise the shared spatial constants

**Status: CLOSED (v9.2), 2026-09-30 — implemented, all deliverables complete, bookkeeping complete; `check_partition.py` P1–P8 PASS (`docs/quality/evidence/CR-0007-gates-v9.2.txt`).** History and dispositions: `CR-0007-review-log.md`.
This document states only current intent.

## Scope
Make `state` the only region-membership key for sighting records in
`analyze_grouse.py`'s outputs, checked against county polygons; give the
shared spatial and region constants one definition; guard the three stale
copies in §3.

## Why now
- **Records belong to several regions.** `clip_to_region`
  (`analyze_grouse.py:198`) selects by overlapping boxes, so each
  `evaluated_sightings_R.csv` holds other states' records (P1 "today"),
  whose keys also appear in their own state's file (P2). This is the
  membership half of BUG-0027 and the positive half of BUG-0029. CR-0012
  pools records across regions and needs each in exactly one region.
- **Constants are defined in many places** (PA-0001; list and count: P6).
  `TIGER_YEAR` was 2025 in one of them until CR-0014 set 2023 (`05d788d`).

**One change (§1.1 A5).** The deliverables are pipeline code, the re-run
of `analyze_grouse.py` that regenerates its derived files from that code
(not a data repair), and this CR's own bookkeeping. Constants and partition
could land separately but are kept together: `verify_partition`/`in_state`
need `REGIONS`, `STATE_FIPS` and the county vintage in `regions.py`,
CR-0012 needs both, and both edit `generate_negatives.py:60`. The
`legacy/download*.py` guards are here by user decision (2026-09-30) as the
remediation of BUG-0031, which this CR files. BUG-0034 is promoted only
because PA-0020 (BUG-0029's preventive action) cites it as sole evidence.

## The change

### 1. `regions.py` and `grouse_data.py`
No value changes. `BOXES` keeps its values and gets a docstring: raster
request extents, not membership.

| name | value | today defined at |
|---|---|---|
| `REGIONS` | `("ME", "NH", "VT")` | `repair_coverage_rasters.py:53`; `REGIONS_DEFAULT` and inline lists (re-point table) |
| `STATE_FIPS` | `{"ME": "23", "NH": "33", "VT": "50"}` | `generate_road_distance.py:122`, `diagnose_road_bias.py:71` |
| `STATE_NAMES` | `{"ME": "Maine", "NH": "New Hampshire", "VT": "Vermont"}` | `get_negatives.py:45`; inverted at `sightings.py:123` |
| `TIGER_YEAR` | 2023 (value owned by CR-0014) | `generate_road_distance.py:116`, `diagnose_road_bias.py:72` |
| `COUNTY_POLYGONS_YEAR` | 2023 | new; pinned independently of `TIGER_YEAR` |
| `MIN_SPACING_M` | 30 | `prepare_training_data.py:49`, `generate_negatives.py:71` |
| `BLOCK_SIZE_M` | 3000 | `prepare_training_data.py:52`; imported by `generate_negatives.py:60` |
| `BUFFER_M` | 300 | `generate_negatives.py:70` |

`grouse_data.PATH_TEMPLATES` gains `"tiger_county":
"data/roads/tl_{year}_us_county.zip"` and `"availability_sample":
"data/pipeline/availability_sample_{region}.csv"` (PA-0003).

- **`verify_partition(lon, lat, state)`** returns the records whose
  county-polygon state differs from `state` or that lie in no polygon. It
  reads `PATH_TEMPLATES["tiger_county"]` at `COUNTY_POLYGONS_YEAR` with the
  pyogrio filter `STATEFP IN (<STATE_FIPS values>)`, dissolves by
  `STATEFP`, reprojects EPSG:4269 → 4326 and joins with `within`.
  geopandas and `grouse_data` are imported inside the function; the
  dissolved polygons are cached in a module-level dict on first read.
  **`in_state(lon, lat, region)`** uses the same polygons and predicate.

**Re-points** (`R` = `regions`):

| file:line | today | after |
|---|---|---|
| `predict.py:92`, `download_treemap.py:110`, `download_tcc_nlcd.py:74` | `BOXES` from `prepare_training_data` | `R.BOXES` |
| `diagnose_road_bias.py:68,71,72` | `BOXES` likewise; `STATE_FIPS`, `TIGER_YEAR` literals | `R.BOXES`, `R.STATE_FIPS`, `R.TIGER_YEAR` |
| `generate_negatives.py:60,70,71,241` | `BOXES`, `BLOCK_SIZE_M_DEFAULT` from `prepare_training_data`; `BUFFER_M`, `MIN_SPACING_M` literals | `R.BOXES`, `R.BLOCK_SIZE_M` (at `:241`), `R.BUFFER_M`, `R.MIN_SPACING_M`; `thin_by_min_distance` unchanged |
| `prepare_training_data.py:42,49,52` | `REGIONS_DEFAULT`, `MIN_SPACING_M_DEFAULT`, `BLOCK_SIZE_M_DEFAULT` literals | `list(R.REGIONS)`, `R.MIN_SPACING_M`, `R.BLOCK_SIZE_M` (CR-0012 v2 later deletes all three) |
| `repair_coverage_rasters.py:53` | `REGIONS` literal | `R.REGIONS` |
| `check_exotic.py:31`, `diagnose_water_bias.py:58`, `dupe_check.py:27`, `tune.py:40`, `tune_bins.py:40` | `REGIONS_DEFAULT` literal | `list(R.REGIONS)` |
| `bench_pipeline.py:66`, `calibrate.py:310`, `diagnose_training.py:35`, `diagnose_wetland.py:138`, `pretrain.py:118`, `train.py:394`, `download_tcc_nlcd.py:460` | `default=["ME", "NH", "VT"]` | `default=list(R.REGIONS)` |
| `check_raster.py:71` | `("ME", "NH", "VT")` | `R.REGIONS` |
| `get_negatives.py:45`; `sightings.py:123`; `ebird.py:16` | `STATES`; `state_mapping`; `STATES` literals | `R.STATE_NAMES`; `{n: c.lower() for c, n in R.STATE_NAMES.items()}`; `{r.lower(): f"US-{r}" for r in R.REGIONS}` |
| deliverable 7: `generate_road_distance.py:116,122,173`, `check_road_dist.py:472` | `TIGER_YEAR`, `STATE_FIPS` literals; county path from `CACHE_DIR`; region list | `R.TIGER_YEAR`, `R.STATE_FIPS`, `PATH_TEMPLATES["tiger_county"]`, `list(R.REGIONS)` |

`check_road_dist.py:127` keeps its own county path: it is CR-0014's
verifier and resolves its inputs from its own pins.

### 2. `analyze_grouse.py`
**Before:** every stage and output of `analyze_region` (`:667`) uses the
box-clipped frame from `clip_to_region`.

**After:**
- `load_all_sightings` (`:156`), after the longitude flip (`:187-193`),
  raises if any `state` is not in `REGIONS`; if any key is filed under two
  states (0 today; otherwise the box collapse could keep the foreign record
  as representative); or if `verify_partition` returns any record.
- `analyze_region` keeps the box clip, collapse, extraction and KDE stage
  (`:778-795`) on the box frame: the KDE source is every box record with
  the required features, of any state (PA-0018). Intended consequence:
  stratified percentiles are over the box source, so "Hotspot 10%" is not
  exactly 10 % of own-state rows.
- Immediately after the KDE stage, `valid` is restricted to
  `state == region` and gains a `region` column. Every later stage uses
  it: the `nonveg_flagged_{region}.csv` write (moved from `:776`), binner
  fitting, envelopes, selection ratios, the `evaluated_sightings_*` and
  `envelope_metrics_*` writes (`:1016-1017`), and the map's markers and
  contours. The map's density surface (`visualization_density_surface`) is
  fit on the box KDE source, like the KDE. The map is not checked.
- Because the `nonveg_flagged_*` write now follows the KDE stage, the file
  also carries `spatial_density` and `spatial_zone` (and `region`).
- **Availability** (`background_envelope_sample`, `:411`): box points are
  drawn in batches from one generator, keeping those where `in_state`
  holds, until `BACKGROUND_N` exist (raise after 20 batches; in-state share
  ME 0.526 / NH 0.477 / VT 0.540, 20,000 points, seed 1). It writes
  `availability_sample_{region}.csv`: exactly `BACKGROUND_N` rows, the
  in-state points before raster sampling, with `longitude`, `latitude`,
  `used` (survived the nodata `dropna` and non-veg filter) and
  `envelope_id` (empty unless `used`). `MIN_VALID_FRAC` (`:444`) is
  unchanged (denominator: in-state points). `background_nonveg_rate`
  (`:324`) uses the same rule; it is print-only and not checked.
- geopandas becomes a dependency of `analyze_grouse.py`.

Known limit: a record in coastal water inside a county polygon passes
`verify_partition`; the extraction `dropna` removes it.

**Provenance of `state`.** Positives: GBIF `stateProvince`, grouped into
per-state files by `sightings.py:132`. Negatives: the `stateProvince`
query parameter at `get_negatives.py:268`. P4 is the evidence for both.

### 3. Stale copies (PA-0002; BUG-0031)
`legacy/audit.py` (a copy of `analyze_grouse.py` writing the same paths,
`:1021-1022`), `legacy/download.py` and `legacy/download_more.py`
(diverged copies writing `download_rev.py`'s raster paths) each get, as the
first statement after the docstring and before any import,
`raise SystemExit("<file> is a stale copy of <live script> (BUG-0031); use
<live script>")`, as CR-0012 v2 §6 does for `clean.py` and
`legacy/gen_negs.py`. Nothing imports these files.

**v9.2 (BUG-0048):** `legacy/download_landfire.py`, `_2.py` and `_3.py`
(PA-0026 sweep: they write `data/landfire/*.tif`, `download_rev.py`'s
directory, and were guarded only inside `__main__`, naming the stale
`download.py`) get the same first-statement guard, naming
`download_rev.py` and citing BUG-0031 and BUG-0048. Their old `__main__`
block is left in place, unreachable. They hold no P6 violation, so they
are not P6-exempt.

## Acceptance
`check_partition.py` (deliverable 0) never imports `analyze_grouse.py` or
calls `verify_partition`/`in_state`. Constants are read by
`ast.literal_eval` from their single definitions: `regions.py`;
`analyze_grouse.py` (`BACKGROUND_N`, `REQUIRED_FEATURES`,
`COORD_ROUND_DECIMALS`, `KDE_MODE`, `STRATIFY_BY`, `MIN_STRATUM_FOR_KDE`,
`KDE_BANDWIDTH_M`, `RASTER_DIR`); `grouse_data.py` (`NODATA_SENTINELS`,
`PATH_TEMPLATES`). It
re-implements loading, collapse, sampling, the vintage rule, the polygon
test (own dissolve, `shapely.contains_xy`) and the KDE (numpy sum); the
analysis CRS comes from the evaluated files' `x_<epsg>` column. A run with
`--assume` or `--only` is labelled NOT AN ACCEPTANCE RUN.

**Definitions.** A *key* is `(lon, lat)` rounded to
`COORD_ROUND_DECIMALS`. *Raw*: records loaded as `load_all_sightings` does
(file-name regex, first `lon`/`lat` column, `dropna`, flip). *S_R*: raw
records inside `BOXES[R]` (inclusive), collapsed to one row per key (the
first-loaded row of the key's latest year), with a value in every
`REQUIRED_FEATURES` raster of R at the vintage nearest the row's year
(earlier on a tie). A value is missing when the point is outside the
raster's inclusive bounds, equals its nodata, or is in `NODATA_SENTINELS`,
as in `sample_raster` (`:276-295`). *E_R*: the own-state rows of S_R.

| id | check | today (pre-CR files) | required |
|---|---|---|---|
| P1 | every row of `evaluated_R` and `nonveg_flagged_R` has `state == R` and `region == R` | foreign rows: evaluated 283 / 2,696 / 1,476 (4,455), nonveg 148 / 1,545 / 751; no `region` column | 0 |
| P2 | keys of the three `evaluated` files are pairwise disjoint | ME∩NH 1,184, NH∩VT 3,271 | 0 |
| P3 | keys(`evaluated_R`) = keys(E_R); no own-state key outside `BOXES[R]`; no duplicate key; no key filed under two states; each `REQUIRED_FEATURES` value in `evaluated_R` equals the resampled one | extra keys 283 / 2,696 / 1,476; 0 missing; NH 2,305 value mismatches (O4) | all 0 |
| P4 | every raw record has `state` in `REGIONS` and lies inside its own state's polygon | 0 of 43,024 | 0 |
| P5 | per R: (a) `availability_sample_R` has `BACKGROUND_N` rows, each inside `BOXES[R]` and R's polygon, `envelope_id` present iff `used`; (b) each envelope's `Avail_N` = count of `used` rows with that `envelope_id`, and `sum(Avail_N)` = `used` count; (c) `Sightings` = `evaluated_R[~nonveg_landcover].envelope_id.value_counts()` (0 if absent); (d) `Envelope` unique, each row in (b)'s or (c)'s set | (a), (b) file absent; (c) 0 mismatches | all hold |
| P6 | `tests/test_shared_constants.py`: `regions.py` holds §1's pinned values; `PATH_TEMPLATES` holds both entries; the scan finds nothing | 34: 10 pins absent, 24 literal lines in 21 files | 0 |
| P7 | the P7 list imports; each of the six §3 copies' first statement is the guard and running it exits non-zero naming BUG-0031; no P6-scanned module imports a `docs…` module or passes a `docs/` path to `sys.path` or a path-based loader (v9.2) | 28 of 28 import; 3 guards absent | holds |
| P8 | per R, each `evaluated_R` row: `evt_phys` = crosswalk(`evt`); `spatial_density` (rtol 1e-6) and `spatial_zone` equal the `KDE_MODE` computation over S_R (a zone within rtol of p10/p90 is exempt) | holds (today's files are box-sourced) | holds |

**P6 scan.** Scanned: `git ls-files '*.py'` minus basenames `inv_*`/`res_*`,
`tests/` and `docs/quality/evidence/` (frozen review evidence, never run
as pipeline code; excluded by v9.1 after CR-0013 committed evidence copies
there). Exempt by name, nothing else: `regions.py`; `clean.py` and
`legacy/gen_negs.py` (CR-0012 §6 guards); `legacy/audit.py`,
`legacy/download.py`, `legacy/download_more.py` (§3). (The road files'
exemption ended with deliverable 7.) Known limit of P7's docs-import
check: it matches `docs` written literally in an import, a `sys.path`
call or a path loader's arguments; a path assembled in a variable, or
`import_module`/`exec`, is not detected — the evidence exclusion's safety
there rests on review.
A violation is (i) an assignment, at any depth, to a §1 name, `BOXES`, or
their `_DEFAULT` alias whose value contains a literal; (ii) a list, tuple
or set of string literals equal to `REGIONS`, case-folded; (iii) a dict of
string literals whose keys or values equal `REGIONS`, case-folded. The
exempt files hold 8 more lines (`clean.py` 3, `legacy/gen_negs.py` 2,
`generate_road_distance.py` 2, `check_road_dist.py` 1). Round 8's "13"
counted rule (i) only.

**P7 list.** `regions`, `grouse_data`, `analyze_grouse`, every re-point
file, and `download_rev` (an unedited importer of `regions`). Guarded
copies are not imported. The `docs/` check (v9.2) keeps the P6 exclusion
of `docs/quality/evidence/` safe: excluded code can never be run by
scanned code (`check_partition.docs_import_problems`).

**Today** P1, P2, P3, P5, P6, P7 fail
(`docs/quality/evidence/CR-0007-check-today.txt`); a no-op fails P1–P3 and
a deletion P3 (PA-0021(b)). `tests/test_check_partition.py` shows each
wrong construction round 8 named failing its check (no-op, box membership,
`state` overwritten, dropped record, both `envelope_metrics` constructions,
post-filter or box-drawn availability, KDE restricted, wrong-state record).
**Limit:** P5 does not recompute a point's `used` flag or `envelope_id`
(that re-implements binning); a wrong flag with consistent counts passes.

**Observations** (never blocking): O1 symmetric difference of post-CR
`evaluated_R` keys vs pre-CR `evaluated_R` ∩ state-R keys (P3 predicts 0);
O2 own-state habitat rows (today 3,740 / 1,119 / 1,552); O3 judgeable
envelopes (`Avail_N ≥ MIN_AVAIL_BG`) before and after; O4 the NH `ch`/`cc`
rasters (mtime 2026-09-20) postdate `evaluated_sightings_NH.csv`
(2026-09-18) and 1,040 `ch` / 1,265 `cc` values differ; the re-run
replaces them; cause untested (PA-0016), tracked.

## Impact
- **Rewritten:** `evaluated_sightings_*`, `envelope_metrics_*`,
  `nonveg_flagged_*`; `availability_sample_*` is new. Selection ratios, and
  so CR-0012's negative weights, change. **Not read by training**
  (`train.py`, `calibrate.py`, `bench_pipeline.py`); CR-0009's baselines
  are unaffected. **Other readers:** `prepare_training_data.py`,
  `generate_negatives.py` (via `grouse_data`'s `.evaluated`, `:148`),
  `tune.py:215`, `tune_bins.py:213`, `check_exotic.py:109`,
  `dupe_check.py:90`. Re-points change no value or CLI default. Rasters,
  `road_dist`, model code, negatives and splits are not affected.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Old `generate_negatives.py` runs between this CR's run and CR-0012; its per-region buffer then sees only own-state sightings | 3 candidate keys are within 300 m of a foreign-state sighting only (verified 2026-09-30); CR-0012's rebuild is the next data run; deliverable 1's backup restores the pre-CR state |
| Rejection sampling cannot fill `BACKGROUND_N` | Raise after 20 batches; in-state share ≥ 0.477 |
| A re-point breaks an import or changes a value | P7; P6 pins the values |
| Edits collide with CR-0012/CR-0014 in the same files | CR-0007 lands before CR-0012; road files wait for CR-0014 (deliverable 7) |
| A silently dropped record | P3 |
| Polygon check across a datum | Explicit `to_crs` in `verify_partition` and in the checker |

## Test plan
**Here:** P1–P8 on the real run; P1–P3 fail on the backed-up pre-CR files;
both test files pass (the repository-tree test is `expectedFailure` until
deliverable 2 removes the marker, then must pass); the guards fire.
**Not here:** model effect (CR-0009); behaviour without geopandas or the
county file (specified, not exercised).

## Deliverables (in execution order)
- [x] 0. **Pre-approval (round 9):** commit `check_partition.py`, both test
      files, `docs/quality/evidence/CR-0007-check-today.txt`, and the
      untracked drafts deliverable 6 promotes from (`DRAFT_BUG-0034-…md`,
      `res_qms_PA-0019-0020-0021-draft-rows.md`).
- [x] 1. Back up `data/pipeline/`, `data/negatives/` (24 + 27 MB) to
      `/home/ec2-user/grouse_backup/CR-0007/` with a sha256 manifest.
- [x] 2. §1 (all but deliverable 7's re-points); remove the
      `expectedFailure` marker (removed with v9.1).
- [x] 3. §2.
- [x] 4. §3.
- [x] 5. Run `analyze_grouse.py`, then `check_partition.py` (acceptance
      run): P1–P8 pass; record O1–O4. Do **not** run
      `prepare_training_data.py` or `generate_negatives.py` (CR-0012).
      O1–O4: `docs/quality/evidence/CR-0007-gates.txt`; P1–P8 PASS after
      v9.1 and deliverable 7 (`CR-0007-gates-d7.txt`) and after v9.2
      (`CR-0007-gates-v9.2.txt`).
- [x] 6. Bookkeeping (BUG ids: next free at filing): *(2026-09-30:
      BUG-0043..0047 + PA-0025; BUG-0031 + PA-0026, sweep BUG-0048;
      BUG-0029, BUG-0034 promoted; PA-0020 filed; see the review log's
      Implementation record.)*
      - **Constants BUG** (literals outside `regions.py`, incl. the
        `TIGER_YEAR` drift); recurrence review against BUG-0001/PA-0001
        with prior-PA failure analysis (sweep covered `BOXES` only; no
        check). New PA: "Extends PA-0001. A project-chosen spatial or
        region-domain constant is assigned a literal only in `regions.py`
        (a data path only in `PATH_TEMPLATES`) and imported everywhere
        else, CLI defaults and `_DEFAULT` aliases included; enforced by
        `tests/test_shared_constants.py`, whose pins and names grow with
        each new such constant."
      - **§3.5 sweep for that PA**, one BUG per remediation: (a) region-code
        sequences and dicts (P6 rules ii–iii), fixed by deliverable 2;
        (b) state name/eBird-code maps (`get_negatives.py:45`,
        `sightings.py:123`, `ebird.py:16`), deliverable 2; (c) county path
        built twice, §1 + deliverable 7 (`check_road_dist.py:127` justified
        above); (d) analysis CRS `"EPSG:5070"` (16 literals in 7 files incl.
        `clean.py`): **open, deferred**, owner CR-0007's author (tracker),
        who opens a CR after CR-0012 lands. Reason: the CRS is also encoded
        in the `x_5070`/`y_5070` schema and CR-0012's `BLOCK_ORIGIN_5070`,
        so a constant alone protects nothing; the downloaders' EPSG:5070 is
        Earth Engine's delivery lattice, a different quantity.
      - **BUG-0031** (PA-0014's sweep missed `legacy/audit.py`; PA-0002's
        left five runnable copies); §4.2 analysis of PA-0002/0012/0014
        (swept by name similarity; a move to `legacy/` counted as
        "deprecated"). New PA: "Extends PA-0002 and PA-0012. A stale copy
        is found by what it writes: a tracked script writing a path another
        live script writes is its single owner or starts with
        `raise SystemExit` naming the replacement; a comment, `legacy/` or a
        suffix is not a guard." Sweep by output path; correct PA-0002's and
        PA-0014's Swept? cells.
      - Promote `DRAFT_BUG-0034` (status "open; fix owned by a future CR")
        and `DRAFT_BUG-0029` (with a `BUG_LOG.md` row; §8 cites PA-0020).
        File PA-0020 from the draft row: no `coord_uncertainty_m` example
        in its Rule; its Swept? cell keeps the measured-inert
        `MAX_COORD_UNCERTAINTY_M` result as a sweep finding.
      - PA-0018's Swept? cell: KDE source box-sourced, checked by P8.
      - BUG-0027, BUG-0029: corrective action "membership: CR-0007; split
        and draw: CR-0012"; fixed when CR-0012 lands, closed after CR-0009.
- [x] 7. After CR-0014 closes: the road-file re-points (last table row);
      remove their two P6 exemptions; P6 and P7 pass. CR-0007 closes after
      this deliverable.
- [x] 8. v9.2 amendment: BUG-0048 guards (§3), P7's `docs/` check, the
      synthetic tests (`tests/test_shared_constants.py`
      `test_evidence_dir_skipped_other_docs_scanned`, `DocsImports`); P1–P8
      pass (`docs/quality/evidence/CR-0007-gates-v9.2.txt`).

## Landing order
Independent of CR-0010/CR-0008 (only LANDFIRE vegetation channels are
read). Before CR-0012, which requires `check_partition.py` to pass.
CR-0014 already set `TIGER_YEAR = 2023`; deliverables 0–6 do not touch its
files; deliverable 7 follows its closure. Either side of CR-0009's
baselines.

## Out of scope
Global grid, pooled thin/draw, standing checks, the `clean.py` and
`legacy/gen_negs.py` guards → CR-0012; their acceptance → CR-0013;
`TIGER_YEAR`'s value, `road_dist` → CR-0014; `sample_background_points` →
CR-0015. BUG-0026 (only re-pointed here), BUG-0034's fix, BUG-0028, the
retrain (CR-0009), the analysis-CRS constant (sweep item (d)).
