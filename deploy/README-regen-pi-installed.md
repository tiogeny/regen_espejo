# REGEN instalado en la Raspberry

La Raspberry `192.168.1.48`, usuario `raspberry`, utiliza Raspberry Pi OS Lite
Debian 13 (trixie), ARM64. El reloj del dispositivo registró la instalación el
2026-10-06 UTC; la sesión de trabajo corresponde al 2026-10-05 en Lima.
No se almacenó la contraseña de SSH en los archivos del proyecto.

## Integración

Se conservó el runner y la API de inferencia existentes. La versión de cámara
instalada fue adaptada mediante `pi-regen-camera.patch`; no se reemplazó por
la versión diferente de este checkout. Su SHA-256 antes del cambio era:

```
a9dcb456a1a2c4d6f59a36957c2b45b19f8dfd484024a9e86676becb89c09dfc
```

`pi-regen-mobile.patch` amplía su servidor original con el espejo local sin
importar el motor de recomendaciones de este checkout, ausente en esa Pi.
SHA-256 del servidor anterior:

```
152d2decb07e090ca042e9561127be08a9a73bd0ef96139e2c7325e67c3559d5
```

Se copiaron `mirror.html/css/js`, la proyección de diagnóstico, los helpers de
señalamiento y área localizada y `hand_landmarker.task`. Las calibraciones,
modelos ONNX, API y datos existentes no fueron sustituidos. La lectura localizada
se calcula sobre la máscara del modelo instalado; no se asignan las
prescripciones globales del rostro a la zona señalada.

## Servicios

- `derma-appliance.service` conserva el proceso de API y cámara. Su drop-in
  `regen-web.conf` activa `DERMA_WEB=1`, `DERMA_TOUCH_MODE=1` y el presentador
  `none`, liberando DRM para Cage.
- `regen-kiosk.service` abre Cage y Chromium en tty1, con sesión PAM propia.
  Se instalaron `cage`, `chromium` y sus dependencias mediante apt.
- El target predeterminado pasa a `graphical.target`; el kiosco inicia
  automáticamente sin requerir un escritorio completo ni intervención manual.
- El navegador abre `http://127.0.0.1:8080/mirror` a pantalla completa y espera
  que la cámara entregue un fotograma antes de iniciar la página.
- El perfil y caché del navegador están en `/run/user/1000/regen-chromium`,
  almacenamiento volátil. No se generaron capturas de la cámara para verificarlo.

La depuración del navegador se habilitó temporalmente mediante un drop-in bajo
`/run/systemd/system/regen-kiosk.service.d`, accesible únicamente por loopback.
Ese drop-in desaparece al reiniciar. El servicio normal no abre un puerto de
depuración.

Se verificaron los servicios activos, la página real de Chromium, cámara
visible, círculo de 768 × 768 dentro de una pantalla de 1280 × 800 y ausencia de
desbordamiento. La cámara produjo una lectura real con estado `DIAGNOSTICADO`,
señalamiento `COMPLETADO`, región seleccionada y porcentaje localizado. No se
copiaron imágenes ni datos personales al informe de verificación.

Después de reiniciar físicamente el sistema por SSH se verificó el nuevo
arranque: ambos servicios activos y habilitados, target `graphical.target`,
Chromium con `--kiosk --ozone-platform=wayland` en la URL del espejo y cámara
conectada esperando una nueva selección. La depuración temporal desapareció
tras el reinicio. El servicio de kiosco tuvo un reintento al iniciar y quedó
activo con la sesión gráfica en tty1.

Configuración de Cage basada en la
[documentación oficial de su servicio systemd](https://github.com/cage-kiosk/cage/wiki/Starting-Cage-on-boot-with-systemd).

## Respaldo y restauración

Respaldo previo:

```
/opt/derma-onedge/backups/regen-web-20261006-001311
```

Incluye la cámara original, la carpeta móvil anterior, los drop-ins previos y
el target de arranque anterior (`multi-user.target`). Para volver al presentador
anterior:

```bash
sudo bash /opt/derma-onedge/deploy/rollback-regen-pi.sh
```

El script detiene y deshabilita el kiosco y restaura los archivos anteriores.
Los paquetes de navegador y el modelo de mano pueden permanecer instalados;
la cámara anterior no los utiliza. Reiniciar para comprobar el arranque anterior.
