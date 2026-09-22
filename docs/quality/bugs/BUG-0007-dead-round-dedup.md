# BUG-0007: No-op `.round(5)` call in negative-sample dedup gives false impression of rounding-based dedup

## 1. Description
`generate_negatives.py` and `gen_negs.py` both contain a `drop_duplicates`
call that appears to dedupe on coordinates rounded to 5 decimal places, but
`.round(5).columns.tolist()` doesn't actually apply the rounding to the
dedup key — it just yields the unchanged column name list. The real
rounded-key dedup happens in the next two lines, which are correct; the
first call does nothing beyond dropping bit-for-bit exact duplicates.

## 2. Where encountered
- `generate_negatives.py:165-169`
- `gen_negs.py:157-161` (identical)

## 3. What it caused to fail
No incorrect output — the subsequent lines correctly recompute the rounded
key and dedupe on it. The defect is dead/misleading code: a reader (or
future editor) sees what looks like the intended rounding-based dedup logic
in the first call and could reasonably assume it's load-bearing, when it
isn't, or could remove the second (correct) block thinking it's now
redundant with the first.

## 4. What the defect was
```python
cand = cand.drop_duplicates(
    subset=cand[['longitude', 'latitude']].round(5).columns.tolist()
)
coords_key = cand[['longitude', 'latitude']].round(5)
cand = cand.loc[~coords_key.duplicated()].copy()
```
`.round(5)` rounds the *values*, but `.columns` reads off the *column
names*, which `.round()` doesn't touch — so `.round(5).columns.tolist()`
is exactly equivalent to `.columns.tolist()`, i.e. `['longitude',
'latitude']`. The first `drop_duplicates` call therefore dedupes on raw,
unrounded coordinates.

## 5. Root cause analysis (Five Whys)
1. Why does the first `drop_duplicates` call do nothing useful? Because
   its `subset=` argument evaluates to the same plain column list as
   omitting `subset=` and using raw values.
2. Why does `.round(5).columns.tolist()` not apply rounding to the dedup
   key? Because `.round()` returns a DataFrame with the same column
   *names*, and only `.columns` (names) is read from the result, not the
   rounded values.
3. Why was this written this way? The author intended to build a "rounded
   coordinate" key but wrote a chained call that extracts a value-blind
   metadata (`.columns`) from an otherwise value-transforming operation
   (`.round()`) — a plausible copy/refactor slip where `subset=[...]`
   should have been `subset=cand[['longitude','latitude']].round(5)` used
   as an actual joined key, not reduced to column names.
4. Why wasn't this caught before now? Because the code produces correct
   final output (the second, correct block masks the first block's
   ineffectiveness) — there was no test or review step that would surface
   a no-op line as long as overall behavior was right.

**Root cause:** a copy/paste or refactor error extracted `.columns` from a
`.round()` result instead of using the rounded values themselves as the
dedup key, producing dead code that happens to be harmless only because a
second, correct block immediately follows it.

## 6. Corrective action
None implemented yet — documentation-only pass. Recommended: delete the
first (no-op) `drop_duplicates` call in both files, since the following two
lines already perform the correct rounded-key dedup. Status: **OPEN**.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug concerns
dead/no-op code from a misapplied `.round()`/`.columns` chain. Note this
bug exists identically in both `generate_negatives.py` and `gen_negs.py`
(the same duplicate-file pair as BUG-0004) — it is not itself an instance
of the "fix not backported" mechanism (BUG-0002/0003/0004), since neither
copy has the bug fixed; it's present, unfixed, in both. Result: **none
found** for this specific mechanism (dead code from a misapplied chained
call).

## 8. Preventive action
**PA-0005** (see `PREVENTIVE_ACTIONS.md`): when deduplicating on rounded/
normalized values, build the dedup key as its own variable first (e.g.
`key = df[cols].round(n)`) and dedupe on that key directly — never chain
`.round()` into `.columns` expecting it to carry the rounding into a
`subset=` argument.
