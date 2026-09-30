# CR-0007 / CR-0008 open issues

To-do list of unresolved review findings. Detail lives in each CR's § Review.
Tick an item only when the fix is in the CR's operative text (body,
Deliverables, test plan), not just in a revision note.

IDs: `R7-n` = CR-0008 round 7 concern n; `B-n` = CR-0007 v7 reviewer B concern n.

## Shared / decisions needed
- [ ] Land bookkeeping batch: PA-0019/0020/0021, BUG-0030/0033/0035; name an owner (0007 B-8, 0008 R7-2) — **PA-0021 and BUG-0033 filed** (CR-0013 deliverable 0, 2026-09-30; calibration cause split out as BUG-0038); BUG-0030/0035 filed earlier (CR-0008/CR-0010). Remaining: PA-0019 (Tracked, with BUG-0028) and PA-0020 (CR-0007 deliverable 7)
- [x] Decide: pre-landing baselines vs `gate_obs_only` — **baselines first, no escape mode** (user, 2026-09-30). CR-0009 updated to match in v4 (0007 B-2)
- [x] Decide: CR-0007 structure — **split into 3** (user, 2026-09-30): CR-0007 partition + constants; CR-0012 global split + pooled draw; CR-0013 acceptance gates as a committed script
- [x] Decide: `TIGER_YEAR` — **2023** (user, 2026-09-30); set by CR-0014, centralised by CR-0007 (0007 B-9)
- [x] Decide: TreeMap coverage boundary — NLCD (CR-0010 repair, CR-0008 v9 generator) (0008 R7-1, R7-3)
- [x] Decide: Canadian-border road distance — **nodata where Canadian land is nearer than the nearest TIGER road** (user, 2026-09-30); CR-0014 (0008 R7-4)
- [x] Reconcile I17 / G5 hand-off — moved to CR-0010: 0 positive centre values change, so I17 is unaffected; X3 reports window exposure (0008 R7-5, R7-6)
- [x] **I17 WILL change under CR-0014** (140 ME / 717 VT positives' `road_dist` values): CR-0012/CR-0013 must take I17 after CR-0014 lands, and say so (CR-0014 B6) — CR-0013 O8/E8 taken after CR-0014 or repeated; CR-0012 landing order
- [x] Reconcile PA-0021 clause text: one version, cited consistently (0008 R7-12) — filed in `PREVENTIVE_ACTIONS.md` (draft + (a) "built by someone other than the author, recorded so it can be re-run" + (f)); earlier CR texts quoting other forms are superseded by the filed row (CR-0013 deliverable 0)
- [x] Decided (user): fresh first review for each. Quorum for CR-0007 v8 / CR-0012 / CR-0013 — author proposes fresh first reviews of each, with the v8 disposition table as the no-drop record (prior agents cannot be resumed) (CR-0007-review-log § v8)
- [x] Decided (user): exact replay. CR-0013 replaces v7's statistical gates with exact predicates + independent replay; statistics become OBS. Confirm this direction before review (CR-0013 design rule 2)

## CR-0007
- [x] B-1 Recover rounds 3–6 verdicts from prior-session transcripts; rebuild round table; disposition all concerns; list every reviewer for quorum — review log reconstructed; all 100 open rows dispositioned; v8 quorum → Shared (see CR-0007-review-log.md § v8 dispositions)
- [x] B-2 Escape-mode contradiction (`gate_obs_only` undefined; "Deleted: the escape mode") — no escape mode; CR-0012 deliverable 0 (see CR-0007-review-log.md § v8 dispositions)
- [x] B-3 Gate call-site matrix (GATE/OBS per script); SUP rows have no call site — CR-0013 call-site matrix (see CR-0007-review-log.md § v8 dispositions)
- [x] B-4 I16b: in-run null vs frozen constants — CR-0013 O4 (OBS, in-run null, no constants) (see CR-0007-review-log.md § v8 dispositions)
- [x] B-5 I19′ nulls must come from independent harness, pre-registered — CR-0013: no GATE uses a null; OBS nulls from its own replay (see CR-0007-review-log.md § v8 dispositions)
- [x] B-6 Deliverable: run recorded attacks against implemented gates; port or pin broken `inv_*` scripts — CR-0013 § Attacks, deliverables 1, 4; CR-0012 §7 pins scripts to `ec1470a` (see CR-0007-review-log.md § v8 dispositions)
- [x] B-7 Fold accepted dispositions into operative text (`TIGER_YEAR`, `ignore_index`, negative `verify_partition`, windowless drop, PA-0020 cite, §6 (d), test plan, "Not optional detail" header); mark superseded v4 sections — clean rewrite; each item mapped in the log (see CR-0007-review-log.md § v8 dispositions)
- [x] B-8 Bookkeeping batch owner (see Shared) — per-CR filers named; batch owner still open (Shared) (see CR-0007-review-log.md § v8 dispositions)
- [x] B-9 `TIGER_YEAR` behaviour change (see Shared) — CR-0014 sets 2023; CR-0007 v8 §1 centralises (see CR-0007-review-log.md § v8 dispositions)
- [x] B-10 `generate_negatives.py --regions` write guard; raise before any `to_csv` — CR-0012 §3, §2 Writes (see CR-0007-review-log.md § v8 dispositions)
- [x] B-11 Rule in/out: hash ordering, `draw_val_blocks`, stratification, flag removal — CR-0012: hash order + flag removal in; stratification, `draw_val_blocks` out (see CR-0007-review-log.md § v8 dispositions)
- [x] B-12 Pin I5 window (`img_size + 2·jitter`, year rule) in manifest — CR-0012 §1 `WINDOW_PX`, §5; CR-0013 E8 (see CR-0007-review-log.md § v8 dispositions)
- [x] B-13 `PATH_TEMPLATES` entries for new paths — CR-0012 §4 (see CR-0007-review-log.md § v8 dispositions)
- [x] B-14 KDE clip vs PA-0018 — CR-0007 v8 §2 (KDE source box-clipped, output partitioned) (see CR-0007-review-log.md § v8 dispositions)
- [x] B-15 SUP0 VT/val 0.87 claim appears false — claim withdrawn (verified false) (see CR-0007-review-log.md § v8 dispositions)
- [x] B-16 Family-wise false-fail rate; threshold-rule consistency; C11, I15, I18 gaps — CR-0013: exact gates only; OBS rows fully specified (see CR-0007-review-log.md § v8 dispositions)
- [x] B-17 I6 target definition — CR-0013 R1 (see CR-0007-review-log.md § v8 dispositions)
- [x] B-18 BUG ids for `TIGER_YEAR` drift, `STATE_FIPS`/`MIN_SPACING_M` dupes, `generate_negatives.py:153` — CR-0007 deliverable 7; CR-0012 deliverable 8 (see CR-0007-review-log.md § v8 dispositions)
- [x] B-19 Citation/count fixes (`:444`, `:143`, `:443-444`, consumers 18 + `tune_bins.py`, 5 guards, backup items, I5 raise point) — citations re-verified in v8/CR-0012 (see CR-0007-review-log.md § v8 dispositions)
- [x] B-20 Reorder deliverables (backup first) — all three CRs in execution order (see CR-0007-review-log.md § v8 dispositions)
- [x] B-21 §7 geopandas dependency in `train.py` — CR-0012 §6 (see CR-0007-review-log.md § v8 dispositions)
- [x] Risk table: add 4 missing risks; extend "cannot validate" list — CR-0007/0012/0013 Risk tables, CR-0013 stated limit 2 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-1 **BLOCKING** I18 per-region inverted: false-fails ~52 % of correct runs, blind to BUG-0027 leak; revert to pooled or per-region null bands — CR-0013 O1 pooled OBS; leak gated by E4/E5 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-2 **BLOCKING** No gate on 300 m exclusion buffer (removing it: ~2,053 of 6,230 negatives within 300 m of grouse, all gates green); add exact min-distance predicate, centralise `BUFFER_M`, lower bound on I19′ — CR-0007 `BUFFER_M`; CR-0012 manifest count; CR-0013 E7, R3, O5 two-sided (see CR-0007-review-log.md § v8 dispositions)
- [x] A-3 **BLOCKING** Rounds 3–5 verdicts/dispositions (same as B-1) — as B-1 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-4 I19′ val cells calibrated on wrong null (6–11σ slack); condition on realised positive split; fix stated limit 3 — CR-0013 O5 N-draw conditioned on realised split; attack fails R3 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-5 Gate duplicate negatives within a split (0 dup 5 dp keys, 0 pairs < `MIN_SPACING_M`) — CR-0013 E3 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-6 Re-derive C5–C17 on rebuilt footing (deliverable) — CR-0013 `--calibrate` on rebuilt footing (deliverable 6) (see CR-0007-review-log.md § v8 dispositions)
- [x] A-7 Persist `weight`, `weight_basis`, `evt_phys`, `common_name`, `envelope_id`, `year`; compute C rows in `acceptance.py`, not `generate_negatives.py` — CR-0012 §2 step 11; computed in `acceptance_split.py` (see CR-0007-review-log.md § v8 dispositions)
- [x] A-8 Escape mode (same as B-2) — as B-2 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-9 §6 contradictions / superseded (d), "Not optional detail" (overlaps B-7) — clean rewrite (see CR-0007-review-log.md § v8 dispositions)
- [x] A-10 I16b (same as B-4) — as B-4 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-11 VT val NonVeg claim false (same as B-15) — as B-15 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-12 SUP-R/SUP-O headroom; re-pin after rebuild — CR-0013 O7 (OBS) (see CR-0007-review-log.md § v8 dispositions)
- [x] A-13 Known-exceptions: ticked in deliverables, open in body — CR-0012 §2 pool step 4 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-14 Citations (`:302`→`CSV_KEEP :89-90`, `:143`, `:160`, `:444`, `:443-444`, "723 blocks", year rule, NH 3 of 5,220) — citations re-verified (see CR-0007-review-log.md § v8 dispositions)
- [x] A-15 `GATE_REGIONS` from artifact under test; `generate_negatives --regions` guard (overlaps B-10) — CR-0007 `REGIONS`; CR-0013 E1/E11; CR-0012 §3 (see CR-0007-review-log.md § v8 dispositions)
- [x] A-16 Deliverable order (same as B-20) — as B-20 (see CR-0007-review-log.md § v8 dispositions)

## CR-0008
- [x] R7-1 TreeMap generator needs external mask; strengthen G4.2; withdraw "latent defect is closed" — v8 (see CR-0008-review-log.md)
- [x] R7-2 Approval preconditions + sign-off paragraph (v6 → v7, quorum rule) — v8 (see CR-0008-review-log.md)
- [x] R7-3 `download_treemap.py` mask chain; `:315` clip — v8 (see CR-0008-review-log.md)
- [ ] R7-4 Canadian-border roads (see Shared) — moved to road_dist CR
- [x] R7-5 Impact cross-CR claims (I17, "2 records", "4 of 3,659", measure both landing orders) — v8 (see CR-0008-review-log.md)
- [x] R7-6 "Either order" vs PA-0020 dependency — v8 (see CR-0008-review-log.md)
- [x] R7-7 Remove withdrawn text from operative sections ("three" schemas, § Disk idiom list, "18.4 %", test plan, Impact 47.1 %, "1.0000", disk "not a blocker") — v8 (see CR-0008-review-log.md)
- [x] R7-8 "§ Scope's table" → § Coverage — v8 (see CR-0008-review-log.md)
- [x] R7-9 `tsd` `hit` parenthetical; vintage set d ≤ Y — v8 (see CR-0008-review-log.md)
- [ ] R7-10 G7: all 10 `road_dist` year-copies byte-identical — moved to road_dist CR
- [x] R7-11 Name all four encoders (`tpa_live_encode`, `tsd_encode`, `treemap_encode`, `road_dist_encode`) — v8 (see CR-0008-review-log.md)
- [x] R7-12 PA-0021 exemptions; calibrate or label OBS (0.06 %, G6 1.2×, RD1/2/4); GATE/OBS labels for G3, G5 — v8 (see CR-0008-review-log.md)
- [x] R7-13 PA-0019 provenance tags on repaired files — v8 (see CR-0008-review-log.md)
- [x] R7-14 Risk table rows (G8 cache, RD5, G8.3) — v8 (see CR-0008-review-log.md)
- [x] R7-15 Attribute rounds 1–5 disposition rows to round/reviewer — v8 (see CR-0008-review-log.md)
- [x] R7-16 Restore rehearsal: order, scratch space, G8.2 — v8 (see CR-0008-review-log.md)
- [x] R7-17 LOW batch (`:294`, G0.2, 33 % vs 25.6 %, G6 coverage of `road_dist`, VT counties, G8.3 files, CR-0009 "9.75 GB", MiB) — v8 (see CR-0008-review-log.md)

## Handed over from CR-0010 review
- [x] CR-0008 v8: add deliverable to remove CR-0010's `GROUSE_REPAIR` refuse-to-overwrite guard once generators are fixed (CR-0010 B4)
- [ ] CR-0006: drop BUG-0030 creation (CR-0008 v8 done) — CR-0010 owns it (CR-0010 B3)

## New CR to write
- [x] ~~`road_dist` ME/VT CR~~ — written as **CR-0014** (see its review log for the carried items). Was: `road_dist` ME/VT CR (split from CR-0008): regeneration, `_download` atomicity, densified footprint reprojection, `TIGER_YEAR`, Canadian-border decision (R7-4), G7/RD1–RD5 with truth from all TIGER counties intersecting grid+pad (PA-0018) and excluded-point count gated at 0, all 10 year-copies byte-identical (R7-10), G6 for regenerated files, BUG-0023 §6 retroactive-review ruling for `bf8d31a`
- [x] ~~After first real `download_tcc_nlcd.py` run: G2 check~~ — replaced by CR-0008 v9 in-code post-download check
- [x] CR-0009: "CR-0008 owns the raster backup (9.75 GB)" — fixed in CR-0009 v4
- [x] PA numbering: PA-0022 was filed while PA-0019–0021 are only drafts (res_qms file). Either file 0019–0021 or record the reservation as a deliberate exception to creation-order numbering (CR-0008 B14) — recorded as a deliberate exception: PA-0022's row reserves 0019–0021; PA-0021 filed 2026-09-30 after PA-0022/0023 under its reserved id, no renumbering (PA-0021 Source cell, BUG-0033 §8). PA-0019/0020 stay reserved until their owners file them (see Shared)
- [ ] If CR-0008's post-download `tcc` check (U5) ever refuses a real download, switch it to masking `tcc` by the region NLCD footprint (as CR-0010 does) instead of refusing (CR-0008 A7)
- [ ] BUG-0037 is reserved for CR-0014 (Canada over-read). The untracked `res_qms_PA-0019-0020-0021-draft-rows.md` proposes BUG-0036/0037 for other defects — renumber them when filed (BUG-0036 is the encoder bug) (CR-0014 B8) — note: BUG-0038..0040 are now taken (CR-0013 deliverables 0/2a); the draft's two proposals take the next free id (≥ BUG-0041) when filed
- [ ] CR-0007 B-9 (`TIGER_YEAR` value is a behaviour change) moved to CR-0014, which sets 2023 (CR-0014 B6)
- [ ] CR-0014 residual: Canadian land beyond the grid edge is unseen (NH 6,884 px, VT 1,881 px at the top edges). Closes only with Canadian road data (Statistics Canada NRN) (CR-0014 A4)
- [ ] CR-0009: remove dependence on CR-0007 escape mode; capture additional baselines before CR-0012 lands — text done in CR-0009 v4 (§ Baselines, deliverable 2); the capture itself is pending and is CR-0012 deliverable 0 (0007 A-8/B-2)
- [ ] `DRAFT_BUG-0034` says "DECIDED … fixed in CR-0007": correct to "open; fix owned by a future CR" on promotion (CR-0007 v9 deliverable 6) (0007 FC-C5)
- [ ] BUG-0034 fix CR (not yet written): per-class drop-rate assert at dataset build (BUG-0034 §8) and mechanism-scoped sweep (e.g. `predict.py:164`); re-calibrate CR-0013 OBS references on the new footing (0007 FA-Q4, FA-Q5)
- [ ] `old_road_dist/`, `new_road_dist/` are untracked and unprotected; decide ownership (CR-0014 or CR-0009) — not CR-0007 (`INVESTIGATION_REPORT_errol_map.md` is in git) (0007 H-X7)

## Decisions on the CR-0007 split (user, 2026-09-30)
- [x] CR-0013 gates: **exact replay** of a deterministic thin/split/draw; v7 statistics become report-only
- [x] Quorum for CR-0007 v8 / CR-0012 / CR-0013: **fresh first review** (two reviewers each); the v8 dispositions table in CR-0007-review-log.md is the record that no prior finding was dropped
- [x] Evidence: **commit only the scripts CR-0013's attack table cites**, under docs/quality/evidence/CR-0007-r7/ where copied; other inv_/res_ files stay untracked
- [x] Bookkeeping batch (PA-0021, BUG-0033): **filed by CR-0013's author before CR-0013's approval**; new BUGs take the next free id at filing
- [x] Replay author ≠ CR-0012 implementer: workable (separate agents)
- [ ] **CR-0015** (not yet written): `sample_background_points` in-state partition (BUG-0029 remainder) and the 0/nodata conflation (file BUG-0032). The function is live (`pretrain.py:63,179`; `sweep/launch.sh --an-background 1.0`). Moved out of CR-0012 v2 (CR-0012 R1 B-2, B-7)
- [x] (duplicate of the item below) Runtime guards for `legacy/download.py` and `legacy/download_more.py` (diverged copies; BUG-0031 sweep). Moved out of CR-0012 v2 → **CR-0007 v9** (user decision) (CR-0012 R1 B-7)
- [ ] CR-0009: update the expected positive count to 6,232 (CR-0012 v2 hash-ordered specification) and commit CR-0009 v4 before CR-0012 deliverable 0 (CR-0012 R1 B-5, B-12)
- [x] PA-0021 sweep (owner of PA-0021's Swept? cell once CR-0013 deliverable 0 files it): acceptance tables of CR-0007..0013 plus live-code thresholds (CR-0013 R1 B-C6) — run as CR-0013 deliverable 2a (2026-09-30): 2 instances, BUG-0039 (CR-0009 symptom GATEs) and BUG-0040 (`check_road_dist.py` RD1/RD4); result in PA-0021's Swept? cell
- [ ] BUG-0039: CR-0009's symptom GATEs 1a/1b/2a/2b — calibrate per PA-0021(c)/(f) (≥50 retrain seeds; compute needs user sign-off) or demote to OBS; 2b needs a constructed failing model — owner: CR-0009's next revision
- [ ] BUG-0040: `check_road_dist.py` RD1/RD4 — demote to OBS or calibrate (seed-varied fair vs pre-CR-0014/constructed broken rasters); add failing tests; state whether RD2/RD3's analytic bound substitutes for a quantile — needs a CR (none written)
- [ ] Decide (user): a finding dispositioned by moving its subject to another CR (CR-0008 R7 item 12 → CR-0014) was not carried into the receiving CR's log (BUG-0040 §7). Existing §1.3 rule, not followed — new PA or not?
- [ ] Decide (user): runtime input guards are outside PA-0021 (not change acceptance) per the sweep; noted there: `download_rev.py` `_raster_valid_fraction` returns 1.0 when a raster declares no nodata and `None` on an open error, and both pass the 1 % guard (documented as "can't judge"; not confirmed as a defect, PA-0016)


## Decisions (user, 2026-09-30, continued)
- [x] `sample_background_points` / BUG-0029 remainder / BUG-0032 → **separate CR-0015** (not yet written). CR-0015 must also restrict AN-background points to **training blocks**, not just the state (CR-0012 A1: ~20 % land in val blocks today)
- [x] `legacy/download.py` and `download_more.py` deprecation guards → **CR-0007 v9** (same mechanism as BUG-0031)
- [x] `acceptance_split.py` authorship: **a fresh agent given only CR-0013 + the pinned commit**, never CR-0012's implementation; CR-0012 implemented by a different fresh agent; both transcript ids recorded in the review logs
- [ ] BUG-0034 scope must include `filter_by_year_gap` running after the split (drops 23.1 % of positives, effective neg:pos ≈ 1.3) and the thin-order interaction (CR-0012 A9)
- [x] CR-0015 written (v1, 2026-09-30): assumed-negative background — in-state, training blocks only, 0 not nodata (BUG-0032), interim `--an-background` guard. Awaiting review

## CR-0007 v9 (round-8 follow-ups, 2026-09-30)
- [ ] Commit CR-0007 deliverable 0 (pre-approval): `check_partition.py`, `tests/test_check_partition.py`, `tests/test_shared_constants.py`, `docs/quality/evidence/CR-0007-check-today.txt`, `DRAFT_BUG-0034-…md`, `res_qms_PA-0019-0020-0021-draft-rows.md` — owner: coordinator (0007 R8 B3)
- [ ] Analysis-CRS constant (`"EPSG:5070"`: 16 code literals in 7 files; also the `x_5070`/`y_5070` schema and CR-0012's `BLOCK_ORIGIN_5070`): deferred PA-0001-extension sweep item (d), its own BUG at CR-0007 deliverable 6 — owner: CR-0007's author, opens a CR after CR-0012 lands (0007 R8 B7)
- [ ] CR-0014 `:12`, `:146` say "CR-0007's I17"; it is CR-0013 O8 since the split — owner: CR-0014's author (0007 R8 B10)
- [ ] CR-0009 `:64` says "when CR-0007/CR-0012 land"; the baselines are affected only by CR-0012 — owner: CR-0009's author (0007 R8 B10)
- [ ] CR-0012: when `VAL_FRACTION`/`SPLIT_SEED` join `regions.py`, add them (and `_DEFAULT` aliases) to `check_partition.P6_NAMES` and pin them in `tests/test_shared_constants.py` — owner: CR-0012's author (0007 v9 C1)
- [ ] CR-0013 v2 `:296` cites "CR-0007 (P1–P7)"; v9 has P1–P8 — owner: CR-0013's author (0007 v9 C2)
- [ ] NH `ch`/`cc` rasters (mtime 2026-09-20 11:32) postdate `evaluated_sightings_NH.csv` (2026-09-18): 1,040 `ch` / 1,265 `cc` values differ. Find what rewrote them (untested, PA-0016; provenance, PA-0019 draft). CR-0007's re-run supersedes the values (O4) — owner: CR-0007's author (0007 v9 C3)
- [ ] CR-0012 implementation: confirm the `clean.py` and `legacy/gen_negs.py` guards before CR-0007's P6 exemption for them is relied on (CR-0007 B-R9-1)
- [ ] **Hypothesis, untested (PA-0016):** `download_rev.py`'s valid-pixel check may pass a raster that declares no nodata value or fails to open. Not a BUG until checked; owner: next change to `download_rev.py` (CR-0013 sweep note)
- [x] Runtime input guards (`download_rev.py:100`, `download_tcc_nlcd.py:409`, `model_handler.py:871`) are outside PA-0021's scope (user, 2026-09-30)
- [x] BUG-0039 → demote CR-0009 v4's symptom gates 1a/1b/2a/2b to OBS (user, 2026-09-30); applied in the CR-0009 working tree (v4 still uncommitted per user)
- [ ] BUG-0040 → CR-0016 (demote RD1/RD4 to OBS) — written, awaiting review

## CR-0015 v2 (round-1 follow-ups, 2026-09-30)
- [x] User decision (2026-09-30): CR-0015 adds `regions.block_split(block_ids, assignments)` after CR-0012 lands and switches `generate_negatives.py`'s pool step to it (behaviour-preserving; CR-0015 B1 digest check + CR-0013 acceptance unchanged). **CR-0012's pinned text (`29f388b`) is not reopened**; its §2 prose rule and `split_for_unassigned` reference are superseded in code by CR-0015 deliverable 5 (CR-0015 R1 A4/B1)
- [ ] CR-0012 Landing order says "CR-0015 (assumed negatives) is independent"; CR-0015 depends on CR-0012 (block grid, `SPLIT_SEED`, `block_assignments.csv`) and CR-0007 (`in_state`). CR-0015 § Order governs; correct on CR-0012's next revision, if any — owner: CR-0012's author (CR-0015 R1 A10, B9)
- [ ] BUG-0029 closure rule, one wording across CRs: corrective action "membership: CR-0007; split and draw: CR-0012; assumed negatives: CR-0015"; FIXED when CR-0015 deliverable 7b passes, CLOSED when CR-0009 also closes. CR-0012 d8 is consistent; **CR-0007 v9 deliverable 6 ("fixed when CR-0012 lands") conflicts** — whoever executes CR-0007 d6 writes BUG-0029 with this rule — owner: CR-0007's author (CR-0015 R1 B8)
- [ ] CR-0007 review log E-9 / FA-Q3 dispositions say "CR-0012 deliverable 8 files BUG-0032"; the filer is now CR-0015 deliverable 2 (CR-0012 B-2) — annotate as "moved to CR-0015" (PA-0024(b)) — owner: CR-0007's author (CR-0015 R1 B9)
- [x] Decide (user): the 4326→5070 transform CR-0015 needs for block ids lives only in `generate_negatives.to_albers` (and a separate Transformer at `analyze_grouse.py:679`); CR-0012 v2.1 adds no transform helper to `regions.py`. CR-0015 v2 imports `to_albers` lazily on the AN branch (pulls scipy/sklearn/matplotlib via `analyze_grouse`, ~1.3 s). Alternative: move it to `regions.py` now (a second helper, beyond the block_split decision) or leave to CR-0007 item (d) — owner: user (CR-0015 R1 B1) — **decided (user, 2026-09-30):** `regions.to_5070(lon, lat)` added by CR-0015 next to `block_split`; `generate_negatives.to_albers` delegates to it after CR-0012 lands (B1 byte-identical gate); `train.py`'s AN path imports only `regions`. Applied in CR-0015 v2
- [ ] CR-0015 reserves **BUG-0042** (AN points in validation blocks) and files BUG-0032; the two new PAs ("extends PA-0006", "extends PA-0018") take the next free PA ids at filing — owner: CR-0015's author (CR-0015 R1 A7, B3)
