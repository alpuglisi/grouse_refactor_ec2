import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
from lib import *
pos0 = pd.read_csv(f"{OUT}/pos_thinned.csv")
P0 = pd.read_csv(f"{OUT}/pool_prebuffer.csv", low_memory=False); P0 = P0[P0.d_grouse > 300]
res=[]
for ps in range(30):
    pos = split_positives(pos0, seed=ps); P = assign_neg_split(P0, pos)
    rr=[i19(pos, draw(P, pos, s)) for s in range(25)]
    A=pd.DataFrame(rr); m=A.mean(); m['ps']=ps; m['nvalNH']=int(((pos.state=='NH')&(pos.split=='val')).sum())
    for c in A.columns: m['sd_'+c]=A[c].std()
    res.append(m)
D=pd.DataFrame(res)
cells=[c for c in D.columns if c.split('_')[0] in ('S','Exc','Sws','Excws')]
wsd=D[['sd_'+c for c in cells]].mean().values
bsd=D[cells].std().values
print(pd.DataFrame({'within_split_sd':wsd,'between_split_sd_of_means':bsd,'ratio':bsd/wsd, 'range_of_means':(D[cells].max()-D[cells].min()).values},index=cells).round(4))
print(D[[c for c in cells if c.startswith(("Sws","Excws"))]].describe().round(4)); print("NH val n range", D.nvalNH.min(), D.nvalNH.max())
# using fixed-split calibration (split seed 0) thresholds mu+5sd, false-fail on other splits
c0=D.iloc[0]
thr={c:c0[c]+5*c0['sd_'+c] for c in cells}
print("cells whose mean on another split exceeds split-0 mu+5sd:", {c:int((D[c]>thr[c]).sum()) for c in cells if (D[c]>thr[c]).any()})
