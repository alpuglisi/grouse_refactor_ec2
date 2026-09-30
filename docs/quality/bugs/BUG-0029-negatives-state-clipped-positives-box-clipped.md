# BUG-0029: negative candidates are clipped to a state, positives to a box, so each region's out-of-state positives have no negatives

> Promoted from `DRAFT_BUG-0029-…md` (committed at `f8fafbc`) by CR-0007
> deliverable 6, 2026-09-30. §§1–5 and 7 are the investigation as drafted.
> §6 records the corrective action as assigned. §8 was rewritten to cite
> PA-0020 as filed (the draft's narrower geographic-only wording is
> superseded; see `res_qms_PA-0019-0020-0021-draft-rows.md`).

## 1. Description
Positive records are assigned to a region by **bounding box**
(`analyze_grouse.clip_to_region`, `BOXES[region]` from `regions.py`).
Negative candidates for the same region are downloaded from GBIF with a
**`stateProvince` filter** (`get_negatives.py:268`), so they can only
come from that one state's administrative area. The region's boxes reach
well into neighbouring states — NH's is `(-72.626, 42.605, -70.600,
45.398)` — so each region's dataset covers a rectangle for positives and
a state polygon for negatives.

The result: the part of each region's box that lies outside its own
state contains positives and essentially **no** negatives. Pooled across
regions by `train.py`, the label prevalence becomes a function of
geography in a model that has no location input.

## 2. Where encountered
Found during the Errol map investigation (2026-09-30,
`INVESTIGATION_REPORT_errol_map.md` §2 step 7 and §4), while checking
whether the in-box AUC could be used to measure a fix.

- `get_negatives.py:266-269`, `base_params`:
  ```python
      def base_params(st, key, year):
          return {"datasetKey": EOD_DATASET_KEY, "taxonKey": key,
                  "country": "US", "stateProvince": STATES[st],
                  "year": year, "hasCoordinate": "true"}
  ```
  with `get_negatives.py:45`:
  ```python
  STATES = {"ME": "Maine", "NH": "New Hampshire", "VT": "Vermont"}
  ```
  writing `data/negatives/gbif_negatives_{st}.csv`, which
  `generate_negatives.py:140` reads as its **only** candidate pool:
  ```python
      cand_path = f"data/negatives/gbif_negatives_{region}.csv"
  ```
- Positives, by contrast: `analyze_grouse.clip_to_region`,
  `longitude.between(min_lon, max_lon) & latitude.between(min_lat, max_lat)`
  over `BOXES[region]`.

## 3. What it caused to fail
**Measured on the real datasets** (spatial join of every region's
positives and negatives against TIGER state polygons,
`data/roads/tl_2023_us_county.zip`):

```
NH pos: n=2244 by state {'NH': 1116, 'VT': 728, 'ME': 400}
NH neg: n=2244 by state {'NH': 2243, 'ME': 1}
ME pos: n=3860 by state {'ME': 3723, 'NH': 137}
ME neg: n=3860 by state {'ME': 3859, 'other/none': 1}
VT pos: n=2261 by state {'VT': 1544, 'NH': 717}
VT neg: n=2261 by state {'VT': 2261}
```

- **Half of the NH region's positives (1,128 of 2,244) lie outside New
  Hampshire**, against **1 of 2,244 negatives**. The NH dataset is
  balanced 1:1 by count and violently unbalanced in space.
- Pooled over all three regions, prevalence by state is ME 4,123 pos /
  3,860 neg = **51.6 %**, NH 1,970 / 2,243 = **46.8 %**, VT 2,272 /
  2,261 = **50.1 %**. (Modest on its own; the spatial *support* mismatch
  above, not this figure, is the defect.)
- **It broke the metric this investigation needed.** Inside the reported
  Errol box the 66 in-box points are 14 ME positives, 0 ME negatives,
  41 NH positives, 11 NH negatives. With no Maine negatives, in-box AUC
  *rewards* inflating the whole Maine side: the defective map scored
  AUC 0.7570 and the corrected one 0.7273. The plan's step 7 names
  in-box AUC as the number to measure a fix against
  (`INVESTIGATION_PLAN_errol_map.md` §9); here it points the wrong way,
  and only the state-split statistics settled it.
- **Suspected, unmeasured:** a spatially non-stationary label
  distribution that the model can only express through the features
  correlated with it. Whether it contributes to any real scoring bias
  is an **untested hypothesis** and is explicitly *not* claimed as a
  cause of the reported Errol symptom — that is BUG-0023, confirmed
  separately by three checks.

## 4. What the defect was
Two different definitions of "this region", one per label class. The
positive side is a rectangle:

```python
def clip_to_region(sightings, region):
    min_lon, min_lat, max_lon, max_lat = BOXES[region]
    in_box = (
        sightings['longitude'].between(min_lon, max_lon) &
        sightings['latitude'].between(min_lat, max_lat)
    )
```

The negative side is a state name handed to a remote API:

```python
        return {"datasetKey": EOD_DATASET_KEY, "taxonKey": key,
                "country": "US", "stateProvince": STATES[st],
                "year": year, "hasCoordinate": "true"}
```

Nothing downstream reconciles them; `generate_negatives.py` samples,
buffers, weights and block-splits whatever the state-filtered file
contains, over the box's block grid.

## 5. Root cause analysis (Five Whys)
1. *Why do out-of-state parts of a region's box have no negatives?* The
   negative candidate pool was fetched with `stateProvince = <the
   region's state>`.
2. *Why a state filter?* GBIF's `stateProvince` is the convenient
   handle for "get me the records for New Hampshire", and the region was
   conceived as a state.
3. *Why doesn't that match the positives?* The positives use
   `BOXES[region]`, a rectangle drawn around each state's sighting
   extent with a buffer, for raster download. Membership for records
   was then taken from the same rectangle.
4. *Why did nobody notice the two disagree?* Both produce the right
   *count* — the negative sampler draws as many negatives as there are
   positives, so the dataset looks balanced at 1:1. Nothing compares
   their **spatial support**; a count-based check cannot see it.
5. *Why was there no rule?* PA-0018 requires a spatial computation's
   source to be "everything that intersects the computation's full
   extent plus a margin, never a per-state or per-region subset chosen
   by label". This is exactly that, applied to the negative-sample pool.
   PA-0018's own sweep looked at *computations* — distances, buffers,
   thinning, block splits — and examined `generate_negatives.py`'s 300 m
   buffer. It did not examine where the candidates it buffers **come
   from**.

**Root cause:** the two label classes of one dataset are drawn from
differently-shaped regions — positives from a bounding box, negatives
from a state polygon — so the dataset's positive support and negative
support do not coincide, and no check compares them.

## 6. Corrective action
**Assigned: membership — CR-0007; split and draw — CR-0012; assumed negatives — CR-0015.**
- *Membership (the positive half), CR-0007 (implemented 2026-09-30,
  deliverables 2–5):* `state` is the only region-membership key for
  sighting records. `analyze_grouse.load_all_sightings` raises unless every
  record lies in its own state's county polygons
  (`analyze_grouse.check_state_partition`, `regions.verify_partition`).
  `evaluated_sightings_R` holds only state-R records (CR-0007 P1–P3 PASS,
  `docs/quality/evidence/CR-0007-gates.txt`). Positives are now assigned by
  state, the same definition the negatives' `stateProvince` query uses
  (option 1(a) below).
- *Split and draw, CR-0012 (merged `4eb10dd`; real run `1bc2df6`,
  18/18 CR-0013 GATEs):* both classes are split on one global grid over
  the same state partition, and the negatives are drawn per (region,
  split) against the positives of that cell.
  - E1 checks `state == region` for every positive, negative and pool
    row.
  - E9 checks each cell's count against `n_pos`.

  **The positive-side part of this bug is fixed.**
- *Assumed negatives, CR-0015 (2026-09-30):* `train.sample_background_points`
  drew over the region's raster box, and 36.0 / 52.5 / 47.3 % (ME/NH/VT)
  of accepted points were out of state. It now keeps only
  `regions.in_state` draws (CR-0015 §2, deliverable 6, `2c23d7d`).
  V1 finds 0 out-of-state points in every region, using an independent
  polygon test on real data (deliverable 7b,
  `docs/quality/evidence/CR-0015-background.txt`).

Status: **FIXED** (CR-0015 deliverable 9 closure rule: CR-0012 landed,
and CR-0015 deliverable 7b passed). It becomes CLOSED when CR-0009
closes.

Original proposal (kept for the record):
1. **Make both classes use one definition of a region.** Either is
   defensible, but it must be the same one:
   - if regions become a true partition (the fix BUG-0027 needs
     anyway), assign both classes by the same partition; or
   - fetch negatives for every state the box intersects, then clip both
     classes to the box.
   Option (a) composes with BUG-0027 and is likely the cheaper joint
   fix; the CR should decide.
2. **A support check at dataset-build time:** compare positive and
   negative spatial support (e.g. occupied 3 km blocks, or a convex
   hull / state histogram) and fail or warn when they diverge beyond a
   threshold. This is the check whose absence is why 50 %-of-positives
   went unnoticed; it is the enforcement for the rule in §8.
3. **Re-fetch negatives and rebuild the splits.** Requires network
   access to GBIF, and invalidates every existing checkpoint's training
   set — so it should be done in one pass with BUG-0027's split fix and
   BUG-0023's `road_dist` regeneration, not three separate retrains.

**Verification:** re-run the §3 by-state table and confirm the negative
distribution matches the positive distribution region by region; then
re-run `inv_points_auc.py` and confirm the Errol box has ME negatives,
making in-box AUC a usable measure again.

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`:

- **BUG-0027 / PA-0018 — same family, and the closest prior.** BUG-0027
  is overlapping *boxes* plus a per-region split; this is a *box* for
  one class and a *state* for the other. Both are "a per-region subset
  chosen by label, used where the extent is something else". They share
  the region-membership machinery and should be fixed together.
- **BUG-0023 / PA-0017** — per-state source (TIGER roads) written onto a
  multi-state grid. Identical shape one level down, in rasters rather
  than records. This bug is its analogue for the *record* pipeline's
  negative class. Notably: the reported Errol symptom and this finding
  come from the same underlying mistake — treating a region's
  rectangular grid as if it were its state.
- **BUG-0026** — `diagnose_road_bias.py`, per-state roads in a
  diagnostic. Same family.
- **BUG-0001 / PA-0001** — duplicated box constants. Concerns the values,
  not their use. Not this.

Not a recurrence of a *fixed* bug: BUG-0027 is still OPEN and unfixed,
and this was found by the same rule (PA-0018) that found it. It is a
second instance in the same sweep's territory that the sweep missed.

**Prior-preventive-action failure analysis (PA-0018).** PA-0018 is the
right rule and it did not catch this. Why:

- **The sweep was scoped to computations, not to data sources.**
  PA-0018's Swept? entry reads "every per-region spatial computation on
  `main`, from code", and it did examine `generate_negatives.py`: "the
  300 m buffer uses the region's box-clipped sightings, which already
  include neighbouring-state sightings inside the box — no new instance
  beyond the outer box edge". That inspected what the buffer is measured
  *against* and passed it. It never asked what the candidate pool being
  buffered is, so it stopped one file short of
  `data/negatives/gbif_negatives_{region}.csv` and one file further
  short of `get_negatives.py`.
- **The per-state filter is not in this repository's spatial code.** It
  is a `stateProvince` string in an HTTP query parameter to GBIF. A
  sweep reading spatial computations does not look like one that reads
  API query dictionaries, so the instance was invisible to the method
  used.

## 8. Preventive action
**PA-0020** (filed by CR-0007 deliverable 6, 2026-09-30; extends PA-0018
from spatial computations to the **acquisition and selection** of the data
they consume, on **every** axis). The operative rule is the row in
`docs/quality/PREVENTIVE_ACTIONS.md`. In summary: any parameter that
decides which records enter a dataset is part of the computation
downstream of it. Where classes are acquired separately, their supports
must be compared on every axis such a parameter acts on. Equal counts are
not evidence of matching support.

This bug is PA-0020's geographic instance. BUG-0034 is its temporal
instance and the only live evidence for clauses (ii)–(iv). The draft of
this section proposed a geographic-only rule. That wording is superseded
by the filed row and must not be used.

**Sweep (§3.5).** Recorded in PA-0020's Swept? cell (read-only pass,
2026-09-30): the live instances are this bug and BUG-0034;
`MAX_COORD_UNCERTAINTY_M` is inert (0 of 265,212 candidate rows carry the
field); the source-axis asymmetry (two positive sources, one negative) is
owned by BUG-0034.

**Mechanical enforcement (§3.4).** A dataset-build support check (compare
the classes' occupied spatial blocks and year histograms; fail on
divergence) is feasible and belongs with CR-0012's pooled-split checks. Not
yet implemented. No CI exists, so it would run as a build-time assertion.
