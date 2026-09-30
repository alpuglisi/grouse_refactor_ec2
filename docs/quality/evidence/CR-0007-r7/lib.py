import hashlib, numpy as np, pandas as pd
from scipy.spatial import cKDTree
OUT = "/tmp/claude-1000/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/scratchpad/cr0007_A"
R = ["ME", "NH", "VT"]
RF = 1920.0

def bid(x, y, B=3000.0):
    return np.array([f"{a}_{b}" for a, b in zip(np.floor(x / B).astype(int), np.floor(y / B).astype(int))])

def split_positives(pos, seed=42, vf=0.2):
    b = pd.Series(bid(pos.x_5070.values, pos.y_5070.values), index=pos.index)
    bc = b.value_counts()
    sh = bc.sample(frac=1, random_state=seed).index.tolist()
    tgt = int(round(vf * len(pos))); val, run = set(), 0
    for k in sh:
        if run >= tgt: break
        val.add(k); run += bc[k]
    pos = pos.copy(); pos['block_id'] = b.values
    pos['split'] = np.where(b.isin(val), 'val', 'train')
    return pos

def hsplit(b, vf, seed):
    h = int(hashlib.md5(f"{seed}:{b}".encode()).hexdigest(), 16)
    return 'val' if (h % 10_000) < vf * 10_000 else 'train'

def assign_neg_split(pool, pos, seed=42):
    pool = pool.copy()
    pool['block_id'] = bid(pool.x_5070.values, pool.y_5070.values)
    blocks = pos.drop_duplicates('block_id')[['block_id', 'split']]
    bs = dict(zip(blocks.block_id, blocks.split))
    vf = (blocks.split == 'val').mean()
    pool['split'] = [bs.get(b) or hsplit(b, vf, seed) for b in pool.block_id]
    return pool

def draw(pool, pos, seed, replace=False, nonveg_frac=0.30):
    rng = np.random.default_rng(seed)
    picked = []
    for r in R:
        for s in ['train', 'val']:
            nt = int(((pos.state == r) & (pos.split == s)).sum())
            pl = pool[(pool.state == r) & (pool.split == s)]
            nv = pl[pl.is_nonveg]; hb = pl[~pl.is_nonveg]
            nnv = min(int(round(nt * nonveg_frac)), len(nv)); nh = nt - nnv
            def take(sp, n):
                if n <= 0 or len(sp) == 0: return sp.iloc[0:0]
                if len(sp) <= n and not replace: return sp
                p = sp.weight.values / sp.weight.sum()
                idx = rng.choice(np.arange(len(sp)), size=n, replace=replace, p=p)
                return sp.iloc[idx]
            th = take(hb, nh); sf = nh - len(th)
            if sf > 0: nnv = min(nnv + sf, len(nv))
            tn = take(nv, nnv)
            g = pd.concat([th, tn], ignore_index=True); g['region'] = r
            picked.append(g)
    return pd.concat(picked, ignore_index=True)

def i19(pos, neg):
    out = {}
    for r in R:
        p = pos[pos.state == r]; n = neg[neg.state == r]
        d = cKDTree(n[['x_5070', 'y_5070']].values).query(p[['x_5070', 'y_5070']].values)[0]
        out[f'S_{r}'] = float((d > RF).mean())
        out[f'Exc_{r}'] = float(np.maximum(0, d - RF).mean() / 1000)
        pv = p[p.split == 'val']; nv = n[n.split == 'val']
        dv = cKDTree(nv[['x_5070', 'y_5070']].values).query(pv[['x_5070', 'y_5070']].values)[0]
        out[f'Sws_{r}'] = float((dv > RF).mean())
        out[f'Excws_{r}'] = float(np.maximum(0, dv - RF).mean() / 1000)
    return out
