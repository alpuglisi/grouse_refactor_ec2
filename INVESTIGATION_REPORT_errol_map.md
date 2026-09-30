# Investigation report: wrong suitability map around Errol, NH

Run 2026-09-30 on the training box (`~/grouse2`, branch `main`, HEAD
`1fa3bde`), following `INVESTIGATION_PLAN_errol_map.md` §11 and PA-0016.

No project code, raster, checkpoint or training-data file was modified.
The one allowed data change (regenerating NH `road_dist`) was made with
the pre-change files copied to `old_road_dist/` first; the regenerated
files are in `new_road_dist/` and are what `data/landfire/` now holds.
`bce.pth` is byte-identical to its state at the start
(`inv_bce_md5_before.txt`, verified after every run).

---

## 1. Symptom

The user's words, verbatim (2026-09-29):

> "everything on the maine side of the state border is ranked
> significantly higher than the new hampshire side despite being
> essentially the same habitat"

Reported command:

```
python predict.py --region NH --model bce.pth --bounds -71.25 44.70 -70.95 44.90
```

Location: the box `-71.25 44.70 -70.95 44.90` around Errol, NH. The
ME/NH line crosses it near 71°01′W; Maine is the eastern (right) part.

**Symptom reproduced and quantified.** Over the 51,714 scored cells
(17,320 on the Maine side, 34,394 on the New Hampshire side; state sides
from TIGER county polygons, `data/roads/tl_2023_us_county.zip`):

| map | ME mean | NH mean | ME−NH mean | P(ME pixel > NH pixel) |
|---|---|---|---|---|
| the user's own output file | 0.7949 | 0.6289 | +0.1660 | **0.8513** |
| my reproduction, `bce.pth` | 0.6887 | 0.4228 | +0.2659 | **0.8235** |

`P(ME pixel > NH pixel)` is the Mann–Whitney rank statistic: 0.5 means
"no difference". 0.85 means a randomly chosen Maine cell outscores a
randomly chosen NH cell 85 % of the time. The user's description is
correct and large.

Script: `inv_state_split.py`. Output: `inv_state_split_before.out`.

### 1a. The reported map was NOT made with `bce.pth`

Step 1's question "is the checkpoint the run the user thinks it is?"
answered no. `data/predictions/NH_custom_suitability.tif` (the user's
file, saved 2026-09-29 14:51, preserved as
`inv_before/USER_ORIGINAL_NH_custom_suitability.tif`) is **pixel-exact
identical** to a re-run with `--model gap3.pth`:

```
candidate                           spearman  max|diff|   median
inv_probe_old/bce_cal.tif           0.914368    0.53724   0.4880
inv_probe_old/bce_compile.tif       0.914368    0.53724   0.4880
inv_probe_old/bce_nocal.tif         0.914368    0.44596   0.7292
inv_probe_old/bce_noflip.tif        0.913992    0.54560   0.4879
inv_probe_old/ed_cal.tif            0.902055    0.63580   0.4917
inv_probe_old/gap3_cal.tif          1.000000    0.00000   0.7092
inv_probe_old/single_best.tif       0.095143    0.97796   0.0034
```

`np.array_equal` → `True`, 0 differing pixels. Every candidate was run
with the *pre-fix* `road_dist` rasters swapped back in, so the
comparison is like-for-like.

This changes nothing about the diagnosis — the symptom is present with
both `gap3.pth` (P = 0.8513) and `bce.pth` (P = 0.8235), and the cause
below is confirmed separately for each — but it is a finding in its own
right: see §7, **BUG-0028 (draft)**.

---

## 2. What each step found

### Step 8 — cross-region train/val leakage (BUG-0027). **CONFIRMED.**
Run first, independent of the map. Full tables in §4 below.

### Step 1 — inventory. Two findings, neither a cause of the symptom.
Script `inv_inventory.py`, output `inv_inventory_before.out`.

- **Checkpoint:** `bce.pth` mtime `2026-09-29 13:55:53`. Config as the
  plan describes (15 features, `pool=attn`, `center_skip=True`,
  `dual_branch=dilated/32`, `missing_mask=true`, `loss=an_full`). Not
  overwritten. But it is not the checkpoint that made the map (§1a).
- **Calibration does not belong to the checkpoint named in the command.**
  `data/calibration/calibration.json` records
  `model_path: /home/ec2-user/grouse2/gap3.pth`, `fitted_at
  2026-09-29T14:44:10`, `scale 1.4555`, `bias -1.4895`. `predict.py`
  detects and warns about this: *"calibration was fitted on …/gap3.pth,
  but you're predicting with …/bce.pth"*. **Not a defect, and not a
  cause:** calibration is a single monotone scale-then-bias applied to
  every cell, so it cannot produce a spatial ME/NH difference. It is
  also, as it happens, the *correct* calibration for the map the user
  actually produced.
- **Mixed vintages at prediction time:** `evt/evh/evc/sclass/fdist/ch/cc`
  2024, `tcc` 2023, `nlcd/road_dist/tsd/balive/tpa_live/qmd/carbon_dwn`
  2025. Recorded as the plan asks. Uniform across the box, so not a
  cause of an ME/NH split.
- `NH_2025_evc.tif` and `NH_2025_fdist.tif` exist on disk but are
  **100 % nodata** (`valid_frac=0.0000`). `latest_raster_path`'s content
  check correctly rejects them and falls back to 2024. Working as
  designed; noted so nobody mistakes the 2024 vintage for a bug.
- **Grid:** every feature `grid=OK` against the reference raster. No
  misalignment.

### Step 2 — what the output contains. No defect.
```
before, calibrated : n=51714 min=0.0015 median=0.4880 mean=0.5119 max=0.9912  47.29% >=0.5  15.37% >=0.8
before, raw logits : n=51714 min=0.0308 median=0.7292 mean=0.7139 max=0.9861  92.70% >=0.5  26.22% >=0.8
```
100 % of cells scored, none masked. The ME/NH split has
`P(ME>NH) = 0.8235` **identically with and without calibration**, which
rules calibration out as the cause by a check that could have shown
otherwise.

### Step 5 — train/predict reader parity. **Ruled out.**
Script `inv_parity.py`, output `inv_parity.out`. 20 NH validation
positives, training reader (`GrousePatchDataset`) vs prediction reader
(`predict.read_window_stack`) on the same year's rasters:

```
no channel differences
max |logit diff| train vs predict (same year): 0.00e+00
max |logit diff| same-year vs latest vintage : 1.0043
```

Identical tensors, bit-identical logits. No off-by-one centre, channel
order, scale, nodata or resampling defect. (The 1.0043 figure is the
separate, expected effect of predicting on the *latest* vintage instead
of the sighting year's — not a defect, but a magnitude worth knowing.)

### Step 4 — every input as a map over the box. No second per-state layer.
Script `inv_feature_maps.py`, output `inv_feature_maps.out`, rasters and
PNGs in `inv_feature_maps/`. Per-feature statistics split by state side
(post-fix rasters):

```
feature       miss%  miss%ME  miss%NH  nuniq       min        max      medME      medNH      ME-NH
evt           0.00%    0.00%    0.00%     57   7238.00    9817.00    7373.00    7302.00      71.00
evh           0.00%    0.00%    0.00%     68     11.00     310.00     114.00     115.00      -1.00
evc           0.00%    0.00%    0.00%    208     11.00     385.00     166.00     168.00      -2.00
sclass        0.00%    0.00%    0.00%     11      1.00     180.00       3.00       5.00      -2.00
fdist         0.00%    0.00%    0.00%     13      0.00     633.00       0.00       0.00       0.00
nlcd          0.00%    0.00%    0.00%     14     11.00      95.00      42.00      42.00       0.00
ch            0.00%    0.00%    0.00%      8      0.00     270.00     150.00     150.00       0.00
cc            0.00%    0.00%    0.00%     10      0.00      95.00      65.00      65.00       0.00
tcc           0.00%    0.00%    0.00%     97      0.00      96.00      82.00      84.00      -2.00
road_dist     0.00%    0.00%    0.00%   1040      0.00    7756.00    6236.00    5896.00     340.00
tsd           0.00%    0.00%    0.00%     27    693.00    3434.00    3434.00    3434.00       0.00
balive        0.00%    0.00%    0.00%    657      0.00    2812.00     812.00     837.00     -25.00
tpa_live      0.00%    0.00%    0.00%    606      0.00    9017.00    6786.00    6705.00      81.00
qmd           0.00%    0.00%    0.00%    436      0.00    1340.00     369.00     382.00     -13.00
carbon_dwn    0.00%    0.00%    0.00%    483      0.00    1997.00     321.00     365.00     -44.00
```

(The `road_dist` row is in **encoded** units × `FEATURE_SPEC` scale, not
metres; metres are in §3.) **Zero missing data anywhere in the box, on
either side.** No layer ends at, or steps at, the state line. This
confirms on real data what BUG-0022 §6 had only read in code: every
input except `road_dist` is a rectangle that covers the whole box.

**`tsd` observation (BUG-0024, not a contributor here):** 76.67 % of the
box sits at the encoded maximum 3434 = exactly `TSD_MAX_YEARS` = 30
years ("undisturbed for ≥30 years") over what is heavily-cut industrial
forest. That is consistent with BUG-0024's mechanism. It is **ruled out
as a cause of this symptom** because `medME = medNH = 3434` — it is
saturated identically on both sides — and because the ablation
(step 6) gives `tsd` a ME−NH effect of −0.001 logits.

### Step 3 — raw inputs at matched Maine/NH points. **CONFIRMS road_dist.**
The user offered matched pairs; they were not needed, because pairs can
be selected objectively. `inv_matched_pairs.py` picks cells that are the
**same habitat by the model's own inputs** — identical `evt`, `evh`,
`evc`, `sclass`, `nlcd`, and `|Δch| ≤ 2 m`, `|Δcc| ≤ 5 %`,
`|Δtcc| ≤ 5 %` — one on each side of the line. From 143,991 ME and
355,233 NH candidate cells, 8 pairs (`inv_matched_pairs.csv`):

```
 pair side       lon      lat  evt  evh  evc  sclass  nlcd    ch   cc  tcc  road_dist_m_OLD  road_dist_m_NEW  prob_OLD  prob_NEW
    0   ME -70.97698 44.86778 7373  113  187       2    42 110.0 85.0 75.0           5535.0             42.0    0.5360    0.2878
    0   NH -71.06526 44.88739 7373  113  187       2    42 110.0 85.0 80.0            591.0            591.0    0.4069    0.4069
    1   ME -71.01492 44.76001 7555  116  162       3    43 150.0 65.0 84.0           3462.0            685.0    0.9471    0.6257
    1   NH -71.10228 44.86786 7555  116  162       3    43 150.0 65.0 89.0            870.0            870.0    0.4216    0.4216
    2   ME -70.97115 44.74223 7373  117  179       2    90 190.0 75.0 83.0           6939.0            532.0    0.8970    0.5312
    2   NH -71.06032 44.84850 7373  117  179       2    90 190.0 75.0 86.0             42.0             42.0    0.3650    0.3632
    3   ME -71.03334 44.77495 7292   11   11     111    11   0.0  0.0  0.0           1862.0           1514.0    0.0214    0.0168
    3   NH -71.05315 44.88302 7292   11   11     111    11   0.0  0.0  5.0            360.0            360.0    0.0794    0.0725
    4   ME -70.98117 44.79654 7481  113  181       2    90 150.0 85.0 77.0           5197.0            516.0    0.7719    0.4470
    4   NH -71.05326 44.83227 7481  113  181       2    90 150.0 85.0 75.0            313.0            313.0    0.2500    0.2502
    5   ME -70.98040 44.79735 7373  117  188       2    90 190.0 95.0 75.0           5223.0            524.0    0.7992    0.4584
    5   NH -71.13405 44.79027 7373  117  188       2    90 190.0 95.0 74.0            679.0            679.0    0.4767    0.4767
    6   ME -70.98910 44.87054 7302  112  167       5    41 110.0 65.0 85.0           4637.0            930.0    0.5828    0.4971
    6   NH -71.11954 44.89115 7302  112  167       5    41 110.0 65.0 86.0             95.0             95.0    0.3776    0.3776
    7   ME -70.98322 44.81761 7302  113  174       5    41 150.0 75.0 74.0           4669.0            360.0    0.8979    0.6566
    7   NH -71.16664 44.89134 7302  113  174       5    41 150.0 75.0 78.0            531.0            531.0    0.2892    0.2892

--- ME minus NH, per pair ---
  road_dist m (OLD)    mean ME-NH =  +4255.3750   per pair: [4944.0, 2592.0, 6897.0, 1502.0, 4884.0, 4544.0, 4542.0, 4138.0]
  road_dist m (NEW)    mean ME-NH =   +202.7500   per pair: [-549.0, -185.0, 490.0, 1154.0, 203.0, -155.0, 835.0, -171.0]
  prob (OLD)           mean ME-NH =     +0.3484   per pair: [0.129, 0.526, 0.532, -0.058, 0.522, 0.323, 0.205, 0.609]
  prob (NEW)           mean ME-NH =     +0.1078   per pair: [-0.119, 0.204, 0.168, -0.056, 0.197, -0.018, 0.119, 0.367]
```

On habitat the model itself cannot tell apart, the Maine cell was read
as **4.3 km farther from a road** than its New Hampshire twin, in every
one of the 8 pairs. The NH-side probabilities do not move at all when
`road_dist` is regenerated; the ME-side ones drop.

### Step 6 — ablation: which input drives the flagged pattern. **road_dist, alone.**
`inv_ablation_old.py` (on the pre-fix rasters, i.e. the inputs that
produced the reported map), 899 windows on a 720 m grid, 255 ME centres
and 644 NH centres. Output `inv_ablation_before.out`:

```
feature       mean dl  mean|dl|  sp.std    dl ME    dl NH  dl ME-NH
(base)                                     1.398    0.664     0.735
evt            +0.100     0.335   0.471   +0.469   -0.045    +0.514
evh            +0.140     0.281   0.382   +0.480   +0.005    +0.475
evc            +0.051     0.220   0.298   +0.279   -0.039    +0.318
sclass         -0.114     0.289   0.338   +0.229   -0.250    +0.479
fdist          +0.084     0.126   0.205   +0.324   -0.011    +0.335
nlcd           +0.065     0.291   0.393   +0.506   -0.109    +0.615
ch             +0.130     0.135   0.137   +0.259   +0.080    +0.179
cc             +0.068     0.119   0.186   +0.297   -0.022    +0.319
tcc            +0.146     0.172   0.270   +0.481   +0.013    +0.469
road_dist      -0.375     0.399   0.546   -0.980   -0.135    -0.845
tsd            -0.023     0.056   0.068   -0.024   -0.023    -0.001
balive         +0.194     0.209   0.295   +0.561   +0.049    +0.512
tpa_live       +0.126     0.259   0.387   +0.620   -0.070    +0.689
qmd            +0.134     0.137   0.186   +0.361   +0.044    +0.317
carbon_dwn     +0.091     0.098   0.117   +0.213   +0.042    +0.171
```

The pre-fix ME−NH logit gap is **+0.735**. `road_dist` is the **only**
one of the 15 inputs whose removal closes it (`dl ME−NH = −0.845`);
every other input, when blanked, *widens* it. Re-run on the post-fix
rasters (`inv_ablation.py`, `inv_ablation_after.out`) the base gap is
already **−0.050** and `road_dist`'s ablation effect drops to −0.059.

The plan's caveat — "missing" is out-of-distribution for a
`missing_mask` model — applies to this step and is why it is not the
confirming check on its own. The confirming check is §3.

### Step 7 — known points versus the map.
Script `inv_points_auc.py`, output `inv_points_auc.out`. 66 points fall
in the box: 55 positives, 11 negatives.

```
state  label
ME     1        14
NH     0        11
NH     1        41
```

```
=== inv_before/before_cal.tif
  in-box all : n=  66 pos= 55 AUC=0.7570 AP=0.9434 mean_pos=0.4950 mean_neg=0.2992
  NH side    : n=  52 pos= 41 AUC=0.6918 AP=0.8976 mean_pos=0.4152 mean_neg=0.2992
  label=1: ME n=14 mean=0.7287 | NH n=41 mean=0.4152 | P(ME>NH)=0.8728

=== inv_after/after_cal.tif
  in-box all : n=  66 pos= 55 AUC=0.7273 AP=0.9307 mean_pos=0.4341 mean_neg=0.2989
  NH side    : n=  52 pos= 41 AUC=0.6918 AP=0.8976 mean_pos=0.4141 mean_neg=0.2989
  label=1: ME n=14 mean=0.4924 | NH n=41 mean=0.4141 | P(ME>NH)=0.6533
```

Read carefully, because the headline number moves the "wrong" way:
- **The ME side of the box contains 14 positives and zero negatives**,
  so an ME-side AUC does not exist and the all-points AUC is driven by
  NH negatives. Inflating every Maine cell therefore *raises* the
  in-box AUC (0.7570) for a reason that has nothing to do with the model
  being right. After the fix it falls to 0.7273. **This is not evidence
  against the fix**; it is evidence that in-box AUC is not a usable
  metric with this point distribution.
- **The NH-side AUC is identical before and after (0.6918 / 0.6918)** —
  the change is confined to where `road_dist` was wrong.
- Among *positives only*, the Maine-over-NH rank advantage falls from
  0.8728 to 0.6533.
- The zero-Maine-negatives fact is itself a finding: see §7,
  **BUG-0029 (draft)**.

### The road_dist no-retrain check (plan §0, "Status of the road_dist hypothesis"). **CONFIRMED.**

The check that could have falsified the hypothesis, and did not.

1. `old_road_dist/` ← the 10 pre-fix `NH_*_road_dist.tif`
   (`NH_2025` md5 `0786b20eb217231759a3cb4383cb4e1b`).
2. `python generate_road_distance.py --regions NH --tiger-year 2023`
   (log: `inv_regen_road_dist.log`). **`--tiger-year 2023` on purpose:**
   the existing rasters were built with TIGER 2023, and the module
   default is now 2025, so pinning the vintage isolates the *coverage*
   fix from a road-vintage change. The run reports:
   `roads from 31 counties across 4 state(s) (STATEFP: {'23': 6, '25': 4, '33': 10, '50': 11})`
   — where the old code used NH's 10 counties only.
3. Re-run the **same** `predict.py` with the **same, unmodified**
   checkpoints (`md5sum -c inv_bce_md5_before.txt` → `bce.pth: OK`,
   checked after every run).

**`road_dist` in metres over the box** (`inv_road_dist_box.py`):

```
=== OLD_NH: old_road_dist/NH_2025_road_dist.tif
  ME: n=182183 min=0m p10=1482m median=4315m p90=7114m max=8759m mean=4313m
  NH: n=411633 min=0m p10=  60m median= 365m p90=1116m max=2939m mean= 493m
  ME median / NH median = 11.82x

=== NEW_NH: data/landfire/NH_2025_road_dist.tif
  ME: n=182183 min=0m p10=  85m median= 510m p90=1431m max=2335m mean= 639m
  NH: n=411633 min=0m p10=  60m median= 363m p90=1081m max=2230m mean= 477m
  ME median / NH median = 1.41x
```

Cross-check against an independent raster that never had the defect on
this side — Maine's *own* region raster over the same box:

```
=== OLD_MEregion: data/landfire/ME_2025_road_dist.tif
  ME: n=141670 min=0m p10=85m median=516m p90=1449m max=2295m mean=651m
```

The regenerated NH raster's Maine side (**510 m** median) matches the ME
region's own raster (**516 m**). The pre-fix value was **4,315 m** — a
**8.4× inflation**, and a 11.8× step at the border.

**Effect on the map, same box, same checkpoints, calibration on:**

| checkpoint | | ME mean | NH mean | ME−NH mean | ME ≥0.8 | NH ≥0.8 | P(ME>NH) |
|---|---|---|---|---|---|---|---|
| `gap3.pth` (the map the user reported) | before | 0.7949 | 0.6289 | +0.1660 | 67.93 % | 5.05 % | **0.8513** |
| | after | 0.6333 | 0.6277 | +0.0056 | 10.24 % | 4.88 % | **0.5400** |
| `bce.pth` (the checkpoint in the command) | before | 0.6887 | 0.4228 | +0.2659 | 45.68 % | 0.11 % | **0.8235** |
| | after | 0.4217 | 0.4220 | −0.0003 | 0.18 % | 0.10 % | **0.5089** |

The same collapse occurs with calibration off
(`before_nocal` P = 0.8235 → `after_nocal` P = 0.5089), so it is not a
calibration artefact.

The New Hampshire side is **unchanged** (0.6289 → 0.6277; 0.4228 →
0.4220). Only the Maine side moves, which is what the mechanism
predicts and what a coincidental global shift would not produce.

Picture: `inv_before_after.png` — the old `road_dist` panel shows the
bright distance "wall" starting exactly at the state line, and the
"before" suitability panels show the red block sitting on top of it.
Both are gone in the "after" panels, and the structure that remains is
shaped like terrain and cover, not like a border.

**The `road_dist` hypothesis is no longer untested. It is confirmed.**

---

## 3. Conclusion

**Cause identified: BUG-0023.** `road_dist` for the NH region was
computed from New Hampshire's TIGER counties only, while the NH region
grid is the LANDFIRE request rectangle reaching −70.600, well into
Maine. Every Maine pixel in the box was given the distance to the
nearest road *in New Hampshire* — a median of 4,315 m where the true
value is about 510 m. The model, which was trained on the same
defective rasters and has no location input, reads "far from any road"
as grouse-like, and scores the whole Maine side up.

Confirmed by three independent checks, each of which could have failed:

1. **Regenerate and re-predict with the same checkpoint** — the Maine
   jump collapses, `P(ME>NH)` 0.8513 → 0.5400 (`gap3.pth`, the
   reported map) and 0.8235 → 0.5089 (`bce.pth`), while the NH side
   does not move.
2. **Matched-habitat point pairs** — on cells the model's own
   categorical inputs cannot tell apart, `road_dist` was +4,255 m
   higher on the Maine side in 8 of 8 pairs; +203 m after the fix.
3. **Ablation over the box** — `road_dist` is the only one of 15 inputs
   whose removal closes the ME−NH logit gap (−0.845 against a +0.735
   gap); all 14 others widen it.

**Stages checked and found clean:** input coverage and nodata over the
box (step 4 — no missing data on either side, no other layer steps at
the line); train/predict reader parity (step 5 — bit-identical tensors
and logits); calibration (the split is identical with calibration on
and off); model rebuild from checkpoint config; output georeferencing
and extent.

**Residual, stated as unexplained.** After the fix, `bce.pth` shows no
Maine bias (P = 0.5089, ME−NH mean −0.0003). `gap3.pth` retains a small
one (P = 0.5400, ME−NH mean +0.0056, ME ≥0.8 10.24 % vs NH 4.88 %), and
the 8 matched pairs retain +0.1078 mean probability. Part of this is
genuine — the Maine side really is slightly more remote (510 m vs 363 m
median) — and the matched pairs constrain only 8 of the 15 inputs and
none of the 64×64 neighbourhood. Whether anything else contributes is
an **untested hypothesis**; §7's BUG-0029 is one candidate. It was not
investigated further because it is an order of magnitude smaller than
the reported symptom and all three checks above attribute the reported
symptom to `road_dist`.

---

## 4. Leakage count (step 8) — BUG-0027 **CONFIRMED on real data**

`inv_leakage.py` → `inv_leakage.out`, verbatim:

```
split        train  val
region kind            
ME     neg    3088  772
       pos    3088  772
NH     neg    1794  450
       pos    1794  450
VT     neg    1809  452
       pos    1809  452 

pos: 1,653 coordinates appear in >1 region (24.6% of 6,712 unique)
neg: 0 coordinates appear in >1 region (0.0% of 8,365 unique)
pos: 522 coordinates are TRAIN and VAL at once (32.4% of val coordinates)
neg: 0 coordinates are TRAIN and VAL at once (0.0% of val coordinates)
pos: val with a TRAIN point within   30 m - pooled  31.7% | same-region only   0.0%
pos: val with a TRAIN point within  300 m - pooled  32.6% | same-region only   1.4%
pos: val with a TRAIN point within 3000 m - pooled  74.7% | same-region only  61.3%
neg: val with a TRAIN point within   30 m - pooled   0.0% | same-region only   0.0%
neg: val with a TRAIN point within  300 m - pooled   1.4% | same-region only   1.4%
neg: val with a TRAIN point within 3000 m - pooled  71.6% | same-region only  71.0%
```

`inv_leakage_detail.py` → `inv_leakage_detail.out`, verbatim:

```
pooled positive rows: 8365  unique coords: 6712

coordinate membership by region set (unique coords):
region
(ME,)       3420
(NH, VT)    1213
(VT,)       1048
(NH,)        591
(ME, NH)     440

colliding coords: 522
val ROWS whose coord is also a pooled train coord: 522 of 1674

collision coords, region+split combos:
((NH, val), (VT, train))    194
((NH, train), (VT, val))    181
((ME, val), (NH, train))     76
((ME, train), (NH, val))     71
```

**Reading, per the plan's guidance:**

- **Sections 1–2 (exact duplicates).** Not zero. **522 coordinates are
  simultaneously training data and validation data**, i.e. **522 of the
  1,674 pooled validation positive rows (31.2 %)** were trained on
  directly, at the identical coordinate. 1,653 of 6,712 unique positive
  coordinates (24.6 %) belong to more than one region. The region pairs
  are exactly the two overlaps BUG-0027 predicted from the box
  constants: NH∩VT (1,213 coordinates) and ME∩NH (440).
- **Section 3 (proximity).** The block holdout works *within* a region —
  the same-region-only rate of a validation positive having a training
  positive within 30 m is **0.0 %**, and within 300 m is **1.4 %**,
  which is the small leak at block edges it is designed to leave. Once
  the regions are pooled, which is what `train.py` actually trains on,
  those become **31.7 %** and **32.6 %**. The gap — 31.7 points at 30 m
  — is pure cross-region leakage.
- **Negatives are unaffected** (0 duplicates, 0 collisions, pooled and
  same-region proximity identical). That is because negative candidates
  are drawn per state, not per box — which is itself the subject of
  BUG-0029 below.

**Consequence:** roughly a third of the validation positives are not
held out. The reported validation AUC/AP (about 0.82 / 0.79) and the
"best validation rank about 0.811" figure overstate real performance by
an unmeasured amount, and **no validation comparison between the
checkpoints in this repository can currently be trusted** — which was
the point of running this step first. The BUG-0027 fix will change every
split; the tables above are its "before".

Nothing was fixed here, per the plan's instruction. BUG-0027 needs a CR.

---

## 5. Proposed fixes (confirmed causes only — not implemented)

### 5.1 For the confirmed cause (BUG-0023)

The code fix is **already committed** (`bf8d31a` on `main`) and is what
this investigation verified. What remains is data and model work, which
is the user's call:

1. **Regenerate `road_dist` for every region**, not just NH:
   `python generate_road_distance.py`. ME and VT have the identical
   defect on their own out-of-state grid margins — the ME raster reads
   6,673 m median on the NH side of this same box where the truth is
   365 m (§2, `OLD_MEregion`). NH is currently regenerated; ME and VT
   are not.
2. **Decide the TIGER vintage.** This investigation pinned
   `--tiger-year 2023` to keep the check controlled. The module default
   is 2025. A production regeneration should use one vintage
   deliberately and record which.
3. **Retrain from scratch** (not `--resume`): every existing
   checkpoint, `bce.pth` and `gap3.pth` included, learned from the wrong
   distances at every state line in all three regions.
4. **Do BUG-0027 first, or at the same time.** Retraining against a
   leaking split would produce a new set of untrustworthy validation
   numbers, and there would be no way to tell the `road_dist` fix's
   effect from the split change.

**How to verify the fix afterwards**, with the numbers in this report as
the baseline:
- `python inv_state_split.py <new map>` → `P(ME pixel > NH pixel)` should
  stay near 0.5 (it is 0.5089 / 0.5400 now, was 0.8235 / 0.8513).
- `python inv_matched_pairs.py` → `road_dist m (OLD)` mean ME−NH was
  +4,255 m, should stay near the current +203 m.
- `python inv_points_auc.py <new map>` → NH-side in-box AUC, currently
  0.6918. **Do not use the all-points in-box AUC**: with 14 ME positives
  and 0 ME negatives it rewards inflating the Maine side (§2, step 7).
  Fixing BUG-0029 would make that metric usable.

### 5.2 For BUG-0027 (confirmed, needs a CR before anything)

BUG-0027 §6 already proposes the right shape and this investigation
adds nothing to it beyond confirming the magnitude. Not restated here.
It changes the dataset split, so per `CLAUDE.md` §1 it needs a change
request and independent review first.

### 5.3 For the two new findings

See §7. Both need their own BUG record and, being non-trivial, a CR.
No fix is proposed in detail until you have seen the drafts.

---

## 6. What was NOT done

- **No user-supplied matched pairs were requested.** Step 3 was run on
  8 pairs selected objectively by the model's own inputs instead. If you
  want your own ME/NH pairs checked, `inv_matched_pairs.py` and
  `inspect_point.py --region NH --lon <lon> --lat <lat> --model <ckpt>`
  will do it in a minute.
- **ME and VT `road_dist` were not regenerated** — outside the one data
  change the brief allowed.
- **Nothing was retrained.** No fix was implemented; BUG-0027 was
  measured, not touched.
- **`inv_points.kml` was not written** (`simplekml` is not installed).
  The point counts it would have visualised are in step 7.
- **Step 4's rasters were dumped from the post-fix `road_dist`.** The
  pre-fix Maine values are in §2's metre table and `inv_road_dist_old.out`.

---

## 7. Quality records

Per `CLAUDE.md` §2 and §5. **Nothing has been committed.** The two new
bug drafts are in the working tree as `DRAFT_BUG-0028-*.md` and
`DRAFT_BUG-0029-*.md` for your review; they are not in
`docs/quality/bugs/` and `BUG_LOG.md` / `PREVENTIVE_ACTIONS.md` have not
been touched.

| record | what this investigation changes | action needed |
|---|---|---|
| **BUG-0023** | Status was "OPEN, fix implemented, link to the reported symptom not yet confirmed". **Now confirmed on real data.** | Update §6 with the numbers in §2; keep OPEN for the ME/VT regeneration + retrain and the outstanding retroactive CR. |
| **BUG-0022** | The map defect it records as unidentified **is now identified**, by the method PA-0016 requires. | Update §6; the process finding itself stands unchanged. |
| **BUG-0027** | Status was "OPEN, unconfirmed on real data". **Now confirmed**: 522 of 1,674 val positives are also pooled train. | Update §3 and §6 with §4's tables; still needs a CR. |
| **BUG-0024** | `tsd` saturates at the 30-year cap over 76.67 % of this box. Consistent with its mechanism; **ruled out** as a contributor here. | Add as a real-data data point. Not a new bug. |
| **BUG-0028 (new, draft)** | `predict.py` writes to one mutable path with no provenance; the reported map's checkpoint was unidentifiable from the file and had to be brute-forced. PA-0014 mechanism. | Review draft. |
| **BUG-0029 (new, draft)** | `get_negatives.py:268` filters negatives by `stateProvince` while positives are box-clipped, so each region's out-of-state positives have no negatives. PA-0018 mechanism. | Review draft. |

BUG-0028 and BUG-0029 are both non-trivial (a file-format/CLI change and
a data-schema change respectively), so per `CLAUDE.md` §1 each needs a
CR and independent review before any implementation. None is proposed
yet.

---

## 8. Files produced

Investigation scripts (all read-only except where noted):

| file | what it does |
|---|---|
| `inv_leakage.py` / `.out` | step 8, BUG-0027 count |
| `inv_leakage_detail.py` / `.out` | step 8, region-pair breakdown |
| `inv_inventory.py`, `inv_inventory_before.out` | step 1 |
| `inv_state_split.py`, `inv_state_split_{before,after,gap3}.out` | ME vs NH statistics for any prediction GeoTIFF |
| `inv_road_dist_box.py`, `inv_road_dist_{old,new}.out`, `inv_road_dist_*.npy` | `road_dist` in metres over the box, by state |
| `inv_matched_pairs.py`, `inv_matched_pairs.csv` | step 3, matched-habitat pairs |
| `inv_feature_maps.py` / `.out`, `inv_feature_maps/` | step 4, every input as a map + per-state statistics |
| `inv_parity.py` / `.out` | step 5, train/predict parity |
| `inv_ablation.py`, `inv_ablation_old.py`, `inv_ablation_{before,after}.out`, `inv_ablation_*.npy` | step 6 |
| `inv_points_auc.py` / `.out` | step 7 |
| `inv_figure.py`, `inv_before_after.png` | the before/after panel |
| `inv_regen_road_dist.log` | the `generate_road_distance.py` run |

Data copies: `old_road_dist/` (pre-fix, 10 files), `new_road_dist/`
(post-fix, 10 files, identical to what `data/landfire/` now holds),
`inv_before/`, `inv_after/`, `inv_probe/`, `inv_probe_old/`,
`inv_bce_md5_before.txt`.

**State of `data/` at the end of this investigation:**
- `data/landfire/NH_*_road_dist.tif` — the **regenerated** (corrected)
  rasters, verified identical to `new_road_dist/`. The pre-fix files are
  in `old_road_dist/`; `cp old_road_dist/NH_*_road_dist.tif data/landfire/`
  reverts. ME and VT `road_dist` are untouched and still defective.
- `data/predictions/NH_custom_suitability.{tif,kmz}` — now the
  **corrected** map for `gap3.pth` (the checkpoint that made the
  reported map), so it can be opened in Google Earth directly. **Your
  original map was overwritten by this investigation and is preserved
  as `inv_before/USER_ORIGINAL_NH_custom_suitability.{tif,kmz}`.**
- Nothing else in `data/` was written. No checkpoint was modified
  (`md5sum -c inv_bce_md5_before.txt` → `bce.pth: OK`). No tracked file
  in the repository was modified.

**Deviations from the plan's listings**, all confined to investigation
scripts, none to project code:
- `inv_ablation.py` runs on CUDA (the plan hardcoded CPU) and reports
  each feature's ME/NH split so the ablation speaks to the symptom
  directly. `inv_ablation_old.py` is the same script with
  `rd.latest_raster_path` monkey-patched to resolve `road_dist` to
  `old_road_dist/NH_2025_road_dist.tif`, so the ablation runs on the
  inputs that produced the reported map.
- `inv_parity.py` adds a third score per point, using
  `latest_raster_path`, to separate reader differences from vintage
  differences.
- `inv_feature_maps.py` adds the per-state statistics table.
- `inv_state_split.py`, `inv_road_dist_box.py`, `inv_matched_pairs.py`,
  `inv_points_auc.py`, `inv_leakage_detail.py`, `inv_figure.py` are new;
  the plan describes what they measure but supplies no listing.
- `inv_points_auc.py` skips the KML when `simplekml` is absent rather
  than failing.
