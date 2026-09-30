# BUG-0013: Broad `except Exception` blocks swallow all error types in download/polling loops

## 1. Description
The LandFire/GBIF job submission and status-polling loops across the
download scripts catch `Exception` broadly, print, and `continue`/`break`
without logging tracebacks or distinguishing transient network failures
from programming errors. **Updated by the PA-0011 sweep** (run in response
to BUG-0019): the same mechanism also exists in `ebird.py`'s day-by-day
polling loop, a 7th file not in the original catalogue.

## 2. Where encountered
`download_landfire.py:114-118` and equivalent blocks in
`download_landfire_2.py`, `download_landfire_3.py`, `download.py`,
`download_more.py`/`download_rev.py` (status-poll loops). **Added by the
PA-0011 sweep:** `ebird.py:107-108`, structurally identical — a day-by-day
polling loop over a full year calling `session.get()`, with a broad
`except Exception as e: print(f"...{e}")` wrapping the network call plus
response/JSON/CSV-handling logic, silently continuing to the next date on
any exception.

## 3. What it caused to fail
A genuine programming error (e.g. an `AttributeError` from a malformed
response, a `KeyError` from an unexpected JSON shape) is caught by the same
`except Exception` block as a transient network failure, printed as if it
were a routine retry-worthy condition, and the loop continues/skips —
masking bugs in the polling logic itself as if they were server-side
flakiness. No traceback is logged, making root-causing a real failure
difficult after the fact.

## 4. What the defect was
```python
except Exception as e:
    print(...)
    continue
```
(pattern repeated across the download scripts' submit/poll loops, with
minor variations in the printed message and `continue` vs. `break`).

## 5. Root cause analysis (Five Whys)
1. Why can a real bug in the polling logic go unnoticed? Because it's
   caught by the same handler as a transient network error and treated the
   same way (print and move on).
2. Why is the exception handling this broad? Because `except Exception`
   was used defensively to keep long-running download jobs from dying on
   any single unexpected error.
3. Why wasn't a narrower exception type used instead (e.g.
   `requests.exceptions.RequestException`)? Because narrowing requires the
   author to enumerate the specific failure modes worth tolerating, which
   is more effort than a blanket catch-all.
4. Why does this pattern repeat across so many files? Because it was
   likely copied along with the rest of the submit/poll loop structure
   each time a new download script was created from an earlier one (the
   same copy-based workflow implicated in BUG-0002/0003/0004).

**Root cause:** defensive coding favored a blanket `except Exception` over
narrower, intentional exception types in retry/polling loops, and this
pattern was propagated by copying the loop structure into each new download
script.

## 6. Corrective action
None implemented yet — documentation-only pass. Low severity; recommended
as a lower-priority cleanup: narrow to `requests.exceptions.RequestException`
(or the library's specific transient-error types) where retryable, and
log `traceback.format_exc()` before continuing when a broad catch is kept
intentionally. Status: **OPEN** (now covering 7 files, 21 call sites).

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug specifically
concerns exception-handling breadth (distinct from BUG-0002/0003/0004,
which concern fixes not being backported, not exception scope). Result:
**none found**.

**PA-0011 sweep addendum:** the sweep also checked all other files for
narrow-exception counterexamples and found two: `get_negatives.py:72` and
`download_attribute_tables.py:115` already correctly use
`requests.exceptions.RequestException` rather than a broad catch —
evidence the narrower pattern was known and used elsewhere in the
codebase, just not applied consistently to every retry/polling loop.

## 8. Preventive action
**PA-0011** (see `PREVENTIVE_ACTIONS.md`): prefer narrow exception types
(e.g. `requests.exceptions.RequestException`) over bare `except Exception`
in retry/polling loops; if a broad catch is genuinely necessary, log the
exception type and traceback before continuing so a programming error isn't
silently treated as a transient failure.
