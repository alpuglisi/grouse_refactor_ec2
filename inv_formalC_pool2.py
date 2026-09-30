"""FORMAL C: faithful pooled negative candidate pool -- WITH the raster
extraction dropna, envelope ids, is_nonveg and real weights that
inv_fix_breaks.py omitted.  READ-ONLY (scratch writes only)."""
import os, numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData
from inv_formalA_thin import fast_thin
from analyze_grouse import (ENVELOPE_SCHEME, build_envelope_id,
                            fit_scheme_binners, load_evt_crosswalk,
                            sample_raster, NON_VEG_SCLASS_CODES,
                            is_evt_phys_nonveg, RASTER_DIR)
import generate_negatives as GN
import sys
SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME","NH","VT"]
T = Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
data = GrouseData()
def p(*a): print(*a); sys.stdout.flush()

# buffer set = pooled OWN-STATE evaluated rows (veg+nonveg), i.e. what
# analyze_grouse produces after CR-0007 s2 partition clip.
ev = []
for r in R:
    e = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv", low_memory=False)
    ev.append(e[e.state == r])
EV = pd.concat(ev, ignore_index=True)
p("buffer set (own-state evaluated, veg+nonveg):", len(EV))

C = pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv", low_memory=False)
               for r in R], ignore_index=True)
n0=len(C); C = C[~(C['coord_uncertainty_m']>GN.MAX_COORD_UNCERTAINTY_M).fillna(False)].copy()
p(f"raw {n0} -> uncertainty {len(C)}")
n1=len(C); C = C.loc[~C[['longitude','latitude']].round(5).duplicated()].copy()
p(f"5dp dedup {n1} -> {len(C)}")
C['x_5070'],C['y_5070'] = T.transform(C.longitude.values, C.latitude.values)
n2=len(C); C = fast_thin(C.reset_index(drop=True), GN.MIN_SPACING_M, 42)
p(f"pooled 30m thin {n2} -> {len(C)}")
ex,ey = T.transform(EV.longitude.values, EV.latitude.values)
d,_ = cKDTree(np.c_[ex,ey]).query(C[['x_5070','y_5070']].values, k=1)
n3=len(C); C = C[d>GN.BUFFER_M].copy()
p(f"300m buffer {n3} -> {len(C)}")

feats = sorted({c for c,_ in ENVELOPE_SCHEME if c not in ("evt_phys","evt_group")} | {"sclass","evt"})
p("feats:", feats)
xw = load_evt_crosswalk(RASTER_DIR)
out=[]
for r in R:
    sub = C[C['state']==r].copy(); rd = data[r]
    for f in feats:
        vals = np.full(len(sub), np.nan)
        for yr in sorted(sub['year'].dropna().unique()):
            m = (sub['year']==yr).values
            vals[m] = sample_raster(rd.raster_path(f,int(yr)),
                                    sub.loc[m,'longitude'].values, sub.loc[m,'latitude'].values)
        sub[f]=vals
    n4=len(sub); sub=sub.dropna(subset=feats).copy()
    p(f"  {r}: extraction dropped {n4-len(sub)} -> {len(sub)}")
    sub['evt_phys']=sub['evt'].astype(int).map(xw['phys']).fillna("Unmapped")
    e=rd.evaluated; hab=e[~e['nonveg_landcover'].astype(bool)]
    sub['envelope_id']=build_envelope_id(sub, ENVELOPE_SCHEME,
                                        binners=fit_scheme_binners(hab, ENVELOPE_SCHEME))
    sub['is_nonveg']=(sub['sclass'].isin(NON_VEG_SCLASS_CODES)|is_evt_phys_nonveg(sub['evt_phys']))
    mm={row['Envelope']:row for _,row in rd.envelope_metrics.iterrows()}
    w,wc=[],[]
    for eid,nv in zip(sub['envelope_id'],sub['is_nonveg']):
        a,b=GN.build_weight(eid,mm,nv); w.append(a); wc.append(b)
    sub['weight']=w; sub['weight_basis']=wc
    out.append(sub)
C=pd.concat(out,ignore_index=True)
p("FINAL pool:", len(C), C.groupby('state').size().to_dict(),
  "nonveg", round(float(C.is_nonveg.mean()),4))
p("weight basis:", C.weight_basis.value_counts().to_dict())
C[['longitude','latitude','state','year','x_5070','y_5070','evt','evh','sclass',
   'envelope_id','is_nonveg','weight','weight_basis']].to_csv(f"{SCR}/fc_pool.csv",index=False)
p("saved")
