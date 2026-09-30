# BUG-0034: positives and negatives are acquired over different year ranges, silently breaking the 1:1 class balance and leaving a vintage→label signal

> Promoted from `DRAFT_BUG-0034-…md` (committed at `f8fafbc`) by CR-0007
> deliverable 6, 2026-09-30, because PA-0020 cites it as its only live
> evidence. The investigation text (§§1–5, 7) is unchanged. §6's status
> and §8's filing note were updated at promotion. References to "CR-0007
> §6" and "gate (d)" are to CR-0007 v5/v6, which were superseded.
> **Status: FIXED (root cause: disjoint per-class temporal support) by
> CR-0019, 2026-09-30** (§6). Consequence (b)'s within-epoch remainder
> moved to **BUG-0073** (OPEN) per PA-0024(b).

## 1. Description
The two label classes of one dataset are fetched from the **same GBIF
dataset**, with the **same state filter**, over **different year
ranges**: positives from 2016, negatives from 2020. Nothing downstream
reconciles them and nothing compares them.

`train.py`'s `filter_by_year_gap` then removes every record whose
sighting year has no raster within ±2 years. Because LANDFIRE exists
only from 2022, the filter's accept set is exactly `year >= 2020` — so
it drops **1,973 positives (23.59 %) and 0 negatives**, which is
precisely the pre-2020 population of each class.

Three consequences, none of them recorded anywhere: the documented 1:1
class balance is silently broken; raster vintage becomes partially
predictive of the label; and three change requests quote the drop
asymmetry as a property of the data and design around it.

## 2. Where encountered
Found by a research investigation commissioned during the CR-0007
review (2026-09-30), after a reviewer noticed the two year bounds while
auditing PA-0020's scope.

- **Positives, year floor:** `sightings.py:21` and `ebird.py:22`
- **Negatives, year floor:** `get_negatives.py:227-228`, consumed at
  `:268`
- **The filter:** `train.py:168` `filter_by_year_gap`, invoked per class
  per split in `build_datasets`
- **The broken invariant:** `generate_negatives.py:35-36` (docstring),
  implemented at `:250-251`
- **Raster vintages that make 2020 the binding year:**
  `grouse_data.RegionData.raster_years` — LANDFIRE features exist only
  from 2022, all others from 2016

## 3. What it caused to fail

**Measured on the selected training records (verified independently):**

```
positives  n=8365  pre-2020 = 1973 (23.59%)   years 2016-2024
negatives  n=8365  pre-2020 =    0 ( 0.00%)   years 2020-2024
```

The set `filter_by_year_gap` drops is **identically** `{year < 2020}` —
1,973 is the exact pre-2020 positive count and 0 the exact pre-2020
negative count, in every region and both splits (ME 22.31/22.41 %,
NH 24.80/27.11 %, VT 24.16/23.67 %, negatives 0.00 % throughout).

**(a) The documented 1:1 balance is silently broken.**

```
designed        train 6691/6691    val 1674/1674     prevalence 0.5000
after filter    train 5120/6691 -> prevalence 0.4335
                val   1272/1674 -> prevalence 0.4318
```

Batch composition is rescued by `StratifiedBatchSampler`, so the
training loss is unaffected — but `calibrate.py:351` calls the same
filtered `build_datasets`, so **the Platt bias is fitted at 43.2 %
prevalence against a documented 50 %**, and every reported AP inherits
it. Nothing checks the invariant the docstring asserts.

**(b) Raster vintage partially encodes the label.** Because a record's
own year selects its raster vintage (`dataset.py:122-126` →
`grouse_data.raster_path`), and the classes' year ranges are disjoint
below 2020, vintage predicts the label:

```
vintage:  2016  2017  2018  2019 | 2020  2021  2022  2023  2024
neg:         0     0     0     0 | 2830  2325  1788   765   657
pos:       382   371   618   602 | 1235  1367  1471   996  1323
```

For 8 of 15 channels, vintage ∈ {2016..2019} implies label = 1 with
probability 1. Post-filter the confound narrows but does not vanish:
**vintage year alone predicts the label at AUC 0.6365**, driven by the
negative pool's front-loading onto 2020 (33.8 % of negatives), itself a
consequence of 2020 being the earliest requested year.

This is a hazard the project explicitly designs against elsewhere.
`ARCHITECTURE.md:193-198` and `generate_time_since_disturbance.py:39-47`
record that `TSD_MAX_YEARS` was made a fixed cap precisely so that *"the
most common value in the feature would itself identify the vintage, and
the network would have a free year label."* That protection exists
within one feature. Nothing does the equivalent across label classes.

**(c) Unfiltered consumers see the full confound.** Only
`build_datasets` applies the filter. `analyze_grouse.py`,
`generate_negatives.py`, `tune_bins.py` and every `diagnose_*.py` read
the unfiltered records — including 1,371 positives whose `carbon_dwn`
comes from the TreeMap-2016 vintage, which reads **45 % lower at
identical locations**, and which no negative ever uses.

**(d) 17.5 % of positive-occupied 3 km blocks lose all their
positives** (901 of 5,138 pooled), and **266 of those emptied blocks
still contain negatives** — one-sided spatial support manufactured by a
temporal parameter, and therefore invisible to BUG-0029's spatial
checks and to CR-0007's gate (d).

**(e) Three change requests design around the symptom.** CR-0006 and
CR-0007 both place their standing assertions *before*
`filter_by_year_gap` because it "drops 22–24 % of positives and 0 % of
negatives and would otherwise guarantee divergence on correct data" —
and in CR-0007 that placement is what forces `build_datasets` to be
split into a load pass and a construct pass, the riskiest code change in
that CR. A design constraint is being derived from an unrecorded defect.
(Measured caveat: at gate (d)'s own 30 km resolution the filter barely
moves the statistic — ME 0.0484 → 0.0484, NH 0.3220 → 0.3103,
VT 0.2500 → 0.2545. The divergence is real at 3 km, not at 30 km.)

## 4. What the defect was

Positives, `sightings.py:19-21`:
```python
SPECIES_NAME = "Bonasa umbellus" # Scientific name for Ruffed Grouse
STATES = ["Maine", "New Hampshire", "Vermont"]
START_YEAR = 2016
```
and `ebird.py:22`:
```python
START_YEAR = 2016
```

Negatives, `get_negatives.py:227-228`:
```python
    parser.add_argument("--years", nargs="+", type=int,
                        default=list(range(2020, dt.date.today().year + 1)))
```
consumed at `:266-269` — the **same dataset, the same state filter, one
key away** from the parameter BUG-0029 indicts:
```python
    def base_params(st, key, year):
        return {"datasetKey": EOD_DATASET_KEY, "taxonKey": key,
                "country": "US", "stateProvince": STATES[st],
                "year": year, "hasCoordinate": "true"}
```

The invariant that breaks, `generate_negatives.py:35-36`:
```
Counts: per region and per split, negatives are sampled 1:1 against the
positive counts in train_positives/val_positives (NEG_RATIO adjustable).
```
implemented at `:250-251`:
```python
    targets = {'train': int(round(n_train_pos * NEG_RATIO)),
               'val': int(round(n_val_pos * NEG_RATIO))}
```
The targets are computed from the **unfiltered** positive counts, and
the filter then removes 23.6 % of the positives and none of the
negatives — so the 1:1 rule holds at the point it is written and is
false at the point it is used.

## 5. Root cause analysis (differential analysis)

Comparing the two acquisition paths, which are identical in every
respect that was considered and differ in one that was not:

| | positives | negatives |
|---|---|---|
| GBIF dataset | `EOD_DATASET_KEY` | **same** |
| geographic filter | `stateProvince` | **same** |
| coordinate requirement | `hasCoordinate` | **same** |
| **year range** | **2016+** | **2020+** |

1. *Why does the filter drop 23.6 % of positives and 0 % of negatives?*
   Because it accepts exactly `year >= 2020`, and only positives exist
   below that.
2. *Why does only one class exist below 2020?* Because the two
   acquisition queries carry different year floors.
3. *Is that a data limit?* **No — it is a choice.**
   `data/sightings/me_sightings_2016.csv` carries `datasetKey =
   4fa7b334-ce0d-4e88-aaae-2e0c138d049e`, byte-identical to
   `get_negatives.py:43`'s `EOD_DATASET_KEY`, with `stateProvince =
   Maine`, `year = 2016` and real `eventDate`s. The exact dataset, the
   exact state filter, pre-2020 years: it returns data. The sightings
   were fetched at 06:33 and the negatives at 07:44–07:54 the same day.
   No comment, docstring, `ARCHITECTURE.md` entry or CHANGELOG line
   justifies 2020, and `git log -S "range(2020"` returns only the
   initial import.
4. *Why did nothing catch it?* Because both classes produce the
   **right count**. The negative sampler draws 1:1 against the positive
   count, so the dataset looks balanced at every point a count is
   checked. Nothing compares the classes' **temporal support**, and a
   count-based check cannot see a support difference.
5. *Why was temporal support not compared, when spatial support is?*
   Because every rule and every sweep in the QMS is scoped to geography.
   PA-0017 and PA-0018 name distances, buffers, thinning, block
   holdouts, boxes and `STATE_FIPS`. A year range is not a spatial
   subset, so no rule reaches it and no sweep looked for it.

**Root cause:** the two label classes of one dataset are defined by
acquisition-query parameters that differ on an axis (time) for which no
rule requires the classes' supports to be compared — and equal record
counts, produced by construction, mask the difference at every point
where a check exists.

## 6. Corrective action
**At promotion (2026-09-30): not fixed in CR-0007.** A decision recorded
in CR-0007 v6 had put the fix in CR-0007. CR-0007 v6 later descoped it, and
v9 (approved) contains no BUG-0034 fix (CR-0007 v9 "Out of scope":
"BUG-0034's fix"). The fix is **owned by a future CR** (not yet opened).
The recommendation below stands as that CR's starting point.

The fix changes the training data, so per `CLAUDE.md` §1 it
needs a CR. **CR-0007 is the natural home** — it already rebuilds every
split, already edits `prepare_training_data.py` and
`generate_negatives.py`, and its assertion placement derives from this
defect. Fixing it elsewhere means rebuilding the splits twice.

Recommended, on measured cost (neither option needs network):

- **Restrict positives to 2020+ at *selection*, not acquisition.** Costs
  ~1,911 thinned positives and **~0 training positives** — re-thinning
  the 2020+ subset yields ME 2,952 / NH 1,636 / VT 1,670 against
  today's post-filter 2,946 / 1,630 / 1,661, i.e. **+6 / +6 / +9**,
  because thinning is spacing-greedy and a dropped pre-2020 point is
  replaced by a neighbouring post-2020 one. It must be at selection:
  cutting the *source* years would shrink the 300 m exclusion buffer
  (`generate_negatives.py:181-186`), which is built from all
  `evaluated_sightings`, and would admit negatives at sites with
  2016–2019 grouse records.
- **Year-match the negative draw within 2020+.** Stratify the weighted
  draw so each (region, split) negative year histogram matches the
  positives'. Today's pool supports it with 11.2×–120.8× headroom per
  cell. Drives vintage→label AUC to 0.5 by construction.

Together these restore a true 1:1, remove the vintage confound, and make
`filter_by_year_gap` a **no-op** — which would let CR-0007's assertions
run post-filter on the frame that actually trains, and **remove the
`build_datasets` load/construct split entirely**.

Rejected: re-fetching negatives from 2016 (recovers 0 positives — the
rasters still do not exist — and the `yr_cap = sp_cap/len(years)`
divisor would redistribute the pool into the years the filter discards);
relaxing `--max-year-gap` (hands 2016 sightings a 2022 landscape, the
thing the filter exists to prevent); backfilling LANDFIRE (blocked —
`download_rev.py:51-58` records that LF2020 non-topo products were
retired from LFPS in Dec 2025).

Status: **OPEN**, confirmed on real data, unfixed; fix owned by a future CR.

**Corrective action (CR-0019, IMPLEMENTED 2026-09-30).** "Floor at
selection, refusal, E14":
- One constant `regions.YEAR_MIN = 2020` selects both classes: positives
  at step 2, **before thinning** (the recommendation above; the CR-0012 A9
  thin-order interaction), candidates at pool step 1. Acquisition is
  unchanged, so the 300 m buffer still uses every sighting year. Code
  `628083d` (pipeline), `65b2469` (acceptance), merged to `main`
  (`c990a82`, `c599307`; test `b8e96cf`).
- `train.filter_by_year_gap` **refuses** (`SystemExit`) instead of
  dropping, so what trains equals what CR-0013 accepted.
- CR-0013 gained exact gate **E14** ((a) every P/N year `≥ YEAR_MIN`;
  (b) pooled P and N year sets equal), also in the standing subset: the
  build-time support comparison §8 asked for, as an exact predicate
  rather than a drop-rate tolerance.
- Live run (evidence `00b0b84`, `docs/quality/evidence/CR-0019/live/`):
  P 6,232 → 4,809, N 6,232 → 4,809, both 2020–2024; prevalence 0.5000 in
  both splits; `filter_by_year_gap` at tolerance 2 drops 0 rows; MC 42/42,
  20/20 GATEs, record `ed27583b…`.

Verified against the root cause, not the symptom: the classes now share
one floor by construction and E14(b) fails any support divergence at
either end. Consequences (a) and (e) are fixed. (c) and (d) came from the
train-time drop acting after the files were built; there is no such drop
now, so unfiltered consumers read the same floored rows that train, and
the block split and draw are computed on them (CR-0019 §4: 656
positive-only-pre-2020 blocks removed before the split). The year-matching half of
the recommendation was **not** done (the pool cannot supply it; CR-0019
§5): consequence (b)'s remainder (year→label AUC 0.6615 within
2020–2024) is **BUG-0073**.

Status: **FIXED** (root cause), 2026-09-30, by CR-0019. Residual: BUG-0073 (OPEN).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` (all 27 rows), `PREVENTIVE_ACTIONS.md`
(PA-0001…0018), both root-level drafts, and CR-0006 through CR-0009.

**This is a second occurrence of BUG-0029's mechanism on a different
axis.** BUG-0029: positives clipped by *box*, negatives clipped by a
`stateProvince` *API parameter*. This: positives bounded by
`START_YEAR = 2016`, negatives bounded by a `year` *API parameter*
defaulting to 2020. Identical shape — one dataset, two label classes,
one acquisition-query parameter differing between them, nothing
reconciling them, and count-equality masking the divergence. BUG-0029's
own Five-Whys step 4 applies verbatim with "temporal" substituted for
"spatial": *both produce the right count … nothing compares their
support; a count-based check cannot see it.*

It is **not a duplicate**: different parameter, different axis, a
different downstream consequence (class-balance destruction and a
vintage/label confound, rather than spatial support), and a different
fix surface.

Related but not the same: BUG-0023 / BUG-0026 (per-state source over a
larger extent — same family, geographic axis, raster layer);
BUG-0005 (the only prior *year*-related bug — a glob pattern, not a year
range).

**Prior-preventive-action failure analysis.** Three rules should have
caught it and could not:

- **PA-0018** (*"never a per-state or per-region subset chosen by
  label"*) — every clause is geographic: distances, nearest-neighbour
  queries, buffers, thinning, block holdouts, point sampling, region
  boxes, `STATE_FIPS`. A year range is not a spatial subset. **Too
  narrow by axis.**
- **PA-0020 as drafted in BUG-0029 §8** — scoped to *"any filter that
  bounds a dataset **geographically** — a remote API query parameter
  (`stateProvince`, `country`, an admin code), a download bounding box,
  a file-per-state naming convention."* The offending parameter is in
  the **same params dict, one key away** from `stateProvince`, and
  outside the rule. Its "spatial supports must be compared explicitly"
  clause is *satisfied* by this data while the temporal supports are
  100 %/0 % disjoint. **Right layer, wrong dimension.**
- **The sweeps** looked at spatial code and asked, of each acquisition
  query, *what extent does it use* — extent, not epoch. The `year` key
  sits in the dictionary BUG-0029 quotes verbatim and was not noticed,
  because the reader was looking for geography.

## 8. Preventive action
**No new rule: PA-0020 was filed (CR-0007 deliverable 6) as re-scoped**, from
*geographic* acquisition filters to **any per-class dataset-defining
filter**. This bug is that broadening's evidence base and should be
cited in it.

That matters: CR-0007 withdrew its only cited sibling for the broadening
(`coord_uncertainty_m`, measured inert — null in all 265,212 candidate
rows and all 43,024 sighting rows), leaving the generalisation resting
on **zero live evidence**. This is the **first and only measured live
instance**: 1,973 records, 23.59 % against 0.00 %, a documented
invariant broken, and AUC 0.6365 of vintage→label.

If the broadening is dropped, a new rule is required, and it must name
the mechanism rather than the trigger:

> Any per-class parameter that determines which records enter a
> dataset — geographic, **temporal**, precision, source or taxon — must
> have its per-class supports compared explicitly, on the axis the
> parameter acts on. **Equal record counts are not evidence of matching
> support**, and where the counts are produced by construction (a 1:1
> sampler) they are not evidence of anything.

**Mechanical enforcement (§3.4) — feasible today, three lines.**
`filter_by_year_gap` already computes and prints the per-class drop
counts separately (`train.py:190-197`). Assert that the per-class drop
*rates* do not diverge beyond a stated tolerance, and fail or warn when
they do. That check would have fired on the first training run ever
executed. Pair it with a per-class year-histogram comparison at
dataset-build time, alongside BUG-0029's proposed spatial-support check
— both are "compare the classes' support" assertions on the same frame.

**Sweep (§3.5), scoped by the mechanism — run by CR-0019 deliverable 8 (2026-09-30; result in PA-0020's Swept? cell: BUG-0073, BUG-0074, BUG-0075).** Original text: Every
acquisition or selection parameter that is applied to one class and not
the other, on any axis. Known candidates: the year floors above;
`MAX_COORD_UNCERTAINTY_M` (`generate_negatives.py:159`, applied to
negatives only — measured **inert**, the field is null in all 265,212
candidate rows, so it is a latent instance rather than a live one); the
`taxonKey` species list, which has no positive-side analogue; and
`predict.py`'s use of `latest_raster_path`, which resolves a 2025
vintage **no training record of either class ever used**.
