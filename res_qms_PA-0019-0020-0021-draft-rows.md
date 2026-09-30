# DRAFT rows for `docs/quality/PREVENTIVE_ACTIONS.md` — PA-0019, PA-0020, PA-0021

> Research draft (2026-09-30). **Nothing in `docs/quality/` was modified.**
> Paste these three rows at the end of `PREVENTIVE_ACTIONS.md`'s table, in
> id order, when the owning CRs land (see filing order at the bottom).
> Column order is the existing one: `| ID | Rule | Swept? | Source |`.

---

## PA-0019 — provenance inside the artifact (supersedes PA-0014)

| ID | Rule | Swept? | Source |
|----|------|--------|--------|
| PA-0019 | **Supersedes PA-0014**, extending it from "duplicate scripts" to any non-interchangeable producers. Any mutable output path that can be written by producers whose outputs are not interchangeable — different scripts, **or the same script run with different inputs, checkpoints, flags, vintages or parameters** — must carry a marker of what produced it **inside the artifact itself**: file/raster tags, an embedded header, a written manifest, or a sidecar keyed to the artifact. For a run artifact (a map, a metric table, a report, a checkpoint) the marker must name every input that changes its values. A discriminating filename, a `print` to stdout, or a terminal log does **not** satisfy this; neither does metadata that identifies the producer's *shape* but not the *run* (a checkpoint recording architecture while two different runs carry byte-identical configs). Where an existing artifact cannot yet carry a marker, add a loud runtime warning until it can (PA-0014's stopgap, retained, not watered down). | yes — read-only code/artifact pass, 2026-09-30, scoped to every fixed output path in `PATH_TEMPLATES` and every `to_csv` / `rasterio.open(...,"w")` / `json.dump` / `torch.save` target: `data/calibration/calibration.json` **conformant** (carries `model_path`, `fitted_at`, `regions`, `features`, `flip_tta`, `loss`, `n_points` — the model of what this rule wants); `data/predictions/*_suitability.tif|.kmz` defective (BUG-0028, no `update_tags` anywhere in `predict.py`); `*.pth` / `*.pth.resume` defective — **new finding, BUG-0036 proposed**: `model_handler._wrap_checkpoint:464-478` stores architecture geometry only, and `bce.pth` / `gap3.pth` carry byte-identical `config` dicts while producing different maps; `data/pipeline/*.csv` + `data/negatives/*.csv` rewritten in place with no parameter manifest — **BUG-0037 proposed**, partially closed by CR-0007's I12; `data/landfire/{region}_{year}_{feature}.tif` written in `"w"` mode by three generators plus two legacy copies (CR-0007 §4, CR-0008 deliverables); `bin_tuning_{region}.csv` = BUG-0016, stopgap warning only, marker still not in the artifact. Remediation pending under BUG-0028 / BUG-0036 / BUG-0037. | BUG-0028 |

PA-0014's existing row must additionally be annotated **"Superseded by
PA-0019"** per `CLAUDE.md` §3.6. Note that CR-0007 separately edits
PA-0014's **Swept?** cell (BUG-0031, the `legacy/audit.py` omission) —
same row, different cell; the two edits must be sequenced, not merged.

---

## PA-0020 — per-class dataset-defining filters, on every axis

| ID | Rule | Swept? | Source |
|----|------|--------|--------|
| PA-0020 | Extends PA-0018 from spatial *computations* to the **acquisition and selection** of the data they consume, and **off the geographic axis onto every axis**. (i) Any parameter that decides which records enter a dataset — a remote API query key (`stateProvince`, `country`, `year`, `taxonKey`, an admin code), a download box, a year floor, a precision/quality threshold, a source choice, a file-per-state naming convention — is part of the computation downstream of it, and must use the same extent, epoch and source set as everything its output will be combined with. (ii) Where one dataset's classes or strata are acquired or selected separately (positives vs negatives, two sources, two vintages), their **supports must be compared explicitly on every axis any such parameter acts on** — space, time, source, precision, taxon — and a divergence beyond a stated tolerance must fail or warn **at dataset-build time**. (iii) **Equal record counts are not evidence of matching support**; where the counts are equal by construction (a 1:1 sampler) they are evidence of nothing. (iv) A filter whose *predicate* is applied to both classes can still have a per-class *effect* — `train.py`'s `filter_by_year_gap` drops 23.59 % of positives and 0.00 % of negatives — so the rule is on the **support**, never on the symmetry of the predicate. (v) When sweeping for PA-0017 / PA-0018 / PA-0020 instances, trace each input back to its acquisition query and read **every key in it**, not only the geographic ones. | yes — read-only pass, 2026-09-30, scoped to every acquisition/selection parameter applied to one class and not the other, on any axis: **live** — year floors 2016 (`sightings.py:21`, `ebird.py:22`) vs 2020 (`get_negatives.py:227-228`) = BUG-0034, measured (1,973 / 23.59 % vs 0 / 0.00 %, vintage→label AUC 0.6365, `calibration.json` `val_prevalence` 0.4318 against a documented 0.5000); box-vs-`stateProvince` = BUG-0029, measured. **Latent** — `MAX_COORD_UNCERTAINTY_M` (`generate_negatives.py:159`, negatives only) is inert: `coord_uncertainty_m` non-null in **0 of 265,212** candidate rows. **Source-axis asymmetry, undiagnosed** — positives come from two acquisition paths (GBIF predicate download `sightings.py:56` + eBird API `ebird.py`), negatives from one; also the two classes' geographic filters are *different code shapes* (a GBIF `{"type":"in","key":"STATE_PROVINCE"}` predicate vs a per-record `stateProvince` query param), which is why a grep-scoped sweep can see one and miss the other. **n/a with reason** — `TARGET_SPECIES`/`taxonKey`, `BUFFER_M`, `NONVEG_MAX_FRAC` are negatives-only *by definition* (they constitute the negative class). **Separate mechanism** — `predict.py`'s `latest_raster_path` resolves a vintage no training record of either class used; record, not a PA-0020 instance. | BUG-0029; broadened off-axis by BUG-0034 |

Filing constraint: PA-0020's clauses (ii)–(iv) are evidenced **only** by
BUG-0034 (CR-0007's original example, `coord_uncertainty_m`, is
withdrawn as measured-inert). BUG-0034 must therefore be filed at or
before PA-0020, and **DRAFT_BUG-0029 §8 must be rewritten** before
promotion — as drafted it states the narrow geographic-only version of
PA-0020, which would contradict this row on the day both land.

---

## PA-0021 — acceptance criteria must be able to fail

| ID | Rule | Swept? | Source |
|----|------|--------|--------|
| PA-0021 | Extends **PA-0016** from *diagnosing* a reported defect to *accepting* a fix: an acceptance criterion is evidence only if it could have failed. **(a)** Every acceptance invariant must be measured on at least one constructed pipeline that is wrong in the way that invariant exists to catch — not only on the current data and the intended pipeline. **(b)** An acceptance set built only from "violation count == 0" predicates is incomplete by construction — monotone under deletion, so a pipeline that silently drops half the dataset passes all of them. It must include at least one gate constraining what the change set **MAY** do: a pre-registered must-change count, an exact cardinality, or a digest of the intended change, such that a no-op **and** a deletion both fail. **(c)** Any gate that is not an exact predicate must have its threshold calibrated against **both** the statistic's fair-pipeline sampling distribution and its broken-pipeline distribution, and must **separate** them. State both as quantiles, over a draw count that supports the quantile quoted (≥50 draws minimum; a p99 needs ≥100; a min/max over a handful is not a calibration). If the two distributions overlap, **no gate exists** — demote the row to an observation and say so. Exact-zero predicates need no calibration and are preferred where available. **(d)** Every acceptance row is labelled GATE or OBS. A row whose failure mode is "record a justification" is an **OBS**. A GATE may carry a pre-registered, scope-limited escape (e.g. "pre-fix data only") **only** if the escape is recorded in every artifact an escaped run produces; a case-by-case waiver is not such an escape. **(e)** A gate's reference must be recomputed **independently of the change under test** — never read from the artifact being verified (a recorded `block_id`, the repair's own mask, the producer's own bookkeeping), and never derived so that another gate in the same set makes it true by construction. A property that every correct **and** every incorrect implementation has is not a gate. | no — not yet run. Scope by mechanism: every acceptance/verification predicate in the project — the acceptance tables of CR-0006..CR-0009, `smoke_test_training.py`, `bench_pipeline.py`, every `assert` in the pipeline scripts, and the `inv_*` / `res_*` verification harnesses. Runnable read-only today (document + code reading, no pipeline run). Known instances to remediate, all already recorded in their CRs: CR-0009 open defects 1–3 (thresholds that fail the accepted baseline; 6.2 % and 21.1 % false-fail rates; an unlabelled item) = (c)/(d); CR-0007's I14 and v1 assertion (d) = (e); CR-0008 v3's mask-consuming G1/G2 and the withdrawn circular completeness reference = (e); CR-0007's I1–I5 monotone-under-deletion = (b). | BUG-0033 |

**Explicitly NOT filed as extending PA-0018.** PA-0018's text contains no
enforcement, acceptance, gate or threshold clause — verified against the
current `PREVENTIVE_ACTIONS.md`; it is a rule about the source extent of
spatial computations. CR-0007's deliverable wording ("Extends PA-0018's
enforcement clause") is a false cross-reference and must be corrected to
**"extends PA-0016"** before PA-0021 is filed, or §4.3's cross-reference
requirement is satisfied against a clause that does not exist. PA-0018's
enforcement gap being closed by CR-0007's assertions (b)/(c) belongs in
**PA-0018's Swept? cell**, which CR-0007 already carries as a separate
deliverable.

---

## Filing order (see the audit for the full rationale)

1. **Batch 0 — bookkeeping only, no code, no CR required** (precedent:
   BUG-0019/PA-0015 and BUG-0022/PA-0016 both landed this way): file
   BUG-0033 + PA-0021, and BUG-0028 + PA-0019. This is the only ordering
   that removes the circularity, because CR-0007, CR-0008 and CR-0009 all
   cite PA-0021 in their own bodies.
2. **CR-0007** — promote DRAFT_BUG-0029 and DRAFT_BUG-0034, then file
   PA-0020 (re-scoped), file BUG-0031 and BUG-0032, correct PA-0002 /
   PA-0014 / PA-0018 Swept? cells.
3. **CR-0008** — file BUG-0030 (`tcc`) and BUG-0035 (`nlcd`), update
   PA-0017's Swept? cell.
4. **CR-0009** — no records of its own; update PA-0016's Swept? cell.
5. Follow-on — BUG-0036 / BUG-0037 (PA-0019 sweep findings) and the
   BUG-0034 *fix*, which CR-0007 v6 descoped to its own CR.
