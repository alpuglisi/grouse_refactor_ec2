"""CR-0009 § Symptom acceptance and § symptom_check.py (v5).

Every symptom row is an OBSERVATION (BUG-0039, user decision
2026-09-30). Each row carries its type, the three PA-0021(f) fields
(class, subset, null population), its "investigate if" reference, the
calibration source and the counts per subset. A value beyond its
reference is a finding to investigate (PA-0016), never a rejection.

Replaces the untracked inv_state_split.py (item 1), inv_matched_pairs.py
(item 2) and inv_points_auc.py (item 3), keeping their methods:
  - Side of a map pixel: TIGER county polygons (regions.
    COUNTY_POLYGONS_YEAR; STATEFP 23 = ME, 33 = NH, 50 = VT) rasterised on
    the map grid, pixel-centre rule (all_touched=False).
  - Side of a record: `within` join on the same polygons, first match
    kept. The region files' `state` column is not used.
  - NaN (predict.py's "not scored") pixels, and records on them, are
    excluded and counted per side.
  - Pairs: the frozen pairs CSV (--pairs; inv_matched_pairs.csv's 8
    pairs) mapped to NH-grid cells by lon/lat. inv_matched_pairs.py's
    matching is re-run on the current NH rasters and the report says
    whether it selects the same cells; 2a/2b always use the frozen pairs.
  - Probabilities: sigmoid(logit / T + bias) with T and bias from
    --calibration, as predict.py applies them. Pair windows are scored in
    fp32, one 64x64 window each, D4 TTA with flip (inv_matched_pairs.py).

Map provenance (BUG-0028): a --map is copied into --out and hashed before
it is read; --predict (and REGION=predict) scores in-process through
predict.py's own functions (predict.py itself has no output-path flag and
overwrites data/predictions/). Either way >= 20 map cells are re-scored
with --model and --calibration and the run refuses (exit 2) if any differs
by more than SPOT_TOL. The sha256 of every input read is recorded.

Exit codes: 0 = observations written (whatever the numbers); 1 = the R
reproduction (--reproduce) did not reproduce; 2 = a missing input or a
failed guard (provenance, duplicate record, output under data/).

Modes:
  python symptom_check.py --model M --calibration CAL --pairs CSV \\
        (--map TIF | --predict) --out DIR \\
        [--region-map ME=TIF | --region-map ME=predict] [--points CSV]
  python symptom_check.py --reproduce --calibration CAL --pairs CSV \\
        --out DIR [--evidence FILE] [--points CSV] [--region-map ...]
      R: gap3.pth and bce.pth, maps scored in-process, must equal the
      investigation's numbers at their printed precision (pins
      "reproduction"). A GATE on the instrument, not a symptom row.

Pins (references, baselines, R targets): docs/quality/cr0009_symptom_pins.json.
Unit tests: tests/test_symptom_check.py.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict

import numpy as np

from regions import BOXES, COUNTY_POLYGONS_YEAR, STATE_FIPS

HERE = os.path.dirname(os.path.abspath(__file__))
PINS = os.path.join(HERE, "docs", "quality", "cr0009_symptom_pins.json")
IMG = 64
HALF = IMG // 2
MATCH_CAT = ("evt", "evh", "evc", "sclass", "nlcd")
MATCH_TOL = {"ch": 2.0, "cc": 5.0, "tcc": 5.0}
N_PAIRS, PAIR_SEED = 8, 0
N_BOOT, BOOT_SEED = 100_000, 0
SPOT_N, SPOT_SEED, SPOT_TOL = 20, 0, 1e-3
BOX_STRIDE, REGION_STRIDE, BATCH = 4, 8, 256
ME, NH = "ME", "NH"
PAIRS_GRID = NH
BY_FIPS = {v: k for k, v in STATE_FIPS.items()}

# PA-0021(f) fields, CR-0009 v5 § Symptom acceptance.
FIELDS = {
    "1a": ("calibrated pixel scores of one map (rank statistic, so "
           "calibration-invariant)",
           "finite pixels in the box, ME vs NH side by TIGER 2023 county "
           "(other/none excluded)",
           "none: two post-fix values from two recipes, not a seed null"),
    "1b": ("same map, thresholded at 0.8 (depends on calibration)",
           "as 1a", "none, as 1a"),
    "2a": ("road_dist raster values at pair centres (model-independent)",
           "the 8 frozen pairs, NH region grid",
           "none needed for a deterministic raster read; the value changes "
           "only if a raster changes"),
    "2b": ("calibrated probability of a single 64x64 window at each pair "
           "centre, D4 TTA (as inv_matched_pairs.py)",
           "the 8 frozen pairs, NH region grid",
           "none for retrain seeds; an 8-pair bootstrap is reported as "
           "pair-sampling spread only (95 % interval of the mean)"),
    "3": ("map value sampled at each record",
          "in-box records of the named point set, by split x side",
          "none; few negatives, mostly training points"),
    "4": ("calibrated pixel scores of a whole-region map",
          "the region grid, split into state sides (TIGER 2023 county, "
          "pixel centre) and outside US counties (Canada, water)",
          "none (descriptive)"),
    "5": ("- (not distributional)", "-", "-"),
}


class GuardError(Exception):
    """A failed input guard: exit 2."""


def load_pins(path=PINS):
    with open(path) as f:
        return json.load(f)


def county_zip():
    from grouse_data import PATH_TEMPLATES
    return os.path.join(HERE, PATH_TEMPLATES["tiger_county"].format(
        year=COUNTY_POLYGONS_YEAR))


# ==========================================================================
# Pure statistics (unit-tested on synthetic data)
# ==========================================================================
def rank_prob(a, b):
    """P(random a > random b), ties counted half: Mann-Whitney U / (na nb)."""
    from scipy.stats import mannwhitneyu
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.size == 0 or b.size == 0:
        return float("nan")
    return float(mannwhitneyu(a, b, alternative="two-sided").statistic) / (
        a.size * b.size)


def value_stats(v):
    v = np.asarray(v, float)
    if v.size == 0:
        return {"n": 0}
    q = np.percentile(v, [1, 10, 50, 90, 99])
    return {"n": int(v.size), "mean": float(v.mean()),
            "p01": float(q[0]), "p10": float(q[1]), "median": float(q[2]),
            "p90": float(q[3]), "p99": float(q[4]),
            "ge05_pct": float(100 * (v >= 0.5).mean()),
            "ge08_pct": float(100 * (v >= 0.8).mean())}


def item1(arr, me_mask, nh_mask):
    """Items 1a and 1b. NaN cells are excluded and counted per side;
    cells on neither side are counted as other/none."""
    fin = np.isfinite(arr)
    me, nh = arr[me_mask & fin], arr[nh_mask & fin]
    out = {ME: value_stats(me), NH: value_stats(nh),
           "nan_cells": {ME: int((me_mask & ~fin).sum()),
                         NH: int((nh_mask & ~fin).sum())},
           "other_cells": int((~me_mask & ~nh_mask).sum()),
           "p_me_gt_nh": rank_prob(me, nh)}
    both = bool(me.size and nh.size)
    out["gap08_pp"] = (out[ME]["ge08_pct"] - out[NH]["ge08_pct"]
                       if both else float("nan"))
    out["mean_diff"] = (out[ME]["mean"] - out[NH]["mean"]
                        if both else float("nan"))
    return out


def bootstrap_interval(diffs, n_boot=N_BOOT, seed=BOOT_SEED):
    """Pair-sampling spread of a mean: resample the per-pair differences
    with replacement n_boot times; 95 % interval of the resampled means."""
    d = np.asarray(diffs, float)
    out = {"n_pairs": int(d.size), "n_boot": 0, "seed": seed,
           "mean": float(d.mean()) if d.size else float("nan"),
           "lo95": float("nan"), "hi95": float("nan")}
    if d.size < 2:
        return out
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, d.size, size=(n_boot, d.size))].mean(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    out.update(n_boot=int(n_boot), lo95=float(lo), hi95=float(hi))
    return out


def match_pairs(sig, ch, cc, tcc, me_ok, nh_ok, n_pairs=N_PAIRS,
                seed=PAIR_SEED):
    """inv_matched_pairs.py's matcher. sig: (k, H, W) categorical signature;
    ch/cc/tcc: (H, W) in real units; me_ok/nh_ok: candidate cells. ME
    candidates are visited in rng.permutation order; each takes the first
    NH cell (row-major) with the same signature and every structure value
    within MATCH_TOL. Returns [((r, c) ME, (r, c) NH), ...]."""
    rng = np.random.default_rng(seed)
    me_idx = np.argwhere(me_ok)
    buckets = defaultdict(list)
    for r, c in np.argwhere(nh_ok):
        buckets[tuple(sig[:, r, c])].append((r, c))
    pairs = []
    for k in rng.permutation(len(me_idx)):
        r, c = me_idx[k]
        for r2, c2 in buckets.get(tuple(sig[:, r, c]), ()):
            if (abs(ch[r, c] - ch[r2, c2]) <= MATCH_TOL["ch"]
                    and abs(cc[r, c] - cc[r2, c2]) <= MATCH_TOL["cc"]
                    and abs(tcc[r, c] - tcc[r2, c2]) <= MATCH_TOL["tcc"]):
                pairs.append(((int(r), int(c)), (int(r2), int(c2))))
                break
        if len(pairs) >= n_pairs:
            break
    return pairs


def by_pair(rows, key):
    out = defaultdict(dict)
    for r in rows:
        out[r["pair"]][r["side"]] = r[key]
    return out


def pair_diffs(rows, key, rnd=None):
    """ME minus NH per pair (pairs in order); each side is rounded to `rnd`
    decimals first when given (the investigation rounded road_dist to
    whole metres and probabilities to 4 decimals before differencing).
    A pair with a NaN on either side gives NaN."""
    out = []
    for p, s in sorted(by_pair(rows, key).items()):
        a, b = s.get(ME, np.nan), s.get(NH, np.nan)
        if rnd is not None and np.isfinite(a) and np.isfinite(b):
            a, b = round(a, rnd), round(b, rnd)
        out.append(a - b)
    return out


def item2_from_rows(rows):
    raw_road = pair_diffs(rows, "road_dist_m")
    rec_road = pair_diffs(rows, "road_dist_m", 0)
    raw_prob = pair_diffs(rows, "prob")
    rec_prob = pair_diffs(rows, "prob", 4)
    fin = [v for v in raw_prob if np.isfinite(v)]

    def mean(v):
        v = [x for x in v if np.isfinite(x)]
        return float(np.mean(v)) if v else None
    return {"n_pairs": len(raw_road),
            "n_pairs_finite_road": int(np.isfinite(raw_road).sum()),
            "n_pairs_finite_prob": len(fin),
            "cells_missing_input": sum(bool(r["missing_at_centre"])
                                       for r in rows),
            "diff_road_m": raw_road, "diff_road_m_recorded": rec_road,
            "diff_prob": raw_prob, "diff_prob_recorded": rec_prob,
            "mean_diff_road_m": mean(raw_road),
            "mean_diff_road_m_recorded": mean(rec_road),
            "mean_diff_prob": mean(raw_prob),
            "mean_diff_prob_recorded": mean(rec_prob),
            "boot_2b": bootstrap_interval(fin)}


def union_point_set(frames):
    """Union of per-region-file point frames; a duplicate (lon, lat, label)
    is refused (CR-0009 v5: each record in one region after CR-0012)."""
    import pandas as pd
    pts = pd.concat(frames, ignore_index=True)
    key = pts[["longitude", "latitude", "label"]]
    dup = key.duplicated(keep=False)
    if dup.any():
        d = pts[dup].sort_values(["longitude", "latitude"])
        raise GuardError(
            f"{int(key.duplicated().sum())} duplicate (lon, lat, label) "
            f"records across point files - refused (pass a captured point "
            f"set with --points). First: "
            f"{d.head(4).to_dict('records')}")
    return pts


def auc_block(labels, scores):
    from sklearn.metrics import average_precision_score, roc_auc_score
    labels, scores = np.asarray(labels), np.asarray(scores, float)
    out = {"n": int(labels.size), "pos": int((labels == 1).sum()),
           "neg": int((labels == 0).sum())}
    if out["pos"]:
        out["mean_pos"] = float(scores[labels == 1].mean())
    if out["neg"]:
        out["mean_neg"] = float(scores[labels == 0].mean())
    if out["pos"] and out["neg"]:
        out["auc"] = float(roc_auc_score(labels, scores))
        out["ap"] = float(average_precision_score(labels, scores))
    return out


def item3_blocks(labels, scores, sides, splits):
    """AUC/AP blocks: side in (all + sides present) x split in (all,
    train, val). Records on NaN are excluded and counted per side."""
    labels, scores = np.asarray(labels), np.asarray(scores, float)
    sides, splits = np.asarray(sides), np.asarray(splits)
    ok = np.isfinite(scores)
    blocks = {}
    for side in ["all"] + sorted(set(sides.tolist())):
        for split in ("all", "train", "val"):
            m = ok.copy()
            if side != "all":
                m &= sides == side
            if split != "all":
                m &= splits == split
            blocks[f"{side}/{split}"] = auc_block(labels[m], scores[m])
    off = {s: int((~ok & (sides == s)).sum()) for s in set(sides.tolist())}
    return blocks, off


def zone_summary(arr, zone, degraded=None, names=None):
    """Item 4 per zone code. arr: map (NaN = not scored); zone: int code per
    cell; degraded: bool per cell (an input missing at the centre) or None."""
    out = {}
    fin = np.isfinite(arr)
    for z in np.unique(zone):
        m = zone == z
        s = value_stats(arr[m & fin])
        s["cells"] = int(m.sum())
        s["nan_pct"] = float(100 * (m & ~fin).sum() / m.sum())
        if degraded is not None:
            nf = int((m & fin).sum())
            s["degraded_pct_of_scored"] = (
                float(100 * (degraded & m & fin).sum() / nf) if nf
                else float("nan"))
        out[(names or {}).get(int(z), str(int(z)))] = s
    return out


def map_cell_to_source(map_tr, ref_tr, gy, gx):
    """Map cell -> centre (row, col) of the 64 px window predict_region
    scored for it: cell (gy, gx)'s centre lies on the corner of source
    pixel (r_start + 32 + gy*stride, c_start + 32 + gx*stride)."""
    x = map_tr.c + (np.asarray(gx) + 0.5) * map_tr.a
    y = map_tr.f + (np.asarray(gy) + 0.5) * map_tr.e
    return (np.rint((y - ref_tr.f) / ref_tr.e).astype(int),
            np.rint((x - ref_tr.c) / ref_tr.a).astype(int))


def spot_check(scorer, arr, tr, n=SPOT_N, tol=SPOT_TOL, seed=SPOT_SEED):
    """Re-score n finite map cells with the scorer's model and calibration
    (as predict_region scores: CUDA autocast). Raises GuardError when any
    cell differs by more than tol: the map was not made by this model and
    calibration on these rasters."""
    fin = np.argwhere(np.isfinite(arr))
    if len(fin) < n:
        raise GuardError(f"map has {len(fin)} scored cells, fewer than the "
                         f"{n} the provenance check needs")
    rng = np.random.default_rng(seed)
    pick = fin[rng.choice(len(fin), n, replace=False)]
    rows, cols = map_cell_to_source(tr, scorer.ref.transform, pick[:, 0],
                                    pick[:, 1])
    p = np.asarray(scorer.probs(list(zip(rows.tolist(), cols.tolist())),
                                amp=True))
    d = np.abs(p - arr[pick[:, 0], pick[:, 1]])
    res = {"n": int(n), "tol": tol, "max_abs_diff": float(d.max()),
           "median_abs_diff": float(np.median(d))}
    if not np.all(d <= tol):
        raise GuardError(
            f"provenance: {int((d > tol).sum())}/{n} re-scored cells differ "
            f"from the map by more than {tol:g} (max {d.max():.3g}); the map "
            f"was not made with this model and calibration (BUG-0028)")
    return res


def equal_at_precision(measured, ref):
    """R's comparison: `ref` is the published string ("0.5400", "+202.75");
    measured must round to it at its printed number of decimals."""
    s = ref.lstrip("+")
    dec = len(s.split(".")[1]) if "." in s else 0
    if measured is None or not np.isfinite(measured):
        return False
    return round(float(measured), dec) == round(float(s), dec)


# ==========================================================================
# I/O
# ==========================================================================
_SHA = {}


def sha256(path):
    path = os.path.abspath(path)
    if path not in _SHA:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                h.update(chunk)
        _SHA[path] = h.hexdigest()
    return _SHA[path]


def git_state():
    def run(*a):
        try:
            return subprocess.run(["git", "-C", HERE, *a], capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unknown"
    return {"head": run("rev-parse", "HEAD"),
            "dirty_tracked": run("status", "--porcelain",
                                 "--untracked-files=no")}


def read_counties(crs, bounds_ll=None, fips=None, path=None):
    import geopandas as gpd
    kw = {"bbox": tuple(bounds_ll)} if bounds_ll is not None else {}
    c = gpd.read_file(path or county_zip(), **kw)
    if fips is not None:
        c = c[c.STATEFP.isin(fips)]
    return c.to_crs(crs)


def zone_codes(counties, shape, transform):
    """int32 per cell: STATEFP number of the county containing the cell
    centre (all_touched=False); 0 = no US county."""
    from rasterio.features import rasterize
    shapes = [(g, int(fp)) for g, fp in zip(counties.geometry,
                                            counties.STATEFP)
              if g is not None]
    if not shapes:
        return np.zeros(shape, np.int32)
    return rasterize(shapes, out_shape=shape, transform=transform, fill=0,
                     all_touched=False, dtype="int32")


def side_masks(counties, shape, transform):
    z = zone_codes(counties, shape, transform)
    return z == int(STATE_FIPS[ME]), z == int(STATE_FIPS[NH])


def read_map(path):
    import rasterio
    with rasterio.open(path) as src:
        a = src.read(1, masked=True).astype(np.float32).filled(np.nan)
        return a, src.transform, src.crs


def write_map(path, arr, transform, crs):
    """The GeoTIFF predict.main writes (float32, nodata NaN)."""
    import rasterio
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0],
                       width=arr.shape[1], count=1, dtype=rasterio.float32,
                       crs=crs, transform=transform, nodata=np.nan) as dst:
        dst.write(arr, 1)


def load_calibration(path, model_path):
    """As predict.main applies calibration.json: T = 1/scale, shift = bias
    (or a temperature-only file)."""
    with open(path) as f:
        cal = json.load(f)
    info = {"path": os.path.abspath(path), "sha256": sha256(path),
            "model_path": cal.get("model_path"),
            "fitted_at": cal.get("fitted_at")}
    if "scale" in cal and "bias" in cal:
        info.update(temperature=1.0 / float(cal["scale"]),
                    shift=float(cal["bias"]),
                    kind=f"Platt scale {float(cal['scale']):.6f} bias "
                         f"{float(cal['bias']):+.6f}")
    else:
        info.update(temperature=float(cal.get("temperature", 1.0)),
                    shift=0.0, kind="temperature-only")
    info["fitted_on_this_model"] = (
        cal.get("model_path") == os.path.abspath(model_path))
    if not info["fitted_on_this_model"]:
        print(f"[warn] calibration {path} was fitted on "
              f"{cal.get('model_path')}, not {os.path.abspath(model_path)}",
              file=sys.stderr)
    return info


def cal_source(cal):
    return (f"{cal['path']} ({cal['kind']}; model_path {cal['model_path']}"
            + ("" if cal["fitted_on_this_model"] else " - NOT this model")
            + ")")


class Scorer:
    """--model on one region's current rasters, loaded as predict.main
    loads it."""

    def __init__(self, model_path, region, cal, device):
        import predict
        import torch
        from grouse_data import (GrouseData,
                                 refuse_legacy_checkpoint_on_repaired)
        from models import FEATURE_SPEC
        self.torch, self.predict, self.device = torch, predict, device
        self.region, self.cal = region, cal
        self.rd = GrouseData()[region]
        feats = [f for f in self.rd.available_features() if f in FEATURE_SPEC]
        (self.model, self.cat_f, self.cont_f, self.features,
         self.cfg) = predict.load_model(model_path, feats, device)
        self.raster_paths = {f: self.rd.latest_raster_path(f)
                             for f in self.cat_f + self.cont_f}
        refuse_legacy_checkpoint_on_repaired(
            self.model, list(self.raster_paths.values()))
        self.srcs, self.ref = predict.open_aligned_sources(
            self.rd, self.cat_f, self.cont_f)

    def window(self, row, col):
        from rasterio.windows import Window
        return self.predict.read_window_stack(
            self.srcs, self.cat_f, self.cont_f,
            Window(col - HALF, row - HALF, IMG, IMG))

    def probs(self, centres, amp):
        """Calibrated probability per (row, col) window centre. amp=True
        scores as predict_region does (CUDA autocast); False in fp32, as
        inv_matched_pairs.py did."""
        from models import d4_tta_logits
        torch = self.torch
        cats, conts = zip(*(self.window(r, c) for r, c in centres))
        ac = (torch.amp.autocast("cuda")
              if amp and self.device.type == "cuda" else None)
        with torch.no_grad():
            lg = d4_tta_logits(
                self.model, torch.from_numpy(np.stack(cats)).to(self.device),
                torch.from_numpy(np.stack(conts)).to(self.device),
                flip_tta=True, autocast=ac).float().cpu().numpy()
        return 1.0 / (1.0 + np.exp(-(lg / self.cal["temperature"]
                                     + self.cal["shift"])))

    def predict_map(self, bounds, stride, out_path):
        """predict.main's scoring path with its defaults (bounds_to_window's
        default pad, batch 256, no compile, D4 + flip), written to out_path
        - never to data/predictions/."""
        wb = self.predict.bounds_to_window(self.ref, bounds)
        heat, tr, _, _ = self.predict.predict_region(
            self.model, self.device, self.srcs, self.ref, self.cat_f,
            self.cont_f, wb, stride, BATCH, False, flip_tta=True,
            temperature=self.cal["temperature"],
            logit_shift=self.cal["shift"])
        write_map(out_path, heat, tr, self.ref.crs)
        return out_path

    def close(self):
        for s in self.srcs.values():
            s.close()


# ==========================================================================
# Items
# ==========================================================================
def run_item1(arr, tr, crs, county_path=None):
    cty = read_counties(crs, fips=[STATE_FIPS[ME], STATE_FIPS[NH]],
                        path=county_path)
    me, nh = side_masks(cty, arr.shape, tr)
    return item1(arr, me, nh)


def load_frozen_pairs(path):
    """inv_matched_pairs.csv (or its evidence copy): columns pair, side,
    lon, lat; the recorded road_dist_m_NEW / prob_NEW are kept."""
    import pandas as pd
    df = pd.read_csv(path)
    need = {"pair", "side", "lon", "lat"}
    if not need <= set(df.columns):
        raise GuardError(f"{path}: needs columns {sorted(need)}")
    pairs = []
    for p in sorted(df.pair.unique()):
        d = df[df.pair == p].set_index("side")
        if set(d.index) != {ME, NH}:
            raise GuardError(f"{path}: pair {p} lacks an ME and an NH row")
        pairs.append({s: {"lon": float(d.loc[s, "lon"]),
                          "lat": float(d.loc[s, "lat"]),
                          **{k: float(d.loc[s, k]) for k in
                             ("road_dist_m_NEW", "prob_NEW") if k in d}}
                      for s in (ME, NH)})
    return pairs


def pairs_to_cells(pairs, ref):
    """Frozen pairs -> [((row, col) ME, (row, col) NH)] on a grid, by
    lon/lat (the cell containing the point)."""
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", ref.crs, always_xy=True)
    return [tuple(ref.index(*t.transform(p[s]["lon"], p[s]["lat"]))
                  for s in (ME, NH)) for p in pairs]


def pair_rows(scorer, cells):
    """Per cell: every input at the centre (real units), road_dist in
    metres, missing inputs, and the fp32 calibrated probability."""
    from grouse_data import MISSING_CODE
    from models import FEATURE_SPEC, road_dist_decode
    from pyproj import Transformer
    ref = scorer.ref
    inv = Transformer.from_crs(ref.crs, "EPSG:4326", always_xy=True)
    centres = [rc for p in cells for rc in p]
    probs = scorer.probs(centres, amp=False) if centres else []
    rows = []
    for i, (r, c) in enumerate(centres):
        cat, cont = scorer.window(r, c)
        lon, lat = inv.transform(*ref.xy(r, c))
        rec = {"pair": i // 2, "side": (ME, NH)[i % 2], "row": int(r),
               "col": int(c), "lon": round(lon, 6), "lat": round(lat, 6)}
        missing = []
        for j, f in enumerate(scorer.cat_f):
            rec[f] = int(cat[j, HALF, HALF])
            if rec[f] == MISSING_CODE:
                missing.append(f)
        for j, f in enumerate(scorer.cont_f):
            v = float(cont[j, HALF, HALF]) * FEATURE_SPEC[f].get("scale", 1.0)
            rec[f] = v
            if not np.isfinite(v):
                missing.append(f)
        rd = rec.get("road_dist", float("nan"))
        rec["road_dist_m"] = (float(road_dist_decode(rd)) if np.isfinite(rd)
                              else float("nan"))
        rec["missing_at_centre"] = ",".join(missing)
        rec["prob"] = float(probs[i])
        rows.append(rec)
    return rows


def rematch(scorer, box):
    """inv_matched_pairs.py's draw on the scorer's grid, current rasters:
    box window (pad 0), full 64x64 window inside it, no missing key value."""
    import predict
    from grouse_data import MISSING_CODE
    from models import FEATURE_SPEC
    from rasterio.windows import Window
    ref = scorer.ref
    r0, r1, c0, c1 = predict.bounds_to_window(ref, box, pad=0)
    win = Window(c0, r0, c1 - c0, r1 - r0)
    cat, cont = predict.read_window_stack(scorer.srcs, scorer.cat_f,
                                          scorer.cont_f, win)
    cty = read_counties(ref.crs, fips=[STATE_FIPS[ME], STATE_FIPS[NH]])
    me, nh = side_masks(cty, cat.shape[1:], ref.window_transform(win))
    ci = {f: i for i, f in enumerate(scorer.cat_f)}
    ni = {f: i for i, f in enumerate(scorer.cont_f)}

    def real(f):
        return cont[ni[f]] * FEATURE_SPEC[f].get("scale", 1.0)
    sig = np.stack([cat[ci[f]] for f in MATCH_CAT]).astype(np.int64)
    complete = (sig != MISSING_CODE).all(0) & np.isfinite(cont).all(0)
    H, W = complete.shape
    inner = np.zeros((H, W), bool)
    inner[HALF:H - HALF, HALF:W - HALF] = True
    pairs = match_pairs(sig, real("ch"), real("cc"), real("tcc"),
                        me & inner & complete, nh & inner & complete)
    return [((r0 + a, c0 + b), (r0 + c, c0 + d))
            for (a, b), (c, d) in pairs]


def box_frame(df, label, region, box):
    W, S, E, N = box
    d = df[df.longitude.between(W, E) & df.latitude.between(S, N)]
    d = d[["longitude", "latitude"] + (["split"] if "split" in d else [])]
    d = d.copy()
    d["label"], d["source_file_region"] = label, region
    return d


def region_point_frames(regions, box):
    """In-box positives('all') and negatives('all') per region file, with
    the files' sha256."""
    from grouse_data import GrouseData
    g = GrouseData()
    frames, files = [], {}
    for r in regions:
        rd = g[r]
        for label, kind, fn in ((1, "thinned", rd.positives),
                                (0, "negatives", rd.negatives)):
            frames.append(box_frame(fn("all"), label, r, box))
            try:
                p = rd.path(kind)
                files[str(p)] = sha256(p)
            except Exception as e:          # path template naming differs
                files[f"{r}:{kind}"] = f"not hashed ({e})"
    return frames, files


def point_sides(pts, county_path=None):
    """Side of each record: `within` a TIGER county of ME/NH/VT, first
    match kept; 'none' otherwise."""
    import geopandas as gpd
    from shapely.geometry import Point
    cty = read_counties("EPSG:4326", fips=list(STATE_FIPS.values()),
                        path=county_path)
    g = gpd.GeoDataFrame(index=pts.index, crs="EPSG:4326", geometry=[
        Point(x, y) for x, y in zip(pts.longitude, pts.latitude)])
    j = gpd.sjoin(g, cty[["STATEFP", "geometry"]], how="left",
                  predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    return j["STATEFP"].map(BY_FIPS).fillna("none").values


def sample_map(map_path, pts):
    import rasterio
    from pyproj import Transformer
    with rasterio.open(map_path) as src:
        t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = t.transform(pts.longitude.values, pts.latitude.values)
        v = np.array([s[0] for s in src.sample(list(zip(x, y)))], float)
        if src.nodata is not None and np.isfinite(src.nodata):
            v[v == src.nodata] = np.nan
    return v


def run_item3(map_path, name, pts):
    pts = pts.reset_index(drop=True)
    v = sample_map(map_path, pts)
    side = point_sides(pts)
    split = (pts["split"].fillna("none").astype(str).values
             if "split" in pts else np.full(len(pts), "none"))
    blocks, off = item3_blocks(pts.label.values, v, side, split)
    return ({"point_set": name, "points": int(len(pts)),
             "on_map": int(np.isfinite(v).sum()), "off_map_by_side": off,
             "blocks": blocks},
            pts.assign(point_set=name, side=side, score=v))


def run_item4(region, map_path, scorer):
    """Whole-region map by zone; degraded = scored but at least one input
    missing at the cell centre (current rasters)."""
    import predict
    from grouse_data import MISSING_CODE
    from pyproj import Transformer
    from rasterio.windows import Window
    arr, tr, crs = read_map(map_path)
    ref = scorer.ref
    stride = abs(tr.a / ref.transform.a)
    rows, _ = map_cell_to_source(tr, ref.transform, np.arange(arr.shape[0]),
                                 0)
    _, cols = map_cell_to_source(tr, ref.transform, 0,
                                 np.arange(arr.shape[1]))
    degraded = np.zeros(arr.shape, bool)
    c_lo, c_hi = int(cols.min()), int(cols.max())
    block = max(1, 64 // max(1, int(round(stride))))
    for i in range(0, arr.shape[0], block):
        rr = rows[i:i + block]
        w = Window(c_lo, int(rr.min()), c_hi - c_lo + 1,
                   int(rr.max() - rr.min()) + 1)
        cat, cont = predict.read_window_stack(scorer.srcs, scorer.cat_f,
                                              scorer.cont_f, w)
        miss = (cat == MISSING_CODE).any(0) | ~np.isfinite(cont).all(0)
        degraded[i:i + block] = miss[np.ix_(rr - rr.min(), cols - c_lo)]
    west, north = tr.c, tr.f
    east, south = west + tr.a * arr.shape[1], north + tr.e * arr.shape[0]
    ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    xs, ys = ll.transform([west, east, west, east],
                          [north, north, south, south])
    zone = zone_codes(read_counties(crs, (min(xs), min(ys), max(xs),
                                          max(ys))), arr.shape, tr)
    names = {0: "outside_US"}
    names.update({int(z): BY_FIPS.get(f"{int(z):02d}", f"STATEFP_{int(z):02d}")
                  for z in np.unique(zone) if z})
    return {"region": region, "map": map_path, "shape": list(arr.shape),
            "stride_px": stride,
            "all": zone_summary(arr, np.zeros(arr.shape, int), degraded,
                                {0: "all"})["all"],
            "coverage": zone_summary(arr, (zone > 0).astype(int), degraded,
                                     {0: "outside_US", 1: "inside_US"}),
            "by_state": zone_summary(arr, zone, degraded, names)}


# ==========================================================================
# Rows (PA-0021(f)) and report
# ==========================================================================
def fmt(v, f="{:.4f}"):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return f.format(v)


def row(item, statistic, value, investigate_if, beyond, calibration,
        counts, detail=(), subset=None):
    cls, sub, null = FIELDS[item]
    return {"id": item, "type": "OBS", "statistic": statistic,
            "value": value, "investigate_if": investigate_if,
            "beyond_reference": beyond, "class": cls,
            "subset": subset or sub, "null_population": null,
            "calibration": calibration, "counts": counts,
            "detail": list(detail)}


def build_rows(res, pins):
    ref = pins["reference"]
    cal = cal_source(res["calibration"])
    rows = []
    i1 = res["item1"]
    lo, hi = ref["1a_band"]
    counts1 = (f"ME {i1[ME].get('n')} scored + {i1['nan_cells'][ME]} NaN; "
               f"NH {i1[NH].get('n')} scored + {i1['nan_cells'][NH]} NaN; "
               f"other/none {i1['other_cells']} excluded")
    base = ["baselines (pre-fix / post-fix, § Why now), then this run:",
            "  map                  ME mean  NH mean  P(ME>NH)  ME>=.8  "
            "NH>=.8  gap pp"]
    for model, b in pins["baselines"].items():
        if not isinstance(b, dict) or "after" not in b:
            continue
        for when in ("before", "after"):
            x = b[when]
            base.append(f"  {model + ' ' + when:20s} {x['me_mean']:.4f}   "
                        f"{x['nh_mean']:.4f}   {x['p_me_gt_nh']:.4f}    "
                        f"{x['me_ge08_pct']:6.2f}  {x['nh_ge08_pct']:6.2f}  "
                        f"{x['me_ge08_pct'] - x['nh_ge08_pct']:6.2f}")
    base.append(f"  {'this run':20s} {fmt(i1[ME].get('mean'))}   "
                f"{fmt(i1[NH].get('mean'))}   {fmt(i1['p_me_gt_nh'])}    "
                f"{fmt(i1[ME].get('ge08_pct'), '{:6.2f}')}  "
                f"{fmt(i1[NH].get('ge08_pct'), '{:6.2f}')}  "
                f"{fmt(i1['gap08_pp'], '{:6.2f}')}")
    base.append(f"  ({pins['baselines'].get('calibration_note', '')})")
    for s in (ME, NH):
        st = i1[s]
        base.append(f"  {s}: mean={fmt(st.get('mean'))} "
                    f"median={fmt(st.get('median'))} p10={fmt(st.get('p10'))}"
                    f" p90={fmt(st.get('p90'))} "
                    f">=0.5={fmt(st.get('ge05_pct'), '{:.2f}')}% "
                    f">=0.8={fmt(st.get('ge08_pct'), '{:.2f}')}%")
    rows.append(row("1a", "P(ME pixel > NH pixel), Mann-Whitney U / "
                          "(n_ME n_NH)", fmt(i1["p_me_gt_nh"]),
                    f"outside [{lo}, {hi}]",
                    not lo <= i1["p_me_gt_nh"] <= hi, cal, counts1))
    rows.append(row("1b", "ME >=0.8 share - NH >=0.8 share (pp)",
                    fmt(i1["gap08_pp"], "{:+.2f}"),
                    f"> {ref['1b_max_pp']} pp",
                    not i1["gap08_pp"] <= ref["1b_max_pp"], cal, counts1,
                    base))
    i2 = res["item2"]
    same = res["rematch"]["same_cells"]
    counts2 = (f"{i2['n_pairs']} pairs; finite road_dist "
               f"{i2['n_pairs_finite_road']}, finite prob "
               f"{i2['n_pairs_finite_prob']}; cells with an input missing at "
               f"the centre {i2['cells_missing_input']}")
    rm = [f"re-run of inv_matched_pairs.py's matching on the current NH "
          f"rasters: {res['rematch']['n']} pairs; same cells as the frozen "
          f"pairs: {'yes' if same else 'NO'}"]
    mr = i2["mean_diff_road_m"]
    rows.append(row(
        "2a", "mean ME-NH road_dist (m) over the frozen pairs, NH grid",
        f"{fmt(mr, '{:+.2f}')} (sides rounded to whole metres as recorded: "
        f"{fmt(i2['mean_diff_road_m_recorded'], '{:+.2f}')})",
        f"|.| > {ref['2a_max_abs_m']:.0f} m", mr is None
        or abs(mr) > ref["2a_max_abs_m"], "n/a (raster read)", counts2,
        [f"per pair, as recorded: "
         f"{[fmt(v, '{:.0f}') for v in i2['diff_road_m_recorded']]}"] + rm))
    mp, b = i2["mean_diff_prob"], i2["boot_2b"]
    rows.append(row(
        "2b", "mean ME-NH calibrated probability over the frozen pairs",
        f"{fmt(mp, '{:+.4f}')} (sides rounded to 4 decimals as recorded: "
        f"{fmt(i2['mean_diff_prob_recorded'], '{:+.4f}')})",
        f"> +{ref['2b_max']:.2f}", mp is None or mp > ref["2b_max"], cal,
        counts2,
        [f"per pair, as recorded: "
         f"{[fmt(v, '{:.3f}') for v in i2['diff_prob_recorded']]}",
         f"pair-sampling spread: 95 % interval of the mean over "
         f"{b['n_pairs']} pairs [{fmt(b['lo95'], '{:+.4f}')}, "
         f"{fmt(b['hi95'], '{:+.4f}')}] (n_boot={b['n_boot']}, "
         f"seed={b['seed']}); not a retrain-seed null"]))
    auc_ref = pins["auc_baselines"]
    for i3 in res["item3"]:
        det = []
        for key, bl in i3["blocks"].items():
            if not bl["n"]:
                continue
            side = key.split("/")[0]
            r = ""
            if key.endswith("/all") and side in auc_ref["after"]:
                r = (f"   ref post-fix {auc_ref['after'][side]} (pre-fix "
                     f"{auc_ref['before'][side]})")
            det.append(f"{key:9s} n={bl['n']:4d} pos={bl['pos']:4d} "
                       f"neg={bl['neg']:3d} AUC={fmt(bl.get('auc'))} "
                       f"AP={fmt(bl.get('ap'))} "
                       f"mean_pos={fmt(bl.get('mean_pos'))} "
                       f"mean_neg={fmt(bl.get('mean_neg'))}{r}")
        det.append(f"references: {auc_ref['point_set']}; {auc_ref['map']}")
        a = i3["blocks"]["all/all"]
        rows.append(row(
            "3", "AUC and AP of the item-1 map at in-box records",
            f"all points AUC {fmt(a.get('auc'))}, NH side AUC "
            f"{fmt(i3['blocks'].get('NH/all', {}).get('auc'))}",
            "report", None, cal,
            f"{i3['points']} records, {i3['on_map']} on scored pixels; off "
            f"the map by side {i3['off_map_by_side']}", det,
            subset=f"point set '{i3['point_set']}': {FIELDS['3'][1]}"))
    for i4 in res["item4"]:
        det = [f"map {i4['map']} shape={i4['shape']} stride="
               f"{i4['stride_px']:g} px"]
        zones = ([("all", i4["all"])] + list(i4["coverage"].items())
                 + list(i4["by_state"].items()))
        for z, s in zones:
            det.append(f"{z:12s} cells={s['cells']:9d} NaN="
                       f"{s['nan_pct']:6.2f}% degraded="
                       f"{fmt(s.get('degraded_pct_of_scored'), '{:6.2f}')}% "
                       f"mean={fmt(s.get('mean'))} p01={fmt(s.get('p01'))} "
                       f"p10={fmt(s.get('p10'))} "
                       f"median={fmt(s.get('median'))} "
                       f"p90={fmt(s.get('p90'))} p99={fmt(s.get('p99'))} "
                       f">=0.8={fmt(s.get('ge08_pct'), '{:.2f}')}%")
        rows.append(row("4", f"whole-{i4['region']}-region map summaries",
                        "see detail", "report", None, cal,
                        f"{i4['all']['cells']} cells", det,
                        subset=f"{i4['region']} " + FIELDS["4"][1]))
    rows.append(row("5", "1a/1b/2a/2b beside bf8d31a's before/after "
                         "(§ Why now; the 1b row's detail)", "stated",
                    "stated", None, "n/a", "n/a"))
    return rows


def render(res, rows):
    pv = res["provenance"]
    L = ["CR-0009 § Symptom acceptance - symptom_check.py. Every row is "
         "OBS (BUG-0039); none is pass/fail.",
         f"run {pv['utc']}  git HEAD {pv['git']['head']}"
         + ("  (tracked files modified)" if pv["git"]["dirty_tracked"]
            else "") + f"  device {pv['device']}",
         f"argv: {' '.join(pv['argv'])}",
         f"model {pv['model']}",
         f"calibration {cal_source(res['calibration'])}"]
    for m in res["maps"]:
        sp = m["spot_check"]
        L.append(f"map ({m['role']}) {m['path']} - {m['origin']}; "
                 f"re-scored {sp['n']} cells with --model/--calibration: "
                 f"max|diff| {sp['max_abs_diff']:.2e} <= {sp['tol']:g}")
    L.append("inputs (sha256):")
    L += [f"  {h}  {p}" for p, h in sorted(pv["sha256"].items())]
    for r in rows:
        L += ["", f"{r['id']:3s} {r['type']}  {r['statistic']}",
              f"    value: {r['value']}   investigate if: "
              f"{r['investigate_if']}"
              + ("" if r["beyond_reference"] is None else
                 ("   -> BEYOND REFERENCE: investigate (PA-0016)"
                  if r["beyond_reference"] else "   -> within reference")),
              f"    class: {r['class']}",
              f"    subset: {r['subset']}",
              f"    null population: {r['null_population']}",
              f"    calibration: {r['calibration']}",
              f"    counts: {r['counts']}"]
        L += [f"      {d}" for d in r["detail"]]
    return L


# ==========================================================================
# Driver
# ==========================================================================
def refuse_data_path(path):
    data = os.path.join(HERE, "data") + os.sep
    if os.path.abspath(path).startswith(data) or \
            os.path.realpath(path).startswith(os.path.realpath(data)):
        raise GuardError(f"{path}: this script never writes under data/")


def check(model, calibration, pairs_csv, out, pins, device, map_path=None,
          predict=False, region_maps=(), points=None, point_regions=None,
          argv=()):
    """Every row for one checkpoint. Writes only under `out`."""
    import pandas as pd
    refuse_data_path(out)
    os.makedirs(out, exist_ok=True)
    box, map_region = pins["box"], pins["map_region"]
    cal = load_calibration(calibration, model)
    stem = os.path.splitext(os.path.basename(model))[0]
    hashes = {os.path.abspath(p): sha256(p)
              for p in (model, calibration, pairs_csv, county_zip())}
    res = {"calibration": cal, "maps": []}
    scorers = {}

    def scorer(region):
        if region not in scorers:
            scorers[region] = Scorer(model, region, cal, device)
            for p in scorers[region].raster_paths.values():
                hashes[os.path.abspath(p)] = sha256(p)
        return scorers[region]

    def obtain(region, src, bounds, stride, role):
        if src == "predict":
            path = scorer(region).predict_map(
                bounds, stride, os.path.join(
                    out, f"map_{role}_{region}_{stem}.tif"))
            origin = ("scored in-process by predict.py's functions "
                      f"(stride {stride})")
        else:
            path = os.path.join(out, f"input_map_{role}_"
                                     f"{os.path.basename(src)}")
            shutil.copyfile(src, path)
            origin = f"copied from {os.path.abspath(src)}"
        hashes[os.path.abspath(path)] = sha256(path)
        arr, tr, crs = read_map(path)
        sp = spot_check(scorer(region), arr, tr)
        res["maps"].append({"role": role, "region": region, "path": path,
                            "origin": origin, "sha256": sha256(path),
                            "spot_check": sp})
        return path, arr, tr, crs

    try:
        mpath, arr, tr, crs = obtain(map_region,
                                     "predict" if predict else map_path,
                                     box, BOX_STRIDE, "box")
        res["item1"] = run_item1(arr, tr, crs)

        sc = scorer(PAIRS_GRID)
        frozen = pairs_to_cells(load_frozen_pairs(pairs_csv), sc.ref)
        prow = pair_rows(sc, frozen)
        res["item2"] = item2_from_rows(prow)
        pd.DataFrame(prow).to_csv(os.path.join(out, "pairs_frozen.csv"),
                                  index=False)
        drawn = rematch(sc, box)
        res["rematch"] = {"n": len(drawn),
                          "same_cells": sorted(drawn) == sorted(frozen),
                          "cells": drawn}

        if points:
            hashes[os.path.abspath(points)] = sha256(points)
            name, pts = "captured", union_point_set([pd.read_csv(points)])
        else:
            regs = point_regions or sorted(STATE_FIPS)
            frames, files = region_point_frames(regs, box)
            hashes.update(files)
            name = "region files " + "+".join(regs)
            pts = union_point_set(frames)
        i3, pframe = run_item3(mpath, name, pts)
        res["item3"] = [i3]
        pframe.to_csv(os.path.join(out, "points.csv"), index=False)

        res["item4"] = []
        for region, src in region_maps:
            p4, _, _, _ = obtain(region, src, BOXES[region], REGION_STRIDE,
                                 "region")
            res["item4"].append(run_item4(region, p4, scorer(region)))
    finally:
        for s in scorers.values():
            s.close()

    res["provenance"] = {
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git": git_state(), "device": str(device), "argv": list(argv),
        "model": os.path.abspath(model), "sha256": hashes}
    rows = build_rows(res, pins)
    res["rows"] = rows
    lines = render(res, rows)
    with open(os.path.join(out, "report.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(out, "results.json"), "w") as f:
        json.dump(res, f, indent=1, default=float)
    return res, lines


def reproduce(calibration, pairs_csv, out, pins, device, evidence=None,
              points=None, region_maps=(), argv=()):
    """R: the investigation's numbers, current rasters, maps in-process."""
    rp = pins["reproduction"]
    L = ["symptom_check.py --reproduce (CR-0009 v5 § symptom_check.py, R): "
         "GATE on the instrument, exact at the published precision.",
         "Maps are scored in-process; predict.py's CLI is not called and "
         "nothing is written under data/."]
    ok_all = True

    def cmp(name, measured, ref):
        nonlocal ok_all
        ok = equal_at_precision(measured, ref)
        ok_all &= ok
        L.append(f"   {'PASS' if ok else 'FAIL'} {name:30s} measured "
                 f"{fmt(measured, '{:+.6f}')}  published {ref}")

    def cmp_list(name, measured, ref, dec):
        nonlocal ok_all
        got = [round(float(v), dec) if np.isfinite(v) else None
               for v in measured]
        ok = got == [round(float(v), dec) for v in ref]
        ok_all &= ok
        L.append(f"   {'PASS' if ok else 'FAIL'} {name:30s} measured {got}"
                 f"  published {ref}")

    for model, t in rp["maps"].items():
        res, rep = check(model, calibration, pairs_csv,
                         os.path.join(out, f"R_{os.path.splitext(model)[0]}"),
                         pins, device, predict=True, points=points,
                         point_regions=None if points else [
                             pins["map_region"]],
                         region_maps=region_maps, argv=argv)
        i1, i2 = res["item1"], res["item2"]
        blk = res["item3"][0]["blocks"]
        measured = {"p_me_gt_nh": i1["p_me_gt_nh"],
                    "gap08_pp": i1["gap08_pp"],
                    "me_mean": i1[ME].get("mean"),
                    "nh_mean": i1[NH].get("mean"),
                    "mean_diff_prob_recorded": i2["mean_diff_prob_recorded"],
                    "auc_all": blk["all/all"].get("auc"),
                    "auc_NH": blk.get("NH/all", {}).get("auc")}
        m = res["maps"][0]
        L += ["", f"== {model} sha256 {sha256(model)}",
              f"   map {m['path']} sha256 {m['sha256']} ({m['origin']}); "
              f"spot check max|diff| {m['spot_check']['max_abs_diff']:.2e}",
              f"   calibration {cal_source(res['calibration'])} sha256 "
              f"{res['calibration']['sha256']}",
              f"   item 3 point set: {res['item3'][0]['point_set']}"]
        for k, ref in t.items():
            if k == "diff_prob_recorded_3dp":
                cmp_list("2b per pair (3 dp)", i2["diff_prob_recorded"],
                         ref, 3)
            else:
                cmp(k, measured[k], ref)
        inv_map = rp.get("investigation_maps", {}).get(model)
        if inv_map and os.path.exists(os.path.join(HERE, inv_map)):
            a, _, _ = read_map(os.path.join(HERE, inv_map))
            b, _, _ = read_map(m["path"])
            eq = a.shape == b.shape
            L.append(f"   info: pixel compare with {inv_map} (untracked "
                     f"investigation output): max|diff| "
                     f"{fmt(float(np.nanmax(np.abs(a - b))) if eq else None, '{:.2e}')}"
                     f", NaN pattern equal "
                     f"{eq and bool(np.array_equal(np.isnan(a), np.isnan(b)))}")
        if model == rp["pairs"]["model"]:
            pr = rp["pairs"]
            cmp("2a mean (recorded rounding)",
                i2["mean_diff_road_m_recorded"], pr["mean_diff_road_m"])
            cmp_list("2a per pair (m)", i2["diff_road_m_recorded"],
                     pr["diff_road_m"], 0)
            same = res["rematch"]["same_cells"]
            ok_all &= same
            L.append(f"   {'PASS' if same else 'FAIL'} re-run matching "
                     f"selects the frozen cells")
        L.append("   --- report ---")
        L += ["   " + x for x in rep]
    L += ["", f"R RESULT: {'PASS - reproduced' if ok_all else 'FAIL - not reproduced (stop the CR; PA-0016)'}"]
    text = "\n".join(L) + "\n"
    with open(os.path.join(out, "R_reproduction.txt"), "w") as f:
        f.write(text)
    if evidence:
        with open(evidence, "w") as f:
            f.write(text)
    return ok_all, L


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    ap = argparse.ArgumentParser(
        description="CR-0009 symptom observations (see module docstring)")
    ap.add_argument("--model")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--map", help="predict.py output GeoTIFF of the box "
                                   "(copied into --out and hashed)")
    src.add_argument("--predict", action="store_true",
                     help="score the box in-process into --out")
    src.add_argument("--reproduce", action="store_true",
                     help="R: reproduce the investigation (gap3/bce)")
    ap.add_argument("--calibration", required=True,
                    help="calibration.json path (explicit)")
    ap.add_argument("--pairs", required=True,
                    help="frozen pairs CSV (inv_matched_pairs.csv copy)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--evidence", help="--reproduce: also write R here")
    ap.add_argument("--pins", default=PINS)
    ap.add_argument("--region-map", action="append", default=[],
                    metavar="REGION=TIF|predict",
                    help="item 4 whole-region map; 'predict' scores it "
                         "in-process at stride 8 (~36 min for ME)")
    ap.add_argument("--points", help="captured point-set CSV (longitude, "
                                     "latitude, label, split)")
    a = ap.parse_args(argv)
    if not a.reproduce and not (a.model and (a.map or a.predict)):
        ap.error("--model and one of --map / --predict are required "
                 "(or --reproduce)")
    region_maps = []
    for spec in a.region_map:
        if "=" not in spec:
            ap.error(f"--region-map wants REGION=TIF|predict, got {spec!r}")
        region_maps.append(tuple(spec.split("=", 1)))

    needed = [a.pins, county_zip(), a.calibration, a.pairs]
    needed += ([a.map] if a.map else []) + ([a.points] if a.points else [])
    needed += [p for _, p in region_maps if p != "predict"]
    pins = load_pins(a.pins) if os.path.exists(a.pins) else None
    needed += (list(pins["reproduction"]["maps"]) if a.reproduce and pins
               else [a.model] if a.model else [])
    missing = [p for p in needed if not os.path.exists(p)]
    if missing:
        print(f"missing input(s): {missing}", file=sys.stderr)
        return 2
    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    try:
        for p in [a.out] + ([a.evidence] if a.evidence else []):
            refuse_data_path(p)
        if a.reproduce:
            ok, lines = reproduce(a.calibration, a.pairs, a.out, pins, device,
                                  a.evidence, a.points, region_maps,
                                  ["symptom_check.py"] + argv)
            print("\n".join(lines))
            return 0 if ok else 1
        _, lines = check(a.model, a.calibration, a.pairs, a.out, pins,
                         device, map_path=a.map, predict=a.predict,
                         region_maps=region_maps, points=a.points,
                         argv=["symptom_check.py"] + argv)
    except GuardError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
