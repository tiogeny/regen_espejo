#!/usr/bin/env bash
# Restaurar el presentador anterior desde el respaldo creado durante la migración.
set -euo pipefail
app=/opt/derma-onedge
backup="${1:-$(cat "$app/deploy/regen-backup-path.txt")}"
case "$backup" in "$app"/backups/regen-web-*) ;; *) echo 'Ruta de respaldo inválida' >&2; exit 1;; esac
[[ -f "$backup/demo_camara.py" && -d "$backup/src/mobile" ]]
systemctl disable --now regen-kiosk.service
systemctl stop derma-appliance.service
cp -a "$backup/demo_camara.py" "$app/demo_camara.py"
cp -a "$backup/src/mobile/." "$app/src/mobile/"
# Retirar solo la configuración añadida por esta migración.
if [[ -f /etc/systemd/system/derma-appliance.service.d/regen-web.conf ]]; then
    unlink /etc/systemd/system/derma-appliance.service.d/regen-web.conf
fi
systemctl set-default "$(cat "$backup/system/default-target.txt")"
systemctl daemon-reload
systemctl start derma-appliance.service
printf 'Restaurado desde %s.\n' "$backup"
