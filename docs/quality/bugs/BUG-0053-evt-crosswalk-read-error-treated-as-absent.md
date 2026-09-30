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
**None yet.** The fix is confined to one function: let the read error
propagate, either by deleting the `try` or by adding context and
re-raising. That meets the trivial-fix test, so no CR is needed; a BUG is
required. This pass is documentation only. Owner: the next change to
`analyze_grouse.py` (tracker).

Status: **OPEN**.

## 7. Recurrence review
- **BUG-0049** (same pass): same mechanism.
- **BUG-0013 / PA-0011:** see BUG-0049 §7.
- **BUG-0035 / BUG-0030** (a masked source read as a legitimate value)
  have a related shape. They work on data values rather than exceptions,
  and PA-0017 covers them.

## 8. Preventive action
Covered by **PA-0027** (an unexpected error never resolves to a designed
success or degrade branch). No new rule.
