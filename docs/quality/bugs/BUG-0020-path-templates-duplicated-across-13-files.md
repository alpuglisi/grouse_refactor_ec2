# BUG-0020: 13 files independently hardcode paths that duplicate `PATH_TEMPLATES` (PA-0003 sweep finding)

## 1. Description
The PA-0003 sweep (run in response to a direct question about whether
preventive-action sweeps were actually being conducted — see BUG-0019)
found that `PATH_TEMPLATES` entries in `grouse_data.py` are independently
re-hardcoded as literal path fragments in at least 13 other files, with
`organize_project.py` — the script responsible for the project's on-disk
layout — reconstructing essentially the entire `PATH_TEMPLATES` table as
its own separate literal-string dict. No currently-wrong value was found
(unlike BUG-0005); this is a maintenance/drift hazard, the same class as
PA-0001's bounding-box duplication, not yet a manifested defect.

## 2. Where encountered
By `PATH_TEMPLATES` entry (representative locations; see the sweep detail
in this bug's discovery message for the full per-line list):
- **sightings**: `analyze_grouse.py`, `audit.py`, `organize_project.py`
  (x3), `ebird.py`, `sightings.py`.
- **evaluated / envelope_metrics / nonveg_flagged**: `analyze_grouse.py`,
  `audit.py`, `check_exotic.py`, `clean.py`, `prepare_training_data.py`,
  `dupe_check.py`, `tune.py`, `tune_bins.py`, `organize_project.py`.
- **thinned / train_positives / val_positives / block_assignments**:
  `clean.py`, `prepare_training_data.py`, `organize_project.py`.
- **negatives / train_negatives / val_negatives / gbif_candidates**:
  `gen_negs.py`, `generate_negatives.py`, `get_negatives.py`,
  `organize_project.py`.
- **bin_tuning**: `tune.py`, `tune_bins.py`, `organize_project.py`.
- **diagnostic_map**: `analyze_grouse.py`, `audit.py`,
  `organize_project.py`.
- **raster_dir default**: `analyze_grouse.py`/`audit.py` hardcode
  `RASTER_DIR = "data/landfire"` independently of `DataConfig.raster_dir`;
  `check_raster.py`, all `download*.py` scripts set their own output dir
  independently too.
- **attribute_dir default**: `analyze_grouse.py`, `audit.py`,
  `check_exotic.py` hardcode `"attribute_tables"` independently of
  `DataConfig.attribute_dir`.

**Worst offender: `organize_project.py`** reconstructs every single
`PATH_TEMPLATES` destination directory and filename-prefix convention as
its own literal table (its `DIR_LAYOUT`/prefix-rewrite dict), rather than
deriving any of it from `PATH_TEMPLATES` — structurally identical to
BUG-0005's root cause, just not yet manifested as an observed defect.

## 3. What it caused to fail
Nothing yet — every hardcoded copy currently matches its corresponding
`PATH_TEMPLATES` value. The risk is exactly PA-0001's mechanism: if
`PATH_TEMPLATES` is ever edited (a directory renamed, a naming convention
changed), none of these ~13 files' independent copies would follow, and
`organize_project.py` specifically would start moving files to — or
consumers would start searching for files at — the wrong location, with
no error, matching BUG-0005's exact failure mode (silently empty results)
or worse (misplaced files).

## 4. What the defect was
A structural pattern, not a single faulty line — e.g. `organize_project.py`'s
layout table hardcodes `"data/pipeline/evaluated_sightings_{region}.csv"`-
style fragments independently of `PATH_TEMPLATES["evaluated"] =
"data/pipeline/evaluated_sightings_{region}.csv"` in `grouse_data.py`,
repeated with equivalent independent hardcoding for every other template
entry across the files listed in §2.

## 5. Root cause analysis (Five Whys)
1. Why do 13 files hardcode paths independently instead of importing
   `PATH_TEMPLATES`? Because most of these files predate, or were written
   without reference to, `grouse_data.py`'s `PATH_TEMPLATES` being the
   documented single source of truth.
2. Why wasn't this caught by the original review? Because the original
   review found the *one instance* that had already drifted (BUG-0005,
   inside `grouse_data.py` itself, one method vs. another) but didn't
   extend PA-0003's sweep to every OTHER file using the same paths, at
   the time PA-0003 was written.
3. Why wasn't that sweep done at the time? Same root cause as BUG-0019 —
   the sweep step depends on the implementing session remembering to run
   it, and it wasn't run for PA-0003 until directly asked about.
4. Why does `organize_project.py` in particular reconstruct the whole
   table independently rather than importing it? Because it is
   responsible for *establishing* the layout other scripts then read via
   `PATH_TEMPLATES`, so it was plausibly written before or independently
   of `PATH_TEMPLATES` being formalized as the canonical reference,
   rather than being derived from it.

**Root cause:** `PATH_TEMPLATES` was introduced as a documented single
source of truth, but no migration swept the files that predated it (or
were written without reference to it) onto deriving their paths from it —
the same "duplicated constant, no propagation mechanism" mechanism as
PA-0001, applied to path strings instead of geographic bounding boxes.

## 6. Corrective action
**None implemented — deliberately deferred, scope too large for this
pass.** Migrating 13 files (worst: `organize_project.py`'s full layout
table) onto deriving from `PATH_TEMPLATES` is a substantial refactor
touching the project's file-layout logic — exactly the kind of change
`CLAUDE.md` §1 requires a CR and independent review for, not a
same-session trivial fix, especially since `organize_project.py` performs
file *moves* (higher blast radius than a read-only path lookup getting
it wrong). **Status: OPEN, recommend a CR** to introduce path-derivation
helpers (e.g. a function on `PATH_TEMPLATES` or a shared `paths.py`) and
migrate the ~13 files, prioritizing `organize_project.py` first since it's
both the worst offender and the file whose mistakes have the highest
blast radius (misplacing real files, not just misreading them).

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: **matches PA-0003**
exactly (found via the very sweep PA-0003 itself calls for) — same
mechanism as BUG-0005, now confirmed repository-wide rather than confined
to `grouse_data.py`.

**Prior-preventive-action failure analysis:** PA-0003 was written but,
per BUG-0019, never swept until now. This is not "the rule failed to
prevent a recurrence" in the sense of a new drift happening — no new
drift has happened yet — but it is exactly the risk PA-0003 exists to
name, now confirmed present at scale. Classified as **not yet enforced**
(same as BUG-0015's classification for PA-0012): the rule was correct,
the sweep obligation existed, neither had been executed until asked.

## 8. Preventive action
No new PA needed — this is exactly what PA-0003 already targets, now with
confirmed scope. Tracked via `PREVENTIVE_ACTIONS.md`'s new **Swept?**
column (PA-0015) as "yes — found repo-wide structural risk, see
BUG-0020, remediation deferred to a future CR."
