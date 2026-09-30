import pandas as pd
from grouse_data import GrouseData
from models import FEATURE_SPEC
import train as TR
gd=GrouseData()
feats=list(FEATURE_SPEC.keys())
print("features:",feats[:5],"...",len(feats))
tot={}
for r in ["ME","NH","VT"]:
    rd=gd[r]
    for cls in ["positives","negatives"]:
        for sp in ["train","val"]:
            df=getattr(rd,cls)(sp)
            out=TR.filter_by_year_gap(df,rd,feats,2,f"{cls}/{sp}",r)
            k=(cls,sp); a,b=tot.get(k,(0,0)); tot[k]=(a+len(df),b+len(out))
print()
for k,(a,b) in tot.items():
    print(f"{k}: {a} -> {b}  dropped {100*(a-b)/a:.1f}%")
pa=sum(v[0] for k,v in tot.items() if k[0]=='positives'); pb=sum(v[1] for k,v in tot.items() if k[0]=='positives')
na=sum(v[0] for k,v in tot.items() if k[0]=='negatives'); nb=sum(v[1] for k,v in tot.items() if k[0]=='negatives')
print(f"POOLED positives {pa}->{pb} dropped {100*(pa-pb)/pa:.1f}% ; negatives {na}->{nb} dropped {100*(na-nb)/na:.1f}%")
