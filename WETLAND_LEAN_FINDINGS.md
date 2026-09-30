# Wetland-Lean Diagnosis and Remediation Plan

## Symptom
Suitability maps lean toward wetland areas instead of the expected
aspen/new-growth covers. Symptom appeared after the TCC/NLCD features
were added.

## Root cause (from code inspection; confirm with diagnose_wetland.py)

1. PRIMARY - negative sample contains almost no wetlands.
   get_negatives.py TARGET_SPECIES lists six species (Ovenbird,
   Black-throated Blue Warbler, Hermit Thrush, Blue-headed Vireo,
   Brown Creeper, Pileated Woodpecker) - ALL mature upland-forest
   birds, no wetland guild. The negative class is therefore "places
   upland-forest birds are reported"; wetland interiors barely exist
   as negatives, and grouse positives in lowland alder covers make
   wetland signatures purely-positive evidence.

2. AMPLIFIER - Annual NLCD provides a shortcut. Class 90 (woody
   wetlands) is one coarse categorical code; a class that appears
   almost only under positive labels plus a crisp indicator for it is
   textbook shortcut learning. Fragmented EVT codes never exposed
   wetlandness this cleanly, which is why the lean is new.

3. STRUCTURAL - shrub wetlands mimic regen in this feature space
   (low EVH, dense EVC/CC, low CH, low-mid TCC) and no hydrology or
   topographic-wetness layer exists to separate them. The uniform
   background negatives (~1:1 per positive, wetlands ~5-10% of area)
   are too small a counterweight under 50/50 stratified batching.

## Verification (run FIRST, before any fix)
    python diagnose_wetland.py
  A: per-class empirical positive fraction of train data - wetland
     classes (90/95) near 1.0 proves the label shortcut exists.
  B: val scores by center NLCD class - wetlands at the top confirms
     the model learned it.
  C: scores with the nlcd channel ablated to its padding vector.
     DECISION POINT: large wetland drop under ablation = shortcut on
     the nlcd code (fixes 1+3 below suffice); wetland scores that
     survive ablation = structural mimicry (also consider fix 4).

## Remediation, in order of correctness
1. Fix the negatives at the root: add wetland-guild species to
   TARGET_SPECIES in get_negatives.py - Alder Flycatcher (Empidonax
   alnorum), Common Yellowthroat (Geothlypis trichas), Swamp Sparrow
   (Melospiza georgiana), Northern Waterthrush (Parkesia
   noveboracensis) - re-pull GBIF, regenerate negatives
   (gen_negs.py), retrain. This repairs the target-group background.
2. Cheap counterweight available immediately: raise --an-background
   to 3.0-5.0 so uniform negatives (which include wetlands
   proportionally) carry more weight.
3. Confirming ablation run: retrain with
   --features evt evh evc sclass fdist ch cc tcc (nlcd omitted).
   If the wetland lean shrinks, the shortcut is corroborated; nlcd
   can return once the negatives are fixed.
4. If mimicry survives ablation (C): add a topographic-wetness or
   hydrology layer (e.g. TWI from a DEM, or NWI wetlands as an
   explicit mask/feature) so wetland-shrub and upland regen become
   separable on merit.

## Success criteria
- diagnose_wetland.py part A: wetland positive fraction moves toward
  the landscape base rate after negative regeneration.
- Part B: wetland classes no longer top the score table; deciduous/
  shrub regen classes rise.
- rank score on the unchanged validation set does not regress
  materially (validation is never filtered/altered by these fixes).
