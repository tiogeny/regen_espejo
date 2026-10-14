# Interfaz táctil instalada

Actualizada el 2026-10-06 en Raspberry 192.168.1.48, /opt/derma-onedge.

Formulario con selecciones de edad y salud para varones y mujeres, opción
«No aplica» en embarazo/lactancia y sin campos de escritura. Las alergias y
tratamientos presentes se envían como información pendiente de revisión.

Barras animadas: área 0–100 %, edad 0–120 años, fototipo I–VI. Los sensores
sin conexión permanecen sin mediciones. Controles táctiles de al menos 44 px.

Vista previa con límite de 20 Hz y JPEG calidad 75; consultas de estado cada
250 ms y reutilización del contenido de resultados cuando no cambia.
No se modificaron modelos, calibraciones ni el proceso de inferencia instalado.
El servidor de la Pi se adaptó en dos parámetros; conserva su versión propia.

Respaldo de los cuatro archivos anteriores:
/opt/derma-onedge/backups/touch-20261006-01/src/mobile/

Se reiniciaron derma-appliance.service y regen-kiosk.service. Ambos activos,
sin reinicios automáticos; Chromium en modo kiosk y cámara conectada.
Los archivos HTTP coincidieron con los instalados. Cinco consultas locales de
fotogramas respondieron entre 2.1 y 5.5 ms; esto mide HTTP local, no la latencia
completa de cámara/inferencia/pantalla. Temperatura observada: 68.1 °C.

La verificación Chromium con cámara sintética pasó en cuatro tamaños, incluidos
1280×720 y 1080×1920: sin superposición de paneles ni errores JavaScript/CSP.
Comprobó cuestionario, recomendaciones, reinicio, desconexión y ampliación.
Se aplicó la corrección final de posición del botón de detalles a la Pi.

## Formulario por sexo

Actualizado también en la Pi: selector Masculino/Femenino. Femenino muestra
embarazo/lactancia; Masculino muestra la pregunta de sensibilidad con referencia
al afeitado y oculta/deshabilita embarazo/lactancia. Cambiar sexo borra las
respuestas de esos campos. El selector adapta la interfaz; no se persiste.
La API conserva su contrato. El resultado del envío distingue datos incompletos,
revisión profesional y ausencia de reglas aprobadas compatibles.
Se confirmó que el catálogo instalado contiene cero reglas.
Respaldo: /opt/derma-onedge/backups/profile-20261006-01/src/mobile/.
Chromium sintético verificó ambas ramas y envío masculino; sin errores JS/CSP.

## Respuesta del dedo

Ajustado el señalamiento en el código local y la versión propia de cámara de la
Pi: límite de mano de 8 a 15 Hz; confianza de detección/presencia de 0.6 a 0.5;
fijación de 0.8 a 0.45 s, tolerancia de movimiento de 3.5 % a 5 % del ancho
facial, confirmación de mano retirada de 0.5 a 0.35 s. Se mantienen 1.5 s de
estabilidad, exclusión de ojos/labios, rechazo de dos índices y reinicio ante
pérdida del rostro. Localización facial a 640 px cuando el fotograma es mayor;
coordenadas normalizadas convertidas al fotograma original como antes.

15 pruebas pasadas, incluidas fijación con temblor pequeño, cambio real de zona,
retirada obligatoria y estabilidad. La Pi arrancó con cámara conectada, ambos
servicios activos y cero reinicios; temperatura 65.9 °C, throttled=0x0.
La cadencia efectiva y la detección física dependen del hardware y del gesto;
no se ha medido aquí la latencia completa del dedo frente a la cámara.
Respaldo: /opt/derma-onedge/backups/finger-20261006-01/.
