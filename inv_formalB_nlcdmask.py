"""Formal review B / CR-0008 G0: reproduce the pre-registered `nlcd` masks.
Tries several defensible recipes and all years, prints inside-count and
sha256(packbits(mask.ravel()))[:32] for each.  READ-ONLY."""
import hashlib, glob, numpy as np, rasterio

EXPECT = {
 ('ME','nlcd'): (107406613, '59a7639b5fb0389d0955eb61e45ad3fc'),
 ('NH','nlcd'): ( 51384193, '15375b62cca9ab85ec4c23869218a6d7'),
 ('VT','nlcd'): ( 50450696, '682ef390d584a2a7b30b3eed10c75e15'),
}
SENT = (-9999, -32768, 32767, -1111)

def dig(m):
    return hashlib.sha256(np.packbits(m.ravel())).hexdigest()[:32]

for reg in ['ME','NH','VT']:
    want_n, want_h = EXPECT[(reg,'nlcd')]
    print(f"=== {reg}  expect inside={want_n:,} sha={want_h}")
    for p in sorted(glob.glob(f"data/landfire/{reg}_*_nlcd.tif")):
        yr = p.split('_')[1]
        with rasterio.open(p) as s:
            a = s.read(1)
        recipes = {
          'ne_-9999'   : a != -9999,
          'not_sent'   : ~np.isin(a, SENT),
          '11..95'     : (a >= 11) & (a <= 95),
          'gt0'        : a > 0,
        }
        for k, m in recipes.items():
            n = int(m.sum()); h = dig(m)
            flag = ''
            if n == want_n: flag += ' COUNT-MATCH'
            if h == want_h: flag += ' SHA-MATCH'
            print(f"  {yr} {k:9s} inside={n:>12,} sha={h}{flag}")
        del a, recipes
