# CR-0030 review log

## Lineage
Split from CR-0022 v2 §3 (OBS O11) on 2026-09-30 under CR-0011 A5
(CR-0022 review log A3/B1). Author: the review session that filed
BUG-0077. The findings that moved with the text, and where CR-0030 v1
dispositioned them (PA-0024(b)):
| CR-0022 round-1 finding | disposition in CR-0030 |
|---|---|
| A2 MAJOR: `acceptance_split.py --obs` does not exist; `OBS_IDS`, docstring and test pins must change; a config key would refuse training; the full run rewrites the record | §2: O11 lives in `stats_fixed`; `OBS_IDS`/docstrings/`test_every_gate_and_obs_row_reported_once`; no config key; record rewrite stated |
| B2 MAJOR: O11 extends O9, in-run z like O3/O4, Mann-Whitney with average tie ranks | §2: after the O9 block, z as O3/O4, `_year_auc` definition (`preregister.py:94-102`) |
| A6 LOW: O11(b) from O9's `year_hist` and `_tv` | §2: `_tv` on the per-year share dictionaries |
Reviewers: two fresh agents (CLAUDE.md §1.2, §1.4 agent-only quorum),
each reading BUG-0073/BUG-0077 and the code before the CR; review logs
were not read by them.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | A (agent, fresh) | APPROVE WITH FOLLOW-UPS (conditional on 1, 2 text) | 0 |
| 1 | v1 | B (agent, fresh) | APPROVE WITH FOLLOW-UPS (conditional on 1 text) | 0 |

## Round 1, reviewer A
- A1 MEDIUM (PA-0024(b)): no lineage table for the findings moved from
  CR-0022 (all addressed in the text; the table is required).
- A2 MEDIUM: CR-0013's N-perm is "val labels over blocks"; O11 permutes
  the class label over rows within (s, R), a different null; name it.
- A3 LOW: 0.6615 was computed on the `Floored` replay's frames
  (`preregister.py:189-190`, `:230`), reproduced by the live run; say so
  and treat a mismatch as a finding.
- A4 LOW: the tie test needs a callable (`_auc` next to `_tv`); ranks
  once, labels permuted.
- A5 LOW: cost is 12 cells × `n_perm`, not 24 keys ×.
- A6 LOW: null-year handling (drop per class as O9); skip when
  `Nsel is None`.
- A7 LOW: no id collision (O12 CR-0029, O13 CR-0020); a `range` literal
  can print `n/a` depending on landing order.
- A8 LOW (A4): 0.6615 three times; `:2914` → `:2915`; `write_record`
  also refreshes `created_utc`, `commit`, `dirty`, `rasters`.
- Sound: implementable in `stats_fixed`; frames carry `split`/`year`;
  config sha and `standing_checks` unaffected; record rewrite; AUC
  matches `preregister.py`; PA-0021(a)/(f); A5.

## Round 1, reviewer B
- **B1 MAJOR:** `OBS_IDS = range(1, 12)` collides with landing order:
  if CR-0020 lands first (O13), the literal drops O13's row silently
  (`obs_report`, `full_run` iterate `OBS_IDS`; the reported-once test
  iterates the same tuple); `range(1, 14)` would demand an O12 row
  `acceptance_split.py` never produces. Remedy: explicit tuple, append
  `"O11"`, record the id map.
- B2 MEDIUM: `compute_obs` wraps `stats_fixed` in a broad handler
  (`:2657-2660`, pinned in `tests/test_pa0027_lint.py:113`); an O11
  exception blanks O3/O4/O7/O9/O10; specify narrow guards or a separate
  function (then classify the new handler in the lint); state the pinned
  handlers are not edited.
- B3 MEDIUM: the tracker's edge-band OBS item ("decide with the next
  change to `acceptance_split.py`'s OBS set") is unaddressed.
- B4 LOW: a third "O1-O10" docstring at `:2433`.
- B5 LOW: same as A2 (null naming).
- B6 LOW: the test config uses `n_perm = 30`; helper name; z values are
  printed not recorded; `N is None` in the risk table.
- B7 LOW: cites (`:2558-2561`, `:2593-2601`, `:2913`).
- B8 LOW: CR-0013 design rule 4 (separate authorship): state whether
  it binds.
- B9 LOW (A4): 0.6615 repeated.
- Sound: frames and masks implementable; 12 cells; config unpinned
  `obs`; record rewrite; AUC and TV recomputed from BUG-0073 §3's
  histograms (0.6615, 0.2431); `obs_report` generic over `OBS_IDS`.

## v2 dispositions (both reviewers)
| # | sev | disposition (operative location) |
|---|---|---|
| B1 / A7 | MAJOR / LOW | **Accept** — §2 `OBS_IDS` bullet: explicit tuple, append `"O11"`, id map, non-contiguous allowed |
| A1 | MEDIUM | **Accept** — this log's Lineage table; Status points to it |
| A2 / B5 | MEDIUM / LOW | **Accept** — §2 null bullet names N-perm-class; § 3 table; deliverable 4 adds it to CR-0013 |
| B2 | MEDIUM | **Accept** — §2: narrow guards (`nan` on an empty class; O9's year handling; skip when `Nsel is None`); `compute_obs`/`full_run` and their pinned handlers not edited |
| B3 | MEDIUM | **Accept** — § Impact: decision recorded (not bundled, A5; stays its own amendment, owner lead); tracker updated; deliverable 4 |
| A3 | LOW | **Accept** — § Why now cites the replay frames and the live reproduction; § 3 treats a mismatch as a finding |
| A4 / B6 | LOW | **Accept** — §2 `_year_auc` helper; ranks once per cell; `n_perm = 30` noted in § 3; z captured from the log (deliverable 3); risk row |
| A5 | LOW | **Accept** — § Impact: 12 cells |
| A6 | LOW | **Accept** — §2 second bullet |
| A8 / B7 / B9 | LOW | **Accept** — cites corrected; 0.6615 stated once (§ Why now); record refresh stated |
| B4 | LOW | **Accept** — §2: `:2433` listed |
| B8 | LOW | **Accept** — §2 last bullet and deliverable 1 |

## Versions
| version | change |
|---|---|
| v1 | initial draft, split from CR-0022 v2 |
| v2 | explicit `OBS_IDS` tuple and id map; N-perm-class; `_year_auc`; narrow guards; edge-band decision; dispositions above; approved by agent quorum |
