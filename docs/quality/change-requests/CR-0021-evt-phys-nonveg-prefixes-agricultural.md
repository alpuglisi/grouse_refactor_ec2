# CR-0021: `EVT_PHYS_NONVEG_PREFIXES`: match LANDFIRE's "Agricultural", drop the dead "Barren", and pin the list to the attribute table

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented; no data has been touched.** Review log: `CR-0021-review-log.md`, to be created by the first reviewer.

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
The `SCLASS_NAMES[180] = "Agriculture"` label (`:112`) is the project's own name for the SClass code and is not changed.

### 3. Test (PA-0035; pre-approval per CR-0011 A3)
`tests/test_evt_phys_prefixes.py`: loads the EVT_PHYS value set from `data/landfire/attribute_tables/LF*_EVT.csv` when present, else from the pinned `PHYS values:` line of `docs/quality/evidence/BUG-0078-evt-phys-values.txt`; asserts every prefix in `EVT_PHYS_NONVEG_PREFIXES` matches at least one class (no dead prefix), that the matched set equals the expected ten strings, and that the acceptance config's copy equals the code's list. It applies `analyze_grouse.is_evt_phys_nonveg` itself when pandas is available and a `re`-based fallback otherwise, so it can run in an environment without pandas.

### 4. Measurement (deliverable 1; decides the rebuild)
On the live tree, read-only, before any change: rows of `evaluated_sightings_{R}.csv` with `evt_phys == "Agricultural"` and `sclass` not in `NON_VEG_SCLASS_CODES`, by region, by `nonveg_landcover`, and by whether the row is in `thinned_positives`/`train_positives`/`val_positives`; the same over `candidate_pool.csv` by (region, split, `weight_basis`). These are exactly the rows whose flag flips. Recorded in `docs/quality/evidence/CR-0021/measure.txt` and pre-registered as the must-change counts (MC, PA-0021(b)).
- **If every count is 0:** the CR reduces to §2, §3 and the pin/fixture update (§5); no rebuild; risk LOW.
- **Otherwise:** the rebuild in §6 runs, and MC requires exactly those rows to change.

### 5. Acceptance (amends CR-0013)
- `docs/quality/acceptance_split.json` `envelope.EVT_PHYS_NONVEG_PREFIXES` → the §2 list (the replay's `is_evt_phys_nonveg` reads it).
- `tests/test_acceptance_split.py:46` fixture: `7007: "Agricultural"`, and one fixture EVT with phys `"Barren"`-free spelling of the quarries class to prove the drop is safe.
- No new gate: E1p, E9 (weight-basis counts) and the R-gates already replay the flag from the config; MC pins the changed rows.

### 6. Rebuild (only if §4 finds changed rows)
`analyze_grouse.py` → `prepare_training_data.py` → `generate_negatives.py` → `acceptance_split.py`, with backup and preconditions as CR-0019 deliverables 5–6. Positives' `nonveg_landcover` changes, so thinning, block assignment (`VAL_FRACTION` rounding) and both draws can change. Validation metrics before and after are not comparable; retrain follow-up.

## Impact
- Without changed rows: code, test, pin and fixture only.
- With changed rows: every split file regenerates; every validation metric and `calibration.json` before the change are not comparable; `envelope_metrics_{R}.csv` loses the `EVT_PHYS:Agricultural|…` habitat envelopes.
- CR-0013's config pin changes (config sha), so the standing record must be re-issued either way (a config-only re-run of `acceptance_split.py` on unchanged files if §4 finds nothing).

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
**Validatable here:** §3 test with the pinned list (`re` fallback); the acceptance fixture test where the harness runs without rasterio.
**Not validatable here:** §4 measurement, the rebuild, MC, the live acceptance run.

## Deliverables (in execution order)
- [ ] 1. Measurement (§4), read-only, recorded and pre-registered.
- [ ] 2. Pre-approval (A3): `tests/test_evt_phys_prefixes.py`, fixture and config-pin changes on an unmerged branch, reviewed with this CR.
- [ ] 3. Code change (§2).
- [ ] 4. If §4 found changed rows: scratch-tree run, then backup, then the live rebuild (§6) with MC.
- [ ] 5. Otherwise: config-only re-issue of the acceptance record.
- [ ] 6. Bookkeeping: BUG-0078 → FIXED naming §2/§3; `BUG_LOG.md`; PA-0035 Swept? cell; CHANGELOG.
- [ ] 7. Close-out.

## Out of scope
- Whether `Exotic Herbaceous`, `Exotic Tree-Shrub`, `Grassland` or `Sparsely Vegetated` should count as non-habitat (the code comment's stated judgment call).
- Verifying `NON_VEG_SCLASS_CODES` against the LANDFIRE SClass documentation (PA-0035 test target, small separate item).
- The retrain.
