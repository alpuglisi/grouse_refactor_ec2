import os
import re
import time
import json
import requests
import zipfile
import shutil
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =======================================================================
# 1. DEFINE YOUR REGIONS
# =======================================================================
# Rebuilt from the actual sighting-data extent (was previously pointed at
# Montana/N. California test coordinates that never overlapped the ME/NH/VT
# sighting CSVs). Keyed by state so BOX_PREFIX in analyze_grouse.py can
# match the 'state' column directly. Values are (min_lon, min_lat, max_lon,
# max_lat) with a ~0.1 deg buffer around each state's observed sighting
# extent so points near the border still land inside a raster.
BOXES_COORDINATES = {
    "ME": (-71.158, 42.889, -66.852, 47.555),
    "NH": (-72.626, 42.605, -70.614, 45.398),
    "VT": (-73.510, 42.632, -71.422, 45.112),
}

EMAIL = "your.email@example.com"

# =======================================================================
# 2. CONFIGURATION
# =======================================================================
YEARS = ["2020", "2022", "2023", "2024", "2025"]
FEATURES = ["evt", "evh", "evc", "sclass", "slope", "gradient"]

# --- NEW API base (the old ArcGIS GPServer/submitJob path was retired in 2025) ---
BASE_URL = "https://lfps.usgs.gov/api/job"
SUBMIT_URL = f"{BASE_URL}/submit"
STATUS_URL = f"{BASE_URL}/status"
DOWNLOAD_URL_RE = re.compile(r'https?://[^\s"\']+\.zip')

# Products known to be unavailable from LFPS right now (see prior audit):
# LF2020 veg/sclass layers were retired from live distribution in Dec 2025;
# LF2025 SClass has not been published yet as of Aug 2026. Skipping these
# outright avoids burning a submit/poll cycle on a request that can't
# succeed, and keeps the log readable.
KNOWN_UNAVAILABLE = {
    ("2020", "evt"), ("2020", "evh"), ("2020", "evc"), ("2020", "sclass"),
    ("2025", "sclass"),
}


def get_bounding_box(bbox):
    min_lon, min_lat, max_lon, max_lat = bbox
    return f"{min_lon} {min_lat} {max_lon} {max_lat}"


def get_layer_code(feature, year):
    mapping = {
        "evt": "EVT", "evh": "EVH", "evc": "EVC",
        "sclass": "SClass", "slope": "SlpD", "gradient": "Asp"
    }
    if feature in ["slope", "gradient"]:
        return f"LF2020_{mapping[feature]}"
    return f"LF{year}_{mapping[feature]}"


def download_landfire_data():
    out_dir = "data/landfire"
    os.makedirs(out_dir, exist_ok=True)

    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "application/json"
    })

    for region_name, bbox in BOXES_COORDINATES.items():
        bbox_str = get_bounding_box(bbox)
        print(f"\n==========================================")
        print(f" Processing {region_name} (BBox: {bbox_str})")
        print(f"==========================================")

        for year in YEARS:
            for feature in FEATURES:
                layer_code = get_layer_code(feature, year)
                out_filename = f"{region_name}_{year}_{feature}.tif"
                out_filepath = os.path.join(out_dir, out_filename)

                if os.path.exists(out_filepath):
                    print(f"[-] {out_filename} already exists. Skipping...")
                    continue

                if (year, feature) in KNOWN_UNAVAILABLE:
                    print(f"[x] Skipping {feature.upper()} {year} "
                         f"({layer_code}) - known unavailable from LFPS.")
                    continue

                if feature in ["slope", "gradient"] and year != "2020":
                    base_topo = os.path.join(out_dir, f"{region_name}_2020_{feature}.tif")
                    if os.path.exists(base_topo):
                        print(f"[~] Copying static 2020 topography baseline to {out_filename}")
                        shutil.copy(base_topo, out_filepath)
                        continue

                print(f"Requesting {feature.upper()} for {year} (Layer: {layer_code})...")

                params = {
                    "Layer_List": layer_code,
                    "Area_of_Interest": bbox_str,
                    "Email": EMAIL,
                }

                # 1. Submit the job
                try:
                    res = session.get(SUBMIT_URL, params=params, timeout=30)
                    if res.status_code != 200:
                        print(f"  [!] HTTP {res.status_code}: {res.text[:300].strip()}")
                        continue
                    res_json = res.json()
                except requests.exceptions.JSONDecodeError:
                    print(f"  [!] Non-JSON response from submit. Snippet: {res.text[:200].strip()}")
                    continue
                except Exception as e:
                    print(f"  [!] Network error submitting job: {e}")
                    continue

                if res_json.get("success") is False:
                    print(f"  [!] Server rejected job: {res_json.get('message')}")
                    continue

                job_id = res_json.get("jobId")
                if not job_id:
                    print(f"  [!] No jobId in response: {res_json}")
                    continue

                # 2. Poll job status
                status_json = {}
                job_succeeded = False
                while True:
                    try:
                        status_res = session.get(STATUS_URL, params={"JobId": job_id}, timeout=30)
                        status_json = status_res.json()
                    except requests.exceptions.JSONDecodeError:
                        print(f"  [!] Non-JSON status response: {status_res.text[:200].strip()}")
                        break
                    except Exception as e:
                        print(f"  [!] Error checking job status: {e}")
                        break

                    status = str(status_json.get("status", "")).lower()

                    if "succeed" in status:
                        job_succeeded = True
                        break
                    elif status in ("failed", "canceled", "cancelled") or "fail" in status:
                        msgs = status_json.get("messages", [])
                        print(f"  [!] Job failed: {msgs}")
                        break

                    time.sleep(5)

                if not job_succeeded:
                    continue

                # 3. Find the download URL.
                download_url = None
                for key in ("downloadUrl", "download_url", "resultUrl", "url"):
                    if isinstance(status_json.get(key), str) and status_json[key].endswith(".zip"):
                        download_url = status_json[key]
                        break

                if not download_url:
                    match = DOWNLOAD_URL_RE.search(json.dumps(status_json))
                    if match:
                        download_url = match.group(0)

                if not download_url:
                    print("  [!] Could not locate a download URL. Raw status response:")
                    print(json.dumps(status_json, indent=2)[:2000])
                    continue

                # 4. Download and extract
                zip_path = os.path.join(out_dir, f"temp_{job_id}.zip")
                try:
                    with session.get(download_url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(zip_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)

                    with zipfile.ZipFile(zip_path, 'r') as z:
                        tif_files = [f for f in z.namelist() if f.endswith('.tif')]
                        if tif_files:
                            with z.open(tif_files[0]) as zf, open(out_filepath, "wb") as f:
                                shutil.copyfileobj(zf, f)
                            print(f"  [+] Successfully saved {out_filename}")
                        else:
                            print("  [!] No .tif file found inside the downloaded zip.")

                except Exception as e:
                    print(f"  [!] Error downloading or extracting data: {e}")
                finally:
                    if os.path.exists(zip_path):
                        os.remove(zip_path)


if __name__ == "__main__":
    download_landfire_data()
    print("\nAll tasks completed!")

