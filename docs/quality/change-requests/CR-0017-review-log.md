# CR-0017 review log

Verdicts, concern dispositions and revision history for
`CR-0017-negatives-buffer-domain-edge.md`. The CR states only current
intent (CR-0011 A4).

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 (`b043fb2`, `01e0605`) | A: correctness of diagnosis and fix (fresh agent) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 2 MEDIUM, 4 LOW) |
| 1 | v1 (`01e0605`) | B: implementability, composition, acceptance (fresh agent) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR, 4 MEDIUM, 4 LOW) |
| 2 (bounded, A2) | v2 (`73a08ec`) | A | APPROVE | 0 (1 LOW) |
| 2 (bounded, A2) | v2 (`73a08ec`) | B | APPROVE WITH FOLLOW-UPS | 0 (1 MEDIUM, 1 LOW) |

**Approval.**
- Author and reviewers approved; user pre-authorised (2026-09-30).
- Quorum (CLAUDE.md §1.4): the author and both reviewers who commented.
  A: APPROVE (round 2). B: APPROVE WITH FOLLOW-UPS (round 2).
- No BLOCKING concern was raised in either round.
- The round-2 findings (A8, B11, B12) were applied in v3, after the
  verdicts, as the reviewers suggested. Nothing else changed in v3.

Both reviewers re-derived the fix from the code and data, not from the CR:
- **A** recomputed the 88 / 23 split and the 39/31/18 and 12/6/5 counts
  with its own script. Its 111-key set equals `preregister_keys.csv`.
- **A** checked from the query keys (`sightings.py:58`, `ebird.py:18`) and
  the data (0 of 43,024 raw sightings outside D) that the acquisition
  domain is ME∪NH∪VT.
- **A** confirmed that steps 7–10 act per row, and that a simulated
  regeneration passes MC.
- **B** confirmed the CR-0015 composition at `3add80b`.
- **B** measured the three paths to D (0.0 m difference).
- **B** built five wrong and correct trees for PA-0021(a).

## Round 1: concerns and dispositions
Each correction a reviewer claimed was checked against the code before it
was applied.

| id | sev | concern (short) | disposition | where (v2) |
|---|---|---|---|---|
| A1 = B1 | MAJOR | Deliverable 2's expected result on today's files omits R4. `gate_R4` compares against the replay's own draw (`acceptance_split.py:1104-1107`, `:2040-2054`; verified), so R4 FAILs too. | Accepted and revised. The expected result now says E13, R3 and R4 FAIL. R4 is added to the attack rows "No domain-edge filter" and "every US county". The A5 bullet is corrected. | § Test plan; §3 attack table; § One change per CR |
| B2 | MAJOR | The backup lacks P and B, so MC0 and MC1 would fail a correct run. | Accepted and revised. Deliverable 5 backs up all 20 artifacts, the manifest, the record and the OBS file, mirroring `data/...`. MC0 must pass on the backup. | Deliverable 5 |
| A2 | MEDIUM | PA-0020(ii): negatives leave the edge band, positives do not. The author verified 10 of 4,986 train and 0 of 1,246 val within 300 m. | Accepted and revised. The numbers, a tolerance and the acceptance rationale are stated. It is recorded, not gated. An optional OBS row goes to the tracker (LOW, owner: the deliverable 2 replay author). | §3 Support after the change |
| A3 = B4 | MEDIUM | Nothing controls the refusal window between merging the config change and the new record. | Accepted and revised. Deliverables 2–4 stay on an unmerged branch, and the merge is step 1 of deliverable 6. | § Impact (refusal window); deliverables 2, 3, 6 |
| B3 (+ A6) | MEDIUM (A6 LOW) | MC checks N by keys only, so the "weights ×2" tree passes. MC4's docstring overstates the check. The parts files are not read. | Accepted and revised. `check_must_change.py` v2: retained N lines must be byte-identical (MC3); added rows must equal their new C row on the shared columns, in the same region and cell, with no new cells (MC4); new MC5 checks the parts. Re-run on reviewer B's trees: W5 now FAILs, W2 (correct) PASSes, W4 (wrong replacements) PASSes, which is the stated limit covered by R4. | §3 MC; `mc_wrongtrees.txt`; `mc_selftest.txt` |
| B5 | MEDIUM | There is no failure path if MC fails after the live write. | Accepted and revised. MC runs before `acceptance_split.py` writes the record. On any FAIL: restore from the backup (sha256-verified), record the failure, revert the merge, stop. | Deliverable 6 |
| B6 | MEDIUM | The PA proposal for BUG-0064 is cited but missing. | Accepted. It is in § Proposed bookkeeping rows below. | this log |
| A4 | LOW | D is reached by different CRS paths (via 4326 in the pipeline, direct in the replay). | Accepted and revised. The pipeline builds D from the file CRS straight to EPSG:5070. B's measurement of the three paths is cited. | §2 Domain D; §3 Pre-registration validity |
| A5 = B7 | LOW | The attacks need fixture rows the CR does not specify, and could pass vacuously. | Accepted and revised. Each attack names its required fixture rows, including the thinning pair (straddles the band, in-band member first in the thin order). The test asserts that the rows exist. | §3 attack table |
| A7 | LOW | Stale surplus (119 → 116). Overlap counting in the log is unspecified. Mislabelled in-domain records are not listed as unvalidatable. | Accepted and revised: 116 (and the NonVeg surplus 554); the log prints (a), (b)-only and the overlap; added to § Not validatable. | § Risk; §2; § Test plan |
| B8 | LOW | The `domain_edge` config copies the county pins. | Accepted and revised. It references `paths.county_polygons` by key, and `load_config` refuses any other value. | §3 Config |
| B9 | LOW | There is no test seam for an injected domain. | Accepted and revised: `domain_edge_m(x, y, *, domain=None)`. | §2 Code; § Test plan |
| B10 | LOW | CR-0009 remaining work is 9–12, not 8–12. Facts are restated (18/4,986, 1.802 m, the B1 precondition). The fixture "gets" a non-domain county it already has. `mc_selftest.txt` cites an old HEAD. | Accepted and revised. The CR-0009 range is corrected. The counts and margin are stated once and referenced elsewhere. The attack preamble now says "already has". `mc_selftest.txt` is regenerated for MC v2. The B1 precondition appears in §2 (why) and deliverable 5 (check), and Risk now points to the deliverable. | §4; § Risk; §3 |

## Round 2: concerns and dispositions
Round 2 was bounded (CR-0011 A2).
- **Round-1 concerns:** both reviewers found all of them resolved in the
  operative text.
- **Reviewer A:** rebuilt a faithful regeneration (`tree2`), which passes
  MC v2, and a one-weight mutation (`tree3`), which fails MC3.
- **Reviewer B:** confirmed that every live N row equals its C row as text
  on all 19 shared columns, so MC4 cannot fail a correct regeneration.

| id | sev | concern (short) | disposition | where (v3) |
|---|---|---|---|---|
| A8 | LOW | The support tolerance wording is muddled ("either class"). "Cannot be a label cue" is asserted, not measured. | Accepted and revised: "at most 0.5 % of the positives in each split". The band holds no negatives by design. The cue statement is labelled as the author's unmeasured judgement. | §3 Support after the change |
| B11 | MEDIUM | MC v2 passes W6 (added rows with `label=1` and junk `obs_date`/`coord_uncertainty_m`) and W7 (reordered N). "What fails MC" overstated this. R4 and the order checks catch both in the same run, so it is not BLOCKING. | Accepted and revised; both of B's options were taken in part. MC v3: MC4 requires `label` "0" on added rows, and canonical (lon, lat) order of the combined file. The text now says `obs_date` and `coord_uncertainty_m` on added rows are a stated limit, covered by R4. Verified against the real code: `canonical(sel, NEGATIVE_ORDER)` sorts by (longitude, latitude), and live `negatives_ME.csv` is sorted. Re-run on all 9 trees: W6 and W7 now FAIL; W2 and A's `tree2` PASS; W4 PASSes (the stated limit); the rest FAIL. | §3 MC; `check_must_change.py`; `mc_wrongtrees.txt`; `mc_selftest.txt` |
| B12 | LOW | `regions.py` would hold two readers of the county file. | Accepted and revised. One private helper reads the filtered counties in the file CRS, and both D and `_state_polygons()` use it. The code review of deliverable 3 checks it. | §2 Code |

## Implementation code review
Code review of deliverables 2–4 on the unmerged branch `cr0017-combined`
(diff `666474c..b059624`: pipeline side `ee59d12`, acceptance side
`b059624`). Both reviewers were fresh agents, read-only, and ran tests
and mutants in scratch copies.

| reviewer | head | verdict | blocking |
|---|---|---|---|
| A (independent) | `b059624` | APPROVE WITH FOLLOW-UPS | 0 (1 MEDIUM, 3 LOW, 2 INFO) |
| B (independent) | `b059624` | APPROVE WITH FOLLOW-UPS | 0 (5 LOW) |

**Evidence at `c0d6997`** (`docs/quality/evidence/CR-0017/combined/RUN.txt`):
scratch-tree real-data run of the combined code at `b059624` (clean
tree): acceptance 19/19 GATEs, MC PASS (88 C / 23 N removed, as
pre-registered), run 2 byte-identical to run 1 (the record differs only in
`created_utc`), live `data/` unchanged.

**Approval.** Author sign-off: APPROVE. Author and reviewers approved;
user pre-authorised (2026-09-30). No BLOCKING or MAJOR finding. The branch
stays unmerged until deliverable 6 step 1.

| id | sev | finding (short) | disposition |
|---|---|---|---|
| A F1 | MEDIUM | The acceptance side's inclusive `<= BUFFER_M` at `Replay.domain_edge_mask` (`return e <= b`) and `gate_E13` (`bad = e <= b`) is untested: `<` at either site survives the suite. | Fixed in `c17c30d`: `TestDomainEdgeUnits.test_domain_edge_mask_threshold_inclusive` and `test_gate_e13_threshold_inclusive` (a row at exactly BUFFER_M is dropped / FAILs, BUFFER_M + 1e-6 is kept / passes; stub context, square D). Mutation check in a `git archive` copy with `git init`: unmutated 109/109 OK; `<` at `domain_edge_mask` killed by the first test only; `<` at `gate_E13` killed by the second test only. Test code only; `acceptance_split.py` unchanged. |
| A F2 | LOW | "File CRS straight to 5070, never via 4326" is not observable here (null NAD83→WGS84 transform); an acceptance-side detour survives. | Tracker (`CR-0007-0008-OPEN-ISSUES.md` § CR-0017 implementation code review), owner lead. |
| A F3 | LOW | `regions._ANALYSIS_EPSG` comment claims it is the target of `to_5070`, which still has its own literal. | Fixed in `c17c30d`: comment reworded (used only for D; must equal `to_5070`'s literal target; wiring is CR-0007 (d)) and `tests/test_cr0017.py` `DomainD.test_analysis_epsg_is_the_to_5070_target` pins the equality. No behaviour change. |
| A F4 | LOW | D inherits the cwd-relative county read. | Tracker: added to the existing cwd-resolution item (§ CR-0012 code (20a52c1), owner BUG-0047 CR). Fail-closed (R3). |
| A F5 | INFO | Merging before deliverable 6 would make `standing_checks` refuse training until a new record. | Process note: merge only at deliverable 6 step 1, after deliverable 5's preconditions. |
| A F6 | INFO | CR-0012 §2 step 6 pointer line and `CHANGELOG.md` entry are pending. | Process note: they are deliverable 7. |
| B B-1 | LOW | Pipeline and replay edge distances agree to ~1e-10 m, not bit-exactly, at `edge_m == BUFFER_M` on long diagonals. | Tracker, owner lead. Loud on disagreement (R3/R4); real margin 1.802 m. |
| B B-2 | LOW | Pipeline (project, then union) and replay (dissolve in file CRS, then project) differ on non-noded inputs. | Tracker, owner lead: re-check D equality if the county file changes. Identical on the pinned file. |
| B B-3 | LOW | The `combined/` evidence was untracked (ignored by `.gitignore` `*`). | Resolved by `c0d6997` (force-added `combined/`: scripts, logs, sha256 files, MC outputs, records). |
| B B-4 | LOW | Misleading comment in `test_reference_has_no_row_in_the_edge_band` ("both step-6 rules bite ... separately"). | Fixed in `c17c30d`: comment now points to `TestDomainEdgeUnits.test_step6_drops_rule_a_or_rule_b`. |
| B B-5 | LOW/INFO | CRS-less or non-EPSG NAD83 county file: pipeline accepts, replay refuses (loud). | Tracker, owner lead. File is sha-pinned. |

## Revision history
- **v1** (`b043fb2`): first draft.
- **v1** (`01e0605`): specified against CR-0015 head `3add80b` (lead
  instruction). The NY/MA sibling BUG became placeholder BUG-0064
  (the lead allocates ids).
- **v2**: round-1 dispositions above. Evidence added:
  `mc_wrongtrees.txt` and `reviewB_build_trees.py` (reviewer B's tree
  builder, committed so the PA-0021(a) run can be re-run), and a
  regenerated `mc_selftest.txt`.
- **v3**: round-2 dispositions (A8, B11, B12), with MC at v3. Status
  APPROVED. Evidence: `reviewB_build_trees_r2.py` (W6, W7) and
  `mc_wrongtrees.txt` re-run over 9 trees. Reviewer A's `tree2` and
  `tree3` builder was not committed. It is described above: pool minus
  the 88 rows, a real `draw_region_split`, added rows assembled from the
  new C plus the `gbif_negatives_R` N-only fields; `tree3` is `tree2`
  with one retained VT weight doubled.

## Proposed bookkeeping rows (for deliverable 8; not yet filed)
The author does not edit `BUG_LOG.md` or `PREVENTIVE_ACTIONS.md`. The lead
allocates the BUG-0064 id.

**BUG_LOG.md, BUG-0050 row update:** "... remediation: CR-0017 (pool step 6
also drops candidates within `BUFFER_M` of the sightings' acquisition-domain
edge, ME∪NH∪VT); status FIXED".

**BUG_LOG.md, new row BUG-0064:**
- date: 2026-09-30;
- symptom: the negatives' 300 m buffer is blind at the NY and MA state
  lines, affecting 49 pool candidates and 11 selected negatives;
- root cause: the buffer source ends at the acquisition-domain edge, and
  BUG-0050's evidence took the national border as that edge;
- remediation: CR-0017;
- status: FIXED at CR-0017 deliverable 6.

**BUG-0064 recurrence review (draft).** It matches BUG-0050 / PA-0023
(same mechanism) and BUG-0037.

*Prior-preventive-action failure analysis:*
- **PA-0023's text covers it** ("national or other data-domain border").
- **The failed layer was the check.**
  - BUG-0050's evidence script built its boundary from ME, NH, VT, NY and
    MA counties. That treated the NY and MA state lines as interior,
    although no sighting was acquired there.
  - PA-0020(v) ("trace each input back to its acquisition query and read
    every key in it") was not applied when the border was chosen.
- **Category:** not followed / too implicit. PA-0023 does not say how the
  domain is determined.

**Proposed PA (extends PA-0023; next free PA id at filing).** For a
neighbourhood computation, a source's data domain is the extent its
acquisition query selects: the union of the query's region keys (for
example `stateProvince`, eBird region codes), not the country or the
analysis box.
- A PA-0023 check must derive the domain from the query keys and name the
  query (file:line).
- A check or sweep that assumes data beyond that extent is incomplete.
- Enforcement is by review only (no CI).
- **Swept?:** "no — not yet run; owner: CR-0017 deliverable 8" (PA-0022).
  Scope: every neighbourhood computation over sightings or candidates. The
  known instance is BUG-0051 (the KDE also has the NY and MA edges),
  recorded against BUG-0051.

**PA-0023 Swept? cell addendum:**
- BUG-0050 FIXED (CR-0017);
- NY and MA instance: BUG-0064, FIXED (CR-0017);
- KDE: BUG-0051 (Canada, NY and MA edges), owned by its own CR.

- 2026-09-30 lead: placeholder BUG-NEW-a allocated as **BUG-0064** (BUG-0063 is CR-0015's test-harness PA-0027 finding). The BUG-0064 investigation doc and its BUG_LOG/PA rows are produced with CR-0017's bookkeeping deliverable.
