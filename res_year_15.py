import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np
from pyproj import Transformer
R=['ME','NH','VT']; B=30000.0
tr=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def blocks(df):
    x,y=tr.transform(df['longitude'].values, df['latitude'].values)
    return set(zip(np.floor(np.asarray(x)/B).astype(int), np.floor(np.asarray(y)/B).astype(int)))
print("CR-0007 gate (d)-style: fraction of positive-occupied 30km blocks holding NO negative")
print(f"{'reg':4s} {'pre-filter':>12s} {'post-filter':>12s}")
for r in R:
    p=pd.concat([pd.read_csv(f'data/pipeline/{k}_positives_{r}.csv') for k in ['train','val']],ignore_index=True)
    n=pd.concat([pd.read_csv(f'data/negatives/{k}_negatives_{r}.csv') for k in ['train','val']],ignore_index=True)
    pb,nb=blocks(p),blocks(n)
    pre=len(pb-nb)/len(pb)
    p2=p[p['year']>=2020]; pb2=blocks(p2)
    post=len(pb2-nb)/len(pb2)
    print(f"{r:4s} {pre:12.4f} {post:12.4f}   (npos_blocks {len(pb)}->{len(pb2)})")
# and the reverse: negative-occupied blocks with no positive, post-filter
print("\nreverse: fraction of negative-occupied 30km blocks holding NO positive")
for r in R:
    p=pd.concat([pd.read_csv(f'data/pipeline/{k}_positives_{r}.csv') for k in ['train','val']],ignore_index=True)
    n=pd.concat([pd.read_csv(f'data/negatives/{k}_negatives_{r}.csv') for k in ['train','val']],ignore_index=True)
    nb=blocks(n); pb=blocks(p); pb2=blocks(p[p['year']>=2020])
    print(f"{r}: pre {len(nb-pb)/len(nb):.4f}  post {len(nb-pb2)/len(nb):.4f}")
