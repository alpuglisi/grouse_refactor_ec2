import pandas as pd, glob, re, os
rows=[]
for f in sorted(glob.glob("data/sightings/*_sightings_*.csv")):
    m=re.match(r"^([A-Za-z]{2})_sightings_(\d{4})\.csv$",os.path.basename(f)); d=pd.read_csv(f)
    lon=next(c for c in d.columns if 'lon' in c.lower()); lat=next(c for c in d.columns if 'lat' in c.lower())
    rows.append(pd.DataFrame({'lon':d[lon],'lat':d[lat],'st':m.group(1).upper()}))
s=pd.concat(rows,ignore_index=True).dropna()
print(s.groupby('st').agg(min_lon=('lon','min'),max_lon=('lon','max'),min_lat=('lat','min'),max_lat=('lat','max')).round(4).to_string())
from regions import BOXES
print("\nBOXES:",BOXES)
print("regions.py NOTE asks: is NH max_lon -70.600 >= real NH max sighting lon?",
      s[s.st=='NH'].lon.max(), "->", s[s.st=='NH'].lon.max() <= -70.600)
