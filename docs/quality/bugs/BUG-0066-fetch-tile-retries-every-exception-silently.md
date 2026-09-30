# BUG-0066: `fetch_tile` retries every exception, silently

> Filed from CR-0018 lint candidate **C2** (`docs/quality/change-requests/CR-0018-pa0027-lint.md` §4),
> 2026-09-30. Keys `('download_tcc_nlcd.py', 'fetch_tile', 0)` and
> `('download_treemap.py', 'fetch_tile', 0)` (duplicate code, one BUG).

## 1. Description
`fetch_tile` in `download_tcc_nlcd.py` and its copy in
`download_treemap.py` retry one Earth Engine tile download with
exponential backoff. The retry loop caught `Exception`, so a programming
error (a bad parameter, a `TypeError`) was retried like a network blip,
five attempts and about 30 s of sleeping per tile, and nothing was
logged per retry. On exhaustion it raised a `RuntimeError` carrying the
last message but not its type, and without chaining the cause. PA-0027's
retry clause requires: only transient types, bounded, raise on
exhaustion, type and traceback logged on each retry. Only "bounded" and
"raise on exhaustion" held.

## 2. Where encountered
- `download_tcc_nlcd.py:338` and `download_treemap.py:263` at `666474c`
  (the handlers in `fetch_tile`).
- Found by the CR-0018 lint, 2026-09-30. The PA-0027 sweep (BUG-0049 §8)
  classed both as "re-raise".
- Never observed failing in a run.

## 3. What it caused to fail
The run still fails closed (the `RuntimeError` propagates and
`_fetch_all` cancels the queued tiles), so no output is wrong. The
defects are diagnostic and cost:
- a deterministic error is retried 5 times with 2+4+8+16 s of sleep in
  each worker before surfacing;
- the final message drops the exception type and the original
  traceback (no `from e`), so the cause of a failed download has to be
  reproduced to be seen;
- transient failures that later succeed leave no trace in the log.

## 4. What the defect was
`download_tcc_nlcd.py:328-343` at `666474c` (`download_treemap.py:253-268`
is identical):
```python
    for attempt in range(retries + 1):
        try:
            url = image.getDownloadURL(params)
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            with open(dest, "wb") as f:
                f.write(r.content)
            with rasterio.open(dest):     # parse check
                pass
            return
        except Exception as e:
            if attempt == retries:
                raise RuntimeError(f"tile {rect} failed after "
                                   f"{retries + 1} attempts: {e}")
            time.sleep(delay)
            delay *= 2
```

## 5. Root cause analysis (Five Whys)
1. *Why was a `TypeError` retried?* The handler's type was `Exception`,
   not the transient types.
2. *Why `Exception`?* The loop wraps three libraries (Earth Engine,
   `requests`, `rasterio`) and the author did not enumerate their
   transient exception types.
3. *Why no per-retry log?* The loop was written for "eventually raise"
   and treated the intermediate failures as noise.
4. *Why did the PA-0027 sweep not flag it?* The sweep classed it as
   "re-raise" because the exhaustion branch raises. It checked the
   fail-closed half of the rule and not the retry clause.
5. *Why only half?* The sweep was a manual read with one question per
   handler ("where does the error branch go?"), not the rule's full
   list of clauses.

**Root cause:** a retry loop caught every exception type and logged
nothing per attempt, and the PA-0027 sweep's manual classification
checked only whether the loop eventually raised.

## 6. Corrective action
Trivial fix (one function per file, no signature/CLI/schema change), no
CR. In both files:
```python
        except (requests.exceptions.RequestException, ee.EEException,
                rasterio.errors.RasterioIOError) as e:
            # BUG-0066 (PA-0027 retry clause): only transient types are
            # retried (network, EE server, truncated GeoTIFF); anything
            # else propagates at once. Each retry is logged with its
            # type and traceback; exhaustion raises.
            if attempt == retries:
                raise RuntimeError(f"tile {rect} failed after "
                                   f"{retries + 1} attempts: "
                                   f"{type(e).__name__}: {e}") from e
            import traceback
            print(f"   [retry {attempt + 1}/{retries}] tile {rect}: "
                  f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                  file=sys.stderr, flush=True)
            time.sleep(delay)
            delay *= 2
```
Transient types: `requests.exceptions.RequestException` (connection,
timeout, HTTP status, chunked body), `ee.EEException` (EE server errors,
including quota and "too many requests"; a permanent EE error is still
bounded by the retry count as before) and `rasterio.errors.RasterioIOError`
(a truncated or HTML body that is not a GeoTIFF). Any other exception
now propagates on the first attempt. The handler now aborts on every
path, so the lint no longer flags it; both `EXPECTED_UNCLASSIFIED`
entries were removed.

**Verified:** `tests/test_cr0018_candidates.py::Bug0066FetchTileRetry`,
both modules: a `TypeError` is raised after 1 call; a `ConnectionError`
and an `EEException` are retried (3 calls at `retries=2`), each retry
logs type and traceback, the final `RuntimeError` names the type and
chains the cause; a non-GeoTIFF body is retried as `RasterioIOError`.
All fail on `666474c`.

Status: **FIXED** (`0355240`, branch `worktree-agent-a76c8932c8a2f4fc3`).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for retry loops,
PA-0011, PA-0027.
- **BUG-0013 / PA-0011** (superseded by PA-0027): the retry/polling loops
  in `download_rev.py` and `ebird.py` catching `Exception` and continuing.
  Same retry-loop mechanism; still OPEN and in the lint's `KNOWN_OPEN`.
- **BUG-0049 / PA-0027** and its sweep findings BUG-0052..0055, BUG-0063:
  the broad-handler family. **Recurrence** of the retry clause that
  PA-0027 inherited from PA-0011.

**Prior-preventive-action failure analysis.** PA-0011 (retry loops: prefer
narrow types, log type and traceback) was written for exactly this shape
and did not prevent it: these loops were written after PA-0011 and were
**not checked against it** (review only). PA-0027 restated the retry
clause, and its sweep **misapplied** it (classified "re-raise" on the
exhaustion branch alone). Both failures are review failures, not a
too-narrow rule. CR-0018's lint closes the enumeration gap: a retry
handler that does not abort on every path must be reviewed into the
`ALLOWLIST`, with a reason that cites the rule, before the test passes.
The remaining residual (a reviewer allowlisting a retry loop without
checking the retry clause) is review-only and is recorded in CR-0018 §5.

## 8. Preventive action
**No new PA.** PA-0027's retry clause is the rule; CR-0018's lint is its
enforcement (with this fix the two loops abort on every path and are not
flagged). Sweep of the retry-loop mechanism
(`docs/quality/evidence/CR-0018-candidates/sweep_retry_loops.py`, output
`sweep_retry_loops_output.txt`): 12 broad handlers sit inside a loop in
the lint's file set after the fix. Two abort on every path
(`_fetch_all` ×2). Of the ten that do not, the retry/polling loops are
BUG-0013's (`download_rev.download_one`, `ebird.main`; open,
`KNOWN_OPEN`); the rest are not retries: per-stage or per-gate loops in
`acceptance_split.py` (error recorded as FAIL / mismatch, allowlisted),
per-region OBS in `check_road_dist.cmd_check` and per-file hashing in
`symptom_check.region_point_frames` (BUG-0069), `dataset._close_handles`
(cleanup) and `download_tcc_nlcd.resolve_collection` (candidate
fallback). No other retry loop with a broad handler.
PA-0027 Swept? text for the lead:
`docs/quality/evidence/CR-0018-candidates-bookkeeping-rows.md`.
