# CR-0008: Mark uncovered area as nodata in every derived raster

**Status: v7 REJECTED in round 7 (2 reviewers, 2026-09-30) — dispositions pending, see § Review. Previously: REVISED (v7) after seven reviews across six rounds, a coverage
research investigation, and the cross-CR seam measurements from CR-0007's
v7 research — awaiting re-review (`CLAUDE.md` §1.2).** Nothing committed.
All deliverables pending.

**Split (2026-09-30):** §1 "Repair the existing rasters" and the gates
governing it (G0–G3, G6, G8) move to **CR-0010**. This CR's remaining scope
is the generator and downloader fixes and the `road_dist` ME/VT
regeneration; it will be rewritten as v8 on that scope. Open round-7 items
are tracked in `docs/quality/CR-0007-0008-OPEN-ISSUES.md`.

**Counting convention, stated once because rounds and reviews differ:**
**six rounds, seven reviews** — round 1 had two reviewers. The § Review
table is the authority; a reviewer numbering this round "7" is counting
reviews, not rounds.

### Revision note (v6 → v7)
v7 is **not** a response to a new review of this document — v6's answers to
round 6 stand unchanged. It records what CR-0007's v7 research measured
about *this* CR's seams, which was previously asserted:

1. **§ Impact now carries the measured cross-CR effect.** The candidate
   pool moves by **2 records** (both marine ME points, 0 positives); the
   `generate_negatives.py` extraction `dropna` reads three features all
   **out of this CR's scope**, so the intersection is **empty** and the
   hypothesis that this CR could mechanically create a negative-supply
   defect is **refuted**; exactly one CR-0007 row (**I17**) reads a
   rewritten raster, 6 of its 7 in-scope features are **bit-identical at
   the records**, and `road_dist` moves **4 of 3,659** ME positives.
2. **§ G5's hand-off extended to I17** — re-measured, not re-thresholded,
   by whichever CR lands second, because its argmax feature changes while
   its threshold does not.
3. **PA-0021(c)'s exemptions cited.** G0.2's digests and the `N_pre` values
   are pre-registered constants (point-mass null) and G1/G2/G2′/RD5 are
   exact predicates — both explicitly exempt from the quantile requirement,
   which needs saying now that PA-0021's clause set is written out.
4. The "either order" claim is therefore **measured**, not asserted.

### Revision note (v5 → v6)
v5 was rejected (round 6, formal, fresh). It confirmed the repair core —
all nine G0 digests, all twelve `N_pre` counts and every distributional
claim reproduced from independently written code, seven attacks failed —
and rejected on the two seams the CR had carved out for itself.

1. **`road_dist`'s nodata placement was gated in one direction only.**
   G1 and G2′ both exempt `road_dist` ME/VT and G2 asks only that
   *outside*-coverage pixels read nodata, so a nodata set that is a
   **superset** of outside-coverage passed *a fortiori*. Measured cost of
   an over-masking repair: **32,560 ME + 3,287 VT legitimate in-US pixels
   destroyed per file × 10 year-copies = 325,600 ME + 32,870 VT**, on the
   feature this investigation is about, with G0/G2/G6/G8 all passing and
   G7's detection probability **0** (the over-masked pixels read nodata,
   so `|err|` cannot be computed at them and every implementation
   excludes them — and v5 filed the excluded-point count under "reported,
   not gated"). **RD5 added**; the excluded-point count is now **gated at
   0**; G2 is restated as a **pixel count**, not a 4-dp fraction.
2. **The withdrawn `tsd` claim survived a third time, in the operative
   deliverable.** v4 left it in the deliverable, v5 rewrote the prose and
   left the deliverable, and the disposition table recorded it "Accepted —
   §9.2 rewritten" citing a section number **this document does not
   have**. Both surviving instances are corrected in place, and the
   disposition now cites line-anchored locations.
3. **G2 restated as a count, G6 widened to `IMAGE_STRUCTURE`, G8's glob
   and mtime clause made mechanism-based, G4.2 given an instrument with
   power, G5 made order-independent, G0.4 given a vintage-addition
   trigger** — see each gate.
4. **PA-0021 / BUG-0033 re-pointed.** They are cited as governing by
   CR-0007's own body, so CR-0007 cannot be the document that first
   defines them. They move to a bookkeeping batch that lands **before**
   both CRs; this CR cites them as extant-by-then, not as CR-0007's.
5. **The gates are presented in order** — v5 ran G0, G2′, G1, G2, G3,
   G4, baselines, G7, G8, G5, G6, so an implementer working the section
   top-down met G7 before G5. Now G0, G1, G2, G2′, G3, G4, G5, G6, G7,
   G8. No gate text was changed by the reordering.
6. Unit, count and schema corrections: the backup is **9.49 GiB =
   10.19 GB**, not "9.75 GB" (wrong in both units); **174** in-scope
   files, not "~170"; **206 `.npy` + 1 `.tmp`**, not "207"; the VAT
   schemas number **four canonical / six literal**, not "three".

### Revision note (v4 → v5)
v4 was rejected (round 5, formal, fresh) for carrying no verdicts and no
disposition table after four rounds, and for leaving the withdrawn `tsd`
claim operative. v5 added the § Review verdict and disposition tables,
widened G6 from the hand-passed profile subset to the full profile dict
plus a size check, added **G8** (the metadata-preserving replace that
defeats the patch cache), corrected the `tsd` footprint table to print
both columns, corrected `-1111` to 6 of 26 tables, and rewrote § Coverage's
prose — but left the withdrawn claim standing in the deliverable and the
risk table, which is why round 6 rejected it again.

### Revision note (v3 → v4)
v3 was rejected: both governing gates consumed the repair's own mask, so
they held for any mask at all, and the declared coverage reference was
uncomputable for five of six features.

1. **The "`tsd` coverage is not derivable" claim is WITHDRAWN** — it was
   wrong. Every vintage ships a value-attribute table; the GeoTIFF
   nodata tag is what is wrong, not the data.
2. **Per-feature references settled** — TIGER, disturbance-intersection,
   NLCD — with no Earth Engine run required.
3. **G0 added**: the mask is pinned by pre-registered digest and
   inside-count. This is what closes the aliased-mask and whole-grid
   attacks.
4. **G2′ added**: G1 becomes equality against pre-registered
   must-change counts, so a no-op fails. `road_dist` is exempt from the
   conjunction and gated by G7 instead.
5. **G7 added** for `road_dist`'s in-coverage values — a median or p95
   gate on a uniform sample passes the broken raster on disk.
6. **The "independent" completeness reference is withdrawn as
   circular** — the fractions proposed were the NLCD nodata fractions.
7. **A blocking self-inflicted defect fixed**: v4 first shipped the
   `tsd` footprint table with the *inside* fraction under an "outside"
   heading. Caught in review before implementation.

### Revision note (v2 → v3)
v2 was rejected (round 2, seam reviewer, 2 blocking): its coverage
threshold was stated as "≥0.99" in the wrong units — a fraction of the
*outside-coverage* area rather than of the grid, which on ME admitted
**962,158 fabricated pixels** against a stated budget of 101,811 while on
VT it was *stricter* than intended — and every figure in it was taken from
an 8× decimated sample.

v3 responded by adopting **Branch A** (repair the existing rasters by local
post-process, and fix the generators as well rather than instead), settling
a **per-generator** coverage reference instead of one global mask, and
pairing the change-set whitelist with "the expected outside-coverage
fraction stated independently".

Round 3 rejected all three of v3's load-bearing pieces: the "independent"
reference was **circular** (the fractions proposed were precisely the NLCD
nodata fractions, to six decimals), **both governing gates consumed the
repair's own mask** so they held for any mask whatsoever, and the declared
coverage reference was **uncomputable for five of six features**. v3 also
deferred `road_dist`'s in-coverage values to a test-plan "spot-check" with
no threshold, and omitted `models.py`'s encode path. G0, G2′ and G7 in v4
are the answers to those three.

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

### v4: the reference is settled per feature, and one prior claim is withdrawn

A prior revision said `tsd`'s coverage "is not derivable by any sentinel
test" and that the Earth Engine footprint was unobtainable — which left
this CR circular at its operative step. Research resolved it. **No Earth
Engine run and no re-fetch is required.**

**`tsd` coverage IS derivable, and the claim that it was not was wrong.**
Every disturbance vintage ships `CSV_Data/LF20xx_Distyy.csv`, a value
attribute table, alongside `Spatial_Metadata/conus_0k.shp` /
`conus_90k.shp`. All 26 tables declare `-9999` and `0`; **6 of them** (`LF2020_Dist17-20`, `LF2022_Dist21-22`) also declare `-1111`; **none** declares `32767` or `-32768`:

```
VALUE, DIST_YEAR, DIST_TYPE, ...
-1111, 2017, Fill-Not Mapped ...
-9999, 2017, Fill-NoData ...
    0, 2017, NA ... Background        <- COVERED and undisturbed
   11, 2017, Fire, High ...
```

`32767` and `-32768` appear in **no** table — the GeoTIFF nodata tag is
simply wrong and inconsistent between vintages. Note also that the VAT
schema itself differs by vintage (`VALUE,YEAR,DIST_TYPE,SEVERITY,…` in
LF2001 against `VALUE,DIST_YEAR,DIST_TYPE,TYPE_CONFIDENCE` in LF2023),
so a table-reading implementation must handle **three**: `LF2024_Dist24` is `VALUE,FISCAL_YR,CALENDAR_YR,DIST_TYPE,…` and its header carries a **UTF-8 BOM** (`'\ufeffVALUE'`), so `df["VALUE"]` raises `KeyError` under default encoding. All four out-of-coverage
codes are **already** in `grouse_data.NODATA_SENTINELS`.

**Two vintages do map genuine out-of-US ground, and the intersection
excludes them by design.** Measured on the ME grid: `Dist23` carries
**504,222 px** and `Dist24` **480,563 px** of real disturbance codes
outside the US (≤27 px in every other vintage), because those two
releases map LANDFIRE's 90 km buffer. A separate 9,071,546 px read
`32767` — a fill code that happens to be positive, and which an earlier
revision conflated with the above. Both statements are now stated
separately because v4 asserted the first was "a misreading" and then
restated it as true two sentences later; the measurement says it is
true, and the 90 km buffer is excluded deliberately by taking the
intersection over vintages.

Derived footprint, as the intersection over consulted vintages — and
**`cov_2016` and `cov_2025` are byte-identical by SHA-256**, so one
reference serves every output year:

| region | **inside**-coverage fraction | outside-coverage fraction |
|---|---|---|
| ME | 0.527061 | **0.472939** |
| NH | 0.900714 | **0.099286** |
| VT | 0.959960 | **0.040040** |

**Both columns are stated because v4 shipped this table with the inside
fraction under an "outside" heading** — the exact complement of G0's
pre-registered values. An implementer building the mask from it would
have blanked 52.7 % of ME, 90.1 % of NH and 96.0 % of VT. The outside
column is the operative one and matches G0. Sanity check for any future
reader: New Hampshire is wholly within CONUS, so only ocean and Canada
are uncovered — an outside fraction near 0.90 is impossible on its
face.

**Per-feature reference, settled:**

| feature | reference | why |
|---|---|---|
| `road_dist` | **TIGER county union** (`all_touched=True`, as the generator rasterises) | exact; already cached |
| `tsd` | **disturbance-stack intersection** | source-authoritative and free |
| `balive`, `tpa_live`, `qmd`, `carbon_dwn` | **NLCD valid footprint** | no alternative exists, and nothing is lost — measured below |
| `tcc` | **NLCD valid footprint** | not a fallback: `tcc` **is** NLCD Tree Canopy Cover, so this is its product-authoritative footprint. Proof: its outside-footprint `>0` count is **exactly 0** in all three regions |
| `evt`, `evh`, `evc`, `sclass`, `fdist`, `ch`, `cc`, `nlcd` | **out of scope** | see below |

**What using NLCD costs for TreeMap and `tcc`, measured at full
resolution.** Pixels reading `>0` outside the NLCD footprint: TreeMap
ME **11,700** / NH **4,464** / VT **2,137** — of which **100 % lie
within 3 px of the boundary**, in components whose largest is **13 px**.
That is TreeMap's own nearest-neighbour reprojection smear along the
coast and border, not coverage NLCD lacks. For `tcc` the count is
**exactly 0** in all three regions. In the reverse direction, `nodata
inside the NLCD footprint` is **0** for all five products. A zero
outside the footprint carries no information either way.

**Why NLCD is NOT used for `tsd`:** it would leave **97,560 ME pixels**
fabricated ("undisturbed 30 years" over Penobscot Bay, which the
disturbance record genuinely does not cover) and blank 12,447 px the
record does cover. LANDFIRE does not map large estuarine water; NLCD
does. Both are inside the cross-check budget, but the per-generator
reference is free and strictly better.

**Why LANDFIRE vegetation channels are out of scope, explicitly.**
Applying NLCD to them would blank **52.1 M ME pixels (25.6 %)** of
genuine LANDFIRE mapping: LANDFIRE's 90 km zone buffer really does map
southern Québec and New Brunswick, and the outside-NLCD `evt` values are
the full vegetation vocabulary (7555, 7755, 7302 …), the same codes as
inside. They already carry correct nodata. **PA-0017's Swept? cell
records "LANDFIRE none", which is right in effect but reached without
this evidence — correct the cell to record it.**

**Cross-check, replacing the asserted 0.05 % budget.** Three
*independent lineages* — USGS raster (NLCD), Census vector (TIGER
polygons), LANDFIRE tabular metadata (the disturbance value tables) —
agree on the outside fraction to **0.00059 (ME) / 0.00012 (NH) /
0.00007 (VT)**, i.e. ≤0.06 % of grid. That measured agreement is the
budget. The prior 0.05 % figure was asserted, and its calibrating
measurement ("0.006–0.008 %") reproduces only under `all_touched=False`,
the option the generator does **not** use; at `all_touched=True` ME is
**0.0182 %**.

**Two corrections to figures this CR previously stated:**
- "18.4 % of `tcc`'s zeros are real 0 % canopy inside the US" — at full
  resolution the in-footprint share of `tcc == 0` is **ME 11.0 %,
  NH 22.6 %, VT 44.3 %**. The conclusion holds a fortiori; the scope was
  misstated.
- `evt` carries **84,675 ME px of nodata inside the NLCD footprint**, so
  **no candidate mask is a superset of the others** and the cross-check
  must be stated in both directions.

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
- Cost: **174** in-scope files, ~9 GB of int16 I/O, local CPU, minutes.
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
  disturbance recorded" with "not covered". **Derive coverage as
  `value ∉ grouse_data.NODATA_SENTINELS`, intersected over the vintage
  list pinned in G0** — *not* from the declared GeoTIFF nodata tag,
  which reads `32767` everywhere except `LF2022_Dist22` (`-32768`) and
  is wrong: neither value appears in any of the 26 value-attribute
  tables. All four out-of-coverage codes are already in
  `NODATA_SENTINELS`.

  **A prior revision instructed the opposite here** — "coverage is not
  derivable by any sentinel test" — which survived into v4's deliverable
  after § Coverage had withdrawn it. It is withdrawn here too. G0's
  pinned `disturbance∩` mask *is* derived by exactly this sentinel test;
  that is how a reviewer reproduced its digest byte-for-byte. An
  implementer who followed the withdrawn instruction would have reached
  for NLCD instead, leaving **97,560 ME px** fabricated over Penobscot
  Bay.

  **Do not** reuse `:312-314`'s `hit` (`arr > 0 and arr != nodata`): a
  covered, undisturbed pixel has value 0 and would be masked, destroying
  the **81–93 %** of training centre pixels that legitimately read
  `TSD_MAX_YEARS`.
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
- **Measured effect on CR-0007's record set (v7 — was previously asserted,
  now measured on the faithful sampler).** An independent investigation
  reproduced all nine G0 masks byte-for-byte, then measured this CR's
  effect on the record set CR-0007 builds:
  - **The candidate pool moves by 2 records**, 22,201 → 22,199. Both are
    ME, both marine GBIF points in the Gulf of Maine —
    `(-68.12830, 43.96860)` and `(-67.10082, 44.501766)`, the latter being
    the single record § G5 already names. **0 positives** are affected in
    any region.
  - **`generate_negatives.py`'s extraction `dropna` cannot be changed by
    this CR at all.** It reads `['evh', 'evt', 'sclass']` (from
    `ENVELOPE_SCHEME` ∪ `{sclass, evt}` at `:196-207`); all three are
    **out of scope** (see § Scope's table). The intersection with this CR's
    seven in-scope features is **empty**. The hypothesis that this CR might
    mechanically strip northern candidates and so create a negative-supply
    defect is therefore **refuted**, and the asymmetry in fact runs the
    other way: positives are filtered on a strict *superset*
    (`['evt','evh','evc','sclass','ch','cc']`).
  - **Exactly one CR-0007 acceptance row reads a raster this CR rewrites:
    I17** (`ks_feat_max`, 7 of its 9 features in scope). **6 of the 7 are
    provably bit-identical at the records**: the count of positives whose
    centre pixel lies outside that feature's own G0 reference is **0 in ME,
    0 in NH, 0 in VT**, every feature — so their sampled values, and hence
    their KS terms, cannot change. `road_dist` ME/VT is the only real
    change and it moves **4 of 3,659 ME positives**, all within 5 km of a
    state line. I17's maximum over 200 split seeds moves
    **0.0696 → 0.0671** against a `≤ 0.095` gate (27 % headroom), and
    `road_dist` becomes the argmax feature in 50/200 seeds instead of
    39/200.
  - **Window-level exposure is real but record-neutral, and ME-only.**
    Candidates with any out-of-coverage pixel in the 64×64 window, worst of
    the three references: ME 94/11,407 (83 of them in the northern 15 %
    band, a 4.1× rate over positives), NH 7/5,220, VT 16/5,574 — but
    **zero centre-pixel losses** in the band for either class. The effect
    is information loss over part of a receptive field, not supply loss;
    no record is removed.

  **Consequence for landing order.** "Independent of CR-0007 and may be
  landed in either order" is now *measured*, not asserted. One addition is
  warranted: **I17 must be re-measured — not re-thresholded — by whichever
  CR lands second**, in exactly the form § G5 already uses, because its
  argmax feature changes even though its threshold does not. See § G5.
- **The repair cannot newly trip the training-time geolocation probe.**
  `dataset.py:264`'s `_probe_first_point` reads `(cat_features +
  cont_features)[0]`, which is `evt` by `RASTER_FEATURES` spec order —
  **out of scope**. This is the training-time analogue of the `predict.py`
  `cat_np[0]` exposure above, and unlike that one it is unaffected.
- **Not affected:** record membership, splits, model architecture.

## Risk level: **MEDIUM**

| risk | mitigation |
|---|---|
| A naive `tsd` fix destroys 81–93 % of the channel. | § Coverage mask — **derived by the `∉ grouse_data.NODATA_SENTINELS` test over the vintage intersection**, which is exactly how G0.3's pinned `disturbance∩` digest is built. **Not** `:312-314`'s `hit` (masks legitimate 0 = undisturbed) and **not** NLCD (leaves 97,560 ME px fabricated). The "nodata inside coverage" direction of the acceptance check catches it. |
| A negative sentinel is silently clamped back to 0 by `_clean:261`, producing a no-op regeneration that reports success. | Named explicitly above; the acceptance check is evaluated on the **per-region derived rasters the model reads**, not the raw downloads. |
| An interrupted TIGER download poisons the cache permanently. | `_download` atomicity fixed before any regeneration. |
| The post-process overwrites the only copy. | Full raster backup before step 1; temp-file-then-rename within it. |
| A coverage gate fails on already-correct data and gets waived. | Per-generator reference plus the **measured** three-lineage cross-check budget (≤0.06 % of grid), per direction per feature per region. The prior asserted 0.05 % figure is withdrawn. |

## § Acceptance — measured, full resolution

**v3 inverts the acceptance design.** v2 enumerated outcomes that must
not occur (no fabricated value outside coverage; zero counts unchanged;
`tsd` saturation unchanged). A reviewer broke that set four ways, and
the reason is structural: a blacklist can only forbid the failures its
author thought of. v3 instead **constrains what may change**, which is a
whitelist and is closed by construction.

### G0 — pin the mask (v4, and the reason the earlier set was vacuous)
Both G1 and G2 read the coverage mask. A reviewer proved that when the
gate's mask equals the repair's mask — which it will, since the CR gives
one definition per generator — **G1 ∧ G2 hold identically for any mask
whatsoever**, correct or not. Measured: derive the mask at 16× and
upsample it, and the repair passes G1 (0 violating px), G2 (exactly
1.000000), G3, G6 **and** the cross-check budget in both directions,
while destroying 93,986 genuine in-US readings and leaving 100,877
fabricated ones *per file per year*. Set the mask to the whole grid and
the repair becomes a no-op that passes both vacuously.

G3 ("full resolution is mandatory") was added to close the earlier
aliasing break. It constrains the resolution of the **measurement**, not
of the **mask derivation**, so it does not close it.

**G0, per (feature, region):**
1. The mask is derived at **native resolution** by rasterising the named
   source onto the raster's own `transform` and `(height, width)` — never
   upsampled from a coarser lattice, and with `all_touched` stated.
2. It is a **persisted, checksummed artifact**, not an in-flight
   intermediate: publish `sha256(np.packbits(mask.ravel()))` and the
   inside-pixel count, and require the implementation to reproduce both.
3. The verifier **recomputes it independently of the repair** and the two
   digests must match.
4. **Each row carries its exact source list and predicate**, because a
   digest nobody can reproduce next month gets waived:
   - `nlcd` — `{REGION}_{year}_nlcd.tif`, predicate `!= -9999`. Verified
     year- and recipe-invariant: all 10 years give the identical digest.
   - `tiger_at1` — `data/roads/tl_2023_us_county.zip`, counties
     intersecting the grid bbox, `all_touched=True`. Verified
     insensitive to pad and densification of the selection footprint;
     sensitive **only** to `all_touched`.
   - `disturbance∩` — the **26 named vintage files** (Dist99–Dist24 as
     present today), predicate `value ∉ NODATA_SENTINELS`, intersected.
     This digest changes when LANDFIRE publishes a new vintage, since
     the generator's usable set is everything on disk — so the file list
     is part of the pin, not an implementation detail.
     **Pin each vintage by content hash, not by name (v6).**
     `data/disturbance/` holds **two byte-identical extractions** of the
     same bundle (§ Disk), and they are not interchangeable to a reader:
     `fetch_disturbance`'s `p > found[y]` path sort selects the **nested**
     copy, while every reproduction script written against this CR so far
     — the author's and two reviewers' — globs the **outer** one. They are
     md5-identical today (spot-verified on `LF2016_Dist15`), so no
     measurement is in doubt; but this CR simultaneously proposes
     reclaiming the nested 15 GB, after which a name-only pin becomes
     ambiguous about which copy it meant. Content hashes remove the
     ambiguity.

   **G0.4 — re-verification trigger, not just a digest change (v6).**
   "One reference serves every output year" is **empirical, not
   structural**: `generate_time_since_disturbance.py:303-316` folds in
   only the vintages with `d ≤ Y` when emitting output year Y, so the
   *correct* coverage for year Y is the intersection over `d ≤ Y`, not
   over all 26. A single pinned digest is therefore legitimate only while
   those intersections coincide. They do today — a round-6 reviewer
   computed both ends and found `cov(≤2016, 18 vintages)`
   **byte-identical** to `cov(≤2025, 26 vintages)` for all three regions,
   digest for digest (the reason being that Dist23/24's 90 km buffer is a
   superset). So: **whenever a vintage is added, re-verify
   `cov_minyear == cov_maxyear` and re-pin — do not merely note that the
   digest changed.** If they ever diverge, the single pin becomes wrong
   for the early years and a correct implementation would *fail* G0.

**Which clause does the work.** G0.2 — the digest and inside-count
published as literal constants in this document, *before* implementation
— is what closes the aliased-mask and whole-grid attacks: it is an
anchor external to the implementation, which is what was missing. G0.3
adds little against those two, because the repair and the verifier run
the same derivation and would agree on a wrong mask as readily as a
right one; it catches a bookkeeping slip (verifier using a different mask
than the repair applied) and is kept for that. **Do not drop the
pre-registration as redundant with the recomputation.**

**Residual, corrected in v5.** v4 stated the cause wrongly and proposed
a mitigation with no power. The three lineages do **not** share a code
path: `nlcd` is index-for-index (no rasterisation, no resampling),
`tiger_at1` is a vector rasterisation, `disturbance∩` is a WarpedVRT
reprojection from EPSG:5070. The real exposure is a per-lineage
registration shift, measured:

| displaced mask | worst disagreement vs `nlcd` | cross-check ≤0.06 % | boundary-px count |
|---|---|---|---|
| ME `tiger` +1 px | 0.0149 % | **passes — undetected** | 45,688 vs 45,689 |
| ME `dist` +1 px | 0.0515 % | **passes — undetected** | 49,842 vs 49,843 |
| ME `dist` +½ px | 0.0473 % | **passes — undetected** | 49,833 vs 49,843 |

An undetected ME `dist` shift misclassifies **37,843 px per file**
across 10 `tsd` files. v4's proposed mitigation — a pre-registered
boundary-pixel count — moves by **1 px in 45,689** under a whole-pixel
shift: no power whatsoever. Withdrawn.

**G0.2's digest is the only registration check**, and it does catch all
three (verified by a second independent implementation). The
three-lineage budget must **not** be presented as an independent check
of registration. Note also that ≤0.06 % is a **fitted** threshold — the
observed ME maximum is 0.0590 % (`tiger`-vs-`dist`, 120,177 px), leaving
1.7 % headroom.

Pre-registered values (full resolution, measured):

| region | reference | inside px | outside frac | sha256 (first 32) |
|---|---|---|---|---|
| ME | `nlcd` | 107,406,613 | 0.472521 | `59a7639b5fb0389d0955eb61e45ad3fc` |
| ME | `tiger_at1` | 107,441,621 | 0.472349 | `22a9995e0b920e81c205a962e7e64237` |
| ME | disturbance∩ | 107,321,500 | 0.472939 | `9006374548fa58f4a59e3ff14c24130d` |
| NH | `nlcd` | 51,384,193 | 0.099210 | `15375b62cca9ab85ec4c23869218a6d7` |
| NH | `tiger_at1` | 51,386,748 | 0.099165 | `1a29cc5bc79b7d4c73dc49e4fb9ac93a` |
| NH | disturbance∩ | 51,379,852 | 0.099286 | `c10c46f12978de0e68fd1ded93b65a84` |
| VT | `nlcd` | 50,450,696 | 0.039973 | `682ef390d584a2a7b30b3eed10c75e15` |
| VT | `tiger_at1` | 50,450,367 | 0.039980 | `52e5049c360a5143146ac1342d4177f8` |
| VT | disturbance∩ | 50,447,193 | 0.040040 | `64677a7523a8b20e24f1e595dbf8c39a` |

**The prior "independent" reference was circular and is withdrawn.** v3
proposed pairing the whitelist with "the expected outside-coverage
fraction stated independently (ME ~0.4725, NH ~0.0992, VT ~0.0400)".
Those are *exactly* the NLCD nodata fractions, to six decimals. Pairing
a gate with its own input adds nothing.

### G1 — the change-set invariant
> **`set(pixels whose value changed) ⊆ set(pixels outside that
> generator's coverage)`**, verified at **full resolution** against the
> checksummed backup, per file, per feature, per year, per region.
> Reported as a count of violating pixels; **required 0**.
> `road_dist` ME/VT is the one exemption — it changes in-coverage values
> by design (that is the BUG-0023 fix) and is gated by **G7 (RD1–RD5)**
> instead. **Not by G2**: G2 constrains only the outside→nodata
> direction and provably cannot gate in-coverage values. v5 said "G2"
> here and "G7" at the revision note and G2′ — the contradiction is
> resolved in favour of G7.

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

### G2 — coverage is actually applied (restated as a **count** in v6)
> **`count(pixels outside that generator's coverage whose value is not
> the file's declared nodata) == 0`**, per feature, per region, per year,
> **full resolution**, against the generator's own reference.

**Why a count and not v5's "fraction, required exactly 1.0000".** At four
decimal places a fraction admits ≥0.99995 — **4,809 fabricated ME
`road_dist` pixels per file**. For `tsd`/TreeMap/`tcc` that budget is
closed anyway by G2′'s `|changed| == N_pre` equality, but **`road_dist`
is exempt from G2′**, so on the one feature this whole investigation is
about the budget was live. Corroborated by measurement: a 3-pixel
under-mask scores 0.99999997, which *rounds to* 1.0000 and passes. A
pixel count cannot round. This is the same units-and-precision mechanism
that broke v2's "≥0.99 in the wrong units"; stating the gate in the units
of the defect (pixels) is the fix.

**"Nodata" means the file's declared nodata** (`src.nodata` = `-9999`),
not "any member of `NODATA_SENTINELS`". v5 never said which, so a
sentinel-set reading would pass while contradicting the `nodata=-9999`
tag G6 preserves. In-repo consumers were traced — `dataset.py:273,325`,
`dataset._read_patch`, `train.py:142`, `realign_rasters.py:79`,
`predict.read_window_stack:250-252` all handle the whole sentinel tuple
or read `src.nodata` — so in-repo damage from a wrong sentinel is **nil**;
only external GIS and `read(masked=True)` would mis-render. Specified for
determinacy, not because a break was demonstrated.

**G2 is one-directional by construction, and that is its limit.** It
constrains only the *outside → nodata* direction, so a nodata set that is
a **superset** of outside-coverage satisfies it *a fortiori*. The
opposite direction — nodata appearing *inside* coverage — is carried by
G1 (`changed ⊆ outside`) for every feature **except `road_dist` ME/VT,
which is exempt from G1 and G2′ both**. That was v5's live gap; it is
closed by **RD5** in G7, not here.

**Determinacy of the repair core.** For `tsd`/TreeMap/`tcc`, G1 ∧ G2′ ∧ G2
determine the repair **uniquely**: `changed ⊆ outside`,
`|changed| = N_pre = #(outside ∧ ¬sentinel_before)`, and all outside must
end nodata ⟹ `changed` *is* exactly that set. Re-writing an
already-sentinel outside pixel to a *different* sentinel pushes
`|changed| > N_pre` and fails G2′. A round-6 reviewer derived this
independently; it is why the 174-file core survived seven attacks.

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
on VT it was *stricter* than intended. The prior 0.05 %-of-grid figure is **withdrawn entirely** — it was
asserted, and its calibrating measurement reproduces only under
`all_touched=False`, the option the generator does not use. The
cross-check tolerance is the measured three-lineage agreement:
**≤0.06 % of grid**, per direction, per feature, per region.

### G2′ — exact must-change equality (v4)
G1 is a **subset** test, so a repair that changes nothing satisfies it.
Paired with G0 and a pre-registered count it becomes set equality: for
each file, `|changed| == N_pre` **and** `changed ⊆ outside-coverage`. A
no-op then fails G2′ and an inflated mask fails G0.

**`road_dist` ME/VT is exempt from the conjunction**, for the same reason
G1 exempts it: the regeneration changes in-coverage values by design, so
`|changed| ≫ N_pre` and `changed ⊄ outside-coverage`. Applying G2′ whole
would fail the *correct* outcome. For `road_dist` the N_pre row is a
**nodata-transition count, diagnostic only**; its in-coverage values are
gated by G7 instead.

`N_pre`, measured full-resolution against each feature's own reference:

| feature | ME | NH | VT |
|---|---|---|---|
| `tsd` (per year) | 96,300,932 | 5,663,604 | 2,104,152 |
| `balive`/`tpa_live`/`qmd`/`carbon_dwn` (each, per year) | 96,215,819 | 5,659,263 | 2,100,649 |
| `tcc` (per year) | 95,946,265 | 5,653,164 | 2,096,352 |
| `road_dist` | 96,180,811 | **0 (already correct)** | 2,100,978 |

`nodata inside coverage` is currently **0** for every in-scope
feature-year, so the over-masking direction starts from a clean zero.
For `road_dist` specifically — the one feature exempt from both G1 and
G2′ — that zero is what **RD5** gates: measured on all 30 files, ME and
VT carry exactly 0 nodata and NH's nodata set *is* the `tiger_at1` mask
(5,656,708 px = 0.099165, matching the pinned outside fraction to six
decimals).

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
   of one raw band at **recorded pixel coordinates that lie INSIDE
   coverage**, asserting on **the output value at exactly those pixels**
   (required: nodata, not `0.0`).

   **v5's instrument had no power over what it tested.** It said "and
   **G2** evaluated on that output" — but G2 measures the
   *outside-coverage* nodata fraction, and a sentinel injected at
   in-coverage pixels does not move it at all. The `_clean:261`
   (`a[a < 0] = 0.0`) defect is an *in-coverage* value defect, so the
   assertion must be at the injection sites. Where the injection goes is
   part of the test specification, not left to the implementer.

### G5 — training-window impact, on the final record set
Count of training records with any out-of-coverage pixel in a 64×64
window, and with an out-of-coverage centre pixel.

**G5 is order-independent (fixed v6 — v5's disposition claimed this and
its text did not do it).** v5 said "**Measured on the record set CR-0007
produces, not the current one**", which makes G5 *unmeasurable* if
CR-0008 lands first — while this CR's header says the two may land in
either order. The round-5 disposition recorded "Accepted — G5 assigned to
whichever CR lands second", but G5's text was never changed. It is
changed here:

> **G5 is measured on whichever record set exists when this CR lands, and
> re-measured by whichever of CR-0007/CR-0008 lands second. The same
> hand-off covers **CR-0007's I17**, for the reason given in § Impact:
> it is the one CR-0007 row that reads a raster this CR rewrites, and its
> argmax feature changes even though its threshold (≤ 0.095, 27 %
> headroom) does not.** If CR-0008
> lands first, the "before" and "after" are both on the current set, and
> CR-0007 re-runs G5 on the set it produces. Neither reading is
> substituted for the other, and each records which set it was taken on.

v2's error was different and remains withdrawn: it measured the current
set and reported it *as* the post-CR-0007 figure.

Today, against the NLCD footprint: ME **23 train + 4 val** negatives with
some nodata in-window (v2 said "27 … train"; it pooled train and val),
18 + 4 above 10 %, and **one val negative at 100 % whose centre pixel is
out of coverage** — `(-67.10082, 44.50177)`, `val_negatives_ME.csv`.
That is CR-0007's second known exception, it is a **validation** record,
and CR-0009's validation baseline is computed on it. Its disposition is
CR-0007's; this CR records the dependency.

### G6 — grid identity, **full profile** (widened in v5)
v4 checked transform, width, height, CRS, dtype and nodata — which is
**exactly the set an implementer passes to `rasterio.open(..., "w")` by
hand**, and therefore exactly the set a naive rewrite preserves. The
fields it omitted are the ones such a rewrite drops:

```
174 in-scope files, compressed on disk : 9,021 MB
same files as uncompressed int16       : 36.3 GB
free space                             : 16 GB, less the 10.19 GB backup -> ~6 GB
```

A repair that loses `compress="deflate"` therefore aborts on ENOSPC
after roughly 15–20 ME files, with an unknown number of originals
already replaced — and v4's G6 would report "identical". `blockxsize`
also differs by feature today (128 for `balive`, 256 for `tcc` and
`road_dist`), so a uniform profile silently re-tiles every file.

**G6 compares the full `rasterio` profile dict against the backup's**,
per file, **plus `src.tags(ns='IMAGE_STRUCTURE')`**. Plus a post-repair
total-size check: ≤ ~1.2× the backup.

**Why the tags are needed (round 6).** `rasterio`'s profile dict does
**not** contain `predictor`, while every in-scope file carries
`IMAGE_STRUCTURE PREDICTOR=2` — verified: the profile keys are
`blockxsize, blockysize, compress, count, crs, driver, dtype, height,
interleave, nodata, tiled, transform, width`, and the tag namespace
returns `{'COMPRESSION': 'DEFLATE', 'INTERLEAVE': 'BAND', 'PREDICTOR':
'2'}`. So v5's "full profile dict" was **still** "exactly the set an
implementer passes to `rasterio.open(..., 'w')`" — the same criticism v4
received, one layer out. `zlevel`, `BIGTIFF` and `SPARSE_OK` are in the
same class.

**Measured consequence is benign, and it is recorded as such rather than
inflated:** dropping `PREDICTOR` makes the repaired files *smaller*
(0.70× / 0.93× / 0.69×), because the masked constant region deflates
better without it — so the ENOSPC scenario does **not** materialise and
the ≤1.2× check is never touched. This is a correctness-of-claim fix, not
a data-loss fix.

### G7 — `road_dist` in-coverage values (v4; **RD5 added v6**)
G1 exempts ME/VT `road_dist` because it changes in-coverage values by
design, which left **52.75 % of the ME grid gated by nothing** — on the
feature this whole investigation is about. v3 deferred to a test-plan
"spot-check" with no threshold.

**A median or p95 gate on a uniform sample is vacuous.** Measured
against the *broken* ME raster currently on disk:

| statistic | correct NH | broken pre-fix NH | **broken current ME** |
|---|---|---|---|
| uniform median abs err | 10.2 m | 2,352 m | **10.9 m — PASSES** |
| uniform p90 / p95 | 22.7 / 25.6 m | 31,369 / 37,670 m | **26 / 36 m — PASSES** |
| interior median / p95 | 10.5 / 26.2 m | 17 / 45,747 m | **9.4 / 27 m — PASSES** |
| state-line median | 10.2 m | 593 m | **367 m** |
| grid-edge median | 9.2 m | 23,859 m | **11,699 m** |
| frac(abs err > 60 m) | **0 / 2000** | 0.330–0.963 | 0.007–0.998 |

Only the state-line and grid-edge strata and the exceedance fraction
separate. **Truth** = exact `shapely` STRtree distance to the nearest
paved TIGER-2023 road (same MTFCC list and vintage as the generator; no
densification — a segmentised KD-tree biases truth up ~7.5 m).
**Sampling** = 400 points per stratum, seed pinned, 5 strata: uniform;
interior (>5 km from coverage edge, other-state line and grid edge);
within 5 km of a land boundary with another US state; within 10 km of
the grid edge; within 5 km of the coverage boundary.

Per region, per stratum, on the regenerated raster:
- **RD1** median |err| ≤ **20 m**
- **RD2** p99 |err| ≤ **60 m**
- **RD3** `count(|err| > 60 m) == 0`
- **RD4** median signed err in **[−20, +5] m** — the correct raster reads
  systematically low (−7.2 to −9.2 m) because `all_touched=True` widens
  each road
- **RD5 (added v6) — the other direction:
  `count(pixels inside the pinned G0 tiger_at1 mask whose value is the
  declared nodata) == 0`**, full resolution, per file. See below.
- **Gated, not reported: the excluded-point count == 0.** v5 filed this
  under "reported, not gated", which is precisely what made RD1–RD4 blind
  to over-masking.
- Reported, not gated: per-stratum truth/raster medians, max |err|

**Why RD5 exists (round-6 blocking finding).** `road_dist` ME/VT is
exempt from G1 **and** from G2′, and G2 is one-directional, so **nothing
in v5 constrained where `road_dist`'s nodata went.** An over-masking
repair — e.g. the coverage rasterisation run at `all_touched=False`
instead of `True`, and G0's own recipe table names `all_touched` as the
single parameter the mask is sensitive to — passes **G0** (which pins the
*verifier's* mask, never the artifact's), **G2 at exactly 1.000000**
(superset of outside-coverage), G3, G6 and G8, while destroying
**32,560 ME + 3,287 VT legitimate in-US pixels per file × 10 year-copies
= 325,600 ME + 32,870 VT** destroyed readings.

**RD1–RD4 have detection probability 0 against it**, structurally: the
over-masked pixels read nodata, so `|err|` is uncomputable at them and
any implementation excludes them — which v5 then declined to gate. Even
*without* exclusion, every over-masked pixel lies in stratum 5 ("within
5 km of the coverage boundary", population 7,673,995 px in ME), so 400
draws miss it with probability **0.1825 (ME) / 0.2645 (VT)** — measured,
not estimated.

**RD5 starts from a verified zero, so it cannot false-fail.** Measured on
all 30 `road_dist` files on disk today: ME and VT carry **exactly 0**
nodata pixels (the pre-fix rasters have none at all), and NH carries
**5,656,708 = 0.099165** of its grid, which equals the outside-TIGER
fraction to six decimals — i.e. NH's nodata set **is** the `tiger_at1`
mask, 0 in both directions. Any nonzero RD5 reading is therefore a
regression introduced by the repair, never a pre-existing condition.

**The gap RD5 closes is unconditional.** The `all_touched=False` route
requires an edit nothing in this CR asks for, so that *particular*
perturbation is of moderate-low likelihood; but the missing constraint
admits **any** over-masking route, and this CR asserts the
no-new-in-coverage-nodata direction for every feature *except* the one
where the whole-conjunction exemption silently dropped it.

**Preconditions on the 60 m derivation below.** (i) The encoding term is
a *sample max*, not a bound: `road_dist_encode` is
`rint(log1p(m)·1000)`, so the half-unit error is `0.5·(1+d)/1000` m —
3.4 m at 6.9 km, 7.9 m at 15.7 km, 25 m at the 50 km cap. The bound is
properly `42.43 + 0.5(1+d)/1000`, which stays under 60 m only for
`d ≲ 35 km`; observed in-coverage max truth is 12–16 km, so RD3 is safe
**as a stated precondition**, not as an unconditional bound. (ii)
"In-coverage" means **inside the pinned G0 mask**, not `arr != NODATA` —
the pre-fix ME raster has zero nodata, and sampling `arr != NODATA`
gives uniform p90/p95 of 23.7 km / 41.6 km, figures unrecognisable
against the table above.

**60 m is derived, not fitted.** The EDT measures pixel-centre to
nearest road-marked pixel centre, so the recorded value can under-read by
the line's in-pixel offset (≤ half-diagonal 21.2 m) plus the sample
point's own offset from its pixel centre (≤ 21.2 m), plus log1p encoding
(measured max 2.94 m). Deterministic bound ≈ 45 m; observed max over
2,000 correct points **38.9 m**, flat across every distance bin out to
6.9 km. So RD3's zero false-fail rate is **structural, not a sampling
accident** — corroborated by 10,000-resample bootstraps at n = 100/200/400
per stratum, all `P(breach) = 0.0000`.

**Preconditions on the truth source (renamed v6 — v5 had two separate
paragraphs both headed "Two preconditions", i.e. four preconditions under
one label, inside a gate spec).**
1. The gate must pin the same TIGER **vintage** and **MTFCC list** as the
   generator — `TIGER_YEAR` is still `2025` at
   `generate_road_distance.py:114` while every cached file is 2023, so a
   mismatch would produce real-looking failures.
2. **The truth's road set must be every TIGER county intersecting
   grid + `pad_km`, never `STATE_FIPS[region]`.** v5 pinned vintage and
   MTFCC but left the roads' *spatial extent* unstated — which is the
   exact PA-0018 mechanism this project has already logged twice
   (BUG-0023, BUG-0026). A verifier built from the region's own state
   would **reproduce BUG-0023 inside the gate** and false-fail the
   state-line stratum, which is precisely where this CR's own table puts
   the discriminating signal (broken NH state-line median 593 m against
   RD1's 20 m). The gate would then report the *fix* as the defect.
3. The 8 uncached VT counties must be fetched before VT's truth is
   computable at all.

**Exception class, measured empty.** A point whose nearest road lies
outside grid + `pad_km` is legitimately over-read; checked directly,
**0 of 2,000 in NH and 0 of 2,000 in ME**. No carve-out needed. Max truth
distance NH 6,864 m / ME 15,701 m, nowhere near `ROAD_DIST_MAX_M`.

### G8 — the repair actually reaches the model (v5; corrected v6)
Closes the cache break above. After the repair, per region:

**G8.1 — the purge happened: `count(data/cache/patches_*) == 0`.**
Glob on **`patches_*`, with no extension anchor.** v5 wrote
`patches_*.npy`, which **passes today with a live 379 MB artifact on
disk**: `data/cache/patches_61055cdd3521daef.npy.tmp6337`
(379,453,568 bytes, dated Sep 29 12:50) does not match that glob. The
true inventory is **206 `.npy` + 1 `.tmp`**, which is also where § Disk's
"207 `patches_*.npy`" came from — the temp file miscounted as a patch
cache. The consequence is disk, not correctness
(`_load_or_build_cache` only `os.path.exists()`-checks the final path) —
but § Disk's entire premise **is** disk contention, so the miscount
matters there.

**G8.2 — the replace did not preserve metadata: every repaired file's
mtime must differ from the pre-repair mtime recorded in the backup
manifest.**

v5 said "strictly greater than its **backup's** mtime". That is
*sufficient* against the defect, but only by an argument v5 never made,
and it is stated against the wrong reference:
- If the backup preserves mtime (`cp -a/-p`, `rsync -a`, `shutil.copy2`,
  `tar -p`), backup mtime = T₀ and the check is exactly "mtime advanced".
- If it does not (plain `cp`, `shutil.copy`, reflink), backup mtime
  = T_b > T₀, so the check is *stricter* than needed — still catches it.
- A pass with an unchanged mtime would require `repaired == T₀ >
  backup_mtime`, and **a backup can never be older than its source**.
  So v5's form does hold — for a reason that is a property of backups,
  not of the check.

Stated instead against **§ Disk's already-required backup manifest
record of each file's pre-repair mtime**, it is self-evidently right and
needs no such argument. **Note the limit:** G8.2 is **unevaluable for an
archive-format backup** (`tar`/`zip`), which § Disk's "separate inode set
+ manifest hashes" otherwise permits, because there is no per-file
`st_mtime` to compare — so the manifest must record mtimes explicitly,
and that is now a § Disk requirement, not an assumption.

**The forbidden-idiom clause is stated as a mechanism, not a list.**
v5 enumerated `shutil.copystat`, `cp -p`, `rsync -a` — an enumeration
that misses `shutil.copy2`, `shutil.copytree`,
`cp --preserve=timestamps`, `tar -p` and `os.utime`. **`shutil.copy2` is
this codebase's own idiom for fanning a raster across years**
(`generate_treemap_features.py:444`, which produces 36 of the 40 TreeMap
files per region), so the obvious and ~10× cheaper repair — repair year 1,
`copy2` onto the other 9, mirroring existing code — was *not* on v5's
list. It happens to pass G8.2 because its source is fresh, so it is not
itself a break; but the clause as drafted did not cover the idiom an
implementer is most likely to reach for. **The rule is therefore: the
repaired file's mtime must differ from the manifest's recorded pre-repair
mtime — by whatever route, and no idiom is exempt because it is absent
from a list.**

**G8.3 — no stale derived artifact is published between this CR and
CR-0009.** G8 is titled "the repair actually reaches the model", and
`data/cache` is **not** the only thing fitted on pre-repair rasters:
`data/calibration/calibration.json` and the six
`data/predictions/*.{tif,kmz}` are too. The retrain is correctly routed
to CR-0009, but nothing in v5 forbade **publishing a prediction between
CR-0008 and CR-0009** — i.e. re-rendering exactly the Errol map this
investigation began with, now stale-but-plausible, from repaired rasters
under a checkpoint and a calibration fitted on fabricated ones. No
prediction or calibration artifact may be published until CR-0009 lands;
the existing ones are marked stale on this CR's completion. (Dovetails
with `DRAFT_BUG-0028`, which is why provenance is unrecoverable from the
artifacts themselves.)

**Scope of G8 was checked, not assumed.** `data/cache` is the only cache
directory in the repo; `predict.py` contains zero occurrences of "cache";
and no other materialised artifact carries a repaired feature — the
record CSVs (`train_positives_*`, `val_positives_*`, `train_negatives_*`,
`evaluated_sightings_*`, `nonveg_flagged_*`) carry only
`evt, evh, evc, sclass, fdist, ch, cc`, all explicitly out of scope.
`dataset._cache_key` (`dataset.py:151-172`) hashes path + `getmtime` and
never content, so one changed mtime invalidates every key that touches
the file.

These are one-line checks and none is inferable from G0–G7, which read
only the rasters.

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

## § Disk (v4 — added; three reviewers flagged its absence)
The raster backup is not only a rollback copy: **G1 and G2′ are verified
against it**, so its integrity is a gate input. Requirements:
- Back up every raster this CR touches (**9.49 GiB = 10.19 GB**, 204 files) **on a
  separate inode set** — a hard-link backup (`cp -al`) plus any in-place
  write would make G1 read 0 by construction *and* destroy the only
  rollback copy.
- Re-verify the backup manifest hashes **immediately before** G1 runs.
- Repair writes temp-file-then-atomic-rename, per §1.

**Measured free space is 16 GB of 150 G (90 % used) — unchanged.** A
volume extension was reported during this work but has not landed on the
filesystem this repository sits on, so the contention between the
9.49 GiB backup and the 28 GB patch cache is **live**. G0/G1 make it
tighter, not looser: the backup is now a gate input, so `cp -al` is
forbidden and it must be a real copy. **Back up first, then purge** — back up before
anything is destroyed, and purge the cache once the rasters actually
change. **The purge is mandatory and must NOT be assumed automatic.** v4 claimed
"all 207 `patches_*.npy` die the moment this CR touches a raster".
(The inventory is also wrong: **206 `.npy` + 1 `.tmp`** — see G8.1.)
That is false, and a reviewer demonstrated it. `dataset._cache_key`
(`dataset.py:151-172`) hashes each raster path **and its mtime — never
its content**. The textbook metadata-preserving form of §1's mandated
"temp file then atomic rename" is `shutil.copystat(old, tmp);
os.replace(tmp, old)`, under which:

```
content changed     : yes (5,709,000 px on VT_2025_tsd.tif)
mtime before/after  : 1790752367.3632996 / 1790752367.3632996
cache-key component : UNCHANGED
```

Every gate G0–G7 then passes on correct rasters while all **206**
`patches_*.npy` (plus the 379 MB `.tmp` stray) stay cache **hits**, and `train.py` (default
`--cache-dir data/cache`) serves patches built from the **pre-repair
fabricated** values. `predict.py` has no patch cache — so the visible
artifact, the Errol map this investigation began with, would look fixed
while CR-0009's retrain and its entire validation baseline consume
fabricated data.

Therefore: **`shutil.copystat`, `cp -p` and `rsync -a` are forbidden on
the repair path**, and the purge is a numbered deliverable, not a
consequence.

**Reclaimable, recorded as a finding not a prerequisite:**
`data/disturbance/` is 31 GB and holds **two byte-identical
extractions** — the nested
`USAnnualDisturbance_1999_present/USAnnualDisturbance_1999_present/`
copy is **15 GB** and md5-identical to the outer one. It is a side
effect of `_extract_nested_zips` running over a directory that already
contained the outer bundle. Note `fetch_disturbance`'s `p > found[y]`
path sort currently selects the **nested** copy, so the outer is the
safe one to keep. Not a blocker now that disk is extended; worth
reclaiming, and the extraction bug is its own small defect.

## Test plan
**Validatable here:**
- **Coverage, both directions, per region, per feature, on the derived
  rasters**: no feature carries a value outside its generator's
  coverage; no feature is nodata inside it where it was not before.
  Disagreement against the NLCD cross-check **≤0.06 %** per direction
  (the measured three-lineage agreement), recorded.
- `tsd`: the fraction of pixels reading `TSD_MAX_YEARS` **inside**
  coverage is unchanged (today 81–93 % of training centre pixels); the
  fraction outside coverage is 0.
- `tcc`: real 0 % canopy inside the US survives — count of `tcc == 0`
  inside coverage unchanged.
- TreeMap: in-CONUS non-forest `0` count unchanged (Branch A);
  `balive > 0` outside coverage goes 11,700 / 4,464 / 2,137 → 0.
- Grid identity re-verified after the post-process: transform, width,
  height, CRS, dtype, nodata unchanged on all **174** files.
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
      `tcc` 1.3G, `road_dist` ME/VT/NH 698M ≈ **9,717 MiB = 9.49 GiB
      = 10.19 GB**. (v5 said "9.75 GB", wrong in *both* units; § Disk
      already said 9.49 GiB two paragraphs on. Measured, 204 files.)
- [ ] `generate_road_distance.py`: atomic `_download`; densified
      footprint reprojection; `TIGER_YEAR` pinned to 2023.
- [ ] Regenerate ME and VT `road_dist` at TIGER 2023 (8 county files).
- [ ] `generate_time_since_disturbance.py`: coverage = the § Coverage
      mask, **derived as `value ∉ grouse_data.NODATA_SENTINELS` over the
      intersection of the vintages with `d ≤ Y` — this IS a sentinel
      test**, and it is the same test G0.3's pinned `disturbance∩` digest
      is built from. The "not derivable by any sentinel test" claim was
      **withdrawn in v4** (§2); it survived here through v4 and v5 and is
      now corrected. Do **not** substitute NLCD (leaves **97,560 ME px**
      fabricated over Penobscot Bay) and do **not** reuse `:312-314`'s
      `hit` (masks legitimate `0` = disturbed-this-year).
- [ ] `download_treemap.py`: no fill outside the footprint; real nodata.
- [ ] `generate_treemap_features.py`: `_clean` mask-aware **and**
      `models.py`'s encode path, which v3 omitted. `_clean:259` and
      `:261` (`a[a < 0] = 0.0`) silently clamp NaN and any negative
      sentinel back to `0.0` — the exact fabricated value this CR
      removes. Three further sites turn a sentinel into `0`:
      `models.qmd_from_balive_tpa:716` (`ok = tpa > 0`; `NaN > 0` is
      False, so `out` keeps its `np.zeros` initialisation),
      `models.treemap_encode:741-742` (`np.rint(NaN).astype(np.int16)`
      → 0, with a cast warning rather than an error), and
      `np.clip(v, 0, cap)`. **`models.py` is a deliverable**, with an
      explicit nodata contract for all four output features.
- [ ] `generate_treemap_features.py`: add an **output-directory flag**
      (and a vintage/year selector). Without one, G4's "one real run for
      one region-year" is unachievable: `raster_dir` resolves to
      `data/landfire`, `write_vintage:293` opens in `"w"` mode, and
      `main:439-449` copies each vintage's representative year over every
      other year — so the minimum unit is **40 files overwritten in
      place**, with a deliberately sentinel-injected band, against the
      very rasters G1 diffs.
- [ ] `download_tcc_nlcd.py`: explicit EE `unmask(-1)` for `tcc` **and**
      `nlcd`.
- [ ] Post-process the existing rasters (§1), atomically.
- [ ] Record the full two-direction coverage table, all three regions,
      all fifteen features, before and after.
- [ ] Create **BUG-0030** (`tcc`) with a `BUG_LOG.md` row; update
      BUG-0023/0024/0025 to confirmed and fixed.
- [ ] `PREVENTIVE_ACTIONS.md`: PA-0017's Swept? cell updated with the
      `tcc` result and the corrected coverage reference; note that the
      reference must be per-generator.
- [ ] Confirm **BUG-0033** and **PA-0021** are filed **by the
      bookkeeping batch that lands before both CRs — not by CR-0007**
      (re-pointed in v6). This CR's gates apply PA-0021(a), (b) and (e);
      it does not file them.

      **Two clauses need their exemptions cited explicitly (v7), or a
      reviewer will read this CR as violating them.** PA-0021(c) requires
      thresholds to be quantiles over a sampling distribution — but G0.2's
      digests and inside-counts, and the twelve `N_pre` values, are
      **pre-registered constants**, because their null over the pipeline's
      own randomness is a **point mass** (the masks and counts are
      deterministic given the source files). That is (c)'s explicit
      point-mass carve-out, not a violation. Likewise G1, G2, G2′ and RD5
      are **exact predicates** (`count(...) == 0`, `|changed| == N_pre`),
      which (c) exempts because there is nothing to calibrate. And
      PA-0021(f) — every distributional row must name (class, subset, null
      population) — binds only G7's stratified sampling, which does name
      all three (positives-irrelevant; per-region per-stratum; 400 points
      against a pinned truth).

      v5 verified that CR-0007 carries "Create BUG-0033" and "Add
      PA-0021" in its deliverables, and that verification was honest —
      v4 had repeated a reviewer's claim that no CR did, without
      checking, which is exactly what `CLAUDE.md` §1.3 exists to prevent.
      But **CR-0007 cites PA-0021(b)/(d) and BUG-0033 in its own body to
      justify its own acceptance design**, so it cannot be the document
      that first defines them — a rule cannot be consulted (§3.2) before
      it exists, and a gate claiming to "apply PA-0021(a)/(b)" cannot be
      checked against text that is not written. Ownership therefore moves
      to a bookkeeping batch (precedent: PA-0015/BUG-0019 and
      PA-0016/BUG-0022 both landed as bookkeeping with no CR, because
      §1's trigger is a *code* change). `PREVENTIVE_ACTIONS.md` ends at
      **PA-0018** and `BUG_LOG.md` at **BUG-0027** today — verified — so
      PA-0019/0020/0021 and BUG-0028..0035 are all pending, and this CR
      is **not approvable until PA-0021 exists**.

      One consequence for §4.3: PA-0021's proposed lineage "extends
      PA-0018's enforcement clause" is **false** — PA-0018's text
      contains no enforcement, acceptance, gate or threshold clause
      (verified by grep on the live file). It extends **PA-0016**:
      PA-0016 forbids stating a *cause* without a check that could have
      falsified it; PA-0021 forbids accepting a *fix* without a check
      that could have failed it.
- [ ] **Purge `data/cache/` after the repair, as a numbered step** —
      not as an assumed consequence (see § Disk). Record free space
      before and after, and the G8 checks.
- [ ] `generate_time_since_disturbance.py`: add an **`--out-dir`** flag
      and a year selector. Without one the generator fix ships
      unexercised: `main()` offers only `--regions`, `--dist-dir`,
      `--block-rows` and opens `data/landfire/{region}_{y}_tsd.tif` in
      `"w"` mode, so testing it overwrites the 30 files G1 diffs. Then
      add a G4-equivalent: regenerate one region-year to a scratch dir,
      require its coverage footprint to match the pinned `disturbance∩`
      digest and its in-coverage `TSD_MAX_YEARS` share to match the
      repaired file. **`data/disturbance` is present, so this is
      runnable here** — it does not belong in the accepted-gap list.
- [ ] **Draft BUG-0030 before approval.** Scope names it as a bug this
      CR fixes and §4's recurrence review licenses the PA-0017 sweep
      closure, so a reviewer cannot check §2's eight elements against a
      record that does not exist. The project keeps root-level drafts
      (0028/0029/0034); this needs one too.
- [ ] **File BUG-0035 for the `nlcd` defect — its own id, not folded
      into BUG-0030.** Its correctness is "incidental" (`valid_range`
      starts at 11 and rejects the mask's 0 by accident) and `CLAUDE.md`
      §2 counts a defect found in review even if never observed running.
      v5 left the id "to allocate"; **§3.5 requires each sweep
      remediation to carry its own BUG**, and the sweep found two (`tcc`
      and `nlcd`), so folding them into one id violates it. **BUG-0035**
      is the next free id after the 0028/0029/0034 drafts and
      BUG-0030..0033 as claimed by CR-0007/CR-0008.
- [ ] Update **BUG-0023 §6** to reference this CR's ruling below.

**Does this CR discharge BUG-0023 §6's recorded deviation?** (v5 left
this as a checklist item and never answered it in the body; answered
here.) **Partly, and the deviation stays recorded.** `bf8d31a` (the
NH-side `road_dist` fix) landed with no CR and no pre-implementation
review, and BUG-0023 §6 records a retroactive CR as outstanding. This CR
**is** that retroactive CR for the `road_dist` change: it re-derives the
diagnosis from the current state of the code, extends the fix to ME and
VT, and submits the whole of it to independent review — which is what the
retroactive record was for. What it **cannot** do is supply review that
happens *before* implementation, so §1.1's ordering violation for
`bf8d31a` is **not** discharged and is not marked closed; it remains a
recorded deviation with this CR named as its retroactive review.
- [ ] **Implement RD5** (`count(nodata inside the pinned tiger_at1 mask)
      == 0`, per `road_dist` file) and **gate the excluded-point count at
      0**. Baseline verified 0 on all 30 files today.
- [ ] **G8.1 purge and gate on `patches_*`** (no extension anchor), and
      delete the stray `patches_61055cdd3521daef.npy.tmp6337` (379 MB).
- [ ] **The backup manifest records each file's pre-repair mtime**, so
      G8.2 compares against the manifest, not the backup file's `stat` —
      and G8.2 is declared unevaluable for an archive-format backup.
- [ ] **G8.3**: no prediction or calibration artifact published between
      this CR and CR-0009; mark the existing six
      `data/predictions/*.{tif,kmz}` and `data/calibration/calibration.json`
      stale on completion.
- [ ] **G6 compares `src.tags(ns='IMAGE_STRUCTURE')`** as well as the
      profile dict.
- [ ] **G5's hand-off covers I17** — whichever of CR-0007/CR-0008 lands
      second re-measures CR-0007's I17 and records the new value and
      argmax feature; its ≤ 0.095 threshold is not re-derived.
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

| round | reviewer | verdict | blocking |
|---|---|---|---|
| 1 | raster lane (resumed) | APPROVE WITH CHANGES | 2 |
| 1 | seam (fresh) | REJECT | 4 |
| 2 | seam (resumed) | REJECT | 2 |
| 3 | fresh, whitelist attack | REJECT | 2 |
| 4 | expedited, raster lane | APPROVE WITH CHANGES | 1 |
| 5 | **formal, fresh** | **REJECT** | 3 |
| 6 | **formal, fresh (round 2)** | **REJECT** | 2 |
| 7 (v7) | **formal, fresh** | **REJECT** | 2 |
| 7 (v7) | implementation + §1 compliance (fresh) | **REJECT** | 1 |

**Dispositions.** v4 carried no verdict and no disposition table despite
four prior rounds — a §1.3/§1.4 violation that made quorum uncomputable
and meant no reader could check whether a finding had been dropped.
Every concern from every round is dispositioned below.

| concern | disposition |
|---|---|
| Coverage reference uncomputable for 5 of 6 features | **Accepted** — resolved: the VAT tables make `tsd` derivable; per-feature references settled (§ Coverage). |
| A2/A3 pass a corrupted channel (values doubled; 39 % of grid constant-filled) | **Accepted** — replaced by G1's change-set constraint; A2/A3 demoted to diagnostics. |
| Every figure an 8× decimated sample | **Accepted** — G3, full resolution mandatory. |
| A3's premise false (`tsd` has 0 in-coverage zeros only in 2025) | **Accepted** — per-year counts reported; the guard is G1, not A3. |
| ≥0.99 in the wrong units, on the wrong reference | **Accepted** — G2 requires exactly 1.0000 against the generator's own reference. |
| A4 vacuous under the local-post-process plan | **Accepted** — G4 is a `_clean` unit test plus a real `--src-dir` run. |
| No resource section | **Accepted** — § Disk added; its free-space premise corrected to the measured 16 GB. |
| A1's `nlcd` row measured on the rejected reference | **Accepted** — row removed. |
| **G1 and G2 both consume the repair's mask → vacuous for any mask** | **Accepted** — G0 pins the mask by pre-registered digest and inside-count. A reviewer independently reproduced all nine. |
| **Whole-grid mask → no-op passes vacuously** | **Accepted** — G2′ makes G1 an equality against pre-registered `N_pre`. |
| `road_dist` 52.75 % of ME ungated | **Accepted** — G7, with the finding that a median/p95 gate on a uniform sample passes the broken raster. |
| The "independent" completeness reference is circular | **Accepted** — withdrawn; replaced by three-lineage triangulation. |
| `models.py` encode path omitted | **Accepted** — added to deliverables. |
| `generate_treemap_features.py` has no output-dir flag | **Accepted** — deliverable. |
| `tsd` footprint table printed inside fraction under "outside" heading | **Accepted** — both columns now stated, with the NH sanity check. |
| `-1111` in 6 of 26 tables, not all 26 | **Accepted** — corrected, and the BOM recorded. **The schema count was also wrong and is corrected in v6:** the VATs have **four canonical schemas / six literal header strings**, not "three". Measured over all 52 CSVs (26 vintages × the two extractions): six distinct headers, collapsing to four once the DBF 10-character truncations are canonicalised (`TYPE_CONFI`≡`TYPE_CONFIDENCE`, `SEV_CONFID`≡`SEV_CONFIDENCE`, `DESCRIPTIO`≡`DESCRIPTION`) — 18 + 14 + 18 + 2 files. A round-6 reviewer said "four"; four is right only under canonicalisation, so both forms are stated. Evidence only, not operative. |
| **Withdrawn claim still the operative `tsd` instruction** (rounds 5 **and 6** — third shipment) | **Accepted, and v5's own disposition was false.** v5 recorded this "Accepted — §9.2 rewritten"; **this document has no §9.2** (the string occurs only inside two measurement tables), and the withdrawn claim survived in the **Deliverables** item for `generate_time_since_disturbance.py` — the operative instruction — and in the § Risk level table. Both are now corrected **in place**, stating the sentinel test affirmatively rather than negating it. The disposition-verification failure is itself logged: a disposition must cite a locatable anchor, and the citation must be checked to exist. |
| **Metadata-preserving replace defeats the cache** | **Accepted** — G8 added; `copystat`/`cp -p`/`rsync -a` forbidden; purge made a numbered deliverable. |
| **No verdicts or dispositions recorded** | **Accepted** — this table. |
| G6 omits compression/tiling; ENOSPC mid-repair | **Accepted** — G6 compares the full profile; size check added. |
| `tsd` generator ships unexercised and untestable | **Accepted** — `--out-dir` deliverable and a G4-equivalent. |
| G0 recipes not reproducible next month | **Accepted** — source list and predicate pinned per row. |
| Common-mode cause misstated; mitigation has no power | **Accepted** — cause corrected (three different code paths); the boundary-count mitigation withdrawn as measured powerless. |
| G5 makes the CR order-dependent | **Accepted** — G5 assigned to whichever CR lands second. |
| Unverified reviewer claim propagated | **Accepted** — withdrawn and verified against CR-0007. |
| BUG-0030 does not exist; `nlcd` defect unfiled | **Accepted** — both are deliverables, required before approval. |
| G7 encoding term is a sample max; stratum undefined | **Accepted** — both stated as preconditions. |

**Round 6 dispositions (formal, fresh — REJECT, 2 blocking + 14).** Every
concern below was re-derived against the live files before being applied,
per §1.3; where my check disagreed with the reviewer's, both readings are
stated.

| # | concern | disposition |
|---|---|---|
| 1 | **BLOCKING** — withdrawn `tsd` claim still operative at the Deliverables item and the Risk row; disposition cited a nonexistent §9.2 | **Accepted.** Verified both survivals (the Deliverables one is wrapped across lines, which is why a line-anchored grep for the phrase returns only the Risk row — the same false-negative class as this programme's earlier `grep -v '^\s*#'` error). Both corrected **in place** and stated affirmatively; the false disposition is recorded as such. |
| 2 | **BLOCKING** — `road_dist` nodata placement gated in one direction only, to 4 dp, with G7 structurally blind | **Accepted in full.** **RD5** added; excluded-point count promoted to a gate at 0; **G2 restated as a pixel count**. Baseline independently re-measured on all 30 files: ME/VT exactly 0 nodata, NH 5,656,708 = 0.099165 ≡ the outside-TIGER fraction — so RD5 starts from a verified zero and cannot false-fail. |
| 3 | MAJOR — G5's text still hard-wires "the record set CR-0007 produces" though the round-5 disposition claimed it was reassigned | **Accepted.** Verified the text was unchanged. G5 rewritten to be order-independent, and the stale disposition acknowledged rather than re-asserted. |
| 4 | MAJOR — G8.1's glob misses `patches_*.npy.tmp*`; one 379 MB such file is on disk; "207" is that file miscounted | **Accepted.** Verified: 206 `.npy` + 1 `.tmp` (`patches_61055cdd3521daef.npy.tmp6337`, 379,453,568 B, Sep 29 12:50). Glob, counts and a deletion deliverable all corrected. |
| 5 | MAJOR — G6's "full profile dict" omits `PREDICTOR` (=2 on every file) | **Accepted.** Verified: the profile dict has no `predictor` key while the tag namespace returns `PREDICTOR: '2'`. G6 now compares `tags(ns='IMAGE_STRUCTURE')`. The reviewer's measurement that the consequence is *benign* (files get smaller, no ENOSPC) is recorded too — this is a correctness-of-claim fix, not a data-loss fix, and is not inflated into one. |
| 6 | MAJOR — G8.2's forbidden-idiom list is enumerative and misses `shutil.copy2`, the repo's own year-fanout idiom | **Accepted.** Verified `shutil.copy2` at `generate_treemap_features.py:444`. Clause restated as a **mechanism** against the manifest's recorded pre-repair mtime, with the archive-backup limit declared. |
| 7 | MEDIUM — G4.2's instrument has no power: it injects in-coverage and asserts on G2, which measures outside-coverage | **Accepted.** Assertion moved to the output value **at the injected pixels**, and the injection site made part of the spec. |
| 8 | MEDIUM — G7's truth pins vintage and MTFCC but not the roads' spatial extent (the PA-0018 mechanism, twice logged) | **Accepted.** Precondition 2 added: every TIGER county intersecting grid + `pad_km`, never `STATE_FIPS[region]` — otherwise the verifier reproduces BUG-0023 internally and false-fails the very stratum that carries the signal. |
| 9 | MEDIUM — G1's exemption paragraph said `road_dist` is gated by G2 while the v4→v5 revision note and G2′ said G7. Plus two paragraphs both headed "Two preconditions" (line numbers omitted deliberately: they shift with every revision, which is part of how the round-5 disposition came to cite a section that did not exist) | **Accepted.** Resolved in favour of **G7** (G2 provably cannot gate in-coverage values); both heading collisions renamed and the preconditions numbered. |
| 10 | MEDIUM — "one reference serves every output year" is empirical, not structural | **Accepted.** G0.4 now requires re-verifying `cov_minyear == cov_maxyear` whenever a vintage is added, not merely noting that the digest changed. The reviewer's byte-identical `cov(≤2016) ≡ cov(≤2025)` result is recorded as the reason the single pin is legitimate *today*. |
| 11 | LOW — G2 never says which value counts as nodata | **Accepted.** Specified as the file's declared nodata. The reviewer's trace showing in-repo damage is **nil** is recorded, so the fix is stated as determinacy, not as a closed break. |
| 12 | LOW — G0's `disturbance∩` does not disambiguate the two byte-identical extractions | **Accepted.** Content hashes now part of the pin. Verified the duplication independently: **52 VAT CSVs for 26 vintages**. |
| 13 | LOW — v5's own new text says the VATs have "three" schemas | **Accepted, with a correction to the correction.** The reviewer said four; measured over all 52 CSVs it is **six literal headers / four canonical** once the DBF 10-char truncations are collapsed. Both forms now stated — "four" alone would have been the third wrong count in this row's history. |
| 14 | LOW — count/size inconsistencies: "~170 files", "9.75 GB", "207" | **Accepted.** Independently measured: 204 backup files = **9,717 MiB = 9.49 GiB = 10.19 GB** (so "9.75 GB" was wrong in *both* units); **174** in-scope; 206 + 1. All corrected. |
| 15 | LOW — G8 says nothing about `calibration.json` or the published predictions | **Accepted.** **G8.3** added: no prediction or calibration artifact may be published between this CR and CR-0009, and the existing ones are marked stale. This closes the specific hazard of re-rendering the Errol map as stale-but-plausible. |
| 16 | LOW — the BUG-0023 §6 retroactive question is never discharged in the body | **Accepted.** Answered in the body before Deliverables: this CR **is** the retroactive CR for `bf8d31a`'s `road_dist` change, but it cannot supply pre-implementation review, so §1.1's ordering deviation stays recorded and is not marked closed. |

**Round 6's verified reproductions, recorded because they are the
document's main asset.** An independent reviewer reproduced, from
independently written code: all **nine** G0 digests (and confirmed
`nlcd` year- and recipe-invariant across 10 years × 4 predicates, and
`tiger_at1` insensitive to pad and densification but sensitive only to
`all_touched`); all **twelve** `N_pre` counts on *every* year, not one;
the `tsd` footprint table both columns; `balive > 0` outside NLCD
(11,700 / 4,464 / 2,137); `tcc > 0` outside footprint (exactly 0); the
three-lineage maxima per direction; 36.3 GB uncompressed; 174 in-scope /
204 backup files; the 26 vintages' nodata tags and all 26 VATs; and
**every code citation checked was exact**. Seven attacks failed, including
the sharpest structural one available (per-year `tsd` coverage
divergence). The repair core is closed: G1 ∧ G2′ ∧ G2 determine it
uniquely.

**What six rounds could not break:** the 174-file repair core. Two
successive formal reviewers, working independently, verified all nine G0
digests, all twelve `N_pre` counts and every distributional claim from
their own code, and between them listed fourteen failed attacks. Round 5's
assessment was that v5 was "an editing pass, not a new investigation";
round 6's was that "v5's numbers are trustworthy, which is not a small
thing after six rounds", and that every failure was at a seam the CR had
carved out for itself — the `road_dist` exemptions and the document's own
bookkeeping, not the repair.

**The recurring defect in this document is editorial, not analytical**,
and v6 treats it as the mechanism it is: v3→v4 withdrew the `tsd`
sentinel claim, v4 left it in the deliverable, v5 rewrote the prose and
*still* left the deliverable while recording it fixed against a section
number that does not exist. Three shipments of one defect. The rule
applied here — fold every correction into the body at the point of use,
never into an appendix, and check that a disposition's cited anchor
resolves — is PA-0021's territory and is why this CR cannot be approved
before PA-0021 is written.

**Author sign-off:** withheld. v6 answers round 6's sixteen concerns,
but §1.4's quorum is **arithmetically unmet** — no reviewer has signed
off on any revision, and the last three rounds returned REJECT. Approval
also requires PA-0019/0020/0021 and BUG-0030/0035 to exist (§3.1, §2),
and `PREVENTIVE_ACTIONS.md` ends at PA-0018 today. **This CR is not
approvable until the bookkeeping batch lands and one reviewer signs off
on v6.**

### Round 7 (v7) — two independent fresh reviews, 2026-09-30 — dispositions PENDING

Both reviewers returned **REJECT**. Concerns are recorded here so none can be
dropped (§1.3); **no disposition has been decided yet** — each is `pending`
until the author re-derives it against the live files and rules on it in v8.
"A" = formal lane, "B" = implementation/§1 lane. Evidence scripts:
session scratchpad `cr0008_A/` (A); B used read-only shell checks.

| # | sev | reviewer | concern | disposition |
|---|---|---|---|---|
| 1 | **BLOCKING** | A, B | TreeMap generator fix cannot separate outside-CONUS from non-forest: `data/treemap_raw` has `nodata=None` (`unmask(0)`), so a mask-aware `_clean` has nothing to propagate and `--src-dir data/treemap_raw` re-fabricates 0 outside coverage (VT 2,098,512 / NH 5,654,800 px). G4.2 passes it. Needs an external mask (pinned G0 `nlcd`) applied in the generator; G4.2 must also require G2 == 0 and pixel identity with the repaired file outside the injection. "latent defect is closed by the generator fix" must be withdrawn. | pending — author spot-check: raw ME BALIVE `nodata=None`, 0 % NaN/neg, 68 % zeros (confirmed) |
| 2 | **BLOCKING** | A, B | Approval preconditions unmet: PA-0019/0020/0021 not in `PREVENTIVE_ACTIONS.md` (ends PA-0018); no BUG-0030/0035 draft; sign-off paragraph still says "v6" and misstates §1.4 quorum. | pending |
| 3 | MAJOR | A | `download_treemap.py` deliverable contradicts "one mask" settled decision (a sentinel unmask also marks in-CONUS non-forest → silent Branch B); `:315` `np.clip(arr, 0, None)` clamps a negative sentinel back to 0 and is not named. | pending — `:315` clip confirmed |
| 4 | MAJOR | A | Canadian-border roads: TIGER has no Canadian roads; up to 978,374 ME / 109,251 NH / 281,662 VT in-coverage px (19 positives) may over-read distance; G7's TIGER-only truth is blind by construction. Needs nodata or an accepted-residual disposition in BUG-0023 / PA-0017. | pending |
| 5 | MAJOR | A, B | Cross-CR Impact claims wrong: I17 is OBS in CR-0007 v7 (0.0306, 400 seeds), not a ≤ 0.095 gate at 0.0696; "pool moves by 2 records" is a modelling assumption (real pipeline removes 0); "4 of 3,659 ME" omits VT and is model-based; "either order" measured one order only (CR-0008-first: 140 ME / 717 VT positives with \|err\| > 60 m). G5/I17 hand-off has no reciprocal owner in CR-0007/0009. | pending |
| 6 | MAJOR | B | Approval preconditions (PA-0020 is a CR-0007 deliverable) contradict "independent of CR-0007 … either order". | pending |
| 7 | MAJOR | A, B | Withdrawn/superseded text in operative sections (4th shipment of this class): "must handle **three**" VAT schemas; enumerated `copystat`/`cp -p`/`rsync -a` list in § Disk; "18.4 %" in §2; Test plan's v4 six-field G6, "47.1 %", NH-style spot-check, "81–93 %"; Impact "47.1 % (NH 9.8 %)"; "G2 requires exactly 1.0000"; "Not a blocker now that disk is extended" vs "has not landed". | pending — "three", "18.4 %" confirmed present |
| 8 | MEDIUM | A, B | v7 cites "§ Scope's table" — no such table (it is in § Coverage). | pending — confirmed |
| 9 | MEDIUM | A, B | `tsd` deliverable: `hit` parenthetical says "0 = disturbed-this-year"; raw 0 is VAT Background (covered, undisturbed). §2 vintage set (all 26) vs deliverable (d ≤ Y). | pending |
| 10 | MEDIUM | A | G7 checks one of ten `road_dist` year-copies; require all copies per region byte-identical (true today). | pending — one md5 per region × 10 files confirmed |
| 11 | MEDIUM | B | Encoder sentinel→0 sweep incomplete: `tpa_live_encode`, `tsd_encode`, `treemap_encode`, `road_dist_encode` all map nan/-9999 → 0; `tpa_live_encode` and `tsd_encode` unnamed. | pending |
| 12 | MEDIUM | A, B | PA-0021 clause text cited in two incompatible forms; 0.06 % cross-check and G6 "≤ ~1.2×" are fitted/uncalibrated; RD1/RD2/RD4 thresholds lack null quantiles; GATE/OBS labels missing for G3, G5, cross-check. | pending |
| 13 | MEDIUM | B | PA-0019 required but not applied: no provenance tag on repaired/regenerated files. | pending |
| 14 | MEDIUM | B | Risk table lacks the G8 cache, RD5 over-mask and G8.3 stale-publication risks. | pending |
| 15 | MEDIUM | B | Rounds 1–5 disposition rows are unattributed (27 rows vs 14 blocking findings); tag each with round/reviewer. | pending |
| 16 | MEDIUM | A | Restore rehearsal unordered and has no space (10.19 GB vs ~6–7 GB free); in-place `cp -a` restore reverts the repair and defeats G8.2. | pending |
| 17 | LOW | A, B | Misc: `write_vintage` open is `:294` not `:293`; "G0.3's pinned digest" should be G0.2; "~33 %" vs "25.6 %" ME outside-US; G6 does not cover the 20 regenerated `road_dist` files; VT TIGER counties fetchable (network available) and v7's VT truth skipped 8 counties (result unchanged, 0 diff at 2,261 positives); G8.3 omits `reliability.{csv,png}` and `grouse_ssl_backbone.pth`; CR-0009 still says "9.75 GB"; "9,021 MB" is MiB. | pending |

**Verified again by round 7 (both reviewers, independent code):** all nine G0
digests and inside-counts; all `N_pre` counts every year; nodata inside
coverage = 0 (RD5 baseline); cross-lineage maxima; disk figures (204 files =
10.19 GB); cache 206 + 1 `.tmp`; nearly every code citation. Failed attacks:
aliased/whole-grid mask, per-year `tsd` divergence, nested-vs-outer
disturbance copy, G6 tag loss, stray caches, RD5 false-fail, 0.06 %
false-fail, I17 "6 of 7 bit-identical". **The 174-file repair core survived a
seventh round; every blocking finding is at the generator/re-run seam or in
bookkeeping.**

**Author sign-off (round 7):** withheld — two REJECTs, dispositions pending.
