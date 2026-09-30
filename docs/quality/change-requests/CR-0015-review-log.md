# CR-0015 review log

## Lineage
Split out of CR-0012 at v2 by user decision (2026-09-30). Carried items:

| item | source | in CR-0015 v1 |
|---|---|---|
| `sample_background_points` out-of-state draw (BUG-0029 remainder) | CR-0007 v7 §7; CR-0012 v1 §6 | §1 in-state |
| 0/nodata conflation at `:143` (BUG-0032, allocated, never filed) | CR-0007 v7 §7; CR-0012 round-1 B LOW ("file BUG-0032 now") | §1 validity; deliverable 2 |
| Oversample budget must absorb the rejection rate | CR-0007 v7 §7 | §1 budget |
| Function is live, not dormant (`pretrain.py:63,179`; sweep `--an-background 1.0`) | CR-0012 round-1 B MAJOR 2 | Why now; §2 |
| AN points must be restricted to training blocks (~20 % land in val) | CR-0012 round-1 A1 (MAJOR) | §1 training blocks; U2; V1 |
| An interim guard until the fix lands | CR-0012 round-1 A1 alternative | §3; deliverable 1 |

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | — | not yet reviewed | — |

## Author sign-off
Pending.
