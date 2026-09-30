# CR-0013 evidence manifest (deliverable 1)

Written 2026-09-30 by CR-0013's author. Lists every script that CR-0013
§ Attacks names, the local modules those scripts import, and the scripts
that produce the scratch data they read. Each file is listed with its
sha256 at the time of writing, so a later edit is visible.

Nothing here is staged or committed by this deliverable. Every file listed
is committable as it stands:
- Root-level `*.py` files are already allowed by `.gitignore` rule 2
  (`!/*.py`).
- The copies of round-7 reviewer A's scripts under
  `docs/quality/evidence/CR-0007-r7/` needed one new allow rule,
  `.gitignore` rule 9: `!/docs/quality/evidence/CR-0007-r7/*.py`. The
  directory itself was already allowed by rule 4 (`!/docs/**/`). This is
  the narrowest rule that works; `docs/quality/evidence/*.py` and the
  scripts' CSV outputs stay ignored.

## How to read this manifest
- **status**: `tracked` means the file is already in git (commit `0f58a9b`,
  the reviewer A–G set). `untracked` means deliverable 1 makes it
  committable.
- **provenance-only**: the script reads session scratch data. That data
  is not committed, lives under `/tmp`, and is not expected to survive
  (it was still on disk when this manifest was written). The script
  records how a number in the review record was produced. It is not a
  runnable test. CR-0013's own attack suite
  (`tests/test_acceptance_split.py`, deliverable 4) re-implements each
  attack as a mutation, so it does not depend on these files.
- **Code pin.** Every script imports live pipeline modules
  (`prepare_training_data`, `generate_negatives`, `analyze_grouse`,
  `grouse_data`, `models`, `train`). CR-0012 rewrites or removes some of
  their names. Run them from a worktree at `05d788d` (CR-0012 §6). Their
  `data/` inputs are the pre-CR files as they were on 2026-09-30.
  CR-0010 (rasters) and CR-0014 (`road_dist`) have since changed some of
  those inputs, so a re-run today need not reproduce the recorded numbers
  exactly.
- **Hard-coded paths.** The scratch directories are absolute:
  - rounds 5–6 (Formal A, Formal C) and the research agents:
    `SCR`/`SCRATCH = /tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad`;
  - round-7 reviewer A: `OUT = /tmp/claude-1000/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/scratchpad/cr0007_A`
    (in `lib.py` and in the `sys.path.insert` lines).

  To re-run, recreate that directory or edit the constant. The copies
  below are byte-identical to the originals and are not edited.

## 1. Attack scripts named in CR-0013 § Attacks
| file | status | sha256 | attack row | inputs | provenance |
|---|---|---|---|---|---|
| `inv_reviewB_confirm.py` | tracked | `bf0617ac240ce5495546e8a59b331bbd0968c8d19bded119ea0269055b623fa5` | Box-clipped membership | `data/` only | runnable at `05d788d` |
| `inv_reviewB_pipeline.py` | tracked | `3e4fc681e60c2439845ca6f905a07d269c18f6c6848728c48a44b85593523759` | Per-region thin, then pool | `data/` only (imports `train`) | runnable at `05d788d` |
| `inv_reviewF_i12.py` | tracked | `56a1d19387f62201e073a5cba821b72ebb4ae1d3d856fb8cd8dd506b4a7aa9dd` | Thin at 60 m | `data/` only | runnable at `05d788d` |
| `res_determ_orders.py` | untracked | `778e656f62a4aca1b9505e3a6b59aba234c888cc6ae81ba187c9f0e6bfbb35c2` | Order-dependent thinner or draw | `data/pipeline/evaluated_sightings_R.csv` | runnable at `05d788d` |
| `inv_reviewF_i14.py` | tracked | `6e3b79f1e603c2d26d1c384b0b05d5aeb0f79897a0e427b5c30fb69e3d13fa27` | Order-dependent thinner or draw | `data/` only | runnable at `05d788d` |
| `inv_reviewF_attack1.py` | tracked | `e68961552cdd895fdc2940b8be5b32d25523fb0049d6e4baccb14d9d394eb2a2` | Dropped shuffle | `data/` only | runnable at `05d788d` |
| `inv_reviewF_attack_i14.py` | tracked | `dc933d860704bf47cd46669ed4d18e95b0fa5d423577bfdee9f5496a773d1342` | Eastern-half or dense-first val draw | `data/` only | runnable at `05d788d` |
| `res_thresh_pos.py` | untracked | `973320073e183242103a139b73382441fd86d8342fb157e0515f435191fb355b` | Eastern-half or dense-first val draw | `data/` via `res_thresh_prep`; writes `res_thresh_{fair,attack}_pos.csv` to scratch | runnable at `05d788d` (writes to a hard-coded scratch path) |
| `inv_reviewH_i14c.py` | untracked | `82f14aa5557991abd41f1f224935d9a552178d8f53c785f054454a94b161dcb9` | Neighbour-preferring stratified draw | `inv_reviewH_pooled_positives.csv` (repo root, untracked, ignored), from `inv_reviewH_pool.py` | provenance-only |
| `inv_reviewD_attack.py` | tracked | `b3709803bccce71d702bdc02ef3d03f775c6b82ddefa488647c9c291062f58ed` | Two origins; ids read from the column | `data/` only | runnable at `05d788d` |
| `inv_reviewD_attack2.py` | tracked | `8e665f7712e7982096fe8b3237f6133ce500385379070e9ff3fa974e6fc3b9fd` | Two origins; ids read from the column | `data/` only | runnable at `05d788d` |
| `inv_reviewD_cr7b.py` | tracked | `c1a7c7ef016424afbc8e6fdc2efd6eeb1104b0aa15eca4ca5a331001c5f530bc` | Southern-half/southern-sixth draw | `data/` only | runnable at `05d788d` |
| `inv_reviewF_attack4b.py` | tracked | `d7fa40834bc59e4411fba16b5d9cb64c69cfe25bf48a60d58a9aeb4b50685ff8` | Southern-half/southern-sixth draw | `data/` only | runnable at `05d788d` |
| `inv_formalA_break1.py` | untracked | `2347648fd389ffa247ed89f97e824b0de53451a695a3832f7329c5caed6f6cc7` | NH-only skew (Break 1) | scratch `cand.pkl`, `pos.pkl` (§ 4) | provenance-only |
| `inv_formalA_attackC.py` | untracked | `4274834f5e45a87bc4121d2fdae4ed4e44058f13ebbdc6457963de6e4a80fd1d` | Sorted-id positive-free split (Break 2) | scratch `cand.pkl`, `pos.pkl` (§ 4) | provenance-only |
| `inv_formalA_attackC2.py` | untracked | `85f943642d2eb2f008778fca731957b13b6e52e089ba33aefb8b077ccab7988a` | Sorted-id positive-free split (Break 2) | scratch `cand.pkl`, `pos.pkl` (§ 4); `data/landfire/` | provenance-only |
| `inv_formalC_attack1.py` | untracked | `c550e609c5ab7d8c40be7cd1ecf877c2232312c5cb7c2ffa233bd653e6ced595` | 10A inter-region skew | scratch `fc_pool.csv`, `fc_pos.csv` via `inv_formalC_lib` | provenance-only |
| `inv_formalC_attack2.py` | untracked | `2d87e473f22043ebf37e8bbe188f8ccf03c101305cc99c74635b5e9b4a468fbe` | 10A inter-region skew | as `inv_formalC_attack1.py` | provenance-only |
| `inv_formalC_attack3.py` | untracked | `11562bb734a55346e6d001148507d93fee790a4ab7e5f905e8ef4b4ecf0380bf` | 10B feature-extremum split | scratch `fc_feat_pool.csv`, `fc_feat_pos.csv` | provenance-only |
| `inv_formalC_attack4.py` | untracked | `c0de79eadba061bc7d8ee8c666c9d1f47609c15ac8e74e52acba7abc43d1277b` | 10A″ northern candidates dropped by pipeline code | as `inv_formalC_attack1.py` | provenance-only |
| `inv_formalC_attack5.py` | untracked | `dd92c9278dc9e2a15fc1527db532ba7779fd8f59673e201c439e85d92547ab1d` | 10A″ northern candidates dropped by pipeline code | as `inv_formalC_attack1.py` | provenance-only |
| `inv_formalC_attack6.py` | untracked | `4eb603eac4b6e0c192688f5eb118e3f814cadaa19ca480fb748f8b198bb363e6` | 10C NonVeg top-up | as `inv_formalC_attack1.py` | provenance-only |
| `res_supply_1.py` | untracked | `c434633f7132696c461b0b57963a9da9506ac78aca8f1e0a4785c8d7cb197a52` | Pool strips at 3–20 % | scratch `fc_pos.csv`, `fc_pool.csv`, `{R}_{nlcd,evt,tiger_at1,dist2_cov_all_2025}.npy`; `data/`. Writes `rs1_cand_predropna.csv`, `rs1_pos_cov.csv` | provenance-only |
| `res_supply_2.py` | untracked | `8d5645a724e6fb75762cb0f0782f1b29eb7b0b18d82e699966c7f4b04e53e0a0` | Pool strips at 3–20 % | scratch `fc_pos.csv`, `rs1_cand_predropna.csv`, masks; `data/`. Writes `rs2_dedup_feat.csv` | provenance-only |
| `res_supply_3.py` | untracked | `2743e2f903a52f485065e4045c08952b836d2874d41dea28db0560efe5d98683` | Pool strips at 3–20 % | scratch `fc_*`, `rs1_*`, `rs2_*`; `data/` | provenance-only |
| `res_supply_4.py` | untracked | `929890e167b9a022425f91015f5cdcde5391f306400c1e65c3f78d05949c60b9` | Pool strips at 3–20 % | scratch `fc_pos.csv`, masks; `data/landfire/` (incl. pre-CR-0014 `road_dist`) | provenance-only |
| `res_supply_5.py` | untracked | `8e2d83cd1e0dcf8edb84b0be1dd536b2fdf152052b1385519394c8d99856580c` | Pool strips at 3–20 % | scratch `fc_*`, `rs1_*` | provenance-only |
| `res_supply_6.py` | untracked | `e7f291228d8ef7d3e2af4e063a15ceedafad6d6c905234190a3219e764fbad70` | Pool strips at 3–20 % | scratch `fc_*`, `rs1_*` | provenance-only |
| `res_supply_7.py` | untracked | `0c49f7af6169c559cfc475225656afcdb74d4061ad0bf14ccc46a0c0ad5d2c2b` | Pool strips at 3–20 % | scratch `fc_*`, `rs1_*`. Writes `rs7.pkl` | provenance-only |
| `res_supply_8.py` | untracked | `fda883f39895f4f627342f8a92cf1ca454b04a2492938709a3351ed5276eff96` | Pool strips at 3–20 % | scratch `fc_*`, `rs1_*`, `rs7.pkl` | provenance-only |
| `res_comp_attacks.py` | untracked | `a79346772a2b3c5971c436c9d548605d8bb8ec32ae9d8add10c66a1fc856614c` | Weight collapse; NonVeg or species monoculture | scratch `fc_feat_*` via `res_comp_stats`; `fc_*` via `inv_formalC_lib` | provenance-only |
| `inv_reviewF_attack_buffer.py` | tracked | `57d49c2c186364a5c53c932f42ab4fa19e971306aab0bcda59363038fc4984c0` | No 300 m buffer | `data/` only | runnable at `05d788d` |
| `inv_reviewH_negdup.py` | untracked | `227178a1e6abeb369fb360bd85f1ee5235f1c00ae6af851c0201e0aad5bfe7da` | Duplicate negatives, 5–10 % | `data/` only (pre-CR split files, `nlcd`) | runnable at `05d788d` |
| `inv_reviewH_i5.py` | untracked | `4394cb3cc96025cd4e8140ddf34970619865d6c0f1b4fe9ed6c2a9eacec5c923` | Windowless record kept | `inv_reviewH_pooled_positives.csv` (from `inv_reviewH_pool.py`); `data/` | provenance-only |

Attack rows with no script in this table:
- "CR-0013 round-1 A/B" rows: specified in `CR-0013-review-log.md` round 1;
  they exist only as mutations in deliverable 4.
- "Pool weight suppression; `build_weight` changed": CR-0007 v7 stated
  limits 4–5 (`bb170ea`), text only.
- "`--regions` subset": CR-0007 v7 § `--regions` hole (`bb170ea`), text only.

## 2. Round-7 reviewer A's scripts (copied to `docs/quality/evidence/CR-0007-r7/`)
Copied byte-for-byte (`cp -p`, verified with `cmp`) from round-7
reviewer A's scratch directory (see "Hard-coded paths" above). The CSV
outputs in that directory (`pos_thinned.csv`, `pool_prebuffer.csv`,
`pool_prebuffer_f9.csv`, `pool_post.csv`, `fair.csv`) are regenerable
and are not committed.

| file | sha256 | role / attack row | inputs | provenance |
|---|---|---|---|---|
| `build.py` | `40ead1deedbce7a7193ae64540fa0bbc799a5ed1b33676b24b70b85e90d73551` | data producer: independent rebuild of the post-partition positives and the pre-buffer negative pool. Writes `pos_thinned.csv`, `pool_prebuffer.csv` | `data/` only (imports `grouse_data`, `analyze_grouse`, `generate_negatives`) | runnable at `05d788d`; writes to the hard-coded `OUT` |
| `lib.py` | `6cbb379b0f0f6ea4c914526536dff399a820056ef41207432d9be87dc95f2bac` | helpers imported by every script below (split, hash split, block ids, `OUT`) | — | — |
| `feats.py` | `35380ad15d9ed374b81bc14fc0fd7deed78de27606c84ff865505045f628d39b` | data producer: samples 9 continuous features onto the pool. Writes `pool_prebuffer_f9.csv` | `pool_prebuffer.csv`; `data/landfire/` | provenance-only (scratch input) |
| `attacks.py` | `141cf72f23b5017a6e18ddd75f47098b78e753a975b1c4a396814f0cfdc44bb9` | "No 300 m buffer" (A1); "With replacement; ×20 near grouse" (A2 `replace=True`; A3 near-grouse ×20 by weight). Also counts within-class duplicates. Writes `fair.csv` | `pos_thinned.csv`, `pool_prebuffer.csv` | provenance-only |
| `comp.py` | `a2d5ae6fb534dbab5a92f2014a3dca78806a5549f29d98ec7a7bbc2936fc6d8b` | cited for "Duplicate negatives, 5–10 %" (with `inv_reviewH_negdup.py`); computes the composition rows under A1 and A3p (near-grouse ×20 by draw probability, weight column intact), the A3p of the "×20 near grouse" row | `pos_thinned.csv`, `pool_prebuffer.csv` | provenance-only |
| `valattack.py` | `6ade7ed6adbd411e66c76ac89dfc3b1ca29d9d901216b64f06f814d2eb9b7e1d` | "Val candidates near val positives thinned" | `pos_thinned.csv`, `pool_prebuffer_f9.csv` | provenance-only |
| `window_sup.py` | `021372736ca68f3f433f6f9f6e79ad3ac4e9e3e5697168818fb6a370c9919450` | window-drop count and SUP-O/SUP-R (supporting; no attack row). Writes `pool_post.csv` | `pos_thinned.csv`, `pool_prebuffer.csv`; `data/landfire/` headers | provenance-only |
| `splitdep.py` | `5d0cea8208c4d387484f730e5d5a898bd67f012d3d3d71cca62c3bad00e79ab4` | split dependence of the draw (supporting; no attack row) | `pos_thinned.csv`, `pool_prebuffer.csv` | provenance-only |
| `suploss.py` | `4b5458bae43e27195f83e99e4e38995ba49107cc2bc09bbff5582dfa0ace08f5` | support loss (supporting; no attack row); `exec`s part of `window_sup.py` | as `window_sup.py` | provenance-only |

## 3. Local modules imported by § 1 (untracked, made committable)
| file | sha256 | imported by |
|---|---|---|
| `res_thresh_prep.py` | `808d8971af86a6869526ae3000552ff8615ba2b70a6904832da9efebc5548415` | `res_thresh_pos.py` |
| `inv_formalA_harness.py` | `78e8f6d780c3bffbb4d55f82af981ebbbfdf6b5373f3c805eb73190be43e976b` | `inv_formalA_break1.py`, `inv_formalA_attackC.py`, `inv_formalA_attackC2.py`; the § 4 producer |
| `inv_formalA_thin.py` | `712448bc5c30a82f36f33453ab5bbc0d1a100e97b4da733ce5e72620db79e06c` | `inv_formalA_harness.py`, `res_supply_1/2/3/5.py`, `inv_formalC_pool2.py` |
| `inv_formalC_lib.py` | `2b32b887ed3afb8b344e4c0e9993c8f61021207ad9550961342ae5fdc722a170` | `inv_formalC_attack1–6.py`, `res_supply_3/4/5/6/8.py`, `res_comp_attacks.py`, `res_comp_stats.py`, `inv_formalC_feat.py` |
| `res_comp_stats.py` | `fa588affa5e8b068f2b70254d8ef6ba7c3dc5254a955a82f9ae9873a7a07c67e` | `res_comp_attacks.py` |

Tracked live modules they import (`prepare_training_data`,
`generate_negatives`, `analyze_grouse`, `grouse_data`, `models`, `train`,
`regions`, `blocks`, `dataset`, `model_handler`, `losses`) are pinned at
`05d788d`, not copied.

## 4. Producers of the scratch data read by § 1 (untracked, made committable)
| file | sha256 | produces | read by |
|---|---|---|---|
| `inv_formalC_pool.py` | `95c53300eedc768501595935cb899e1c3c68eb7ffc84c54c8c18f0a3e5e22469` | `fc_pos.csv` (and the first, approximate `fc_pool.csv`) | `inv_formalC_lib.py` users, `res_supply_*` |
| `inv_formalC_pool2.py` | `eebae69c29a670c6deb6f31e28f3bc0b2cd9e2f8385dea42e26cfbf207f539f8` | `fc_pool.csv`, the faithful pool (reproduces I6 = 6,230). Run after `inv_formalC_pool.py`; it overwrites `fc_pool.csv` | as above |
| `inv_formalC_feat.py` | `f7614e397bbfdb509bb7fe42f1cbbff09af494ae62a25d91d766274f517f497e` | `fc_feat_pos.csv`, `fc_feat_pool.csv` | `inv_formalC_attack3.py`, `res_comp_stats.py` |
| `inv_reviewH_pool.py` | `39329865283b856165f0e566b5f0f3cd5525f5a07130207a9a1ca221745da1a5` | `inv_reviewH_pooled_positives.csv` (repo root) | `inv_reviewH_i14c.py`, `inv_reviewH_i5.py` |
| `res_cov_masks.py` | `b181fe402a434cbf5856d83b26c81d6ee6ef1c7c6df94113881acaad240cc5b0` | `{R}_nlcd.npy`, `{R}_evt.npy` | `res_supply_1.py`, `res_cov_dist2.py` |
| `res_cov_tiger.py` | `bdf994329b790ed2330d0fb891d96be3f2be3bee4b041998ad9ed58c75d43152` | `{R}_tiger_at1.npy` (and `_at0`) | `res_supply_1/2/4.py`, `res_cov_dist2.py` |
| `res_cov_dist2.py` | `fd1fd5b14d2f2838355e3c49734159dfb07f4362a42e082c1150a05c9d420d53` | `{R}_dist2_cov_all_2025.npy` (one run per region) | `res_supply_1/2/4.py` |

**`cand.pkl` and `pos.pkl` (read by the three `inv_formalA_*` attacks)
have no producer script.** Formal A wrote them with an inline heredoc
(round 5, 2026-09-30T06:45:59Z, transcript `agent-a199a3616d6eefd65.jsonl`
of session `c7549c28`). The command is copied here verbatim so the
provenance is committed:

```
python - <<'EOF'
import numpy as np, pandas as pd
from inv_formalA_harness import *
own_all, hab = load_positives()
print("own-state evaluated (buffer source):", len(own_all))
pos = fast_thin(hab, MIN_SPACING_M, SEED)
pos['blk']=blk(pos.x_5070.values,pos.y_5070.values)
print("pooled thinned positives:", len(pos), pos.state.value_counts().reindex(R).to_dict())
bxy = own_all[['x_5070','y_5070']].values
cand = build_candidates(bxy)
print("candidates after unc/dedup/thin/pooled-buffer:", len(cand), cand.state.value_counts().reindex(R).to_dict())
cand.to_pickle("/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad/cand.pkl")
pos.to_pickle("/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad/pos.pkl")
own_all[['longitude','latitude','x_5070','y_5070','state','year','nonveg_landcover']].to_pickle("/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad/ownall.pkl")
EOF
```

## 5. Who built the attacks (PA-0021(a), E-PAa)
PA-0021(a) requires the constructed failing pipeline to be built by
someone other than the author of the acceptance set, and recorded for
re-run. The rows above were built by reviewers of CR-0007:
- reviewers B, D, F and H, rounds 1–3;
- Formal A, round 5;
- Formal C, round 6;
- round-7 reviewer A.

The `res_*` scripts came from the six v7 research agents. Those agents
were not the author, but they worked for the author, so they only
partly meet (a).

CR-0013's author wrote none of them. Rows marked "CR-0013 round-1 A/B"
were specified by CR-0013's round-1 reviewers. Deliverable 4 re-implements
every row as a mutation that can be re-run.
