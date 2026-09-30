# BUG-0027: Overlapping region boxes plus a per-region block split can put the same record in training for one region and validation for another

## 1. Description
Found by the PA-0018 sweep (BUG-0026 follow-up). Records are assigned to
regions by **bounding box**, not by state, and the boxes overlap heavily.
A record inside two boxes is included in both regions' datasets. Each
region then runs its own thinning and its own spatial block train/val
split: a block grid anchored at *that region's* box corner, and an
independent random draw of validation blocks. The two splits are never
reconciled, so the same record, or records a few metres apart, can be
**training data in one region and validation data in another**.
`train.py` pools all regions' train sets and all regions' val sets
without de-duplication.

## 2. Where encountered
- Box membership: `analyze_grouse.py` `clip_to_region` (main:202-224),
  keeping `longitude.between(min_lon, max_lon) &
  latitude.between(min_lat, max_lat)` for `BOXES[region]`.
- Boxes (`regions.py` on this branch; `prepare_training_data.py:46-49`
  and `analyze_grouse.py` on main):
  - ME `(-71.158, 42.889, -66.852, 47.555)`
  - NH `(-72.626, 42.605, -70.600|-70.614, 45.398)`
  - VT `(-73.510, 42.632, -71.422, 45.112)`
- Overlaps:
  - NH∩VT: lon −72.626…−71.422 (about 1.2° of NH's about 2.0° width);
  - NH∩ME: lon −71.158…−70.600.
  - Most of the NH box is inside another region's box. Errol
    (−71.14) is inside both the NH and ME boxes.
- Per-region split: `prepare_training_data.py` `assign_spatial_blocks`
  (main:87-116), called per region at main:164-165.
- Pooling: `train.py` `build_datasets`, `for region in regions:`, then
  concatenated with no cross-region de-duplication.

## 3. What it caused to fail
- **Validation leakage (suspected, magnitude unmeasured).** A sighting in
  an overlap can sit in a training block of one region and a validation
  block of the other. The model is then scored on points it trained on,
  or on near neighbours of them, inflating validation AUC/AP.
- **Undermines every comparison made this session.** The block holdout
  exists to prevent exactly this leakage (`prepare_training_data.py`
  docstring, "SPATIAL BLOCK HOLDOUT"); it only holds within one region.
- **Double weighting.** Records in overlaps appear twice (or more),
  over-weighting border-area habitat in training.
- **Unconfirmed on real data.** The number of records in two or more
  boxes, and how many land in conflicting splits, has not been counted.
  The check: load every region's `train_positives`/`val_positives`, match
  on rounded coordinates across regions, and count train/val collisions.
  Also count points within the block size (3 km) of an opposite-split
  point in another region.

## 4. What the defect was
Region membership by overlapping box (`analyze_grouse.py`, main):
```python
def clip_to_region(sightings, region):
    min_lon, min_lat, max_lon, max_lat = BOXES[region]
    in_box = (
        sightings['longitude'].between(min_lon, max_lon) &
        sightings['latitude'].between(min_lat, max_lat)
    )
```
A block grid and random draw per region (`prepare_training_data.py`,
main):
```python
    min_lon, min_lat, max_lon, max_lat = box
    ...
    x0, y0 = min(corners_x), min(corners_y)

    bx = np.floor((df['x_5070'].values - x0) / block_size_m).astype(int)
    by = np.floor((df['y_5070'].values - y0) / block_size_m).astype(int)
    ...
    shuffled_blocks = block_counts.sample(frac=1, random_state=seed).index.tolist()
```
called once per region:
```python
        block_id, split = assign_spatial_blocks(
            thinned, BOXES[region], args.block_size_m, args.val_fraction, args.seed)
```

## 5. Root cause analysis (Five Whys)
1. *Why can one record be both train and val?* It belongs to two regions,
   and each region splits independently.
2. *Why does it belong to two regions?* Membership is decided by
   rectangles that overlap, not by a partition such as the state polygon
   or one nearest region.
3. *Why doesn't each region's split see the other's?* The spatial
   holdout, a computation that needs one consistent view of all records
   in space, is run on a per-region subset: grid origin from that
   region's box, random draw per region.
4. *Why was that considered safe?* The pipeline treats regions as
   disjoint units ("partition each region into a grid of blocks"). The
   rectangles were chosen for raster downloads, where overlap is
   harmless, and reused for record membership, where it is not.
5. *Why no check?* Nothing verifies that regions partition the records,
   or that the pooled train and val sets are spatially disjoint.

**Root cause:** a spatial computation that must be global (the train/val
block holdout) is run separately on per-region subsets selected by
overlapping labels (bounding boxes), so its guarantee holds within one
region but not across the pooled data.

## 6. Corrective action
**Assigned (2026-09-30): membership — CR-0007; split and draw — CR-0012.**
- *Membership (item 1 below), CR-0007 (implemented 2026-09-30,
  deliverables 2–5):* records are partitioned by `state`, checked against
  TIGER county polygons (`regions.verify_partition`, called from
  `analyze_grouse.check_state_partition`). Each `evaluated_sightings_R`
  holds only state-R records, and the three files' keys are pairwise
  disjoint (CR-0007 P1–P3 PASS; before: ME∩NH 1,184, NH∩VT 3,271 shared
  keys; `docs/quality/evidence/CR-0007-gates.txt`).
- *Global grid, pooled split and draw (items 2–3), CR-0012 (code
  `20a52c1`, merged `4eb10dd`, follow-ups `df83c27`; real run
  `1bc2df6`):*
  - one global block grid (`regions.block_ids`, origin
    `BLOCK_ORIGIN_5070`);
  - one pooled thin and one pooled block split over every region
    (`prepare_training_data.py`);
  - one pooled buffer and draw (`generate_negatives.py`).

  CR-0013's exact pooled gates PASS on the rebuilt files (18/18,
  `docs/quality/evidence/CR-0012-d6/acceptance.log`):
  - **E4:** 0 keys in both train and val, per class and across classes;
  - **E5:** 0 recomputed blocks hold both a train and a val record.

  Before the fix, E4 counted 522 keys and E5 882 blocks (CR-0012 § Why
  now). `acceptance_split.standing_checks` re-runs E4/E5 on the files
  `train.py` reads before every `build_datasets` (`train.py:250`), so
  a later edit cannot reintroduce the leak unnoticed (item 3 of the
  original proposal).

Status: **FIXED (CR-0012), 2026-09-30.** It closes after CR-0009's
retrain, because the split change invalidates every checkpoint and
metric. CR-0009 deliverable 10 records the closure.

Original proposal (needs a CR: it changes the dataset split, a data
schema and behaviour change):
1. **One partition of records into regions:** by state polygon or
   `stateProvince`, or nearest-region-by-point, never overlapping boxes.
2. **One global block grid and one assignment across all regions:** a
   shared origin (e.g. a fixed EPSG:5070 origin) and a single random draw
   over the pooled block set, so a block is train or val everywhere.
3. **A pooled-split check in `train.py`:** fail if any coordinate
   (rounded) appears in both train and val, and warn on opposite-split
   points closer than the block size.

Regenerating splits invalidates every checkpoint and every metric
comparison. Retrain and re-measure after the fix; the validation numbers
may drop, and a drop would be the real performance, not a regression.

(Status as originally filed: OPEN, unconfirmed on real data. Superseded
by the status line at the top of this section.)

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`:
- **BUG-0001 / PA-0001** (duplicated geographic constants, the box values
  themselves) concerns constant *values*, not how the boxes are *used*.
  The boxes are now shared (`regions.py`, CR-0002) and the overlap
  persists.
- **BUG-0023/0026 / PA-0017/0018:** per-label subsets fed into spatial
  computations. Same family. This is the PA-0018 mechanism applied to the
  holdout split rather than to a distance.

Not a recurrence of a fixed bug. PA-0018 covers it (it was found by that
rule's sweep).

## 8. Preventive action
Covered by **PA-0018** (BUG-0026). No new rule. Mechanical enforcement
proposed in §6.3: a pooled train/val disjointness check at dataset build
time. That is feasible and would catch this class directly; it needs a
CR.
