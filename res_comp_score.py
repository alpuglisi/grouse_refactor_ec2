"""RES-COMP: final calibration + separation table.  Thresholds are set by a
single mechanical rule (1.30x the fair 500-seed max for one-sided upper gates,
fair_min/1.03 for the lower one), so nothing is hand-tuned per attack; exact
predicates carry no threshold.  READ-ONLY."""
import numpy as np, pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype
SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
F = pd.read_csv(f"{SCR}/rc_fair500.csv")
A = pd.read_csv(f"{SCR}/rc_atk20.csv")
EXACT = {'D1_nvexcess_max': ('<=', 0), 'D3_shortfall_max': ('==', 0),
         'D4_topup_fired': ('==', 0), 'D6_weight_mismatch': ('==', 0)}
LOWER = ['D5_hab_supply_min', 'Q6_wratio_min', 'Q3_env_cov_min']
OBS = ['D2_nvshare_max', 'B1_recs_per_valblock', 'B2_blockrec_gap_pp',
       'B3_max_recs_one_block', 'Q6_wratio_max', 'S1z_pooled', 'S2z_region',
       'S3z_pooled', 'S4z_region']
stats = [c for c in F.columns if (is_numeric_dtype(F[c]) or is_bool_dtype(F[c]))
         and c != 'seed']
for c in stats: F[c] = F[c].astype(float)

thr = {}
print(f"{'statistic':24} {'kind':5} {'fair min':>10} {'fair p50':>10} "
      f"{'fair p99':>10} {'fair max':>10} {'THRESHOLD':>12} {'false-fail':>11}")
for c in stats:
    v = F[c].values
    if c in EXACT:
        op, t = EXACT[c]; thr[c] = ('<=', t)
        ff = int((v > t).sum()); kind = 'EXACT'
    elif c in LOWER:
        t = round(float(v.min()) / 1.03, 4); thr[c] = ('>=', t)
        ff = int((v < t).sum()); kind = 'LOW'
    elif c in OBS:
        thr[c] = None; ff = 0; kind = 'OBS'
    else:
        t = round(1.30 * float(v.max()), 4); thr[c] = ('<=', t)
        ff = int((v > t).sum()); kind = 'UP'
    ts = '-' if thr[c] is None else f"{thr[c][0]} {thr[c][1]:g}"
    print(f"{c:24} {kind:5} {v.min():10.4f} {np.median(v):10.4f} "
          f"{np.quantile(v,.99):10.4f} {v.max():10.4f} {ts:>12} "
          f"{ff:>6}/{len(v)}")

print("\n\n=== ATTACK SEPARATION (worst-case over 20 seeds per attack) ===")
print("value shown = the attack's WORST-CASE value against its gate direction")
print("   (min for an upper gate, max for a lower gate); * = gate FIRES on every seed,")
print("   ~ = fires on some seeds only, blank = never fires.\n")
atks = [a for a in A.attack.unique() if a != 'fair'] 
gated = [c for c in stats if thr.get(c) is not None]
rowsout = []
for c in gated:
    op, t = thr[c]
    r = {'statistic': c, 'gate': f"{op} {t:g}"}
    for a in ['fair'] + atks:
        v = A.loc[A.attack == a, c].astype(float).values
        if len(v) == 0: r[a] = ''; continue
        if op == '<=':
            worst = v.min(); nfire = int((v > t).sum())
        else:
            worst = v.max(); nfire = int((v < t).sum())
        mark = '*' if nfire == len(v) else ('~' if nfire else ' ')
        r[a] = f"{worst:.4g}{mark}"
    rowsout.append(r)
T = pd.DataFrame(rowsout).set_index('statistic')
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 40)
print(T.to_string())

print("\n\n=== WHICH GATES FIRE, per attack (all 20 seeds) ===")
for a in ['fair'] + atks:
    fires = []
    for c in gated:
        op, t = thr[c]
        v = A.loc[A.attack == a, c].astype(float).values
        n = int((v > t).sum()) if op == '<=' else int((v < t).sum())
        if n == len(v): fires.append(c.split('_')[0])
    print(f"  {a:18} -> {', '.join(sorted(set(fires))) if fires else 'NONE (all gates green)'}")

print("\n\n=== CR-0007's OWN GATES under each attack (seed 1000) ===")
crc = [c for c in A.columns if c.startswith('CR_')]
C = A[A.seed == 1000].set_index('attack')[crc].astype(float)
print(C.round(4).T.to_string())
