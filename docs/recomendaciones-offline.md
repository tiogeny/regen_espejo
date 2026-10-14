# Recomendaciones sin internet

El motor funciona con Python, SQLite y un catálogo JSON local. No utiliza modelos de lenguaje, servicios externos ni búsquedas en línea. La interfaz móvil requiere una red local entre el celular y el equipo, sin salida a internet. Los paquetes, modelos y archivos web deben estar instalados antes de desconectar el equipo.

## Uso

1. Capturar una lectura con la cámara.
2. Abrir la consulta móvil y completar **Cuestionario para esta lectura**.
3. Enviar las respuestas para evaluar las recomendaciones.
4. Revisar los mensajes y las recomendaciones disponibles; el PDF utiliza el mismo resultado.

Cada lectura requiere un cuestionario nuevo. Se usa la edad declarada para las reglas y se mantiene la edad estimada únicamente como medición. Las respuestas no se guardan en SQLite ni en almacenamiento del navegador. La sesión guarda los identificadores de las reglas seleccionadas, como antes. El cuestionario no se reutiliza para otra persona o lectura.

La API local también admite `questionnaire` en `POST /api/v1/diagnostics/analyze`:

```json
{
  "age": 30,
  "sensitive_skin": false,
  "salicylate_allergy": false,
  "is_pregnant": false,
  "is_lactating": false,
  "known_allergies": [],
  "has_open_wounds": false,
  "has_cystic_acne": false,
  "current_treatments": [],
  "concerning_changes": false
}
```

Este objeto es el valor de `questionnaire`, junto a los campos existentes `shm_descriptor` y `telemetry`. Omitir el cuestionario permite la medición, pero devuelve una lista de prescripciones vacía y `datos.orientacion.estado = DATOS_INCOMPLETOS`. `null` significa desconocido; no equivale a `false`. Las listas vacías deben ser respuestas explícitas.

## Estados y alcance

- `DATOS_INCOMPLETOS`: faltan respuestas; `datos_faltantes` identifica los campos.
- `LECTURA_INVALIDA`: medición fuera de rango o no finita.
- `REVISION_PROFESIONAL`: perfil fuera del alcance inicial (menores, embarazo, lactancia, heridas, acné quístico, cambios preocupantes, alergias declaradas o tratamientos actuales).
- `CATALOGO_NO_DISPONIBLE`: archivo ausente, ilegible o estructura inválida.
- `SIN_RECOMENDACION_VALIDADA`: ninguna regla vigente y compatible.
- `RECOMENDACIONES_DISPONIBLES`: selección determinista con explicación, precauciones y fuentes revisadas.

Estas exclusiones delimitan el alcance del software; no establecen por sí mismas una contraindicación médica. El porcentaje detectado no diagnostica la causa de una mancha. La primera versión conserva el alcance del catálogo existente de hiperpigmentación. Ampliarlo requiere criterios y contenido clínico revisado.

## Revisión y actualización local del catálogo

`data/recommendations.json` se distribuye sin reglas aprobadas. Los textos y reglas heredados no se consideran validados por estar programados. Un profesional debe revisar los criterios, filtros, fuentes, explicación y precauciones antes de habilitar cada regla. No se añaden dosis ni sustituciones automáticas.

Exportar un borrador desde la misma base y versión de código del dispositivo:

```sh
python scripts/review_catalog.py draft /tmp/catalogo-borrador.json
```

El borrador contiene la huella de cada regla y filtros. El profesional debe completar `reviewed_by`, `reviewed_on`, `valid_until`, `sources`, `explanation`, `precautions`, asignar una versión al catálogo y cambiar a `approved` únicamente las reglas revisadas. Las fechas usan `YYYY-MM-DD`. La huella no acredita la revisión: comprueba que corresponde al código y los criterios actuales.

Validar el archivo revisado:

```sh
python scripts/review_catalog.py check /ruta/catalogo-revisado.json
```

Transferirlo por USB y configurar `DERMA_KNOWLEDGE_PATH` con la ruta local, o reemplazar `data/recommendations.json` con el proceso detenido y conservando una copia anterior. El motor lee el archivo en cada evaluación. Una revisión vencida, una regla desconocida o cambios en criterios/código bloquean la selección. El reloj del equipo debe ser correcto, incluso sin internet. El paquete no tiene firma digital: la instalación corresponde al operador autorizado del dispositivo.

## Verificación

```sh
python -m pytest tests/test_offline_recommendations.py tests/test_domain_rules.py tests/test_mobile_control.py tests/test_clinical_report.py
```

Las pruebas usan revisores y fuentes ficticios exclusivamente en bases y archivos temporales. Incluyen una evaluación con conexiones de sockets y resolución DNS bloqueadas. Esto verifica el motor, no constituye una auditoría de tráfico de todo el dispositivo. Falta medir el consumo y tiempo de respuesta en la Raspberry con cámara real.
