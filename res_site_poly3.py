import time, resource, geopandas as gpd
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0
t=time.perf_counter()
c = gpd.read_file("data/roads/tl_2023_us_county.zip",
                  columns=["STATEFP","geometry"],
                  where="STATEFP IN ('23','33','50')", engine="pyogrio")
print(f"read_file with where= : {1000*(time.perf_counter()-t):.0f} ms, {len(c)} rows, maxRSS {rss():.0f} MB")
t=time.perf_counter()
st=c.dissolve(by="STATEFP")
print(f"dissolve: {1000*(time.perf_counter()-t):.0f} ms, maxRSS {rss():.0f} MB")
