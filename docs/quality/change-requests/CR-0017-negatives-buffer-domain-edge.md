# CR-0017: Drop candidate negatives within BUFFER_M of the sightings' acquisition-domain edge

**Status: APPROVED (v3), 2026-09-30.** Author and reviewers approved;
user pre-authorised (2026-09-30). Verdicts and dispositions:
`CR-0017-review-log.md`. This document states only current intent.

## Scope
In `generate_negatives.py` pool step 6, also drop every candidate whose
EPSG:5070 distance to the edge of the sightings' acquisition domain (the
union of the ME, NH and VT county polygons) is `≤ BUFFER_M`. Extend
CR-0013's acceptance to match, then regenerate the pool and negatives.

## Fixes
- **BUG-0050**: the 300 m buffer has no sightings across the Canadian
  border.
- **A sibling instance, found while scoping this CR**: the same blindness
  at the NY and MA state lines. It gets its own BUG, placeholder
  **BUG-0064**; the lead allocates the id (deliverable 8). BUG-0050's evidence script
  (`docs/quality/evidence/CR-0012-d8/canada_buffer.py`) included NY and
  MA counties in its boundary, as if sightings existed there. None do:
  every sighting was acquired by `stateProvince` ∈ {Maine, New Hampshire,
  Vermont} or eBird `US-ME`/`US-NH`/`US-VT` (43,024 of 43,024 rows; same
  evidence file, line 1).

## Why now
Pool step 6 (`generate_negatives.py:392-400` on this branch;
`:380-389` in CR-0015's implementation, `3add80b`) guarantees "no negative
within `BUFFER_M` of a known grouse". It checks that only against sightings
inside ME ∪ NH ∪ VT. A candidate near the edge of that domain is tested
against part of its 300 m neighbourhood. The rest lies in Canada, NY or
MA, where no sighting was acquired. E7 (CR-0013) reads the same sightings,
so it cannot see this (BUG-0050 §5).

**Measured on today's accepted artifacts** (the CR-0012 deliverable 6
files, whose digests equal `data/pipeline/acceptance_record.json`):
`docs/quality/evidence/CR-0017/preregister.txt`, produced by
`preregister.py` in the same directory. Every number below comes from it.

| set | rows | within `BUFFER_M` of the domain edge | nearest outside: Canada | NY | MA |
|---|---|---|---|---|---|
| C, pool | 22,187 | 88 | 39 | 31 | 18 |
| N, selected | 6,232 | 23 | 12 | 6 | 5 |

- **The 23 selected negatives by region and split:**
  - ME: 7 train, 2 val;
  - NH: 1 train;
  - VT: 10 train, 3 val.
- **Overall:** 18 of 4,986 train negatives and 5 of 1,246 val negatives.
- **The Canadian column** reproduces BUG-0050's 39 and 12 exactly.

Whether any of these rows really has a grouse within 300 m is unknown.
No sighting was acquired there (PA-0016). The defect is an unverified
guarantee, not an observed wrong label.

## The change

### 1. Root cause
The buffer's reference set was chosen by acquisition label: three US
states. Its neighbourhood crosses the edge of that set's domain (BUG-0050
§5). PA-0023 says so for "a national or other data-domain border". The
data domain here is the extent the acquisition query selects (PA-0020(v)).
That is ME ∪ NH ∪ VT, not the United States.

The fix is PA-0023's nodata option. A candidate whose neighbourhood leaves
the domain cannot be certified, so it is dropped. It is never relabelled
or kept.

### 2. Pipeline (normative; amends CR-0012 §2 pool step 6)
**Domain D.** D is the union of the TIGER `COUNTY_POLYGONS_YEAR` county
polygons whose `STATEFP` is in `STATE_FIPS`. It is built from the same read
as `_state_polygons()` (the polygons `verify_partition` and `in_state`
use): the file comes through `PATH_TEMPLATES["tiger_county"]`, with the
same `STATEFP` filter, and is taken as EPSG:4269 if it has no CRS. The
counties are then projected **from the file CRS straight to EPSG:5070**
and unioned. D is not built from the EPSG:4326 copy, so there is no
NAD83→WGS84 step whose result depends on the PROJ build.

**Edge distance.** For a point `p` in EPSG:5070 (from `regions.to_5070`
of its lon/lat, never from an `x_5070` column):
- `edge_m(p) = distance(p, boundary(D))` if D contains `p`;
- otherwise `edge_m(p) = 0.0`.

**Pool step 6, as amended.** Drop a candidate if **either** of these is
true:
- **(a)** its squared distance to any row of any `evaluated_sightings_R`
  is `≤ BUFFER_M²` (unchanged);
- **(b)** `edge_m ≤ BUFFER_M` (new).

(a) and (b) are row filters on the same step-5 pool, so their order does
not matter. The manifest count `"6"` keeps its meaning: rows remaining
after step 6, now after both filters. The manifest schema is unchanged.
The run log prints three counts: the rows (a) drops, the rows only (b)
drops, and the overlap.

**Placement.** The new filter is part of step 6, after thinning (step 5),
as the sighting buffer is. So thinning is unchanged. Steps 7–10 act on
each row alone: the envelope binners are fitted on sightings, not on
candidates. So the final pool is the old pool minus exactly the rows with
`edge_m ≤ BUFFER_M`. This is what gate MC2 checks.

**Code.**

| file | change |
|---|---|
| `regions.py` | New `domain_edge_m(x, y, *, domain=None)` (x, y in EPSG:5070): returns a float64 array of `edge_m`. With `domain=None` it builds D once, as above, and caches it. One private
helper reads the filtered counties in the file CRS, and both D and
`_state_polygons()` use it. So the template, the `STATEFP` filter and the
missing-CRS default exist once. `domain` is the test seam: a shapely polygon that replaces D. No new constant: `BUFFER_M` and `STATE_FIPS` already exist (PA-0001, PA-0025). |
| `generate_negatives.py` | New `domain_edge_drop_mask(lon, lat)` = `regions.domain_edge_m(*to_5070(lon, lat)) <= BUFFER_M`. Pool step 6 drops `in_buffer \| at_edge`. Module docstring step 6 and the summary print are updated. |
| `tests/test_cr0017.py` (new) | Synthetic unit tests (§ Test plan). |

`regions.py` still imports geopandas only inside functions.

**Dependency on CR-0015 (APPROVED, being implemented).** This CR lands
**after CR-0015's implementation is merged and its gate B1 has passed**.
It is written against that code: branch
`worktree-agent-a74570e35615ea5e3`, head `3add80b`, under code review. At
that head, CR-0015 changes nothing in `generate_negatives.py`, `regions.py`
or `prepare_training_data.py` beyond deliverable 5 (`52cb67c`):
- `to_5070` is `regions.to_5070`, reached through
  `prepare_training_data.to_5070`;
- pool step 10 calls `regions.block_split`.

CR-0015 does not touch pool step 6, and CR-0017 does not touch step 10 or
the transform. Two reasons for the order:
- B1 compares CR-0015's re-run against the CR-0012 deliverable 6 digests.
  Regenerating first would make B1 impossible.
- MC0 (below) needs the same unchanged baseline.

CR-0015's assumed-negative sampler has no presence buffer (CR-0015
§ Out of scope), so this CR does not change it.

### 3. Acceptance (amends CR-0013; normative for the replay author)
**Config (`docs/quality/acceptance_split.json`).** A new
`paths.domain_edge` entry:
- `source`: the string `"paths.county_polygons"`, a reference by key. The
  path, sha256, `where` and `dissolve_by` are not copied; `load_config`
  refuses any other value;
- `edge_crs` EPSG:5070. The dissolved polygons are projected from the
  file CRS (`county_polygons.source_crs`) straight to it;
- rule: "union of the dissolved polygons; `edge_m` = distance to the
  union's boundary for contained points, else 0; drop iff
  `edge_m ≤ BUFFER_M`".

The `GATE_SECTION_SHA256` pin for `paths` in
`tests/test_acceptance_split.py` is updated. That update is part of this
CR's review.

**R3.** The replay's `buffer_drop` also applies rule (b). It builds D from
its own county read and dissolve (the `county_states` read, projected
from the file CRS to EPSG:5070), not from `regions`, so design rule 1 (independence) holds. R3's per-step counts
check the new `"6"` count.

**New gate E13 (exact).**

| id | set, pooling | predicate |
|---|---|---|
| E13 | N combined, pooled; C | `edge_m > BUFFER_M` for every row, with `edge_m` recomputed from lon/lat by the replay's own D |

- E13 is not in the standing subset, because it needs geopandas. The
  record digests cover it, as they cover E7.
- E7 is unchanged. It is still right for sightings inside D.

**New attack rows** (CR-0013 § Attacks; in
`tests/test_acceptance_split.py`, on the synthetic fixture). The fixture
already has a non-domain county (STATEFP 36) beyond part of the domain
edge. Each attack names the fixture rows it needs; the test asserts they
exist, so no attack can pass vacuously (PA-0021(a)).

| attack | fixture rows required | must fail |
|---|---|---|
| No domain-edge filter | ≥ 1 candidate with `edge_m ≤ BUFFER_M`, more than `BUFFER_M` from every sighting, that survives steps 7–10 and is selected | E13, R3, R4 |
| D = every US county (the edge is only the national border) | ≥ 1 such candidate whose nearest outside point is in the non-domain county | E13, R3, R4 |
| D not dissolved (per-state polygons, so the edges between states count) | ≥ 1 candidate within `BUFFER_M` of an internal state line, more than `BUFFER_M` from the domain edge and from every sighting | R3 (over-drop; E13 passes) |
| Edge radius `BUFFER_M / 2` | ≥ 1 candidate with `BUFFER_M / 2 < edge_m ≤ BUFFER_M` | E13, R3 |
| Edge filter applied before thinning | a pair closer than `MIN_SPACING_M` that straddles the band edge, where the in-band member comes first in the seeded thin order, so the thin keeps it and drops its out-of-band neighbour | R3 |

**Must-change gate MC (PA-0021(b); one-off, for this regeneration).**
`docs/quality/evidence/CR-0017/check_must_change.py --old <pre-CR tree>
--new <post-CR tree>`. It is committed before approval (CR-0011 A3) and
reads the pre-registered removals in `preregister_keys.csv`:
- **MC0:** the old tree's 20 digested artifacts equal the CR-0012
  deliverable 6 record copy. Otherwise the pre-registration is stale and
  MC fails.
- **MC1:** P and B are byte-identical.
- **MC2:** C = old C minus exactly the 88 pre-registered rows. Every other
  line is byte-identical, in the same order.
- **MC3:** per region, the negatives removed are exactly the pre-registered
  rows (see § Why now). Every retained row's line is byte-identical.
- **MC4:** per (region, split, `is_nonveg`):
  - the row count is unchanged, and additions equal removals;
  - every added row is a row of the new C in the same region and cell,
    and equals it, as text, on every column N and C share;
  - no cell appears in the new tree that is absent from the old;
  - every added row has `label` 0;
  - the new combined file is in canonical (longitude, latitude) order.
- **MC5:** each `train_`/`val_negatives_R` file is the header plus the
  combined file's lines of that split, in order.

**What fails MC:**
- a no-op (MC2, MC3);
- a deletion without replacement (MC4);
- rewritten values on kept rows (MC3);
- rewritten C-shared columns or `label` on added rows (MC4);
- row order (MC4).

**Limit.** MC does not check two things:
- *which* replacements are drawn;
- the N-only columns of added rows other than `label` (`obs_date`,
  `coord_uncertainty_m`).

R4's full-row replay checks both, in the same run.

**PA-0021(a) runs.** The reviewers built wrong and correct trees; their
results under the current MC are in `mc_wrongtrees.txt`:
- **Reviewer B:**
  - "every US county" → FAIL;
  - undissolved → FAIL;
  - weights ×2 → FAIL;
  - added rows relabelled → FAIL;
  - reordered → FAIL;
  - correct → PASS;
  - wrong replacements → PASS, the stated limit.
- **Reviewer A:**
  - faithful regeneration → PASS;
  - one retained weight changed → FAIL.

`mc_selftest.txt` is the author's no-op check.

**Pre-registration validity.** Two properties of `preregister.py`:
- **Independent of the implementation.** It uses its own transformer, its
  own county read and `shapely` union, and no `generate_negatives` or
  `regions` geometry helper.
- **Wide numerical margin.** The smallest `|edge_m − BUFFER_M|` over every
  row of C and N is 1.802 m, and D has 0 interior rings. Reviewer B
  measured it three ways, one for each path to D (pipeline, replay,
  pre-registration). The pairwise maximum |Δ`edge_m`| is 0.0 m.

**Support after the change (PA-0020(ii)).** The change removes negatives
from the edge band but not positives. Positives within `BUFFER_M` of the
domain edge:
- train: 10 of 4,986;
- val: 0 of 1,246.

Within 1 km, the counts are 27 train and 4 val (author's check, same
method as `preregister.py`). Tolerance: the band holds at most 0.5 % of
the positives in each split. By design it holds no negatives after the
change. The author judges, without measuring it, that a difference this
small cannot be a usable label cue. It is recorded, not gated.

### 4. Retrain decision: no retrain under this CR
**Decision:**
- `grouse_cr0009.pth` is **not** retrained for this CR.
- This CR's live regeneration (deliverable 6) runs only **after CR-0009
  closes**.
- The next model retrain, under whichever CR next requires one, trains on
  the post-CR-0017 negatives. It gets them automatically, because
  `standing_checks` binds every `build_datasets` call to the new record.
- The CR-0009 model's provenance is recorded in `CHANGELOG.md`. The follow-up is tracked
  (deliverable 8).

**Rationale:**
1. **Scale.** The affected rows are the 23 in § Why now. None is known to
   be mislabelled; that is unknowable without out-of-domain data.
2. **The val effect is bounded.** Hold the CR-0009 model fixed and
   replace 5 of the 1,246 val negatives. The val AUC then moves by at most
   5 / 1,246 = 0.0040, because at most that share of positive–negative
   pairs changes.
3. **The train effect is not measurable here.** Measuring it would take
   a retrain, and a single retrain cannot separate this effect from
   seed variance (BUG-0039 is open on exactly that).
4. **Coherence.** CR-0009's remaining deliverables (9–12: maps, symptom
   acceptance, bookkeeping) are evidence about the model it
   trained and the record it trained against:
   - Regenerating the negatives mid-way would change the val set under
     them.
   - It would also invalidate the acceptance record that CR-0009's
     evidence cites.
5. **Cost.** A retrain restarts CR-0009's evaluation chain for a change
   that is unmeasured and bounded.

## Impact
- **Data (deliverable 6):**
  - `candidate_pool.csv` and every `negatives_R`, `train_negatives_R` and
    `val_negatives_R` file are rewritten.
  - The manifest's `negatives` section is rewritten, with new step-6..11
    counts and output digests.
  - `acceptance_record.json` is rewritten.
  - P, B and S are unchanged (MC1).
  - The pre-CR files are backed up first.
- **Acceptance:** `acceptance_split.py`, its config and its tests change
  (§3). The config sha256 changes, so `standing_checks` refuses training
  until the new full run writes a record.
  - **Refusal window.** Deliverables 2–4 are committed on an unmerged
    CR-0017 branch. They merge into the working branch only in
    deliverable 6, immediately before the live run. So the refusal lasts
    only from that merge to the new record, which is minutes.
  - Until then, `train.py` and `calibrate.py` on the working branch are
    unaffected. The OBS
  references are recalibrated, because R4's null draws come from the new
  pool.
- **Models:** see §4. Every model trained before deliverable 6 used
  negatives not checked within 300 m of the domain edge.
- **CR texts:** a pointer line is added to CR-0012 §2 step 6 and to
  CR-0013's E-table and § Attacks ("amended by CR-0017"). No other text
  changes.
- **Not affected:** positives, block assignments, rasters,
  `train.py`/`dataset.py`/`models.py`, `predict.py`, the CR-0015 sampler
  and the `analyze_grouse.py` KDE (BUG-0051, out of scope).

## One change per CR (CR-0011 A5)
The deliverables span generator code, acceptance design, data
regeneration and bookkeeping. They cannot land separately:
- The generator change without the replay change fails R3. Then no
  record is written, and `standing_checks` refuses all training.
- The replay change without the generator change fails E13, R3 and R4 on
  today's files (deliverable 2 shows it).
- The regeneration is how the two changes land together.
- Bookkeeping closes the BUGs they fix.

## Risk: LOW
| risk | mitigation |
|---|---|
| The pipeline and the replay disagree at the 300 m threshold | Margin and paths to D: § Pre-registration validity. A disagreement fails R3 loudly; nothing is accepted silently. |
| Wrong domain (every US county, or undissolved per-state polygons) | Attack rows (§3); MC2 and MC3 pin the exact removal set |
| Habitat pool undersupplied after the drop (`RuntimeError`) | The pool loses 88 rows in all. The smallest habitat surplus after the drop is 116 (VT val: 304 candidates for a target of 188). The NonVeg cap binds in every cell, and the smallest NonVeg surplus is 554, so `n_nv` cannot change. |
| Regeneration while CR-0009 is open, or before CR-0015's B1 | Deliverable 5's preconditions, checked and recorded before anything under `data/` is written |
| A live run that fails part-way | Deliverable 6's order and restore rule |
| Seaward over-exclusion (the complement of D includes sea) | 0 today. The 39 "CA/sea" rows in `preregister.txt` are BUG-0050's 39, and their nearest boundary points all lie on the Canadian land border (`canada_buffer.txt`). The other 49 are nearest NY or MA. Accepted: this error can only remove candidates. |
| The replay author reuses pipeline code | CR-0013 design rule 4: a separate fresh agent writes §3; reviewers check the transcript ids |

## Test plan
**Validatable here:**
- **`tests/test_cr0017.py`** (synthetic, with no county file; the domain
  is injected through `domain=`):
  - `edge_m` is correct for a point inside, outside and on the boundary;
  - a point at exactly `BUFFER_M` is dropped, and one at `BUFFER_M + 1e-6`
    is kept;
  - the line between two dissolved "states" is not an edge;
  - step-6 drops = (a) ∪ (b).
- **Acceptance tests (deliverable 2):**
  - the unit tests for E13 and the new rule in R3;
  - the five attack rows;
  - the config pin;
  - the existing suite still passes.
- **Today's real files, read-only (deliverable 2):**
  - E13 FAILs with C 88 and N 23;
  - R3 FAILs;
  - R4 FAILs, because the replay's draw replaces exactly the 23
    pre-registered negatives; the draw counts are equal;
  - every other gate passes.
- **Scratch-tree real-data run (deliverable 4):**
  - the tree holds copied CSVs, and its rasters and county zip are
    symlinked;
  - first check that no output path is a symlink;
  - run `generate_negatives.py`, then `acceptance_split.py`: 19/19 GATEs;
  - MC PASS with `--old` = the live tree and `--new` = the scratch tree;
  - a second run is byte-identical.
- **PA-0021(a):** MC, done in round 1 (§3, `mc_wrongtrees.txt`). For E13 and
  the attack rows, the round-2 reviewer of deliverable 2's code re-runs
  the attack suite and checks that each required fixture row exists.

**Not validatable here:**
- Whether any removed candidate truly had a grouse within 300 m (no data
  outside D was acquired).
- The model-quality effect (no retrain, §4).
- Seaward over-exclusion on future inputs (not gated; §Risk).
- Records located in D but acquired under another label (for example a
  VT-located record filed as New York). None could enter S, because the
  query selects by label, and whether they exist is unknowable from the
  acquired data.

## Deliverables (in execution order)
- [x] 1. Pre-approval (CR-0011 A3), reviewed in rounds 1–2 (MC at v3):
      - `docs/quality/evidence/CR-0017/preregister.py`,
        `preregister.txt` and `preregister_keys.csv`;
      - `check_must_change.py`, `mc_selftest.txt`, `mc_wrongtrees.txt`
        and the reviewer tree builders.
- [ ] 2. Acceptance changes (§3), on the unmerged CR-0017 branch (§ Impact),
      by a fresh agent that does not also write deliverable 3 (CR-0013
      rule 4):
      - `acceptance_split.py`, the config and the tests;
      - the tests pass;
      - a read-only run on today's files gives the expected FAILs
        (§ Test plan);
      - evidence: `docs/quality/evidence/CR-0017/acceptance_prefix.txt`.
- [ ] 3. Pipeline changes (§2) and `tests/test_cr0017.py`, on the same
      unmerged branch, on top of the merged CR-0015.
      `tests/test_cr0012.py`, `tests/test_shared_constants.py` and
      `tests/test_nodata_zero_lint.py` still pass.
- [ ] 4. Scratch-tree real-data run (§ Test plan). Evidence goes to
      `docs/quality/evidence/CR-0017/scratch/`.
- [ ] 5. Preconditions, recorded in the evidence before any write under
      `data/`:
      - CR-0009 is CLOSED;
      - CR-0015 B1 has passed;
      - the live artifacts equal the CR-0012 d6 record (MC0).

      Then back up all 20 digested artifacts (P, N, B, C), the manifest,
      the record and the OBS file to `/home/ec2-user/grouse_backup/CR-0017/`,
      mirroring the `data/...` layout, sha256 verified. MC0 must pass with
      `--old` = the backup.
- [ ] 6. Live run, in this order:
      1. Merge the CR-0017 branch.
      2. Run `generate_negatives.py`.
      3. Run MC with old = the backup and new = live. It must PASS.
      4. Run `acceptance_split.py`: 19/19 GATEs, and the record is
         written.
      5. Run `--calibrate`.

      **On any FAIL in steps 2–5:**
      - restore every backed-up file from the backup, sha256 verified;
      - record the failure in the evidence;
      - commit no data evidence;
      - revert the merge;
      - stop.

      On success, commit the evidence, the record copy and the OBS file.
- [ ] 7. Pointer lines in CR-0012 §2 step 6 and in CR-0013 (§ Impact).
      `CHANGELOG.md` entry covering:
      - the negatives change;
      - the fact that `grouse_cr0009.pth` and every earlier model were
        trained on pre-CR-0017 negatives (23 rows within 300 m of the
        domain edge).
- [ ] 8. Bookkeeping:
      - **BUG-0050:** corrective action "CR-0017"; status FIXED;
        `BUG_LOG.md` row updated.
      - **BUG-0064** (placeholder; id allocated by the lead): the buffer is blind at the NY and MA
        state lines (C 49, N 11). It carries the full §2 sections and a
        recurrence review against BUG-0050 and PA-0023, with a
        prior-preventive-action failure analysis. BUG-0050's evidence
        took the national border as the data border, contrary to
        PA-0020(v). The preventive-action decision is recorded there;
        the proposal is in the review log. Add a `BUG_LOG.md` row.
      - **PA-0023 Swept? cell:** BUG-0050 FIXED by CR-0017, and the new
        BUG. Sweep by mechanism for every neighbourhood computation whose
        source ends at a state line with no data beyond it. Known:
        BUG-0051's KDE, which also has the NY and MA edges; record it
        against BUG-0051.
      - **Tracker:**
        - BUG-0051 re-owned to its own CR;
        - the retrain follow-up (§4);
        - MEDIUM and LOW review items.
- [ ] 9. Close-out: every item above is ticked; status IMPLEMENTED.

## Out of scope
- **BUG-0051**, the `analyze_grouse.py` KDE. It is a different
  computation, and it changes S (`spatial_density`, `spatial_zone`),
  which re-runs CR-0012 and CR-0013 from the positives. It has no
  model-input effect. It needs its own CR (CR-0011 A5). The tracker owner
  changes from "same CR as BUG-0050" to "its own CR".
- **Acquiring sightings outside D** (Canada, NY, MA) as a buffer-only
  source (BUG-0050 option (a)). That would mean new acquisition paths
  and a PA-0020 support comparison. Dropping is exact and needs no new
  data.
- **Restricting the complement of D to land.** That is the CR-0014-style
  evt land test. It adds a raster dependency and changes nothing today
  (§Risk).
- **Retraining** (§4).
- **Buffering assumed-negative background points** (CR-0015 § Out of
  scope).
- The analysis-CRS constant (CR-0007 item (d)).
