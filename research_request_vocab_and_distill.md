# Information request: LANDFIRE categorical code ranges and distillation teacher checkpoints

## Who you are and what this is for

You are a Claude chat agent helping the owner of a ruffed grouse habitat
suitability CNN. A separate Claude Code session reviewed the codebase and
found two issues it cannot fully resolve without information that only
exists outside the repository (on the public LANDFIRE website, and on the
training machine where the data lives). Your job is to collect that
information and hand it back in the format given in **Part D** so the
Code session can implement the fixes.

You do NOT need to fix anything. You do NOT need to read the codebase.
Everything you need to know about the code is summarised here.

Two of the tasks need commands run on the training machine. You cannot
run those yourself; give the exact commands to the user, ask them to
paste the output back to you, and then interpret it.

---

## Background: the two issues

### Issue 1: categorical vocabulary clamp

The model turns each categorical raster code into an embedding vector.
Before the lookup, every code is clamped into `[0, vocab - 1]`. The
vocabulary sizes are hardcoded:

| feature | LANDFIRE product | vocab | so codes above ... collapse |
|---|---|---|---|
| evt    | EVT    | 10000 | 9999 |
| evh    | EVH    | 300   | 299  |
| evc    | EVC    | 300   | 299  |
| sclass | SClass | 300   | 299  |
| fdist  | FDist  | 10000 | 9999 |
| nlcd   | Annual NLCD (not LANDFIRE) | 256 | 255 |

The suspected problem: since the LANDFIRE 2016 Remap, EVC and EVH encode
cover and height in three blocks by life form (tree 1xx, shrub 2xx,
herbaceous 3xx). If that is true for the vintages this project uses,
every herbaceous code (301 and up) is being clamped to 299, which is a
real shrub code, so herb cover percent and herb height are silently
destroyed. Fixing it means raising the vocab, which requires retraining
from scratch, so the owner wants the code ranges confirmed first, from
the official tables AND from the actual rasters on disk.

The vintages this project downloads are **LF2022, LF2023, LF2024 and
LF2025** (the LF2020 layers were retired from the LANDFIRE product
service and are not on disk). Products are fetched from the LANDFIRE
Product Service as `EVT`, `EVH`, `EVC`, `SClass`, `FDist`, `CH`, `CC`.
LF2025 SClass is not published.

### Issue 2: distillation teachers built with the wrong feature list

`train.py --distill-from <ckpt...>` loads already-trained "teacher"
checkpoints and uses their averaged predictions as soft targets for one
new "student" model. Each wrapped checkpoint stores its own feature list
under `config["features"]`, and that list is what the weights actually
encode (embedding tables, stem width). The distill loader ignores it and
builds each teacher from the features found on disk for the current run
instead. If the two lists differ, either the load fails with a raw
tensor-shape traceback, or, when the channel counts happen to match, the
teacher silently scores garbage.

The fix is a code change the Code session can make on its own, but it
needs to know what the real checkpoints look like and how the owner
intends to use the flag, so it can choose between "refuse loudly on
mismatch" (simple) and "support teachers with different feature sets"
(much larger change).

---

## Part A: LANDFIRE code ranges from the official attribute tables (web)

LANDFIRE publishes one CSV attribute table per product per vintage.
Observed URL patterns (try each; the folder is sometimes `LF2024` and
sometimes `2024`):

```
https://landfire.gov/sites/default/files/CSV/LF{year}/LF{year}_{product}.csv
https://landfire.gov/sites/default/files/CSV/{year}/LF{year}_{product}.csv
https://www.landfire.gov/sites/default/files/CSV/LF{year}/LF{year}_{product}.csv
https://www.landfire.gov/sites/default/files/CSV/{year}/LF{year}_{product}.csv
```

with `{year}` in `2022, 2023, 2024, 2025` and `{product}` in
`EVC, EVH, SClass, EVT, FDist`. If a URL pattern fails, find the table
through the product's page on landfire.gov (Data > Data Products >
Vegetation / Fuel / Disturbance) and record the URL you actually used.

For **each product and each vintage** that exists, report:

1. The column that holds the raster code (usually `VALUE`).
2. The minimum and maximum `VALUE`.
3. The number of rows.
4. Every distinct "block" of codes and its meaning. For EVC and EVH this
   means: which VALUE range is tree, which is shrub, which is
   herbaceous, and what the codes below 100 are (water, developed,
   barren, snow, NoData and so on). Quote the label text for the first
   and last code in each block.
5. **Specifically for EVC and EVH: list every VALUE greater than or
   equal to 300 with its label.** This is the single most important
   output of Part A. If there are none, say so explicitly.
6. For EVC and EVH: the label attached to VALUE 299 exactly, if that
   row exists.
7. For SClass: the complete list of VALUEs and labels (it is short).
8. For EVT and FDist: only the minimum and maximum VALUE and the row
   count, plus any VALUE at or above 9000.
9. Any row representing NoData, "Fill", or "no value" and its VALUE.

Also answer, with a citation to a LANDFIRE document or page:

- In what LANDFIRE release did EVC switch from 10-percent cover bins to
  1-percent codes, and did EVH change its encoding at the same time?
- Are the EVC and EVH code spaces identical across LF2022, LF2023,
  LF2024 and LF2025, or did any vintage add or remove codes?

## Part B: what is actually in the rasters on the training machine

Give the user the following script to run from the project directory on
the training machine (the one with `data/landfire/*.tif`). It prints,
for every categorical raster, the maximum code, the pixel count at or
above 300, and the distinct codes at or above 300 with counts. It reads
at reduced resolution so it finishes quickly; ask the user to rerun it
with `FULL=1` if any raster shows codes at or above 300, so the counts
are exact.

```python
# save as scan_codes.py in the project directory and run: python scan_codes.py
import glob, os, sys
import numpy as np
import rasterio

FULL = os.environ.get("FULL") == "1"
FEATURES = ["evc", "evh", "sclass", "evt", "fdist", "nlcd"]
paths = sorted(glob.glob("data/landfire/*_*_*.tif"))
for feat in FEATURES:
    print(f"\n=== {feat} ===")
    for p in paths:
        if not p.endswith(f"_{feat}.tif"):
            continue
        with rasterio.open(p) as src:
            if FULL:
                a = src.read(1)
            else:
                a = src.read(1, out_shape=(1, max(1, src.height // 8),
                                           max(1, src.width // 8)))[0]
            nd = src.nodata
            valid = a[(a != nd) if nd is not None else np.ones(a.shape, bool)]
            valid = valid[valid > -1000]
            hi = valid[valid >= 300]
            codes, counts = np.unique(hi, return_counts=True)
            print(f"{os.path.basename(p):28s} nodata={nd} "
                  f"min={valid.min() if valid.size else None} "
                  f"max={valid.max() if valid.size else None} "
                  f"pixels>=300: {hi.size}/{valid.size} "
                  f"({100.0 * hi.size / max(valid.size, 1):.2f}%)"
                  f"{'  (decimated 8x)' if not FULL else ''}")
            if codes.size:
                print("    codes>=300:", ", ".join(
                    f"{int(c)}x{int(n)}" for c, n in zip(codes, counts)))
```

Also ask the user to run this, which prints the maximum code in the
attribute tables the project has already downloaded (they may or may not
be present):

```bash
for f in data/landfire/attribute_tables/LF*_EV[CH].csv data/landfire/attribute_tables/LF*_SClass.csv; do
  [ -f "$f" ] || continue
  echo "== $f"
  python -c "
import pandas as pd, sys
t = pd.read_csv(sys.argv[1]); t.columns = [c.upper().strip() for c in t.columns]
v = t['VALUE'].astype(int)
print('rows', len(t), 'min', v.min(), 'max', v.max())
hi = t[v >= 300]
print(hi.iloc[:, :3].to_string(index=False) if len(hi) else 'no VALUE >= 300')
" "$f"
done
```

Report the pasted output verbatim in Part D, then summarise it.

## Part C: the distillation checkpoints and the intended workflow

Give the user this script to run in the project directory. It opens
every checkpoint it can find and prints the stored feature list and
geometry, plus the stem width implied by the weights. No GPU needed.

```python
# save as scan_ckpts.py in the project directory and run: python scan_ckpts.py [extra paths...]
import glob, sys
import torch

paths = sorted(set(glob.glob("*.pth") + glob.glob("*.pth.member*")
                   + glob.glob("data/models/*.pth*") + sys.argv[1:]))
for p in paths:
    try:
        obj = torch.load(p, map_location="cpu", weights_only=True)
    except Exception as e:
        print(f"{p}: could not load ({type(e).__name__}: {e})")
        continue
    if isinstance(obj, dict) and "state_dict" in obj:
        sd, cfg = obj["state_dict"], obj.get("config") or {}
        kind = "wrapped"
    else:
        sd, cfg, kind = obj, {}, "BARE (no config)"
    conv1 = sd.get("conv1.weight")
    stem = conv1.shape[1] if conv1 is not None else "?"
    emb = sorted(k[len("embeddings."):-len(".weight")] for k in sd
                 if k.startswith("embeddings.") and k.endswith(".weight"))
    print(f"\n{p} [{kind}] stem_in_channels={stem}")
    print("  features:", cfg.get("features"))
    print("  embeddings present:", emb)
    for k in ("pool", "center_skip", "keep_early_resolution", "early_attn",
              "early_attn_pos_mode", "dual_branch", "dual_branch_channels",
              "loss", "an_pos_weight", "focal_alpha"):
        if k in cfg:
            print(f"  {k}: {cfg[k]}")
```

And this, which prints the feature set train.py would discover on disk
right now for the default regions:

```bash
python -c "
from grouse_data import GrouseData
from train import discover_features
print(discover_features(GrouseData(), ['ME','NH','VT']))
"
```

Then ask the user these questions and record the answers:

1. Which checkpoint files are the intended teachers for `--distill-from`?
2. What is the exact `train.py` command they plan to run for
   distillation (all flags)?
3. Were the teachers trained on the same feature set that is on disk
   now? If not, which features differ?
4. Do they ever expect to distill from teachers that were trained on a
   different feature set than the student, or is "same features, refuse
   otherwise" acceptable? (The reviewer recommends refusing: supporting
   mixed feature sets needs one dataset per distinct teacher feature
   list and is a much larger change.)
5. For the vocab fix: do they accept that raising the EVC and EVH
   vocabulary is a cold start (existing checkpoints stop loading, and
   `--resume` and `--init-from` become invalid against them)? Do they
   want the new vocab sized at 400 (covers every documented code) or
   larger for headroom?

## Part D: what to hand back

Return one markdown document with these sections, in this order. Keep
raw outputs verbatim in fenced code blocks and put your interpretation
after each one.

```
# Findings

## A. Official LANDFIRE code ranges
### EVC
| vintage | URL used | rows | min | max | tree block | shrub block | herb block | codes >= 300 present? |
(one row per vintage)
- Full list of VALUE >= 300 with labels, per vintage (or "none")
- Label at VALUE 299, per vintage
### EVH
(same table and lists)
### SClass
- Complete VALUE/label list per vintage
### EVT and FDist
| product | vintage | rows | min | max | any VALUE >= 9000? |
### NoData / fill rows found in any table
### When did EVC/EVH move to 1-percent codes (with citation)
### Are the code spaces identical across LF2022-LF2025 (with citation)

## B. Rasters on the training machine
- Verbatim output of scan_codes.py (note whether decimated or FULL)
- Verbatim output of the attribute-table loop (or "tables not on disk")
- Summary: for evc and evh, the maximum code present and the percent
  of pixels at or above 300, per region and vintage

## C. Distillation
- Verbatim output of scan_ckpts.py
- Verbatim output of the discover_features one-liner
- Answers to questions 1 through 5

## D. Anything unexpected
Anything that did not match the description above (a product with a
different code layout, a checkpoint with no config, a script that
errored) belongs here, verbatim.
```

If any part could not be completed, say which part and why rather than
leaving it out. Do not guess at raster contents or checkpoint contents:
only report what the scripts printed.
