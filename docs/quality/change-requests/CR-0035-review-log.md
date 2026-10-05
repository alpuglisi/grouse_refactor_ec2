# CR-0035 review log

Companion to `CR-0035-redownload-ee-layers.md` (CR-0011 A4).

## Rounds
| round | text | reviewer | verdict | BLOCKING |
|---|---|---|---|---|
| 1 | v1 (`bca963d`) | A: correctness | REVISE | 0 (1 MAJOR, 2 MEDIUM, 3 LOW) |
| 1 | v1 (`bca963d`) | B: implementability, operations | REVISE | 1 (B35-1; 4 MAJOR, 2 MEDIUM, 1 LOW) |

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
