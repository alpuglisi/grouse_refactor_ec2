"""Fast exact-equivalent reimplementation of
prepare_training_data.thin_by_min_distance, for formal-review measurement.
Read-only helper; writes nothing."""
import numpy as np
from scipy.spatial import cKDTree


def fast_thin_mask(xy, m, seed):
    n = len(xy)
    if n == 0:
        return np.zeros(0, bool)
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    tree = cKDTree(xy)
    pairs = tree.query_pairs(m, output_type='ndarray')
    if len(pairs):
        d = np.linalg.norm(xy[pairs[:, 0]] - xy[pairs[:, 1]], axis=1)
        pairs = pairs[d < m]          # original rejects only on dist < m
    nb = [[] for _ in range(n)]
    for i, j in pairs:
        nb[i].append(j)
        nb[j].append(i)
    kept = np.zeros(n, bool)
    for pos in order:
        ok = True
        for j in nb[pos]:
            if kept[j]:
                ok = False
                break
        if ok:
            kept[pos] = True
    return kept


def fast_thin(df, m, seed):
    xy = df[['x_5070', 'y_5070']].values
    return df[fast_thin_mask(xy, m, seed)].copy()
