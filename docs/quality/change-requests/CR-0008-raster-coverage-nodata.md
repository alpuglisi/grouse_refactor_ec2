# CR-0008: Mark uncovered area as nodata in every derived raster

**Status: DRAFT (v2) — awaiting independent review (`CLAUDE.md` §1.2).**
Nothing committed. All deliverables pending.

### Revision note (v1 → v2)
v1 was written as part of the CR-0006 split and inherited that
document's weakest habit: acceptance stated as prose rather than as
computations, and never tested against a pipeline deliberately broken in
the way each check exists to catch. Reviewers broke CR-0006's acceptance
set three times and CR-0007's once, always for that reason. v2 adds
§ Acceptance — a measured table — and applies the rule this work has
converged on:

> **Every acceptance invariant must be measured on at least one
> constructed pipeline that is wrong in the way that invariant exists to
> catch — not only on the current data and the intended pipeline.**

Concretely, v2 adds a gate for a failure v1 described but could not
detect: an implementer following §2's TreeMap spec literally would
choose a negative sentinel, `generate_treemap_features._clean:261`
(`a[a < 0] = 0.0`) would silently convert it back to the fabricated
non-forest `0`, and the regeneration would **report success**. v1 named
that hazard in prose and then had no check that would fail on it.

**Supersedes part of CR-0006** (see CR-0007's header for why that CR was
split). This CR carries the PA-0017 raster work. It is independent of
CR-0007 and may be reviewed and landed in either order; CR-0009 is gated
on both.

## Scope
Fix BUG-0023 (ME/VT `road_dist`), BUG-0024 (`tsd`), BUG-0025 (TreeMap:
`balive`, `tpa_live`, `qmd`, `carbon_dwn`) and BUG-0030 (`tcc`, new) by
marking area outside each product's coverage as nodata instead of a
legitimate-looking value, in both the generators and the existing
rasters.

## Why now
**Six of fifteen model input channels currently feed fabricated readings
over roughly 47 % of the ME grid.** Confirmed on real files by the
author and two reviewers independently. Sampling where LANDFIRE `evt` is
nodata:

```
evh/evc/sclass/fdist/ch/cc   nodata 1.000   correct
nlcd                         nodata 0.998   correct
tsd                          nodata 0.000   constant 3434 "undisturbed 30 yr"   BUG-0024
balive/tpa_live/qmd/carbon_dwn nodata 0.000  0 "non-forest"                     BUG-0025
tcc                          nodata 0.006   0                                    BUG-0030 (new)
road_dist  ME (old)          nodata 0.000   10820 saturated                      BUG-0023
road_dist  NH (regenerated)  nodata 0.996   -9999                                correct
```

`tcc` also settles PA-0017's open sweep item, which recorded the
TCC/NLCD masked-pixel export as "not determined from code — needs a
real-file check": **`tcc` is defective, `nlcd` is correct — but only
incidentally**, because its `valid_range` starts at 11 and rejects the
mask's 0 by accident. PA-0017 and `CLAUDE.md` §3.3 require fixing the
mechanism, so both products are corrected.

## Settled decisions
**Branch A (user, 2026-09-30): `balive == 0` is a reading, not a gap.**
In-CONUS non-forest stays `0`; only outside-US becomes nodata. TreeMap's
Earth Engine mask is *non-forest ∪ outside-CONUS* — one mask — so this
distinction cannot come from the product and needs an external land
reference (§ Coverage).

Evidence the decision rests on:
```
balive == 0, share of the evt-valid grid:   ME 50.2%  NH 30.4%  VT 29.2%
  of those ME zeros, inside the US:         35%
balive == 0 at a record's CENTRE pixel:     ME 25.4%  NH 26.3%  VT 25.3%
tcc  == 0, share of the evt-valid grid:     ME 40.1%  NH 12.5%  VT  7.2%
```
Branch B (0 is not a reading) would flip ~25 % of four channels' centre
pixels to `MISSING_CODE` and is a modelling change, not a coverage fix.

**TIGER vintage 2023 (user, 2026-09-30).** Matches the already-regenerated
NH raster, so **NH `road_dist` needs no regeneration**. Download cost,
measured with the script's own `counties_for_grid`: ME 23 counties
(0 uncached), NH 31 (0 uncached), VT 34 (**8 uncached** — MA 25003,
25015; NY 36019, 36031, 36083, 36091, 36113, 36115). National county
file cached. `TIGER_YEAR` currently defaults to **2025** in
`generate_road_distance.py:114` while `diagnose_road_bias.py:72` says
2023 and every cached file is 2023; it is pinned to 2023 here.

## § Coverage — per generator, not one global mask
CR-0006 asserted a single reference (NLCD's valid footprint) for four
products whose sources have four different footprints. A reviewer
measured the consequence on the **already-correct** NH `road_dist`:
3,520 px carry a valid distance where NLCD is nodata, and 965 px are
nodata where NLCD is valid. Stated as an absolute zero, such an
invariant fails on an artifact this CR calls correct — and a gate that
gets waived on its first run has no authority.

Therefore:
- **Each generator's coverage reference is the footprint its own sources
  define**: TIGER county union for `road_dist`; the LANDFIRE disturbance
  stack's covered area for `tsd`; the Earth Engine product footprint for
  TreeMap and `tcc`.
- **NLCD's valid footprint is the cross-check**, not the definition,
  with a **bounded disagreement budget of ≤0.05 % of grid pixels per
  direction per feature per region**, recorded rather than assumed zero.
  NH `road_dist` measures 0.006 % / 0.002 % against that budget.
- Supporting measurements: NLCD nodata = 47.25 % (ME) / 9.92 (NH) /
  4.00 (VT), against independently derived `road_dist` NODATA of
  47.1 / 9.8 / 4.0 %; agreement with the TIGER union is 0.006–0.008 % of
  grid pixels in each direction; the NLCD mask is **time-invariant**
  (2016 vs 2025 differ by 0 pixels in all three regions).
- **LANDFIRE `evt` nodata is NOT a coverage reference.** 32.8 % of
  evt-*valid* ME pixels lie outside the US, and VT's evt nodata fraction
  is **0.0000**, which makes any evt-anchored check vacuous there.

## The change

### 1. Repair the existing rasters (local post-process)
Validated by a reviewer: within a region, every raster — `nlcd, tcc,
balive, tpa_live, qmd, carbon_dwn, tsd, road_dist, evt`, first and last
year of each — is byte-identical in transform, width, height, CRS,
`dtype=int16` and `nodata=-9999`. 54 files checked across three regions,
zero mismatches. So the repair is index-for-index, with no warp, no
resample and no re-encoding.

For each region, for `balive, tpa_live, qmd, carbon_dwn, tcc, tsd`, for
every year on disk: set the generator's own coverage mask to `-9999`.

- **It must be spatial, not value-based.** `balive > 0` outside the
  footprint is 11,700 px (ME), 4,464 (NH), 2,137 (VT) — TreeMap carries
  non-zero imputations past the border, so "turn the zeros into nodata"
  leaves those fabricated.
- **Temp file then atomic rename.** Once the originals are overwritten
  the backup is the only copy.
- Cost: ~170 files, ~9 GB of int16 I/O, local CPU, minutes.
- **No Earth Engine, no GCP, no 6.6 GB `data/treemap_raw` re-fetch.**
- `tcc` has no re-derivable intermediate (its EE tiles live in a
  `TemporaryDirectory`), so for `tcc` the post-process is the only
  non-network option.

Residuals to record, not hide: a ≤1–2 px (≤60 m) boundary fringe where
masks disagree; US open water (NLCD 11) keeps its `0`, which under
Branch A is the intended reading.

### 2. Fix the generators — mandatory, not an alternative
PA-0017 is a rule about **generators**. The post-process repairs
artifacts; without the code fix the next run silently restores all four
defects. CR-0006's "re-run (or post-processed)" wording implied a
substitution; these are two obligations.

- **`generate_road_distance.py`** — already fixed (`bf8d31a`) and
  ground-truthed at 400 Maine points: median error 16,086 m before,
  **10 m** after. Regenerate **ME and VT only**, at TIGER 2023. Two
  residuals fixed first: `_download` (`:124-130`) has no temp file,
  atomic rename or size check, so an interrupted download poisons the
  cache permanently (`if os.path.exists(path): return path` never
  re-fetches a truncated zip); and `counties_for_grid` reprojects an
  undensified footprint (densification added; `pad_px` derived from the
  x resolution alone is documented as safe only because every grid is
  30 × 30 m).
- **`generate_time_since_disturbance.py`** — `:339` is
  `np.where(last >= 0, year - last, TSD_MAX_YEARS)`, conflating "no
  disturbance recorded" with "not covered". **Do not derive coverage
  from the source's nodata**: measured, the sources declare
  `nodata=32767` but most vintages store an undeclared **−9999**
  outside the US (`LF2001_Dist00`, `LF2023_Dist23`: 100 % −9999 in the
  NE corner, 0 % matching the declared value; `LF2024_Dist24`: 32767),
  and two vintages return real disturbance codes at out-of-US points.
  Coverage is not derivable by any sentinel test — use the § Coverage
  reference mask. Also **do not** reuse `:312-314`'s `hit` (`arr > 0 and
  arr != nodata`): a covered, undisturbed pixel has value 0 and would be
  masked, destroying the **81–93 %** of training centre pixels that
  legitimately read `TSD_MAX_YEARS`.
- **`download_treemap.py`** — `:293`'s `unmask(0)` must not fill outside
  the product footprint, and the file must carry a real nodata (it
  currently writes `nodata=None`).
- **`generate_treemap_features.py`** — in scope; CR-0006 omitted it
  although it owns the 7.6 GB of per-region rasters the model reads.
  `_clean` (`:256-262`) is:
  ```
  259:     a[~np.isfinite(a)] = 0.0
  260:     a[a >= NODATA_FLOOR] = 0.0
  261:     a[a < 0] = 0.0
  ```
  **Line 261 clamps any negative sentinel to 0.0** and `:259` does the
  same for NaN — so a sentinel is not passed through, it is silently
  converted back into the fabricated "non-forest 0" this CR removes,
  with no error. `_clean` must become mask-aware and propagate nodata.
  *(CR-0006 described the opposite mechanism and cited `:257-260`; the
  operative line was outside its citation. Corrected here.)*
  Its documented contract — "qmd=0 AND tpa_live=0 is exactly the
  non-forest signature, so the joint pattern carries forest/non-forest
  without a mask channel" — is at **line 61**, and Branch A preserves it.
- **`download_tcc_nlcd.py`** — the fix **cannot** live at `:366`
  (`(arr>=lo)&(arr<=hi)`, `lo=0`), because 18.4 % of `tcc`'s zeros are
  real 0 % canopy inside the US. It must be an explicit
  `unmask(<sentinel outside valid_range>)` at the Earth Engine stage.
  `unmask(-1)` works: `:366` converts any out-of-range value to
  `NODATA = -9999` (`:77`), which is in `grouse_data.NODATA_SENTINELS`.
  Apply to **both** products; `nlcd`'s current correctness is incidental
  and is recorded as such.

## Impact
- **ME `road_dist` becomes 47.1 % NODATA** (NH 9.8 %, VT 4.0 %). The ME
  *prediction map* loses that channel over nearly half its extent.
- **Training inputs change less than CR-0006 claimed, but not zero.**
  CR-0006 said "0 of 6,702 training records have a nodata `evt` pixel
  in-window, so the regenerations change no training input at all" —
  true, but anchored on the reference § Coverage forbids. Against the
  NLCD footprint a reviewer measured, for ME: **16 train positives and
  27 negatives with some nodata in-window** (7 and 22 above 10 %, one
  negative at 100 %), plus **10 of 1,794 NH train positives**, one at
  51 %. And **one ME negative's centre pixel** is out of coverage —
  the same record CR-0007 must disposition. So: the effect is small and
  Branch A's conclusion holds, but "no training input changes" is
  withdrawn.
- **`road_dist` ME/VT additionally changes in-US values by design** —
  that is the BUG-0023 fix. Records within 5 km of a land border with
  another US state: ME 124 pos + 111 neg, VT 218 + 403.
- **`predict.py` masks its output on `cat_np[0]`** (`:332-333`) — the
  first categorical channel, `evt` only by spec ordering. After this CR
  the ~33 % of the ME grid outside the US with valid `evt` still renders
  predictions from a degraded channel set. **Changing that mask is
  deliberately out of scope**: the model consumes missingness through
  validity channels by design (`read_window_stack` docstring,
  `:231-232`), the Errol map was wrong because values were *fabricated*
  rather than *missing*, and CR-0006's two descriptions of the intended
  behaviour contradicted each other. It needs its own decision, with the
  blanked fraction measured per region first.
- **Not affected:** record membership, splits, model architecture.

## Risk level: **MEDIUM**

| risk | mitigation |
|---|---|
| A naive `tsd` fix destroys 81–93 % of the channel. | § Coverage mask, not a sentinel test; the "nodata inside coverage" direction of the acceptance check catches it. |
| A negative sentinel is silently clamped back to 0 by `_clean:261`, producing a no-op regeneration that reports success. | Named explicitly above; the acceptance check is evaluated on the **per-region derived rasters the model reads**, not the raw downloads. |
| An interrupted TIGER download poisons the cache permanently. | `_download` atomicity fixed before any regeneration. |
| The post-process overwrites the only copy. | Full raster backup before step 1; temp-file-then-rename within it. |
| A coverage gate fails on already-correct data and gets waived. | Per-generator reference plus a stated ≤0.05 % disagreement budget, measured per feature per region. |

## § Acceptance — measured, full resolution

**v3 inverts the acceptance design.** v2 enumerated outcomes that must
not occur (no fabricated value outside coverage; zero counts unchanged;
`tsd` saturation unchanged). A reviewer broke that set four ways, and
the reason is structural: a blacklist can only forbid the failures its
author thought of. v3 instead **constrains what may change**, which is a
whitelist and is closed by construction.

### G1 — the governing invariant
> **`set(pixels whose value changed) ⊆ set(pixels outside that
> generator's coverage)`**, verified at **full resolution** against the
> checksummed backup, per file, per feature, per year, per region.
> Reported as a count of violating pixels; **required 0**.
> `road_dist` ME/VT is the one exemption — it changes in-coverage values
> by design (that is the BUG-0023 fix) and is gated by G2 instead.

This single invariant closes three of the four demonstrated breaks:
- a repair that also **doubled every in-coverage non-zero value** — v2
  passed it;
- a repair that **overwrote 79,406,422 in-coverage pixels (39 % of the
  ME grid) with a constant**, collapsing 1,732 distinct values to 2 —
  v2 passed it;
- a repair that masked **in-coverage `tsd == 0`**, destroying 0.99–2.03 M
  legitimate pixels per year — v2 passed it, because v2's `tsd` guard was
  exactly invariant under it.

It also makes v2's A2 (zero counts) and A3 (`tsd` saturation)
**redundant**; both are demoted to reported diagnostics.

### G2 — coverage is actually applied
Fraction of outside-coverage pixels reading nodata, per feature per
region per year, **full resolution**, against the generator's own
reference: **required exactly 1.0000.**

v2 set this at ≥0.99 and justified the relaxation with a control
measurement of 0.9992 / 69 stray pixels. That measurement was taken
against NLCD; measured against the **declared** reference (the TIGER
county union), the already-fixed NH `road_dist` scores **1.000000 with
0 stray pixels**, and its total nodata fraction equals the outside-TIGER
fraction exactly (0.099165). So 1.0000 is achievable on real data and
the basis for relaxing it does not exist.

v2's ≥0.99 was also in the wrong units — a fraction of the
*outside-coverage* area, not of the grid — so on ME it admitted
**962,158 fabricated pixels** against a stated budget of 101,811, while
on VT it was *stricter* than intended. The 0.05 %-of-grid budget
survives only as the **NLCD cross-check** tolerance (NH measures
0.0062 % / 0.0017 %).

### G3 — full resolution is mandatory
Every figure in v2 was an 8× decimated sample. A reviewer showed that an
implementer deriving the coverage mask the same way is **measured on the
lattice its own aliasing avoids**: A1 read 1.000000 for all three regions
while 107,326 ME pixels stayed fabricated and 78,995 were destroyed. All
acceptance measurements are full-resolution. Decimated figures may be
reported as a fast pre-check, labelled as such.

### G4 — the `_clean` defect gets a real test
v2 claimed "A1 on derived rasters" detects
`generate_treemap_features._clean:261` (`a[a < 0] = 0.0`) swallowing a
negative sentinel. Under Branch A the data is repaired by the §1 local
post-process, which never calls `_clean`, so that gate cannot fire.
Replaced by two concrete tests, **both runnable here** — `data/treemap_raw`
is present (27 files, 6.6 GB) and `generate_treemap_features.py` takes
`--src-dir`:
1. a unit test on `_clean`: sentinel in → nodata out, not `0.0`;
2. one real `generate_treemap_features.py --src-dir data/treemap_raw`
   run for one region-year, with a sentinel injected into a scratch copy
   of one raw band, and G2 evaluated on that output.

### Measured baselines (corrected)

Outside-US fraction, full resolution: **ME 0.472521, NH 0.099210,
VT 0.039973**. For contrast `evt`-nodata is ME 0.2169, NH 0.0040,
**VT 0.0000** — why `evt` is not the reference, and why any evt-anchored
check leaves VT unexamined. ME `road_dist` becomes **47.23 %** NODATA
(v2 said 47.1 %); NH **9.92 %** (v2 said 9.8 %).

Fabricated-today counts, the "before" for G2, per region:

| feature | ME | NH | VT |
|---|---|---|---|
| `tsd`, TreeMap ×4 | all outside-coverage px | all | all |
| `tcc` | 99.7 % of them | 99.9 % | 99.8 % |
| `road_dist` | all | **0 (already fixed)** | all |

Diagnostics, reported not gated: in-coverage zero counts (ME TreeMap
437,796 / `tcc` 185,465 at 8×, year 2025/2023 — **state the year, they
vary: ME TreeMap zeros are 451,031 in 2016**); `tsd` in-coverage
saturation share, which spans **0.7998–0.9727** across years and regions,
not the 81–93 % v2 quoted (that figure is a *training-centre-pixel*
statistic, a different population).

**`tsd` correction:** v2 asserted "`tsd` has 0 in-coverage zeros". That
is true **only for 2025**, the single year sampled. Nine of ten years per
region carry **185 k–2.03 M** in-coverage zeros (`tsd == 0` means
"disturbed this year"). A per-year in-coverage `tsd == 0` count is
reported alongside G1.

### G5 — training-window impact, on the final record set
Count of training records with any out-of-coverage pixel in a 64×64
window, and with an out-of-coverage centre pixel. **Measured on the
record set CR-0007 produces, not the current one** — v2 measured the
current set, which CR-0007 replaces, so neither the "before" nor the
"after" was reproducible in either landing order.

Today, against the NLCD footprint: ME **23 train + 4 val** negatives with
some nodata in-window (v2 said "27 … train"; it pooled train and val),
18 + 4 above 10 %, and **one val negative at 100 % whose centre pixel is
out of coverage** — `(-67.10082, 44.50177)`, `val_negatives_ME.csv`.
That is CR-0007's second known exception, it is a **validation** record,
and CR-0009's validation baseline is computed on it. Its disposition is
CR-0007's; this CR records the dependency.

### G6 — grid identity
Transform, width, height, CRS, dtype, nodata unchanged on all 174
post-processed files (verified today: 54 files across three regions,
zero mismatches).

## Test plan
**Validatable here:**
- **Coverage, both directions, per region, per feature, on the derived
  rasters**: no feature carries a value outside its generator's
  coverage; no feature is nodata inside it where it was not before.
  Disagreement against the NLCD cross-check ≤0.05 % per direction,
  recorded.
- `tsd`: the fraction of pixels reading `TSD_MAX_YEARS` **inside**
  coverage is unchanged (today 81–93 % of training centre pixels); the
  fraction outside coverage is 0.
- `tcc`: real 0 % canopy inside the US survives — count of `tcc == 0`
  inside coverage unchanged.
- TreeMap: in-CONUS non-forest `0` count unchanged (Branch A);
  `balive > 0` outside coverage goes 11,700 / 4,464 / 2,137 → 0.
- Grid identity re-verified after the post-process: transform, width,
  height, CRS, dtype, nodata unchanged on all ~170 files.
- ME/VT `road_dist` regenerated: the script's own printed NODATA
  fraction ≈ 47.1 % / 4.0 %; a spot-check of Maine points against
  nearest-road ground truth, as was done for NH.
- Checksums before and after, and a restore rehearsal from backup.

**Cannot be validated here, and why:**
- **The Earth Engine generator fixes** (`download_treemap.py`,
  `download_tcc_nlcd.py`). They require GCP auth and an EE project.
  Under Branch A the *data* is repaired locally, so the code fix ships
  unexercised — it is verified only by inspection until the next real
  download. **Stated as an accepted test gap**, with the first future
  run required to record its coverage table.
- **TIGER 2025 behaviour** — only 2023 is cached; the 8 uncached VT
  county files need network.
- **Any effect on model performance** — requires CR-0009.

## Deliverables
- [ ] Back up every raster this CR touches, with checksums: `tsd` 148M,
      `balive` 1.9G, `tpa_live` 2.0G, `qmd` 1.9G, `carbon_dwn` 1.8G,
      `tcc` 1.3G, `road_dist` ME/VT/NH 698M ≈ **9.75 GB**.
- [ ] `generate_road_distance.py`: atomic `_download`; densified
      footprint reprojection; `TIGER_YEAR` pinned to 2023.
- [ ] Regenerate ME and VT `road_dist` at TIGER 2023 (8 county files).
- [ ] `generate_time_since_disturbance.py`: § Coverage mask, not a
      sentinel test, and not `hit`.
- [ ] `download_treemap.py`: no fill outside the footprint; real nodata.
- [ ] `generate_treemap_features.py`: `_clean` mask-aware.
- [ ] `download_tcc_nlcd.py`: explicit EE `unmask(-1)` for `tcc` **and**
      `nlcd`.
- [ ] Post-process the existing rasters (§1), atomically.
- [ ] Record the full two-direction coverage table, all three regions,
      all fifteen features, before and after.
- [ ] Create BUG-0030 (`tcc`) with a `BUG_LOG.md` row; update
      BUG-0023/0024/0025 to confirmed and fixed.
- [ ] `PREVENTIVE_ACTIONS.md`: PA-0017's Swept? cell updated with the
      `tcc` result and the corrected coverage reference; note that the
      reference must be per-generator.
- [ ] Confirm **BUG-0033** and **PA-0021** are filed by CR-0007 (the
      acceptance-criteria defect class and its rule). This CR's G1–G4
      apply PA-0021(b) and PA-0021(a); it does not file them, and a
      reviewer found that no CR did.
- [ ] Independent review with every concern dispositioned.

## Out of scope
- **Record membership and splits** → CR-0007.
- **The retrain and the end-to-end map check** → CR-0009.
- **`predict.py`'s validity mask** — see Impact; needs its own decision
  and a measurement first.
- **Branch B** (`0` is not a reading). Decided against; revisiting it is
  a modelling change and a new CR.
- `data/treemap_raw` remains as-is; the latent defect is closed by the
  generator fix, not by re-fetching 6.6 GB.

## § Review
Not yet reviewed. Author sign-off withheld.
