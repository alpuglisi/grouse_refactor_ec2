# CR-0007 / CR-0008 open issues

To-do list of unresolved review findings. Detail lives in each CR's § Review.
Tick an item only when the fix is in the CR's operative text (body,
Deliverables, test plan), not just in a revision note.

IDs: `R7-n` = CR-0008 round 7 concern n; `B-n` = CR-0007 v7 reviewer B concern n.

## Shared / decisions needed
- [ ] Land bookkeeping batch: PA-0019/0020/0021, BUG-0030/0033/0035; name an owner (0007 B-8, 0008 R7-2)
- [ ] Decide: pre-landing baselines vs defined `gate_obs_only` mode; fix CR-0009 to match (0007 B-2)
- [ ] Decide: `TIGER_YEAR` value (2023 vs 2025, commit a995898); align both CRs (0007 B-9)
- [ ] Decide: TreeMap coverage boundary (pinned G0 `nlcd` mask?) (0008 R7-1, R7-3)
- [ ] Decide: Canadian-border road distance — nodata or accepted residual (0008 R7-4)
- [ ] Reconcile I17 / G5 hand-off between CRs; give it an owner in CR-0007 or CR-0009 (0008 R7-5, R7-6)
- [ ] Reconcile PA-0021 clause text: one version, cited consistently (0008 R7-12)

## CR-0007
- [ ] B-1 Recover rounds 3–6 verdicts from prior-session transcripts; rebuild round table; disposition all concerns; list every reviewer for quorum
- [ ] B-2 Escape-mode contradiction (`gate_obs_only` undefined; "Deleted: the escape mode")
- [ ] B-3 Gate call-site matrix (GATE/OBS per script); SUP rows have no call site
- [ ] B-4 I16b: in-run null vs frozen constants
- [ ] B-5 I19′ nulls must come from independent harness, pre-registered
- [ ] B-6 Deliverable: run recorded attacks against implemented gates; port or pin broken `inv_*` scripts
- [ ] B-7 Fold accepted dispositions into operative text (`TIGER_YEAR`, `ignore_index`, negative `verify_partition`, windowless drop, PA-0020 cite, §6 (d), test plan, "Not optional detail" header); mark superseded v4 sections
- [ ] B-8 Bookkeeping batch owner (see Shared)
- [ ] B-9 `TIGER_YEAR` behaviour change (see Shared)
- [ ] B-10 `generate_negatives.py --regions` write guard; raise before any `to_csv`
- [ ] B-11 Rule in/out: hash ordering, `draw_val_blocks`, stratification, flag removal
- [ ] B-12 Pin I5 window (`img_size + 2·jitter`, year rule) in manifest
- [ ] B-13 `PATH_TEMPLATES` entries for new paths
- [ ] B-14 KDE clip vs PA-0018
- [ ] B-15 SUP0 VT/val 0.87 claim appears false
- [ ] B-16 Family-wise false-fail rate; threshold-rule consistency; C11, I15, I18 gaps
- [ ] B-17 I6 target definition
- [ ] B-18 BUG ids for `TIGER_YEAR` drift, `STATE_FIPS`/`MIN_SPACING_M` dupes, `generate_negatives.py:153`
- [ ] B-19 Citation/count fixes (`:444`, `:143`, `:443-444`, consumers 18 + `tune_bins.py`, 5 guards, backup items, I5 raise point)
- [ ] B-20 Reorder deliverables (backup first)
- [ ] B-21 §7 geopandas dependency in `train.py`
- [ ] Risk table: add 4 missing risks; extend "cannot validate" list
- [ ] A-1 **BLOCKING** I18 per-region inverted: false-fails ~52 % of correct runs, blind to BUG-0027 leak; revert to pooled or per-region null bands
- [ ] A-2 **BLOCKING** No gate on 300 m exclusion buffer (removing it: ~2,053 of 6,230 negatives within 300 m of grouse, all gates green); add exact min-distance predicate, centralise `BUFFER_M`, lower bound on I19′
- [ ] A-3 **BLOCKING** Rounds 3–5 verdicts/dispositions (same as B-1)
- [ ] A-4 I19′ val cells calibrated on wrong null (6–11σ slack); condition on realised positive split; fix stated limit 3
- [ ] A-5 Gate duplicate negatives within a split (0 dup 5 dp keys, 0 pairs < `MIN_SPACING_M`)
- [ ] A-6 Re-derive C5–C17 on rebuilt footing (deliverable)
- [ ] A-7 Persist `weight`, `weight_basis`, `evt_phys`, `common_name`, `envelope_id`, `year`; compute C rows in `acceptance.py`, not `generate_negatives.py`
- [ ] A-8 Escape mode (same as B-2)
- [ ] A-9 §6 contradictions / superseded (d), "Not optional detail" (overlaps B-7)
- [ ] A-10 I16b (same as B-4)
- [ ] A-11 VT val NonVeg claim false (same as B-15)
- [ ] A-12 SUP-R/SUP-O headroom; re-pin after rebuild
- [ ] A-13 Known-exceptions: ticked in deliverables, open in body
- [ ] A-14 Citations (`:302`→`CSV_KEEP :89-90`, `:143`, `:160`, `:444`, `:443-444`, "723 blocks", year rule, NH 3 of 5,220)
- [ ] A-15 `GATE_REGIONS` from artifact under test; `generate_negatives --regions` guard (overlaps B-10)
- [ ] A-16 Deliverable order (same as B-20)

## CR-0008
- [ ] R7-1 TreeMap generator needs external mask; strengthen G4.2; withdraw "latent defect is closed"
- [ ] R7-2 Approval preconditions + sign-off paragraph (v6 → v7, quorum rule)
- [ ] R7-3 `download_treemap.py` mask chain; `:315` clip
- [ ] R7-4 Canadian-border roads (see Shared)
- [ ] R7-5 Impact cross-CR claims (I17, "2 records", "4 of 3,659", measure both landing orders)
- [ ] R7-6 "Either order" vs PA-0020 dependency
- [ ] R7-7 Remove withdrawn text from operative sections ("three" schemas, § Disk idiom list, "18.4 %", test plan, Impact 47.1 %, "1.0000", disk "not a blocker")
- [ ] R7-8 "§ Scope's table" → § Coverage
- [ ] R7-9 `tsd` `hit` parenthetical; vintage set d ≤ Y
- [ ] R7-10 G7: all 10 `road_dist` year-copies byte-identical
- [ ] R7-11 Name all four encoders (`tpa_live_encode`, `tsd_encode`, `treemap_encode`, `road_dist_encode`)
- [ ] R7-12 PA-0021 exemptions; calibrate or label OBS (0.06 %, G6 1.2×, RD1/2/4); GATE/OBS labels for G3, G5
- [ ] R7-13 PA-0019 provenance tags on repaired files
- [ ] R7-14 Risk table rows (G8 cache, RD5, G8.3)
- [ ] R7-15 Attribute rounds 1–5 disposition rows to round/reviewer
- [ ] R7-16 Restore rehearsal: order, scratch space, G8.2
- [ ] R7-17 LOW batch (`:294`, G0.2, 33 % vs 25.6 %, G6 coverage of `road_dist`, VT counties, G8.3 files, CR-0009 "9.75 GB", MiB)

## Handed over from CR-0010 review
- [ ] CR-0008 v8: add deliverable to remove CR-0010's `GROUSE_REPAIR` refuse-to-overwrite guard once generators are fixed (CR-0010 B4)
- [ ] CR-0008 v8 and CR-0006: drop BUG-0030 creation — CR-0010 owns it (CR-0010 B3)
