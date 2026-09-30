# CR-0018 review log

Verdicts, concern dispositions and revision history for
`CR-0018-pa0027-lint.md`. The CR states only current intent (CR-0011 A4).
Reviewers: A and B, independent general-purpose agents, neither the author.

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 (`6773aa4`) | A | REQUEST CHANGES | R-A1 |
| 1 | v1 (`6773aa4`; B's HEAD `73a08ec`, CR-0018 files unchanged) | B | REQUEST CHANGES | B1 |
| 2 (bounded, A2) | v2 (`8a42b6e`) | A | APPROVE WITH FOLLOW-UPS | — |
| 2 (bounded, A2) | v2 (`8a42b6e`) | B | APPROVE WITH FOLLOW-UPS | — |
| — | v2.1 | author | APPROVE | — |

**Approval: author + reviewers approved; user pre-authorised (2026-09-30).**
Status APPROVED. v2.1 differs from the reviewed v2 only by the two §5
known-limit bullets asked for in B11/B12, the status line and the
deliverable ticks; no rule, code or classification change.

## Concerns and dispositions

### Round 1
Every correction below was verified by the author against the code
before it was applied.

| id | sev | concern (short) | disposition |
|---|---|---|---|
| R-A1 = B1 | BLOCKING | `always_aborts` was `any(...)`: an early `return`/`continue`/`break` before a `raise` passed (A: M1, M2, M5, M6, M8; B: M3, M4, M5, M9 — M9 is the BUG-0049 per-region skip). | **Accepted, revised.** Verified: `violations()` returned `{}` for A's M1 on `generate_negatives.main`. `always_aborts` now walks statements in order; `_escapes` fails the block on any `return`, or a `break`/`continue` not inside a loop nested within it (nested scopes ignored, `finally` included). Nine new positive controls (T1) and two new negative controls (T2). A's M1 now flagged; the repository result is unchanged (the 10 mechanically conforming handlers have no escape, as B's enumerator also found). CR §2. |
| R-A2 = B3 | MAJOR | The "with the exception type" criterion was used for C1 but not applied to allowlisted visible-unknown entries; `diagnose_training.py:52` and `diagnose_water_bias.py:115` skip a region. | **Accepted, revised.** One criterion, PA-0027's text: a visible-unknown entry must print or record the type. Verified each site. Eight entries without the type moved to `EXPECTED_UNCLASSIFIED`: seven as **C5** (LOW) and `git_commit` under C4; the two region skips as **C6** (MEDIUM, BUG-0055 shape). Fail-closed entries (e.g. `gate_E0`) are not visible-unknown and keep their class: PA-0027 attaches the type requirement to "unknown" only. CR §3, §4. |
| R-A3a = B2 | MAJOR | `ee_init` ×2 reason false: `except Exception as persistent_err: pass` unbinds the name, so the SystemExit f-string raises `UnboundLocalError`. | **Accepted.** Verified (Python 3 deletes the `as` target at the end of the clause; `download_tcc_nlcd.py:146,161`, `download_treemap.py:152,167`). Moved to `EXPECTED_UNCLASSIFIED` as **C3** (LOW, latent; still exits non-zero). |
| R-A3b = B4 | MAJOR | `git_commit` reason partly false: `build_manifest` writes `"dirty": bool(dirty)` (`acceptance_split.py:1185`), so unknown is recorded as clean. | **Accepted.** Verified at `:1185` vs `:2513`. Moved to `EXPECTED_UNCLASSIFIED` as **C4** (LOW). |
| R-A4 = B6 | MEDIUM | Digest pinned only the `ExceptHandler`; FALLBACK/`pass` entries depend on code after it (B: M10 deleting `collection_years`' fallback, M11 removing `raster_path`'s warning, both passed). | **Accepted, revised.** Digest now covers the handler and its whole enclosing scope. New T5 mutation (M10's shape) changes the digest. M11 is in a *caller* (`raster_path`), listed under §5 as review-only. |
| R-A5 | MEDIUM | (a) broad→narrow laundering then skip; (b) `SystemExit(var)`/`sys.exit(rc)` accepted; aliased `suppress`; `with suppress: raise`. | (b) **Accepted, revised**: an exit/`SystemExit` argument counts only if it is a non-falsy constant or an f-string; controls added. `with suppress(...)` accepted with B7. (a) and aliased `suppress`: **listed in §5** (known limit; none in the tree today). |
| R-A6 | LOW | `ast.dump` output changes on 3.13 (`show_empty`). | **Accepted, revised**: `show_empty=True` passed on 3.13+. |
| R-A7 | LOW | Risk cited T6 for re-derivation (is T8); evidence header not at the reviewed commit. | **Accepted**: Risk text fixed; evidence regenerated at the v2 head (deliverable 2 regenerates again at approval). |
| B5 | MEDIUM | `generate_treemap_features.py:179` probe → `False` → vintage skipped with a wrong cause, exit 0. | **Accepted.** Verified (`find_source` / `discover_vintages`, warning at the `discover_vintages` loop). Moved to `EXPECTED_UNCLASSIFIED` as **C7** (MEDIUM). `grouse_data.py:327` stays allowlisted: the sweep records its caller fallback as designed and recorded by E11(b); the reason now says so. |
| B7 | LOW | `with suppress(X): raise` accepted. | **Accepted, revised**: a `with` holding a `suppress(...)` item never aborts; control added. |
| B8 | LOW | Ordinal shift reported as "changed" + "new" without explanation. | **Accepted, revised**: failure output prints a re-key hint when a scope has both. |
| B9 | LOW | `docs/quality/evidence/` acceptance scripts excluded. | **Justified, listed in §5**: same file set as the precedent lint; none has a broad handler today. Tracker follow-up (owner: lead). |
| B10 | LOW | walrus / alias forms. | Already in §5 (walrus added to the text). No change. |
| B (T8 note) | LOW | `download_tcc_nlcd.py:209` fallback not printed; id parse not provably equal to timestamps. | **Kept allowlisted**, reason extended: an empty result aborts in the caller (`download_tcc_nlcd.py:507`), and the enclosing-function digest now pins the fallback. Tracker follow-up (LOW, owner: next change to `download_tcc_nlcd.py`). |

### Round 2 (bounded)
Both reviewers: every round-1 BLOCKING/MAJOR concern resolved (R-A1,
R-A2, R-A3a/b; B1–B4), no new BLOCKING or MAJOR.

| id | sev | concern (short) | disposition |
|---|---|---|---|
| A-r2 | MEDIUM | R-A5(a) laundering and the other §5 limits need a tracker row with an owner. | **Accepted**: tracker § "CR-0018 (2026-09-30)", owner lead. |
| A-r2b | LOW | Whole-function digests churn on large functions. | Accepted as designed (CR Impact). No change. |
| B11 | LOW | Run-time string exit messages (`SystemExit(msg)`, `+`, `.format`) over-flagged. | **Accepted as documented behaviour**: added to CR §5 (conservative; none today); tracker item, owner lead. |
| B12 | LOW | `yield` before `raise` in a handler conforms. | **Accepted**: added to CR §5; tracker item, owner lead. |
| B13 | LOW | Digest churn (same as A-r2b). | Accepted as designed. |
| B14 | MEDIUM (process) | Record that M11 remains a known limit. | Recorded: B6 row and round-2 T7 below; §5 caller limit. |

## Reviewer-built mutations (T7) and allowlist re-derivation (T8)
### Round 1
- **A, T7:** M1 conditional `return` before `raise`, M2 `return` then a
  dead `raise`, M5 loop `continue`, M6 `continue` in `with`, M8
  `try: return` / `finally`: all missed on v1 (R-A1). M3, a plain
  `return`: flagged. M7 laundering, M4/M9 `SystemExit(var)`: missed
  (R-A5). Scripts are in the session scratchpad, `reviewerA/`.
- **B, T7:** M1 (gate_E8 edited) and M2 (`atomic_write` `raise` → `return`)
  fail T6; M6 (inserted handler) fails. M3, M4, M5, M9 missed (B1); M8
  missed (B7); M10, M11 missed (B6); M7 walrus missed (known limit).
  Independent enumeration over 246 tracked files: the same 36
  non-conforming handlers and 10 conforming ones, none missing.
- **A, T8:** every non-`acceptance_split.py` entry plus five
  `acceptance_split.py` entries. Confirmed except `diagnose_*` (R-A2),
  `ee_init` (R-A3a) and `git_commit` (R-A3b).
- **B, T8:** every entry. Confirmed except as B2–B5 and the `:209` note.
### Round 2
- **A, T7 on v2:** M1, M2, M4, M5, M6, M8, M9 now flagged; M3 flagged;
  M7 (laundering) missed, §5. Extra probes M10–M17 (for-else continue,
  if-raise/else-continue, `SystemExit(msg_var)`, nested handler return,
  match/case return; inner while/break, `async with` raise, lambda) all
  behave as the v2 rule states.
- **B, T7 on v2:** M1–M6, M8, M9, M10 fail T6 (M6 prints the re-key
  hint); M7 (walrus) and M11 (caller) missed, both §5. Independent
  path-sensitive enumerator: same 36 handlers.
- **v2 check by the author:** A's M1 on `generate_negatives.main` →
  flagged; every v1 positive/negative control keeps its result.

## Revision history
- v1 (`6773aa4`): initial draft, gate code committed under A3.
- v2: round-1 dispositions above. Rule (early exits, exit arguments,
  `suppress` in `with`), digest scope, 3.13 dump; ALLOWLIST 30 → 17,
  candidates 3 → 16 sites (C1–C7).
- v2.1: round-2 dispositions (B11, B12 to §5), APPROVED; deliverables
  ticked; bookkeeping rows and tracker entries written.
