# BUG-0077: `tests/test_cr0021.py` run as a script skips every test defined after a mid-file `__main__` block

> Found in the CR-0021 implementation code review (finding C4,
> 2026-10-03). **Status: FIXED** (trivial fix, no CR).

## 1. Description
`tests/test_cr0021.py` had `if __name__ == "__main__": unittest.main()`
in the middle of the file. Run as `python tests/test_cr0021.py`,
`unittest.main()` runs (and exits) before the classes below it are
defined, so 15 of 39 tests, including every deliverable-3 pipeline test,
never ran, and the run reported `OK`.

## 2. Where encountered
`tests/test_cr0021.py:318-319` (as of `81cc603`); the deliverable-1
tests were above the block, the deliverable-3 tests appended below it.

## 3. What it caused to fail
`python tests/test_cr0021.py` → `Ran 24 tests … OK`;
`python -m unittest tests.test_cr0021` → `Ran 39 tests … OK`. Every
recorded run of this suite used `-m unittest`, so no recorded result was
affected; a contributor running the file directly would have been told
the stratified draw was tested when it was not.

## 4. What the defect was
```python
        self.assertNotEqual(flat, strat)


if __name__ == "__main__":
    unittest.main()


class FetchCappedWithCollector(unittest.TestCase):
```

## 5. Root cause analysis (Five Whys)
1. *Why were tests skipped?* `unittest.main()` collects the classes
   defined so far and calls `sys.exit`; later classes are never defined.
2. *Why were classes defined after it?* Deliverable 3 appended its tests
   to the end of a file whose last statement was the entry block.
3. *Why was that not noticed?* The author ran the suite only with
   `-m unittest`, which imports the whole module and ignores the block.
4. *Why is the position of the block load-bearing?* Python executes a
   script top to bottom; anything after a block that exits is dead on
   that entry path only — an entry-path-dependent result.

**Root cause:** a module's behaviour depended on the entry path: the
script entry block was not the last top-level statement, so the script
path ran a subset of the module silently.

## 6. Corrective action
The block moved to the end of the file; `python tests/test_cr0021.py`
now runs 41 tests (39 + two added for review findings C1/C2), the same
as `-m unittest`. No CR.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "__main__",
"skipped", "SkipTest", "reports OK", "entry".
**Matches:** **BUG-0063** (a test harness reported `OK (skipped=6)`
while broken) — same consequence (a suite reports OK without running its
tests), different mechanism (a broad handler turned errors into
`SkipTest`; PA-0027). **BUG-0048** (a guard attached to the `__main__`
path only, PA-0026) — same family (behaviour that depends on the entry
path), different instance (a write guard).
**Prior-preventive-action failure analysis.** PA-0027 covers handlers,
not statement order; PA-0026 covers stale-copy guards ("a guard inside
`__main__` is not a guard"). Neither says code must not depend on the
entry path in general: **too narrow** for this mechanism.

## 8. Preventive action
**PA-0035 (extends PA-0026's entry-path point beyond guards):** a
module's `if __name__ == "__main__":` block is its last top-level
statement; nothing a module defines or checks may depend on how it is
entered. Enforcement: `docs/quality/evidence/CR-0021/sweep_main_last.py`
(re-runnable AST sweep, 0 hits required); a lint test needs a CR
(tracker, with PA-0031's).

**Sweep (§3.5):** `sweep_main_last.py` over all 282 git-tracked `*.py`
(2026-10-03, `sweep_main_last.txt`): 0 hits after the fix; run on the
pre-fix tree it reports exactly `tests/test_cr0021.py:318` (control).
No new BUG.

## Cross-references
CR-0021 (implementation review C4), BUG-0063, BUG-0048, PA-0026,
PA-0027, PA-0035.
