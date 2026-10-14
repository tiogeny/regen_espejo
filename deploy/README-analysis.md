# Análisis funcional en REGEN

Instalado sobre la Raspberry `192.168.1.48`. La interfaz muestra el análisis
por cámara directamente en el espejo: área segmentada de la zona, edad estimada
y fototipo estimado. El gráfico circular representa el área segmentada y el
resto de la misma zona; no representa ingredientes ni la severidad de una lesión.

La pestaña «Sensores» conserva los indicadores de hidratación, oleosidad y pH
como «Sin sensor». No se deducen esos valores ni se inventa una fórmula de jabón.
La medición de esos parámetros se realiza con instrumentos específicos, como
muestran estos [métodos de medición publicados](https://pmc.ncbi.nlm.nih.gov/articles/PMC5122300/).

## Flujo

1. Señalar una zona de piel con el índice y sostenerlo hasta fijarla.
2. Retirar la mano y mantener el rostro estable.
3. Validar exposición y coordenadas de la zona en el recorte facial RGB.
4. Ejecutar los modelos ONNX existentes y obtener su máscara de segmentación.
5. Calcular el porcentaje localizado con el círculo como denominador y el
   porcentaje global con los píxeles exactos del soporte facial.
6. Presentar resultados y ampliación de la **captura analizada** con la máscara
   resaltada en dorado. La cámara de fondo continúa mostrando el reflejo en vivo.

La ampliación se mantiene solo en RAM y está vinculada al identificador de
análisis vigente. Se retira al repetir una zona, cambiar de persona, desconectar
o dejar la página en segundo plano. No se guardan fotografías desde este flujo.

«Repetir zona» conserva la sesión. «Nueva persona» solicita confirmación, cierra
la sesión, limpia las lecturas anteriores del espejo y crea otro identificador.
Los botones esperan el acuse de la cámara antes de habilitar otra acción.

## Validez y errores

Las cifras son estimaciones de los modelos instalados, pendientes de validación
clínica para su uso final. Un porcentaje segmentado de cero no descarta una
lesión ni equivale a diagnosticar piel sana. La estimación espectral de fototipo
no reemplaza una evaluación de la respuesta de la piel al sol.

Se rechazan capturas de zona muy oscuras o sobreexpuestas. Los controles técnicos
son media de gris <20 o >235, más de 35% de píxeles casi negros (<=3), o más de
25% saturados (>=252). No son umbrales de enfermedad y necesitan revisión con el
sensor y la iluminación del dispositivo. El campo «Captura aceptable» significa
que pasó ese control de exposición; no certifica nitidez ni precisión clínica.

Un error de extracción de fototipo devuelve «No disponible», no un fototipo IV
fijo. Se rechazan predicciones no finitas y mapas de probabilidad fuera de
0–1/224×224. No se modificaron pesos, calibración de edad, percentil ni suelo de
señal del segmentador de la Pi. Se corrigió el denominador global para contar
los mismos píxeles del soporte que el numerador.

## Verificación

Pasaron 53 pruebas de exposición, región, máscara, controles, cambio de persona,
privacidad del endpoint de ampliación, motor y UI. Chromium con datos sintéticos
verificó los resultados principales, el gráfico, la ampliación capturada, modos
cámara/sensores, navegación, confirmación, reinicio y desconexión sin errores
JavaScript/CSP. La captura sintética está en `/tmp/regen-analysis.png`.

En la Pi se comprobaron el navegador real, la cámara visible y los nuevos
controles. También se ejecutaron los modelos ONNX reales con una imagen
sintética directamente en el motor, sin crear diagnósticos ni escribir en la
base de producción. La prueba de gesto completo en la cámara queda disponible
para realizarla con la persona frente al espejo.

## Despliegue y respaldo

La cámara de la Pi sigue siendo su versión propia, adaptada con
`pi-analysis-camera.patch`. El servidor y el pipeline se adaptaron con
`pi-analysis-mobile.patch` y `pi-analysis-pipeline.patch`; no se sustituyeron por
las versiones diferentes de este checkout. Se copiaron los archivos del espejo,
la proyección del diagnóstico y `src/inference/region_analysis.py`.

Respaldo previo en la Pi:

```
/opt/derma-onedge/backups/analysis-20261006-004840
```

Volver al espejo anterior, conservando el arranque web:

```bash
sudo bash /opt/derma-onedge/deploy/rollback-analysis-pi.sh
```

Para restaurar también el antiguo presentador Python/DRM, consultar
`README-regen-pi-installed.md` y su respaldo independiente.
