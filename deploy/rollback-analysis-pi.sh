#!/usr/bin/env bash
set -euo pipefail
app=/opt/derma-onedge
backup="${1:-$(cat "$app/deploy/analysis-backup-path.txt")}"
case "$backup" in "$app"/backups/analysis-*) ;; *) echo 'Ruta de respaldo inválida' >&2; exit 1;; esac
[[ -f "$backup/demo_camara.py" && -f "$backup/src/inference/pipeline.py" ]]
systemctl stop regen-kiosk.service derma-appliance.service
cp -a "$backup/demo_camara.py" "$app/demo_camara.py"
cp -a "$backup/src/inference/pipeline.py" "$app/src/inference/pipeline.py"
cp -a "$backup/src/mobile/." "$app/src/mobile/"
systemctl start derma-appliance.service regen-kiosk.service
printf 'Análisis restaurado desde %s.\n' "$backup"
