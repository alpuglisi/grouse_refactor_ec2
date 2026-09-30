# BUG-0086: `--use-weights` applies the envelope weight twice: the CR-0012 draw already samples negatives in proportion to `weight`, and the loss multiplies by the same column again (latent)

> Found by the 2026-09-30 static code review at `3b3e7d1`. Latent: the
> flag is off by default and no recorded recipe (CHANGELOG, CR-0009,
> results summary) uses it.
> **Status: OPEN (latent); owner: lead; decide and fix with the next
> `model_handler.py` change or as a trivial fix.**

## 1. Description
Before CR-0012 the negatives were drawn uniformly and `weight` was a
per-sample loss weight, which `--use-weights` applies ("default off =
original behavior"). CR-0012 replaced the draw with an Efraimidis-
Spirakis weighted sample on the same column, so a candidate's
probability of being selected is already proportional to its weight.
The column is carried into `negatives_{R}.csv`, `dataset.py` serves it
as `w`, and `_batch_loss` multiplies the per-sample loss by it when the
flag is on. A NonVeg candidate (weight 10, up to `NONVEG_MAX_FRAC` of
the draw) is therefore over-represented by the draw and then given
ten times the loss weight; positives stay at 1.0.

## 2. Where encountered
- Draw: `generate_negatives.py:283-295` (`draw_region_split`), weights
  from `:257-258`.
- Column served: `dataset.py:87-89`, `:116-117`.
- Loss: `model_handler.py:445-447`; flag `train.py:487-490`.

## 3. What it caused to fail
With the flag on, the negative class's gradient mass is dominated by the
trivially separable water/urban rows that `NONVEG_MAX_FRAC`
(`generate_negatives.py:100-106`) exists to keep from dominating, and
avoided-envelope negatives are similarly double-counted. Nothing warns;
the flag's help text still describes the pre-CR-0012 meaning. Latent.

## 4. What the defect was
`generate_negatives.py:288-292`:
```python
    w = sub["weight"].to_numpy(dtype=np.float64)
    scored = []
    for i, (k, wi) in enumerate(zip(keys.tolist(), w.tolist())):
        u = (int(k) + 0.5) / 2**64
        scored.append((-(math.log(u) / wi), int(k), i))
```
`model_handler.py:445-447`:
```python
        if self.use_sample_weights:
            per_sample = criterion(outputs, y)          # reduction='none'
            hard = (per_sample * w.unsqueeze(1)).mean()
```
`train.py:487-490`:
```python
    parser.add_argument("--use-weights", action="store_true",
                        help="Weight negative samples by their envelope-"
                             "derived weights (default off = original "
                             "behavior).")
```

## 5. Root cause analysis (Five Whys)
1. *Why twice?* The draw and the loss both consume `weight`.
2. *Why does the loss still consume it?* CR-0012 changed the producer's
   use of the column (uniform draw → weighted draw) and left the
   downstream flag untouched.
3. *Why was the consumer not revisited?* CR-0012's scope was the pooled
   draw; nothing required listing the column's consumers when its
   meaning changed.
4. *Why no rule?* PA-0030 covers optional keys, PA-0026 stale writers;
   no rule covers a semantic change to an existing column.

**Root cause:** a CR changed what a shared column does upstream without
enumerating its downstream consumers, so a flag that was correct under
the old semantics now compounds the new ones.

## 6. Corrective action
**None yet.** Decision for the lead: either (a) remove the loss
weighting (drop the flag, or make it a no-op with a message) because
the draw now carries the prior, or (b) keep the flag but draw uniformly
within the NonVeg cap when it is on. Either way fix the help text.
Status: **OPEN (latent)**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0027-use-weights-flag-semantics.md` (DRAFT v1, awaiting independent review under CLAUDE.md §1.2; nothing implemented).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "weight",
"use-weights", "semantic", "consumer".

**Matches:** none for this mechanism. Adjacent: PA-0030 (producer key
sets), PA-0026 (stale writers of one path), CR-0012 §2 step 11
(persisting `weight`/`weight_basis`, reviewer A-7).

**Prior-preventive-action failure analysis.** No prior rule; CR-0012's
review asked to persist the column (A-7) but not to re-derive its
consumers. Category: no rule.

## 8. Preventive action
**PA-0042**: when a CR changes how an artifact column is produced or
what it means, the CR lists every consumer of that column (a recorded
name search) and states for each whether its use is still correct; a
CLI flag or help text describing the pre-CR meaning is a defect.

**Sweep (§3.5), consumers of `weight` (`grep -rlE '\bweight\b'`,
tracked non-test `*.py`):** `generate_negatives.py` (producer);
`dataset.py:87-89` (passthrough); `grouse_data.training_frame`
(`fillna(1.0)`); `model_handler.py:445-447` + `train.py:487` (this);
`acceptance_split.py` (E9 counts by `weight_basis`, unaffected);
`smoke_test_training.py` (prints one sample's weight); `pretrain.py`
(`weight_decay` only). No other instance.

## Cross-references
CR-0012 §2; BUG-0004 (the NonVeg cap's origin); PA-0026, PA-0030,
PA-0042.
