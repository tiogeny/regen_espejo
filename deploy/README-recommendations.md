# Recomendaciones en el espejo

Después del análisis, abrir **Recomendaciones** con la flecha del panel o el
tercer punto de navegación y pulsar **Completar cuestionario**. El formulario
recoge edad real, sensibilidad, alergia a salicilatos, embarazo/lactancia,
heridas, acné quístico, cambios preocupantes, otras alergias y tratamientos.
«No lo sé» se transmite como dato desconocido, nunca como ausencia de riesgo.

El espejo solicita explícitamente alcance `face`: el motor usa el porcentaje
global del rostro, aunque exista una zona señalada. No aplica los umbrales del
rostro al porcentaje localizado. La edad usada para recomendaciones es la
**declarada**, no la estimación del modelo. El alcance `zone` se mantiene para
otros clientes y devuelve orientación localizada sin prescripciones.

## Estados

- Datos incompletos: completar las respuestas desconocidas.
- Revisión profesional: el catálogo no cubre ese perfil.
- Sin recomendación validada: ninguna regla aprobada vigente y compatible.
- Catálogo no disponible: archivo ausente o inválido.
- Recomendaciones disponibles: nombre, explicación, precauciones y fuentes de
  las reglas aprobadas. No se calculan recetas ni proporciones de jabón.

`data/recommendations.json` contiene actualmente una lista vacía pendiente de
revisión. **El flujo está implementado, pero no hay activos aprobados que mostrar
en producción.** Las pruebas usan revisores y catálogos ficticios únicamente en
bases temporales; no se copian a la Raspberry.

Para cargar reglas reales, usar `scripts/review_catalog.py` y aportar revisor,
fuentes, explicación, precauciones y fechas de revisión/vigencia. La huella de
cada regla invalida su aprobación cuando cambian criterios o filtros de
seguridad. La aprobación clínica y la formulación de un bioproducto deben
provenir de una revisión real; no las genera el sistema.

## Integración y privacidad

`POST /mirror/api/recommendations` solo acepta el navegador local y valida
host/origin como los demás controles del espejo. Requiere `analysis_id`,
`revision`, `scope` y `questionnaire`. La lectura debe seguir vigente, sin
reinicios pendientes y con cámara conectada. El móvil conserva su ruta con
Bearer `POST /api/recommendations`.

Las respuestas no se guardan en SQLite ni se exponen en el estado. El formulario
se borra al cerrar, cambiar la lectura, reiniciar, cambiar de persona o perder
conexión. SQLite registra únicamente los identificadores de reglas asignadas a
la sesión, reutilizando su tabla existente. El resultado se comparte con la
lectura actual de la cámara. No se agregan fotografías ni tablas nuevas.

## Raspberry

Se adaptó el servidor instalado mediante `pi-recommendations-mobile.patch`.
Se instaló el módulo de recomendaciones, el filtro que excluye especies sin
reglas de seguridad, el catálogo vacío y los archivos del espejo. Se conservaron
los modelos, la cámara y el API de inferencia propio de la Pi.

Respaldo:
`/opt/derma-onedge/backups/recommendations-20261006-001126`.
La ruta también se guarda en `deploy/recommendations-backup-path.txt` en la Pi.

Pruebas: motor con catálogo aprobado ficticio, catálogo vacío/inválido,
contraindicaciones, edad declarada, alcance global vs localizado, acceso local,
lecturas obsoletas y cuestionario del navegador. En la Pi se verificaron la ruta,
el formulario servido, el motor con catálogo pendiente y la cámara activa sin
crear sesiones de prueba en producción.
