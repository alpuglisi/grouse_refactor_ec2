# Reviewer briefing: grouse habitat suitability CNN

This is a handoff document for an AI model (or human reviewer) with no
prior context on this codebase, being asked to do a comprehensive
correctness/quality review of its core scripts. It exists so the review
starts from an accurate map of the project instead of re-deriving one
from scratch, or worse, flagging deliberate design choices as bugs.

Everything in this file is a **summary written by a prior AI session**
for orientation purposes. Where it conflicts with `ARCHITECTURE.md`,
`CHANGELOG.md`, or the code itself, those are authoritative — this file
is not.

---

## 1. What this project is

A CNN that predicts ruffed grouse (*Bonasa umbellus*) habitat
suitability for Maine/New Hampshire/Vermont from LANDFIRE + Google Earth
Engine raster features (vegetation type/height/cover, canopy cover, NLCD
land cover, road distance, time-since-disturbance, tree biomass, etc.),
trained on eBird/GBIF presence points against **assumed-negative
background points** (other bird species' sightings, or random background
locations) — not confirmed absences. That "presence-background" framing
matters for review: some of the model's apparent error (accuracy
capped well below 100%, a persistent train/val gap) is very likely
**irreducible label noise**, not necessarily a bug — see §5.

Full pipeline (data acquisition → raster generation → training →
calibration → prediction) is documented in `ARCHITECTURE.md`. **Read
that file first, in full.** It is short, deliberately written for
exactly this purpose ("what is core, what order things run in, and the
invariants that are not visible from the code you happen to be
editing"), and this briefing assumes you've read it.

## 2. Required reading, in order, before touching any code

1. **`ARCHITECTURE.md`** — module map, pipeline order, and a dedicated
   **Invariants** section: load-bearing facts that aren't visible from
   the code you'd be editing, each one having cost real debugging time
   previously. Do not skip this section — several look like bugs if you
   don't know them going in (see §4).
2. **`CHANGELOG.md`** — decisions, hypotheses that were tested and
   **disproven** (so they don't get re-litigated), and past bugs with
   their root causes. Read it before flagging something as suspicious —
   there is a real chance it's a documented, already-understood issue,
   a deliberately-rejected alternative, or a fix already shipped for
   exactly the thing you're about to flag.
3. `git log --oneline` and recent commits — the project has been under
   active, well-documented iteration; recent commit messages explain
   *why*, not just *what*, for the most recent changes and are more
   current than this briefing.

## 3. Scope: what "core functionality" means here

Per `ARCHITECTURE.md`'s own module table, review in this priority order:

**Tier 1 — library modules (imported by everything, highest leverage
if wrong):**
| File | Owns |
|---|---|
| `grouse_data.py` | Disk layout, path resolution, year-matching policy. **Every path/raster convention resolves through here** — an error here propagates everywhere. |
| `models.py` | `GrouseResNet` (the model), feature registry, `road_dist_encode/decode`, `d4_tta_logits` (the single inference-side scorer). |
| `losses.py` | `FocalLoss`, `ANFullLoss`, `loss_logit_bias`. |
| `dataset.py` | `GrousePatchDataset` (point → patch), the patch cache, `StratifiedBatchSampler`. |
| `model_handler.py` | `GrouseModelHandler` — the actual training loop, checkpoint selection, TensorBoard instrumentation. This is the single largest and most complex file; give it the most time. |

**Tier 2 — pipeline entry points (thin orchestrators over Tier 1, but
where CLI-level bugs and flag-interaction bugs live):**
- `train.py` — training CLI, dataset assembly, ensemble/distillation orchestration
- `predict.py` — inference CLI, GeoTIFF/KMZ output
- `calibrate.py` — temperature scaling
- `pretrain.py` — optional SimSiam SSL warm-start

**Tier 3 — lower priority unless time permits:**
- Diagnostic/one-off scripts (`diagnose_*.py`, `inspect_point.py`,
  `check_*.py`, `find_tsd_contrast_points.py`, `tune*.py`)
- `legacy/` — explicitly superseded, imported by nothing, kept only for
  history. **Do not review this as if it were live code.**

## 4. Known invariants — verify code respects these, don't flag them as bugs

These are copied from `ARCHITECTURE.md` because a reviewer who misses
them will burn time on false positives. Read the full explanations
there; short version:

- **`ModelEMA.shadow` tensors must be written through, never replaced.**
  Rebinding `self.shadow = {...}` instead of using `load_shadow()`
  silently freezes the EMA average forever while training *looks*
  normal. This exact bug happened once already.
- **Adding/removing a feature is a geometry change** — model channel
  count derives from `FEATURE_SPEC` + whatever rasters exist on disk,
  so `--resume`/`--init-from` become invalid against older checkpoints
  when the feature set changes. This is intentional, not a missing
  compatibility shim.
- **`discover_features` intersects across regions** — a feature present
  for one region but missing for another is silently dropped
  project-wide, no error. Intentional (documented), but worth
  double-checking nothing downstream assumes a feature it can't
  actually rely on being present.
- **Checkpoints come in two formats** (wrapped `{state_dict, config}`
  vs. bare `state_dict`) — `config_to_model_kwargs` owns every geometry
  key and legacy fallback. Any new loader needs to go through this, not
  reimplement it.
- **`--select-min-delta` compares against the last SAVED checkpoint, not
  the running maximum** — deliberate, to filter noise-level
  "improvements." Don't flag as an off-by-one or wrong-comparison bug.
- **`--an-pos-weight` takes precedence over `--pos-neg-ratio`** for
  `--loss an_full`. If you see code that looks like it's ignoring one of
  these, check this precedence rule first.
- **`road_dist` is stored log-encoded**, not in metres — `road_dist_encode`/`decode`
  in `models.py` are the single definition. Anything that reports a
  distance to a human must decode first; anything that looks like it's
  treating the stored value as raw metres is a real bug.
- **`--dynamic-dropout` is a trend-following integrator, not a function
  of gap magnitude** — each epoch it only compares this epoch's
  val-minus-train gap to *last* epoch's, nudging dropout up/down by a
  fixed step. This is deliberate (see `model_handler.py`'s inline
  comment), and it means dropout trajectories can diverge meaningfully
  between two otherwise-similar runs due to path-dependence — that's
  expected behavior, not a bug, unless the step/comparison logic itself
  is wrong.

## 5. Known open issues / where to look harder

Unlike §4 (don't flag these), these are things a prior review session
identified as genuinely open or unresolved — worth extra scrutiny:

- **Persistent train/val overfitting.** Recent training runs show
  train accuracy ~99%+ against validation accuracy plateauing around
  65%, with the val-minus-train loss gap not closing even as
  `--dynamic-dropout` pushes dropout toward its ceiling. This may be a
  genuine capacity/regularization problem, or may partly reflect the
  presence-background label-noise ceiling described in §1 (background
  points aren't confirmed absences). If you can reason about which,
  that's valuable; if not, flag it as unresolved rather than assuming
  either explanation.
- **`--distill-from` is new and unverified against real data.** The
  most recent commit (`train.py`'s `--distill-from`/`--distill-alpha`,
  `dataset.py`'s `soft_labels=`, `model_handler.py`'s distillation loss
  blend) was written to let an ensemble collapse into one deployable
  checkpoint. It was verified with a **synthetic** dry run (fake region
  data, monkeypatched raster reads) proving the code runs end-to-end
  without shape/device errors — it has **never been run against the
  real pipeline or real data**. This is the single highest-value target
  for careful review: check the point-alignment logic between
  `build_datasets`' per-region/per-class dataframes and the soft-label
  arrays attached to each `GrousePatchDataset`, and the loss-blending
  math in `GrouseModelHandler._batch_loss`.
- **Ensemble/init-from/resume interactions.** `--resume` is explicitly
  documented as incompatible with `--ensemble > 1` (only resumes member
  0). `--init-from` **does** apply to every ensemble member, which was
  previously found to cause an unintended near-full-checkpoint reload
  for members sharing a pool type with the source (see `CHANGELOG.md`,
  the `06fe5fe` entry). Worth checking whether any other flag
  combinations have similar unintended-interaction risk that hasn't
  been audited yet.
- **`predict.py` has no multi-checkpoint/ensemble inference path.**
  Confirmed absent as of this writing. If `--distill-from` isn't judged
  sufficient long-term, this is the alternative gap to eventually close.
- **A prior TensorBoard screenshot showed two training runs
  (`030840_grouse_single_best` and `043215_grouse_single_best`, ~1.5h
  apart) that may have both been targeting the same checkpoint file** —
  never confirmed either way from within this environment (no process
  access to the actual training host). If you have any way to check for
  concurrent-write collision risk on `--save-path`, worth a look.

## 6. Environment constraints for the reviewer

- **No real raster data or trained checkpoints are available in a
  cloned/CI copy of this repo.** Per `.gitignore`, all data
  (`landfire_data/`, `data/`, checkpoints, caches) is excluded from
  version control by design. Training happens on a separate machine.
  **Assume you cannot execute training, prediction, or any script that
  touches real rasters** — review must be static (reading code,
  reasoning about logic, checking cross-file consistency), not
  execution-based, unless you've confirmed you have some other way to
  get real or synthetic data in front of the code.
- If you want to exercise code paths without real data, the pattern
  used to verify `--distill-from` (a fake `RegionData` implementing just
  `raster_years`/`raster_path`, plus monkeypatching
  `GrousePatchDataset._read_patch` to return synthetic arrays instead of
  doing real I/O) is reusable — it bypasses rasterio entirely while
  still exercising the real dataset/model/training code.
- `smoke_test_training.py` exists for a full pipeline smoke test but
  **requires real pipeline outputs on disk** (`landfire_data/`,
  evaluated/thinned/negatives CSVs) — it will not run in a bare clone.

## 7. What "comprehensive review" should cover

In priority order:

1. **Correctness bugs**, especially:
   - **Indexing/alignment bugs.** This codebase has a real history of
     exactly this class of bug (CRS mismatches producing all-nodata
     patches; a stale EMA frozen silently; TensorBoard tile
     normalization destroying magnitude in two separate files). Treat
     any place where an array, dataframe, or dataset is reordered,
     filtered, concatenated, or indexed by position as higher risk than
     average.
   - **Duplicated logic across files that could drift.** `predict.py`
     has already once carried a duplicate of a `model_handler.py` bug
     (documented in `CHANGELOG.md`). Actively grep for other
     near-duplicated logic between `train.py`/`predict.py`/
     `model_handler.py`/`calibrate.py` and check whether a fix in one
     place was actually mirrored in the other, or only looks similar.
   - **Silent fallback/skip behavior that should be loud.** Several
     parts of this codebase deliberately skip-and-report rather than
     crash (e.g. `load_backbone`'s shape-mismatch handling) — check
     that reviewer intuition doesn't conflict with these being
     intentional, but also check for places that skip *silently* where
     a loud failure would be safer (per this project's own stated
     preference, e.g. `_probe_first_point`'s constant-input check).
2. **Cross-file geometry/config consistency** — e.g., does everything
   that reconstructs a model from a checkpoint go through
   `config_to_model_kwargs` rather than re-deriving kwargs by hand
   (drift risk)?
3. **Efficiency/performance**, but only where it doesn't trade off
   against documented, deliberate choices (e.g. the batch-size/memory
   tradeoffs documented in `train.py`'s header comments, or the
   accumulate-on-device-then-sync-once pattern in the training loop —
   these are already reasoned about, not oversights).
4. **Security/robustness at data boundaries** — this is a research/ML
   pipeline, not a network service, so classic injection surface is
   low; more relevant here is path handling (raster path construction),
   any use of `eval`/`pickle`/`subprocess`, and checkpoint loading (are
   `torch.load` calls using `weights_only=True` where they should be?
   — some legitimately need `weights_only=False` for optimizer/scheduler
   state; check that's scoped correctly, not blanket).
5. **Documentation accuracy** — do `ARCHITECTURE.md`'s module
   descriptions and `CHANGELOG.md`'s invariants still match the code as
   it exists now? Flag drift.

## 8. Output format requested

- **Cite every finding as `file:line`.**
- **Rank findings by severity/confidence**, and be explicit about which
  findings you're confident are real bugs vs. which are worth a human
  double-checking (especially anything touching §5's unresolved areas,
  where you can't execute code to confirm).
- **Don't re-report anything already covered in `CHANGELOG.md`** as a
  new finding — check there first if something looks familiar.
- Prefer a small number of well-verified findings over a long list of
  speculative ones. If you're not confident something is a real bug,
  say so explicitly rather than asserting it.
