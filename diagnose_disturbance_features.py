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
  * USFS LCMS (default USFS/GTAC/LCMS/v2024-10, CONUS): annual Change
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
import os
import time

import numpy as np
import pandas as pd

import diagnose_gbm_baseline as gbm

LCMS_ASSET = "USFS/GTAC/LCMS/v2024-10"
GFC_ASSET = "UMD/hansen/global_forest_change_2024_v1_12"
LCMS_FIRST_YEAR = 1985
TREE_REMOVAL = 9
SUCCESSIONAL_GROWTH = 14
VEG_LOSS = (1, 2, 6, 7, 8, 9, 10, 11, 12, 13)   # 3-5: snow/ice, desiccation, inundation
NONE_YEARS = 40                                  # "no event on record" cap
BATCH = 800                                      # points per Earth Engine request

FEATURES_LCMS = ["lcms_ys_removal", "lcms_ys_loss", "lcms_growth10",
                 "lcms_rm20_r250", "lcms_rm20_r1000"]
FEATURES_GFC = ["gfc_ys_loss", "gfc_loss20_r250", "gfc_treecover2000"]


def point_frame(concat):
    """longitude, latitude, year of every point, in the order
    gbm.patch_frames returns them (dataset parts in order, rows in order)."""
    return pd.concat([part.df[["longitude", "latitude", "year"]]
                      for part in concat.datasets], ignore_index=True)


def lcms_image(ee, asset, year):
    """Per-pixel features from LCMS Change up to and including `year`."""
    col = (ee.ImageCollection(asset)
           .filter(ee.Filter.eq("study_area", "CONUS"))
           .filter(ee.Filter.rangeContains("year", LCMS_FIRST_YEAR, year)))
    proj = ee.Image(col.first()).select("Change").projection()

    def year_where(img, cond):
        y = ee.Number(img.get("year"))
        return ee.Image.constant(y).toInt16().updateMask(cond)

    def removal(img):
        return year_where(img, img.select("Change").eq(TREE_REMOVAL))

    def loss(img):
        chg = img.select("Change")
        return year_where(img, chg.remap(list(VEG_LOSS), [1] * len(VEG_LOSS), 0))

    def growth_recent(img):
        y = ee.Number(img.get("year"))
        recent = y.gt(year - 10)
        return (img.select("Change").eq(SUCCESSIONAL_GROWTH)
                .And(ee.Image.constant(recent)).toInt16())

    def removal_recent(img):
        y = ee.Number(img.get("year"))
        recent = y.gt(year - 20)
        return (img.select("Change").eq(TREE_REMOVAL)
                .And(ee.Image.constant(recent)).toInt16())

    last_rm = col.map(removal).max().unmask(0).rename("last_removal")
    last_ls = col.map(loss).max().unmask(0).rename("last_loss")
    growth = col.map(growth_recent).sum().rename("growth10")
    rm20 = col.map(removal_recent).max().unmask(0).reproject(proj)
    r250 = rm20.reduceNeighborhood(ee.Reducer.mean(),
                                   ee.Kernel.circle(250, "meters"))
    r1000 = rm20.reduceNeighborhood(ee.Reducer.mean(),
                                    ee.Kernel.circle(1000, "meters"))
    return (ee.Image.cat([last_rm, last_ls, growth]).reproject(proj)
            .addBands(r250.rename("rm20_r250"))
            .addBands(r1000.rename("rm20_r1000")))


def gfc_image(ee, asset, year):
    """Hansen loss up to and including `year`, and 2000 tree cover."""
    g = ee.Image(asset)
    ly = g.select("lossyear")                        # 0 none, k = 2000 + k
    cal = ly.add(2000)
    valid = ly.gt(0).And(cal.lte(year))
    last = cal.updateMask(valid).unmask(0).rename("gfc_last_loss")
    recent = valid.And(cal.gt(year - 20)).toInt16()
    r250 = recent.reduceNeighborhood(ee.Reducer.mean(),
                                     ee.Kernel.circle(250, "meters"))
    return (last.addBands(r250.rename("gfc_loss20_r250"))
            .addBands(g.select("treecover2000").rename("gfc_treecover2000")))


def sample(ee, image, pts):
    """reduceRegions(first) at 30 m for a frame with columns idx,
    longitude, latitude; returns {idx: {band: value}}."""
    out = {}
    for start in range(0, len(pts), BATCH):
        chunk = pts.iloc[start:start + BATCH]
        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([float(r.longitude), float(r.latitude)]),
                       {"idx": int(r.idx)}) for r in chunk.itertuples()])
        res = image.reduceRegions(collection=fc, reducer=ee.Reducer.first(),
                                  scale=30).getInfo()
        for f in res["features"]:
            p = f["properties"]
            out[int(p["idx"])] = p
    return out


def years_since(year, last):
    last = np.asarray(last, dtype=float)
    ys = np.where(last > 0, year - last, NONE_YEARS)
    return np.clip(ys, 0, NONE_YEARS)


def fetch(ee, pts, lcms_asset, gfc_asset):
    rows = []
    for y in sorted(pts["year"].unique()):
        sub = pts[pts["year"] == y]
        t = time.time()
        lc = sample(ee, lcms_image(ee, lcms_asset, int(y)), sub)
        gf = sample(ee, gfc_image(ee, gfc_asset, int(y)), sub)
        for r in sub.itertuples():
            a, b = lc.get(int(r.idx), {}), gf.get(int(r.idx), {})
            rows.append({"idx": int(r.idx), "year": int(y),
                         "last_removal": a.get("last_removal"),
                         "last_loss": a.get("last_loss"),
                         "growth10": a.get("growth10"),
                         "rm20_r250": a.get("rm20_r250"),
                         "rm20_r1000": a.get("rm20_r1000"),
                         "gfc_last_loss": b.get("gfc_last_loss"),
                         "gfc_loss20_r250": b.get("gfc_loss20_r250"),
                         "gfc_treecover2000": b.get("gfc_treecover2000")})
        print(f"   year {int(y)}: {len(sub):,} points sampled "
              f"({time.time() - t:.0f} s)")
    return pd.DataFrame(rows).sort_values("idx").reset_index(drop=True)


def derive(raw):
    f = pd.DataFrame({"idx": raw["idx"]})
    y = raw["year"].to_numpy(float)
    num = lambda c: pd.to_numeric(raw[c], errors="coerce").to_numpy(float)
    f["lcms_ys_removal"] = years_since(y, num("last_removal"))
    f["lcms_ys_loss"] = years_since(y, num("last_loss"))
    f["lcms_growth10"] = num("growth10")
    f["lcms_rm20_r250"] = num("rm20_r250")
    f["lcms_rm20_r1000"] = num("rm20_r1000")
    f["gfc_ys_loss"] = years_since(y, num("gfc_last_loss"))
    f["gfc_loss20_r250"] = num("gfc_loss20_r250")
    f["gfc_treecover2000"] = num("gfc_treecover2000")
    # A point the sample did not return (outside coverage) stays NaN; the
    # years-since columns must then be NaN too, not NONE_YEARS.
    for src, dst in (("last_removal", "lcms_ys_removal"),
                     ("last_loss", "lcms_ys_loss"),
                     ("gfc_last_loss", "gfc_ys_loss")):
        f.loc[np.isnan(num(src)), dst] = np.nan
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
