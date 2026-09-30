# CR-0013 replay implementer: spec findings

Author: the separate author of `acceptance_split.py` (CR-0013 design rule 4).
Date: 2026-09-30.

**Sources used:**
- CR-0013 v2.2 at `HEAD` (`ba240fb`).
- CR-0012 v2.1 at `29f388b`.
- The normative code at `05d788d`: `analyze_grouse.py`, `generate_negatives.py`,
  `prepare_training_data.py`, `grouse_data.py`, `dataset.py`, `models.py`
  (`FEATURE_SPEC`) and `train.py` (`IMG_SIZE`). It was read with `git show`
  and re-implemented, never imported.
- One deviation, CR-0007 v8 text, is explained in F1.

**Sources not read:**
- the CR review logs;
- `check_partition.py` or any other CR-0007 implementation;
- any implementation of CR-0012 (none exists).

**What each finding gives:** the spec text, what I implemented, and whether it
should become a CR amendment. They are ordered by importance.

---

## F1. The spec depends on CR-0007, which rule 4 does not list as a source (amend CR-0013)

- CR-0012 §1 adds its constants "to CR-0007's table".
- CR-0012 pool step 4 and CR-0013 E12 use `verify_partition`.
- CR-0012 positives step 1 requires a `region` column in `evaluated_sightings_R`.

All three are defined only in CR-0007. CR-0013's § Normative definitions
table does not list `verify_partition`. The config needs these values:
`REGIONS`, `STATE_FIPS`, `COUNTY_POLYGONS`, and the polygon rule (filter,
dissolve, CRS, predicate).

**Choice.** I read CR-0007 v8's text at `HEAD`, only its §1 table, its
`verify_partition` paragraph and its §2 `region` paragraph. That is a
specification, not an implementation, so independence from CR-0012's
implementer is unaffected. I re-implemented `verify_partition` from that
paragraph:
- pyogrio `where="STATEFP IN ('23','33','50')"`;
- dissolve by `STATEFP`;
- EPSG:4269 → EPSG:4326;
- `within`;
- a record is returned if it is in no polygon, or if its polygon's state is
  not its `state`.

The config records the consultation under `pins.cr0007_text_consulted_at`.

The other constants match the literals at `05d788d`:
- `MIN_SPACING_M` 30 and `BLOCK_SIZE_M` 3000 (`prepare_training_data.py:49,52`);
- `BUFFER_M` 300, `NEG_RATIO` 1.0, `NONVEG_MAX_FRAC` 0.30, `W_FLOOR` 0.1,
  `W_CAP` 10.0, `NEUTRAL_WEIGHT` 1.0, `NONVEG_WEIGHT` 10.0 and
  `MAX_COORD_UNCERTAINTY_M` 1000 (`generate_negatives.py:70-86`);
- `VAL_FRACTION`, `SPLIT_SEED`, `WINDOW_PX` and `BLOCK_ORIGIN_5070` (CR-0012 §1).

**Amendment.**
- Add `verify_partition` (CR-0007 v8 §1, pinned to the commit where CR-0007's
  text is approved) to the normative table.
- Add CR-0007 at that commit to rule 4's source list.
- Pin CR-0007 like CR-0012, so a later CR-0007 revision re-pins CR-0013.

## F2. CR-0012 never gives the manifest's schema (amend CR-0012 and CR-0013)

CR-0012 §2 lists the manifest's content: constants, hash spec, input and
output sha256, "the count at every numbered step, per region", the dropped
coordinates, commit, dirty and versions. It gives no key names, file-path
convention, count semantics or dropped-list format. E11, E12, R1, R3 and R4
must read these fields. As written, a correct pipeline can fail on naming
alone.

**Choice.** `acceptance_split.json` → `manifest_schema` defines it. Each of
the `positives` and `negatives` sections has these keys:
- `constants`, `hash_spec`, `environment`;
- `inputs` and `outputs`: `{path relative to the data root: sha256}`;
- `counts`: `{R: {"<step>": rows of region R remaining after that step}}`,
  with positives steps 1–6 and pool steps 1–11, recorded even where a step
  removes nothing;
- `negatives.draw`: `{R: {split: {n, n_nv, n_hab}}}`;
- `negatives.dropped`: `[[lon, lat], ...]` sorted ascending;
- `commit`, `dirty`.

**Amendment (needed before CR-0012 is implemented).**
- CR-0012 §2 should cite CR-0013's `manifest_schema` as normative.
- Otherwise CR-0013 must adopt whatever CR-0012 specifies, and CR-0012's text
  needs to specify one.

## F3. Where the `region` column goes in the positive files: CR-0007, CR-0012 and CR-0013 disagree (amend)

- CR-0007 v8 §2 gives `evaluated_sightings` a `region` column right after the
  KDE stage, which places it between `spatial_zone` and `env_zone`.
- CR-0012 positives step 6 says "adding `region`, `block_id` and `split`", but
  `region` already exists.
- CR-0013 deliverable 2 fixes E0's positive list as the pinned
  `evaluated_sightings` columns plus `region`, `block_id`, `split`, with
  `region` last but two.

A pipeline that keeps S's columns and appends `block_id` and `split` has
`region` in position 22, and fails E0. E0 compares an ordered list.

**Choice.**
- E0 compares the header as an ordered list: the config's list, derived
  exactly as deliverable 2 says.
- The replay writes the columns in that order, selecting them from S whatever
  S's own order is.
- For the negatives, "plus `region`" is taken as appended last. The config
  lists both columns.

**Amendment.** CR-0012 step 6 should say that the output column order is
CR-0013's config list, moving `region` after `envelope_id`. Alternatively,
E0 should say "set" and the canonical order should be pinned elsewhere.

## F4. CR-0013's expected-FAIL list for deliverable 5 is incomplete (amend deliverable 5)

On the CR-0007 backup, everything the list names fails, and E1p passes.
These gates fail too:

| gate | why it fails |
|---|---|
| E2 | 1,690 pooled positive pairs are closer than 30 m. They are box-clipped duplicates at distance 0. |
| E8 | 4 NH-filed foreign positives fail the window predicate, and C is missing. |
| E3, E7, E9, E10 | C is a named input of each and does not exist ("missing artifact = named FAIL"). Their N parts are clean. |

Details are in `CR-0013-first-run.txt`.

**Amendment.** The expected FAIL set is every gate except E1p.

## F5. The `--data-root` example does not match the backup's layout (amend deliverable 5 / CR-0012 deliverable 0)

The example is `/home/ec2-user/grouse_backup/CR-0007/`. That backup holds
`pipeline/` and `negatives/` without the `data/` prefix. It also has no
rasters, crosswalk or county file, while every CR-0013 path is `data/...`
under the data root.

**Choice.** I used a scratch root of symlinks. The CSVs are linked file by
file, so the record can never be written into the backup. `data/landfire`
and `data/roads` link to the live, unchanged tree. The layout is described in
the evidence file.

**Amendment.** Describe this composition, or make the backup's layout match
the data root.

## F6. The standing checks cannot recompute 5070 coordinates (amend CR-0013)

Two statements conflict:
- "Block ids are recomputed from lon/lat, never read."
- `standing_checks` may import only numpy, pandas and scipy.

The 4326 → 5070 transform needs pyproj.

**Choice.** In `standing_checks`, E3/E4/E5/E6 take `x_5070`/`y_5070` from
the files. The standing digests bind those columns to the accepted bytes.
R1 and R4, in the full run, check them against lon/lat through full-row
equality.

**Amendment.** State this in § Standing subset.

## F7. The `FEATURE_SPEC` list in CR-0013 omits `nlcd` (amend wording)

CR-0013 says "`FEATURE_SPEC` keys: evt, evh, evc, sclass, fdist, ch, cc and
the continuous features". `FEATURE_SPEC` at `05d788d` (`models.py:517`) has
15 keys, including the categorical `nlcd`. CR-0012 step 3 says "any
`FEATURE_SPEC` raster".

**Choice.** All 15 keys, in `feature_spec_keys`. The window predicate uses
them in positives step 3, pool step 8 and E8.

**Amendment.** List the 15 keys.

## F8. The envelope-feature list is worded differently from the code (amend wording)

CR-0013 says "`ENVELOPE_SCHEME` columns plus `sclass` and `evt`". Read
literally, that includes `evt_phys`. The normative code
(`generate_negatives.py:198-199`) excludes `evt_phys`/`evt_group`, which
gives `["evh", "evt", "sclass"]`.

**Choice.** The code.

**Amendment.** Quote the rule.

## F9. Which coordinates distances use is unspecified (amend CR-0012 §2)

`evaluated_sightings` carries its own `x_5070`/`y_5070`. On today's files,
these differ from a fresh 4326 → 5070 transform by up to 1.4e-9 m. The
pinned positive thinner used the file columns. The pool used a fresh
transform.

**Choice.** Every distance, thin, buffer and block id in the full run uses a
fresh transform of lon/lat. The positive outputs keep S's own `x_5070` column
unchanged, as it is a passthrough.

The risk is a pair within about 1e-9 m of 30 m or 300 m, or of a block edge.
It is negligible but unspecified.

**Amendment.** CR-0012 §2 conventions: "EPSG:5070 coordinates are recomputed
from longitude/latitude."

## F10. The E11 predicates needed interpretation (amend CR-0013 E11)

**(a) "M's input digests equal the files in I and S".** Implemented as:
- every S ∪ I file is listed, and its sha256 equals the file on disk;
- a listed input outside S ∪ I passes only if it is a digested artifact that
  matches disk (for example `generate_negatives.py` reading
  `block_assignments.csv`);
- anything else fails.

**(b) "Every raster the replay or E8 reads".** This includes the rasters that
`raster_path`'s content validation opens, and so every fallback candidate it
rejects. The pipeline's `RegionData.raster_path` opens the same files. On
today's inputs that is 276 rasters.

**(c) Stated limit 7 says an environment change fails E11.** The E11
predicate only compares M's environment. E11 therefore also compares the
running environment with the config.

**(d) "`regions.py`'s values equal the config".** `regions.py` is parsed with
`ast`, and its values must be literals. The names checked are:
- the 8 CR-0012 names: `REGIONS`, `MIN_SPACING_M`, `BLOCK_SIZE_M`,
  `BUFFER_M`, `BLOCK_ORIGIN_5070`, `VAL_FRACTION`, `SPLIT_SEED`, `WINDOW_PX`;
- `COUNTY_POLYGONS` and `STATE_FIPS`, because the config holds them.

The file is the repository's `regions.py`; the config key `regions_py.path`
can give an absolute path, which the tests use.

**Amendment.** Write (a)–(d) into E11.

## F11. No gate checks the canonical row order (amend CR-0013)

- R1–R4 match rows on key, which is order-free as specified.
- E1p checks the parts' order against the combined file.
- Nothing checks that a combined file, B or C is in CR-0012's canonical order.

A file with correct content in the wrong order passes. Its digests still bind
it, but byte-level reproducibility across rebuilds, which CR-0012's order
test assumes, is not gated.

**Choice.** R-gates report a visible `NOTE:` line (non-blocking) when the
rows match but are out of canonical order. A test covers this. I did not make
it a GATE: the CR lists no such predicate, and design rule 2 forbids adding
gates here.

**Amendment.** Add "rows are in canonical order" to R1–R4, or to E1p's
combined-file check.

## F12. The environment pin omits libraries that affect the replay (amend CR-0013 config list)

The config pins pandas, numpy, scipy, pyproj, PROJ and the operation string,
as specified. Two other libraries determine results:
- rasterio/GDAL: `sample_raster` values (pool step 7) and `rowcol`;
- geopandas/shapely/pyogrio: `verify_partition`.

Pandas is 3.0.5, which infers `str` dtype and keeps NaN through
`astype(str)`. The normative code was written against pandas 2. E10
reproduced all 8,365 pre-CR negatives exactly, so no difference is visible
on real data.

**Amendment.** Add rasterio, GDAL, geopandas, shapely and pyogrio versions to
the environment list, in both the manifest and the config.

## F13. Deliverable 2 conflicts with § Files about the OBS file (amend wording)

- Deliverable 2 says "The config and OBS file (constants, specs and
  environment; no references)".
- § Files says `acceptance_split_obs.json` is written only by `--calibrate`.

**Choice.** I followed § Files and did not create the OBS file. OBS settings
(`OBS_Z` = 4, null sizes, seeds) live in the config's `obs` section.

## F14. `standing_checks` and `--standing` details (amend CR-0013 / CR-0012 §5)

- The signature is `standing_checks(img_size, jitter, augment, *,
  data_root=None, config=None)`. The two keyword-only arguments exist for
  tests. Their defaults are the repository and the default config, and
  neither can disable a check.
- Failures are collected, then a single `AcceptanceError` (a `RuntimeError`,
  never `assert`) lists all of them.
- The standing checks also refuse:
  - a record made under a different config sha256;
  - a missing record.
- The CLI has no flags for `img_size`, `jitter` or `augment`.
  `--standing` uses the config's `standing` defaults (64, 0, False), which
  are CR-0012's `IMG_SIZE` and default jitter.

## F15. The OBS rows are under-specified (amend CR-0013 § Observations; non-blocking)

OBS never blocks, so these were implemented rather than asked about. My
choices:

| row | choice |
|---|---|
| Null seeds | N-split and N-draw use `null_seed_base + i`; N-perm uses seed 42. The "block-order seed" and "draw seed" are the `order_key` seed. |
| O2 | "records per val block" is the mean. |
| O4 | A block's val indicator is "holds any val record" (E5 makes blocks pure). |
| O6 | "weight-proportional pool" is the pool's `weight_basis` histogram weighted by `weight`. |
| O7 | "worst cell" is the worse of (R, train) and (R, val). SUP cells are 10 km squares in EPSG:5070, with ≥ 5 positives. |
| O8 | The continuous features are `FEATURE_SPEC`'s continuous kinds, sampled with `sample_raster` at `raster_path(feat, year)`. `road_dist` is read as it is on disk; see CR-0014. |
| O5 | `d` uses the combined files of the same region. |

- Calibration stores each statistic's null mean and sd with a footing digest
  over the S ∪ I input digests.
- A run computes z against them, and marks them stale when the footing
  changes.
- "Previous accepted run" means the previous `acceptance_record.json`'s
  `obs` values.

## F16. Tie-breaks and premises the CRs leave open (amend CR-0012 §2 wording)

**(a) Block-order ties.** A 64-bit `order_key` collision between block ids
breaks on the `block_id` string. This is unspecified; the chance is about
1e-12.

**(b) The `gbif_id` premise.** CR-0012 states that `gbif_id` is non-null and
unique, but does not say what happens otherwise. The replay raises
`ReplayError` (so R3 fails), because "smallest `gbif_id`" is then undefined.
Today it holds: 265,212 unique values.

**(c) The crosswalk pin.** If the newest `LF*_EVT.csv` is not the pinned path,
or its sha256 differs, the replay raises. The CR pins both values but does
not say what a mismatch does.

**(d) The year fill (`dataset.py:98-102`) for E8.** The max is taken per
checked file and region: the combined P/N file of R, or C's rows of R. The
dataset fills per (region, split) frame. The difference is moot while no year
is NaN. That is true today, and pool step 7 removes NaN-year candidates.

## F17. Two attack rows needed interpretation

**(a) "a positive `weight` set to 0.2".** Positive files have no `weight`
column in E0's list, so this attack adds a column. It fails R1 (as required)
and E0.

**(b) "×20 near grouse".** This must fail E3 as well as R4, so it is
implemented as near-grouse rows (< 1 km from a positive) replicated ×20 in
the draw's sub-pool, which produces duplicate negatives. A variant that only
multiplies their weights ×20 fails R4, and E10 if the weights are written,
but not E3.

## F18. Other choices, for the record (no amendment needed)

- **`--emit-reference DIR`** runs the replay only. It writes P, B, C, N and a
  manifest (built to F2's schema) under `DIR` with the same relative paths,
  and exits 0 if the replay succeeds. It evaluates no gates.
- **The record's sha256** is printed. Writing `CR-0012-acceptance.txt` is left
  to CR-0012's implementer.
- **Missing-input reporting.** A gate with several inputs evaluates every
  input it has and reports `FAIL (missing <first path> +k more)`, plus any
  other problems. Unexpected exceptions become `FAIL (gate not evaluable ...)`,
  never PASS.
- **Replay stages.** The positives stage failing stops the pool and draw
  stages (pool step 10 needs B). E12's dropped list is then recomputed
  separately from pool steps 1–4.
- **`raster_path` content validation** streams band 1 in 512-row windows and
  stops once the valid fraction reaches 0.01. That gives the same decision as
  a full read, in bounded memory.
