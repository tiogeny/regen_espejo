# Espejo web REGEN

La migración de la Raspberry `192.168.1.48` ya se realizó con Cage y Chromium.
Ver [configuración instalada, respaldo y restauración](README-regen-pi-installed.md).

La referencia visual es `WhatsApp Image 2026-10-05 at 4.53.06 PM.jpeg`.
La página conserva el espejo circular, aro cálido, paleta oliva/dorado,
marca centrada, ampliación circular de piel, indicadores, tarjeta de jabón,
diagrama de ingredientes y navegación por puntos.

## Ejecutar este checkout

Desde la raíz, con los modelos locales y la cámara disponibles:

```bash
DERMA_WEB=1 DERMA_TOUCH_MODE=1 .venv/bin/python demo_camara.py
```

Abrir `http://127.0.0.1:8080/mirror` en el navegador del mismo equipo.
El modo web es el predeterminado. `DERMA_WEB=1` inicia el servidor web sin crear
la ventana de OpenCV; `DERMA_WEB=0` permite ejecutar la interfaz anterior.
El navegador no solicita la cámara: Python la captura y sirve fotogramas JPEG
en RAM, con un máximo de ocho actualizaciones por segundo. El reflejo ya viene
invertido horizontalmente y recortado al centro; no volver a invertirlo.

Señalar una zona de piel con el índice, sostenerlo hasta fijarla y retirar la
mano. La detección existente valida la zona y espera estabilidad antes de
analizar. Los círculos siguen el punto detectado y la ampliación usa el mismo
fotograma y recorte. Es señalamiento 2D; no certifica contacto físico.
El botón «Nueva lectura» utiliza la cola y revisión existentes de la cámara.

Los indicadores de hidratación, oleosidad y pH muestran «Sin medición»:
los modelos actuales no proporcionan esos datos. El jabón, nombres de
ingredientes y colores reproducen la referencia; la fórmula no está asignada
ni tiene porcentajes inventados. Las recomendaciones reales, cuando existen,
se muestran en los detalles. El control móvil permanece en la raíz para
conexiones desde la LAN y no recibe las imágenes del espejo.

## Arranque automático en Raspberry Pi

En un equipo nuevo con Raspberry Pi OS de escritorio de 64 bits:

1. Instalar Chromium y curl; disponer de todos los modelos y dependencias locales.
2. Adaptar `regen-web.service.example` al usuario y ubicación del proyecto.
   Instalarlo como `/etc/systemd/system/regen-web.service` y habilitarlo:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now regen-web.service
   ```

3. Habilitar inicio automático de la sesión gráfica en Raspberry Pi OS.
4. En Raspberry Pi OS con labwc, añadir al archivo
   `~/.config/labwc/autostart` del usuario de la sesión gráfica, conservando su
   contenido actual y adaptando la ruta:

   ```bash
   /bin/bash /opt/derma-onedge/deploy/launch-regen-kiosk.sh &
   ```

   En escritorios que admiten autostart XDG se proporciona también
   `regen-kiosk.desktop.example`. Utilizar un solo mecanismo de inicio.
5. Desactivar el apagado automático de pantalla desde la configuración del escritorio.
6. Reiniciar y verificar cámara, selección, lectura y recuperación del servicio.

El lanzador espera que la cámara entregue imágenes antes de abrir Chromium en
modo kiosco. El servicio se reinicia si el proceso termina. Estas plantillas
son para equipos nuevos; la Pi existente conserva su runner y utiliza
`regen-kiosk.service` según el documento de instalación.

**Pi ya instalada:** leer `README-mobile.md`. Su proceso de cámara es otra
versión refactorizada con presentador DRM; no reemplazarlo por `demo_camara.py`
ni activar una segunda cámara en paralelo. Primero integrar en esa versión
`ScanControl.publish_preview(frame, selector)` sobre el fotograma reflejado,
antes de dibujar el HUD, y omitir el presentador al activar `DERMA_WEB=1`.
Deshabilitar el presentador antiguo al cambiar al escritorio/kiosco y conservar
la configuración existente de cámara, API y modelos. Estas instrucciones no
describen la integración; el documento de instalación registra la verificación
real realizada en la Pi.

Referencia del arranque con labwc:
[guía oficial de Raspberry Pi](https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/).

## Verificación local sin cámara

```bash
.venv/bin/python -m pytest tests/test_web_mirror.py tests/test_mobile_control.py tests/test_face_touch.py -q
```

La página y los endpoints de cámara son locales; se comprueba recorte,
coordenadas, eliminación de imágenes al desconectar, caducidad, control de
reinicio y rechazo de acceso remoto/orígenes externos.

Con Playwright y Chromium de pruebas instalados:

```bash
.venv/bin/python scripts/check_mirror_browser.py
```

Comprueba los fotogramas, la ampliación, cuatro tamaños de pantalla, los
detalles, el reinicio y la desconexión. Guarda una captura con imagen sintética
en `/tmp/regen-mirror.png`; no usa cámara ni base de datos de producción.
