# CR-0036 review log

Verdicts, concerns and dispositions for `CR-0036-3dep-lidar-structure-generator.md` (CLAUDE.md §1.3). Full reviews: `evidence/CR-0036/REVIEW_A_r1.md` and `REVIEW_B_r1.md`.

## Round 1 (v1)
| Reviewer | Verdict |
|---|---|
| A (registration, metrics, process) | REVISE: 3 BLOCKING, 10 MAJOR, 4 MEDIUM, 2 LOW |
| B (ecology, data reality) | REVISE: 2 BLOCKING, 5 MAJOR, 10 MEDIUM, 3 LOW |

All concerns below were checked against the code or sources before being accepted. v2 addresses them as follows.

| id | sev | concern (short) | disposition | where (v2) |
|---|---|---|---|---|
| A36-1 = B36-1 | BLOCKING | rockyweb tiles are in native CRSs and sometimes US feet; v1 assumed EPSG:3857 | accepted: per-source pinned PROJ pipeline and XY/Z unit factors in `lidar_sources.csv`, built from WESM `horiz_crs`/`vert_crs` and source headers; the generator refuses on mismatch; C3 and C5 run per work unit; pilot W2 spans both readers; feet test | §Sources, §1.4, §5, §6 |
| A36-2 | BLOCKING | one project per block vs per cell | accepted: assignment per cell (newest `collect_end` covering the cell centre); a block reads every work unit assigned to its cells and bins each point only into cells assigned to its own unit | §1.1, §1.2, §1.6 |
| A36-3 = B36-2 | BLOCKING | stale mask blind when the vintage precedes the flight | accepted: Mask A uses `tsd` at max(Y, A) and masks `min(Y,A) ≤ D ≤ max(Y,A)`; tests cover Y < A, Y = A, Y > A | §2, tests |
| A36-4 | MAJOR | mask arithmetic: rounding, equality, multi-year projects, tsd nodata | accepted: `D` uses `round(tsd_decode)`; inclusive bounds; per-cell `A` from median `GpsTime`; tsd nodata is masked; rounding test | §2, tests |
| A36-5 = B36-3 | MAJOR | regrowth after the flight is not caught; V1-class problem understated | accepted: Mask B (young stands where \|Y−A\| > tolerance); CR-0037 bound to report within \|Y−A\| ≤ 2 (deliverable 4 tracker row) | §2, deliverable 4 |
| A36-6 = B36-9 | MAJOR | withheld points are not Classification ≥ 128; buildings, wires and bridges kept | accepted: `Withheld`/`ClassFlags` bit; classes 6, 7, 13–18 dropped | §1.3 |
| A36-7 | MAJOR | clipping breaks PA-0034 / `mch_*` | accepted: encoders raise on out-of-range values; noise HAG dropped before encoding | §1.5, §1.7, tests |
| A36-8 | MAJOR | metric edge cases undefined | accepted: denominators, `ddof`, percentile method, minimum counts and per-cell rules all stated; oracle tests | §1.7, tests |
| A36-9 = B36-7 = B36-19 | MAJOR | `hag_nn` defaults: seams not exact; slope errors; the PDAL seam test would skip | accepted: HAG moved to pinned numpy/scipy (IDW k = 6 within 30 m ≤ 60 m pad), so seams are exact by construction; the seam test runs without PDAL; steep window W3 | §1.5, §5, §6 |
| A36-10 = B36-13 | MAJOR | block memory (1.3–2.4 G points per 256² block) | accepted: 64-cell blocks (~80 M points at QL1); LAZ tiles processed tile-major, downloaded once | §1.2 |
| A36-11 | MAJOR | cache key misses grid, WESM and PROJ | accepted: key hashes the template grid, the source table sha256 (which pins WESM and pipelines), the recipe and the work units | §1.8 |
| A36-12 = B36-5 = B36-6 | MAJOR | gates cannot fail; no controls; road sweep cannot run on the `/tmp` pilot; Spearman blind to scale; understory untested | accepted: `check_lidar_structure.py` with a negative control per gate (the gate passes only if the control fails); C2 reads the pilot file directly on W1 (20 km, ~25 windows of 128); C3 is an absolute scale test that rejects feet; C4 is an understory ecological contrast that rejects permutation; `--self-test` | §5, `check_lidar_structure.py` |
| A36-13 = B36-14 | MAJOR / MEDIUM | test and gate code not committed; thresholds in prose | accepted: both committed with v2; thresholds live only in the script's constants | `check_lidar_structure.py`, `tests/test_cr0036.py` |
| B36-4 | MAJOR | project, leaf and density offsets; pilot inside one project | accepted: per-cell `A` and day-of-year bands; leaf-risk flag in the source table; C7 boundary offsets in W2; CR-0037 bound to within-work-unit evaluation | §1.7 table, §3, §5, §6, deliverable 4 |
| A36-14 | MEDIUM | `Transformer.from_crs` operation not pinned | accepted: `from_pipeline` with pinned strings; lint forbids `from_crs` | §1.4, lint |
| A36-15 = B36-16 | MEDIUM | registries not in `models.py`; `test_cr0032.py:163`; `PATH_TEMPLATES` | accepted: all registry entries moved to CR-0037; encoders local to the generator for this CR | §4, Out of scope |
| A36-16 = B36-11 | MEDIUM | WESM/EPT name mapping and live WESM | accepted: pinned `lidar_sources.csv` from a WESM snapshot with sha256 (PA-0048) | §Sources |
| A36-17 | MEDIUM | A5: registry and rockyweb reader belong elsewhere | partly accepted: registry → CR-0037. The rockyweb reader stays, because both reviewers' BLOCKING CRS concern can only be tested by a pilot that exercises it. One landable unit: generator plus pilot | §Scope, §6 |
| A36-18 | LOW | vintages 2016–2025; pad units; "rotated template"; duplicated facts | accepted: corrected; the pad is in template metres; the "rotated" claim is removed (templates are north-up, `grid_mismatch`) | throughout |
| A36-19 | LOW | int16 count cap; lint misses thinning filters; S3 request fan-out | accepted: meta bands are int32; lint extended; `requests` = 8 | §1.2, §3, lint |
| B36-8 | MEDIUM | leaf-off all-return fractions; occlusion-adjusted form preferred; more bins | accepted: four occlusion-adjusted bins (0.5–2, 1–3, 3–5, 5–10 m); `lid_wcov5` renamed and redefined as woody/conifer cover | §1.7 |
| B36-10 | MEDIUM | per-cell "no ground" rule creates habitat-tracking missingness | accepted: no per-cell ground rule; points lacking ground within 30 m have no HAG; a cell is NODATA only below 50 returns | §1.5, §1.7 |
| B36-12 | MEDIUM | rockyweb throughput tested at one stream; requester-pays bucket unchecked | accepted: C8 measures 8 and 32 streams and lists the `usgs-lidar` requester-pays bucket | §5 C8 |
| B36-15 | MEDIUM | cited evidence files not committed | accepted: `WESM.csv` is committed now; `wesm_summary.txt` and `newest_points.txt` regenerated by `build_lidar_sources.py` (deliverable 3) | deliverables |
| B36-17 | MEDIUM | conflicts with HYBRID_REPORT numbering and v1 scope; CR-0038 source-year gate | accepted: stated in Impact | §Impact |
| B36-18 | LOW | snow on early-spring flights | accepted as a tracked item for CR-0037 QA | §Risk |
| B36-20 | LOW | figure inconsistencies | accepted: volume and cost now quoted once, from the pilot | §6 |

## Round 2 (v2, bounded re-review per CR-0011 A2)
| Reviewer | Verdict |
|---|---|
| A | APPROVE WITH FOLLOW-UPS. All round-1 BLOCKING concerns resolved; no new BLOCKING. A36-2-1 and A36-2-2 must be fixed in the text before code. Full review: `evidence/CR-0036/REVIEW_A_r2.md` |
| B | APPROVE WITH FOLLOW-UPS. Both round-1 BLOCKING concerns resolved; no new BLOCKING. B36-2-1 tracked to before deliverable 3. Full review: `evidence/CR-0036/REVIEW_B_r2.md` |
| Author | APPROVE (v3 applies the required text fixes and the follow-ups below) |

**Quorum met (CLAUDE.md §1.4): both reviewers and the author signed off. Status: APPROVED WITH FOLLOW-UPS (v3).**

| id | sev | concern (short) | disposition | where (v3) |
|---|---|---|---|---|
| A36-2-1 = B36-2-7 | MAJOR / MEDIUM | withheld is `ClassFlags & 0x04` (bit 3 is overlap); blacklist kept classes 19–22 | accepted (required before code): class whitelist {0,1,2,3,4,5,9}; withheld = `Withheld` or `ClassFlags & 0x04`; point-filter test | §1.3; `test_point_filter` |
| A36-2-2 = B36-2-13 | MAJOR / LOW | C6 control "maxdist > pad" can be accepted on dense data; C6 compared `lid_p95` only | accepted (required before code): control = the same blocks computed with pad 0, which must differ; all seven features and the count bands compared | §5 C6; `check_seam`, `_read_set` |
| A36-2-3 = B36-2-11 | MAJOR / MEDIUM | C3 and C5 fail on slivers and footprint overreach | accepted: units with fewer than `MIN_CELLS` forest cells are OBS; fallback to the next covering unit when the assigned unit delivers no return | §1.1, §5; `gated_units`, test |
| A36-2-4 = B36-2-4 | MAJOR / MEDIUM | the units/CRS test could pass with no assertions; no XY or header-refusal test | accepted: synthetic rows; feet Z, EPT Z, a pinned UTM→Albers pipeline checked against `from_pipeline`, header-mismatch refusals | tests |
| A36-2-5 | MEDIUM | pilot used `lid_p95` validity for every feature | accepted: per-feature validity | `pilot()` |
| A36-2-6 | MAJOR (follow-up) | controls uncalibrated; single draw | accepted: C4 now needs the real contrast to beat the p99 of a 100-draw permutation null. C3 and C5 controls are deterministic transformations, not random draws, so PA-0021(c) draw counts do not apply | §5 C4; `regen_null` |
| A36-2-7 = B36-2-5 | MEDIUM | Mask B needs `tsd_2015`; nodata, boundary and 1999 start unstated | accepted: years at A < 2016 derived from `tsd_2016`; inclusive bounds; nodata masks; pre-1999 reads as the cap; test | §2; `test_mask_b_before_tsd_record` |
| A36-2-8 | MEDIUM | oracle and CR misaligned (noise drop, ground HAG 0, zero distance, water, first return) | accepted: all stated in the CR and tested | §1.3, §1.5; tests |
| A36-2-9 | MEDIUM | EPT Z already metres; WESM `vert_crs` ftUS would apply feet twice | accepted: Z factor 1 for every EPT row | §1.4; `test_z_units` |
| A36-2-10 | MEDIUM | source table delivered after approval with no review step | accepted: independent agent review of the built table before the pilot | deliverable 2 |
| A36-2-11 = B36-2-12 | LOW | GPS time type; acquisition date vs WESM window | accepted: decode as adjusted standard regardless of the flag; cells outside the window ± 7 days are NODATA and counted | §2 |
| A36-2-12 = B36-2-8 | LOW | prose restates thresholds; C3 effective band; `ch`/`cc` 2022 fallback | accepted: §5 states rules and points to the script's constants; effective band and 2022 fallback stated; the log prints the year used | §5 |
| A36-2-13 | LOW | when masks apply; tsd not in cache key | accepted: blocks cached unmasked, masks applied at assembly, so tsd is not part of the block key | §1.8 |
| B36-2-1 | MAJOR (follow-up) | W3 cannot detect steep-terrain HAG error | accepted as a tracked follow-up: C9, a leave-one-out ground-Z RMSE by slope class with a nearest-1 control, added to the gate script before deliverable 3 | §5 C9; deliverable 2 |
| B36-2-2 | MEDIUM | ties on `collect_end` | accepted: tie-break QL, then EPT, then name; test | §1.1; `test_assign_order_tie_break` |
| B36-2-3 | MEDIUM | footprints from unpinned `WESM.gpkg` | accepted: NNE footprint layer committed with sha256 alongside the table | §1.1; deliverable 2 |
| B36-2-6 | MEDIUM | leaf-risk flag unused in assignment | accepted: `LIDAR_ASSIGN_POLICY` pinned (`newest` here; `newest_leaf_off` for CR-0037 to decide) | §1.1 |
| B36-2-9 | LOW | narrow the regrowth range | accepted: 3–10 years | `REGEN_YEARS` |
| B36-2-10 | MEDIUM | C2 never runs on a rockyweb source | accepted: pilot window W4 (~12 km, one rockyweb unit) runs C2, C3 and C5 | §6 |
| B36-2-14 | LOW | independent party for controls | accepted: both reviewers recorded as the independent party | §5 |
