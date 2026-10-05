"""Would harvest / disturbance-history features raise the data ceiling?

diagnose_gbm_baseline.py put the ceiling of today's 15 raster features
at ~0.770 val AUC (gradient-boosted trees), with succession class (sclass)
the strongest signal. Ruffed grouse key on stand age after cutting
(roughly 5-20 years), which today's inputs carry only coarsely (sclass
classes; tsd from LANDFIRE Annual Disturbance, 1999+, which it barely
used). This tests candidate replacements BEFORE anyone builds rasters:
it samples them at the ~9,600 training/validation points through Earth
Engine and re-fits the same trees with and without them.

Candidate sources (both on Earth Engine, 30 m):
  * USFS LCMS (default projects/gtac-data-publish/assets/LCMS/Product_Version/2025-11,
    CONUS; USFS/GTAC/LCMS/v2024-10 via --lcms-asset): annual Change
    band 1985+ with cause attribution - 9 = Tree Removal (harvest),
    14 = Vegetation Successional Growth, 1-2 and 6-13 = other vegetation
    loss (3-5 are hydrologic/snow transitions, ignored).
  * Hansen Global Forest Change (default
    UMD/hansen/global_forest_change_2024_v1_12): lossyear (stand-replacing
    tree-cover loss, 2001+) and treecover2000.

Features, per point, computed from data up to and including the point's
OWN year Y (never later - same no-future rule as tsd):
  lcms_ys_removal   years since the last Tree Removal (capped, NONE_YEARS)
  lcms_ys_loss      years since the last vegetation loss of any cause
  lcms_growth10     years of Successional Growth in (Y-10, Y]
  lcms_rm20_r250    share of a 250 m radius with Tree Removal in (Y-20, Y]
  lcms_rm20_r1000   the same within 1 km
  gfc_ys_loss       years since Hansen stand-replacing loss (capped)
  gfc_loss20_r250   share of a 250 m radius with Hansen loss in (Y-20, Y]
  gfc_treecover2000 Hansen 2000 tree cover (%)
A pixel with no event gets NONE_YEARS (a fixed cap, so the most common
value does not encode the vintage; same reasoning as models.TSD_MAX_YEARS).
Positives and negatives have identical year histograms (CR-0021), so a
time-based feature cannot carry the year->label signal back in.

Reports: the AUC of each new feature alone (> 0.5: higher in positives),
and the trees' val AUC/AP for today's features vs today's + LCMS vs
today's + LCMS + Hansen, over several seeds. Reading: a gain of about
+0.01 AUC or more, stable across seeds, justifies a CR to build the
rasters and add the features to the CNN; less than ~0.003 does not.

Read-only for the project: points come from train.build_datasets
(cache_dir=None: same split and standing checks; nothing written under
data/). Earth Engine samples are cached to --cache (default under /tmp)
so a re-run does not re-query. Needs Earth Engine credentials, set up as
for download_tcc_nlcd.py (--project or EARTHENGINE_PROJECT).

Usage (repository root, same environment as train.py):
    python diagnose_disturbance_features.py --project <gcp-project>
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd

import diagnose_gbm_baseline as gbm

LCMS_ASSET = "projects/gtac-data-publish/assets/LCMS/Product_Version/2025-11"
GFC_ASSET = "UMD/hansen/global_forest_change_2024_v1_12"
LCMS_FIRST_YEAR = 1985
TREE_REMOVAL = 9
SUCCESSIONAL_GROWTH = 14
VEG_LOSS = (1, 2, 6, 7, 8, 9, 10, 11, 12, 13)   # 3-5: snow/ice, desiccation, inundation
NONE_YEARS = 40                                  # "no event on record" cap
BATCH_POINTS = 500                               # points per Earth Engine request
BATCH_BUFFERS = 150                              # buffered points per request
RADII_M = (250, 1000)

FEATURES_LCMS = ["lcms_ys_removal", "lcms_ys_loss", "lcms_growth10",
                 "lcms_rm20_r250", "lcms_rm20_r1000"]
FEATURES_GFC = ["gfc_ys_loss", "gfc_loss20_r250", "gfc_treecover2000"]


def point_frame(concat):
    """longitude, latitude, year of every point, in the order
    gbm.patch_frames returns them (dataset parts in order, rows in order)."""
    return pd.concat([part.df[["longitude", "latitude", "year"]]
                      for part in concat.datasets], ignore_index=True)


def lcms_stack(ee, asset, years):
    """One image, one band per year: c{year} = LCMS Change (CONUS)."""
    col = ee.ImageCollection(asset).filter(ee.Filter.eq("study_area", "CONUS"))
    have = set(int(v) for v in col.aggregate_array("year").getInfo())
    missing = [y for y in years if y not in have]
    if missing:
        raise SystemExit(f"{asset} has no CONUS image for years {missing}")
    return ee.Image.cat([
        col.filter(ee.Filter.eq("year", y)).first().select("Change")
        .rename(f"c{y}") for y in years])


def _features(ee, pts, radius=None):
    feats = []
    for r in pts.itertuples():
        g = ee.Geometry.Point([float(r.longitude), float(r.latitude)])
        if radius:
            g = g.buffer(radius)
        feats.append(ee.Feature(g, {"idx": int(r.idx)}))
    return ee.FeatureCollection(feats)


def reduce_batches(ee, image, pts, reducer, radius, batch, label):
    """reduceRegions over points (radius None) or buffers; on a timeout the
    batch is split in half and retried, down to single points (then the
    error propagates). Returns {idx: properties}."""
    from ee.ee_exception import EEException
    out = {}
    todo = [pts.iloc[i:i + batch] for i in range(0, len(pts), batch)]
    done = 0
    while todo:
        chunk = todo.pop(0)
        try:
            res = image.reduceRegions(collection=_features(ee, chunk, radius),
                                      reducer=reducer, scale=30,
                                      tileScale=4).getInfo()
        except EEException as e:
            if "timed out" not in str(e).lower() or len(chunk) == 1:
                raise
            half = len(chunk) // 2
            todo[:0] = [chunk.iloc[:half], chunk.iloc[half:]]
            print(f"   [{label}] timeout on {len(chunk)} points - "
                  f"retrying as {half} + {len(chunk) - half}")
            continue
        for f in res["features"]:
            out[int(f["properties"]["idx"])] = f["properties"]
        done += len(chunk)
        print(f"   [{label}] {done:,}/{len(pts):,}", flush=True)
    return out


def fetch(ee, pts, lcms_asset, gfc_asset):
    """Raw per-point samples (no per-year logic here; see derive):
    c{year} LCMS Change at the point, s{r}_{year} share of Tree Removal
    within r metres in that year, Hansen lossyear/treecover2000 at the
    point and the lossyear histogram within 250 m."""
    years = list(range(LCMS_FIRST_YEAR, int(pts["year"].max()) + 1))
    stack = lcms_stack(ee, lcms_asset, years)
    raw = pd.DataFrame({"idx": pts["idx"].to_numpy(),
                        "year": pts["year"].to_numpy()})
    first = ee.Reducer.first()
    at = reduce_batches(ee, stack, pts, first, None, BATCH_POINTS, "LCMS at points")
    for y in years:
        raw[f"c{y}"] = [at.get(i, {}).get(f"c{y}") for i in raw["idx"]]
    removal = stack.eq(TREE_REMOVAL)
    for r in RADII_M:
        sh = reduce_batches(ee, removal, pts, ee.Reducer.mean(), r,
                            BATCH_BUFFERS if r > 300 else BATCH_POINTS,
                            f"LCMS removal share {r} m")
        for y in years:
            raw[f"s{r}_{y}"] = [sh.get(i, {}).get(f"c{y}") for i in raw["idx"]]
    g = ee.Image(gfc_asset).select(["lossyear", "treecover2000"])
    gp = reduce_batches(ee, g, pts, first, None, BATCH_POINTS, "Hansen at points")
    raw["gfc_lossyear"] = [gp.get(i, {}).get("lossyear") for i in raw["idx"]]
    raw["gfc_treecover2000"] = [gp.get(i, {}).get("treecover2000") for i in raw["idx"]]
    gh = reduce_batches(ee, g.select("lossyear"), pts,
                        ee.Reducer.frequencyHistogram(), 250, BATCH_POINTS,
                        "Hansen loss histogram 250 m")
    raw["gfc_hist250"] = [json.dumps(gh.get(i, {}).get("histogram"))
                          for i in raw["idx"]]
    return raw


def _num(raw, col):
    return pd.to_numeric(raw[col], errors="coerce").to_numpy(float)


def derive(raw):
    """Per-point features from the raw samples, using only years <= the
    point's own year Y (no future)."""
    Y = raw["year"].to_numpy(int)
    years = sorted(int(c[1:]) for c in raw.columns
                   if c.startswith("c") and c[1:].isdigit())
    yr = np.array(years)
    C = np.stack([_num(raw, f"c{y}") for y in years], axis=1)   # (N, T)
    upto = yr[None, :] <= Y[:, None]
    have = ~np.isnan(C).all(axis=1)

    def last_year(mask):
        m = mask & upto
        last = np.where(m, yr[None, :], 0).max(axis=1).astype(float)
        ys = np.where(last > 0, Y - last, NONE_YEARS)
        ys = np.clip(ys, 0, NONE_YEARS).astype(float)
        ys[~have] = np.nan
        return ys

    f = pd.DataFrame({"idx": raw["idx"]})
    f["lcms_ys_removal"] = last_year(C == TREE_REMOVAL)
    f["lcms_ys_loss"] = last_year(np.isin(C, VEG_LOSS))
    recent10 = upto & (yr[None, :] > (Y[:, None] - 10))
    g = ((C == SUCCESSIONAL_GROWTH) & recent10).sum(axis=1).astype(float)
    g[~have] = np.nan
    f["lcms_growth10"] = g
    recent20 = upto & (yr[None, :] > (Y[:, None] - 20))
    for r in RADII_M:
        S = np.stack([_num(raw, f"s{r}_{y}") for y in years], axis=1)
        # area-years harvested in the window / window length 1: the sum of
        # annual removal shares (a pixel cut twice counts twice; rare)
        share = np.where(recent20, np.nan_to_num(S), 0.0).sum(axis=1)
        share[np.isnan(S).all(axis=1)] = np.nan
        f[f"lcms_rm20_r{r}"] = np.clip(share, 0, 1)

    ly = _num(raw, "gfc_lossyear")                   # 0 none, k -> 2000 + k
    tc = _num(raw, "gfc_treecover2000")
    covered = ~np.isnan(tc)
    # Hansen leaves no-loss pixels MASKED (null), not 0: where the point
    # has tree-cover data, a null lossyear means "no loss on record".
    ly = np.where(np.isnan(ly) & covered, 0.0, ly)
    cal = np.where(ly > 0, 2000 + ly, 0)
    cal = np.where(cal <= Y, cal, 0)                 # a later loss is the future
    ys = np.where(cal > 0, Y - cal, NONE_YEARS).astype(float)
    ys[np.isnan(ly)] = np.nan
    f["gfc_ys_loss"] = np.clip(ys, 0, NONE_YEARS)
    shares = []
    for h, y0, cov in zip(raw["gfc_hist250"], Y, covered):
        hist = json.loads(h) if isinstance(h, str) and h != "null" else None
        if not hist:
            # no unmasked (= lost) pixel within 250 m: share 0 where Hansen
            # covers the point, unknown otherwise
            shares.append(0.0 if cov else np.nan)
            continue
        tot = sum(hist.values())
        win = sum(v for k, v in hist.items()
                  if 0 < float(k) and y0 - 20 < 2000 + float(k) <= y0)
        shares.append(win / tot if tot else np.nan)
    f["gfc_loss20_r250"] = shares
    f["gfc_treecover2000"] = tc
    return f


def single_auc(x, y):
    from sklearn.metrics import roc_auc_score
    ok = ~np.isnan(x)
    if ok.sum() < 10 or len(np.unique(y[ok])) < 2:
        return np.nan
    return float(roc_auc_score(y[ok], x[ok]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=os.environ.get("EARTHENGINE_PROJECT"))
    ap.add_argument("--lcms-asset", default=LCMS_ASSET)
    ap.add_argument("--gfc-asset", default=GFC_ASSET)
    ap.add_argument("--cache", default="/tmp/grouse_disturbance_samples.csv",
                    help="Earth Engine samples are saved here and re-used "
                         "when present (delete it to re-query).")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--img-size", type=int, default=64)
    args = ap.parse_args()

    import train
    from grouse_data import GrouseData, MISSING_CODE
    from models import split_features
    from regions import REGIONS

    t0 = time.time()
    data = GrouseData()
    regions = list(REGIONS)
    features = train.discover_features(data, regions)
    cat_f, cont_f = split_features(features)
    train_ds, val_ds, _ = train.build_datasets(
        data, regions, features, args.img_size, cache_dir=None,
        jitter=0, augment=False, background_per_pos=0.0)
    cat_tr, cont_tr, ytr = gbm.patch_frames(train_ds, args.workers)
    cat_va, cont_va, yva = gbm.patch_frames(val_ds, args.workers)
    pts = pd.concat([point_frame(train_ds), point_frame(val_ds)],
                    ignore_index=True)
    if len(pts) != len(ytr) + len(yva):
        raise SystemExit(f"point frame ({len(pts)}) and patches "
                         f"({len(ytr) + len(yva)}) disagree")
    pts["idx"] = np.arange(len(pts))
    pts["year"] = pts["year"].astype(int)
    print(f"Points: train {len(ytr):,}, val {len(yva):,}; patches read in "
          f"{time.time() - t0:.0f} s")

    key = (args.lcms_asset, args.gfc_asset, len(pts),
           float(pts["longitude"].sum()), int(pts["year"].sum()))
    raw = None
    if os.path.exists(args.cache):
        cached = pd.read_csv(args.cache)
        if (len(cached) == len(pts) and "key" in cached
                and cached["key"].iloc[0] == repr(key)):
            raw = cached.drop(columns=["key"])
            print(f"Earth Engine samples re-used from {args.cache}")
    if raw is None:
        from download_tcc_nlcd import ee_init
        ee = ee_init(args.project)
        print(f"Sampling {args.lcms_asset} and {args.gfc_asset} at "
              f"{len(pts):,} points ...")
        raw = fetch(ee, pts, args.lcms_asset, args.gfc_asset)
        raw.assign(key=repr(key)).to_csv(args.cache, index=False)
        print(f"   saved to {args.cache}")
    feats = derive(raw)
    n_tr = len(ytr)
    y_all = np.concatenate([ytr, yva])

    print("\n1. EACH NEW FEATURE ALONE (AUC; > 0.5: higher in positives; "
          "< 0.5: lower in positives)")
    for c in FEATURES_LCMS + FEATURES_GFC:
        x = feats[c].to_numpy(float)
        miss = np.isnan(x).mean() * 100
        pos, neg = x[y_all == 1], x[y_all == 0]
        print(f"  {c:18s} AUC train {single_auc(x[:n_tr], ytr):.3f}  "
              f"val {single_auc(x[n_tr:], yva):.3f}   median pos "
              f"{np.nanmedian(pos):7.2f} / neg {np.nanmedian(neg):7.2f}   "
              f"missing {miss:.1f}%")
    for c, lo, hi in (("lcms_ys_removal", 5, 20), ("gfc_ys_loss", 5, 20)):
        x = feats[c].to_numpy(float)
        win = (x >= lo) & (x <= hi)
        print(f"  share with {c} in [{lo}, {hi}] years: positives "
              f"{win[y_all == 1].mean() * 100:.1f}%  negatives "
              f"{win[y_all == 0].mean() * 100:.1f}%")

    print("\n2. TREES (centre + neighbourhood, val), with and without the "
          "new features")
    n = cat_tr.shape[-1]
    train_centre = cat_tr[:, :, n // 2, n // 2]
    Xtr, names, is_cat = gbm.design(cat_tr, cont_tr, cat_f, cont_f,
                                    train_centre, MISSING_CODE, True)
    Xva, _, _ = gbm.design(cat_va, cont_va, cat_f, cont_f,
                           train_centre, MISSING_CODE, True)
    F = feats[FEATURES_LCMS + FEATURES_GFC].to_numpy(float)
    sets = (("today's features", []),
            ("+ LCMS", FEATURES_LCMS),
            ("+ LCMS + Hansen", FEATURES_LCMS + FEATURES_GFC))
    base = None
    for label, extra in sets:
        cols = [ (FEATURES_LCMS + FEATURES_GFC).index(c) for c in extra]
        Xt = np.concatenate([Xtr, F[:n_tr][:, cols]], axis=1)
        Xv = np.concatenate([Xva, F[n_tr:][:, cols]], axis=1)
        ic = np.concatenate([is_cat, np.zeros(len(cols), bool)])
        aucs, aps = [], []
        for s in args.seeds:
            _, a, p = gbm.fit_eval(Xt, ytr, Xv, yva, ic, s)
            aucs.append(a)
            aps.append(p)
        m = float(np.mean(aucs))
        base = m if base is None else base
        print(f"  {label:18s} {Xt.shape[1]:3d} features  AUC {m:.4f} +/- "
              f"{np.std(aucs):.4f}  AP {np.mean(aps):.4f}  "
              f"(vs today {m - base:+.4f})")
    print(f"\nDone in {time.time() - t0:.0f} s.")


if __name__ == "__main__":
    main()
