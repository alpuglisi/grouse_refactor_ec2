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
| 1 | v1 | — | not yet reviewed | — |

## Dispositions
(none yet)

## Author sign-off
Pending.
