# BUG-0080: `acceptance_split.standing_checks` does not bind `block_assignments.csv`, the file `train.py --an-background` reads to keep assumed negatives out of validation blocks

> Found by the 2026-09-30 static code review at `3b3e7d1`.
> **Status: OPEN (latent: `--an-background` defaults to 0.0 and BUG-0074
> already forbids using it); owner: lead; small CR (acceptance design).**

## 1. Description
`standing_checks`, which `train.build_datasets` runs before every
training, calibration or benchmark run, verifies the acceptance config
digest, the 18 per-region positive/negative CSVs, the rasters' size and
mtime, and gates E0/E1/E1p/E3/E4/E5/E6/E14 with the block table (B) and
candidate pool (C) excluded. The full acceptance run digests B and C
(`digested_paths`, 20 files) and stores those digests in the record, but
the standing subset never compares them. `train.py --an-background`
reads `block_assignments.csv` at run time and decides, per background
draw, whether its block is "train" (`regions.block_split`). A replaced or
edited block table therefore passes the standing check and puts assumed
negatives into validation blocks: the BUG-0042 leak, with no gate left to
see it.

## 2. Where encountered
- `acceptance_split.py:125-134` (`digested_paths` vs
  `standing_csv_paths`), `:2822` (loop over `standing_csv_paths`),
  `:2840` (`("E6", gate_E6, {"include_C": False, "include_B": False})`).
- Consumer: `train.py:369-374` (`sample_background_points(...,
  train_blocks_only=True, assignments=data.block_assignments)`),
  `regions.block_split` (`regions.py:251-267`).
- Pin: `tests/test_acceptance_split.py:2239` asserts
  `len(standing_csv_paths(cfg)) == 18`.

## 3. What it caused to fail
Latent. Scenario: after acceptance, `data/pipeline/block_assignments.csv`
is overwritten (a pre-CR-0012 per-region file restored from
`grouse_backup/`, or a hand edit relabelling a validation block "train").
`standing_checks` passes (the 18 CSVs and rasters are unchanged). A run
with `--an-background 1.0` draws label-0 rows inside validation blocks,
the CR-0015 U2/V1 gates that proved the fix are not re-run, and the
validation metrics are contaminated exactly as BUG-0042 measured
(19 to 21 % of draws).

## 4. What the defect was
`acceptance_split.py:125-134`:
```python
def digested_paths(cfg):
    """The 20 digested artifacts: 18 region CSVs, B and C."""
    regions = cfg["constants"]["REGIONS"]
    out = [rpath(cfg, k, R) for R in regions for k in P_KINDS + N_KINDS]
    return out + [rpath(cfg, "block_assignments"), rpath(cfg, "candidate_pool")]


def standing_csv_paths(cfg):
    regions = cfg["constants"]["REGIONS"]
    return [rpath(cfg, k, R) for R in regions for k in P_KINDS + N_KINDS]
```
`acceptance_split.py:2822` and `:2840`:
```python
        for rel in standing_csv_paths(cfg):
...
                        ("E6", gate_E6, {"include_C": False, "include_B": False}),
```

## 5. Root cause analysis (Five Whys)
1. *Why can a changed block table pass?* The standing subset digests
   only `standing_csv_paths`, which omits B.
2. *Why was B omitted?* The standing subset was derived from the split
   files `train.py` reads by default (CR-0013 "standing" = "what training
   consumes"); B was then read only by the pipeline, not by training.
3. *Why did that stop being true?* CR-0015 made `sample_background_points`
   read B at training time (the fix for BUG-0042).
4. *Why was the standing subset not extended then?* CR-0015 gated the
   fix with CR-time checks (U2, V1) and its PA-0029 sweep recorded the
   `build_datasets` rows as "gated by `standing_checks`" without checking
   which files that gate binds.
5. *Why no rule?* PA-0029 requires a gate that reads what a producer
   produces; it does not say the gate must be **standing** or that the
   standing digest list must be derived from the consumers' inputs.

**Root cause:** the standing acceptance subset's file list is a hand
list fixed at CR-0013, not derived from the set of files training-time
code reads, so a later consumer of a pipeline artifact (CR-0015) added a
read the standing check does not cover.

## 6. Corrective action
**None yet.** Proposed (small CR, acceptance design): add
`block_assignments` to `standing_csv_paths` (19 files), run E6 in the
standing subset with `include_B=True`, update the test pin, and derive
the list from a single `TRAINING_INPUTS` constant shared with
`train.build_datasets`. Until then the BUG-0074 rule stands: no run with
`--an-background > 0`. Status: **OPEN (latent)**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0024-standing-checks-bind-block-assignments.md` (v3, awaiting round-3 bounded re-review; nothing implemented).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "standing",
"block_assignments", "an-background", "gate".

**Matches:** BUG-0042 (the leak this gate gap re-opens; fixed by
CR-0015), PA-0029 (its rule), BUG-0074 (same producer, time axis).

**Prior-preventive-action failure analysis.** PA-0029's sweep statement
"gated by `standing_checks`. Not affected" (BUG-0042 §sweep) was not
verified against `standing_csv_paths`; the gate that proved the fix
(V1) runs once at CR time. Category: not enforced-verifiable (a one-time
gate mistaken for a standing one).

## 8. Preventive action
**PA-0037** (extends PA-0029): the standing acceptance subset binds
every file any training-time producer reads; its digest list is derived
from, and pinned by a test against, the consumers' input list; and a
CR-time gate on a run-time producer is either re-run by
`standing_checks` or recorded as an open item naming the file it leaves
unbound.

**Sweep (§3.5), files read by `build_datasets` and its callers at run
time:** 18 split CSVs (bound); rasters (bound by size and mtime);
acceptance config (bound by sha); `block_assignments.csv` (read by
`--an-background`; unbound: this bug); `candidate_pool.csv` (not read
at training time; n/a); `calibration.json` (predict-time, not a training
input). No other instance.

## Cross-references
BUG-0042, BUG-0074, CR-0013, CR-0015 (U2, V1), PA-0029, PA-0037.
