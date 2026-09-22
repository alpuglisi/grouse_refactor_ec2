# BUG-0009: `predict.py` output GeoTIFF is geolocated half an output pixel off

## 1. Description
The Affine transform written for `predict.py`'s output heatmap raster sets
its corner coordinate directly to the coordinate of each patch's *center*,
instead of converting from center to corner convention (subtracting half an
output pixel). Every output pixel is systematically shifted.

## 2. Where encountered
`predict.py:300-304`.

## 3. What it caused to fail
Each `heatmap[gy, gx]` value is the prediction for a patch centered at input
pixel `(r_start + gy*stride + IMG_SIZE//2, c_start + gx*stride + IMG_SIZE//2)`.
By GDAL/rasterio Affine convention, the transform's constant term must be
the coordinate of pixel (0,0)'s *corner*, not its center. Using the center
coordinate directly as the corner value shifts the entire exported
suitability raster (and downstream KMZ overlay) by half an output pixel —
e.g. ~60 m north/west for the default `stride=4` at 30 m source resolution,
growing proportionally to `--stride`. This silently misaligns the output
against sightings data, other rasters, or ground-truth checks, with no
error or warning.

## 4. What the defect was
```python
new_trans = rasterio.Affine(
    ref.transform.a * stride, ref.transform.b,
    ref.transform.c + (c_start + IMG_SIZE // 2) * ref.transform.a,
    ref.transform.d, ref.transform.e * stride,
    ref.transform.f + (r_start + IMG_SIZE // 2) * ref.transform.e)
```

## 5. Root cause analysis (Five Whys)
1. Why is the output raster shifted? Because its transform's corner
   coordinate is set to a patch-center coordinate.
2. Why is a center coordinate used as a corner value? Because the code
   computes the pixel index of each patch's center (`r_start + IMG_SIZE//2`)
   and feeds that directly into the Affine constant term without adjusting
   for the corner-vs-center convention difference.
3. Why wasn't the half-pixel adjustment applied? Because Affine's corner
   convention is easy to overlook when the surrounding code is naturally
   thinking in terms of "patch center" (which is what the model actually
   scores).
4. Why wasn't this caught by visual/spatial QA? Because a half-output-pixel
   shift is subtle at low `--stride` values and doesn't produce an obviously
   wrong-looking map — it only becomes visible when compared precisely
   against ground truth or another raster.

**Root cause:** conflating "coordinate of a pixel's corner" (the Affine
transform's required convention) with "coordinate of a pixel's center"
(what the surrounding patch-scoring code naturally computes) when
constructing the output transform.

## 6. Corrective action
None implemented yet — documentation-only pass. Recommended: subtract half
an output pixel in each axis when converting the patch-center coordinate to
the transform's corner term, i.e. `... + (c_start + IMG_SIZE // 2 - 0.5 *
stride) * ref.transform.a` and the equivalent for the row axis. Status:
**OPEN**.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug concerns
Affine transform/corner-vs-center conventions (BUG-0008 is also in
`predict.py` but is a distinct mechanism — nodata/zero value conflation,
not a coordinate-transform bug). Result: **none found**.

## 8. Preventive action
**PA-0007** (see `PREVENTIVE_ACTIONS.md`): when building an output raster's
Affine transform from patch/tile center coordinates, explicitly convert
center to corner convention (subtract half a pixel in each axis) — never
assign a center coordinate directly as the transform's corner constant.
