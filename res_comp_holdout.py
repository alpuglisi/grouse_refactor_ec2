"""RES-COMP: threshold stability -- derive each gate from the FIRST 250 fair
seeds and measure its false-fail rate on the HELD-OUT 250.  READ-ONLY."""
import numpy as np, pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype
SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
F = pd.read_csv(f"{SCR}/rc_fair500.csv")
LOWER = ['D5_hab_supply_min', 'Q6_wratio_min', 'Q3_env_cov_min']
skip = ['seed', 'D1_nvexcess_max', 'D3_shortfall_max', 'D4_topup_fired']
cols = [c for c in F.columns if (is_numeric_dtype(F[c]) or is_bool_dtype(F[c]))
        and c not in skip]
A, B = F.iloc[:250], F.iloc[250:]
print(f"{'statistic':24} {'thr(A,1.30x)':>13} {'ff on A':>9} {'ff on B':>9} "
      f"{'B max':>10} {'headroom':>9}")
for c in cols:
    a = A[c].astype(float).values; b = B[c].astype(float).values
    if c in LOWER:
        t = a.min() / 1.03
        print(f"{c:24} {t:13.4f} {int((a<t).sum()):6d}/250 {int((b<t).sum()):6d}/250 "
              f"{b.min():10.4f} {b.min()/t:9.3f}")
    else:
        t = 1.30 * a.max()
        print(f"{c:24} {t:13.4f} {int((a>t).sum()):6d}/250 {int((b>t).sum()):6d}/250 "
              f"{b.max():10.4f} {t/max(b.max(),1e-12):9.3f}")
