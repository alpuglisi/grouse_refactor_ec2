"""ATTACK C: bias the NEGATIVE split inside positive-free blocks.

Everything about the positive side is the intended CR-0007 pipeline: one global
grid on BLOCK_ORIGIN_5070, one pooled thin, one fair block draw.  The only
change is the rule that splits the ~65 % of blocks that hold no positive: the
CR leaves that to `split_for_unassigned` (a hash).  Replace the hash with
"val iff the block centre is in the eastern half of its state" and the
validation negatives become a geographically distinct population from the
training negatives, while every positive-side statistic is untouched.

Scored against every GATE row in CR-0007 v5 § Acceptance that is computable
from the record CSVs.  READ-ONLY.
"""
import hashlib
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp

from inv_formalA_harness import R, BS, VF, SEED, blk, val_blocks_fair, hash_split

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
pos = pd.read_pickle(f"{SCR}/pos.pkl").copy()
cand = pd.read_pickle(f"{SCR}/cand.pkl").copy()
RF = 1920.0

vb = val_blocks_fair(pos, SEED)
pos['split'] = np.where(pos['blk'].isin(vb), 'val', 'train')
posblocks = set(pos['blk'].unique())
blocktab = {b: ('val' if b in vb else 'train') for b in posblocks}
gvf = len(vb) / len(posblocks)
targets = {(r, s): int(((pos.state == r) & (pos.split == s)).sum())
           for r in R for s in ('train', 'val')}

# eastern-half rule, a PURE FUNCTION OF THE BLOCK (so I2/I3 stay 0):
# rank positive-free blocks by block-x and take the easternmost ones as val,
# up to the same global val fraction the fair hash delivers.
cand['bx'] = np.floor(cand.x_5070.values / BS).astype(np.int64)
free = cand.loc[~cand['blk'].isin(posblocks), ['blk', 'bx']].drop_duplicates('blk')
n_val_free = int(round(gvf * len(free)))
attack_val_free = set(free.sort_values('bx', ascending=False).blk.values[:n_val_free])


def assign_neg_split(mode):
    out = []
    for b in cand['blk']:
        if b in blocktab:
            out.append(blocktab[b])                      # block-consistent: forced
        elif mode == 'fair':
            out.append(hash_split(b, gvf, SEED))
        else:
            out.append('val' if b in attack_val_free else 'train')
    return np.array(out)


def draw(nsplit, seed):
    rng = np.random.default_rng(seed)
    out = []
    for (r, s), n in targets.items():
        m = (cand.state.values == r) & (nsplit == s)
        pool = cand[m].assign(split=s)
        take = min(n, len(pool))
        out.append(pool.iloc[rng.choice(len(pool), size=take, replace=False)])
    return pd.concat(out, ignore_index=True)


def score(label, neg):
    rec = pd.concat([pos.assign(cls='pos')[['x_5070', 'y_5070', 'blk', 'split', 'state', 'cls']],
                     neg.assign(cls='neg')[['x_5070', 'y_5070', 'blk', 'split', 'state', 'cls']]],
                    ignore_index=True)
    print(f"\n########## {label} ##########")
    px = pos[['x_5070', 'y_5070']].values
    print(f"  I1  pooled positive pairs < 30 m ............ "
          f"{len(cKDTree(px).query_pairs(30.0, output_type='ndarray'))}  (require 0)")
    g = rec.groupby('blk')['split'].nunique()
    print(f"  I2  blocks holding both splits (recomputed) . {int((g > 1).sum())}  (require 0)")
    trb = set(rec.loc[rec.split == 'train', 'blk'])
    vn = rec[(rec.split == 'val') & (rec.cls == 'neg')]
    print(f"  I3  val negs whose block holds a train rec .. {100*vn.blk.isin(trb).mean():.2f}%  (require 0%)")
    for c in ('pos', 'neg'):
        s = rec[rec.cls == c]
        kt = set(map(tuple, np.round(s.loc[s.split == 'train', ['x_5070', 'y_5070']].values, 3)))
        kv = list(map(tuple, np.round(s.loc[s.split == 'val', ['x_5070', 'y_5070']].values, 3)))
        print(f"  I4  [{c}] 5dp train/val coord collisions .... {sum(1 for k in kv if k in kt)}  (require 0)")
    print(f"  I6  pooled positive count ................... {len(pos)}  (require 6230 +/- 10)")
    ok = all(int(((neg.state == r) & (neg.split == s)).sum()) == targets[(r, s)]
             for r in R for s in ('train', 'val'))
    print(f"  I8  exact per-(region,split) 1:1 ............ {'PASS' if ok else 'FAIL'}  "
          + str({f"{r}/{s}": int(((neg.state == r) & (neg.split == s)).sum())
                 for r in R for s in ('train', 'val')}))
    print(f"  I9  state partition, both classes ........... "
          f"pos out-of-state {int((pos.state.isin(R) == False).sum())}, "
          f"neg out-of-state {int((neg.state.isin(R) == False).sum())}  (require 0)")
    # I15 block-vs-record val fraction gap
    for tag, sub in (("pos", pos), ("pooled", rec)):
        bl = sub.drop_duplicates('blk')
        bfrac = 100 * (bl.split == 'val').mean()
        rfrac = 100 * (sub.split == 'val').mean()
        print(f"  I15 [{tag}] |block val% - record val%| ...... {abs(bfrac-rfrac):.3f} pp  (require <= 2.5)")
    # I16 Moran, on two candidate definitions of "the occupied-block set"
    for tag, sub in (("positive-occupied", pos), ("all-record-occupied", rec)):
        bl = sub.drop_duplicates('blk')[['blk', 'split']].copy()
        bl['cx'] = (bl.blk // 100000 + 0.5) * BS
        bl['cy'] = (bl.blk % 100000 + 0.5) * BS
        XY = bl[['cx', 'cy']].values
        y = (bl.split == 'val').values.astype(float)
        z = y - y.mean()
        for k in (4, 8):
            _, idx = cKDTree(XY).query(XY, k=k+1)
            idx = idx[:, 1:]
            I = (z[idx].mean(axis=1) * z).sum() / (z**2).sum()
            n = len(y)
            sd = 1.0 / np.sqrt(n)                      # ~Cliff-Ord scale
            print(f"  I16 [{tag:19}] Moran k={k} .. I={I:+.4f}  z~{(I+1/(n-1))/sd:+6.2f}  (gate z<=5)")
    # I18 median val -> nearest train, both readings
    for tag, sub in (("pos only", pos), ("pooled", rec)):
        t = sub[sub.split == 'train'][['x_5070', 'y_5070']].values
        v = sub[sub.split == 'val'][['x_5070', 'y_5070']].values
        d, _ = cKDTree(t).query(v, k=1)
        print(f"  I18 [{tag:8}] median val->nearest train .. {np.median(d)/1000:.3f} km  (fair [2.33,2.75])")
    # I19
    d, _ = cKDTree(neg[['x_5070', 'y_5070']].values).query(px, k=1)
    print(f"  I19 frac(pos->nearest-neg > 1920 m) ......... {(d>RF).mean():.4f}  (gate <= 0.55)")
    # the harm the gate set is supposed to notice
    for tag in ('neg', 'pos'):
        s = rec[rec.cls == tag]
        vx = s.loc[s.split == 'val', 'x_5070'].values
        tx = s.loc[s.split == 'train', 'x_5070'].values
        print(f"  HARM [{tag}] KS(val,train) on x_5070 ....... {ks_2samp(vx,tx).statistic:.3f}   "
              f"mean shift {(vx.mean()-tx.mean())/1000:+.1f} km")
    print(f"  HARM val-negative / val-positive x_5070 mean gap ... "
          f"{(rec[(rec.split=='val')&(rec.cls=='neg')].x_5070.mean() - rec[(rec.split=='val')&(rec.cls=='pos')].x_5070.mean())/1000:+.1f} km")


nf = assign_neg_split('fair')
na = assign_neg_split('attack')
print("negatives whose block holds NO positive (hash/attack-assigned): "
      f"{int((~cand['blk'].isin(posblocks)).sum())} of {len(cand)} candidates")
score("A: FAIR (hash for positive-free blocks)", draw(nf, 0))
score("B: ATTACK (eastern-half rule for positive-free blocks)", draw(na, 0))
