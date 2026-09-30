# BUG-0089: `ebird.py` writes `lat`/`lng`, and `analyze_grouse.py` (and `check_partition.py`) detect coordinate columns by the substring "lon", so every eBird-API sightings file is skipped with one print line (latent)

> Found by the 2026-09-30 static code review at `3b3e7d1`. Latent:
> CR-0019's preregistration found all 43,024 raw sighting rows come from
> the GBIF path (BUG-0034's source-axis note: "the `ebird.py` path is
> latent (no rows)").
> **Status: OPEN (latent); owner: lead; fix with the next change to the
> sightings acquisition (BUG-0073/BUG-0075's CR).**

## 1. Description
Both acquisition scripts write `data/sightings/{state}_sightings_{year}.csv`
(`PATH_TEMPLATES["sightings"]`). `sightings.py` keeps GBIF's column
names (`decimalLongitude`/`decimalLatitude`); `ebird.py` writes the eBird
API's `lat`/`lng`. `analyze_grouse.py` finds the coordinate columns by
`'lon' in c.lower()` and `'lat' in c.lower()`; `"lng"` contains no
"lon", so an eBird file is reported "No lon/lat columns found …
Skipping." and dropped. Because both scripts write the same filename, an
eBird run for a state/year silently replaces the GBIF file and the year
then vanishes from the analysis.

## 2. Where encountered
- `ebird.py:35-40` (`csv_headers` with `"lat", "lng"`), `:48`
  (filename).
- `analyze_grouse.py:174-177`; the same rule at
  `check_partition.py:169-172`.
- `sightings.py:136-138` (same filename pattern).

## 3. What it caused to fail
Latent today. If the eBird path is ever used: a state/year of positives
disappears with a single log line (mixed sources), or the run exits at
`analyze_grouse.py:186` if it is the only source (loud).

## 4. What the defect was
`ebird.py:35-40`:
```python
    csv_headers = [
        "speciesCode", "comName", "sciName", "locId", "locName", 
        "obsDt", "howMany", "lat", "lng", "obsValid", 
        "obsReviewed", "locationPrivate", "subId", "subnational2Code",
        "subnational2Name", "exoticCategory"
    ]
```
`analyze_grouse.py:174-177`:
```python
        lon_col = next((c for c in df.columns if 'lon' in c.lower()), None)
        lat_col = next((c for c in df.columns if 'lat' in c.lower()), None)
        if not (lon_col and lat_col):
            print(f"  [!] No lon/lat columns found in {os.path.basename(file)}. Skipping.")
```

## 5. Root cause analysis (Five Whys)
1. *Why is the file skipped?* No column contains "lon".
2. *Why?* The eBird API names the field `lng`, and `ebird.py` passes
   the API's names through.
3. *Why does the reader guess column names?* It was written to accept
   either source without a shared schema.
4. *Why no rule?* PA-0026 covers stale copies by what they write; two
   **live** writers of one path with different schemas is not a stale
   copy, and no rule requires one schema per `PATH_TEMPLATES` entry.

**Root cause:** two writers of one `PATH_TEMPLATES` entry emit
different schemas, and the readers select columns by substring instead
of by a shared column list.

## 6. Corrective action
**None yet.** Proposed, with BUG-0073/BUG-0075's acquisition CR: one
`SIGHTINGS_COLUMNS` list in `regions.py` (or a sightings module) written
by both scripts (`ebird.py` renames `lat`/`lng` to it), readers select
by exact name, a test pins both writers' headers to the list.
Status: **OPEN (latent)**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0028-sightings-schema-shared-columns.md` (DRAFT v1, awaiting independent review under CLAUDE.md §1.2; nothing implemented).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "ebird",
"column", "schema", "lon".

**Matches:** BUG-0034 (source-axis note naming the eBird path as
latent), BUG-0075 (duplicated `START_YEAR` in both scripts), BUG-0045
(eBird code maps), PA-0020 (source axis), PA-0026.

**Prior-preventive-action failure analysis.** PA-0020's source-axis
item recorded the path as latent and stopped; PA-0026 looks for stale
writers, not live writers with divergent schemas. Category: too narrow.

## 8. Preventive action
**PA-0045**: every writer of a `PATH_TEMPLATES` entry writes one schema,
defined once as a shared column list and pinned by a test; readers
select columns by exact name from that list, never by substring.

**Sweep (§3.5), substring column detection and multi-writer entries:**
`analyze_grouse.py:174-175`, `check_partition.py:169-170` (this);
writers of `sightings`: `sightings.py`, `ebird.py` (this). No other
`PATH_TEMPLATES` entry has two live writers (`legacy/` copies are
guarded, PA-0026).

## Cross-references
BUG-0034, BUG-0045, BUG-0075; PA-0020, PA-0026, PA-0045.
