"""CR-0019 reviewer B: PA-0021(a) wrong-tree builder for check_must_change.py.

Written independently of preregister.py (does not import Floored): each
tree is CR-0013's replay (acceptance_split.Replay) subclassed at the one
place the tree is wrong, emitted with Replay.emit() into OUT/<name>.
Read-only on the repository; writes only under OUT (outside the repo).

    PYTHONPATH=. nice -n 10 python docs/quality/evidence/CR-0019/reviewB/build_trees.py OUT [name ...]
"""
import os
import sys

import numpy as np
import pandas as pd

import acceptance_split as A

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", "..", ".."))
YMIN = 2020


def floor(df, op=">="):
    y = df["year"]
    if y.isna().any():
        raise A.ReplayError("null year")
    y = y.astype(int)
    return df[(y >= YMIN) if op == ">=" else (y > YMIN) if op == ">" else (y >= YMIN - 1)].copy()


class Correct(A.Replay):
    """CR-0019 as written: step-2 floor (>= YEAR_MIN, raise on null) and the
    pool step-1 guard."""
    def habitat_rows(self, df):
        if df["year"].isna().any():
            raise A.ReplayError("sighting with null year")
        return floor(super().habitat_rows(df))

    def load_candidates(self):
        c = super().load_candidates()
        if c["year"].isna().any() or (c["year"] < YMIN).any():
            raise A.ReplayError("candidate year < YEAR_MIN")
        return c


class NoOp(A.Replay):
    pass


class OffByOne(A.Replay):
    def habitat_rows(self, df):
        return floor(super().habitat_rows(df), ">")


class Floor2019(A.Replay):
    def habitat_rows(self, df):
        return floor(super().habitat_rows(df), "2019")


class AfterThin(A.Replay):
    """Floor applied after thinning (pre-2020 thin winners still suppress
    their post-2020 neighbours); block split on the floored set."""
    def thin(self, lons, lats, xs, ys, frame=None):
        keep = super().thin(lons, lats, xs, ys, frame)
        if frame is not None and "n_visits" in frame.columns:      # positives
            keep = keep & (frame["year"].astype(int).to_numpy() >= YMIN)
        return keep


class SourceAll(A.Replay):
    """Floor at the source: evaluated_sightings floored for every consumer
    (positives, the 300 m buffer, the envelope binners)."""
    def sightings(self, R, section):
        return floor(super().sightings(R, section))


class SourceBuffer(A.Replay):
    """Correct positives, but the 300 m buffer uses only >= YEAR_MIN sightings."""
    def habitat_rows(self, df):
        return floor(super().habitat_rows(df))

    def all_sightings_xy(self):
        xs, ys = [], []
        for R in self.regions:
            S = floor(self.sightings(R, "negatives"))
            x, y = A.to_5070(S["longitude"].to_numpy(dtype=float), S["latitude"].to_numpy(dtype=float))
            xs.append(x)
            ys.append(y)
        return np.concatenate(xs), np.concatenate(ys)


class TrainOnly(A.Replay):
    """Floor applied to the training split only (the val split keeps its
    pre-2020 positives); block table unchanged."""
    def run_positives(self):
        super().run_positives()
        for R in self.regions:
            p = self.pos[R]
            self.pos[R] = p[~((p["split"] == "train") & (p["year"].astype(int) < YMIN))]


class StaleBlocks(A.Replay):
    """Correct positives, but the pool's step-10 split read from the
    pre-CR block_assignments.csv (generate_negatives run against a stale B)."""
    def habitat_rows(self, df):
        return floor(super().habitat_rows(df))

    def assign_split(self, bids, sub=None):
        live = A.read_csv(os.path.join(ROOT, "data/pipeline/block_assignments.csv"))
        cur = self.B
        self.B = live
        try:
            return super().assign_split(bids, sub)
        finally:
            self.B = cur


TREES = {"correct": Correct, "noop_replay": NoOp, "off_by_one": OffByOne,
         "floor_2019": Floor2019, "after_thin": AfterThin, "source_all": SourceAll,
         "source_buffer": SourceBuffer, "train_only": TrainOnly, "stale_blocks": StaleBlocks}


def main():
    out = os.path.abspath(sys.argv[1])
    if os.path.realpath(out).startswith(os.path.realpath(ROOT)):
        sys.exit("refusing to write inside the repository")
    names = sys.argv[2:] or list(TREES)
    cfg = A.load_config()
    for n in names:
        rep = TREES[n](ROOT, cfg).run(stop_on_error=True)
        rep.emit(os.path.join(out, n))
        P = pd.concat([rep.pos[R] for R in rep.regions])
        N = pd.concat([rep.neg[R] for R in rep.regions])
        print(f"{n}: P {len(P)} (min year {int(P['year'].min())}), N {len(N)}, "
              f"pool {len(rep.pool)}, B {len(rep.B)}", flush=True)


if __name__ == "__main__":
    main()
