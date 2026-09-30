"""CR-0019 deliverable 4 combined check: acceptance_split.standing_checks
(the check train.build_datasets runs first) on the scratch tree after the
acceptance run, with train.py's defaults (IMG_SIZE, jitter 0, no augment).
Read-only.   cd SCRATCH && python .../standing_check.py
"""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
sys.path.insert(0, W)
import acceptance_split  # noqa: E402
import train  # noqa: E402

acceptance_split.standing_checks(train.IMG_SIZE, 0, False,
                                 data_root=os.path.abspath("."))
print(f"standing_checks PASS on {os.path.abspath('.')} (img_size {train.IMG_SIZE})")
