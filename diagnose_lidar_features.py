"""Would lidar-grade forest structure raise the data ceiling?

Ruffed grouse select young, dense forest - a thick 0-5 m understory of
saplings and shrubs - which 30 m LANDFIRE canopy layers (ch, cc, evh)
and TreeMap carry only coarsely. Building a wall-to-wall airborne lidar
(USGS 3DEP) layer for ME/NH/VT is a large job; this tests the idea first
with two Earth Engine products, sampled at the ~9,600 training and
validation points, by re-fitting diagnose_gbm_baseline's trees with and
without them:

  * Meta/WRI 1 m canopy height
    (projects/sat-io/open-datasets/facebook/meta-canopy-height): height
    predicted from sub-metre imagery by a model trained on airborne
    lidar (MAE 2.8 m; imagery mostly 2018-2020). Stands in for a lidar
    canopy-height model: fine gaps, sapling/pole patches, edges.
      meta_mean_rR, meta_sd_rR          mean / std of height within R m
      meta_f0_1_rR, meta_f1_5_rR,       share of 1 m pixels in height
      meta_f5_12_rR, meta_f12p_rR       classes 0-1, 1-5, 5-12, >= 12 m
    for R = 30 m (1 m pixels) and 100 m (2 m pixels).
  * GEDI L2B (LARSE/GEDI/GEDI02_B_002_MONTHLY): spaceborne lidar
    waveform metrics, 25 m footprints, 2019-2024, quality-filtered
    (l2b_quality_flag == 1, degrade_flag == 0). Within 250 m of a point:
      gedi_n         number of quality footprints (0 = no coverage)
      gedi_pavd_0_5  plant area volume density 0-5 m (understory)
      gedi_pavd_5_10 the same 5-10 m
      gedi_cover, gedi_pai, gedi_fhd   canopy cover, plant area index,
                                       foliage height diversity
    GEDI samples along tracks, so many points have no footprint nearby;
    the report says how many and also scores the trees on that subset.

Reading: a stable gain of about +0.01 val AUC (Meta) or a clear gain on
the GEDI-covered subset would justify building a structure layer (a CR:
3DEP-derived understory density or the Meta product as a raster). Less
than ~0.003 means fine-scale structure adds little beyond today's inputs.

Read-only for the project (train.build_datasets, cache_dir=None; nothing
written under data/). Earth Engine samples cached to --cache (default
under /tmp). Credentials as for download_tcc_nlcd.py.

Usage (repository root):
    python diagnose_lidar_features.py --project <gcp-project>
"""
import argparse
import os
import re
import time

import numpy as np
import pandas as pd

import diagnose_gbm_baseline as gbm
import diagnose_disturbance_features as ddf

META_ASSET = "projects/sat-io/open-datasets/facebook/meta-canopy-height"
GEDI_ASSET = "LARSE/GEDI/GEDI02_B_002_MONTHLY"
META_RADII = ((30, 1), (100, 2))          # (radius m, sampling scale m)
HEIGHT_BINS = ((0, 1), (1, 5), (5, 12), (12, 200))
GEDI_RADIUS = 250


def meta_image(ee):
    h = ee.ImageCollection(META_ASSET).mosaic()
    h = h.select([0]).rename("h")
    bands = [h]
    for lo, hi in HEIGHT_BINS:
        name = f"f{lo}_{hi}" if hi < 200 else f"f{lo}p"
        bands.append(h.gte(lo).And(h.lt(hi)).rename(name))
    return ee.Image.cat(bands)


def gedi_image(ee):
    col = ee.ImageCollection(GEDI_ASSET)
    names = ee.Image(col.first()).bandNames().getInfo()
    pavd = sorted((b for b in names if re.fullmatch(r"pavd_z\d+", b)),
                  key=lambda b: int(b[6:]))
    if len(pavd) < 2:
        raise SystemExit(f"{GEDI_ASSET}: no pavd_z* bands in {names[:20]}...")
    want = {"cover": "cover", "pai": "pai", "fhd_normal": "fhd"}
    missing = [b for b in want if b not in names]
    if missing:
        raise SystemExit(f"{GEDI_ASSET}: bands {missing} not found")
    print(f"   GEDI understory bands: {pavd[0]} (0-5 m), {pavd[1]} (5-10 m)")

    def q(im):
        good = im.select("l2b_quality_flag").eq(1).And(
            im.select("degrade_flag").eq(0))
        return (im.select([pavd[0], pavd[1], "cover", "pai", "fhd_normal"],
                          ["pavd_0_5", "pavd_5_10", "cover", "pai", "fhd"])
                .updateMask(good))
    return col.map(q).mean()


def fetch(ee, pts):
    raw = pd.DataFrame({"idx": pts["idx"].to_numpy()})
    cols = {}
    meta = meta_image(ee)
    red = ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True)
    for r, scale in META_RADII:
        res = ddf.reduce_batches(ee, meta, pts, red, r,
                                 ddf.BATCH_POINTS if r <= 30 else ddf.BATCH_BUFFERS,
                                 f"Meta canopy height {r} m", scale=scale)
        for b in ["h_mean", "h_stdDev"] + [
                f"f{lo}_{hi}_mean" if hi < 200 else f"f{lo}p_mean"
                for lo, hi in HEIGHT_BINS]:
            cols[f"meta_{b}_r{r}"] = [res.get(i, {}).get(b) for i in raw["idx"]]
    gedi = gedi_image(ee)
    red = ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True)
    res = ddf.reduce_batches(ee, gedi, pts, red, GEDI_RADIUS,
                             ddf.BATCH_BUFFERS, f"GEDI within {GEDI_RADIUS} m",
                             scale=25)
    for b in ("pavd_0_5", "pavd_5_10", "cover", "pai", "fhd"):
        cols[f"gedi_{b}"] = [res.get(i, {}).get(f"{b}_mean") for i in raw["idx"]]
    cols["gedi_n"] = [res.get(i, {}).get("cover_count") for i in raw["idx"]]
    return pd.concat([raw, pd.DataFrame(cols)], axis=1)


def derive(raw):
    f = pd.DataFrame({"idx": raw["idx"]})
    for r, _ in META_RADII:
        f[f"meta_mean_r{r}"] = ddf._num(raw, f"meta_h_mean_r{r}")
        f[f"meta_sd_r{r}"] = ddf._num(raw, f"meta_h_stdDev_r{r}")
        for lo, hi in HEIGHT_BINS:
            tag = f"{lo}_{hi}" if hi < 200 else f"{lo}p"
            f[f"meta_f{tag}_r{r}"] = ddf._num(raw, f"meta_f{tag}_mean_r{r}")
    n = np.nan_to_num(ddf._num(raw, "gedi_n"), nan=0.0)
    f["gedi_n"] = n
    for b in ("pavd_0_5", "pavd_5_10", "cover", "pai", "fhd"):
        v = ddf._num(raw, f"gedi_{b}").copy()
        v[n == 0] = np.nan               # no footprint nearby: unknown
        f[f"gedi_{b}"] = v
    return f


def trees(Xtr, Xva, is_cat, F, cols, ytr, yva, seeds, rows_va=None):
    n_tr = len(ytr)
    Xt = np.concatenate([Xtr, F[:n_tr][:, cols]], axis=1)
    Xv = np.concatenate([Xva, F[n_tr:][:, cols]], axis=1)
    ic = np.concatenate([is_cat, np.zeros(len(cols), bool)])
    aucs, aps = [], []
    for s in seeds:
        clf, a, p = gbm.fit_eval(Xt, ytr, Xv, yva, ic, s)
        if rows_va is not None:
            from sklearn.metrics import roc_auc_score, average_precision_score
            pr = clf.predict_proba(Xv[rows_va])[:, 1]
            a = roc_auc_score(yva[rows_va], pr)
            p = average_precision_score(yva[rows_va], pr)
        aucs.append(a)
        aps.append(p)
    return float(np.mean(aucs)), float(np.std(aucs)), float(np.mean(aps))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=os.environ.get("EARTHENGINE_PROJECT"))
    ap.add_argument("--cache", default="/tmp/grouse_lidar_samples.csv")
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
    pts = pd.concat([ddf.point_frame(train_ds), ddf.point_frame(val_ds)],
                    ignore_index=True)
    if len(pts) != len(ytr) + len(yva):
        raise SystemExit("point frame and patches disagree")
    pts["idx"] = np.arange(len(pts))
    print(f"Points: train {len(ytr):,}, val {len(yva):,}; patches read in "
          f"{time.time() - t0:.0f} s")

    key = repr((META_ASSET, GEDI_ASSET, len(pts),
                float(pts["longitude"].sum())))
    raw = None
    if os.path.exists(args.cache):
        cached = pd.read_csv(args.cache)
        if len(cached) == len(pts) and cached["key"].iloc[0] == key:
            raw = cached.drop(columns=["key"])
            print(f"Earth Engine samples re-used from {args.cache}")
    if raw is None:
        from download_tcc_nlcd import ee_init
        ee = ee_init(args.project)
        print(f"Sampling Meta canopy height and GEDI L2B at {len(pts):,} points ...")
        raw = fetch(ee, pts)
        raw.assign(key=key).to_csv(args.cache, index=False)
        print(f"   saved to {args.cache}")
    feats = derive(raw)
    n_tr = len(ytr)
    y_all = np.concatenate([ytr, yva])
    meta_cols = [c for c in feats.columns if c.startswith("meta_")]
    gedi_cols = [c for c in feats.columns if c.startswith("gedi_")]

    print("\n1. EACH NEW FEATURE ALONE (AUC; > 0.5: higher in positives)")
    for c in meta_cols + gedi_cols:
        x = feats[c].to_numpy(float)
        pos, neg = x[y_all == 1], x[y_all == 0]
        print(f"  {c:20s} AUC train {ddf.single_auc(x[:n_tr], ytr):.3f}  "
              f"val {ddf.single_auc(x[n_tr:], yva):.3f}   median pos "
              f"{np.nanmedian(pos):8.3f} / neg {np.nanmedian(neg):8.3f}   "
              f"missing {np.isnan(x).mean() * 100:.1f}%")
    has = feats["gedi_n"].to_numpy() > 0
    print(f"  GEDI quality footprints within {GEDI_RADIUS} m: "
          f"{has.mean() * 100:.1f}% of points (median "
          f"{np.median(feats['gedi_n'][has]) if has.any() else 0:.0f} "
          f"footprints where present)")

    print("\n2. TREES (centre + neighbourhood, val)")
    n = cat_tr.shape[-1]
    train_centre = cat_tr[:, :, n // 2, n // 2]
    Xtr, names, is_cat = gbm.design(cat_tr, cont_tr, cat_f, cont_f,
                                    train_centre, MISSING_CODE, True)
    Xva, _, _ = gbm.design(cat_va, cont_va, cat_f, cont_f,
                           train_centre, MISSING_CODE, True)
    allc = meta_cols + gedi_cols
    F = feats[allc].to_numpy(float)
    idx = lambda cs: [allc.index(c) for c in cs]
    base = None
    for label, cs in (("today's features", []), ("+ Meta 1 m height", meta_cols),
                      ("+ GEDI", gedi_cols), ("+ Meta + GEDI", allc)):
        m, sd, p = trees(Xtr, Xva, is_cat, F, idx(cs), ytr, yva, args.seeds)
        base = m if base is None else base
        print(f"  {label:18s} AUC {m:.4f} +/- {sd:.4f}  AP {p:.4f}  "
              f"(vs today {m - base:+.4f})")
    rows = has[n_tr:]
    if rows.sum() >= 100 and len(np.unique(yva[rows])) == 2:
        print(f"\n  Val points WITH a GEDI footprint within {GEDI_RADIUS} m "
              f"({int(rows.sum())}):")
        b = None
        for label, cs in (("today's features", []), ("+ GEDI", gedi_cols)):
            m, sd, p = trees(Xtr, Xva, is_cat, F, idx(cs), ytr, yva,
                             args.seeds, rows_va=rows)
            b = m if b is None else b
            print(f"  {label:18s} AUC {m:.4f} +/- {sd:.4f}  AP {p:.4f}  "
                  f"(vs today {m - b:+.4f})")
    print(f"\nDone in {time.time() - t0:.0f} s.")


if __name__ == "__main__":
    main()
