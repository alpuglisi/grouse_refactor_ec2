"""FORMAL D / CR-0008 G2' N_pre: independent per-year reproduction.
|changed| = #(outside that feature's OWN pinned coverage AND value not already
a NODATA_SENTINEL).  Also reports nodata-inside-coverage (the over-masking
direction the CR asserts is 0 for every in-scope feature-year).  READ-ONLY."""
import glob, re, sys, numpy as np, rasterio
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
SENT = (-9999, -32768, 32767, -1111)
NPRE = {('tsd','ME'):96300932,('tsd','NH'):5663604,('tsd','VT'):2104152,
        ('tree','ME'):96215819,('tree','NH'):5659263,('tree','VT'):2100649,
        ('tcc','ME'):95946265,('tcc','NH'):5653164,('tcc','VT'):2096352,
        ('road_dist','ME'):96180811,('road_dist','NH'):0,('road_dist','VT'):2100978}
reg = sys.argv[1]
cov_d = np.load(f"{SCRATCH}/covD_{reg}_2025.npy")
with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
    cov_n = s.read(1) != -9999
print(f"==== {reg}  outside_nlcd={int((~cov_n).sum()):,}  outside_dist={int((~cov_d).sum()):,}")
for feat in ['tsd','balive','tpa_live','qmd','carbon_dwn','tcc']:
    cov = cov_d if feat=='tsd' else cov_n
    key = 'tsd' if feat=='tsd' else ('tcc' if feat=='tcc' else 'tree')
    npre = NPRE[(key,reg)]
    print(f"  {feat:11s} N_pre(pinned)={npre:,}")
    for p in sorted(glob.glob(f"data/landfire/{reg}_*_{feat}.tif")):
        yr = re.search(r'_(\d{4})_',p).group(1)
        with rasterio.open(p) as s: a = s.read(1)
        isnd = np.isin(a, SENT)
        chg = int((~cov & ~isnd).sum()); ndin = int((cov & isnd).sum())
        print(f"    {yr} |changed|={chg:>12,} delta={chg-npre:>+9,} "
              f"nodata_inside_cov={ndin:>9,}"
              + ("" if chg==npre else "   <-- G2' EQUALITY FAILS"))
        del a, isnd
