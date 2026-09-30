"""RESEARCH (read-only): how much of each faithful envelope is contributed by
the CANDIDATE WEIGHTS, i.e. by `envelope_metrics` + `fit_scheme_binners`, both
of which a clean post-CR-0007 `analyze_grouse.py` run rewrites.

V0  baseline  : current weights (already run by res_env_fair.py)
V1  uniform-w : weights = 1 inside each of the two pools (cap intact).
                Bounds the total weight contribution.
V2  used-side : `Sightings` recounted from the OWN-STATE habitat set (what
                CR-0007 s2's partition clip does), Avail_N held fixed,
                Selection_Ratio / Classification / weight rebuilt.
                Measures the half of the change that IS computable here.
Also reports how far the EVH quantile edges move and how many candidates
change envelope_id when `fit_scheme_binners` is refit on the clipped
habitat set.
"""
import sys, time
import numpy as np, pandas as pd
from grouse_data import GrouseData
from analyze_grouse import (ENVELOPE_SCHEME, build_envelope_id,
                            fit_scheme_binners, MIN_AVAIL_BG,
                            SELECT_W_HI, SELECT_W_LO, load_evt_crosswalk,
                            RASTER_DIR)
import generate_negatives as GN
import inv_formalC_lib as L
import res_env_core as K

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
P0, C0 = K.load_all()
data = GrouseData()
R = L.R
_xw = load_evt_crosswalk(RASTER_DIR)
C0['evt_phys'] = C0['evt'].astype(int).map(_xw['phys']).fillna("Unmapped")


def classify(sr, avail_n):
    if avail_n < MIN_AVAIL_BG:
        return 'Landscape-Rare (availability too low to judge)'
    if pd.isna(sr):
        return 'Selected (ratio undefined)'
    if sr >= SELECT_W_HI:
        return 'Selected'
    if sr <= SELECT_W_LO:
        return 'Avoided'
    return 'Proportional'


# ---------- binner shift under the s2 clip -------------------------------
print("=== EVH quantile-edge shift when fit_scheme_binners is refit on the "
      "own-state habitat set ===")
new_ids = {}
for r in R:
    e = data[r].evaluated
    hab_now = e[~e['nonveg_landcover'].astype(bool)]
    hab_clip = hab_now[hab_now['state'] == r]
    b_now = fit_scheme_binners(hab_now, ENVELOPE_SCHEME)
    b_clip = fit_scheme_binners(hab_clip, ENVELOPE_SCHEME)
    for col in b_now:
        print(f"  {r} {col}: now {np.round(np.asarray(b_now[col],float),3)}")
        print(f"  {r} {col}: clip {np.round(np.asarray(b_clip[col],float),3)}")
    sub = C0[C0.state == r]
    idn = build_envelope_id(sub, ENVELOPE_SCHEME, binners=b_now)
    idc = build_envelope_id(sub, ENVELOPE_SCHEME, binners=b_clip)
    ch = (np.asarray(idn) != np.asarray(idc)).mean()
    print(f"  {r}: {100*ch:.2f}% of {len(sub)} candidates change envelope_id "
          f"under the refit binners")
    new_ids[r] = (np.asarray(idn), np.asarray(idc), hab_now, hab_clip,
                  b_now, b_clip)

# ---------- V2: recount Sightings on the clipped habitat set ------------
print("\n=== V2: envelope_metrics with Sightings recounted on own-state "
      "habitat (Avail_N held fixed) ===")
w2 = np.full(len(C0), np.nan)
basis2 = np.array(['?'] * len(C0), dtype=object)
for r in R:
    idn, idc, hab_now, hab_clip, b_now, b_clip = new_ids[r]
    m = data[r].envelope_metrics.copy()
    # used side, OLD binners so Avail_N stays keyed consistently
    hid = build_envelope_id(hab_clip, ENVELOPE_SCHEME, binners=b_now)
    cnt = pd.Series(hid).value_counts()
    m['Sightings_new'] = m['Envelope'].map(cnt).fillna(0.0)
    tot_new = m['Sightings_new'].sum()
    m['Used_Pct'] = 100 * m['Sightings_new'] / tot_new
    m['Selection_Ratio'] = np.where(m['Avail_Pct'] > 0,
                                    m['Used_Pct'] / m['Avail_Pct'], np.nan)
    m['Classification'] = [classify(sr, an) for sr, an
                           in zip(m['Selection_Ratio'], m['Avail_N'])]
    old = data[r].envelope_metrics
    print(f"  {r}: used total {old['Sightings'].sum():.0f} -> {tot_new:.0f}; "
          f"class changes {int((old['Classification'].values != m['Classification'].values).sum())}"
          f"/{len(m)}; SR median ratio "
          f"{np.nanmedian(m['Selection_Ratio']/old['Selection_Ratio']):.3f}")
    mm = {row['Envelope']: row for _, row in m.iterrows()}
    sel = (C0.state.values == r)
    ww, bb = [], []
    for eid, nv in zip(C0.loc[sel, 'envelope_id'], C0.loc[sel, 'is_nonveg']):
        a, b = GN.build_weight(eid, mm, nv)
        ww.append(a); bb.append(b)
    w2[sel] = ww; basis2[sel] = bb
hab = ~C0.is_nonveg.values
print(f"  habitat-pool weight: spearman(old,new) = "
      f"{pd.Series(C0.weight.values[hab]).corr(pd.Series(w2[hab]), method='spearman'):.4f}; "
      f"median |log2 ratio| = "
      f"{np.nanmedian(np.abs(np.log2(w2[hab]/C0.weight.values[hab]))):.3f}")
print("  new weight_basis:", pd.Series(basis2).value_counts().to_dict())

# ---------- run the envelopes -------------------------------------------
variants = {}
variants['V1_uniform_w'] = np.ones(len(C0))
variants['V2_usedside_clip'] = w2
rows, t0 = [], time.time()
for name, wv in variants.items():
    Cv = C0.copy(); Cv['weight'] = wv
    for sd in range(N):
        Pa, Ca, tg, gvf = K.assign(P0, Cv, sd)
        neg = L.real_draw(Ca, tg, sd)
        g = K.score(Pa, Ca, neg, tg)
        g['seed'] = sd; g['variant'] = name
        rows.append(g)
    print(f"{name} done {time.time()-t0:.0f}s", flush=True)
pd.DataFrame(rows).to_csv(f"{K.SCR}/res_variants_{N}.csv", index=False)
print("saved")
