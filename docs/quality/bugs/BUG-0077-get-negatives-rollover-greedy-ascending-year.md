# BUG-0077: `get_negatives.py` rollover hands each species' whole unmet quota to the first non-exhausted year, in ascending order (candidate code cause of BUG-0073's 2020 front-loading)

> Found by the 2026-09-30 static code review at `3b3e7d1`. The loop
> defect is confirmed from the code; its link to BUG-0073's measured
> counts is a candidate cause under PA-0016 (no data here to re-measure).
> **Status: OPEN; owner: lead; fixed with BUG-0073's CR (needs a
> re-fetch, user decision).**

## 1. Description
Pass 1 of the negatives download fills each species' cap evenly across
`--years` (`yr_cap = ceil(sp_cap / len(years))`). Pass 2 ("rollover")
then walks the years **in ascending order** and passes the species'
**entire** remaining shortfall to each non-exhausted year in turn. The
first year with data left, which is the earliest year in the list,
absorbs the whole shortfall. With `--years` defaulting to
`range(YEAR_MIN, today + 1)` (seven years, of which the two most recent
are near-empty on GBIF), the shortfall is about two sevenths of every
species' cap and it lands on 2020.

## 2. Where encountered
- `get_negatives.py:306-333` (rollover loop), `:247-249` (caps),
  `:230-231` (`--years` default).
- Downstream: `generate_negatives.py:178-180` keeps the smallest
  `gbif_id` per coordinate (earliest record), so the year written into
  the negatives' `year` column inherits the front-loading; `dataset.py`
  resolves each record's raster vintage from that year.

## 3. What it caused to fail
BUG-0073 measured negatives at 1,861 of 4,809 in 2020 against positives
peaking in 2022, and year alone predicting the label at AUC 0.6615, after
CR-0019 equalised the year *supports*. This loop is the acquisition-side
mechanism that can produce exactly that shape; BUG-0073 lists
"`get_negatives.py` acquisition order" as a candidate without naming the
loop. Vintage-bearing features (`tsd`, `fdist`, TreeMap) then carry a
label correlate into training.

## 4. What the defect was
`get_negatives.py:311-333`:
```python
        while progress:
            progress = False
            for st in args.states:
                for common, key in taxa.items():
                    k = (st, common)
                    sp_cap = caps[st]["species_cap"]
                    remaining = sp_cap - counts.get(k, 0)
                    if remaining <= 0:
                        continue
                    for year in args.years:
                        ps = pstate[(st, common, year)]
                        if ps["exhausted"] or remaining <= 0:
                            continue
                        n, stopped, exhausted, off = fetch_capped(
                            session, writers[st][1],
                            base_params(st, key, year), st, common,
                            TARGET_SPECIES[common], remaining, seen,
                            start_offset=ps["offset"])
                        ps["offset"] = off
                        ps["exhausted"] = exhausted
                        counts[k] = counts.get(k, 0) + n
                        remaining -= n
```
`remaining` (the whole shortfall) is the cap passed to `fetch_capped` for
the first year; only what that year cannot supply reaches the next.

## 5. Root cause analysis (Five Whys)
1. *Why is 2020 over-represented?* The rollover gives the first
   non-exhausted year the full shortfall, and 2020 is first.
2. *Why the full shortfall?* The per-year cap (`yr_cap`) applies only in
   pass 1; pass 2 has no per-year allocation, only `remaining`.
3. *Why ascending order?* `args.years` is a range; the loop iterates it
   as given.
4. *Why not caught?* Gate E14 (CR-0019) compares the positive and
   negative year *sets*; no check compares the per-year *distributions*
   of the two classes, and the acquisition log prints per-year lines
   nobody re-reads.
5. *Why no rule?* PA-0020 asks that acquisition *query keys* be read and
   that supports be compared; the allocation loop is control flow around
   the query, not a key.

**Root cause:** the quota-rollover allocation is greedy in a fixed year
order with no per-year bound, and no build-time check compares the
per-class year distributions (only their supports).

## 6. Corrective action
**None yet.** Proposed, inside BUG-0073's CR: bound each rollover fetch
to `ceil(remaining / n_open_years)` per pass (round-robin), or allocate
the shortfall proportionally to the positives' per-year counts; print the
per-year totals per species at the end; add an OBS row (per PA-0021(f))
comparing the positive and negative per-year histograms. Any change
requires a re-fetch and a rebuild of negatives (user decision recorded in
BUG-0073). Status: **OPEN**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0022-negatives-rollover-round-robin.md` (DRAFT v3 after round-1 review; nothing implemented). **User decision 2026-09-30: no re-fetch** — the code fix is latent until the next acquisition; today's year imbalance stays with BUG-0073's no-network remedy. Round 1 found the same defect on a resumed run's first pass (`load_existing` has no per-year counts); v3 covers it. The per-class year-distribution observation (O11) is CR-0030.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "year",
"rollover", "quota", "acquisition", "distribution".

**Matches:** BUG-0073 (the symptom; this entry is a candidate cause on
the acquisition side, distinct from the representative-year rules it
names), BUG-0034 / PA-0020 (per-class time-axis asymmetry), BUG-0074.

**Prior-preventive-action failure analysis.** PA-0020 (ii) requires a
support comparison at build time; E14 implements it and passed, because
the supports are equal. PA-0020 (v) requires reading every query key; the
CR-0019 sweep did, and classed "acquisition order" as an untested
candidate because the loop is not a query key. Category: too narrow
(query keys and supports, not allocation logic and distributions).

## 8. Preventive action
**PA-0034** (extends PA-0020): an acquisition script that fills a quota
across strata (years, species, states) allocates round-robin or
proportionally, never greedily in a fixed stratum order; and the
PA-0020 (ii) build-time comparison covers the per-class **distribution**
over each stratum as a named OBS statistic, not only the support.

**Sweep (§3.5), quota-filling loops over strata in acquisition scripts:**
`get_negatives.py` (this); `sightings.py` (full download per year, no
quota); `ebird.py` (per-day full fetch, no quota); no other instance.

## Cross-references
BUG-0073 (symptom, owner of the CR), BUG-0034, PA-0016, PA-0020, PA-0034,
CR-0019 E14.
