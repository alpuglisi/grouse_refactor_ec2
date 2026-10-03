# CR-0021 review log

Verdicts, concern dispositions and revision history for
`CR-0021-harmonised-year-and-year-stratified-draw.md`. The CR states only
current intent (CR-0011 A4).

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 (`9422a38`) | A: correctness of diagnosis and fix (fresh agent; read-only; no data) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR, 4 MEDIUM, 3 LOW) |
| 1 | v1 (`9422a38`) | B: implementability, composition, acceptance (fresh agent; read-only; no data; pytest not installed, suites not run) | APPROVE WITH FOLLOW-UPS | 0 (3 MAJOR, 5 MEDIUM, 3 LOW) |

**Approval: not reached.**
- No BLOCKING concern. Five MAJOR concerns must be dispositioned before
  approval (CR-0011 A1).
- Approval also waits on deliverable 1, the pre-registration on the live
  data tree (CR §4). Both reviewers accept that as CR-0011 A3 practice
  (CR-0019 precedent) and treat round 1 as the design review.
- Both reviewers re-derived from code and committed evidence only; the
  live data is not in this checkout. Conclusions marked [data] depend on
  it.
- B does not require an A5 split; A finds the bundling justified.

**Open scope decision (user), raised by this round.** A1, A2/B1, A3, A4,
A6 and B2 all follow from part A or from the merged 2023–2024 stratum.
B1 also shows that strata `((2020,),(2021,),(2022,2023,2024))` have zero
shortfall on CR-0019's measured supplies **without** part A. Three
scopes are on the table:

| scope | network | removes | leaves |
|---|---|---|---|
| (i) A + B, as v1 | no | rule asymmetry; per-stratum count difference | A1 (habitat/nodata judged at the latest vintage, trained at the earliest), B2 (unchecked column), likely strata revision (B1) |
| (ii) B only, strata `(2020)(2021)(2022–2024)` | no | per-stratum count difference; feasible on measured supplies | a within-stratum residual across 2022–2024 (needs a stated tolerance, A3/B8); the rule asymmetry, made harmless for strata counts but not removed |
| (iii) C + B, single-year strata (re-fetch 2023–2024 negatives) | yes (public GBIF API; a user decision) | per-year distribution equal by construction; A unnecessary, so A1, A3, A4, A6, B2 lapse | supply unknown until the fetch [data]; candidate pool and every negative change |

Dispositions marked **pending scope** are decided when the scope is.

## Round 1, reviewer A: concerns and dispositions
| id | sev | concern (short) | disposition |
|---|---|---|---|
| A1 | MAJOR | Rule A judges positives' habitat (`nonveg_landcover`) and required-feature nodata at the latest visit's vintage but trains them at `first_year_min`'s; negatives are judged and trained at one year: a new per-class asymmetry (`analyze_grouse.py:764-779, 842`; `generate_negatives.py:216-227, 247-248`) [data: size] | pending scope (lapses under (ii) and (iii); under (i) re-apply the predicates at the training year or justify with a pre-registered count) |
| A2 | MAJOR | v1 strata not supported by the cited evidence: merged 2023–2024 stratum still ~155 short in 4 cells on CR-0019 supplies; near exhaustion ES sampling stops weighting | pending scope; accepted in substance: the CR's stated reason for the merge is wrong as written and will be corrected; fallback strata named in advance (see B1) |
| A3 | MEDIUM | Within-merged-stratum residual has no tolerance; O11 names no null population (PA-0020(ii), PA-0021(f)) | accepted for (i)/(ii): state a tolerance or accepted-risk justification and O11's class, subset and null; lapses under (iii) |
| A4 | MEDIUM | New pool step 3 changes the representative row (coords at 6 dp, `gbif_id`, date, species), so thinning order, ES keys and buffer distances move; null-year-smallest-id keys newly survive step 7 | pending scope (lapses under (ii) and (iii)); under (i) pre-registration counts changed rows and newly surviving keys |
| A5 | MEDIUM | Re-running `analyze_grouse.py` assumed to reproduce everything but the new column | accepted under (i); merged with B3 |
| A6 | MEDIUM | "B only" missing from alternatives | accepted: added as scope (ii) above; the CR's alternatives table gains it |
| A7 | LOW | "B and C expected unchanged" is not guaranteed (window check by vintage) | accepted: made a measured output, not a premise (with B7) |
| A8 | LOW | Per-stratum NonVeg rounding: cell total can differ from `round(n·0.3)` by up to ±(strata−2) | accepted: state it; manifest totals defined as sums over strata (with B4) |
| A9 | LOW | `tune.py`, `tune_bins.py` read `evaluated_sightings_*`; not in § Impact | accepted (with B10) |

## Round 1, reviewer B: concerns and dispositions
| id | sev | concern (short) | disposition |
|---|---|---|---|
| B1 | MAJOR | v1 strata leave 155 short in 4 of 24 cells on CR-0019 supplies; `((2020,),(2021,),(2022,2023,2024))` gives 0. Have the pre-registration evaluate a pre-fixed, finest-first list of candidate strata under a pre-fixed rule (first with zero SHORT) before any AUC is seen; define "within reason" | accepted in substance for (i) and (ii): the candidate list and selection rule go into §4; the stop is "never a single all-year stratum (today's draw)"; under (iii) the same rule applies after the fetch |
| B2 | MAJOR | Nothing checks `first_year_min` independently: the replay's root input S carries the value, so a wrong value passes R1/R4/E15 (PA-0021(e), PA-0029); §4 cannot run as written on today's S | pending scope (lapses under (ii) and (iii)); under (i) accept both fixes: pre-registration recomputes from raw sightings and MC pins every P year; an exact consistency gate on S with an attack row |
| B3 | MAJOR | Re-running `analyze_grouse.py` is unbounded: rewrites envelope metrics, `nonveg_flagged_*`, maps, may fetch state boundaries; drift changes weights, C and N for reasons outside this CR | pending scope (lapses under (ii) and (iii), which do not re-run it); under (i) accept: MC checks byte-identity of metrics and of S minus the new column; backups extended |
| B4 | MEDIUM | Acceptance changes under-specified for a separate replay author: exact `draw` JSON shape, totals as sums, `NEG_RATIO == 1.0` dependence; unlisted config sections (`manifest_schema.draw`, `dedup.rule`, `rounding`, `obs`) and code (`GATE_IDS`, `GATES`, `OBS_IDS`, standing tuple) | accepted (every scope): §3 lists them with the exact `draw` shape |
| B5 | MEDIUM | Attack rows name wrong gates: row 1 fails R1/R4 not E15(b) (draw is stratified on P's own years); row 3 fails R4 only if the key is drawn; off-by-one needs differing mixes across the boundary | accepted: rows corrected and their required fixture rows stated |
| B6 | MEDIUM | Missing attack rows: config vs `regions.py` strata mismatch (E11), overlapping/gapped strata (E15(a)), C year outside strata, NonVeg cap per cell instead of per stratum (R4), wrong S value, missing per-stratum manifest breakdown | accepted (the S-value row only under (i)) |
| B7 | MEDIUM | §4 item 5 expects C and P unchanged; wrong for C under (i) and possibly P | accepted: measured outputs; the control does not abort on them (with A7) |
| B8 | MEDIUM | O11 lacks class, subset, null; no tolerance for the within-stratum residual; §4 does not say how the acquisition-order cause is tested | accepted (tolerance part lapses under (iii)) |
| B9 | LOW | `YEAR_STRATA` must be a pure literal (E11 reads it with `ast.literal_eval`); the replay takes strata from the config, not `regions.year_stratum` | accepted |
| B10 | LOW | Code table misses `tests/test_cr0012.py` (calls `dedup_min_gbif_id`, `draw_region_split(sub, int)`); § Impact misses `tune.py`, `tune_bins.py`, `train.filter_by_year_gap` | accepted |
| B11 | LOW | Tracker items pointing at "BUG-0073's CR" (BUG-0075 `START_YEAR`; envelope epoch) have no disposition | accepted: v2 dispositions both (bundle or explicitly leave to their own CRs) |

## Next
v2 is written after the scope decision. Under CR-0011 A2 its re-review is
bounded to the MAJOR concerns above and the changed text; a change of
scope to (ii) or (iii) rewrites §2 substantially, so that text is in
scope for re-review in full.
