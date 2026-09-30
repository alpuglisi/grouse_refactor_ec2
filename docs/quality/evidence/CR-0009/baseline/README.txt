CR-0009 deliverable 2 (§ Baselines): baseline capture, 2026-09-30.
Read-only on data/ and /home/ec2-user/grouse_backup/CR-0007/; written only here.
Maps were scored in-process by symptom_check.py --reproduce; the predict.py CLI was not run.

Commands (repo root):
  python docs/quality/evidence/CR-0009/baseline/capture_baseline.py points
  python symptom_check.py --reproduce \
      --calibration docs/quality/evidence/CR-0009/baseline/calibration.json \
      --pairs docs/quality/evidence/CR-0009/baseline/inv_matched_pairs.csv \
      --points docs/quality/evidence/CR-0009/baseline/points_S1_NH_region_files.csv \
      --out docs/quality/evidence/CR-0009/baseline/R \
      --evidence docs/quality/evidence/CR-0009/baseline/R_reproduction.txt
  python docs/quality/evidence/CR-0009/baseline/capture_baseline.py scores
  (cd docs/quality/evidence/CR-0009/baseline && sha256sum -c SHA256SUMS)

Files:
  points_capture_log.txt          S0 verified against CR-0007-backup-manifest.txt; S0 vs S1 byte-identity; copies
  points_S{0,1}_all_region_files.csv   in-box records of all three region files (lon, lat, label, split,
                                  source_file_region, TIGER side, duplicate_across_files); not a reference set
  points_S{0,1}_NH_region_files.csv    reference set (NH region files), --points form
  calibration.json                copy of data/calibration/calibration.json (fitted on gap3.pth)
  inv_matched_pairs.csv           frozen pairs (copy of the untracked repo-root file)
  R_reproduction.txt, R/          R run against the copies above (maps, per-model report/results/pairs/points)
  item3_scores.{txt,json}         gap3/bce scores at every point set, AUC/AP by side x split
  inputs_sha256.txt               sha256 of every input read (checkpoints, calibration, pairs, county file,
                                  point files S0 and S1, NH rasters)
  capture_baseline.py             the capture script
Item 4 (whole-ME map) is not captured here (runs after CR-0012; rasters/checkpoints only).
