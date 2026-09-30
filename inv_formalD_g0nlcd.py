"""FORMAL D / CR-0008 G0: independently reproduce the pinned `nlcd` masks.
Digest = sha256(np.packbits(mask.ravel()))[:32]; predicate `!= -9999`.
Also tests alternate defensible predicates and every year on disk. READ-ONLY."""
import hashlib, glob, re, numpy as np, rasterio
PIN = {'ME': (107406613, 0.472521, '59a7639b5fb0389d0955eb61e45ad3fc'),
       'NH': ( 51384193, 0.099210, '15375b62cca9ab85ec4c23869218a6d7'),
       'VT': ( 50450696, 0.039973, '682ef390d584a2a7b30b3eed10c75e15')}
SENT = (-9999, -32768, 32767, -1111)
d = lambda m: hashlib.sha256(np.packbits(m.ravel())).hexdigest()[:32]
for reg,(wn,wf,wh) in PIN.items():
    print(f"=== {reg}: pinned inside={wn:,} outfrac={wf} sha={wh}")
    for p in sorted(glob.glob(f"data/landfire/{reg}_*_nlcd.tif")):
        yr = re.search(r'_(\d{4})_', p).group(1)
        with rasterio.open(p) as s:
            a = s.read(1); n = a.size
        for name, m in (('!=-9999', a != -9999),
                        ('notsent', ~np.isin(a, SENT)),
                        ('11..95', (a>=11)&(a<=95)),
                        ('>0', a > 0)):
            c = int(m.sum()); h = d(m)
            tag = ('COUNT' if c==wn else '     ') + ('+SHA' if h==wh else '    ')
            of = 1-c/n
            print(f"  {yr} {name:8s} inside={c:>12,} outfrac={of:.6f} sha={h} {tag}"
                  + ('  OUTFRAC-MATCH' if abs(of-wf)<5e-7 else ''))
            del m
        del a
