# CR-0031 review log

Companion to `CR-0031-background-years-match-positives.md` (CR-0011 A4):
rounds, verdicts and every concern's disposition.

## Rounds
| round | text | reviewer | verdict | BLOCKING |
|---|---|---|---|---|
| 1 | v1 (`9bb1636`) | A: correctness of diagnosis and fix (fresh agent; read-only) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 3 MEDIUM, 2 LOW) |
| 1 | v1 (`9bb1636`) | B: implementability, composition, test plan (fresh agent; read-only; ran `test_cr0015_sampler` + `test_pa0027_lint`: 23 OK) | REVISE | 0 (3 MAJOR, 5 MEDIUM, 3 LOW) |

## Round 1, reviewer A: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A1 | MAJOR | `tests/test_cr0031.py` not committed; acceptance tests unreviewable | accepted: tests committed with v2 (15 tests; fail at `9bb1636` as expected, pass against an uncommitted trial implementation) | `tests/test_cr0031.py`; Test plan |
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

## Round 2 (bounded, CR-0011 A2), text v2 `069f50c`
| reviewer | verdict | prior concerns | new concerns |
|---|---|---|---|
| A | APPROVE | A1–A6 resolved (U4 digests independently reproduced) | A7 LOW |
| B | APPROVE WITH FOLLOW-UPS | B1–B11 resolved; B8 justification accepted (`train.py:189-202` filters read only coordinates) | B12–B14 LOW |

Both reviewers built a correct §2 A–C independently: 15/15 tests pass.
Reviewer-built wrong implementations, each caught by the test the CR
names (reviewer A, `scratchpad/reviewA22/impl.py`): (i) U1, U2, U5, U6,
W1, W3; (ii) U2; (iii) U3; (iv) U2, U5, U7, W1, W3; (v) W1; extra
variants (validity without content check; exact-year path) U2. Reviewer
B's independent set agrees. These are the deliverable-3 runs in substance;
deliverable 3 re-runs them against the committed code.

| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A7 = B12 | LOW | `ASSIGN` has validation share 0, so U4's `train_blocks_only=True` digests pin only a no-op filter | accepted: comment in the test naming `test_cr0015_sampler` as the filter's owner; tracker entry to add a non-zero-share fixture | `tests/test_cr0031.py` `ASSIGN`; tracker |
| B13 | LOW | U6b passes if the column stays float; `pos_years` type unstated | fixed: U6b asserts an integer dtype; §2 B says array-like | U6; §2 B |
| B14 | LOW | test docstring names the wrong passing test | fixed | `tests/test_cr0031.py:4-7` |

## Approval (2026-10-05)
Quorum (CLAUDE.md §1.4): author and both reviewers who commented. A:
APPROVE (round 2). B: APPROVE WITH FOLLOW-UPS (round 2). No BLOCKING
concern in either round; every MAJOR resolved in the text. **CR-0031
APPROVED.** Deliverable 2 (code) may start.

## Deliverable 3: wrong-implementation runs (reviewer A, at `e18944d`)
Record: `docs/quality/evidence/CR-0031/reviewA/wrong_impl_runs.txt`
(variants re-runnable with `mutate.py`). Control: `test_cr0031` 15/15,
`test_cr0015_sampler` 12/12. Every variant, (i)–(v) and the reviewer's two
extras, is detected (each run FAILED). The record's verdict line reads
**FAIL** by the literal rule the author set ("each variant fails the test
the CR names for it"), because the CR's Test plan named the wrong test for
two variants. The record is kept unedited.

- **I1 (LOW, Test-plan transcription; found by reviewer A).** (i) was
  mapped to U1/U2/U7, but U7 asserts the helper's `RuntimeError`, which (i)
  still raises, so U7 passes; U1 and U2 fail. (v) was mapped to W3, but W3
  asserts the `build_datasets` `RuntimeError`, which (v) triggers, so W3
  passes; W1 fails. Resolution: the Test plan now names U1/U2 for (i) and
  W1 for (v). No code or test change. On the corrected mapping every
  variant fails its named test — reviewer A's statement in the record
  ("correct the CR's test mapping for (i) and (v) and re-state the
  verdict"), with no re-run needed since the outcomes are unchanged.

## Renumbering CR-0022 → CR-0031 (user decision, 2026-10-05)
The unmerged branch `claude/wonderful-gauss-ghz53i` (2026-09-30, based on
`3b3e7d1`) had already allocated CR-0020..CR-0030, BUG-0076..BUG-0092 and
PA-0033..PA-0047. Decision: IDs already on `main` stay; this CR, not yet
merged, becomes **CR-0031**; new IDs start above both sets (CR-0032+,
BUG-0093+, PA-0048+). Files, code comments, tests (`tests/test_cr0031.py`)
and the evidence directory were renamed. Commits up to `22d8879` and
reviewer A's record (`evidence/CR-0031/reviewA/wrong_impl_runs.txt`, kept
verbatim) say "CR-0022"; they refer to this CR.
