import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd
R=['ME','NH','VT']
tot_b=tot_lost=0
for r in R:
    d=pd.concat([pd.read_csv(f'data/pipeline/{p}_positives_{r}.csv') for p in ['train','val']],ignore_index=True)
    all_b=set(d['block_id']); keep_b=set(d.loc[d['year']>=2020,'block_id'])
    lost=all_b-keep_b
    print(f"{r}: occupied 3km blocks (positives) {len(all_b)} -> {len(keep_b)} after year-gap filter; "
          f"{len(lost)} blocks ({100*len(lost)/len(all_b):.1f}%) lose all positives")
    # do those blocks still have negatives?
    n=pd.concat([pd.read_csv(f'data/negatives/{p}_negatives_{r}.csv') for p in ['train','val']],ignore_index=True)
    nb=set(n['block_id'])
    print(f"    of those {len(lost)} emptied blocks, {len(lost & nb)} still contain negatives "
          f"(positive-free blocks with negatives = one-sided support)")
    tot_b+=len(all_b); tot_lost+=len(lost)
print(f"POOLED: {tot_lost}/{tot_b} = {100*tot_lost/tot_b:.1f}% of positive-occupied blocks emptied by the filter")
