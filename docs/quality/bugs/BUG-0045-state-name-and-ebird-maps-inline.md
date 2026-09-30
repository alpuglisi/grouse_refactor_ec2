# BUG-0045: State-name and eBird-code maps of the regions written inline in the acquisition scripts (PA-0025 sweep, item b)

## 1. Description
The three data-acquisition scripts each carried their own map from the
regions to an external naming scheme (GBIF `stateProvince` names and eBird
region codes), as dict literals. One of them was the inverse of another.

## 2. Where encountered
PA-0025 §3.5 sweep, item (b); CR-0007 P6 scanner rule (iii) (a dict of
string literals whose keys or values equal `REGIONS`, case-folded):
`get_negatives.py:45`, `sightings.py:123`, `ebird.py:16`.

## 3. What it caused to fail
Nothing observed; the three maps agreed. Latent: the negatives' GBIF query
(`get_negatives.py`) and the positives' file naming (`sightings.py`) could
drift apart. That is the same axis on which BUG-0029 found the two classes
already disagreeing (box vs `stateProvince`).

## 4. What the defect was
`get_negatives.py:45`
```python
STATES = {"ME": "Maine", "NH": "New Hampshire", "VT": "Vermont"}
```
`sightings.py:123-127`
```python
    state_mapping = {
        "Maine": "me",
        "New Hampshire": "nh",
        "Vermont": "vt"
    }
```
`ebird.py:16-20`
```python
STATES = {
    "me": "US-ME",
    "nh": "US-NH",
    "vt": "US-VT"
}
```

## 5. Root cause analysis
Same root cause as BUG-0043 (differential analysis: these are derived
naming maps, not the constants themselves). With no shared region list or
name map, each script wrote its own. PA-0001's sweep did not cover
external-name maps.

**Root cause:** no shared region-name definition existed, and no check
looked for region-keyed literals.

## 6. Corrective action
CR-0007 deliverable 2 (§1 re-point table):
- `get_negatives.py`: `from regions import STATE_NAMES as STATES`
- `sightings.py`: `{n: c.lower() for c, n in STATE_NAMES.items()}`
- `ebird.py`: `{r.lower(): f"US-{r}" for r in REGIONS}`

Values are unchanged. The P6 scan reports none of these lines.

Status: **FIXED** (CR-0007 deliverable 2).

## 7. Recurrence review
Swept under PA-0025 (BUG-0043); see its recurrence review against
BUG-0001/PA-0001. Related but distinct: BUG-0029 (the classes' geographic
filters differ in kind). This bug is only about the literal copies.

## 8. Preventive action
Covered by **PA-0025**; P6 rule (iii) enforces it. No new rule.
