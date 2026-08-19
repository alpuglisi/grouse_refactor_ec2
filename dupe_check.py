"""
check_duplicate_coordinates.py

Tests the "reused pin location" hypothesis directly: are the records
piling into the top envelopes / non-vegetated flags because many
distinct sightings share the EXACT same lat/lon (a hotspot-style default
location), or because sightings are just genuinely clustered nearby?

Those are different findings with different implications:
  - Exact duplicate coordinates = almost certainly a location-precision
    artifact (one pin reused across many checklists/records).
  - Nearby-but-not-identical coordinates = could be real fine-scale
    habitat clustering (e.g. birds really do concentrate at a food
    source), which duplicate-checking alone can't rule out.

INPUT: evaluated_sightings_{REGION}.csv from analyze_grouse.py.

Usage:
    python check_duplicate_coordinates.py
    python check_duplicate_coordinates.py --regions ME
    python check_duplicate_coordinates.py --round-decimals 5 --top 15
"""
import os
import argparse
import pandas as pd

REGIONS_DEFAULT = ["ME", "NH", "VT"]


def duplicate_summary(df, round_decimals, label):
    """Round coordinates to collapse floating-point noise, then measure
    how much of the dataset sits on a coordinate shared with other
    records. round_decimals=5 is about 1.1m at these latitudes - tight
    enough that two genuinely independent observers would essentially
    never land on it by chance, loose enough to not be fooled by trivial
    float formatting differences."""
    if len(df) == 0:
        return None

    coords = df[['longitude', 'latitude']].round(round_decimals)
    coord_key = coords['longitude'].astype(str) + "," + coords['latitude'].astype(str)
    counts = coord_key.value_counts()

    n_total = len(df)
    n_unique_coords = len(counts)
    n_on_shared_coord = int((counts[counts > 1]).sum())
    pct_on_shared_coord = 100 * n_on_shared_coord / n_total

    print(f"\n  --- {label} ---")
    print(f"    {n_total:,} records, {n_unique_coords:,} distinct coordinates "
         f"(rounded to {round_decimals} decimals, ~{'%.1f' % (111000 / (10 ** round_decimals))}m)")
    print(f"    {n_on_shared_coord:,} records ({pct_on_shared_coord:.1f}%) sit on a "
         f"coordinate used by 2+ records")

    return coord_key, counts


def report_top_shared_coords(df, coord_key, counts, top_n):
    top = counts[counts > 1].head(top_n)
    if len(top) == 0:
        print("    No repeated coordinates found.")
        return
    print(f"    Top {min(top_n, len(top))} most-reused coordinates:")
    for coord, n in top.items():
        lon_str, lat_str = coord.split(",")
        sub = df[coord_key == coord]
        years = sorted(sub['year'].unique())
        year_span = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
        nonveg_note = ""
        if 'nonveg_landcover' in sub.columns:
            nv = int(sub['nonveg_landcover'].sum())
            if nv > 0:
                nonveg_note = f", {nv} flagged non-veg"
        print(f"      ({lon_str}, {lat_str}): {n:,} records, years {year_span}{nonveg_note}")


def main():
    parser = argparse.ArgumentParser(
        description="Check whether high-count envelopes/flags are driven "
                    "by exact-duplicate coordinates (reused pins).")
    parser.add_argument("--regions", nargs="+", default=REGIONS_DEFAULT)
    parser.add_argument("--round-decimals", type=int, default=5,
                        help="Decimal places to round lon/lat to before "
                             "matching (default: %(default)s, ~1.1m)")
    parser.add_argument("--top", type=int, default=10,
                        help="How many top reused coordinates to print (default: %(default)s)")
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

        # 1. All records
        result_all = duplicate_summary(df, args.round_decimals, "ALL RECORDS")
        if result_all:
            report_top_shared_coords(df, *result_all, args.top)

        # 2. Non-vegetated-flagged records specifically - this is the
        # subset we suspected of being artifact-driven
        if 'nonveg_landcover' in df.columns:
            nonveg_df = df[df['nonveg_landcover'].astype(bool)]
            result_nonveg = duplicate_summary(
                nonveg_df, args.round_decimals, "NON-VEGETATED-FLAGGED RECORDS")
            if result_nonveg:
                report_top_shared_coords(nonveg_df, *result_nonveg, args.top)

        # 3. Vegetated habitat records - the ones actually feeding the
        # envelope table. If duplication shows up here too, the "Flat/
        # NoAspect" dominance in top envelopes is suspect for the same
        # reason as the non-veg flags were.
        if 'nonveg_landcover' in df.columns:
            habitat_df = df[~df['nonveg_landcover'].astype(bool)]
            result_habitat = duplicate_summary(
                habitat_df, args.round_decimals, "VEGETATED HABITAT RECORDS (feeds envelope table)")
            if result_habitat:
                report_top_shared_coords(habitat_df, *result_habitat, args.top)

                # Cross-check: how much of the #1 top envelope specifically
                # sits on a handful of reused coordinates?
                if 'env_zone' in habitat_df.columns:
                    coord_key, counts = result_habitat
                    # Recompute the actual envelope_id isn't saved in the
                    # CSV (only env_zone is) - approximate by re-deriving
                    # the top SCLASS/EVH-quantile/aspect combination isn't
                    # possible without re-binning, so instead report
                    # duplication specifically within Hotspot records,
                    # which is the same population driving the top
                    # envelope rows.
                    if 'spatial_zone' in habitat_df.columns:
                        hot_df = habitat_df[habitat_df['spatial_zone'] == 'Hotspot 10%']
                        result_hot = duplicate_summary(
                            hot_df, args.round_decimals,
                            "HOTSPOT RECORDS (top spatial-density decile)")
                        if result_hot:
                            report_top_shared_coords(hot_df, *result_hot, args.top)


if __name__ == "__main__":
    main()

