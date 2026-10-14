# Control móvil en la Raspberry Pi instalada

Instalado el 2026-10-05 en `/opt/derma-onedge`, con acceso en el puerto 8080.
El servidor se ejecuta dentro del proceso de cámara. Conserva el presentador DRM,
la API en el puerto 8000, los modelos y la configuración clínica existentes.

La cámara instalada en la Pi corresponde a una versión refactorizada diferente de
`demo_camara.py` de este checkout. **No reemplazarla por la versión de este checkout.**
`pi-mobile-camera.patch` registra únicamente la integración de control móvil sobre
esa versión. El SHA-256 del archivo original es:

```
49c53cd075852cc1d4faace7f5c39190324afe6cf98c246cf770df0f737eb778
```

Los archivos de `src/mobile/` son compartidos por ambas versiones. Si se reinstala
el parche, verificar primero la versión original y ejecutar `patch --dry-run -p1`.
No aplicar de nuevo sobre la cámara ya modificada.

Se habilitó el arranque con un drop-in de systemd:
`/etc/systemd/system/derma-appliance.service.d/mobile.conf`:

```ini
[Service]
Environment="DERMA_MOBILE=1"
Environment="DERMA_MOBILE_PORT=8080"
```

El dermatólogo debe conectar su celular a la misma red y abrir
`http://192.168.1.48:8080`. La dirección puede cambiar si el router asigna otra IP.
El código de acceso cambia cuando se reinicia el servicio; se consulta en la Pi:

```bash
journalctl -u derma-appliance.service -b --no-pager | grep 'Código temporal:' | tail -1
```

El respaldo anterior a esta instalación está en
`/opt/derma-onedge/backups/mobile-20261005/`. Para volver a la cámara anterior,
restaurar `demo_camara.py` desde ese respaldo, retirar el drop-in `mobile.conf`,
ejecutar `sudo systemctl daemon-reload` y reiniciar `derma-appliance.service`.
Las sesiones, los modelos y el API no se modificaron durante la instalación.


## Lectura del diagnóstico desde el celular

La ampliación de consulta móvil publica el `last_result` final de la cámara,
con su sesión y contador de lecturas, a través del control autenticado existente.
La proyección explícita en `src/mobile/diagnostic.py` limita los campos expuestos;
no consulta historiales ni transporta imágenes, máscaras o identificadores SHM.
La interfaz presenta métricas, fototipo, recomendaciones y precauciones del equipo.
No calcula reglas clínicas ni modifica las prescripciones.

El resultado se retira al repetir una lectura, mientras se analiza, al perder
conexión, al pasar la pestaña a segundo plano o al cerrar la consulta. Los campos
que no llegan se muestran como no disponibles. No hay almacenamiento de resultados
ni del código de acceso en localStorage, sessionStorage o service workers.

La verificación del navegador utiliza datos sintéticos en un servidor separado;
no inyectar lecturas de prueba en la cámara ni en la base clínica de producción.

Respaldo previo a habilitar lectura clínica:
`/opt/derma-onedge/backups/mobile-diagnostic-20261005-155213/`.
Para regresar al panel anterior, restaurar su `demo_camara.py` y su carpeta `mobile`
en `src/mobile`, y reiniciar el servicio. Mantener el drop-in de systemd.
