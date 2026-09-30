# BUG-0078: `EVT_PHYS_NONVEG_PREFIXES` lists "Agriculture", but LANDFIRE's EVT_PHYS class is "Agricultural", so the physiognomy-based non-vegetated filter never flags agricultural pixels for either class

> Found by the 2026-09-30 static code review at `3b3e7d1`; the spelling
> was verified against LANDFIRE's published LF2022, LF2023 and LF2024
> EVT attribute tables (`docs/quality/evidence/BUG-0078-evt-phys-values.txt`).
> The size of the effect on the live data is not measurable in this
> environment (no `data/` tree).
> **Status: OPEN; owner: lead; fix needs a CR (rebuilds the split
> files).**

## 1. Description
`analyze_grouse.py` flags a record as non-vegetated when its SClass is
one of the fixed non-veg codes **or** its EVT physiognomy string
contains one of `EVT_PHYS_NONVEG_PREFIXES`. The prefix list says
`"Agriculture"`. In every current LANDFIRE EVT attribute table the
physiognomy class is `"Agricultural"` (47 EVT codes, including 7754
"Agriculture-Pasture and Hay" and 7755 "Agriculture-Cultivated Crops
and Irrigated Agriculture"). `"Agriculture"` is not a substring of
`"Agricultural"`, so the physiognomy half of the filter never fires on
farmland; only `SCLASS == 180` does. The comment above the list records
that EVT_PHYS and SClass disagree in practice, which is why the
physiognomy filter exists. `"Barren"` in the same list matches no
EVT_PHYS value either (the barren class is the "Quarries-…" string,
already caught by `"Quarries"`), so that entry is dead rather than
wrong. The same `"Agriculture"` string is pinned in
`docs/quality/acceptance_split.json:166` and used in the test fixture
(`tests/test_acceptance_split.py:46`), so the acceptance replay agrees
with the defect and no test can fail on it.

## 2. Where encountered
- `analyze_grouse.py:126-134` (the list and `is_evt_phys_nonveg`).
- Consumers: `analyze_grouse.py:839-842` (positives' `nonveg_landcover`),
  `:541` (availability sample filter), `generate_negatives.py:251-252`
  (candidates' `is_nonveg`, which selects the `NONVEG_WEIGHT` hard
  negative branch of `build_weight`, `:145-147`).
- Pins: `docs/quality/acceptance_split.json:166`,
  `tests/test_acceptance_split.py:46`.

## 3. What it caused to fail
For any pixel whose EVT is agricultural but whose SClass is a succession
code rather than 180:
- a positive (an eBird pin on a hayfield or cropland, the
  location-precision artifact the flag exists to remove) stays
  "habitat", passes the year floor and thinning, and enters
  `thinned_positives`;
- the matching negative candidates are placed in habitat envelopes at
  envelope weight instead of the NonVeg hard-negative cap, and envelope
  ids such as `EVT_PHYS:Agricultural|…` become habitat envelopes in
  `envelope_metrics`;
- the availability sample keeps them as available habitat.
The predicate is symmetric but its effect is not (positives are kept
by it, negatives re-bucketed), so class composition on farmland shifts.
How many records this touches is unknown until measured on the live
`evaluated_sightings_*` files (see §6).

## 4. What the defect was
`analyze_grouse.py:126-134`:
```python
EVT_PHYS_NONVEG_PREFIXES = (
    "Developed", "Open Water", "Barren", "Agriculture",
    "Quarries", "Snow", "Ice",
)


def is_evt_phys_nonveg(evt_phys_series):
    pattern = "|".join(EVT_PHYS_NONVEG_PREFIXES)
    return evt_phys_series.astype(str).str.contains(pattern, case=False, na=False)
```
Applied to the LF2023 table, that pattern matches the six `Developed…`
classes, `Open Water`, `Quarries-Strip Mines-Gravel Pits-Well and Wind
Pads` and `Snow-Ice`, and never `Agricultural` (evidence file).

## 5. Root cause analysis (Five Whys)
1. *Why is farmland not flagged by physiognomy?* The prefix is
   "Agriculture" and the class string is "Agricultural".
2. *Why the wrong string?* The project's own SClass label for code 180
   is "Agriculture" (`SCLASS_NAMES`, `:112`), and the EVT table's
   `EVT_LF`/`EVT_NAME` columns also say "Agriculture"; the prefix was
   written from those, not from the `EVT_PHYS` column it is applied to.
3. *Why did no test catch it?* The fixture assigns `"Agriculture"` to a
   fake EVT code and the acceptance config pins the same string, both
   copied from the code, so every check is consistent with the defect.
4. *Why no rule?* PA-0021 (e) forbids gate references read from the
   artifact under test, but no rule covers literals that must match an
   **external** vocabulary.

**Root cause:** a string literal that must match an external data
vocabulary was written from a neighbouring column's spelling and never
verified against the column it is matched to; the test fixture and the
acceptance pin were derived from the code, so they cannot fail.

## 6. Corrective action
**None yet.** Proposed (CR: it changes `nonveg_landcover` for both
classes and therefore the split files, so it rebuilds and re-runs
acceptance): change the prefix to `"Agricultural"`, drop the dead
`"Barren"`, update `acceptance_split.json` and the fixture, add the
PA-0035 test. Measure first, on the live tree:
`evaluated_sightings_{R}.csv` rows with `evt_phys == "Agricultural"`
and `sclass != 180`, split by `nonveg_landcover`, and the same over
`candidate_pool.csv`; record the counts in the CR. Status: **OPEN**.
Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "EVT_PHYS",
"nonveg", "Agricultur", "vocabulary", "fixture", "label".

**Matches:** BUG-0053 (EVT crosswalk read failure; same table, control
flow), BUG-0033 / PA-0021 (acceptance criteria that cannot fail;
references read from the artifact), BUG-0018 (`check_exotic.py` dead
constant, the "Barren" half). No prior BUG for a mismatched external
label.

**Prior-preventive-action failure analysis.** PA-0021 (e) is the
nearest rule: "a gate's reference must be recomputed independently of
the change under test". It is scoped to acceptance gates; a unit-test
fixture and a production constant that both restate the code's own
string are the same mechanism one layer down, and the rule was not read
as applying there. Category: too narrow (acceptance gates only).

## 8. Preventive action
**PA-0035**: a literal that must match an external data vocabulary (a
class label, a code list, an attribute-table string) is verified
against that vocabulary's source, the attribute table on disk or a
pinned extract of the published table, by a test; a fixture copied
from the code under test does not count. Enforcement: a test that reads
`data/landfire/attribute_tables/LF*_EVT.csv` when present, else the
pinned value list in `docs/quality/evidence/BUG-0078-evt-phys-values.txt`,
and asserts every prefix in `EVT_PHYS_NONVEG_PREFIXES` matches at least
one real class.

**Sweep (§3.5), string literals matched against external
vocabularies:** `EVT_PHYS_NONVEG_PREFIXES` (this; "Barren" dead);
`NON_VEG_SCLASS_CODES` and `SCLASS_NAMES` (numeric LANDFIRE SClass
codes from the LF documentation; not re-verified here, recorded as a
PA-0035 test target); `NLCD_NAMES` and `WETLAND_NLCD_CLASSES` (numeric
NLCD legend, standard values, correct). No other string-matched
vocabulary found.

## Cross-references
`docs/quality/evidence/BUG-0078-evt-phys-values.txt`; BUG-0018,
BUG-0033, BUG-0053; PA-0021, PA-0035; `acceptance_split.json:166`,
`tests/test_acceptance_split.py:46`.
