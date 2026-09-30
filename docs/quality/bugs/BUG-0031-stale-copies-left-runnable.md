# BUG-0031: Stale script copies left runnable, writing the live pipeline's output paths (`legacy/audit.py`, `legacy/download.py`, `legacy/download_more.py`, `clean.py`, `legacy/gen_negs.py`)

## 1. Description
PA-0002 requires a superseded copy to be deleted or "explicitly marked
deprecated". The superseded copies were moved to `legacy/` (`bf509da`) or
left in place with the fixes back-ported, and counted as dealt with. Five
of them still run end to end, and each writes the same paths as the live
script it duplicates. Running any of them silently overwrites the live
pipeline's outputs with the old logic. After CR-0007, running
`legacy/audit.py` would replace the state-partitioned `evaluated_sightings_*`
with the box-clipped versions this CR removes.

## 2. Where encountered
CR-0007 review (round 7/8, the PA-0014 sweep question), confirmed while
writing CR-0007 §3. Copies and the live paths they write:

| stale copy | live script | shared output |
|---|---|---|
| `legacy/audit.py` | `analyze_grouse.py` | `data/pipeline/{evaluated_sightings,envelope_metrics,nonveg_flagged}_{region}.csv`, maps (`legacy/audit.py:1021-1022`, `:781`) |
| `legacy/download.py` | `download_rev.py` | `data/landfire/{region}_{year}_{feature}.tif` (`out_dir = "data/landfire"`, `:67`) |
| `legacy/download_more.py` | `download_rev.py` | same (`OUT_DIR = "data/landfire"`, `:72`) |
| `clean.py` | `prepare_training_data.py` | `thinned_positives_*`, `train/val_positives_*`, `block_assignments_*` |
| `legacy/gen_negs.py` | `generate_negatives.py` | `data/negatives/{,train_,val_}negatives_{region}.csv` |

## 3. What it caused to fail
No observed overwrite (none of the copies was run after its live script
diverged, as far as the artifacts show). The hazard is real, and grows with
each change to a live script:
- `legacy/audit.py` differs from pre-CR-0007 `analyze_grouse.py` only in
  its local `NODATA_SENTINELS` copy (13 diff lines). After CR-0007 it would
  write overlapping-box region files, the defect BUG-0027 and BUG-0029
  describe.
- `legacy/download*.py` write the LANDFIRE rasters that CR-0010 repaired
  and CR-0008 re-generates. They lack later fixes (BUG-0015: no
  empty-raster check in `download_more.py`).
- PA-0014's sweep called `clean.py` and `legacy/gen_negs.py` "content-
  identical, so overwriting is harmless". That holds only until the live
  script changes, and CR-0012 changes both.

## 4. What the defect was
`legacy/audit.py`, verbatim (pre-CR-0007; no guard anywhere in the file):
```python
    valid.to_csv(f"data/pipeline/evaluated_sightings_{region}.csv", index=False)
    env_df.to_csv(f"data/pipeline/envelope_metrics_{region}.csv", index=False)
```
`legacy/download_more.py:72`:
```python
OUT_DIR = "data/landfire"
```
PA-0014's Swept? cell, verbatim:
```
yes — swept every shared-output-path pair in the repo; the only two others found (`gen_negs.py`/`generate_negatives.py`, `clean.py`/`prepare_training_data.py`) are content-identical, so overwriting is harmless — no new hazard
```

## 5. Root cause analysis (Five Whys)
1. *Why could a stale copy overwrite live outputs?* It runs, and it writes
   the live paths.
2. *Why does it still run?* "Deprecated" was satisfied by moving it to
   `legacy/`, adding a comment, or back-porting fixes. None of these stops
   execution.
3. *Why did PA-0014's sweep miss `legacy/audit.py`?* The sweeps (PA-0002,
   PA-0012, PA-0014) found copies **by file-name similarity** (numbered /
   `_rev` / `_more` siblings). `audit.py` shares no name with
   `analyze_grouse.py`.
4. *Why were `clean.py` and `gen_negs.py` judged harmless?* Harm was judged
   by today's content ("content-identical"), not by the fact of sharing an
   output path with a live script that will change.
5. *Why no check?* The rules name what a copy looks like (a filename), not
   what it does (what it writes), and a "deprecated" mark has no
   mechanical meaning.

**Root cause:** stale copies were identified by name and neutralised by
labels (a directory, a comment, a suffix), not identified by the paths they
write and neutralised by something that stops them from running.

## 6. Corrective action
- **CR-0007 §3 (deliverable 4):** `legacy/audit.py`, `legacy/download.py`
  and `legacy/download_more.py` now start with
  `raise SystemExit("<file> is a stale copy of <live script> (BUG-0031); use <live script>")`
  as their first statement (line 1 of each file). `check_partition.py` P7
  checks by AST that the guard is first, and that running the file exits
  non-zero naming BUG-0031. PASS in `docs/quality/evidence/CR-0007-gates.txt`.
- **CR-0012 v2 §6:** the same guard for `clean.py` and `legacy/gen_negs.py`
  (owner: CR-0012; until then both stay P6-exempt, CR-0007 round-9 B-R9-1).
- **PA-0026** (below). PA-0002's and PA-0014's Swept? cells corrected.

Status: **FIXED for the three CR-0007 copies**; `clean.py` and
`legacy/gen_negs.py` **open, owned by CR-0012 §6**.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`:
- **BUG-0002, BUG-0003, BUG-0004, BUG-0015 / PA-0002, PA-0012:** the same
  mechanism (a superseded copy carrying old behaviour). This is a
  recurrence.
- **BUG-0016 / PA-0014:** shared output path between diverged scripts. This
  is a recurrence, and PA-0014's sweep had declared this territory clean.

**Prior-preventive-action failure analysis.**
- **PA-0002** ("delete or explicitly mark ... deprecated"): **wrong layer.**
  A mark is documentation. Moving a file to `legacy/` was counted as
  marking it, and the file still ran.
- **PA-0012** (sweep "file-name-similarity clusters"): **too narrow.** It
  defines the search by name, so a renamed copy (`audit.py`) is invisible.
- **PA-0014** (shared mutable output path needs a marker or warning):
  **right mechanism, wrong sweep and judgement.** The sweep again started
  from name pairs, and it accepted "content-identical today" as harmless.
- None was **enforced-verifiable**: nothing checked that a copy cannot run.

## 8. Preventive action
**PA-0026** (extends PA-0002 and PA-0012): "A stale copy is found by what it
writes: a tracked script writing a path another live script writes is its
single owner or starts with `raise SystemExit` naming the replacement; a
comment, `legacy/` or a suffix is not a guard."

**Sweep (§3.5), by output path.** Every write target (`to_csv`, `savefig`,
`to_file`, `torch.save`, `open(..., "w")`, `rasterio.open(..., "w")`) in
git-tracked `*.py` minus `inv_*`/`res_*`/`tests/`/`docs/`, grouped by the
path written (`CR-0007-implementer-findings.md`, F5):
- The five copies above: this bug.
- **`legacy/download_landfire.py`, `_2.py`, `_3.py`** write
  `data/landfire/*.tif`. Their guard is a `raise SystemExit(1)` inside
  `if __name__ == "__main__":` (not the first statement), and it tells the
  user to run `download.py`, itself a stale copy. **BUG-0048**, open.
- **`tune.py`** writes `data/pipeline/bin_tuning_{region}.csv`, as does
  `tune_bins.py`. By its own warning (`tune.py:210`) it is superseded by
  `tune_bins.py`, and it still runs. This is **BUG-0016**, already logged
  and still OPEN, so no new BUG is filed. PA-0026 now states the required
  remediation: guard `tune.py`, or give the output one owner. The domain
  owner's call that BUG-0016 waits on is still needed.
- Not stale copies (examined, n/a): `repair_coverage_rasters.py` and
  `realign_rasters.py` rewrite rasters in place as designed repair steps
  (CR-0010, realignment); `check_road_dist.py` and
  `generate_road_distance.py` share the TIGER download cache (identical
  bytes by URL); the three `download_*`/`generate_*` families write
  disjoint feature names.

**Mechanical enforcement:** CR-0007 P7 checks the three §3 guards
(`check_partition.py`, `P7_GUARDED`). A general output-path check is
feasible, as a test that runs the sweep above and fails on a shared write
target without a first-statement guard. It is not added here (it would be
new gate code outside CR-0007's approved scope); candidate for the CR that
remediates BUG-0048 and BUG-0016.
