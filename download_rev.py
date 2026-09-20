import os
import re
import time
import json
import shutil
import zipfile
import threading
import requests
import urllib3
import rasterio
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =======================================================================
# 1. REGIONS (lon/lat AOI - LFPS accepts WGS84 min_lon min_lat max_lon
#    max_lat; delivered GeoTIFFs come back in LANDFIRE's native Albers)
# =======================================================================
BOXES_COORDINATES = {
    "ME": (-71.158, 42.889, -66.852, 47.555),
    "NH": (-72.626, 42.605, -70.600, 45.398),
    "VT": (-73.510, 42.632, -71.422, 45.112),
}

EMAIL = "your.email@example.com"

# =======================================================================
# 2. CONFIGURATION
# =======================================================================
YEARS = ["2020", "2022", "2023", "2024", "2025"]

# feature key -> LFPS product code (as used in LF{year}_{code} layer names)
LAYER_CODES = {
    # original stack
    "evt": "EVT", "evh": "EVH", "evc": "EVC", "sclass": "SClass",
    "slope": "SlpD", "gradient": "Asp",
    # added for habitat structure: FDist = disturbance type/severity/
    # time-since (proxy for "recently disturbed, regenerating stand");
    # CH = overstory tree canopy height (distinct from EVH, which can
    # reflect any lifeform); CC = overstory tree canopy cover (distinct
    # from EVC's all-lifeform total) - canopy openness over dense
    # understory regrowth is close to the textbook grouse habitat profile.
    "fdist": "FDist",
    "ch": "CH",
    "cc": "CC",
}
FEATURES = list(LAYER_CODES.keys())
TOPO_FEATURES = {"slope", "gradient"}     # static; fetched once (2020) and
                                          # copied to other years in phase 2

# Verified-unavailable (year, feature) pairs, skipped to save submit/poll
# cycles: LF2020 non-topo products were retired from LFPS in Dec 2025, and
# LF2025 SClass is not yet published (as of Aug 2026). FDist/CH/CC follow
# the normal annual release cycle (unlike SClass) so they aren't
# pre-skipped for 2025 - if any 2025 layer fails with 'Invalid products',
# add that (year, feature) pair here.
KNOWN_UNAVAILABLE = {("2025", "sclass")} | {
    ("2020", f) for f in FEATURES if f not in TOPO_FEATURES
}

# Concurrency: LFPS does the heavy work server-side per job, so wall-clock
# time is dominated by job processing, not bandwidth. Submitting several
# jobs at once is the real speedup. Kept modest to stay polite to a
# shared federal service - raise carefully if jobs aren't being rejected.
MAX_CONCURRENT_JOBS = 4
POLL_SECONDS = 5

BASE_URL = "https://lfps.usgs.gov/api/job"
SUBMIT_URL = f"{BASE_URL}/submit"
STATUS_URL = f"{BASE_URL}/status"
DOWNLOAD_URL_RE = re.compile(r'https?://[^\s"\']+\.zip')
# The same host publishes one ArcGIS ImageServer per product and
# vintage, and the per-vintage folder listing is a release-status API:
# a product absent from Landfire_LF{year}'s listing does not exist for
# that vintage at all, so there is no point submitting (and polling,
# and content-validating) a job for it. Checked once per vintage before
# planning. LANDFIRE rolls vintages out by GeoArea, so a product CAN be
# listed and still be empty for the Northeast (LF2025 vegetation for
# ME/NH/VT is scheduled for November 2026, SClass for December 2026) -
# the post-download content check stays as the second line of defence.
SERVICES_URL = "https://lfps.usgs.gov/arcgis/rest/services"

OUT_DIR = "data/landfire"
# Existing files are NEVER overwritten or deleted by this script. A
# download is written to a temp file and content-validated there; only
# a valid result is moved into place, and any file already at that path
# (e.g. an empty placeholder clip kept on disk while a vintage is
# awaited, or a hand-obtained file) is first moved, unchanged, into
# REPLACED_DIR - a subdirectory, so the raster discovery globs never see
# it. An earlier backup of the same name is never replaced either: the
# new one gets a timestamp suffix.
REPLACED_DIR = os.path.join(OUT_DIR, "replaced")

# A job can report "Succeeded" and produce a well-formed, correctly-
# georeferenced GeoTIFF that is nonetheless entirely nodata - this
# happens when LFPS accepts an AOI request for a region whose data for
# that product/vintage isn't populated yet (e.g. LANDFIRE's LF2025
# rollout is staggered by GeoArea; requesting an unreleased GeoArea's
# extent "succeeds" and returns an empty clip, not an error). Job status
# alone can't detect this - the content has to be checked after download.
MIN_VALID_PIXEL_FRAC = 0.01   # below this fraction non-nodata, reject

_print_lock = threading.Lock()
def log(msg):
    with _print_lock:
        print(msg, flush=True)


def bbox_str(region):
    min_lon, min_lat, max_lon, max_lat = BOXES_COORDINATES[region]
    return f"{min_lon} {min_lat} {max_lon} {max_lat}"


def _raster_valid_fraction(path):
    """Fraction of non-nodata pixels in a raster's first band. Returns
    None (skip the check) if the file can't be opened as a raster at all
    - that's a different failure mode, already handled by the zip/tif
    checks above."""
    try:
        with rasterio.open(path) as src:
            data = src.read(1)
            if src.nodata is None:
                return 1.0   # no nodata value defined - can't judge, allow it
            n_valid = int((data != src.nodata).sum())
            return n_valid / data.size if data.size else 0.0
    except Exception:
        return None


def published_products(year, session=None):
    """Product codes LFPS lists for one vintage (e.g. {'EVT', 'EVH',
    'FDist', ...}), parsed from the ArcGIS folder listing's service
    names (`Landfire_LF2024/LF2024_EVT_CONUS`). None when the listing
    can't be fetched or parsed - callers then fall back to trying the
    job, exactly as before this check existed. Topo products live in a
    separate `Landfire_Topo` folder and only at the LF2020 vintage, so
    they are looked up there."""
    session = session or make_session()
    folder = "Landfire_Topo" if year == "2020" else f"Landfire_LF{year}"
    try:
        res = session.get(f"{SERVICES_URL}/{folder}", params={"f": "pjson"},
                          timeout=30)
        if res.status_code != 200:
            return None
        services = res.json().get("services") or []
    except Exception:
        return None
    codes = set()
    pat = re.compile(rf"^LF{year}_([A-Za-z0-9]+)(?:_|$)")
    for svc in services:
        name = str(svc.get("name", "")).split("/")[-1]
        m = pat.match(name)
        if m:
            codes.add(m.group(1))
    return codes or None


def _backup_existing(path):
    """Move whatever is at `path` into REPLACED_DIR without overwriting
    an earlier backup. Returns the backup path, or None if nothing was
    there."""
    if not os.path.exists(path):
        return None
    os.makedirs(REPLACED_DIR, exist_ok=True)
    dest = os.path.join(REPLACED_DIR, os.path.basename(path))
    if os.path.exists(dest):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        root, ext = os.path.splitext(dest)
        dest = f"{root}.{stamp}{ext}"
    shutil.move(path, dest)
    return dest


def _place_result(tmp_path, out_filepath):
    """Install a validated download at out_filepath. The previous file,
    if any, is backed up first (never deleted). Returns a note for the
    log."""
    backup = _backup_existing(out_filepath)
    os.replace(tmp_path, out_filepath)
    return f" (previous file kept at {backup})" if backup else ""


def make_session():
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/115.0.0.0 Safari/537.36",
        "Accept": "application/json",
    })
    return s


# =======================================================================
# 3. ONE DOWNLOAD TASK (runs inside a worker thread)
# =======================================================================
def download_one(region, year, feature):
    """Submit one LFPS job, poll it, download and extract the result.
    Returns (task, status_string). Each worker uses its own Session -
    requests.Session is not guaranteed thread-safe."""
    task = f"{region} {year} {feature}"
    layer_code = f"LF{year}_{LAYER_CODES[feature]}"
    out_filename = f"{region}_{year}_{feature}.tif"
    out_filepath = os.path.join(OUT_DIR, out_filename)
    session = make_session()

    params = {
        "Layer_List": layer_code,
        "Area_of_Interest": bbox_str(region),
        "Email": EMAIL,
    }

    try:
        res = session.get(SUBMIT_URL, params=params, timeout=30)
        if res.status_code != 200:
            return task, f"submit HTTP {res.status_code}: {res.text[:200].strip()}"
        res_json = res.json()
    except Exception as e:
        return task, f"submit error: {e}"

    if res_json.get("success") is False:
        return task, f"server rejected job: {res_json.get('message')}"
    job_id = res_json.get("jobId")
    if not job_id:
        return task, f"no jobId in response: {res_json}"

    log(f"  [~] {task}: job {job_id} submitted ({layer_code})")

    status_json = {}
    while True:
        try:
            status_res = session.get(STATUS_URL, params={"JobId": job_id}, timeout=30)
            status_json = status_res.json()
        except Exception as e:
            return task, f"status error: {e}"

        status = str(status_json.get("status", "")).lower()
        if "succeed" in status:
            break
        if status in ("failed", "canceled", "cancelled") or "fail" in status:
            msgs = status_json.get("messages", [])
            err = next((m.get("description", "") for m in msgs
                        if isinstance(m, dict) and "Error" in str(m.get("type", ""))
                        and "Invalid" in str(m.get("description", ""))), None)
            return task, f"job failed: {err or msgs}"
        time.sleep(POLL_SECONDS)

    download_url = None
    for key in ("downloadUrl", "download_url", "resultUrl", "url"):
        if isinstance(status_json.get(key), str) and status_json[key].endswith(".zip"):
            download_url = status_json[key]
            break
    if not download_url:
        m = DOWNLOAD_URL_RE.search(json.dumps(status_json))
        if m:
            download_url = m.group(0)
    if not download_url:
        return task, "no download URL in status payload"

    zip_path = os.path.join(OUT_DIR, f"temp_{job_id}.zip")
    tmp_tif = os.path.join(OUT_DIR, f"temp_{job_id}.tif")
    # The LFPS job has already succeeded server-side at this point; the
    # result zip stays downloadable, so transient transfer failures
    # (IncompleteRead / broken connections, common with several
    # concurrent streams) are retried here instead of discarding the
    # finished job and re-submitting it on the next run.
    DOWNLOAD_RETRIES = 3
    last_err = None
    try:
        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            try:
                with session.get(download_url, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(zip_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            f.write(chunk)

                with zipfile.ZipFile(zip_path, 'r') as z:
                    if z.testzip() is not None:
                        raise zipfile.BadZipFile("zip failed integrity check")
                    names = z.namelist()
                    tifs = [n for n in names if n.lower().endswith('.tif')]
                    if not tifs:
                        return task, "no .tif inside downloaded zip"
                    with z.open(tifs[0]) as zf, open(tmp_tif, "wb") as f:
                        shutil.copyfileobj(zf, f)

                    # Content validation: a "Succeeded" job can still
                    # deliver a well-formed, correctly-georeferenced,
                    # entirely-empty raster (see MIN_VALID_PIXEL_FRAC
                    # comment above). Job status can't catch this -
                    # check the actual pixel content before accepting.
                    pct_valid = _raster_valid_fraction(tmp_tif)
                    if pct_valid is not None and pct_valid < MIN_VALID_PIXEL_FRAC:
                        os.remove(tmp_tif)      # the existing file, if any, is untouched
                        return task, (
                            f"job succeeded but raster is empty "
                            f"({pct_valid * 100:.2f}% valid pixels) - "
                            f"almost certainly means this product/vintage "
                            f"isn't populated yet for this region (e.g. "
                            f"LANDFIRE's staggered GeoArea rollout), not a "
                            f"transfer error. Retrying won't help; check "
                            f"LANDFIRE's release schedule.")

                    # Preserve attribute tables / metadata sidecars
                    # (VALUE -> class-name crosswalks) rather than
                    # discarding them.
                    meta_files = [n for n in names
                                 if n != tifs[0] and not n.endswith('/')]
                    if meta_files:
                        meta_dir = os.path.join(
                            OUT_DIR,
                            f"{os.path.splitext(out_filename)[0]}_meta")
                        os.makedirs(meta_dir, exist_ok=True)
                        for name in meta_files:
                            dest = os.path.join(meta_dir,
                                                os.path.basename(name))
                            if os.path.exists(dest):
                                continue          # never overwrite
                            with z.open(name) as zf, open(dest, "wb") as f:
                                shutil.copyfileobj(zf, f)
                    note = _place_result(tmp_tif, out_filepath)
                return task, "ok" + note
            except (requests.exceptions.RequestException,
                    zipfile.BadZipFile, EOFError, OSError) as e:
                last_err = e
                if os.path.exists(tmp_tif):
                    os.remove(tmp_tif)        # never leave a partial tif;
                                              # the existing file is untouched
                if attempt < DOWNLOAD_RETRIES:
                    log(f"  [~] {task}: transfer failed "
                       f"(attempt {attempt}/{DOWNLOAD_RETRIES}: {e}) - "
                       f"retrying download...")
                    time.sleep(5 * attempt)
        return task, f"download/extract error after {DOWNLOAD_RETRIES} attempts: {last_err}"
    finally:
        for p in (zip_path, tmp_tif):
            if os.path.exists(p):
                os.remove(p)


# =======================================================================
# 4. TASK PLANNING + TWO-PHASE EXECUTION
# =======================================================================
def plan_tasks(refetch_empty=True):
    """Everything that needs an actual network download. Topo features
    are planned for 2020 only; other years get filesystem copies of the
    2020 baseline in phase 2 (can't run concurrently with phase 1
    because the copies depend on the baseline existing).

    refetch_empty: re-plan an existing file whose content is (near-)
    empty - a placeholder from an unpublished vintage. A successful
    re-fetch backs the placeholder up (see REPLACED_DIR) rather than
    overwriting it; a failed one leaves it exactly as it was."""
    tasks = []
    listings = {}
    for region in BOXES_COORDINATES:
        for year in YEARS:
            for feature in FEATURES:
                if feature in TOPO_FEATURES and year != "2020":
                    continue
                if (year, feature) in KNOWN_UNAVAILABLE:
                    continue
                # Pre-flight: skip a product LFPS does not list for this
                # vintage (e.g. LF2025 SClass) instead of submitting a
                # job that fails or returns nothing. None = listing
                # unavailable -> try the job as before.
                if year not in listings:
                    listings[year] = published_products(year)
                    if listings[year] is None:
                        log(f"  [~] LF{year}: product listing unreachable "
                            f"- will try jobs without a pre-flight check.")
                    else:
                        log(f"  [i] LF{year} publishes: "
                            f"{sorted(listings[year])}")
                codes = listings[year]
                if codes is not None and LAYER_CODES[feature] not in codes:
                    if region == list(BOXES_COORDINATES)[0]:
                        log(f"  [-] LF{year}_{LAYER_CODES[feature]}: not "
                            f"published for this vintage - skipped for "
                            f"every region.")
                    continue
                out = os.path.join(OUT_DIR, f"{region}_{year}_{feature}.tif")
                if os.path.exists(out):
                    if not refetch_empty:
                        continue
                    # A file that exists but is (near-)empty is a
                    # placeholder from a vintage LANDFIRE had not yet
                    # published for this GeoArea when it was fetched -
                    # the content check below only started rejecting
                    # those after some were already on disk. Treat it
                    # as missing so the next run re-fetches it, instead
                    # of the empty file blocking the real data forever.
                    frac = _raster_valid_fraction(out)
                    if frac is None or frac >= MIN_VALID_PIXEL_FRAC:
                        continue
                    log(f"  [~] {region} {year} {feature}: existing file "
                        f"is {frac * 100:.2f}% valid - will re-download; "
                        f"the existing file is kept (backed up under "
                        f"{REPLACED_DIR} only if a valid replacement "
                        f"arrives).")
                tasks.append((region, year, feature))
    return tasks


def copy_topo_baselines():
    copied = 0
    for region in BOXES_COORDINATES:
        for feature in TOPO_FEATURES:
            base = os.path.join(OUT_DIR, f"{region}_2020_{feature}.tif")
            if not os.path.exists(base):
                log(f"  [!] Missing 2020 {feature} baseline for {region}; "
                   f"cannot copy to other years.")
                continue
            for year in YEARS:
                if year == "2020":
                    continue
                dest = os.path.join(OUT_DIR, f"{region}_{year}_{feature}.tif")
                if not os.path.exists(dest):
                    shutil.copy(base, dest)
                    copied += 1
    return copied


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Download LANDFIRE clips via LFPS. Never overwrites "
                    "or deletes an existing file: replaced files are "
                    f"moved to {REPLACED_DIR}.")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Skip every existing file, even an empty "
                         "placeholder. Default: re-fetch empty ones, "
                         "keeping the placeholder unless a valid "
                         "replacement arrives.")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    tasks = plan_tasks(refetch_empty=not args.skip_existing)
    skipped_known = sum(1 for r in BOXES_COORDINATES for y in YEARS
                        for f in FEATURES if (y, f) in KNOWN_UNAVAILABLE)
    log(f"Planned {len(tasks)} download job(s) "
       f"({skipped_known} known-unavailable combos skipped; "
       f"already-present files skipped).")
    log(f"Running up to {MAX_CONCURRENT_JOBS} concurrent LFPS jobs.\n")

    results = {"ok": 0, "failed": []}
    if tasks:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as pool:
            futures = {pool.submit(download_one, *t): t for t in tasks}
            for fut in as_completed(futures):
                task, status = fut.result()
                if status.startswith("ok"):
                    results["ok"] += 1
                    log(f"  [+] {task}: saved{status[2:]}")
                else:
                    results["failed"].append((task, status))
                    log(f"  [!] {task}: {status}")

    n_copies = copy_topo_baselines()

    log(f"\n==========================================")
    log(f" SUMMARY")
    log(f"==========================================")
    log(f"Downloads succeeded: {results['ok']}")
    log(f"Topo baseline copies made: {n_copies}")
    if results["failed"]:
        log(f"Failed ({len(results['failed'])}):")
        for task, status in results["failed"]:
            log(f"  - {task}: {status}")
        log("If a failure says 'Invalid products', that layer/year isn't "
           "published on LFPS - add it to KNOWN_UNAVAILABLE to skip next run.")


if __name__ == "__main__":
    main()

