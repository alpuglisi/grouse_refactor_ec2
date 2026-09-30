#!/bin/bash
# CR-0009 deliverable 9 map regeneration (user go-ahead 2026-09-30). Extents of the ME/VT custom maps
# are the lon/lat bounds of the pre-CR files (rasterio transform_bounds of the backed-up tifs; BUG-0028:
# original request bounds unknown, so the extent may differ by the window padding).
set -e
cd /home/ec2-user/grouse2
M=docs/quality/evidence/CR-0009/maps
run() { name=$1; shift; echo "== $name start $(date -u +%FT%TZ): python predict.py $*" | tee -a $M/maps.txt
  nice python predict.py "$@" > $M/$name.log 2>&1
  echo "== $name end $(date -u +%FT%TZ) exit 0" | tee -a $M/maps.txt; }
run NH_custom --region NH --model grouse_cr0009.pth --bounds -71.25 44.70 -70.95 44.90
run VT_custom --region VT --model grouse_cr0009.pth --bounds -72.92913 43.57997 -72.57322 43.87024 --stride 8
run ME_custom --region ME --model grouse_cr0009.pth --bounds -67.33428 44.69736 -67.06689 44.9043 --stride 16
run ME_region --region ME --model grouse_cr0009.pth --stride 8
sha256sum data/predictions/* | tee -a $M/maps.txt
