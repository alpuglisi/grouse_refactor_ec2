# BUG-0075: the positives' acquisition start year `START_YEAR = 2016` is a literal in two files (`sightings.py`, `ebird.py`) (PA-0025 instance)

> Found by the PA-0020 sweep in CR-0019 deliverable 8, 2026-09-30, at
> `00b0b84` (CR-0019 review B8 named it for this sweep).
> **Status: OPEN (low); owner: lead.**

## 1. Description
The two acquisition paths for positives each define their own year floor
as a literal. They agree today (2016). A change to one and not the other
would give the two positive sources different epochs (PA-0020, time and
source axes) with nothing to catch it, and it would move the epoch of the
300 m buffer and the envelope metrics that `evaluated_sightings_*` feed
(CR-0019 §2), not the split files (`YEAR_MIN` selects those).

## 2. Where encountered
- `sightings.py:23` and `ebird.py:20`, at `00b0b84`.
- Found by the mechanism search recorded in PA-0020's Swept? cell
  (CR-0019 deliverable 8): `grep` for `START_YEAR`, `YEAR_MIN`,
  `range(19xx|20xx`, and comparisons on `year` over the tracked
  production `*.py`.

## 3. What it caused to fail
Nothing observed: both literals are 2016, all 43,024 raw sighting rows
carry the GBIF eBird dataset key (`preregister.txt`), and the `ebird.py`
path is latent (PA-0020 Swept?). It is a divergence waiting for an edit, of the class
PA-0001/PA-0025 exist to prevent. `tests/test_shared_constants.py` does
not pin it.

## 4. What the defect was
`sightings.py:23`:
```python
START_YEAR = 2016
```
`ebird.py:20`:
```python
START_YEAR = 2016
```

## 5. Root cause analysis (Five Whys)
1. *Why two literals?* Each acquisition script was written standalone
   with its own configuration block.
2. *Why was it not moved to `regions.py`?* PA-0025's sweep (CR-0007
   deliverable 6) was scoped to **spatial and region-domain** constants
   (boxes, region codes, state maps, CRS, county path); a year floor is a
   temporal domain constant and was not enumerated.
3. *Why is it one now?* CR-0019 made the time axis a project-chosen
   domain constant (`regions.YEAR_MIN`, pinned under PA-0025), so the
   acquisition floor is its sibling.

**Root cause:** a project-chosen acquisition-domain constant on the time
axis was left outside PA-0025's sweep scope, which enumerated spatial
constants only.

## 6. Corrective action
**None yet.** Fix: `regions.START_YEAR = 2016` (comment: the positives'
acquisition floor, earlier than `YEAR_MIN` by design, CR-0019 §2),
imported by `sightings.py` and `ebird.py`, pinned in
`tests/test_shared_constants.py`. Two production files plus the test:
outside the one-function trivial-fix definition, so it goes with the next
change that touches positive acquisition (BUG-0073's fix CR is the likely
one) or its own small CR. No data changes (same value).

Status: **OPEN** (low). Owner: lead (tracker).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "literal",
"duplicate", "constant", "START_YEAR", "PA-0025".

**Matches:** **BUG-0043/PA-0025** and **BUG-0001/PA-0001** (same
mechanism: a project-chosen constant duplicated as literals);
BUG-0044..0047 (PA-0025's sweep findings).

**Prior-preventive-action failure analysis.** PA-0025 says "a
project-chosen spatial or region-domain constant". Its sweep read that
as geographic and did not enumerate year floors: **too narrow by axis**,
the same failure BUG-0034 §7 found in PA-0018/PA-0020 before their
broadening. CR-0019 already applies PA-0025 to `YEAR_MIN` (pinned).

## 8. Preventive action
**No new rule; PA-0025 applies** (a year floor is an acquisition-domain
constant, as CR-0019's `YEAR_MIN` pin already treats it). The PA-0025
Swept? cell records this finding and the reading "region-domain includes
the acquisition epoch". Mechanical enforcement: the fix adds the pin to
`tests/test_shared_constants.py`; a bare `2016` literal elsewhere stays
review-only (as CR-0019 §2 states for `2020`).

## Cross-references
CR-0019 review B8; PA-0001, PA-0025, PA-0020; BUG-0043.
