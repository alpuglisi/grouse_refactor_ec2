# CR-0036 v2, Reviewer B, round 2 (bounded re-review, CR-0011 A2)

Date: 2026-10-05. Commit `bd40218`. I edited no repository file.

**What I ran:**
- `python3 check_lidar_structure.py --self-test`: PASS. All 8 gates pass, and every control is rejected.
- `python3 -m pytest -q tests/test_cr0036.py`: 9 passed, 12 skipped. The skipped tests are generator tests, which skip by design until deliverable 2.

**What I checked against data:**
- The committed `WESM.csv` sha256 matches its recorded digest (`eb1a447a…`).
- EPT `GpsTime` was probed per project.

**VERDICT: APPROVE WITH FOLLOW-UPS.**
- No BLOCKING concern remains. Both round-1 BLOCKING items are resolved in the operative text.
- One prior MAJOR (B36-7, steep-terrain HAG) is only partly resolved. I accept it as a tracked follow-up, provided the W3 check in B36-2-1 is added to `check_lidar_structure.py` before deliverable 3 (the pilot).
- The new items are MEDIUM or LOW.

---

## (a) Round-1 concerns

| id | r1 sev | status | where / note |
|---|---|---|---|
| B36-1 | BLOCKING | **Resolved** | §Sources pinned table (CRS, XY/Z factors, pipeline, header refusal); §1.4 `from_pipeline`; C3 and C5 per work unit; W2 spans EPT and rockyweb (NY_NHGaps_1/2 are UTM 6347/6348 in WESM). The unit test for this concern is weak: see B36-2-4. |
| B36-2 | BLOCKING | **Resolved** | §2 Mask A uses `tsd` at max(Y, A) with an inclusive interval; the oracle cases in `test_mask_a_both_directions` are correct. One residual on `tsd` year availability: B36-2-5. |
| B36-3 | MAJOR | **Resolved** | Mask B; CR-0037 is bound to report within \|Y−A\| ≤ 2 (§2 and the deliverable 4 tracker row). |
| B36-4 | MAJOR | **Resolved enough; residual MEDIUM** | Resolved: day-of-year band, per-cell A, C7, and the binding to within-work-unit evaluation. Residual: the leaf-risk flag is recorded but **not used** by the assignment rule (§1.1 is newest `collect_end` only), so CR-0037 cannot prefer a leaf-off unit without reopening the generator. C7 compares the two sides of a boundary, which is confounded with geography, though acceptable as an observation. See B36-2-6. |
| B36-5 | MAJOR | **Resolved** | C3 is an absolute ratio with a feet control; C4 is a falsifiable understory contrast with a permutation control; C5 is per-unit coverage; a gate passes only if its control fails. Thresholds are discussed in §(b). |
| B36-6 | MAJOR | **Resolved** | C2 reads the pilot file directly. W1 (20 km) gives 5 × 5 = 25 candidate windows of 128 cells against `MIN_WINDOWS` = 8. `test_registration_needs_enough_windows` covers the 1-window case. |
| B36-7 | MAJOR | **Partly resolved** | Resolved: HAG is now IDW of the 6 nearest ground points within 30 m (better than nearest-1), and seams are exact. Not resolved: **no gate in W3 is sensitive to HAG error.** In `pilot()` W3 runs only C3 (a median canopy-height ratio, blind to ±2 m errors in understory bins) and C5. C4 does not run in W3, despite CR §6 saying "C3–C5", and it would not reach `MIN_CELLS` in a notch anyway. See B36-2-1. |
| B36-8 | MEDIUM | **Resolved** | Four occlusion-adjusted bins; the n(−2, b) denominator matches Campbell's normalised relative density (NRD) definition. `lid_wcov5` is redefined. |
| B36-9 | MEDIUM | **Resolved, with wording and class-set residual** | §1.3. See B36-2-7. |
| B36-10 | MEDIUM | **Resolved** | The per-cell ground rule is removed (§1.5, §1.7). |
| B36-11 | MEDIUM | **Resolved** | Pinned `lidar_sources.csv`. New issues: collect_end ties (B36-2-2) and unpinned footprints (B36-2-3). |
| B36-12 | MEDIUM | **Resolved** | C8. |
| B36-13 | MEDIUM | **Resolved** | 64-cell blocks: 1.92² km² × 22 pts/m² ≈ 81 M points, ✓. |
| B36-14 | MEDIUM | **Resolved** | Script and tests committed; thresholds held as constants. |
| B36-15 | MEDIUM | **Resolved** | `WESM.csv` committed and its sha256 checked; the remaining evidence is in deliverable 3. |
| B36-16 | MEDIUM | **Resolved** | Registries moved to CR-0037. |
| B36-17 | MEDIUM | **Resolved** | §Impact. |
| B36-18 | LOW | **Resolved (tracked)** | §Risk / Out of scope. |
| B36-19 | LOW | **Resolved** | Pad 60 m ≥ max distance 30 m; `test_seam_exact`. |
| B36-20 | LOW | **Resolved** | §6: 12 G points × 8.24 B ≈ 99 GB × $0.02 ≈ $2 ✓. That cost falls on the bucket owner rather than the reader, which does not matter here. |

---

## (b) Review of the changed text and the new acceptance code

### C3 reference: LANDFIRE `ch`

**The decimetre assumption is correct.** LANDFIRE's product description says: "CH measurement units are meters * 10 and extracted from Existing Vegetation Height (EVH). CH is assigned the midpoint of the EVH forested classes at non-disturbed locations" (https://wifire-data.sdsc.edu/dataset/lf-canopy-height). So `LANDFIRE_CH_PER_M = 10` holds.

**Vintages.** `ch` and `cc` exist only for 2022 and later.
- `pilot()` takes `yr` = the median A of each window and reads references through `rd.raster_path(..., yr)`.
- Its nearest-year fallback (`grouse_data.py:336-356`) resolves `ch` and `cc` to 2022:
  - W1 (A ≈ 2020): a gap of 2 years, silent.
  - W2 and W3 (A = 2015–2018 for the CT River and Umbagog units): a gap of 4–7 years, with a warning, but no crash.
- Over 4–7 years, height growth of a few decimetres a year moves the ratio by under 10%, which is harmless for a band of [0.5, 2.0].
- Harvests between A and 2022 are not masked in C3, but the median is robust to them.
- The fallback should still be stated in the CR (B36-2-8).

**Effective band.** Because the gate also requires the feet control (ratio × 3.2808) to be *rejected*, the real ratio must exceed 2.0 / 3.2808 = **0.61**. The effective band is therefore [0.61, 2.0], not [0.5, 2.0].
- `lid_p95` (all returns ≥ 0.5 m, leaf-off) measured against LANDFIRE's class-midpoint top height should come out at about 0.8–1.1, so a false fail is unlikely.
- The CR should still state the effective band (B36-2-8).

**Ecologically**, the median ratio is a sound scale test. It catches the Z-unit error that mattered in B36-1, and a double conversion (×0.305) as well.

### C4 contrast

The design is sound and can fail:
- regenerating forest (`tsd` 3–15 years at the cell's own A, NLCD forest) against mature forest (undisturbed since 1999 and `cc` ≥ 60);
- the median `lid_u1_3` difference must be at least 50 per mille;
- the permutation control drives the difference to about 0.

Risks:
- **The 3–15-year range dilutes the signal.** Stems are 1–3 m at about years 3–10 in northeastern hardwood regeneration, and at 12–15 years they are 5–8 m, with a thinning 1–3 m layer.
- **Mature stands are not empty below 3 m.** Mature cc ≥ 60 stands in SE NH often carry a hemlock understory or marcescent beech, both dense in leaf-off returns.

An effect of 50 per mille is still plausible, and a false fail would stop the pilot rather than pass a bad layer. That is acceptable. I would narrow the regenerating range to 3–10 years (LOW, B36-2-9).

The gate as coded runs in W1 only. W1 is a single QL1 leaf-off unit, so the understory metric's validity on QL2 or leaf-risk units remains a CR-0037 item. Deliverable 4 binds it there, which is acceptable.

### W2 seam-selection rule

The rule is workable.
- In NH the rockyweb units are NY_NHGaps_1/2_D24 (UTM 18/19, QL2, **leaf-on**, collect_end 2024-06-16). Being newest, they win wherever they cover.
- "Most even EPT/rockyweb split" will therefore pick a NY_NHGaps edge.
- This exercises a native-CRS reader and a leaf-on against leaf-off contrast for C7, which is useful.
- But see B36-2-10: C2 registration never runs on the rockyweb reader.

### W3 candidates

Crawford, Franconia and Pinkham Notch are all inside the bounding boxes of EPT `USGS_LPC_CT_River_Lot6_Winnipesaulee_2015_LAS_2017` and `NH_Umbagog_2016`. Umbagog (collect_end 2018-05-24, leaf-risk) would win wherever its footprint covers.
- So the choice is workable.
- **Two work units in a 128-cell window is likely.** Any unit with fewer than `MIN_CELLS` = 200 forest cells makes C3 return NaN, so the pilot cannot pass (B36-2-11).
- W3 has no HAG-sensitive check (B36-2-1).

### `GpsTime` → A (verified)

I probed EPT nodes and decoded `GpsTime` as adjusted standard time:

| Project | Decoded median date | WESM collection window |
|---|---|---|
| NH_Coastal_1_2019 | 2020-04-23 | Nov 2019 – Apr 2020 |
| CT_River_Lot6_2015 | 2015-11-15 | Oct 2015 – Apr 2016 |
| NH_Umbagog_2016 | 2018-05-11 | Apr 2016 – May 2018 |
| VT_Statewide_1_A23 | 2023-04-29 | Mar – May 2023 |

Every decoded date falls inside its WESM window. However, the LAZ header's global-encoding flag reads **0 (GPS week time)** in all four, so the generator must not decide the time encoding from the header flag (B36-2-12).

---

## New concerns (round 2)

### B36-2-1: MAJOR, follow-up acceptable. W3 cannot detect steep-terrain HAG error

**Evidence.** `check_lidar_structure.py:378-389` runs only C3, C5 and C6 outside W1. CR §6 says W3 provides C3–C5, and the Risk table lists "W3" as the mitigation for steep-terrain HAG.

**Fix.** Add a **leave-one-out ground check**, gated in W3 with a control:
- the generator logs, per slope class, the HAG of a 1% sample of class-2 points computed with that point withheld;
- the gate requires |median| ≤ 0.10 m and p95 |error| ≤ 0.5 m in the ≥ 20° slope class;
- control: nearest-1 HAG, or ground taken as the minimum Z within 30 m, must fail.

This needs no external reference. Also correct the "C3–C5" text in §6.

### B36-2-2: MEDIUM. The "newest `collect_end`" rule has ties inside the newest-wins set

**Evidence.** WESM ties:

| collect_end | Tied work units |
|---|---|
| 2020/04/23 | NH_Coastal_1 (QL1) and NH_Coastal_2 (QL2), inside the W1 area |
| 2023/05/13 | VT_Statewide_2 (EPT) and VT_Statewide_3 (rockyweb) |
| 2016/04/29 | NH_CT P1 and P3 |
| 2017/12/04 | ME_Eastern_B1 and B2 |
| 2022/05/11 | ME_MidCoast_2 and 3 |
| 2024/06/16 | NY_NHGaps_1 and 2 |

Where footprints overlap at edges, the assignment depends on table order.

**Fix.** Pin a tie-break, for example the higher QL, then the later `collect_start`, then the work-unit name. Test it.

### B36-2-3: MEDIUM. Footprints are not pinned

**Evidence.** The committed `WESM.csv` has no geometry. Cell assignment (§1.1) needs the WESM polygons (`WESM.gpkg`, 3.7 GB), which have no recorded digest. That is against the spirit of PA-0048.

**Fix.** Commit the clipped NNE footprint layer, or its sha256, and have `build_lidar_sources.py` record it in the table digest and the cache key.

### B36-2-4: MEDIUM. `test_units_and_crs` can pass vacuously and tests no CRS

**Evidence.** `tests/test_cr0036.py:319-327` loops over `feet[:1]`. If `lidar_sources.csv` has no feet row, the loop does not run. That is likely, because NH_Coastal is read from EPT in metres. The test also has no UTM or XY check, although CR §5 says it covers "a feet source and a UTM source". This is the test for the round-1 BLOCKING concern B36-1.

**Fix.**
- Use synthetic rows: one feet row and one EPSG:6348 row. Put the same ground-truth points through `to_metres_z` and the pinned pipeline, and assert that the cells match the EPSG:3857 path.
- Assert the header-refusal path.
- Assert the row set is non-empty.

### B36-2-5: MEDIUM. Mask B for A = 2015 needs `tsd_2015`, which does not exist

**Evidence.** The CR-0035 inventory has `tsd` for 2016–2025 only. NH_CT_River cells flown in Oct–Dec 2015 have A = 2015, and that collection covers about 54% of NH.

**Fix.** Either have CR-0037 generate `tsd_2015` (the record starts in 1999), or state the rule: use the nearest available year, compute D relative to that raster's own year, and test it. Fail closed on any other missing year.

### B36-2-6: MEDIUM. The leaf-risk flag does not affect assignment

**Evidence.** §1.1 versus §Sources.

**Fix.** Make the assignment policy a pinned parameter (`newest` or `newest_leaf_off`, with a tested default), so CR-0037 can switch without a generator CR. Record it in the cache key.

### B36-2-7: MEDIUM. The class filter is a blacklist, and "bit 3" is ambiguous

**Evidence.** §1.3 says "bit 3 of `ClassFlags` clear".
- In the EPT nodes I probed, withheld points are `ClassFlags` value **4**, which is bit 2 counting from 0. Value 8 is the overlap flag.
- An off-by-one would drop overlap points and keep withheld ones.
- The blacklist keeps:
  - class 20 (ignored ground, present in EPT, harmless);
  - class 21 (snow);
  - class 22 (temporal exclusion, i.e. points from another date), which would mix acquisition dates within a cell.

**Fix.**
- Write the flag as `ClassFlags & 0x04 == 0`.
- Use a whitelist: {1, 2, 3, 4, 5, 9}, plus 20 counted as ground-level.
- Add a test.

### B36-2-8: LOW. State the reference-year fallback and the effective C3 band

**Evidence.** `ch` and `cc` resolve to 2022 for A = 2015–2020. The C3 band is effectively [0.61, 2.0] because of the feet control.

**Fix.** One sentence in §5, and print the resolved reference year in the gate log.

### B36-2-9: LOW. The C4 regenerating range is wide

**Evidence.** The `REGEN_YEARS` range of (3, 15) dilutes the 1–3 m signal.

**Fix.** Use 3–10 years. If the range stays at 3–15, record the reason in the script.

### B36-2-10: MEDIUM. Registration (C2) never runs on a native-CRS (rockyweb) source

**Evidence.** C2 runs only in W1 (EPT, EPSG:3857). W2 and W3 run C3 and C5, which catch gross misplacement (cells become NODATA) but not a metre-scale datum or pipeline offset in the UTM path.

**Fix.** Add a C2 run on a rockyweb unit large enough for 8 windows of 128 cells, about 12 × 12 km. At QL2 that is about 0.5 G points, which is cheap. Alternatively, run C2 on W2 enlarged.

### B36-2-11: MEDIUM. Sliver work units make the pilot unpassable

**Evidence.**
- `run_checks` (`check_lidar_structure.py:274-279`) and `pilot()` (:379-384) run C3 for **every** work unit present.
- `height_ratio` returns NaN below `MIN_CELLS` = 200, so the check fails.
- A sliver of NH_Coastal_2 in W1, or of a second unit in W3, therefore fails the pilot on correct data. That invites post-hoc edits to the thresholds.

**Fix.** Gate C3 on units with at least `MIN_CELLS` forest cells in the window. Report smaller units as observations. Require each unit in `lidar_sources.csv` that the pilot is meant to exercise to be gated somewhere.

### B36-2-12: LOW. A from `GpsTime` must not trust the header flag

**Evidence.** The global-encoding flag reads 0 in the EPT nodes, while the values are adjusted standard time (verified above).

**Fix.** Decode as adjusted standard time and refuse a cell date outside the work unit's WESM [`collect_start`, `collect_end`] ± 7 days.

### B36-2-13: LOW. Mismatch between the CR and the code on the C6 control; C6 checks one feature

**Evidence.** CR §5 says the C6 control is "`LIDAR_HAG_MAXDIST_M` set above `LIDAR_PAD_M`". The code perturbs one cell (`perturb_one`), and compares only `lid_p95`.

**Fix.** Compare every feature plus the meta bands, and align the text with the code.

### B36-2-14: LOW. PA-0021(a) "built by someone other than the author"

**Evidence.** The controls were written by the CR author.

**Fix.** Record in the review log that the reviewers examined each control as the independent party, or have a reviewer add one control (for example B36-2-1's).

---

## (c) Outside the changed text

No new BLOCKING findings.

## Sources
- LANDFIRE CH description: https://wifire-data.sdsc.edu/dataset/lf-canopy-height
- WESM.csv as committed: `docs/quality/evidence/CR-0036/WESM.csv` (sha256 `eb1a447a…`)
- EPT nodes: https://s3-us-west-2.amazonaws.com/usgs-lidar-public/{NH_Coastal_1_2019, USGS_LPC_CT_River_Lot6_Winnipesaulee_2015_LAS_2017, NH_Umbagog_2016, VT_Statewide_1_A23}/ept-data/
