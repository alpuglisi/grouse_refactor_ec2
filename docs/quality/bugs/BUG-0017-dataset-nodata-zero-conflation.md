# BUG-0017: `dataset.py` may conflate nodata sentinels with a legitimate value of 0 in training patches (unconfirmed — needs domain input)

## 1. Description
`dataset.py`'s patch-building paths convert nodata/sentinel values to NaN
during raster reads, then collapse those NaNs to `0` before feeding
categorical and continuous channels into the model — the same conflation
class already confirmed and fixed once in `predict.py` (BUG-0008/PA-0006).
**Unlike BUG-0008, this instance is not confirmed against real data** — no
attribute tables or raster data are available in this environment to check
whether any in-use LANDFIRE feature actually assigns legitimate meaning to
class code `0`.

## 2. Where encountered
`dataset.py:152` (`_load_or_build_cache`) and `dataset.py:269-270`
(`_raw_stack`): both call
`np.nan_to_num(patch_or_array, nan=0.0)` before the result is cast and used
as model input (categorical channels feed `.long()` embedding indices
directly).

## 3. What it caused to fail
**Not confirmed as an active failure** — flagged per PA-0006's mechanism,
not verified ground truth. If any LANDFIRE feature (`evt`, `evh`, `evc`,
`sclass`, `fdist`, `ch`, `cc`) legitimately uses code `0` for a real class
(plausible — `0` is a common "background"/"no forest" encoding in
categorical land-cover products), a patch straddling a nodata-padded edge
and a genuinely-`0`-coded region would present identical channel values for
both to the model — the categorical embedding couldn't distinguish "no
data here" from "real class 0 here," a silent training-signal corruption
matching BUG-0008's confirmed impact in `predict.py`.

## 4. What the defect was
`dataset.py:152`:
```python
arr[i, k] = np.nan_to_num(patch, nan=0.0).astype(np.int16)
```
`dataset.py:269-270`:
```python
np.nan_to_num(self._read_patch(...), nan=0.0)
```
Both collapse "we don't know" (NaN, itself already a correct conversion
from the raw sentinel) into `0`, the same value a legitimate class-0 pixel
would carry, with no separate validity mask carried alongside.

## 5. Root cause analysis (Five Whys)
1. Why might a legitimate class-0 pixel be indistinguishable from nodata
   in a training patch? Because both are represented by the numeric value
   `0` after `nan_to_num`, with no separate mask.
2. Why is `0` used as the fill value instead of a mask-aware
   representation? Because it's numerically convenient — patches feed
   directly into fixed-shape int16/float32 arrays and PyTorch embedding
   layers, and a dedicated validity channel would need to be threaded
   through the dataset, model input shape, and training loop.
3. Why wasn't this addressed when the identical defect was found and
   fixed in `predict.py` (BUG-0008)? Because BUG-0008's fix was scoped to
   `predict.py`'s masking check specifically (which raster cells to
   *skip predicting on*) — it did not touch how training patches
   themselves represent nodata, a different code path serving a different
   purpose (training-time data loading vs. inference-time masking).
4. Why does that gap matter? Because if the same `0`-overload conflation
   exists in the training data pipeline, the model may have been trained
   on a signal where "no data" and "real class 0" were indistinguishable —
   a defect that predates and is independent of the `predict.py` fix, and
   fixing `predict.py` alone doesn't address it.
5. Why is this bug marked unconfirmed rather than fixed immediately? Because
   verifying it requires checking LANDFIRE's actual attribute tables/class
   codes for whether `0` is a real, meaningful category for any in-use
   feature — data not present in this environment (no `data/` tree), and a
   domain question, not one resolvable by code inspection alone.

**Root cause (provisional, pending confirmation):** if confirmed, the same
mechanism as BUG-0008/PA-0006 — overloading `0` to mean both "sentinel
nodata" and "legitimate zero" removes the information needed to
distinguish them, here in the training-data path rather than the
inference-masking path.

## 6. Corrective action
**None implemented — deliberately deferred, not a documentation gap.** A
fix analogous to BUG-0008's (carry an explicit validity mask) would touch
`dataset.py`'s patch-building, the cache file format (`_load_or_build_cache`
writes a cache to disk — a mask would need cache-format versioning), and
potentially `models.py`'s input channel handling — a materially larger
blast radius than `predict.py`'s masking-only fix, and one this session
should not guess at without confirming the premise first. **Status: OPEN,
pending domain-owner confirmation of whether class code `0` is ever a real
category for any of the 7 `RASTER_FEATURES`.** If confirmed, this needs a
CR per `CLAUDE.md` §1 (non-trivial: touches cache format and possibly
model input shape).

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: **matches BUG-0008**'s
mechanism (nodata/zero conflation, PA-0006) if confirmed, but in a
different code path (training-data loading vs. inference masking) that
BUG-0008's fix did not cover.

**Prior-preventive-action failure analysis:** PA-0006 ("raster nodata/mask
handling must use a dedicated mask array... never overload 0 for both")
was written scoped to `predict.py`'s specific masking check. This
potential instance shows the rule, as enforced, only reached the file it
was found in — **too narrow** in practice, even though PA-0006's own
wording ("raster nodata/mask handling," not "`predict.py`'s nodata/mask
handling") already states the mechanism generally. Same failure shape as
BUG-0014's recurrence: a correctly-worded rule that wasn't swept against
sibling code paths at fix time.

## 8. Preventive action
**PA-0006 is not reworded** (already correctly general). This bug is
logged as a **flagged-but-unconfirmed sibling instance** rather than a
new preventive action, since confirming the premise (does any feature use
class 0 meaningfully) is a prerequisite to any corrective action or new
rule being worth writing. Recorded here so it isn't lost, and so a future
sweep for PA-0006 violations checks `dataset.py` explicitly.
