# Design competition brief

## Project intent (from the project owner)
Predict the suitability of Ruffed Grouse habitat so that **productive areas can be located for grouse hunting** in Maine, New Hampshire and Vermont. The goal is to squeeze **as much precision and accuracy as possible** out of the model.

## What you have
- The research report: `/home/user/grouse_refactor_ec2/docs/grouse_model_report.md`. Read all of it first. It covers grouse habitat, how habitat is represented in the data, the mathematics of the current model, ML methods not yet used, and an abstract interpretation of what the model actually estimates (§5). It also explains why the leak-free AUC ceiling is about 0.76–0.77.
- The full repository at `/home/user/grouse_refactor_ec2` (Python). Read any code you need: `models.py`, `train.py`, `losses.py`, `generate_negatives.py`, `prepare_training_data.py`, `predict.py`, `calibrate.py`, `diagnose_gbm_baseline.py`, `ARCHITECTURE.md`, `CHANGELOG.md`, `grouse_model_results_summary.md`, `docs/quality/`.
- Web search and web fetch, for research: papers, datasets, state wildlife agency data, hunter survey data, remote-sensing products, and so on.

## Environment facts
- The raster data (`data/`) and the GPU live on the owner's EC2 host. They are **not** in this container, so you cannot train anything here.
- The owner runs commands on EC2. Designs should be implementable in Python with this kind of stack: PyTorch, rasterio, Google Earth Engine, sklearn/LightGBM.
- **Do NOT edit any file in the repository.** Write only to your own output file.

## The competition
You are one of five designers competing adversarially. Your job is a **clever, novel, cutting-edge model, or a new way of approaching this project**, that beats the other four designs at the owner's goal. A design can change any of these:
- the model;
- the data;
- the labels or estimand;
- the evaluation;
- the end product.

After round 1, every designer sees every other design and revises. Expect your design to be attacked, and design so it survives scrutiny.

Use explicit brainstorming techniques and **show them**. Briefly record the technique, the raw ideas it generated, and how you converged. Your assigned primary technique is in your prompt; you may add others.

## What your design document must contain
1. **Title and one-paragraph pitch.**
2. **Brainstorming record.** Techniques used, raw idea list, convergence.
3. **The design.** Enough mathematical and engineering detail to implement: data sources (with URLs), estimand, model, loss, training, inference and end product.
4. **Why it beats the status quo.** Tie the argument to the report's diagnosis, especially the claim that "the data is the ceiling" and the PU, effort-bias and estimand issues.
5. **Expected gains, quantified where possible, with honest uncertainty.** Say how a gain would be measured without fooling ourselves: spatial-block CV, independent validation data, hunter-relevant metrics.
6. **Risks, failure modes and the cheapest falsification experiment.**
7. **Implementation plan.** Ordered phases, rough effort, and the first experiment the owner could run on EC2 within a day.
8. **References.** Real URLs or DOIs. Mark anything you could not verify as **unverified**.
