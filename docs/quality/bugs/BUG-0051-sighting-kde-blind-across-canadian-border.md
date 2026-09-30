# BUG-0051: `analyze_grouse.py` sighting KDE has no neighbours across the Canadian border (PA-0023 instance)

## 1. Description
`analyze_grouse.py` computes a Gaussian KDE of sighting locations, with a
3 km bandwidth per region. The KDE is stratified by `evt_phys`. It writes
`spatial_density` and a percentile zone, `spatial_zone`, onto every
sighting.

The KDE's source is every record in the region's box. Every record was
acquired by US state (GBIF `stateProvince`, eBird US state codes), so the
source ends at the Canadian border. For a sighting within a few
bandwidths of the border, the kernel neighbourhood extends into Canada,
where no data exists. Those records get densities that are too low, and
their zones are skewed towards "Coldest 10%". Nothing marks them as
affected.

## 2. Where encountered
CR-0012 deliverable 8, 2026-09-30, while checking PA-0023's Swept? cell.
The cell lists this item: "`analyze_grouse.py` KDE against Canadian
sightings not determined — owned by CR-0012 (E7) per PA-0022". CR-0012
does not change the KDE, and E7 does not read it, so the item needed a
real owner.
- The KDE is at `analyze_grouse.py:801-817`, with the
  `kde_spatial`, `kde_joint` and `kde_stratified` functions at `:558-600`.
- The sources are US-only: `docs/quality/evidence/CR-0012-d8/canada_buffer.txt`,
  line 1, shows 43,024 of 43,024 raw sightings with `countryCode` US.

## 3. What it caused to fail
The damage is limited to diagnostics. The `spatial_density` and
`spatial_zone` columns are read only by:
- `analyze_grouse.py` itself: the hotspot and coldspot comparisons at
  `:985-1000`, and the diagnostic map at `:1050-1056`;
- `dupe_check.py:138-139`;
- `check_partition.py:585-589`, which is CR-0007's P8. P8 reproduces the
  same box-source KDE, so it cannot detect this.

`prepare_training_data.py:79` passes the columns through into the
positive files. No live code reads them in `train.py`, `dataset.py` or
`models.py`, in the envelope, in the weights or in the split. This was
checked by a grep of every git-tracked `*.py` file outside `inv_*`,
`res_*`, `docs/`, `legacy/` and `tests/`.

So it has no effect on model inputs, labels or splits. Hotspot and
coldspot statements for records near the border are biased downwards.
How many records are affected was not measured; an upper bound would be
the records within about 9 km, which is 3 bandwidths.

## 4. What the defect was
`analyze_grouse.py:801-817`:
```python
    bw = KDE_BANDWIDTH_M.get(region, 1000)
    ...
    if KDE_MODE == "spatial":
        valid['spatial_density'], valid['spatial_zone'] = kde_spatial(valid, bw)
    elif KDE_MODE == "joint":
        valid['spatial_density'], valid['spatial_zone'] = kde_joint(valid, bw)
    elif KDE_MODE == "stratified":
        valid['spatial_density'], valid['spatial_zone'] = kde_stratified(valid, bw)
```
`valid` holds the box records of every US state. The kernel is fitted on
them and evaluated at the same points, with no treatment of
neighbourhoods that cross the border.

## 5. Root cause analysis (Five Whys)
1. **Why are densities near the border too low?** The kernel's
   neighbourhood includes Canadian land, which has no records.
2. **Why are there no records there?** Acquisition is keyed to US
   states.
3. **Why was this not handled?** CR-0007 fixed the KDE's source *across
   state lines*: it moved to every box record of any state (PA-0018). It
   did not consider the national border.
4. **Why was it still open?** PA-0023's sweep marked it "not
   determined". It was then owned by CR-0012, whose scope (the split and
   the draw) never included the KDE.

**Root cause:** a neighbourhood computation's source was chosen by
acquisition label (the US states), and that source ends at a national
border inside the neighbourhood. This is the same root cause as BUG-0050.

## 6. Corrective action
**None yet. It needs a CR**, because it changes `spatial_density` and
`spatial_zone` values in `evaluated_sightings_R`, a data schema input to
CR-0012 and CR-0013. There are two options under PA-0023:
- acquire Canadian sightings near the border as a KDE-only source;
- write `spatial_density` as NaN (zone "border-limited") for records
  whose kernel neighbourhood, taken as 3 × bandwidth, reaches land
  outside the US counties.

The rebuild would change S's digest, so CR-0012 and CR-0013 would need
to be re-run. Priority is low, because no model input is affected.

**Owner: its own CR** (re-owned by CR-0017 deliverable 8, 2026-09-30;
tracker). It was first assigned to "the same new CR as BUG-0050", but
CR-0017 (which fixed BUG-0050) excluded it under CR-0011 A5: it is a
different computation, and it changes S, which re-runs CR-0012 and
CR-0013 from the positives.

**Scope widened by the CR-0017 sweep (BUG-0064 §8, 2026-09-30).** The
KDE's source is the records acquired for ME, NH and VT, so its data
domain is ME ∪ NH ∪ VT (PA-0032), not the United States. The KDE is
therefore blind at the **NY and MA state lines** as well as at the
Canadian border, like the negatives' buffer was (BUG-0064). The sweep
located the affected code at `6342f2a`:
- `analyze_grouse.py:560-601` (`kde_spatial`, `kde_joint`,
  `kde_stratified`), applied at `:816-820`; the diagnostic map surfaces
  at `:698` and `:725` use the same source;
- `check_partition.py:516` (`kde_density`) and `:575` (P8), which
  reproduces the same KDE and so shares the blind edges.
The fix's CR must use the domain D of CR-0017 (the three states' county
union), not "land outside the US counties" as the nodata option above
says. No separate BUG is filed for the NY/MA edges.

Status: **OPEN** (low priority; diagnostics only).

## 7. Recurrence review
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` (as for BUG-0050).

**Match: BUG-0037 / PA-0023.** This is the same mechanism, and it is the
KDE item listed in PA-0023's own sweep. BUG-0050, filed in the same pass,
has the same root cause.

**Prior-preventive-action failure analysis:** as in BUG-0050 §7.
- PA-0023's text covers this case.
- The sweep's deferral put the item under an owner (CR-0012) whose scope
  did not include the KDE.
- That is a PA-0024(a) failure: the disposition's owner does not contain
  the fix. It was caught when that disposition was checked.

## 8. Preventive action
**No new PA.** PA-0023, PA-0022 (an owner is required) and PA-0024(a) (the
owner must contain the fix) cover it. PA-0023's Swept? cell now names
BUG-0051 as the owner.
