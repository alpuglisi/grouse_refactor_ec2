# BUG-0018: `check_exotic.py` carries a dead, misleading constant

## 1. Description
`check_exotic.py` defines `ROUND_DECIMALS = 5` with a comment claiming it
"matches check_duplicate_coordinates.py," but the constant is never
referenced anywhere in the file — the module's actual concentration check
uses the preserved `n_visits` column instead, per its own docstring.

## 2. Where encountered
`check_exotic.py:33` (before this fix): `ROUND_DECIMALS = 5   # ~1.1m -
matches check_duplicate_coordinates.py`.

## 3. What it caused to fail
No functional failure — the constant is unused. The impact is purely
cosmetic/confusing: a reader sees a constant claiming to match another
script's coordinate-rounding approach and could reasonably assume the
file still does coordinate-based deduplication, when `check_visit_concentration`'s
own comment already explains it switched to `n_visits`-based checking
because raw coordinates are always unique post-dedup.

## 4. What the defect was
```python
ROUND_DECIMALS = 5   # ~1.1m - matches check_duplicate_coordinates.py
```
with zero references to `ROUND_DECIMALS` anywhere else in the file
(confirmed via grep).

## 5. Root cause analysis (Five Whys)
1. Why is there a dead constant in the file? Because it's left over from
   an earlier version of the check that did coordinate rounding.
2. Why wasn't it removed when the check was rewritten to use `n_visits`?
   Because removing a constant that "looks like" configuration is easy to
   overlook during a logic rewrite — nothing breaks by leaving it.
3. Why does that matter enough to log as a bug rather than ignore? Because
   `CLAUDE.md` §2 counts "a defect found in review" broadly, and a stale
   constant actively misleads a reader about what the current
   implementation does — a real (if low-severity) defect in the code's
   trustworthiness as documentation of itself.

**Root cause:** a constant from a superseded implementation approach was
left in place when the approach changed, with nothing removing dead
configuration during the rewrite.

## 6. Corrective action
Fixed directly (trivial: deleted one unused line, no behavior change — no
CR required): removed `ROUND_DECIMALS` from `check_exotic.py`. Verified:
file parses, no remaining reference. **Status: CLOSED.**

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug concerns
dead/unused constants left over from a superseded implementation approach
within a single file (distinct from BUG-0002/0003/0004's cross-*file*
duplication). Result: **none found**.

## 8. Preventive action
No new preventive action — this is a single-instance, low-severity,
single-file cosmetic defect, not a recurring mechanism. Not every finding
needs a new standing rule; per `CLAUDE.md` §3, this list is for rules that
generalize, and "remove dead code during a rewrite" is already ordinary
code hygiene rather than a distinct failure mode worth codifying.
