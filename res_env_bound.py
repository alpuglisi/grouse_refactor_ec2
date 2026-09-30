"""RESEARCH (read-only):
(a) composite false-fail rate of the recommended gate set on the 1000 fair
    seeds (each bound = fair p99.9);
(b) the ADAPTIVE BOUND: finest pool-truncation attack that still passes every
    recommended gate, and the residual harm it delivers, measured as the
    SE-scaled south-north bias of the negatives relative to the positives."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
import res_env_core as K
from res_env_attacks import skew_cells, north_strip, starve

F = pd.read_csv(f"{K.SCR}/res_fair_1000.csv")
P0, C0 = K.load_all()

Q = 99.9
B = {}
for s in ['I19_ME', 'I19_NH', 'I19_VT', 'I19_pooled', 'med_ME', 'med_NH',
          'med_VT', 'med_pooled', 'ksneg_max', 'nv_share', 'I10_worst']:
    B[s] = np.percentile(F[s].values, Q)
for s in ['I16b_pool_k8', 'I16b_pool_k4', 'I16b_sel_k8', 'I16b_sel_k4']:
    B[s] = np.percentile(np.abs(F[s].values), Q)
print("recommended bounds (fair p99.9 of a 1000-seed calibration):")
for k, v in B.items():
    print(f"   {k:16} {v:.5f}")

TWO = ['I16b_pool_k8', 'I16b_pool_k4', 'I16b_sel_k8', 'I16b_sel_k4']


def verdict(row):
    bad = []
    for s, t in B.items():
        x = abs(row[s]) if s in TWO else row[s]
        if x > t:
            bad.append(s)
    for s in ('I2', 'I3', 'I4_neg', 'I8_short'):
        if row[s] > 0:
            bad.append(s)
    return bad


print("\n--- composite false-fail on the 1000 fair seeds ---")
fails = [verdict(r) for _, r in F.iterrows()]
nf = sum(1 for b in fails if b)
print(f"  {nf}/{len(F)} = {100*nf/len(F):.2f}%   (binomial 95% upper bound "
      f"{100*(nf+1.92*2)/len(F):.2f}%)")
from collections import Counter
print("  which gate fired:", Counter(x for b in fails for x in b))
for mult in (1.0, 1.02, 1.05):
    Bm = {k: v * mult for k, v in B.items()}
    n = 0
    for _, r in F.iterrows():
        if any((abs(r[s]) if s in TWO else r[s]) > t for s, t in Bm.items()):
            n += 1
    print(f"  bounds x{mult:.2f}: false-fail {100*n/len(F):.2f}%")


# ---------------- y-bias harm metric ------------------------------------
def ybias(P, neg):
    out = {}
    for r in L.R:
        p = P[P.state == r]; n = neg[neg.state == r]
        se = p.y_5070.std() / np.sqrt(len(n))
        out[r] = float((n.y_5070.mean() - p.y_5070.mean()) / se)
    return out


print("\n--- fair y-bias envelope (SE units), 40 seeds ---")
yb = []
for sd in range(40):
    Pa, Ca, tg, _ = K.assign(P0, C0, sd)
    neg = L.real_draw(Ca, tg, sd)
    yb.append(ybias(Pa, neg))
YB = pd.DataFrame(yb)
for r in L.R:
    print(f"   {r}: min {YB[r].min():+.2f} p50 {YB[r].median():+.2f} "
          f"max {YB[r].max():+.2f}")

print("\n--- adaptive bound: A2 southern-quantile truncation, fine sweep ---")
print(f"{'variant':26}{'pass rate':>10}{'I19_ME p50':>12}{'med_ME p50':>12}"
      f"{'ybias ME':>10}{'ybias VT':>10}  gates fired")
for regions, tag in ((("ME", "VT"), 'MEVT'), (("ME", "NH", "VT"), 'ALL')):
    for f in (1.00, 0.95, 0.90, 0.85, 0.82, 0.80, 0.75):
        recs, ybs, fired = [], [], []
        for sd in range(40):
            Pa, Ca, tg, _ = K.assign(P0, C0, sd)
            if f < 1.0:
                Cp, ok = skew_cells(Ca, tg, regions, f, 30000.)
            else:
                Cp = Ca
            neg = L.real_draw(Cp, tg, sd)
            g = K.score(Pa, Cp, neg, tg)
            recs.append(g); ybs.append(ybias(Pa, neg))
            fired.append(verdict(g))
        R_ = pd.DataFrame(recs); Y_ = pd.DataFrame(ybs)
        pr = np.mean([len(b) == 0 for b in fired])
        from collections import Counter as Ct
        c = Ct(x for b in fired for x in b)
        print(f"{tag+' f='+format(f,'.2f'):26}{100*pr:9.0f}%"
              f"{R_.I19_ME.median():12.4f}{R_.med_ME.median():12.1f}"
              f"{Y_['ME'].median():+10.2f}{Y_['VT'].median():+10.2f}  "
              f"{dict(c.most_common(3))}")
