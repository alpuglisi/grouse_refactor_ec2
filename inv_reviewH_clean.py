"""Reviewer H: does CR-0008's scoped generator fix (_clean mask-aware only)
actually make the four TreeMap channels nodata-aware?"""
import numpy as np, warnings
from models import qmd_from_balive_tpa, treemap_encode, tpa_live_encode

SENT = -9999.0
NODATA_FLOOR = 1e9

def clean_v2(arr):
    """Hypothetical 'mask-aware' _clean per CR-0008 deliverable: propagate
    nodata as NaN instead of clamping to 0."""
    a = np.asarray(arr, dtype=np.float64).copy()
    bad = (~np.isfinite(a)) | (a >= NODATA_FLOOR) | (a < 0)
    a[bad] = np.nan
    return a

# one pixel outside coverage (sentinel in every raw band), one real forest px,
# one real in-CONUS non-forest px (Branch A: must stay 0)
balive_raw = np.array([SENT, 120.0, 0.0])
tpa_raw    = np.array([SENT, 300.0, 0.0])
cdwn_raw   = np.array([SENT,   4.0, 0.0])

b, t, c = clean_v2(balive_raw), clean_v2(tpa_raw), clean_v2(cdwn_raw)
print("after mask-aware _clean:  balive", b, " tpa", t, " carbon_dwn", c)

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    q = qmd_from_balive_tpa(b, t)
    print("qmd native units       :", q, "   <-- pixel 0 SHOULD be nan")
    enc = {"balive": treemap_encode("balive", b),
           "qmd": treemap_encode("qmd", q),
           "carbon_dwn": treemap_encode("carbon_dwn", c),
           "tpa_live": tpa_live_encode(t)}
    for k, v in enc.items():
        print(f"  encoded int16 {k:11s}: {v}")
    print("  warnings raised:", [str(x.message)[:60] for x in w])

print()
print("NOW: what if _clean passes the NEGATIVE sentinel through unchanged")
print("     (the literal reading of 'propagate nodata') instead of NaN?")
def clean_passthrough(arr):
    a = np.asarray(arr, dtype=np.float64).copy()
    a[~np.isfinite(a)] = SENT
    a[a >= NODATA_FLOOR] = SENT
    return a
b2 = clean_passthrough(balive_raw)
print("  balive after:", b2, "-> encoded:", treemap_encode("balive", b2))
