# BUG-0087: `symptom_check.pair_rows` labels its per-cell inputs "real units" but writes the stored int16 codes for `tsd`, `tpa_live`, `balive`, `qmd` and `carbon_dwn`; only `road_dist` is decoded

> Found by the 2026-09-30 static code review at `3b3e7d1`.
> **Status: FIXED in code (`2c05388`, 2026-09-30, trivial fix, no CR); validation pending on the data host; owner: lead.**
> fix once a shared decoder exists.**

## 1. Description
`pair_rows` multiplies each continuous centre value by its
`FEATURE_SPEC` scale, which undoes the model-input scaling and returns
the **stored** number, then decodes `road_dist` to metres and stops.
The other five encoded features are written to `pairs_frozen.csv` as
stored units under a docstring that promises real units: a `tsd` of
3434 is log1p(30)·1000, not 3434 years; a `balive` of 1234 is 123.4
ft²/acre.

## 2. Where encountered
- `symptom_check.py:576-578` (docstring), `:596-598` (scale only),
  `:603-604` (`road_dist_decode` only).
- Encoders/decoders: `models.py:639-767` (`road_dist_decode`,
  `tsd_decode`, `tpa_live_decode`, `treemap_decode`).
- ARCHITECTURE.md invariant: "Every continuous feature has a storage
  encoding distinct from its `FEATURE_SPEC` scale … undoing both, in
  that order."

## 3. What it caused to fail
A human reading `pairs_frozen.csv` sees encoded integers labelled as
real units. Diagnostic output only.

## 4. What the defect was
`symptom_check.py:576-578`, `:596-598`, `:603-604`:
```python
def pair_rows(scorer, cells):
    """Per cell: every input at the centre (real units), road_dist in
    metres, missing inputs, and the fp32 calibrated probability."""
...
        for j, f in enumerate(scorer.cont_f):
            v = float(cont[j, HALF, HALF]) * FEATURE_SPEC[f].get("scale", 1.0)
            rec[f] = v
...
        rd = rec.get("road_dist", float("nan"))
        rec["road_dist_m"] = (float(road_dist_decode(rd)) if np.isfinite(rd)
                              else float("nan"))
```

## 5. Root cause analysis (Five Whys)
1. *Why encoded?* Only the scale is undone; the log/fixed-point step is
   applied to one feature.
2. *Why one?* `road_dist` was the feature the symptom (CR-0009) was
   about; the others were added to the row without the second step.
3. *Why easy to miss?* There is no single decoder entry point; each
   writer has to know which of four decoders applies to which feature
   (`inspect_point.py` does, by a hand-written table).
4. *Why no rule?* The invariant is in ARCHITECTURE.md only.

**Root cause:** the two-step decode is an invariant without an API;
every human-facing writer re-derives the per-feature decoder table by
hand, and this one stopped after the first feature.

## 6. Corrective action
**None yet.** Proposed: add `models.decode_feature(name, stored)`
mapping each encoded feature to its decoder (identity for the rest),
call it in `pair_rows` and `inspect_point.py`, and add the PA-0043
test. **Implemented 2026-09-30, commit `2c05388` (trivial fix under CLAUDE.md §1: one function, no public signature, file format or schema change).** `pair_rows` undoes the storage encoding after the `FEATURE_SPEC` scale for every encoded feature (log decoders for `road_dist`/`tsd`/`tpa_live`, `treemap_decode` for the fixed-point three); `road_dist_m` is kept as a column. The shared `decode_feature` API of PA-0043 is still a CR item. Validation here: `python -m py_compile` only, since this environment has no numpy, torch, rasterio or data tree. To verify: re-run `symptom_check.py` in-process as CR-0009 deliverable 9 did: `pairs_frozen.csv` `tsd` values lie in [0, 30], `balive` in [0, 400]; the 2a/2b OBS rows are unchanged against `docs/quality/evidence/CR-0009/symptom/report.txt`.
Status: **FIXED (code); validation pending on the data host.** Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "decode",
"metres", "units", "log-encoded".

**Matches:** none as a BUG; ARCHITECTURE.md records the invariant and
names `inspect_point.py` as the worked example.

**Prior-preventive-action failure analysis.** No rule; the invariant
was documented after the road-distance saturation episode (CHANGELOG
"road-hugging investigation") and relies on each author reading it.
Category: not a rule.

## 8. Preventive action
**PA-0043**: `models.py` owns one `decode_feature(name, stored)`
covering every encoded feature; any table, CSV or print that labels a
feature value as a real unit calls it; a test asserts the human-facing
writers (`inspect_point.py`, `symptom_check.py`) decode every encoded
feature in `FEATURE_SPEC`.

**Sweep (§3.5), human-facing writers of feature values:**
`symptom_check.pair_rows` (this); `inspect_point.py` (all four decoders,
correct); `check_road_dist.py`, `find_tsd_contrast_points.py` (decode,
correct); `predict.py` TensorBoard feature maps (documented as the
scaled model input, not real units; recorded). No other instance.

## Cross-references
ARCHITECTURE.md (storage encodings); CR-0009 (symptom check); PA-0043.
