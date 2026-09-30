# BUG-0053: `load_evt_crosswalk` treats an unreadable EVT table as "no table", and the pipeline carries on with `evt_phys = "Unmapped"` (PA-0027 sweep)

## 1. Description
`analyze_grouse.load_evt_crosswalk` returns `None` both when no
`LF*_EVT.csv` exists and when reading the newest one raises any
exception. Both callers treat `None` as the documented "table not
downloaded yet" case, print a warning and carry on:
- `analyze_grouse.py` sets every record's `evt_phys` and `evt_group` to
  `"Unmapped"`. The stratified KDE collapses to one stratum, and
  `envelope_id`, whose scheme starts with `EVT_PHYS`, is built from
  `"Unmapped"`.
- `generate_negatives.py:406-410` computes the candidates' `evt_phys` and
  weights the same way.

So a corrupt table, or a programming error inside `pd.read_csv`, produces
fully written, degraded outputs and exit 0.

## 2. Where encountered
PA-0027 §3.5 sweep (BUG-0049 §8), 2026-09-30:
- `analyze_grouse.py:343-347`;
- callers at `analyze_grouse.py:1107-1110` and `:792-798`, and
  `generate_negatives.py:406-410`.

## 3. What it caused to fail
- **Observed:** nothing. Today's table reads cleanly, and its sha256 is
  pinned by CR-0013's config.
- **Possible outcome:**
  - `evaluated_sightings_R` and `envelope_metrics_R` would be rebuilt with
    `evt_phys = "Unmapped"`. That changes `envelope_id` and the envelope
    weights.
  - For the negatives, CR-0013's replay would catch it: it reads the
    pinned crosswalk and raises on a mismatch (§ Normative definitions,
    "Crosswalk"), and E10 recomputes `evt_phys`.
  - For `analyze_grouse.py`'s own outputs, S, CR-0013 takes the inputs as
    given (stated limit 1). The degradation would pass into the split
    unless CR-0007's gates caught it. Whether they would was not checked.

## 4. What the defect was
`analyze_grouse.py:339-347`:
```python
    files = sorted(glob.glob(os.path.join(raster_dir, "attribute_tables", "LF*_EVT.csv")))
    if not files:
        return None
    path = files[-1]  # lexicographic sort puts the newest LF year last
    try:
        tbl = pd.read_csv(path)
    except Exception as e:
        print(f"  [!] Could not read {path}: {e}")
        return None
```

## 5. Root cause analysis (differential analysis)
**Differential analysis:**
- **"No file".** Returning `None` is a designed, documented outcome
  (docstring: "Returns None if no table is on disk"). The callers
  implement a deliberate degrade for it.
- **"File present but unreadable".** This is not a designed outcome, but
  the broad handler maps it onto the same `None`. The callers cannot
  tell the two apart, so an error takes the degrade path, which reports
  success.

**Root cause:** a broad handler resolved an unexpected error to a
designed non-error outcome whose branch continues (BUG-0049's mechanism).

Whether "no file" should itself degrade rather than raise is a design
question. CR-0013 treats the crosswalk as a pinned, required input. That
question is outside this bug and is recorded in the tracker.

## 6. Corrective action
Commit `4683e3c` (trivial fix, no CR).

**Lead decision (2026-09-30):** the EVT crosswalk is a required input
(CR-0013 pins its path and sha256), so a missing crosswalk and an
unreadable one both **raise** (fail closed); neither degrades to
`None` / `"Unmapped"`. This settles the design question in §5, under
PA-0027's "a missing **required** input raises". A table that reads but
lacks `VALUE`/`EVT_PHYS` also used to return `None` and is treated the
same way.

`analyze_grouse.load_evt_crosswalk` now:
- raises `FileNotFoundError` (naming the glob and
  `download_attribute_tables.py`) when no `LF*_EVT.csv` exists;
- lets any `pd.read_csv` error propagate (the `try/except Exception` is
  deleted);
- raises `ValueError` (naming the path and the columns found) when
  `VALUE` or `EVT_PHYS` is missing;
- never returns `None`; the docstring says so.

Confinement check: the change is inside one function, with no signature,
schema, CLI or file-format change. The behaviour change is the defect
fix itself: every former `None` return now raises. The callers' `None`
branches (`analyze_grouse.py:787` in `analyze_region` and `:1110` in `__main__`,
`generate_negatives.py:407`) are now unreachable. They were left in
place so the fix stays inside one function; their removal is a tracker
item. `grouse_data.GrouseData.evt_crosswalk` still returns `None` when
the table is absent or malformed. It has no caller in tracked code; it is
a tracker item too.

Test: `tests/test_pa0027_fixes.py::Bug0053EvtCrosswalk`: missing table
-> `FileNotFoundError`, empty file -> `EmptyDataError`, a `read_csv`
`RuntimeError` propagates, missing columns -> `ValueError`, and the
newest valid table still loads. The four defect tests fail on the
pre-fix code. `tests/test_cr0012.py` (which runs `generate_negatives.py`
on a synthetic tree with a crosswalk) passes.

Status: **FIXED** (`4683e3c`).

## 7. Recurrence review
- **BUG-0049** (same pass): same mechanism.
- **BUG-0013 / PA-0011:** see BUG-0049 §7.
- **BUG-0035 / BUG-0030** (a masked source read as a legitimate value)
  have a related shape. They work on data values rather than exceptions,
  and PA-0017 covers them.

## 8. Preventive action
Covered by **PA-0027** (an unexpected error never resolves to a designed
success or degrade branch). No new rule.
