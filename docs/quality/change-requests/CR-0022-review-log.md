# CR-0022 review log

Companion to `CR-0022-background-years-match-positives.md` (CR-0011 A4):
rounds, verdicts and every concern's disposition.

## Rounds
| round | text | reviewer | verdict | BLOCKING |
|---|---|---|---|---|
| 1 | v1 (`9bb1636`) | A: correctness of diagnosis and fix (fresh agent; read-only) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 3 MEDIUM, 2 LOW) |
| 1 | v1 (`9bb1636`) | B: implementability, composition, test plan (fresh agent; read-only; ran `test_cr0015_sampler` + `test_pa0027_lint`: 23 OK) | REVISE | 0 (3 MAJOR, 5 MEDIUM, 3 LOW) |

## Round 1, reviewer A: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A1 | MAJOR | `tests/test_cr0022.py` not committed; acceptance tests unreviewable | accepted: tests committed with v2 (15 tests; fail at `9bb1636` as expected, pass against an uncommitted trial implementation) | `tests/test_cr0022.py`; Test plan |
| A2 | MEDIUM | U2 only tests exact-year rasters; resolver variants (exact path, no fallback, own tie-break) pass | accepted: fixture has no 2021 raster (tie → 2020) and an empty 2023 placeholder (fallback → 2024); U2 asserts the validity path equals `GrousePatchDataset._path_for` | U2; fixture |
| A3 | MEDIUM | the run-time check compares against the helper's own counts (PA-0021(e)); a wrong frame wired in passes | accepted: `build_datasets` recomputes the expected counts from `pos_df["year"]` independently (§2 C); W3 wires the training negatives in and must fail | §2 C; W3 |
| A4 | MEDIUM | U4's reference ("pre-CR function") unspecified; `todays_sampler` is pre-BUG-0042 | accepted: sha256 digests of the sampler's frames at `9bb1636` pinned in the test (four fixtures), generated before any production edit | U4; `PRE_CR_DIGESTS` |
| A5 | LOW | integer check traps: `np.int64` rejected by `isinstance(int)`, `True` accepted | accepted: `numbers.Integral` minus `bool`; U3 adds `np.int64(2022)` (accept) and `True` (reject) | §2 A; U3 |
| A6 | LOW | "0.5 exactly" holds only for integer R | accepted: before/after row reworded; the "+N" line prints `Σ n_y` | §2 C; table |

## Round 1, reviewer B: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| B1 | MAJOR | U2 not run through the helper: a helper making one `"latest"` draw and overwriting `year` passes U1/U7 and the check | accepted: U2 runs through the helper; wrong implementation (iv) added. Author's trial: that mutant fails U2 (and U5, U7, W1, W3) | U2; Test plan (iv) |
| B2 | MAJOR | helper signature lacks `region_i` and `in_state`; helper tests would need county polygons | accepted: signature `(…, *, seed, region_i, region, assignments, in_state=None)`; helper tests inject `in_state` and a synthetic `assignments` | §2 B; Test plan |
| B3 | MAJOR | tests not committed (= A1) | accepted: see A1 | – |
| B4 | MEDIUM | missing `year`: `ValueError` vs `TypeError` ambiguous; U3 too loose | accepted: no default → `TypeError` on omission; bad values → `ValueError`; U3 exact | §2 A; U3 |
| B5 | MEDIUM | `np.int64` years; `2020.0`/`True` unspecified | accepted: sampler takes `Integral` minus `bool` (floats refused); the helper accepts integral floats from positives and casts (PA-0034); U1 feeds `np.int64`, U6 `2020.0` | §2 A, B; U1, U3, U6 |
| B6 | MEDIUM | U4 reference unspecified (= A4) | accepted: see A4 | – |
| B7 | MEDIUM | EC2 smoke writes `data/cache` | accepted: smoke command passes `--cache-dir ''` and `--save-path /tmp/…` | Test plan |
| B8 | MEDIUM | real-data V1 (`draw()`, `"latest"`) no longer reads the per-year path | justified as not needing a new gate: the in-state and block filters read only coordinates (`train.py:196-202`); only the validity raster depends on the year, which U2 covers with the real resolver; V1 still exercises the filters on real polygons and blocks; the smoke run checks the per-year counts on real data. Recorded in the Risk table | Risk table |
| B9 | LOW | `SystemExit` message names path, not year | accepted: message names region and year | §2 A |
| B10 | LOW | PA-0029 Swept? cell and tracker not in deliverables | accepted | Deliverable 5 |
| B11 | LOW | `pd.concat` drops differing `attrs` | accepted: `attrs` set after the concat | §2 B |

## Author's trial implementation (not committed)
To check the tests before review, the author implemented §2 A–C in a
throwaway worktree: all 15 tests pass; wrong implementation (iv) fails
U2, U5, U7, W1 and W3. The worktree was deleted; the production change
waits for approval.
