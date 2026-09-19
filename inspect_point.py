"""
inspect_point.py

A direct fact check, not another aggregate statistic: given one lon/lat
you know the ground truth for (e.g. a point on Route 16's pavement),
this reads the RAW feature values the model actually sees at that exact
pixel - NLCD, EVT, canopy cover, everything - and runs the model on
that window, so you can compare against reality directly instead of
inferring it from a correlation.

What this catches that nothing else in this project's diagnostics does:
diagnose_road_bias.py/diagnose_water_bias.py test the TRAINING data's
point distribution; predict.py --tensorboard's Class/Correlation/Edge
breakdowns all test relationships WITHIN the model's own internal grid,
comparing its output against its own input consistently. None of them
verify the input data is actually CORRECT at any given location - a
raster registration offset, a stale/wrong-year raster, or a genuine
land-cover misclassification would be invisible to all of them (every
diagnostic would still look internally self-consistent even if the
whole grid were shifted or a specific area's data were simply wrong).
This is the one check that goes against known ground truth instead.

Also reports the raw pixel's round-tripped lon/lat (reprojected back
from the row/col actually read) - if that doesn't match where you
clicked, there's a registration bug independent of anything about the
model itself.

Usage:
    python inspect_point.py --region NH --lon -71.0505 --lat 44.83
    python inspect_point.py --region NH --lon -71.0505 --lat 44.83 \
        --model data/models/grouse_single_best.pth
"""
import argparse

import torch
from pyproj import Transformer

from grouse_data import GrouseData, NLCD_NAMES
from predict import (load_model, open_aligned_sources, read_window_stack,
                     IMG_SIZE)
from models import (FEATURE_SPEC, split_features, road_dist_decode,
                    d4_tta_logits)
from rasterio.windows import Window


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--model", default="data/models/grouse_single_best.pth")
    ap.add_argument("--pool", default="attn")
    ap.add_argument("--center-skip", action=argparse.BooleanOptionalAction,
                    default=True)
    ap.add_argument("--flip-tta", action=argparse.BooleanOptionalAction,
                    default=True)
    ap.add_argument("--no-model", action="store_true",
                    help="Report raw feature values only, skipping the "
                         "model entirely - for verifying a newly "
                         "generated raster before any checkpoint exists "
                         "that was trained with it.")
    ap.add_argument("--temperature", type=float, default=1.0,
                    help="Manual override; default 1.0 (raw, uncalibrated "
                         "probability) - this tool is about the INPUT "
                         "data and raw model response, not the deployment "
                         "calibration.")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = GrouseData()
    rd = data[args.region]
    # Raw values are reported for everything ON DISK, deliberately NOT
    # for the checkpoint's feature list: a newly generated raster (e.g.
    # road_dist) has to be verifiable BEFORE any model has been trained
    # on it, which is exactly when no checkpoint knows about it yet.
    # The model, when loaded, still runs on its own feature list - the
    # two are read separately below.
    disk_features = [f for f in rd.available_features() if f in FEATURE_SPEC]
    disk_cat, disk_cont = split_features(disk_features)

    model = cat_f = cont_f = None
    if not args.no_model:
        model, cat_f, cont_f, _, _ = load_model(
            args.model, disk_features, device, cli_pool=args.pool,
            cli_center_skip=args.center_skip)
        missing = [f for f in disk_features
                   if f not in (list(cat_f) + list(cont_f))]
        if missing:
            print(f"   [note] on disk but NOT in this checkpoint: "
                 f"{missing} - reported below, but the score comes from "
                 f"a model that never saw them. Retrain to include them.")

    srcs, ref = open_aligned_sources(rd, disk_cat, disk_cont)
    try:
        t = Transformer.from_crs("EPSG:4326", ref.crs, always_xy=True)
        x, y = t.transform(args.lon, args.lat)
        row, col = ref.index(x, y)
        # Round-trip the pixel CENTER back to lon/lat - if this doesn't
        # match --lon/--lat closely, something about the raster's own
        # georeferencing (or the CRS transform above) is off, independent
        # of the model entirely.
        cx, cy = ref.xy(row, col)
        back = Transformer.from_crs(ref.crs, "EPSG:4326", always_xy=True)
        rt_lon, rt_lat = back.transform(cx, cy)
        print(f"Requested:      lon={args.lon:.6f}, lat={args.lat:.6f}")
        print(f"Resolved pixel: row={row}, col={col} "
             f"(round-tripped lon={rt_lon:.6f}, lat={rt_lat:.6f}, "
             f"offset {abs(rt_lon - args.lon) * 111000:.0f}m E-W / "
             f"{abs(rt_lat - args.lat) * 111000:.0f}m N-S from requested "
             f"- should be well under one pixel's width)")

        window = Window(col - IMG_SIZE // 2, row - IMG_SIZE // 2,
                        IMG_SIZE, IMG_SIZE)
        cat, cont = read_window_stack(srcs, disk_cat, disk_cont, window)

        cy_px, cx_px = IMG_SIZE // 2, IMG_SIZE // 2
        print(f"\nRaw feature values AT THE REQUESTED POINT (center pixel "
             f"of the {IMG_SIZE}x{IMG_SIZE} window the model actually "
             f"scores):")
        for i, f in enumerate(disk_cat):
            code = int(cat[i, cy_px, cx_px])
            label = f" ({NLCD_NAMES[code]})" if f == "nlcd" and code in NLCD_NAMES else ""
            frac_same = float((cat[i] == code).mean())
            print(f"   {f:8s} = {code}{label}  "
                 f"[{frac_same * 100:.0f}% of the surrounding window "
                 f"shares this code]")
        for i, f in enumerate(disk_cont):
            val = float(cont[i, cy_px, cx_px])
            window_mean = float(cont[i].mean())
            extra = ""
            if f == "road_dist":
                # Stored log-encoded (models.road_dist_encode), so the
                # model-input number is meaningless to read directly.
                scale = float(FEATURE_SPEC[f].get("scale", 1.0))
                extra = (f"  -> {road_dist_decode(val * scale):,.0f} m "
                        f"to nearest paved road")
            print(f"   {f:8s} = {val:.3f}  "
                 f"(window mean {window_mean:.3f}, model-input scale)"
                 f"{extra}")

        if model is None:
            print("\n--no-model: raw feature values only, no score.")
            return

        # Select the CHECKPOINT's features, in ITS channel order, out of
        # everything read from disk - the two lists legitimately differ
        # whenever a raster has been generated but not yet trained on.
        cat_idx = [disk_cat.index(f) for f in cat_f]
        cont_idx = [disk_cont.index(f) for f in cont_f]
        t_cat = torch.from_numpy(cat[cat_idx][None]).to(device)
        t_cont = torch.from_numpy(cont[cont_idx][None]).to(device)
        model.eval()
        with torch.no_grad():
            logit = d4_tta_logits(model, t_cat, t_cont,
                                  flip_tta=args.flip_tta)
            prob = torch.sigmoid(logit / args.temperature).item()
        print(f"\nModel score at this exact point (raw, uncalibrated, "
             f"T={args.temperature:g}): {prob:.4f}")
        print("\nCompare the feature values above against what you "
             "actually know is at this location. If nlcd/evt read as "
             "forest/wetland here but this is pavement, that's a "
             "data/registration bug, not a modeling question.")
    finally:
        for s in srcs.values():
            s.close()


if __name__ == "__main__":
    main()
