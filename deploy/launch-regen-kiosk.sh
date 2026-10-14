#!/usr/bin/env bash
# Ejecutar desde Cage o desde el inicio de la sesión gráfica.
set -eu
port="${DERMA_MOBILE_PORT:-8080}"
url="http://127.0.0.1:${port}/mirror"
if command -v chromium >/dev/null 2>&1; then
    browser=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
    browser=chromium-browser
else
    echo 'Instala Chromium antes de iniciar el espejo REGEN.' >&2
    exit 1
fi
profile="${XDG_RUNTIME_DIR:?Se requiere una sesión gráfica activa}/regen-chromium"
mkdir -p "$profile"
flags=(--kiosk --incognito --noerrdialogs --no-first-run --disable-session-crashed-bubble
       "--user-data-dir=$profile" "--disk-cache-dir=$profile/cache" --password-store=basic)
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    flags+=(--ozone-platform=wayland)
fi
# Solo mantenimiento local; se omite en el arranque normal.
if [[ -n "${REGEN_DEBUG_PORT:-}" ]]; then
    flags+=(--remote-debugging-address=127.0.0.1 "--remote-debugging-port=${REGEN_DEBUG_PORT}")
fi
while ! curl --fail --silent --max-time 2 "http://127.0.0.1:${port}/mirror/api/frame" >/dev/null; do
    sleep 1
done
exec "$browser" "${flags[@]}" "$url"
