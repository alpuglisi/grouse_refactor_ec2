# BUG-0064: The negatives' 300 m exclusion buffer has no sightings across the NY and MA state lines (sibling of BUG-0050; PA-0023 instance)

> Found while scoping CR-0017 (placeholder "BUG-NEW-a", allocated as
> BUG-0064 by the lead; `CR-0017-review-log.md` § Proposed bookkeeping
> rows). Filed by CR-0017 deliverable 8, 2026-09-30.

## 1. Description
`generate_negatives.py` pool step 6 drops every candidate within
`BUFFER_M` (300 m) of a ruffed grouse sighting, testing it against every
row of every region's `evaluated_sightings_R`. Those sightings were
acquired only for Maine, New Hampshire and Vermont. So the buffer's
source ends at the edge of ME ∪ NH ∪ VT, not only at the Canadian border
(BUG-0050) but also at the New York and Massachusetts state lines. A
candidate less than 300 m from NY or MA was tested only against the part
of its neighbourhood inside the three states; a grouse just across the
line could not exclude it, because no NY or MA sighting was ever
acquired.

## 2. Where encountered
- **Pipeline:** `generate_negatives.py:392-400` at `20a52c1` (CR-0012
  code), pool step 6 (quoted in §4).
- **Acquisition queries (the data domain):**
  - GBIF: `sightings.py:56,58`, `{"type": "in", "key": "STATE_PROVINCE",
    "values": STATES}` with `COUNTRY` US;
  - eBird: `ebird.py:18`, `STATES = {r.lower(): f"US-{r}" for r in
    REGIONS}`.
  - Data: 43,024 of 43,024 raw sightings have `stateProvince` ∈ {Maine,
    New Hampshire, Vermont}
    (`docs/quality/evidence/CR-0012-d8/canada_buffer.txt`, line 1).
- **The check that missed it:** BUG-0050's evidence script
  `docs/quality/evidence/CR-0012-d8/canada_buffer.py:29-42` (quoted in
  §4).
- Found by the CR-0017 author while scoping the BUG-0050 fix, 2026-09-30,
  and confirmed independently by CR-0017 reviewer A (its own script; its
  111-key set equals `docs/quality/evidence/CR-0017/preregister_keys.csv`).

## 3. What it caused to fail
Measured on the accepted CR-0012 deliverable 6 files by
`docs/quality/evidence/CR-0017/preregister.py`
(`preregister.txt`; nearest outside territory per row):
- **Pool candidates (C):** 49 of 22,187 within 300 m of the domain edge
  with the nearest outside point in NY (31) or MA (18).
- **Selected negatives (N):** 11 of 6,232:
  - NH: 1 (MA; train);
  - VT: 10 (NY 6: 4 train, 2 val; MA 4: 3 train, 1 val);
  - ME: 0.
  In all, 8 train and 3 val.

For these rows the guarantee "no negative within 300 m of a known grouse"
(CR-0012 §2 step 6; CR-0013 E7) was checked against part of the
neighbourhood only. Whether any of them really had a grouse within
300 m is **unknown**: no data was acquired beyond the line (PA-0016; no
harm is claimed beyond an unverified guarantee). E7 passed, because its
reference set S has the same edge. BUG-0050's fix as first framed
("drop within `BUFFER_M` of land outside the US counties") would have
left all 49 / 11 in place.

Every model trained before CR-0017 deliverable 6, including
`grouse_cr0009.pth`, trained on these negatives (CR-0017 §4; `CHANGELOG.md`).

## 4. What the defect was
The pipeline code, `generate_negatives.py:392-400` at `20a52c1`:
```python
    # 6. buffer against every row of every region's sightings
    evaluated = {r: read_csv(digest(data[r].path("evaluated")))
                 for r in REGIONS}
    sights = pd.concat(list(evaluated.values()), ignore_index=True)
    in_buffer = buffer_drop_mask(
        pool["longitude"].to_numpy(dtype=np.float64),
        pool["latitude"].to_numpy(dtype=np.float64),
        sights["longitude"].to_numpy(dtype=np.float64),
        sights["latitude"].to_numpy(dtype=np.float64))
```
The source (`sights`) covers ME ∪ NH ∪ VT; the 300 m neighbourhood of a
candidate near NY or MA does not stop at the state line.

The check that characterised the defect, BUG-0050's evidence script
`docs/quality/evidence/CR-0012-d8/canada_buffer.py:29-42`:
```python
NEIGHBOUR_FIPS = {"NY": "36", "MA": "25"}   # US land neighbours of ME/NH/VT
...
fips = list(R.STATE_FIPS.values()) + list(NEIGHBOUR_FIPS.values())
...
cty = cty[cty.STATEFP.isin(fips)].to_crs(ANALYSIS_CRS)
bnd = cty.union_all().boundary
```
It drew the boundary around ME, NH, VT **and NY and MA**, so the NY and
MA state lines became interior lines, as if sightings existed beyond
them. Its first output line (`canada_buffer.txt:1`) shows that none do.

## 5. Root cause analysis (differential analysis, then Five Whys)
**Differential analysis** (why BUG-0050 found the Canadian rows but not
these):
- Same code, same sightings, same buffer. The only difference between
  the 39/12 rows BUG-0050 reported and the 49/11 it missed is the
  territory beyond the edge: Canada vs NY/MA.
- BUG-0050's check treated "no data beyond" as a property of the
  national border. NY and MA are in the US, so the script counted them
  as covered, without reading which records the acquisition selects.

**Five Whys:**
1. **Why can a candidate near NY or MA escape the buffer?** No NY or MA
   sighting is in the source set.
2. **Why not?** Both acquisition queries select by US state key
   (`STATE_PROVINCE` ∈ the three states; eBird `US-ME`/`US-NH`/`US-VT`).
3. **Why did BUG-0050's investigation not report these rows?** Its
   evidence script took the national border as the data border and
   added NY and MA counties to the covered area.
4. **Why was the national border assumed?** PA-0023 names "a national or
   other data-domain border" but does not say how the domain is
   determined; the national border was the example in PA-0023's source
   (BUG-0037) and in the prompting sweep cell ("near the Canadian
   border"). PA-0020(v), which requires tracing each input to its
   acquisition query and reading every key, was not applied when the
   boundary was chosen.
5. **Why did no gate catch it?** E7 reads the same sightings (as in
   BUG-0050 §5, step 4).

**Root cause:** the buffer's source ends at the edge of its acquisition
domain (the three states' query keys), and the check of that edge used
an assumed domain (the country) instead of the one the acquisition query
actually selects.

## 6. Corrective action
**CR-0017** (APPROVED; implemented and run live, merge `4080f74`,
evidence `6342f2a`): pool step 6 also drops every candidate whose
EPSG:5070 distance to the boundary of D, the union of the ME, NH and VT
county polygons, is `≤ BUFFER_M` (`regions.domain_edge_m`,
`regions.py:155`; `generate_negatives.domain_edge_drop_mask`,
`generate_negatives.py:205`). D is derived from the acquisition keys
(`STATE_FIPS` of `REGIONS`), so the NY, MA and Canadian edges are all
edges. Acceptance: new exact gate E13 and rule (b) in R3
(`acceptance_split.py:1798`, `:866`), built independently from the county
file.

**Verification that it addresses the root cause, not the symptom:** the
must-change gate removed exactly the 88 pre-registered pool rows (39
Canada + 49 NY/MA) and the 23 pre-registered selected negatives (12 +
11), with every other row byte-identical
(`docs/quality/evidence/CR-0017/live/mc_live.txt`); acceptance 19/19
GATEs including E13 (`live/acceptance.log`; final record `9d5ad0a9…`).
The domain is computed from the acquisition keys, not from the national
border, which is the failed assumption. The check-layer cause is
addressed by PA-0032 (§8).

Status: **FIXED** (CR-0017 deliverable 6, `6342f2a`).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "border",
"buffer", "neighbourhood", "domain", "state line", "acquisition".

**Matches:**
- **BUG-0050 / PA-0023:** same mechanism and same code (the buffer's
  source ends at a data-domain border inside the neighbourhood). This is
  a recurrence: BUG-0050's investigation examined exactly this
  computation and missed these rows.
- **BUG-0037 / PA-0023:** same mechanism for `road_dist`.
- **BUG-0023, BUG-0026, BUG-0029 / PA-0018, PA-0020:** a source chosen by
  region label; PA-0020(v) is the rule about reading the acquisition
  query's keys.

**Prior-preventive-action failure analysis:**
- **PA-0023** (from BUG-0037) — the rule text covers this case ("a
  national or other data-domain border"). It did not fail by being
  wrong; it failed by being **too implicit**: it does not say how the
  data domain is determined, and its example and its sweep were phrased
  around the Canadian border. The sweep for BUG-0050 inherited that
  framing.
- **PA-0020(v)** — requires tracing each input to its acquisition query
  and reading every key. It was **not followed** when BUG-0050's
  boundary was chosen: the query keys (three states) were read for the
  country code (US) but not applied as the domain.
- **Layer:** the check (the evidence script and the investigation), not
  the pipeline. BUG-0050's evidence became the basis of its proposed fix
  (drop near "land outside the US counties"), so the wrong domain would
  have been built into the fix.
- **Category:** not followed (PA-0020(v)) / too implicit (PA-0023), not
  enforceable by the review-only regime without an explicit step.

## 8. Preventive action
**New: PA-0032 (extends PA-0023)**, the rule proposed in
`CR-0017-review-log.md` § Proposed bookkeeping rows: a neighbourhood
computation's data domain is the extent its acquisition query selects
(the union of the query's region keys), not the country or the analysis
box; a PA-0023 check must derive the domain from the query keys and name
the query (file:line); a check or sweep that assumes data beyond that
extent is incomplete. It also carries the sweep-method clause from
BUG-0072 (enumerate by recorded search). It strengthens PA-0023 at the
layer that failed (how the domain is determined) rather than restating
PA-0023 with a new example.

**Enforcement:** review only (no CI; `CLAUDE.md` §3.4). A mechanical
check is not feasible generically: the domain depends on each source's
query.

**Sweep (`CLAUDE.md` §3.5), 2026-09-30, at `6342f2a`:** scoped by the
mechanism: every neighbourhood computation (distance transform, buffer,
nearest-neighbour or radius query, KDE, smoothing) in the git-tracked
`*.py` outside `inv_*`, `res_*`, `docs/`, `legacy/` and `tests/`,
enumerated by a search for `distance_transform`, `cKDTree`/`KDTree`,
`KernelDensity`/`gaussian_kde`, `sjoin_nearest`, `.buffer(`,
`query_ball`, filters and `BUFFER_M`/`MIN_SPACING_M`; for each, the
source's domain was read from its acquisition:
- `generate_negatives.py` pool step 6, and `acceptance_split.py` E7/R3:
  this bug and BUG-0050 — **FIXED** by CR-0017 (E13 added).
- `analyze_grouse.py` KDE (`kde_spatial`/`kde_joint`/`kde_stratified`
  `:560-601`, applied `:816-820`; map surfaces `:698`, `:725`) and
  `check_partition.py` P8 `kde_density` (`:516`, `:575`, which
  reproduces it): the source is the three states' records, so the KDE is
  blind at the Canadian **and** the NY and MA edges — **known, recorded
  against BUG-0051** (owned by its own CR); no new BUG.
- `diagnose_road_bias.py:77-110`: home-state PRISECROADS only, so every
  state line (internal ones too) — **known, BUG-0026** (OPEN).
- `diagnose_water_bias.py:72-82`: NLCD distance to water; the source
  ends at the NLCD coverage edge (Canadian border), not at a state line —
  **new, BUG-0072** (national/coverage-edge instance missed by
  BUG-0037's sweep).
- `generate_road_distance.py`: roads from every US county intersecting
  the padded grid, NODATA outside US counties and by the Canada rule —
  not affected at state lines (CR-0014; BUG-0037 residual open).
  `check_road_dist.py` is its verifier and models the same edges.
- Not the mechanism (neighbourhoods among the dataset's own records, no
  claim about data beyond the domain): thinning
  (`prepare_training_data.thin_by_min_distance`, pool step 5, `clean.py`,
  `acceptance_split.thin_mask`/`close_pairs`), Moran's I and O1 in
  `acceptance_split.py`, block assignment; the CR-0015 assumed-negative
  sampler has no neighbourhood.

Evidence for the BUG-0072 measurement:
`docs/quality/evidence/CR-0017/sweep/water_dist_edge_probe.py` and `.txt`.
