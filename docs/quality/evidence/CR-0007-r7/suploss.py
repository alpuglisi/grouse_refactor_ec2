import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
exec(open("window_sup.py").read().split("pool['win'] = True")[0].split("HALF = 32")[0])
from window_sup import sup  # noqa
