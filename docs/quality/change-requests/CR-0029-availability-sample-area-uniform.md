# CR-0029: Draw the availability background sample uniform in area (EPSG:5070), not in degrees

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented.** Review log: `CR-0029-review-log.md`, to be created by the first reviewer.

## Scope
Change `analyze_grouse.sample_availability` to draw uniformly over the projected box and transform to lon/lat, regenerate the availability samples and everything that depends on them, and check the draw's density in acceptance (BUG-0090; PA-0046).

## Why now
BUG-0090: the availability points are uniform in longitude and latitude over the region box, which is not uniform in area at these latitudes (cos 47.6° / cos 42.9° ≈ 0.92 across Maine), so `Avail_Pct` is biased toward envelopes common in the south by up to about 8 %, and `Selection_Ratio` and the negatives' weights inherit it. Small, but it feeds the training design, and CR-0020 re-bins whatever sample is on disk, so it is better fixed first or alongside.

## The change
### 1. Root cause
As BUG-0090 §5: a random spatial draw made in a geographic CRS and used as an area-uniform sample; no rule named the CRS a draw must be uniform in.

### 2. Code (normative)
`analyze_grouse.sample_availability` (`:365-372`): transform the four box corners with `regions.to_5070`, take the bounding rectangle in metres, draw `rng.uniform` in x and y over it (same `rng`, same `seed`, same batch loop and `MAX_BG_BATCHES`), transform back with the inverse transformer (`Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)`, cached like `to_5070`), then `in_state` as today. The rectangle is slightly larger than the lon/lat box; the in-state filter is what defines the sample, as before. Written output (`availability_sample_{R}.csv`) keeps its schema and gains a `draw_crs` attribute row? No: the manifest records it instead (§3). `check_partition.py` P5 (in-state) is unchanged.

### 3. Acceptance (amends CR-0007 P5 / CR-0013)
- Config: `availability.draw_crs = "EPSG:5070"`, `availability.seed` (today's constant), so the replay can reproduce the draw.
- **Gate P5b (exact):** the replay redraws the sample with the config rule and seed and compares to the recorded `availability_sample_{R}.csv` (coordinates to the config `rounding` rule). Attack row: a degree-uniform draw with the same seed → FAIL.
- **OBS O12 (PA-0021(f)):** in-state points per unit area in three equal-area latitude bands per region; class n/a (background), subset per region, null: multinomial with equal expected counts (chi-square p reported). A degree-uniform draw shows a monotone north-south deficit; reported, not gated (the in-state polygon shape also affects it).

### 4. Rebuild
`analyze_grouse.py` (availability and envelope metrics change; sightings columns unchanged) → `generate_negatives.py` (weights change) → `acceptance_split.py`. Positives and blocks unchanged. With CR-0020, the train-only metrics are rebuilt from the new sample in the same run.

## Impact
- `availability_sample_*`, `envelope_metrics_*`, the candidate pool weights and both negative draws regenerate; validation metrics before/after not comparable; retrain follow-up.
- The diagnostic map and `tune_bins.py` read the new metrics; no code change for them.

## One change per CR (CR-0011 A5)
One draw rule with its acceptance and regeneration; cannot land without the regeneration (the recorded sample would fail P5b).

## Risk: LOW–MEDIUM (rebuild)
| risk | mitigation |
|---|---|
| Replay and pipeline transformers differ (pyproj versions) | Same `regions.to_5070`/inverse used by both; E11's environment pin; rounding rule |
| Ordering with CR-0020 | Either order; each CR's replay reads the sample on disk; the second to land re-runs acceptance |

## Test plan
**Validatable here:** none (pyproj not installed).
**Not validatable here:** P5b harness test, O12, the rebuild.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): P5b, O12 and the attack row on an unmerged branch.
- [ ] 2. Code (§2); config.
- [ ] 3. Scratch-tree run: O12 before/after; changed-weight counts pre-registered (MC).
- [ ] 4. Backup; live rebuild (§4); acceptance.
- [ ] 5. Bookkeeping: BUG-0090 → FIXED; `BUG_LOG.md`; PA-0046 Swept? cell; CHANGELOG (not-comparable statement).
- [ ] 6. Close-out.

## Out of scope
- The retrain.
- `BACKGROUND_N` and the envelope thresholds.
