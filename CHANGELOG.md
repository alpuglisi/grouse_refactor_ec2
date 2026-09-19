# Change log

Why this file exists, given `git log` already exists: commit messages
record *what changed*. This records the **decisions** — including the
hypotheses that were tested and **disproven**, so nobody spends a day
re-running them, and the **bugs introduced during this work**, so the
patterns behind them stay visible.

Newest first. Every entry cites its commit(s); `git show <hash>` is the
authoritative detail.

**Maintenance:** update this file in the same commit as the change it
describes. A new entry earns its place if it records a decision, a
disproven hypothesis, or a bug and its cause — not if it merely restates
the diff.

---

## predict.py: same TensorBoard magnitude bug, found by searching for
## the pattern instead of waiting to trip over it (2026-09-19, e00d956)

Asked where else the model_handler.py tile bug (below) might be
hiding. `_tb_log_windows`' own docstring already says it "mirrors
model_handler's _tb_log_epoch_extras patch/attention visualization,
rebuilt here" - and a grep for `amin(dim` / `amax(dim` found the
literal duplicate: same `norm01` per-sample min/max stretch, same
`t_cont` arriving pre-divided by FEATURE_SPEC scale (this file's own
`read_window_stack`, not dataset.py's, but the identical scaling
contract). Same fix, same scope - `clip01` for the raw input-feature
loop only, `norm01` stays for the logit map and attention weights,
which are model outputs with no fixed physical scale.

Checked the rest of the codebase for the same shape of bug
(`imshow`/`matshow`/per-sample `.min(dim`/`.max(dim` immediately
before a rendered or logged image) and found nothing else - the
diagnostic scripts (diagnose_road_bias.py, diagnose_water_bias.py,
inspect_point.py, analyze_grouse.py) print statistics or use
matplotlib with deliberate, documented percentile stretches (predict.py's
own `--style stretched`), not this "silently re-derive the display
range from data that already had a real one" pattern. pretrain.py logs
no images at all.

---

## model_handler.py: TensorBoard input-feature tiles were rendering
## magnitude as a coin flip (2026-09-19, 5ab679c)

Reported directly: the new balive/tpa_live/qmd/carbon_dwn tiles showed
up (train.py's discovered-features line confirmed they were in
`cont_features`), but were "just colored tiles that don't mean
anything" - a screenshot showed an identical white silhouette shape
repeated across every one of the 8 validation samples, for both
balive and carbon_dwn.

Root cause: `cont_x` reaches the visualization code already divided
by each feature's FEATURE_SPEC `scale` (dataset.py's `_to_tensors`) -
a fixed, physically-anchored quantity, comparable across samples and
epochs by design. The viz code's `norm01()` then re-stretched it
PER-SAMPLE using that sample's own min/max before display. For
TreeMap's four features - ~0 outside forest, then near-uniform across
however much of the patch one imputed FIA plot covers - that meant
any nonzero pixel, at basal area 50 ft2/acre or 380, got stretched to
identical pure white: the tile could only ever show a forest/
non-forest silhouette, never the actual stand-structure value the
feature exists to carry. `ch`/`cc` hid the same bug better only
because LANDFIRE's canopy surfaces vary continuously within a patch,
so per-sample stretching still left some texture behind, at the cost
of the same lost cross-sample comparability.

Fixed by adding `clip01` - clamp the already-scaled value into
display range - used ONLY for the raw input-feature loop. `norm01`'s
per-sample dynamic stretch stays for actual model outputs (logit map,
attention weights, branch activations), which have no fixed physical
scale and need it.

---

## generate_treemap_features.py: median smoothing removed, only after
## being asked to justify it (2026-09-19)

Asked how the default 3x3 `--smooth` worked. Answer: `scipy.ndimage.
median_filter`, median (not mean) of the 9-pixel neighborhood, applied
to the raw TreeMap-derived bands before encoding - a real, nontrivial
transform of the data, on by default, that I explained the mechanics
of without flagging it as a decision point. It took an explicit "undo
that" to get it removed; I did not raise on my own that anyone running
this script with default flags was silently getting filtered values,
not raw ones.

Removed `--smooth`, the `median_filter` call, the halo/window
bookkeeping it required to read block seams correctly, and the now-
unused `scipy` import. `write_vintage` now writes the resampled
per-pixel values straight through, unfiltered.

The mistake wasn't the smoothing itself (it predates this session -
see the original script's own docstring rationale for it). It's that
when asked a mechanics question about a default that changes output
data, "here's how it works" isn't a complete answer - "and here's why
it's on by default, tell me if you don't want that" is the part that
was missing, and the user had to supply it.

---

## generate_treemap_features.py: recomputing identical output per year
## instead of copying it (2026-09-19)

Asked directly, mid-run: was this re-deriving the same TreeMap output
for multiple years instead of reusing it. Yes. `write_vintage`'s actual
work - opening the three 200-360MB source rasters, warping them onto
the region's grid, the median smoothing pass, deriving QMD, encoding -
depends only on `(region, vintage)`; `year` only names the output
file. `process_region` looped over every one of OUR years and called
`write_vintage` for each one independently, so any group of years
mapping to the same TreeMap vintage (ME's actual mapping that night:
2016/2017/2018 -> 2016, 2019/2020/2021 -> 2020, 2022/2023/2024/2025 ->
2022) reran the full pipeline from scratch for each year in the group
- 10 full passes for 3 actually-distinct results.

Fixed by grouping years by vintage first: the expensive path runs once
per unique vintage, and every other year sharing it gets `shutil.copy2`
of that output instead of an independent re-derivation.

Verified two things separately, since the fix's correctness rests on
both: (1) `write_vintage` invoked independently with `year=2016` and
`year=2017` against the same vintage produces byte-identical output
(the precondition for copying being safe at all - proven with a
SHA-256 comparison, not assumed), and (2) `process_region` on a
synthetic 10-year/3-vintage mapping calls the expensive path exactly 3
times, not 10, with every copied year's output verified byte-identical
to its source year.

---

## prune_empty.sh: a free check that doesn't require a re-run (2026-09-19)

Asked for a way to check whether tonight's downloads had left anything
blank without re-running `generate_treemap_features.py`'s own (now
content-validating) pass, which reads and warps real data and isn't
free. `prune_empty.sh` is the cheap complement: pure filesystem checks
(zero-byte files, empty directories), no rasterio, no opening anything
- instant even across the full multi-GB data tree.

Deliberately scoped to NOT attempt content validation (an all-zero-but-
nonempty GeoTIFF, e.g., won't be caught) - that's a different, more
expensive check, and conflating the two would have made this slow for
no reason. Dry-run by default; `--delete` required to remove anything.
Directory deletion runs AFTER file deletion within one invocation,
since removing a zero-byte file can leave its parent newly empty - a
scan taken before any deletion wouldn't see that. Verified against a
synthetic tree with a zero-byte file sitting in an otherwise-real
directory, a directly-empty directory, and a nested one that only
becomes empty once its child is removed - all three handled correctly
in one pass.

---

## generate_treemap_features.py: existence was not enough (2026-09-19)

Asked directly, mid-run, whether the script could be reading from a
blank/empty source - a fair question given the region-collision bug
above was exactly this class of failure (a path that resolved without
error but pointed at the wrong content). `find_source` previously
returned the first glob hit unconditionally; a zero-byte file from an
interrupted download, or a GeoTIFF that opens fine but is entirely
zero (wrong bbox, an empty Earth Engine tile), would have been
silently accepted and warped into a real training feature with no
error anywhere in the pipeline.

`_source_is_valid` (`functools.lru_cache`d, so the same handful of
underlying files aren't re-opened on every one of the ~90 find_source
calls one run makes) now gates every path find_source returns.
Deliberately NOT an all-nodata test like `grouse_data._is_valid_raster`:
`download_treemap.py` writes non-forest as 0 with `nodata=None` (a
real value, not a sentinel), so a raster with no nodata pixels at all
is the NORMAL case here. Instead it checks for at least one nonzero
pixel - a state-sized clip with literally none anywhere is the failure
signature, not a plausible outcome for ME/NH/VT. A name-matching but
invalid file is reported by name and treated as not found, not
silently skipped.

Verified with three synthetic files: a zero-byte file, a GeoTIFF that
opens but is entirely zero, and one with real content - the first two
correctly return `None` with a warning naming the file, the third is
accepted.

---

## download_treemap.py / generate_treemap_features.py: region collision
## in TreeMap filenames (2026-09-19)

First live run: ME's TreeMap 2016 download wrote
`TreeMap2016_BALIVE.tif`, and NH/VT then reported that same file as
"exists - skipping" - not because they had their own data, but because
`out_filename()` never included the region in the name, so all three
regions raced for one path. NH and VT would have silently trained on
Maine's TreeMap numbers if `generate_treemap_features.py` had been run
on the result.

Root cause: `generate_treemap_features.py` was written for the USFS
rastergateway's actual behavior - one CONUS-wide file shared by every
region, no per-region subsetting offered there (verified in the
external research this project commissioned). `download_treemap.py`
clips PER REGION instead, like `download_tcc_nlcd.py` does, but kept
writing the CONUS-implying filename anyway. Two scripts, incompatible
assumptions about what a filename means.

Fixed on both sides:
- `download_treemap.py` now writes `TreeMap{vintage}_{region}_{attr}.tif`
  - always region-qualified, no CONUS naming for anything it downloads
  itself.
- `generate_treemap_features.py`'s `find_source()` takes an optional
  `region` and tries the region-specific name first, falling back to
  the CONUS naming only for someone who downloaded from the
  rastergateway by hand (where one file legitimately does serve every
  region).
- `discover_vintages()` now requires a vintage to be complete for
  EVERY region being processed, not just found somewhere - mirroring
  the `discover_features` intersects-across-regions rule already
  documented for the model's own feature list. A vintage present for
  ME but missing for NH/VT is excluded entirely rather than run for a
  subset, with the exact regions/attributes missing named in the
  warning.
- `write_vintage()` fails loud with a clear message if `find_source`
  ever returns `None` despite `discover_vintages` having approved the
  vintage, instead of crashing inside `rasterio.open(None)`.

Verified with a fixture reproducing the exact failure: ME's files
present, NH/VT absent. `find_source(..., region="NH")` correctly
returns `None` (no fallback to ME's file); `discover_vintages` for all
three regions raises, naming every missing (region, attribute) pair;
restricted to `["ME"]` alone it correctly reports 2016 available.

**Action needed on the box: delete `data/treemap_raw/` and re-run
`download_treemap.py` from scratch.** Every file currently in there was
written under the old, colliding naming - Maine's data is numerically
correct but under a name the fixed scripts will no longer look for.

---

## download_treemap.py: default tile size too large for Float32 (2026-09-19)

First real download run: auth succeeded, TreeMap 2016 opened, then
every tile failed with "Total request size (51232005 bytes) must be
less than or equal to 50331648 bytes." `--tile-m 96000` had been
copied from `download_tcc_nlcd.py` unchanged - correctly sized for
THAT script's int16 output (2 bytes/px: 3200px tiles = 20.48MB,
comfortably under the 48MB cap) but never re-derived for this script's
Float32 output (4 bytes/px). The actual failure size implies Earth
Engine charges closer to 5 bytes/px for a single-band export here, not
4 - an observed, undocumented overhead, not something the API
guarantees.

Default dropped to 48000m (1600px tiles, ~12.8MB worst case at the
observed rate) - real margin under the cap, not the bare minimum, so
the same silent assumption can't bite again at a slightly larger
region.

---

## Earth Engine auth: Workspace-blocked shared client, and a latent
## ee_init() bug (2026-09-19)

First real run on the EC2 box: `earthengine authenticate` failed with
Google's "This app is blocked... Google blocked this access" - no bypass
link. That message is Google Workspace org policy rejecting Earth
Engine's own shared OAuth client (`764086051850-...`) outright, not a
transient error to retry. Confusingly, `ee.Authenticate(auth_mode='gcloud')`
does NOT do what its name implies either - it still drives its consent
screen through that same blocked client, so it failed identically.

What actually worked: `gcloud auth application-default login` (gcloud's
OAuth client is Google-verified and wasn't blocked), producing
Application Default Credentials Earth Engine's own init path never looks
for on its own. `ee_init()` in both `download_tcc_nlcd.py` and
`download_treemap.py` now tries the normal `ee.Initialize(project=...)`
path first, and falls back to loading ADC via `google.auth.default()`
and passing it to `ee.Initialize(credentials, project=...)` explicitly
if that fails - so this is a one-time `gcloud` command on an affected
account, not a manual workaround needed on every run.

**Also fixed, found while patching this: neither script's `ee_init()`
ever `return`ed the `ee` module.** Both callers do `ee = ee_init(args.project)`
expecting it back; the original function implicitly returned `None` on
success. `download_tcc_nlcd.py` would have crashed on its first real
Earth Engine call (`AttributeError` on a `None`) independent of any auth
problem - this suggests it had not actually been run to completion
before. Both scripts now `return ee` explicitly.

---

## TreeMap acquisition via Earth Engine (2026-09-19)

`generate_treemap_features.py --src-dir` needed the three raw attribute
rasters (BALIVE, TPA_LIVE, CARBON_DWN) already on disk, and its own
docstring explained why it couldn't fetch them itself: the rastergateway
serves per-attribute downloads through an HTML `<select>` whose option
values aren't visible in the page's markup, so no URL template could be
constructed from it.

`download_treemap.py` sources the same numbers from Earth Engine instead
(`USFS/GTAC/TreeMap/v2016`, `v2020`, `v2022`), reusing
`download_tcc_nlcd.py`'s tiled-download/retry/merge machinery rather than
writing new fetch code. **2023 is not available this way** — not yet
ingested into the EE catalog — so this covers three of TreeMap's four
vintages; `generate_treemap_features.py` already tolerates a partial
vintage set by design (nearest-year mapping), so this costs nothing
beyond what a missing vintage always would.

Two decisions worth recording:
- **Band names are verified at runtime, not hardcoded.** The exact band
  list was not independently confirmed for each vintage before writing
  this — only that BALIVE/TPA_LIVE/CARBON_DWN-shaped attributes exist
  somewhere in the image. `resolve_band` matches case-insensitively
  against the real `bandNames()` and fails loud with the actual list if
  an expected one is missing, rather than assuming the name matches.
- **Non-forest is `unmask(0)` at download time**, not left as TreeMap's
  own NoData sentinel (`4.2949673e+09`, which GDAL won't auto-detect).
  This is also the correct value, not a placeholder — a non-forest pixel
  genuinely has zero basal area, zero live stems, zero down dead wood —
  and it matches `generate_treemap_features.py`'s own non-forest
  convention, so no scrubbing is needed downstream.

Verified offline (no live Earth Engine credentials in this environment):
region-grid math snaps to the 30 m lattice, tiling divides a state into
tractable requests, and band resolution fails loudly with the real band
list on a deliberately-missing attribute. The live download path itself
is unverified — run it on the EC2 box, which already holds working EE
credentials for `download_tcc_nlcd.py`.

---

## document_tree.sh: making the data-vintage situation reviewable (2026-09-19)

Data files are gitignored and never reach a clone, so which features
exist for which years - the thing every question about training-record
retention actually turns on - was invisible from the repo alone.
`document_tree.sh` parses the `{REGION}_{YEAR}_{feature}.tif`
convention into a feature x year coverage matrix per region (gaps
marked explicitly), plus directory sizes, a checkpoint listing, and
the full per-file tree. Reads names, sizes and timestamps only, never
file contents, so it can't copy a credential out of a config file into
the repo.

`-r` (the directory to document) and `-o` (where to write/stage the
result) may point at different repositories - the normal case here,
since the rasters live in the training working directory and the repo
is a separate checkout. Verified against a synthetic tree with a
deliberate coverage hole (the matrix flags it), a repository with no
commits yet, and an output path under a `.gitignore` rule that would
otherwise swallow it silently.

---

## Five stand-structure / disturbance features added (2026-09-19)

`tsd`, `balive`, `tpa_live`, `qmd`, `carbon_dwn`. Stem input channels
116 → 121; **cold start required**, `--resume` and `--init-from` invalid
against every older checkpoint.

**Five at once is a deliberate choice by the user, against a
recommendation of two.** Flagged here because it has a known cost: the
result will not be attributable to any individual feature, exactly as the
cold-start + `road_dist` change before it is still unattributable. If the
run improves, an ablation is the only way to learn which channel did it.

**`tsd` — years since last disturbance** (`generate_time_since_disturbance.py`).
Added because the strongest signal ever measured on this model is a
disturbance signal — `fdist` boundary density at −0.509, twice any canopy
correlation — and `fdist` is a categorical *embedding*. Embedding indices
carry no order, so the network cannot learn that the code meaning "3
years" sits nearer to "5 years" than to "20 years". `tsd` supplies that
ordered magnitude, from the annual LANDFIRE disturbance record (1999–2024, 26 vintages as of this run) rather
than the four `fdist` vintages on disk. Not redundant: `fdist` says what
happened, `tsd` says how long ago as a number the network can do
arithmetic on.

**Fixed same day: the CONUS bundle is a zip of zips.** `fetch_disturbance`
originally `extractall()`'d only the outer
`USAnnualDisturbance_1999_present.zip`, which yields one
`LF{release}_Dist{yy}_CONUS.zip` per year — never a `.tif`. First real run
failed with "No Dist{yy} rasters found" against a directory that plainly
had 26 zip files in it. `_extract_nested_zips` now unpacks those too,
looped (in case of a third level) and marked per-archive so a second run
doesn't re-extract 26 zips to learn there was nothing new. Runs for an
explicit `--dist-dir` as well as the downloaded default, since pointing
`--dist-dir` at a raw copy of the bundle hits the same problem. Verified
against a synthetic zip-of-zips fixture: four nested archives extract on
the first call, none re-extract on the second, and `fetch_disturbance`
returns the correct year → path mapping both times.

Two decisions inside it. The undisturbed value is a **fixed**
`TSD_MAX_YEARS`, not "years since the record began" — a cap that grew with
the vintage (24 in 2022, 27 in 2025) would make the feature's single most
common value a vintage label. And unlike `road_dist`, which writes
identical copies because roads are static, `tsd` is **recomputed per
vintage from the record up to and including that year**; the clock runs,
and using later disturbance would leak the future into a sighting's
landscape.

**TreeMap stand structure** (`generate_treemap_features.py`). The stack
measures cover three ways and height two ways and had **nothing** for stem
density or stem size — so 60% cover at 50 ft could be 80 large stems per
acre or 2,000 saplings, identical in every feature, opposite habitats for
an early-successional obligate.

Four attributes, not the twelve with no LANDFIRE counterpart: QMD is
exactly `sqrt(BALIVE/(0.005454·TPA))`, and `SDIsum`/`ALSTK`/`GSSTK`/
`DRYBIO_L`/`CARBON_L`/`VOLCFNET_L` are all functions of the same two
numbers. Twelve channels would buy about three dimensions. `CANOPYPCT` and
`STANDHT` are excluded outright — TreeMap is imputed *from* LANDFIRE, and
USFS report 94.2% / 99.0% within-class agreement with the `evc`/`evh`
already present.

`qmd` is **derived rather than downloaded**: TreeMap publishes it only for
2020/2022/2023, and 2016's `QMD_RMRS` is a different definition, so
downloading would open a vintage seam or cost the 2016 vintage. The
identity was verified numerically (`BALIVE` reconstructs exactly from the
derived QMD).

Three things that had to be decided rather than defaulted:
- **Smoothing is on by default (3×3).** TreeMap's fine texture is
  imputation artifact, and it has no reference data for boundaries at all
  — only single-condition, 100%-forested plots were eligible, so plots
  straddling a stand edge were excluded by construction. This
  architecture computes edge magnitude from every channel it is given and
  cannot be told to skip one, so the detail is destroyed at generation
  time instead.
- **Non-forest is written as 0, not a sentinel.** Zero basal area, zero
  stems and zero down wood are true of a hayfield. `qmd=0` is undefined
  rather than true, but `qmd=0 ∧ tpa_live=0` is exactly the non-forest
  signature, so the joint pattern replaces a mask channel. TreeMap's own
  NoData (`4.2949673e+09`) is not GDAL-detectable and cannot survive the
  int16 patch cache, so it is remapped on read.
- **Vintages map by nearest year.** Writing every one of our years from
  the nearest of TreeMap's 2016/2020/2022/2023 keeps a file present for
  each, so the `all()` year-gap filter sees no change and LANDFIRE stays
  the binding constraint — these features cost zero training records. The
  cost is that the filter also cannot warn about a stale mapping, so the
  generator prints it and flags gaps over 2 years itself.

**Not added, and why.** `elev` was recommended alongside `tsd` and was
declined with slope; the model still has no terrain input at all (`slope`
and `gradient` are downloaded by `download_rev.py` but appear in neither
`FEATURE_SPEC` nor `RASTER_FEATURES`). `dist_type` was rejected as
redundant with `fdist`, which already encodes type and severity.

---

## Code structure and reviewability (2026-09-18 → 19)

**Three silent-divergence duplications collapsed** — `b60e480`.
`NODATA_SENTINELS` had three independent definitions (two sets, one
tuple); "raw window → model input" and the D4 TTA scorer each had three
copies. None of those would crash if they drifted apart — the deployed
map and the diagnostics meant to explain it would simply stop agreeing,
each internally consistent. Now: `grouse_data.NODATA_SENTINELS`,
`predict.read_window_stack`, `models.d4_tta_logits`.

Verified by an 18-array golden harness capturing `read_strip`,
`predict_region` (heatmap, capture maps, edge maps, at
`temperature=1.3 / logit_shift=-0.4`), `_tb_capture_windows`, and a
`flip_tta=False` variant from the *unmodified* code — all 18
bit-identical afterward.

*Deliberately not unified:* the training path's equivalents. Its D4
comes from the dataset (`expand_rotations=True`) with only the mirror
added in code; its patch read routes sentinels through NaN so
`dataset.py`'s 100%-nodata geolocation probe can fire at all. Same
numbers, different routes, real reasons. An earlier draft of this work
called them blind duplication — that was wrong.

**Superseded files archived to `legacy/`, `ARCHITECTURE.md` added** —
`bf509da`. `audit.py` was byte-identical to `analyze_grouse.py` and had
been actively misleading (identical grep hits at identical line numbers
in two files). `gen_negs.py` lacked `NONVEG_MAX_FRAC` entirely. Four
downloaders predated `fdist`/`ch`/`cc`. ~2,500 lines off the review
surface; `git mv`, so recoverable.

`fit()` (371 lines) and `predict.py main()` (~305) were left alone
deliberately — review burden, not a bug class, and decomposing them is
where a new bug would come from.

---

## The road-hugging investigation (2026-09-18)

A suitability map over Errol, NH visibly tracked Route 16. Four
hypotheses, three disproven with data. **Do not re-run these.**

**Disproven — road-accessibility bias in the presence data** (`86fcc70`,
`diagnose_road_bias.py`). eBird records are famously biased toward
accessible locations, so this was the leading theory. Measured against
TIGER/Line roads, training positives sit **2–5× farther** from roads
(median 2,951–4,875 m) than the trained-on negatives (844–1,451 m), in
all three states. If anything the *negatives* are road-biased, which
would suppress scores near roads, not inflate them.

**Disproven — riparian/wetland corridor** (`a96e2fa`,
`diagnose_water_bias.py`). Roads follow valleys; wetlands score high; so
maybe the map tracked the valley. Also backwards: positives sit
*farther* from water/wetland (124–182 m) than negatives and raw
candidates (67–108 m).

**Disproven — calibration.** Raised twice. Temperature scaling is a
monotonic transform of the logits: it moves absolute scores, never their
ordering. It cannot make one region bright relative to its neighbours,
so it can never explain *where* a map is bright.

**Partially confirmed — feature correlations** (`7daed36`, `73f2519`).
Per-feature `Class/`, `Correlation/` and `Edge/` breakdowns over a
predicted region. Canopy features correlate positively but modestly
(`cc` +0.209, `tcc` +0.199, `ch` +0.169). Edge-magnitude correlations
are stronger and feature-specific: `evt` boundary density **+0.402**,
`fdist` (disturbance) boundary density **−0.509** — the model rewards
natural vegetation-type mosaics and *penalises* disturbance/
infrastructure boundaries.

**Actual cause — 30 m rasters cannot resolve a two-lane road**
(`fef3b7d`, `inspect_point.py`). Settled by checking the model's raw
inputs against known ground truth, which nothing else in the project
did — every other diagnostic compares the model to itself and would look
self-consistent even if the whole grid were shifted. On Route 16:

| point | `nlcd` reads | score |
|---|---|---|
| on pavement, narrow stretch | 90 WOODY WETLANDS | 0.68 |
| on pavement, wide stretch | 22 Developed Low | 0.09 |

Same road, same model. Where the road is narrower than a pixel it
vanishes into the surrounding cover; the model scores that cover,
correctly by its own inputs, and the renderer paints the result over the
road line.

**Fix — `road_dist` feature** (`5f48f26`, `generate_road_distance.py`).
Metres to the nearest paved road, from TIGER/Line, rasterized per region.
TIGER has no surface attribute, so "paved" is approximated by MTFCC
class: `S1100/S1200/S1400/S1630/S1640` in; 4WD trails (`S1500`),
logging/private roads (`S1740`) and footpaths out. `S1400` mixes paved
town roads with rural gravel and TIGER cannot separate them — included
anyway, because excluding it would drop nearly every paved secondary
road. Adjustable via `--mtfcc`.

---

## Bugs introduced during this work, and fixed

Logged deliberately: all four were silent or delayed failures, and three
came from instrumentation added in the same session.

**`--resume` silently froze the EMA** — `5937e9b`. `ModelEMA.update()`
writes through `_dst_float`, references to the tensor *objects* built in
`__init__`; the restore rebound `self.shadow` to a fresh dict. `update()`
then wrote into the old tensors while `applied()` read the new ones, so
the average froze at the restore point forever. Training looked normal
while **every validation metric and every saved checkpoint served
identical stale weights**. Caught only because three consecutive epochs
printed bit-identical loss/AUC/AP/logit-std. Fixed with
`ModelEMA.load_shadow()` (copies in place); regression test shows the old
path drifting `0.000000` over 50 steps.

**`road_dist` saturated at its own cap** — `059911a`. A 5 km linear cap
put Maine's *median* distance at the cap under highways-only MTFCC — half
the state pinned to one constant — while `diagnose_road_bias.py` had
already measured positives at 2,951–4,875 m. The cap was erasing signal
in exactly the range the data occupied. Now log-encoded
(`round(log1p(m)*1000)`, int16): 0–500 m spans 0.622 model-input units,
5–50 km spans 0.230.

**TensorBoard crashed a live 150-epoch run at epoch 85** — `4e2c8e8`.
Non-finite gradients (likely the epoch-70 warm-restart LR spike) hit
`add_histogram`, which raises on an all-non-finite tensor. Now filtered,
with the finite remainder logged and an `events/nonfinite_grad` text
warning instead of a crash.

**TensorBoard crashed on an empty LR param group** — `9345e90`.
`--init-from` loading every tensor leaves the "fresh" group with zero
params, and `torch.cat([])` raises. The gradient-histogram path already
handled this; the weight-histogram path did not.

---

## Training mechanics (2026-09-18)

- **`--resume`** (`b7b1c60`) — continues optimizer momentum, scheduler
  phase, EMA, and checkpoint-selection state from a `.resume` sidecar
  written every epoch. Not just weights: losing scheduler phase silently
  reheats the LR at whatever point just crashed the run.
- **`--dynamic-dropout`** (`c1b4936`) — dropout reacts to the trend in
  the val/train loss gap. A sinusoidal schedule was requested and argued
  against: unlike cyclical LR it has no comparable mechanism, and an
  oscillation out of phase with `warm_restarts` risked compounding the
  instability already seen at the epoch-70 restart.
- **`rank` selection + min-delta** (`9055e1d`) — `0.5*(TTA AUC + TTA AP)`
  against the *last saved* checkpoint, not the running max. Selecting on
  AUC alone had kept saving through epochs 12–30 for +0.002 AUC (a third
  of its own standard error) while AP fell and val loss rose 38%.

## Features and objectives

- **`road_dist`** (`5f48f26`, `059911a`) — see above.
- **Loss-aware calibration** (`bb6aa48`) — an asymmetric objective bakes
  a constant `log(λ)` offset into the logits, which temperature scaling
  (a pure scale) can never remove. `predict.py` now warns instead of
  applying a fitted temperature as if it restored honest probabilities.
- **L_AN-full** (`a355f9a`) + `--pos-neg-ratio`/`--an-lambda`
  (`04fc331`). Note `--an-pos-weight` takes precedence over
  `--pos-neg-ratio`; the printed `L_AN-full lambda ... [reason]` line
  names the winner.
- **Dual-branch head** (`1972e52`), **early-attention with 2D RoPE +
  relative bias** (`35982c1`, `42b970d`), **SimSiam pretraining**
  (`97e068f`), **USFS TCC + Annual NLCD via Earth Engine** (`960c898`).
- **Year-gap exclusion** (`6659f57`) — training records with no raster
  within ±2 years of the sighting are dropped rather than matched to a
  landscape that didn't exist yet.

## Work that didn't pan out

**LiDAR/3DEP terrain features — added then removed** (`26bfa7e` …
`a743772`, reverted in `fc7faf3`). Eight commits of download machinery,
multi-resolution patch geometry, and a static-feature year exemption,
fighting Earth Engine export limits (reprojection caps, unbounded-image
errors, tile size vs. the download cap, silent 30 m downloads). Removed
because the download was impractically slow — the 10 m rough band alone
projected many hours per state. Training geometry returned to a single
30 m / 64 px grid. **If terrain is revisited, start from why the export
was slow, not from this code.**

**Wetland-shortcut hypothesis — disproven** (`646c9fb`, `c4cf68d`).
`diagnose_wetland.py` against the real checkpoint: WOODY WETLANDS'
positive fraction (0.69) is tied with Deciduous/Evergreen/Mixed
(0.70/0.71/0.69), not an outlier; wetland val scores rank mid-pack behind
Shrub/Scrub; and NLCD ablation raises scores fairly uniformly, with
wetland's shift *smaller* than several non-wetland classes — the opposite
of a wetland-specific shortcut.
