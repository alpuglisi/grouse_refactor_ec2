"""Baseline for CR-0008's acceptance table: per region, per feature, how
many pixels are fabricated OUTSIDE the US land footprint, and how many
legitimate values sit INSIDE it (which must not change). Reference is
NLCD's valid footprint, not evt. Read-only."""
import numpy as np, rasterio
from grouse_data import GrouseData
STEP=8
FEATS=["tsd","balive","tpa_live","qmd","carbon_dwn","tcc","road_dist","nlcd","evt"]
for region in ("ME","NH","VT"):
    rd=GrouseData()[region]
    with rasterio.open(rd.latest_raster_path("nlcd")) as s:
        nl=s.read(1)[::STEP,::STEP]; nd=s.nodata
    outside = nl==nd                      # outside US land footprint
    with rasterio.open(rd.latest_raster_path("evt")) as s:
        evt=s.read(1)[::STEP,::STEP]; evtnd=s.nodata
    print(f"\n=== {region}: NLCD-invalid (outside US) {outside.mean():.4f} | "
          f"evt-nodata {(evt==evtnd).mean():.4f} | "
          f"evt-valid AND outside-US {((evt!=evtnd)&outside).mean():.4f} ===")
    print(f"{'feature':11s} {'nodata OUT':>11s} {'FABRICATED out':>15s} {'zeros IN (keep)':>16s}")
    for f in FEATS:
        if f in ("nlcd","evt"): continue
        try: p=rd.latest_raster_path(f)
        except Exception: continue
        with rasterio.open(p) as s:
            a=s.read(1)[::STEP,::STEP]; fnd=s.nodata
        out_nd=(a[outside]==fnd).mean() if outside.any() else float('nan')
        fab=int((~(a[outside]==fnd)).sum()) if outside.any() else 0
        zeros_in=int((a[~outside]==0).sum())
        flag="  <-- must become nodata" if out_nd<0.5 else ""
        print(f"{f:11s} {out_nd:11.4f} {fab:15,d} {zeros_in:16,d}{flag}")
