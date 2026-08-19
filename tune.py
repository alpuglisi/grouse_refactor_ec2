"""
tune_envelope_bins.py

Systematically tests which environmental variables - and how many of them,
at what binning granularity - produce the best-behaved envelope
distribution for KDE-based analysis.

WHAT "IDEAL" MEANS HERE (stated up front, because it is a choice, not a
law of nature): an envelope scheme is useful for density estimation when
    1. COVERAGE   - most sightings land in envelopes big enough to
                    support a stable per-envelope spatial KDE
                    (>= MIN_PTS_PER_ENVELOPE points; ~30+ is the usual
                    rule of thumb for a 2D KDE),
    2. BALANCE    - records are spread across those viable envelopes
                    rather than one giant bin holding everything
                    (measured as normalized Shannon evenness), and
    3. RESOLUTION - there are enough distinct viable envelopes to
                    actually stratify the landscape (log-scaled so 500
                    bins isn't automatically "better" than 50).
The composite score multiplies the three. Every raw metric is exported
per combination, so if you weight these differently, re-rank the CSV
yourself - the ranking is a heuristic, the metrics are the data.

INPUT: evaluated_sightings_{REGION}.csv produced by analyze_grouse.py
(uses the already-extracted feature columns; no raster access needed).
Non-vegetated records (nonveg_landcover == True) are excluded, matching
the main pipeline.

Usage:
    python tune_envelope_bins.py
    python tune_envelope_bins.py --regions ME
    python tune_envelope_bins.py --min-pts 50 --top 15
"""
import os
import argparse
import itertools
import numpy as np
import pandas as pd

REGIONS_DEFAULT = ["ME", "NH", "VT"]
MIN_PTS_PER_ENVELOPE_DEFAULT = 30



# ==========================================
# BINNING VARIANTS
# ==========================================
# Each candidate variable maps to one or more (variant_label, function)
# options. The sweep tries every subset of variables crossed with every
# combination of their variants. Functions take the full dataframe and
# return a string Series (the bin label per record).

def _qcut(series, q):
    labels = [f"Q{i + 1}" for i in range(q)]
    try:
        binned = pd.qcut(series, q=q, labels=False, duplicates='drop')
        return binned.map(lambda v: f"Q{int(v) + 1}" if pd.notna(v) else "NA").astype(str)
    except ValueError:
        return series.astype(int).astype(str)


def _slope_fixed(series, edges, labels):
    return pd.cut(series, bins=edges, labels=labels).astype(str)


VARIANTS = {
    "evt": [
        ("raw", lambda df: df["evt"].astype(int).astype(str)),
    ],
    # Macro classes mapped from the LANDFIRE EVT attribute table by
    # analyze_grouse.py (columns present in evaluated_sightings CSVs when
    # the attribute tables have been downloaded). ~10 physiognomy classes;
    # groups are coarser than raw EVT but finer than physiognomy.
    "evt_phys": [
        ("raw", lambda df: df["evt_phys"].astype(str)),
    ],
    "evt_group": [
        ("raw", lambda df: df["evt_group"].astype(str)),
    ],
    "sclass": [
        ("raw", lambda df: df["sclass"].astype(int).astype(str)),
    ],
    "evh": [
        ("q2", lambda df: _qcut(df["evh"], 2)),
        ("q3", lambda df: _qcut(df["evh"], 3)),
        ("q4", lambda df: _qcut(df["evh"], 4)),
        ("q5", lambda df: _qcut(df["evh"], 5)),
    ],
    "evc": [
        ("q2", lambda df: _qcut(df["evc"], 2)),
        ("q3", lambda df: _qcut(df["evc"], 3)),
        ("q4", lambda df: _qcut(df["evc"], 4)),
        ("q5", lambda df: _qcut(df["evc"], 5)),
    ],
    "slope": [
        ("t4", lambda df: _slope_fixed(df["slope"], [-1, 5, 15, 30, 90],
                                       ["Flat", "Rolling", "Steep", "Extreme"])),
        ("t2", lambda df: _slope_fixed(df["slope"], [-1, 15, 90],
                                       ["Gentle", "Steep"])),
    ],
    # aspect removed from the sweep per analysis decision: not a
    # meaningful habitat criterion for this study.
}


# ==========================================
# METRICS
# ==========================================
def evaluate_scheme(env_ids, min_pts):
    """Distribution-quality metrics for one envelope scheme."""
    counts = env_ids.value_counts()
    n_records = len(env_ids)
    n_env = len(counts)

    viable = counts[counts >= min_pts]
    n_viable = len(viable)
    coverage = viable.sum() / n_records if n_records else 0.0
    singleton_pct = 100 * (counts == 1).sum() / n_env if n_env else 0.0

    # Evenness among viable envelopes (normalized Shannon). 1.0 = records
    # spread perfectly evenly; -> 0 as one envelope dominates. Undefined
    # for <2 viable envelopes, treated as 0 (a single mega-bin gives no
    # stratification even though its "KDE" would be stable).
    if n_viable >= 2:
        p = viable / viable.sum()
        evenness = float(-(p * np.log(p)).sum() / np.log(n_viable))
    else:
        evenness = 0.0

    score = coverage * evenness * np.log1p(n_viable)

    return {
        "n_envelopes": n_env,
        "n_viable": n_viable,
        "coverage_pct": 100 * coverage,
        "evenness": evenness,
        "singleton_pct": singleton_pct,
        "median_per_env": float(counts.median()) if n_env else 0.0,
        "score": score,
    }


# ==========================================
# SWEEP
# ==========================================
def run_sweep(df, min_pts):
    var_names = [v for v in VARIANTS if _has_column_data(df, v)]
    skipped = [v for v in VARIANTS if v not in var_names]
    if skipped:
        print(f"  [!] Skipping variables with no usable data: {skipped}")

    # Precompute every variant's labels once - the sweep then just
    # concatenates precomputed columns instead of re-binning per combo.
    labels = {}
    for var in var_names:
        for variant_name, fn in VARIANTS[var]:
            labels[(var, variant_name)] = pd.Series(fn(df), index=df.index).astype(str)

    rows = []
    for k in range(1, len(var_names) + 1):
        for subset in itertools.combinations(var_names, k):
            variant_choices = [VARIANTS[v] for v in subset]
            for combo in itertools.product(*variant_choices):
                spec = [(var, variant_name) for var, (variant_name, _) in zip(subset, combo)]
                env_ids = labels[spec[0]].copy()
                for key in spec[1:]:
                    env_ids = env_ids + "|" + labels[key]
                metrics = evaluate_scheme(env_ids, min_pts)
                metrics["n_vars"] = k
                metrics["combo"] = " + ".join(f"{v}({t})" for v, t in spec)
                rows.append(metrics)
    return pd.DataFrame(rows)


def _has_column_data(df, var):
    if var not in df.columns or not df[var].notna().any():
        return False
    # Macro columns exist but are all "Unmapped" when no EVT attribute
    # table was available at analyze time - a single-value column adds
    # nothing to any scheme, so exclude it from the sweep.
    if var in ("evt_phys", "evt_group") and df[var].nunique() <= 1:
        return False
    return True


# ==========================================
# MAIN
# ==========================================
def main():
    parser = argparse.ArgumentParser(
        description="Sweep envelope variable subsets and bin granularities; "
                    "rank by distribution quality for KDE stratification.")
    parser.add_argument("--regions", nargs="+", default=REGIONS_DEFAULT)
    parser.add_argument("--min-pts", type=int, default=MIN_PTS_PER_ENVELOPE_DEFAULT,
                        help="Minimum records for an envelope to count as "
                             "KDE-viable (default: %(default)s)")
    parser.add_argument("--top", type=int, default=10,
                        help="How many top combos to print (default: %(default)s)")
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
        n_total = len(df)
        if "nonveg_landcover" in df.columns:
            df = df[~df["nonveg_landcover"].astype(bool)].copy()
        print(f"  {len(df):,} vegetated habitat records "
              f"(of {n_total:,} total) | viability threshold: "
              f">= {args.min_pts} records/envelope")

        if len(df) < args.min_pts * 2:
            print(f"  [!] Too few records to stratify meaningfully. Skipping.")
            continue

        results = run_sweep(df, args.min_pts)
        results = results.sort_values("score", ascending=False).reset_index(drop=True)

        out_csv = f"data/pipeline/bin_tuning_{region}.csv"
        results.to_csv(out_csv, index=False)

        cols = ["combo", "n_vars", "n_envelopes", "n_viable",
                "coverage_pct", "evenness", "singleton_pct", "score"]
        print(f"\n  TOP {args.top} SCHEMES OVERALL "
              f"(score = coverage x evenness x log(1 + viable envelopes)):")
        print(results.head(args.top)[cols].to_string(
            index=False, float_format=lambda x: f"{x:.3f}"))

        print(f"\n  BEST SCHEME PER NUMBER OF VARIABLES:")
        best_per_k = results.loc[results.groupby("n_vars")["score"].idxmax()]
        print(best_per_k.sort_values("n_vars")[cols].to_string(
            index=False, float_format=lambda x: f"{x:.3f}"))

        print(f"\n  Full results ({len(results):,} combinations tested) "
              f"saved to {out_csv} - re-sort by any column to apply your "
              f"own weighting.")


if __name__ == "__main__":
    main()

