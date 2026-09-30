# CR-0029: Draw the availability background sample uniform in area (EPSG:5070), not in degrees

**Status: v3, 2026-09-30 — APPROVED by agent quorum and signed off by the lead on 2026-09-30 (CLAUDE.md §1.4; round 2: reviewers A and B both APPROVE WITH FOLLOW-UPS, conditional on removing the new `EPSG:5070` literal; met in v3 §2/§3). Nothing has been implemented; the lead has signed off; implementation may begin (deliverables that need the data host wait for one).** Review log: `CR-0029-review-log.md`.

## Scope
Change `analyze_grouse.in_state_background_points` to draw uniformly over the projected box and transform back to lon/lat, replay the draw exactly in `check_partition.py`, and regenerate everything downstream of the availability sample (BUG-0090; PA-0046).

## Why now
BUG-0090: the availability points are uniform in longitude and latitude over the region box, which is not uniform in area at these latitudes (cos 47.6° / cos 42.9° ≈ 0.92 across Maine), so `Avail_Pct` is biased toward envelopes common in the south by up to about 8 %, and `Selection_Ratio`, `env_zone` and the negatives' weights inherit it. Small, but it feeds the training design.

## The change
### 1. Root cause
As BUG-0090 §5: a random spatial draw made in a geographic CRS and used as an area-uniform sample; no rule named the CRS a draw must be uniform in.

### 2. Code (normative)
- `regions.py` gains `from_5070(x, y)`, the cached inverse of `to_5070`. No new `EPSG:5070` literal anywhere (BUG-0047 open; PA-0025(d)): `analyze_grouse.py` calls `regions.to_5070`/`from_5070` only, and the replay derives the CRS from `regions._ANALYSIS_EPSG` (`regions.py:88`, a top-level literal).
- `analyze_grouse.py` gains module constants, readable by `check_partition.literal_assignments`: `AVAILABILITY_SEED = 1` (today the keyword default of `background_envelope_sample`, `:468`), `NONVEG_RATE_SEED = 0` (today the literal default of `background_nonveg_rate`, `:383`); both callers pass their constant.
- `in_state_background_points(region, n_samples, seed)` (`:360-379`; degree draw at `:369-370`): transform the four corners of `BOXES[region]` with `regions.to_5070` and take their bounding rectangle (valid for these boxes: all lie east of the projection's central meridian, −96°, so x and y are monotone along every box edge and the projected box's extrema are at its corners); per batch draw `rng.uniform` in x then y over the rectangle (same `rng`, same batch loop, same `MAX_BG_BATCHES`); `regions.from_5070` back to lon/lat; **reject points outside `BOXES[region]`** (the rectangle exceeds the lon/lat box; rectangle ∩ box ∩ state = state, so the clip does not bias the area-uniform draw) so P5a's "every row in the box" holds unchanged; then `in_state` as today. The output schema of `availability_sample_{R}.csv` is unchanged (or the CR-0020 superset, whichever has landed).
- Both callers change: `background_envelope_sample` (`:488`, the sample this CR is about) and `background_nonveg_rate` (`:392`, the non-vegetated landscape baseline, print-only), whose printed rate moves slightly.

### 3. Acceptance (amends CR-0007's `check_partition.py`; CR-0013 for the OBS)
- **Gate P9 (exact).** `check_partition.py` replays the draw from module constants read by AST: `BOXES`, `BACKGROUND_N` (already in `ANALYZE_CONSTS`), `MAX_BG_BATCHES` and `AVAILABILITY_SEED` (added to `ANALYZE_CONSTS`, `:77-79`), and `_ANALYSIS_EPSG` (added to `REGION_CONSTS`, `:74-76`). It builds its own `pyproj.Transformer` from `LONLAT_EPSG` (`:47`) to `_ANALYSIS_EPSG` (it never imports `regions`, CR-0007 P3), runs `default_rng(AVAILABILITY_SEED)`, the batch loop, x-then-y order, the inverse transform, the box clip and `in_state` (`contains_xy` on the unioned county polygons, `:343-355`, the same predicate `regions._polygon_region` applies), and compares the result to the recorded `availability_sample_{R}.csv` coordinates under a `check_partition.py` literal `P9_RTOL` (as `KDE_RTOL`, `:85`). P9 also requires agreement on every rejected draw (a boundary disagreement would shift the sequence): measure-zero, stated. Attack row (PA-0021(a), reviewer-built): a degree-uniform draw with the same seed → FAIL; the intended draw → PASS. P9 prints the pyproj and PROJ versions it ran under.
- P5a (every row in the lon/lat box) and P5 (in-state) unchanged.
- `tests/test_check_partition.py`: the stub `analyze_grouse.py` (`:120-125`) gains the new literals; the fixture's `availability()` builder (`:182-197`, per-point degree draws today) is rewritten to the batch semantics so the correct-partition fixture passes P9.
- **OBS O12 (PA-0021(f)), in `acceptance_split.py`.** In-state points per unit area in three latitude bands per region, the bands being equal-area cuts of the projected box (so their in-state areas differ): class n/a (background); subset per region; null: multinomial with expected counts proportional to the in-state area of each band (from the dissolved county polygons in EPSG:5070, `acquisition_domain`, `:831`), chi-square p reported. A degree-uniform draw shows a monotone north-south deficit; reported, not gated. O12 needs `paths.availability_sample` (added by whichever of CR-0020 and this CR lands first). Its id presumes O11 (CR-0030) lands first; otherwise the next free id is taken.
- No must-change pin: P9 is exact and every recorded coordinate changes by design.
- Pins: `check_partition.py`'s constant lists; `GATE_SECTION_SHA256["paths"]` (the `obs` section is unpinned, `OBS_ONLY_SECTIONS`, `tests/test_acceptance_split.py:2016`); `OBS_IDS`.

### 4. Rebuild
`analyze_grouse.py` (availability sample, envelope metrics and S's `env_zone` change, `:964-975`, written at `:1099`) → `prepare_training_data.py` (`env_zone` is a positives column, `:81-86`) → `generate_negatives.py` → `acceptance_split.py` (O12, R-gates) → `check_partition.py` (P9). Every split file regenerates; validation metrics before and after are not comparable; retrain follow-up. With CR-0020 landed first, its train-only metrics are rebuilt from the new sample in the same run.

## Impact
- `availability_sample_*`, `evaluated_sightings_*` (`env_zone`), `envelope_metrics_*`, the positives files, the candidate pool and both negative draws regenerate; `calibration.json` invalid until retrain.
- The diagnostic map, `tune_bins.py` and `background_nonveg_rate`'s printed baseline change; no code change for them.
- Tracker note (reviewer B): E11's `m_in.update` is last-wins (`acceptance_split.py:2142`), so a stale positives manifest section would not be caught by E11 alone; R1 catches it here.

## One change per CR (CR-0011 A5)
One draw rule with its exact replay gate and the regeneration it forces; cannot land without the regeneration (the recorded sample would fail P9). **Landing order with CR-0020:** either; each CR's replay reads the sample on disk, and the second to land re-runs acceptance (see CR-0020 § One change per CR).

## Risk: LOW–MEDIUM (rebuild)
| risk | mitigation |
|---|---|
| Replay and pipeline transformers differ (pyproj/PROJ versions) | Both use the same CRS definition (`_ANALYSIS_EPSG`); P9 prints the versions it ran under, and `P9_RTOL` absorbs sub-millimetre differences; a PROJ change between the pipeline run and the check that exceeds it is an accepted dependence: re-run P9 under the pipeline's PROJ |
| Rejection efficiency falls (rectangle ⊃ box ⊃ state) | `MAX_BG_BATCHES` = 20 at `BACKGROUND_N` per batch is ample (ME acceptance ≈ 0.4 → about 3 batches); the run reports batches used |
| The rebuild changes the positives files | Expected and stated (§4); CR-0019's backup/restore; not-comparable statement |

## Test plan
**Validatable here:** none (pyproj, rasterio not installed).
**On the data host, before approval of the acceptance code (A3):** P9 harness test with the attack row and the rewritten fixture builder; O12 on the fixture.
**After approval:** scratch-tree run (O12 before/after), then the live rebuild.

## Deliverables (in execution order)
- [ ] 1. Acceptance code (A3): P9, O12, the attack row and the fixture changes on an unmerged branch.
- [ ] 2. Code (§2: `regions.from_5070`, constants, the draw); pins.
- [ ] 3. Scratch-tree run: O12 before/after recorded.
- [ ] 4. Backup; live rebuild (§4); acceptance (`acceptance_split.py`, `check_partition.py`).
- [ ] 5. Bookkeeping: BUG-0090 → FIXED; `BUG_LOG.md`; PA-0046 Swept? cell; tracker note on E11 last-wins; CHANGELOG (not-comparable statement).
- [ ] 6. Close-out.

## Out of scope
- The retrain.
- `BACKGROUND_N` and the envelope thresholds.
- The availability sample's feature columns (CR-0020 step 0).
- Consolidating the existing `EPSG:5070` literals (BUG-0047).
