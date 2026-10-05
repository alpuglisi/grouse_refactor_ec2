import sys
v = sys.argv[1]; p = "train.py"; s = open(p).read()
LOOP = """    for y, n in want.items():
        df = sample_background_points(
            rd, features, n, seed=(int(seed), int(region_i), y),
            region=region, train_blocks_only=True, year=y,
            assignments=assignments, in_state=in_state)
        acc.append(df.attrs.get("acceptance"))
        parts.append(df)
"""
ONE = """    if want:
        df = sample_background_points(
            rd, features, sum(want.values()), seed=(int(seed), int(region_i)),
            region=region, train_blocks_only=True, year="latest",
            assignments=assignments, in_state=in_state)
"""
def rep(a, b):
    global s
    assert s.count(a) == 1, (v, a)
    s = s.replace(a, b)
if v == "i":
    rep(LOOP, ONE + """        acc.append(df.attrs.get("acceptance"))
        parts.append(df)
""")
elif v == "iv":
    rep(LOOP, ONE + """        df["year"] = [y for y, n in want.items() for _ in range(n)]
        acc.append(df.attrs.get("acceptance"))
        parts.append(df)
""")
elif v == "ii":
    rep("        path = rd.raster_path(feat, year)   # = dataset.py's per-row resolver",
        "        path = rd.latest_raster_path(feat)")
elif v == "iii":
    rep("train_blocks_only, year, assignments=None,", 'train_blocks_only, year="latest", assignments=None,')
elif v == "v":
    rep('                rd, features, pos_df["year"], background_per_pos,',
        '                rd, features, neg_df["year"], background_per_pos,')
elif v == "x1":
    rep("        path = rd.raster_path(feat, year)   #", "        path = rd.raster_path(feat, year, validate=False)   #")
elif v == "x2":
    rep("        path = rd.raster_path(feat, year)   #", '        path = rd.path("raster", feature=feat, year=year)   #')
open(p, "w").write(s)
