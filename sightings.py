import os
import time
import zipfile
import requests
import pandas as pd

# ==========================================
# GBIF CREDENTIALS & SETTINGS
# ==========================================
# Your registered GBIF account credentials
GBIF_USER = "alpuglisi"
GBIF_PWD = "Password1994!"
GBIF_EMAIL = "albert.puglisi94@gmail.com"

# The unique Dataset UUID for the "eBird Observation Dataset" on GBIF
EBIRD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
SPECIES_NAME = "Bonasa umbellus" # Scientific name for Ruffed Grouse
STATES = ["Maine", "New Hampshire", "Vermont"]
START_YEAR = 2016
# ==========================================

def get_taxon_key(species_name):
    """Dynamically fetches the GBIF Taxon Key for the target species."""
    print(f"Looking up GBIF Taxon Key for {species_name}...")
    res = requests.get(f"https://api.gbif.org/v1/species/match?name={species_name}")
    res.raise_for_status()
    data = res.json()
    
    if 'usageKey' not in data:
        raise ValueError(f"Could not find a valid taxon key for {species_name}")
        
    print(f" -> Found Taxon Key: {data['usageKey']}")
    return str(data['usageKey'])

def trigger_gbif_download(taxon_key):
    """Submits the asynchronous download job to the GBIF API."""
    print("\nSubmitting bulk download request to GBIF...")
    
    url = "https://api.gbif.org/v1/occurrence/download/request"
    
    # Build the JSON query predicate using GBIF's logical syntax
    payload = {
        "creator": GBIF_USER,
        "notification_addresses": [GBIF_EMAIL],
        "sendNotification": True,
        "format": "SIMPLE_CSV", # Note: GBIF calls it CSV, but it is tab-separated (TSV)
        "predicate": {
            "type": "and",
            "predicates": [
                {"type": "equals", "key": "TAXON_KEY", "value": taxon_key},
                {"type": "equals", "key": "DATASET_KEY", "value": EBIRD_DATASET_KEY},
                {"type": "equals", "key": "COUNTRY", "value": "US"},
                {"type": "greaterThanOrEquals", "key": "YEAR", "value": str(START_YEAR)},
                {"type": "in", "key": "STATE_PROVINCE", "values": STATES}
            ]
        }
    }
    
    res = requests.post(url, json=payload, auth=(GBIF_USER, GBIF_PWD))
    
    if res.status_code == 201:
        download_id = res.text.strip()
        print(f" -> Success! Download ID: {download_id}")
        return download_id
    else:
        print(f"[!] Failed to submit request. HTTP {res.status_code}")
        print(res.text)
        exit(1)

def poll_and_download(download_id):
    """Polls the GBIF server until the download is compiled, then downloads it."""
    status_url = f"https://api.gbif.org/v1/occurrence/download/{download_id}"
    
    print("\nPolling GBIF server for job completion (this usually takes 1 to 5 minutes)...")
    while True:
        res = requests.get(status_url).json()
        status = res.get("status")
        
        if status == "SUCCEEDED":
            download_link = res.get("downloadLink")
            print(f" -> Job finished! Data is ready at: {download_link}")
            break
        elif status in ["FAILED", "KILLED", "CANCELLED"]:
            print(f"[!] Job failed on GBIF server with status: {status}")
            exit(1)
            
        print(f" -> Status: {status}. Waiting 15 seconds...")
        time.sleep(15)
        
    print("\nDownloading the zip file...")
    zip_path = f"{download_id}.zip"
    
    # Stream download the file
    with requests.get(download_link, stream=True) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
    print(f" -> Download saved to {zip_path}")
    return zip_path

def process_and_split_data(zip_path):
    """Extracts the zip, reads the data, and splits it into state/year files."""
    print("\nExtracting and splitting the dataset by State and Year...")
    
    # Extract the CSV from the downloaded zip
    csv_filename = ""
    with zipfile.ZipFile(zip_path, 'r') as z:
        csv_filename = [f for f in z.namelist() if f.endswith('.csv')][0]
        z.extract(csv_filename)
        
    # Read the extracted file. GBIF "SIMPLE_CSV" is actually tab-separated.
    df = pd.read_csv(csv_filename, sep='\t', low_memory=False)
    
    if df.empty:
        print("[!] No records found in the download.")
        return
        
    # Standardize our prefix mapping
    state_mapping = {
        "Maine": "me",
        "New Hampshire": "nh",
        "Vermont": "vt"
    }
    
    files_created = 0
    
    # Group the dataframe by the GBIF column headers for state and year
    for (state, year), group in df.groupby(['stateProvince', 'year']):
        # Ignore edge-case rows missing state or year data
        if state not in state_mapping or pd.isna(year):
            continue
            
        prefix = state_mapping[state]
        out_file = f"{prefix}_sightings_{int(year)}.csv"
        
        group.to_csv(out_file, index=False)
        print(f" -> Created {out_file} ({len(group)} records)")
        files_created += 1
        
    print(f"\nAll done! Successfully split the master dataset into {files_created} distinct files.")
    
    # Clean up massive temporary files
    os.remove(zip_path)
    os.remove(csv_filename)

if __name__ == "__main__":
    if GBIF_USER == "your_gbif_username":
        print("WARNING: Please insert your GBIF credentials at the top of the script before running.")
        exit(1)
        
    # Run the execution pipeline
    taxon_key = get_taxon_key(SPECIES_NAME)
    download_id = trigger_gbif_download(taxon_key)
    zip_path = poll_and_download(download_id)
    process_and_split_data(zip_path)
