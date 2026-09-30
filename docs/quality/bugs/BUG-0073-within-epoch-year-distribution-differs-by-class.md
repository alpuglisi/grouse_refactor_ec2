# BUG-0073: within the common epoch 2020–2024, the two classes' year distributions differ; year alone predicts the label at AUC 0.6615 (PA-0020 time-axis selection asymmetry)

> Filed by CR-0019 deliverable 8, 2026-09-30, at `00b0b84`, as the residual
> of BUG-0034 consequence (b) (CR-0019 §5; proposed there as "BUG-NEW-a",
> review log § Proposed bookkeeping). PA-0024(b): the remainder moved here
> from BUG-0034, which CR-0019 fixed for its root cause.
> **Status: OPEN; owner: lead; fix by its own CR.**

## 1. Description
After CR-0019 both classes span exactly 2020–2024 (one floor,
`regions.YEAR_MIN`; gate E14(b) requires the pooled year sets to be
equal). Their year **distributions** within that span still differ:
negatives are front-loaded on 2020, positives peak in 2022. Because a
record's year selects its raster vintage (`dataset.py:122-126`), vintage
still carries information about the label. Nothing checks the
distributions; E14 checks the support only.

## 2. Where encountered
- CR-0019 pre-registration, `docs/quality/evidence/CR-0019/preregister.txt:41`
  ("year->label AUC after (no filter needed): 0.6615"), and the live run's
  OBS O9 (`docs/quality/evidence/CR-0019/live/acceptance.log`,
  `year_hist.*`).
- Representative year of a positive location:
  `analyze_grouse.py:255-281` (`collapse_duplicate_locations`).
- Representative year of a negative key:
  `generate_negatives.py:160-180` (`dedup_min_gbif_id`, pool step 3).
- Negative acquisition order: `get_negatives.py:247-252` (first-pass
  per-year cap) and `:306-337` (rollover).

## 3. What it caused to fail
Measured on the live post-CR-0019 split files (acceptance record
`ed27583b…`, OBS O9):

| year | 2020 | 2021 | 2022 | 2023 | 2024 | total |
|---|---|---|---|---|---|---|
| negatives (ME+NH+VT) | 1,861 | 1,293 | 1,010 | 380 | 265 | 4,809 |
| positives (ME+NH+VT) | 928 | 1,057 | 1,174 | 708 | 942 | 4,809 |

- Year alone predicts the label at **AUC 0.6615** (`preregister.txt:41`;
  0.6578 on the pre-CR-0019 files after the tolerance-2 filter).
- A model can therefore score some separation from vintage-specific
  raster properties rather than habitat. The size of that effect on a
  trained model is not measured (no retrain yet; CR-0020), and it needs a
  seed-varied null (BUG-0039's lesson).

## 4. What the defect was
Positives, `analyze_grouse.py:268-272` — a location's year is its
**latest** visit:
```python
    visit_stats = sightings.groupby('_loc_key')['year'].agg(
        n_visits='count', first_year='min', last_year='max')

    rep_idx = sightings.groupby('_loc_key')['year'].idxmax()
```
Negatives, `generate_negatives.py:178-180` — a key's year is that of its
**smallest `gbif_id`**, which is the key's earliest year for 98.9 % of
the selected negatives (11.4 % have a later year available; CR-0019
review log, reviewer A's A2, re-measured by the author):
```python
    order = pool["gbif_id"].sort_values(kind="mergesort").index
    first = ~key.loc[order].duplicated(keep="first")
    return pool.loc[order[first.to_numpy()]].reset_index(drop=True)
```
Negative acquisition, `get_negatives.py:247-248` — a first pass capped
per (species, year), then rollover into the years not yet exhausted:
```python
        sp_cap = math.ceil(needed[st] / n_species * args.headroom)
        yr_cap = math.ceil(sp_cap / len(args.years))
```

## 5. Root cause analysis (differential analysis; candidate causes, PA-0016)
Differential between the two classes' paths from raw record to training
row, on the time axis:

| step | positives | negatives |
|---|---|---|
| acquisition floor | 2016 (`START_YEAR`) | 2020 (`--years`) |
| selection floor | `YEAR_MIN` (CR-0019) | `YEAR_MIN` (CR-0019) |
| **representative year of a repeated location** | **latest visit** | **smallest `gbif_id` ≈ earliest** |
| **acquisition order within the epoch** | full download | **per-year first-pass cap, then rollover** |
| draw | – | 1:1 per (region, split); not year-matched |

Measured on the pre-registered P and N (CR-0019 review log, reviewer A,
re-measured by the author): year→label AUC is 0.6615 as specified,
**0.5584** if positives take `max(first_year, 2020)`, and **0.6125** if
negatives take their key's latest year.

1. *Why does year predict the label?* The classes' year histograms
   differ within the common support.
2. *Why do they differ?* Two differences remain on the time axis after
   CR-0019: the representative-year rules pull positives late and
   negatives early; the draw is not stratified by year.
3. *Why were the rules never compared?* Each rule was written for its own
   class (positives: "most recent year" for a collapsed location;
   negatives: an order-free deterministic dedup, CR-0012 step 3) and
   neither is described as a time-axis choice.
4. *Why did PA-0020 not catch it?* PA-0020(ii) requires the classes'
   supports to be compared; a support comparison (E14) cannot see a
   distribution difference within an equal support.

**Stated root cause (to be confirmed by its own check, PA-0016):** the two
classes' per-record year is produced by different selection rules on the
time axis (latest visit vs earliest record), and no check compares the
classes' year distributions, only their supports. The acquisition order
is a second candidate cause; neither is confirmed until the remedy's CR
tests it (the AUC figures above are counterfactual measurements, not a
trained-model effect).

## 6. Corrective action
**None yet.** CR-0019 §5 and § Out of scope leave it to its own CR.
Candidate remedies, not yet chosen:
- **Harmonise the representative-year rule** (no network): e.g. both
  classes take the same rule on a repeated location (AUC 0.5584 or 0.6125
  on the measured variants above).
- **Year-matched draw** (per region, split and year): infeasible from
  today's pool — 6 of 30 cells are short of habitat candidates (215 in
  all; ME train 2024 −70, VT train 2024 −77; `preregister.txt`
  § REJECTED OPTION 1b) — without more 2023–2024 candidates or coarser
  matching.
- **Re-fetch negatives** for 2023–2024 (network; a user decision).
The CR must state the acceptance change (a distribution gate or OBS next to
E14) and is independent of the rule fix's need for network (none).

Status: **OPEN**. Owner: lead (tracker, `CR-0007-0008-OPEN-ISSUES.md`
§ CR-0019). Must be decided before CR-0020's baseline is taken as final,
or CR-0020 records the residual AUC with its baseline.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` (all rows) and `PREVENTIVE_ACTIONS.md` for
"year", "vintage", "epoch", "support", "representative", "dedup",
"per-class".

**Matches:**
- **BUG-0034 / PA-0020** — same axis (time), same consequence (vintage
  predicts the label). BUG-0034 was a **support** difference (disjoint
  year ranges from different acquisition floors), fixed by CR-0019. This
  is a **distribution** difference within an equal support, from
  different selection rules. Not a duplicate: different mechanism step
  (representative-year rule and draw, not the floor), and BUG-0034's fix
  could not reach it. It is the remainder of BUG-0034 consequence (b),
  recorded there.
- **BUG-0029** — same family (per-class acquisition parameter), spatial
  axis.

**Prior-preventive-action failure analysis.**
- **PA-0020** (BUG-0029, broadened by BUG-0034). Clause (i) covers "any
  parameter that decides which records enter a dataset" and (ii) requires
  the **supports** to be compared. A representative-year rule does not
  decide *which* records enter; it decides *which year* an entering record
  carries, so it sits outside (i). And (ii) asks for supports, which are
  now equal. **Too narrow:** the rule addresses membership and support,
  not the per-class distribution of a label-correlated attribute, nor the
  rule that assigns it.
- **PA-0020's sweeps** (CR-0007 deliverable 6; BUG-0034 §8) looked at
  acquisition keys and floors, not at dedup/collapse rules.

## 8. Preventive action
**Deferred to the fix CR, with a stated owner (PA-0022).** The candidate
extension of PA-0020 — "every per-class rule that assigns a
label-correlated attribute (year/vintage, source, precision) to a record
is part of the selection and must be the same rule for both classes, and
the classes' distributions on that axis, not only their supports, are
compared at build time against a stated tolerance" — is written into
`PREVENTIVE_ACTIONS.md` only when the fix CR has confirmed the cause
(PA-0016: the cause is still a hypothesis). Until then PA-0020's Swept?
cell names this BUG as the owner of the within-support time item.

**Sweep (§3.5):** the CR-0019 deliverable-8 PA-0020 sweep
(`PREVENTIVE_ACTIONS.md` PA-0020 Swept?) enumerated the per-class year
rules; its other findings are BUG-0074 (`train.sample_background_points`
single vintage) and BUG-0075 (duplicated `START_YEAR`).

## Cross-references
BUG-0034 (parent; fixed by CR-0019), CR-0019 §5, PA-0020, PA-0016,
PA-0022, PA-0024(b).
