# CR-0017 deliverable 2 (acceptance replay): proposed bookkeeping rows

Proposed by the deliverable-2 replay author for the lead. The author does
not edit `BUG_LOG.md`, `PREVENTIVE_ACTIONS.md`, the CR-0017 text or the
tracker. Nothing here is filed yet.

## What deliverable 2 delivered
- Code: `7e7b29b` on branch `worktree-agent-a524a3433860bbee3`, based on
  the CR-0015 implementation head `3add80b` (branch
  `worktree-agent-a74570e35615ea5e3`). Not merged: merging changes the
  config sha256, and `standing_checks` then refuses training until the
  deliverable-6 run writes a new record (CR-0017 § Impact, refusal window).
- `acceptance_split.py`: gate E13; rule (b) in `Replay.buffer_drop`;
  `load_config` refuses a missing, re-pointed or re-projected
  `paths.domain_edge`; 19 GATEs.
- `docs/quality/acceptance_split.json`: `paths.domain_edge`. New config
  sha256 `cd4b9b487a0076dac7a8f27858f682c51e5fcca5a174467a957f82282585f6e7`
  (the live record was made under `1e3bfaa4…`).
- `tests/test_acceptance_split.py`: the five §3 attack rows, E13 and
  `edge_m` unit tests, config refusal tests, `paths` pin updated. 107 tests
  pass (90 before).
- CR-0013: the two "Amended by CR-0017" pointer lines (E-table, Attacks).
  This is the CR-0013 half of deliverable 7; the CR-0012 pointer line and
  the `CHANGELOG.md` entry are not part of this branch.
- Evidence: `docs/quality/evidence/CR-0017/acceptance_prefix.txt`, produced
  by `acceptance_prefix.py` in the same directory.

## Separate authorship (CR-0013 design rule 4; CR-0017 § Risk)
The domain and `edge_m` were written from CR-0017 §2–§3 only. Nothing was
imported or copied from `regions.py` or `generate_negatives.py`, and
neither file was opened for the new code or edited. The replay's method
also differs from the one CR-0017 §2 specifies for the pipeline:
- containment: a `geopandas.sjoin(..., predicate="within")`;
- distance: exact float64 point-to-segment distances over every boundary
  segment. Segments are cut into collinear pieces of at most `BUFFER_M`,
  and a `cKDTree` over the piece midpoints finds the candidates.
- No shapely distance call is used (`acceptance_split.py` does not import
  shapely).

For the review-log row:
- replay author: worktree agent `agent-a524a3433860bbee3`, session
  `491a150a-d26d-456d-b9b4-036cd4a6478b`;
- pipeline author (deliverable 3): a different agent, per the lead.

## Results on today's files (read-only; the full text is in `acceptance_prefix.txt`)
The expected result in the CR-0017 test plan was met exactly:
- 16/19 GATEs pass. E13, R3 and R4 fail.
- **E13:** C 88, N 23.
- **R3:** 88 rows not in the replay. Live C minus the replay's C equals the
  pre-registered 88 (`preregister_keys.csv`). The manifest counts differ
  from step 6 on.
- **R4:** the replay's draw replaces exactly the 23 pre-registered
  negatives (live minus replay = those 23; replay minus live = 23
  replacements). The draw counts are equal.
- The live record (`66d63e1d…`) is unchanged before and after the run.

Other checks on the same files:
- The replay's `edge_m` agrees with the `preregister.py` distances to at
  most 0.0005 m (`d_m` is printed to 3 dp).
- The smallest `|edge_m − BUFFER_M|` over C is 1.802 m, which reproduces
  CR-0017 §3.

## Proposed rows
**CR-0017 deliverable 2 checkbox (for the lead to tick):**
> [x] 2. … done at `7e7b29b` (+ evidence commit); 107 tests; read-only run
> on today's files: E13 (C 88, N 23), R3, R4 FAIL, 16/19 otherwise PASS
> (`acceptance_prefix.txt`).

**CR-0017 review log, PA-0021(a) note.** The CR's test plan assigns the
check of E13 and the attack rows to the round-2 reviewer of deliverable
2's code. That reviewer:
- re-runs `python -m unittest tests.test_acceptance_split`;
- checks that each attack's precondition assertion exists and binds:
  `TestDomainEdgeAttacks`, where every attack first asserts its fixture
  rows using a shapely reference `edge_m` (`shapely_edge_m`) that is
  independent of the code under test.
This reviewer has not been appointed yet.

**Tracker (`CR-0007-0008-OPEN-ISSUES.md`), CR-0017 A2 optional OBS row
(LOW, owner: the deliverable-2 replay author).**
- Proposed disposition: **not implemented in deliverable 2**; the item
  stays open with the same owner.
- Reason:
  - CR-0017 §3 records the positives-in-band support as "recorded, not
    gated", and deliverable 2's scope in §3 lists no OBS row.
  - Adding one would change `compute_obs` and the OBS calibration file,
    which only deliverable 6's `--calibrate` writes.
  - It can be added under its own reviewed change, with CR-0013 design
    rule 2 governing any promotion to a gate.

**BUG_LOG / PREVENTIVE_ACTIONS.**
- No new defect was found while implementing deliverable 2, so there is no
  new BUG row.
- The BUG-0050 and BUG-0064 (formerly BUG-NEW-a) rows are deliverable 8.
  Their corrective action is "CR-0017". This proposal adds the acceptance
  commit, so each row reads "CR-0017 (pipeline: deliverable 3; acceptance
  E13/R3: `7e7b29b`)".

## Notes for the lead (not rows)
- **PA-0025 / BUG-0047.** `acceptance_split.py` gains one more
  `"EPSG:5070"` literal (`REQUIRED_DOMAIN_EDGE`).
  - This follows the existing CR-0013 design-rule-1 exemption: the replay
    must not import `regions`.
  - `tests/test_shared_constants.py` passes.
  - BUG-0047 (the analysis-CRS literal) is already open and owns the
    general item.
- **Missing CRS.**
  - CR-0017 §2 lets the pipeline take EPSG:4269 when the county file has
    no CRS.
  - The replay keeps CR-0013's existing stricter behaviour: it raises
    unless the file CRS equals `county_polygons.source_crs`, so it fails
    loudly and never silently disagrees.
  - The real file carries EPSG:4269, so nothing changes today.
- **Merge.**
  - This branch edits `CR-0013-split-acceptance-gates.md`. The records
    branch (`fc52728`) also edits that file, but in different hunks
    (status line, deliverables 0/1/2a), so the merge is expected to be
    clean.
  - It also adds `docs/quality/evidence/CR-0017/acceptance_prefix.{py,txt}`
    next to the records branch's evidence files. There is no name clash.
