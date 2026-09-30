"""Formal review B: verify CR-0008's tsd keystone claim about the 26 value
attribute tables: -9999 Fill-NoData in all, -1111 Fill-Not-Mapped in 6
(LF2020_Dist17-20, LF2022_Dist21-22), 0 Background in all, 32767/-32768 in
none.  READ-ONLY."""
import csv, glob, os, re
paths = sorted(p for p in glob.glob(
  "data/disturbance/USAnnualDisturbance_1999_present/*/*/CSV_Data/*.csv"))
print("tables found:", len(paths))
has = {}
for p in paths:
    name = os.path.basename(p)[:-4]
    with open(p, newline='') as f:
        rows = list(csv.reader(f))
    hdr = rows[0]
    vals = {}
    for r in rows[1:]:
        if not r: continue
        try: v = int(float(r[0]))
        except Exception: continue
        vals[v] = r
    has[name] = (hdr, vals)
    print(f"{name:20s} nrows={len(rows)-1:4d} hdr={','.join(hdr)}")
print()
for key in (-9999, -1111, 0, 32767, -32768, -1):
    yes = [n for n,(h,v) in has.items() if key in v]
    print(f"VALUE {key:>7}: present in {len(yes):2d}/{len(has)} tables  {sorted(yes) if 0<len(yes)<=8 else ''}")
print()
print("label text for the special codes, per table:")
for n in sorted(has):
    h,v = has[n]
    bits=[]
    for key in (-9999,-1111,0):
        if key in v:
            row=v[key]
            lbl=" | ".join(x for x in row[1:] if x.strip())
            bits.append(f"{key}:[{lbl[:60]}]")
    print(f"  {n:20s} {'  '.join(bits)}")
