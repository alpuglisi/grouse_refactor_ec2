# CR-0014 review log

## Lineage
Split out of CR-0008 at v8 (2026-09-30): CR-0008 v7's `road_dist` ME/VT
scope. v7 text: commit `bb170ea`. Every carried item from v7 and from
accepted dispositions, and where it now lives:

| carried item | source | in CR-0014 v1 |
|---|---|---|
| Regenerate ME/VT at TIGER 2023 | v7 §2, user decision | §1–§2; NH added (Canada rule) |
| `_download` atomicity | v7 §2 | §1 |
| Densified footprint reprojection | v7 §2, CR-0008 R8-B2 | §1 |
| `TIGER_YEAR` pinned 2023 | v7 Settled decisions; user 2026-09-30 | §1 |
| Canadian-border roads | CR-0008 R7-4 (user: nodata) | §1 Canada rule, R2, BUG-0037 |
| G7 RD1–RD4, strata, 60 m derivation | v7 G7 | Acceptance |
| Truth from every county ∩ grid+pad (PA-0018) | v7 G7 precondition 2, round 6 #8 | Acceptance |
| Excluded-point count gated at 0 | round 6 #2 | RD5 |
| RD5 (no nodata inside coverage) | round 6 #2 | R2 (now: nodata ∩ T = C exactly) |
| All 10 year-copies byte-identical | CR-0008 R7-10 | R3 |
| G6 for regenerated files | CR-0008 R7-17 | R6 |
| 8 uncached VT counties (network available) | v7; R7-11 | Deliverable 3 |
| BUG-0023 §6 retroactive-review ruling for `bf8d31a` | round 6 #16 | Deliverables |
| `tiger_at1` G0 pins | v7 G0 table | R0 |

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | B — implementability + §1 (fresh) | **REJECT** | 1 (+4 MAJOR) |
| 1 | v1 | A — correctness (fresh) | **APPROVE WITH FOLLOW-UPS** | 0 (1 MAJOR) |

## Dispositions
Round 1, reviewer B. All applied in **v2** (written at the user's request
while reviewer A was still reviewing v1; A's findings will be checked
against v2).

| # | sev | concern | disposition |
|---|---|---|---|
| B1 | BLOCKING | D1 pins VT's `C` before D3 fetches the 8 VT counties; 6 of them intersect the VT grid itself (Clinton NY 36019, 27.8 % in-grid, to the Quebec border). A pin without them over-masks; fetching into `data/roads` before approval violates A3 | **Accept** — the verifier keeps its own TIGER copy in `~/.cache/grouse_cr0014/` (fetched before approval, outside `data/`) and pins `C` from it; `data/roads` fetch stays after approval (D3); R0b requires the generator's zips byte-identical to the verifier's |
| B2 | MAJOR | R2 exact equality needs a pinned `C` recipe: 5,238 NH in-T pixels have \|D_can − D_road\| < 20 m, so decoded-vs-float, pad rounding, `all_touched`, road set, tie rule, evt file all flip pixels. NH `C` = 109,251 reproduced from decoded current raster | **Accept** — recipe pinned in §1 (float64 before encoding, pad 333 px, `all_touched`, road set, MTFCC, sampling, strict `<`, `{R}_2024_evt.tif`); `C` pins never from current rasters |
| B3 | MAJOR | A3 not met: RD thresholds restated in prose; verifier and pins not committed before approval | **Accept** — D1 is a pre-approval deliverable: verifier + pins committed and reviewed before approval |
| B4 | MAJOR | A5 not addressed: no stated reason for not splitting | **Accept** — one-CR justification added under Order |
| B5 | MAJOR | BUG-0037 §4: recurrence of PA-0017/0018 (generator docstring `:74-78` already knew); needs prior-PA failure analysis, PA decision (next free PA-0023), §3.5 sweep scope | **Accept** — D8 names the §4 recurrence review, prior-PA failure analysis, PA-0023 (extends PA-0018) and its §3.5 sweep scope |
| B6 | MEDIUM | Tracker says I17 unaffected — false once CR-0014 changes 140 ME / 717 VT positives; no reciprocal owner in CR-0012 (not drafted); B-9 now CR-0014's | **Accept** — Impact states I17 changes; tracker I17 line corrected; B-9 marked moved to CR-0014 |
| B7 | MEDIUM | v7's restore rehearsal dropped silently | **Accept** — restore rehearsal in the Test plan and D5 |
| B8 | MEDIUM | BUG-0037 id collision with the untracked draft-rows file | **Accept** — BUG-0037 reserved in the tracker; the untracked draft-rows file's proposed BUG-0036/0037 must be renumbered (BUG-0036 is already the encoder bug) |
| B9 | LOW | (a) digests are sha256 first 32 hex; (b) `testzip` raises on truncation, clean `.part`; (c) pad_px x-res note and "nearest road outside grid+pad" exception class dropped; (d) "about 19" stated twice; (e) bug status vs §6 deviation; (f) verifier input-dir option; (g) densification changes no county today — U4 trivial; (h) refusal message names CR-0010 only | **Accept** all: (a) stated; (b) `BadZipFile` counts as invalid, `.part` removed; (c) pad_px note restored, X3 reports the exception class; (d) stated once; (e) status vs deviation distinguished in D8; (f) verifier `--root`; (g) stated in §1; (h) refusal message generalised |

Round 1, reviewer A (reviewed v1; checked against v2/v3). Measured the
Canada rule in all three regions: no US over-masking (every `C` pixel's
nearest `L` is Canadian); St. Lawrence, Missisquoi Bay, Memphremagog are
7292 and excluded; ocean and the LANDFIRE-extent gap are sentinels;
home-state-only, `all_touched=False`, a differently computed `C` and a
stale year-copy each fail a gate.

| # | sev | concern | disposition |
|---|---|---|---|
| A1 | MAJOR | R2 exact equality needs the verifier's `C` recipe pinned (float32 vs float64 differs on 57 VT / 96 NH px; exact ties 1,114 VT / 857 NH / 2,824 ME; evt 2022 vs 2024 differs) | **Resolved in v2** (recipe pinned) **+ v3**: evt pinned by sha256 in `cr0014_pins.json` and verified before use; strict `<` tie behaviour unit-tested |
| A2 | MEDIUM | Empty `L` → scipy EDT is finite → silent masking near a corner | **Accept** — v3: `D_can = +inf` if `L` empty; verifier returns empty `C`; U3 and the verifier's unit test cover it |
| A3 | MEDIUM | D1 before D3: VT `C` needs the 8 uncached counties | **Resolved in v2** (verifier's own TIGER copy, fetched before pinning) |
| A4 | MEDIUM | X2 exposure has no disposition: NH 6,884 px, VT 1,881 px (top edges), ME 0 — contradicts the Scope wording | **Accept as stated residual** — v3 Scope narrowed to "Canadian land within the grid"; residual measured and recorded in BUG-0037 as open until Canadian road data exists; X2 reports it. Tracker item |
| A5 | LOW | 60 m derivation wording (truth from pixel centre; ±21.2 m + encoding) | **Accept** — v3 text and the script docstring corrected |
| A6 | LOW | `testzip()` raises on truncation | **Resolved in v2**; verifier unit-tested (truncated download, poisoned cache) |
| A7 | LOW | Stratum 5 = ∂T or ∂(T\C)?; U4 trivially true | **Accept** — ∂T stated; U4 note already in v2 |

### Round 2 (bounded re-review of v3)
| reviewer | verdict |
|---|---|
| A — correctness | **APPROVE WITH FOLLOW-UPS** — A1–A7 resolved; `C` pins reproduced exactly (count and digest) in all three regions from an independent road copy; evt sha256 pins match |
| B — implementability | **APPROVE WITH FOLLOW-UPS** — B1–B9 resolved; all `C` and `T` pins reproduced exactly by an independent implementation (different county selection) |

| # | sev | concern | disposition |
|---|---|---|---|
| A8 | LOW | Script's X2 counts every non-US edge (incl. ocean), CR said "Canada-facing" | **Accept** — CR text aligned with the script: an upper bound on the residual |
| A9 | LOW | R6 silently skipped when a backup file is missing | **Accept** — now a failing R6 row |
| A10 | LOW | R1/R2 read one copy; sound only with R3 | **Accept** — commented in the script; R3 runs by default |
| B10 | LOW | `pin` overwrote the T pins with the verifier's own T (R0 would check itself) | **Accept** — `pin` now refuses if derived T ≠ pinned T and writes only C |
| B11 | LOW | R6 silently skipped without a backup | **Accept** — same fix as A9 |
| B12 | LOW | `check` on ME may peak at 15–20 GB | **Accept** — deliverable 6: one region at a time, never alongside the generator |
| — | note | Reviewer could not run the tests (no pytest) | They are `unittest`: `python -m unittest tests.test_check_road_dist` — 10 pass (author run) |

## Versions
| version | date | change |
|---|---|---|
| v1 | 2026-09-30 | Split from CR-0008 v7 |
| v2 | 2026-09-30 | Round-1 reviewer B dispositions |
| v3 | 2026-09-30 | Round-1 reviewer A dispositions; `check_road_dist.py`, pins and verifier tests written (pre-approval deliverable 1) |

## Quorum (§1.4)
Reviewer A: APPROVE WITH FOLLOW-UPS (v3). Reviewer B: APPROVE WITH FOLLOW-UPS (v3). Author: **signed off** — user instructed implementation 2026-09-30. **CR-0014 APPROVED (v3).**

## Implementation record (2026-09-30)
- Generator fixes + U1–U4 (7 tests) committed `05d788d`; manifest of the
  30 originals committed before regeneration; backup verified.
- VT rehearsal into scratch: all 60 gate rows pass; the generator's own
  Canada count equals the pin; restore rehearsal matches the manifest.
- Regeneration in place: generator's Canada counts VT 69,475 / NH 108,684
  / ME 822,494 — each equal to the pre-registered pin.
- Full check, one region at a time: 3 × 60 rows, 0 gate failures; R8 after
  purge. Evidence `docs/quality/evidence/CR-0014-gates.txt`.
- **X2 corrected during implementation:** as first written it measured
  edges outside `T`, which are already `L`, so it read 0. Redefined to
  edges within 20 km of Canadian land (an upper bound): ME 8,522 / NH
  24,841 / VT 17,804 — looser than reviewer A's Canada-facing-edge
  measurement (NH 6,884 / VT 1,881). OBS only; CR text updated.
- X1: positives with centre in `C` ME 10 / NH 6 / VT 2; negatives ME 2.
- Bookkeeping: BUG-0037 filed; BUG-0023 FIXED; PA-0023 added; PA-0017/0018
  Swept? cells; `BUG_LOG.md` rows.

## Post-implementation change (2026-09-30)
CR-0016 demoted RD1 and RD4 from gates to observations in
`check_road_dist.py` (BUG-0040: fitted to one run; the round-7 concern had
been dropped in the CR-0008 → CR-0014 split, BUG-0041). CR-0014's accepted
result is unchanged: re-run T2 gave 0 gate failures and identical RD1/RD4
values. Affected rows: RD1, RD4. Evidence
`docs/quality/evidence/CR-0016-check.txt`.

