# CR-0021 review log

Verdicts, concern dispositions and revision history for
`CR-0021-year-matched-negative-draw.md` (v1 was filed as
`CR-0021-harmonised-year-and-year-stratified-draw.md`; renamed with v2
when the scope changed). The CR states only current intent (CR-0011 A4).

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 (`9422a38`) | A: correctness of diagnosis and fix (fresh agent; read-only; no data) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR, 4 MEDIUM, 3 LOW) |
| 1 | v1 (`9422a38`) | B: implementability, composition, acceptance (fresh agent; read-only; no data; pytest not installed, suites not run) | APPROVE WITH FOLLOW-UPS | 0 (3 MAJOR, 5 MEDIUM, 3 LOW) |
| 2 | v2 (`4bb44bc`) | A (bounded per CR-0011 A2; §2–§5 rewritten, so reviewed in full) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 3 MEDIUM, 3 LOW); A1, A2 resolved |
| 2 | v2 (`4bb44bc`) | B (same bounds; pytest not installed, suites not run) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 3 MEDIUM, 3 LOW); B1, B2, B3 resolved |
| 3 | v3 (`75dc4bd`) | A (last round under A2; bounded) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 2 LOW); A10 resolved |
| 3 | v3 (`75dc4bd`) | B (last round under A2; bounded) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 1 LOW); B12 partly resolved (block tolerance, see B19) |

**Approval: not reached.** Waits on round 3 and on deliverable 1 (the
top-up fetch and the pre-registration on the EC2 host), which has not
run. Both reviewers accept a pre-registration-gated approval as CR-0011
A3 practice (CR-0019 precedent). After deliverable 1, writing its
results into the CR is a **transcription verified by a reviewer**, not a
fourth design round. Anything non-mechanical goes to the user (CR §4;
B18).

## Scope decision (user, 2026-10-03)
Round 1 showed that A1, A2/B1, A3, A4, A6, B2 and B3 all follow from part
A or from v1's merged stratum, and that strata
`((2020,),(2021,),(2022,2023,2024))` are feasible on CR-0019's measured
supplies without part A. Three scopes were put to the user: (i) A + B as
v1; (ii) B only with merged strata; (iii) re-fetch 2023–2024 negatives (C)
+ B with single-year strata. **The user chose (iii).** v2 adds, from
round 1, a strata list fixed in advance and evaluated finest-first (B1),
which keeps (ii) as the last fallback entry.

## Round 1, reviewer A: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where (v2) |
|---|---|---|---|---|
| A1 | MAJOR | Rule A judges positives' habitat and nodata at the latest vintage but trains them at the earliest; negatives judged and trained at one year | resolved by scope: part A dropped; positives untouched (MC1); recorded as the reason in § Alternatives and § Residual | §2, §5, Alternatives |
| A2 | MAJOR | v1 strata infeasible on CR-0019 supplies (~155 short); ES weighting degrades near exhaustion | resolved: top-up C; strata chosen by a pre-fixed finest-first rule (S1→S3) before any AUC; `n_hab / supply` reported per stratum, > 0.8 named | §2 C, §4 |
| A3 | MEDIUM | No tolerance for a within-stratum residual; O11 null unnamed | accepted: O11 class, subset, statistic and within-cell permutation null stated; tolerance 0.55 pooled if a merged stratum is chosen; exactly 0.5 under S1 | §3 O11 |
| A4 | MEDIUM | New pool step 3 changes the representative row | resolved by scope: step 3 unchanged. The new raw rows can still win a 5 dp key or the thin order: measured by the pre-registration and pinned (MC3) | §4, §3 MC |
| A5 | MEDIUM | `analyze_grouse.py` re-run assumed reproducible | resolved by scope: not re-run | §2 B "Unchanged" |
| A6 | MEDIUM | "B only" missing from alternatives | accepted: row (ii) | Alternatives |
| A7 | LOW | "B and C expected unchanged" not guaranteed | accepted: P and B are now unchanged by construction (positives not regenerated; MC1 byte-identity); C is a measured output | §3 MC, §4 |
| A8 | LOW | Per-stratum NonVeg rounding changes the cell total | accepted: totals defined as sums; E9 amended accordingly | §2 B, §3 E9 |
| A9 | LOW | `tune.py`, `tune_bins.py` read S | accepted: listed (S unchanged) | § Impact |

## Round 1, reviewer B: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where (v2) |
|---|---|---|---|---|
| B1 | MAJOR | v1 strata leave 155 short; pre-fix a finest-first candidate list and a selection rule before any AUC; define "within reason" | accepted: S1→S3, first with zero SHORT, selected before O11 is computed; never coarser than S3 (a single stratum is today's draw) | §4 |
| B2 | MAJOR | `first_year_min` unchecked independently | resolved by scope: no new column | – |
| B3 | MAJOR | Unbounded `analyze_grouse.py` re-run | resolved by scope: not re-run; the new unbounded input (GBIF) is bounded instead by fetching once into a scratch tree, pinning the raw files' sha256 and copying them live (MC2) | §2 C, §3 MC |
| B4 | MEDIUM | Acceptance under-specified for the replay author | accepted: exact `draw` JSON shape; totals as sums and the `NEG_RATIO == 1.0` dependence; config sections (`manifest_schema.draw`, `rounding`, `obs`); code (`GATE_IDS`, registry, `OBS_IDS`, standing tuple). `dedup.rule` unchanged under (iii) | §2 B, §3 |
| B5 | MEDIUM | Attack rows named wrong gates | accepted: rows rewritten for the v2 change, each with the fixture rows that make the named gate fail | §3 Attacks |
| B6 | MEDIUM | Missing attack rows | accepted: config vs `regions.py` (E11), overlapping/gapped strata (E15(a)), C year outside strata, NonVeg cap per cell (R4), manifest breakdown (R4). The S-value row lapses with part A | §3 Attacks |
| B7 | MEDIUM | §4 expected C and P unchanged | accepted: P and B unchanged by construction and pinned; C measured | §3 MC, §4 |
| B8 | MEDIUM | O11 class/subset/null; tolerance; how acquisition order is tested | accepted: O11 fully specified with a tolerance; acquisition order: the fix does not depend on it (the draw no longer takes the pool's mix); it stays a recorded candidate | §3, §5 |
| B9 | LOW | `YEAR_STRATA` a pure literal; replay reads the config | accepted | §2 B, §3 |
| B10 | LOW | `tests/test_cr0012.py` calls; `tune.py`, `tune_bins.py`, `filter_by_year_gap` | accepted | Code table, § Impact |
| B11 | LOW | BUG-0075 and the envelope epoch undispositioned | accepted: both left to their own CRs, stated in § Out of scope; tracker updated at deliverable 8 | § Out of scope |

## Found by the author while revising (v2)
- **E9 would fail a correct stratified draw.** `gate_E9` caps NonVeg at
  `round(n × NONVEG_MAX_FRAC)` per cell (`acceptance_split.py:1979-1982`);
  per-stratum caps can sum above it by rounding. v2 amends E9 to
  per-stratum caps and the count to a sum over strata (§3).
- **`get_negatives.py` cannot top up as written.** Caps are per (state,
  species) over all years and are already met, so `--years 2023 2024`
  fetches nothing (`get_negatives.py:245-249, 287-290`). v2 uses a
  one-off evidence script, run once in a scratch tree, with its output
  pinned (§2 C).

## Round 2, reviewer A: new concerns and dispositions (as of v3)
| id | sev | concern (short) | disposition | where (v3) |
|---|---|---|---|---|
| A10 | MAJOR | O11 tolerance (pooled ≤ 0.55) cannot fail: cross-stratum pairs score exactly 0.5, so pooled AUC = 0.5 + f·(within − 0.5) with f ≈ 0.12 (S2) / 0.35 (S3); worst case under S2 ≈ 0.534; the 0.5584 justification is a different statistic (PA-0021(c)) | accepted: O11 split into O11a (pooled, report-only, stated as unable to detect a within-stratum residual) and O11w (within each merged stratum) with a within-cell permutation null; criterion = pooled O11w above its null's 99th percentile → user decision. No fixed AUC threshold | §3 O11, §4 |
| A11 | MEDIUM | Root cause half 1 (rules differ) stays: a per-year composition asymmetry; dropping BUG-0073 §8's "same rule" needs justification | accepted: BUG-0073's root cause restated as confirmed (the unmatched draw + no distribution check); the rule asymmetry filed as a tracked residual with an owner (PA-0022), not "accepted"; the PA wording keeps "made identical or recorded as a tracked residual" and BUG-0073 §8 justifies the change | § Fixes, §5, deliverable 8 |
| A12 | MEDIUM | Top-up can reduce 2020–2022 supply: 5 dp key wins, thinning displacement, two-state keys | accepted: reported separately by mechanism; § Risk row | §4, § Risk |
| A13 | MEDIUM | "roughly triples" overstates pool yield; `e = 0` partitions get nothing | accepted: reworded (raw rows only; S1 uncertain); per-partition yield and zero-`e` reported | §2 C, §4 |
| A14 | LOW | E9's `n_hab_k` undefined | accepted (with B14): formula stated, from the pool, strata from the config | §3 E9 |
| A15 | LOW | Relative paths in `load_existing`; unchecked GBIF `year` | accepted (with B13): realpath check; rows outside {2023, 2024} refused; tested | §2 C, § Test plan |
| A16 | LOW | `n_hab / supply > 0.8` has no consequence | accepted: report-only, does not block, stated | §4 |

## Round 2, reviewer B: new concerns and dispositions (as of v3)
| id | sev | concern (short) | disposition | where (v3) |
|---|---|---|---|---|
| B12 | MAJOR | The top-up is a second acquisition pass for two years only; PA-0020(ii) requires comparing separately acquired strata on every axis (species, space, `coord_uncertainty_m`), not only year | accepted: per-region comparison of new vs existing 2023–2024 rows (and 2020–2022 for context) on species shares, block and county occupancy, non-null `coord_uncertainty_m`, raw and pool survivors; tolerance TVD ≤ 0.10 (species, blocks) and ±10 pp (uncertainty) → else user decision. Per-species quotas preserve species mix by construction unless exhausted | §2 C, §4, § Risk |
| B13 | MEDIUM | Two producers of the raw files (PA-0026); path-equality guard weak; later `get_negatives.py` runs count top-up rows | accepted: single-use by construction (refuses unless target files equal the pinned pre-top-up sha256, and realpath ≠ live tree); disabled after deliverable 1; second producer recorded in `ARCHITECTURE.md`/`CHANGELOG.md` | §2 C, § Risk, deliverable 7 |
| B14 | MEDIUM | E9 supply clause ambiguous; E9 redundant with E15(b); add E9 to the shortfall attack row | accepted | §3 E9, Attacks |
| B15 | LOW | Attack fixtures do not force the named failure | accepted: each row asserts the effect on the attacked output | §3 Attacks |
| B16 | LOW | MC0's old tree ambiguous; MC2 prefix needs the same writer | accepted: old tree = deliverable 5's backup of today's live tree (record `ed27583b…`); append with `csv.DictWriter`, `CSV_FIELDS`, `\r\n` | §2 C, §3 MC |
| B17 | LOW | `e = 0` partitions get no top-up | accepted (with A13): reported | §2 C, §4 |
| B18 | LOW | v3 is round 3 (last under A2) | accepted: round 3 bounded to A10, B12 and v3's changed text; the post-pre-registration write-in is a reviewer-verified transcription; non-mechanical changes go to the user | CR status, §4 |

## Round 3 (final under CR-0011 A2): concerns and dispositions
| id | sev | concern (short) | disposition |
|---|---|---|---|
| A17 / B19 | MAJOR (raised independently by both) | The block-occupancy tolerance (TVD ≤ 0.10 on 3 km blocks, from B12) is uncalibrated and fails on a fair top-up: two samples of 1–3 thousand rows over thousands of blocks differ by TVD far above 0.10 by sampling alone (B's simulation on made-up distributions: median 0.53–0.80 over 10,000 cells, ~0.19 over 1,000). PA-0021(c). Fails safe (to the user), so not BLOCKING. Fix proposed by both: a permutation null (pool (a) and (b), random splits of the same sizes, ≥ 100 / 1,000 draws, flag above p99), with counties as the coarser axis | escalated to the user (no fourth round). **User decision (2026-10-03): block and county occupancy are report-only;** the species (TVD ≤ 0.10) and `coord_uncertainty_m` (±10 pp) tolerances stay. Applied to CR §4 and § Risk before deliverable 1 runs |
| A18 | LOW | O11w significance is not effect size | applied: effect size (O11w − 0.5) reported next to the percentile (§3) |
| A19 / B20 | LOW | Stale lines: §5 "O11's tolerance"; deliverable 1 "then v3" | applied: §5 "subject to the O11w criterion (§3)"; deliverable 1 "then v4: transcription only" |

A13–A16 and B13–B18 dispositions: accepted by their reviewers in round 3.

## Approval status after round 3
- **Design:** both reviewers APPROVE WITH FOLLOW-UPS in round 3; no
  BLOCKING concern in any round; every MAJOR concern resolved or decided
  by the user (A17/B19). Author signs off on the design.
- **Not yet APPROVED:** deliverable 1 (scripts written and reviewed; the
  top-up fetch and pre-registration run on the EC2 host) must complete,
  and its results be transcribed (v4) and verified by a reviewer against
  `preregister.txt` (CR §4 "Writing the result in"). No code outside
  `docs/quality/evidence/CR-0021/` and nothing under `data/` is written
  before that.

## Deliverable 1: code review of the evidence scripts (reviewer B, `8a0ad4c`)
Verdict **FIX FIRST** (0 BLOCKING, 1 MAJOR, 4 MEDIUM, 2 LOW); all addressed
before any run on the EC2 host.

| id | sev | finding (short) | disposition |
|---|---|---|---|
| S1 | MAJOR | `fetch_topup.check_tree` misses a hardlinked scratch copy (`cp -al`, `rsync --link-dest`): sha pin passes, realpath differs, the append reaches the live raw file | fixed: refuse if `os.path.samefile(scratch, live)` or link count > 1; test with `os.link` |
| S2 | MEDIUM | An aborted attempt's log blocked every retry | fixed: guard only on `fetch_topup_result.json`; one timestamped log per attempt; test: abort writes nothing, retry runs |
| S3 | MEDIUM | Species TVD tolerance applied to pool survivors too, where a fair sample sits near 0.10 | fixed: tolerances apply to the raw rows (what the fetch controls); pool stage report-only. Reading of CR §4 recorded here; the v4 transcription states it |
| S4 | MEDIUM | `mc_selftest` relied on `Replay.emit` writing P/B byte-identical to the live files | fixed: the self-test copies P and B from the live tree, as the live run (which regenerates only C and N) leaves them |
| S5 | MEDIUM | Untested: real `fetch_capped` with `Collector`; `main`; MC on synthetic trees | partly fixed: tests for `fetch_capped` + `Collector` + shared `seen`, and `main` end to end with a fake module (success, record guard, abort, retry). MC on synthetic tree pairs: covered instead by the EC2 self-test and the reviewer's PA-0021(a) wrong-tree runs in deliverable 1 |
| S6 | LOW | MC4 parsed `is_nonveg` with `bool()` and checked only per-stratum `n` | fixed: one `truthy()` parser for MC3/MC4; MC4 compares the whole per-stratum `{n, n_nv, n_hab}` |
| S7 | LOW | An I/O error during the appends is fail-closed but undocumented | fixed: docstring says re-copy the scratch tree |

Tests: `python -m unittest tests.test_cr0021` → 27 tests OK.

## Deliverable 1 results and user decisions (v4 transcription)
- Top-up (`224d3c3`) and pre-registration (`e955fa1`) ran on the EC2 host;
  control passed; **S1 chosen** by the pre-fixed rule; O11a predicted 0.5.
- **Species tolerance exceeded** (NH, VT; wetland species exhausted in
  GBIF). Follow-up check with its rule fixed before outputs were seen
  (wetland-guild share of drawn habitat negatives, 2023 and 2024 within
  ±10 pp of 2020–2022): **failed**; today's split shows the difference
  pre-exists (`wetland_mix.txt`).
- **User decision (2026-10-03): accept**; record the year × wetland-guild
  mix as a tracked residual with an owner, follow-up CR for a
  within-year wetland/upland-balanced draw. Not a design change to CR-0021,
  so no further review round (CR-0011 A2); the residual is written into
  CR §5 and § Out of scope.
- Transcribed: `YEAR_STRATA` = S1; `check_must_change.PRE_SHA` pinned to
  the committed outputs; `fetch_topup.DISABLED = True`; tests updated
  (29 OK).
- **Pending for approval:** reviewer verification of this transcription;
  `mc_selftest` on the EC2 host; the reviewer's PA-0021(a) wrong-tree runs.

## Deliverable 1: transcription verification and MC wrong-tree script (reviewer A)
- **v4 transcription: verified** against the committed evidence: strata
  (S1), control, > 0.8 cells, O11a, `PRE_SHA` (equal to `sha256sum` of the
  three preregister files), post-top-up sha256 (`preregister_draw.json` =
  `fetch_topup_result.json`), `DISABLED = True`, the user decision, and no
  change beyond transcription.
- Two LOW wording items, fixed: b1, name the exhausted species (Alder
  Flycatcher, Northern Waterthrush) instead of "the two wetland species"
  (the wetland guild has four); b2, state in CR §4 Result that the
  tolerances were applied to raw rows (code review S3) and point to the
  pool-stage values.
- PA-0021(a): reviewer A wrote `reviewA/mc_wrongtrees.py` (a correct tree
  plus 11 wrong trees, each mapped to the MC check it must trip). Compiled;
  five text mutations exercised on a synthetic tree. **Pending:** the run
  on the EC2 host (`reviewA/mc_wrongtrees.txt`).

## Approval (2026-10-03)
- `mc_selftest.txt` (`37dd9f8`): predicted tree PASS 63/63; no-op (live
  as NEW) FAIL. `reviewA/mc_wrongtrees.txt` (`75370ae`): correct tree
  PASS; noop, unstratified, nonveg_cap_cell, raw_not_topped_up,
  raw_append_dropped, raw_old_altered, p_altered, n_year_swap,
  n_nonveg_flip, trainval_desync, c_split_flip each FAIL via the expected
  MC check; WRONGTREES PASS.
- Quorum (CLAUDE.md §1.4): author and both reviewers who commented.
  A: APPROVE WITH FOLLOW-UPS (round 3) and transcription verified.
  B: APPROVE WITH FOLLOW-UPS (round 3). No BLOCKING concern in any round;
  every MAJOR concern resolved or decided by the user (A17/B19, the
  species tolerance and the wetland-mix residual).
- **CR-0021 APPROVED.** Deliverables 2–9 follow, in order; deliverable 2
  (acceptance changes) by a fresh agent that does not write deliverable 3
  (CR-0013 rule 4).

## Deliverable 3: implementation findings (author, 2026-10-03)
- **I1 (MAJOR, resolved in the CR text).** §3 requires `YEAR_STRATA` in
  both manifest sections (E11(c)), but §2 B said `prepare_training_data.py`
  is not re-run, and only that script writes the `positives` section; the
  live run as written would fail E11. `measured_constants()` lives in
  `prepare_training_data.py` and is shared by both sections, so the
  constant is added there (code table corrected). Resolution: deliverable
  6 starts at `prepare_training_data.py`. It is deterministic on unchanged
  inputs; MC1 (P and B byte-identical) is the check that the re-run
  changes nothing but the manifest constants. No acceptance change.
- **I2 (LOW).** `tests/test_cr0017.py` also calls the draw through
  `generate_negatives.run`; its fixtures use years outside S1, so both
  CR-0012 and CR-0017 fixtures run under a test-only single stratum
  (`tests/test_cr0012.py: fixture_strata`). Added to the code table.
- **I3 (LOW, transcription; found by the deliverable-2 author).** The Test
  plan's expected FAIL list for the read-only run on today's files omitted
  E9: today's unstratified N exceeds the per-stratum NonVeg cap in some
  strata, and the pre-top-up pool is short of habitat in single-year
  strata (`preregister.txt` §3 "before", e.g. ME train 2024 143 < 213).
  E9 is a consequence of the amended gate, not a new requirement; the
  list now reads E9, E11, E15(b), R4, and `acceptance_prefix.py` asserts
  it (E9 only per-stratum problems, count clause holding). The scratch-tree
  run starts at `prepare_training_data.py` (I1).

## Deliverable 2 (acceptance changes, `afd36fe`, separate author)
Merged into the CR branch after deliverable 3 (`81cc603`). Author choices
accepted: R4 compares the draw entry with exact JSON types and stratum key
order (§2 B "keys and types are exact"); overlapping strata resolve to the
first match for lookups while E15(a) fails the config; O11 keys
`O11.a.<split|pooled>.<region|pooled>`, `O11.w` "n/a" under S1; concrete
wrong implementations chosen for the NonVeg-cap-per-cell and
boundary-off-by-one attack rows; the four CR-0019 year-floor attacks that
the stratified draw now refuses run on the unstratified draw and also
assert the refusal.
