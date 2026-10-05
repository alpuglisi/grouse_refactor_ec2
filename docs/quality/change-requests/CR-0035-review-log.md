# CR-0035 review log

Companion to `CR-0035-redownload-ee-layers.md` (CR-0011 A4).

## Rounds
| round | text | reviewer | verdict | BLOCKING |
|---|---|---|---|---|
| 1 | v1 (`bca963d`) | A: correctness | REVISE | 0 (1 MAJOR, 2 MEDIUM, 3 LOW) |
| 1 | v1 (`bca963d`) | B: implementability, operations | REVISE | 1 (B35-1; 4 MAJOR, 2 MEDIUM, 1 LOW) |
| 2 | v2 (`fb3a824`), bounded | A | APPROVE WITH FOLLOW-UPS (A35-2-1 before step 3) | 0 (1 MAJOR, 2 MEDIUM, 2 LOW) |
| 2 | v2 (`fb3a824`), bounded | B | APPROVE WITH FOLLOW-UPS (two MAJORs dispositioned before approval) | 0 (2 MAJOR, 3 MEDIUM, 3 LOW) |

| 3 | v3 (`8281e48`), bounded | A | APPROVE WITH FOLLOW-UPS | 0 (3 LOW) |
| 3 | v3 (`8281e48`), bounded | B | APPROVE WITH FOLLOW-UPS | 0 (1 MEDIUM) |

Round 3: both reviewers and the author sign off on v3; approved. v4
applies the follow-ups.

Round 2: both reviewers and the author sign off on v2 subject to the
MAJORs; v3 fixes all of them in code/text. Because v3 changes the gate
script and the steps, the changed text goes to a bounded round 3.

## Round 1: concerns and dispositions (v2)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| B35-1 = A35-1 | BLOCKING | gate measures only the latest vintage; argmax with no margin; VT tcc already "aligned" while shifted - the gate cannot fail on the wrong pipeline (PA-0021) | accepted: new per-file gate `check_layer_registration.py` (every year): NLCD/TCC vs Earth Engine point samples of the source at native scale at template cell centres; raw TreeMap vs point samples 7 m NW of each pixel centre (opposite to the SE tie); derived TreeMap vs the raw BALIVE forest mask; `MIN_EQUAL` = 0.99 in the script. Tests: passes registered files, fails the SE-tie-shifted versions of all three kinds. Step 3 also requires it to FAIL on the pre-repair snapshot. The road sweep is corroboration only | step 3; `check_layer_registration.py`; tests |
| A35-2 | MEDIUM | no margin or sub-pixel estimate; half-pixel case untested | accepted via A35-1: the gate is equality against a point-sampled source (a half-pixel shift gives far below 99 %); the tests build the real half-pixel (SE tie) shift, not a whole-cell roll | step 3; tests |
| B35-2 | MAJOR | `WINDOW_PX` redefined in `diagnose_layer_registration.py` (P6 name) - `test_shared_constants` red | accepted: renamed `SWEEP_WINDOW_PX`; suite green | `diagnose_layer_registration.py` |
| B35-3 | MAJOR | "--force re-runs only what is missing" false; copied backup leaves an old/new mix | accepted: step 0 snapshots then deletes the in-scope files, so missing = to do; new files tagged `GROUSE_GRID=native-lattice`; inventories before/after compared | step 0, 2 |
| B35-4 | MAJOR | no `--years`: new published years would be added | accepted: per-region `--years` from the step-0 inventory for all three scripts; inventory equality required | step 2 |
| A35-3 | MEDIUM | product version not pinned | accepted: `--collection` (CR-0034) pins the id recorded at the pilot; files tagged `GROUSE_SOURCE` | step 1, 2; CR-0034 §1 |
| B35-5 | MAJOR | no data-root flag for the "before" arm; standing checks would refuse | accepted: hard-linked snapshot of the whole tree (`cp -al`, mtimes preserved) and a second worktree whose `data` links to it | step 0, 5 |
| B35-6 | MEDIUM | TCC pilot's coverage check reads the old NLCD | accepted: no separate TCC pilot; TCC runs after the NLCD re-download | step 1, 2 |
| B35-7 | MEDIUM | byte-identity gate's file list in prose; old manifest not kept | accepted: `check_split_unchanged.py` compares the snapshot manifest's outputs with the new manifest and the files on disk over `digested_paths` (20 artifacts); tested | step 4.2 |
| B35-8 | LOW | rollback needs re-acceptance | accepted: rollback restores files by hard link and the old manifest and record, so the old record validates without re-running acceptance | Rollback |
| A35-4 | LOW | OBS rows over tcc/TreeMap go stale | accepted: stated as expected in step 4.3 | step 4.3 |
| A35-5 | LOW | CR-0010 coverage repairs keep a half-cell residual | accepted residual, tracked (own change) | Impact; tracker |
| A35-6 | LOW | CR-0032 base arm confounded | accepted: the "after" arm is CR-0032's base arm; CR-0032 deliverable 4 after step 2 | step 5 |

## Round 2: concerns and dispositions (v3)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A35-2-1 | MAJOR | derived check compared forest masks against BALIVE; `carbon_dwn` and rounding break it on correct data | accepted: each derived layer is rebuilt exactly as the generator does from its own raw attributes (`rebuild_derived`: `_clean`, `treemap_encode`/`tpa_live_encode`, `qmd_from_balive_tpa`) and compared for equality; test with harvested plots (BALIVE 0, CARBON_DWN > 0) | gate; `DerivedGate` |
| A35-2-2 | MEDIUM | raw probe NW only | accepted: four diagonal probes, all must match; NW-tie fixture fails | gate; `test_raw_file` |
| A35-2-3 = B35-2-4 | MEDIUM | correct data may score < 0.99 (datum ~1 m; approximate warp) | accepted: (1) the approximate warp is a real defect, BUG-0095, fixed in CR-0034 §5 (measured 0.932 -> 1.000); (2) the gate reports the share of mismatches within `EDGE_M` of a source edge; (3) pre-stated pilot decision rule: jitter -> code change under its own CR, never a lower bar | step 3; CR-0034 §5 |
| A35-2-4 = B35-2-3 | LOW / MEDIUM | `--data-root` needs the parent of `data/`; worktree created only in step 5 | accepted: worktree and symlink in step 0.2; exact snapshot command; must report a nonzero file count; usage string fixed | step 0.2, 3 |
| A35-2-5 = B35-2-8 | LOW | `check_split_unchanged.py` usage path | accepted: `.../pipeline/split_manifest.json` | script |
| B35-2-1 | MAJOR | `tests/test_cr0035.py` `__main__` block mid-file (PA-0035) | accepted: block moved to the end; sweep 0 hits (302 files) | test file |
| B35-2-2 | MAJOR | rollback leaves changed split CSVs | accepted: whole-tree rollback (`mv data ...; cp -al data_before_bug0094 data`) after verifying `snapshot.sha256` | Rollback |
| B35-2-5 | MEDIUM | snapshot failure not attributable to the shift | accepted: gate reports equality at the BUG-0094 offset (+15, -15 m): high on shifted files, low on repaired ones (tested) | gate; step 3 |
| B35-2-6 | LOW | hard links shared with live tree | accepted: `snapshot.sha256` recorded at step 0.1 and verified before step 3's snapshot run, the before arm and any rollback | step 0.1 |
| B35-2-7 | LOW | TreeMap step without `--vintages` | accepted: `--vintages V(R)` | step 2.3 |

## Round 3: concerns and dispositions (v4)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A35-3-1 | LOW | step 3 still says "raw BALIVE forest mask" (CR-0011 A4) | accepted: reworded to the exact rebuild | step 3 |
| A35-3-2 | LOW | derived test checks `rebuild_derived` against itself, not the generator | accepted: `DerivedGateRealGenerator` runs the real `generate_treemap_features.write_vintage` on native-lattice raw files; all four derived layers pass at 100 % (with CR-0034's exact warp) | tests |
| A35-3-3 | LOW | `DerivedGate` re-ran the parent's tests | accepted: shared `GateFixture` base with no tests | tests |
| B35-3-1 | MEDIUM | Risk row claims atomic writes everywhere; TreeMap raw and the generators write final paths | accepted: TreeMap raw write made atomic (CR-0034 §3); Risk row names the two rewrite-always generators | Risk; CR-0034 §3 |
| A34-3-1 (CR-0034) | MEDIUM | `tsd` warp | step 2.5 regenerates `tsd` with the exact warp (BUG-0096) | step 2.5 |
