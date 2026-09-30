# CR-0021: `EVT_PHYS_NONVEG_PREFIXES`: match LANDFIRE's "Agricultural", drop the dead "Barren", and pin the list to the attribute table

**Status: DRAFT v2, 2026-09-30 — round-1 concerns dispositioned (`CR-0021-review-log.md`); awaiting re-review (CLAUDE.md §1.2, bounded per A2). Nothing has been implemented; no data has been touched.**

## Scope
Change the physiognomy non-vegetated prefix list so it matches LANDFIRE's EVT_PHYS class strings, verify it against the attribute table by a test, update the acceptance pin and fixture, measure how many records change, and rebuild the split files if any do (BUG-0078).

## Why now
BUG-0078, verified against LANDFIRE's published LF2022, LF2023 and LF2024 EVT attribute tables (`docs/quality/evidence/BUG-0078-evt-phys-values.txt`): the prefix `"Agriculture"` never matches the class `"Agricultural"` (47 EVT codes, including 7754 Pasture and Hay and 7755 Cultivated Crops), and `"Barren"` matches no class at all. Farmland is flagged non-vegetated only when its SClass is 180. The comment above the list records that EVT_PHYS and SClass disagree in practice, which is why the physiognomy filter exists. How many records this touches is unknown; it is this CR's first deliverable.

## The change
### 1. Root cause
As BUG-0078 §5: a literal that must match an external vocabulary was written from a neighbouring column's spelling (`EVT_LF`/`EVT_NAME` say "Agriculture"; `EVT_PHYS` says "Agricultural") and never checked against the column it is applied to; the fixture and the acceptance pin were copied from the code, so no check could fail. PA-0035 now states the rule.

### 2. Code (normative)
`analyze_grouse.py:126-130`:
```python
EVT_PHYS_NONVEG_PREFIXES = (
    "Developed", "Open Water", "Agricultural", "Quarries", "Snow-Ice",
)
```
- `"Agricultural"` replaces `"Agriculture"`.
- `"Barren"` is removed: no EVT_PHYS value contains it; the barren class is `Quarries-Strip Mines-Gravel Pits-Well and Wind Pads` (EVT_LF Barren), matched by `"Quarries"`.
- `"Snow-Ice"` replaces the pair `"Snow", "Ice"` (one class, one string; the pair matched the same class).
- `is_evt_phys_nonveg` is unchanged (`str.contains`, case-insensitive). Verified against the LF2023 table: the new list matches exactly the six `Developed…` classes, `Open Water`, `Agricultural`, the `Quarries…` class and `Snow-Ice`, and no other class.
The `NON_VEG_SCLASS_LABELS[180] = "Agriculture"` label (`:110-113`) is the project's own name for the SClass code and is not changed. `legacy/audit.py:128` carries the old list; it is guarded (PA-0026) and not changed.

### 3. Test (PA-0035; pre-approval per CR-0011 A3)
`tests/test_evt_phys_prefixes.py`: extracts `EVT_PHYS_NONVEG_PREFIXES` from `analyze_grouse.py` by AST (the `tests/test_shared_constants.py` pattern; `analyze_grouse` imports rasterio at module level, so it is not imported), loads the EVT_PHYS value set from `data/landfire/attribute_tables/LF*_EVT.csv` when present (the live pinned crosswalk is LF2025, `acceptance_split.json:208`; deliverable 1 records its value set in the evidence file), else from the pinned `PHYS values:` line of `docs/quality/evidence/BUG-0078-evt-phys-values.txt`; applies the same case-insensitive alternation with `re`; asserts every prefix matches at least one class (no dead prefix), that the matched set equals the expected ten strings, and that the acceptance config's copy equals the code's list. Runnable here.

### 4. Measurement (deliverable 1; decides the rebuild)
On the live tree, read-only, before any change, three counts per region: (a) rows of `evaluated_sightings_{R}.csv` (S) with `evt_phys == "Agricultural"` and `sclass` not in `NON_VEG_SCLASS_CODES`, by `nonveg_landcover` and by membership in `thinned/train/val_positives`; (b) the same over `candidate_pool.csv` by (split, `weight_basis`); (c) rows of `availability_sample_{R}.csv` with `used == True` whose `envelope_id` starts `EVT_PHYS:Agricultural|` (the same filter sets `used` at `analyze_grouse.py:541`). Recorded in `docs/quality/evidence/CR-0021/measure.txt`.
- **If (a), (b) and (c) are all 0 in every region:** the CR reduces to §2, §3 and §5; the acceptance record is re-issued for the config change only; risk LOW.
- **Otherwise:** the rebuild in §6 runs. Because one flipped row changes `used_total`/`avail_total` and therefore every `Used_Pct`, `Avail_Pct`, `Selection_Ratio`, `env_zone`, weight and both draws, the must-change requirement (PA-0021(b),(e)) is a **pre-registration via a `Replay` subclass with a control** (the CR-0019 `preregister.py` pattern), not "exactly those rows": exact pins on the set of S rows (5 dp key) and availability rows whose flag flips, and pre-registered outputs (counts per file, per region and split) that the live run must reproduce. The control first shows the unmodified replay reproduces today's files.

### 5. Acceptance (amends CR-0013)
- `docs/quality/acceptance_split.json` `envelope.EVT_PHYS_NONVEG_PREFIXES` → the §2 list (the replay's `is_evt_phys_nonveg` reads it).
- `tests/test_acceptance_split.py:46` fixture: `7007: "Agricultural"`, plus one fixture EVT whose phys is the real quarries string `Quarries-Strip Mines-Gravel Pits-Well and Wind Pads` (proves dropping "Barren" loses nothing); the fixture's `nonveg_landcover` (`:241`, random today) is derived from `evt_phys`/`sclass` with the config rule so the positives side is exercised; every fixture-existence assertion and attack row (`:926-949`) re-checked, since ~4 % of fixture candidates become NonVeg.
- **New exact gate E16.** `nonveg_landcover` over S, recomputed from S's `evt_phys` and `sclass` with the config's `NON_VEG_SCLASS_CODES` and `EVT_PHYS_NONVEG_PREFIXES`, equals S's recorded column (the replay today takes the flag as given, `acceptance_split.py:1000-1001`; E10 replays only C's `is_nonveg`, `:731-732`, so a stale `analyze_grouse.py` run would otherwise pass). Attack row: S with the old flag under the new config → FAIL.
- E10 already replays the candidates' flag from the config; the pre-registration (§4) pins the changed rows. Pins: `GATE_SECTION_SHA256["envelope"]`, `GATE_IDS` and its length.

### 6. Rebuild (only if §4 finds changed rows)
`analyze_grouse.py` → `prepare_training_data.py` → `generate_negatives.py` → `acceptance_split.py`, with backup and preconditions as CR-0019 deliverables 5–6. Positives' `nonveg_landcover` changes, so thinning, block assignment (`VAL_FRACTION` rounding) and both draws can change. Validation metrics before and after are not comparable; retrain follow-up.

## Impact
- Without changed rows: code, test, pin, fixture and gate E16 only.
- With changed rows: every split file regenerates; every validation metric and `calibration.json` before the change are not comparable; `envelope_metrics_{R}.csv` loses the `EVT_PHYS:Agricultural|…` habitat envelopes.
- CR-0013's config pin changes (config sha), so the standing record must be re-issued either way (a config-only re-run of `acceptance_split.py` on unchanged files if §4 finds nothing).
- **PA-0042 consumers of `nonveg_landcover` / `is_nonveg` / `weight_basis`:** `prepare_training_data.py:388` (habitat filter; changes with the flag, intended), `generate_negatives.py:251-252` (candidates' flag, intended), `check_partition.py:463` (reads S's flag; E16 now verifies it), `check_exotic.py:121` and `dupe_check.py:72-121` (diagnostics, read as-is), `clean.py` and `legacy/audit.py` (guarded), `acceptance_split.py` E9/E10/O6 (replay from config; unchanged semantics), `tune_bins.py` (reads S's flag).

## One change per CR (CR-0011 A5)
Code, pin, fixture and test land together (the pin and the code must agree for the replay). The rebuild is conditional on the measurement and is the same change's consequence. The retrain is split out.

## Risk: LOW (no changed rows) / MEDIUM (rebuild)
| risk | mitigation |
|---|---|
| An older LANDFIRE vintage in `attribute_tables/` spells the class differently | The §3 test reads the table on disk first and fails loudly; the pinned list covers LF2022–LF2024 |
| Removing `"Barren"` drops a match in some vintage | The test asserts the matched set; "Barren" matched nothing in any of the three tables |
| Rebuild changes block assignments and the validation set | MC pins the changed rows; CR-0019's backup/restore procedure; not-comparable statement |
| Agricultural positives were real grouse habitat (edge/hedgerow) | The SClass-180 rule already removes most farmland; this restores the documented intent. If §4 shows a large share of positives affected (> 5 % of any region's thinned positives), the reviewer decides before the rebuild |

## Test plan
**Validatable here:** the §3 test with the pinned list (AST + `re`).
**Not validatable here:** §4 measurement, E16 and the fixture changes (harness needs rasterio), the rebuild, the pre-registration, the live acceptance run.

## Deliverables (in execution order)
- [ ] 1. Measurement (§4), read-only, recorded and pre-registered.
- [ ] 2. Pre-approval (A3): `tests/test_evt_phys_prefixes.py`, E16 and its attack row, fixture and config-pin changes (pins re-derived) on an unmerged branch, reviewed with this CR.
- [ ] 3. Code change (§2).
- [ ] 4. If §4 found changed rows: scratch-tree run, pre-registration with control (§4), backup, then the live rebuild (§6).
- [ ] 5. Otherwise: config-only re-issue of the acceptance record.
- [ ] 6. Bookkeeping: BUG-0078 → FIXED naming §2/§3; `BUG_LOG.md`; PA-0035 Swept? cell; CHANGELOG.
- [ ] 7. Close-out.

## Out of scope
- Whether `Exotic Herbaceous`, `Exotic Tree-Shrub`, `Grassland` or `Sparsely Vegetated` should count as non-habitat (the code comment's stated judgment call).
- Verifying `NON_VEG_SCLASS_CODES` against the LANDFIRE SClass documentation (PA-0035 test target, small separate item).
- The retrain.
