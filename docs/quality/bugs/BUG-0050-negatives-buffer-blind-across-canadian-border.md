# BUG-0050: The negatives' 300 m exclusion buffer has no sightings across the Canadian border (PA-0023 instance)

## 1. Description
`generate_negatives.py` pool step 6 drops every candidate within
`BUFFER_M` (300 m) of a ruffed grouse sighting. The sightings it tests
against are the rows of every region's `evaluated_sightings_R`. Those
come from US-only acquisitions: the GBIF `stateProvince` predicate and
eBird US state codes.

So the buffer's source data stops at the international border. A
candidate less than 300 m from Canadian land is tested only against the
US side of its neighbourhood. A grouse sighting just across the border
cannot exclude it, because no Canadian sighting was ever acquired.

## 2. Where encountered
CR-0012 deliverable 8, 2026-09-30. PA-0023's Swept? cell handed this
question to CR-0012, citing E7 (under PA-0022). Before closing that cell
the code was checked, as PA-0024(a) requires.
- The buffer source is `generate_negatives.py:392-400`: every row of
  every region's `evaluated_sightings_R`.
- The raw sightings are 43,024 rows. All of them have `countryCode` US,
  with `stateProvince` Maine 18,896, Vermont 15,512 and New Hampshire
  8,616. Evidence: `docs/quality/evidence/CR-0012-d8/canada_buffer.txt`,
  produced by `canada_buffer.py` in the same directory.

## 3. What it caused to fail
The records are on today's accepted CR-0012 files; the evidence file
lists each one with the nearest border point:
- **Pool candidates:** 39 of 22,187 lie within 300 m of the outer US
  boundary (102 within 1 km). For every one of them, the nearest boundary
  point is on the Canadian border:
  - ME: the Saint John River at about 47.2–47.45° N, and the New
    Brunswick line;
  - NH and VT: the 45.0° N line.
- **Selected negatives:** 12 of 6,232, which is 0.19 %:
  - ME: 9 (7 train, 2 val);
  - NH: 0;
  - VT: 3 (all train).

For these records, the rule "no negative within 300 m of a known grouse"
(CR-0013 E7) was only checked against part of the neighbourhood. Whether
any of them actually has a sighting across the border is **unknown**: the
data was not acquired (PA-0016: no cause or harm is claimed beyond this).
E7 passes because its reference set, S, has the same border (§5).

## 4. What the defect was
`generate_negatives.py:392-400` (CR-0012 code, `20a52c1`):
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
`evaluated_sightings_R` holds only state-R records (CR-0007), and those
were acquired by US `stateProvince`. The neighbourhood (300 m) crosses the
border; the source does not.

## 5. Root cause analysis (differential analysis, then Five Whys)
**Differential analysis:**
- **Across state lines** the buffer is correct. It pools every region's
  sightings, so an ME candidate 100 m from an NH sighting is dropped.
  This is what CR-0012 fixed, and what PA-0018 asked for.
- **Across the national border** it is not. The difference is the source
  set: sightings exist on both sides of a state line, but on only one
  side of the border.

**Five Whys:**
1. **Why can a candidate near Canada escape the buffer?** No Canadian
   sighting is in the source set.
2. **Why not?** Every acquisition query is keyed to the three US states
   (GBIF `stateProvince`, eBird `US-ME`/`US-NH`/`US-VT`).
3. **Why was that not seen as a PA-0023 violation?** PA-0023's sweep
   (BUG-0037 §8) said "sightings include Canadian records where the
   sources do". It left the question to "CR-0012's buffer gate (E7)".
4. **Why could E7 not answer it?** E7 measures distance to S, the same
   US-only sightings. A gate whose reference set has the same border
   cannot detect the border.
5. **Why did CR-0012 deliverable 8 propose closing it?** The text says
   "against every sighting (pool step 6, all regions)". That describes
   pooling across regions. It was read as covering the border without
   checking what the sightings contain.

**Root cause:** the buffer's source set was chosen by acquisition label
(the three US states). That source ends at a national border inside the
300 m neighbourhood. The check meant to confirm it was then delegated to
a gate that reads the same source.

## 6. Corrective action
**CR-0017** (`docs/quality/change-requests/CR-0017-negatives-buffer-domain-edge.md`;
APPROVED, merged `4080f74`, live run `6342f2a`). Option (b), with the
domain taken from the acquisition query: pool step 6 also drops every
candidate whose EPSG:5070 distance to the boundary of D, the union of the
ME, NH and VT county polygons, is `≤ BUFFER_M`
(`regions.domain_edge_m`, `generate_negatives.domain_edge_drop_mask`).
CR-0013 gained exact gate E13 and rule (b) in R3. The domain is the three
states, not the United States: the text of option (b) below ("land
outside the US counties") would have missed the NY and MA state lines,
filed as **BUG-0064**.

**Verified:** must-change gate PASS against the pre-CR backup: exactly
the pre-registered 88 pool candidates (this bug's 39 plus BUG-0064's 49)
and 23 selected negatives (this bug's 12 plus BUG-0064's 11) removed and
replaced in the same cells, every other row byte-identical; acceptance
19/19 GATEs including E13; final record `9d5ad0a9…`
(`docs/quality/evidence/CR-0017/live/`). The fix removes the rows whose
neighbourhood the source cannot see, which is the root cause, rather than
adding a caveat.

Status: **FIXED** (CR-0017 deliverable 6, `6342f2a`).

*Original text (the options as first written):* Either option changes pipeline behaviour,
CR-0012 §2 pool step 6, and CR-0013's replay (R3) and E7:
- **(a)** Acquire Canadian ruffed grouse sightings within `BUFFER_M` of
  the border (GBIF `countryCode` CA, Québec and New Brunswick) as a
  buffer-only source. They would never be positives, because the
  partition is US states.
- **(b)** Apply PA-0023's nodata option: drop every candidate within
  `BUFFER_M` of land outside the US counties, as CR-0014 does for
  `road_dist`.

Either option changes the selected negatives, so CR-0013's acceptance
must be re-run, and it interacts with the CR-0009 retrain. Owner: a new
CR, not yet written, tracked in `docs/quality/CR-0007-0008-OPEN-ISSUES.md`.
Scale for the risk assessment: 12 selected negatives, 0.19 %.

## 7. Recurrence review
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`, for "Canad",
"border", "buffer" and "neighbourhood".

**Match: BUG-0037 / PA-0023** (`road_dist` over-reads near Canada). It is
the same mechanism: a neighbourhood computation whose source data ends
at the national border. This instance is not new. It is the "negatives'
300 m buffer … not determined" item in PA-0023's own sweep. It was owned
by CR-0012 under PA-0022.

**Related, same parent rule:** BUG-0023, BUG-0026 and BUG-0027 (PA-0018),
where a source was chosen by region label.

**Prior-preventive-action failure analysis:**
- **PA-0023** did not fail as a rule. Its text covers this case exactly.
- What failed was the sweep's **deferral**: it handed the item to E7,
  which reads the same US-only source. That is the wrong layer, a check
  that could not have failed (PA-0021(e): a reference that shares the
  defect).
- **PA-0024(a)** requires a disposition's location to contain the fix. It
  is the rule that caught this, when CR-0012's deliverable-8 closure was
  checked against the code.

## 8. Preventive action
**No new PA.** PA-0023 covers the mechanism. PA-0021(e) and PA-0024(a)
cover the deferral to a gate that could not fail, and PA-0024(a) worked
here. PA-0023's Swept? cell now records this instance, with BUG-0050 as
the owner.

**Later (CR-0017 deliverable 8):** this investigation took the national
border as the data border, contrary to PA-0020(v); the NY and MA state
lines were missed (BUG-0064). That recurrence produced **PA-0032**
(extends PA-0023: derive the domain from the acquisition query's keys).
