"""
diagnose_wetland.py

Tests the "wetland lean" hypothesis with numbers instead of eyeballs.

HYPOTHESIS (from code inspection): every negative-sample target species
(get_negatives.py TARGET_SPECIES) is a mature-UPLAND-forest bird -
Ovenbird, BTB Warbler, Hermit Thrush, Blue-headed Vireo, Brown Creeper,
Pileated Woodpecker. No wetland-guild species at all. So wetlands are
nearly absent from the negative class, any grouse positives in lowland
alder covers make wetland signatures purely-positive evidence, and the
new Annual-NLCD layer hands the model one coarse 'woody wetland' code
(90) to shortcut on - a signal the fragmented EVT classes never exposed
this cleanly. Shrub wetlands also structurally mimic regen (low height,
dense cover), and there is no hydrology layer to separate them.

WHAT IT MEASURES
  A. COMPOSITION: center-pixel NLCD class distribution of train
     positives, curated GBIF negatives, and (optionally) uniform
     background points -> the per-class empirical positive fraction.
     If wetland classes (90/95) are overwhelmingly positive-labeled,
     the shortcut exists in the DATA.
  B. MODEL SCORES BY CLASS: per-point val TTA scores grouped by center
     NLCD class. If wetland classes rank at/near the top, the model
     learned the shortcut.
  C. NLCD ABLATION: the same val scores with the nlcd channel replaced
     by padding (0). If wetland-class scores drop sharply while overall
     TTA AUC barely moves, the wetland lean is riding on the nlcd
     shortcut specifically (and dropping/regularizing that channel is a
     cheap intervention). If scores stay high without nlcd, the lean
     comes through the structural features (EVH/EVC/CC/TCC mimicry) and
     needs negative-data surgery instead.

USAGE
    python diagnose_wetland.py --model data/models/grouse_single_best.pth
    python diagnose_wetland.py --regions ME --max-points 800
"""
import os
import sys
import argparse

import numpy as np
import torch
import rasterio
from torch.utils.data import DataLoader

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from grouse_data import GrouseData
from models import FEATURE_SPEC
from dataset import GrousePatchDataset

NLCD_NAMES = {
    11: "Open Water", 12: "Snow/Ice",
    21: "Developed Open", 22: "Developed Low", 23: "Developed Med",
    24: "Developed High", 31: "Barren",
    41: "Deciduous Forest", 42: "Evergreen Forest", 43: "Mixed Forest",
    52: "Shrub/Scrub", 71: "Grassland", 81: "Pasture/Hay",
    82: "Cropland", 90: "WOODY WETLANDS", 95: "EMERGENT WETLANDS",
}
WETLAND = (90, 95)


def center_codes(rd, df, feature="nlcd"):
    """Center-pixel feature code for every point, year-matched."""
    from pyproj import Transformer
    codes = np.full(len(df), -1, dtype=int)
    if "year" not in df.columns:
        return codes
    for year in sorted(df["year"].dropna().astype(int).unique()):
        mask = (df["year"].astype(int) == year).values
        try:
            path = rd.raster_path(feature, int(year))
        except Exception:
            continue
        with rasterio.open(path) as src:
            t = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            xs, ys = t.transform(df.loc[mask, "longitude"].values,
                                 df.loc[mask, "latitude"].values)
            vals = np.array([v[0] for v in src.sample(zip(xs, ys))],
                            dtype=float)
        vals[~np.isfinite(vals)] = -1
        codes[mask] = vals.astype(int)
    return codes


def area_composition(rd, feature="nlcd", stride=10):
    """Decimated read of the raster's own class distribution across the
    WHOLE region - the landscape's area share of each class, independent
    of any point set. stride=10 -> every 10th pixel (100x fewer reads;
    a composition estimate doesn't need full resolution)."""
    path = rd.latest_raster_path(feature)
    with rasterio.open(path) as src:
        out_h = max(1, src.height // stride)
        out_w = max(1, src.width // stride)
        arr = src.read(1, out_shape=(out_h, out_w),
                       resampling=rasterio.enums.Resampling.nearest)
    vals, counts = np.unique(arr, return_counts=True)
    return {int(v): int(c) for v, c in zip(vals, counts) if v > 0}


def composition_table(name, codes):
    total = (codes > 0).sum()
    print(f"\n   {name} (n={total:,}):")
    rows = []
    for c in sorted(set(codes[codes > 0])):
        n = int((codes == c).sum())
        rows.append((n, c))
    for n, c in sorted(rows, reverse=True):
        label = NLCD_NAMES.get(c, f"class {c}")
        flag = "  <-- wetland" if c in WETLAND else ""
        print(f"      {label:20s} {n:6,}  ({100 * n / max(total, 1):5.1f}%)"
              f"{flag}")
    wet = int(np.isin(codes, WETLAND).sum())
    print(f"      TOTAL WETLAND       {wet:6,}  "
          f"({100 * wet / max(total, 1):5.1f}%)")
    return {c: int((codes == c).sum()) for c in set(codes[codes > 0])}


@torch.no_grad()
def score_points(model, ds, device, nlcd_idx=None, batch_size=256,
                 workers=4):
    """Per-POINT mean sigmoid over the 4 stored rotations. nlcd_idx set
    -> that categorical channel is replaced by padding (ablation)."""
    loader = DataLoader(ds, batch_size=batch_size, num_workers=workers)
    outs = []
    for cat_x, cont_x, _y, _w in loader:
        cat_x = cat_x.to(device)
        cont_x = cont_x.to(device)
        if nlcd_idx is not None:
            cat_x = cat_x.clone()
            cat_x[:, nlcd_idx] = 0
        outs.append(torch.sigmoid(
            model.logits(cat_x, cont_x).float()).squeeze(1).cpu())
    s = torch.cat(outs).numpy()
    return s.reshape(-1, 4).mean(axis=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="data/models/grouse_single_best.pth")
    parser.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"])
    parser.add_argument("--max-points", type=int, default=None,
                        help="Cap val points per region/class for a "
                             "quick pass.")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = GrouseData()

    # ---- A. composition of the TRAINING classes ----------------------
    print("=" * 70)
    print("A. CENTER NLCD CLASS COMPOSITION (training data)")
    print("=" * 70)
    pos_by_class, neg_by_class = {}, {}
    for region in args.regions:
        rd = data[region]
        print(f"\n[{region}]")
        p = composition_table("train POSITIVES",
                              center_codes(rd, rd.positives("train")))
        n = composition_table("train NEGATIVES (GBIF)",
                              center_codes(rd, rd.negatives("train")))
        for c, v in p.items():
            pos_by_class[c] = pos_by_class.get(c, 0) + v
        for c, v in n.items():
            neg_by_class[c] = neg_by_class.get(c, 0) + v

    print("\n   PER-CLASS EMPIRICAL POSITIVE FRACTION (all regions):")
    print("   (near 1.0 = the class exists almost only as positives -")
    print("    a label shortcut the model WILL find)")
    for c in sorted(set(pos_by_class) | set(neg_by_class)):
        p, n = pos_by_class.get(c, 0), neg_by_class.get(c, 0)
        if p + n < 20:
            continue
        frac = p / (p + n)
        flag = "  <-- wetland" if c in WETLAND else ""
        print(f"      {NLCD_NAMES.get(c, f'class {c}'):20s} "
              f"pos {p:5,} / neg {n:5,}  -> {frac:.2f}{flag}")

    # ---- B + C. model scores by class, with and without nlcd ---------
    from predict import load_model
    features_on_disk = [f for f in data[args.regions[0]].available_features()
                        if f in FEATURE_SPEC]
    model, cat_f, cont_f, features = load_model(
        args.model, features_on_disk, device)
    if "nlcd" not in cat_f:
        print("\nModel was trained without nlcd - parts B/C skipped "
              "(composition above still stands).")
        return
    nlcd_idx = cat_f.index("nlcd")

    print("\n" + "=" * 70)
    print("B/C. VAL SCORES BY CENTER NLCD CLASS - intact vs nlcd-ablated")
    print("=" * 70)
    all_codes, all_s, all_s_abl, all_y = [], [], [], []
    for region in args.regions:
        rd = data[region]
        for split_name, getter, label in (("val pos", rd.positives, 1.0),
                                          ("val neg", rd.negatives, 0.0)):
            df = getter("val")
            if args.max_points:
                df = df.head(args.max_points)
            ds = GrousePatchDataset(df, rd, cat_f, cont_f, img_size=64,
                                    expand_rotations=True, label=label,
                                    cache_dir="data/cache")
            s = score_points(model, ds, device, None,
                             workers=args.workers)
            s_abl = score_points(model, ds, device, nlcd_idx,
                                 workers=args.workers)
            codes = center_codes(rd, df)
            all_codes.append(codes)
            all_s.append(s)
            all_s_abl.append(s_abl)
            all_y.append(np.full(len(df), label))
    codes = np.concatenate(all_codes)
    s = np.concatenate(all_s)
    s_abl = np.concatenate(all_s_abl)
    y = np.concatenate(all_y)

    print(f"\n   {'class':20s} {'n':>6s} {'mean score':>11s} "
          f"{'ablated':>8s} {'drop':>7s}")
    order = sorted(set(codes[codes > 0]),
                   key=lambda c: -s[codes == c].mean())
    for c in order:
        m = codes == c
        if m.sum() < 10:
            continue
        flag = "  <-- wetland" if c in WETLAND else ""
        print(f"   {NLCD_NAMES.get(c, f'class {c}'):20s} {m.sum():6,} "
              f"{s[m].mean():11.3f} {s_abl[m].mean():8.3f} "
              f"{s[m].mean() - s_abl[m].mean():+7.3f}{flag}")

    from model_handler import roc_auc
    print(f"\n   Overall per-point AUC: intact {roc_auc(s, y):.4f} | "
          f"nlcd-ablated {roc_auc(s_abl, y):.4f}")
    print("\nREADING: wetland rows at the top of the score table with a "
          "large positive 'drop' = the lean rides on the nlcd shortcut. "
          "High wetland scores that SURVIVE ablation = structural "
          "mimicry through EVH/EVC/CC/TCC - fix the negatives, not the "
          "feature. If neither shows a wetland-specific signature, the "
          "per-point model may be fine and part D below tests whether "
          "the perceived map-level lean is a spatial-EXTENT effect "
          "instead.")

    # ---- D. landscape area share x mean score -------------------------
    print("\n" + "=" * 70)
    print("D. LANDSCAPE AREA SHARE x MEAN SCORE")
    print("=" * 70)
    print("   A class can dominate a RENDERED MAP's lit area without "
          "topping the per-point score ranking above, if it simply "
          "covers more ground (large contiguous wetland complexes vs "
          "small scattered clearcuts). This estimates each class's "
          "share of the map's total 'lit area' as (landscape area "
          "share) x (mean model score) - the map-level analog of part B.")
    area_counts = {}
    for region in args.regions:
        for c, n in area_composition(data[region]).items():
            area_counts[c] = area_counts.get(c, 0) + n
    total_area = sum(area_counts.values()) or 1

    weighted = []
    for c, n in area_counts.items():
        m = codes == c
        if m.sum() < 10:
            continue
        weighted.append((c, n / total_area, float(s[m].mean())))
    norm = sum(a * sc for _, a, sc in weighted) or 1.0
    print(f"\n   {'class':20s} {'area share':>11s} {'mean score':>11s} "
          f"{'lit-area share':>15s}")
    for c, a, sc in sorted(weighted, key=lambda r: -(r[1] * r[2])):
        flag = "  <-- wetland" if c in WETLAND else ""
        print(f"   {NLCD_NAMES.get(c, f'class {c}'):20s} {100 * a:10.1f}% "
              f"{sc:11.3f} {100 * a * sc / norm:14.1f}%{flag}")
    print("\nREADING: if a wetland class ranks much higher HERE than in "
          "part B's per-point score ranking, the 'lean' is a landscape-"
          "area effect, not a per-point defect - the model is scoring "
          "correctly but wetlands simply cover more ground, so an "
          "absolute-probability map shows them prominently. Remedy is "
          "at the map layer, not the model: predict.py --style quantile "
          "(ranks within the mapped area, immune to raw area) or "
          "--prior (re-anchors the displayed threshold), not retraining.")


if __name__ == "__main__":
    main()
