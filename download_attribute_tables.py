"""
download_attribute_tables.py

Standalone companion to download.py. Does NOT touch any AOI raster data.
Scans your existing landfire_data/ folder for which {feature}_{year}
combinations you actually have (EVT/EVH/EVC/SClass only - slope/aspect are
continuous values and don't need a class attribute table), then fetches
the corresponding NATIONAL attribute-table CSV directly from landfire.gov's
public product pages.

These are the authoritative VALUE -> class-name crosswalks (e.g. which
EVT/SClass integer codes are water, urban, or a specific succession
class/vegetation type) - the same tables described in
https://landfire.gov/faqs under "Attribute Tables (CSV, ADD)". They are
NOT AOI-specific: one file per product+year covers the whole country, so
this never needs to touch LFPS or re-download any raster.

Usage:
    python download_attribute_tables.py
    python download_attribute_tables.py --raster-dir ./landfire_data
    python download_attribute_tables.py --features evt sclass --years 2022 2024
"""
import os
import re
import glob
import argparse
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

RASTER_DIR_DEFAULT = "data/landfire"
OUT_DIR_NAME = "attribute_tables"

# feature key (as used in {region}_{year}_{feature}.tif filenames) ->
# LANDFIRE's product code as it appears in their CSV filenames. Only
# categorical products need a crosswalk table; slope/gradient are
# continuous physical values and are intentionally excluded.
FEATURE_TO_PRODUCT = {
    "evt": "EVT",
    "evh": "EVH",
    "evc": "EVC",
    "sclass": "SClass",
}

PRODUCT_PAGE = {
    "evt": "https://landfire.gov/vegetation/evt",
    "evh": "https://landfire.gov/vegetation/evh",
    "evc": "https://landfire.gov/vegetation/evc",
    "sclass": "https://landfire.gov/vegetation/sclass",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "text/csv,*/*",
}


def candidate_urls(product, year):
    """LANDFIRE's CSV folder naming isn't fully consistent across years
    (e.g. LF2025_EVT.csv lives under .../CSV/LF2025/, while
    LF2024_SClass.csv lives under .../CSV/2024/ - no 'LF' prefix on the
    folder). Try the patterns actually observed on landfire.gov product
    pages, in order, and use whichever responds."""
    return [
        f"https://landfire.gov/sites/default/files/CSV/LF{year}/LF{year}_{product}.csv",
        f"https://landfire.gov/sites/default/files/CSV/{year}/LF{year}_{product}.csv",
        f"https://www.landfire.gov/sites/default/files/CSV/LF{year}/LF{year}_{product}.csv",
        f"https://www.landfire.gov/sites/default/files/CSV/{year}/LF{year}_{product}.csv",
    ]


def scan_needed_tables(raster_dir, only_features=None, only_years=None):
    """Find every (feature, year) combo actually present in raster_dir's
    .tif filenames, restricted to categorical features that need a
    crosswalk table."""
    pattern = re.compile(r"^[A-Za-z0-9]+_(\d{4})_([a-z]+)\.tif$")
    needed = set()
    for path in glob.glob(os.path.join(raster_dir, "*.tif")):
        m = pattern.match(os.path.basename(path))
        if not m:
            continue
        year, feature = m.group(1), m.group(2)
        if feature not in FEATURE_TO_PRODUCT:
            continue  # slope/gradient - no attribute table needed
        if only_features and feature not in only_features:
            continue
        if only_years and year not in only_years:
            continue
        needed.add((feature, year))
    return sorted(needed)


def looks_like_valid_csv(content):
    """LANDFIRE's attribute CSVs all start with a VALUE column header.
    A 200 status alone isn't proof of success - some misses still return
    a 200 with an HTML error/redirect page, so check content shape too."""
    if not content or len(content) < 20:
        return False
    head = content[:200].decode("utf-8", errors="ignore").lstrip()
    return head.upper().startswith("VALUE") or head.startswith("value")


def download_attribute_table(session, feature, year, out_dir):
    product = FEATURE_TO_PRODUCT[feature]
    out_path = os.path.join(out_dir, f"LF{year}_{product}.csv")
    if os.path.exists(out_path):
        print(f"[-] LF{year}_{product}.csv already exists. Skipping...")
        return True

    for url in candidate_urls(product, year):
        try:
            res = session.get(url, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"    ... {url} -> network error: {e}")
            continue

        if res.status_code == 200 and looks_like_valid_csv(res.content):
            with open(out_path, "wb") as f:
                f.write(res.content)
            print(f"[+] Saved LF{year}_{product}.csv (from {url})")
            return True
        else:
            print(f"    ... {url} -> HTTP {res.status_code}, not a match")

    print(f"[!] Could not locate the attribute table for {product} {year} "
         f"automatically. Check the product page and download it manually: "
         f"{PRODUCT_PAGE[feature]}")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Download only the LANDFIRE attribute-table CSVs needed "
                    "for rasters already present in landfire_data/.")
    parser.add_argument("--raster-dir", default=RASTER_DIR_DEFAULT,
                        help=f"Folder containing your .tif rasters (default: {RASTER_DIR_DEFAULT})")
    parser.add_argument("--features", nargs="+", choices=list(FEATURE_TO_PRODUCT.keys()),
                        help="Restrict to specific features (default: all categorical features found)")
    parser.add_argument("--years", nargs="+",
                        help="Restrict to specific years (default: all years found)")
    args = parser.parse_args()

    needed = scan_needed_tables(args.raster_dir, args.features, args.years)
    if not needed:
        print(f"No matching .tif files found under {args.raster_dir} "
             f"(looking for EVT/EVH/EVC/SClass rasters). Nothing to do.")
        return

    print(f"Found {len(needed)} attribute table(s) needed based on rasters in "
         f"{args.raster_dir}:")
    for feature, year in needed:
        print(f"  - {FEATURE_TO_PRODUCT[feature]} {year}")

    out_dir = os.path.join(args.raster_dir, OUT_DIR_NAME)
    os.makedirs(out_dir, exist_ok=True)

    session = requests.Session()
    session.verify = False
    session.headers.update(HEADERS)

    results = {}
    for feature, year in needed:
        print()
        results[(feature, year)] = download_attribute_table(session, feature, year, out_dir)

    print("\n==========================================")
    print(" SUMMARY")
    print("==========================================")
    n_ok = sum(results.values())
    print(f"{n_ok} of {len(results)} attribute table(s) available in {out_dir}/")
    failed = [k for k, v in results.items() if not v]
    if failed:
        print("Failed (see product page links above to fetch manually):")
        for feature, year in failed:
            print(f"  - {FEATURE_TO_PRODUCT[feature]} {year}: {PRODUCT_PAGE[feature]}")


if __name__ == "__main__":
    main()

