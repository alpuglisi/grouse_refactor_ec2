# BUG-0028 (DRAFT — not committed): `predict.py` writes every map to one mutable path with no record of what produced it

> Draft for review. Not in `docs/quality/bugs/`; `BUG_LOG.md` and
> `PREVENTIVE_ACTIONS.md` are untouched.

## 1. Description
`predict.py` writes its output to
`data/predictions/{REGION}_custom_suitability.tif` (and `.kmz`), a
single path fixed by region. Every run for that region overwrites the
previous one, and the file records **nothing** about which checkpoint,
which flags, which bounds, which raster vintages or which calibration
produced it. A saved map is therefore not attributable to a run, and
two maps of the same region from different checkpoints are
indistinguishable except by re-deriving them.

## 2. Where encountered
Found during the Errol map investigation (2026-09-30,
`INVESTIGATION_REPORT_errol_map.md` §1a), while establishing
`INVESTIGATION_PLAN_errol_map.md` step 1, "Is the checkpoint the run the
user thinks it is?".

- Output path and write: `predict.py:1095-1107`. The filename is the
  region plus `"_custom"` when `--bounds` is given, and nothing else;
  there is no `update_tags` call anywhere in the module.
- Verified on the artifact itself:
  ```
  >>> rasterio.open("inv_before/USER_ORIGINAL_NH_custom_suitability.tif").tags()
  {'AREA_OR_POINT': 'Area'}
  >>> .tags(1) -> {}      >>> .descriptions -> (None,)
  ```
  `grep -n "update_tags\|TIFFTAG\|set_band_description" predict.py` → no
  matches.

## 3. What it caused to fail
The user reported a map and gave the command they believed produced it:

```
python predict.py --region NH --model bce.pth --bounds -71.25 44.70 -70.95 44.90
```

The map on disk was **not** produced by `bce.pth`. Establishing that
cost a brute-force search over seven candidate runs (every checkpoint in
the repository plus `--compile` / `--no-flip-tta` / `--no-calibration`
variants), each of which had to be re-run with the pre-fix `road_dist`
rasters swapped back in to make the comparison like-for-like:

```
candidate                           spearman  max|diff|   median
inv_probe_old/bce_cal.tif           0.914368    0.53724   0.4880
inv_probe_old/bce_compile.tif       0.914368    0.53724   0.4880
inv_probe_old/bce_nocal.tif         0.914368    0.44596   0.7292
inv_probe_old/bce_noflip.tif        0.913992    0.54560   0.4879
inv_probe_old/ed_cal.tif            0.902055    0.63580   0.4917
inv_probe_old/gap3_cal.tif          1.000000    0.00000   0.7092
inv_probe_old/single_best.tif       0.095143    0.97796   0.0034
```

`gap3.pth` matched pixel-exactly (`np.array_equal` → `True`,
0 differing pixels). Observable impacts:

- **A wrong command is now recorded in three project documents** as the
  provenance of this map: `INVESTIGATION_PLAN_errol_map.md` §1,
  BUG-0022 §1, and BUG-0023 §1 all name `bce.pth`.
- **The investigation ran its first pass against the wrong
  checkpoint.** Every "before" measurement had to be repeated for
  `gap3.pth`.
- **A near-miss on a wrong conclusion.** Had the two checkpoints
  disagreed about the symptom, the investigation would have been
  measuring an artifact of the wrong model against a map produced by
  another. They happened to agree (P(ME>NH) 0.8235 vs 0.8513), so this
  cost time rather than correctness — this time.
- **Silent overwrite.** The user's original map was overwritten by the
  investigation's first `predict.py` run; it survived only because it
  was copied aside first, by hand, on this occasion.

## 4. What the defect was
The output is opened and written with no tags, and the path carries no
discriminator beyond the region:

`predict.py:1095-1107`, verbatim:
```python
    tag = args.region + ("_custom" if args.bounds else "")
    tif_path = os.path.join(OUT_DIR, f"{tag}_suitability.tif")
    with rasterio.open(tif_path, "w", driver="GTiff",
                       height=heatmap.shape[0], width=heatmap.shape[1],
                       count=1, dtype=rasterio.float32, crs=ref.crs,
                       transform=transform, nodata=np.nan) as dst:
        dst.write(heatmap, 1)
    print(f"Saved GeoTIFF: {tif_path}")

    if not args.tif_only:
        kmz_path = os.path.join(OUT_DIR, f"{tag}_suitability.kmz")
        generate_kmz(tif_path, kmz_path, style=args.style,
                     cmap_name=args.cmap, alpha_below=args.alpha_below)
```
`tag` distinguishes "whole region" from "some custom box" and nothing
more: two different boxes, two different checkpoints and two different
flag sets all land on the same filename.

The run *prints* everything needed — checkpoint path, calibration
source and its `model_path` mismatch warning, the resolved raster
filename for each of the 15 features — to stdout, where it is lost when
the terminal scrolls. None of it reaches the artifact.

## 5. Root cause analysis (Five Whys)
1. *Why could the map's checkpoint not be determined?* The file records
   no provenance, and its name is the same for every run of that region.
2. *Why is there no provenance?* The GeoTIFF is written with the minimum
   profile needed to be geographically valid. Writing metadata was never
   part of "write the output".
3. *Why is the path the same for every run?* `tag` is built from the
   region and whether `--bounds` was passed. That models an output as
   "one file per region", which is right for a **pipeline input** (a
   raster feature, where the latest is the only one wanted) and wrong
   for a **run artifact** (a map, where which run made it is the whole
   question).
4. *Why did nothing catch it?* The provenance exists only in stdout. No
   check compares an artifact to the run that made it, because the
   artifact carries nothing to compare.
5. *Why wasn't this foreseen?* PA-0014 already names this mechanism —
   "duplicate scripts must never share a single mutable output path
   without a visible marker (in the filename, or a written
   manifest/header row) recording which script/variant-set produced it"
   — but it is scoped to *duplicate scripts*. Here one script produces
   mutually incompatible artifacts from different checkpoints and
   flags. The hazard is identical; the trigger PA-0014 names is not.

**Root cause:** a run artifact is written to a path keyed only by
region, carrying no record of the inputs that produced it, so its
provenance is recoverable only by re-deriving it. The existing rule
against unmarked shared mutable output paths (PA-0014) is scoped to
*different scripts* sharing a path, and so does not reach *one script's
different runs* sharing a path.

## 6. Corrective action
None implemented. This is non-trivial (it changes the output file
format and, if the path changes, the CLI contract), so per `CLAUDE.md`
§1 it needs a CR and independent review first.

Proposed, for the CR to evaluate:
1. **Write provenance tags into the GeoTIFF** — the cheap,
   backward-compatible half. `dst.update_tags(...)` with: checkpoint
   path + its mtime + an md5 or the config dict, the resolved raster
   filename per feature, bounds, stride, flip-TTA, calibration source
   and `model_path`, prior/temperature, and the `predict.py` git
   revision. Costs nothing, breaks no reader, and would have answered
   §3's question in one call.
2. **Mirror the same into the KMZ description**, which is what the user
   actually looks at in Google Earth.
3. **Make the default filename discriminating** (e.g. include the
   checkpoint stem), or at minimum refuse to silently overwrite an
   existing output whose tags name a different checkpoint. This is the
   part with a CLI-contract cost; the CR should weigh it against (1).

**Verification:** re-run any two checkpoints over the same box and
confirm the checkpoint is readable from each artifact without re-running
the model — the check that failed in §3.

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for the same bug and
for a different bug with the same root cause:

- **BUG-0016 / PA-0014 — `tune.py` shared output path. This is the same
  mechanism, and this is a second occurrence.** BUG-0016 was two
  diverged scripts writing one mutable output path with nothing
  recording which produced it. This is one script's different runs doing
  the same thing.
- **BUG-0005 / PA-0003** (re-hardcoded path patterns) concerns path
  *derivation*, not artifact identity. Related, not the same.
- **BUG-0010 / PA-0008** is the nearest relative in spirit: a
  checkpoint's config was *saved but never validated on load*. Here the
  artifact's config is never saved at all. Same family — provenance
  recorded but unusable, versus not recorded — at a different stage.
- No prior bug about prediction outputs. **BUG-0016 is the prior
  instance of the mechanism.**

**Prior-preventive-action failure analysis (PA-0014).** PA-0014 states
the right rule and it did not prevent this, for two reasons:

1. **Scoped to the trigger, not the mechanism** — contrary to
   `CLAUDE.md` §3.3. Its text is "*When duplicate scripts have diverged
   … such scripts must never share a single mutable output path without
   a visible marker*". The hazard is "a mutable output path shared by
   producers that are not interchangeable". "Duplicate scripts" was the
   trigger that surfaced it; the rule was written around that trigger,
   so a single script producing non-interchangeable artifacts from
   different checkpoints and flags falls outside it.
2. **Its sweep inherited the same narrow scope.** PA-0014's Swept? entry
   reads "swept every shared-output-path pair in the repo; the only two
   others found (`gen_negs.py`/`generate_negatives.py`,
   `clean.py`/`prepare_training_data.py`) are content-identical". The
   sweep looked for *pairs of scripts*. `predict.py` has no pair, so it
   was never examined, even though its output path is shared by every
   checkpoint the project has ever trained.

## 8. Preventive action
**PA-0019 (proposed; supersedes PA-0014, extending it from "duplicate
scripts" to "non-interchangeable producers").**

> Any mutable output path that can be written by producers whose outputs
> are not interchangeable — different scripts, or the **same script with
> different inputs, checkpoints, flags or parameters** — must carry a
> visible marker of what produced it, *in the artifact itself* (file
> tags, an embedded header, or a sidecar manifest) and not only in the
> path or in stdout. For a run artifact (a map, a metric table, a
> report) the marker must name every input that changes its values.
> Printing provenance to stdout does not satisfy this rule.
> Extends/supersedes PA-0014, whose "duplicate scripts" scope missed
> BUG-0028.

PA-0014 stays listed and says it is superseded by PA-0019, per
`CLAUDE.md` §3.6.

**Sweep (§3.5) — required before this is closed, and NOT yet run.**
Scope it by the mechanism (any mutable output path written by
non-interchangeable producers), not by "prediction outputs". Candidates
visible from `PATH_TEMPLATES` and the CLI scripts, to be confirmed:
`data/calibration/calibration.json` (one path per project, rewritten by
every `calibrate.py` run against a different checkpoint — it *does*
record `model_path`, and `predict.py` warns on mismatch, so this may
already satisfy PA-0019; confirm), `data/predictions/*.kmz`,
`runs/`/TensorBoard directories, `*.csv` training logs, and the
`.pth.resume` files.

**Mechanical enforcement (§3.4).** Feasible and cheap for the raster
case: a test that runs `predict.py` twice with different checkpoints and
asserts the two artifacts' tags differ and name the right checkpoint. No
CI exists in this repository yet, so it would run as a manual check
until one does.
