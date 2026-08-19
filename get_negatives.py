"""
gbif_negatives_download.py  (v3 - sufficiency-driven caps + year rollover)

Retrieve negative-candidate species records from the GBIF occurrence API
(eBird Observation Dataset). Changes from v2, driven by the training-set
shortfall (the model saw ~94:1 positive imbalance because too few
negatives survived the downstream pipeline):

  1. HEADROOM RAISED 2.0 -> 6.0 (configurable). v2's x2 assumed mild
     losses; the real pipeline attrition is much harsher, and the buffer
     is the reason: target-group candidates come from the SAME popular
     birding locations as grouse sightings, so the 300m exclusion around
     every grouse location removes a large share of them. Add exact-
     duplicate collapse (hotspot pins), coordinate-uncertainty drops,
     30m thinning, extraction nodata drops, and per-split block
     partitioning, and x2 starves the train pool. Downloading is cheap;
     starved training data is not.
  2. CROSS-YEAR ROLLOVER: v2 split each species cap evenly across years
     and never redistributed - a thin year permanently forfeited its
     quota. v3 does an even first pass, then keeps cycling non-exhausted
     years (continuing from saved page offsets) until each cap is met or
     the data is genuinely gone.
  3. EXHAUSTION vs RATE-LIMIT are reported separately: "GBIF has no more
     records for this species/state" is actionable (add species or
     request the EBD); "fetches kept failing" means just re-run.

Outputs: gbif_negatives_{ME|NH|VT}.csv - same schema; existing rows are
counted toward caps and deduped on startup, so re-running resumes.

After this completes, RE-RUN generate_negatives.py to rebuild the
negative train/val sets from the enlarged candidate pool.
"""
import os
import csv
import math
import time
import argparse
import datetime as dt

import requests

GBIF_API = "https://api.gbif.org/v1"
EOD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"

STATES = {"ME": "Maine", "NH": "New Hampshire", "VT": "Vermont"}

TARGET_SPECIES = {
    "Ovenbird": "Seiurus aurocapilla",
    "Black-throated Blue Warbler": "Setophaga caerulescens",
    "Hermit Thrush": "Catharus guttatus",
    "Blue-headed Vireo": "Vireo solitarius",
    "Brown Creeper": "Certhia americana",
    "Pileated Woodpecker": "Dryocopus pileatus",
}

PAGE_LIMIT = 300
OFFSET_CAP = 100000          # GBIF hard cap on offset paging per query
MAX_RETRIES = 4
THROTTLE_SECONDS = 0.05      # insurance against GBIF's reactive soft limit
HEADROOM_DEFAULT = 6.0       # see module docstring

CSV_FIELDS = ["common_name", "scientific_name", "longitude", "latitude",
              "obs_date", "year", "month", "state", "gbif_id",
              "how_many", "coord_uncertainty_m"]


def api_get(session, path, params=None):
    url = f"{GBIF_API}{path}"
    for attempt in range(MAX_RETRIES):
        try:
            res = session.get(url, params=params, timeout=60)
        except requests.exceptions.RequestException:
            time.sleep(2 ** attempt)
            continue
        if res.status_code == 200:
            time.sleep(THROTTLE_SECONDS)
            try:
                return res.json()
            except ValueError:
                return None
        if res.status_code in (429, 500, 502, 503):
            time.sleep(2 ** (attempt + 1))
            continue
        return None
    return None


def verify_dataset(session):
    meta = api_get(session, f"/dataset/{EOD_DATASET_KEY}")
    title = (meta or {}).get("title", "")
    if "ebird" not in title.lower():
        raise SystemExit(
            f"Dataset key {EOD_DATASET_KEY} resolved to '{title or 'nothing'}' "
            f"- not the eBird Observation Dataset. Aborting.")
    print(f"Dataset verified: {title}")


def resolve_taxon_keys(session):
    print("Resolving GBIF taxon keys...")
    keys = {}
    for common, sci in TARGET_SPECIES.items():
        m = api_get(session, "/species/match", params={"name": sci})
        key = (m or {}).get("usageKey")
        if not key or (m or {}).get("matchType", "NONE") == "NONE":
            raise SystemExit(f"Could not resolve '{sci}' ({common}). Aborting.")
        print(f"  {common}: taxonKey={key}")
        keys[common] = key
    return keys


def positives_needed(states, override=None):
    needed = {}
    for st in states:
        path = f"data/pipeline/thinned_positives_{st}.csv"
        if os.path.exists(path):
            with open(path) as f:
                needed[st] = sum(1 for _ in f) - 1
        elif override is not None:
            needed[st] = override
        else:
            raise SystemExit(
                f"{path} not found and no --needed-per-state given. Run "
                f"prepare_training_data.py first, or pass the override.")
    return needed


def load_existing(states):
    counts = {}
    seen = set()
    for st in states:
        path = f"data/negatives/gbif_negatives_{st}.csv"
        if not os.path.exists(path):
            continue
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or "gbif_id" not in reader.fieldnames:
                raise SystemExit(
                    f"\n{path} doesn't have this script's expected columns.\n"
                    f"  Found columns: {reader.fieldnames}\n"
                    f"  Expected:      {CSV_FIELDS}\n\n"
                    f"Likely cause: a file from another source saved under "
                    f"this name. Rename/move it, or share its header and "
                    f"I'll add a column-mapping import path.")
            for row in reader:
                seen.add(row["gbif_id"])
                k = (st, row["common_name"])
                counts[k] = counts.get(k, 0) + 1
    return counts, seen


def fetch_capped(session, writer, base_params, st, common, sci, cap_left,
                 seen, start_offset=0):
    """Page one (state, species, year) partition from start_offset,
    writing at most cap_left new records. Returns
    (written, stopped_early, exhausted, next_offset):
      stopped_early - fetches failed after retries (rate-limit territory);
                      partition is retryable
      exhausted     - GBIF reported end of records (or offset cap hit);
                      this partition genuinely has no more data"""
    n = 0
    offset = start_offset
    stopped_early = False
    exhausted = False
    while n < cap_left:
        res = api_get(session, "/occurrence/search",
                      params={**base_params, "limit": PAGE_LIMIT,
                              "offset": offset})
        if res is None:
            stopped_early = True
            break
        for r in res.get("results", []):
            if n >= cap_left:
                break
            gid = str(r.get("gbifID"))
            lat, lon = r.get("decimalLatitude"), r.get("decimalLongitude")
            if gid in seen or lat is None or lon is None:
                continue
            seen.add(gid)
            writer.writerow({
                "common_name": common,
                "scientific_name": sci,
                "longitude": lon,
                "latitude": lat,
                "obs_date": (r.get("eventDate") or "")[:10],
                "year": r.get("year"),
                "month": r.get("month"),
                "state": st,
                "gbif_id": gid,
                "how_many": r.get("individualCount"),
                "coord_uncertainty_m": r.get("coordinateUncertaintyInMeters"),
            })
            n += 1
        if n >= cap_left:
            break                      # page partially consumed; resume
                                       # at same offset later (dedupe
                                       # skips what we already took)
        if res.get("endOfRecords", True):
            exhausted = True
            break
        offset += PAGE_LIMIT
        if offset >= OFFSET_CAP:
            exhausted = True
            break
    return n, stopped_early, exhausted, offset


def main():
    parser = argparse.ArgumentParser(
        description="Sufficiency-driven, state-interleaved GBIF negatives "
                    "download with cross-year rollover.")
    parser.add_argument("--states", nargs="+", default=list(STATES.keys()),
                        choices=list(STATES.keys()))
    parser.add_argument("--years", nargs="+", type=int,
                        default=list(range(2020, dt.date.today().year + 1)))
    parser.add_argument("--needed-per-state", type=int, default=None)
    parser.add_argument("--headroom", type=float, default=HEADROOM_DEFAULT,
                        help="Multiplier on needed/species (default: "
                             "%(default)s; raise it if generate_negatives"
                             ".py still reports undersupplied splits).")
    args = parser.parse_args()

    session = requests.Session()
    verify_dataset(session)
    taxa = resolve_taxon_keys(session)
    n_species = len(taxa)

    needed = positives_needed(args.states, args.needed_per_state)
    caps = {}
    for st in args.states:
        sp_cap = math.ceil(needed[st] / n_species * args.headroom)
        yr_cap = math.ceil(sp_cap / len(args.years))
        caps[st] = {"species_cap": sp_cap, "year_cap": yr_cap}
        print(f"  {st}: {needed[st]:,} positives -> cap "
             f"{sp_cap:,}/species (first pass {yr_cap:,}/species/year, "
             f"then rollover), ~{sp_cap * n_species:,} total")

    counts, seen = load_existing(args.states)
    if counts:
        print(f"  Resuming: {sum(counts.values()):,} existing records "
             f"counted toward caps.")

    writers = {}
    for st in args.states:
        path = f"data/negatives/gbif_negatives_{st}.csv"
        new = not os.path.exists(path)
        fh = open(path, "a", newline="")
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        if new:
            w.writeheader()
        writers[st] = (fh, w)

    def base_params(st, key, year):
        return {"datasetKey": EOD_DATASET_KEY, "taxonKey": key,
                "country": "US", "stateProvince": STATES[st],
                "year": year, "hasCoordinate": "true"}

    # per-(st, species, year) paging state for rollover continuation
    pstate = {(st, c, y): {"offset": 0, "exhausted": False}
              for st in args.states for c in taxa for y in args.years}
    total = 0
    stalled_final = []
    try:
        # ---- PASS 1: even spread (year -> state -> species) ------------
        print("\nPass 1 (even per-year quotas):")
        for year in args.years:
            for st in args.states:
                for common, key in taxa.items():
                    k = (st, common)
                    sp_cap = caps[st]["species_cap"]
                    quota = min(caps[st]["year_cap"],
                                sp_cap - counts.get(k, 0))
                    if quota <= 0:
                        continue
                    ps = pstate[(st, common, year)]
                    n, stopped, exhausted, off = fetch_capped(
                        session, writers[st][1], base_params(st, key, year),
                        st, common, TARGET_SPECIES[common], quota, seen,
                        start_offset=ps["offset"])
                    ps["offset"] = off
                    ps["exhausted"] = exhausted
                    counts[k] = counts.get(k, 0) + n
                    total += n
                    if n:
                        print(f"  [{st}] {common} {year}: +{n:,} "
                             f"({counts[k]:,}/{sp_cap:,})"
                             + (" [year exhausted]" if exhausted else ""))
                writers[st][0].flush()

        # ---- PASS 2+: rollover - keep cycling non-exhausted years until
        # caps met or data genuinely gone --------------------------------
        print("\nRollover passes (redistributing unmet quota across years "
             "with remaining data):")
        progress = True
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
                        total += n
                        if n:
                            progress = True
                            print(f"  [{st}] {common} {year} (rollover): "
                                 f"+{n:,} ({counts[k]:,}/{sp_cap:,})")
                        if stopped:
                            stalled_final.append((st, common, year))
                writers[st][0].flush()
    except KeyboardInterrupt:
        print("\nInterrupted - existing rows count toward caps on re-run.")
    finally:
        for fh, _ in writers.values():
            fh.close()

    print(f"\nDone: {total:,} new records this run.")
    for st in args.states:
        sp_cap = caps[st]["species_cap"]
        print(f"  {st} (cap {sp_cap:,}/species):")
        for common in taxa:
            got = counts.get((st, common), 0)
            if got >= sp_cap:
                note = "met"
            else:
                all_exhausted = all(pstate[(st, common, y)]["exhausted"]
                                    for y in args.years)
                note = ("GBIF EXHAUSTED - no more records exist for this "
                        "species/state/date range; widen years, add "
                        "species, or request the EBD"
                        if all_exhausted else
                        "short - re-run to retry (fetch failures, not "
                        "data exhaustion)")
            print(f"    {common}: {got:,}/{sp_cap:,} ({note})")
    if stalled_final:
        print(f"\n{len(set(stalled_final))} partition(s) hit repeated fetch "
             f"failures; simply re-running resumes them.")
    print("\nNEXT STEP: re-run generate_negatives.py to rebuild the "
         "negative train/val sets from this enlarged pool.")


if __name__ == "__main__":
    main()

