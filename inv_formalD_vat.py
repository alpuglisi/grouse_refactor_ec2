"""FORMAL D / CR-0008 § Coverage: verify the VAT claims that make `tsd`
coverage derivable -- 26 tables, all declare -9999 and 0; 6 declare -1111;
none declares 32767 or -32768; three header schemas; LF2024_Dist24 has a BOM."""
import glob, os, csv, re
ps = sorted(glob.glob("data/disturbance/USAnnualDisturbance_1999_present/"
                      "LF*/LF*/CSV_Data/*.csv"))
print(f"{len(ps)} VAT files (outer copy)")
n1111 = []; schemas = {}; bom = []
for p in ps:
    raw = open(p,'rb').read(3)
    has_bom = raw == b'\xef\xbb\xbf'
    with open(p, newline='', encoding='utf-8') as f:
        rd = csv.reader(f); hdr = next(rd)
        vals = set()
        for row in rd:
            if row and row[0].strip(): 
                try: vals.add(int(float(row[0])))
                except ValueError: pass
    key = ",".join(h.strip().lstrip('﻿') for h in hdr[:5])
    schemas.setdefault(key, []).append(os.path.basename(p))
    if has_bom: bom.append(os.path.basename(p))
    flags = []
    for v in (-9999, 0, -1111, 32767, -32768):
        if v in vals: flags.append(v)
    if -1111 in vals: n1111.append(os.path.basename(p))
    miss = [v for v in (-9999,0) if v not in vals]
    bad  = [v for v in (32767,-32768) if v in vals]
    print(f"  {os.path.basename(p):24s} bom={has_bom!s:5s} declares={flags}"
          + (f"  MISSING{miss}" if miss else "") + (f"  HAS SENTINEL{bad}" if bad else ""))
print(f"\n-1111 declared in {len(n1111)} tables: {sorted(n1111)}")
print(f"BOM in: {bom}")
print(f"{len(schemas)} distinct header schemas:")
for k,v in schemas.items(): print(f"   {k}   <- {len(v)} files, e.g. {v[0]}")
