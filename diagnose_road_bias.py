"""
diagnose_road_bias.py

Quick diagnostic for the ROADSIDE ACCESSIBILITY BIAS hypothesis raised by
predict.py --tensorboard's suitability map visibly hugging Route 16/26
through Errol, NH: eBird/GBIF presence records (positives) are collected
almost exclusively by observers who can physically reach a location,
which in rural northern New England mostly means "on or very near a
road" - independent of whether that location is actually good grouse
habitat.

analyze_grouse.py already documents and partially corrects the sharpest
form of this (reused-pin duplication - see collapse_duplicate_locations,
59-76% of raw records were repeat visits to one coordinate) but its own
KDE-stage methods note explicitly flags what survives dedup: "observer
effort grew over 2016-2024, so more DISTINCT locations get reported...
regardless of grouse density." generate_negatives.py's target-group
background (other bird species from the SAME eBird platform/states) is
the textbook counter-design - both classes should then share the same
accessibility skew - but its 300m exclusion buffer around every grouse
location, and its per-envelope inverse-Selection_Ratio weighting, both
key off raw grouse detection density, which is itself accessibility-
inflated near roads. Neither mechanism has ever actually been checked
against a real roads layer.

This computes distance-to-nearest-road (TIGER/Line primary+secondary
roads, downloaded once per state and cached under data/roads/) for three
point sets per region:
    positives            train+val positives that actually trained the
                          model (data/pipeline/{train,val}_positives_*)
    selected negatives    the negatives that actually trained the model
                          (data/negatives/negatives_{region}.csv)
    raw GBIF candidates   the negative pool BEFORE the 300m buffer /
                          envelope weighting filtered it down
                          (data/negatives/gbif_negatives_{region}.csv)

Reading:
  - positives sitting conspicuously closer to roads than the raw GBIF
    candidate pool does -> accessibility bias in the raw eBird data
    itself (upstream of this project entirely - both species groups are
    eBird-sourced, so if only grouse skews close, something about grouse
    reporting specifically is road-biased, e.g. drumming counts being a
    roadside-route survey method in many state protocols).
  - selected negatives sitting conspicuously FARTHER from roads than the
    raw candidate pool did -> this project's own 300m buffer / envelope
    weighting amplifying the bias by disproportionately stripping
    roadside negatives, not (only) the raw data being biased.
  Both can be true at once, and either alone is enough to explain a
  model that has learned "close to a road" as a shortcut for "likely
  positive."

CAVEAT: PRISECROADS is primary + secondary roads only (one file per
state, no county enumeration needed) - it undercounts local/logging/
forest roads that plausibly matter as much in this landscape. A weak
signal here does NOT rule out road bias; a strong one is decisive.

Usage:
    python diagnose_road_bias.py
    python diagnose_road_bias.py --regions NH
"""
import os
import argparse
import urllib.request

import numpy as np
import pandas as pd

from prepare_training_data import BOXES

DATA_DIR = "data/roads"
STATE_FIPS = {"ME": "23", "NH": "33", "VT": "50"}
TIGER_YEAR = 2023
# Same radius generate_negatives.py excludes candidate negatives within
# of any known grouse location - reused here so "% within threshold" is
# directly comparable to that filter's own footprint.
ROAD_BUFFER_THRESHOLD_M = 300


def load_roads(region):
    import geopandas as gpd
    os.makedirs(DATA_DIR, exist_ok=True)
    fips = STATE_FIPS[region]
    fname = f"tl_{TIGER_YEAR}_{fips}_prisecroads.zip"
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path):
        url = (f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/"
              f"PRISECROADS/{fname}")
        print(f"  Downloading {region} primary/secondary roads from "
             f"{url} ...")
        urllib.request.urlretrieve(url, path)
    gdf = gpd.read_file(path).to_crs("EPSG:5070")
    print(f"  {region}: {len(gdf):,} road segments loaded.")
    return gdf


def to_points_gdf(df):
    import geopandas as gpd
    return gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326").to_crs("EPSG:5070")


def distance_to_road(points_gdf, roads_gdf):
    import geopandas as gpd
    joined = gpd.sjoin_nearest(points_gdf.reset_index(drop=True),
                               roads_gdf[["geometry"]],
                               distance_col="dist_to_road_m")
    # A point exactly equidistant from two road segments duplicates the
    # row under sjoin_nearest - keep one (the distance is identical
    # either way, only the matched segment index differs).
    joined = joined[~joined.index.duplicated(keep="first")]
    return joined["dist_to_road_m"].values


def summarize(label, dists):
    if len(dists) == 0:
        print(f"    {label}: no points")
        return
    pct_within = 100 * (dists <= ROAD_BUFFER_THRESHOLD_M).mean()
    print(f"    {label:24s} n={len(dists):6,} | median {np.median(dists):7.0f} m "
         f"| mean {dists.mean():7.0f} m | "
         f"{pct_within:5.1f}% within {ROAD_BUFFER_THRESHOLD_M}m of a road")


def process_region(region):
    print(f"\n{'=' * 60}\n{region}\n{'=' * 60}")
    if region not in BOXES:
        print(f"  [!] {region} not in BOXES - skipping.")
        return None
    roads = load_roads(region)

    pos_paths = [f"data/pipeline/train_positives_{region}.csv",
                f"data/pipeline/val_positives_{region}.csv"]
    pos_frames = [pd.read_csv(p) for p in pos_paths if os.path.exists(p)]
    pos = pd.concat(pos_frames, ignore_index=True) if pos_frames else pd.DataFrame()

    neg_path = f"data/negatives/negatives_{region}.csv"
    neg = pd.read_csv(neg_path) if os.path.exists(neg_path) else pd.DataFrame()

    cand_path = f"data/negatives/gbif_negatives_{region}.csv"
    cand = pd.read_csv(cand_path) if os.path.exists(cand_path) else pd.DataFrame()

    if len(pos) == 0:
        print(f"  [!] No positives found for {region} (expected "
             f"{pos_paths[0]}) - run prepare_training_data.py first. "
             f"Skipping.")
        return None

    results = {}
    for label, df in (("positives (trained on)", pos),
                      ("selected negatives", neg),
                      ("raw GBIF candidates", cand)):
        if len(df) == 0:
            print(f"    [!] {label}: file missing/empty, skipping.")
            continue
        dists = distance_to_road(to_points_gdf(df), roads)
        summarize(label, dists)
        results[label] = dists
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(STATE_FIPS),
                    choices=list(STATE_FIPS))
    args = ap.parse_args()

    try:
        import geopandas  # noqa: F401
    except ImportError:
        raise SystemExit(
            "diagnose_road_bias.py needs geopandas: pip install geopandas")

    all_results = {r: process_region(r) for r in args.regions}

    print(f"\n{'=' * 60}\nVERDICT\n{'=' * 60}")
    any_evidence = False
    for region, res in all_results.items():
        if not res or "positives (trained on)" not in res:
            continue
        pos_med = float(np.median(res["positives (trained on)"]))
        line = f"  {region}: positives median {pos_med:.0f}m from nearest road"
        if "raw GBIF candidates" in res:
            cand_med = float(np.median(res["raw GBIF candidates"]))
            ratio = (cand_med / pos_med) if pos_med > 0 else float("inf")
            line += f" | raw GBIF candidates {cand_med:.0f}m ({ratio:.1f}x farther)"
            if ratio > 1.5:
                line += " [accessibility bias in the raw eBird data itself]"
                any_evidence = True
        if "selected negatives" in res:
            neg_med = float(np.median(res["selected negatives"]))
            line += f" | selected negatives {neg_med:.0f}m"
            if "raw GBIF candidates" in res:
                cand_med = float(np.median(res["raw GBIF candidates"]))
                if neg_med > cand_med * 1.2:
                    line += (" [the 300m buffer / envelope weighting is "
                            "itself pushing negatives farther from roads "
                            "than the raw candidate pool was]")
                    any_evidence = True
        print(line)
    if not any_evidence:
        print("  No region showed a clear road-distance gap by these "
             "thresholds - PRISECROADS-only undercounts local/forest "
             "roads, so this doesn't rule the hypothesis out, but it "
             "isn't confirmed by primary/secondary roads alone either.")


if __name__ == "__main__":
    main()
