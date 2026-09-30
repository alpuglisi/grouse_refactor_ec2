# Investigation plan: wrong suitability map around Errol, NH

This is a guide for a Claude Code session run in the project directory on
the training box (`~/grouse2`). Read it all before doing anything.

## 0. Rules for this investigation (from PA-0016, BUG-0022)

A previous session got this wrong three times by asserting causes it had
not checked. Do not repeat that.

1. **Get the symptom from the user first.** Ask what is wrong, where
   (lon/lat or a named place), and what they expected there instead.
   Record the answer word for word in the report (§11). Do not infer the
   defect from the screenshots or from what looks most striking.
2. **No cause is stated until a check that could have failed it has
   passed.** Until then call it an "untested hypothesis".
3. **A rejected hypothesis retires its premise.** Return to the
   step-by-step trace below; don't try a variation of the same idea.
4. **No code, data or retraining changes during the investigation.**
   Report findings; the user decides what to fix.
5. **"No defect found in steps X, Y, Z" is a valid result.** Say exactly
   that. Never present it as a resolution.

### The reported symptom (user, 2026-09-29, verbatim)
> "everything on the maine side of the state border is ranked
> significantly higher than the new hampshire side despite being
> essentially the same habitat"

### Status of the road_dist hypothesis
The user rejected the first answer, which asserted per-state road data
(`road_dist`) as the cause without any check. What they rejected, and on
what basis, is not recorded, so **treat `road_dist` as an untested
hypothesis, neither confirmed nor ruled out.** Settle it with the checks
in steps 3 and 6 before any conclusion. Ask the user whether they have
already inspected `road_dist` values on the Maine side; if so, record
what they saw here.

Code trace (read in code only; no real data examined): of the 15 inputs,
`road_dist` is the only one whose construction depends on which side of
the state line a pixel falls.
- `generate_road_distance.py:113-125` uses TIGER roads for NH counties
  only.
- Every other input for the NH region is a rectangle (LANDFIRE request
  box to −70.60, Earth Engine `region_grid`), or is built over that
  rectangle's grid (`tsd`).
- The model has no location or region input.

**Update:** a fix for the per-state road source was committed (CHANGELOG,
"road_dist: roads from neighbouring states"). The most direct check of
this hypothesis needs no retraining:
1. Copy the current `NH_*_road_dist.tif` files aside.
2. Run `python generate_road_distance.py --regions NH`.
3. Re-run the same `predict.py` command with the **same old checkpoint**.

If the Maine-side jump collapses, `road_dist` was the cause. If it
persists, rule it out and continue below.

If step 6 shows the Maine-side jump survives blanking `road_dist`, the
cause lies outside what the code shows (the data values themselves).
Continue with steps 3–5 comparing inputs on matched Maine/NH points.

### Already checked in code (not against real data)
- Every input except `road_dist` is a rectangle reaching −70.60
  (`download_rev.py:21`, `region_grid` in `download_tcc_nlcd.py` and
  `download_treemap.py`).
- Window centre is pixel index 32 in both `dataset._read_patch` and
  `predict.predict_region`.
- Continuous features are divided by the same `FEATURE_SPEC` scale in
  both readers.
- Nodata is `MISSING_CODE` for categorical features and NaN for
  continuous ones in both readers.
- `predict.load_model` rebuilds the model from the checkpoint config and
  sets eval mode.
- Calibration is applied as scale then bias.
- `generate_kmz` reprojects to EPSG:4326 and takes the overlay's
  `LatLonBox` from the reprojected corners.

These were read in code only; nothing has been run against the real
rasters and checkpoint. Treat them as "not yet confirmed on real data".

## 1. The case
- **Command that made the map:**
  `python predict.py --region NH --model bce.pth --bounds -71.25 44.70 -70.95 44.90 --compile`
  The user may have used different flags; ask.
- **Outputs:** `data/predictions/NH_custom_suitability.tif` and `.kmz`.
- **Checkpoint:** `bce.pth`, trained with
  `--loss an_full --embed-dropout 0.1 --dropout 0.4 --dynamic-dropout
  --dynamic-dropout-step 0.05 --dynamic-dropout-max 0.9 --weight-decay
  1e-3`, with the defaults `--missing-mask --dual-branch dilated`/32.
  15 features, best validation rank about 0.811. It may since have been
  overwritten by later runs; step 1 checks.
- **What the screenshots show** (description only, not the diagnosis):
  - `jet` colormap, `--style absolute`.
  - Mostly yellow/orange west of about 71°01′W; red east of it; cyan and
    blue on wetlands and lake margins.
  - Lakes transparent (scored below `--alpha-below 0.15`).
- **The user's statement of what is wrong:** see §0. Maine-side cells
  score significantly higher than NH-side cells of essentially the same
  habitat.

## 2. Step 0: establish the symptom (required, do this first)
Ask the user:
1. What exactly is wrong: location of high/low areas, overall level,
   texture, orientation, placement, or something else?
2. At least one place where the map is clearly wrong: lon/lat, or a
   landmark you can convert.
3. What they expected there, and how they know (field knowledge, a known
   grouse spot, land cover).
4. Whether they changed anything since training (other runs overwriting
   `bce.pth`, `git pull`, new rasters).

Write the answers down (§11). Pick the steps below that bear on the
symptom, but run steps 1 and 2 regardless; they are cheap.

For this symptom, also ask for matched pairs: one Maine point and one NH
point the user considers the same habitat. Run steps 3 and 6 on those
pairs first.

## 3. Step 1: inventory (what exactly was run)
Save as `inv_inventory.py` and run `python inv_inventory.py`.

```python
import os, json, datetime as dt, torch, rasterio
from grouse_data import GrouseData, grid_mismatch
from models import FEATURE_SPEC
from model_handler import GrouseModelHandler

CKPT, REGION = "bce.pth", "NH"
obj = torch.load(CKPT, map_location="cpu", weights_only=True)
state, cfg = GrouseModelHandler.unwrap_checkpoint(obj)
print("checkpoint mtime:", dt.datetime.fromtimestamp(os.path.getmtime(CKPT)))
print("config:", json.dumps(cfg, indent=1, default=str))
cal = "data/calibration/calibration.json"
if os.path.exists(cal):
    c = json.load(open(cal))
    print("calibration:", {k: c.get(k) for k in ("model_path", "fitted_at",
          "scale", "bias", "temperature", "val_prevalence",
          "ece_cross_fitted")})
rd = GrouseData()[REGION]
feats = cfg["features"]
paths = {f: rd.latest_raster_path(f) for f in feats}
with rasterio.open(paths[feats[0]]) as ref:
    for f in feats:
        with rasterio.open(paths[f]) as s:
            print(f"{f:10s} {os.path.basename(paths[f]):40s} crs={s.crs.to_string()[:25]:25s} "
                  f"nodata={s.nodata} bounds={tuple(round(b) for b in s.bounds)} "
                  f"grid={'OK' if not grid_mismatch(s, ref) else grid_mismatch(s, ref)}")
    print("ref years available per feature:",
          {f: rd.raster_years(f) for f in feats})
```

Check and record:
- Is the checkpoint the run the user thinks it is (its date)?
- Does `calibration.json` belong to this checkpoint (`model_path`, and
  `fitted_at` later than the checkpoint's date)?
- Which **vintage (year)** each feature uses at prediction time. A
  prediction built from mixed years (e.g. 2025 EVT with 2016 TreeMap) is
  a finding.
- Any grid mismatch against the reference raster.

## 4. Step 2: what the output actually contains
```python
import numpy as np, rasterio
with rasterio.open("data/predictions/NH_custom_suitability.tif") as s:
    a = s.read(1); print(s.crs, s.transform, s.shape)
v = a[np.isfinite(a)]
print("valid", v.size, "/", a.size, "| min/median/max", v.min(), np.median(v), v.max())
print("fraction >=0.5:", (v >= .5).mean(), " >=0.8:", (v >= .8).mean())
print("histogram:", np.histogram(v, bins=10, range=(0, 1))[0])
```
Then rerun `predict.py` with the same flags plus `--no-calibration
--tif-only` into a copy, and compare. This separates the model's raw
output from the calibration.

## 5. Step 3: raw inputs at the user's spots (the ground-truth check)
For every location the user named in step 0, plus two control points they
consider correct:
```bash
python inspect_point.py --region NH --lon <lon> --lat <lat> --model bce.pth
```
Compare each printed value (land-cover class names, canopy height and
cover, road distance in metres, years since disturbance, TreeMap stems
per acre) against what is really there. Use the user's knowledge or
recent imagery. Look for:
- `NODATA`;
- values that contradict the ground (a clearcut read as mature forest, a
  lake read as forest);
- stale vintages.

## 6. Step 4: every input as a map over the same box
This dumps each model input over the exact prediction box, so each layer
can be checked for alignment, gaps, seams and vintage artifacts. Save as
`inv_feature_maps.py`.

```python
import os, numpy as np, rasterio, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rasterio.windows import Window
from grouse_data import GrouseData, MISSING_CODE
from models import split_features
import predict, torch

BOUNDS, OUT = (-71.25, 44.70, -70.95, 44.90), "inv_feature_maps"
os.makedirs(OUT, exist_ok=True)
rd = GrouseData()["NH"]
model, cat_f, cont_f, feats, cfg = predict.load_model(
    "bce.pth", [f for f in rd.available_features()], torch.device("cpu"))
srcs, ref = predict.open_aligned_sources(rd, cat_f, cont_f)
r0, r1, c0, c1 = predict.bounds_to_window(ref, BOUNDS, pad=0)
cat, cont = predict.read_window_stack(srcs, cat_f, cont_f,
                                      Window(c0, r0, c1 - c0, r1 - r0))
for i, f in enumerate(cat_f + cont_f):
    arr = (cat[i].astype(float) if i < len(cat_f) else cont[i - len(cat_f)])
    miss = (cat[i] == MISSING_CODE) if i < len(cat_f) else np.isnan(arr)
    arr = np.where(miss, np.nan, arr)
    print(f"{f:10s} missing {miss.mean():6.1%}  unique/min/max "
          f"{len(np.unique(arr[~miss])) if (~miss).any() else 0} "
          f"{np.nanmin(arr) if (~miss).any() else 'NA'} {np.nanmax(arr) if (~miss).any() else 'NA'}")
    plt.figure(figsize=(8, 6)); plt.imshow(arr, cmap="tab20" if i < len(cat_f) else "viridis",
                                           interpolation="nearest")
    plt.title(f); plt.colorbar(); plt.savefig(f"{OUT}/{f}.png", dpi=110); plt.close()
    with rasterio.open(f"{OUT}/{f}.tif", "w", driver="GTiff", height=arr.shape[0],
                       width=arr.shape[1], count=1, dtype="float32", crs=ref.crs,
                       transform=ref.window_transform(Window(c0, r0, c1 - c0, r1 - r0)),
                       nodata=np.nan) as d:
        d.write(arr.astype("float32"), 1)
for s in srcs.values(): s.close()
```
Open the `.tif` files in Google Earth or QGIS over imagery. Check each
layer for:
- **Misregistration:** is `evt` water where the lakes are?
- **Artifacts:** straight seams, tiles, stripes.
- **Wrong or stale content.**
- **The user's symptom showing up in a single layer.**

## 7. Step 5: train/predict parity (catches pipeline bugs)
The same location should produce the same input tensor, and the same
score, through the training reader and the prediction reader. Save as
`inv_parity.py`.

```python
import numpy as np, torch, rasterio
from pyproj import Transformer
from rasterio.windows import Window
from grouse_data import GrouseData, MISSING_CODE
from dataset import GrousePatchDataset
from models import d4_tta_logits
import predict

rd = GrouseData()["NH"]
model, cat_f, cont_f, feats, cfg = predict.load_model(
    "bce.pth", list(rd.available_features()), torch.device("cpu"))
pts = rd.positives("val").head(20).copy()
ds = GrousePatchDataset(pts, rd, cat_f, cont_f, img_size=64, label=1.0)
worst = 0
for i in range(len(pts)):
    c_ds, x_ds, _, _ = ds[i]
    lon, lat, yr = pts.longitude.iloc[i], pts.latitude.iloc[i], int(ds._year[i])
    # prediction reader on the SAME year's rasters (isolates reader
    # differences from vintage differences)
    srcs = {f: rasterio.open(rd.raster_path(f, yr)) for f in cat_f + cont_f}
    ref = srcs[(cat_f + cont_f)[0]]
    x, y = Transformer.from_crs("EPSG:4326", ref.crs, always_xy=True).transform(lon, lat)
    r, c = ref.index(x, y)
    cat, cont = predict.read_window_stack(srcs, cat_f, cont_f, Window(c - 32, r - 32, 64, 64))
    for s in srcs.values(): s.close()
    same_cat = np.array_equal(c_ds.numpy(), cat)
    same_cont = np.allclose(x_ds.numpy(), cont, equal_nan=True)
    with torch.no_grad():
        a = d4_tta_logits(model, c_ds[None], x_ds[None]).item()
        b = d4_tta_logits(model, torch.from_numpy(cat)[None], torch.from_numpy(cont)[None]).item()
    worst = max(worst, abs(a - b))
    print(f"pt{i} yr{yr} cat_equal={same_cat} cont_equal={same_cont} "
          f"logit_train={a:+.4f} logit_predict={b:+.4f}")
print("max |logit diff|:", worst)
```
- **Expected:** identical tensors and logits equal to about 1e-5.
- If they differ, find the first differing channel and pixel. Common
  culprits: an off-by-one centre, channel order, scale, the rotation or
  flip direction, a nodata value one reader treats differently, or
  resampling in `WarpedVRT`.
- Then repeat with the prediction reader on **`latest_raster_path`**
  (what `predict.py` really uses) to measure how much the vintage alone
  moves the score.

## 8. Step 6: which inputs drive the pattern the user flagged
Ablation: score a coarse grid over the box, then again with each feature
blanked (set to missing over the whole window), and map the change.
Save as `inv_ablation.py`.

```python
import numpy as np, torch
from rasterio.windows import Window
from grouse_data import GrouseData, MISSING_CODE
from models import d4_tta_logits
import predict

BOUNDS, STEP = (-71.25, 44.70, -70.95, 44.90), 24          # 24 px = 720 m grid
rd = GrouseData()["NH"]
model, cat_f, cont_f, feats, cfg = predict.load_model(
    "bce.pth", list(rd.available_features()), torch.device("cpu"))
srcs, ref = predict.open_aligned_sources(rd, cat_f, cont_f)
r0, r1, c0, c1 = predict.bounds_to_window(ref, BOUNDS, pad=0)
coords = [(r, c) for r in range(r0, r1 - 64, STEP) for c in range(c0, c1 - 64, STEP)]
cats, conts = zip(*[predict.read_window_stack(srcs, cat_f, cont_f, Window(c, r, 64, 64))
                    for r, c in coords])
cat, cont = torch.from_numpy(np.stack(cats)), torch.from_numpy(np.stack(conts))
def score(cx, nx):
    with torch.no_grad():
        return torch.cat([d4_tta_logits(model, cx[i:i+64], nx[i:i+64])
                          for i in range(0, len(cx), 64)]).numpy()
base = score(cat, cont)
H, W = len(range(r0, r1 - 64, STEP)), len(range(c0, c1 - 64, STEP))
np.save("inv_ablation_base.npy", base.reshape(H, W))
for i, f in enumerate(cat_f + cont_f):
    cx, nx = cat.clone(), cont.clone()
    if i < len(cat_f): cx[:, i] = MISSING_CODE
    else: nx[:, i - len(cat_f)] = float("nan")
    d = (score(cx, nx) - base).reshape(H, W)
    np.save(f"inv_ablation_{f}.npy", d)
    print(f"{f:10s} mean dlogit {d.mean():+.3f}  mean|d| {np.abs(d).mean():.3f}  "
          f"spatial std {d.std():.3f}")
for s in srcs.values(): s.close()
```
- **Runtime:** about 900 windows × 8 views × 16 passes. Minutes on
  a GPU, roughly 15–30 minutes on CPU; raise `STEP` to 48 for a quicker
  first pass.
- **Read it against the user's symptom:** which feature, when removed,
  makes the flagged pattern go away? Plot `inv_ablation_<f>.npy` next to
  `inv_ablation_base.npy`.
- **Caveat:** for `missing_mask` models, "missing" is an input the model
  saw only at raster edges, so a large change can partly be
  out-of-distribution behaviour. Confirm a suspected driver with step 3
  (raw values) before stating it.

## 9. Step 7: known sightings versus the map
Plot the training and validation points inside the box against the map.
Do the known grouse locations score high and the background points low?

```python
import pandas as pd, simplekml
from grouse_data import GrouseData
rd = GrouseData()["NH"]; W, S, E, N = -71.25, 44.70, -70.95, 44.90
k = simplekml.Kml()
for name, df, col in (("pos", rd.positives("all"), "ff00ff00"),
                      ("neg", rd.negatives("all"), "ff0000ff")):
    df = df[(df.longitude.between(W, E)) & (df.latitude.between(S, N))]
    print(name, len(df))
    for _, r in df.iterrows():
        p = k.newpoint(name=name, coords=[(r.longitude, r.latitude)])
        p.style.iconstyle.color = col
k.save("inv_points.kml")
```
(`pip install simplekml` if needed.) Open `inv_points.kml` with the map
in Google Earth. Also sample the prediction GeoTIFF at these points and
compute AUC inside the box. A map whose in-box AUC is far below the
validation AUC (about 0.82) confirms a real local failure, and gives a
number to measure any fix against.

## 10. Step 8: cross-region train/val leakage count (BUG-0027)

Independent of the map symptom. Run it regardless, because it decides
whether any validation number in this project can be trusted. BUG-0027 (on
branch `claude/quality-policy-bug-review-hiptpa`) found in code that:
- records are assigned to regions by **overlapping bounding boxes**
  (most of the NH box lies inside the VT or ME box), so one sighting can
  be in two regions' datasets;
- each region makes its **own** block grid and random train/val draw;
- `train.py` pools all regions without de-duplicating.

So a record can be training data for one region and validation data for
another. That is **unconfirmed on real data**; this step measures it. Save
as `inv_leakage.py`.

```python
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData

REGIONS, BLOCK_M, NEAR_M = ["ME", "NH", "VT"], 3000, (30, 300, 3000)
data = GrouseData()
rows = []
for reg in REGIONS:
    rd = data[reg]
    for kind, get in (("pos", rd.positives), ("neg", rd.negatives)):
        for split in ("train", "val"):
            df = get(split)[["longitude", "latitude"]].copy()
            df["region"], df["kind"], df["split"] = reg, kind, split
            rows.append(df)
allr = pd.concat(rows, ignore_index=True)
x, y = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True).transform(
    allr.longitude.values, allr.latitude.values)
allr["x"], allr["y"] = x, y
allr["key"] = allr.longitude.round(5).astype(str) + "," + allr.latitude.round(5).astype(str)
print(allr.groupby(["region", "kind", "split"]).size().unstack(), "\n")

# 1. The same coordinate in more than one region
multi = allr.groupby(["kind", "key"]).region.nunique()
for kind in ("pos", "neg"):
    m = multi.loc[kind]
    print(f"{kind}: {int((m > 1).sum()):,} coordinates appear in >1 region "
          f"({(m > 1).mean():.1%} of {len(m):,} unique)")

# 2. The same coordinate as TRAIN in one region and VAL in another
for kind in ("pos", "neg"):
    k = allr[allr.kind == kind]
    tr = set(k[k.split == "train"].key); va = set(k[k.split == "val"].key)
    both = tr & va
    print(f"{kind}: {len(both):,} coordinates are TRAIN and VAL at once "
          f"({len(both) / max(len(va), 1):.1%} of val coordinates)")

# 3. Pooled proximity: val points with a pooled TRAIN point within d
#    metres. Compare with the within-region-only rate - the difference is
#    what cross-region pooling adds.
for kind in ("pos", "neg"):
    k = allr[allr.kind == kind]
    tr, va = k[k.split == "train"], k[k.split == "val"]
    d_pool, _ = cKDTree(tr[["x", "y"]].values).query(va[["x", "y"]].values, k=1)
    d_own = np.full(len(va), np.inf)
    for reg in REGIONS:
        t, v = tr[tr.region == reg], va.region.values == reg
        if len(t) and v.any():
            d_own[v], _ = cKDTree(t[["x", "y"]].values).query(va[v][["x", "y"]].values, k=1)
    for d in NEAR_M:
        print(f"{kind}: val with a TRAIN point within {d:>4} m - pooled "
              f"{(d_pool <= d).mean():6.1%} | same-region only {(d_own <= d).mean():6.1%}")
```

How to read it:
- **Sections 1–2 (exact duplicates):** anything above zero in "TRAIN and
  VAL at once" confirms BUG-0027. Those validation points were trained
  on directly.
- **Section 3 (proximity):**
  - The **same-region-only** rate is what the block holdout was designed
    to keep low (only points near block edges).
  - The **pooled** rate is what training actually sees.
  - A large gap, above all at 30 m and 300 m, is cross-region leakage.
    The bigger it is, the more the reported validation AUC/AP (about
    0.82 / 0.79) overstate real performance.
- **Record every table verbatim in the report.** The BUG-0027 fix changes
  every split, and these numbers are its "before".
- **Do not fix anything here.** BUG-0027 needs a change request, per the
  rules in §0.

## 11. Reporting (hand this back to the user)
Write `INVESTIGATION_REPORT_errol_map.md` with:
1. **Symptom:** the user's words, verbatim, and their locations.
2. **What each step found:** actual numbers and file names; for each step
   either "ruled out because …" or "confirmed because …". Steps not run,
   with the reason.
3. **Conclusion:** the confirmed cause with the check that confirmed it,
   *or* "not identified; stages checked: …".
4. **Leakage count (step 8):** its tables, and whether BUG-0027 is
   confirmed.
5. **Proposed fix:** only for a confirmed cause, with how to verify it
   (the step-7 in-box AUC and the step-3 points before and after). Do
   not implement it without the user's go-ahead.
6. **Quality records:** if a code defect is confirmed, it needs a
   BUG-XXXX doc on the `claude/quality-policy-bug-review-hiptpa` branch,
   following that branch's `CLAUDE.md` (a change request for anything
   non-trivial). BUG-0022 there is the record for this investigation.
