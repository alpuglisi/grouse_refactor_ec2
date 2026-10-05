# CR-0036 v2 — Reviewer A, round 2 (bounded re-review, CR-0011 A2)

Reviewed 2026-10-05 at HEAD `bd40218`. No repository file was edited.

Scope:
- (a) the status of A36-1..19 against `CR-0036-review-log.md`;
- (b) the whole of v2, plus `check_lidar_structure.py` and `tests/test_cr0036.py`, which are new A3 acceptance code;
- (c) BLOCKING findings outside the changed text only. There are none.

**VERDICT: APPROVE WITH FOLLOW-UPS.**
- All three round-1 BLOCKING concerns are resolved in the operative text.
- There are no new BLOCKING concerns.
- Each of the new MAJORs below must be dispositioned before approval. A tracked follow-up is acceptable.
- I ask that A36-2-1 (the withheld bit) and A36-2-2 (the C6 control) be fixed in the CR text before deliverable 2, not merely tracked. Both are one-line specification errors, and either would otherwise produce a wrong filter or a gate that cannot pass.

## 0. What I ran and checked

| Item | Result |
|---|---|
| `python3 check_lidar_structure.py --self-test` | PASS, exit 0. Every control is REJECTED. C2's control peaks at (−1, −1), C3's ratio becomes 3.281, and C4's contrast becomes 0.0. |
| `python3 -m pytest -q tests/test_cr0036.py` | 9 passed and 12 skipped. The skipped tests are the generator tests and the lint, which wait for deliverable 2. |
| Skip guard | `skipUnless(_HAVE_GEN or GENERATOR_REQUIRED)`. Once the flag is set to True, a missing module fails rather than skips. This is correct. |
| `WESM.csv` sha256 | It matches `WESM.csv.sha256.txt` (`eb1a447a…`). |
| `NH_Coastal_1_2019` in WESM | QL1, `horiz_crs` 6525 (NAD83(2011) NH ftUS), `vert_crs` 6360 (NAVD88 ftUS), collected 2019-11-23 to 2020-04-23. |
| `NY_NHGaps_1/2_D24` in WESM | 6347 (UTM 18N) and 6348 (UTM 19N). |
| `NH_CT_River*_2015` in WESM | 6348, collection starting 2015-10-24. |
| EPT GpsTime encoding | The `NH_Coastal_2019` source header has `global_encoding` = 17, meaning adjusted standard GPS time. |
| PDAL flag layout | `ClassFlags` is "deprecated in favor of Synthetic/KeyPoint/Withheld/Overlap" (pdal.io/dimensions). These are bits 0, 1, 2 and 3 as in the LAS 1.4 R15 spec, so Withheld is bit 2 (0x04) and Overlap is bit 3 (0x08). |
| Binning on exact edges, `~T·(x, y)` | No misbins at a realistic origin over 20 000 edges. `(1000, 1700)` gives v = 10.000000000000007, so it falls outside as the test expects. The oracle uses the CR's formula exactly. |
| tsd decode and rounding | `rint(decode(encode(y))) == y` for 0..30, as in round 1. Mask A's rounding test (±4e-4) matches this. |

## 1. Status of round-1 concerns

| id | r1 sev | status in v2 | note |
|---|---|---|---|
| A36-1 | BLOCKING | **Resolved in text** | §Sources, §1.4 and the per-work-unit C3 address it. The test evidence the disposition cites is weak; see A36-2-4 and A36-2-9. |
| A36-2 | BLOCKING | **Resolved** | §1.1 assigns per cell and §1.6 bins only into a cell assigned to the point's work unit. The footprint-only assignment creates a new gate risk; see A36-2-3. |
| A36-3 | BLOCKING | **Resolved** | Mask A uses `tsd_M` with M = max(Y, A) and the window [min, max]. I re-derived this: the latest D ≤ M is ≥ min(Y, A) exactly when some disturbance falls in that window. Tests cover Y < A, Y = A and Y > A. |
| A36-4 | MAJOR | **Resolved** | Rounding, inclusive bounds, tsd nodata, and A from the per-cell median `GpsTime`. A LOW remains: A36-2-11. |
| A36-5 | MAJOR | **Resolved** | Mask B plus the CR-0037 obligation to report within \|Y−A\| ≤ 2. A MEDIUM remains: A36-2-7. |
| A36-6 | MAJOR | **Not resolved** | "bit 3 of `ClassFlags`" is the Overlap bit. Classes 19–22 are now kept. See A36-2-1. |
| A36-7 | MAJOR | **Resolved** | Encoders raise, HAG outside [−2, 80] is dropped, and the test pins height to [0, 800] dm. |
| A36-8 | MAJOR | **Mostly resolved** | Denominators, ddof, the percentile method and the minimum counts are stated. Residual: A36-2-8. |
| A36-9 | MAJOR | **Resolved in design** | IDW with k = 6 within 30 m ≤ 60 m pad makes the seam exact by construction. `test_seam_exact` can fail (a no-pad implementation changes HAG near the edges) and runs without PDAL. The C6 control is wrong; see A36-2-2. |
| A36-10 | MAJOR | **Resolved** | 64-cell blocks are 3.69 km², about 81 M points at 22 pts/m². |
| A36-11 | MAJOR | **Resolved** | The key covers the grid, the table sha, the recipe and the work units. A LOW remains: A36-2-13. |
| A36-12 | MAJOR | **Partly resolved** | Controls now exist and C2 reads the pilot. Residuals: A36-2-2, -3, -5, -6 and -12. |
| A36-13 | MAJOR | **Resolved** | Both files are committed and the script owns the constants. A LOW remains: the prose restates the numbers (A36-2-12). |
| A36-14 | MEDIUM | **Resolved in text** | `from_pipeline`; the lint forbids `Transformer.from_crs`. |
| A36-15 | MEDIUM | **Resolved** | Registries moved to CR-0037. |
| A36-16 | MEDIUM | **Resolved in text** | A WESM snapshot and sha are pinned. The table itself is not reviewable before approval; see A36-2-10. |
| A36-17 | MEDIUM | **Resolved (justified)** | The reason for keeping the rockyweb reader, that the BLOCKING CRS concern needs a pilot that exercises it, is acceptable. |
| A36-18 | LOW | **Resolved** | |
| A36-19 | LOW | **Resolved** | |

## 2. New concerns (v2 text and the A3 code)

### A36-2-1 — MAJOR — The withheld-flag rule names the Overlap bit; classes 19–22 are silently kept
**Evidence.**
- CR §1.3 keeps points with "`Withheld` == 0 where that dimension exists, else bit 3 of `ClassFlags` clear". In the LAS 1.4 numbering that PDAL follows (Synthetic, KeyPoint, Withheld, Overlap = bits 0–3), bit 3 is **Overlap**. Withheld is bit 2 (`ClassFlags & 4`).
- EPT stores `ClassFlags` and has no `Withheld` dimension, which I verified in `NH_Coastal_1_2019/ept.json` in round 1. For EPT the fallback therefore applies: as written, overlap points are dropped and withheld points are kept.
- The new drop list {6, 7, 13–18} also stops dropping the classes v1 dropped:
  - 19, overhead structure;
  - 20, ignored ground;
  - 21, snow;
  - 22, temporal exclusion: USGS uses it for points from overlapping swaths flown at a different time, so it can carry pre- or post-harvest structure;
  - ≥ 23, user-defined.
- No test exercises the point filter at all. The API list in `tests/test_cr0036.py:13-23` has no keep/drop function.

**Fix.**
- Write `(ClassFlags & 0x04) == 0`.
- Drop class 22 and classes ≥ 19 except where a class is justified. Snow (21) is tracked to CR-0037 by B36-18; dropping it now is the safe choice.
- Add a `keep_points(...)` function to the pinned API, with a test over every class value 0–255 crossed with each flag bit.

### A36-2-2 — MAJOR — The C6 control in the CR and in the script differ; neither works as a PA-0021(a) control
**Evidence.**
- CR §5 C6 specifies the control as "`LIDAR_HAG_MAXDIST_M` set above `LIDAR_PAD_M`". On QL1 data the 6 nearest ground points lie within a few metres. Raising `max_distance` from 30 m to anything above 60 m changes an in-block point's neighbour set only where fewer than 6 ground points lie within 60 m **and** that point is within 60–90 m of one of W2's two internal seams, for example a pond on a seam. Usually no such point exists.
- So the specified control would usually be **ACCEPTED**, and C6 would FAIL for the wrong reason. As written, deliverable 3 ("every control passes as specified") is then unachievable.
- The script instead uses `perturb_one` (`check_lidar_structure.py:211-214, 389`). `array_equal` rejects it on any input, so it shows only that `check_seam` is not constant-true. It does not show that the pipeline can produce a seam defect.
- The pilot layout has no file for the CR's control. C6 also compares only `lid_p95` (`W2seam_lid_p95.tif`), not all seven features or the metadata counts.

**Fix.**
- Make the control a run of the 64-block assembly with **pad = 0** (`W2seam_nopad_*`). That reliably changes HAG near the seams.
- Require C6 real equality on all seven features and on meta bands 3–5.
- Update CR §5 and the script so they state the same control.

### A36-2-3 — MAJOR — C3 and C5 per work unit will predictably fail on slivers and footprint edges (fail-closed, but it forces post-hoc gate edits)
**Evidence.**
- C3 runs for every work unit in a window and FAILs below `MIN_CELLS` = 200 forest cells (`:119-120`, `:274-279`, `:379-384`).
- Assignment uses the WESM footprint alone (§1.1). WESM polygons are generalised, so cells whose centre is inside the newest work unit's polygon but which lie outside its actual point extent get fewer than 50 returns. Those cells are NODATA, even when an older work unit has full data there.
- C5 requires ≥ 0.99 valid per work unit. W2 is *deliberately* chosen at a boundary between work units (§6). With 128 cells along the boundary out of roughly 8 000 per work unit, a one-cell over-reach of the footprint is about 1.6% of cells. C5 then fails, and so does C3 for any small work-unit sliver in W1 (20 km) or W2.
- The gate fails closed, so no wrong data lands. But this predictably blocks deliverable 3 and pressures a threshold edit after the data is seen.

**Fix.** Pre-register both rules now.
- **Assignment fallback.** A cell takes the newest covering work unit that has ≥ `LIDAR_MIN_RETURNS` returns in the cell, else the next newest. This is better data in any case.
- **Sliver rule.** Work units with fewer than `MIN_CELLS` assigned forest cells in a window are reported as OBS, and the gate requires their combined share to be ≤ a stated constant.

### A36-2-4 — MAJOR — The unit/CRS test that the A36-1 resolution cites is vacuous and trivial
**Evidence.** `test_units_and_crs` (`tests/test_cr0036.py:319-325`) does this:
- It selects table rows with a feet Z factor, then loops `for r in feet[:1]`. With no feet row it runs zero assertions and **passes**.
- It checks only that `z * 1200/3937` is correct.
- It contains no XY or pipeline test, no UTM case and no header-mismatch refusal.

CR §5 claims "CRS and units, with a feet source and a UTM source".

**Fix.**
- Use synthetic rows rather than table rows.
- For the XY path, transform one known point (for example from EPSG:6525 ftUS and from EPSG:6348) through the row's pinned pipeline. Assert it against an independent computation to within 1 mm.
- Assert that the generator refuses a header whose CRS or units differ from its row.
- Assert `len(feet) ≥ 1` for the real table once it exists, since NH_Coastal is ftUS.

### A36-2-5 — MEDIUM — NODATA values leak into C2 and C4 as data
**Evidence.**
- In pilot mode, `valid = lay["lid_p95"] != NODATA` (`:356`) is used for every layer.
- `lid_wcov5` and `lid_u1_3` have their own NODATA (denominator < 20, §1.7), so −9999 values can enter the C2 means and SDs and the C4 medians.
- In C4, a −9999 in the *mature* group lowers its median, which inflates the contrast: the bias runs toward PASS.

**Fix.** Use per-feature validity, `layer != NODATA`, for each check.

### A36-2-6 — MAJOR (tracked follow-up acceptable) — Distributional gates are uncalibrated under PA-0021(c)
**Evidence.**
- The C3 band [0.5, 2.0], the C4 threshold of 50 per mille and the C5 threshold of 0.99 have no fair-side distribution behind them.
- The controls are single draws: one seed for the permutation and one fixed factor. PA-0021(c) requires ≥ 50 draws on both sides, and they must separate.
- Round-1 A36-12 asked to "calibrate or demote" these gates; v2 does neither.

**Fix.**
- For C4: run a permutation null of ≥ 100 draws, and require real > the null's p99 as well as the threshold.
- For C3: record the per-sub-window distribution of the ratio across W1 to W3, and state where its band comes from.
- Otherwise, demote the rows to OBS.

### A36-2-7 — MEDIUM — Mask B: `tsd_A` does not exist for A = 2015, and the boundary and record start are unstated
**Evidence.**
- `NH_CT_River*_2015` starts 2015-10-24 (WESM) and covers 54% of NH (`ROUTE.md` §4). The per-cell median `GpsTime` therefore gives A = 2015 for its fall flights.
- tsd exists only for 2016–2025 (CR-0035 inventory). Mask B's `tsd_A` is then undefined. Mask A is fine, because M ≥ Y ≥ 2016.
- The Mask B nodata case is unspecified.
- Whether "within 20 years" includes 20 exactly is unstated, and the test has no boundary case.
- The disturbance record starts in 1999, so for A < 2019 the 20-year look-back reaches before the record and 1995–98 disturbances read as "old". This is not stated.

**Fix.**
- Define `tsd_A` for A < 2016: compute it from the disturbance stack directly, or use tsd_2016, which is conservative.
- Make tsd nodata in Mask B mask the cell.
- Pin `≤ 20` and add the boundary test.
- State the 1999 truncation.

### A36-2-8 — MEDIUM — The oracles and the CR definitions differ in places
**Evidence.**
- **Noise drop.** §1.5 drops HAG < −2 and > 80 m and counts them. `oracle_metrics` does not drop them: they enter `min_returns`, `tall` and the `nf` denominator. The test draws HAG from [−1, 30], so the drop is never exercised and it is unpinned whether `cell_metrics` or its caller performs it.
- **Ground HAG and zero distance.** Ground HAG = 0 and the d = 0 rule (mean Z of the coincident ground points) exist only in `oracle_hag` (`:136-147`), not in §1.5.
- **Water case.** The "water case" listed in §5's test list does not exist in the tests.
- **First returns.** "First return" (`ReturnNumber == 1`) and the handling of `ReturnNumber` = 0 are not stated.

**Fix.**
- Put these rules in §1.5 and §1.7.
- Test HAG values −5 and 100, and pin which function drops them.
- Add the water test (water points over a pond more than 30 m from ground get NaN HAG), or remove the claim.

### A36-2-9 — MEDIUM — EPT rows: building the table from WESM CRS fields would apply the feet factor twice
**Evidence.**
- §Sources says the table is built "from WESM `horiz_crs`/`vert_crs` and source headers". For `NH_Coastal_1_2019`, WESM gives 6525 and 6360, both ftUS. The EPT copy, however, is already in 3857 with Z converted to metres: I verified in round 1 that 244.85 ft × 0.3048006 = 74.63, the value in the EPT bounds.
- An EPT row built from the WESM fields would therefore get `z_to_m` = 0.3048, applied to metres.
- `ept.json` declares no vertical SRS, so the header check cannot catch this.
- C3 would catch it at runtime (ratio about 0.3), so this fails closed.

**Fix.** State the rule per reader: EPT rows use CRS 3857 and `z_to_m` = 1.0, verified per row from the `ept-sources` metadata. LAS rows use the header, cross-checked against WESM.

### A36-2-10 — MEDIUM — The pinned source table is never reviewed under this CR
**Evidence.**
- `lidar_sources.csv` and `build_lidar_sources.py` hold the pinned PROJ pipelines and unit factors. These carry the resolution of BLOCKING A36-1 and of A36-14.
- Both are deliverable 2, after approval, and the CR names no review step for them.

**Fix.** Either commit both before approval under A3, or record in the review log that both reviewers must check the table, including each row's pipeline string and its unit factors against the headers, before deliverable 2 is checked off.

### A36-2-11 — LOW — The per-cell A depends on the GPS time encoding
**Evidence.** The median `GpsTime` gives a date only under adjusted standard GPS time (`global_encoding` bit 0). That holds for the sampled NH_Coastal source (17), but no rule requires it.

**Fix.** Refuse a source without bit 0. Cross-check that each cell's A falls within the row's collection window.

### A36-2-12 — LOW — Residual acceptance hygiene
- The §5 table restates the script's numbers (0.5, 2.0, 8, 50, 0.99, 128), which A3 and A4 ask the CR not to do. Name the constants only.
- C1 is still true by construction. Its half-cell control is rejected on every input, so under PA-0021(e) it is not a gate. Label it OBS, or add the independent sample recompute I proposed in round 1.
- No ½-cell registration error is demonstrated against C2. Record the ½-cell shift result as OBS.

### A36-2-13 — LOW — Where the masks are applied is unstated
**Evidence.** The cache key holds no tsd digest.

**Fix.** State that Masks A and B are applied at assembly and are never cached, or add the tsd digests to the key.

## 3. Summary

| id | sev | summary |
|---|---|---|
| A36-2-1 | MAJOR | "bit 3 of ClassFlags" is Overlap, not Withheld (0x04); classes 19–22 now kept; no filter test |
| A36-2-2 | MAJOR | C6 control: the CR's (MAXDIST > PAD) is usually accepted on dense data; the script's (`perturb_one`) is trivially rejected; use pad = 0 and compare all features |
| A36-2-3 | MAJOR | C3 `MIN_CELLS` and C5 0.99 per work unit will fail on slivers and footprint over-reach at W2's boundary; pre-register the fallback and sliver rules |
| A36-2-4 | MAJOR | `test_units_and_crs` passes with zero assertions and never tests XY, UTM or a header mismatch |
| A36-2-5 | MEDIUM | p95 validity is reused for wcov5 and u13, so −9999 enters C2 and C4 (C4 biased toward PASS) |
| A36-2-6 | MAJOR (follow-up) | C3, C4 and C5 thresholds uncalibrated and controls single-draw (PA-0021(c)) |
| A36-2-7 | MEDIUM | Mask B: `tsd_2015` does not exist; nodata, boundary and 1999 record start unstated |
| A36-2-8 | MEDIUM | Oracle and CR differ on noise drop, ground HAG, d = 0, the water case and first returns |
| A36-2-9 | MEDIUM | EPT Z is already metres; WESM `vert_crs` would double-apply ftUS; the header check cannot see it |
| A36-2-10 | MEDIUM | `lidar_sources.csv` and its build script are unreviewed post-approval deliverables |
| A36-2-11 | LOW | GpsTime encoding and the A-within-collection-window check |
| A36-2-12 | LOW | Prose restates thresholds; C1 by construction; ½-cell C2 result not recorded |
| A36-2-13 | LOW | Where the masks are applied versus the cache key |
