"""res_thresh_negprep.py -- Phase A of the negative-side calibration.

Builds, ONCE, the pooled negative candidate pool with the real
generate_negatives.py hygiene + envelope weighting, so that 60 seeds of the
negative draw can be run cheaply afterwards.  Nothing about this phase depends
on the seed except the 30 m thinning and the 300 m buffer, which Phase B
redoes per seed.

Faithful to generate_negatives.process_region except where stated:
  * hygiene: drop coord_uncertainty_m > 1000 (NaN kept); dedupe on
    round(longitude,5), round(latitude,5)  -- done POOLED with ignore_index
    (CR-0007 s5)
  * features: sorted({c for c,_ in ENVELOPE_SCHEME if c not in
    ('evt_phys','evt_group')} | {'sclass','evt'}) == ['evh','evt','sclass'],
    sampled from the candidate's OWN STATE rasters at its own year via
    RegionData.raster_path (post-CR region == state)
  * dropna on those three
  * evt_phys via the EVT crosswalk; is_nonveg via NON_VEG_SCLASS_CODES /
    is_evt_phys_nonveg
  * envelope_id with binners fitted on the candidate's own state's habitat
    evaluated rows (post-CR: state-clipped)
  * weight via build_weight against envelope_metrics_{state}.csv

KNOWN LIMIT (stated, not hidden): envelope_metrics_*.csv on disk are the
PRE-CR metrics (fitted on box-clipped evaluated sets).  Post-CR they change.
So the weights used here are the closest available approximation to the
post-CR weights, not the post-CR weights themselves.

READ-ONLY on the project.  Writes one CSV into the scratchpad.
"""
import os, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
from pyproj import Transformer
import generate_negatives as GN
from analyze_grouse import (ENVELOPE_SCHEME, build_envelope_id,
                            fit_scheme_binners, sample_raster,
                            NON_VEG_SCLASS_CODES, is_evt_phys_nonveg)
from grouse_data import GrouseData

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
REG = ["ME", "NH", "VT"]
OUT = f"{SCRATCH}/res_thresh_cand_pool.csv"


def main():
    t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    frames = []
    for r in REG:
        c = pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
        frames.append(c)
        print(f"  {r}: {len(c):,} raw candidates")
    cand = pd.concat(frames, ignore_index=True)
    n0 = len(cand)
    cand = cand[~(cand["coord_uncertainty_m"] > GN.MAX_COORD_UNCERTAINTY_M).fillna(False)].copy()
    print(f"  pooled {n0:,} -> {len(cand):,} after uncertainty hygiene")
    key = cand[["longitude", "latitude"]].round(5)
    cand = cand.loc[~key.duplicated()].copy().reset_index(drop=True)
    print(f"  -> {len(cand):,} after pooled 5 dp dedupe")
    cand["x_5070"], cand["y_5070"] = t.transform(cand["longitude"].values,
                                                 cand["latitude"].values)
    print(f"  state composition: {cand['state'].value_counts().to_dict()}")

    data = GrouseData()
    xwalk = data.evt_crosswalk()
    feats = sorted({c for c, _ in ENVELOPE_SCHEME
                    if c not in ("evt_phys", "evt_group")} | {"sclass", "evt"})
    print(f"  features to extract: {feats}")
    for f in feats:
        cand[f] = np.nan
    t0 = time.time()
    for r in REG:
        rd = data[r]
        m_state = (cand["state"] == r).values
        for f in feats:
            for yr in sorted(cand.loc[m_state, "year"].dropna().unique()):
                m = m_state & (cand["year"] == yr).values
                if not m.any():
                    continue
                tif = rd.raster_path(f, int(yr))
                cand.loc[m, f] = sample_raster(tif, cand.loc[m, "longitude"].values,
                                               cand.loc[m, "latitude"].values)
        print(f"   {r} extracted ({time.time()-t0:.0f}s)")
    n1 = len(cand)
    cand = cand.dropna(subset=feats).copy().reset_index(drop=True)
    print(f"  extraction dropna: {n1:,} -> {len(cand):,}")

    if xwalk is not None:
        cand["evt_phys"] = cand["evt"].astype(int).map(xwalk["phys"]).fillna("Unmapped")
    else:
        cand["evt_phys"] = "Unmapped"
    cand["is_nonveg"] = (cand["sclass"].isin(NON_VEG_SCLASS_CODES)
                         | is_evt_phys_nonveg(cand["evt_phys"]))

    # per-state binners on that state's OWN-STATE habitat evaluated rows
    ev = {}
    for r in REG:
        d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
        d = d[d["state"] == r]                       # post-CR partition clip
        ev[r] = d[~d["nonveg_landcover"].astype(bool)]
    cand["envelope_id"] = ""
    for r in REG:
        m = (cand["state"] == r).values
        binners = fit_scheme_binners(ev[r], ENVELOPE_SCHEME)
        cand.loc[m, "envelope_id"] = build_envelope_id(
            cand.loc[m], ENVELOPE_SCHEME, binners=binners).values

    cand["weight"] = 1.0
    cand["weight_basis"] = ""
    for r in REG:
        met = pd.read_csv(f"data/pipeline/envelope_metrics_{r}.csv")
        mm = {row["Envelope"]: row for _, row in met.iterrows()}
        m = (cand["state"] == r).values
        ws, cls = [], []
        for e, nv in zip(cand.loc[m, "envelope_id"], cand.loc[m, "is_nonveg"]):
            w, c = GN.build_weight(e, mm, nv)
            ws.append(w); cls.append(c)
        cand.loc[m, "weight"] = ws
        cand.loc[m, "weight_basis"] = cls
    print(f"  weight basis: {cand['weight_basis'].value_counts().to_dict()}")
    keep = ["longitude", "latitude", "state", "year", "x_5070", "y_5070",
            "is_nonveg", "envelope_id", "weight", "weight_basis"]
    cand[keep].to_csv(OUT, index=False)
    print(f"  wrote {OUT}  ({len(cand):,} rows)")


if __name__ == "__main__":
    main()
