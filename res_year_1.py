import pandas as pd, glob, os, collections
os.chdir('/home/ec2-user/grouse2')
R=['ME','NH','VT']
def dist(p):
    df=pd.read_csv(p)
    if 'year' not in df.columns: return None,None
    return len(df), df['year'].value_counts(dropna=False).sort_index()

print("=== POSITIVES (train/val) ===")
allpos=[]
for kind in ['train_positives','val_positives']:
    for r in R:
        p=f'data/pipeline/{kind}_{r}.csv'
        df=pd.read_csv(p); df['_kind']=kind; df['_region']=r; allpos.append(df)
        print(kind,r,len(df), dict(df['year'].value_counts(dropna=False).sort_index()))
P=pd.concat(allpos,ignore_index=True)
print("POS TOTAL",len(P))
print(P['year'].value_counts(dropna=False).sort_index())
print("pre2020 pos:",int((P['year']<2020).sum()), "=%.2f%%"%(100*(P['year']<2020).mean()))
print("NaN year pos:",int(P['year'].isna().sum()))

print()
print("=== NEGATIVES (train/val) ===")
allneg=[]
for kind in ['train_negatives','val_negatives']:
    for r in R:
        p=f'data/negatives/{kind}_{r}.csv'
        df=pd.read_csv(p); df['_kind']=kind; df['_region']=r; allneg.append(df)
        print(kind,r,len(df), dict(df['year'].value_counts(dropna=False).sort_index()))
N=pd.concat(allneg,ignore_index=True)
print("NEG TOTAL",len(N))
print(N['year'].value_counts(dropna=False).sort_index())
print("pre2020 neg:",int((N['year']<2020).sum()))
print("NaN year neg:",int(N['year'].isna().sum()))

print()
print("=== GBIF candidate pool ===")
for r in R:
    df=pd.read_csv(f'data/negatives/gbif_negatives_{r}.csv')
    print(r,len(df), dict(df['year'].value_counts(dropna=False).sort_index()))

print()
print("=== negatives_{r}.csv (pre-split) ===")
for r in R:
    df=pd.read_csv(f'data/negatives/negatives_{r}.csv')
    print(r,len(df), dict(df['year'].value_counts(dropna=False).sort_index()))

print()
print("=== upstream positives: evaluated / thinned ===")
for kind,base in [('evaluated','data/pipeline/evaluated_sightings_%s.csv'),('thinned','data/pipeline/thinned_positives_%s.csv')]:
    for r in R:
        df=pd.read_csv(base%r)
        yc = dict(df['year'].value_counts(dropna=False).sort_index()) if 'year' in df.columns else 'NOYEARCOL'
        print(kind,r,len(df),yc)
