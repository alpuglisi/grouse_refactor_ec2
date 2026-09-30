# CR-0029: Draw the availability background sample uniform in area (EPSG:5070), not in degrees

**Status: DRAFT v2, 2026-09-30 — round-1 concerns dispositioned (`CR-0029-review-log.md`); awaiting re-review (CLAUDE.md §1.2, bounded per A2). Nothing has been implemented.**

## Scope
Change `analyze_grouse.in_state_background_points` to draw uniformly over the projected box and transform back to lon/lat, replay the draw exactly in `check_partition.py`, and regenerate everything downstream of the availability sample (BUG-0090; PA-0046).

## Why now
BUG-0090: the availability points are uniform in longitude and latitude over the region box, which is not uniform in area at these latitudes (cos 47.6° / cos 42.9° ≈ 0.92 across Maine), so `Avail_Pct` is biased toward envelopes common in the south by up to about 8 %, and `Selection_Ratio`, `env_zone` and the negatives' weights inherit it. Small, but it feeds the training design.

## The change
### 1. Root cause
As BUG-0090 §5: a random spatial draw made in a geographic CRS and used as an area-uniform sample; no rule named the CRS a draw must be uniform in.

### 2. Code (normative)
- `regions.py` gains `from_5070(x, y)`, the cached inverse of `to_5070` (no new `EPSG:5070` literal outside `regions.py`, BUG-0047).
- `analyze_grouse.py` gains module constants, readable by `check_partition.literal_assignments`: `AVAILABILITY_SEED = 1` (today the keyword default of `background_envelope_sample`, `:472`), `NONVEG_RATE_SEED = 0` (today the literal at `:384`), `AVAILABILITY_DRAW_CRS = "EPSG:5070"`; both callers pass their constant.
- `in_state_background_points(region, n_samples, seed)` (`:355-372`): transform the four corners of `BOXES[region]` with `regions.to_5070` and take their bounding rectangle (valid for these boxes: all lie east of the projection's central meridian, so the projected box's extrema are at its corners); per batch draw `rng.uniform` in x then y over the rectangle (same `rng`, same batch loop, same `MAX_BG_BATCHES`); `regions.from_5070` back to lon/lat; **reject points outside `BOXES[region]`** (the rectangle exceeds the lon/lat box) so P5a's "every row in the box" holds unchanged; then `in_state` as today. The output schema of `availability_sample_{R}.csv` is unchanged (or the CR-0020 superset, whichever has landed).
- Both callers change: `background_envelope_sample` (the sample this CR is about) and `background_nonveg_rate` (`:384`, the non-vegetated landscape baseline), whose printed rate moves slightly.

### 3. Acceptance (amends CR-0007's `check_partition.py`; CR-0013 for the OBS)
- **Gate P9 (exact; new id, "P5b" exists).** `check_partition.py` replays the draw from the module constants it already reads by AST (`BOXES`, `BACKGROUND_N`, `MAX_BG_BATCHES`, `AVAILABILITY_SEED`, `AVAILABILITY_DRAW_CRS`): `default_rng(seed)`, the batch loop, x-then-y order, `to_5070`/`from_5070`, the box clip and `in_state` (`within` on the dissolved counties), and compares the result to the recorded `availability_sample_{R}.csv` coordinates under `comparison.float_rel_tol`. Attack row (PA-0021(a), reviewer-built): a degree-uniform draw with the same seed → FAIL; the intended draw → PASS.
- P5a (every row in the lon/lat box) and P5 (in-state) unchanged.
- **OBS O12 (PA-0021(f)).** In-state points per unit area in three equal-area latitude bands per region: class n/a (background); subset per region; null: multinomial with expected counts proportional to the **in-state area of each band** (from the dissolved county polygons in EPSG:5070), chi-square p reported. A degree-uniform draw shows a monotone north-south deficit; reported, not gated.
- No must-change pin: P9 is exact and every recorded coordinate changes by design.
- Pins: `check_partition.py`'s constant list and `GATE_SECTION_SHA256` for the sections that gain O12.

### 4. Rebuild
`analyze_grouse.py` (availability sample, envelope metrics and S's `env_zone` change, `:955-966`, written at `:1099`) → `prepare_training_data.py` (`env_zone` is a positives column, `:81-86`) → `generate_negatives.py` → `acceptance_split.py`. Every split file regenerates; validation metrics before and after are not comparable; retrain follow-up. With CR-0020 landed first, its train-only metrics are rebuilt from the new sample in the same run.

## Impact
- `availability_sample_*`, `evaluated_sightings_*` (`env_zone`), `envelope_metrics_*`, the positives files, the candidate pool and both negative draws regenerate; `calibration.json` invalid until retrain.
- The diagnostic map, `tune_bins.py` and `background_nonveg_rate`'s printed baseline change; no code change for them.
- Tracker note (reviewer B): E11's `m_in.update` is last-wins (`acceptance_split.py:2142`), so a stale positives manifest section would not be caught by E11 alone; R1 catches it here.

## One change per CR (CR-0011 A5)
One draw rule with its exact replay gate and the regeneration it forces; cannot land without the regeneration (the recorded sample would fail P9). **Landing order with CR-0020:** either; each CR's replay reads the sample on disk, and the second to land re-runs acceptance (see CR-0020 § One change per CR).

## Risk: LOW–MEDIUM (rebuild)
| risk | mitigation |
|---|---|
| Replay and pipeline transformers differ (pyproj versions) | Same `regions.to_5070`/`from_5070` used by both; E11's environment pin; `float_rel_tol` |
| Rejection efficiency falls (rectangle ⊃ box ⊃ state) | `MAX_BG_BATCHES` = 20 at `BACKGROUND_N` per batch is ample; the run reports batches used |
| The rebuild changes the positives files | Expected and stated (§4); CR-0019's backup/restore; not-comparable statement |

## Test plan
**Validatable here:** none (pyproj, rasterio not installed).
**On the data host, before approval (A3):** P9 harness test with the attack row; O12 on the fixture.
**After approval:** scratch-tree run (O12 before/after), then the live rebuild.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): P9, O12 and the attack row on an unmerged branch.
- [ ] 2. Code (§2: `regions.from_5070`, constants, the draw); pins.
- [ ] 3. Scratch-tree run: O12 before/after recorded.
- [ ] 4. Backup; live rebuild (§4); acceptance.
- [ ] 5. Bookkeeping: BUG-0090 → FIXED; `BUG_LOG.md`; PA-0046 Swept? cell; tracker note on E11 last-wins; CHANGELOG (not-comparable statement).
- [ ] 6. Close-out.

## Out of scope
- The retrain.
- `BACKGROUND_N` and the envelope thresholds.
- The availability sample's feature columns (CR-0020 step 0).
