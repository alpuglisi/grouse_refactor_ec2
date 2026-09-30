# BUG-0090: availability background points are drawn uniform in lon/lat degrees over the region box, not uniform in area, biasing `Avail_Pct` and hence `Selection_Ratio` and the negatives' weights against northern envelopes

> Found by the 2026-09-30 static code review at `3b3e7d1`.
> **Status: OPEN (low); owner: lead; trivial fix inside
> `sample_availability` with a rebuild of envelope metrics.**

## 1. Description
`analyze_grouse.py` draws the availability sample as independent
uniforms in longitude and latitude over `BOXES[region]`, keeps the
in-state ones and samples the rasters there. A degree of longitude is
shorter at the north of a box than at the south (cos 47.6° / cos 42.9°
≈ 0.92), so per unit ground area the north is under-sampled by about
8 % relative to the south across the Maine box (less for NH and VT).
`Avail_Pct` per envelope is therefore biased toward envelopes common in
the south; `Selection_Ratio = Used_Pct / Avail_Pct` and the negatives'
`weight = 1 / Selection_Ratio` inherit the bias.

## 2. Where encountered
- `analyze_grouse.py:365-372` (`sample_availability` draw).
- Consumers: `:918-923` (`Avail_Pct`, `Selection_Ratio`),
  `generate_negatives.build_weight` (`:150-154`).

## 3. What it caused to fail
A few percent of systematic error in `Avail_Pct` along the north-south
axis, propagated into negative sampling weights. Small; recorded because
the same draw feeds the training design.

## 4. What the defect was
`analyze_grouse.py:369-370`:
```python
        blon = rng.uniform(min_lon, max_lon, n_samples)
        blat = rng.uniform(min_lat, max_lat, n_samples)
```

## 5. Root cause analysis (Five Whys)
1. *Why biased?* Uniform in degrees is not uniform in area.
2. *Why drawn in degrees?* The box constants are in lon/lat and the
   in-state test takes lon/lat.
3. *Why not caught?* CR-0007 P5 checks the sample is in-state, not its
   density; no rule states which CRS a spatial draw must be uniform in.

**Root cause:** a random spatial draw made in a geographic CRS and used
as an area-uniform sample.

## 6. Corrective action
**None yet.** Trivial fix: draw uniformly in EPSG:5070 over the box's
projected bounds (or by pixel index of the region template, as
`train.sample_background_points` does) and transform to lon/lat; then
re-run `analyze_grouse.py`, `generate_negatives.py` and acceptance
(rebuild). Status: **OPEN (low)**. Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for
"availability", "uniform", "background", "degrees", "area".

**Matches:** CR-0007 P5 (in-state availability), BUG-0032/BUG-0042
(background sampler, other axes), PA-0018.

**Prior-preventive-action failure analysis.** No rule names the CRS a
draw must be uniform in; PA-0018 concerns the source extent of spatial
computations, not their sampling measure. Category: no rule.

## 8. Preventive action
**PA-0046**: a random spatial draw that must be uniform in area is drawn
in the projected analysis CRS (EPSG:5070) or by raster pixel index and
then transformed to lon/lat, never uniform in degrees.

**Sweep (§3.5), `rng.uniform(`/`np.random.uniform(` over tracked
`*.py`:** `analyze_grouse.py:369-370` (this);
`train.sample_background_points` and `pretrain.py` draw by pixel index
(correct). No other instance.

## Cross-references
CR-0007 P5; BUG-0032, BUG-0042; PA-0018, PA-0046.
