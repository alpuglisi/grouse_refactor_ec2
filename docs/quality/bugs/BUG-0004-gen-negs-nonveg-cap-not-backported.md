# BUG-0004: `gen_negs.py` lacks the non-vegetated negative-sampling cap fixed in `generate_negatives.py`

## 1. Description
`generate_negatives.py` caps how much of the sampled "negative" training set
can come from trivially-separable non-vegetated candidates (water/urban),
with comments explaining this was done to prevent the model from "solving"
the negative class via background embeddings instead of learning real
habitat discrimination. `gen_negs.py`, an older/duplicate standalone script
with the same purpose and CLI, still does plain uncapped weighted sampling.

## 2. Where encountered
- `gen_negs.py` (uncapped weighted sampling — no `NONVEG_MAX_FRAC` logic)
- Contrast: `generate_negatives.py` (`NONVEG_MAX_FRAC = 0.30` and the
  pool-split logic around it)

## 3. What it caused to fail
If `gen_negs.py` is run instead of `generate_negatives.py` (both are
runnable standalone scripts with matching docstrings/CLI, and `gen_negs.py`
is not imported anywhere else, confirmed via grep), the resulting negative
training set is systematically over-weighted toward non-vegetated (water/
urban) candidates, since `NONVEG_WEIGHT` (10.0) is the maximum weight and
nothing caps its share under uncapped `p = pool['weight'] / pool['weight'].sum()`
sampling. This silently degrades model quality (the exact failure mode
`generate_negatives.py`'s own comments describe: focal loss "solving" the
negative class in one epoch via easy background embeddings) with no error
or warning.

## 4. What the defect was
`generate_negatives.py` (fixed):
```python
NONVEG_MAX_FRAC = 0.30
...
nonveg_pool = pool[pool['is_nonveg']]
habitat_pool = pool[~pool['is_nonveg']]
n_nonveg_t = min(int(round(n_target * NONVEG_MAX_FRAC)), len(nonveg_pool))
```
`gen_negs.py` (still broken):
```python
p = pool['weight'].values / pool['weight'].sum()
idx = rng.choice(pool.index.values, size=n_target, replace=False, p=p)
```

## 5. Root cause analysis (Five Whys)
1. Why does `gen_negs.py` produce worse negative samples than
   `generate_negatives.py`? Because it lacks the non-vegetated fraction cap.
2. Why does it lack the cap when the fix clearly exists and is documented?
   Because the cap was added only to `generate_negatives.py`, a separate
   file, not to `gen_negs.py`.
3. Why wasn't `gen_negs.py` updated or removed once the fix was made
   elsewhere? Same mechanism as BUG-0002/0003: `gen_negs.py` is a stale
   duplicate/superseded copy left runnable in the repository.
4. Why does this class of defect keep recurring across unrelated parts of
   the codebase (download scripts, negative-sampling scripts)? Because
   there is no repository-wide convention against keeping duplicate,
   independently-runnable copies of a script around after one is fixed —
   this is a systemic pattern, not a one-off.

**Root cause:** same mechanism as BUG-0002/0003 (stale superseded script
copy not receiving a backported fix), now confirmed as a repository-wide
pattern rather than isolated to the LandFire download scripts.

## 6. Corrective action
CR-0003-B (approved after independent review): backported
`generate_negatives.py`'s `NONVEG_MAX_FRAC = 0.30` cap and the full
two-pool sampling block (`habitat_pool`/`nonveg_pool` split,
`weighted_take` helper, shortfall top-up) into `gen_negs.py` verbatim
(diffed against `generate_negatives.py`'s equivalent block — identical
apart from an added comment), and added a superseded-by header comment.
Verified: file parses and imports cleanly, `NONVEG_MAX_FRAC` resolves to
`0.3`. **Status: CLOSED.**

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: **matches BUG-0002/
BUG-0003** — same root cause and mechanism (stale superseded script not
receiving a backported fix), third instance, now found in a completely
different subsystem (negative sampling vs. LandFire downloads). This is the
recurrence case §4.2 of `CLAUDE.md` describes.

**Prior-preventive-action failure analysis:** PA-0002 (from BUG-0002) was
only written up during this same review pass, in parallel with this
finding — it had no chance to be "applied" before this instance was found
(both were discovered by different agents in the same review round, not
sequentially). Classifying PA-0002's failure mode here as **too narrow**:
as originally scoped to the LandFire download scripts context, someone
reading only BUG-0002's narrative could mistakenly treat it as an issue
specific to that one download pipeline rather than a repository-wide
pattern. This third occurrence, in an entirely different subsystem, proves
the mechanism is general.

## 8. Preventive action
**PA-0002 is hereby broadened/reworded** (not superseded — its actionable
rule already generalizes; this bug is the evidence justifying stating it
repo-wide instead of leaving it implicitly scoped to one pipeline) to
explicitly apply repository-wide: *any* directory, not just the download
scripts. See the updated wording in `PREVENTIVE_ACTIONS.md`. Additionally,
**PA-0012** is added: a repo-wide sweep for near-duplicate/superseded
script files is required (see `PREVENTIVE_ACTIONS.md` §sweep note) —
tracked as follow-up scope, not fully executed in this pass (this review
covered all 33 root-level `.py` files already; the specific duplicate-file
pairs identified are BUG-0001's audit.py/analyze_grouse.py,
BUG-0002/0003's download_landfire*.py trio, and this bug's gen_negs.py/
generate_negatives.py pair — no further undiscovered duplicate pairs were
reported by the reviewing agents, but a dedicated pass explicitly diffing
all file-name-similarity clusters is recommended as a future CR rather than
assumed complete here).
