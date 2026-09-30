"""RESEARCH (read-only): 1000-seed FAIR envelope for every negative-dependent
CR-0007 acceptance statistic, on the faithful sampler."""
import sys, time, pandas as pd
import res_env_core as K

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
P, C = K.load_all()
rows, t0 = [], time.time()
for sd in range(N):
    rows.append(K.fair_seed(P, C, sd))
    if (sd + 1) % 50 == 0:
        print(f"{sd+1}/{N}  {time.time()-t0:.0f}s", flush=True)
pd.DataFrame(rows).to_csv(f"{K.SCR}/res_fair_{N}.csv", index=False)
print("saved", f"{K.SCR}/res_fair_{N}.csv")
