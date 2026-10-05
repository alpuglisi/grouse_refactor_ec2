"""
generate_canopy_structure.py - CR-0032: Meta 1 m canopy-structure layers.

Builds four static 30 m features from the Meta/WRI 1 m global canopy-height
map (Earth Engine community catalog, MCH_ASSET), on each region's template
grid (its latest EVT clip):

    mch_mean   mean canopy height of the cell's valid 1 m pixels (dm)
    mch_f01    share of valid 1 m pixels < 1 m tall           (per mille)
    mch_f15    share 1 <= h < 5 m                             (per mille)
    mch_f512   share 5 <= h < 12 m                            (per mille)

Written as data/landfire/{REGION}_{YEAR}_{feature}.tif, int16, nodata
-9999, for every YEAR in the union of the region's other features'
vintages (identical copies of one static layer, as road_dist does).

Pipeline (CR-0032 §3):
  1. Earth Engine (mch_image): mosaic of the collection with the first
     tile's projection as its default (a bare mosaic has a WGS84 1 deg
     default, and reduceResolution would then sample one pixel); height,
     three bin indicators and an unmasked validity band, each averaged by
     reduceResolution onto the output grid; unmask(-1) so a masked cell is
     not exported as 0.
  2. Tiles: windows of the template grid (tile_px square), fetched raw
     (float32, 5 bands) by fetch_window directly on the template's own
     CRS and transform - no warp, no mosaic. Each tile is checked against
     the requested window; tiles are cached under a key of the grid and
     the recipe, so an interrupted run resumes.
  3. Local encoding (encode_tile): NODATA where < MCH_MIN_VALID_FRAC of
     the pixels are valid or a band is -1; NODATA (counted) where the mean
     height exceeds MCH_HEIGHT_MAX_M; otherwise models.mch_*_encode.
  4. Staged .tmp files, windowed writes; refused (existing files
     untouched) when < 1 % of the template's valid cells are valid or the
     > 60 m share exceeds MCH_MAX_OVER_FRAC; grid_mismatch must be None;
     then copied to every vintage year with os.replace.

Pilot (--dry-run): one window (most training positives; --pilot-lonlat
overrides), written to --pilot-out only, with counts, ranges, the native
pixel size check and a grid check against the region's NLCD file. Then:
    python check_canopy_structure.py --pilot /tmp/mch_pilot_NH.tif --pilot-region NH

Usage (repository root):
    python generate_canopy_structure.py --regions NH --dry-run
    python generate_canopy_structure.py --regions ME NH VT
    python generate_canopy_structure.py --regions NH --copy-only
"""
import argparse
import hashlib
import math
import os
import shutil
import sys
import tempfile
import time

import numpy as np
import rasterio
from rasterio.windows import Window

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

import download_tcc_nlcd as dtn
from grouse_data import GrouseData, MissingDataError, grid_mismatch
from models import (MCH_HEIGHT_MAX_M, MCH_MIN_VALID_FRAC, mch_height_encode,
                    mch_share_encode)
from regions import REGIONS

MCH_ASSET = "projects/sat-io/open-datasets/facebook/meta-canopy-height"
MCH_FEATURES = ("mch_mean", "mch_f01", "mch_f15", "mch_f512")
# Static layers: written for the union of the OTHER features' years, so a
# stale static file can never keep its own year alive.
STATIC_FEATURES = ("road_dist",) + MCH_FEATURES
MCH_MAX_PIXELS = 4096          # reduceResolution input pixels per cell
MCH_MAX_OVER_FRAC = 0.001      # of valid cells; more -> region refused
MIN_VALID_REGION_FRAC = 0.01   # of template-valid cells; less -> refused
# Pilot grid check (CR-0032 code review C1): the on-disk NLCD came through
# two nearest-neighbour steps (native -> 5070 lattice -> template), the
# fetched copy through one, so exact equality is not expected. Registration
# is tested instead: agreement at offset (0, 0) must beat every shift up to
# GRID_MAX_SHIFT cells by at least GRID_MARGIN.
GRID_MAX_SHIFT = 2
GRID_MARGIN = 0.02
# Bump when mch_image's expression changes: it keys the tile cache.
RECIPE_VERSION = 1
EE_MASKED = -1.0
NODATA = -9999
RAW_BANDS = ("h", "f01", "f15", "f512", "valid")


# ---- Earth Engine side ------------------------------------------------

def mch_image(ee, bounds_lonlat):
    """The five raw float bands (CR-0032 §3.1). Refuses an empty
    collection over the region."""
    region = ee.Geometry.Rectangle(list(bounds_lonlat))
    coll = ee.ImageCollection(MCH_ASSET).filterBounds(region)
    if coll.size().getInfo() == 0:
        raise RuntimeError(f"{MCH_ASSET}: no tiles over {bounds_lonlat}")
    proj = coll.first().projection()
    h = coll.mosaic().select([0]).setDefaultProjection(proj)
    lo, mid, hi = 1, 5, 12      # models.MCH_BIN_EDGES_M
    stack = ee.Image.cat([
        h.rename("h"),
        h.lt(lo).rename("f01"),
        h.gte(lo).And(h.lt(mid)).rename("f15"),
        h.gte(mid).And(h.lt(hi)).rename("f512")])
    valid = (ee.Image(1).updateMask(h.mask()).unmask(0)
             .setDefaultProjection(proj).rename("valid"))
    red = ee.Reducer.mean()
    out = ee.Image.cat([
        stack.reduceResolution(red, maxPixels=MCH_MAX_PIXELS),
        valid.reduceResolution(red, maxPixels=MCH_MAX_PIXELS)])
    return out.toFloat().unmask(EE_MASKED), proj


def fetch_window(ee, image, crs_wkt, transform, width, height, dest,
                 retries=4):
    """One getDownloadURL request for a window of the template grid ->
    GeoTIFF at dest. Same transient-error retry clause as
    download_tcc_nlcd.fetch_tile (BUG-0066)."""
    import requests
    x0, y1 = transform.c, transform.f
    x1, y0 = transform * (width, height)
    proj = ee.Projection(crs_wkt)
    params = {
        "crs": crs_wkt,
        "crs_transform": list(transform)[:6],
        "region": ee.Geometry.Rectangle([min(x0, x1), min(y0, y1),
                                         max(x0, x1), max(y0, y1)],
                                        proj, False),
        "format": "GEO_TIFF",
    }
    delay = 2.0
    for attempt in range(retries + 1):
        try:
            url = image.getDownloadURL(params)
            r = requests.get(url, timeout=300)
            if r.status_code >= 400:
                # Earth Engine puts the reason in the body; a 4xx other
                # than 429 is the request itself and fails the same way
                # on every retry, so it is raised at once, with the body.
                body = r.text[:2000]
                if r.status_code < 500 and r.status_code != 429:
                    raise RuntimeError(
                        f"window {transform.c:.0f},{transform.f:.0f}: "
                        f"Earth Engine refused the request (HTTP "
                        f"{r.status_code}, not retried): {body}")
                raise requests.exceptions.HTTPError(
                    f"HTTP {r.status_code}: {body}", response=r)
            with open(dest, "wb") as f:
                f.write(r.content)
            with rasterio.open(dest):     # parse check
                pass
            return
        except (requests.exceptions.RequestException, ee.EEException,
                rasterio.errors.RasterioIOError) as e:
            if attempt == retries:
                raise RuntimeError(f"window {transform.c:.0f},"
                                   f"{transform.f:.0f} failed after "
                                   f"{retries + 1} attempts: "
                                   f"{type(e).__name__}: {e}") from e
            import traceback
            print(f"   [retry {attempt + 1}/{retries}] window "
                  f"{transform.c:.0f},{transform.f:.0f}: "
                  f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                  file=sys.stderr, flush=True)
            time.sleep(delay)
            delay *= 2


# ---- local side ---------------------------------------------------------

def vintage_years(rd):
    """Union of the region's feature vintages, static features excluded."""
    return sorted({y for f in rd.available_features()
                   if f not in STATIC_FEATURES for y in rd.raster_years(f)})


def template_bounds_lonlat(path):
    """The template's footprint in lon/lat, edges densified."""
    from rasterio.warp import transform_bounds
    with rasterio.open(path) as src:
        return transform_bounds(src.crs, "EPSG:4326", *src.bounds,
                                densify_pts=21)


def encode_tile(raw):
    """raw (5, h, w) float: height m, f01, f15, f512, valid fraction ->
    ({feature: int16 array}, cells over MCH_HEIGHT_MAX_M)."""
    h, f01, f15, f512, valid = (np.asarray(b, np.float64) for b in raw)
    ok = valid >= MCH_MIN_VALID_FRAC
    for b in (h, f01, f15, f512):
        ok &= b != EE_MASKED
    over = ok & (h > MCH_HEIGHT_MAX_M)
    ok &= ~over
    out = {}
    for f, band, enc in (("mch_mean", h, mch_height_encode),
                         ("mch_f01", f01, mch_share_encode),
                         ("mch_f15", f15, mch_share_encode),
                         ("mch_f512", f512, mch_share_encode)):
        a = np.full(band.shape, NODATA, np.int16)
        a[ok] = enc(band[ok])
        out[f] = a
    return out, int(over.sum())


def windows(width, height, tile_px):
    for r in range(0, height, tile_px):
        for c in range(0, width, tile_px):
            yield Window(c, r, min(tile_px, width - c),
                         min(tile_px, height - r))


def _contains(w, r, c):
    return (w.row_off <= r < w.row_off + w.height and
            w.col_off <= c < w.col_off + w.width)


def _pilot_window(rd, tpl, wins, pilot_lonlat):
    """The window holding the most training positives (template centre
    if there are none); pilot_lonlat overrides."""
    from pyproj import Transformer
    to_tpl = Transformer.from_crs("EPSG:4326", tpl.crs, always_xy=True)
    if pilot_lonlat is not None:
        r, c = tpl.index(*to_tpl.transform(*pilot_lonlat))
        hit = [w for w in wins if _contains(w, r, c)]
        if not hit:
            raise SystemExit(f"--pilot-lonlat {pilot_lonlat} is outside "
                             f"the {rd.region} template grid")
        return hit[0]
    try:
        pos = rd.positives("all")
    except MissingDataError as e:
        print(f"   [note] {rd.region}: no positives on disk ({e}); pilot "
              f"window = template centre")
        pos = None
    if pos is not None and len(pos):
        xs, ys = to_tpl.transform(pos["longitude"].to_numpy(),
                                  pos["latitude"].to_numpy())
        rc = [tpl.index(x, y) for x, y in zip(xs, ys)]
        return max(wins, key=lambda w: sum(_contains(w, r, c)
                                           for r, c in rc))
    r, c = tpl.height // 2, tpl.width // 2
    return next(w for w in wins if _contains(w, r, c))


def grid_check(ee, image, rd, feature, window, valid_range=None):
    """Fetch `image` over a template window through fetch_window and test
    that it is registered with the region's on-disk `feature` file: the
    share of equal cells (valid in both) at every offset up to
    GRID_MAX_SHIFT cells. Returns {"agree": {(dy, dx): share}, "best",
    "margin", "ok"}; ok when (0, 0) is the best offset by >= GRID_MARGIN.
    Catches an Earth Engine misreading of the template's CRS, which the
    acceptance gate would share (CR-0032 review B2-3, code review C1)."""
    template = dtn.template_raster(rd)
    with rasterio.open(template) as tpl:
        wkt, tr = tpl.crs.to_wkt(), tpl.window_transform(window)
    with tempfile.TemporaryDirectory() as td:
        dest = os.path.join(td, "grid.tif")
        fetch_window(ee, image, wkt, tr, window.width, window.height, dest)
        with rasterio.open(dest) as s:
            got = s.read(1)
    if valid_range is not None:
        got = dtn.mask_to_valid(got, *valid_range)
    k = GRID_MAX_SHIFT
    padded = Window(window.col_off - k, window.row_off - k,
                    window.width + 2 * k, window.height + 2 * k)
    with rasterio.open(rd.latest_raster_path(feature)) as src:
        disk = src.read(1, window=padded, boundless=True, fill_value=NODATA)
    got_ok = (got != NODATA) & (got != EE_MASKED)
    agree = {}
    for dy in range(-k, k + 1):
        for dx in range(-k, k + 1):
            d = disk[k + dy:k + dy + window.height,
                     k + dx:k + dx + window.width]
            both = got_ok & (d != NODATA)
            agree[(dy, dx)] = (float((got[both] == d[both]).mean())
                               if both.any() else 0.0)
    best = max(agree, key=agree.get)
    runner_up = max(v for o, v in agree.items() if o != (0, 0))
    margin = agree[(0, 0)] - runner_up
    return {"agree": agree, "best": best, "margin": margin,
            "ok": best == (0, 0) and margin >= GRID_MARGIN}


def _report_pilot(raw, enc, n_over, seconds):
    h, f01, f15, f512, valid = raw
    n = valid.size
    vin = float(((valid > 0) & (valid < 1)).sum()) / n
    print(f"   pilot window {valid.shape[1]} x {valid.shape[0]} cells, "
          f"fetched in {seconds:.1f} s")
    print(f"   -1 (EE-masked) cells: {int((h == EE_MASKED).sum()):,}; "
          f"valid < {MCH_MIN_VALID_FRAC}: "
          f"{int((valid < MCH_MIN_VALID_FRAC).sum()):,}; "
          f"> {MCH_HEIGHT_MAX_M:g} m: {n_over:,}")
    print(f"   valid fraction strictly inside (0, 1): {vin:.2%} of cells "
          f"(0 means the validity band was not aggregated)")
    if vin == 0 and (valid >= MCH_MIN_VALID_FRAC).any() and \
            (valid < MCH_MIN_VALID_FRAC).any():
        # a coverage edge with no partial cell: the band was sampled, not
        # averaged (CR-0032 code review C7)
        raise RuntimeError("pilot: the validity band holds only 0/1 across "
                           "a coverage edge - not aggregated. Do not run "
                           "the full build.")
    for f in MCH_FEATURES:
        a = enc[f][enc[f] != NODATA]
        rng = f"{int(a.min())}..{int(a.max())}" if a.size else "none"
        print(f"   {f:9s} encoded {a.size:,} of {n:,} cells, range {rng}")


def build_region(ee, image, rd, tile_px=256, workers=8, dry_run=False,
                 tile_dir=None, pilot_lonlat=None, pilot_out=None,
                 grid_image=None):
    """CR-0032 §3.4. Returns {"years", "written", "valid_frac", "n_tiles",
    "skipped", "over_max"}. grid_image: (image, feature, valid_range) for
    the dry-run grid check (skipped when None)."""
    if tile_px % 16:
        raise ValueError(f"tile_px {tile_px} must be a multiple of 16")
    template = dtn.template_raster(rd)
    if template is None:
        raise SystemExit(f"{rd.region}: no evt raster - no template grid")
    years = vintage_years(rd)
    with rasterio.open(template) as tpl:
        wkt = tpl.crs.to_wkt()
        profile = tpl.profile
        all_wins = list(windows(tpl.width, tpl.height, tile_px))
        tvalid = {(w.row_off, w.col_off):
                  int((tpl.read(1, window=w) != tpl.nodata).sum())
                  for w in all_wins}
        n_tpl_valid = sum(tvalid.values())
        wins = ([_pilot_window(rd, tpl, all_wins, pilot_lonlat)]
                if dry_run else all_wins)
        todo = [w for w in wins if tvalid[(w.row_off, w.col_off)]]
        win_tr = {(w.row_off, w.col_off): tpl.window_transform(w)
                  for w in todo}
    skipped = len(wins) - len(todo)
    tpl_crs = rasterio.crs.CRS.from_wkt(wkt)

    tmpdir = None
    if dry_run or tile_dir is None:
        tmpdir = tempfile.mkdtemp(prefix="mch_tiles_")
        tile_dir = tmpdir
    key = hashlib.sha256(repr((wkt, tuple(profile["transform"])[:6],
                               profile["width"], profile["height"],
                               tile_px, MCH_ASSET, RECIPE_VERSION)
                              ).encode()).hexdigest()[:16]
    tile_dir = os.path.join(tile_dir, key)
    os.makedirs(tile_dir, exist_ok=True)

    def tile_path(w):
        return os.path.join(tile_dir, f"{w.row_off}_{w.col_off}.tif")

    def identical(s, w):
        want = tuple(win_tr[(w.row_off, w.col_off)])[:6]
        return (s.shape == (w.height, w.width) and s.crs == tpl_crs and
                all(abs(a - b) <= 1e-3 * abs(want[0])
                    for a, b in zip(tuple(s.transform)[:6], want)))

    def cached(w):
        try:
            with rasterio.open(tile_path(w)) as s:
                return s.count == len(RAW_BANDS) and identical(s, w)
        except rasterio.errors.RasterioIOError:
            return False

    need = [w for w in todo if not cached(w)]

    def fetch(i):
        w = need[i]
        dest = tile_path(w)
        fetch_window(ee, image, wkt, win_tr[(w.row_off, w.col_off)],
                     w.width, w.height, dest + ".part")
        with rasterio.open(dest + ".part") as s:
            if s.count != len(RAW_BANDS) or not identical(s, w):
                raise RuntimeError(
                    f"{rd.region} window {w}: Earth Engine returned "
                    f"{s.count} bands on {s.crs} {tuple(s.transform)[:6]}, "
                    f"not the requested window - not used")
        os.replace(dest + ".part", dest)

    print(f"   {rd.region}: {len(todo)} windows to build "
          f"({len(todo) - len(need)} cached, {skipped} all-nodata skipped), "
          f"years {years}")
    t0 = time.time()
    try:
        if need:
            dtn._fetch_all(len(need), fetch, workers, rd.region)
        if dry_run:
            if not todo:
                raise SystemExit(f"{rd.region}: pilot window is all "
                                 f"template nodata; pass --pilot-lonlat")
            w = todo[0]
            with rasterio.open(tile_path(w)) as s:
                raw = s.read()
            enc, n_over = encode_tile(raw)
            _report_pilot(raw, enc, n_over, time.time() - t0)
            prof = dict(profile, height=w.height, width=w.width,
                        count=len(MCH_FEATURES),
                        transform=win_tr[(w.row_off, w.col_off)],
                        dtype="int16", nodata=NODATA, tiled=False)
            prof.pop("blockxsize", None)
            prof.pop("blockysize", None)
            with rasterio.open(pilot_out, "w", **prof) as dst:
                for b, f in enumerate(MCH_FEATURES, 1):
                    dst.write(enc[f], b)
                    dst.set_band_description(b, f)
            print(f"   pilot written to {pilot_out} (nothing under data/)")
            if grid_image is not None:
                gimg, gfeat, grange = grid_image
                g = grid_check(ee, gimg, rd, gfeat, w, grange)
                print(f"   grid check vs on-disk {gfeat}: {g['agree'][(0, 0)]:.2%}"
                      f" equal at offset (0, 0); best offset {g['best']}, "
                      f"margin over the best shift {g['margin']:+.2%} "
                      f"(need (0, 0) and >= {GRID_MARGIN:.0%})")
                if not g["ok"]:
                    raise RuntimeError(
                        f"{rd.region}: Earth Engine's reading of the "
                        f"template grid is not registered with {gfeat} on "
                        f"disk (best offset {g['best']}, margin "
                        f"{g['margin']:+.2%}) - do not run the full build; "
                        f"if the window is too uniform to tell, retry "
                        f"with another --pilot-lonlat")
            return {"years": years, "written": [], "valid_frac": None,
                    "n_tiles": 1, "skipped": skipped, "over_max": n_over}

        d = os.path.dirname(template)
        staged = {f: os.path.join(d, f"{rd.region}_{f}.staged.tmp")
                  for f in MCH_FEATURES}
        prof = dict(profile, dtype="int16", nodata=NODATA, count=1,
                    compress="deflate", tiled=True, blockxsize=tile_px,
                    blockysize=tile_px)
        n_valid = n_over = 0
        try:
            dsts = {f: rasterio.open(p, "w", **prof)
                    for f, p in staged.items()}
            try:
                for f in MCH_FEATURES:
                    dsts[f].update_tags(GROUSE_COVERAGE="ee-mask",
                                        GROUSE_SOURCE=MCH_ASSET)
                done = {(w.row_off, w.col_off) for w in todo}
                for w in all_wins:
                    if (w.row_off, w.col_off) in done:
                        with rasterio.open(tile_path(w)) as s:
                            enc, o = encode_tile(s.read())
                        n_over += o
                        n_valid += int((enc["mch_mean"] != NODATA).sum())
                    else:
                        enc = {f: np.full((w.height, w.width), NODATA,
                                          np.int16) for f in MCH_FEATURES}
                    for f in MCH_FEATURES:
                        dsts[f].write(enc[f], 1, window=w)
            finally:
                for x in dsts.values():
                    x.close()
            if n_valid < MIN_VALID_REGION_FRAC * n_tpl_valid:
                raise RuntimeError(
                    f"{rd.region}: {n_valid:,} valid cells of "
                    f"{n_tpl_valid:,} template cells (< "
                    f"{MIN_VALID_REGION_FRAC:.0%}). Not written.")
            if n_over > MCH_MAX_OVER_FRAC * (n_valid + n_over):
                raise RuntimeError(
                    f"{rd.region}: {n_over:,} cells > {MCH_HEIGHT_MAX_M:g} m "
                    f"(> {MCH_MAX_OVER_FRAC:.1%} of valid cells). "
                    f"Not written.")
            with rasterio.open(template) as ref:
                for f, p in staged.items():
                    with rasterio.open(p) as s:
                        mm = grid_mismatch(s, ref)
                    if mm is not None:
                        raise RuntimeError(f"{p}: {mm}. Not written.")
            # every copy staged before any replace, so a failure leaves
            # either all years new or all untouched (code review C6)
            outs = [os.path.join(d, f"{rd.region}_{y}_{f}.tif")
                    for f in MCH_FEATURES for y in years]
            for f in MCH_FEATURES:
                for y in years:
                    shutil.copyfile(staged[f], os.path.join(
                        d, f"{rd.region}_{y}_{f}.tif") + ".tmp")
            for out in outs:
                os.replace(out + ".tmp", out)
            written = outs
        finally:
            for p in list(staged.values()) + [
                    os.path.join(d, f"{rd.region}_{y}_{f}.tif.tmp")
                    for f in MCH_FEATURES for y in years]:
                if os.path.exists(p):
                    os.remove(p)
        print(f"   {rd.region}: wrote {len(written)} files; valid "
              f"{n_valid:,} of {n_tpl_valid:,} template cells; "
              f"> {MCH_HEIGHT_MAX_M:g} m: {n_over:,}")
        return {"years": years, "written": written,
                "valid_frac": n_valid / max(n_tpl_valid, 1),
                "n_tiles": len(todo), "skipped": skipped, "over_max": n_over}
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def copy_only(rd):
    """Write missing vintage years from the existing latest mch_* files
    (no Earth Engine)."""
    years = vintage_years(rd)
    template = dtn.template_raster(rd)
    written = []
    for f in MCH_FEATURES:
        if not rd.raster_years(f):
            raise SystemExit(f"{rd.region}: no {f} file to copy from - "
                             f"run the full build first")
        src = rd.latest_raster_path(f)
        # only a file this generator wrote, on today's template grid
        # (code review C4)
        with rasterio.open(src) as s, rasterio.open(template) as ref:
            mm = grid_mismatch(s, ref)
            tag = s.tags().get("GROUSE_SOURCE")
        if mm is not None or tag != MCH_ASSET:
            raise SystemExit(f"{src}: {mm or f'GROUSE_SOURCE={tag!r}'} - "
                             f"rebuild instead of copying")
        for y in years:
            out = os.path.join(os.path.dirname(src),
                               f"{rd.region}_{y}_{f}.tif")
            if os.path.exists(out):
                continue
            shutil.copyfile(src, out + ".tmp")
            os.replace(out + ".tmp", out)
            written.append(out)
    print(f"   {rd.region}: copied {len(written)} missing files")
    return written


def native_pixel_check(ee, proj, lat):
    """Refuse when a 30 m cell could need more than MCH_MAX_PIXELS input
    pixels (CR-0032 §3.4). Returns the native pixel's ground size (m)."""
    scale = proj.nominalScale().getInfo()
    crs = proj.crs().getInfo()
    wkt = proj.wkt().getInfo() if not crs.startswith("EPSG:") else ""
    mercator = (crs in ("EPSG:3857", "EPSG:900913") or
                "mercator" in wkt.lower())      # code review C5
    ground = scale * (math.cos(math.radians(lat)) if mercator else 1.0)
    need = math.ceil(30.0 / ground + 1) ** 2
    print(f"   source projection {crs}, nominal scale {scale:.3f}, ground "
          f"pixel {ground:.3f} m -> up to {need} pixels per cell "
          f"(maxPixels {MCH_MAX_PIXELS})")
    if need > MCH_MAX_PIXELS:
        raise SystemExit(f"maxPixels {MCH_MAX_PIXELS} too small for a "
                         f"{ground:.3f} m source; raise MCH_MAX_PIXELS "
                         f"(a CR-0032 constant)")
    return ground


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--regions", nargs="+", default=list(REGIONS),
                    choices=list(REGIONS))
    ap.add_argument("--project", default=os.environ.get("EARTHENGINE_PROJECT"))
    # 64: EC2 pilot 2026-10-05 - 256 exceeds Earth Engine's reprojection
    # limit for the 1 m source; 64 fetched fastest per cell (9.9 s)
    ap.add_argument("--tile-px", type=int, default=64)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--tile-dir", default=os.path.expanduser(
        "~/.cache/grouse_mch"))
    ap.add_argument("--dry-run", action="store_true",
                    help="one pilot window; writes only --pilot-out")
    ap.add_argument("--pilot-lonlat", type=float, nargs=2, default=None,
                    metavar=("LON", "LAT"))
    ap.add_argument("--pilot-out", default=None,
                    help="default /tmp/mch_pilot_{REGION}.tif")
    ap.add_argument("--copy-only", action="store_true",
                    help="write missing vintage years from existing files")
    args = ap.parse_args()

    data = GrouseData()
    if args.copy_only:
        for R in args.regions:
            copy_only(data[R])
        return
    ee = dtn.ee_init(args.project)
    for R in args.regions:
        rd = data[R]
        template = dtn.template_raster(rd)
        if template is None:
            raise SystemExit(f"{R}: no evt raster - no template grid")
        bounds = template_bounds_lonlat(template)
        print(f"{R}: template {os.path.basename(template)}")
        image, proj = mch_image(ee, bounds)
        native_pixel_check(ee, proj, (bounds[1] + bounds[3]) / 2)
        grid = None
        if args.dry_run:
            spec = dtn.PRODUCTS["nlcd"]
            if rd.raster_years("nlcd"):
                cid = dtn.resolve_collection(ee, spec["collections"])
                year = max(rd.raster_years("nlcd"))
                gimg, _ = dtn.year_image(ee, cid, spec["bands"], year)
                grid = (gimg, "nlcd", spec["valid_range"])
            else:
                print(f"   [warn] {R}: no nlcd file - grid check skipped")
        build_region(ee, image, rd, tile_px=args.tile_px,
                     workers=args.workers, dry_run=args.dry_run,
                     tile_dir=os.path.join(args.tile_dir, R),
                     pilot_lonlat=args.pilot_lonlat,
                     pilot_out=args.pilot_out or f"/tmp/mch_pilot_{R}.tif",
                     grid_image=grid)


if __name__ == "__main__":
    main()
