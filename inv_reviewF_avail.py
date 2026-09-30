import numpy as np, pandas as pd, geopandas as gpd
import analyze_grouse as AG
from regions import BOXES
FIPS={"23":"ME","33":"NH","50":"VT"}
c=gpd.read_file("data/roads/tl_2023_us_county.zip"); c=c[c.STATEFP.isin(FIPS)]
st=c.dissolve(by='STATEFP').reset_index(); st['s']=st.STATEFP.map(FIPS); st=st.to_crs(4326)
polys={r:st[st.s==r].geometry.iloc[0] for r in FIPS.values()}
xw=AG.load_evt_crosswalk(AG.RASTER_DIR)
N=AG.BACKGROUND_N
for r in ["ME","NH","VT"]:
    fy={f:AG.available_years(r,f) for f in AG.FEATURES}
    rng=np.random.default_rng(1)
    lo,la,hi,ha=BOXES[r]
    lons=rng.uniform(lo,hi,N); lats=rng.uniform(la,ha,N)
    needed={col for col,_ in AG.ENVELOPE_SCHEME if col not in ("evt_phys","evt_group")}|{"sclass"}
    if any(col for col,_ in AG.ENVELOPE_SCHEME if col in ("evt_phys","evt_group")): needed|={"evt"}
    bg=pd.DataFrame({"longitude":lons,"latitude":lats})
    for f in sorted(needed):
        yr=max(fy[f]); import os
        bg[f]=AG.sample_raster(os.path.join(AG.RASTER_DIR,f"{r}_{yr}_{f}.tif"),lons,lats)
    n0=len(bg)
    bg=bg.dropna(subset=sorted(needed))
    n1=len(bg)
    if xw is not None:
        phys=bg['evt'].astype(int).map(xw['phys']).fillna("Unmapped")
        nonveg=bg['sclass'].isin(list(AG.NON_VEG_SCLASS_CODES))|AG.is_evt_phys_nonveg(phys).values
    else:
        nonveg=bg['sclass'].isin(list(AG.NON_VEG_SCLASS_CODES))
    bg=bg[~nonveg]
    g=gpd.GeoDataFrame(bg,geometry=gpd.points_from_xy(bg.longitude,bg.latitude),crs=4326)
    inside=g.within(polys[r])
    print(f"{r}: box sample {n0} -> after dropna {n1} -> after non-veg drop {len(bg)} ; in-state share {100*inside.mean():.1f}%  ({int(inside.sum())} of {len(bg)})")
