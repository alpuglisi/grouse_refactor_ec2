# CR-0013 review log

History, verdicts and dispositions for CR-0013. The CR itself states only
current intent (`CLAUDE.md` §1.1, CR-0011 A4).

## Lineage
Split from CR-0007 v7's acceptance layer (commit `bb170ea`: test-plan
table I1–I19′, § Composition gates, § Supply gates, § The `--regions`
hole, § Stated limits) on 2026-09-30, by user decision.

**Why the layer is redesigned rather than carried over.** Every CR-0007
rejection from round 2 to round 7 was a break in that layer.
- **Rounds 2–6:** a constructed pipeline passed every gate.
- **Round 7:** two things.
  - Two gates were inverted or blind: the per-region I18 (A-1) and the
    missing buffer predicate (A-2).
  - The composition and supply thresholds rested on a footing the CR
    itself changed (A-6).

The common cause: gates were thresholds on statistics of a random draw,
and every threshold traded false-fails against blind spots.

CR-0012 makes the draw deterministic. CR-0013 therefore replaces
statistical gates with exact predicates and an independent replay. The
statistics survive as observations: PA-0021(c) leaves no separation to
calibrate once replay catches every recorded attack.

v7 row → CR-0013 row:
| v7 | CR-0013 |
|---|---|
| I1 | E2 |
| I2, I3, (c) | E5 |
| I4, (b) | E4 |
| I5 | E8 |
| I6 | R1 |
| I7 | O10 |
| I8, C4 | E9 |
| I9 | E12 (negatives); CR-0007 P4 (positives) |
| I10 | not carried (retired in v4) |
| I11 | E6 |
| I12, I14 | E11 + R1–R4 |
| I13 | CR-0007 O3 |
| I15 | O2 |
| I16 | O3 |
| I16b | O4 |
| I17, C5–C8 | O8 |
| I18 | O1 |
| I19′ | O5 |
| C1, C2 | E9 |
| C3 | E10 |
| C9–C16 | O6 |
| C17, SUP0, SUP-O, SUP-R | O7 |
| (a) | E1 |

New rows, from round-7 findings:
- E3: A-5, and C7-5 from round 3.
- E7: A-2.
- E10 on the pool: v7 stated limit 5.
- O9: PA-0020(ii).

Every round 1–7 concern about v7 is dispositioned in
`CR-0007-review-log.md` § v8 dispositions. The table below lists those
whose resolution lives in this CR.

## Dispositions of CR-0007 concerns resolved here
| id (CR-0007 log) | sev | where in CR-0013 |
|---|---|---|
| A-1 | BLOCKING | The per-region I18 gate no longer exists. O1 is pooled, OBS, with an N-split null taken on post-CR data. BUG-0027's leak is gated exactly by E4/E5 (pre-CR: 522 keys, 882 blocks). |
| A-2 | BLOCKING | E7 (exact minimum distance, selected and pool, vs pooled sightings); R3 replays the buffer count; O5 two-sided; attack row "No 300 m buffer". `BUFFER_M` centralised by CR-0007. |
| A-4 | MAJOR | O5's N-draw null holds the realised positive split and pool fixed. The val-candidate thinning attack fails R3, so v7's stated limit 3 no longer applies. |
| A-5, C7-5 | MAJOR | E3 |
| A-6 | MAJOR | C rows become O6–O8. References come from `--calibrate` on the rebuilt footing (deliverable 6), bound to a footing digest. |
| A-10, B-4 | MEDIUM/MAJOR | O4: in-run permutation null, z reported, no frozen constants |
| A-12 | MEDIUM | O7, compared with the previous accepted run; no headroom claim |
| B-3, FC-C4 | MAJOR/BLOCKING | Call-site matrix; one implementation |
| B-5 | MAJOR | No GATE uses a null. OBS nulls come from this script's own replay, calibrated only after every GATE passes. |
| B-6 | MAJOR | § Attacks; deliverables 1 and 4. Broken evidence scripts are pinned to `ec1470a` (CR-0012 §7) or committed (deliverable 1). |
| B-16, FA-C8, FC-C11 | MEDIUM/MAJOR | No min/max or multiple-of-max threshold remains. The family-wise false-fail rate of the GATE set is 0 in the pinned environment, because every gate is an exact predicate on deterministic data. OBS rows name class, subset, pooling and null. |
| B-17 | MEDIUM | R1: the target is the replayed set |
| C7-2, H-I14a | BLOCKING/unrated | Not applicable: R2 and E11 replace I14, and the reviewer's Jaccard-0.992 draw fails R2 |
| C7-9 | LOW | E11 checks the manifest's sha256 values |
| F3-D8, E-18, E-3, E-4, E-PAa, FA-Q3, FC-C7, B-8 (part) | various | Deliverable 0 (PA-0021 and BUG-0033 filing, lineage, sweep scope, split calibration BUG) |
| B-R (part) | unrated | Risk rows: replay false-fail, float/PROJ. Stated limit 2: equivalence of harness and implementation cannot be validated. |
| F2-C8 (support scale) | MAJOR | O5 (receptive-field scale, per region), O9 |
| CR-0014 B6 / tracker "I17 WILL change" | — | O8 and E8 taken after CR-0014, or repeated |

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| — | v1 | not yet reviewed | — | — |

## Versions
| version | date | change |
|---|---|---|
| v1 | 2026-09-30 | Split from CR-0007 v7; exact-replay design |

## Round 1 (fresh first review, 2026-09-30) — dispositions pending
| reviewer | verdict | blocking |
|---|---|---|
| A — attack power | REJECT | 3 |
| B — implementability + §1 | REJECT | 1 |

Reviewer A findings:
- **BLOCKING 1:** gates never check the files training reads
  (`train_/val_positives_R`, `train_/val_negatives_R`); copying train rows
  into `val_positives_ME.csv` passes. Fix: add the six split files; gate
  split file == combined file filtered on `split`; name `standing_checks`'
  files.
- **BLOCKING 2:** R1/R4 compare record sets, not contents — `year`, a
  positive `weight`, `split` unchecked (NaN val `year` or `weight=0.2`
  passes). Fix: full row equality + schema gate.
- **BLOCKING 3:** "identical under shuffled input order" is impossible:
  CR-0012's dedup keeps the first row in file order and 6,492 keys carry
  >1 `year`. Fix: shuffle files/regions only, or an order-free dedup rule
  in CR-0012 (e.g. min `gbif_id`).
- MAJOR: `split_for_unassigned` md5 hash missing from the config spec;
  10A″ overclaims (input-borne nodata passes R3 → stated limit);
  inputs not bound (manifest input digests unchecked, record lacks them);
  spec defined by line refs into code CR-0012 rewrites (pin commit, name
  the shared-definition blind spot).
- MEDIUM: "full window" undefined; coordinated config+regions edit passes;
  evidence scripts depend on scratch fixtures; train-time year-gap filter
  after acceptance.
- LOW: O7/O9/O10 null "none" yet reported as z; E7 boundary; record
  writable; copy R7-A scripts early.
- Confirmed failing as claimed: Break 1, Break 2, 10A, 10B, 10C, 300 m
  buffer, duplicates, with-replacement, I18-class leaks, `--regions`
  subset, windowless (subject to fixes).

Reviewer B findings:
- **BLOCKING C1:** same as A's BLOCKING 1 — record sets omit the
  train/val files training reads; also "the per-region negative files"
  read as all three makes E3 fail every correct run (`negatives_R` is the
  union). Fix: name every path; gate train ∪ val == combined, by `split`;
  enumerate digested artifacts; train/val files in the standing subset.
- MAJOR C2: replay not implementable from the spec alone — needs
  `fit_scheme_binners`, `build_envelope_id`, `sample_raster`,
  `load_evt_crosswalk`, `build_weight` strings, `split_for_unassigned`
  md5 + seed, feature lists (models.py `FEATURE_SPEC`), crosswalk path/sha;
  "full window" undefined — **decides whether CR-0014's Canada nodata drops
  positives** (CR-0014's "records not affected" holds only under the
  in-bounds reading). Fix: pin a commit, list normative functions, put the
  lists/specs in the config, define the window predicate.
- MAJOR C3: deliverable 5 not executable (missing artifacts, E6/R1/R2 also
  fail, data-root option, CLI).
- MAJOR C4: A3 half-used — deliverables 2–5 should be pre-approval and
  reviewed in round 2; record the separate-author requirement.
- MAJOR C5: no attack exercises E12 or `standing_checks`.
- MAJOR C6: deliverable 0 drops E-1 and E-PAa; no BUG-0033 text exists;
  id collisions; Swept? cell conflict; out-of-order PA filing.
- MAJOR C7: review log omits 12 CR-0007 items resolved here and the
  tracker's "Reconcile PA-0021 clause text".
- MEDIUM C8–C11: undefined O5–O8 terms; E1 on the pooled file;
  `--calibrate` changes the config sha; evidence depends on scratch data.
- LOW C12: `dataset.py:98-102`; name the `res_supply_*` files; cite
  `bb170ea`; lazy imports in `standing_checks`; history in "Why now".


## v2 dispositions (author, 2026-09-30)
All round-1 findings were checked against the code and data before
acceptance. Checks performed:
- `gbif_id` is non-null and unique across all 265,212 raw candidates.
- 6,492 keys carry more than one `year`.
- The window math in `dataset._read_patch` is `src.index` with floor and
  `r0 = row − n//2`.
- The year fill is at `dataset.py:98-102`.

| id | sev | disposition |
|---|---|---|
| A-B1 / B-C1 | BLOCKING | Accept. § Artifacts names every path. E1p requires the train and val files to partition the combined file row for row, by `split`. E3 runs on the combined `negatives_R` only; parts are never pooled with it. "Digested artifacts" is enumerated (20 files). The standing subset covers the 18 CSVs. |
| A-B2 | BLOCKING | Accept. R1–R4 require full-row equality (every column; floats to relative 1e-12). E0 is the schema gate. Two attack rows added (NaN `year`, positive `weight`). |
| A-B3 | BLOCKING | Accept, taking the order-free option. Dedup keeps the smallest `gbif_id` per key (verified non-null and unique), so the shuffle test permutes every input row and `REGIONS`. The CR-0012 side is under "Pending for v2" in `CR-0012-review-log.md`. |
| A-M `split_for_unassigned` | MAJOR | Accept. The spec (format, modulus, seed = `SPLIT_SEED`, `vf` formula) is in § Normative definitions and the config. |
| A-M 10A″ overclaim | MAJOR | Accept. Split in two: the pipeline-borne variant fails R3; the input-borne variant is stated limit 1. |
| A-M inputs not bound | MAJOR | Accept. E11 checks the manifest's input digests against S, I and every raster read, including `road_dist` after CR-0014. The record stores them. `standing_checks` compares raster `(path, size, mtime_ns)` fingerprints. |
| A-M spec by line refs into rewritten code | MAJOR | Accept. Normative functions are pinned at `05d788d` and listed; the shared-definition blind spot is named (stated limit 2). |
| A-MED full window undefined | MEDIUM | Accept. The in-bounds predicate is defined exactly. Nodata is deliberately not considered, which keeps CR-0014's "records not affected" true. |
| A-MED coordinated config + `regions` edit | MEDIUM | Accept as stated limit 4. Config edits are reviewed, and the record carries the config sha256. |
| A-MED evidence depends on scratch fixtures | MEDIUM | Accept. Deliverable 1 commits the data-producing scripts; outputs are labelled provenance-only. |
| A-MED year-gap filter after acceptance | MEDIUM | Accept as stated limit 5. E2–E5 hold under removal; O9 reports support. |
| A-L O7/O9/O10 "none" yet z | LOW | Accept. Those rows report value and change from the previous run, with no z. |
| A-L E7 boundary | LOW | Accept. Squared distance `> BUFFER_M²`, matching CR-0012 §2 (keep if `d > BUFFER_M`). |
| A-L record writable | LOW | Accept as stated limit 6. The record's sha256 goes into committed evidence, and `standing_checks` re-runs the coordinate gates. |
| A-L copy R7-A scripts early | LOW | Accept. Deliverable 1 is pre-approval. |
| B-C2 | MAJOR | Accept. Pinned commit and function list. Feature and envelope lists, crosswalk path and sha, and the md5 spec are in the config. Raster resolution is re-implemented. The window predicate is defined. |
| B-C3 | MAJOR | Accept. § CLI and report: `--data-root` (backup path named), missing artifact → named FAIL, every gate reported, exit code. Deliverable 5 lists the expected FAILs (E0, E1, E4–E6, E11, E12, R1–R4). |
| B-C4 | MAJOR | Accept. Deliverables 0–5 are pre-approval and reviewed in round 2. Separate authorship is rule 4, verified by the transcript ids recorded in this log. |
| B-C5 | MAJOR | Accept. Attack rows added for E12 (exception kept; dropped list edited), E11 (input edited) and `standing_checks` (val file edited, pre-CR file swapped, raster touched, `--jitter 8`). |
| B-C6 | MAJOR | Accept. Deliverable 0: <br>• the §2.4 statement (E-1) and the E-PAa clause text; <br>• the BUG-0033 source (CR-0007 v7 deliverable at `bb170ea`, plus the break history); <br>• the calibration BUG takes the next free id at filing (BUG-0036/0037 taken); <br>• the Swept? cell follows PA-0022 with a named owner; <br>• the out-of-order PA filing is recorded under the tracker's PA-numbering item. |
| B-C7 | MAJOR | Accept. The table below adds the 15 CR-0007 rows resolved here but missing from v1's table, including the 12 the reviewer named. The tracker's "Reconcile PA-0021 clause text" is resolved by deliverable 0 (one text). |
| B-C8 | MEDIUM | Accept. § Observations defines RF, TV, KS, SMD, `d`, Exc, S, Sws_val, Excws_val, SUP-O and SUP-R. |
| B-C9 | MEDIUM | Accept. E1 covers the pooled `candidate_pool.csv` (`region ∈ REGIONS`, `state == region`). |
| B-C10 | MEDIUM | Accept. OBS references move to `acceptance_split_obs.json`, so `--calibrate` never changes the gate config's sha. |
| B-C11 | MEDIUM | Accept. Same as A-MED evidence. |
| B-C12 | LOW | Accept: <br>• `:98-102`; <br>• `res_supply_1…8.py` named; <br>• `bb170ea` cited; <br>• `standing_checks` imports numpy/pandas/scipy at call time; <br>• history removed from "Why now". |
| CR-0012-R1 B BLOCKING 1 (`region` missing in negative files) | BLOCKING | CR-0013 keeps E1 strict. CR-0012 v2 adds `region` to the negative outputs (pending list). |
| CR-0012-R1 B MAJOR 4 (window) | MAJOR | Same predicate as the reviewer proposed (in-bounds, floor, nodata ignored). |
| CR-0012-R1 B MEDIUM 8 (constant lists) | MEDIUM | The config constant list must equal CR-0012's manifest list one for one (pending for CR-0012 v2). |

**CR-0007 rows resolved here, missing from the v1 table:**
| id | where in CR-0013 v2 |
|---|---|
| D1-14 | R1/R3/R4 full-row replay; E9 |
| F2-C5 | E11: seed and val fraction from the config |
| F2-C13 | R1/R3 fix the kept set; implementation free |
| F3-D5 | GATE/OBS explicit throughout; clean document |
| E-12 | Deliverable 5 ("before" run on pre-CR files) |
| E-13 | Review is not a deliverable; pre-approval items labelled |
| E-16 | Design rule 3 (no escape) |
| E-17 | Deliverable 0 names this CR's filer; the batch owner is Tracked |
| C7-8 | E8 covers positives |
| F4-Q3 | N/A: clean document |
| FA-Q4 | O9 reports per-class year support until the BUG-0034 CR |
| A-14 | Citations re-verified (`dataset.py:98-102`, `:127` replaced by the pinned `raster_path` definition) |
| A-15 | E1/E11 against config `REGIONS` |
| B-7 | Negative `verify_partition` → E12; windowless → E8 |
| B-12 | Window predicate defined; `WINDOW_PX` in config; `standing_checks` refuses larger `img_size + 2·jitter` |

| version | date | change |
|---|---|---|
| v2 | 2026-09-30 | Round-1 fixes: <br>• named artifacts, E0/E1p, full-row replay; <br>• order-free dedup; normative definitions pinned at `05d788d`; window predicate; <br>• input binding; CLI; <br>• pre-approval deliverables 0–5; <br>• new attacks; OBS file split out. |

## Round 2 (bounded re-review of v2 text, commit 5d51682)
| reviewer | verdict |
|---|---|
| A — attack power | **APPROVE (text)** — all round-1 findings resolved in operative text; interfaces consistent with CR-0012 v2; no new attack passes every gate beyond stated limits 1, 2, 4 |
| B — implementability | REJECT on v2 (2 new BLOCKING) → **APPROVE WITH FOLLOW-UPS on v2.1** (29f388b) |

The script, config and tests (deliverables 2–4) and the first run (5) are
pre-approval and still need their own review once written.

Round-2 reviewer B new findings, applied in **v2.1** (text-only):
| # | sev | concern | disposition |
|---|---|---|---|
| R2-B1 | BLOCKING | A fresh agent given "CR-0013 + `05d788d`" gets CR-0012 **v1** (pool without `gbif_id`, negatives without `region`, no tie-break or canonical order) — full-row R3/R4 and E0 would fail every correct run | **Accept** — rule 4: the implementer gets CR-0012 at the commit where CR-0012 is approved (recorded when it is); CR-0013 re-pinned on any CR-0012 revision; replay written only after CR-0012's text is approved |
| R2-B2 | BLOCKING | E0's "dtypes CR-0012 names" — none are named | **Accept** — E0 reduced to the exact ordered column set (in the config); types constrained by R1–R4 full-row equality |
| R2-L1 | LOW | Swept? owner must be a BUG or CR, not a tracker item | **Accept** — owner: CR-0013 |
| R2-L2 | LOW | "`:304-309` columns plus `region`" is a line reference | **Accept as is** — resolves at the pinned commit; the config carries the column list (R2-B2) |

Reviewer B's v2.1 follow-ups (LOW), applied in **v2.2**:
- Landing order now shows CR-0012 text approval (commit recorded) before
  CR-0013 deliverable 3.
- Deliverable 2a: run the PA-0021 sweep this CR owns.
- Deliverable 2 spells out how E0's column lists are derived.

## Text sign-off (round 2)
Reviewer A: APPROVE (text, v2). Reviewer B: APPROVE WITH FOLLOW-UPS (text,
v2.1). **CR-0013 is not approved yet:** deliverables 0–5 (bookkeeping,
evidence, config, sweep, `acceptance_split.py`, tests, first run) are
pre-approval under §1.1 and must be written and reviewed first; deliverable
3 waits for CR-0012's text approval (rule 4).

## Separate authorship record (rule 4)
- `acceptance_split.py` (deliverables 2–5): fresh agent, transcript id
  `a969037d4098fb0c1`, launched 2026-09-30 with only CR-0013 (HEAD),
  CR-0012 at `29f388b` and the code at `05d788d`. No CR-0012
  implementation existed at launch.
- CR-0012 implementer: fresh agent, transcript id `aee090313522fc4b9`,
  launched 2026-09-30 in an isolated git worktree with CR-0012 at
  `cec1542` and the config; instructed not to read `acceptance_split.py`
  internals or its tests (it may call `standing_checks` by signature).


## Deliverables 0, 1, 2a done (author, 2026-09-30; not yet reviewed, nothing committed)
- **0 — bookkeeping.**
  - `BUG-0033` (falsifiability) is filed. It includes the §2.4 statement
    (E-1): only v3 `1445ccd` and v7 `bb170ea` of CR-0007 can be quoted.
  - The calibration-from-extrema cause is split out as `BUG-0038`, the
    next free id (E-3).
  - `PA-0021` is filed. The text is the draft, plus clause (a) "built by
    someone other than the invariant's author, and recorded so it can be
    re-run" (E-PAa) and clause (f). It extends PA-0016 (E-4).
  - `PA-0021` is filed out of id order, after PA-0022/0023, under its
    reserved id. Nothing is renumbered. This is recorded in its Source
    cell, in BUG-0033 §8 and in the tracker's PA-numbering item.
  - `BUG_LOG.md` has rows for BUG-0033 and BUG-0038..0040.
- **1 — evidence.**
  - `docs/quality/evidence/CR-0013-evidence-manifest.md` lists every
    § Attacks script, its local imports and its scratch-data producers,
    with sha256, attack row and provenance-only labels. `cand.pkl` and
    `pos.pkl` had no producer script, so the inline command that made
    them is quoted verbatim.
  - Round-7 A's 9 scripts were copied byte-identical to
    `docs/quality/evidence/CR-0007-r7/`.
  - `.gitignore` rule 9 was added: `!/docs/quality/evidence/CR-0007-r7/*.py`.
    That is the only allow rule needed; root `*.py` files were already
    allowed.
- **2a — PA-0021 sweep.**
  - Scope: the acceptance tables of CR-0007..0013 and live-code
    thresholds. The live-code enumeration was done by a read-only
    helper agent and spot-verified.
  - Two instances were found:
    - `BUG-0039`: CR-0009 v4 symptom GATEs, owner CR-0009;
    - `BUG-0040`: `check_road_dist.py` RD1/RD4, needs a CR.
  - Superseded texts are noted with no BUG. Runtime input guards are
    classed outside the mechanism.
  - PA-0021's Swept? cell records the result.
- **Open for the user:**
  - BUG-0039's calibration compute;
  - whether a PA is needed for findings lost when a gate moves between
    CRs (BUG-0040 §7);
  - whether runtime guards belong in PA-0021's scope.

## v2.3 dispositions — replay implementer findings F1–F18 (author, 2026-09-30)
Source: `docs/quality/evidence/CR-0013-implementer-findings.md`, from the
separate author at `8501b51`. The author did not read or change
`acceptance_split.py` or its tests; only the config (data) was read.
Each location below is the operative text (PA-0024(a)).

| id | disposition and operative location |
|---|---|
| F1 | **Accept.** CR-0013 rule 4 lists CR-0007 at `6619bdd` (v9 approved) as a source. § Normative definitions adds its §1 names and `verify_partition` rule, and its §2 `region` column. The config still names v8's `COUNTY_POLYGONS`; it is re-pinned to v9's `COUNTY_POLYGONS_YEAR`/`PATH_TEMPLATES["tiger_county"]` by deliverable 5a. |
| F2 | **Accept.** CR-0013 § Config: `manifest_schema` is normative. CR-0012 v2.2 § Split manifest cites it. |
| F3 | **Accept; CR-0012 changes, CR-0007 does not.** CR-0012 v2.2 positives step 6 and Draw: outputs use the config's `columns` lists in order, so `region` is selected from S and placed after `envelope_id`. CR-0013 § Config `columns` states the derivation. E0 stays an ordered-list check. CR-0007 v9 (approved, being implemented) keeps `region` after `spatial_zone` in S. |
| F4 | **Accept.** CR-0013 deliverable 5: every gate FAILs except E1p. E2 and E8 fail substantively; E3/E7/E9/E10 fail on the missing C. |
| F5 | **Accept.** CR-0013 § CLI and report, `--data-root`: required layout, and the symlinked scratch-root composition for a backup. |
| F6 | **Accept.** CR-0013 § Standing subset: file `x_5070`/`y_5070`, bound by digests, checked by R1/R4. The gate-table preamble limits "recomputed" to the full run. |
| F7 | **Accept.** CR-0013 § Normative definitions: all 15 `FEATURE_SPEC` keys, including `nlcd`. |
| F8 | **Accept.** CR-0013 § Normative definitions quotes the `generate_negatives.py:198-199` rule, giving `evh, evt, sclass`. |
| F9 | **Accept in CR-0013; Tracked for CR-0012.** CR-0013 § Normative definitions, "Coordinates". CR-0012's text is not amended for this (v2.2 is limited to F2/F3); tracker item added. |
| F10 | **Accept.** CR-0013 E11 (a)–(e): input listing rule; fallback rasters; running environment; `ast` parse with the eight names plus `STATE_FIPS`, `COUNTY_POLYGONS_YEAR`. |
| F11 | **Accept as an exact GATE** (an exact predicate, not a statistic, so design rule 2 does not apply). CR-0013 § Replay gates: canonical order is required. The code change (NOTE → GATE) is deliverable 5a. |
| F12 | **Accept.** CR-0013 § Config, Environment: adds rasterio, GDAL, geopandas, shapely and pyogrio. The config update is deliverable 5a. The manifest carries the same object (CR-0012 v2.2 § Split manifest). |
| F13 | **Accept.** CR-0013 deliverable 2: no OBS file until `--calibrate`; settings in the config's `obs`. |
| F14 | **Accept.** CR-0013 § Standing subset: signature and test hooks, a single `AcceptanceError`, missing or other-config record refused, `--standing` defaults. |
| F15 | **Implementer's reasonable reading, recorded.** CR-0013 § Observations lists the choices; values are in the config's `obs` section. The rows are non-blocking. |
| F16 | **Accept (a)–(d) as normative readings.** CR-0013 § Normative definitions, "Premises and ties". The (a) block tie-break for CR-0012's text is Tracked with F9. |
| F17 | **Accept.** CR-0013 § Attacks: the positive-`weight` row also fails E0; ×20 is split into a replicated-rows row (E3, R4) and a weight-only row (R4; E10 if written). |
| F18 | **Recorded; no change.** `--emit-reference` behaviour, record sha printed, missing-input reporting, replay staging and bounded-memory validation are the implementer's reasonable readings. The record's evidence copy is written by CR-0012's implementer (CR-0013 § Record). |

| version | date | change |
|---|---|---|
| v2.3 | 2026-09-30 | Implementer findings F1–F18. <br>• Sources: CR-0007 at `6619bdd`; CR-0012 re-pinned to its v2.2 approval commit (to be filled). <br>• Definitions: coordinates, premises and ties; 15 features; envelope rule. <br>• Config: `columns`, `manifest_schema`, environment extended. <br>• Gates and checks: E11 (a)–(e); canonical-order gate; standing details. <br>• Runs: data-root layout; expected-FAIL list. <br>• Deliverable 5a added. |
