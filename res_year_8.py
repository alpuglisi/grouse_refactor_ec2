import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np
import importlib.util
spec=importlib.util.spec_from_file_location("ptd","prepare_training_data.py")
ptd=importlib.util.module_from_spec(spec); spec.loader.exec_module(ptd)
print("MIN_SPACING", ptd.MIN_SPACING_M_DEFAULT, "SEED", ptd.RANDOM_SEED_DEFAULT)
tot_cur=tot_new=0
for r in ['ME','NH','VT']:
    df=pd.read_csv(f'data/pipeline/evaluated_sightings_{r}.csv')
    df=df[~df['nonveg_landcover'].astype(bool)].copy()
    cur=ptd.thin_by_min_distance(df, ptd.MIN_SPACING_M_DEFAULT, ptd.RANDOM_SEED_DEFAULT)
    sub=df[df['year']>=2020].copy()
    new=ptd.thin_by_min_distance(sub, ptd.MIN_SPACING_M_DEFAULT, ptd.RANDOM_SEED_DEFAULT)
    cur_post=int((cur['year']>=2020).sum())
    print(f"{r}: veg evaluated n={len(df)} (pre2020={int((df['year']<2020).sum())})")
    print(f"   thinned ALL years  = {len(cur)}   of which >=2020: {cur_post}")
    print(f"   thinned 2020+ only = {len(new)}")
    print(f"   Option B loss vs current thinned total: {len(cur)-len(new)} "
          f"({100*(len(cur)-len(new))/len(cur):.2f}%)")
    print(f"   Option B vs current POST-year-gap positives ({cur_post}): {len(new)-cur_post:+d}")
    tot_cur+=len(cur); tot_new+=len(new)
print(f"\nPOOLED: current thinned {tot_cur}, 2020+-only thinned {tot_new}, delta {tot_new-tot_cur}")
