import os
import time
import requests
import zipfile
import shutil

# =======================================================================
# 1. DEFINE YOUR BOX COORDINATES
# =======================================================================
# Replace the placeholder coordinates below with your 3 sets of 4 coordinates.
# Each coordinate should be a tuple of (longitude, latitude).
# Note: Longitude is typically negative for North America (e.g., -114.1).
BOXES_COORDINATES = [
    # Box 1
    [
        (-114.1, 47.1), (-114.0, 47.1), 
        (-114.0, 47.2), (-114.1, 47.2)
    ],
    # Box 2
    [
        (-107.7, 46.5), (-106.0, 46.5), 
        (-106.0, 47.3), (-107.7, 47.3)
    ],
    # Box 3
    [
        (-123.7, 41.7), (-123.6, 41.7), 
        (-123.6, 41.8), (-123.7, 41.8)
    ]
]

# The USGS LFPS API logs usage and requests you provide a valid email.
EMAIL = "your.email@example.com" 

# =======================================================================
# 2. CONFIGURATION
# =======================================================================
YEARS = ["2020", "2022", "2023", "2024", "2025"]

# Mapping your desired features to the official LANDFIRE API Layer IDs.
FEATURES_MAPPING = {
    "evt": "EVT",        # Existing Vegetation Type
    "evh": "EVH",        # Existing Vegetation Height
    "evc": "EVC",        # Existing Vegetation Cover
    "sclass": "SClass",  # Succession Classes
    "slope": "SlpD",     # Slope in Degrees 
    "gradient": "Asp"    # Aspect (gradient direction). Change to 'Elev' if you prefer Elevation.
}

# API endpoint for the LANDFIRE Product Service
SUBMIT_URL = "https://lfps.usgs.gov/arcgis/rest/services/LandfireProductService/GPServer/LandfireProductService/submitJob"

def get_bounding_box(coords):
    """Converts 4 corners into the 'Xmin Ymin Xmax Ymax' format expected by the API."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return f"{min(lons)} {min(lats)} {max(lons)} {max(lats)}"

def get_layer_code(feature, year):
    """Constructs the exact LANDFIRE Layer ID."""
    if feature in ["slope", "gradient"]:
        return f"LF2020_{FEATURES_MAPPING[feature]}"
    return f"LF{year}_{FEATURES_MAPPING[feature]}"

# =======================================================================
# 3. DOWNLOAD SCRIPT
# =======================================================================
def download_landfire_data():
    out_dir = "data/landfire"
    os.makedirs(out_dir, exist_ok=True)
    
    # Use a session to improve connection pooling; disable warnings for finicky USGS certs
    session = requests.Session()
    session.verify = False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    for box_idx, coords in enumerate(BOXES_COORDINATES, start=1):
        bbox_str = get_bounding_box(coords)
        print(f"\n==========================================")
        print(f" Processing Box {box_idx} (BBox: {bbox_str})")
        print(f"==========================================")
        
        for year in YEARS:
            for feature in FEATURES_MAPPING.keys():
                layer_code = get_layer_code(feature, year)
                out_filename = f"Box{box_idx}_{year}_{feature}.tif"
                out_filepath = os.path.join(out_dir, out_filename)
                
                # Resume support: skip if the file is already safely downloaded
                if os.path.exists(out_filepath):
                    print(f"[-] {out_filename} already exists. Skipping...")
                    continue
                
                # OPTIMIZATION: Topography hasn't fundamentally changed since the 2020 base map.
                # If we've already downloaded it for the 2020 cycle of this box, duplicate it
                # to complete the user's requested fileset instead of making 10 unnecessary API calls.
                if feature in ["slope", "gradient"] and year != "2020":
                    base_topo = os.path.join(out_dir, f"Box{box_idx}_2020_{feature}.tif")
                    if os.path.exists(base_topo):
                        print(f"[~] Copying static 2020 topography baseline to {out_filename}")
                        shutil.copy(base_topo, out_filepath)
                        continue
                
                print(f"Requesting {feature.upper()} for {year} (Layer ID: {layer_code})...")
                
                # 1. Submit the Job
                params = {
                    "Layer_List": layer_code,
                    "Area_of_Interest": bbox_str,
                    "Email": EMAIL,
                    "f": "json"
                }
                
                try:
                    res = session.post(SUBMIT_URL, data=params, timeout=30).json()
                except Exception as e:
                    print(f"  [!] Network error submitting job: {e}")
                    continue
                    
                job_id = res.get("jobId")
                if not job_id:
                    print(f"  [!] Failed to submit job. Layer '{layer_code}' may not be published.")
                    continue
                
                # 2. Poll the Job Status
                poll_url = f"https://lfps.usgs.gov/arcgis/rest/services/LandfireProductService/GPServer/LandfireProductService/jobs/{job_id}"
                job_succeeded = False
                
                while True:
                    try:
                        status_res = session.get(poll_url, params={"f": "json"}, timeout=30).json()
                        status = status_res.get("jobStatus")
                        
                        if status == "esriJobSucceeded":
                            job_succeeded = True
                            break
                        elif status in ["esriJobFailed", "esriJobCancelled", "esriJobTimedOut"]:
                            messages = [m.get("description") for m in status_res.get("messages", []) if m.get("type") == "esriJobMessageTypeError"]
                            print(f"  [!] Job failed on server. (Layer likely not available yet): {messages}")
                            break
                    except Exception as e:
                        print(f"  [!] Error checking job status: {e}")
                        break
                        
                    time.sleep(5) # Wait 5 seconds before checking again (prevents rate-limiting)
                
                if not job_succeeded:
                    continue
                    
                # 3. Retrieve the Download URL
                results = status_res.get("results", {})
                if not results:
                    print("  [!] No results found in the completed job payload.")
                    continue
                
                out_key = list(results.keys())[0] # Usually 'Output_File'
                result_val_url = f"{poll_url}/results/{out_key}"
                
                try:
                    val_res = session.get(result_val_url, params={"f": "json"}, timeout=30).json()
                    download_url = val_res.get("value", {}).get("url")
                except Exception as e:
                    print(f"  [!] Error fetching result URL: {e}")
                    continue
                    
                if not download_url:
                    print("  [!] Download URL missing.")
                    continue
                    
                # 4. Stream Download and Extract the TIF File
                zip_path = os.path.join(out_dir, f"temp_{job_id}.zip")
                try:
                    with session.get(download_url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(zip_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                            
                    # Extract the first .tif found in the zip bundle, discard the useless metadata/xml files
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        tif_files = [f for f in z.namelist() if f.endswith('.tif')]
                        if tif_files:
                            with z.open(tif_files[0]) as zf, open(out_filepath, "wb") as f:
                                shutil.copyfileobj(zf, f)
                            print(f"  [+] Successfully saved {out_filename}")
                        else:
                            print(f"  [!] No .tif file found inside the downloaded zip.")
                            
                except Exception as e:
                    print(f"  [!] Error downloading or extracting data: {e}")
                finally:
                    # Clean up the temporary zip bundle to conserve disk space
                    if os.path.exists(zip_path):
                        os.remove(zip_path)

if __name__ == "__main__":
    download_landfire_data()
    print("\nAll tasks completed!")
