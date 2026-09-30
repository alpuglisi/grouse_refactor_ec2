# BUG-0069: Diagnostic and OBS handlers report an unknown without the exception type

> Filed from CR-0018 lint candidate **C5** (`docs/quality/change-requests/CR-0018-pa0027-lint.md` §4),
> 2026-09-30. One BUG for the class; seven sites (keys in §2).

## 1. Description
Seven broad handlers in diagnostic scripts, OBS rows and map decoration
resolve an error to a visible "unknown" (a printed warning, an OBS row
marked skipped, a hash recorded as "not hashed"). PA-0027 allows that
outcome only if the printed or recorded reason includes the exception
type. Each of these printed only `str(e)`. For many exceptions `str(e)`
is empty or ambiguous (`KeyError('x')` prints `'x'`; an
`AssertionError()` prints nothing), so a programming error could not be
told from the expected condition the handler was written for (a missing
file, an offline download).

## 2. Where encountered
At `666474c`; found by the CR-0018 lint review, 2026-09-30. The PA-0027
sweep (BUG-0049 §8) classed each "visible unknown (diagnostic/OBS,
reason printed or recorded)" without checking the type clause.

| site | key | outcome |
|---|---|---|
| `acceptance_split.py:2620` | `full_run#0` | previous acceptance record unreadable -> `prev = None`, no OBS drift comparison, nothing printed |
| `analyze_grouse.py:658` | `load_state_boundaries#0` | boundary download failed -> map without state lines |
| `analyze_grouse.py:671` | `load_state_boundaries#1` | boundary file unreadable -> map without state lines |
| `check_exotic.py:71` | `check_sclass_meaning#0` | SClass table unreadable -> check not done |
| `check_raster.py:57` | `check_one#0` | raster unopenable -> "COULD NOT OPEN" |
| `check_road_dist.py:480` | `cmd_check#0` | OBS X1 row "skipped" |
| `symptom_check.py:663` | `region_point_frames#0` | file recorded as "not hashed" |

## 3. What it caused to fail
No gate, output file or training input is affected: every site is a
diagnostic, an OBS row, or map decoration, and each outcome is already
visibly non-success. The loss is diagnostic: a bug inside the `try`
(e.g. a `KeyError` in `rd.path(kind)`, a `TypeError` in the transform)
is reported with the same words as the expected condition. The
`acceptance_split.py:2620` site additionally prints nothing at all: an
unreadable previous record silently turns off the OBS drift comparison.

## 4. What the defect was
`analyze_grouse.py:658-662` and `:671-673`:
```python
        except Exception as e:
            print(f"  [!] Could not download state boundaries ({e}). "
                 f"Map renders without them; to fix, place any state "
                 f"boundary .geojson/.shp in {MAP_DATA_DIR}/")
            return None
...
    except Exception as e:
        print(f"  [!] Could not read boundary file {src}: {e}")
        return None
```
`check_exotic.py:71-73`:
```python
    except Exception as e:
        print(f"\n  Could not read {path}: {e}")
        return
```
`check_raster.py:57-58`:
```python
    except Exception as e:
        print(f"  [!] COULD NOT OPEN: {e}")
```
`check_road_dist.py:480-481`:
```python
        except Exception as e:  # observation only; never fails the check
            add("X1", "OBS", f"{r} records", f"skipped: {e}", "report")
```
`symptom_check.py:663-664`:
```python
            except Exception as e:          # path template naming differs
                files[f"{r}:{kind}"] = f"not hashed ({e})"
```
`acceptance_split.py:2616-2621`:
```python
            if os.path.exists(rec_full):
                try:
                    with open(rec_full, encoding="utf-8") as f:
                        prev = json.load(f).get("obs")
                except Exception:
                    prev = None
```

## 5. Root cause analysis (Five Whys)
1. *Why is the type missing?* Each message interpolates `{e}`, which is
   `str(e)`, the message only.
2. *Why only the message?* The authors wrote the message for the
   expected condition (network, missing file), where `str(e)` is
   informative, and did not consider an unexpected exception reaching
   the same handler.
3. *Why did an unexpected exception reach it?* The handlers are broad
   by design: they protect a non-essential step (decoration, an OBS
   row) from aborting the whole diagnostic. That is allowed by PA-0027
   only as a visible unknown **with the type**.
4. *Why was the type clause not applied?* The handlers predate PA-0027;
   the PA-0027 sweep checked "is the outcome visible?" and stopped
   there.
5. *Why did the sweep stop there?* A manual sweep with one question per
   handler; the rule's second condition was not a checklist item.

**Root cause:** broad handlers guarding non-essential steps reported
`str(e)` only, which cannot distinguish the expected failure from a
programming error, and PA-0027's type clause was never applied to them.

## 6. Corrective action
Trivial fixes, one function each, no signature/CLI/schema change, no CR.
Six sites fixed: each message now includes `type(e).__name__`; the
`analyze_grouse` read-failure and `check_exotic` messages also state the
consequence ("map renders without state boundaries", "SClass meaning
check not done"). Example (`symptom_check.region_point_frames`):
```python
            except Exception as e:          # path template naming differs
                files[f"{r}:{kind}"] = (f"not hashed "
                                        f"({type(e).__name__}: {e})")
```
Each fixed handler is now an `ALLOWLIST` entry of class
`visible-unknown` in `tests/test_pa0027_lint.py` citing this BUG,
replacing its candidate entry.

**Pending: `acceptance_split.py:2620`** (`full_run#0`). CR-0017 is
modifying `acceptance_split.py` on another branch, so it is not touched
here. Proposed fix (one function): `except (OSError, ValueError) as e:`
(unreadable or malformed JSON) with a printed line
`previous record unreadable (<type>: <msg>) - no OBS drift comparison`,
or keep the broad catch and print that line. Its lint entry moved from
`EXPECTED_UNCLASSIFIED` to `KNOWN_OPEN` under BUG-0069, same digest.
Owner: after CR-0017 merges.

**Verified:** `tests/test_cr0018_candidates.py::Bug0069VisibleUnknownType`
drives `check_raster.check_one` (non-raster file), `check_exotic`
(unreadable table), and both `analyze_grouse.load_state_boundaries`
handlers (garbage `.geojson`; download patched to raise `OSError`), and
checks the type is printed. All four fail on `666474c`.
`check_road_dist.cmd_check` and `symptom_check.region_point_frames` need
a real `GrouseData` to reach the handler; their change is the same
one-line message edit, covered by review and by the existing
`tests/test_check_road_dist.py` / `tests/test_symptom_check.py` still
passing.

Status: **PARTIALLY FIXED** (6 of 7 sites fixed in `0355240`; `acceptance_split.py:2620`
pending, owner: after CR-0017 merges).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for broad handlers,
PA-0011, PA-0027, "type".
- **BUG-0013 / PA-0011**: PA-0011 already required "log the exception
  type and traceback" (for retry loops). **BUG-0049 / PA-0027** widened
  the type requirement to every visible unknown. Siblings BUG-0052..0055,
  BUG-0063. **Recurrence** of the "type not recorded" half of the rule.

**Prior-preventive-action failure analysis (PA-0027, and PA-0011 before
it).** The rule's text covers every site. It failed as **not followed in
its own sweep**: the sweep listed these seven as conforming. That is a
verification failure (the sweep's classification was not checked
against the rule's clauses), not a gap in the rule. CR-0018's lint
closes the enumeration part: each of these handlers must now be an
explicitly reviewed `ALLOWLIST` entry pinned by digest, and the test's
comment requires a visible-unknown entry to print or record the type.
Whether the message carries the type is still judged by review (CR-0018
§5); a mechanical check (e.g. the handler body references
`type(<name>)`) is possible but is a lint change, so it is recorded as a
tracker item rather than done here.

## 8. Preventive action
**No new PA.** PA-0027 states the rule; CR-0018's lint enforces the
classification. Tracker item added: consider making the lint check that
a `visible-unknown` `ALLOWLIST` handler references `type(<exc name>)` or
`traceback` (owner: lead; needs a CR-0018 follow-up change). Sweep: the
lint's full list of non-conforming handlers at the fix head was re-read
for the type clause; every `visible-unknown` entry now records the type
(the pre-existing `acceptance_split.compute_obs` ×3 and `full_run#1`
already did). PA-0027 Swept? text for the lead:
`docs/quality/evidence/CR-0018-candidates-bookkeeping-rows.md`.
