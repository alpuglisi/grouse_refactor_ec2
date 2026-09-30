# BUG-0065: `download_rev.published_products` reports any failure as "listing unreachable"

> Filed from CR-0018 lint candidate **C1** (`docs/quality/change-requests/CR-0018-pa0027-lint.md` §4),
> 2026-09-30. Key `('download_rev.py', 'published_products', 0)`.

## 1. Description
`published_products(year)` fetches the LFPS ArcGIS folder listing and
parses the product codes. Any exception in the fetch or the JSON parse
was caught by `except Exception` and turned into `None`. The caller
prints "product listing unreachable" and submits jobs without the
pre-flight check. The exception type was printed nowhere, so a parser
or programming error (for example an `AttributeError` if the listing
JSON is not an object) read as a network outage.

## 2. Where encountered
- `download_rev.py:149` (handler) at `666474c`, in `published_products`;
  its caller `build_tasks`-loop at `download_rev.py:375-378`.
- Found by the CR-0018 lint (`tests/test_pa0027_lint.py`), 2026-09-30.
  Not in the PA-0027 sweep (BUG-0049 §8), although the handler existed
  when the sweep ran (`4683e3c^:download_rev.py:145`).
- Never observed failing in a run.

## 3. What it caused to fail
Nothing is downloaded wrongly: `None` means "no pre-flight", and each
job then fails or succeeds on its own, as before the check existed. The
defect is diagnostic. The run log says "unreachable" for every failure,
so a real parser bug (a change in the listing's JSON shape) would be
hidden behind a message that points at the network, and the pre-flight
would silently stay off for every run.

## 4. What the defect was
`download_rev.py:141-150` at `666474c`:
```python
    try:
        res = session.get(f"{SERVICES_URL}/{folder}", params={"f": "pjson"},
                          timeout=30)
        if res.status_code != 200:
            return None
        services = res.json().get("services") or []
    except Exception:
        return None
```
and the caller, `download_rev.py:375-378`:
```python
                    listings[year] = published_products(year)
                    if listings[year] is None:
                        log(f"  [~] LF{year}: product listing unreachable "
                            f"- will try jobs without a pre-flight check.")
```

## 5. Root cause analysis (Five Whys)
1. *Why could a parser bug read as "unreachable"?* The handler returned
   the same `None` for every exception and printed nothing; the caller's
   only message names one cause.
2. *Why one message?* `None` was designed as "listing unavailable -> fall
   back to the pre-check-free path" and the author thought only of
   network failures.
3. *Why was the type not printed?* PA-0027 requires a visible unknown to
   print the exception type; the handler was written (`a995898`, LFPS pre-flight listing) before
   PA-0027 existed and was never re-checked against it.
4. *Why was it not re-checked?* The PA-0027 sweep (BUG-0049 §8) was a
   manual read of the tree and did not list this handler at all.
5. *Why did the manual sweep miss it?* Enumeration by reading, with no
   mechanical list of broad handlers to tick off.

**Root cause:** a broad handler resolved every error to a fallback value
without recording the exception type, and the only enumeration of such
handlers (the PA-0027 sweep) was manual and incomplete.

## 6. Corrective action
Trivial fix (one function, no signature/CLI/schema change), no CR:
the handler now logs the URL, exception type and message before
returning `None`:
```python
    except Exception as e:
        # BUG-0065 (PA-0027): the caller's "unreachable" message cannot
        # tell a network error from a parser bug; print the type here.
        log(f"  [~] LF{year}: product listing {SERVICES_URL}/{folder} "
            f"failed ({type(e).__name__}: {e}) - treated as unavailable")
        return None
```
The fallback (run jobs without the pre-flight) is unchanged: it is the
pre-existing behaviour and each job still fails on its own. The handler
is now `ALLOWLIST` (visible-unknown) in `tests/test_pa0027_lint.py`,
replacing the `EXPECTED_UNCLASSIFIED` candidate entry.

**Verified:** `tests/test_cr0018_candidates.py::Bug0065PublishedProducts`
(a `ValueError` from `res.json()` and a `ConnectionError` are each
printed with their type; a well-formed listing still parses). Both
error tests fail on `666474c`.

Status: **FIXED** (`0355240`, branch `worktree-agent-a76c8932c8a2f4fc3`).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for broad handlers,
PA-0011, PA-0027.
- **BUG-0049 / PA-0027**: same mechanism (broad handler resolving to a
  non-failure outcome without the type). **Recurrence.** Siblings from
  the PA-0027 sweep: BUG-0052 (the validity probe in this same file),
  BUG-0053..0055; BUG-0063 (test setup). BUG-0013 / PA-0011 (superseded)
  is the family's origin.

**Prior-preventive-action failure analysis (PA-0027).** The rule's
text covers this handler (a visible unknown must carry the type). It
failed as **not enforced / sweep incomplete**: the handler predates the
rule, and the rule's §3.5 sweep was a manual read that did not list it.
The sweep, not the rule, was the gap. CR-0018's lint enumerates every
broad handler mechanically from the AST and fails on any unclassified
one, so a handler can no longer be missed by a sweep; this is the
enforcement that closes the gap (it is how this instance was found).

## 8. Preventive action
**No new PA.** PA-0027 already states the rule; CR-0018's lint
(`tests/test_pa0027_lint.py`) is its mechanical enforcement and now pins
this handler as a reviewed `ALLOWLIST` entry. PA-0027 Swept? update for
the lead: `docs/quality/evidence/CR-0018-candidates-bookkeeping-rows.md`.
Sweep: the lint itself is the by-mechanism sweep (every broad handler in
the tracked file set); CR-0018 §4 lists its results, filed as
BUG-0065..0071.
