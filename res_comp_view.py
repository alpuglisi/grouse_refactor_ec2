import sys, pandas as pd, numpy as np
from pandas.api.types import is_numeric_dtype, is_bool_dtype
pd.set_option('display.width',300); pd.set_option('display.max_columns',90); pd.set_option('display.max_rows',300)
d=pd.read_csv(sys.argv[1])
num=[c for c in d.columns if (is_numeric_dtype(d[c]) or is_bool_dtype(d[c])) and c!='seed']
for c in num: d[c]=d[c].astype(float)
if 'attack' in d:
    print("--- MEDIAN by attack ---"); print(d.groupby('attack')[num].median().round(4).T)
    print("\n--- MIN by attack ---"); print(d.groupby('attack')[num].min().round(4).T)
    print("\n--- MAX by attack ---"); print(d.groupby('attack')[num].max().round(4).T)
else:
    print(d[num].describe(percentiles=[.01,.5,.95,.99]).T.round(5))
