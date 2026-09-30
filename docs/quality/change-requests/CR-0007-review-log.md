# CR-0007 review log

History, verdicts and dispositions for CR-0007
(`docs/quality/change-requests/CR-0007-record-partition-and-global-split.md`),
reconstructed on 2026-09-30 from the review transcripts. Closes the
"reconstruct rounds 3–6" part of open item B-1 / A-3 in
`docs/quality/CR-0007-0008-OPEN-ISSUES.md`. It does **not** disposition
anything: where the CR never recorded a disposition, this log says
**NOT DISPOSITIONED**.

## Where the history is
- **Review reports, verbatim**: prior session
  `~/.claude/projects/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/subagents/agent-<id>.jsonl`
  (rounds 1–6); this session
  `~/.claude/projects/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/subagents/agent-<id>.jsonl`
  (round 7). Each report is the reviewer's final assistant message for the
  turn (rounds 1–6) or its `SubagentHandback` message (round 7). Several
  reviewers were re-used across rounds via `SendMessage`, so one agent file
  can hold several reviews; the turn start/end times identify which.
- **CR text in git**: only two states exist.
  `1445ccd` (2026-09-30 05:23) holds the text round 3 reviewed. Its header
  reads "REVISED (v2)", but it contains the `I14 … (v3)` section and
  "Corrections to v2", so it is v3 (round-3 reviewer F noted the wrong
  label). `bb170ea` (09:42) holds v7. **v1, v2, v4, v5 and v6 were
  overwritten in place and are not recoverable.** Round-3 reviewer E
  flagged this at 05:18, before the first commit.
- **Dispositions**: the only disposition table the CR ever had is the
  "Rounds 1 and 2" table, first present in v3 and carried unchanged to v7.
  Rounds 3–7 have no disposition table. For those rounds this log cites
  the revision notes ("Revision note (vN → vN+1)" in v7), which were
  written after the fact and do not name the concern they answer.

Severity mapping: BLOCKING and MAJOR as given. The reviewers' MINOR is
mapped to LOW. MEDIUM is used only where the reviewer wrote MEDIUM (round 7
A and B). "unrated" means the reviewer raised the point without a severity.

## Rounds

| round | CR version reviewed | reviewer (label) | turn start → report (UTC, 2026-09-30) | verdict on CR-0007 | blocking | transcript (prior session unless noted) |
|---|---|---|---|---|---|---|
| 1 | v1 | B — implementation lane (continuing from CR-0006) | 04:12:53 → 04:21:24 | APPROVE WITH CHANGES | 1 | `agent-a8e8151bfdf378850.jsonl`, turn 4 of 4 |
| 1 | v1 | D — acceptance lane, "attack the invariants" (continuing from CR-0006) | 04:12:35 → 04:22:08 | REJECT | 1 (+5 MAJOR, 6 MINOR) | `agent-adfa8c6372dd663ff.jsonl`, turn 2 of 2 |
| 2 | v1 at start; v2 (580 lines, with I10–I13, R5–R7) at finish | F — fresh, standalone | 04:13:19 → 04:52:22 | REJECT | 4 | `agent-abe305a7a196c1e30.jsonl`, turn 1 of 3 |
| 3 | v3 (= `1445ccd`) | F — round-3 re-review | 05:09:34 → 05:17:56 | REJECT | 4 | `agent-abe305a7a196c1e30.jsonl`, turn 2 of 3 |
| 3 | v3 (with CR-0008 v3, CR-0009 v3) | E — QMS compliance across the set | 05:10:16 → 05:18:10 | APPROVE WITH CHANGES (CR-0007); REJECT CR-0008 and CR-0009 | 4 that bind CR-0007 (programme-level; 9 in the report overall) | `agent-a53e448b3530f7186.jsonl`, turn 3 of 3 |
| 3 | v3 (with CR-0008 v3, CR-0009 v3) | H — fresh attack on the whitelist design | 05:10:44 → 05:39:22 | REJECT | 3 (CR-0007 section) | `agent-a741c08065b0de385.jsonl`, turn 1 of 1 |
| 4 | v4 | F — expedited (~10 min, scope-limited) | 06:30:10 → 06:32:38 | APPROVE WITH CHANGES | 1 (Q3 edit list, "blocking, mechanical") | `agent-abe305a7a196c1e30.jsonl`, turn 3 of 3 |
| 5 | v5 (+ `DRAFT_BUG-0034`) | Formal A — fresh formal quorum review | 06:38:22 → 07:07:16 | REJECT | 4 | `agent-a199a3616d6eefd65.jsonl` |
| 6 | v6 (+ `DRAFT_BUG-0034`) | Formal C — fresh formal round 2 | 07:51:35 → 08:12:09 | REJECT | 10 | `agent-a3a5647bd2ca4ce17.jsonl` |
| 7 | v7 (`bb170ea`) | A — formal / correctness (fresh) | 09:15:33 → 09:33:30 | REJECT | 3 | this session, `agent-a6252da19a9b2a9f9.jsonl` |
| 7 | v7 (`bb170ea`) | B — implementation and §1 compliance (fresh) | 09:15:33 → 09:25:15 | REJECT | 2 | this session, `agent-aa696f988cde92fdf.jsonl` |

**11 reviews over 7 rounds by 7 distinct reviewers** (B, D, E, F, H,
Formal A, Formal C before v7; round-7 A and B are new agents). Quorum
under `CLAUDE.md` §1.4 therefore needs every one of them plus the author.

Excluded, because they are not reviews of CR-0007:
- CR-0006 reviews by the same agents: `ab89dd47` (A, 2 turns), `a8e8151`
  turns 1–3, `ac77bd9b` turns 1–2, `adfa8c6` turn 1, `a53e448` turn 1.
- CR-0008/CR-0009 reviews: `ac77bd9b` turn 3, `a53e448` turn 2,
  `a7b1f356` (3 turns), `a221c3a0`, `a44688df`; this session's CR-0008 and
  CR-0010 agents.
- Research and design agents told explicitly "not a reviewer" / "Do not
  issue a verdict", although their prompts cite CR-0007: `ae8a9b10`,
  `ad937638`, `a77c7cae`, `a52f3637`, `add3b2e0` (05:28–05:29); `a761dc34`,
  `afcc3cf8`, `abceebc0`, `aa55524e`, `abdbde3e`, `accb1b97` (08:18–08:20).
  v7's revision note calls their output "six parallel research
  investigations".

The main-session transcript's `Agent` and `SendMessage` calls were listed
in full. No CR-0007 review exists there that is not in the table above.

## Concerns and dispositions, by round

"Rounds 1–2 table" means the Dispositions table in § Review, which is
identical in v3 and v7. "rev note vX→vY #n" means item n of that revision
note as it stands in v7. "R7 A-n / B-n" means the same point was raised
again in round 7, so it is still open at v7. "Addressed in vN" means a
later text answers the concern, but no disposition was ever recorded for
it. "NOT DISPOSITIONED" means there is no recorded disposition and no
later text fully answers the concern; any partial fix is noted after it.

### Round 1 — reviewer B (v1): APPROVE WITH CHANGES, 1 blocking

| # | severity | concern | disposition |
|---|---|---|---|
| B1-1 | BLOCKING | G1: the pooled `concat` without `ignore_index` makes `weighted_take`'s `subpool.loc[idx]` return duplicate rows. A 3-pick returned 6 rows, so the negative quota overshoots and records are double-weighted. | **Accepted** (Rounds 1–2 table, "pooled `concat` index discipline"). `ignore_index=True` is mandated in §5. Note: the `generate_negatives.py` deliverable still omits it at v7 (R7 B-7). |
| B1-2 | MAJOR | R1's boundary spot-check can be evaded. Make it structural by deriving `train_labels` from `train_parts`. | **Accepted** (Rounds 1–2 table, "R1 evadable; R5–R7 missing"). Superseded in v7: `build_datasets` is no longer split, and R1 is recorded as not applicable (rev note v6→v7 #14). |
| B1-3 | MAJOR | R5 missing: the assertion pass could mutate the cached frames that `_load_csv` returns (`grouse_data.py:237-241`). | **Accepted** (same row). R5 still binds in v7. |
| B1-4 | MAJOR | The escape flag must cover (a)–(c) as well as (d), or the test plan and CR-0009's baseline cannot run. | **Accepted** (Rounds 1–2 table, "escape flag scoped to (d) only": "single pre-CR mode covering all four"). It then became open item 1, which was ruled "(d) only" (round 3 F). v7 deletes (d) and the escape mode (rev note v6→v7 #12). The table row was never updated, and v7 still contradicts itself (R7 A-8, B-2). |
| B1-5 | MAJOR | §7 "fixed here or explicitly deferred with a bug id" is either/or, not a deliverable. | Addressed in substance (no table row): v3 and v7 carry "Allocate **BUG-0032** for the deferred `sample_background_points` nodata/0 conflation". The record itself was never created (see E-9). |
| B1-6 | MAJOR | R6 (per-region `filter_by_year_gap`) and R7 (train/val augmentation asymmetry) are missing. | **Accepted** (Rounds 1–2 table, "R1 evadable; R5–R7 missing"). R6 and R7 are "not applicable" in v7 (rev note v6→v7 #14). |
| B1-7 | LOW | G3: name the pass that owns block-id/split, and record that the global val-block fraction moves (per-region 0.205/0.214/0.213 → global 0.190). | NOT DISPOSITIONED. v7 §5 still reads "Which pass owns the block-id/split step … must be named". The 0.190 is recorded. |
| B1-8 | LOW | I5's "today" set is unpinned, and its "6" does not reproduce (jitter defaults to 0). | Addressed in v2 ("Corrections to v1", I5 bullet). |
| B1-9 | LOW | The availability clip (§2) must use the same pinned polygon source and predicate as `verify_partition()`. | NOT DISPOSITIONED. |
| B1-10 | LOW | § Known exceptions should recommend a disposition. "Drop" is the cheapest option. | Addressed by the open-item-2 ruling recorded in v4+ § Review: DROP, with count and coordinates recorded in I9's output. |
| B1-11 | LOW (positive) | Deleting the per-region `PATH_TEMPLATES` entry makes `legacy/gen_negs.py` raise. Say so. | n/a (positive finding, no change requested). Not recorded. |
| B1-12 | unrated | G4: pooled negative thinning still changes the retained set. Do not say "measured effect: none". | **Accepted** in "Corrections to v1" (third bullet). NOT applied to the body: v7 §5 still says "Measured effect today: none" (Formal A C6, R7 B-7). |
| B1-13 | unrated | G5 (i)–(iv): binner refit moves `envelope_id`; keep `mask` boolean; keep the absent-file return path; `MissingDataError` re-raise in both passes. | Addressed in v2/v3 §5 body (all four present at v7). No table row. |
| B1-14 | unrated | (d): record the 6-record exception budget, and couple (d) to the Known-exceptions disposition. | Moot: (d) was replaced (see D1-1) and then deleted in v7. Never dispositioned. |

### Round 1 — reviewer D (v1): REJECT, 1 blocking / 5 major / 6 minor

| # | severity | concern | disposition |
|---|---|---|---|
| D1-1 (E-1) | BLOCKING | Assertion (d) is a tautology given (a): it is 0.000 pp for any draw. A southern-half negative draw passes every gate while support collapses (ME pos-only fraction 0.688). Restore the occupied-block support check at ≤0.15. | **Accepted** (Rounds 1–2 table, "(d) is a tautology given (a)"). Replaced, then withdrawn; OBS in v4; deleted as an assertion in v7 (rev note v6→v7 #12). |
| D1-2 (E-2) | MAJOR | The `--min-spacing-m` / `--block-size-m` CLI flags are a second source of truth. A 60 m thin passes I6. Add a manifest equality check, or remove the flags. | Addressed in v2 (rev note v1→v2 #6, "a parameter manifest"), which became I12. Removing the flags was never decided ("the cheaper equivalent", v7 l.840). Still open as R7 B-11. |
| D1-3 (E-3) | MAJOR | Per-region validation fraction is ungated (NH 16.6–21.9 % across seeds). | Addressed in v2 (rev note v1→v2 #6). It was a hard ±2 pp gate in v3 and deleted as a gate in v4 (rev note v3→v4 #1); I7 is now OBS. |
| D1-4 (E-4) | MAJOR | `verify_partition()` has no call site for the negative class. | **Accepted** (Rounds 1–2 table). Added in §5. Still missing from the `generate_negatives.py` deliverable at v7 (R7 B-7). |
| D1-5 (E-5) | MAJOR | NH box: 721 NH candidates have no full window, so I5 can fail on a rebuilt draw. Drop windowless candidates before sampling. | **Accepted** (Rounds 1–2 table, "NH box deferred but not optional"). Stage and count later disputed (Formal A C7; R7 A-14). |
| D1-6 (E-6) | MAJOR | Three real `BOXES` importers (`predict.py:91`, `download_treemap.py:110`, `download_tcc_nlcd.py:73`) are missing from the consumer list and the import-smoke gate. | Addressed in v2. Round-2 F saw it fixed mid-review ("sixteen files"). No table row. R7 B-19 counts 18 consumers plus a missing `tune_bins.py`. |
| D1-7 (E-7) | LOW | I1 hard-codes `30` instead of `MIN_SPACING_M`. | Addressed (v7 I1 uses `regions.MIN_SPACING_M`). No table row. |
| D1-8 (E-8) | LOW | I5's jitter value is unspecified. | Partly addressed: the v7 I5 row names the default of 0 and says "name the value the rebuild uses". The value is not pinned (R7 B-12). No table row. |
| D1-9 (E-9) | LOW | §2's availability fix is ungated. | Addressed: I13 added as OBS (v2). No table row. |
| D1-10 (E-10) | LOW | The test plan omits `inv_leakage.py` section 3. | Addressed: deliverable "Re-run `inv_leakage.py` including section 3 … recorded as numbers". No table row. |
| D1-11 (E-11) | LOW | Nothing ties the recorded `block_id` to the recomputed one. | Addressed in v2 (rev note v1→v2 #6), which became I11. |
| D1-12 (E-12) | LOW | `prepare_training_data.BLOCK_SIZE_M_DEFAULT` is not stated to be removed. | Addressed: v7 §1 and a deliverable remove it. No table row. |
| D1-13 | unrated | I6 input set undefined; I9 names no predicate, source or negative call site. | Addressed: the v7 I6 and I9 rows state the recipe, predicate and source. No table row. |
| D1-14 | unrated | Residual: no pooled negative count row, so a matched shrink of both classes passes. | Partly addressed: I8 became an exact predicate in v4, and the SUP rows were added in v7. Never dispositioned. |
| D1-15 | unrated | Slip: the `MIN_VALID_FRAC` check is at `:444`, not `:439`. | **Accepted** in "Corrections to v1". NOT applied: v7 §2 and the deliverables still say `:439` (Formal C C10, R7 B-19). |

### Round 2 — reviewer F (v1 → v2 mid-review): REJECT, 4 blocking

F's report states that the file changed twice while it was working, and
that its findings are against the on-disk v2 as of 04:52.

| # | severity | concern | disposition |
|---|---|---|---|
| F2-C1 | BLOCKING | Break 1: drop the shuffle in `assign_spatial_blocks`. Val lands on the 236 densest blocks, every I1–I13 row stays green, and the result is seed-invariant. | **Accepted** (Rounds 1–2 table, "acceptance set broken (dropped shuffle)"): I14 and I15 added. |
| F2-C2 | BLOCKING | Break 2: the rescaled southern-sixth attack passes (d)/I10 ≤0.15. The 5-sample "fair max" is not a bound. | **Accepted** (Rounds 1–2 table, "acceptance set broken (rescaled (d) attack)"). Threshold withdrawn; I10 is OBS from v4. |
| F2-C3 | BLOCKING | §1.3/§1.4: § Review says "Not yet reviewed" despite two verdicts, and no concern has a disposition. | **Accepted** (Rounds 1–2 table, "§1.3/§1.4 unsatisfied — this table"). The same defect recurred for rounds 3–6 (Formal A §6, Formal C C6, R7 A-3/B-1). |
| F2-C4 | BLOCKING | The deliverables checklist omits v2's requirements and cannot be executed in order: the deletion precedes the backup. | **Accepted** (Rounds 1–2 table, "deliverables not executable in order — backup moved first"). The deletion is now gated on the backup. The backup itself is still not first (E-21, R7 A-16/B-20). |
| F2-C5 | MAJOR | I12's inputs are undefined: seed and val fraction are not `regions.py` constants. Remove the CLI flags. | NOT DISPOSITIONED. The v7 I12 row still says "each equal to its `regions.py` constant", and the §1 list has no seed or val-fraction constant. |
| F2-C6 | MAJOR | I7, I10 and I13 are not pass/fail. Split the table into GATE and OBS. | Addressed in v5 (Formal A: "§ Acceptance has a GATE/OBS column"); v7 has a `kind` column. |
| F2-C7 | MAJOR | A blanket pre-CR mode weakens BUG-0027 enforcement. Keep (a)–(c) unconditional. | Became open item 1. Ruled "(d) only" by F in round 3, recorded in v4+ § Review. Superseded by v7's deletion of (d). |
| F2-C8 | MAJOR | There are two different PA-0020 texts, and the verbatim text is not in the CR. The `coord_uncertainty_m` justification is inert. The rule should require a support comparison at receptive-field scale. | Partly **Accepted** (Rounds 1–2 table, "PA-0020's `coord_uncertainty_m` example is inert"). The verbatim text and the scale requirement: NOT DISPOSITIONED. The inert example is still in the v7 deliverable (F3-D6, R7 B-7). |
| F2-C9 | MAJOR | The Impact chain yields 6,508, not 6,230, and NH is 1,079, not 1,116. | **Accepted** (Rounds 1–2 table, "Impact's 6,230 derivation yields 6,508"). Folded into Impact by v7. |
| F2-C10 | MAJOR | `generate_negatives.py --regions` has no write-guard. | NOT DISPOSITIONED. Still open (R7 A-15, B-10). |
| F2-C11 | LOW | I11 is sensitive to the PROJ version (3 records within 1 m of a block edge). | Addressed in v4 ("PROJ exposure is ~2.7 m" in the I14 section; the manifest records PROJ and pyproj versions). |
| F2-C12 | LOW | `verify_partition()` cannot detect marine records. "Relabel to the polygon" is unavailable for 5 of 6. | The relabel part is recorded in ruling 2. The coastal-water caveat is NOT DISPOSITIONED. |
| F2-C13 | LOW | Pooled thinning is 3× slower (198 s), and the cost is unstated. | NOT DISPOSITIONED. |
| F2-C14 | LOW | The "today" column mixes pipeline generations. | **Accepted** in "Corrections to v2" (last bullet). |
| F2-C15 | LOW | `scripts_backup/` is excused for the wrong reason (relative paths are the real reason). | NOT DISPOSITIONED. v7 Out of scope is unchanged. |
| F2-C16 | LOW | "Definitional, not evidential" is misattributed: both classes carry GBIF `stateProvince`. | NOT DISPOSITIONED. v7 §1 is unchanged. |
| F2-S | unrated | Standalone gaps S1–S10: BUG-0029 path, `clip_to_region` "before", 6,230 derivation, "723 blocks", undefined terms, PA-0019 gap, PA-0020 text, 35,792 denominator, I2 readings, content announced but absent. | S3, S4 and S8 are addressed in "Corrections to v2". The others are NOT DISPOSITIONED. |
| F2-N | unrated | Number corrections: 35,792→35,678; 30–65 m→30–79 m; `:253-315`→`:238-317`; `:141`→`:143`; "723" withdrawn; I7 today 20.01 %; `:302` should be `CSV_KEEP :89-90`; 0.190 is a post-CR value shown as today; "~65 %" is really 61.9 %; NH box 0.0569 %, not 0.0665 %. | The first five are accepted in "Corrections to v2". v7 l.840 still says "≈30–65 m". The `:302`, 0.190/~65 % and 0.0665 % corrections are NOT DISPOSITIONED; v7 §1 and §5 still carry `:302`, 0.190 and ~65 % (R7 A-14). |

### Round 3 — reviewer F (v3): REJECT, 4 blocking

F confirmed that I14 and I15 close round-2 Break 1. It also ruled on the
two open items, and v4+ § Review records both rulings as "RULED, by the
reviewer who raised them".

| # | severity | concern | disposition |
|---|---|---|---|
| F3-D1 | BLOCKING | Break 3: an eastern-half, occupancy-matched val draw passes every gate. ME val median longitude shifts 0.986°, and the longitude KS goes 0.035→0.277. Add I16 (val/train KS). | Addressed in v4: Moran's I location gate (rev note v3→v4 #3). F confirmed "Break 3 closed" in round 4. |
| F3-D2 | BLOCKING | I15's 1 pp gate rejects 6 % of correct pipelines. Use 2 pp. | Addressed in v4: I15 ≤2.5 (v7 I15 row, "v3's 1 pp false-fails 3.75 %"). |
| F3-D3 | BLOCKING | I7's new hard ±2 pp gate rejects 40 %. Use p99 ≈5 pp, or stratify. | Addressed in v4: I7b deleted as a gate (rev note v3→v4 #1). F withdrew its own ±2 pp recommendation in round 4. |
| F3-D4 | BLOCKING | I14(i) is not achievable from the manifest: 6 region orders give 6 val sets, and I6 varies from 6,230 to 6,232. | Addressed in v4: hash-derived ordering and an extended manifest (rev note v3→v4 #5; v7 "What I14 is actually worth"). |
| F3-D5 | MAJOR | 9 of 14 dispositions are prose-only or contradicted, 1 (`TIGER_YEAR`) is false, and the GATE/OBS column claimed in the text is absent. Fold the appendix into the body and fix the header. | NOT DISPOSITIONED. Claimed fixed in v4 (rev note v3→v4 #8). F found 9 further contradictions in v4. `TIGER_YEAR` is still absent from the `regions.py` deliverable at v7 (R7 B-7). The header was fixed only in v7. |
| F3-D6 | MAJOR | The PA-0020 deliverable still cites the `coord_uncertainty_m` example the CR itself withdrew. | NOT DISPOSITIONED. Still present at v7 (R7 B-7). |
| F3-D7 | LOW | I14(i) is satisfied by construction; label it, not as a correctness gate. | Addressed in v4: I14 demoted to a provenance/canonical-form gate (rev note v3→v4 #4). |
| F3-D8 | LOW | PA-0021 has no enforcement hook. Name the sweep: re-audit the CR-0007/0008/0009 acceptance tables against PA-0021(c). | NOT DISPOSITIONED. |
| F3-R1 | ruling | Open item 1: the escape mode covers (d) only. As a fallback, a per-assertion allowlist with names recorded in every artifact. | Recorded in v4+ § Review ("Both open items are now RULED"). The Rounds 1–2 table row was not updated (R7 B-2). |
| F3-R2 | ruling | Open item 2: disposition before approval, by dropping the records and recording them in I9. | Recorded in v4+ § Review. Deliverable ticked `[x]`. The Known-exceptions section still reads "open decision" (Formal C C12, R7 A-13). |

### Round 3 — reviewer E, QMS lane (v3): APPROVE WITH CHANGES on CR-0007

Only concerns that bind CR-0007 are listed. E's other items are about
CR-0008/0009 only: #2, #5–#7, #14, #15, and ordering defect 4 (cache purge).

| # | severity | concern | disposition |
|---|---|---|---|
| E-1 | BLOCKING (programme) | All CRs are untracked, so prior revisions are unrecoverable and version labels are wrong. Commit, fix the headers, and state the §2.4 gap for BUG-0033. | NOT DISPOSITIONED. Partly acted on: the tree was committed in `1445ccd` at 05:23, 5 minutes after the report, and the header was corrected in v7. The statement of the §2.4 gap was never made. |
| E-3 | BLOCKING | BUG-0033 bundles two root causes (falsifiability; calibration) plus an orphan rule (d). Split it. | NOT DISPOSITIONED. The v7 BUG-0033 deliverable still lists all five shapes under one bug. (The id BUG-0034 that E proposed for the calibration half was later used for the year-asymmetry defect.) |
| E-4 | BLOCKING | PA-0021 is filed as extending PA-0018 (wrong layer). It should stand alone, with a back-reference from PA-0018. | NOT DISPOSITIONED. Addressed differently in v7: the lineage now extends **PA-0016** (rev note v6→v7 #17). |
| E-9 | BLOCKING | BUG-0032 is "allocated" but has no document or `BUG_LOG` row. | NOT DISPOSITIONED. v7 still says "Allocate BUG-0032". |
| E-10 | MAJOR | Unfiled defect: positives acquired from 2016, negatives from 2020 (23.6 % of positives are pre-2020). | Addressed in v4: BUG-0034 recorded (rev note v3→v4 #7). Fixed in v5, descoped in v6 (rev notes v4→v5, v5→v6 #1). |
| E-11 | MAJOR | PA-0020's broadening has no live instance after the withdrawal. Substitute the year asymmetry. | NOT DISPOSITIONED. The v7 PA-0020 deliverable still cites the inert example. |
| E-12 | MAJOR | The "before" column is unmeasurable as planned. `analyze_grouse.py` must run twice (pre-change and post-change), and CR-0009 baselines need sequencing. | NOT DISPOSITIONED. v7 has a single "Run … in that order" deliverable after the code changes. |
| E-13 | MAJOR | The review deliverable is last (§1.5). | NOT DISPOSITIONED. It is still last at v7. |
| E-16 | MAJOR | The escape-mode hole: if kept, the escaped mode must refuse to write artifacts, and CR-0009 must cite that. | NOT DISPOSITIONED. v7 deleted the escape mode but still plumbs `gate_obs_only` (R7 A-8, B-2). |
| E-17 | MAJOR | `PREVENTIVE_ACTIONS.md` and `BUG_LOG.md` have three writers and no owner, and BUG_LOG is out of discovery order. | NOT DISPOSITIONED. v7 re-points PA-0021/BUG-0033 to an unowned "bookkeeping batch" (rev note v6→v7 #17; R7 B-8). |
| E-18 | MAJOR | The PA-0021(c) sweep is unbounded. 19 hard thresholds in live code are enumerable. | NOT DISPOSITIONED. |
| E-PAa | unrated | PA-0021(a): the constructed pipeline must be built by someone other than the author and recorded for re-run. | NOT DISPOSITIONED. v7 clause (a) is unchanged. |
| E-PAb | unrated | PA-0021(b): restate as an obligation. | Addressed in v7 (clause (b) rewritten as "must contain at least one gate constraining what the change set MAY do"). |
| E-PAc | unrated | PA-0021(c): exempt exact-zero predicates. | Addressed in v7 (clause (c): "Exact predicates are exempt"). |
| E-19 | LOW | `DRAFT_BUG-0028` has no promotion deliverable in any CR. | NOT DISPOSITIONED. BUG-0028 is still out of scope at v7. |
| E-20 | LOW | The two-stage bug-closure hand-off (fixed in CR-0007, closed in CR-0009) is undeclared. | NOT DISPOSITIONED. |
| E-21 | LOW | The backup is annotated "FIRST:" but sits 11th. | NOT DISPOSITIONED. It is 14th/16th at v7 (R7 A-16, B-20). |
| E-22 | LOW | A struck-through deliverable is left unchecked `[ ]`. | NOT DISPOSITIONED. Still present at v7. |
| E-23 | LOW | PA-0021(d) has two live instances inside CR-0007: I7 and I13. | Addressed: both are labelled OBS by v7. |
| E-R1 | ruling | Open item 1: cover all four only if the escaped mode structurally refuses to write artifacts; otherwise (d) only. | NOT DISPOSITIONED. v7 records only F's ruling, and E's differing position is absent. |
| E-R2 | ruling | Open item 2: before approval. | Consistent with the recorded ruling. |

### Round 3 — reviewer H (v3): REJECT, 3 blocking (CR-0007 section)

| # | severity | concern | disposition |
|---|---|---|---|
| C7-1 | BLOCKING | Break: a draw stratified by (state, count) that prefers blocks with a cross-block neighbour passes I1–I15 (both halves of I14). Val positives within 1.92 km of a train positive go 35.98 %→55.96 %. | Addressed in v4: I18 added (median val→nearest-train distance). The attack is cited in v7 "What I14 is actually worth (v4)". |
| C7-2 | BLOCKING | I14b has no power: PASS at Jaccard 0.992. Use a quantitative Jaccard envelope. | NOT DISPOSITIONED. I14 was demoted in v4 (rev note v3→v4 #4), but the v7 I14 row still reads "val block set differs between seeds", with no envelope. |
| C7-3 | BLOCKING | No invariant measures train↔val distance. Promote `inv_leakage.py` §3 to a gate. | Addressed in v4 (I18). The `inv_leakage.py` §3 deliverable is still "recorded as numbers". |
| C7-4 | MAJOR | I7/I8 are tautologies on the negative class. Add a negative-side absolute count gate against pool supply. | Addressed in v7: I7(neg) recorded as zero-information (rev note v6→v7 #10); supply rows SUP0/SUP-O/SUP-R (rev note #5). |
| C7-5 | MAJOR | No gate on duplicated negative records within a split. | NOT DISPOSITIONED. Re-raised as R7 A-5. |
| C7-6 | MAJOR | The two open items are delegated. H's positions: escape covering all four only with write-refusal; drop 5 no-polygon records and **relabel** 1, in an audited list. | Rulings recorded (F's). H's differing positions are NOT DISPOSITIONED. |
| C7-7 | MAJOR | Assertion (d) has no threshold, so "all four hard-fail" cannot be demonstrated. | Addressed: (d) became OBS in v4 and was deleted in v7 (rev note v6→v7 #12). Residual text remains (R7 A-9). |
| C7-8 | LOW | I5 is "unfailable by construction" only for negatives. Add a positive-side drop or assertion. | NOT DISPOSITIONED. |
| C7-9 | LOW | The manifest has no integrity requirement. Use a sidecar JSON with SHA-256. | NOT DISPOSITIONED. Partly addressed in v4: the manifest records input-file and record-set digests (I14 section). |
| C7-10 | LOW | Assertion population under `train.py --regions <subset>` is unspecified. | Addressed in v7 (rev note v6→v7 #13; `GATE_REGIONS` deliverable). |
| C7-11 | LOW | I12 is an observation dressed as a gate. Make flag removal a deliverable. | NOT DISPOSITIONED (R7 B-11). |
| C7-12 | LOW | PA-0019 is derived but filed by no CR, leaving a hole in the register. | NOT DISPOSITIONED. |
| H-X1 | unrated | Contradictions: Impact still "8,422 → 6,702 → ≈6,230" and "1,116". | Addressed by v7 (Impact now states 6,230 via I6's recipe and NH 1,079). |
| H-X7 | unrated | CR-0007 backs up `old_road_dist/` as a CR-0009 input, but CR-0009 item 2 re-points away from it. | NOT DISPOSITIONED. v7 still backs it up as "inputs to CR-0009's acceptance". |
| H-Q | unrated | §2: BUG-0028 is a review-found defect with no doc or owning CR. | NOT DISPOSITIONED. |
| H-I14a | unrated | Make I14a non-tautological with a per-parameter sensitivity run. | NOT DISPOSITIONED. |

### Round 4 — reviewer F, expedited (v4): APPROVE WITH CHANGES

F answered four questions. Q1: the three deletions are correct. Q2: Moran
catches the eastern-half attack at z 18.5–29.6, so Break 3 is closed.
Neither required a change.

| # | severity | concern | disposition |
|---|---|---|---|
| F4-Q3 | BLOCKING ("blocking, mechanical") | v4 contradicts itself in 9 places. The acceptance table (l.544-556) predates v4 (I6 ±2 %, I8 ±0.02, I10 ≤0.15; no Moran/ks_feat/separation/I14/I15 rows; no GATE/OBS column). v3's superseded block (l.668-713) still reads as normative ("either one alone kills it", I15 1 pp, I7 ±2 pp, the I10 replacement). l.567 says "30–65 m". §6 l.391 says "all four". | NOT DISPOSITIONED. Partly addressed later: the table was rebuilt only in v7 (the I14–I19 rows were spliced into § Review in v5/v6, per Formal A C5 and Formal C C8). The v3 block is gone by v7. "≈30–65 m" is still at v7 l.840. §6 (d) residue remains (R7 A-9, B-7). |
| F4-Q4 | unrated | The two rulings are reported but not in the document: § Review still says "Open items", and the deliverable says "Blocks implementation". | Addressed in v5+ ("Both open items are now RULED"). The Rounds 1–2 table's escape row was never updated. |
| F4-N1 | MAJOR | `frac(>1920 m) ≤ 0.55` is the only support gate, with ~4 % margin on each side. Re-derive it on the rebuilt negatives and mark it provisional. | Addressed across v5–v7: provisional ≤0.55 (rev note v4→v5); per-region 0.64 (v5→v6 #2); I19′ plus the "Re-measure I19′'s twelve cells on the rebuilt negatives" deliverable (v6→v7 #2). |
| F4-N2 | LOW | Gate calibration must be conditional on BUG-0034's disposition. | Addressed: BUG-0034 descoped in v6, and v7 has a hand-off deliverable listing the rows to re-derive. |

### Round 5 — Formal A (v5): REJECT, 4 blocking

| # | severity | concern | disposition |
|---|---|---|---|
| FA-C1 | BLOCKING | Break 1: pooled I19 is defeated by an NH-only negative skew. 75 % of attack draws fall below the fair max, and no operating point works. | Addressed in v6: I19 made per-region (rev note v5→v6 #2; v7 § Review "Break 1"). Broken again by Formal C 10A. |
| FA-C2 | BLOCKING | Break 2: the geography of the negative split is ungated. A block-ordered replacement for the md5 hash gives +38.4 km val/train negative displacement with every gate green. | Addressed in v6: I16b added and every row names its record set (rev note v5→v6 #3–#4; v7 § Review "Break 2"). |
| FA-C3 | BLOCKING | The v5 BUG-0034 fix invalidates I6 (4,809 vs 6,230 ± 10) and I19 (100 % false-fail) while the table carries v4 values. NH drops to 828. | Addressed in v6: BUG-0034 descoped (rev note v5→v6 #1). |
| FA-C4 | BLOCKING | §6 specifies (d) at ≤0.15 with an escape, while the table says I10/(d) is OBS. | NOT DISPOSITIONED. Claimed fixed in v7 (rev note v6→v7 #12), but the §6 (d) specification and "All four hard-fail" remain at v7 (R7 A-9, B-7). |
| FA-C5 | MAJOR | Rows I14–I19 are spliced into § Review and absent from the test-plan table. The deliverable says "I1–I13". | Addressed in v7 (table rebuilt; the deliverable says "I1–I19 (incl. I16b)" and explains the splice). |
| FA-C6 | MAJOR | §5's "Measured effect today: none" for negative thinning is wrong: the retained set differs by 2,067 coordinates. | NOT DISPOSITIONED. v7 §5 is unchanged (R7 B-7). |
| FA-C7 | MAJOR | I5's "NH 721" is quoted at the raw stage. At the sampling stage it is NH 5 / ME 1 / VT 0. | NOT DISPOSITIONED. v7 I5 and §5 still say 721 (R7 A-14: 3 of 5,220). |
| FA-C8 | MAJOR | I18 and I19 are min/max envelopes, contrary to PA-0021(c). I18 false-fails 1/400. | NOT DISPOSITIONED. Partly addressed: I19′ uses μ+Zσ per cell (v7). I18 is still the `[2.33, 2.75]` band (R7 A-1, B-16). |
| FA-C9 | MAJOR | I15's threshold and I16's null depend on an undecided stratification. | NOT DISPOSITIONED (R7 B-11). |
| FA-C10 | MAJOR | I17 needs a per-record feature extractor that no deliverable builds (CRS pitfall; CR-0008 coupling). | Addressed in v7: extractor deliverable added and I17 demoted to OBS (rev note v6→v7 #8). The CR-0008 coupling is not stated. |
| FA-C11 | LOW | Stale v3 text in the BUG-0034 section: the load/construct split, and `:253-315`. | NOT DISPOSITIONED. Partly addressed: v7 has no split (rev note #14) and fixes the cite (#16), but §6 still reads "the pre-filter placement stands, and with it the load/construct split" (R7 A-9). |
| FA-C12 | LOW | Status line says v4; the body says v5. | Addressed in v7 (status note). |
| FA-C13 | LOW | Negative sample weights are ungated. | Addressed in v7 by the composition rows (C12/C14 on weight; rev note v6→v7 #4). |
| FA-Q1 | unrated (§1.3/§1.4) | Rounds 3 and 4 have no verdicts or dispositions, and author sign-off is withheld. | NOT DISPOSITIONED. v7 acknowledges the gap; this log is the reconstruction. |
| FA-Q2 | unrated (§2) | No deliverable promotes `DRAFT_BUG-0034`. | Addressed by v6/v7 (promotion deliverable present). |
| FA-Q3 | unrated (§2/§3.1) | BUG-0031/0032/0033 and PA-0019/0020/0021 do not exist but are cited as governing. | NOT DISPOSITIONED. Re-pointed to an unowned pre-CR batch in v7 (R7 B-8). |
| FA-Q4 | unrated (§3.4) | The BUG-0034 §8 per-class drop-rate assert has no deliverable. | NOT DISPOSITIONED. |
| FA-Q5 | unrated (§3.5) | The BUG-0034 mechanism-scoped sweep (e.g. `predict.py:164`) has no deliverable. | NOT DISPOSITIONED. |
| FA-Q6 | unrated (§1.1) | One deliverable is pre-checked `[x]`. | NOT DISPOSITIONED. Still `[x]` at v7 (R7 A-13). |

### Round 6 — Formal C (v6): REJECT, 10 blocking

| # | severity | concern | disposition |
|---|---|---|---|
| FC-C1 | BLOCKING | Break 10A: skew ME and VT under the region-max I19, leaving 1,116 positives stranded with a median distance of 59.6 km. Break 10B: a local feature-extremum split of positive-free blocks (Moran negative, I17 positives-only). Break 10C: I8 exact is blind to a NonVeg top-up (87.7 % water/urban). | Addressed in v7: I19′ per-cell nulls (rev note v6→v7 #2), composition axis C1–C17 (#4), supply axis (#5), two-sided I16b (#7). |
| FC-C2 | BLOCKING | I19's calibration does not reproduce on the real sampler: fair max 0.6172, 3.7 % headroom, inverted under a uniform draw. | Addressed in v7: faithful harness `inv_formalC_pool2`/`lib`; I19 withdrawn for I19′ (rev note v6→v7 preamble and #2). |
| FC-C3 | BLOCKING | I16b's constants are pool artifacts (9,093/5,232, not 9,482/5,621), and its record set is ambiguous (z 70.4 vs 24.7). | Addressed in v7 (rev note v6→v7 #6–#7; two readings with two call sites). Frozen constants remain in the I16b row (R7 A-10, B-4). |
| FC-C4 | BLOCKING | I14–I19 have no implementing call site, and the deliverable says I1–I13. | NOT DISPOSITIONED. Partly addressed in v7 (`acceptance.py`, call sites listed), but the call sites contradict each other (R7 B-3). |
| FC-C5 | BLOCKING | The BUG-0034 reversal is incomplete: five pieces of v5 residue in §6, and `DRAFT_BUG-0034` still says "DECIDED … fixed in CR-0007". | NOT DISPOSITIONED. v7 still has "I15, I16, I18, I19 — **move** … must be re-derived" (l.515) and the load/construct-split text. `DRAFT_BUG-0034` (untracked working copy) still reads "DECIDED (2026-09-30): fixed in CR-0007". |
| FC-C6 | BLOCKING | §1.3/§1.4 fail again: rounds 3–6 are unrecorded, and sign-off is withheld. | NOT DISPOSITIONED. v7 adds a gap table but gets the rounds wrong (see Reconstruction notes). |
| FC-C7 | BLOCKING | §3.1/§3.2: the CR cites PA-0020/0021 and BUG-0033 as governing, but none of them is filed. | NOT DISPOSITIONED. v7 re-points them to a "bookkeeping batch landing before this CR" (rev note v6→v7 #17), which has no owner (R7 B-8). |
| FC-C8 | BLOCKING | The document is physically corrupted: gate rows are wedged inside § Review, the header says v4, and there are no v2→v3/v4→v5/v5→v6 notes. | Addressed in v7: the table is rebuilt, the header corrected, and the notes added. |
| FC-C9 | BLOCKING | §6 and I10 contradict each other on (d). | NOT DISPOSITIONED. Claimed fixed in v7 (rev note #12); the residue remains (R7 A-9, B-7). |
| FC-C10 | BLOCKING | `:439` vs `:444` is recorded but not applied. The `build_datasets` span is wrong: it is `:238-336`, not `:238-317`. | NOT DISPOSITIONED. `:439` is still in v7 §2 and the deliverables. v7 rev note #16 asserts `:238-317`, which conflicts with FC's `:238-336`; R7 reviewers A and B both accepted `:238-317`. |
| FC-C11 | MAJOR | I15, I18 and I19 are set from extrema, contrary to PA-0021(c). | NOT DISPOSITIONED. I19′ is fixed in v7; I15 and I18 are not (R7 B-16). |
| FC-C12 | MAJOR | The Known-exceptions section is still open although the deliverable is `[x]` DROP. | NOT DISPOSITIONED (R7 A-13). |
| FC-C13 | MAJOR | No gate on the negatives' NonVeg share or the beyond-cap top-up. | Addressed in v7 (C-rows; the "Enforce C2 as a raise" deliverable). |
| FC-C14 | LOW | A pre-checked `[x]` and a struck `[ ]` in the deliverables. | NOT DISPOSITIONED. |
| FC-C15 | LOW | BUG-0029 is still a root DRAFT; BUG-0027's doc says "OPEN, unconfirmed". | NOT DISPOSITIONED. A promotion deliverable exists, but the BUG-0027 status part is not addressed. |

### Round 7 — reviewer A, formal (v7): REJECT, 3 blocking

v8 does not exist, so nothing from this round is dispositioned in the CR.
The items are tracked in `docs/quality/CR-0007-0008-OPEN-ISSUES.md` as
A-1…A-16.

| # | severity | concern | disposition |
|---|---|---|---|
| A-1 | BLOCKING | The per-region I18 is inverted: it false-fails ~52 % of correct runs and is blind to the BUG-0027 leak. Revert to pooled. | NOT DISPOSITIONED |
| A-2 | BLOCKING | No gate on the 300 m exclusion buffer. Removing it puts ~2,053 of 6,230 negatives within 300 m of grouse, with all gates green. I19′ is one-sided. | NOT DISPOSITIONED |
| A-3 | BLOCKING | Rounds 3–5 verdicts and dispositions are unrecorded (§1.3/§1.4). | NOT DISPOSITIONED. This log reconstructs the verdicts, but dispositions are still owed. |
| A-4 | MAJOR | I19′ val cells are calibrated on the wrong null, giving 6–11σ of slack. Stated limit 3 is 4× too small. | NOT DISPOSITIONED |
| A-5 | MAJOR | Duplicate negatives within a split are ungated. | NOT DISPOSITIONED. Also raised as C7-5 in round 3. |
| A-6 | MAJOR | C5–C17 thresholds rest on a footing this CR changes, and no deliverable re-derives them. | NOT DISPOSITIONED |
| A-7 | MAJOR | C12–C16 cannot be reached from the persisted pool, and C5–C8/C13 have no data path (PA-0021(e)). | NOT DISPOSITIONED |
| A-8 | MAJOR | The escape mode is deleted, but this CR and CR-0009 still depend on it. | NOT DISPOSITIONED. The user decided "baselines first, no escape mode" (OPEN-ISSUES), but this is not yet in the CR. |
| A-9 | MEDIUM | §6 contradicts itself: the load/construct split, (d) ≤0.15, "All four hard-fail", "Not optional detail". | NOT DISPOSITIONED |
| A-10 | MEDIUM | I16b claims no frozen constant but gates on frozen values. | NOT DISPOSITIONED |
| A-11 | MEDIUM | The VT val NonVeg "already over cap" claim is false. | NOT DISPOSITIONED |
| A-12 | MEDIUM | SUP-R headroom is ~0, and "0/1,600 draws" is vacuous. SUP-O has 1 of headroom. | NOT DISPOSITIONED |
| A-13 | MEDIUM | Known exceptions: ticked in Deliverables, open in the body. | NOT DISPOSITIONED |
| A-14 | LOW | Wrong citations and stale numbers (`:302`, `:143`, `:160`, `:444`, `:443-444`, "723", year rule, NH 3 of 5,220). | NOT DISPOSITIONED |
| A-15 | LOW | `GATE_REGIONS` is read from the artifact under test; `generate_negatives --regions` is unguarded. | NOT DISPOSITIONED |
| A-16 | LOW | Deliverables are not in execution order. | NOT DISPOSITIONED |

### Round 7 — reviewer B, implementation and §1 (v7): REJECT, 2 blocking

Tracked as B-1…B-21 in `docs/quality/CR-0007-0008-OPEN-ISSUES.md`.

| # | severity | concern | disposition |
|---|---|---|---|
| B-1 | BLOCKING | The review history is recoverable, and the CR's own summary of it is wrong ("seven reviews"; a phantom Round-2 implementation row; the v5 REJECT missing). | NOT DISPOSITIONED. This log is the reconstruction step; dispositions and quorum are still owed. |
| B-2 | BLOCKING | Escape-mode contradiction: `gate_obs_only` is undefined, v7 says "Deleted: the escape mode", and CR-0009 depends on it. | NOT DISPOSITIONED. User decision recorded in OPEN-ISSUES ("baselines first, no escape mode"); not yet in the CR. |
| B-3 | MAJOR | Gate call sites contradict each other; SUP rows have no call site. | NOT DISPOSITIONED |
| B-4 | MAJOR | The I16b definition contradicts itself (in-run null vs frozen constants). | NOT DISPOSITIONED |
| B-5 | MAJOR | Re-deriving I19′ nulls on the rebuilt negatives violates PA-0021(e). | NOT DISPOSITIONED |
| B-6 | MAJOR | Nothing tests the implemented gates against the recorded attacks; 11 evidence scripts will break. | NOT DISPOSITIONED |
| B-7 | MAJOR | "Accepted" dispositions never reached the operative text (`TIGER_YEAR`, `ignore_index`, negative `verify_partition`, windowless drop, PA-0020 cite, §5 "none", Known exceptions, §6 (d), the test plan, "Not optional detail"). | NOT DISPOSITIONED |
| B-8 | MAJOR | The bookkeeping preconditions (PA-0020/0021, BUG-0033) have no owner. | NOT DISPOSITIONED |
| B-9 | MEDIUM | Centralising `TIGER_YEAR = 2023` reverts commit a995898 (2025), which changes a generator. | NOT DISPOSITIONED |
| B-10 | MEDIUM | `generate_negatives.py --regions` is unguarded, and partial writes can happen on a gate failure. | NOT DISPOSITIONED. Also raised as F2-C10 in round 2. |
| B-11 | MEDIUM | Adoption decisions left open: hash ordering, `draw_val_blocks`, stratification, flag removal. | NOT DISPOSITIONED. OPEN-ISSUES records a user decision to split CR-0007 into three CRs; the individual rulings are not made. |
| B-12 | MEDIUM | "I5 unfailable by construction" needs a pinned window and year rule. | NOT DISPOSITIONED |
| B-13 | MEDIUM | New paths need `PATH_TEMPLATES` entries (PA-0003). | NOT DISPOSITIONED |
| B-14 | MEDIUM | §2's KDE clip conflicts with PA-0018. | NOT DISPOSITIONED |
| B-15 | MEDIUM | The SUP0 VT/val 0.87 claim appears false. | NOT DISPOSITIONED |
| B-16 | MEDIUM | Family-wise false-fail rate unmeasured; "1.30 × fair max" C rows; C11 lower bound unstated; I15 and I18 violate PA-0021(f). | NOT DISPOSITIONED |
| B-17 | MEDIUM | I6's target cannot be both fixed and unpredictable. | NOT DISPOSITIONED |
| B-18 | MEDIUM | Review-found defects have no BUG ids (`TIGER_YEAR` drift, `STATE_FIPS`/`MIN_SPACING_M` duplicates, `:153`). | NOT DISPOSITIONED |
| B-19 | LOW | Citation and count errors (`:444`, `:143`, `:443-444`, `:302`, consumers 18 plus `tune_bins.py`, 5 guards, backup items, I5 raise point). | NOT DISPOSITIONED |
| B-20 | LOW | Deliverable order: the backup is 16th. | NOT DISPOSITIONED |
| B-21 | LOW | §7 brings geopandas into `train.py`, unstated; "SystemExit becomes reachable" is unsupported. | NOT DISPOSITIONED |
| B-R | unrated | The risk table is missing four risks; the "cannot validate" list needs two more items. | NOT DISPOSITIONED |

## Reconstruction notes

**What was found.** 11 reviews of CR-0007: 2 in round 1, 1 in round 2,
3 in round 3, 1 in round 4, 1 each in rounds 5 and 6, and 2 in round 7.
The nine pre-v7 reviews in the list handed over with this task are all
confirmed, with the same agent ids, times and verdicts. No review of
CR-0007 was missing from it. The only additions are the round-7 pair,
which the list did not cover. Times in the rounds table are turn start →
final report. The handed-over list gave report times only.

**Discrepancies with the CR's own § Review (v7):**
1. **"Seven reviews have been performed on this CR"** (v7 status note) is
   wrong. There were nine before v7, and eleven counting round 7.
2. **Round 2 is mis-recorded.** v7 lists two Round-2 reviews, including an
   "implementation lane — APPROVE WITH CHANGES — 1 (`weighted_take` `.loc`
   overshoot)". No such review exists. Reviewer B reviewed CR-0007 once, on
   v1, and that blocking finding is B's round-1 G1. The Round-1 and
   Round-2 implementation rows are the same review counted twice. Round 2
   had one reviewer, F, whose review started on v1 and finished on v2.
3. **Round 3 had three reviewers (F, E, H), not one "intermediate"
   reviewer.** Their verdicts were REJECT, APPROVE WITH CHANGES and REJECT.
   v7 says "not recorded".
4. **The v5 formal REJECT (Formal A) is missing from the v7 gap table.**
   v7's "Round 5 — formal, fresh — REJECT — breaks 10A/10B/10C" row
   describes **Formal C's review of v6**. That review was the sixth
   round, not the fifth. Formal A's Breaks 1 and 2 appear in v7 only as
   prose ("The two acceptance breaks the formal review found … (v6)"),
   with no verdict row.
5. **The v4 review is recorded as "not recorded".** It was F's expedited
   APPROVE WITH CHANGES.
6. **"Both open items are now RULED, by the reviewer who raised them."**
   This is true of F. But E (round 3) and H (round 3) gave a different
   ruling on item 1: all four assertions, provided the escaped mode
   refuses to write artifacts. H also gave a different Known-exceptions
   disposition: drop 5 and relabel 1, in an audited list. Neither
   position is recorded. Under §1.3 they need a disposition.
7. **The Rounds 1–2 Dispositions table has a row, "`TIGER_YEAR` owned by no
   CR", that matches no CR-0007 round-1/round-2 concern.** None of B, D or
   F raised it on CR-0007. It traces to the CR-0006 reviews (B's CR-0006
   C11/C12). Round 3 F found the "added to §1" disposition false, and R7 B
   finds it still unapplied at v7.
8. **Several "Accepted" rows were never applied to the operative text**
   (B1-1, D1-4, D1-15, F2-C8, B1-12). Round 3 F, round 4 F, Formal A, Formal C
   and R7 B each flagged this separately.

**Counts.** 170 concern rows in total. **100 are marked NOT DISPOSITIONED**:
62 from rounds 1–6 and all 38 from round 7. 17 rows carry a recorded
"Accepted" disposition, all from the CR's Rounds 1–2 table or its
"Corrections to v1/v2". One of the 17, F2-C8, is only partly accepted and
is also counted as NOT DISPOSITIONED. The other 54 rows fall into three
groups: addressed in a later version with no recorded disposition,
rulings that were recorded, and positive or moot findings. Rows marked
"unrated" are review points the reviewer raised without a severity.

**Unrecoverable.**
- **The v1, v2, v4, v5 and v6 texts.** No commit captured them. So "addressed in
  vN" for N ∈ {2, 4, 5, 6} rests on v7's revision notes, on the next
  reviewer's description of the text, and on git's v3 (`1445ccd`). I
  could not check those texts directly. A concern marked addressed in v4
  may have been dropped or re-worded in v5 or v6 and then restored, and
  that cannot be seen.
- **Which exact text round 2 F reviewed.** The file changed twice during
  that review. F's findings are against the 580-line v2 state as of 04:52,
  not the v1 it was sent.
- **Author responses between rounds.** These exist only as the
  coordinator's `SendMessage` prompts, for example the round-3 and round-4
  prompts to F listing what changed. They are author claims, not
  dispositions, and are not treated as dispositions here.
- **Reviewer evidence scripts.** The `inv_review*_*.py` and
  `inv_formal*_*.py` scripts named in the reports are in the repo root,
  untracked; `0f58a9b` committed the A–G set. They were not re-run for
  this log.

## Original § Review (v7)

Copied verbatim from `git show bb170ea:docs/quality/change-requests/CR-0007-record-partition-and-global-split.md`
(v7, lines 1612–1731).

## § Review

### Round 1 (v1) — two independent reviews
| reviewer | verdict | blocking |
|---|---|---|
| implementation lane | APPROVE WITH CHANGES | 1 (pooled `concat` index discipline) |
| acceptance lane | REJECT | 1 (assertion (d) a tautology) |

### Round 2 (v2) — two independent reviews
| reviewer | verdict | blocking |
|---|---|---|
| implementation lane | APPROVE WITH CHANGES | 1 (`weighted_take` `.loc` overshoot) |
| fresh, standalone | **REJECT** | 3 (acceptance set broken twice; §1.3/§1.4 unsatisfied; deliverables not executable in order) |

### Rounds 3–5 — VERDICTS NOT RECORDED (§1.3/§1.4 gap)
| round | reviewer | verdict | blocking | status |
|---|---|---|---|---|
| 3 | intermediate | **not recorded** | — | **must be recovered before approval** |
| 4 | intermediate / expedited | **not recorded** | — | **must be recovered before approval** |
| 5 | **formal, fresh** | **REJECT** | acceptance layer broken (breaks 10A/10B/10C) | mechanism recorded in the header; dispositions outstanding |

Round 5's finding is the one that governs v7. It treated the author's own
calibrations as unverified — correctly, because they were produced with
`inv_fix_breaks.py`, which **approximates** the negative sampler instead
of running the real draw — and then constructed three pipelines that
passed the entire table while producing a defective dataset. The faithful
harness (`inv_formalC_pool2.py` + `inv_formalC_lib.py`) exists because of
that finding, and every v7 threshold is being re-derived on it.

### The two acceptance breaks the formal review found, and how they close (v6)

**Break 1 — I19 was pooled, and a one-region skew hid inside it.** NH
holds 17 % of the pooled positives, so skewing only NH's negatives moved
the pooled statistic barely at all. Measured over 120 seeds, on the
pipeline this CR builds:

```
                      fair                              NH-only attack
POOLED      p50 0.5097  p99 0.5262  max 0.5266   p50 0.5339 ... min 0.5185   <- OVERLAPS
PER-REGION  p50 0.5533  p99 0.5874  max 0.5885   p50 0.6997 ... min 0.6821   <- SEPARATES
```

Pooled, the attack's minimum sits **below** the fair maximum — the same
shape that retired I7b and I10, and the reason v5's stated attack range
(0.574–0.852) was misleading: it was measured only against all-region
attacks. **Per region, fair max 0.5885 against attack min 0.6821** —
16 % clear on both sides of a 0.64 gate. I19 is now a per-region
statistic, maximised across regions, and is no longer provisional.

**Break 2 — nothing gated the geography of the negative split.** 5,621
of 9,482 occupied blocks (59 %) hold no positive, and their split comes
from `split_for_unassigned`'s md5 hash. Replace that hash with any
block-ordered rule — and since global ids are `bx_by`, sorting the id
*is* sorting on x — and validation negatives land tens of km east of
training negatives with **every gate green**.

The root cause was that **I15–I19 never said which record set they run
over**, and the calibration silently fixed it to positives: I16's null
was measured on the 3,861 positive-occupied blocks, so the 5,621
positive-free blocks were outside every gate. Every row now names its
record set, and I16b adds the missing one:

```
Moran's I, fair      positives-only blocks   p50  0.0021  max 0.0220
                     ALL-record blocks       p50 -0.0006  max 0.0159
Moran's I, attack    ALL-record blocks       p50  0.3587  min 0.3409   z = 61.4
```

The attack is invisible to the positives-only reading and **61 sigma**
on the all-record one. Both readings are kept — they answer different
questions — and each carries its own null.

**Also pinned:** the positive-free-block split rule (hash function,
digest size, input string) joins the thinner's in the manifest, since it
is now understood to be a spatial decision rather than a tie-break.


**Dispositions.** Every concern from **Rounds 1 and 2** is dispositioned
below; none dropped. **Rounds 3–5 are not dispositioned at all** — see the
gap table above; that is the §1.3 defect blocking approval, and it is not
closed by this table. v2 recorded a seven-line summary and left `§ Review`
reading "Not yet reviewed" — a §1.3/§1.4 violation in its own right,
and the reason this table exists.

| concern | disposition |
|---|---|
| (d) is a tautology given (a) | **Accepted** — replaced by the occupied-block support check; now withdrawn again pending re-calibration (see I10). |
| pooled `concat` index discipline | **Accepted** — `ignore_index=True` mandated in §5, with the 3-pick→6-row demonstration. |
| `verify_partition()` has no negative call site | **Accepted** — added in §5. |
| NH box deferred but not optional | **Accepted** — resolved by dropping windowless candidates before sampling. |
| R1 evadable; R5–R7 missing | **Accepted** — R1 made structural; R5 (cached-frame mutation), R6, R7 added. |
| escape flag scoped to (d) only | **Accepted** — single pre-CR mode covering all four, recorded in any artifact produced. Note a reviewer argues (a)–(c) should stay unconditional; **see open item below.** |
| acceptance set broken (dropped shuffle) | **Accepted** — I14/I15 added. |
| acceptance set broken (rescaled (d) attack) | **Accepted** — I10's threshold withdrawn; replacement specified at receptive-field scale. |
| §1.3/§1.4 unsatisfied | **Accepted** — this table. |
| deliverables not executable in order | **Accepted** — backup moved first. |
| Impact's 6,230 derivation yields 6,508 | **Accepted** — see Corrections. |
| PA-0020's `coord_uncertainty_m` example is inert | **Accepted** — see Corrections. |
| `TIGER_YEAR` owned by no CR | **Accepted** — added to §1's centralisation list. |
| A6/`verify_partition` disposition should block approval, not implementation | **Open** — see below. |

**Both open items are now RULED, by the reviewer who raised them:**
1. **The pre-CR escape mode covers (d) only.** (a)–(c) stay
   unconditional. The premise that the test plan needs a blanket mode is
   false and was falsified directly: every "today" figure in the
   acceptance table was produced by reading the CSVs, with no `train.py`,
   `calibrate.py` or `bench_pipeline.py` involvement, and (a)/(b)/(c)
   touch no polygon at all. The polygon path measures 1.19 s, so cost is
   not the constraint either.
2. **The `verify_partition()` exceptions are dispositioned before
   APPROVAL, not before implementation.** I9's `required` cell otherwise
   resolves to a rule that does not exist, which is not reviewable.
   **Disposition: drop the affected records and record the count and
   coordinates in I9's output** — not an audited exception list, which
   PA-0021(b) argues against as a blacklist that grows silently. Cost:
   6 of 35,678 candidates (0.017 %). Note "relabel to the polygon" is
   unavailable for 5 of the 6 — they are inside no polygon at all.

**Author sign-off:** withheld.


## v8 dispositions (author, 2026-09-30)

v8 is the three-way split the user decided on 2026-09-30:
- **CR-0007 v8**: membership and constants.
- **CR-0012**: the global split and the pooled draw.
- **CR-0013**: the acceptance gates, as a committed script.

This table dispositions **every row marked NOT DISPOSITIONED above**, plus
three rows marked "never dispositioned" or "not recorded" (B1-11, B1-14,
D1-14) and five coordinator-raised items. The original rows are unchanged.

Terms used in the table:
- **Resolved**: the fix is in the operative text at the place named.
- **N/A**: the text or mechanism the concern refers to no longer exists
  in any of the three CRs.
- **Tracked**: a tracker item exists in
  `docs/quality/CR-0007-0008-OPEN-ISSUES.md`.

Cross-CR tables with the same content: `CR-0012-review-log.md` and
`CR-0013-review-log.md`.

| row | sev | disposition |
|---|---|---|
| B1-7 | LOW | Resolved — CR-0012 §3 names the owners: `prepare_training_data.py` owns the grid and the val draw; `generate_negatives.py` only reads it. §2 pool step 10: the positive-free val share is global (0.197 today under the hash spec). |
| B1-9 | LOW | Resolved — CR-0007 §1: `in_state` uses `verify_partition`'s polygons, predicate and `to_crs`. |
| B1-11 | positive | Recorded — CR-0012 §4 removes the template; §7 guards `legacy/gen_negs.py`. |
| B1-14 | unrated | N/A — assertion (d) no longer exists. |
| D1-14 | unrated | Resolved — CR-0013 R1/R3/R4 (exact replayed sets) and E9 (counts); a matched shrink of both classes fails. |
| F2-C5 | MAJOR | Resolved — CR-0012 §1 adds `VAL_FRACTION` and `SPLIT_SEED`; §3 removes the flags; CR-0013 E11. |
| F2-C8 | MAJOR | Resolved — CR-0007 deliverable 7 files PA-0020 from the one committed draft text, citing BUG-0034 as its live instance; the inert example is removed. Support at receptive-field scale: CR-0013 O5 and O9 (OBS; CR-0013 design rule 2). |
| F2-C10 | MAJOR | Resolved — CR-0012 §3 (`--regions` dry run on both scripts) and §2 Writes. |
| F2-C12 | LOW | Resolved — CR-0007 §2 "Known limit" (coastal water is removed by the extraction `dropna`); relabelling covered at C7-6. |
| F2-C13 | LOW | Resolved — CR-0012 §2 fixes the kept-set semantics, and CR-0013 R1/R3 check it; the implementation, and so its cost, is free. |
| F2-C15 | LOW | Resolved — CR-0012 Out of scope: `scripts_backup/` uses pre-reorganisation paths (e.g. `landfire_data/`, `scripts_backup/check_raster.py:70`). |
| F2-C16 | LOW | Resolved — CR-0007 §2 "Provenance of `state`": both classes carry GBIF `stateProvince`; the polygon check is the evidence for both. |
| F2-S | unrated | Resolved or N/A: <br>• S1 BUG-0029 path: CR-0007 deliverable 7. <br>• S2 `clip_to_region` before/after: CR-0007 §2. <br>• S3, S4, S8: accepted earlier. <br>• S5 undefined terms: each CR defines its record sets. <br>• S6 PA-0019: Tracked. <br>• S7 PA-0020 text: CR-0007 deliverable 7. <br>• S9 I2 readings: now exact E5. <br>• S10 absent content: v8 has no forward references. |
| F2-N | unrated | Resolved — v8 carries only re-verified numbers: <br>• 35,678; `:238-317`; `:143`. <br>• The 30–79 m window is N/A (flags removed; R1 exact). <br>• `:302` is not cited. <br>• 0.190 is replaced by 0.197 under the hash spec. <br>• "~65 %" is dropped. <br>• The NH box share is not needed: 0 NH sightings lie outside the NH box (verified), and candidates are handled by the window drop. |
| F3-D5 | MAJOR | Resolved — clean rewrite (§1.1 A4). `TIGER_YEAR` is in CR-0007 §1 and deliverable 3; there is no appendix; GATE/OBS are explicit in CR-0013. |
| F3-D6 | MAJOR | Resolved — CR-0007 deliverable 7 (no `coord_uncertainty_m` example). |
| F3-D8 | LOW | Resolved — CR-0013 deliverable 0: PA-0021's Swept? cell names the sweep scope. |
| E-1 | BLOCKING (programme) | Resolved — the CRs have been tracked in git since `1445ccd`, and version headers are correct in v8. The BUG-0033 §2.4 statement goes into its filing (CR-0013 deliverable 0). |
| E-3 | BLOCKING | Resolved — CR-0013 deliverable 0 files the calibration-from-extrema cause as its own BUG. |
| E-4 | BLOCKING | Resolved — PA-0021 extends PA-0016 (CR-0013 deliverable 0). |
| E-9 | BLOCKING | Resolved — CR-0012 deliverable 8 files BUG-0032. |
| E-11 | MAJOR | Resolved — same as F3-D6. |
| E-12 | MAJOR | Resolved: <br>• "Before" is measured by running `check_partition.py` or `acceptance_split.py` on the backed-up pre-CR files (CR-0007 test plan; CR-0013 deliverable 5). <br>• `analyze_grouse.py` runs once (CR-0007 deliverable 6). <br>• CR-0009's baselines come before CR-0012 (CR-0012 deliverable 0). |
| E-13 | MAJOR | Resolved — review is not a deliverable in v8; deliverables begin after approval. CR-0013's pre-approval item is labelled as such. |
| E-16 | MAJOR | N/A — escape mode deleted (user decision); CR-0013 design rule 3. |
| E-17 | MAJOR | Tracked (Shared: "Land bookkeeping batch; name an owner"). Each v8 CR names what it files: <br>• CR-0007 deliverable 7; <br>• CR-0012 deliverable 8; <br>• CR-0013 deliverable 0. <br>A single writer and the BUG_LOG ordering are for the user to decide. |
| E-18 | MAJOR | Resolved — CR-0013 deliverable 0 bounds PA-0021's sweep scope. |
| E-PAa | unrated | Accepted into the PA-0021 filing (CR-0013 deliverable 0): attacks are recorded so they can be re-run. Most CR-0013 attacks were built by reviewers (§ Attacks). |
| E-19 | LOW | Tracked — BUG-0028/PA-0019 promotion (bookkeeping batch). |
| E-20 | LOW | Resolved — CR-0007 deliverable 7 and CR-0012 deliverable 8: fixed when CR-0012 lands, closed after CR-0009. |
| E-21 | LOW | Resolved — the backup is CR-0007 deliverable 1; CR-0012 deliverable 1 verifies it. |
| E-22 | LOW | Resolved — no struck or pre-ticked items. |
| E-R1 | ruling | N/A — moot. The user deleted escape mode (2026-09-30), so no escaped run exists to refuse writes. |
| C7-2 | BLOCKING | N/A — I14b is not a gate. CR-0013 R2 requires the val-block set to equal the replay at the pinned seed; the Jaccard-0.992 draw fails it. |
| C7-5 | MAJOR | Resolved — CR-0013 E3. |
| C7-6 | MAJOR | Escape part: N/A (deleted). Known exceptions: **F's ruling adopted — drop all 6**; H's "drop 5, relabel 1" is not adopted (CR-0012 §2 pool step 4). `state` is the acquisition query key. Relabelling the NH-filed record would make a record fetched by an NH query an ME member, and an audited list grows silently. Cost: 6 of 35,678. |
| C7-8 | LOW | Resolved — CR-0012 §2 positives step 3; CR-0013 E8 covers positives. |
| C7-9 | LOW | Resolved — CR-0012 manifest sha256 values; CR-0013 E11. |
| C7-11 | LOW | Resolved — CR-0012 §3 removes the flags. |
| C7-12 | LOW | Tracked — PA-0019 with BUG-0028 (bookkeeping batch). |
| H-X7 | unrated | Tracked (new item). `INVESTIGATION_REPORT_errol_map.md` is in git and needs no backup. `old_road_dist/` and `new_road_dist/` belong with CR-0014/CR-0009, not CR-0007. |
| H-Q | unrated | Tracked — same as E-19. |
| H-I14a | unrated | N/A — parameters are checked exactly by E11 against the config and by the R1–R4 replay. |
| F4-Q3 | BLOCKING | N/A — clean rewrite; none of the nine contradicted passages exists in v8, CR-0012 or CR-0013. |
| FA-C4 | BLOCKING | N/A — (d) no longer exists. |
| FA-C6 | MAJOR | Resolved — CR-0012 claims no "no effect"; pooled thinning changes the kept set (manifest counts). |
| FA-C7 | MAJOR | Resolved — window counts are recorded at the stage they occur (CR-0012 §2); no raw-stage figure is quoted. |
| FA-C8 | MAJOR | Resolved — there are no extremum thresholds. I18 and I19 are OBS O1 and O5, with defined nulls (CR-0013). |
| FA-C9 | MAJOR | Resolved — stratification not adopted (CR-0012 Out of scope). |
| FA-C11 | LOW | N/A — the BUG-0034 and load/construct text is gone. |
| FA-Q1 | unrated | Resolved — rounds table above plus this table. |
| FA-Q3 | unrated | Resolved — each record has a named filer: <br>• PA-0020: CR-0007 deliverable 7. <br>• PA-0021/BUG-0033: CR-0013 deliverable 0, before CR-0013's approval. <br>• BUG-0031: CR-0007. <br>• BUG-0032: CR-0012. <br>PA-0019 is Tracked. |
| FA-Q4 | unrated | Tracked — the BUG-0034 per-class drop-rate assert belongs to BUG-0034's fix CR (new item); CR-0013 O9 reports per-class year support until then. |
| FA-Q5 | unrated | Tracked — BUG-0034 sweep, same item. |
| FA-Q6 | unrated | Resolved — all deliverables pending. |
| FC-C4 | BLOCKING | Resolved — CR-0013 call-site matrix, with one implementation. |
| FC-C5 | BLOCKING | Resolved — no BUG-0034 residue in any CR. The `DRAFT_BUG-0034` status fix is CR-0007 deliverable 7 plus a tracker item. |
| FC-C6 | BLOCKING | Resolved — this log. |
| FC-C7 | BLOCKING | Resolved — same as FA-Q3. |
| FC-C9 | BLOCKING | N/A — (d) no longer exists. |
| FC-C10 | BLOCKING | Resolved: <br>• `:444` is cited in CR-0007 §2. <br>• `build_datasets` is **`train.py:238-317`** (def `:238`, `return` `:316-317`, verified 2026-09-30); `:238-336` does not match the file. |
| FC-C11 | MAJOR | Resolved — same as FA-C8. |
| FC-C12 | MAJOR | Resolved — CR-0012 §2 pool step 4 states the rule; no contradicting text remains. |
| FC-C14 | LOW | Resolved — same as FA-Q6. |
| FC-C15 | LOW | Resolved — BUG-0029 is promoted by CR-0007 deliverable 7; BUG-0027 is marked fixed by CR-0012 deliverable 8 and closed after CR-0009. |
| A-1 | BLOCKING | Resolved (CR-0013): <br>• There is no per-region I18 gate. <br>• O1 is pooled and OBS, with its null measured post-CR. <br>• BUG-0027's leak is gated exactly by E4/E5 (pre-CR: 522 keys, 882 blocks). |
| A-2 | BLOCKING | Resolved: <br>• `BUFFER_M` is centralised (CR-0007 §1). <br>• The removed count is in the manifest (CR-0012 §2 step 6). <br>• E7 is an exact minimum-distance check and R3 replays the buffer (CR-0013). <br>• O5 is two-sided; the attack is in the suite. |
| A-3 | BLOCKING | Resolved — this log. |
| A-4 | MAJOR | Resolved — CR-0013 O5 N-draw is conditioned on the realised split and pool; the attack fails R3, so stated limit 3 no longer applies. |
| A-5 | MAJOR | Resolved — CR-0013 E3. |
| A-6 | MAJOR | Resolved — CR-0013 O6–O8 are calibrated on the rebuilt footing (deliverable 6) and bound to its digest. |
| A-7 | MAJOR | Resolved — CR-0012 §2 step 11 persists the columns; everything is computed in `acceptance_split.py`. |
| A-8 | MAJOR | Resolved — no escape; CR-0012 deliverable 0; CR-0009 v4 already updated (tracker). |
| A-9 | MEDIUM | N/A — clean rewrite. |
| A-10 | MEDIUM | Resolved — CR-0013 O4. |
| A-11 | MEDIUM | Accepted; the claim is withdrawn. Verified: VT val has 452 selected, of which 136 NonVeg = round(452 × 0.3), with no top-up. It is not used anywhere. |
| A-12 | MEDIUM | Resolved — CR-0013 O7 (OBS; compared with the previous run). |
| A-13 | MEDIUM | Resolved — same as FC-C12. |
| A-14 | LOW | Resolved — v8 citations re-verified. <br>• Provenance: `get_negatives.py:268`, `sightings.py:132`. <br>• `:143`, `:444`. <br>• R5's `:443-444` is not needed: standing checks read the CSVs directly. <br>• "723" is not carried. <br>• The year rule is stated as either/or (CR-0013 E8). <br>• "NH 721" / "3 of 5,220" are not quoted. |
| A-15 | LOW | Resolved — `REGIONS` constant (CR-0007 §1) and config (CR-0013 E1/E11); guard in CR-0012 §3. |
| A-16 | LOW | Resolved — deliverables are numbered in execution order in all three CRs. |
| B-1 | BLOCKING | Resolved — reconstruction (above) plus this table. Quorum: see below. |
| B-2 | BLOCKING | Resolved — the user chose option (i): baselines first, no escape. |
| B-3 | MAJOR | Resolved — CR-0013 matrix. |
| B-4 | MAJOR | Resolved — same as A-10. |
| B-5 | MAJOR | Resolved — no GATE has a null; OBS nulls come from CR-0013's own replay, after the gates pass. |
| B-6 | MAJOR | Resolved — CR-0013 § Attacks, deliverables 1 and 4; CR-0012 §7 pins the evidence scripts to `ec1470a`. |
| B-7 | MAJOR | Resolved, item by item: <br>• `TIGER_YEAR`: CR-0007 §1, deliverable 3. <br>• `ignore_index`: CR-0012 §2 Draw. <br>• negative `verify_partition`: CR-0012 §2 step 4, CR-0013 E12. <br>• windowless drop: CR-0012 §2 steps 3 and 8. <br>• PA-0020: CR-0007 deliverable 7. <br>• "none": see FA-C6. <br>• Known exceptions: see FC-C12. <br>• §6 (d), the test plan and "Not optional detail": the text is gone. |
| B-8 | MAJOR | Resolved per CR (FA-Q3); a batch-wide owner is Tracked (Shared). |
| B-9 | MEDIUM | Resolved — user decision: CR-0014 sets 2023 with its own regeneration and gates; CR-0007 only centralises (§1 reconciliation rule). |
| B-10 | MEDIUM | Resolved — same as F2-C10. |
| B-11 | MEDIUM | Resolved (CR-0012; see CR-0012-review-log): <br>• hash ordering adopted; <br>• flags removed; <br>• stratification not adopted; <br>• `draw_val_blocks` not adopted (R2 makes it redundant). |
| B-12 | MEDIUM | Resolved — CR-0012 §1 `WINDOW_PX`, §2 year rule, §5 refusal; CR-0013 E8. |
| B-13 | MEDIUM | Resolved — CR-0012 §4. |
| B-14 | MEDIUM | Resolved — CR-0007 §2: the KDE source stays box-clipped (it includes neighbouring-state records) and its output is partitioned. Recorded in PA-0018's Swept? cell (CR-0007 deliverable 7). |
| B-15 | MEDIUM | Resolved — same as A-11. |
| B-16 | MEDIUM | Resolved: <br>• Every GATE is exact on deterministic data, so the family-wise false-fail rate in the pinned environment is 0. <br>• No multiple-of-max rule remains. <br>• C11, I15 and I18 are OBS with all fields named (CR-0013). |
| B-17 | MEDIUM | Resolved — CR-0013 R1 (the target is the replayed set); 6,232 is only an expectation (CR-0012 Impact). |
| B-18 | MEDIUM | Resolved — CR-0007 deliverable 7 (new BUG: constants and `TIGER_YEAR` drift, PA-0001 recurrence); CR-0012 deliverable 8 (new BUG: `:153`). |
| B-19 | LOW | Resolved: <br>• citations re-verified; <br>• consumers listed per CR (including `tune_bins.py:213`); <br>• 5 guards (CR-0007: 1, CR-0012: 4); <br>• backup of 2 directories; <br>• the standing checks precede the loop. |
| B-20 | LOW | Resolved — same as A-16. |
| B-21 | LOW | Resolved — CR-0012 §6. |
| B-R | unrated | Resolved — the four risks are in: <br>• CR-0013 Risk (replay false-fail, float/PROJ); <br>• CR-0012 Risk (partial writes, shared misreading); <br>• CR-0007 Risk (`TIGER_YEAR`). <br>"Cannot validate" additions: CR-0013 stated limit 2; non-default jitter is refused (CR-0012 §5). |

**Coordinator-raised items:**
1. **E and H's escape ruling** (all four assertions, provided the escaped
   run refuses to write): moot. The user deleted escape mode on
   2026-09-30. Recorded at E-R1 and C7-6.
2. **Known exceptions, H vs F:** F's "drop all 6" is adopted. Reason at
   C7-6.
3. **Rounds 1–2 row "`TIGER_YEAR` owned by no CR"** (traced to the CR-0006
   reviews): resolved. CR-0014 owns the value (2023); CR-0007 v8 §1
   centralises it, and whichever lands second reconciles.
4. **`build_datasets` range:** `train.py:238-317`, verified. See FC-C10.
5. **`DRAFT_BUG-0034` still says "fixed in CR-0007"**: tracker item added.
   CR-0007 deliverable 7 corrects it on promotion.

**Quorum for v8 (open, needs a user decision).** §1.4 counts every
reviewer who commented: B, D, E, F, H, Formal A, Formal C, and round-7 A
and B. Those agents cannot be resumed. The author proposes the following,
which the user must confirm:
- CR-0007 v8, CR-0012 and CR-0013 each get a first, unrestricted review
  (§1.2), because each is a new document after the split.
- This table serves as the record that no prior concern was dropped.

**Author sign-off on v8:** pending review.

## Versions
| version | date | change |
|---|---|---|
| v8 | 2026-09-30 | Split three ways. CR-0007 keeps membership and constants, with exact checks P1–P7 only. The split and draw go to CR-0012; the acceptance gates to CR-0013 (exact predicates and replay; statistics as OBS). No escape mode. `TIGER_YEAR` value owned by CR-0014. |
| v9 | 2026-09-30 | Round-8 findings dispositioned (below). P6 scan set, rules and exemptions enumerated; P5 envelope predicates; P8 KDE-source check; guards are first statements and P7 checks them instead of importing; full re-point table; `STATE_NAMES`, `COUNTY_POLYGONS_YEAR`, two `PATH_TEMPLATES` entries; `legacy/download*.py` guards moved in (user); gate code written (`check_partition.py`, two test files, evidence). The v8 "Split (user decision)" paragraph was history and is now only here and in § v8 dispositions. |

## Round 8 (v8, fresh first review, 2026-09-30) — dispositions pending
| reviewer | verdict | blocking |
|---|---|---|
| A — correctness | REJECT | 1 |
| B — implementability + §1 | REJECT | 1 |

Both BLOCKING findings are the same: **P6 cannot pass** at deliverable 6 —
unguarded literal constants remain in `clean.py:47,50`,
`legacy/gen_negs.py:77-78` (guarded only by CR-0012) and
`repair_coverage_rasters.py:53` (`REGIONS`); "live module" undefined;
the "8" count is wrong (13 tracked non-evidence). Fix: enumerate the
scanned set (git-tracked, excluding `inv_*`/`res_*`), exempt `clean.py` and
`legacy/gen_negs.py` until CR-0012, re-point or exempt
`repair_coverage_rasters.py`.

Other findings (to disposition in v9):
- A2 MAJOR: `envelope_metrics` used/available half unchecked (two wrong
  constructions pass P1–P7); P5 ambiguous (pre- vs post-filter points).
- A3 MEDIUM: KDE-source decision unchecked; map surface contradicts it.
- A4 MEDIUM: P7 vs the `legacy/audit.py` import-time guard; P7 scope.
- A5–A7 LOW: collapse before restriction (0 cases today); P3 must match
  `sample_raster` exactly; §1 omits `generate_negatives` constant imports.
- B2 MAJOR: **false disposition E-1** — BUG-0033 §2.4 statement is not in
  CR-0013 deliverable 0 (§1.3 drop).
- B3 MAJOR: `check_partition.py` and `tests/test_shared_constants.py` do
  not exist; must be committed and reviewed before approval; deliverable
  order.
- B4–B6 MEDIUM: checker inputs/constants source, independent polygon
  check; P5 wording; enumerate import re-points and P7 list.
- B7 MEDIUM: bookkeeping — BUG-0031 needs a named PA (§4.3); PA-0001
  sweep for `"EPSG:5070"` literals (10 files) and county-path
  duplication; untracked drafts it promotes from.
- B8 MEDIUM: A5 justification (constants, partition, unrelated
  promotions bundled). B9: quorum (now decided by user: fresh review).
- B10 LOW: `PATH_TEMPLATES` for `availability_sample`; `:778-780` not
  `:787`; `verify_partition` after the longitude flip; cache county
  file; A4 duplicates; sibling references to "CR-0007's I17".

## v9 dispositions (author, 2026-09-30)

Every round-8 finding (reports: this session,
`agent-adcfa17f160fdbf6b.jsonl` = A, `agent-ac2b76b407fb0fdf8.jsonl` = B),
plus the items the coordinator relayed. "§" means CR-0007 v9. "Tracked"
means an item in `docs/quality/CR-0007-0008-OPEN-ISSUES.md`.

| id | sev | disposition |
|---|---|---|
| A1 / B1 | BLOCKING | **Accept.** §Acceptance "P6 scan": scanned set = `git ls-files '*.py'` minus basenames `inv_*`/`res_*` (so the tracked `inv_review*` scripts are out) minus `tests/`; exemptions named (`regions.py`; `clean.py`, `legacy/gen_negs.py` as CR-0012 §6 guards them; the three §3 copies; the two road files until deliverable 7). `repair_coverage_rasters.py:53` is re-pointed (§1 table); the v8 claim that `REGIONS` was "implicit" is corrected. Count corrected and measured by the committed scanner: 24 violation lines in 21 files outside the exemptions, 8 in exempt files. The reviewers' 13 counted named assignments to the §1 names only; applying v8's own "`_DEFAULT` aliases" clause adds seven `REGIONS_DEFAULT` literals, and the value rules (ii)–(iii) add inline region lists and code/name maps. All are re-pointed (§1 table). Mechanised in `check_partition.scan_repository` / `tests/test_shared_constants.py`. |
| A2 | MAJOR | **Accept.** §2 availability file = all `BACKGROUND_N` in-state points before raster sampling, with `used` and `envelope_id`; P5(a)–(d) are the reviewer's predicates plus uniqueness. Both constructions fail in `tests/test_check_partition.py` (`test_avail_from_box_draw_while_file_holds_in_state_draw`, `test_sightings_from_box_habitat`), as do a post-filter file and a box-drawn file. `background_nonveg_rate` left unchecked (print-only), as the reviewer allowed. Stated limit: `used`/`envelope_id` per point is not recomputed. |
| A3 | MEDIUM | **Accept.** P8 recomputes every own-state `spatial_density`/`spatial_zone` from the box source S_R; `test_kde_restricted_to_own_state` fails P8 only. On today's box-sourced files P8 reproduces all 18,407 rows, validating the re-implementation. Map choice stated in §2: surface on the box KDE source, markers restricted; not checked. The "Hotspot 10%" consequence is stated as intended. |
| A4 | MEDIUM | **Accept, reviewer's second option.** Guards are the first statement (matching CR-0012 v2 §6). P7 does not import guarded copies; it checks by AST that the guard is first and that running the file exits non-zero naming BUG-0031 (it never runs an unguarded copy). P7 list enumerated; `inv_*` excluded. |
| A5 | LOW | **Accept.** §2: `load_all_sightings` raises if a key is filed under two states; P3 reports that count and names the case. 0 today. |
| A6 | LOW | **Accept.** §Acceptance "Definitions" states the sampling semantics (`sample_raster` `:276-295`: inclusive bounds, file nodata, `NODATA_SENTINELS` read from `grouse_data.py`), `available_years` and `pick_raster_year`; P3 adds an exact feature-agreement sub-check. Today: ME and VT 0 mismatches; NH 2,305, all `ch`/`cc`, because the NH `ch`/`cc` rasters postdate the file (O4). |
| A7 | LOW | **Accept.** §1 re-point table, `generate_negatives.py:60,70,71,241`. |
| B2 | MAJOR | **Accept; the v8 row E-1 was false when written.** Verified 2026-09-30: CR-0013 v2 deliverable 0 (line 352) now reads "Include the §2.4 statement (E-1)". Corrected disposition of E-1: Resolved — moved to CR-0013 v2 deliverable 0. |
| B3 | MAJOR | **Accept.** `check_partition.py`, `tests/test_check_partition.py`, `tests/test_shared_constants.py` and `docs/quality/evidence/CR-0007-check-today.txt` now exist (uncommitted per instruction; the coordinator commits them). Deliverable 0 is the pre-approval item, listed first. |
| B4 | MEDIUM | **Accept.** Constant sources named in §Acceptance: `ast.literal_eval` of the single definitions, no copies. The polygon check is independent (own dissolve, `shapely.contains_xy`). `test_shared_constants.py` reads `regions.py` by AST, so today it fails with a problem list, not an ImportError. The analysis CRS is read from the `x_<epsg>` column; the checker's only CRS literal is the GBIF lon/lat encoding (4326), listed under sweep item (d). |
| B5 | MEDIUM | **Accept.** As A2. |
| B6 | MEDIUM | **Accept.** §1 re-point table and P7 list. |
| B7 | MEDIUM | **Accept.** (a) BUG-0031's new PA (extends PA-0002 and PA-0012) is written out in deliverable 6. (b) The PA-0001 extension's sweep has four items, each its own BUG. The CRS item is deferred with an owner and a reason (tracked). It has 16 code literals in 7 files; the reviewer's 10 files included 3 that contain the string only in comments (`dataset.py`, `grouse_data.py`, `realign_rasters.py`). The county path is remediated via `PATH_TEMPLATES["tiger_county"]` (+ deliverable 7); `check_road_dist.py:127` is justified as CR-0014's pin-driven verifier. (c) The drafts are committed at deliverable 0. (d) PA-0020's Rule has no `coord_uncertainty_m` example; its Swept? cell keeps the measured-inert finding. |
| B8 | MEDIUM | **Accept.** "One change (§1.1 A5)" paragraph. BUG-0034 stays only as PA-0020's filing prerequisite, stated. |
| B9 | MEDIUM | **N/A — decided by the user (2026-09-30):** round 8 was the fresh first review. The quorum for v9 is round-8 A and B plus the author; round 9 is a bounded re-review (§1.2). |
| B10 | LOW | **Accept**, item by item: <br>• Impact names `grouse_data`'s `.evaluated` accessor (`generate_negatives.py:148`). <br>• `PATH_TEMPLATES` gets `availability_sample` and `tiger_county`. <br>• KDE cited as `:778-795`. <br>• `verify_partition` runs after the flip (`:187-193`). <br>• County polygons are cached. <br>• 4,455 and 43,024 appear once each (P1 and P4). <br>• The split paragraph is in this log only. <br>• F2-C15 correction: `scripts_backup/check_raster.py:70` is not in CR-0012's text; the claim itself stands. <br>• Sibling references are **Tracked** (the other CRs cannot be edited here): CR-0014 `:12`, `:146` "CR-0007's I17" should read CR-0013 O8; CR-0009 `:64` "CR-0007/CR-0012 land" should read CR-0012. |
| U1 | user decision | **Accept.** Guards on `legacy/download.py` and `legacy/download_more.py` moved from CR-0012 into v9: §3, deliverable 4, P6 exemptions, P7 guard checks. |
| C1 | coordinator | **Verified, no conflict.** CR-0012 v2 §1 (`:52-54`) deletes `REGIONS_DEFAULT`, `MIN_SPACING_M_DEFAULT`, `BLOCK_SIZE_M_DEFAULT`, `VAL_FRACTION_DEFAULT` and `RANDOM_SEED_DEFAULT` from `prepare_training_data.py`. CR-0007 binds the first three to `regions` in the meantime (§1 table), and the scan accepts either state. `VAL_FRACTION`/`SPLIT_SEED` are CR-0012's constants and are not in CR-0007's P6 names. **Tracked:** CR-0012 adds them, with pins, to `P6_NAMES` and `EXPECTED_REGIONS` when it adds them to `regions.py`. |
| C2 | author | **Tracked.** CR-0013 v2 `:296` cites "CR-0007 (P1–P7)"; v9 adds P8. |
| C3 | author, new | **Tracked** as an observation (O4): NH `ch`/`cc` rasters rewritten 2026-09-20, after `evaluated_sightings_NH.csv`. Cause untested (PA-0016). The CR-0007 re-run supersedes the stale values. |

**Tests (2026-09-30):** `python -m unittest tests.test_check_partition
tests.test_shared_constants`: 26 tests, OK (1 expected failure: the
repository-tree P6 test, by design until deliverable 2).

**Author sign-off on v9:** pending round-9 review.

## Round 9 (bounded re-review of v9, commit f8fafbc)
| reviewer | verdict |
|---|---|
| A — correctness | **APPROVE** — A1–A7 resolved in text and code; P6 passable after a correct implementation (every flagged line is in the §1 re-point table); both envelope_metrics constructions fail P5; 26 tests OK (1 expected failure) |
| B — implementability | **APPROVE WITH FOLLOW-UPS** — B1–B10 resolved; P6 scan (24 lines / 21 files) maps entirely onto the §1 re-point table; exempt files hold exactly 8 lines; deliverable order executable; bookkeeping complete |

| # | sev | concern | disposition |
|---|---|---|---|
| A-R9-1 | LOW | `test_avail_from_box_draw…` asserted only that "P5b" appears (it always does) | **Accept** — now asserts a nonzero Avail_N mismatch count |
| B-R9-1 | LOW | `clean.py` / `legacy/gen_negs.py` P6 exemption relies on CR-0012's guards | **Tracked** — CR-0012 implementation confirms its guards before the exemption is relied on |
| B-R9-2 | LOW | Removing the road-file exemptions at deliverable 7 edits gate code after approval | **Accept** — deliverable 7's edit is reviewed when it lands |
| B-R9-3 | LOW | Sibling-CR items and O4 remain open | **Tracked** (tracker) |

## Quorum (§1.4)
Round 9: reviewer A APPROVE, reviewer B APPROVE WITH FOLLOW-UPS (v9,
`f8fafbc`; test fix A-R9-1 applied after). Author: **signed off** — user
approved 2026-09-30. **CR-0007 v9 APPROVED.**


## Implementation record (deliverables 2–6, 2026-09-30)
Implementer: an agent session separate from the author's; deliverables 0
and 1 were done by the coordinator (`f8fafbc`; backup manifest
`docs/quality/evidence/CR-0007-backup-manifest.txt`). Nothing committed by
the implementer.

**Code (deliverables 2–4), `git diff --stat` lines:**
- `regions.py` (+114): the §1 constants, `BOXES` docstring (extents, not
  membership), `verify_partition`, `in_state` (pyogrio `where` filter on
  `STATEFP`, dissolve, EPSG:4269→4326, `within`; polygons cached in
  `_STATE_POLYGONS`; geopandas and `grouse_data` imported inside).
- `grouse_data.py` (+4): `PATH_TEMPLATES["availability_sample"]`,
  `["tiger_county"]`.
- `analyze_grouse.py` (+146/−): `check_state_partition` called at the end of
  `load_all_sightings`; `in_state_background_points` (box-sized batches,
  `MAX_BG_BATCHES = 20`), used by `background_envelope_sample` (which writes
  `availability_sample_{region}.csv`) and by `background_nonveg_rate`;
  `valid` restricted to `state == region` with a `region` column
  immediately after the KDE stage; the non-veg block (flag, report, write)
  moved after it; the map's density surface fit on `kde_source`.
- Re-points (§1 table, excluding deliverable 7's row): `predict.py`,
  `download_treemap.py`, `download_tcc_nlcd.py`, `diagnose_road_bias.py`,
  `generate_negatives.py`, `prepare_training_data.py`,
  `repair_coverage_rasters.py`, `check_exotic.py`, `diagnose_water_bias.py`,
  `dupe_check.py`, `tune.py`, `tune_bins.py`, `bench_pipeline.py`,
  `calibrate.py`, `diagnose_training.py`, `diagnose_wetland.py`,
  `pretrain.py`, `train.py`, `check_raster.py`, `get_negatives.py`,
  `sightings.py`, `ebird.py` (2–16 lines each). No value or CLI default
  changed.
- Guards (§3): line 1 of `legacy/audit.py`, `legacy/download.py`,
  `legacy/download_more.py`.
- Not done: deliverable 7 (waits for CR-0016, then CR-0014). The
  `expectedFailure` marker in `tests/test_shared_constants.py` was kept
  (F1).

**Validation.**
- `python analyze_grouse.py`: exit 0, 46 s. `python check_partition.py`
  (acceptance run): **P1, P2, P3, P4, P5, P7, P8 PASS; P6 FAIL** on 3 lines,
  all in `docs/quality/evidence/CR-0007-r7/*.py` (F1). Full output and O1–O4:
  `docs/quality/evidence/CR-0007-gates.txt`. O1 = 0 in every region;
  O2 = 3,740 / 1,119 / 1,552; O3 judgeable envelopes ME 46→49, NH 50→50,
  VT 48→49; O4 NH own-state `ch` 539 / `cc` 654 values replaced.
- Test plan "P1–P3 fail on the backed-up pre-CR files": confirmed
  (`--data-root` pointing at the backup; same file).
- `python -m unittest tests.test_check_partition tests.test_shared_constants
  tests.test_cr0008 tests.test_cr0010 tests.test_cr0014
  tests.test_check_road_dist`: 60 tests OK (1 expected failure, F1).
- `py_compile` of every touched file; `train.py`, `calibrate.py`,
  `pretrain.py`, `predict.py --help` all parse.
- Guards fire: `python legacy/audit.py` exits 1 naming BUG-0031 (P7).

**Bookkeeping (deliverable 6)** — ids checked immediately before filing;
BUG-0042 is reserved by CR-0015, so the next free id was BUG-0043.

| item (deliverable 6) | disposition | operative location |
|---|---|---|
| Constants BUG + new PA extending PA-0001 | Filed BUG-0043; PA-0025 (rule text as specified) | `docs/quality/bugs/BUG-0043-…md`; `PREVENTIVE_ACTIONS.md` row PA-0025; PA-0001 Swept? cell annotated |
| §3.5 sweep (a) region-code sequences | BUG-0044, FIXED by deliverable 2 | `BUG-0044-…md` |
| (b) state-name / eBird maps | BUG-0045, FIXED by deliverable 2 | `BUG-0045-…md` |
| (c) county path built twice | BUG-0046, PARTLY FIXED (template); generator re-point = deliverable 7 | `BUG-0046-…md`; `grouse_data.py` `PATH_TEMPLATES["tiger_county"]` |
| (d) analysis CRS | BUG-0047, OPEN, deferred, owner CR-0007's author | `BUG-0047-…md`; tracker "Analysis-CRS constant" |
| BUG-0031 + new PA extending PA-0002/0012 | Filed BUG-0031; PA-0026; sweep by output path; PA-0002 and PA-0014 Swept? cells corrected | `BUG-0031-…md` §8; `PREVENTIVE_ACTIONS.md` rows PA-0002, PA-0014, PA-0026 |
| PA-0026 sweep findings | `legacy/download_landfire*.py` → BUG-0048 (OPEN, not remediated: outside §3, F5); `tune.py` → existing BUG-0016 (open) | `BUG-0048-…md`; tracker |
| Promote DRAFT_BUG-0034 | Moved to `docs/quality/bugs/`; status "OPEN; fix owned by a future CR" (the draft's "DECIDED: fixed in CR-0007" corrected) | `BUG-0034-…md` header, §6, §8; `BUG_LOG.md` |
| Promote DRAFT_BUG-0029 | Moved; §8 rewritten to cite PA-0020 as filed; `BUG_LOG.md` row | `BUG-0029-…md` §6, §8 |
| File PA-0020 from the draft row | Filed (Rule has no `coord_uncertainty_m` example; Swept? keeps the inert `MAX_COORD_UNCERTAINTY_M` finding). The draft's unowned "source-axis asymmetry, undiagnosed" item was given owner BUG-0034 to satisfy PA-0022 | `PREVENTIVE_ACTIONS.md` row PA-0020 |
| PA-0018 Swept? cell | KDE source box-sourced, checked by P8 (plus P1–P5 notes) | `PREVENTIVE_ACTIONS.md` row PA-0018 |
| BUG-0027, BUG-0029 corrective action | "membership: CR-0007; split and draw: CR-0012"; fixed when CR-0012 lands, closed after CR-0009 | `BUG-0027-…md` §6; `BUG-0029-…md` §6; `BUG_LOG.md` rows |

**Implementer findings** (`docs/quality/evidence/CR-0007-implementer-findings.md`):
- **F1 (blocking P6):** the nine `docs/quality/evidence/CR-0007-r7/*.py`
  became git-tracked in `f5e5ee4`, after approval; three of them match P6
  rule (ii). Every remedy (exclude `docs/` from the scan, exempt them, or
  edit frozen evidence) is a spec change → **amendment needed**. Until then
  P6 fails and the `expectedFailure` marker stays.
- F2: the spec's "21 files" is 20 (24 lines correct).
- F3: choices left open by the spec (batch size, `verify_partition` return
  type, non-veg report moved with its write; `nonveg_flagged_*` now carries
  `spatial_density`/`spatial_zone`/`region`).
- F4: `generate_negatives.py`, `prepare_training_data.py`,
  `repair_coverage_rasters.py` edited because the §1 table names them.
- F5: BUG-0048 not remediated (outside §3's scope).
- F6: tracker item (CR-0015 R1 B8) asks for a different BUG-0029 closure
  rule. CR-0015 is unapproved, so the approved v9 wording was used; the
  item stays open.

**Deliverable status:** 0, 1, 3, 4, 6 done; 2 done except the marker; 5
run, P6 fails (F1); 7 pending CR-0016/CR-0014. CR-0007 is **not**
IMPLEMENTED until an amendment resolves F1 and P6 passes.

## Amendment v9.1 (2026-09-30) — implementer finding F1
P6 failed at deliverable 5 on 3 lines in `docs/quality/evidence/CR-0007-r7/`
(`build.py:14`, `feats.py:9`, `lib.py:4`): round-7 reviewer evidence
committed by CR-0013 deliverable 1 (`f5e5ee4`) after v9's approval, inside
P6's scan set. Every file in §1's re-point table was clean.
**Amendment:** P6's scanned set also excludes `docs/quality/evidence/`
(frozen review evidence, never run as pipeline code) — CR text § P6 scan
and `check_partition.py` `p6_scanned_files`. With it: P1–P8 all PASS
(`docs/quality/evidence/CR-0007-gates-v9.1.txt`); the `expectedFailure`
marker is removed from `tests/test_shared_constants.py`, which passes.
F2 (count 20 files, not 21) noted. Needs a bounded re-review of the
amendment (text + gate code) by the round-9 reviewers.

## v9.1 bounded review
| reviewer | verdict |
|---|---|
| A — correctness | **APPROVE WITH FOLLOW-UPS** — exclusion removes exactly the 9 evidence files; no live module imports from `docs/`; P1–P8 pass in a clean clone |
| B — implementability | **APPROVE WITH FOLLOW-UPS** — amendment correct; F2–F4, F6 acceptable implementer choices |

Follow-ups (LOW unless noted), tracked for v9.2: stale italic notes on
deliverables 2 and 5 (B); synthetic test for the evidence exclusion (B);
a P7/P6 assertion that no scanned module imports from `docs/` (A);
F3.3 — `nonveg_flagged_*` now also carries `spatial_density`/`spatial_zone`,
one line in §2 (B); **BUG-0048** — the three `legacy/download_landfire*`
guards found by PA-0026's sweep: remediate in v9.2 or record an accepted
deferral (B, MEDIUM in substance).

## Deliverable 7 (2026-09-30)
`generate_road_distance.py`: `TIGER_YEAR`/`STATE_FIPS` from `regions`, county
path from `PATH_TEMPLATES["tiger_county"]`, region choices from
`R.REGIONS`; `check_road_dist.py`: region default `list(R.REGIONS)`; both
P6 exemptions removed (`check_partition.py` and
`tests/test_shared_constants.py` `EXPECTED_EXEMPT`, as reviewer A flagged).
P1–P8 all PASS (`docs/quality/evidence/CR-0007-gates-d7.txt`).


## v9.2 (author = implementer, 2026-09-30) — v9.1 follow-ups; pending bounded re-review
Each v9.1 follow-up, with the operative location of its change (PA-0024(a)):

| follow-up (v9.1 review) | change | location |
|---|---|---|
| BUG-0048 (B, MEDIUM in substance) | **Remediated, not deferred.** First-statement guard in the three `legacy/download_landfire*.py`, naming `download_rev.py` (the live LANDFIRE downloader that owns `data/landfire/`; not `legacy/download.py`, itself a guarded copy) and citing BUG-0031, BUG-0048. Added to P7's guard list. Not added to `P6_EXEMPT`/`EXPECTED_EXEMPT`: the files hold no P6 violation, and exemptions stay minimal. BUG-0048 → FIXED | line 1 of `legacy/download_landfire.py`, `_2.py`, `_3.py`; `check_partition.py:68-71` (`P7_GUARDED`); CR §3 "v9.2 (BUG-0048)" paragraph; `BUG-0048-…md` §6; `BUG_LOG.md` BUG-0048 row (only that row edited); `PREVENTIVE_ACTIONS.md` PA-0002 and PA-0026 Swept? cells; tracker item ticked |
| Synthetic test for the evidence exclusion (B) | `docs/quality/evidence/x.py` is not in `p6_scanned_files`; `docs/other/x.py` is, and is the single P6 problem reported | `tests/test_shared_constants.py` `SyntheticTree.test_evidence_dir_skipped_other_docs_scanned` |
| No scanned module imports from `docs/` (A) | New P7 sub-check `docs_import_problems`: flags any `import docs…`/`from docs… import`, any `sys.path.insert/append/extend`, and any `spec_from_file_location`/`run_path`/`SourceFileLoader` whose argument mentions `docs`. Synthetic tests: a clean module passes; six ways of loading docs code each flagged once; the repository has none | `check_partition.py` `docs_import_problems`, `check_p7`; `tests/test_shared_constants.py` `DocsImports`; CR §Acceptance P7 row and "P7 list" paragraph |
| F3.3 (B) | One bullet: `nonveg_flagged_*` now also carries `spatial_density`, `spatial_zone` (and `region`) | CR §2, after the map bullet |
| Stale italic notes on deliverables 2, 5 (B) | Replaced with current facts (marker removed in v9.1; P1–P8 pass after d7 and after v9.2) | CR § Deliverables 2, 5; new deliverable 8 (v9.2) |

Also: CR §Acceptance "P6 scan" names the three exempt §3 copies explicitly,
since §3 now lists six guarded copies and only three are exempt.

**Validation.** `python check_partition.py` (acceptance run): P1–P8 all
PASS, exit 0; P7 "6 guarded copies checked; 0 scanned modules load code
from docs/" (`docs/quality/evidence/CR-0007-gates-v9.2.txt`).
`python -m unittest tests.test_check_partition tests.test_shared_constants
tests.test_nodata_zero_lint tests.test_cr0014 tests.test_check_road_dist`:
57 tests OK. `python legacy/download_landfire_2.py` exits 1 with the guard
message. Nothing committed.

**Sign-off:** author (implementer) signs v9.2. Reviewers A and B: pending
bounded re-review.

## v9.2 bounded review
| reviewer | verdict |
|---|---|
| A — correctness | **APPROVE WITH FOLLOW-UPS** — docs-import check closes every direct form, no false positives; four indirect forms (variable path, `import_module`/`__import__`, `exec`, `from sys import path`) not detected (LOW) |
| B — implementability | **APPROVE WITH FOLLOW-UPS** — code and text correct; five stale bookkeeping records after v9.1/deliverable 7 |

Follow-ups applied (v9.2.1, text and bookkeeping only):
- P6 scan paragraph no longer lists the road files as exempt; the
  docs-import check's known limit is stated (§ P6 scan).
- PA-0025 Swept? cell: road generator re-pointed; repository-tree test
  passes.
- BUG-0046 → FIXED (doc § Status and its `BUG_LOG.md` row).
- BUG-0043 → FIXED (doc § Status and its `BUG_LOG.md` row).
- Tracker: the P6/F1 item ticked; A's LOW extension of the docs-import
  check tracked.

## Quorum (v9.2)
Reviewer A: APPROVE WITH FOLLOW-UPS. Reviewer B: APPROVE WITH FOLLOW-UPS.
**CR-0007 is implemented and its bookkeeping complete; CLOSED** (the P7
extension is a tracked LOW improvement, not a CR-0007 deliverable).

