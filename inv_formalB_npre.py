"""Formal review B / CR-0008 G2': is N_pre really constant across years?
G2' pre-registers ONE must-change count per (feature, region), labelled
'(per year)', and demands |changed| == N_pre exactly, per file.
|changed| = #(outside-coverage AND currently-not-nodata).
Also reports #(nodata inside coverage), which the CR asserts is 0 for every
in-scope feature-year.  READ-ONLY."""
import glob, sys, numpy as np, rasterio

NPRE = {  # CR-0008 G2' table
 ('tsd','ME'):96300932, ('tsd','NH'):5663604, ('tsd','VT'):2104152,
 ('tree','ME'):96215819, ('tree','NH'):5659263, ('tree','VT'):2100649,
 ('tcc','ME'):95946265, ('tcc','NH'):5653164, ('tcc','VT'):2096352,
 ('road_dist','ME'):96180811, ('road_dist','NH'):0, ('road_dist','VT'):2100978,
}
SENT = (-9999,-32768,32767,-1111)
regions = sys.argv[1:] or ['NH','VT','ME']
for reg in regions:
    cov_dist = np.load(f"inv_formalB_cov_{reg}_2025.npy")
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        cov_nlcd = s.read(1) != -9999
    print(f"\n======== {reg}: outside_nlcd={int((~cov_nlcd).sum()):,} "
          f"outside_dist={int((~cov_dist).sum()):,}")
    for feat in ['tsd','balive','tpa_live','qmd','carbon_dwn','tcc']:
        cov = cov_dist if feat == 'tsd' else cov_nlcd
        key = 'tsd' if feat=='tsd' else ('tcc' if feat=='tcc' else 'tree')
        npre = NPRE[(key,reg)]
        rows=[]
        for p in sorted(glob.glob(f"data/landfire/{reg}_*_{feat}.tif")):
            yr = p.split('_')[1]
            with rasterio.open(p) as s:
                a = s.read(1); nd = s.nodata
            isnd = np.isin(a, SENT)
            chg = int((~cov & ~isnd).sum())
            ndin = int((cov & isnd).sum())
            rows.append((yr, chg, ndin, nd, chg-npre))
            del a, isnd
        print(f"  {feat:11s} N_pre={npre:,}")
        for yr,chg,ndin,nd,d in rows:
            print(f"    {yr}  |changed|={chg:>12,}  delta_vs_Npre={d:>+10,}"
                  f"  nodata_inside_cov={ndin:>10,}  tag_nodata={nd}"
                  f"{'' if d==0 else '   <-- G2-prime EQUALITY FAILS'}")
        del rows
    del cov_dist, cov_nlcd
