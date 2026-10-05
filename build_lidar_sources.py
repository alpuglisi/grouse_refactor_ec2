"""
build_lidar_sources.py - CR-0036: build the PINNED lidar source table and
footprint layer that generate_lidar_structure.py reads.

Outputs (committed, then independently reviewed before the pilot -
CR-0036 deliverable 2, A36-2-10):
    docs/quality/lidar/lidar_sources.csv      one row per (region, work unit)
    docs/quality/lidar/lidar_footprints.geojson   WESM footprints, EPSG:4326
    docs/quality/lidar/lidar_sources.sha256.txt   digests of every input
    docs/quality/lidar/ept_match.csv          EPT-match evidence per unit

Inputs (all digested):
    docs/quality/evidence/CR-0036/WESM.csv    pinned WESM attribute table
    WESM.gpkg                                 footprints, read remotely with a
                                              bounding-box filter (/vsicurl)
    resources.geojson                         the hobuinc/usgs-lidar EPT index
    each region's template (latest EVT clip)  CRS and extent

Rules (CR-0036 section "Sources" and section 1):
  * Units: every WESM work unit whose footprint intersects a region's
    template extent.
  * Reader: "ept" when ONE EPT resource covers >= EPT_MIN_OVERLAP of the
    unit's footprint AND its name carries one of the unit's collection
    years; otherwise "las" (rockyweb LAZ via the unit's .vpc). The match
    evidence is written to ept_match.csv for review.
  * Units/CRS: EPT rows are EPSG:3857, xy 1, z 1 (EPT Z is metres,
    A36-2-9). LAS rows take CRS and units from the FIRST tile's header
    (downloaded once), falling back to WESM horiz_crs/vert_crs only when
    the header lacks them (flagged in the CSV).
  * Pipeline: the PROJ pipeline pyproj picks from the source CRS to the
    region's template CRS on THIS host, written out as a string so the
    generator uses exactly it (Transformer.from_pipeline, A36-14).
  * leaf_risk: 1 if any day of the collection window falls in
    15 May - 15 Oct.

Run on the EC2 host in the conda env (envs/lidar.yml):
    python build_lidar_sources.py --regions NH            # pilot
    python build_lidar_sources.py --regions ME NH VT      # CR-0037
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

WESM_CSV = os.path.join(_here, "docs", "quality", "evidence", "CR-0036",
                        "WESM.csv")
WESM_GPKG = ("/vsicurl/https://prd-tnm.s3.amazonaws.com/StagedProducts/"
             "Elevation/metadata/WESM.gpkg")
EPT_INDEX = ("https://raw.githubusercontent.com/hobuinc/usgs-lidar/master/"
             "boundaries/resources.geojson")
OUT_DIR = os.path.join(_here, "docs", "quality", "lidar")
EPT_MIN_OVERLAP = 0.90
LEAF_ON = ((5, 15), (10, 15))
COLUMNS = ("region", "work_unit", "reader", "location", "vpc", "horiz_epsg",
           "xy_to_m", "z_to_m", "units_from", "collect_start", "collect_end",
           "ql", "leaf_risk", "pipeline")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def template_info(region):
    import rasterio
    from rasterio.warp import transform_bounds
    from grouse_data import GrouseData
    rd = GrouseData()[region]
    path = rd.latest_raster_path("evt")
    with rasterio.open(path) as t:
        b4326 = transform_bounds(t.crs, "EPSG:4326", *t.bounds, densify_pts=21)
        return t.crs, b4326, path


def wesm_rows():
    with open(WESM_CSV, newline="") as f:
        return {r["workunit"]: r for r in csv.DictReader(f)}


def footprints(bbox, tmpdir):
    """WESM footprints intersecting bbox (EPSG:4326) via ogr2ogr."""
    out = os.path.join(tmpdir, "wesm_bbox.geojson")
    layers = subprocess.run(["ogrinfo", "-ro", "-q", WESM_GPKG],
                            capture_output=True, text=True, check=True).stdout
    layer = re.findall(r"^\d+: (\S+)", layers, re.M)[0]
    subprocess.run(["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326",
                    "-spat", *map(str, bbox), "-spat_srs", "EPSG:4326",
                    "-select", "workunit", out, WESM_GPKG, layer], check=True)
    with open(out) as f:
        return json.load(f), layer


def leaf_risk(start, end):
    d0 = dt.datetime.strptime(start, "%Y/%m/%d").date()
    d1 = dt.datetime.strptime(end, "%Y/%m/%d").date()
    for y in range(d0.year, d1.year + 1):
        a = dt.date(y, *LEAF_ON[0])
        b = dt.date(y, *LEAF_ON[1])
        if d0 <= b and d1 >= a:
            return 1
    return 0


def ept_match(unit_geom, years, ept_features):
    """Best EPT resource for a unit footprint: (name, url, overlap) or None."""
    from shapely.geometry import shape
    best = None
    area = unit_geom.area
    for f in ept_features:
        name = f["properties"]["name"]
        if not any(str(y) in name for y in years):
            continue
        g = shape(f["geometry"])
        if not g.intersects(unit_geom):
            continue
        ov = g.intersection(unit_geom).area / area if area else 0.0
        if best is None or ov > best[2]:
            best = (name, f["properties"]["url"], ov)
    return best


def rockyweb_vpc(lpc_link, work_unit):
    """The .vpc file name in a rockyweb project folder (prefers one naming
    the work unit)."""
    html = urllib.request.urlopen(lpc_link.rstrip("/") + "/").read().decode()
    vpcs = sorted(set(re.findall(r'href="([^"]+\.vpc)"', html)))
    if not vpcs:
        return ""
    named = [v for v in vpcs if work_unit.lower() in v.lower()]
    return os.path.basename((named or vpcs)[0])


def las_header(location, vpc, tmpdir):
    """CRS/units from the first LAZ tile's header (PDAL)."""
    import pdal
    from pyproj import CRS
    with urllib.request.urlopen(location.rstrip("/") + "/" + vpc) as r:
        v = json.load(r)
    href = next(iter(v["features"][0]["assets"].values()))["href"]
    url = href if href.startswith("http") else \
        location.rstrip("/") + "/" + href.lstrip("./")
    dest = os.path.join(tmpdir, os.path.basename(url))
    if not os.path.exists(dest):
        urllib.request.urlretrieve(url, dest)
    p = pdal.Pipeline(json.dumps([{"type": "readers.las", "filename": dest,
                                   "count": 1}]))
    p.execute()
    md = p.metadata.get("metadata", p.metadata)
    rd = md["readers.las"]
    rd = rd[0] if isinstance(rd, list) else rd
    wkt = (rd.get("srs") or {}).get("wkt") or rd.get("comp_spatialreference")
    if not wkt:
        return None
    crs = CRS.from_wkt(wkt)
    horiz = crs.sub_crs_list[0] if crs.is_compound else crs
    vert = crs.sub_crs_list[1] if crs.is_compound and \
        len(crs.sub_crs_list) > 1 else None
    return dict(horiz=horiz,
                xy_to_m=horiz.axis_info[0].unit_conversion_factor,
                z_to_m=(vert.axis_info[0].unit_conversion_factor
                        if vert is not None else None))


def wesm_units(row):
    """Fallback: CRS and units from WESM horiz_crs / vert_crs EPSG codes."""
    from pyproj import CRS
    h = CRS.from_epsg(int(row["horiz_crs"]))
    try:
        z = CRS.from_epsg(int(row["vert_crs"])).axis_info[0].unit_conversion_factor
    except Exception:
        z = None
    return dict(horiz=h, xy_to_m=h.axis_info[0].unit_conversion_factor,
                z_to_m=z)


def pipeline_string(src_crs, dst_crs):
    from pyproj import Transformer
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True).definition


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--regions", nargs="+", required=True)
    args = ap.parse_args()
    from pyproj import CRS
    from shapely.geometry import shape
    os.makedirs(OUT_DIR, exist_ok=True)
    wesm = wesm_rows()
    ept_raw = urllib.request.urlopen(EPT_INDEX).read()
    ept = json.loads(ept_raw)["features"]
    digests = {"WESM.csv": sha256_file(WESM_CSV),
               "resources.geojson": sha256_bytes(ept_raw)}
    rows, matches, foot_out = [], [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for region in args.regions:
            tcrs, bbox, tpath = template_info(region)
            fc, layer = footprints(bbox, tmp)
            digests[f"WESM.gpkg[{layer}] {region} bbox features"] = \
                sha256_bytes(json.dumps(fc, sort_keys=True).encode())
            by_unit = {}
            for feat in fc["features"]:
                by_unit.setdefault(feat["properties"]["workunit"], []).append(feat)
            for wu, feats in sorted(by_unit.items()):
                w = wesm.get(wu)
                if w is None:
                    print(f"   [warn] {wu}: in WESM.gpkg but not WESM.csv - skipped")
                    continue
                geom = shape(feats[0]["geometry"])
                for f in feats[1:]:
                    geom = geom.union(shape(f["geometry"]))
                years = sorted({w["collect_start"][:4], w["collect_end"][:4]})
                m = ept_match(geom, years, ept)
                matches.append(dict(region=region, work_unit=wu,
                                    ept_name=m[0] if m else "",
                                    overlap=f"{m[2]:.3f}" if m else "",
                                    chosen="ept" if m and m[2] >= EPT_MIN_OVERLAP
                                    else "las"))
                if m and m[2] >= EPT_MIN_OVERLAP:
                    reader, loc, vpc = "ept", m[1], ""
                    src = CRS.from_epsg(3857)
                    xy, z, uf = 1.0, 1.0, "ept"
                else:
                    reader, loc = "las", w["lpc_link"]
                    vpc = rockyweb_vpc(loc, wu)
                    hdr = las_header(loc, vpc, tmp) if vpc else None
                    wu_units = wesm_units(w)
                    uf = "header"
                    if hdr is None:
                        hdr, uf = wu_units, "wesm"
                    if hdr["z_to_m"] is None:
                        hdr["z_to_m"], uf = wu_units["z_to_m"], uf + "+wesm_z"
                    src, xy, z = hdr["horiz"], hdr["xy_to_m"], hdr["z_to_m"]
                rows.append(dict(
                    region=region, work_unit=wu, reader=reader, location=loc,
                    vpc=vpc, horiz_epsg=src.to_epsg() or -1, xy_to_m=xy,
                    z_to_m=z, units_from=uf, collect_start=w["collect_start"],
                    collect_end=w["collect_end"], ql=w["ql"],
                    leaf_risk=leaf_risk(w["collect_start"], w["collect_end"]),
                    pipeline=pipeline_string(src, tcrs)))
                foot_out[wu] = geom
                print(f"   {region} {wu}: {reader} ({uf}) "
                      f"{w['collect_start']}..{w['collect_end']} {w['ql']}",
                      flush=True)
    out_csv = os.path.join(OUT_DIR, "lidar_sources.csv")
    with open(out_csv, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=COLUMNS)
        wr.writeheader()
        wr.writerows(rows)
    with open(os.path.join(OUT_DIR, "ept_match.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(matches[0]))
        wr.writeheader()
        wr.writerows(matches)
    from shapely.geometry import mapping
    fp = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"work_unit": k},
         "geometry": mapping(g)} for k, g in sorted(foot_out.items())]}
    fp_path = os.path.join(OUT_DIR, "lidar_footprints.geojson")
    with open(fp_path, "w") as f:
        json.dump(fp, f)
    digests["lidar_sources.csv"] = sha256_file(out_csv)
    digests["lidar_footprints.geojson"] = sha256_file(fp_path)
    with open(os.path.join(OUT_DIR, "lidar_sources.sha256.txt"), "w") as f:
        for k, v in digests.items():
            f.write(f"{v}  {k}\n")
    print(f"\nWrote {len(rows)} rows; review ept_match.csv and the units_from "
          f"column before the pilot (CR-0036 deliverable 2).")


if __name__ == "__main__":
    main()
