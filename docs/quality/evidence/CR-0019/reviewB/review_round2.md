# CR-0019 reviewer B, round 2 (bounded re-review, CR-0011 A2)

**Version reviewed:** v2, commit `a89151f` (diffed against v1 `95d7463`:
CR, review log, `check_must_change.py`, `preregister.py`,
`mc_selftest.txt`). Scope: (a) whether my round-1 MAJOR concerns B1 and B2
are resolved in the operative text; (b) the text that changed since v1.
Read-only on code and `data/`; scratch under `/tmp/claude-1000/cr0019b2/`.

## Re-runs (this round)
- `mc_selftest.py`: predicted tree **MC PASS 42/42**; no-op (live as
  NEW) **FAIL 32/42**; SELFTEST PASS. This matches `mc_selftest.txt`
  exactly.
- My round-1 wrong trees (`build_trees.py` + `edit_trees_and_run_mc.py`)
  rebuilt and re-run against the v2 MC. The table is in
  `reviewB/mc_wrongtrees_round2.txt`. All 23 trees give the same verdicts
  as in round 1, with one change: **`pos_order_reversed` now FAILs (MC1 NH
  order)**, where in round 1 it passed. The only trees MC still passes are
  the two stated limits (`edit_added_pos_evh` and `edit_neg_obs_date`),
  which R1/R4 cover, and the new docstring says so.
- PRE_SHA pins: the four digests equal `sha256sum` of the committed CSVs,
  and the CSVs did not change between `95d7463` and `a89151f`. I copied
  the script to a scratch tree with the same relative layout and edited
  one year in `preregister_N.csv`. MC then stops with "preregister_N.csv:
  sha256 differs from the pinned pre-registration" and exit 1.
- Real files, read-only: `evaluated_sightings_{ME,NH,VT}` have 0
  null years (2016–2024), so the new "none has today" claim holds. The raw
  candidates have 0 null years (2020–2024). In `preregister_P/N`, the P
  year set and the N year set are both {2020..2024}, pooled and in every
  (region, split), so E14(b) passes on the predicted data. The year
  fields are integers in both P and N files, so the set comparison is not
  exposed to a float/int format mismatch.

## Prior MAJOR concerns
| id | status | evidence |
|---|---|---|
| B1 (fixtures break under the new guards) | **RESOLVED** | See the four points below the table. |
| B2 (E14 one-sided) | **RESOLVED** | See the three points below the table. |

**B1 evidence:**
- The pool guard now raises only on a non-null `year < YEAR_MIN` (§2 pool step 1). So `tests/test_cr0012.py:594`, which has NaN candidates, and the assertion at `:835-836` keep working. `preregister.Floored` is aligned with this (B9).
- In `tests/test_acceptance_split.py`, the sighting years (`:227`), candidate years (`:291`) and duplicate years (`:319`, `(year % 5) + 2019`) all produce 2019 today. The CR now lists each of them, plus fixture `REGIONS_PY` (`:62`) and the gate-count pin (`:1492`, 19 → 20), as fixture edits.
- The rule "re-seed, never delete" protects the existing attack rows' existence checks.
- Deliverable 2's note is accurate: `test_cr0012.test_measured_constants_and_environment` (`:95-96`) compares `ptd.measured_constants()` with `CONFIG["constants"]`, so it passes only once deliverable 3 lands.

**B2 evidence:**
- E14(b) adds set equality of P years and N years, pooled over regions and splits.
- A new attack row ("positives later than every negative") targets exactly the upper-end divergence.
- On the pre-registered data both sets are {2020..2024}; today P has 2016–2024, so E14(b) fails as the CR states. The reason for pooling (a small cell can miss a year by chance) is sound.

## Findings on changed text
| id | sev | where | finding / failure scenario | fix |
|---|---|---|---|---|
| B2-1 | LOW | CR §3 "Existing fixtures", the `tests/test_cr0012.py` bullet; deliverable 3 ("the `tests/test_cr0012.py` fixture edit") | "candidate years `:593` move to ≥ `YEAR_MIN`" is a no-op: `:593` is already `rng.choice([2023, 2024, 2025])`, and the sightings at `:551` are too. Under v2's guard, `test_cr0012.py` needs **no** fixture edit. An implementer who follows the text might "fix" years that don't need it and change the seeded draw, then chase test differences that aren't regressions. | Say that `test_cr0012.py` needs no fixture change (years are already ≥ 2023; null candidates stay), and drop "the fixture edit" from deliverable 3. |
| B2-2 | LOW | CR §3 attack table, row "Positives later than every negative" | The fixture requirement ("sightings include a year above every candidate year") does not say that the sighting must be a habitat positive that survives the window and the thin, as the other rows do. If the seeded sighting is non-vegetated or thinned away, P carries no such year and E14(b) passes. The attack test then fails loudly rather than passing vacuously, so no wrong acceptance results; the problem is only an ambiguous spec. | Word it as the "No floor" row is worded: "≥ 1 habitat positive with a year above every candidate year, surviving the window and the thin". |
| B2-3 | LOW | `docs/quality/evidence/CR-0019/__pycache__/preregister.cpython-312.pyc` (added in `a89151f`) | A compiled bytecode file is committed as evidence. `.gitignore` is deny-by-default, so it must have been force-added. It is a derived binary that goes stale as soon as `preregister.py` changes. | `git rm --cached` it in the next bookkeeping commit. |

No BLOCKING findings. Outside the changed text, I found nothing that
reaches BLOCKING. The changes to §6 (the warning widened to all BUG-0060
entry points; CR-0020 trains from scratch), § One change per CR (B10),
§2 envelope weights (B4), the constant note (B8) and § Impact (B11) read
correctly and match their dispositions. B12 is correctly tracked as a
follow-up.

## Verdict
**APPROVE WITH FOLLOW-UPS.** B1 and B2 are resolved. B2-1, B2-2 and
B2-3 are LOW and go to the review log and tracker. B2-1 and B2-2 are
one-line text edits that the author may make before implementation.
