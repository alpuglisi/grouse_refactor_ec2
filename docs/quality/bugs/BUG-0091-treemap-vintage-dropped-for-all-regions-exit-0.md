# BUG-0091: `generate_treemap_features.discover_vintages` drops a TreeMap vintage for every region when one region/attribute file is missing or invalid, remaps each year to the nearest surviving vintage, and the run exits 0

> Found by the 2026-09-30 static code review at `3b3e7d1`. Caller-side
> sibling of BUG-0071, which fixed the probe inside `_source_is_valid`
> and left this "warn and continue" as a design choice (CR-0018 §5).
> **Status: OPEN (low); owner: lead; trivial fix (one function).**

## 1. Description
`discover_vintages` walks `TREEMAP_YEARS` and, if any (region,
attribute) source is absent or fails validation, prints a warning and
skips that vintage **for all regions**. `plan_region` then maps every
one of our years to the nearest surviving vintage; its "far" warning
fires only for gaps over two years. The run writes plausible values
for four features × every year × three regions from the wrong vintage
and exits 0.

## 2. Where encountered
- `generate_treemap_features.py:244-253` (`discover_vintages`), `:386-388`
  (`plan_region` nearest mapping and gap warning).
- Trigger example: an interrupted `download_treemap.py` (which writes
  its final path directly, `:331`; BUG-0079's class) leaves one
  truncated `TreeMap2022_ME_BALIVE.tif`.

## 3. What it caused to fail
Latent. Scenario: one 2022 source file for ME is truncated → 2022 is
dropped for ME, NH and VT → 2022 records read 2020 stand structure with
a warning that reads like a normal skip; 2023 to 2025 records read 2020
with only the gap warning; exit 0. `filter_by_year_gap` sees a file for
every year and passes.

## 4. What the defect was
`generate_treemap_features.py:246-253`:
```python
    for v in TREEMAP_YEARS:
        missing = [(region, a) for region in regions for a in SOURCE_ATTRS
                  if find_source(src_dir, v, a, region) is None]
        if missing:
            print(f"   [warn] TreeMap {v}: missing {missing} - "
                  f"skipping this vintage entirely.")
            continue
        ok.append(v)
```

## 5. Root cause analysis (Five Whys)
1. *Why is a whole vintage lost?* The skip is per vintage across all
   regions and attributes.
2. *Why continue?* The author chose to run with what is present so a
   partial download still produces files.
3. *Why is the outcome invisible?* The mapping warning threshold is two
   years, the run exits 0, and nothing marks the outputs as built from
   a substituted vintage.
4. *Why not fixed with BUG-0071?* CR-0018 §5 limited that fix to the
   probe; PA-0027 does not reach a designed skip.

**Root cause:** a designed unit-of-a-batch skip (a vintage) with no exit
code and no output marking, the same mechanism as BUG-0081.

## 6. Corrective action
**None yet.** Trivial fix: raise `SystemExit` naming the missing files
unless an explicit `--allow-missing-vintages` is passed, and when it is,
tag every written file with the vintage actually used
(`GROUSE_TREEMAP_VINTAGE`) and exit non-zero. Status: **OPEN (low)**.
Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** as BUG-0081. **Matches:** BUG-0071 (probe side of the same
function chain), BUG-0049/BUG-0070 (unit skips), PA-0027.

**Prior-preventive-action failure analysis.** As BUG-0081: PA-0027 is
keyed to exception handlers; CR-0018 §5 named this caller-side skip as
outside the lint's reach and no rule replaced it.

## 8. Preventive action
**PA-0038** (filed under BUG-0081) covers it; the sweep there lists
this site. No separate rule.

## Cross-references
BUG-0071, BUG-0079, BUG-0081; CR-0018 §5; PA-0027, PA-0038.
