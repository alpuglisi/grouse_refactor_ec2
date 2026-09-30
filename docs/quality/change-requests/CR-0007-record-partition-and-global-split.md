# CR-0007: Partition records by state and run the train/val block holdout once over the pooled data

**Status: REVISED (v7) — awaiting re-review (`CLAUDE.md` §1.2).**
Nothing committed. All deliverables pending. The header read "v4" while
the body read v6 through two revisions; corrected in v7.

**Review history is incomplete, and that is a live §1.3/§1.4 defect, not
a formatting gap.** Seven reviews have been performed on this CR.
§ Review records verdicts for **Round 1 (2 reviewers) and Round 2
(2 reviewers)** only; the three later reviews — two intermediate rounds
and the most recent formal round — have **no recorded verdict or
disposition**. §1.3 forbids silently dropping a finding and §1.4 makes
quorum the sum of all reviewers who commented, so **this CR is not
approvable until those verdicts and dispositions are reconstructed from
the review records.** Stated here rather than left for a reviewer to find.

**The acceptance layer has been broken ten times across six revisions.**
The most recent formal round rejected v6 and named the unifying mechanism
no individual patch had addressed: *every acceptance row touching the
negative class measures a **count** (I8) or a **location** (I2, I3, I16b,
I19); none measures **composition** — I15 through I18 are all scoped
"positives only".* v7 is therefore a redesign of the acceptance layer,
not an eleventh patch to it.

### Revision note (v6 → v7)
v6 was rejected by a formal review (round 5) that named the unifying
mechanism ten breaks had shared. **v7 is a redesign of the acceptance
layer, not an eleventh patch to it**, produced from six parallel research
investigations run on the *faithful* sampler
(`inv_formalC_pool2.py` + `inv_formalC_lib.py`, which reproduces I6 =
6,230 exactly) rather than on `inv_fix_breaks.py`, whose approximation of
the negative draw is why v6's calibrations could not be trusted.

1. **The diagnosis was narrower than the defect.** The review said
   "I15–I18 are positives-only". Measured, the table had **no notion of a
   record set at all** for any distributional statistic, and the choice is
   **three fields — (class, subset, null population)** — each of which
   independently decides whether a real attack is seen. New PA-0021(f).
2. **I19 → I19′**, twelve cells with one family-wise `Z`. v6's single
   `max_r S <= 0.64` misses **7 of 11** attacks, and its stated margin was
   wrong: the faithful 600-seed fair max is **0.6172**, so 0.64 is
   **1.037×**, not "1.09× / 16 % both sides". Free-harm budget drops from
   **798** stranded positives to ≈150–240.
3. **A third instance of Break 1, one level deeper.** v6's I19 pools
   train and val positives *and* takes the nearest negative of any split;
   since blocking guarantees train negatives near val positives, the
   reading is systematically optimistic. A val-split-only attack strands
   **1,010 of 1,251 val positives** and v6 fires on 3 of 60 seeds.
4. **The composition axis added** (C1–C17). Breaks 10B and 10C pass the
   whole of v6 — 10C keeps **I8 exact** while NonVeg reaches 90.7 % of a
   cell, which is BUG-0004's mechanism ungated.
5. **The supply axis added** (SUP0/SUP-O/SUP-R). Pool-strip attacks from
   3 % to 20 % pass the **entire** draw-side table, inside the fair
   envelope; SUP-O fires at a **0.5 %** strip.
6. **I16/I16b need no frozen null** — an in-run permutation null costs
   205–630 ms and lands within 7 % of the frozen one. This removes them
   from the superseded-footing failure mode *and* from the BUG-0034
   hand-off.
7. **I16b made two-sided** (a feature-extremum split drives Moran
   *negative*: two attacks score -0.0275 / -0.0283, invisible to v6's
   one-sided form), and its block counts corrected **9,482/5,621 →
   9,093/5,232** (v6's came from a 26,808-candidate approximation).
8. **I17 demoted to OBS** — it passes at 0.0306 on maximally leaky pre-CR
   data, so it has zero regression power against BUG-0027/BUG-0029, and
   costs 8.4–24.3 s / 795 MB.
9. **I18 made per-region** — pooled reads 1.634 km and **hard-fails a
   correct pipeline**; the envelope was always the per-region one. v6's row
   named the class and not the pooling axis.
10. **I7(neg) recorded as carrying zero information** — it is an algebraic
    function of the positive split, numerically identical in the fair
    pipeline and all 22 attacks.
11. **I10 stays an OBS**, but recorded in the fixed `I10p10` form; the
    written 30 km form has two independent defects. It is **not** promoted:
    it adds no detection I19′ does not already have.
12. **Assertion (d) deleted entirely**, with its escape flag, banner and
    artifact-recording machinery — (d) **is** I10, so v6's only three
    implementing call sites implemented a retired gate.
13. **The `--regions` hole closed** — the largest gap in v6: under
    `--regions ME` the pooled gates silently collapse to within-region
    checks, *the pre-CR BUG-0027 condition*, and pass.
14. **`build_datasets` is not split.** The surgery is one guarded call at
    `train.py:244`; R1/R2/R3/R6/R7 are not applicable, R4/R5 bind. This
    removes the change the risk table called the riskiest in the CR.
15. **The candidate pool must be persisted** — it is discarded today, so
    every pool-referencing gate is unreachable from `train.py`. Two
    independent investigations reached this from different directions.
16. Corrections to this document's own numbers and citations:
    `build_datasets` is **`:238-317`** (v6 cited the loop span `:253-315`);
    the polygon path costs **21.9 s naive / 1.3 s with a pyogrio
    pushdown**, not "1.2 s"; the TIGER file is **EPSG:4269**, so
    `verify_partition()` must reproject or it joins across a datum; and
    the withdrawn BUG-0034 cost **"+6/+6/+9"** is replaced by the measured
    **ME 2,854 / NH 828 / VT 1,127**.
17. **PA-0021 and BUG-0033 re-pointed** to a bookkeeping batch landing
    *before* this CR, since this CR cites both in its own body; PA-0021's
    lineage corrected from PA-0018 to **PA-0016**.

### Revision note (v5 → v6)
v6 was produced after a formal review rejected v5's acceptance layer.
1. **BUG-0034 DESCOPED** — diagnosed here, fixed in its own CR. The real
   post-partition cost is ME 2,854 / NH 828 / VT 1,127 (a 63 % cut to NH)
   and it moves I6 to 4,809 ± 2, which would have invalidated every
   calibrated gate before a reviewer had seen one on the new footing.
2. **I19 made per-region** and maximised across regions, at `≤ 0.64`.
3. **I16b added** — Moran's I over an all-record-occupied block set, to
   cover the geography of the *negative* split, which nothing had gated.
4. Every row I15–I19 was made to name its record set (the Break 2 fix).

v7 shows 2 and 4 were both incomplete: a max over region-heterogeneous
cells is slack for every region but the worst, and "record set" is three
fields rather than one.

### Revision note (v4 → v5)
v5 **folded the BUG-0034 fix into this CR** (restricting positives to
2020+ so both classes share a year floor) on the strength of a
"+6/+6/+9 training positives, ~0 cost" measurement, and set I19 as a
provisional `≤ 0.55`. Both were withdrawn in v6 — the cost figure had been
measured on the pre-partition per-region pipeline, and `≤ 0.55` false-fails
**100 %** of fair draws on the post-fix footing.

### Revision note (v3 → v4)
v3 was rejected. Rather than patch the acceptance layer a fourth time,
five research agents calibrated every gated statistic against its
sampling distribution (400–1,000 draws) and against seven distinct
defect families. **The result deletes more of the table than it adds.**

1. **I7b and I10 deleted as gates** — measured, no separating threshold
   exists for either. v3's hard ±2 pp I7b gate rejects **32.7 %** of
   correct pipelines while the attack passes it *always*, scoring better
   than a fair draw. It was inverted, not mis-tuned.
2. **I6 tightened 40×** (±2 % → ±10 records); **I8 becomes an exact
   predicate**, leaving threshold territory entirely.
3. **A location gate added** — Moran's I of the validation indicator,
   the axis every previous version left unconstrained.
4. **I14 demoted** from "the governing invariant" to a provenance and
   canonical-form gate, and its (ii) half shown evadable in one line.
5. **Hash-derived ordering adopted** over the canonical sort, which is
   insufficient against a pandas version bump.
6. **Stratification assessed and re-scoped** — region-level closes zero
   percent of the hole; 30 km × region closes it by construction, with
   three stated conditions.
7. **BUG-0034 recorded** — the year asymmetry this CR was designing
   around turns out to be an unrecorded defect, and it weakens v3's
   justification for splitting `build_datasets`.
8. Every correction previously parked in an appendix is now folded into
   the body. A reviewer found 9 of 14 dispositions were prose-only and
   one was false; that is fixed rather than re-promised.

### Revision note (v2 → v3)
Round 2 returned APPROVE WITH CHANGES (implementation lane, 1 blocking)
and **REJECT** (fresh, standalone, 3 blocking: the acceptance set broken
twice, §1.3/§1.4 unsatisfied, deliverables not executable in order). v3
responded by *adding* gates — an I7b validation-fraction gate at ±2 pp, an
I10 block-coverage gate, and an I15 threshold of 1 pp — and by planning
the `build_datasets` load/construct split that lifted
`filter_by_year_gap` out of the per-region loop. It also withdrew the
`coord_uncertainty_m` example as inert (measured non-null in **0 of
265,212** candidate rows).

v4 measured all three of v3's new thresholds and deleted or loosened every
one: I7b rejects **32.7 %** of correct pipelines while the attack passes it
*always* (inverted, not mis-tuned), I10 has no separating threshold, and
I15's 1 pp false-fails 3.75 %. This is the first revision where adding
gates made the layer worse, and it is why v7 re-derives rather than
patches.

### Revision note (v1 → v2)
Two reviewers returned on v1: APPROVE WITH CHANGES (1 blocking) and
REJECT (1 blocking). A third review was still running when this revision
was written and its findings are not yet incorporated.

1. **Assertion (d) was a tautology and is replaced** (blocking). Given
   (a), each class's per-region `state` histogram is `{R: 1.0}` by
   construction, so (d)'s gap was identically **0.000 pp for any
   negative draw whatsoever**. A reviewer built a conformant pipeline
   that drew negatives only from the southern half of each state — every
   gate green while the positive/negative spatial support collapsed,
   reproducing BUG-0029 at ~15× its pre-CR magnitude. v1 had deleted the
   check that catches this (the per-region occupied-block support test)
   and kept only the one that cannot.
2. **Pooled `concat` index discipline is now specified** (blocking).
   `weighted_take` uses `subpool.loc[idx]`; pooling the three candidate
   frames without `ignore_index=True` makes labels repeat and `.loc`
   returns every match — overshooting the negative quota with duplicated
   records, i.e. reintroducing double-weighting on the negative side by
   way of the fix for it. Demonstrated: a 3-element pick returned 6 rows.
3. `verify_partition()` now has an implementing call site for the
   **negative** class; v1 placed it only in `analyze_grouse`, which never
   sees negatives, while both known exceptions are negatives.
4. **The NH box question is resolved cheaply instead of deferred**: 721
   of 69,219 NH candidates lack a full window, and v1 replaced the
   selection step, so drawing one was sampling luck and I5 would have
   failed with no remedy.
5. Preservation rules R5–R7 added; R1's remedy made structural.
6. Per-region validation fraction, a parameter manifest, and a
   recorded-vs-recomputed `block_id` check added to the acceptance set.
7. Several of v1's own numbers corrected — see "Corrections to v1".

### Corrections to v1
- **I5's "NH 4 / 6"**: `--jitter` defaults to **0** (`train.py:462`), so
  `read_size == img_size == 64` and the real count is **4**. The 6
  requires jitter 8, which no run uses. v1 also failed to say which
  record set "today" refers to: it is the **pre-partition** NH file
  (2,244 rows); the post-partition set (1,079) is **0**, which is a
  point in the partition's favour that v1 stated too loosely to land.
- **`analyze_grouse.py:439`** — the `MIN_VALID_FRAC` check is at
  **`:444`**; `:439` is the loop head.
- **§5's "measured effect: none"** for pooled negative thinning is
  true for the 30 m constraint (0 cross-state candidate pairs under
  30 m) but overstated: pooling still changes the *retained* set,
  because the greedy thinner shuffles once over 35,678 records instead
  of three times over ~12,000.

**Supersedes part of CR-0006**, which bundled this with raster coverage
fixes and a retrain. CR-0006 reached revision 3 and was rejected by both
of its fresh reviewers; five reviews produced 100+ concerns. The
partition design in it survived every attack; the raster half and the
acceptance layer did not. This CR carries the surviving half alone.
CR-0008 carries the raster work; CR-0009 carries the retrain. IDs follow
`CLAUDE.md`'s flat counter — CR-0006 stays on the register, marked
superseded, and is not renumbered.

## Scope
Fix BUG-0027 (cross-region train/val leakage) and BUG-0029 (mismatched
positive/negative spatial support) by making region membership a **state
partition** and running the spatial block holdout **once over the pooled
records**, with dataset-build assertions that make both classes
detectable.

## Why now
Both defects are confirmed on real data and independently reproduced by
four reviewers:

- **522 of 1,674 pooled validation positives (31.2 %) are also pooled
  training positives at the identical coordinate.** Within a region the
  block holdout works (0.0 % of val positives have a train positive
  within 30 m); pooled it is 31.7 %.
- **A further 1,131 positive coordinates are duplicated inside a single
  split** — straight double sample-weighting. (CR-0006 cited only the
  522, understating the duplicate problem threefold.)
- 1,128 of the NH region's 2,244 positives lie outside New Hampshire,
  against **0** of its negatives by the `state` column (1 by polygon).

Every validation number in this repository is therefore unusable,
including the `0.811` best-rank figure used to choose between
checkpoints.

**Not why now:** the Errol map symptom the investigation started from is
**already fixed** by `bf8d31a` — `P(ME pixel > NH pixel)` 0.8513 → 0.5400
on the reported map's checkpoint, with the NH side unmoved. This CR does
not fix that symptom; CR-0009 exists partly to prove it is still fixed
after a rebuild.

## The change

### Root causes
- **BUG-0027:** a spatial computation that must be global (the block
  holdout) is run on per-region subsets selected by overlapping labels,
  so its guarantee holds within a region but not across the pool.
- **BUG-0029:** the two label classes are drawn from differently-shaped
  regions — positives by bounding box, negatives by state — so their
  spatial supports do not coincide, and nothing compares them.

Both have one cure: partition records by **state**, so positives adopt
the definition negatives already use.

### 1. `regions.py` — membership key and shared constants
- **Partition key: the existing `state` column.** Verified: `state`
  equals the dissolved TIGER-2023 county polygon for **43,024 of 43,024**
  raw sightings, 0 outside all polygons, and one reviewer measured **max
  distance-to-own-polygon 0.0 m**. For positives this is evidential —
  `analyze_grouse.load_all_sightings:167` takes it from the filename,
  and those files are written by `sightings.py:132` grouping a GBIF
  export by `stateProvince`, so it is GBIF's per-record value.
  **For negatives it is definitional**, not evidential:
  `get_negatives.py:268` passes `stateProvince` as a query parameter and
  `generate_negatives.py:302` carries it into the column. Recorded as a
  known limit, not presented as verification.
- **`verify_partition()`** — new, mandatory in `analyze_grouse.py`,
  polygon-based, source pinned to `data/roads/tl_2023_us_county.zip`
  dissolved by `STATEFP`. The generalized `cb_*_20m` boundaries are
  forbidden (they generate false disagreements). Predicate: `within`.
  **It must be given a disposition rule before it can pass** — see
  "Known exceptions" below.
- **Constants centralised here** (PA-0001), each currently duplicated or
  drifted:
  - `STATE_FIPS` — `generate_road_distance.py:115` and
    `diagnose_road_bias.py:71`.
  - `MIN_SPACING_M = 30` — `prepare_training_data.py:49` and
    `generate_negatives.py:71`; §3 fuses the two thinning steps, so they
    must not be able to drift.
  - `BLOCK_SIZE_M = 3000` — currently `prepare_training_data.py:52`,
    imported by `generate_negatives.py:60`. Remove
    `prepare_training_data.BLOCK_SIZE_M_DEFAULT` once this exists: two
    names for one constant is the mechanism being centralised against.
  - **`TIGER_YEAR = 2023`** — **already drifted**:
    `generate_road_distance.py:114` reads **2025** while
    `diagnose_road_bias.py:72` reads **2023** and every cached file is
    2023. Three reviewers flagged this; two prior revisions recorded the
    disposition as "accepted" and did not make the edit. It lands here.
    Note the coupling: CR-0008's `road_dist` acceptance gate must pin the
    same vintage as the generator, or it produces real-looking failures.
  - **`BLOCK_ORIGIN_5070 = (0.0, 0.0)`** — new, and the most important.
    `assign_spatial_blocks:95` and `compute_block_ids:104` must agree on
    it *exactly*; if they drift, a positive and a negative at the same
    spot get different block ids and BUG-0027 is recreated. CR-0006
    specified a "global origin" without naming it as a shared constant,
    and a reviewer demonstrated a drifted-origin pipeline that passed
    every one of its acceptance checks.
- `BOXES` is documented as **raster request extents only**. Its NH entry
  does not cover the NH polygon (polygon reaches −70.5751, box −70.600;
  0.0299 % of the state outside, 0.0665 % including a 32 px margin).
  Membership no longer depends on it, but §7 and CR-0008 still sample
  over it, so widening NH to ≈ −70.563 is **raised as an open question**
  — the cost is re-downloading every NH raster, since `BOXES` is the
  download AOI (`download_rev.py:22`).

### 2. `analyze_grouse.py` — partition and consistent availability
- `clip_to_region` (`:198-203`) selects on `state == region`, writes an
  explicit `region` column, and calls `verify_partition()`. An unknown
  `state` value is an **error**, not a silent zero-row drop.
- `background_envelope_sample` (`:411`), `background_nonveg_rate`
  (`:324`) and the KDE fit set are clipped to the partition. Measured
  in-state share of the availability sample *after* the `dropna` and
  non-veg drop those functions apply: **ME 95.9 %, NH 53.2 %, VT
  55.2 %** — so the `Selection_Ratio` bias is severe for NH and VT and
  near-nil for ME. Because this drops ~47 % of the NH/VT sample, the
  draw must **rejection-sample back up to `n_samples`**, and
  `:439`'s `n_valid >= n_samples * MIN_VALID_FRAC` check must be
  re-expressed against the clipped `n` or it silently tightens ~2×.
  Without that, judgeable envelopes fall (measured NH 50→48, VT 48→46 at
  `MIN_AVAIL_BG = 15`), pushing envelopes to `NEUTRAL_WEIGHT`.
- geopandas becomes a **declared dependency of the analysis path**.

### 3. `prepare_training_data.py` — one global grid, one draw
- `assign_spatial_blocks` (`:85-114`) loses its `box` argument and
  anchors on `BLOCK_ORIGIN_5070`.
- `main()`: load every region → concatenate → **thin once over the
  pooled records** → assign blocks and draw validation once → write each
  region's files plus **one global `block_assignments.csv`**.
- `--regions` subset runs become diagnostic-only and refuse to write,
  because a subset run would emit a global block table containing only
  that subset's blocks.
- Dead code removed: `--habitat-only` is `action='store_true',
  default=True` and can never be switched off (the habitat filter at
  `:149-150` becomes unconditional); the `rng` at `:102` is unused
  because the draw uses `block_counts.sample(random_state=seed)`.
- **Expected pooled positive count ≈ 6,230**, reproduced independently
  by three reviewers. A result near **6,508** indicates the habitat flag
  was taken from a foreign region's grid rather than the record's own —
  that is a diagnostic, not an acceptable alternative.

### 4. Duplicate scripts (PA-0002)
`clean.py`, `legacy/gen_negs.py` and `legacy/audit.py` are **executably
identical** to their live counterparts — AST-normalised diff with
docstrings stripped gives **0 / 0 / 2** differing lines, the 2 being a
literal moved to a shared import. All three get runtime `SystemExit`
guards.

The hazard is specific: `legacy/gen_negs.py` writes the *same*
`data/negatives/*.csv` paths, reads `block_assignments` and computes
region-local block ids. After this CR it would read the global file
while emitting local ids — the id ranges do not overlap at all, so 100 %
of candidates fall through to hash splitting, silently reintroducing
BUG-0027's leakage with no error.

**Also in scope, found during CR-0006's review:** `legacy/download.py`
and `legacy/download_more.py` are un-guarded, runnable, **diverged**
copies writing the same `data/landfire/{region}_{year}_{feature}.tif`
paths as `download_rev.py:82`. BUG-0015's remediation backported a fix
instead of deprecating the copy, so PA-0002 was violated by the change
recorded as satisfying it. Both get guards; PA-0002's and PA-0014's
Swept? rows are corrected.

### 5. `generate_negatives.py`
- `compute_block_ids` (`:98-107`) loses `box`, uses `BLOCK_ORIGIN_5070`.
- Reads the single global `block_assignments.csv`. **The per-region
  `block_assignments_{region}.csv` files are deleted and the per-region
  `PATH_TEMPLATES` entry removed** — leaving both namespaces resolvable
  is what makes the drifted-id failure reachable.
- 300 m buffer queries **pooled** grouse locations.
- Thinning pooled. **Measured effect today: none** — pooled negatives
  have 0 pairs under 30 m, because the per-state GBIF queries already
  partition the candidate coordinates. It is done for PA-0018
  conformance, not because it fixes a measured defect, and this CR says
  so rather than implying otherwise.
- `process_region` (`:133-324`) must be **split into a pooled pass and a
  per-region pass**: hygiene, thinning and the buffer become pooled,
  while envelope extraction (`:198-205`), metrics (`:227`) and the 1:1
  targets (`:250-251`) stay per-region. Pooled candidates are assigned a
  region by the **same `state` key** §1 defines. Verified: all three
  candidate files carry a `state` column holding only the 2-letter code.
- **Every pooled `pd.concat` uses `ignore_index=True`** — including the
  existing ones at `:289` and `:301`. `weighted_take` (`:267-274`) does
  `subpool.loc[idx]`; with repeated index labels `.loc` returns every
  match, overshooting the quota with duplicated records. Demonstrated:
  pooling two 4-row frames without `ignore_index`, a 3-element
  `rng.choice` returned **6 rows**. (Converting `weighted_take` to
  positional selection is an acceptable equivalent.)
- **`verify_partition()` runs on the pooled candidate frame here**, with
  the § Known-exceptions rule applied. §1 places the positive-side call
  in `analyze_grouse.clip_to_region`, which never sees negatives — and
  both known exceptions are negatives.
- **Candidates without a full `img_size + 2·jitter` window in every
  feature raster they would be read from are dropped before sampling**,
  and the count recorded (measured today: NH **721** of 69,219, ME 2,
  VT 0). This makes I5 unfailable by construction and resolves the NH
  box question (§1) without re-downloading any raster.
- Which pass owns the block-id/split step (`:241-247`) must be named.
  Note the semantics change: `val_fraction = (blocks['split']=='val').mean()`
  (`:243`) becomes a **global** block-level rate. Measured: per-region
  today ME 0.205 / NH 0.214 / VT 0.213; global **0.190**. That shifts the
  hash-split val rate ~2 pp for every candidate in a block holding no
  positives (~65 % of them).
- `binners = fit_scheme_binners(...)` (`:220-222`) is fitted on that
  region's `evaluated`, which §2 makes state-only — so the quantile edges
  move and every candidate's `envelope_id`, hence its weight, changes.
- Preserve: the boolean `mask` in the extraction loop (`:200-205`) mixes
  positional and label indexing and is correct only while `mask` stays
  boolean; and the "candidate file absent → return" path (`:141-143`).
- `:153`'s bare `except Exception` re-raises `MissingDataError` (it is
  the only thing that block currently swallows; the residual `except`
  logs exception type and traceback per PA-0011). This is what turns a
  half-finished rebuild into "Skipping" over stale negatives.
- `:60` imports `BOXES`/`BLOCK_SIZE_M_DEFAULT`/`thin_by_min_distance`
  from `prepare_training_data`; re-point the constants at `regions`.

### 6. `train.py` — standing assertions
All run **pooled**, and **before `filter_by_year_gap`** — reverted in v6
when BUG-0034 was descoped. The filter is *not* a no-op in this CR, so
the pre-filter placement stands, and with it the load/construct split.

Why the placement matters: the filter drops 22–24 % of positives and
**0 %** of negatives. That asymmetry is not a property of the data — it
is BUG-0034, diagnosed below and fixed in the CR that follows this one.
Until then the assertions must run on the frame where both classes are
still comparable.

**One claim corrected.** The research proposing this fix said it would
remove the `build_datasets` load/construct split entirely. It does not,
and the CR should not repeat that. Assertions (b) and (c) are set
operations **across** regions — cross-region coordinate collisions and
block disjointness cannot be evaluated inside a per-region loop
iteration — so a pooling pass is required whatever the filter does.

What the fix does change is the **shape and risk** of that pass. With a
no-op filter the load pass becomes a **read-only pooling pass placed
before the existing loop**, which is left untouched with
`filter_by_year_gap` still inside it. v3's version had to lift the
filter out of the loop and re-thread the construct half around it.
**Only R4 and R5 bind (v7).** Because the surgery is one inserted call
rather than a restructuring, R1, R2, R3, R6 and R7 describe hazards of
work that is **not performed** — they were written against v3's plan of
lifting `filter_by_year_gap` out of the loop and re-threading the
construct half. R1 in particular is a *description of the status quo*:
`train.py:288-289` already does its structural form
(`train_parts += [p_tr, n_tr]; train_labels += [p_tr.labels,
n_tr.labels]`). R4 (keyword-with-default signature) and R5 (never mutate
the cached frames — `pooled_record_frame` builds one
`pd.concat(..., ignore_index=True)` and touches nothing it read) are the
two that remain live. R1/R2/R3/R6/R7 are recorded **not applicable under
the additive design**, not silently dropped.

Two gates genuinely cannot be hoisted out of the loop — **I5 and I17**,
both of which need `rd` and are per-region. They run **inside** the loop
after `filter_by_year_gap`, accumulating into a failure list raised
before `ConcatDataset`. That is still not a restructuring.

### BUG-0034 — DESCOPED (v6): diagnosed here, fixed in its own CR
The 22–24 %/0 % figure is **100 % a consequence of two acquisition
parameters**, not a property of the data. Positives are fetched from
**2016** (`sightings.py:21`, `ebird.py:22`), negatives from **2020**
(`get_negatives.py:227-228`). LANDFIRE exists only from 2022, so at
±2 years the filter's accept set is exactly `year ≥ 2020` — and the
dropped set is *identically* `{year < 2020}`: **1,973 positives
(23.59 %), 0 negatives**, verified.

**Decision, v6: DESCOPED.** v5 folded the fix into this CR. A formal
review showed that was wrong, and the reversal is recorded rather than
quietly undone.

The v5 cost figures were measured on the **pre-partition, per-region**
pipeline — not the one this CR builds. On the post-partition pooled
footing the real numbers are:

| | v5 stated | measured on this CR's pipeline |
|---|---|---|
| training positives | +6 / +6 / +9 | ME 2,854 / **NH 828** / VT 1,127 |
| records leaving thinning | ~1,911 | 1,472 |
| I6 target | 6,230 ± 10 | **4,809 ± 2** |
| I19 gate ≤ 0.55 | "provisional" | fair envelope **[0.5820, 0.5974]** — false-fails **100 %** of fair draws |

So the fix would have moved **NH to 828 — a 63 % cut** in the region
this investigation is about, a fact v5 never stated — while invalidating
the acceptance layer this document has been rejected over five times,
before any reviewer had seen a gate calibrated on the new footing. v5
itself wrote "if the rebuilt fair max rises 5 % the gate inverts exactly
as I7b did". It rises 11 %.

**The diagnosis stays here** (it is what makes §6's placement decision
legible) **and the fix moves to its own CR, sequenced immediately after
this one.** The efficiency argument for folding it in — avoid rebuilding
the splits twice — is real but is outweighed: gates calibrated against a
superseded footing are not reviewable.

**It must be at selection, not acquisition.** Cutting the *source* years
would shrink the 300 m exclusion buffer
(`generate_negatives.py:181-186`), which is built from all
`evaluated_sightings`, and would admit negatives at sites with
2016–2019 grouse records. The records stay on disk, so the decision is
reversible.

**Consequence the acceptance table inherits.** ~1,911 records leave the
*thinning input*, so I6's target and every fair-draw envelope computed
on the thinned set — I15, I16, I18, I19 — **move**. They must be
re-derived on the post-decision record set before any gate is frozen.
I19 was already marked provisional for the same reason; this extends it
to the rest.

It is a **choice, not a data limit**: `me_sightings_2016.csv` carries the
same GBIF dataset key as `get_negatives.py`, the same state filter and
pre-2020 years, and was pulled an hour before the negatives fetch chose
not to request them.

Two consequences nobody recorded. **The documented 1:1 balance is
silently broken** — train 5,120/6,691 and val 1,272/1,674, prevalence
**0.4335 / 0.4318** against a designed 0.5000, and `calibrate.py` fits
its Platt bias on that. And **a vintage→label signal survives into
training at AUC 0.6365**, the hazard `ARCHITECTURE.md:193-198` documents
the project as designing against *within* a feature.

This is **BUG-0029's temporal twin** — same mechanism, one key away in
the same query dict — and it is the **first and only measured live
instance** of PA-0020's broadening, replacing the `coord_uncertainty_m`
example withdrawn in v3 as inert. It needs its own record: **BUG-0034**.
**The "+6/+6/+9, ~0 cost" figure is WITHDRAWN (v7).** It was measured on
the **pre-partition per-region** pipeline. On the pipeline *this* CR
builds, restricting positives to 2020+ costs **ME 2,854 / NH 828 /
VT 1,127** training positives — a **63 % cut to NH**, the region under
complaint — and moves I6 from 6,230 to **4,809 ± 2**. That is why
BUG-0034 is descoped to its own CR (below) rather than fixed here.

`build_datasets` is **`train.py:238-317`** (`def` at `:238`, `return` at
`:316-317`). v6 cited `:253-315`; `:253` is the **`for region_i, region`
loop head**, not the function — the span was the loop's, and the
"Corrections to v2" section already had this right while §6 did not.

**No split is required (v7).** Everything the pooled gates need —
`longitude`, `latitude`, `state`, `year`, `split`, class, region — is in
the four CSVs per region *pre-filter*, and `RegionData._load_csv` caches
by `(kind, kwargs)` while `GrouseData.__getitem__` caches `RegionData`
per region. So the pooling pass reads 12 CSVs (**measured 120 ms
including the 4326→5070 reprojection**) and the untouched loop then
re-reads nothing. The change is **one guarded call inserted at `:244`**;
the loop body and the return contract are not touched. The failing path
must raise **before any `GrousePatchDataset` is constructed**, which this
placement gives for free — it precedes even the one
`_score_teacher_probs` builds at `train.py:218`.

- **(a) Partition:** every positive and every negative in region R has
  `state == R`. Exact, no threshold, no geopandas.
- **(b) Disjointness:** no coordinate rounded to 5 dp appears in both
  pooled splits, evaluated per class. *(Restored — CR-0006 v3 deleted
  this while rewriting §6, leaving BUG-0027 with no standing
  enforcement at all.)*
- **(c) Block disjointness:** no block holds both a train and a val
  record, either class — **computed by recomputing block ids from
  `longitude`/`latitude` against `BLOCK_ORIGIN_5070` and
  `BLOCK_SIZE_M`, never from the recorded `block_id` column.** The
  column form is a tautology: `split` is derived as a pure function of
  the recorded id, so grouping by it returns 0 for any pipeline,
  correct or not.
- **(d) Spatial support:** per region, the fraction of 30 km blocks
  occupied by positives that hold **no** negative, on a grid anchored on
  `BLOCK_ORIGIN_5070`, computed from lon/lat over the pooled
  pre-`filter_by_year_gap` frame. **Threshold ≤ 0.15.**

  v1 used a per-region comparison of the two classes' `state`
  histograms at ≤0.5 pp. That is **identically zero given (a)** — a
  re-test of (a), not a support check — and a reviewer passed it while
  drawing every negative from the southern half of each state.

  Calibrated across 5 seeds against a fair draw and that skewed draw,
  rather than from one realisation:

  ```
               ME       NH       VT
  fair  max  0.0252   0.0513   0.0250
  skew  min  0.6975   0.5897   0.4000
  pre-CR     0.0484   0.3220   0.2500
  ```

  **This gate fails NH and VT on today's data and does NOT fail ME**
  (0.0484 sits below the fair-draw ceiling of 0.0513, so no threshold
  can both pass a legitimate draw and fail it). That is acceptable only
  because **(a) catches ME's actual defect exactly** — 137 out-of-state
  positives against 0 out-of-state negatives. (a) sees out-of-state
  imbalance and is blind to within-state skew; (d) is the reverse.
  Neither alone is sufficient and the CR does not claim otherwise.
  **Re-measure both endpoints on the rebuilt negatives before freezing
  0.15.**

Three callers execute these: `train.py:980`, `calibrate.py:351`,
`bench_pipeline.py:95`. **All four hard-fail on any pre-CR dataset** —
(a) on 137 + 1,128 + 717 out-of-state positives, (b) on 522, (c) on 882,
(d) on NH 0.322 / VT 0.250 — so the three entry points become unrunnable
against the current data, which this CR's own test plan requires and
CR-0009 needs for a baseline.

**Assertion (d) is deleted, and the escape machinery goes with it (v7).**
(d) **is** I10, which this CR itself retires to OBS because no separating
threshold exists. So v6's only three implementing call sites implemented
a **retired gate**, and the (d)-scoped escape flag, its banner and its
artifact-recording machinery were all built for it. (a)–(c) stay
unconditional. Deleted: the escape mode, the flag, the banner, the
recording requirement.

**No escape mode is needed for the rest, measured.** I15 (8.13 pp),
I16 (z = 6.48 / 5.71), I16b (z = 10.22 / 8.37), I18 (pooled 1.634 km) and
I19 (NH 0.6863) **all hard-fail pre-CR data too**, so they join (a)–(c)
as unconditional gates. Only I17 passes pre-CR data — see its row.

**Cost was misstated (v7).** v6 said "the polygon path measures 1.2 s".
That is `read_file` **alone**. `dissolve(by="STATEFP")` over all 3,235 US
counties costs a further **19.9 s and peaks at 489 MB** — naive total
**21.9 s**. Filtering to the three states before dissolving gives
**1.8 s / 461 MB**; a pyogrio `where="STATEFP IN ('23','33','50')"`
pushdown gives **1.3 s / 167 MB**. The pushdown form is mandatory, not an
optimisation.

**`verify_partition()` must reproject.** The TIGER county file is
**EPSG:4269**, not 4326 (verified: `tl_2023_us_county.zip`, 3,235
features). Without a `to_crs`, a hard-fail gate performs its point-in-
polygon join **across a datum**. Sub-metre here, but it is unstated in
v6 and it is a gate that blocks the pipeline.

### 7. `train.py` — `sample_background_points`
`:120-165` draws assumed-negatives from raster row/col pairs across the
region's **box**, in any state — BUG-0029's mechanism in the file this
CR edits. Dormant at the `--an-background 0.0` default (`:739`).
Brought under the partition; the `attempts < 40` /
`m = max(64, 2*(n-len(lons)))` oversample budget (`:145-149`) must be
raised to absorb a ~47 % rejection rate, or the `SystemExit` at `:161`
becomes reachable. `:141`'s `bad = set(NODATA_SENTINELS) | {nodata, 0}`
conflates 0 with nodata — a live PA-0006/BUG-0017 instance in this
function. **Deferred, not fixed here**, and allocated **BUG-0032**: it is
dormant at the `--an-background 0.0` default, and fixing a nodata
conflation inside a CR about record membership would mix two mechanisms.
An either/or is not a deliverable, so the decision is recorded.

### Preservation rules for the `build_datasets` split
Not optional detail — the failure mode is silent.

- **R1 (structural, not asserted).** Derive the label array *from* the
  parts list after the loop — `train_labels =
  np.concatenate([p.labels for p in train_parts])` — and the failure mode
  ceases to exist. `labels` is a cheap property (`dataset.py:446-453`,
  no raster I/O). Keep `assert len(train_labels) == len(train_ds)` as a
  belt, and forbid reordering `train_parts` after the labels are derived.
  Why it matters: `StratifiedBatchSampler` (`dataset.py:504-510`) uses
  the label array to compute index sets and **never compares
  `len(labels)` with `len(train_ds)`**; labels are `np.repeat(base, 4)`
  under `expand_rotations` (`dataset.py:453`), so a load pass that
  builds labels from dataframes yields a 1× array and **three quarters
  of the training set is silently never sampled**. A hand-maintained
  invariant plus a boundary spot-check is not enough — the spot-check is
  evadable (for parts `[A(1,len 4), B(0,len 4)]` the array
  `[1,0,1,1,0,1,0,0]` matches at both boundaries and is wrong inside).
- **R2.** The construct pass stays per-region, and soft labels are
  computed from the already-filtered frame. `_score_teacher_probs`
  (`train.py:200`) reads patches from *that region's* rasters, so a
  pooled frame cannot be scored. Length is validated
  (`dataset.py:90-96`); **order is not**, so a same-length permutation
  silently misattaches distillation targets.
- **R3.** Background sampling keeps `enumerate(regions)` position and
  the **filtered** count — `n_bg` uses the filtered frame and
  `seed = seed + region_i` (`:291-297`).
- **R4.** The return contract stays `(ConcatDataset, ConcatDataset,
  np.ndarray)`; new parameters keyword-with-default.
- **R5.** The load/assertion pass must **not mutate the frames it
  reads**. `RegionData._load_csv` (`grouse_data.py:237-241`) returns the
  **cached DataFrame object itself**, not a copy — `training_frame`
  defensively `.copy()`s at `:449` for exactly this reason. The
  assertions need derived columns, including a **recomputed `block_id`**
  for (c), and the positives CSVs already carry `block_id` and `split`.
  Assigning onto a frame from `rd.positives(...)` silently overwrites the
  recorded column in memory for every later reader in the process — the
  assertion built to detect id drift would create it. Work on
  `pd.concat([...], ignore_index=True)` copies.
- **R6.** `filter_by_year_gap` stays **per region**: it resolves
  `rd.raster_years(f)` (`train.py:179`) and `raster_path`'s
  empty-vintage fallback is per region. The year sets happen to be
  identical across all three regions for all 15 features today, so
  pooling it is harmless now and would break silently on the first
  single-region re-fetch.
- **R7.** Preserve the train/val asymmetry. Train datasets get `**aug`
  (`cache_dir`, `jitter`, `augment`) plus `soft_labels`; validation gets
  `cache_dir=` only (`train.py:278-315`, "Validation is never augmented"
  at `:307-309`). Collapsing both into one shared constructor is how a
  randomised validation set ships, and nothing downstream would raise.

## Known exceptions that must be dispositioned before the gate can pass
`verify_partition()` is mandatory and fail-hard, and **two negative
records are documented to fail it**: `(-70.92538, 43.3258)` filed NH
with an ME polygon, and `(-67.10082, 44.501766)` filed ME and inside no
polygon at all. The candidate pool holds 6 such records of **35,678** (the code dedups at 5 dp).
Positives: **0 of 43,024**.

This CR must choose one and record it: drop them, relabel to the
polygon, or carry an explicit audited exception list. Until then the
gate is self-contradictory — it cannot be satisfied and cannot be
skipped. This is stated as an open decision, not an oversight.

## Impact
- **Every existing checkpoint and every recorded metric stops being
  comparable.** Calibration must be refit (CR-0009).
- **Dataset size and shape change**, measured on the current
  `evaluated_sightings_*.csv`: 8,422 pooled habitat rows → keep the row
  from the record's **own state** file → habitat filter **6,411** →
  one pooled 30 m thin → **6,230**. (The chain "8,422 → 6,702 unique →
  6,230", stated through v3, actually yields **6,508** — the value this
  CR elsewhere calls a wrong-grid diagnostic. Three reviewers and the
  author reproduced the error independently.) Of those unique
  coordinates, **1,720** appear in more than one region's file and
  **291** appear *only* in a foreign region's file. Rows whose filing
  region differs from their `state`: **2,011**.
  *(CR-0006 stated "1,012 unique habitat positives change region"; that
  figure reproduces under none of these definitions and is withdrawn.)*
- **Per region, positives fall sharply** — this is the number CR-0006
  omitted, and it matters most for the region under complaint:
  post-partition, after one pooled thin: ME **3,659**, NH **1,079**
  (−52 %), VT **1,492**. (1,116 is the *state composition of NH's own
  file* and discards the 137 + 717 NH-state records held in the ME and
  VT files; it was quoted in three places through v3.) With 1:1 negatives
  the NH dataset roughly halves.
- **Reassigned records change feature values, not just membership.**
  Each moves to a different local Albers grid; across coordinates
  present in more than one region's file the same ground point already
  disagrees on `evt` for 29.5 %, `evh` 36.3 %, `evc` 41.0 %,
  `nonveg_landcover` 12.2 %. So `envelope_metrics_*`, `bin_tuning_*`,
  `spatial_zone`/`env_zone`, the KDE surfaces and the negative weighting
  all change, and the habitat filter's own output changes — which is why
  no exact post-rebuild count is promised.
- **Consumers**, all verified at `path:line`: `get_negatives.py:128`,
  `organize_project.py:70,73,104,107`, `tune.py:215`,
  `smoke_test_training.py`, `diagnose_training.py`,
  `diagnose_water_bias.py`, `diagnose_wetland.py`,
  `diagnose_road_bias.py:68`, `calibrate.py:351`, `bench_pipeline.py:95`,
  `generate_negatives.py:60`, `legacy/gen_negs.py:67`, and — restored
  after v1 dropped them in the split — `predict.py:91`,
  `download_treemap.py:110`, `download_tcc_nlcd.py:73`, which also
  import `BOXES` from the restructured module. `clean.py:46`,
  `analyze_grouse.py:21`, `prepare_training_data.py:48` import `regions`
  directly. The import-smoke gate covers **sixteen** files, not twelve.
- **Docs**: `ARCHITECTURE.md:59`, `grouse_data.py:20`,
  `PROJECT_TREE.md`, and the module docstrings of
  `prepare_training_data.py:22-28` and `generate_negatives.py:24,36`.
- `RegionData.block_assignments` moves to `GrouseData`.
- **Not affected:** raster contents (CR-0008), model architecture,
  `predict.py`'s reader. Train/predict reader parity was verified
  bit-identical during the investigation.

## Risk level: **MEDIUM-HIGH**
Lower than CR-0006's because no raster is written and no retrain is
performed; the work is reversible by restoring two directories.

| risk | mitigation |
|---|---|
| Validation numbers get worse. **That is the correct outcome** — removing a 31 % leak removes inflation. | Stated in advance. A lower metric is never a rollback trigger. Baselines recorded in CR-0009. |
| The `build_datasets` split silently mis-samples 75 % of training data. | **Risk removed, not mitigated (v7): there is no split.** The change is one guarded call at `train.py:244`; the loop and return contract are untouched, so no label-ordering hazard is created. R4/R5 bind; R1/R2/R3/R6/R7 are not applicable under the additive design. |
| Origin/block-size drift between the two scripts recreates BUG-0027. | Both centralised in `regions.py`; assertion (c) computed geometrically, which detects drift (measured: a drifted-origin pipeline scores 723 violating blocks where a correct one scores 0). |
| `verify_partition()` cannot pass. | Must be dispositioned before implementation — see Known exceptions. |
| Stale per-region block tables remain resolvable. | Deleted, and the `PATH_TEMPLATES` entry removed. |
| NH dataset halves, reducing power in the region under complaint. | Stated in Impact; CR-0009 measures the consequence rather than assuming it. |

## Test plan

**Validatable in this environment** (real data present, no retrain
needed). Every acceptance item is stated as a **computation**, not a
number — the recurring defect in CR-0006 was invariants whose inputs
were unspecified.

**GATE** = hard fail. **OBS** = recorded, never blocks. A gate whose
failure mode is "record a justification" is an observation (PA-0021(d)),
so every row says which it is.

**Record-set discipline (v7) — the rule the ten breaks share.** The
formal review diagnosed the gap as "I15–I18 are positives-only". Measured,
that is **narrower than the real mechanism**: this table had *no notion of
a record set at all* for any distributional statistic, and the choice is
**three independent fields, not one**:

> **every distributional row must name (i) the CLASS, (ii) the SUBSET
> within that class, and (iii) the NULL POPULATION its threshold is
> calibrated against.**

All three independently decide whether a real attack is visible. Measured
on one identical KS statistic under one attack: positives-only **0.0258
(bit-identical to fair — exactly blind)**, pooled both classes 0.0967
(1.8×), negatives-only **0.2053 (4.3×)**, negatives-habitat-half-only
**0.2004** — and, on the null axis, a max-over-regions reading judged
against a *pooled* null misses an NH-only variant entirely (0.1483 vs
gate 0.1853) while the same statistic against each region's **own** null
catches it on every seed. Break 2 was field (ii); Break 10B is field (i);
the NH-only miss is field (iii).

| # | kind | computed how — **distributional rows must name (class / subset / null)** | today | required |
|---|---|---|---|---|
| I1 | GATE | `cKDTree(pooled positives).query_pairs(regions.MIN_SPACING_M)` on EPSG:5070 coords reprojected from lon/lat | **1690** | 0 |
| I2 | GATE | block ids **recomputed** from lon/lat against `BLOCK_ORIGIN_5070`/`BLOCK_SIZE_M`; count blocks holding both a train and a val record, either class | **882** | 0 |
| I3 | GATE | same recomputation; share of val negatives whose block holds any train record | **37.2 %** | 0 % |
| I4 | GATE | 5 dp coordinate key, per class, set intersection of pooled train and pooled val | **522 pos / 0 neg** | 0 / 0 |
| I5 | GATE | full `img_size + 2·jitter` window (jitter **0** by default, `train.py:462`, so 64 px — name the value the rebuild uses) inside every feature raster the record will be read from, **both classes** | **NH 4** of the pre-partition 2,244; post-partition NH 1,079 → **0**; ME 0, VT 0. Negative candidates: NH **721** of 69,219, ME 2, VT 0 | 0 |
| I6 | GATE | pooled positive count: habitat rows whose filing region equals their `state`, deduped on (lon, lat, year), then one pooled `MIN_SPACING_M` thin | 8,365 rows | **6,230 ± 10** (fair spread is ±3; v3's ±2 % band was 40× too wide). Near 6,508 = habitat flag taken from a foreign grid |
| I7 | OBS | validation fraction, **per class and per region** | ME 0.2000/0.2000, NH 0.2005/0.2005, VT 0.1999/0.1999 — identical to 4 dp between classes | **OBS, and on the negative class it carries ZERO information (v7).** Because I8 pins `len(selected)` per (region, split) to the positive count exactly, I7(neg) is an *algebraic function of the positive split*: measured **numerically identical in the fair pipeline and in all 22 attack configurations** (worst-region min 0.352 / p50 1.529 / max 4.374 in every one). It is a restatement of I8, not a measurement of the negatives. v4 deleted it as a gate for being inverted (fair max 5.95 pp, attack 0.03–0.74 pp); v7 records that on the negative side it is not merely weak but vacuous |
| I8 | GATE | val neg : val pos ratio, pooled and per region | 1.000 | **exact**: per (region, split) `len(selected) == round(n_pos · NEG_RATIO)`, shortfall 0. Measured 1.0000 in 400/400 fair seeds |
| I9 | GATE | `verify_partition()` **ran** over positives (`analyze_grouse`) **and** negatives (`generate_negatives`), predicate `within`, source `tl_2023_us_county.zip` dissolved by `STATEFP`; output recorded | positives 0 of 43,024; selected negatives 1 outside + 1 mismatched of 8,365; candidate pool 5 + 1 of 35,678 | 0 after the § Known-exceptions rule |
| I10 | OBS | **recorded in the `I10p10` form, not as written (v7):** fraction of positives sitting in a **10 km** cell containing no negative, per region. Was assertion (d) — **now deleted as an assertion entirely** | ME 0.0484, NH 0.3220, VT 0.2500 (30 km form) | **OBS.** Two independent defects in the written form: the 30 km step is 1/39 in NH, and a 30 km cell cannot see stranding at any finer scale — a rescaled attack scores 0 % detection against it. The fixed `I10p10` form *does* separate both the rescaled family and 10A, but in the design sweep `Exc + I10p10` tolerates exactly the same Z as `Exc` alone, so **it adds no detection I19′ does not already have** and is not promoted. Recorded in the fixed form because it is the interpretable one ("N positives have no negative anywhere in their 10 km cell") and because anyone re-proposing a block-based support gate must be told both conditions. At 30 km it would also risk a tautology against §Stratification's 30 km × region strata; 10 km does not |
| I11 | GATE | recorded `block_id` == block id recomputed from lon/lat against `BLOCK_ORIGIN_5070`/`BLOCK_SIZE_M`, every record, both classes | not checked | 0 mismatches |
| I12 | GATE | parameter manifest on `block_assignments.csv` — spacing, block size, origin, seed, val fraction actually used — each equal to its `regions.py` constant | not recorded | recorded and equal |
| I13 | OBS | availability sample size == `n_samples` per region per feature after the §2 clip; judgeable-envelope count per region | NH 50, VT 48 (at `MIN_AVAIL_BG = 15`) | unchanged or justified |
| I14 | GATE | provenance and canonical form — see its own section; **not** a correctness gate | fails today on this repo's `data/pipeline/` (~31 % split mismatches per region) | reproduces from the recorded manifest; val block set differs between seeds |
| I15 | GATE | **positives only.** Records per val block / block-vs-record val fraction | fair max 1.734 / 1.161 pp | **≤ 2.5** (3.0 pp if the draw is stratified). v3's 1 pp false-fails 3.75 % |
| I16 | GATE | **(class: positives / subset: all / null: IN-RUN permutation).** Moran's I of the val indicator over positive-occupied blocks (3,861); centres recomputed from lon/lat against `BLOCK_ORIGIN_5070`/`BLOCK_SIZE_M`, row-standardised kNN weights at k=4 and k=8 | **+0.0678 (z 6.48)** k4 / **+0.0443 (z 5.71)** k8 — **fails both today** | **z ≤ 5.0** both k. **Carries NO frozen constant (v7):** a 1,000-draw *permutation* null (val-block count fixed, locations reshuffled, tree reused) costs **205–630 ms** and lands within 7 % of the frozen pipeline-redraw null (sd 0.010588 at k=4 on 4,069 blocks vs 0.011383 on 3,861), so the null is recomputed in-process on every run. This removes I16/I16b from the "threshold calibrated on a superseded footing" failure mode that has rejected this CR repeatedly, **and from the BUG-0034 re-derivation hand-off entirely** |
| I16b | GATE | **TWO-SIDED (v7).** Moran's I over an all-record-occupied block set, same weights and k as I16, in-run permutation null. **Two readings, two call sites** — *(a)* **selected-record** (positives ∪ the drawn negatives, **6,401** blocks mean) in `train.py`; *(b)* **pool-occupied** (positives ∪ the full candidate pool, **9,093** blocks fixed, **5,232** positive-free) inside `generate_negatives.py`, where the candidate frame is in memory | selected **+0.0823 (z 10.22)** k4 / **+0.0500 (z 8.37)** k8 — **fails both today** | **\|I\| ≤ 0.0188 (k8) / 0.0298 (k4)** selected; **≤ 0.0175 / 0.0236** pool. **Must be two-sided**: a feature-extremum split is a checkerboard and drives Moran *negative* — two attack variants score **−0.0275 and −0.0283**, invisible to v6's one-sided `z ≤ 5.0`. Block counts corrected: v6's **9,482 / 5,621** came from a 26,808-candidate approximation; the faithful figures are **9,093 / 5,232**. The pool reading is 3.4× more sensitive (z 63.8 vs 17.5 worst-seed) and catches two attacks the selected reading loses, but `train.py` cannot compute it — the pool is never persisted, hence deliverable *persist the candidate pool* |
| I17 | **OBS (demoted v7)** | **(class: positives / subset: all / null: 400-seed split redraw).** `ks_feat_max` = max two-sample KS(val, train) over the 9 continuous `FEATURE_SPEC` features (`ch, cc, tcc, road_dist, tsd, balive, tpa_live, qmd, carbon_dwn`) | **0.0306** | **Demoted, because it passes on maximally leaky pre-CR data** — 0.0306 against a ≤ 0.095 gate — so it has **zero regression power against BUG-0027 or BUG-0029**, the defects this CR fixes. It costs **8.4 s / 795 MB** (fixed vintage) to **24.3 s / 795 MB** (per-record vintage) and needs a per-record multi-feature extractor that does not exist. Run **once** at rebuild in `acceptance.py`; OBS in `build_datasets`. The footing question is settled: fixed-vintage 0.0302 vs per-record 0.0306, Δ0.0004, so the ≤ 0.095 threshold transfers and the cheap form is defensible. **None of the 9 features is in any pipeline CSV** — this is the one row with no data path today |
| I18 | GATE | **(class: positives / subset: all / null: per-region split redraw). PER-REGION, not pooled (v7).** Median val→nearest-train distance, **two-sided** | **pooled 1.634 km (FAILS); per-region ME 2.553 / NH 2.628 / VT 2.392 km (all pass)** | within **[2.33, 2.75] km per region**. v6 said only "positives only" — it named the class and **not the pooling axis**, and the verdict *flips* on it: the envelope matches the per-region reading, so per-region is what was intended, but a pooled implementation hard-fails a correct pipeline. This is the same under-specification Break 2 was supposed to have closed, surviving in a row that claimed to be fixed — which is why field (iii) is now mandatory |
| **I19′** | GATE | **REDESIGNED (v7) — 12 cells, see § I19′.** 4 readings × 3 regions, each against **its own** fair null: `Exc[r]`, `S[r]` (= v6's I19, per region), `Sws_val[r]`, `Excws_val[r]` | ME 0.5326 / **NH 0.6863** / VT 0.5294 on `S` — **fails today** | **one family-wise `Z = 5`**, applied as `x ≤ μ_cell + Z·σ_cell` from that cell's own ≥400-seed null. Measured **0.33 % false-fail** (2/600; 0/300 held out) and **100 % detection on all eleven attacks**. v6's single `≤ 0.64` on the max over regions is **withdrawn**: it misses **7 of 11** attacks, and its stated margin was wrong — the faithful 600-seed fair max is **0.6172**, so 0.64 is **1.037×**, not the "1.09× / 16 % both sides" claimed |

I6–I8 exist because I1–I5 are all "violation count == 0" predicates and
therefore monotone under deletion: a reviewer passed every one of them
on a pipeline that had silently dropped **half the dataset**.

I12 exists because `--min-spacing-m` and `--block-size-m` survive as CLI
flags on `prepare_training_data.py` while `generate_negatives.py` takes
the constant — so the two classes can be thinned at different distances
from one command line. Measured: positives thinned at 60 m give 6,144,
**inside I6's ±2 % band**, while I1's predicate is one-sided (harder
thinning satisfies "0 pairs under 30 m" more easily). The undetectable
window is ≈30–65 m. Removing the two flags is the cheaper equivalent.

### § I19′ — the support gate, redesigned (v7)

**Why v6's form could not work.** A gate `max_r X_r ≤ c` with a single `c`
grants every region slack `c − median(X_r)` made of three additive parts:
the region's own sampling width, the **level offset** between it and the
extreme region, and the **max-of-K inflation**. Only the first is
legitimate. Expressed as a *free-harm budget* — positives that can be
stranded with **zero** chance of detection:

| gate form | budget |
|---|---|
| v6: `max_r S ≤ 0.640` | **798 positives** (ME +402, NH +79, VT +318) |
| single threshold on `max_r S` at p99.5 | 581 |
| **per-region `S` at p99.5** | **146** |

83 % of v6's free harm sits in ME and VT — which is exactly what Break 10A
exploits. NH sets the bound at 0.6172 while ME's own fair max is 0.5512
and VT's 0.4611, handing an attacker 0.069 and 0.155 of free slack.

**The hole one level deeper, found by attacking the fix itself.** v6's I19
(a) pools train and val positives and (b) takes the nearest negative of
**any split**. Because blocking at 3 km *guarantees* train negatives sit
near val positives, the cross-split reading is systematically optimistic.
Confining only the **val-split** candidate pool to the southern half of
each region strands **1,010 of 1,251 validation positives** with no
validation negative inside the receptive field, at median distances of
**91 km (ME) / 72 km (NH) / 37 km (VT)** — and v6's gate fires on **3 of
60 seeds**. This is Break 1 and Break 10A a third time, on the split axis.

**The gate.** Four readings × three regions = 12 cells, each against its
own ≥400-seed fair null:

| reading | definition |
|---|---|
| `Exc[r]` | mean over region-r positives of `max(0, d − 1920)/1000` km, `d` = distance to nearest region-r negative (any split) |
| `S[r]` | `frac(d > 1920 m)` — v6's I19, per region |
| `Sws_val[r]` | frac over **val** positives of (distance to nearest **val** negative > 1920 m) |
| `Excws_val[r]` | mean km of excess beyond 1920 m, val positives vs val negatives |

`Exc`/`Excws_val` are harm-aligned (how far beyond the receptive field);
`S`/`Sws_val` are breadth (how many). **Both are needed**: an attack
pushing *many* positives to just past 1,920 m keeps `Exc` inside the
envelope, and one pushing *few* positives very far keeps `S` inside it.
The within-split pair is what closes the val-split hole above.

**Threshold: one family-wise `Z`, never a multiple of a maximum.** `Z` is
the quantile of the fair distribution of `max over cells (x − μ)/σ` over
600 seeds — p99 = 3.74, p99.5 = 4.05, p100 = 7.08. **`Z = 5`** sits inside
the p99.5–p100 band and measures **0.33 % false-fail** (2/600; 0/300 held
out) with **100 % detection on all eleven attacks**, worst-seed margin
6.7σ on the thinnest. Absolute equivalents from the 600-seed null:

```
Exc        ME 1.2238   NH 1.5143   VT 0.7842   (fair mean 1.0494 / 1.0945 / 0.5985)
S          ME 0.5667   NH 0.6431   VT 0.4863   (fair mean 0.5297 / 0.5668 / 0.4272)
Excws_val  ME 5.1204   NH 7.8778   VT 4.0744   (fair mean 3.5891 / 3.8353 / 2.3143)
Sws_val    ME 0.7815   NH 0.9358   VT 0.7814   (fair mean 0.6514 / 0.6909 / 0.5717)
```

Free-harm budget falls from 798 positives to ~150–240.

**Three designs that were tried and rejected, recorded so they are not
re-proposed.** (i) *Region-invariant-by-construction normalisation*
(`S/S_pos`, negatives "placed at the positives") aligns the fair levels
but does nothing about the fair *spreads*, and a single threshold on a max
over three cells still pays the max-of-K inflation — measured **no better
than v6**, catching 5 of 11. It buys transferability to a new region
without recalibration, not power. (ii) *A clustering gate* (Moran's I of
the unsupported indicator) is the most region-invariant quantity found and
is spectacular on contiguous attacks, but a finer-rescaled attack scores
*inside* the fair envelope and a dispersed single-site attack scores at
the fair **median**. Diagnostic, not a gate. (iii) *A within-run
permutation null* is **structurally blind to the dominant mechanism**:
0–8 % detection on the nine pool-damage attacks, 100 % on the two pure
draw-tampering attacks. If the pool is damaged, the observed draw genuinely
*is* a fair draw from the damaged pool. Since CR-0008's coverage mechanism
**is** pool damage, a self-normalising gate cannot be primary here — but it
is an excellent *attribution* tool: gate fires with `z_within ≈ 0` ⇒ pool
damage; gate fires with `z_within` large ⇒ tampered draw.

### § Composition gates — the axis the table had no row for (v7)

Every v6 row touching the negative class measured a **count** (I8) or a
**location** (I2, I3, I16b, I19). None measured **composition**. Two
demonstrated breaks live here, and both pass the whole of v6:

- **Break 10B** — positive-free blocks assigned to val by a local
  `tcc`/`road_dist` extremum. Every v6 gate green: I2 = 0, I3 = 0,
  I4 = 0/0, I6 = 6,230, I8 pass, I15 = 1.2225, I18 = 2.384,
  I19 = 0.529–0.563, **I16b k4 = −0.0451 / k8 = −0.0486 (negative, so
  green under a one-sided gate)**, and **I17-as-written = 0.0329 vs 0.095**.
- **Break 10C** — habitat pool short, so the beyond-cap NonVeg top-up at
  `generate_negatives.py:281-289` fills the shortfall. **I8 reads exact at
  every rung**, including NonVeg at 90.7 % of a cell. This is BUG-0004's
  mechanism, ungated.

Calibration: 500 fair seeds pooled / 300 per region, 20 per attack, one
mechanical threshold rule (**1.30 × fair max** upper, **fair min / 1.03**
lower) so nothing is tuned per attack; thresholds derived on seeds 1–250
and false-fails measured on held-out 251–500 gave **0/250 for every gate**.

**Exact predicates — no threshold, 0 false-fail by construction:**

| id | statistic | record set | closes |
|---|---|---|---|
| **C1** | `n_nonveg_selected ≤ round(n_target · NONVEG_MAX_FRAC)` per (region, split) — an **integer count**, not a share | selected negatives | **10C.** As a *share* the fair band is [0.29983, 0.30270] because `round()` moves it; as a **count** the fair excess is identically 0, so the tolerance vanishes |
| **C2** | the beyond-cap top-up branch must not execute: `len(habitat_pool) ≥ n_habitat_target` in every cell | candidate pool + targets | **10C at source.** Today this is a `print` at `:281-289` — it must **raise** |
| **C3** | every selected negative's `weight` == `build_weight(...)` **recomputed** from `envelope_metrics_{region}.csv` | selected negatives + metrics CSV | the negative-class analogue of I11 ("recompute, never read the column"). Free — both inputs on disk, no rasters |
| **C4** | `len(selected) == round(n_pos · NEG_RATIO)`, shortfall 0 | selected negatives | **= I8, kept.** Unfalsifiable against 10C on its own |

**Cross-split contrast — record set: SELECTED NEGATIVES ONLY, never
pooled with positives, never positives-only:**

| id | statistic | fair max | gate | false-fail | attack worst case |
|---|---|---|---|---|---|
| **C5** | `ks_neg_pooled`, 9 continuous features | 0.0570 | **≤ 0.074** | 0/500 | 10B **0.190**, A7 **0.331** |
| **C6** | same, **habitat half only** | 0.0806 | **≤ 0.105** | 0/500 | 10B **0.198**, A7 **0.485** |
| **C7** | `ks_neg_region`, **each region vs its OWN null** | ME .0814 NH .1294 VT .1274 | **ME ≤.106 NH ≤.168 VT ≤.166** | 0/300 | 10B_ME **0.220**, 10B_NH **0.187** |
| **C8** | `smd_neg_region`, max SMD over 9 features × 3 regions | 4.895 | **≤ 6.36** | 0/500 | 10B **10.8**, A7 **15.2** |
| **C9** | `nonveg_share_gap`, \|val − train\|, worst region | 0.0029 | **≤ 0.0038** | 0/500 | 10C **0.0085–0.0139** (second, orthogonal 10C detector) |
| **C10** | `basis_tv_split`, TV of `weight_basis` hist | 0.0766 | **≤ 0.0996** | 0/500 | A7 **0.172** |
| **C11** | `ks_weight_split`, KS on `weight` itself — **two-sided** | 0.1333 | **≤ 0.173**, and a lower bound | 0/500 | A7 **0.569**; a weights-collapse attack reads **0.0004**, *below* the floor, hence two-sided |

The habitat-half reading (C6) is a separate row and not a refinement: the
30 % NonVeg block is a fixed homogeneous mass that dilutes whole-class KS
by ~0.7× (A7 reads 0.357 whole-class vs **0.511** habitat-only).

**Absolute composition — selected negatives vs the per-cell eligible
candidate pool:**

| id | statistic | fair | gate | sole detector of |
|---|---|---|---|---|
| **C12** | `basis_tv_pool` vs weight-proportional pool expectation | max 0.0800 | **≤ 0.104** | — (carries A8b, A12) |
| **C13** | `smd_pool_max`, selected-habitat vs weighted pool mean | max 5.861 | **≤ 7.62** | broadest single detector: A7 **139**, A12 **21.2**, A8b **17.0** |
| **C14** | `weight_ratio`, selected-habitat vs pool-habitat mean weight — **lower side gates** | min 1.0588 | **≥ 1.028** | **"the draw ignored its own weights"** — a weights-collapse reads exactly **1.0000** |
| **C15** | `nonveg_evtphys_tv` — composition *within* the NonVeg half | max 0.2156 | **≤ 0.280** | **a NonVeg monoculture at exactly the cap** (0.568). Nothing else fires |
| **C16** | `species_tv_pool` — TV of `common_name` hist | max 0.1881 | **≤ 0.245** | **a wetland-species monoculture** (0.339). Nothing else fires |
| **C17** | `hab_supply_min` = `len(habitat_pool)/n_habitat_target`, worst cell | **min 1.2045** | **≥ 1.17** | **leading indicator of 10C — fires two rungs before the defect materialises** |

**C15 and C16 are new axes for this repo.** Every pseudo-absence is an
"other species" GBIF observation, so the negative class can be silently
converted into a wetland monoculture through the species mix — the
mechanism `WETLAND_LEAN_FINDINGS.md` is about — while every count,
location and cap reads correct. `common_name` is already a column in
`negatives_{region}.csv`.

**Two structurally distinct sub-axes, one break each.** 10B and A7 are
*cross-split contrast* (train and val negatives differ); 10C, A8/A8b/A9,
A10, A11, A12 are *absolute composition* (both splits equally wrong). A
set built only from the first — the natural reading of "extend I17 to the
negatives" — misses **six of eight** attacks; one built only from the
second misses 10B. Both families are required.

**10C's boundary is measured and the family is closed:** habitat pool kept
100/95/90/85/80 % → C17 = 1.43/1.36/1.27/1.22/**1.11 fires**; at 70 % C1
starts (+5) and C2 begins firing; at 60 % C2 always fires. Between 100 %
and ~75 % there is **no composition defect at all** — the cap is still met
and the thinning unbiased.

**Live status: 10C is latent, not live.** On the shipped
`negatives_*.csv`, C1's excess is **0 in all six cells** (ME 926/926,
232/232; NH 538/538, 135/135; VT 543/543, 136/136) and C3's mismatch count
is 0. But C17's fair minimum is **1.2045** — the tightest cell has only
~20 % slack — and §2's state clip, §5's binner refit and CR-0008's nodata
change all push in the direction that consumes it. **The gate is needed
before the rebuild, not after.**

### § Supply gates — what the draw-side table cannot see (v7)

Strip attacks that remove northern candidates from the *pool* pass the
**entire** draw-side table: I19 reads 0.5700 (3 % strip), 0.5737 (5 %),
0.5635 (8 %), 0.5792 (10 %), **0.5884 (15 %)**, 0.6138 (20 %) — all under
0.64 **and all inside the fair envelope**; I8 exact on every one; I16b
0.0051–0.0112 against a fair max of 0.0159.

**A calibration-form finding first.** A supply statistic's null over the
pipeline's own randomness is a **point mass**: 400 seeds of the real 30 m
thinner give values identical to 4 dp in **400/400**, and the same holds
over I6's ±10-record variation. So these rows are **pre-registered
constants with headroom**, the way CR-0008's G0.2 pins digests — *not*
quantiles of a seed distribution. Raw region-level statistics also cannot
work: a 25 % **aspatial** loss reaches 0.3588, *above* the northern-strip
attack's 0.3528, so any fixed threshold on the raw statistic either
false-fails random loss or passes the band attack. The two gated rows are
therefore **size-invariant ratios**.

| id | statistic | today | gate | false-fail |
|---|---|---|---|---|
| **SUP0** | `len(candidate pool) / n_target` per (region, split) | worst **3.04** (ME val) | **≥ 2.5** | — bounds the aspatial loss the two rows below must tolerate to ≈18 %, which is what makes them calibratable |
| **SUP-O** | on a 10 km grid over cells with ≥5 positives, `m` = median of per-cell median positive→nearest-candidate distance; count positives farther than `10·m` | **2** | **≤ 3** | **0/1,600 draws** |
| **SUP-R** | `max(cell median) / median(cell medians)`, worst region | **4.160** | **≤ 9.0** | **0/1,600 draws** |

Both normalise the worst sub-region reading by the typical reading *of the
same pool*, so aspatial loss scales numerator and denominator together
while a band loss inflates only the numerator. **SUP-O fires on a 0.5 %
strip**, where I19 is still statistically indistinguishable from a fair
draw; Break 10A″ scores **907 (302× the gate)** and **131.96 (14.7×)**.

*Live diagnostic SUP0 surfaces:* the **habitat-only** ratio for VT/val is
**0.87** — VT validation already fills from NonVeg past the 30 % cap
today, and `generate_negatives.py:281-293` only `print`s it.

### § The `--regions` hole — the largest gap in v6 (v7)

`regions` is `args.regions` in all three callers and `train.py:35`
advertises `--regions ME`. Under a single-region invocation the "pooled"
gates (b)/(c)/I2/I3/I4 **silently collapse to within-region checks — the
exact pre-CR condition BUG-0027 describes — and pass.** The entire
acceptance layer is defeatable by a command-line flag, with no tampering.

Fix: the pooling pass loads a fixed **`GATE_REGIONS`** — every region the
manifest declares — independent of the caller's `regions`. The
coordinate-only gates need no rasters, so this costs nothing (the whole
coordinate-only suite, including both in-run Moran nulls, measures
**2.09 s / 117 MB**, against the **163 s / 1,559 MB** `build_datasets`
already spends on `raster_path(validate=True)`). Only I5 and I17 stay
scoped to `regions`.

Three further placement facts that change answers, all measured:
- **I5 must run POST-`filter_by_year_gap`** — 4 violations pre-filter vs
  **3** post-filter; the 2018 NH record at (−72.62267, 42.833378) is
  dropped by the filter, so §6's "before the filter" rule would fail the
  gate on a record no dataset ever reads. I5 is the one exception to the
  pre-filter rule, and its implementation must be pinned to
  `validate=False` + per-CRS transformer cache (3, not 405) + header-only
  opens: **3.1 s vs 357 s, 150 MB vs 1.57 GB**.
- **The gates must reproduce `dataset.py`'s year rule** (`dataset.py:98-101`
  fills a missing `year` with `max(raster_years(cat_features[0]))` then
  `fillna(df['year'].max())`). A gate that fills differently checks a
  different vintage, silently.
- **The pooled assertion frame must never become a dataset input.**
  `pd.concat` of positives (no `weight` column) with negatives (with one)
  yields NaN weights that `dataset.py:87-88` silently fills to **1.0**,
  discarding every envelope weight. `pooled_record_frame` is returned by a
  function that never touches `GrousePatchDataset`.
- **Three entry points bypass `build_datasets` entirely** —
  `smoke_test_training.py:84-94`, `diagnose_training.py:87-144`,
  `diagnose_wetland.py:200` — so "the three entry points become unrunnable"
  is true of `build_datasets`, not of the repo, and the test plan's
  `smoke_test_training.py` run is not gated.

### § Stated limits — what no gate on these axes closes (v7)

Recorded as limits, not as covered cases. Each is measured.

1. **Pool-composition erosion upstream of selection is not closable on the
   selected set.** Any defect changing the *eligible pool's* composition —
   §2's state clip, §5's binner refit, CR-0008's nodata change, the
   extraction `dropna` — moves the very reference C12–C16 compare against,
   so they go green by construction. Demonstrated: keeping
   100/97/95/92/90/85 % of the habitat pool leaves C1 = 0, C4 = 0, C5/C6,
   C12/C13/C14/C16 all inside the envelope on **every seed**. Mitigating:
   the harm is also small (selected habitat `tcc` mean moves ≤ 1.9 pp) and
   C17 fires past ~20 % erosion. Note under a *weighted* design there is no
   unbiased reference — the fair draw's own selected-vs-raw-pool shift is
   already **4.4 SE by design**, so "selected ≠ pool composition" is not a
   defect. The only handles are C17 as a gate and a **recorded
   pool-composition manifest diffed against the previous build**.
2. **A cross-split attack confined to the smallest region.** VT-only 10B
   sits at 1.07× VT's fair max on C7, so a 1.30× gate fires on a minority
   of seeds; residual worst-feature bias ≈ **4.8 SE** against VT's own
   fair max 4.53. Power-limited by **306 VT validation negatives**, not
   fixable by threshold choice.
3. **The validation side of I19′ is an order of magnitude weaker than the
   training side, and one escape survives**: a val-only band attack at
   *t* = 16 km, duty 1/8 strands **+22 val positives / +626 km excess**
   undetected (0/10 seeds). Cause is irreducible here — NH's val set is
   216 positives, so σ(`Sws_val`[NH]) = 0.048 vs σ(`Sws_train`[NH]) =
   0.020. The obvious fix makes it **worse**: corr(`Sws_val`, `Sws_train`)
   is **negative** (−0.43/−0.34/−0.39), so a paired difference has larger
   σ than the val term alone. Real remedies are outside the gate — a larger
   validation fraction, or an explicit val-negative supply requirement.
4. **A defect inside `build_weight` itself.** C3 recomputes *through* that
   function, so a wrong formula reproduces itself with 0 mismatches; only
   C12/C13/C14 see it, and only when realised composition moves.
5. **Pool-side weight suppression.** Setting `weight = 1e-6` on candidates
   to be excluded means they are never selected, so C3 on the *selected*
   set reads 0. C3 checks what was **delivered**, not the pool; C15 is what
   catches this.
6. **A per-20-km-cell southern skew of ≤3 %** evades both supply rows.
   Partly covered by I19′, and harm is small (band median 2.09 km vs fair
   1.97 km).
7. **Whether 0.30 is the right NonVeg cap, or inverse-`Selection_Ratio`
   the right weighting, is untestable by any gate** — acceptance can only
   check that a design constant is obeyed. Said explicitly because C1's
   exactness can read as stronger than it is.
8. **The adaptive bound.** Maximising harm subject to passing caps
   residual composition bias at **1.0–1.4× the honest draw's own sampling
   noise** (gate fires at tilt β ≈ 0.3–0.4, residual 2.7–3.9 SE against a
   fair envelope [0.95, 4.90]); and for I19′, at **≈ +130 stranded
   positives and +500–660 km excess**, against a fair count sd of ≈35.
   Detectability and harm stop decaying together at band thickness
   ≈ 2–3 km, i.e. 1–1.5× the receptive field — below that, positives in
   the band still have a negative inside their receptive field and there is
   nothing left to harm. The bound is structural, not statistical.

### v4 — three gates deleted, the governing invariant demoted

Five research agents calibrated every gated statistic against its
sampling distribution (400–1,000 draws) and against seven distinct
defect families. The result retires more of this table than it adds.

**I7b (per-region validation fraction) — DELETED as a gate.** There is no
separating threshold. Fair-draw envelope over 400 seeds: min 0.04,
median 1.57, p95 3.70, p99 4.84, **max 5.95 pp**. Both committed attacks
sit *inside* it — the eastern-half draw reaches only **0.03–0.74 pp**
(it is constructed to hit 20 % per region exactly, so it scores *better*
than a fair draw) and `break1` reaches 3.33 pp, below the fair p95. Any
gate loose enough to pass correct pipelines passes both attacks; any gate
tight enough to fail `break1` fails 12–33 % of correct ones. v3's hard
±2 pp gate rejects **32.7 %** of intended-pipeline runs (author's own
300-seed reproduction; 33 % and 36.4 % measured independently at 400 and
1,000 seeds). It is not mis-calibrated — it is **inverted**, selecting
for the attack. Becomes an observation.

**I10 / assertion (d) — DELETED as a gate.** Fair worst-region max
**0.1026**; the rescaled attack **0.1282**. The gap is exactly one NH
block out of 39 on a statistic whose step is 1/39 = 0.0256 and whose
fair draws already reach 4/39 in 3.25 % of seeds. The attack's value lies
inside the fair distribution's support. The 0.15 threshold v3 proposed
passes **8 of 9** attack rungs. Becomes an observation.

**I10's replacement, corrected.** v3 specified it "at or below the
receptive-field scale". The correct pipeline's pooled median
positive→nearest-negative distance is **1,871–2,020 m** against a
1,920 m receptive field, so a gate at that value false-fails essentially
every legitimate draw. The receptive field is the right scale
*reference* and the wrong threshold *value*. Usable form:
**frac(pos→nearest-neg > 1920 m) ≤ 0.55** (fair p99 0.5223, max 0.5258,
0/400 false-fail; attacks 0.574–0.852), with ~9 % margin — thin, and
load-bearing, so say so.

**I6 — tightened 40×.** The fair spread is **±3 records** (min 6227,
max 6233), not the ±2 % (±125) v3 allowed. **6230 ± 10.** This also
closes I12's undetectable thinning-drift window from ≈30–79 m to
**30–34 m**, largely subsuming a gate added separately.

**I8 — becomes exact, leaving threshold territory.** Measured 1.0000 in
**400/400** fair seeds with zero shortfall. State it as a predicate:
per (region, split), `len(selected) == round(n_pos · NEG_RATIO)` and
shortfall 0. It then catches every supply-restricting attack (which
score 0.485–0.697) and needs no calibration.

**I15 — 1 pp → ≤ 2.5 pp** (fair max 1.734; a 1 pp gate false-fails
3.75 % over 400 seeds, consistent with 6 % over 50). **3.0 pp if the
draw is stratified**, since stratification raises the fair max to 2.22.

**NEW — the location gate the set never had.** Every previous version
gated *how many* validation blocks there are and *how variable* they are
across seeds, never *where they are*. **Moran's I of the validation
indicator over the occupied-block set** — block centres recomputed from
lon/lat against `BLOCK_ORIGIN_5070`/`BLOCK_SIZE_M`, never from the
recorded `block_id` — row-standardised k-nearest-neighbour weights at
k = 4 and k = 8, gated one-sided at **z ≤ 5.0** against a ≥1,000-draw
calibration (today: mean −0.000191 / sd 0.011383 at k=4,
−0.000206 / 0.007941 at k=8 → I₄ ≤ 0.0567, I₈ ≤ 0.0395). Observed
false-positive rate **0/1000**; catches every location-structured defect
at z = 6.7–102, including the dense-first attack at 9.3. Cost: one
cKDTree on 3,861 points, <50 ms, no rasters, no geopandas.

Chosen over the competing proposal (max KS on `x_5070`/`y_5070`/
`spatial_density` ≤ 0.15) on evidence: KS-type statistics were tested
against seven defect families and **miss the 10-blob, 50-blob and
dense-first draws entirely**, while the KS proposal was tested only
against the two committed attacks. Moran also carries an analytic null
(Cliff–Ord SD within 5.7 % of empirical), so it transfers if the block
size or region set changes.

**NEW — a feature gate, because coordinates and features are not
substitutes.** `ks_feat_max` = max two-sample KS between val and train
over the continuous `FEATURE_SPEC` features, one-sided at ~**0.095**
(1.5× fair p99.9; fair max 0.064; feature-targeted attacks 0.40+).
Moran is blind to pure feature-space draws; `ks_feat_max` is blind to the
eastern-half attack. Each is needed.

**NEW — a two-sided separation gate**, catching the *interleaving*
direction that a representativeness gate actively rewards: median
val→nearest-train distance within the fair envelope **[2.33, 2.75] km**
(dense-first 1.95, no-blocking-at-all 1.36 — both below the floor).

**Why the location gate is the right axis, and why rescaling does not
defeat it.** The eastern-half draw shifts the validation-set mean of
*elevation* by **−12.3 SE with the same sign at every seed** (fair
envelope ±3.3) — and elevation is **not in `FEATURE_SPEC`**, while its
KS on every modelled feature stays inside the fair envelope. Position is
the sufficient statistic for everything spatially varying that was not
measured. And unlike I10, the rescaling escape closes itself: as the
attack moves to finer cells, detectability and harm decay **together**
(Moran z 24.6 → 17.1 → 7.3 → −2.5 while worst-field bias goes
12.3 → 2.5 → 1.4 → 1.0 SE). The 12 km-rescaled draw is not a defect and
the statistic correctly declines to fire. Adaptive bound: maximising bias
subject to passing the gate caps residual location bias at roughly
**1.5–2× the honest draw's own sampling noise**.

### What I14 is actually worth, and what it is not (v4)
v3 called this "the governing invariant". It is not. I14(i) is a
*determinism* property and I14(ii) a *seed-dependence* property; both are
properties of the procedure, and every deterministic seed-consuming
implementation has them, correct or not. A reviewer passed both while
raising validation-to-training receptive-field proximity from 35.98 % to
55.96 %.

**I14(ii) is evadable in one line.** Append
`.sort_values(ascending=False, kind='stable')` after
`bc.sample(frac=1, random_state=seed)`: the draw stays **seed-varying**,
so I14(ii) passes, while delivering identical harm to the
deleted-shuffle break (236 val blocks, 5.28 records per val block,
I15 = 13.9). v3's claim that "either half alone kills it" is **false**
for this variant — only I15 and the records-per-val-block statistic catch
it. I15 is not redundant.

**I14(i) is not achievable from the manifest v3 specifies.** Holding
(30 m, 3000 m, (0,0), 42, 0.2) fixed and varying only the order of
`--regions` produces **six distinct validation block sets**, six distinct
kept-record sets, and pooled counts of 6,230/6,231/6,232. The ungated
leakage statistic moves **4.8 pp (31.17 → 35.98) on argv order alone** —
comparable to what this CR gates its attacks against. Two mechanisms:
`thin_by_min_distance` permutes in pooled-frame row order
(`prepare_training_data.py:64-66`), and `block_counts.value_counts()`
breaks ties in row-encounter order (`:101-103`), which the shuffle then
consumes.

**The canonical sort is necessary and insufficient.** Sorting on
`(state, longitude, latitude)` gives one outcome across all six orders —
but **65.7 % of blocks (2,537 of 3,861) hold exactly one record**, so
nearly every block is tied, and pandas' own `value_counts` docstring
records *"Prior to 3.0.0, the sort was unstable."* Emulating the pre-3.0
order moves **32.9 % of records**. The sort also does nothing about
`rng.permutation(len(df))` being length-keyed: removing one upstream
record changes the kept set by **50 records** and 11.6 % of splits.

**Adopt hash-derived ordering instead.** `blake2b(f"{seed}:{lon:.6f},{lat:.6f}")`
for the thinner and `blake2b(f"{seed}:{block_id}")` for the block draw is
order-invariant, survives the pandas tie-order change with **0 records
moved**, perturbs the kept set by **1 record** rather than 50 when one
upstream record changes, needs no sort, and still satisfies I14(ii). It
also preserves the thinner's documented intent better than a coordinate
sort, which makes a greedy thinner systematically prefer western points.
The coordinate format string becomes part of the contract and must be
pinned.

**PROJ exposure is ~2.7 m, not sub-metre, and it amplifies.** Only one
4326→5070 operation is selectable here; it applies a null datum shift at
4.0 m stated accuracy. If a higher-accuracy operation becomes available,
coordinates move **2.67–2.71 m**, at which up to 14 records change block.
And pushing the single record with 0.33 m clearance across its boundary
changes **911 of 6,230 splits (14.6 %)**, because `value_counts` then
runs over a changed multiset and the whole shuffle prefix shifts. The
hash variant removes the amplification.

**The manifest must record** (v3's five fields are insufficient — none of
them varies across the six failing runs): input file digests and an
order-insensitive record-set digest; the region list and its order, or
the sort rule; the canonical ordering rule (sort key + kind, or hash
function, digest size and coordinate format); the block-list ordering fed
to the shuffle; **which RNG** (`RandomState` vs `Generator(PCG64)` —
numpy guarantees the former's stream and explicitly does not guarantee
the latter's); the filter and dedup rules actually applied; geometry
provenance including the selected **PROJ operation string**; and the
`pandas` / `numpy` / `pyproj` / PROJ versions plus the git commit.

**What it is good for, stated honestly:** stale or foreign artifacts,
hand-edited splits, manifest-vs-run mismatch, unseeded or
environment-seeded RNG — and the class v3 missed, **library-version and
argv-order drift that silently produces a different but equally
valid-looking split**. Run against this repo's own `data/pipeline/`
today it **fails**: `block_id` reproduces with 0 mismatches but `split`
with ~31 % mismatches per region, and no setting reproduces the shipped
val-block sets, because those files are from an earlier pipeline
generation. That is an argument for the gate, as a **staleness and
provenance check** — not as a correctness claim.

### The structural control (v4, primary)
Make the validation draw a pure function whose signature contains **no
coordinates, no features, no region, and no `block_id`**:

```python
draw_val_blocks(counts: np.ndarray, strata: np.ndarray,
                val_fraction: float, seed: int) -> set[int]
```

where positions index a canonically ordered block list held by the
caller. A geographic attack then cannot be written inside the sampler —
it has to be written in the five-line caller, where it is visible. Two
mechanical tests: shuffling the input rows returns the image set under
the shuffle; and seed S ≠ S′ returns different sets.

### Stratification — what it does and does not buy (v4)
v3 was going to adopt region-level stratification to make I7 exact.
Measured, that closes **zero percent** of the hole: every location
statistic under region strata is numerically identical to no strata
(Moran −0.0011 vs −0.0004; occupied-block KS 0.109 vs 0.110), and the
eastern-half attack is *already* per-region-exact at 0.11 pp. It removes
a threshold and nothing else.

**Coarse-spatial stratification does close it by construction** — if
every stratum must contribute the validation fraction, an eligible-set
attack is inexpressible. Recommended: **30 km × region (196 strata)**.
Three conditions:
1. **Strata must be a property of the BLOCK, not the RECORD.** With
   record-level strata, **160 of 200 seeds** produce at least one block
   holding both a train and a val record, with cross-split pairs as close
   as **870 m** — inside the receptive field, so the patches physically
   overlap. That is BUG-0027's exact signature, delivered by the fix for
   the I7 gate. Block-level strata: **0 of 100 seeds**.
2. **Gate and strata must sit at different scales.** Under 30 km strata a
   30 km support statistic collapses to a tautology (0.24 vs fair 2.29) —
   BUG-0033's failure mode. Moran at k=4/k=8 (9–12 km neighbourhoods)
   stays informative.
3. **Specify the allocation rule.** Naive per-stratum greedy
   accumulation overshoots the validation fraction by up to one block per
   stratum (196 strata → 23.1 %, 970 → 35.6 %). "Take the block only if
   it moves closer to the target" fixes it (20.45 %).

PA-0018 conformance: a stratified draw over one global block partition is
still **one** computation over the pooled data — grid, block→stratum map
and pass are all global. A per-region *record* draw is not.

### A side finding that bounds what any of this buys
**33.0 % of validation records already have a training record within
1.92 km**, and 9.6 % within 960 m — their input patches overlap. Fair
envelopes [0.284, 0.386] and [0.063, 0.126]. This is not caused by the
draw and no gate here fixes it. It is an argument for a larger block or
an explicit buffer, and it bounds how much the spatial holdout currently
delivers.

**How every invariant above was calibrated** — and the rule this CR asks
to be made standing policy: *each was measured on at least one
constructed pipeline that is wrong in the way that invariant exists to
catch, not only on the current data and the intended pipeline.* All four
of CR-0006's acceptance failures, and v1's assertion (d), would have
been caught by that rule alone.

Also: assertions (a)–(d) demonstrated **failing** on the current CSVs
and **passing** on rebuilt ones; the three deprecation guards actually
fire; `smoke_test_training.py` runs; import-smoke of all sixteen
consumers; `inv_leakage.py` re-run with sections 1–2 reading 0.

**Cannot be validated in this environment, and why:**
- **Whether the model is better.** Requires the retrain (CR-0009), and
  the number will fall by construction.
- **Exact post-rebuild counts.** `analyze_grouse.py` re-samples
  reassigned records from a different grid, so the habitat filter's own
  output changes; 6,230 is an expectation with a band, not a prediction.
- **A fresh-environment run.** geopandas and
  `data/roads/tl_2023_us_county.zip` are present here; behaviour when
  absent is specified but untested.
- **`--an-background` behaviour at non-zero values.** Default is 0.0 and
  no recorded run used it.

## Deliverables
- [x] **Disposition the two `verify_partition()` exceptions**: DROP
      them, recording count and coordinates in I9's output (ruled in
      § Review). Was blocking approval, now settled.
- [ ] ~~Decide the NH box question~~ — **resolved in §5**: windowless
      candidates are dropped before sampling, which makes I5 unfailable
      without re-downloading any NH raster. `BOXES` is unchanged.
- [ ] `regions.py`: `state` membership; `verify_partition()`;
      centralise `STATE_FIPS`, `MIN_SPACING_M`, `BLOCK_SIZE_M`,
      `BLOCK_ORIGIN_5070`; `BOXES` documented raster-only.
- [ ] `analyze_grouse.py`: partition, `region` column, rejection-sampled
      availability clip, `:439` threshold re-expressed.
- [ ] `prepare_training_data.py`: global origin, pooled pipeline,
      `--regions` write-guard, dead flag and dead `rng` removed.
- [ ] Runtime guards on `clean.py`, `legacy/gen_negs.py`,
      `legacy/audit.py`, `legacy/download.py`, `legacy/download_more.py`.
- [ ] `generate_negatives.py`: pooled/per-region split, global ids,
      pooled buffer and thinning, `:153` narrowed, constants re-pointed.
- [ ] Move the `block_assignments` accessor to `GrouseData`; remove the
      per-region `PATH_TEMPLATES` entry. **Deleting the per-region
      `block_assignments_*.csv` files happens only after the backup
      below is checksummed** — v2 ordered the deletion before it.
- [ ] `train.py`: **one guarded gate call inserted at `:244`** under
      **R4/R5** — not a split (R1/R2/R3/R6/R7 recorded not applicable);
      assertions **(a)–(c)** only, **(d) deleted with its escape flag,
      banner and artifact-recording machinery**;
      `sample_background_points` partitioned and its oversample budget
      raised.
- [ ] **`GATE_REGIONS` decoupled from `--regions`.** The pooled gates
      must load every region the manifest declares, independent of the
      caller's `--regions`. See § The `--regions` hole.
- [ ] Every gate must **`raise`, not `assert`** — `python -O` strips
      `assert` and would silently disable the entire acceptance layer.
      A grep-level check is feasible here; CI is not (`CLAUDE.md` §3.4).
- [ ] Build what does not exist: **`regions.block_ids(lon, lat)`** (one
      block-id function, so origin drift is structurally impossible
      rather than merely detected); **the manifest JSON** (nothing writes
      one today, and I12 plus the standing halves of I6/I9/I14 are all
      manifest-equality checks); **`acceptance.py`**
      (`pooled_record_frame` + `assert_pooled_gates`, imported by
      `prepare_training_data`, `generate_negatives` and `build_datasets`
      — inlining them in `train.py` recreates the PA-0001/PA-0002
      duplicate-logic mechanism); **a per-record continuous-feature
      extractor** for I17; **`verify_partition()`** in the pushdown +
      `to_crs` form.
- [ ] Plumb `gate_obs_only` through `calibrate.py:351` and
      `bench_pipeline.py:95` — neither exposes it today, and CR-0009's
      pre-CR baseline runs through `calibrate.py`.
- [ ] All **sixteen** consumers and five docs updated.
- [ ] **FIRST:** back up `data/pipeline/`, `data/negatives/` (51 MB),
      **and `old_road_dist/`, `new_road_dist/` and
      `INVESTIGATION_REPORT_errol_map.md`** — all untracked, all inputs
      to CR-0009's acceptance, protected by no CR until now.
- [ ] Run `analyze_grouse.py` → `prepare_training_data.py` →
      `generate_negatives.py`, in that order, recording each one's
      output. *(CR-0006 never ordered these; without the first, the
      partition never materialises.)*
- [ ] Record the full **I1–I19 (incl. I16b)** table, before and after —
      v6 said "I1–I13" because the I14–I19 rows had been spliced into
      § Review and were physically absent from the test-plan table.
      Measured "before" values, recorded here for the first time:
      I15 **1.462** records/val-block and **8.13 pp** block-vs-record gap
      (fails), I16 **+0.0678 (z 6.48)** k4 / **+0.0443 (z 5.71)** k8
      (fails both), I16b **+0.0823 (z 10.22)** k4 / **+0.0500 (z 8.37)**
      k8 (fails both), I17 **0.0306** (passes), I18 pooled **1.634 km**
      (fails) / per-region ME 2.553 / NH 2.628 / VT 2.392 km (all pass),
      I19 ME 0.5326 / **NH 0.6863** / VT 0.5294 (fails).
- [ ] Remove `prepare_training_data.BLOCK_SIZE_M_DEFAULT` (`:52`) once
      `regions.BLOCK_SIZE_M` exists — two names for one constant is the
      mechanism this CR centralises against.
- [ ] Re-run `inv_leakage.py` **including section 3 (pooled
      proximity)**, recorded as numbers; sections 1–2 must read 0.
- [ ] Allocate **BUG-0032** for the deferred
      `sample_background_points` nodata/0 conflation (§7).
- [ ] Promote `DRAFT_BUG-0029` into `docs/quality/bugs/` with a
      `BUG_LOG.md` row; update BUG-0027 and BUG-0029 to confirmed+fixed.
- [ ] BUG-0031: PA-0014's sweep **omission** of the
      `legacy/audit.py`/`analyze_grouse.py` pair, and its recording of
      "content-identical → harmless" as a permanent conclusion for
      copies this CR makes diverge. Include §4.2's prior-PA failure
      analysis for **PA-0002**, whose sweep left five runnable copies.
- [ ] `PREVENTIVE_ACTIONS.md`: PA-0020 scoped to **any per-class
      dataset-defining filter**, not only geographic ones — an uncovered
      sibling exists (`generate_negatives.py:159` drops negatives on
      `coord_uncertainty_m`; positives are never filtered on it).
      Correct PA-0002's and PA-0014's Swept? rows; update PA-0018's to
      record that its enforcement gap is closed by (b)/(c).
- [ ] **Confirm BUG-0033 is filed by the pre-CR bookkeeping batch** (see
      the PA-0021 item — this CR cites BUG-0033 in its own body and so
      cannot be its first definition). The acceptance-criteria defect class
      now has **ten documented failures on this CR alone** across six
      revisions, besides CR-0006's three and CR-0008's seven rounds.
      Shapes: a count criterion taken from a simulation of the wrong
      pipeline; invariants that were positives-only; invariants read from
      the pipeline's own bookkeeping instead of geometry; thresholds set
      from a single realisation or a 5-sample maximum; and enumerated
      outcomes where a change-set constraint was needed. `CLAUDE.md` §2:
      "a defect found in review counts, even if never observed running."
      No BUG doc exists for it and no CR files one — each assumed
      another would.
- [ ] **Confirm PA-0021 is filed by the bookkeeping batch that lands
      BEFORE this CR — this CR must not be the document that first defines
      it.** This CR quotes PA-0021(b)/(d) *in its own body* to justify its
      own acceptance design, and CR-0008/CR-0009 cite it as governing. A
      rule cannot be consulted (`CLAUDE.md` §3.2) before it exists, and a
      gate claiming to apply it cannot be checked against unwritten text.
      Precedent for bookkeeping with no CR: PA-0015/BUG-0019 and
      PA-0016/BUG-0022 (§1's trigger is a *code* change). Same for
      **BUG-0033**. Verified: `PREVENTIVE_ACTIONS.md` ends at **PA-0018**
      and `BUG_LOG.md` at **BUG-0027**.

      Clause set, as the v7 research requires it:
      *(a) every acceptance invariant must be measured on at least one
      constructed pipeline that is wrong in the way that invariant exists
      to catch, not only on the current data and the intended pipeline;*
      *(b) an acceptance set made only of "violation count == 0"
      predicates is **incomplete by construction** — such predicates are
      monotone under deletion — so it must contain at least one gate
      constraining what the change set **MAY** do (a pre-registered
      must-change count, an exact cardinality, or a digest of the intended
      change) such that a no-op and a deletion both fail;*
      *(c) any threshold in a hard gate must be calibrated against the
      statistic's sampling distribution, stated as a quantile over enough
      draws to support the quantile quoted (≥50 floor; a p99 needs ≥100),
      never a min/max over a handful — and the calibration must report the
      **broken-pipeline** distribution as well as the fair one, and the
      gate must **separate** them. **Exact predicates are exempt** (there
      is nothing to calibrate), and so is a statistic whose null over the
      pipeline's own randomness is a **point mass** — that must instead be
      pre-registered as a constant with stated headroom;*
      *(d) a gate whose failure mode is "record a justification" is an
      observation — label it one. A **pre-registered, scope-limited escape
      recorded in every artifact an escaped run produces** is legitimate;
      a case-by-case waiver makes the row an OBS;*
      *(e) a gate's reference must be recomputed independently of the
      change under test — never read from the artifact being verified, and
      never derived so that another gate in the same set makes it true by
      construction;*
      *(f) **every distributional acceptance row must name three fields —
      (class, subset, null population) — not one.** All three
      independently determine whether a real defect is visible.*

      **Lineage corrected: PA-0021 extends PA-0016, NOT PA-0018.**
      PA-0018's text contains no enforcement, acceptance, gate or
      threshold clause (verified by grep on the live file), so the claimed
      "extends PA-0018's enforcement clause" would cross-reference a
      clause that does not exist. PA-0016 forbids stating a **cause**
      without a check that could have falsified it; PA-0021 forbids
      accepting a **fix** without a check that could have failed it — same
      mechanism, next phase. PA-0018's own enforcement gap is recorded in
      **PA-0018's Swept? cell**, which this CR already owns.

      Clause (f) is the one the evidence most directly forces: it would
      have caught Break 2 (subset), Break 10B (class) **and** the NH-only
      miss (null population) — three of the ten breaks, by one rule.
- [ ] **Promote `DRAFT_BUG-0034` into `docs/quality/bugs/` with a
      `BUG_LOG.md` row** — diagnosed here, fixed in the next CR. (v5
      folded in the fix and still carried no promotion deliverable.)
- [ ] **Record the hand-off, and its exemptions (v7).** The follow-on CR
      must re-derive, on the post-fix footing (ME 2,854 / NH 828 /
      VT 1,127; I6 → 4,809 ± 2): **I6, I15, I18, all twelve I19′ cells,
      and C5–C8, C12–C14, C16–C17**. Every threshold in this document is
      measured on the pre-BUG-0034 footing of 6,230 positives; the I19′
      *design* transfers (cell granularity, which statistics, the
      family-wise `Z` form, the receptive-field floor on the attack
      ladder) but the **twelve thresholds do not**.

      **Exempt — these need no re-derivation, by construction:**
      **I16 and I16b**, whose nulls are now in-run permutation nulls
      carrying no frozen constant; the **exact predicates** I1–I4, I8/C4,
      C1, C2, C3; and the **supply rows** SUP0/SUP-O/SUP-R, whose null is
      a point mass and which are pinned as constants with headroom. That
      is the practical payoff of the in-run-null and exact-predicate
      forms: the BUG-0034 footing change stops invalidating most of the
      table.
- [ ] **Re-measure I19′'s twelve cells on the rebuilt negatives** from
      ≥400 seeds, re-derive `Z` as a family-wise quantile, and
      **re-measure the family-wise false-fail rate** before freezing.
      A clean `analyze_grouse.py` run is expected to move NH's `S`
      **downward** by ≈0.008–0.014 and `ks_feat` up by ≈15 %, measured by
      bracketing variants — and since the faithful headroom on the old
      0.64 gate was only **2.83 %**, no support threshold may be frozen
      before that run.
- [ ] **Persist the candidate pool and a pool-composition manifest.**
      `generate_negatives.py` discards `cand`, so C12–C17 and I16b's pool
      reading are **unreachable from `train.py`** and from any acceptance
      run on shipped data — the same position I14 is in today. Write
      `data/negatives/candidate_pool_{region}.csv` (lon/lat/state/split/
      is_nonveg, ~22 k rows, ≈1 MB) **with a sha256**, plus a
      per-(region,split) composition manifest (`n_hab_pool`, `n_nv_pool`,
      `n_hab_target`, `n_nv_cap`, `shortfall`, `topup_fired`, sum of
      weight by `weight_basis`, weight-weighted mean/sd per continuous
      feature, `common_name` and `evt_phys` counts). This mirrors
      CR-0008's G0.2-pins / G0.3-recomputes pair and doubles as the
      provenance record the axis otherwise lacks.
- [ ] **Enforce C2 as a raise, not a print.**
      `generate_negatives.py:281-293` currently only `print`s the
      shortfall and the beyond-cap top-up — which is why VT/val's
      habitat-only supply ratio of **0.87** has gone unremarked.
- [ ] **Add the composition and supply rows to the acceptance table** —
      C1–C17 and SUP0/SUP-O/SUP-R — with their call sites: C1/C3/C4/C9/C10/C11 in `train.py` + acceptance; **C2 and C12–C17 in
      `generate_negatives.py`** (the only place the candidate pool
      exists); C5-C8 in the acceptance run.
- [ ] Independent review with every concern dispositioned.

## Out of scope
- **Raster coverage** (BUG-0023 ME/VT, BUG-0024, BUG-0025, BUG-0030) →
  **CR-0008**.
- **The retrain, calibration refit, and the end-to-end map check** →
  **CR-0009**.
- **BUG-0026** (`diagnose_road_bias.py:82`, per-state roads in a
  diagnostic). This CR re-points that file and centralises the constant
  whose only live value-use is that defect, but does not fix it.
  Explicitly deferred, with a bug id.
- **BUG-0028** (prediction outputs carry no provenance).
- The 24–41 % inter-region categorical disagreement at identical
  coordinates. Measured, not diagnosed; needs its own investigation.
- `scripts_backup/` — untracked, holds further runnable copies.
- Model architecture, loss, hyperparameters. Adding CI.

## § Review

### Round 1 (v1) — two independent reviews
| reviewer | verdict | blocking |
|---|---|---|
| implementation lane | APPROVE WITH CHANGES | 1 (pooled `concat` index discipline) |
| acceptance lane | REJECT | 1 (assertion (d) a tautology) |

### Round 2 (v2) — two independent reviews
| reviewer | verdict | blocking |
|---|---|---|
| implementation lane | APPROVE WITH CHANGES | 1 (`weighted_take` `.loc` overshoot) |
| fresh, standalone | **REJECT** | 3 (acceptance set broken twice; §1.3/§1.4 unsatisfied; deliverables not executable in order) |

### Rounds 3–5 — VERDICTS NOT RECORDED (§1.3/§1.4 gap)
| round | reviewer | verdict | blocking | status |
|---|---|---|---|---|
| 3 | intermediate | **not recorded** | — | **must be recovered before approval** |
| 4 | intermediate / expedited | **not recorded** | — | **must be recovered before approval** |
| 5 | **formal, fresh** | **REJECT** | acceptance layer broken (breaks 10A/10B/10C) | mechanism recorded in the header; dispositions outstanding |

Round 5's finding is the one that governs v7. It treated the author's own
calibrations as unverified — correctly, because they were produced with
`inv_fix_breaks.py`, which **approximates** the negative sampler instead
of running the real draw — and then constructed three pipelines that
passed the entire table while producing a defective dataset. The faithful
harness (`inv_formalC_pool2.py` + `inv_formalC_lib.py`) exists because of
that finding, and every v7 threshold is being re-derived on it.

### The two acceptance breaks the formal review found, and how they close (v6)

**Break 1 — I19 was pooled, and a one-region skew hid inside it.** NH
holds 17 % of the pooled positives, so skewing only NH's negatives moved
the pooled statistic barely at all. Measured over 120 seeds, on the
pipeline this CR builds:

```
                      fair                              NH-only attack
POOLED      p50 0.5097  p99 0.5262  max 0.5266   p50 0.5339 ... min 0.5185   <- OVERLAPS
PER-REGION  p50 0.5533  p99 0.5874  max 0.5885   p50 0.6997 ... min 0.6821   <- SEPARATES
```

Pooled, the attack's minimum sits **below** the fair maximum — the same
shape that retired I7b and I10, and the reason v5's stated attack range
(0.574–0.852) was misleading: it was measured only against all-region
attacks. **Per region, fair max 0.5885 against attack min 0.6821** —
16 % clear on both sides of a 0.64 gate. I19 is now a per-region
statistic, maximised across regions, and is no longer provisional.

**Break 2 — nothing gated the geography of the negative split.** 5,621
of 9,482 occupied blocks (59 %) hold no positive, and their split comes
from `split_for_unassigned`'s md5 hash. Replace that hash with any
block-ordered rule — and since global ids are `bx_by`, sorting the id
*is* sorting on x — and validation negatives land tens of km east of
training negatives with **every gate green**.

The root cause was that **I15–I19 never said which record set they run
over**, and the calibration silently fixed it to positives: I16's null
was measured on the 3,861 positive-occupied blocks, so the 5,621
positive-free blocks were outside every gate. Every row now names its
record set, and I16b adds the missing one:

```
Moran's I, fair      positives-only blocks   p50  0.0021  max 0.0220
                     ALL-record blocks       p50 -0.0006  max 0.0159
Moran's I, attack    ALL-record blocks       p50  0.3587  min 0.3409   z = 61.4
```

The attack is invisible to the positives-only reading and **61 sigma**
on the all-record one. Both readings are kept — they answer different
questions — and each carries its own null.

**Also pinned:** the positive-free-block split rule (hash function,
digest size, input string) joins the thinner's in the manifest, since it
is now understood to be a spatial decision rather than a tie-break.


**Dispositions.** Every concern from **Rounds 1 and 2** is dispositioned
below; none dropped. **Rounds 3–5 are not dispositioned at all** — see the
gap table above; that is the §1.3 defect blocking approval, and it is not
closed by this table. v2 recorded a seven-line summary and left `§ Review`
reading "Not yet reviewed" — a §1.3/§1.4 violation in its own right,
and the reason this table exists.

| concern | disposition |
|---|---|
| (d) is a tautology given (a) | **Accepted** — replaced by the occupied-block support check; now withdrawn again pending re-calibration (see I10). |
| pooled `concat` index discipline | **Accepted** — `ignore_index=True` mandated in §5, with the 3-pick→6-row demonstration. |
| `verify_partition()` has no negative call site | **Accepted** — added in §5. |
| NH box deferred but not optional | **Accepted** — resolved by dropping windowless candidates before sampling. |
| R1 evadable; R5–R7 missing | **Accepted** — R1 made structural; R5 (cached-frame mutation), R6, R7 added. |
| escape flag scoped to (d) only | **Accepted** — single pre-CR mode covering all four, recorded in any artifact produced. Note a reviewer argues (a)–(c) should stay unconditional; **see open item below.** |
| acceptance set broken (dropped shuffle) | **Accepted** — I14/I15 added. |
| acceptance set broken (rescaled (d) attack) | **Accepted** — I10's threshold withdrawn; replacement specified at receptive-field scale. |
| §1.3/§1.4 unsatisfied | **Accepted** — this table. |
| deliverables not executable in order | **Accepted** — backup moved first. |
| Impact's 6,230 derivation yields 6,508 | **Accepted** — see Corrections. |
| PA-0020's `coord_uncertainty_m` example is inert | **Accepted** — see Corrections. |
| `TIGER_YEAR` owned by no CR | **Accepted** — added to §1's centralisation list. |
| A6/`verify_partition` disposition should block approval, not implementation | **Open** — see below. |

**Both open items are now RULED, by the reviewer who raised them:**
1. **The pre-CR escape mode covers (d) only.** (a)–(c) stay
   unconditional. The premise that the test plan needs a blanket mode is
   false and was falsified directly: every "today" figure in the
   acceptance table was produced by reading the CSVs, with no `train.py`,
   `calibrate.py` or `bench_pipeline.py` involvement, and (a)/(b)/(c)
   touch no polygon at all. The polygon path measures 1.19 s, so cost is
   not the constraint either.
2. **The `verify_partition()` exceptions are dispositioned before
   APPROVAL, not before implementation.** I9's `required` cell otherwise
   resolves to a rule that does not exist, which is not reviewable.
   **Disposition: drop the affected records and record the count and
   coordinates in I9's output** — not an audited exception list, which
   PA-0021(b) argues against as a blacklist that grows silently. Cost:
   6 of 35,678 candidates (0.017 %). Note "relabel to the polygon" is
   unavailable for 5 of the 6 — they are inside no polygon at all.

**Author sign-off:** withheld.

## Corrections to v2
- **Impact's chain "8,422 → 6,702 → ≈6,230"** yields **6,508**, which
  this CR elsewhere calls a wrong-grid diagnostic. The correct recipe is
  I6's: keep the row from the record's **own state** file → habitat
  filter = 6,411 → pooled thin = **6,230**. Confirmed by three reviewers
  and by the author reproducing the same error in a verification script.
- **NH's post-partition count is 1,079 (−52 %), not 1,116.** 1,116 is the
  state composition of NH's own file and discards the 137 + 717 NH-state
  records held in the ME and VT files. Per-region: ME **3,659**,
  NH **1,079**, VT **1,492**.
- **PA-0020's cited example is inert.** `coord_uncertainty_m` is null in
  all 265,212 candidate rows and `coordinateUncertaintyInMeters` in all
  43,024 sighting rows, so `generate_negatives.py:159` drops nothing.
  The broadening may still be right in direction, but this evidence for
  it does not exist and is withdrawn.
- `35,792` → **35,678** (the code dedups at 5 dp); I12's undetectable
  window is ≈30–**79** m, not 30–65; `build_datasets` is `:238-317`;
  §7's `bad = ...` is at `:143`; `analyze_grouse`'s `MIN_VALID_FRAC`
  check is at `:444`; the risk table's "723 violating blocks" is
  unreproducible and is withdrawn.
- **The "today" column is measured across mixed pipeline generations** —
  `thinned_positives_*` hold 81 / 70 / 76 coordinates absent from the
  current `evaluated_sightings_*` habitat subset. It must be re-measured
  after one clean `analyze_grouse.py` run.
