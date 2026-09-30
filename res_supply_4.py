"""RESEARCH (read-only): the ONE CR-0007 gate that reads a raster CR-0008
rewrites -- I17 (ks_feat_max over continuous FEATURE_SPEC features, positives
only).  7 of its 9 features are in CR-0008's scope.
(a) proves the 6 nodata-only repairs leave every positive's point value
    bit-identical (no positive has an out-of-coverage centre pixel);
(b) computes the post-CR-0008 road_dist at every positive as the EXACT shapely
    distance to the nearest paved TIGER-2023 road from every county
    intersecting grid+10 km -- the generator's own definition -- with NH as the
    method's control (NH is already regenerated on disk);
(c) re-derives I17's envelope over 200 split seeds, today vs post-CR-0008.
Writes nothing outside scratch."""
import os, sys, glob, numpy as np, pandas as pd, rasterio, geopandas as gpd
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box, Point
from shapely import STRtree, unary_union
from pyproj import Transformer
from scipy.stats import ks_2samp
from models import road_dist_decode
import inv_formalC_lib as L

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME","NH","VT"]; VINTAGE = 2022; PAD_KM = 10.0
MT = ["S1100","S1200","S1400","S1630","S1640"]
FIPS = {"ME":"23","NH":"33","VT":"50"}
CONT = ["ch","cc","tcc","road_dist","tsd","balive","tpa_live","qmd","carbon_dwn"]
CR8 = {"tcc","road_dist","tsd","balive","tpa_live","qmd","carbon_dwn"}
G0REF = {"tcc":"nlcd","balive":"nlcd","tpa_live":"nlcd","qmd":"nlcd",
         "carbon_dwn":"nlcd","tsd":"dist","road_dist":"tiger"}
def p(*a): print(*a); sys.stdout.flush()

POS = pd.read_csv(f"{SCR}/fc_pos.csv")
GRID, MASKS = {}, {}
for r in R:
    tpl = sorted(glob.glob(f"data/landfire/{r}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s: GRID[r] = (s.transform, s.crs, s.height, s.width)
    H,W = GRID[r][2], GRID[r][3]
    for nm,k in (("nlcd","nlcd"),("tiger_at1","tiger"),("dist2_cov_all_2025","dist")):
        MASKS[(r,k)] = np.unpackbits(np.load(f"{SCR}/{r}_{nm}.npy"))[:H*W].astype(bool).reshape(H,W)

# ---------- (a) invariance of the 6 nodata-only repairs at positives ----------
p("=== (a) positives whose CENTRE pixel is outside the feature's G0 reference ===")
p(f"{'feature':12} {'G0 ref':10} " + " ".join(f"{r:>6}" for r in R) + "   -> point value changes?")
for f in ["tcc","tsd","balive","tpa_live","qmd","carbon_dwn"]:
    cnt = []
    for r in R:
        s = POS[POS.state==r]
        tr,crs,H,W = GRID[r]
        tx = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        x,y = tx.transform(s.longitude.values, s.latitude.values)
        c,rr = (~tr)*(x,y); c=np.floor(c).astype(int); rr=np.floor(rr).astype(int)
        ok = (c>=0)&(c<W)&(rr>=0)&(rr<H)
        bad = int((~ok).sum()) + int((~MASKS[(r,G0REF[f])][rr[ok],c[ok]]).sum())
        cnt.append(bad)
    p(f"{f:12} {G0REF[f]:10} " + " ".join(f"{c:>6}" for c in cnt) +
      ("   NO -- KS term bit-identical" if sum(cnt)==0 else "   YES"))

# ---------- sample today's rasters at the positives ----------
def sample_today(df, feats):
    out = {f: np.full(len(df), np.nan) for f in feats}
    for r in R:
        m = (df.state.values==r)
        if not m.any(): continue
        with rasterio.open(f"data/landfire/{r}_{VINTAGE}_road_dist.tif") as s0:
            tx = Transformer.from_crs("EPSG:4326", s0.crs, always_xy=True)
        xs,ys = tx.transform(df.loc[m,'longitude'].values, df.loc[m,'latitude'].values)
        pts = list(zip(xs,ys))
        for f in feats:
            with rasterio.open(f"data/landfire/{r}_{VINTAGE}_{f}.tif") as src:
                v = np.array([q[0] for q in src.sample(pts)], float)
                nd = src.nodata
            if nd is not None: v[v==nd]=np.nan
            v[v<=-9990]=np.nan
            out[f][m]=v
    return pd.DataFrame(out)
F = sample_today(POS, CONT)
p("\ntoday's sampled values at positives: NaN counts " +
  str({f:int(F[f].isna().sum()) for f in CONT}))

# ---------- (b) exact truth road_dist at every positive ----------
truth = np.full(len(POS), np.nan); stratum = np.array(["?"]*len(POS), object)
missing_note = {}
for r in R:
    m = (POS.state.values==r)
    tr,crs,H,W = GRID[r]
    pad_px = int(round(PAD_KM*1000.0/abs(tr.a)))
    pt = tr*Affine.translation(-pad_px,-pad_px)
    w,s_,e,n = array_bounds(H+2*pad_px, W+2*pad_px, pt)
    gb = (min(w,e),min(s_,n),max(w,e),max(s_,n))
    gw,gs,ge,gn = array_bounds(H,W,tr)
    grid_box = box(min(gw,ge),min(gs,gn),max(gw,ge),max(gs,gn))
    cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
    fp = gpd.GeoSeries([box(*gb)], crs=crs).to_crs(cty.crs).iloc[0]
    sel = cty[cty.intersects(fp)].to_crs(crs)
    frames, miss = [], []
    for st,cf in zip(sel.STATEFP, sel.COUNTYFP):
        pth = f"data/roads/tl_2023_{st}{cf}_roads.zip"
        if not os.path.exists(pth): miss.append(st+cf); continue
        d = gpd.read_file(pth); frames.append(d[d.MTFCC.isin(MT)][["geometry"]])
    missing_note[r] = miss
    roads = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                            geometry="geometry", crs=frames[0].crs).to_crs(crs)
    p(f"\n{r}: {len(sel)} counties intersecting grid+{PAD_KM:.0f}km, "
      f"{len(miss)} uncached {miss}, paved segments {len(roads):,}")
    tree = STRtree(roads.geometry.values)
    tx = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs,ys = tx.transform(POS.loc[m,'longitude'].values, POS.loc[m,'latitude'].values)
    geoms = [Point(a,b) for a,b in zip(xs,ys)]
    _, dt = tree.query_nearest(geoms, all_matches=False, return_distance=True)
    truth[m] = dt
    # strata, as G7 defines them
    cov = unary_union(sel.geometry.values)
    home = unary_union(sel[sel.STATEFP==FIPS[r]].geometry.values)
    other = unary_union(sel[sel.STATEFP!=FIPS[r]].geometry.values)
    line_other = home.boundary.intersection(other.buffer(1.0))
    gser = gpd.GeoSeries(geoms, crs=crs)
    d_line = gser.distance(line_other).values
    d_cov  = gser.distance(cov.boundary).values
    d_edge = np.minimum.reduce([xs-min(gw,ge), max(gw,ge)-xs, ys-min(gs,gn), max(gs,gn)-ys])
    st_ = np.where(d_line<=5000, "S2_stateline",
          np.where(d_edge<=10000, "S3_gridedge",
          np.where(d_cov<=5000, "S4_covedge", "S1_interior")))
    stratum[m] = st_
    del roads, tree, frames

POS['rd_today_m'] = road_dist_decode(F['road_dist'].values)
POS['rd_truth_m'] = truth
POS['stratum'] = stratum
POS['d_abs'] = np.abs(POS.rd_today_m - POS.rd_truth_m)
p("\n=== (b) road_dist at the 6,230 positives: today's raster vs exact truth ===")
p(f"{'reg':4} {'stratum':13} {'n':>5} {'med|err|':>9} {'p90':>9} {'p95':>9} {'max':>10} {'>60m':>7} {'>500m':>7}")
for r in R:
    for stn in ["S1_interior","S2_stateline","S3_gridedge","S4_covedge"]:
        s = POS[(POS.state==r)&(POS.stratum==stn)]
        if not len(s): continue
        d = s.d_abs.values
        p(f"{r:4} {stn:13} {len(s):>5} {np.median(d):>9.1f} {np.quantile(d,.9):>9.1f} "
          f"{np.quantile(d,.95):>9.1f} {d.max():>10.1f} {int((d>60).sum()):>7} {int((d>500).sum()):>7}")
    s = POS[POS.state==r]; d = s.d_abs.values
    p(f"{r:4} {'ALL':13} {len(s):>5} {np.median(d):>9.1f} {np.quantile(d,.9):>9.1f} "
      f"{np.quantile(d,.95):>9.1f} {d.max():>10.1f} {int((d>60).sum()):>7} {int((d>500).sum()):>7}")
p("\n  NH is the CONTROL: its raster is already regenerated, so its |err| is the")
p("  method's own noise floor (G7 bound ~45 m).")

# ---------- (c) I17 envelope, today vs post-CR-0008 ----------
from models import road_dist_encode
F_post = F.copy()
newenc = road_dist_encode(POS.rd_truth_m.values).astype(float)
mMEVT = POS.state.isin(["ME","VT"]).values
F_post.loc[mMEVT,'road_dist'] = newenc[mMEVT]
p("\n=== (c) I17 = ks_feat_max(val, train) over positives, 200 split seeds ===")
POS['blk'] = L.blk(POS.x_5070.values, POS.y_5070.values)
rows=[]
for sd in range(200):
    vb = L.val_blocks(POS, sd); va = POS.blk.isin(vb).values
    rec = {'seed':sd}
    for tag, FF in (('today',F), ('post',F_post)):
        best, bf = -1, None
        for f in CONT:
            a = FF.loc[va,f].dropna(); b = FF.loc[~va,f].dropna()
            k = ks_2samp(a,b).statistic if (len(a)>20 and len(b)>20) else np.nan
            rec[f'{tag}_{f}'] = k
            if k==k and k>best: best,bf = k,f
        rec[f'{tag}_max']=best; rec[f'{tag}_argmax']=bf
    rows.append(rec)
K = pd.DataFrame(rows); K.to_csv(f"{SCR}/rs4_i17.csv", index=False)
p(f"{'':12} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}   gate <= 0.095")
for tag in ('today','post'):
    v = K[f'{tag}_max']
    p(f"  I17 {tag:8} {v.quantile(.5):>8.4f} {v.quantile(.95):>8.4f} {v.quantile(.99):>8.4f} {v.max():>8.4f}"
      f"   breaches: {int((v>0.095).sum())}/200")
p("\n  per-feature KS, median over 200 seeds (today -> post-CR-0008):")
for f in CONT:
    mark = " *CR-0008 scope*" if f in CR8 else ""
    p(f"    {f:12} {K[f'today_{f}'].median():.4f} -> {K[f'post_{f}'].median():.4f}"
      f"   (max {K[f'today_{f}'].max():.4f} -> {K[f'post_{f}'].max():.4f}){mark}")
p("\n  argmax feature frequency: today", K.today_argmax.value_counts().to_dict())
p("                            post ", K.post_argmax.value_counts().to_dict())
POS.to_csv(f"{SCR}/rs4_pos_rd.csv", index=False)
p("\nsaved rs4_i17.csv rs4_pos_rd.csv ; uncached counties per region:", missing_note)
