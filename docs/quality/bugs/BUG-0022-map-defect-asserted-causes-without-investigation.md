# BUG-0022: A reported defect in a prediction map was answered with asserted causes instead of an investigation

## 1. Description
The user reported that a `predict.py` suitability map around Errol, NH
(`--region NH --bounds -71.25 44.70 -70.95 44.90`, checkpoint `bce.pth`)
was wrong, and supplied two Google Earth screenshots. Over four replies,
the assistant (the Claude Code session working in this repository):

1. named a cause without having confirmed it, and proposed a code change
   and a retrain for it;
2. when the user said that was not the problem, re-asserted a cause
   built on the same observation, with a different mechanism;
3. when rejected again, did its first real checks of the pipeline, but
   still closed by offering options that led back to the rejected frame;
4. only then traced inputs, reader, model, calibration and rendering
   end to end, which is the investigation that should have come first.

The defect the user reported has **still not been identified**. This bug
is about how it was investigated, not about the map.

## 2. Where encountered
Process defect in the assistant's diagnostic conduct during a Claude Code
session (2026-09-29), not in the repository's Python code. The code it
reasoned about:
- `generate_road_distance.py:113-125` (`load_paved_roads`, per-state
  TIGER counties via `STATE_FIPS`), cited as the cause in reply 1 after a
  single `grep`;
- `download_rev.py:19-23` (`BOXES_COORDINATES`), `download_tcc_nlcd.py`
  / `download_treemap.py` (`region_grid`, EE `Rectangle` exports),
  `predict.py:695-776` (`generate_kmz`): read only in replies 3-4.

## 3. What it caused to fail
- **Three rounds of the user's time spent on wrong answers.** Each one
  had to be rejected by the user before the next.
- **A change was proposed for a cause nobody had verified.** Reply 1
  offered to rewrite `generate_road_distance.py`, regenerate every
  `road_dist` raster and retrain, with no check tying that mechanism to
  the reported symptom.
- **Uncertainty was stated as a finding.** Reply 1 said the edge "is the
  NH–ME state line, not habitat" and called road distance "the likely
  cause" on the strength of reading one function.
- **The investigation never found the defect.** When the systematic trace
  was finally done (reply 4) it found no defect, but it had never been
  aimed at the symptom the user saw, because that symptom was never
  established.

## 4. What the defect was
The faulty logic, quoted from the assistant's replies:

Reply 1, after one `grep` of `generate_road_distance.py`:
```
**2. The map: the sharp red edge is the New Hampshire–Maine state line,
not habitat.**
...
The likely cause is the road-distance input:
...
Want me to make that change and push it to `main`?
```

Reply 2, after the user said "that is not the issue, check again":
```
I looked at both screenshots again closely. I still can't rule out the
state line, but I may be focusing on a different problem than the one
you see.
...
If you know `road_dist` covers Maine, the edge could still come from
another input that ends at the state line.
```

Reply 3, after "I told you that isn't the ... problem": it checked KMZ
georeferencing (a real check) but then asked the user to choose from a
list that led straight back to the east side of the map.

The data that could have tested the first claim in reply 1 was already
in the repository and was not read until reply 4: `download_rev.py:21`
(`"NH": (-72.626, 42.605, -70.600, 45.398)`) shows every LANDFIRE, TCC,
NLCD and TreeMap input for the NH region extends to −70.60, well east of
the map. Nobody had asked the user what they found wrong; the answer
started from what looked most striking.

## 5. Root cause analysis (Five Whys)
1. *Why was a cause the user rejected offered first?* The assistant
   treated the most visually striking feature of the screenshot (a sharp
   colour edge on a political boundary) as the defect, without asking
   what the user meant by "something is wrong."
2. *Why was it presented as the likely cause and not as a hypothesis?*
   A single `grep` found a mechanism consistent with the image (per-state
   road data), and a plausible mechanism was taken as confirmation. No
   check existed that could have failed it: coverage extents, raw input
   values (`inspect_point.py`), or the user's own description.
3. *Why did the second and third replies circle back to the same frame?*
   When the user rejected the hypothesis, the assistant replaced only the
   mechanism (road data → "another input that ends at the state line")
   and kept the premise (the state line is the problem). Rejecting a
   hypothesis was handled as "try a sibling," not "discard the frame and
   restart from the symptom."
4. *Why wasn't the systematic trace done first, when it was cheap?* The
   project had already recorded this lesson in `CHANGELOG.md`, "The
   road-hugging investigation" (2026-09-18): three plausible hypotheses
   were disproven, and the cause was found only by checking the model's
   raw inputs against known ground truth. That lesson was never turned
   into a standing rule in `PREVENTIVE_ACTIONS.md`, so nothing required
   it to be applied at the moment of diagnosis.
5. *Why can't the process catch this on its own?* Every existing
   preventive action targets code mechanisms. None governs how a
   reported wrong output is diagnosed, so the sequence "ask for the
   symptom, trace, verify, then conclude" relied on judgement in the
   moment. `CLAUDE.md` §3.4 names exactly this failure mode: a rule that
   depends on memory alone.

**Root cause:** there is no standing rule that a reported wrong output
must be diagnosed from an established symptom, through checks that could
prove a hypothesis wrong, before any cause is stated or any fix proposed.
Without that rule, the first plausible mechanism was presented as the
answer, and a rejection was answered with a variant of the same premise
instead of a fresh investigation.

## 6. Corrective action
- This record, and PA-0016 (below) added to `PREVENTIVE_ACTIONS.md`.
- The end-to-end trace that should have come first was done in reply 4
  and found no code defect in these stages:
  - **Input coverage:** every input except `road_dist` is a rectangle to
    −70.60 (`download_rev.py:21`, `region_grid`).
  - **Train/predict parity:** window centre index 32 in both
    `dataset._read_patch` and `predict_region`; same `FEATURE_SPEC`
    scaling; same `MISSING_CODE`/NaN nodata convention.
  - **Model rebuild:** `predict.load_model` rebuilds geometry from the
    checkpoint config (`config_to_model_kwargs`,
    `spec_with_checkpoint_vocab`) and sets eval mode.
  - **Calibration:** applied as scale then bias.
  - **KMZ placement:** reprojected to EPSG:4326, with the `LatLonBox`
    taken from the reprojected corners.
- **The reported map defect is not resolved.** It needs the user's
  description of the symptom and a raw-input check at a location the user
  identifies as wrong (`inspect_point.py --region NH --lon <lon> --lat
  <lat> --model bce.pth`).

Status: **OPEN**. The process corrective action is in place; the map
defect the user reported is unidentified.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for (a) the same
failure and (b) a different failure with the same root cause (a
diagnostic or verification step that depends on memory):
- **BUG-0019** (sweeps not run) has the same root-cause *class*: a
  required process step with no structural checkpoint. It concerns
  sweeps after a preventive action, not diagnosis of a reported symptom,
  so it is related, not a recurrence.
- **BUG-0017** is the counter-example: a suspected defect correctly
  recorded as "unconfirmed" and not acted on. The labelling discipline
  existed in the QMS but was not applied here.
- No preventive action covers diagnosis. **None found** as a direct prior.
- Outside the QMS, `CHANGELOG.md` "The road-hugging investigation"
  (2026-09-18) records the same pattern: plausible hypotheses offered
  first, with raw-input ground-truth checking the step that finally
  worked.

**Prior-lesson failure analysis:** that lesson lived only as narrative in
the change log ("Do not re-run these" about specific hypotheses), not as a
rule. It named the hypotheses to avoid, not the method to use, so it
could not stop a *new* hypothesis being asserted the same way. PA-0016
turns the method into a rule.

## 8. Preventive action
**PA-0016** (new, see `PREVENTIVE_ACTIONS.md`). It targets the mechanism,
cause-before-evidence and frame-anchoring, not the state-line trigger:

1. **Establish the symptom before any hypothesis.** Get what is wrong, in
   the reporter's words, with at least one concrete location or value.
   If the report is only "something is wrong," ask. Do not infer the
   defect from the most striking feature of an image.
2. **Every stated cause must have survived a check that could have
   failed it:** raw input values at the affected location
   (`inspect_point.py`), coverage/extent of the inputs involved, or an
   end-to-end trace of the path that produces the output. Until then,
   label it "untested hypothesis," and never propose a code, data or
   retraining change for it.
3. **A rejected hypothesis retires its premise, not just its
   mechanism.** The next step is the systematic trace (inputs → reader →
   model → calibration → rendering), not a sibling hypothesis resting on
   the same observation.
4. **Diagnosis is not done until the reported symptom is explained or
   explicitly recorded as unexplained.** "No defect found in the stages
   I checked" is reported as exactly that, with the stages listed.

Mechanical enforcement (`CLAUDE.md` §3.4): not feasible as a CI check,
because the defect is in conversational diagnosis, not code. The
structural aid is that any BUG doc raised from a user report must include
the reporter's symptom statement and the list of checks that ruled
hypotheses in or out. Manual review is the enforcement until a template
exists.

**Sweep (§3.5):** reviewed the diagnostic statements made in this session
before this incident:
- training-run interpretations: grounded in the logged metrics;
- "0.82 is not comparable to 0.886": checked against `CHANGELOG.md`'s
  year-gap entry before being stated;
- the BUG-0009 +0.5 px remark: explicitly labelled unverified.

Also re-read BUG-0001..0021 for causes stated without a recorded check:
BUG-0017 is already labelled unconfirmed; the others quote the code they
diagnose. No further instance found.
