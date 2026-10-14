# Indicadores visuales por cámara

La pestaña «Análisis visual» reemplaza los indicadores sin sensor por tres
barras experimentales: brillo visible, textura visible y señales de sequedad.
Cada porcentaje representa la cobertura de un patrón en la zona seleccionada;
no mide hidratación, cantidad de sebo ni pH. Tampoco es una probabilidad clínica.

Se procesa el recorte RGB original de la captura, antes de dibujar la máscara.
El brillo detecta contrastes claros de baja saturación; la textura usa
microcontraste con CLAHE y filtrado bilateral; las señales de sequedad buscan
fragmentos pequeños y claros. Estas últimas pueden ser vello, cosméticos o
ruido: no confirman piel seca. La iluminación afecta a los tres indicadores.
Los umbrales son heurísticos y no están calibrados ni validados clínicamente.

El cálculo se limita al círculo seleccionado, con contexto próximo para los
filtros. Se reduce el recorte a un máximo de 160 píxeles de lado; no se amplía
para inventar detalle. Se requiere un diámetro original de al menos 32 píxeles
y 600 píxeles útiles tras reducir y erosionar la máscara. El control de
exposición existente sigue aplicándose. Estos mínimos no garantizan enfoque.

Sin zona, detalle o exposición adecuados, los valores son nulos y las barras
se vacían. Un cero válido significa que no apareció el patrón del algoritmo;
no descarta sequedad ni otros problemas de piel. Al reiniciar se eliminan las
lecturas anteriores. El cálculo ocurre una vez por diagnóstico, no en cada
fotograma, y conserva los datos solo en RAM dentro del flujo del espejo.

La proyección `visual_appearance` permite únicamente estado, método, alcance,
unidad y tres números finitos entre 0 y 100. No contiene imágenes. Estos valores
no intervienen en las recomendaciones ni sustituyen instrumentos de medición.

## Verificación

Pasaron 21 pruebas de cálculo, exposición, proyección, controles y API del
espejo. Chromium con datos sintéticos comprobó cinco tamaños de pantalla,
barras, falta de detalle, cuestionario, recomendaciones, reinicio y desconexión
sin errores JavaScript ni CSP. Estas pruebas verifican el funcionamiento del
software, no precisión clínica ni rendimiento en la Raspberry.

## Raspberry

El despliegue de esta actualización está pendiente: en el último intento la
dirección `192.168.1.48` no respondió por SSH («No route to host»).
El parche `deploy/pi-appearance-camera.patch` está preparado para la versión
de cámara descargada de ese dispositivo. Antes de aplicarlo hay que confirmar
que esa versión sigue vigente, respaldar los archivos y copiar también
`src/inference/visual_appearance.py`, `src/mobile/diagnostic.py`,
`src/mobile/mirror.html` y `src/mobile/mirror.js`. Después deben reiniciarse
`derma-appliance.service` y `regen-kiosk.service` y comprobarse en el equipo.
