# save as scan_ckpts.py in the project directory and run: python scan_ckpts.py [extra paths...]
import glob, sys
import torch

paths = sorted(set(glob.glob("*.pth") + glob.glob("*.pth.member*")
                   + glob.glob("data/models/*.pth*") + sys.argv[1:]))
for p in paths:
    try:
        obj = torch.load(p, map_location="cpu", weights_only=True)
    except Exception as e:
        print(f"{p}: could not load ({type(e).__name__}: {e})")
        continue
    if isinstance(obj, dict) and "state_dict" in obj:
        sd, cfg = obj["state_dict"], obj.get("config") or {}
        kind = "wrapped"
    else:
        sd, cfg, kind = obj, {}, "BARE (no config)"
    conv1 = sd.get("conv1.weight")
    stem = conv1.shape[1] if conv1 is not None else "?"
    emb = sorted(k[len("embeddings."):-len(".weight")] for k in sd
                 if k.startswith("embeddings.") and k.endswith(".weight"))
    print(f"\n{p} [{kind}] stem_in_channels={stem}")
    print("  features:", cfg.get("features"))
    print("  embeddings present:", emb)
    for k in ("pool", "center_skip", "keep_early_resolution", "early_attn",
              "early_attn_pos_mode", "dual_branch", "dual_branch_channels",
              "loss", "an_pos_weight", "focal_alpha"):
        if k in cfg:
            print(f"  {k}: {cfg[k]}")
