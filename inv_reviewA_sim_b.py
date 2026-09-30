"""What the implementation described in CR-0006 section 3 would actually produce:
pool evaluated_sightings (state-partitioned) -> dedup -> thin ONCE at 30 m ->
one global 3 km grid -> one draw.  Compare with the CR's acceptance numbers."""
import numpy as np, pandas as pd, geopandas as gpd
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]; FIPS={"23":"ME","33":"NH","50":"VT"}
BLOCK_M,VAL_FRAC,SEED,MINSP=3000,0.2,42,30
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
cty=cty[cty.STATEFP.isin(FIPS)].dissolve(by="STATEFP").reset_index().to_crs("EPSG:4326")
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in R}
for r in R: print(r,"evaluated rows",len(ev[r]),"habitat rows",int((~ev[r]['nonveg_landcover'].astype(bool)).sum()))
allev=pd.concat([ev[r].assign(src=r) for r in R],ignore_index=True)
allev["key"]=allev.longitude.round(5).astype(str)+","+allev.latitude.round(5).astype(str)
g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(allev.longitude,allev.latitude),crs="EPSG:4326")
j=gpd.sjoin(g,cty[["STATEFP","geometry"]],how="left",predicate="within"); j=j[~j.index.duplicated()]
allev["state"]=j.STATEFP.map(FIPS).values
print("\npooled evaluated rows",len(allev),"unique coords",allev.key.nunique(),"no-state",int(allev.state.isna().sum()))
# coverage: is every state-X record present in region X's own evaluated file?
for st in R:
    s=allev[allev.state==st]
    own=set(s[s.src==st].key); alll=set(s.key)
    print(f"  {st}: unique coords tagged {st} anywhere={len(alll)}, present in evaluated_sightings_{st}={len(own)}, LOST by partition={len(alll-own)}")
    if alll-own:
        ex=s[s.key.isin(list(alll-own)[:5])][['longitude','latitude','src','nonveg_landcover']]
        print(ex.to_string())
# partitioned pool: take the row from region==state
part=allev[allev.state==allev.src].copy()
print("\npartitioned pooled rows (state==src):",len(part),"unique coords",part.key.nunique())
hab=part[~part['nonveg_landcover'].astype(bool)].copy()
hab=hab.drop_duplicates("key")
print("habitat, deduped:",len(hab))
to5070=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
hx,hy=to5070.transform(hab.longitude.values,hab.latitude.values)
hab["x_5070"],hab["y_5070"]=hx,hy
def thin(df,min_m,seed):
    rng=np.random.default_rng(seed); order=rng.permutation(len(df))
    coords=df[['x_5070','y_5070']].values[order]
    kept=np.zeros(len(df),bool); kc=[]; tree=None
    for i,pt in enumerate(coords):
        keep = True if (tree is None or not kc) else (tree.query(pt,k=1)[0]>=min_m)
        if keep:
            kc.append(pt); kept[order[i]]=True; tree=cKDTree(np.array(kc))
    return df[kept].copy()
thinned=thin(hab,MINSP,SEED)
print(f"\nGLOBAL thin at {MINSP} m: {len(hab)} -> {len(thinned)} kept")
print("  by state:",thinned.state.value_counts().to_dict())
df=thinned
df["gblock"]=np.floor(df.x_5070/BLOCK_M).astype(int).astype(str)+"_"+np.floor(df.y_5070/BLOCK_M).astype(int).astype(str)
counts=df.gblock.value_counts(); order=counts.sample(frac=1,random_state=SEED).index.tolist()
target=int(round(VAL_FRAC*len(df))); vb=set(); run=0
for b in order:
    if run>=target: break
    vb.add(b); run+=counts[b]
df["new_split"]=np.where(df.gblock.isin(vb),"val","train")
tr=df[df.new_split=="train"]; va=df[df.new_split=="val"]
print(f"\nCR-section-3 pipeline result: pooled positives {len(df)}  occupied blocks {len(counts)}  val blocks {len(vb)}  val records {len(va)} ({len(va)/len(df):.1%})")
print(f"  coords in both: {len(set(tr.key)&set(va.key))}")
d,_=cKDTree(tr[['x_5070','y_5070']].values).query(va[['x_5070','y_5070']].values,k=1)
for m in (30,300,3000): print(f"  val with train pos within {m:>5} m: {(d<=m).mean():6.2%}")
print("  val by state:",va.state.value_counts().to_dict())
print("\nCR acceptance numbers were: 6712 positives / 4069 blocks / 1344 val (20.0%) / 0.0,1.3,64.4%")
