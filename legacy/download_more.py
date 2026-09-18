import os
import re
import time
import json
import shutil
import zipfile
import threading
import requests
import urllib3
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

OUT_DIR = "data/landfire"

_print_lock = threading.Lock()
def log(msg):
    with _print_lock:
        print(msg, flush=True)


def bbox_str(region):
    min_lon, min_lat, max_lon, max_lat = BOXES_COORDINATES[region]
    return f"{min_lon} {min_lat} {max_lon} {max_lat}"


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
                    with z.open(tifs[0]) as zf, open(out_filepath, "wb") as f:
                        shutil.copyfileobj(zf, f)
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
                            with z.open(name) as zf, open(dest, "wb") as f:
                                shutil.copyfileobj(zf, f)
                return task, "ok"
            except (requests.exceptions.RequestException,
                    zipfile.BadZipFile, EOFError, OSError) as e:
                last_err = e
                if os.path.exists(out_filepath):
                    os.remove(out_filepath)   # never leave a partial tif
                if attempt < DOWNLOAD_RETRIES:
                    log(f"  [~] {task}: transfer failed "
                       f"(attempt {attempt}/{DOWNLOAD_RETRIES}: {e}) - "
                       f"retrying download...")
                    time.sleep(5 * attempt)
        return task, f"download/extract error after {DOWNLOAD_RETRIES} attempts: {last_err}"
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)


# =======================================================================
# 4. TASK PLANNING + TWO-PHASE EXECUTION
# =======================================================================
def plan_tasks():
    """Everything that needs an actual network download. Topo features
    are planned for 2020 only; other years get filesystem copies of the
    2020 baseline in phase 2 (can't run concurrently with phase 1
    because the copies depend on the baseline existing)."""
    tasks = []
    for region in BOXES_COORDINATES:
        for year in YEARS:
            for feature in FEATURES:
                if feature in TOPO_FEATURES and year != "2020":
                    continue
                if (year, feature) in KNOWN_UNAVAILABLE:
                    continue
                out = os.path.join(OUT_DIR, f"{region}_{year}_{feature}.tif")
                if os.path.exists(out):
                    continue
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
    os.makedirs(OUT_DIR, exist_ok=True)
    tasks = plan_tasks()
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
                if status == "ok":
                    results["ok"] += 1
                    log(f"  [+] {task}: saved")
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

