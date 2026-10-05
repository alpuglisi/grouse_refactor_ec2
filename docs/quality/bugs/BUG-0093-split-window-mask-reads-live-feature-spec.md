# BUG-0093: the split's window mask reads the live `models.FEATURE_SPEC`, while its acceptance replay reads a frozen list (latent; any model-feature addition breaks split regeneration)

**Status:** FIXED (CR-0033, 2026-10-05). Found in CR-0032 round-1 review
(reviewer A, concern A5); never observed running.

## 1. Description
The split producer (`prepare_training_data.py`, and `generate_negatives.py`
through it) decides which records keep their 64 px window from **every
`FEATURE_SPEC` raster**. The acceptance replay (`acceptance_split.py`)
decides the same thing from its own frozen config list
`feature_spec_keys` (15 names). Nothing ties the two, so registering a new
model feature silently changes the split pipeline's inputs.

## 2. Where encountered
- `prepare_training_data.py:161-177` (`window_mask`), called at
  `prepare_training_data.py:392` and `generate_negatives.py:481`.
- `acceptance_split.py:657-669` (`window_mask` over
  `cfg["feature_spec_keys"]`) and `acceptance_split.py:2399` (manifest
  input check); `docs/quality/acceptance_split.json:122`.
- Context: CR-0032 adds four `mch_*` entries to `FEATURE_SPEC`.

## 3. What it caused to fail
Latent. With any `FEATURE_SPEC` addition:
1. before the new rasters exist on a host, `prepare_training_data.py` /
   `generate_negatives.py` raise `MissingDataError` (shown by
   `tests/test_cr0033.py` T2 on the pre-fix code);
2. once they exist, each path `window_mask` resolves enters
   `rd.rasters_touched` and the manifest's inputs, which acceptance
   rejects ("manifest lists an input outside S and I"), and the standing
   checks then refuse training on the regenerated split;
3. a new raster with a smaller extent would also change which records
   are kept (T2 on-disk variant: the centre record flips to dropped).

## 4. What the defect was
```python
def window_mask(df, rd):
    """True where regions.window_in_bounds holds on every FEATURE_SPEC
    raster at rd.raster_path(feat, year), ..."""
    import rasterio
    from models import FEATURE_SPEC
    ...
    for feat in FEATURE_SPEC:
        for yr in sorted(set(years.tolist())):
            sel = years == yr
            path = rd.raster_path(feat, int(yr))
```
versus the replay:
```python
        for feat in cfg["feature_spec_keys"]:
            rel = rasters.raster_path(region, feat, yr)
            ok[m] &= rasters.window_ok(rel, lons[m], lats[m])
```

## 5. Root cause analysis (Five Whys)
1. Why would registering `mch_*` break split regeneration? Because the
   producer's window mask would read four rasters the replay does not.
2. Why does the producer read them? It iterates `FEATURE_SPEC`, the
   model's channel registry.
3. Why does the split read the model registry? When CR-0012 wrote the
   window rule, "every model raster" and "every split raster" were the
   same 15 names, so the registry served as the list.
4. Why did nothing catch the divergence? The acceptance config pinned its
   own copy (by design, CR-0013: acceptance reads only its config and
   `regions.py`), and no test compared the producer's source with it.
5. Why was that comparison never required? PA-0001/PA-0025 require one
   definition per *spatial/region-domain* constant; a split input list
   held in a registry that other changes edit was outside their scope.

**Root cause:** an input set of an accepted artifact (the split) was taken
from a live registry owned by another concern (the model's feature spec),
instead of a pinned constant tied to the acceptance replay's copy.

## 6. Corrective action
CR-0033: `prepare_training_data.SPLIT_WINDOW_FEATURES` (the 15 names, in
the acceptance order) is the only list `window_mask` iterates; module and
function docstrings say so. `tests/test_cr0033.py`: T1 equality with
`acceptance_split.json["feature_spec_keys"]`; T2 (two variants) an extra
registered feature is never opened, never recorded in `rasters_touched`,
and leaves the mask unchanged. Today's list equals `list(FEATURE_SPEC)`, so
no split output changes. Addresses the root cause (the registry is no
longer an input of the split), not only the symptom (`mch_*`).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for a split/acceptance
input taken from a live source, a constant held in two places, and
producer/replay drift. Related: **PA-0001** (BUG-0001) and **PA-0025**
(BUG-0043): one definition per spatial/region-domain constant, imported
everywhere, enforced by `tests/test_shared_constants.py`. Not the same
bug, but the same family (two sources for one fact).

**Prior-preventive-action failure analysis.** PA-0025 did not prevent this
because it is **too narrow**: its scope is spatial/region-domain constants
assigned in `regions.py`, and its enforcement pins named constants. The
split's raster list was not a named constant at all; it was implicit in a
registry iteration, so neither the rule nor the test could see it. The
acceptance design (CR-0013) correctly froze its own copy, but no rule
required the producer to be tied to that copy.

## 8. Preventive action
**PA-0048** (extends PA-0025): every list or constant that selects the
inputs or records of an accepted artifact is a pinned constant tied by a
test to the acceptance replay's copy; never a registry other changes edit.
Sweep (2026-10-05, by mechanism): `git grep` for `FEATURE_SPEC`,
`RASTER_FEATURES`, `available_features(`, `discover_features(` over the
tracked `*.py` minus `inv_*`/`res_*`/`docs/`/`tests/`/`legacy/`, keeping
producers of accepted artifacts (split files, negatives, envelope,
manifest): only `prepare_training_data.window_mask` (this bug, fixed).
Not the mechanism: `generate_negatives.extract_envelope` uses the pinned
`ENVELOPE_FEATURES`; `analyze_grouse.FEATURES` is its own literal;
`grouse_data.training_frame` and the training/prediction scripts are
consumers; `realign_rasters.py`'s CLI default, and the static generators'
year unions (`generate_road_distance.py:311`,
`generate_time_since_disturbance.py:252`,
`generate_treemap_features.py:373`) produce rasters no acceptance replays.
The year unions gain new members once `mch_*` is registered; harmless
(`mch_*` copies the same union) but recorded in the tracker for CR-0032.
No new BUG.

## Cross-references
CR-0033 (fix); CR-0032 review log A5 (discovery); PA-0048; extends PA-0025.
