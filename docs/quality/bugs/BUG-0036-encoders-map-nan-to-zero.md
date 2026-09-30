# BUG-0036: Raster encoders silently turn NaN into 0, a real reading

## 1. Description
The five fixed-point encoders in `models.py` — `tsd_encode`,
`road_dist_encode`, `tpa_live_encode`, `treemap_encode` and
`qmd_from_balive_tpa` — accept NaN and return `0` with at most a cast
warning. `0` is a legitimate value for every one of these features
(`tsd` 0 = disturbed this year, `road_dist` 0 = on a road, TreeMap 0 =
non-forest). A generator that marks missing data as NaN before encoding
would therefore write a fabricated reading, not nodata.

## 2. Where encountered
- `models.py:625-629` (`road_dist_encode`), `:658-662` (`tsd_encode`),
  `:708-718` (`qmd_from_balive_tpa`), `:721-726` (`tpa_live_encode`),
  `:736-742` (`treemap_encode`) — line numbers before CR-0008.
- Found in CR-0008 review (round 7, R7-11); a review finding counts under
  `CLAUDE.md` §2 even though never observed running.

## 3. What it caused to fail
Nothing observed: every current caller passes finite values
(`generate_road_distance.py:216` encodes the EDT result before masking;
the `tsd` and TreeMap generators produced no NaN). The defect is
**latent** — it made the obvious generator fix for BUG-0024/0025 (mark
uncovered pixels NaN, then encode) silently reproduce the bug.

## 4. What the defect was
```python
def tsd_encode(years):
    y = _np.clip(_np.asarray(years, dtype=_np.float64), 0, TSD_MAX_YEARS)
    return _np.rint(_np.log1p(y) * TSD_LOG_SCALE).astype(_np.int16)
...
    ok = tpa > 0          # NaN > 0 is False -> out keeps its zeros
```
`np.clip(NaN)` is NaN, and `np.rint(NaN).astype(int16)` is `0` on this
platform. The same pattern holds in all five functions.

## 5. Root cause analysis (Five Whys)
1. *Why does NaN become 0?* The float→int16 cast of NaN yields 0, and
   `qmd`'s `tpa > 0` guard treats NaN as "no stems".
2. *Why doesn't the encoder notice?* It has no input contract; it
   assumes callers pass real values.
3. *Why is that assumption unsafe?* NaN is this codebase's in-memory
   marker for continuous nodata (PA-0006), so passing it is natural.
4. *Why wasn't the contract written?* The encoders were written for
   generators that, at the time, never produced missing values.
5. *Why did that matter now?* BUG-0024/0025's fixes introduce missing
   values into exactly those generators.

**Root cause:** an encoder for a feature whose `0` is a real reading
accepted the codebase's nodata marker without error — `0` overloaded for
two meanings, which PA-0006 forbids.

## 6. Corrective action
CR-0008 §3: each encoder validates its input through `models._finite`
and raises `ValueError` on any NaN or ±inf. Contract (docstrings):
encoders take finite values; generators write nodata by mask after
encoding. Test U2 (`tests/test_cr0008.py`).

Status: **FIXED** (CR-0008).

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`:
- **PA-0006** (from BUG-0008, swept in BUG-0017): never overload `0` for
  nodata and a legitimate value. This is the same mechanism in a new
  place — a **recurrence**.
- **Prior-preventive-action failure analysis.** PA-0006 is worded for
  *mask handling* ("raster nodata/mask handling must use a dedicated mask
  array"). Its sweep looked at readers and masks (`dataset.py`,
  `predict.py`), not at **write-side encoders**, which are not "mask
  handling" in any obvious reading. Too narrow in its trigger wording,
  not in its principle.

## 8. Preventive action
**Extends PA-0006** — no new PA number: PA-0006's Swept? cell and trigger
are widened to name value encoders/decoders (any function converting a
physical value to a stored code) as in scope, with this bug as the
sweep result. Sweep (§3.5), scoped to the mechanism — every function
that converts a float to a stored integer code:
- `models.py`: the five encoders above — fixed.
- `models.tsd_decode`, `road_dist_decode`, `tpa_live_decode`,
  `treemap_decode`: decode int16 → float; no NaN path. Not affected.
- `download_tcc_nlcd.mask_to_valid`: NaN fails both comparisons and
  becomes NODATA. Not affected.
- `generate_road_distance.py`: encodes before masking, writes
  `ROAD_DIST_NODATA` by mask. Not affected.
- `dataset.py:196`: `np.nan_to_num(patch, nan=MISSING_CODE)` before the
  int16 cast — NaN is mapped to the missing code explicitly. Not affected.
No other instances (`grep -n "astype(.*int16"` over root-level
production scripts: `dataset.py`, `download_tcc_nlcd.py`,
`generate_road_distance.py`, `models.py`).
