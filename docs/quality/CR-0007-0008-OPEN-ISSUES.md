# CR-0007 / CR-0008 open issues

To-do list of unresolved review findings. Detail lives in each CR's § Review.
Tick an item only when the fix is in the CR's operative text (body,
Deliverables, test plan), not just in a revision note.

IDs: `R7-n` = CR-0008 round 7 concern n; `B-n` = CR-0007 v7 reviewer B concern n.

## Shared / decisions needed
- [ ] Land bookkeeping batch: PA-0019/0020/0021, BUG-0030/0033/0035; name an owner (0007 B-8, 0008 R7-2) — **PA-0021 and BUG-0033 filed** (CR-0013 deliverable 0, 2026-09-30; calibration cause split out as BUG-0038); BUG-0030/0035 filed earlier (CR-0008/CR-0010). Remaining: PA-0019 (Tracked, with BUG-0028). **PA-0020 filed** (CR-0007 deliverable 6, 2026-09-30; the tracker said "deliverable 7" in error)
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
- [x] CR-0009: remove dependence on CR-0007 escape mode; capture additional baselines before CR-0012 lands — text done in CR-0009 v4 (§ Baselines, deliverable 2); the capture itself is pending and is CR-0012 deliverable 0 (0007 A-8/B-2) — **done**: capture committed as CR-0012 deliverable 0 (ticked; `docs/quality/evidence/CR-0009/baseline/`, `SHA256SUMS`)
- [ ] `DRAFT_BUG-0034` says "DECIDED … fixed in CR-0007": correct to "open; fix owned by a future CR" on promotion (CR-0007 v9 deliverable 6) (0007 FC-C5)
- [x] BUG-0034 fix CR (not yet written): per-class drop-rate assert at dataset build (BUG-0034 §8) and mechanism-scoped sweep (e.g. `predict.py:164`); re-calibrate CR-0013 OBS references on the new footing (0007 FA-Q4, FA-Q5) — **written as CR-0019 (APPROVED v3, 2026-09-30)**: exact train-time refusal + E14 instead of a drop-rate assert; sweep = its deliverable 8; OBS recalibration = its deliverable 6 step 6. Tick at CR-0019 close-out — **done**: CR-0019 IMPLEMENTED (live run `00b0b84`, OBS recalibrated; sweep in PA-0020 Swept?)
- [ ] `old_road_dist/`, `new_road_dist/` are untracked and unprotected; decide ownership (CR-0014 or CR-0009) — not CR-0007 (`INVESTIGATION_REPORT_errol_map.md` is in git) (0007 H-X7)

## Decisions on the CR-0007 split (user, 2026-09-30)
- [x] CR-0013 gates: **exact replay** of a deterministic thin/split/draw; v7 statistics become report-only
- [x] Quorum for CR-0007 v8 / CR-0012 / CR-0013: **fresh first review** (two reviewers each); the v8 dispositions table in CR-0007-review-log.md is the record that no prior finding was dropped
- [x] Evidence: **commit only the scripts CR-0013's attack table cites**, under docs/quality/evidence/CR-0007-r7/ where copied; other inv_/res_ files stay untracked
- [x] Bookkeeping batch (PA-0021, BUG-0033): **filed by CR-0013's author before CR-0013's approval**; new BUGs take the next free id at filing
- [x] Replay author ≠ CR-0012 implementer: workable (separate agents)
- [ ] **CR-0015** (not yet written): `sample_background_points` in-state partition (BUG-0029 remainder) and the 0/nodata conflation (file BUG-0032). The function is live (`pretrain.py:63,179`; `sweep/launch.sh --an-background 1.0`). Moved out of CR-0012 v2 (CR-0012 R1 B-2, B-7)
- [x] (duplicate of the item below) Runtime guards for `legacy/download.py` and `legacy/download_more.py` (diverged copies; BUG-0031 sweep). Moved out of CR-0012 v2 → **CR-0007 v9** (user decision) (CR-0012 R1 B-7)
- [x] CR-0009: update the expected positive count to 6,232 (CR-0012 v2 hash-ordered specification) and commit CR-0009 v4 before CR-0012 deliverable 0 (CR-0012 R1 B-5, B-12) — **done**: CR-0009 v5 cites CR-0012 § Impact (round 5 confirmed, `9d8c1c9`); the real run gave 6,232 (`1bc2df6`)
- [x] PA-0021 sweep (owner of PA-0021's Swept? cell once CR-0013 deliverable 0 files it): acceptance tables of CR-0007..0013 plus live-code thresholds (CR-0013 R1 B-C6) — run as CR-0013 deliverable 2a (2026-09-30): 2 instances, BUG-0039 (CR-0009 symptom GATEs) and BUG-0040 (`check_road_dist.py` RD1/RD4); result in PA-0021's Swept? cell
- [ ] BUG-0039: CR-0009's symptom GATEs 1a/1b/2a/2b — calibrate per PA-0021(c)/(f) (≥50 retrain seeds; compute needs user sign-off) or demote to OBS; 2b needs a constructed failing model — owner: CR-0009's next revision
- [x] BUG-0040: `check_road_dist.py` RD1/RD4 — demote to OBS or calibrate (seed-varied fair vs pre-CR-0014/constructed broken rasters); add failing tests; state whether RD2/RD3's analytic bound substitutes for a quantile — needs a CR (none written)
- [ ] Decide (user): a finding dispositioned by moving its subject to another CR (CR-0008 R7 item 12 → CR-0014) was not carried into the receiving CR's log (BUG-0040 §7). Existing §1.3 rule, not followed — new PA or not?
- [ ] Decide (user): runtime input guards are outside PA-0021 (not change acceptance) per the sweep; noted there: `download_rev.py` `_raster_valid_fraction` returns 1.0 when a raster declares no nodata and `None` on an open error, and both pass the 1 % guard (documented as "can't judge"; not confirmed as a defect, PA-0016)


## Decisions (user, 2026-09-30, continued)
- [x] `sample_background_points` / BUG-0029 remainder / BUG-0032 → **separate CR-0015** (not yet written). CR-0015 must also restrict AN-background points to **training blocks**, not just the state (CR-0012 A1: ~20 % land in val blocks today)
- [x] `legacy/download.py` and `download_more.py` deprecation guards → **CR-0007 v9** (same mechanism as BUG-0031)
- [x] `acceptance_split.py` authorship: **a fresh agent given only CR-0013 + the pinned commit**, never CR-0012's implementation; CR-0012 implemented by a different fresh agent; both transcript ids recorded in the review logs
- [x] BUG-0034 scope must include `filter_by_year_gap` running after the split (drops 23.1 % of positives, effective neg:pos ≈ 1.3) and the thin-order interaction (CR-0012 A9) — **in CR-0019 §2** (floor before thinning; filter refuses). Tick at CR-0019 close-out — **done**: `628083d` (floor at step 2 before thinning; refusal), live `00b0b84` (14 positives restored by re-thinning)
- [x] CR-0015 written (v1, 2026-09-30): assumed-negative background — in-state, training blocks only, 0 not nodata (BUG-0032), interim `--an-background` guard. Awaiting review

## CR-0007 v9 (round-8 follow-ups, 2026-09-30)
- [ ] Commit CR-0007 deliverable 0 (pre-approval): `check_partition.py`, `tests/test_check_partition.py`, `tests/test_shared_constants.py`, `docs/quality/evidence/CR-0007-check-today.txt`, `DRAFT_BUG-0034-…md`, `res_qms_PA-0019-0020-0021-draft-rows.md` — owner: coordinator (0007 R8 B3)
- [ ] Analysis-CRS constant (`"EPSG:5070"`: 16 code literals in 7 files; also the `x_5070`/`y_5070` schema and CR-0012's `BLOCK_ORIGIN_5070`): deferred PA-0001-extension sweep item (d), its own BUG at CR-0007 deliverable 6 — owner: CR-0007's author, opens a CR after CR-0012 lands (0007 R8 B7)
- [ ] CR-0014 `:12`, `:146` say "CR-0007's I17"; it is CR-0013 O8 since the split — owner: CR-0014's author (0007 R8 B10)
- [ ] CR-0009 `:64` says "when CR-0007/CR-0012 land"; the baselines are affected only by CR-0012 — owner: CR-0009's author (0007 R8 B10)
- [x] CR-0012: when `VAL_FRACTION`/`SPLIT_SEED` join `regions.py`, add them (and `_DEFAULT` aliases) to `check_partition.P6_NAMES` and pin them in `tests/test_shared_constants.py` — owner: CR-0012's author (0007 v9 C1) — **done** (CR-0012 code): `check_partition.py:606` lists `BLOCK_ORIGIN_5070`, `VAL_FRACTION`, `SPLIT_SEED`, `WINDOW_PX`; pinned in `tests/test_shared_constants.py:37-40`
- [ ] CR-0013 v2 `:296` cites "CR-0007 (P1–P7)"; v9 has P1–P8 — owner: CR-0013's author (0007 v9 C2)
- [ ] NH `ch`/`cc` rasters (mtime 2026-09-20 11:32) postdate `evaluated_sightings_NH.csv` (2026-09-18): 1,040 `ch` / 1,265 `cc` values differ. Find what rewrote them (untested, PA-0016; provenance, PA-0019 draft). CR-0007's re-run supersedes the values (O4) — owner: CR-0007's author (0007 v9 C3). Re-run done 2026-09-30: own-state NH rows ch 539 / cc 654 values replaced, P3 feature mismatches 0 (`docs/quality/evidence/CR-0007-gates.txt`, O4); cause still untested
- [x] (resolved by CR-0007 v9.1, `fab0795`) CR-0007 P6 cannot pass: three git-tracked evidence scripts (`docs/quality/evidence/CR-0007-r7/{build,feats,lib}.py`, committed in `f5e5ee4` after v9's approval) are in the P6 scan set. Needs a CR-0007 amendment (exclude `docs/` from the scan, or exempt/re-point them); the repository-tree test keeps its `expectedFailure` marker until then — owner: CR-0007's author (implementer finding F1)
- [x] BUG-0048: first-statement guards for `legacy/download_landfire{,_2,_3}.py` — **done in CR-0007 v9.2 §3** (P7 checks them) (PA-0026 sweep; outside CR-0007 v9 §3) — owner: CR-0007's author (implementer finding F5)
- [x] CR-0012 implementation: confirm the `clean.py` and `legacy/gen_negs.py` guards before CR-0007's P6 exemption for them is relied on (CR-0007 B-R9-1) — **confirmed** (CR-0012 deliverable 8, 2026-09-30): both files start with `raise SystemExit` (CR-0012 §6, `4eb10dd`); `tests/test_cr0012.py::Guards` PASS; BUG-0031 FIXED 5/5
- [ ] **Hypothesis, untested (PA-0016):** `download_rev.py`'s valid-pixel check may pass a raster that declares no nodata value or fails to open. Not a BUG until checked; owner: next change to `download_rev.py` (CR-0013 sweep note) — **Update (PA-0027 sweep, 2026-09-30):** the fails-to-open half is confirmed from code and filed as **BUG-0052** (probe returns `None`, callers read it as a pass), FIXED `4683e3c`. The declares-no-nodata half (`return 1.0`) stays an untested hypothesis here
- [x] Runtime input guards (`download_rev.py:100`, `download_tcc_nlcd.py:409`, `model_handler.py:871`) are outside PA-0021's scope (user, 2026-09-30)
- [x] BUG-0039 → demote CR-0009 v4's symptom gates 1a/1b/2a/2b to OBS (user, 2026-09-30); applied in the CR-0009 working tree (v4 still uncommitted per user)
- [x] BUG-0040 → CR-0016 IMPLEMENTED (RD1/RD4 OBS; analytic-bound question closed)

## CR-0015 v2 (round-1 follow-ups, 2026-09-30)
- [x] User decision (2026-09-30): CR-0015 adds `regions.block_split(block_ids, assignments)` after CR-0012 lands and switches `generate_negatives.py`'s pool step to it (behaviour-preserving; CR-0015 B1 digest check + CR-0013 acceptance unchanged). **CR-0012's pinned text (`29f388b`) is not reopened**; its §2 prose rule and `split_for_unassigned` reference are superseded in code by CR-0015 deliverable 5 (CR-0015 R1 A4/B1)
- [ ] CR-0012 Landing order says "CR-0015 (assumed negatives) is independent"; CR-0015 depends on CR-0012 (block grid, `SPLIT_SEED`, `block_assignments.csv`) and CR-0007 (`in_state`). CR-0015 § Order governs; correct on CR-0012's next revision, if any — owner: CR-0012's author (CR-0015 R1 A10, B9)
- [x] BUG-0029 closure rule, one wording across CRs: corrective action "membership: CR-0007; split and draw: CR-0012; assumed negatives: CR-0015"; FIXED when CR-0015 deliverable 7b passes, CLOSED when CR-0009 also closes. CR-0012 d8 is consistent; **CR-0007 v9 deliverable 6 ("fixed when CR-0012 lands") conflicts** — whoever executes CR-0007 d6 writes BUG-0029 with this rule — owner: CR-0007's author (CR-0015 R1 B8). **CR-0007 d6 executed 2026-09-30 with the approved v9 wording** (CR-0015 is unapproved); see `docs/quality/evidence/CR-0007-implementer-findings.md` F6 — still open — **resolved** (CR-0012 deliverable 8, 2026-09-30): BUG-0029 doc § 6 and `BUG_LOG.md` now carry this rule (positive side fixed by CR-0007/CR-0012; FIXED at CR-0015 7b; CLOSED with CR-0009)
- [ ] CR-0007 review log E-9 / FA-Q3 dispositions say "CR-0012 deliverable 8 files BUG-0032"; the filer is now CR-0015 deliverable 2 (CR-0012 B-2) — annotate as "moved to CR-0015" (PA-0024(b)) — owner: CR-0007's author (CR-0015 R1 B9)
- [x] Decide (user): the 4326→5070 transform CR-0015 needs for block ids lives only in `generate_negatives.to_albers` (and a separate Transformer at `analyze_grouse.py:679`); CR-0012 v2.1 adds no transform helper to `regions.py`. CR-0015 v2 imports `to_albers` lazily on the AN branch (pulls scipy/sklearn/matplotlib via `analyze_grouse`, ~1.3 s). Alternative: move it to `regions.py` now (a second helper, beyond the block_split decision) or leave to CR-0007 item (d) — owner: user (CR-0015 R1 B1) — **decided (user, 2026-09-30):** `regions.to_5070(lon, lat)` added by CR-0015 next to `block_split`; `generate_negatives.to_albers` delegates to it after CR-0012 lands (B1 byte-identical gate); `train.py`'s AN path imports only `regions`. Applied in CR-0015 v2
- [ ] CR-0015 reserves **BUG-0042** (AN points in validation blocks) and files BUG-0032; the two new PAs ("extends PA-0006", "extends PA-0018") take the next free PA ids at filing — owner: CR-0015's author (CR-0015 R1 A7, B3)
- [ ] CR-0012 next revision: state "EPSG:5070 coordinates are recomputed from lon/lat" (§2 conventions) and the block-order tie-break by `block_id` string. Both are already normative in CR-0013 v2.3 § Normative definitions; v2.2 was limited to F2/F3 (CR-0013 implementer F9, F16(a))
- [x] CR-0013 deliverable 5a (replay author): re-pin the config to CR-0007 v9 (`pins.cr0007` → `6619bdd`; `regions_py` extra `COUNTY_POLYGONS` → `COUNTY_POLYGONS_YEAR` + `PATH_TEMPLATES["tiger_county"]`); add rasterio/GDAL/geopandas/shapely/pyogrio to the environment; canonical-order check in R1–R4 from NOTE to GATE; re-run deliverable 5 (CR-0013 implementer F1, F11, F12) — **done** at `3230262` (CR-0013 deliverable 5a ticked; 84 tests, re-run 1/18 as expected)
- [x] After CR-0012 v2.2's bounded re-review: fill its approval commit into CR-0013 rule 4 and the config's `pins.cr0012_text_commit` — **done**: CR-0013 rule 4 cites `cec1542`; `acceptance_split.json` `pins.cr0012_text_commit` = `cec1542`
- [x] CR-0013 v2.3: canonical row order is a **GATE** inside R1–R4 (user, 2026-09-30); the replay author implements it in deliverable 5a
- [ ] CR-0007 P7 docs-import check: extend to `import_module`/`__import__`, `exec`/`compile`, and any `.path.insert/append` receiver (CR-0007 v9.2 reviewer A, LOW); limit stated in the CR

## CR-0009 v5 (round-4 follow-ups, 2026-09-30)
- [x] (round 5 confirmed, 9d8c1c9) Round-4 MEDIUM/LOW items A-D1..D4, A-L1..L5, B-D1..D4, B-L1..L8: addressed in CR-0009 v5 text; tick after round-5 reviewers confirm (dispositions: `CR-0009-review-log.md` § v5 dispositions) — owner: CR-0009's author
- [x] (round 5 confirmed, 9d8c1c9) Items above addressed by CR-0009 v5, to tick on round-5 confirmation: "update the expected positive count to 6,232" (cited from CR-0012 § Impact), BUG-0039 (rows OBS with PA-0021(f) fields), "`:64` says when CR-0007/CR-0012 land" (§ Baselines: CR-0012 only; verified the point files are byte-identical to CR-0007's backup) — owner: CR-0009's author
- [ ] `data/maps/STALE_SEE_CR-0010.txt`: the directory holds `analyze_grouse.py` sightings diagnostics (PNGs rewritten 2026-09-30 11:42, after the marker) and an input download, no model outputs; CR-0009 does not regenerate them. Decide whether the marker still applies — owner: CR-0010's author
- [ ] `old_road_dist/` ownership (item above): CR-0009 v5 no longer reads it (the reproduction uses current rasters; +4,255 m is quoted, not re-measured) — owner unchanged (CR-0014 or user)

## CR-0012 code (20a52c1) — lead notes
- [ ] LOW (owner: CR-0013 replay author): CR-0013's table "I other inputs" does not name the county file `data/roads/tl_2023_us_county.zip`, though `acceptance_split.py:976,1833` requires it as an input. Add it to the table's wording.
- [ ] LOW (owner: CR-0012 implementer): `P7_GUARDED` in `check_partition.py` does not include the `clean.py` / `legacy/gen_negs.py` guards (they are tested in `test_cr0012`).
- [ ] LOW (owner: lead): regenerate `PROJECT_TREE.md` after CR-0012 deliverable 6.
- [ ] LOW (owner: BUG-0047 CR): `generate_negatives.load_evt_crosswalk` and `verify_partition` resolve paths from cwd/`raster_dir`, not the data root; so does CR-0017's domain D (`regions._county_polygons`, `regions.py:87`, reads `PATH_TEMPLATES["tiger_county"]` from cwd while `generate_negatives.py:385` digests the file under `root`; a mismatch FAILs R3, fail-closed; CR-0017 code review F4); `KEY_DECIMALS` lives in `generate_negatives.py`, outside P6 (CR-0012 code review F3, I-L1, I-L5)
- [ ] LOW (owner: CR-0012 implementer): `git_state` gives an opaque error outside a git checkout; `organize_project.py:107` stale `block_assignments_` rewrite; `prepare_training_data` imported twice when run as `__main__` (F4, I-L4, I-L6)


## CR-0012 deliverable 8 bookkeeping (2026-09-30)
- [x] **BUG-0050** (needs a CR): negatives' 300 m buffer blind across the Canadian border; 12 of 6,232 selected negatives, 39 pool candidates within 300 m (`docs/quality/evidence/CR-0012-d8/canada_buffer.txt`). Options: Canadian sightings as a buffer-only source, or drop candidates within `BUFFER_M` of land outside US counties. Changes CR-0012 §2 step 6, CR-0013 E7/R3; re-run acceptance; interacts with the CR-0009 retrain — owner: lead (new CR), user decision on timing vs the retrain — **written as CR-0017** (`docs/quality/change-requests/CR-0017-negatives-buffer-domain-edge.md`): drop candidates within `BUFFER_M` of the sightings' acquisition-domain edge (ME∪NH∪VT, so NY/MA lines too: 88 pool / 23 selected); live run after CR-0009 closes; no retrain (CR-0017 §4) — owner: CR-0017 — **FIXED by CR-0017** (live run `6342f2a`: MC PASS 88/23, 19/19 GATEs, record `9d5ad0a9…`; BUG_LOG updated by deliverable 8)
- [ ] **BUG-0051** (needs its own CR, low; formerly "same CR as BUG-0050"): `analyze_grouse.py` KDE blind across the Canadian border; diagnostic columns only — owner: lead — **re-owned:** out of CR-0017's scope (CR-0011 A5; changes S, re-runs CR-0012/0013 from positives); needs its own CR. Note: the KDE is also blind at the NY/MA state lines (same acquisition domain, CR-0017 review log) — owner: lead (own CR). **CR-0017 deliverable 8:** owner confirmed as its own CR; NY/MA edges and `check_partition.py` P8 recorded in BUG-0051 §6; the fix must use CR-0017's domain D (PA-0032), not "outside US counties"
- [x] **BUG-0052** trivial fix (one function; BUG required, no CR): `download_rev._raster_valid_fraction` return invalid on rasterio/OS errors, re-raise others — **FIXED `4683e3c`** (returns 0.0 and logs on `RasterioIOError`/`OSError`; `tests/test_pa0027_fixes.py`)
- [x] **BUG-0053** trivial fix: `analyze_grouse.load_evt_crosswalk` let read errors propagate — **FIXED `4683e3c`**. Design question settled by the lead (2026-09-30): the crosswalk is required, so missing, unreadable and malformed (no `VALUE`/`EVT_PHYS`) all raise; never returns `None`
- [x] **BUG-0054** trivial fix: `download_tcc_nlcd.sighting_years` catch `MissingDataError` only, print the skip — **FIXED `4683e3c`**
- [x] **BUG-0055** trivial fix: `diagnose_wetland.center_codes` catch `MissingDataError` only, print the skip — **FIXED `4683e3c`** (prints year and uncoded record count)
- [ ] LOW (BUG-0053 follow-up, owner: next change to `analyze_grouse.py` / `generate_negatives.py`): the `evt_xwalk is None` branches at `analyze_grouse.py:787`, `:1110` and `generate_negatives.py:407` are unreachable since `4683e3c`; delete them (left in place so the fix stayed inside one function)
- [ ] LOW (BUG-0053 follow-up, owner: lead): `grouse_data.GrouseData.evt_crosswalk` still returns `None` for a missing or malformed table, and its docstring claims the same semantics as `load_evt_crosswalk`, which no longer holds. No caller in tracked code; decide whether to raise the same way or delete it
- [ ] LOW (BUG-0052 follow-up, owner: next change to `download_rev.py`): after a download, an unreadable raster is rejected with the caller's "raster is empty (0.00% valid pixels)" message; the probe's preceding log line names the real cause. Reword the caller message if it misleads
- [x] **PA-0027 enforcement** (needs a CR; `CLAUDE.md` §3.4) — **DONE: CR-0018 APPROVED, `tests/test_pa0027_lint.py`; PA-0027 row update in `docs/quality/evidence/CR-0018-bookkeeping-rows.md` for the lead**: lint test in the style of `tests/test_nodata_zero_lint.py` flagging every broad handler that neither re-raises nor is allow-listed with a reason (PA-0027 Swept? classification is the initial allow-list) — owner: lead

## CR-0017 round 1 (2026-09-30)
MAJOR items (A1=B1, B2) and most MEDIUM/LOW items were revised into CR-0017 v2 (review log). Open follow-ups:
- [ ] LOW (A2): optional OBS row for the edge-band support asymmetry (positives within `BUFFER_M` of the domain edge per class: train 10 / 4,986, val 0 / 1,246 today; recorded in CR-0017 §3, not gated) — owner: CR-0017 deliverable 2 (replay author), decide and record — **re-owned at CR-0017 close-out:** deliverable 2 landed without it (O1–O10 unchanged); owner: lead, decide with the next change to `acceptance_split.py`'s OBS set — **decided 2026-09-30 at CR-0030 (O11, the next OBS change):** not bundled there (one observation per CR, A5; the edge band is a spatial axis); stays its own small acceptance amendment, owner lead
- [ ] LOW (CR-0017 §4, retrain follow-up): `grouse_cr0009.pth` and earlier models were trained on pre-CR-0017 negatives (23 within 300 m of the domain edge); the next CR that retrains must train on the post-CR-0017 record and say so (live record since CR-0017 deliverable 6: `9d5ad0a9…`; `CHANGELOG.md` CR-0017 entry) — owner: author of the next retrain CR
- [x] MEDIUM (A3=B4, process): CR-0017 deliverables 2–4 stay on an unmerged branch until deliverable 6; whoever merges branches must not merge it early (config sha change refuses all training until the new record) — owner: lead — **done:** merged at deliverable 6 step 1 (`4080f74`), record written in the same run (`6342f2a`)
- [x] BUG-0064 (NY/MA sibling of BUG-0050) and the proposed PA extending PA-0023 (review log § Proposed bookkeeping rows): allocate the BUG id — owner: lead; filing — owner: CR-0017 deliverable 8 — **filed:** BUG-0064 (FIXED by CR-0017), PA-0032 (extends PA-0023), sweep in BUG-0064 §8

## CR-0017 round 2 (2026-09-30)
Round 2 approved v3. A8, B11 and B12 were applied in v3; there are no
open round-2 items beyond the CR-0017 round-1 list above.
- [x] LOW (B11 residual, stated limit): MC does not check the N-only
      columns of added rows other than `label` (`obs_date`,
      `coord_uncertainty_m`), nor the identity of the replacements. R4
      checks both in the same run. If MC is ever run without R4, extend
      MC4 to compare them with `gbif_negatives_R` by `gbif_id` — owner:
      CR-0017 deliverable 6 executor. — **Not triggered:** MC was a
      one-off for this regeneration and R4 ran and passed in the same
      deliverable (`docs/quality/evidence/CR-0017/live/acceptance.log`).

## BUG-0056 bookkeeping / PA-0030 sweep (2026-09-30)
- [ ] **BUG-0062** (needs a CR): `evaluate()` / `calibrate.collect_val_logits()` check the TTA grouping contract from the dataset (every leaf `GrousePatchDataset.expand_rotations`, sequential loader) and raise when `tta_group > 0`; drop `collect_val_logits`' per-rotation fallback. CR outline in BUG-0062 §6 — owner: lead
- [ ] **BUG-0061** decision + trivial fix: `_log_metrics` header mismatch on append → raise `ValueError` (recommended) vs. new file; one function — owner: next change to `model_handler.py`
- [ ] **PA-0030 enforcement** (needs a CR; `CLAUDE.md` §3.4): lint test from `docs/quality/evidence/BUG-0056/sweep_condkeys.py` with an allow-list seeded from `sweep_triage.md` — owner: lead
- [ ] LOW: `fit()` always calls `evaluate()` with the default `tta_group=4` and cannot opt out; decide with BUG-0062's CR whether `fit()` forwards `tta_group` (signature change) — owner: BUG-0062 CR author
- [x] CR-0012 deliverable 6 test plan item 7 (`smoke_test_training.py`) re-run after `40dbecf`: PASS, all 7 stages, scratch tree B (`docs/quality/evidence/CR-0012-d6/smoke_rerun.txt`)

## CR-0018 (2026-09-30)
PA-0027 lint `tests/test_pa0027_lint.py`. BUG candidates, pinned in its `EXPECTED_UNCLASSIFIED` (CR-0018 §4); filing or fixing one must remove/re-key its entries. Filed 2026-09-30 as BUG-0065..0071 (fixes `0355240`); `EXPECTED_UNCLASSIFIED` is now empty, the two pending `acceptance_split.py` sites are in `KNOWN_OPEN`:
- [x] LOW **C1** `download_rev.py:149` `published_products`: broad catch → `None`, caller prints "unreachable" without the exception type; missed by the PA-0027 sweep — **BUG-0065, FIXED** (`0355240`: type logged; allowlisted visible-unknown)
- [x] LOW **C2** `fetch_tile` in `download_tcc_nlcd.py:338` and `download_treemap.py:263`: retry catches `Exception`, no per-retry log (PA-0027 retry clause) — **BUG-0066, FIXED** (`0355240`: transient types only, type+traceback per retry)
- [x] LOW **C3** `ee_init` in `download_tcc_nlcd.py:146` and `download_treemap.py:152`: `as persistent_err` is unbound after the clause, so the SystemExit message becomes `UnboundLocalError` — **BUG-0067, FIXED** (`0355240`; confirmed by repro; new PA-0031 proposed)
- [ ] LOW **C4** `acceptance_split.git_commit` (`:152`): unknown dirty state recorded as `False` by `build_manifest` (`:1185`) — **filed BUG-0068, OPEN** (also: non-zero `git status` return code reads as clean); fix pending, owner: after CR-0017 merges (CR-0013 author on fix; two functions + manifest `dirty` may become `null`, so a CR or the next CR touching the file)
- [ ] LOW **C5** visible-unknown without the exception type: `acceptance_split.py:2620`, `analyze_grouse.py:658,671`, `check_exotic.py:71`, `check_raster.py:57`, `check_road_dist.py:480`, `symptom_check.py:663` — **filed BUG-0069, PARTIALLY FIXED**: six sites fixed and allowlisted (`0355240`); `acceptance_split.py:2620` (`full_run#0`) pending, owner: after CR-0017 merges
- [x] MEDIUM **C6** region skip in diagnostics: `diagnose_training.py:52`, `diagnose_water_bias.py:115` (BUG-0055 shape) — **BUG-0070, FIXED** (`0355240`: `MissingDataError` only; totals marked INCOMPLETE)
- [x] MEDIUM **C7** `generate_treemap_features.py:179` `_source_is_valid`: any error → vintage skipped with a wrong printed cause, exit 0 — **BUG-0071, FIXED** (`0355240`: `OSError` only, cause printed)

BUG-0065..0071 follow-ups (2026-09-30):
- [ ] LOW (BUG-0070): `diagnose_water_bias.main`'s VERDICT omits a skipped region without a line of its own (the skip is printed in the region's section); add a "skipped: [...]" VERDICT line — owner: next change to `diagnose_water_bias.py`
- [ ] LOW (BUG-0067 / PA-0031): PA-0031's enforcement is the re-runnable sweep `docs/quality/evidence/CR-0018-candidates/sweep_except_name.py`; a lint test (zero hits over the lint file set) needs a CR — owner: lead
- [ ] LOW (BUG-0069): the PA-0027 lint does not check that a `visible-unknown` ALLOWLIST handler records the exception type (CR-0018 §5); consider a check that the handler body references `type(<exc name>)` or `traceback` — owner: lead (CR-0018 follow-up change)

Review follow-ups:
- [ ] MEDIUM (A-r2, R-A5a): lint limits in CR-0018 §5 — broad→narrow laundering, aliases/walrus, caller-side handling, `finally`-swallow, `yield` before `raise` — decide whether to extend PA-0027's text and the lint — owner: lead. Caller-side handling now has two filed instances: BUG-0068 (`None` coerced to clean by `bool()` in another function) and BUG-0071 (probe's `False` turned into a vintage skip by its callers); see their §8
- [ ] LOW (B11): run-time string exit messages (`SystemExit(msg)`) do not conform mechanically; accept str-producing expressions if such a handler appears — owner: lead
- [ ] LOW (B9): `docs/quality/evidence/` acceptance scripts are outside the lint's file set; revisit if one gains a broad handler — owner: lead
- [ ] LOW (CR-0018 T8, reviewer B): `download_tcc_nlcd.collection_years` (`:209`) fallback to `system:index` is silent; print it — owner: next change to `download_tcc_nlcd.py`

## CR-0015 implementation code review (head 3add80b) — follow-ups, owner: lead
- [ ] A-1 (MEDIUM): the V3 broken-side calibration uses 5 draws per sampler (`tests/cr0015_background_check.py`, `for s in range(5)`), below PA-0021(c)'s ≥ 50. It does not affect the OBS verdict. Before V3 is ever re-read as a GATE, run ≥ 50 seeds per broken sampler, or record that the unassigned-excluded statistic is deterministic (share 0 → equals the reference share).
- [ ] A-5 (LOW): no test checks the `train.build_datasets` call site (`train_blocks_only=True`, global `data.block_assignments`). A wrong-but-valid assignments frame would pass silently. Add a mock-based call-site test, or run V1's checker on the `bg_df` built inside `build_datasets`.
- [ ] A-6 / B-7 (LOW / INFO): NH's observed acceptance of 0.3773 (V2) is below CR-0015 §2's budget premise of p ≥ 0.38. Sampling still converged in 6 of 40 rounds. Do not cite the budget argument as verified for NH.
- [ ] B-3 (LOW): `regions.block_split` does not validate `assignments`:
  - an empty frame gives `vf` NaN, so every unassigned block becomes "train";
  - a duplicated `block_id` is decided by its last row;
  - a label outside {train, val} lowers `vf`.

  Fix: raise `ValueError` on each case, then re-check B1 and `test_cr0012`. This is a production-code validation change, out of CR-0015's scope, and needs a CR or a trivial-fix record.
- [ ] B-4 (LOW): V3 is OBS under CR-0015's literal rule (lead decision; both reviewers concur). Optional later CR: scope V3's separation requirement to the samplers the CR's "caught by" table assigns to V3, and restore it as a GATE (needs A-1 first).
- [ ] B-6 (LOW): `pretrain.py`'s preflight calls the private `regions._state_polygons()`. Use a public API, such as a one-point `regions.in_state` or a new `regions.require_state_polygons()`.

## CR-0015 bookkeeping design questions (2026-09-30), owner: lead
- [ ] **D1:** validation data drives model selection, the divergence guard, `--dynamic-dropout` (`model_handler.py:1306`) and Platt calibration. There is no third holdout, so reported validation metrics carry selection bias. Decision needed: accept and document, or add a test holdout.
- [ ] **D2:** `calibrate.cross_fitted_probs` (`calibrate.py:229-239`) uses random folds, not block folds, so `ece_cross_fitted` and `nll_cross_fitted` are slightly optimistic. Reported numbers only.
- [ ] **D3:** training-negative weights (`Selection_Ratio` over every sighting, validation included) and the 300 m buffer depend on validation positives (`generate_negatives.attach_weights`). No CR-0013 gate asks this. — **filed as BUG-0076** (2026-09-30 static review; PA-0033); the buffer half is recorded there as removing, not steering.
- [ ] **D4** (still a design question, no BUG; noted by the 2026-09-30 static review): there is no buffer between training and validation blocks. The 64 px window is about 1.9 km and the blocks are 3 km, so features leak across block edges. Labels do not.
- [ ] The `train.py:246` comment "Covers every caller" omits `smoke_test_training.py` and `diagnose_training.py`, which build datasets without `standing_checks` (no model is kept). Doc fix.
- [ ] The `find_tsd_contrast_points.py` docstring (about lines 40-44) says `read_window_stack` "zeroes NODATA_SENTINELS to 0". That has been stale since `51a4ad0`. Doc fix.

## CR-0017 implementation code review (head b059624) — follow-ups, owner: lead
- [ ] F2 (LOW, reviewer A): "file CRS straight to EPSG:5070, never via 4326" is not observable in this environment (NAD83→WGS84 is a null/ballpark transform here). An acceptance-side detour via `target_crs` survives the suite; a pipeline-side detour is killed only incidentally. Optional: an `ast` source-shape test that `regions._domain_5070` and `acceptance_split.acquisition_domain` project nothing to 4326/`target_crs`; otherwise record as not validatable here. A disagreement would FAIL R3 (fail-closed).
- [ ] B-1 (LOW, reviewer B): pipeline (`regions.domain_edge_m`, GEOS distance) and replay (`acceptance_split.domain_edge_within`, segment split) agree to ~1e-10 m, not bit-exactly, at `edge_m == BUFFER_M` on long diagonal edges (3 of 20,000 synthetic points at 300 ± 1e-7 m). Any disagreement FAILs R3/R4 (loud). Real-data margin is 1.802 m and the real D is identical in both. No code change; recorded here.
- [ ] B-2 (LOW, reviewer B): the pipeline projects each county then unions in 5070; the replay dissolves by state in the file CRS then projects. On non-noded inputs (T-joins) they differ (synthetic: 33.6 km² sliver). Identical on the pinned TIGER file. If the county file or year changes (the config sha pin forces a re-review), re-check D equality between the two constructions, or make the pipeline dissolve by `STATEFP` before projecting.
- [ ] B-5 (LOW/INFO, reviewer B): a county file with no CRS is assumed EPSG:4269 by the pipeline (`regions.py:91`), and a WKT NAD83 CRS without an EPSG id is accepted; the replay (`acceptance_split.py:775`) refuses anything whose `to_string()` is not `EPSG:4269` (loud `ReplayError`). The file is sha-pinned; no action unless the file changes.

## CR-0017 deliverable 8 bookkeeping (2026-09-30)
- [ ] **BUG-0072** (LOW, diagnostic only): `diagnose_water_bias.build_distance_raster` reads NLCD nodata (Canada) as "no water"; 28/8 (ME), 2/1 (NH), 3/2 (VT) positives/negatives nearer nodata than water (`docs/quality/evidence/CR-0017/sweep/water_dist_edge_probe.txt`). Fix: NaN where nodata is nearer than water, summaries drop and count them (two functions, prints change) — owner: next change to `diagnose_water_bias.py` (with BUG-0070's VERDICT item)

## CR-0019 (IMPLEMENTED, 2026-09-30) — follow-ups
- [ ] **CR-0020** (to write): retrain from scratch, refit calibration, new validation baseline on the post-CR-0019 split (CR-0009's shape). Owner: lead. CR-0009's baseline (AUC 0.7783, AP 0.6851 at prevalence 0.4372) is not comparable after CR-0019
- [ ] **Checkpoint warning** (CR-0019 §6): after CR-0019's live run, no pre-CR-0019 checkpoint (`grouse_cr0009.pth` or older) in `calibrate.py --model`, `--distill-from`, `--init-from`, `--resume`, nor evaluated on the new val set (48 of 962 new val negatives were its training negatives). Owner: lead until CR-0020 lands
- [ ] LOW (CR-0019 A6): the warning above is prose only; mechanical refusal — owner: **BUG-0060**'s CR
- [x] **BUG-NEW-a** (proposed in CR-0019 review log § Proposed bookkeeping; next free id BUG-0073): residual within-epoch year imbalance (year→label AUC 0.6615); candidate causes the two representative-year rules and the acquisition order. Owner: lead (files at CR-0019 deliverable 8; fix by its own CR) — **filed as BUG-0073** (fix item below)
- [ ] LOW (CR-0019 B12 = code review A-1): `filter_by_year_gap` refuses via `SystemExit` from a library function; consider a named exception (e.g. a `SystemExit` subclass) for testability — decided in code review: bare `SystemExit` accepted for approval (fail-closed, CLI correct); reviewer A recommends `class YearGapRefused(SystemExit)` in `train.py` with `FilterByYearGap` asserting it. Owner: lead, with CR-0020's train-side work
- [x] Sweep items for CR-0019 deliverable 8 (PA-0020): `train.sample_background_points` single vintage; envelope-metric epoch (2016+ sightings weighting 2020+ training, CR-0019 B4); the two representative-year rules (A2); duplicated `START_YEAR` (`sightings.py:23`, `ebird.py:20`; B8, PA-0025 review-only) — owner: CR-0019 deliverable 8 — **done**: PA-0020 Swept? (CR-0019 deliverable 8): BUG-0073, BUG-0074, BUG-0075 filed; envelope epoch recorded as not an instance (item below)
- [ ] **BUG-0073** (OPEN): within-epoch year-distribution residual (AUC 0.6615). Own CR: harmonise the representative-year rules (no network; test PA-0016 first), year-matched draw (215 short in 6 of 30 cells) or re-fetch (user decision); add a distribution check next to E14; candidate PA-0020 extension (BUG-0073 §8). Decide before CR-0020's baseline is final, or CR-0020 records the residual. Owner: lead
- [ ] **BUG-0074** (OPEN, latent): `train.sample_background_points` gives every `--an-background` row one vintage (latest of `features[0]`). **No run with `--an-background > 0` until fixed** (CR-0020 must not use it unless it fixes this first). Fix needs a CR. Owner: lead
- [ ] **BUG-0075** (OPEN, low): `START_YEAR = 2016` literal in `sightings.py:23` and `ebird.py:20` → `regions.START_YEAR`, pinned; with BUG-0073's CR or its own small CR. Owner: lead
- [ ] Envelope-metric epoch (CR-0019 B4, deliverable 8 sweep item 4): metrics fitted on 2016+ sightings weight 2020+ negatives; not a PA-0020 instance (a sampling weight, no label), kept by CR-0019 §2. Open question "is 2016–2019 habitat use different?" goes with BUG-0073's CR. Owner: lead

## CR-0019 implementation code review (heads c599307 / 3cd1ea9) — follow-ups, owner: lead
Reviews: `docs/quality/evidence/CR-0019/code-review/`; dispositions in `CR-0019-review-log.md` § Implementation code review. Both APPROVE WITH FOLLOW-UPS.
- [ ] LOW (A-2 = B F4): `acceptance_split.pool_year_floor` / `load_candidates` raise a raw `KeyError: 'year'` when a candidate file has no `year` column, where CR-0019 §3 says the replay raises `ReplayError` where the pipeline raises (`generate_negatives.py:372` ValueError). Fail-closed (R-gate FAIL via `:984`); message only. Fix: `ReplayError(f"{rpath(...)}: no 'year' column")` in `load_candidates`, plus a test. Re-pin PA-0027 lint digests if touched
- [ ] LOW (B F2): `download_tcc_nlcd.py:291-295` warning still says "train.py will EXCLUDE these records unless --max-train-year-gap loosens it"; since CR-0019 train.py refuses. A runtime string, not a comment, so not fixed in CR-0019 deliverable 7 (the same stale text in `grouse_model_results_summary.md:61` was fixed there). Fix: "train.py refuses …; see regions.YEAR_MIN" (trivial fix + BUG entry, or with the next change to that file)
- [ ] LOW (B F3, PA-0030(a)/(d)): `acceptance_split.gate_E14`'s `years` dict holds "P"/"N" conditionally (fail-closed consumer guard). Add a comment naming the optional keys and a unit test dropping `year` from one N file → FAIL "N: no 'year' column"
- [ ] LOW (B F5, pre-existing from CR-0017): the PA-0031 sweep reports 2 false positives in `acceptance_split.gate_E13` (`except MissingInput as e:` returns; `e` later rebound). Rename the later variable or teach the sweep about rebinding; with the PA-0031 lint item above
- [ ] LOW (B F6): `docs/quality/evidence/CR-0019/combined/standing_check.py:1-4` and `RUN.txt` step 7 say "no augment"; train.py's default is `--augment` on (equivalent, jitter 0 → pad 0). Evidence wording only; correct if the evidence is ever re-run
- [x] MEDIUM (B F1): E14(b) mirror test (a year only in N) — **fixed** `b8e96cf` (mutant P⊆N now killed)
- [x] LOW (A-3): deliverable-4 evidence called `filter_by_year_gap` directly, not `build_datasets` — resolved on the combined scratch tree (`3cd1ea9`): `combined/standing_check.py` shows the check `build_datasets` runs first passes, `yeargap_check_run*.txt` makes the four `filter_by_year_gap` calls `build_datasets` makes (tol 2: 0 dropped; tol 1: refuses), and `combined/RUN.txt` step 7 records why `build_datasets` itself was not called (reviewer A's second option)

## Static code review 2026-09-30 (whole pipeline at `3b3e7d1`, no data, no execution), owner: lead
Filed as BUG-0076..BUG-0092 (`docs/quality/bugs/`, `BUG_LOG.md`), rules PA-0033..PA-0047 (PA-0040 supersedes PA-0009). All OPEN, none fixed. In priority order:
- [ ] BUG-0076 validation negatives drawn with holdout-fitted envelope weights (was D3) — **CR-0020** v3 approved by agent quorum (two rounds); not implemented
- [ ] BUG-0077 `get_negatives.py` rollover greedy in ascending year (candidate cause of BUG-0073) — **CR-0022** v4 approved by agent quorum (two rounds; user decided 2026-09-30 not to re-fetch; latent code fix only, resumed-run quotas included); not implemented; the year-distribution observation O11 is **CR-0030** (split under A5; v2 approved by agent quorum); BUG-0073's harmonisation CR still to write
- [ ] BUG-0078 `EVT_PHYS_NONVEG_PREFIXES` "Agriculture" never matches LANDFIRE "Agricultural" — **CR-0021** v3 approved by agent quorum (two rounds; measure first, rebuild if any row changes); not implemented
- [ ] BUG-0079 non-atomic multi-year raster writes + `raster_path` fallback + filename-only year check (tsd future leakage, latent) — **CR-0023** v3 (unconditional refusal on the training path; seven writer sites; close-then-validate-then-replace) awaiting round-3 bounded re-review
- [ ] BUG-0080 `standing_checks` does not bind `block_assignments.csv` (latent, `--an-background`) — **CR-0024** v3 (code-owned `STANDING_KINDS`; path recording in `path()`; run-time guard) awaiting round-3 bounded re-review; open item from its review: CR-0015's V1 gate on `sample_background_points` output is not re-run by `standing_checks` (PA-0037 second clause) — recorded at CR-0024 close-out with BUG-0074
- [ ] BUG-0081 `analyze_grouse.py` skip paths leave stale outputs, exit 0 — **CR-0025** v3 approved by agent quorum (two rounds; five skip paths, `:836-837` added to BUG-0081 §2); not implemented
- [ ] BUG-0083, BUG-0085 `diagnose_training.py` §3, `smoke_test_training.py`, `bench_pipeline.py` restate `train.py` defaults by hand — **CR-0026** v3 approved by agent quorum (two rounds); not implemented
- [x] BUG-0082, BUG-0084, BUG-0087, BUG-0088, BUG-0091, BUG-0092 — fixed in code (`2c05388`, trivial fixes); validation pending on the data host (commands in each BUG §6)
- [ ] BUG-0086 `--use-weights` double weighting (latent) — **CR-0027** v3 approved by agent quorum (two rounds; option A on the reviewers' technical verdict, the lead may object at implementation); not implemented
- [ ] BUG-0089 — **CR-0028** v3 approved by agent quorum (two rounds; constant in `regions.py`, row remap, fail-closed readers); BUG-0090 — **CR-0029** v3 approved by agent quorum (two rounds); neither implemented
- Candidates not filed (unverified here, need one check each): Earth Engine exports requested on a lattice half a pixel off the NLCD/TCC/TreeMap native grid (`download_tcc_nlcd.py:310-313`, `download_treemap.py:234-237`; fixed ~15 m shift before the template warp — confirm native origins, then file); GBIF negatives taken as an index-order prefix rather than a sample (`get_negatives.py:269-272`; folded into BUG-0073/BUG-0077's CR as a question).
