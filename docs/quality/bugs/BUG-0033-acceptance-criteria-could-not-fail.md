# BUG-0033: Acceptance criteria were accepted as evidence without being shown able to fail

Filed 2026-09-30 by CR-0013's author, as CR-0013 deliverable 0
(bookkeeping only). Sources:
- CR-0007 v7's "Confirm BUG-0033 is filed" deliverable (`bb170ea`);
- v3's "Create BUG-0033" deliverable (`1445ccd`);
- the break history in `CR-0007-review-log.md`;
- the v8/v9 dispositions E-1, E-3, E-4, E-PAa, E-18 and FA-Q3.

**Scope of this bug.** Round-3 reviewer E (E-3) found that v7's BUG-0033
bundled two root causes. This bug keeps one of them: **falsifiability**,
meaning criteria that could not fail on the defect they existed to catch.
It also takes the rule E called orphaned, PA-0021(d): a gate whose failure
mode is "record a justification" cannot fail either. The other root
cause, **calibration from extrema**, is split out as BUG-0038.

## 1. Description
The acceptance layers of CR-0006, CR-0007 and CR-0008 were built from
criteria that passed the intended pipeline and failed today's pre-CR
data. Nobody showed that any criterion failed a pipeline that was wrong
in the way it existed to catch. Reviewers repeatedly built such
pipelines, and every gate stayed green.

The shapes were:
- a criterion that restated another criterion, so it was identically
  satisfied;
- a reference read from the pipeline's own bookkeeping, not recomputed;
- sets of "violation count == 0" predicates, which a deletion satisfies;
- statistics whose record set (class, subset or null) was left unnamed,
  so they were silently scoped away from the attack;
- gates whose failure could be answered by a written justification.

## 2. Where encountered
- **CR-0006** (v2 → v3): its acceptance criteria "failed three times in
  three different ways" (CR-0006 at `1445ccd`, header). A v2 gate was
  anchored on `evt` nodata and looped only `("ME","NH")`.
- **CR-0007**, v1–v7 acceptance layer:
  - ten breaks across six revisions by rounds 1–6 (reviewers D, F, H,
    Formal A, Formal C);
  - round 7 found two more (A-1, A-2) and the footing defect A-6
    (`CR-0007-review-log.md`, § Rounds and § Concerns).
- **CR-0008** v1–v7: four breaks and seven review rounds (CR-0007 v3's
  BUG-0033 deliverable). v7's fitted cross-check and G6 are counted under
  BUG-0038.
- Found in review, never observed running. `CLAUDE.md` §2 counts it: "A
  defect found in review counts, even if never observed running."

## 3. What it caused to fail
- CR-0007 was rejected in rounds 2, 3 (F, H), 5, 6 and 7. Every one of
  those rejections was a break in the acceptance layer, and the CR had to
  be split three ways (v8: CR-0007 / CR-0012 / CR-0013).
- Had any version been approved, a pipeline that leaks train/val across
  regions could have been accepted as fixed. So could one that
  concentrates validation on the densest blocks, or skews negatives into
  one state or one half of a state. That is the defect class the CRs
  existed to remove (BUG-0027, BUG-0029).
- CR-0008 and CR-0009 cited "PA-0021" as governing although it did not
  exist (FA-Q3, FC-C7). Their own acceptance designs therefore rested on
  a rule nobody could check.

## 4. What the defect was
**§2.4 statement (E-1).** `CLAUDE.md` §2.4 requires the faulty text to be
quoted verbatim. Only two versions of the faulty CR-0007 text can be
quoted:
- **v3** at `1445ccd` (its header reads "REVISED (v2)", but
  `CR-0007-review-log.md` shows it is v3);
- **v7** at `bb170ea`.

**v1, v2, v4, v5 and v6 were overwritten in place before any commit and
cannot be recovered** (`CR-0007-review-log.md` § Where the history is).
Their faulty criteria are known only from the reviewers' reports and from
v7's revision notes. The quotes below are all from v3 or v7. Where a
criterion belongs to an unrecoverable version, the quote is a later
version's own description of it, and says so. CR-0008 v1–v7 exist only
as the v7 state at `bb170ea`.

**Shape 1: a criterion identically true given another criterion.**
v3 describes its own v1 criterion (d) (`1445ccd`, §6 "`train.py` — standing assertions"):
> v1 used a per-region comparison of the two classes' `state`
> histograms at ≤0.5 pp. That is **identically zero given (a)** — a
> re-test of (a), not a support check — and a reviewer passed it while
> drawing every negative from the southern half of each state.

**Shape 2: a reference read from the artifact under test.**
v3 (`1445ccd`, §6, assertion (c)) describes the column form it replaced:
> `longitude`/`latitude` against `BLOCK_ORIGIN_5070` and
> `BLOCK_SIZE_M`, never from the recorded `block_id` column.** The
> column form is a tautology: `split` is derived as a pure function of
> the recorded id, so grouping by it returns 0 for any pipeline,
> correct or not.

v7 kept the other half of this shape. I14 was a provenance gate that
checked the pipeline against its own recorded manifest (`bb170ea`, § Test
plan):
> | I14 | GATE | provenance and canonical form — see its own section; **not** a correctness gate | …

**Shape 3: only "violation count == 0" rows, monotone under deletion.**
v3 (`1445ccd`, § Test plan, invariant table):
> | I1 | `cKDTree(pooled positives).query_pairs(regions.MIN_SPACING_M)` on EPSG:5070 coords reprojected from lon/lat | **1690** | 0 |
> | I2 | block ids **recomputed** from lon/lat against `BLOCK_ORIGIN_5070`/`BLOCK_SIZE_M`; count blocks holding both a train and a val record, either class | **882** | 0 |
> | I4 | 5 dp coordinate key, per class, set intersection of pooled train and pooled val | **522 pos / 0 neg** | 0 / 0 |

A pipeline that drops half the records passes all of these. The v3
deliverable itself names this shape: "enumerated outcomes where a
change-set constraint was needed".

**Shape 4: the record set left unnamed, and so scoped away from the
attack.** v7 records Formal A's Break 2 against v5 (`bb170ea`, § Review,
"Break 2"):
> The root cause was that **I15–I19 never said which record set they run
> over**, and the calibration silently fixed it to positives: I16's null
> was measured on the 3,861 positive-occupied blocks, so the 5,621
> positive-free blocks were outside every gate.

v7's own header states the same shape one level up:
> *every acceptance row touching the negative class measures a **count**
> (I8) or a **location** (I2, I3, I16b, I19); none measures
> **composition** — I15 through I18 are all scoped "positives only".*

**Shape 5: a gate that fails into a written justification.**
v3 (`1445ccd`, § Test plan, invariant table):
> | I7 | validation fraction, **per class and per region** | — | 20 % ± 1 pp pooled per class; per-region spread recorded, and justified if > ±3 pp |
> | I13 | availability sample size == `n_samples` per region per feature after the §2 clip; judgeable-envelope count per region | NH 50, VT 48 (at `MIN_AVAIL_BG = 15`) | unchanged or justified |

## 5. Root cause analysis (Five Whys)
1. **Why did ten constructed pipelines pass CR-0007's acceptance
   layer?** Each gate had been checked only against today's data (which
   it failed) and the intended pipeline (which it passed). Nobody had
   run it on a pipeline that was wrong in the way it targeted. The
   failing pipelines were built by reviewers, after the text was
   written.
2. **Why was passing the intended output and failing today's data
   taken as enough?** Those two runs are the author's own check. They
   answer "does the gate accept the fix?", not "does the gate reject
   the defect?". A zero-violation predicate, or a restatement of another
   gate, looks self-evidently correct from the author's side.
3. **Why did each break get patched rather than prevent the next
   one?** Each revision fixed the specific break: added I14/I15, then
   Moran's I, then per-region I19, then I16b. It did not change how a
   gate is admitted. The next reviewer found the next unconstrained
   axis: class, subset, null, composition or supply.
4. **Why was there no admission rule?** `PREVENTIVE_ACTIONS.md` has
   PA-0016, which forbids stating a **cause** without a check that could
   have falsified it, but only for diagnosing a reported wrong output.
   No rule applied that requirement to **accepting a fix**. The draft
   PA-0021 was cited by CR-0007, CR-0008 and CR-0009 from round 3 on, but
   no CR filed it. It stayed an unfiled draft (FA-Q3, FC-C7; round-7
   B-8). A rule that does not exist cannot be consulted (`CLAUDE.md`
   §3.2).
5. **Root cause:** the QMS had no standing rule that an acceptance
   criterion counts as evidence only if it has been shown able to fail.
   That means shown failing on a constructed pipeline wrong in the way
   it targets, with a reference independent of the change and with a
   constraint on what the change may do. So gate authoring stopped at
   "passes the fix", and reviewers were the only falsification step.

## 6. Corrective action
- **PA-0021 filed** (this record; § 8). It carries clauses (a)–(f) and
  extends PA-0016.
- **CR-0013** (text signed off by both round-2 reviewers; pre-approval
  deliverables in progress) replaces CR-0007 v7's acceptance layer:
  - every GATE is an exact predicate or an independent full-row replay
    (E0–E12, R1–R4), with the reference recomputed and never read from
    the artifact (design rule 1, PA-0021(e));
  - the replay and exact cardinalities fail a no-op and a deletion
    (PA-0021(b));
  - every recorded break is a re-runnable attack row, built by reviewers
    (§ Attacks; deliverables 1 and 4; PA-0021(a));
  - there is no escape mode (design rule 3; PA-0021(d));
  - each OBS names its class, subset, pooling and null (PA-0021(f)).
- **CR-0007 v8/v9** keeps only exact checks P1–P8, with a no-op and a
  deletion shown failing (`tests/test_check_partition.py`). **CR-0008 v8+**
  and **CR-0010** have only exact gates, and CR-0010's G2′ is a
  must-change count.
- **Does this address the root cause?** Yes. The root cause is a missing
  admission rule, and PA-0021 is that rule. CR-0013 applies it to the
  layer that failed. The PA-0021 sweep (CR-0013 deliverable 2a) applies
  it to every other acceptance table and to live-code thresholds.
- **Status:** OPEN until CR-0013 deliverables 3–5 pass (the attack suite
  shows every recorded break failing its gate).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` (BUG-0001..0037) and `PREVENTIVE_ACTIONS.md`
(PA-0001..0018, 0022, 0023) for:
- an acceptance, verification, gate or threshold defect;
- a claim treated as established without a check that could have
  falsified it.

Findings:
- **BUG-0022 / PA-0016: same mechanism, earlier phase.** A cause was
  asserted without a falsifying check. BUG-0033 is a fix accepted
  without a failing check.
- **BUG-0014 / PA-0013 (related, different mechanism).** A fix was
  verified only against the call sites its own investigation quoted.
  That is a verification scoped to the author's own view, but for a
  code sweep, not for an acceptance gate.
- **BUG-0019 / PA-0015 (related).** A process step was recorded as done
  but never actually run. That is visibility, not falsifiability.
- No earlier acceptance-gate bug exists.

**Prior-preventive-action failure analysis (PA-0016).** PA-0016 was filed
on 2026-09-29, before CR-0006 v2/v3 and every CR-0007 revision. It did
not prevent BUG-0033 because it is **too narrow and at the wrong layer**.
Its trigger is "a wrong output is reported", and its clauses govern
stating a cause. Designing the acceptance criteria for a fix never
triggers it. It was also **not enforced**: nothing checks a CR's
acceptance table against it.

The draft PA-0021 was a second, informal barrier. It failed because it
was **not filed**. Three CRs quoted it and each assumed another would
file it (v7 deliverable: "No BUG doc exists for it and no CR files one —
each assumed another would").

So the new rule **extends PA-0016** from diagnosis to acceptance, rather
than restating it (§4.3). It has an owned sweep (CR-0013 deliverable 2a),
per PA-0022.

## 8. Preventive action
**PA-0021** (`PREVENTIVE_ACTIONS.md`). It extends PA-0016. Clauses (a),
(b), (d), (e) and (f) derive from this bug; clause (c) derives from
BUG-0038.
- **Mechanical enforcement (§3.4):** partial. CR-0013's attack suite
  (`tests/test_acceptance_split.py`) enforces (a) for the split and draw
  gates. No CI exists, so for other CRs enforcement is reviewer checking
  only (`CLAUDE.md` project notes).
- **Sweep:** CR-0013 deliverable 2a; the result is recorded in PA-0021's
  Swept? cell. It found BUG-0039 and BUG-0040.
- **Numbering:** PA-0021 is filed after PA-0022 and PA-0023, with no
  renumbering. PA-0019 and PA-0020 remain drafts. PA-0022's row reserved
  PA-0019–0021 for this batch, and CR-0008 B14 recorded that reservation
  as an exception to creation-order numbering. The tracker's
  PA-numbering item records it (`docs/quality/CR-0007-0008-OPEN-ISSUES.md`).
