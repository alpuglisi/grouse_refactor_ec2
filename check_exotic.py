"""
check_exotic_habitat.py

Disambiguates the 'Exotic Tree-Shrub'/'Exotic Herbaceous' selection
signal: genuine (grouse using shrub-thicket structure) vs. another
flavor of the location-precision artifact (exotic vegetation
disproportionately borders roads/edges/disturbed accessible land).

Two independent checks:
  1. Reused-coordinate concentration - the same test that confirmed the
     original water/urban artifact. If a handful of physical locations
     account for most of these records, that's the artifact signature.
     Genuine dispersed habitat use should show many distinct locations.
  2. SClass attribute-table lookup (if landfire_data/attribute_tables/
     LF*_SClass.csv is present) - what does raw SClass code 7 actually
     mean for the BpS models tied to these EVT types? A label like
     'Bare Ground'/'Recently Disturbed' would suggest the same kind of
     loophole as the 'Developed' fix; a real late-succession-stage shrub
     label would support genuine habitat interpretation.

Usage:
    python check_exotic_habitat.py
    python check_exotic_habitat.py --regions ME
"""
import os
import glob
import argparse

import pandas as pd

REGIONS_DEFAULT = ["ME", "NH", "VT"]
TARGET_PHYS = ["Exotic Tree-Shrub", "Exotic Herbaceous"]
ROUND_DECIMALS = 5   # ~1.1m - matches check_duplicate_coordinates.py


def check_visit_concentration(df, label):
    """Compares n_visits (preserved by analyze_grouse.py's location-
    collapse step - how many original records fed into each now-unique
    row before dedup) between subsets. This is the correct test post-
    collapse: raw coordinate duplication is always 0% by construction
    once dedup has run, since every row IS already a unique location -
    n_visits is where the 'was this a popular reused location' signal
    actually still lives."""
    if len(df) == 0 or 'n_visits' not in df.columns:
        return None
    median_v = df['n_visits'].median()
    mean_v = df['n_visits'].mean()
    pct_multi = 100 * (df['n_visits'] > 1).mean()
    print(f"    {label}: {len(df):,} locations, median n_visits="
         f"{median_v:.0f}, mean={mean_v:.1f}, {pct_multi:.1f}% were "
         f"visited more than once before dedup")
    top = df.nlargest(3, 'n_visits')['n_visits'].tolist()
    if top and top[0] > 1:
        print(f"      Most-visited locations in this subset: {top}")
    return mean_v


def check_sclass_meaning(raster_dir):
    files = sorted(glob.glob(os.path.join(raster_dir, "attribute_tables",
                                          "LF*_SClass.csv")))
    if not files:
        print("\n  No SClass attribute table found under "
             f"{raster_dir}/attribute_tables/ - run "
             "download_attribute_tables.py to enable this check. "
             "Falling back to coordinate evidence only.")
        return
    path = files[-1]
    try:
        tbl = pd.read_csv(path)
    except Exception as e:
        print(f"\n  Could not read {path}: {e}")
        return
    tbl.columns = [c.upper().strip() for c in tbl.columns]
    print(f"\n  SClass attribute table: {os.path.basename(path)}")
    name_col = next((c for c in ("CLASSNAME", "CLASS_NAME", "LABEL", "SCLASS")
                     if c in tbl.columns), None)
    bps_col = next((c for c in tbl.columns if "BPS" in c and "NAME" in c), None)
    if "VALUE" not in tbl.columns or name_col is None:
        print(f"    Columns present: {list(tbl.columns)} - expected "
             f"VALUE + a class-name column, layout unrecognized.")
        return
    # Rows where the model/name text mentions "Exotic" AND the class
    # code is 7, to see what that specific combination is actually
    # labeled as.
    text_col = bps_col or name_col
    mask = tbl[text_col].astype(str).str.contains("Exotic", case=False, na=False)
    exotic_rows = tbl[mask]
    if len(exotic_rows) == 0:
        print(f"    No rows reference 'Exotic' in {text_col} - can't "
             f"cross-reference by name; table may use a different "
             f"naming convention.")
        return
    code7 = exotic_rows[exotic_rows["VALUE"].astype(str).str.strip() == "7"]
    if len(code7) > 0:
        print(f"    SClass code 7 for Exotic-referencing models:")
        for _, row in code7.head(10).iterrows():
            print(f"      {row.get(text_col, '?')}: {row.get(name_col, '?')}")
    else:
        print(f"    No SClass=7 rows found among {len(exotic_rows)} "
             f"Exotic-referencing model rows.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--regions", nargs="+", default=REGIONS_DEFAULT)
    parser.add_argument("--raster-dir", default="data/landfire")
    args = parser.parse_args()

    for region in args.regions:
        path = f"data/pipeline/evaluated_sightings_{region}.csv"
        print(f"\n##########################################")
        print(f"# REGION: {region}")
        print(f"##########################################")
        if not os.path.exists(path):
            print(f"  [!] {path} not found - run analyze_grouse.py first. Skipping.")
            continue

        df = pd.read_csv(path)
        if 'nonveg_landcover' in df.columns:
            df = df[~df['nonveg_landcover'].astype(bool)]
        if 'evt_phys' not in df.columns:
            print("  [!] No evt_phys column - can't identify Exotic records.")
            continue

        exotic = df[df['evt_phys'].isin(TARGET_PHYS)]
        other = df[~df['evt_phys'].isin(TARGET_PHYS)]

        print(f"\n  Visit-concentration comparison (pre-dedup popularity, "
             f"preserved in n_visits):")
        mean_exotic = check_visit_concentration(exotic, "Exotic Tree-Shrub/Herbaceous")
        mean_other = check_visit_concentration(other, "All other habitat records")

        if mean_exotic is None or mean_other is None:
            print("    [!] No 'n_visits' column in this CSV - re-run "
                 "analyze_grouse.py (current version) to regenerate it "
                 "with that column included.")
        elif mean_exotic > mean_other * 1.3:
            print(f"    -> Exotic locations were visited MORE before dedup "
                 f"than other habitat locations ({mean_exotic:.1f} vs "
                 f"{mean_other:.1f} avg visits) - consistent with an "
                 f"accessibility artifact (popular, easy-to-reach spots "
                 f"reported repeatedly), similar to the original "
                 f"water/urban issue.")
        elif mean_exotic < mean_other * 0.7:
            print(f"    -> Exotic locations were visited LESS before dedup "
                 f"than other habitat locations ({mean_exotic:.1f} vs "
                 f"{mean_other:.1f} avg visits) - does not fit the "
                 f"artifact pattern; more consistent with genuine, "
                 f"dispersed habitat use.")
        else:
            print(f"    -> Similar visit patterns ({mean_exotic:.1f} vs "
                 f"{mean_other:.1f} avg visits) - inconclusive from this "
                 f"test alone.")

        check_sclass_meaning(args.raster_dir)


if __name__ == "__main__":
    main()

