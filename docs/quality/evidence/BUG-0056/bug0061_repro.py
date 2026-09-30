"""BUG-0061 reproduction: GrouseModelHandler._log_metrics (called verbatim)
appending a row whose key set differs from the header written by an
earlier run. Case A: earlier run had `dropout` (--dynamic-dropout), later
run does not -> values shift left under the old header, file still parses.
Case B: the reverse -> one extra field, the file no longer parses.
Run from the repo root: python docs/quality/evidence/BUG-0056/bug0061_repro.py
Writes only to a temporary directory."""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.getcwd())
from model_handler import GrouseModelHandler  # noqa: E402

log = GrouseModelHandler._log_metrics
with tempfile.TemporaryDirectory() as d:
    a = os.path.join(d, "a.csv")
    log(a, {"epoch": 1, "val_loss": 0.50, "dropout": 0.20, "auc": 0.70})
    log(a, {"epoch": 1, "val_loss": 0.40, "auc": 0.80})
    print("Case A file:\n" + open(a).read())
    print(pd.read_csv(a).to_string())
    print("-> run 2's row: auc 0.80 correct, but epoch 1 lands under "
          "'dropout', val_loss 0.40 under 'epoch', and val_loss reads NaN "
          "(every column after the missing key shifts left).\n")
    b = os.path.join(d, "b.csv")
    log(b, {"epoch": 1, "val_loss": 0.50, "auc": 0.70})
    log(b, {"epoch": 1, "val_loss": 0.40, "dropout": 0.20, "auc": 0.80})
    print("Case B file:\n" + open(b).read())
    try:
        pd.read_csv(b)
        print("parsed")
    except Exception as e:
        print(f"pd.read_csv fails: {type(e).__name__}: {e}")
