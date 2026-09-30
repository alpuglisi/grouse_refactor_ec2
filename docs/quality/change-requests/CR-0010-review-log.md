# CR-0010 review log

History, verdicts and dispositions for CR-0010. The CR itself states only
current intent; everything about how it got there lives here.

## Lineage
Split from CR-0008 on 2026-09-30. The repair core (CR-0008 §1, G0–G3, G6,
G8) was reviewed across CR-0008 rounds 1–7; see CR-0008 § Review. No round
found a break in it. Round 7's two reviewers again reproduced all G0
digests and `N_pre` counts from independent code.

Round-7 concerns carried into CR-0010 v1:
| CR-0008 R7 | how v1 handles it |
|---|---|
| R7-7 stale text (G6 six-field set, 47.1 %, "9.75 GB", enumerated idiom list) | Clean rewrite; each fact stated once |
| R7-12 fitted 0.06 % and G6 1.2× used as tolerances | Both are OBS (X1, X2) |
| R7-13 no provenance tag | Rule 4 |
| R7-16 restore rehearsal has no order or space | Single-file scratch rehearsal before the repair |
| R7-17 "9,021 MB" is MiB | Stated as 9,020 MiB with bytes |
| R7-1/R7-3 generators would re-fabricate | Out of scope (CR-0008); rule 5 guard prevents silent overwrite in the meantime |
| R7-5/R7-6 cross-CR I17 hand-off | Not needed: `road_dist` excluded and no positive centre value changes |

## Rounds
| round | version | reviewer | verdict | blocking |
|---|---|---|---|---|
| 1 | v1 | B — implementability + §1 (fresh) | APPROVE WITH FOLLOW-UPS | 0 (3 MAJOR) |
| 1 | v1 | A — correctness (fresh) | APPROVE WITH FOLLOW-UPS | 0 (0 MAJOR) |
| 2 (bounded) | v3 | A — correctness | **APPROVE** — A1–A8 resolved; no new blocking | 0 |
| 2 (bounded) | v3 | B — implementability | **APPROVE WITH FOLLOW-UPS** — B1–B7 resolved; no new blocking | 0 |

## Dispositions
Round 1, reviewer B. Checked against the live system before accepting.
All seven applied in **v2** (2026-09-30, at the user's request, before
reviewer A reported). Reviewer A is reviewing v1; each A finding will be
checked against v2 before disposition, and any already resolved by v2 is
recorded as such.

| # | sev | concern | disposition |
|---|---|---|---|
| B1 | MAJOR | Rule 5 guard: TreeMap `copy2` year fan-out (`generate_treemap_features.py:444-448`) reads no tags; an untagged earlier representative year would be generated and then `copy2`'d over tagged repaired years. tsd opens all years `"w"` together at `:293-295`; tcc must check before download. | **Accept** — verified `copy2` loop. v2 lists every write site (tsd pre-open check on all target years; TreeMap `:294` path and every `copy2` destination; tcc before `build_raster`) plus a unit test on the `copy2` path. |
| B2 | MAJOR | Impact's "model already handles nodata through validity channels" is false for the default checkpoints: no `missing_mask` in config → decoded False → NaN fed as 0 (`models.py:1122-1123`); out-of-coverage `tsd` becomes "disturbed this year". | **Accept** — verified both `grouse_single_best.pth` copies lack `missing_mask`. v2 corrects Impact: checkpoints without `missing_mask` are invalid on repaired data until CR-0009; `predict.py`/`calibrate.py` warn-and-refuse when such a checkpoint reads a `GROUSE_REPAIR`-tagged file. |
| B3 | MAJOR | Deliverable 10 skips §2/§4/§3.5 bookkeeping for BUG-0030 (recurrence review vs PA-0017, prior-PA failure analysis, PA-0017 Swept? cell); BUG-0030 claimed by CR-0006, CR-0008 and CR-0010. | **Accept** — v2 deliverable 10 includes the full bookkeeping; CR-0010 becomes sole owner of BUG-0030; CR-0008's claim moved to the open-issues tracker for removal in its v8. |
| B4 | MEDIUM | CR-0008 has no deliverable to remove the guard. | **Accept** — added to open-issues tracker (owner: CR-0008 v8). |
| B5 | MEDIUM | G8.3 is not scriptable. | **Accept** — v2 makes G8.3 a process gate checked by presence of the stale markers. |
| B6 | LOW | Backup path unnamed (in-tree copy would match `grouse_data.py:250` globs); checker needs a subset/scratch mode; `docs/quality/evidence/` missing. | **Accept** — v2 names a backup path outside `data/landfire/`, adds `--files`/`--root` to the checker, creates the directory. |
| B7 | LOW | Disk units: 16,668,200,960 B free → 7.21 GB after backup. | **Accept** — corrected in v2. |

Round 1, reviewer A (reviewed v1; checked against v2 before disposition).
Reproduced independently: all file counts and bytes; all 6 G0 pins in all
three regions; `nlcd` digest year-invariant; `cov(≤2016) == cov(all 26)`
in every region; `N_pre` for all 174 files; 0 pre-existing `-9999` inside
the masks. No attack produced wrong pixel values past the gates.

| # | sev | concern | disposition |
|---|---|---|---|
| A1 | MEDIUM | No gate checks the provenance tag; an untagged repair passes and disables the guard. Guard untested. | **Accept** — v3 adds G7 (tag and digest on every file) and a per-generator refusal test. Also noted: guard must check before any `"w"` open (already in v2 rule 5; reviewer's `:287-289` cite is the source opens — the output opens are `:293-295`, verified). |
| A2 | LOW-MED | Checker file set unspecified; a glob could skip a missing file. | **Accept** — v3 F1. |
| A3 | LOW | Manifest origin unspecified; a corrupt backup would pass G1 against itself. | **Accept** — v3: hash originals before copying, commit, B0 compares backup to them. |
| A4 | LOW | Nothing checks out-of-scope files are untouched. | **Accept** — v3 F2. |
| A5 | LOW | G6 misses overviews, mask flags, band tags, sidecars. | **Accept** — v3 G6 extended. |
| A6 | LOW | ∩ mask also blanks real later-vintage readings (VT 2023: 3,331 px) and 1–2 px TreeMap bleed. | **Accept** — v3 states this as a deliberate conservative choice (rule 1). |
| A7 | LOW | `tsd` mask warp method unnamed. | **Accept** — v3 names WarpedVRT nearest, default error threshold. |
| A8 | LOW | G8.3 not mechanical; `data/maps/` missing. | **Already resolved in v2** (process gate); **Accept** `data/maps/` in v3. |

Round 2 follow-ups (reviewer B):
| # | sev | concern | disposition |
|---|---|---|---|
| B8 | LOW | CR-0006 still claims BUG-0030 (`:615`). | **Tracked** — open-issues tracker item "CR-0006: drop BUG-0030 creation". |
| B9 | LOW | Rule 5 says "before any download starts" but the tcc table row said "before `build_raster`", which runs per year. | **Accept** — table row clarified in v3 (text-only): every year's path checked before the first `build_raster` call. |

## Versions
| version | date | change |
|---|---|---|
| v1 | 2026-09-30 | Split from CR-0008 |
| v3 | 2026-09-30 | Reviewer A: G7 tag gate, F1 file set, F2 out-of-scope files, B0 against original hashes, G6 extended, conservative-mask statement, warp method named, `data/maps/` stale marker, generator refusal tests. |
| v2 | 2026-09-30 | B1: guard covers every write site incl. `copy2` fan-out. B2: rule 6 refuses `missing_mask=False` checkpoints on repaired rasters; Impact corrected. B3: full BUG-0030 bookkeeping; sole owner. B5: G8.3 is a process gate. B6: backup path outside `data/landfire/`; checker `--root`/`--files`; evidence dir. B7: disk 7.21 GB. |

## Quorum (§1.4)
Reviewer A: APPROVE (v3). Reviewer B: APPROVE WITH FOLLOW-UPS (v3).
Author: **signed off** — user instructed implementation 2026-09-30. **CR-0010 APPROVED (v3).**

## Implementation record (2026-09-30)
- Rehearsal (VT_2025_tsd, scratch): all gates pass; restore reproduces the
  original hash. `docs/quality/evidence/CR-0010-rehearsal.txt`.
- Manifests of 174 originals + 168 other rasters committed before any data
  change (`ec1470a`); backup verified on separate inodes.
- Repair: 174/174 files; every region's masks matched the pins first.
- Full check: 1,145 rows, 0 gate failures; then G8.1 after the purge (207
  `patches_*` removed) and G8.3 stale markers.
- **Correction found by X3:** v3's Impact said "0 positives have a centre
  pixel outside any in-scope mask". On the *current* record set 1 NH
  training positive's centre is outside the `tsd` (disturbance∩) mask; the
  "0" was a round-7 measurement on CR-0007's post-partition record set.
  Impact corrected in place; no gate affected.
- CR-0008 G4 independently regenerated 15 of the repaired files with the
  fixed generators: pixel-identical.
