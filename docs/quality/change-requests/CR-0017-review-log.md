# CR-0017 review log

Verdicts, concern dispositions and revision history for
`CR-0017-negatives-buffer-domain-edge.md`. The CR states only current
intent (CR-0011 A4).

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 (`b043fb2`, `01e0605`) | A: correctness of diagnosis and fix (fresh agent) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 2 MEDIUM, 4 LOW) |
| 1 | v1 (`01e0605`) | B: implementability, composition, acceptance (fresh agent) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR, 4 MEDIUM, 4 LOW) |

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
| B6 | MEDIUM | The PA proposal for BUG-NEW-a is cited but missing. | Accepted. It is in § Proposed bookkeeping rows below. | this log |
| A4 | LOW | D is reached by different CRS paths (via 4326 in the pipeline, direct in the replay). | Accepted and revised. The pipeline builds D from the file CRS straight to EPSG:5070. B's measurement of the three paths is cited. | §2 Domain D; §3 Pre-registration validity |
| A5 = B7 | LOW | The attacks need fixture rows the CR does not specify, and could pass vacuously. | Accepted and revised. Each attack names its required fixture rows, including the thinning pair (straddles the band, in-band member first in the thin order). The test asserts that the rows exist. | §3 attack table |
| A7 | LOW | Stale surplus (119 → 116). Overlap counting in the log is unspecified. Mislabelled in-domain records are not listed as unvalidatable. | Accepted and revised: 116 (and the NonVeg surplus 554); the log prints (a), (b)-only and the overlap; added to § Not validatable. | § Risk; §2; § Test plan |
| B8 | LOW | The `domain_edge` config copies the county pins. | Accepted and revised. It references `paths.county_polygons` by key, and `load_config` refuses any other value. | §3 Config |
| B9 | LOW | There is no test seam for an injected domain. | Accepted and revised: `domain_edge_m(x, y, *, domain=None)`. | §2 Code; § Test plan |
| B10 | LOW | CR-0009 remaining work is 9–12, not 8–12. Facts are restated (18/4,986, 1.802 m, the B1 precondition). The fixture "gets" a non-domain county it already has. `mc_selftest.txt` cites an old HEAD. | Accepted and revised. The CR-0009 range is corrected. The counts and margin are stated once and referenced elsewhere. The attack preamble now says "already has". `mc_selftest.txt` is regenerated for MC v2. The B1 precondition appears in §2 (why) and deliverable 5 (check), and Risk now points to the deliverable. | §4; § Risk; §3 |

## Revision history
- **v1** (`b043fb2`): first draft.
- **v1** (`01e0605`): specified against CR-0015 head `3add80b` (lead
  instruction). The NY/MA sibling BUG became placeholder BUG-NEW-a
  (the lead allocates ids).
- **v2**: round-1 dispositions above. Evidence added:
  `mc_wrongtrees.txt` and `reviewB_build_trees.py` (reviewer B's tree
  builder, committed so the PA-0021(a) run can be re-run), and a
  regenerated `mc_selftest.txt`.

## Proposed bookkeeping rows (for deliverable 8; not yet filed)
The author does not edit `BUG_LOG.md` or `PREVENTIVE_ACTIONS.md`. The lead
allocates the BUG-NEW-a id.

**BUG_LOG.md, BUG-0050 row update:** "... remediation: CR-0017 (pool step 6
also drops candidates within `BUFFER_M` of the sightings' acquisition-domain
edge, ME∪NH∪VT); status FIXED".

**BUG_LOG.md, new row BUG-NEW-a:**
- date: 2026-09-30;
- symptom: the negatives' 300 m buffer is blind at the NY and MA state
  lines, affecting 49 pool candidates and 11 selected negatives;
- root cause: the buffer source ends at the acquisition-domain edge, and
  BUG-0050's evidence took the national border as that edge;
- remediation: CR-0017;
- status: FIXED at CR-0017 deliverable 6.

**BUG-NEW-a recurrence review (draft).** It matches BUG-0050 / PA-0023
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
- NY and MA instance: BUG-NEW-a, FIXED (CR-0017);
- KDE: BUG-0051 (Canada, NY and MA edges), owned by its own CR.
