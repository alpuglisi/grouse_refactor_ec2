import csv
import time
import requests
from datetime import date, timedelta

# ==========================================
# HARDCODED GLOBAL VARIABLE FOR API KEY
# ==========================================
# Insert your eBird API key here before running
API_KEY = "69gtab3miaee"
SPECIES_CODE = "rufgro"

# eBird region codes for the states requested
STATES = {
    "me": "US-ME",
    "nh": "US-NH",
    "vt": "US-VT"
}

START_YEAR = 2016

def main():
    if API_KEY == "YOUR_API_KEY_HERE":
        print("WARNING: You are using the placeholder API key. Please insert your actual API key at the top before running.\n")
        
    end_year = date.today().year
    
    headers = {
        "X-eBirdApiToken": API_KEY
    }
    
    # Standard metadata fields returned by the eBird API that we want in our CSV
    csv_headers = [
        "speciesCode", "comName", "sciName", "locId", "locName", 
        "obsDt", "howMany", "lat", "lng", "obsValid", 
        "obsReviewed", "locationPrivate", "subId", "subnational2Code",
        "subnational2Name", "exoticCategory"
    ]
    
    # Use a session to improve connection pooling for thousands of requests
    session = requests.Session()
    session.headers.update(headers)
    
    for state_prefix, region_code in STATES.items():
        for year in range(START_YEAR, end_year + 1):
            filename = f"{state_prefix}_sightings_{year}.csv"
            print(f"\n=======================================================")
            print(f" Fetching data for {state_prefix.upper()} in the year {year}...")
            print(f"=======================================================")
            
            start_date = date(year, 1, 1)
            # End date is either Dec 31st of that year, or today's date if it's the current year
            if year == end_year:
                end_date = date.today()
            else:
                end_date = date(year, 12, 31)
                
            current_date = start_date
            sightings_count = 0
            
            # Open the CSV file in write mode
            with open(filename, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=csv_headers, extrasaction='ignore')
                writer.writeheader()
                
                # Loop through every single day of that year
                while current_date <= end_date:
                    
                    # Print a progress indicator at the start of each month so you know it's not frozen
                    if current_date.day == 1:
                        print(f" -> Fetching records for {current_date.strftime('%B %Y')}...")
                        
                    # API endpoint for historic observations on a specific date
                    url = f"https://api.ebird.org/v2/data/obs/{region_code}/historic/{current_date.year}/{current_date.month}/{current_date.day}"
                    
                    # 'detail=full' ensures we get coordinates (lat/lng) and time of day
                    params = {
                        "detail": "full" 
                    }
                    
                    try:
                        response = session.get(url, params=params, timeout=15)
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            # The API returns ALL birds seen on that day. Filter just for Ruffed Grouse.
                            grouse_sightings = [obs for obs in data if obs.get("speciesCode") == SPECIES_CODE]
                            
                            if grouse_sightings:
                                for s in grouse_sightings:
                                    writer.writerow(s)
                                sightings_count += len(grouse_sightings)
                                
                                # Flush the buffer to ensure data writes safely to the disk immediately
                                f.flush()
                                
                        elif response.status_code in (401, 403):
                            print(f"  [!] Authentication error. Check your API Key.")
                            return
                        else:
                            print(f"  [!] Error {response.status_code} on {current_date}")
                            
                    except Exception as e:
                        print(f"  [!] Network exception during request on {current_date}: {e}")
                        
                    # Increment the date by 1 day
                    current_date += timedelta(days=1)
                    
                    # VERY IMPORTANT: Pause to respect eBird's rate limits. 
                    # Without this, they will close the connection and block your API Key.
                    time.sleep(1.0)
                
            print(f"[+] Finished {state_prefix.upper()} {year}. Saved {sightings_count} Ruffed Grouse sightings to {filename}")

if __name__ == "__main__":
    main()
