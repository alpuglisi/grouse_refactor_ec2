# BUG-0076: validation negatives are drawn with envelope weights fitted on every sighting, validation positives included (holdout-dependent evaluation set)

> Found by the 2026-09-30 static code review of the whole pipeline at
> `3b3e7d1` (no `data/` tree, no execution; every claim is a code trace).
> The open-issues tracker records the mechanism as design question **D3**
> (`docs/quality/CR-0007-0008-OPEN-ISSUES.md:240`) with no BUG and no gate;
> this entry gives it an id, a root cause and a rule.
> **Status: OPEN; owner: lead; fix by its own CR.**

## 1. Description
`analyze_grouse.py` fits the envelope binners and the per-envelope
`Selection_Ratio` on **every** habitat record of a state, all years from
`START_YEAR`, before any train/validation split exists.
`generate_negatives.py` turns those ratios into a per-candidate sampling
weight (`1 / Selection_Ratio`, clipped to [0.1, 10]) and draws the
**validation** negatives of each region with those weights, exactly as it
draws the training negatives. So the validation negative set is
constructed as a function of where the validation positives sit in
envelope space: envelopes the positives use get a low weight, envelopes
they avoid a high one. The validation set is therefore separable by
envelope alone, by construction, before the model has seen anything.

## 2. Where encountered
- `analyze_grouse.py:881-890` (binners and envelope ids fitted on all
  habitat records), `:918-923` (`Used_Pct`, `Avail_Pct`,
  `Selection_Ratio`), `:1100` (`envelope_metrics_{region}.csv`).
- `generate_negatives.py:247-259` (`attach_weights`: the same binners,
  `build_weight` per candidate), `:150-154` (`build_weight` returns
  `1 / clip(Selection_Ratio)`), `:283-295` (`draw_region_split`:
  Efraimidis-Spirakis draw on `sub["weight"]`), `:466-469` (one draw per
  region per split, validation included).
- Consumers of the result: `train.build_datasets` (`train.py:345-350`,
  `:388-393`), `model_handler.evaluate`, checkpoint selection
  (`model_handler.py:1344-1357`), `calibrate.py:356-392` (Platt fit and
  `val_prevalence`).

## 3. What it caused to fail
The validation AUC/AP/strict accuracy, and everything that consumes them
(checkpoint selection under `--select-by rank`/`--select-min-delta`, the
divergence guard, `--dynamic-dropout`, the Platt scale and bias), carry an
envelope-separability term that was built into the evaluation set rather
than learned. The size of the term is not measurable in this environment
(no data); on the training side the same weighting is the intended
design, so nothing distinguishes the two in the outputs. No CR-0013 gate
tests it (tracker D3).

## 4. What the defect was
`analyze_grouse.py:881-890`:
```python
    habitat = valid[~valid['nonveg_landcover']].copy()
    if len(habitat) == 0:
        print(f"  [!] All {region} records were non-vegetated. Skipping envelopes.\n")
        return valid, None

    print(f"\nBinning multi-feature envelopes "
         f"(scheme: {' + '.join(f'{c}({v})' for c, v in ENVELOPE_SCHEME)})...")
    binners = fit_scheme_binners(habitat, ENVELOPE_SCHEME)
    habitat['envelope_id'] = build_envelope_id(habitat, ENVELOPE_SCHEME,
                                               binners=binners)
```
`valid` is every collapsed location of the state (`:775-776`), no split.
`generate_negatives.py:247-259`:
```python
    habitat = evaluated[~evaluated["nonveg_landcover"].astype(bool)]
    binners = fit_scheme_binners(habitat, ENVELOPE_SCHEME)
    cand["envelope_id"] = build_envelope_id(cand, ENVELOPE_SCHEME,
                                            binners=binners)
    cand["is_nonveg"] = (cand["sclass"].isin(NON_VEG_SCLASS_CODES)
                         | is_evt_phys_nonveg(cand["evt_phys"]))
    metrics_map = {row["Envelope"]: row for _, row in metrics.iterrows()}
    weights, basis = [], []
    for env_id, nv in zip(cand["envelope_id"], cand["is_nonveg"]):
        w, cls = build_weight(env_id, metrics_map, nv)
        weights.append(w)
        basis.append(cls)
    cand["weight"] = weights
```
`generate_negatives.py:466-469`:
```python
        for s in SPLITS:
            n_pos = len(read_csv(digest(rd.path(f"{s}_positives"))))
            sub = pool[(pool["region"] == r) & (pool["split"] == s)]
            got, draw[r][s] = draw_region_split(sub, n_pos)
```
`draw_region_split` (`:288-292`) weights by `sub["weight"]` for both
splits.

## 5. Root cause analysis (Five Whys)
1. *Why is the validation negative draw a function of validation
   positives?* Its weights come from `Selection_Ratio`, which counts every
   positive's envelope, validation positives included.
2. *Why are validation positives in that count?* `analyze_grouse.py`
   runs before `prepare_training_data.py` assigns blocks; it has no notion
   of a split, and the metrics table is one per region.
3. *Why does the validation draw use the training-side weights at all?*
   CR-0012 pooled the draw and applied one weight column to every split;
   the weights were designed as a training prior (hard negatives, avoided
   envelopes) and the validation draw reused them for symmetry.
4. *Why did no gate catch it?* CR-0013's gates test the split partition
   (E4/E5), the buffer (E7/E13), counts and years; none asks whether the
   holdout's construction depends on the holdout's own labels (D3 says
   so).
5. *Why no rule?* PA-0018/PA-0029 protect the **training** side from the
   holdout (leakage of holdout rows or labels into training). Nothing
   required the holdout itself to be built independently of its labels.

**Root cause:** the statistics that parameterise the negative draw are
fitted once on the whole sighting set and applied to the validation draw,
so validation rows' inclusion probability depends on other validation
rows' labels; no rule or gate covers holdout self-dependence.

## 6. Corrective action
**None yet.** Proposed (own CR; per CR-0011 A5 it spans generator code,
data regeneration and acceptance design, so it may need splitting):
1. fit the envelope binners and `Selection_Ratio` on training-block
   habitat records only (or draw validation negatives with the neutral
   weight inside the `NONVEG_MAX_FRAC` cap), and record which rule was
   used in `split_manifest.json`;
2. add an exact gate that recomputes the validation weights from
   training-block records alone and requires the recorded validation
   `weight` column to equal it;
3. regenerate negatives, re-run acceptance, and treat every validation
   metric before the fix as not comparable (as CR-0009 did for the split).
Status: **OPEN**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0020-holdout-independent-negative-weights.md` (v3, approved by agent quorum after two review rounds; nothing implemented).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "validation",
"holdout", "leak", "weight", "envelope", "Selection_Ratio".

**Matches:** BUG-0027 and BUG-0042 (holdout leaks, spatial, label side);
PA-0018 and PA-0029 (pooled spatial computation; every producer of
training rows constrained by the holdout); tracker D3 (this mechanism,
unowned). No prior BUG for holdout self-dependence.

**Prior-preventive-action failure analysis.** PA-0029 is the nearest
rule. It targets producers of *training* rows and signal, and its sweep
(CR-0015 deliverable 2) enumerated training-time producers; the
validation draw was classed as a split-file row "gated by
`standing_checks`", which only checks the partition. The rule is at the
wrong layer: it constrains what reaches training, not how the holdout is
built. Category: wrong layer / scope.

## 8. Preventive action
**PA-0033** (extends PA-0029): any statistic that parameterises how a
holdout set is constructed (sampling weights, bin edges, KDEs, caps) is
fitted on training-split records only or on a source carrying no holdout
label, a gate recomputes it from training records and compares, and a
holdout row's inclusion probability is never a function of other holdout
rows' labels.

**Sweep (§3.5), by mechanism (statistics fitted on all sightings and
consumed by a holdout-side producer):** `analyze_grouse.py` envelope
metrics (this bug); the sighting KDE (`spatial_density`/`spatial_zone`,
all sightings; diagnostic columns only, BUG-0051); the 300 m buffer
(pool step 6, all sightings; excludes candidates near validation
positives, which removes rather than steers, recorded not filed);
`calibrate.cross_fitted_probs` random folds (tracker D2, reported numbers
only). No other instance.

## Cross-references
Tracker D3; CR-0012 §2 (pooled draw), CR-0013 (gates); PA-0018, PA-0029,
PA-0033; BUG-0027, BUG-0042, BUG-0051.
