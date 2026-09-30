# CR-0008 review log

History, verdicts and dispositions for CR-0008. The CR itself states only
current intent (`CLAUDE.md` §1.1, CR-0011 A4).

## Where the history is
- **v1–v7 full text**, including every revision note: commit `bb170ea`
  (`git show bb170ea:docs/quality/change-requests/CR-0008-raster-coverage-nodata.md`).
- **Rounds 1–7 verdicts and dispositions**: copied verbatim below from v7's
  § Review.
- **Round-7 open items**: `docs/quality/CR-0007-0008-OPEN-ISSUES.md`,
  section "CR-0008"; their v8 dispositions are in the table at the end.

## v8 restructuring (2026-09-30)
Under CR-0011 A5 (one change per CR), v7's scope is split three ways:
| part | now in |
|---|---|
| Repair of the 174 existing `tsd`/TreeMap/`tcc` rasters (v7 §1, G0–G3, G6, G8) | **CR-0010** |
| `road_dist` ME/VT regeneration, `_download` atomicity, `TIGER_YEAR`, Canadian-border roads, G7/RD1–RD5 | **new CR, not yet written** (tracker item) |
| Generator and encoder fixes for `tsd`, TreeMap, `tcc`/`nlcd` | **CR-0008 v8** |

v8 writes no raster in `data/`; the generators are exercised only into
scratch directories and compared against CR-0010's gated output.

## § Review

| round | reviewer | verdict | blocking |
|---|---|---|---|
| 1 | raster lane (resumed) | APPROVE WITH CHANGES | 2 |
| 1 | seam (fresh) | REJECT | 4 |
| 2 | seam (resumed) | REJECT | 2 |
| 3 | fresh, whitelist attack | REJECT | 2 |
| 4 | expedited, raster lane | APPROVE WITH CHANGES | 1 |
| 5 | **formal, fresh** | **REJECT** | 3 |
| 6 | **formal, fresh (round 2)** | **REJECT** | 2 |
| 7 (v7) | **formal, fresh** | **REJECT** | 2 |
| 7 (v7) | implementation + §1 compliance (fresh) | **REJECT** | 1 |

**Dispositions.** v4 carried no verdict and no disposition table despite
four prior rounds — a §1.3/§1.4 violation that made quorum uncomputable
and meant no reader could check whether a finding had been dropped.
Every concern from every round is dispositioned below.

| concern | disposition |
|---|---|
| Coverage reference uncomputable for 5 of 6 features | **Accepted** — resolved: the VAT tables make `tsd` derivable; per-feature references settled (§ Coverage). |
| A2/A3 pass a corrupted channel (values doubled; 39 % of grid constant-filled) | **Accepted** — replaced by G1's change-set constraint; A2/A3 demoted to diagnostics. |
| Every figure an 8× decimated sample | **Accepted** — G3, full resolution mandatory. |
| A3's premise false (`tsd` has 0 in-coverage zeros only in 2025) | **Accepted** — per-year counts reported; the guard is G1, not A3. |
| ≥0.99 in the wrong units, on the wrong reference | **Accepted** — G2 requires exactly 1.0000 against the generator's own reference. |
| A4 vacuous under the local-post-process plan | **Accepted** — G4 is a `_clean` unit test plus a real `--src-dir` run. |
| No resource section | **Accepted** — § Disk added; its free-space premise corrected to the measured 16 GB. |
| A1's `nlcd` row measured on the rejected reference | **Accepted** — row removed. |
| **G1 and G2 both consume the repair's mask → vacuous for any mask** | **Accepted** — G0 pins the mask by pre-registered digest and inside-count. A reviewer independently reproduced all nine. |
| **Whole-grid mask → no-op passes vacuously** | **Accepted** — G2′ makes G1 an equality against pre-registered `N_pre`. |
| `road_dist` 52.75 % of ME ungated | **Accepted** — G7, with the finding that a median/p95 gate on a uniform sample passes the broken raster. |
| The "independent" completeness reference is circular | **Accepted** — withdrawn; replaced by three-lineage triangulation. |
| `models.py` encode path omitted | **Accepted** — added to deliverables. |
| `generate_treemap_features.py` has no output-dir flag | **Accepted** — deliverable. |
| `tsd` footprint table printed inside fraction under "outside" heading | **Accepted** — both columns now stated, with the NH sanity check. |
| `-1111` in 6 of 26 tables, not all 26 | **Accepted** — corrected, and the BOM recorded. **The schema count was also wrong and is corrected in v6:** the VATs have **four canonical schemas / six literal header strings**, not "three". Measured over all 52 CSVs (26 vintages × the two extractions): six distinct headers, collapsing to four once the DBF 10-character truncations are canonicalised (`TYPE_CONFI`≡`TYPE_CONFIDENCE`, `SEV_CONFID`≡`SEV_CONFIDENCE`, `DESCRIPTIO`≡`DESCRIPTION`) — 18 + 14 + 18 + 2 files. A round-6 reviewer said "four"; four is right only under canonicalisation, so both forms are stated. Evidence only, not operative. |
| **Withdrawn claim still the operative `tsd` instruction** (rounds 5 **and 6** — third shipment) | **Accepted, and v5's own disposition was false.** v5 recorded this "Accepted — §9.2 rewritten"; **this document has no §9.2** (the string occurs only inside two measurement tables), and the withdrawn claim survived in the **Deliverables** item for `generate_time_since_disturbance.py` — the operative instruction — and in the § Risk level table. Both are now corrected **in place**, stating the sentinel test affirmatively rather than negating it. The disposition-verification failure is itself logged: a disposition must cite a locatable anchor, and the citation must be checked to exist. |
| **Metadata-preserving replace defeats the cache** | **Accepted** — G8 added; `copystat`/`cp -p`/`rsync -a` forbidden; purge made a numbered deliverable. |
| **No verdicts or dispositions recorded** | **Accepted** — this table. |
| G6 omits compression/tiling; ENOSPC mid-repair | **Accepted** — G6 compares the full profile; size check added. |
| `tsd` generator ships unexercised and untestable | **Accepted** — `--out-dir` deliverable and a G4-equivalent. |
| G0 recipes not reproducible next month | **Accepted** — source list and predicate pinned per row. |
| Common-mode cause misstated; mitigation has no power | **Accepted** — cause corrected (three different code paths); the boundary-count mitigation withdrawn as measured powerless. |
| G5 makes the CR order-dependent | **Accepted** — G5 assigned to whichever CR lands second. |
| Unverified reviewer claim propagated | **Accepted** — withdrawn and verified against CR-0007. |
| BUG-0030 does not exist; `nlcd` defect unfiled | **Accepted** — both are deliverables, required before approval. |
| G7 encoding term is a sample max; stratum undefined | **Accepted** — both stated as preconditions. |

**Round 6 dispositions (formal, fresh — REJECT, 2 blocking + 14).** Every
concern below was re-derived against the live files before being applied,
per §1.3; where my check disagreed with the reviewer's, both readings are
stated.

| # | concern | disposition |
|---|---|---|
| 1 | **BLOCKING** — withdrawn `tsd` claim still operative at the Deliverables item and the Risk row; disposition cited a nonexistent §9.2 | **Accepted.** Verified both survivals (the Deliverables one is wrapped across lines, which is why a line-anchored grep for the phrase returns only the Risk row — the same false-negative class as this programme's earlier `grep -v '^\s*#'` error). Both corrected **in place** and stated affirmatively; the false disposition is recorded as such. |
| 2 | **BLOCKING** — `road_dist` nodata placement gated in one direction only, to 4 dp, with G7 structurally blind | **Accepted in full.** **RD5** added; excluded-point count promoted to a gate at 0; **G2 restated as a pixel count**. Baseline independently re-measured on all 30 files: ME/VT exactly 0 nodata, NH 5,656,708 = 0.099165 ≡ the outside-TIGER fraction — so RD5 starts from a verified zero and cannot false-fail. |
| 3 | MAJOR — G5's text still hard-wires "the record set CR-0007 produces" though the round-5 disposition claimed it was reassigned | **Accepted.** Verified the text was unchanged. G5 rewritten to be order-independent, and the stale disposition acknowledged rather than re-asserted. |
| 4 | MAJOR — G8.1's glob misses `patches_*.npy.tmp*`; one 379 MB such file is on disk; "207" is that file miscounted | **Accepted.** Verified: 206 `.npy` + 1 `.tmp` (`patches_61055cdd3521daef.npy.tmp6337`, 379,453,568 B, Sep 29 12:50). Glob, counts and a deletion deliverable all corrected. |
| 5 | MAJOR — G6's "full profile dict" omits `PREDICTOR` (=2 on every file) | **Accepted.** Verified: the profile dict has no `predictor` key while the tag namespace returns `PREDICTOR: '2'`. G6 now compares `tags(ns='IMAGE_STRUCTURE')`. The reviewer's measurement that the consequence is *benign* (files get smaller, no ENOSPC) is recorded too — this is a correctness-of-claim fix, not a data-loss fix, and is not inflated into one. |
| 6 | MAJOR — G8.2's forbidden-idiom list is enumerative and misses `shutil.copy2`, the repo's own year-fanout idiom | **Accepted.** Verified `shutil.copy2` at `generate_treemap_features.py:444`. Clause restated as a **mechanism** against the manifest's recorded pre-repair mtime, with the archive-backup limit declared. |
| 7 | MEDIUM — G4.2's instrument has no power: it injects in-coverage and asserts on G2, which measures outside-coverage | **Accepted.** Assertion moved to the output value **at the injected pixels**, and the injection site made part of the spec. |
| 8 | MEDIUM — G7's truth pins vintage and MTFCC but not the roads' spatial extent (the PA-0018 mechanism, twice logged) | **Accepted.** Precondition 2 added: every TIGER county intersecting grid + `pad_km`, never `STATE_FIPS[region]` — otherwise the verifier reproduces BUG-0023 internally and false-fails the very stratum that carries the signal. |
| 9 | MEDIUM — G1's exemption paragraph said `road_dist` is gated by G2 while the v4→v5 revision note and G2′ said G7. Plus two paragraphs both headed "Two preconditions" (line numbers omitted deliberately: they shift with every revision, which is part of how the round-5 disposition came to cite a section that did not exist) | **Accepted.** Resolved in favour of **G7** (G2 provably cannot gate in-coverage values); both heading collisions renamed and the preconditions numbered. |
| 10 | MEDIUM — "one reference serves every output year" is empirical, not structural | **Accepted.** G0.4 now requires re-verifying `cov_minyear == cov_maxyear` whenever a vintage is added, not merely noting that the digest changed. The reviewer's byte-identical `cov(≤2016) ≡ cov(≤2025)` result is recorded as the reason the single pin is legitimate *today*. |
| 11 | LOW — G2 never says which value counts as nodata | **Accepted.** Specified as the file's declared nodata. The reviewer's trace showing in-repo damage is **nil** is recorded, so the fix is stated as determinacy, not as a closed break. |
| 12 | LOW — G0's `disturbance∩` does not disambiguate the two byte-identical extractions | **Accepted.** Content hashes now part of the pin. Verified the duplication independently: **52 VAT CSVs for 26 vintages**. |
| 13 | LOW — v5's own new text says the VATs have "three" schemas | **Accepted, with a correction to the correction.** The reviewer said four; measured over all 52 CSVs it is **six literal headers / four canonical** once the DBF 10-char truncations are collapsed. Both forms now stated — "four" alone would have been the third wrong count in this row's history. |
| 14 | LOW — count/size inconsistencies: "~170 files", "9.75 GB", "207" | **Accepted.** Independently measured: 204 backup files = **9,717 MiB = 9.49 GiB = 10.19 GB** (so "9.75 GB" was wrong in *both* units); **174** in-scope; 206 + 1. All corrected. |
| 15 | LOW — G8 says nothing about `calibration.json` or the published predictions | **Accepted.** **G8.3** added: no prediction or calibration artifact may be published between this CR and CR-0009, and the existing ones are marked stale. This closes the specific hazard of re-rendering the Errol map as stale-but-plausible. |
| 16 | LOW — the BUG-0023 §6 retroactive question is never discharged in the body | **Accepted.** Answered in the body before Deliverables: this CR **is** the retroactive CR for `bf8d31a`'s `road_dist` change, but it cannot supply pre-implementation review, so §1.1's ordering deviation stays recorded and is not marked closed. |

**Round 6's verified reproductions, recorded because they are the
document's main asset.** An independent reviewer reproduced, from
independently written code: all **nine** G0 digests (and confirmed
`nlcd` year- and recipe-invariant across 10 years × 4 predicates, and
`tiger_at1` insensitive to pad and densification but sensitive only to
`all_touched`); all **twelve** `N_pre` counts on *every* year, not one;
the `tsd` footprint table both columns; `balive > 0` outside NLCD
(11,700 / 4,464 / 2,137); `tcc > 0` outside footprint (exactly 0); the
three-lineage maxima per direction; 36.3 GB uncompressed; 174 in-scope /
204 backup files; the 26 vintages' nodata tags and all 26 VATs; and
**every code citation checked was exact**. Seven attacks failed, including
the sharpest structural one available (per-year `tsd` coverage
divergence). The repair core is closed: G1 ∧ G2′ ∧ G2 determine it
uniquely.

**What six rounds could not break:** the 174-file repair core. Two
successive formal reviewers, working independently, verified all nine G0
digests, all twelve `N_pre` counts and every distributional claim from
their own code, and between them listed fourteen failed attacks. Round 5's
assessment was that v5 was "an editing pass, not a new investigation";
round 6's was that "v5's numbers are trustworthy, which is not a small
thing after six rounds", and that every failure was at a seam the CR had
carved out for itself — the `road_dist` exemptions and the document's own
bookkeeping, not the repair.

**The recurring defect in this document is editorial, not analytical**,
and v6 treats it as the mechanism it is: v3→v4 withdrew the `tsd`
sentinel claim, v4 left it in the deliverable, v5 rewrote the prose and
*still* left the deliverable while recording it fixed against a section
number that does not exist. Three shipments of one defect. The rule
applied here — fold every correction into the body at the point of use,
never into an appendix, and check that a disposition's cited anchor
resolves — is PA-0021's territory and is why this CR cannot be approved
before PA-0021 is written.

**Author sign-off:** withheld. v6 answers round 6's sixteen concerns,
but §1.4's quorum is **arithmetically unmet** — no reviewer has signed
off on any revision, and the last three rounds returned REJECT. Approval
also requires PA-0019/0020/0021 and BUG-0030/0035 to exist (§3.1, §2),
and `PREVENTIVE_ACTIONS.md` ends at PA-0018 today. **This CR is not
approvable until the bookkeeping batch lands and one reviewer signs off
on v6.**

### Round 7 (v7) — two independent fresh reviews, 2026-09-30 — dispositions PENDING

Both reviewers returned **REJECT**. Concerns are recorded here so none can be
dropped (§1.3); **no disposition has been decided yet** — each is `pending`
until the author re-derives it against the live files and rules on it in v8.
"A" = formal lane, "B" = implementation/§1 lane. Evidence scripts:
session scratchpad `cr0008_A/` (A); B used read-only shell checks.

| # | sev | reviewer | concern | disposition |
|---|---|---|---|---|
| 1 | **BLOCKING** | A, B | TreeMap generator fix cannot separate outside-CONUS from non-forest: `data/treemap_raw` has `nodata=None` (`unmask(0)`), so a mask-aware `_clean` has nothing to propagate and `--src-dir data/treemap_raw` re-fabricates 0 outside coverage (VT 2,098,512 / NH 5,654,800 px). G4.2 passes it. Needs an external mask (pinned G0 `nlcd`) applied in the generator; G4.2 must also require G2 == 0 and pixel identity with the repaired file outside the injection. "latent defect is closed by the generator fix" must be withdrawn. | pending — author spot-check: raw ME BALIVE `nodata=None`, 0 % NaN/neg, 68 % zeros (confirmed) |
| 2 | **BLOCKING** | A, B | Approval preconditions unmet: PA-0019/0020/0021 not in `PREVENTIVE_ACTIONS.md` (ends PA-0018); no BUG-0030/0035 draft; sign-off paragraph still says "v6" and misstates §1.4 quorum. | pending |
| 3 | MAJOR | A | `download_treemap.py` deliverable contradicts "one mask" settled decision (a sentinel unmask also marks in-CONUS non-forest → silent Branch B); `:315` `np.clip(arr, 0, None)` clamps a negative sentinel back to 0 and is not named. | pending — `:315` clip confirmed |
| 4 | MAJOR | A | Canadian-border roads: TIGER has no Canadian roads; up to 978,374 ME / 109,251 NH / 281,662 VT in-coverage px (19 positives) may over-read distance; G7's TIGER-only truth is blind by construction. Needs nodata or an accepted-residual disposition in BUG-0023 / PA-0017. | pending |
| 5 | MAJOR | A, B | Cross-CR Impact claims wrong: I17 is OBS in CR-0007 v7 (0.0306, 400 seeds), not a ≤ 0.095 gate at 0.0696; "pool moves by 2 records" is a modelling assumption (real pipeline removes 0); "4 of 3,659 ME" omits VT and is model-based; "either order" measured one order only (CR-0008-first: 140 ME / 717 VT positives with \|err\| > 60 m). G5/I17 hand-off has no reciprocal owner in CR-0007/0009. | pending |
| 6 | MAJOR | B | Approval preconditions (PA-0020 is a CR-0007 deliverable) contradict "independent of CR-0007 … either order". | pending |
| 7 | MAJOR | A, B | Withdrawn/superseded text in operative sections (4th shipment of this class): "must handle **three**" VAT schemas; enumerated `copystat`/`cp -p`/`rsync -a` list in § Disk; "18.4 %" in §2; Test plan's v4 six-field G6, "47.1 %", NH-style spot-check, "81–93 %"; Impact "47.1 % (NH 9.8 %)"; "G2 requires exactly 1.0000"; "Not a blocker now that disk is extended" vs "has not landed". | pending — "three", "18.4 %" confirmed present |
| 8 | MEDIUM | A, B | v7 cites "§ Scope's table" — no such table (it is in § Coverage). | pending — confirmed |
| 9 | MEDIUM | A, B | `tsd` deliverable: `hit` parenthetical says "0 = disturbed-this-year"; raw 0 is VAT Background (covered, undisturbed). §2 vintage set (all 26) vs deliverable (d ≤ Y). | pending |
| 10 | MEDIUM | A | G7 checks one of ten `road_dist` year-copies; require all copies per region byte-identical (true today). | pending — one md5 per region × 10 files confirmed |
| 11 | MEDIUM | B | Encoder sentinel→0 sweep incomplete: `tpa_live_encode`, `tsd_encode`, `treemap_encode`, `road_dist_encode` all map nan/-9999 → 0; `tpa_live_encode` and `tsd_encode` unnamed. | pending |
| 12 | MEDIUM | A, B | PA-0021 clause text cited in two incompatible forms; 0.06 % cross-check and G6 "≤ ~1.2×" are fitted/uncalibrated; RD1/RD2/RD4 thresholds lack null quantiles; GATE/OBS labels missing for G3, G5, cross-check. | pending |
| 13 | MEDIUM | B | PA-0019 required but not applied: no provenance tag on repaired/regenerated files. | pending |
| 14 | MEDIUM | B | Risk table lacks the G8 cache, RD5 over-mask and G8.3 stale-publication risks. | pending |
| 15 | MEDIUM | B | Rounds 1–5 disposition rows are unattributed (27 rows vs 14 blocking findings); tag each with round/reviewer. | pending |
| 16 | MEDIUM | A | Restore rehearsal unordered and has no space (10.19 GB vs ~6–7 GB free); in-place `cp -a` restore reverts the repair and defeats G8.2. | pending |
| 17 | LOW | A, B | Misc: `write_vintage` open is `:294` not `:293`; "G0.3's pinned digest" should be G0.2; "~33 %" vs "25.6 %" ME outside-US; G6 does not cover the 20 regenerated `road_dist` files; VT TIGER counties fetchable (network available) and v7's VT truth skipped 8 counties (result unchanged, 0 diff at 2,261 positives); G8.3 omits `reliability.{csv,png}` and `grouse_ssl_backbone.pth`; CR-0009 still says "9.75 GB"; "9,021 MB" is MiB. | pending |

**Verified again by round 7 (both reviewers, independent code):** all nine G0
digests and inside-counts; all `N_pre` counts every year; nodata inside
coverage = 0 (RD5 baseline); cross-lineage maxima; disk figures (204 files =
10.19 GB); cache 206 + 1 `.tmp`; nearly every code citation. Failed attacks:
aliased/whole-grid mask, per-year `tsd` divergence, nested-vs-outer
disturbance copy, G6 tag loss, stray caches, RD5 false-fail, 0.06 %
false-fail, I17 "6 of 7 bit-identical". **The 174-file repair core survived a
seventh round; every blocking finding is at the generator/re-run seam or in
bookkeeping.**

**Author sign-off (round 7):** withheld — two REJECTs, dispositions pending.


## Round-7 open items — v8 dispositions
| item | disposition in v8 |
|---|---|
| R7-1 TreeMap generator cannot separate outside-CONUS from non-forest | **Resolved** — generator applies the region's NLCD mask (the same reference CR-0010 pins); G4-T requires output == CR-0010's repaired file |
| R7-2 approval preconditions unmet / sign-off stale | **Resolved** — v8 depends on no unwritten PA; only PA-0006/PA-0017 govern it. Sign-off restated below |
| R7-3 `download_treemap.py` mask chain, `:315` clip | **Out of scope, justified** — raw download is an intermediate the model never reads; coverage is resolved once, in the generator. `:315` only affects raw values the mask then overwrites |
| R7-4 Canadian-border roads | **Moved** to the `road_dist` CR |
| R7-5 cross-CR Impact claims (I17, "2 records", landing order) | **Resolved** — v8 changes no data, so it has no effect on CR-0007's record set; claims deleted |
| R7-6 "either order" vs PA-0020 | **Resolved** — PA-0020 no longer cited. Order: after CR-0010 (G4 compares against its output); independent of CR-0007 |
| R7-7 withdrawn text in operative sections | **Resolved** — clean rewrite |
| R7-8 "§ Scope's table" | **Resolved** — deleted |
| R7-9 `tsd` `hit` semantics; vintage set | **Resolved** — `hit` excludes every sentinel; coverage per output year is the intersection over vintages ≤ Y, built in the same stripe loop |
| R7-10 G7 year-copies | **Moved** to the `road_dist` CR |
| R7-11 encoders sentinel→0 | **Resolved** — all four encoders and `qmd_from_balive_tpa` raise on non-finite input; nodata is written by mask after encoding |
| R7-12 PA-0021 exemptions / fitted thresholds | **Resolved** — v8 has no statistical thresholds; every gate is exact equality |
| R7-13 provenance tag | **Resolved** — generators write `GROUSE_COVERAGE` |
| R7-14 risk table | **Resolved** — rewritten for v8 scope |
| R7-15 unattributed dispositions | **Accepted as historical** — the rounds 1–5 table is kept verbatim above; v8 dispositions are attributed |
| R7-16 restore rehearsal | **N/A** — v8 writes no data |
| R7-17 LOW batch | Items tied to repair or `road_dist` moved with them; the rest deleted with the text they referred to |
| CR-0010 B4 guard removal | **Resolved** — deliverable 6 |
| CR-0010 B3 BUG-0030 ownership | **Resolved** — CR-0010 owns BUG-0030; v8 files BUG-0035 only |

## Rounds (v8 onward)
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 8 | v8 | A — correctness (fresh) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR) |
| 8 | v8 | B — implementability + §1 (fresh) | APPROVE WITH FOLLOW-UPS | 0 (4 MAJOR) |

Round-8 findings are recorded in full in the reviewers' reports and will be
dispositioned here in v9 (after CR-0010's implementation, which touches the
same files). Summary: A1 `_clean` placeholder/`bad` per feature vs raising
encoders; A2 `unmask(-1)` on uint8 bands (cast to int16; post-download G2
check); A3 NLCD grid assert must include shape/transform; A4 G9 tag
namespace; A5 guard must see `--out-dir`; A6 `hit` change is cosmetic.
B1 legacy-checkpoint refusal must also match `GROUSE_COVERAGE`; B2 road_dist
carve-out drops densified footprint, BUG-0023 §6 ruling, G7 precondition 2,
excluded-point gate, G6 for regenerated files; B3 encoder/`hit`/`_clean`
defects need BUG records; B4 inaccurate dispositions (R7-17 CR-0009 "9.75
GB", R7-5 "moved" not "resolved", BUG-0035 timing reversal unrecorded);
B5 = A1; B6 `--out-dir` must replace `plan["raster_dir"]`; B7 G4-T exact
command, years 2016/2019/2022, pin `--block-rows 512`; B8 keep tcc guard
until post-download G2 passes; B9 recurrence review scope; B10 flags/tests
on guard removal; B11 A5 justification; B12 R7-15 label.

## Author sign-off
Pending v8 review.
