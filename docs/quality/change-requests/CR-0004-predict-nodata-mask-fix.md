# CR-0004: Fix `predict.py` nodata/zero-value conflation (BUG-0008)

## Scope
Replace `predict_region`'s post-collapse `ref_band[cy, cx] == 0 and
ref_nodata != 0` masking check with an explicit invalid-data mask built
from the reference layer's *raw* values against its *actual* declared
`nodata`, computed before sentinel values are collapsed to `0`.

## Why now
BUG-0008 (severity high): the current check both (a) drops legitimate
cells whose reference feature value is genuinely `0`, and (b) fails to
mask true nodata whenever the reference raster's own declared `nodata`
attribute is `0` — the exact opposite of the module's own documented
"nodata is handled honestly" guarantee.

## The change
Confirmed via code read: `open_aligned_sources` sets `ref =
rasterio.open(paths[feats[0]])` where `feats = cat_f + cont_f`, i.e. `ref`
*is* the same raster as the reference band (`cat_np[0]` /`ref_band`) used
for masking — `ref.nodata` is already the correct nodata value to check
against, the bug is purely in *when*/*how* it's compared (against the
post-sentinel-collapse array, gated by a `!= 0` guard that defeats itself
when nodata is exactly `0`).

`read_strip` (`predict.py:194-207`) — return the raw reference-band array
alongside the existing collapsed `cat`/`cont` arrays, instead of only the
collapsed arrays:
```python
def read_strip(srcs, cat_f, cont_f, r0, rows, c0, cols):
    window = Window(c0, r0, cols, rows)
    cat_raw = [_safe_windowed_read(srcs[f], window, fill_value=0)
               for f in cat_f]
    cont_raw = [_safe_windowed_read(srcs[f], window, fill_value=0)
                for f in cont_f]
    ref_raw = cat_raw[0] if cat_raw else cont_raw[0]

    cat = np.stack(cat_raw).astype(np.int64)
    cont = np.stack(cont_raw).astype(np.float32)
    for s in NODATA_SENTINELS:
        cat[cat == s] = 0
        cont[cont == s] = 0.0
    for i, f in enumerate(cont_f):
        cont[i] /= float(FEATURE_SPEC[f].get("scale", 1.0))
    return cat, cont, ref_raw
```
`predict_region` (`predict.py:211-294`) — build an explicit invalid mask
from `ref_raw` (pre-collapse) against the raster's real nodata value, and
use that instead of the `== 0` / `!= 0` check:
```python
    cat_np, cont_np, ref_raw = read_strip(srcs, cat_f, cont_f,
                                          r_start + y0, rows_here,
                                          c_start, width)
    # BUG-0008: build the invalid-data mask from RAW values (before
    # sentinel collapse to 0) against the reference raster's real nodata,
    # so a legitimate value of 0 is never masked and a raster whose true
    # nodata IS 0 is still masked correctly.
    invalid_mask = (ref_raw == ref_nodata)
    for s in NODATA_SENTINELS:
        invalid_mask |= (ref_raw == s)
    ...
    for (y, x) in chunk:
        cy, cx = y + IMG_SIZE // 2, x + IMG_SIZE // 2
        if invalid_mask[cy, cx]:
            # center pixel had no data - mask
            continue
```
(removes the old `ref_band = cat_np[0] if cat_f else cont_np[0]` line and
the `ref_band[cy, cx] == 0 and ref_nodata != 0` check it fed.)

## Impact on other parts of the system
- Only `predict.py`'s internal `read_strip`/`predict_region` functions
  change signature/return shape; both are private to this module (not
  imported elsewhere — confirmed via grep) so no external caller is
  affected.
- Output prediction maps will differ from previous runs in two ways, both
  intentional: (1) any raster region whose reference feature is
  legitimately `0` will now be predicted-on instead of masked out
  (increases valid coverage); (2) if any raster in current use has
  `nodata == 0` declared, its true nodata cells will now correctly show as
  masked instead of predicted-on-garbage (decreases coverage, but removes
  garbage predictions).
- `_safe_windowed_read`'s existing `fill_value=0` behavior for
  out-of-raster-bounds padding is unchanged and is a related but distinct,
  pre-existing edge behavior (out-of-bounds padding uses a literal `0`
  fill regardless of the raster's declared nodata) — explicitly out of
  scope for this CR, noted below.

## Risk assessment
**Risk level: medium.** The logic itself is a direct, narrowly-scoped fix
matching the root cause identified in BUG-0008. Main residual risk:
**accepted** — cannot be validated against a real raster/model in this
environment (no `data/` tree, no trained checkpoint present), so the fix
is verified by code reasoning and a synthetic unit-level check (Test plan
below), not an end-to-end run.

## Test plan
- `python -c "import ast; ast.parse(open('predict.py').read())"` to
  confirm the file still parses.
- Synthetic verification (run in this environment, not requiring real
  raster/checkpoint data): construct a small numpy array standing in for
  `ref_raw` containing a legitimate `0`, a sentinel `-9999`, and a normal
  value; confirm `invalid_mask` is `True` only for the sentinel position
  and `False` for the legitimate-zero and normal positions. Separately
  confirm that when `ref_nodata == 0`, positions equal to `0` in `ref_raw`
  are correctly flagged `True` (the failure mode BUG-0008 (b) describes).
- Cannot validate against a real LandFire raster + trained model checkpoint
  in this environment (neither is present) — flagged as an accepted test
  gap; recommend the project owner spot-check a real prediction run's edge
  coverage after this lands.

## Deliverables
- [ ] Update `read_strip` to return `ref_raw` alongside `cat`, `cont`.
- [ ] Update `predict_region` to build `invalid_mask` from `ref_raw` vs.
      `ref_nodata`/`NODATA_SENTINELS`, replacing the old `== 0`/`!= 0` check.
- [ ] Run the synthetic invalid-mask check described in the test plan.
- [ ] Update `BUG-0008-predict-nodata-zero-conflation.md` corrective action
      and `BUG_LOG.md` status.

## Out of scope
- `_safe_windowed_read`'s `fill_value=0` for out-of-raster-bounds padding
  (a related but distinct edge-padding behavior, not part of BUG-0008's
  two stated failure modes; worth its own bug entry if it's later found to
  cause a real problem).
- BUG-0009 (half-pixel geolocation offset) — already fixed separately as a
  trivial, single-function change (no CR required per `CLAUDE.md`'s
  triviality bar).

## Reviewer verdicts
See independent review below (§ Review).
