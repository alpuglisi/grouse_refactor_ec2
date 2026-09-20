# Project map

Ruffed grouse (*Bonasa umbellus*) habitat suitability CNN for ME / NH / VT.
Presence points from eBird via GBIF, predictors from LANDFIRE + Earth
Engine rasters, output a per-pixel suitability map.

This file exists to make the project reviewable: what is core, what
order things run in, and — the last section — the invariants that are
not visible from the code you happen to be editing.

`CHANGELOG.md` is the companion: what changed, why, which hypotheses
were tested and **disproven** (so they are not re-run), and which bugs
were introduced along the way.

---

## Library modules (no `__main__`, imported by everything else)

Dependency order, bottom up. Nothing below imports anything above it.

| Module | Owns |
|---|---|
| `blocks.py` | `ChannelAttention`, `SpatialAttention`, `CBAM`. |
| `grouse_data.py` | Disk layout. `GrouseData` / `RegionData`, `PATH_TEMPLATES`, `RASTER_FEATURES`, `NODATA_SENTINELS`, year-matching policy, `NLCD_NAMES`. **Every path and raster convention in the project resolves through here.** Dependency-free leaf, so diagnostics can import it without pulling in torch. |
| `losses.py` | `FocalLoss`, `ANFullLoss`, and `loss_logit_bias` (the constant logit offset an asymmetric objective bakes in). |
| `models.py` | `FEATURE_SPEC` (the feature registry), `GrouseResNet`, `split_features`, `config_to_model_kwargs`, `road_dist_encode/decode`, `d4_tta_logits` (the single inference-side scorer). Imports `blocks`. |
| `dataset.py` | `GrousePatchDataset` (point → patch stack), `SSLPairDataset`, `StratifiedBatchSampler`, and the int16 patch cache. Imports `models`. |
| `model_handler.py` | `GrouseModelHandler` (the `fit()` loop, checkpoint selection, TensorBoard instrumentation), `ModelEMA`, `DivergenceGuard`. Imports `grouse_data`, `losses`, `models`. |

## Pipeline, in execution order

Each stage consumes the previous stage's files. Paths are all defined in
`grouse_data.PATH_TEMPLATES`.

**1. Acquire points**
- `sightings.py` — grouse presence records, GBIF bulk download (eBird dataset)
- `ebird.py` — same species via the eBird API directly
- `get_negatives.py` — *other* bird species as target-group background candidates → `data/negatives/gbif_negatives_{region}.csv`

**2. Acquire rasters** → `data/landfire/{REGION}_{YEAR}_{feature}.tif`
- `download_rev.py` — LANDFIRE: evt, evh, evc, sclass, fdist, ch, cc, slope, gradient
- `download_tcc_nlcd.py` — Earth Engine: tcc, nlcd
- `download_attribute_tables.py` — LANDFIRE class-code crosswalks
- `generate_road_distance.py` — road_dist, from TIGER/Line vectors
- `generate_time_since_disturbance.py` — tsd, from the LANDFIRE Annual
  Disturbance stack (1999–2023, one raster per disturbance year)
- `download_treemap.py` — pulls BALIVE, TPA_LIVE, CARBON_DWN from
  the Earth Engine TreeMap collections (2016/2020/2022; 2023 isn't
  ingested yet) into the naming `generate_treemap_features.py` reads
- `generate_treemap_features.py` — balive, tpa_live, qmd, carbon_dwn,
  from those rasters (`--src-dir`) or any other source in the same
  naming convention

**3. Analyse** — `analyze_grouse.py` → `evaluated_sightings_{region}.csv`,
`envelope_metrics_{region}.csv`. Collapses duplicate coordinates, flags
non-vegetated records, fits habitat envelopes, runs the KDE stage.

**4. Prepare positives** — `prepare_training_data.py` → `thinned_positives`,
`train_positives`, `val_positives`, `block_assignments`. Minimum-spacing
thinning plus a spatial-block train/val split.

**5. Prepare negatives** — `generate_negatives.py` → `negatives_{region}.csv`
+ train/val splits. Needs stages 3 and 4 (envelope metrics, block
assignments).

**6. Train** — `train.py` → checkpoint (default `grouse_single_best.pth`)
+ `<path>.resume` sidecar. `pretrain.py` is the optional SSL warm-start.

**7. Calibrate** — `calibrate.py` → `data/calibration/calibration.json`

**8. Predict** — `predict.py` → GeoTIFF / KMZ suitability map

## Diagnostics

| Script | Question it answers |
|---|---|
| `inspect_point.py` | At one known lon/lat, what raw feature values does the model actually see, and what does it score? **The only tool that checks inputs against external ground truth** — everything else compares the model to itself. |
| `diagnose_road_bias.py` | Are training positives/negatives distributed differently w.r.t. roads? |
| `diagnose_water_bias.py` | Same, w.r.t. water/wetland. |
| `diagnose_wetland.py` | Per-NLCD-class composition and score breakdown. |
| `diagnose_training.py` | Training-set sanity checks. |
| `check_exotic.py`, `check_raster.py`, `dupe_check.py` | One-off data-integrity checks. |
| `smoke_test_training.py` | Fast end-to-end training smoke test. |
| `document_tree.sh` | Inventories the working directory — every file with size and date, plus a **feature × year raster coverage matrix per region**. Data files are gitignored and never reach a clone, so this is how the year-vintage situation becomes reviewable from the repo. |
| `tune.py`, `tune_bins.py` | Hyperparameter / envelope-bin sweeps. |

`predict.py --tensorboard` also emits per-feature `Class/`, `Correlation/`
and `Edge/` breakdowns over a predicted region.

## `legacy/`

Superseded files, kept for history, imported by nothing:

- `audit.py` — byte-identical to `analyze_grouse.py`
- `gen_negs.py` — older `generate_negatives.py`; **lacks the `NONVEG_MAX_FRAC` cap**
- `download.py`, `download_landfire{,_2,_3}.py` — predate fdist/ch/cc
- `download_more.py` — `download_rev.py` minus empty-raster validation

---

## Invariants

Things that are true, load-bearing, and not visible from the code you
are most likely editing when you break them. Each one has cost real
debugging time.

**`ModelEMA.shadow` tensors must be written through, never replaced.**
`update()` writes via `torch._foreach_*` through `_src_float` /
`_dst_float`, which hold references to the tensor *objects* captured in
`__init__`. Rebinding `self.shadow = {...}` leaves `update()` writing
into the old tensors while `applied()` reads the new ones: the average
silently freezes forever. Training looks normal — live weights keep
moving, train accuracy keeps climbing — while every validation metric
and every saved checkpoint serve identical stale weights. Use
`ModelEMA.load_shadow()`. The same rule applies to the model's own
tensors: build the EMA *after* any `.to(device)` / `.to(memory_format)`.

**Adding or removing a feature is a geometry change.** Model channel
count is derived from `FEATURE_SPEC` + whatever rasters are on disk, so
dropping a raster in is enough to change the network. That means
`--resume` and `--init-from` both become invalid against older
checkpoints, and it needs a cold start. `train.py` prints the derived
count (`stem input channels=N`) — check it.

**`discover_features` intersects across regions.** A feature present for
NH but missing for ME is silently dropped from the model entirely, with
no error. Generate new rasters for *all* requested regions.

**Checkpoints come in two formats.** Wrapped (`{state_dict, config}`)
carries its own feature list and geometry, and that list is
authoritative on load. Bare (older) is a raw `state_dict` with no
feature list, so loading it depends on what is on disk *now* — which
breaks whenever the disk feature set changes. `config_to_model_kwargs`
owns every geometry key and legacy fallback — except one that lives in
the weights themselves: each categorical embedding's row count (its
`vocab`). Loaders take that from the checkpoint's own
`embeddings.<f>.weight` via `models.spec_with_checkpoint_vocab`, never
from today's `FEATURE_SPEC`, so a checkpoint keeps loading after the
spec changes. Any new loader must do both.

**A categorical `vocab` must cover the raster's whole code domain, or
the top of it silently disappears.** `GrouseResNet.embed` clamps codes
into `[0, vocab-1]`; a code at or above the vocab lands on the top index
and nothing crashes. That is how the LANDFIRE herbaceous block vanished:
EVC encodes herb cover as 310–399 and EVH herb height as 301–310 (three
life-form blocks since LF 2016 Remap, identical LF2022–LF2025), and both
features had `vocab: 300` until 2026-09-20. `fit()` now checks the spread
sample against the vocab and warns by name; raising a vocab is a
cold-start geometry change (the table is in the state dict).

**`--select-min-delta` compares against the last SAVED checkpoint, not
the running maximum.** This is deliberate: max-based selection creeps
upward on measurement noise. A run can legitimately show several
epochs of tiny improvements with no save.

**`--an-pos-weight` takes precedence over `--pos-neg-ratio`** when
`--loss an_full`. Both flags set lambda; the printed line names the
winner — `L_AN-full lambda (positive weight): N [reason]`. Trust that
line, not the command.

**`road_dist` is stored log-encoded, not in metres.** Raw metres
saturate: at highways-only MTFCC, Maine's median distance exceeded a 5km
linear cap, pinning half the state to one constant. `road_dist_encode` /
`road_dist_decode` in `models.py` are the single definition; anything
reporting a distance to a human must decode first.

**Every continuous feature has a storage encoding distinct from its
`FEATURE_SPEC` scale.** `road_dist`, `tsd` and `tpa_live` are log-encoded;
`balive`, `qmd` and `carbon_dwn` are fixed-point (`TREEMAP_FIXED`). The
scale divides the *stored* number, so reading a model input back to a
real-world unit means undoing both, in that order. `inspect_point.py` is
the worked example.

**`tsd`'s undisturbed value is a FIXED cap, not "years since the record
began".** If the cap grew with the vintage — 24 in the 2022 raster, 27 in
the 2025 one — then the most common value in the feature would itself
identify the vintage, and the network would have a free year label. Same
failure mode as a mixed-vintage `fdist` code space. `TSD_MAX_YEARS` is
constant across every raster written.

**`tsd` is recomputed per vintage; `road_dist` is copied.** Roads are
static, so `road_dist` writes byte-identical files to every year. Time
since disturbance is not: the clock runs. Each vintage year Y is computed
from the disturbance record up to and including Y, never later, or the
feature leaks the future into a sighting's landscape.

**TreeMap features must not be trusted at boundaries.** Only
single-condition, 100%-forested FIA plots were eligible for imputation, so
plots straddling a stand boundary were excluded by construction: a TreeMap
"edge" is the imputation switching between two interior plots, not a
mapped transition. This matters because the model's strongest measured
signals are edge-magnitude correlations (`evt` +0.402, `fdist` −0.509) and
the architecture computes those from every channel it is given — there is
no way to tell it to skip one. `generate_treemap_features.py --smooth`
(default 3×3) destroys that detail on purpose, before it reaches the
network.

**Non-forest in the TreeMap features is 0, not a nodata sentinel.**
TreeMap is NoData off forest, but "no trees" is a real measurement for
three of the four: a hayfield has zero basal area, zero stems, zero down
wood. `qmd=0` is the one fudge, and it stays self-consistent — `qmd=0`
AND `tpa_live=0` is exactly the non-forest signature, so the joint pattern
carries the distinction without a mask channel. Note TreeMap's own NoData
is `4.2949673e+09`, which GDAL does not auto-detect and which cannot
survive the int16 patch cache; it is remapped at generation time.

**`qmd` is derived, never downloaded.** `QMD = sqrt(BALIVE / (0.005454 ×
TPA_LIVE))` is the USFS query definition verbatim. TreeMap publishes QMD
only for 2020/2022/2023 — 2016 ships `QMD_RMRS` under a different
definition — so downloading it would open a definitional seam across
vintages or cost the 2016 vintage. One formula for all four has neither
problem, and it is one fewer CONUS download.

**TreeMap vintages are mapped to ours by nearest year, so these features
never shrink retention.** TreeMap has 2016/2020/2022/2023; the stack has
its own vintages. Writing every one of our years from the nearest TreeMap
year keeps a file present for each, so the `all()` year-gap filter
(`train.py:182`) sees no change and LANDFIRE remains the binding
constraint. The cost is that the filter also cannot warn when a mapping is
stale — `generate_treemap_features.py` prints the mapping and flags any
gap over 2 years itself.

**The patch cache keys on the feature list and raster mtimes**, so it
self-invalidates when either changes — but it stores **int16**, so a
continuous feature must survive integer truncation (scaling happens
after, at tensorize time).

**Temperature scaling cannot change a map's spatial pattern.** It is a
monotonic transform of the logits: it moves absolute scores, never their
ordering. A region that looks hot relative to its neighbours will still
look hot at any temperature. Calibration is never the explanation for
*where* a map is bright.

**30m rasters cannot resolve a two-lane road.** Verified with
`inspect_point.py`: a point on Route 16 pavement reads `nlcd=90 WOODY
WETLANDS` where the road is narrow, and `nlcd=22 Developed Low` where it
is wide. Land-cover-derived conclusions about narrow linear features are
unsound; that is what `road_dist` exists to supply.

**There is exactly one inference-side scorer and one inference-side
patch reader.** `models.d4_tta_logits` (4 rotations × optional mirror,
averaged BEFORE the sigmoid) and `predict.read_window_stack` (sentinels
zeroed, continuous channels divided by their `FEATURE_SPEC` scale) each
had three copies. Nothing about a divergence between copies would
crash — the deployed map and the diagnostics meant to explain it would
simply stop agreeing, each internally consistent. Add a new inference
path by calling these, never by re-deriving them.

**The training path deliberately does NOT share those two.** Its D4
comes from the dataset (`expand_rotations=True`) with only the mirror
added in code (`GrouseModelHandler._pooled_logits`), and its patch read
routes sentinels through NaN first so the 100%-nodata geolocation probe
can fire (impossible once 0 is in the array, since 0 is a legitimate
value). Same numbers by different routes, for reasons — do not "unify"
them without reading both.
