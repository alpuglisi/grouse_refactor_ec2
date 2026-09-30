# BUG-0047: The analysis CRS `"EPSG:5070"` is a string literal in 16 places in 7 files (PA-0025 sweep, item d) — OPEN, deferred

## 1. Description
The project's analysis CRS (CONUS Albers, EPSG:5070) is written as a
literal wherever a transformer is built. It is also encoded in the column
schema (`x_5070`, `y_5070`) and, once CR-0012 lands, in
`BLOCK_ORIGIN_5070`.

## 2. Where encountered
PA-0025 §3.5 sweep, item (d). AST count of string constants equal to
`"EPSG:5070"` in the P6 scan set (git-tracked `*.py` minus
`inv_*`/`res_*`, `tests/`, `docs/`, `legacy/`), 2026-09-30:

| file | lines |
|---|---|
| `analyze_grouse.py` | 691, 718, 740 |
| `clean.py` | 90 |
| `diagnose_road_bias.py` | 89, 98 |
| `download_tcc_nlcd.py` | 293, 316, 318, 425 |
| `download_treemap.py` | 223, 247, 249, 318 |
| `generate_negatives.py` | 95 |
| `prepare_training_data.py` | 92 |

16 literals in 7 files. `legacy/audit.py` (3) and `legacy/gen_negs.py` (1)
are guarded stale copies. `dataset.py`, `grouse_data.py` and
`realign_rasters.py` contain the string only in comments.

## 3. What it caused to fail
Nothing observed; every copy agrees. Latent: changing the analysis CRS in
one place would silently mix coordinate systems. Because the value is also
in column names, a constant alone would not prevent that.

## 4. What the defect was
For example, `analyze_grouse.py:691` (post-CR-0007 line numbering):
```python
    to_albers = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
```
and `download_treemap.py:247`, an Earth Engine export parameter:
```python
        "crs": "EPSG:5070",
```

## 5. Root cause analysis
Same root cause as BUG-0043 (no shared definition, no check). PA-0001
names "CRS" as an example, but its sweep covered only `BOXES`.

Differential note: not every `"EPSG:5070"` is the same quantity. The
downloaders' value is Earth Engine's delivery lattice. The analysis
modules' value is the metric CRS for distances, KDE and blocks. One
constant for both would couple two independent choices.

**Root cause:** as BUG-0043. It is left separate because the remediation is
a schema question (`x_5070`/`y_5070`, `BLOCK_ORIGIN_5070`), not a simple
re-point.

## 6. Corrective action
**None yet — open, deferred.** Owner: **CR-0007's author**, who opens a CR
after CR-0012 lands. Tracked in `docs/quality/CR-0007-0008-OPEN-ISSUES.md`
(the "Analysis-CRS constant" item). Reason for deferral (CR-0007 deliverable
6, sweep item (d)): the CRS is also encoded in the `x_5070`/`y_5070` schema
and in CR-0012's `BLOCK_ORIGIN_5070`, so a constant alone protects nothing.
The downloaders' EPSG:5070 is a different quantity and must stay separate.

Status: **OPEN** (deferred; owner named above).

## 7. Recurrence review
Swept under PA-0025 (BUG-0043); see its recurrence review against
BUG-0001/PA-0001, whose example list already named "CRS".

## 8. Preventive action
Covered by **PA-0025**. When the owning CR adds the constant, it adds the
name and pin to `tests/test_shared_constants.py` and `check_partition.P6_NAMES`.
No new rule.
