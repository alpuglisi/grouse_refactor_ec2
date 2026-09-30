"""ATTACK on the v3 design (I1-I15 + (a)-(d)).
I14 whitelists PARAMETERS (spacing, block size, origin, seed, val fraction).
The block-SELECTION PROCEDURE is code, not a parameter, so it is outside
the whitelist.  Attack: pick val blocks only from the eastern half of each
region, seed-varying, occupancy-matched, per-region exactly 20%."""
import pandas as pd, numpy as np
import prepare_training_data as P
R=["ME","NH","VT"]
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R}
a=pd.concat([ev[r] for r in R],ignore_index=True)
own=a[(~a['nonveg_landcover'].astype(bool))&(a.state==a._reg)].drop_duplicates(subset=['longitude','latitude'])
base=P.thin_by_min_distance(own,30,42).reset_index(drop=True)
SZ=3000.0
base['blk']=[f"{x}_{y}" for x,y in zip(np.floor(base.x_5070/SZ).astype(int),np.floor(base.y_5070/SZ).astype(int))]

def correct(seed,vf=0.2):
    bc=base['blk'].value_counts()
    order=bc.sample(frac=1,random_state=seed).index.tolist()
    t=int(round(vf*len(base))); vb=set(); run=0
    for b in order:
        if run>=t: break
        vb.add(b); run+=bc[b]
    return vb

def attack_east(seed,vf=0.2):
    """per region: val blocks drawn ONLY from the eastern half, 20% of that
    region's records, uniformly at random among eligible blocks."""
    vb=set(); rng=np.random.default_rng(seed)
    for r in R:
        sub=base[base.state==r]
        bc=sub['blk'].value_counts()
        bx=pd.Series({b:int(b.split('_')[0]) for b in bc.index})
        cut=bx.median()
        elig=[b for b in bc.index if bx[b]>=cut]
        rng.shuffle(elig)
        t=int(round(vf*len(sub))); run=0
        for b in elig:
            if run>=t: break
            vb.add(b); run+=bc[b]
    return vb

def score(tag,vb,seedpair=None):
    sp=base['blk'].map(lambda b:'val' if b in vb else 'train')
    nb=base['blk'].nunique()
    blkf=100*len(vb)/nb; recf=100*(sp=='val').mean()
    per={r:100*(sp[base.state==r]=='val').mean() for r in R}
    worst=max(abs(per[r]-20) for r in R)
    v=base[sp=='val']; t=base[sp=='train']
    print(f"{tag}")
    print(f"   I6 {len(base)} | I7 pooled {recf:5.2f}%  per-region ME {per['ME']:5.2f} NH {per['NH']:5.2f} VT {per['VT']:5.2f}"
          f"  worst dev {worst:4.2f} pp  [I7 gate +/-2pp: {'PASS' if worst<=2 else 'FAIL'}]")
    print(f"   I15 block-frac {blkf:5.2f}% vs record-frac {recf:5.2f}% = {abs(blkf-recf):4.2f} pp "
          f"[gate 1pp: {'PASS' if abs(blkf-recf)<=1 else 'FAIL'}]   rec/valblk {len(v)/len(vb):.2f}")
    g=base.groupby('blk')['blk'].count(); both=sum(1 for b in base['blk'].unique()
        if len(set(sp[base['blk']==b]))>1)
    print(f"   I2/(c) blocks holding both splits: {both} [PASS]" if both==0 else f"   I2/(c): {both} FAIL")
    if seedpair: print(f"   I14(ii) val set seed{seedpair[0]} == seed{seedpair[1]}? {seedpair[2]} "
                       f"[{'FAIL' if seedpair[2] else 'PASS'}]")
    # the harm nothing measures
    for r in R:
        vr=v[v.state==r]; tr=t[t.state==r]
        print(f"      {r}: val lon [{vr.longitude.min():.3f},{vr.longitude.max():.3f}] "
              f"train lon [{tr.longitude.min():.3f},{tr.longitude.max():.3f}] | "
              f"val median lon {vr.longitude.median():.3f} vs train {tr.longitude.median():.3f} "
              f"(shift {vr.longitude.median()-tr.longitude.median():+.3f} deg)")
    print()

print("pooled positives:",len(base),"occupied blocks:",base['blk'].nunique(),"\n")
score("CORRECT draw, seed 42",correct(42),(42,7,correct(42)==correct(7)))
score("ATTACK  eastern-half val blocks, seed 42",attack_east(42),(42,7,attack_east(42)==attack_east(7)))
score("ATTACK  eastern-half val blocks, seed 7",attack_east(7))
