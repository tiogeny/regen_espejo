# [SPEC-001]: Sistema Embebido de Diagnóstico Dermatoscópico Facial y Recomendación Fitoterapéutica

- **Documento Estándar**: `spec.md` (Plantilla Canónica para Agentes de Código)
- **Rol**: Principal Software Architect
- **Versión**: 1.1.0 (Refinada y validada para SQLite 3NF y On-Edge RPi 5)
- **Principio Rector**: La especificación es la única fuente de la verdad (*Source of Truth*). El código es una consecuencia determinista de este documento. Todo diseño debe adherirse estrictamente a una arquitectura guiada por pruebas (*Test-First*) e independiente de integraciones de código prematuras.

---

## 1. Objetivo

### Descripción del Problema
Se requiere un sistema de evaluación dermatológica automatizada que opere en el borde (*on-edge*) mediante una Raspberry Pi 5. El problema central es realizar inferencias complejas (edad biológica y nivel de hiperpigmentación) y cruzar los resultados con una base de conocimientos fitoterapéuticos sin comprometer la privacidad del usuario, garantizando cero persistencia de datos biométricos y operando en entornos sin conectividad a internet.

### Alcance (In-Scope)
- **Servicio de Captura y Estabilización (Daemon de Cámara)**: Ingesta de video en tiempo real vía sensor CSI y estabilización de fotogramas mediante tracking facial en hilo secundario de baja latencia.
- **Aislamiento de Regiones de Interés (ROI)**: Extracción y alineación afín de regiones faciales (frente y mejillas) mapeadas en un buffer estandarizado de memoria volátil compartida POSIX (`shm_descriptor`) en dimensiones $224 \times 224 \times 3$.
- **Inferencia Optimizada On-Edge**: Ejecución de modelos ONNX cuantizados a **INT8** (MobileNetV3 para regresión de edad y U-Net ligera para segmentación de manchas) utilizando aceleración de CPU multihilo (ARM NEON, 4 threads).
- **Motor de Reglas Determinista**: Cruce de edad y severidad de manchas contra una base de conocimientos botánicos estructurada en SQLite bajo 3NF estricta.
- **API Loopback Segura**: Exposición de un contrato API HTTP local (`127.0.0.1`) consumido exclusivamente por la interfaz de usuario en el dispositivo.

### Fuera de Alcance (Out-of-Scope)
- Almacenamiento persistente, temporal o en caché de fotogramas, recortes faciales o vectores de características biométricas (cero escritura en disco de imágenes).
- Uso de arquitecturas sobredimensionadas basadas en YOLO o dependencias pesadas como PyTorch/CUDA en el entorno de producción.
- Cualquier llamada a APIs de terceros o procesamiento en la nube (sistema 100% offline).

### Criterio de Éxito Medible
- **Tiempo de respuesta total del pipeline**: Desde el disparo de estabilidad hasta el retorno del payload $\le 180\text{ ms}$.
- **Consumo pico de RAM del proceso**: $\le 350\text{ MB}$.
- **Cumplimiento estricto de privacidad**: Cero artefactos de imagen escritos en el disco tras procesar 1,000 transacciones de prueba consecutivas.

### Perfil de Hardware Objetivo (Raspberry Pi 5 - 8GB)
- **SoC y CPU**: Broadcom BCM2712 Quad-core ARM Cortex-A76 (64-bit) @ 2.4 GHz.
  - Caché: 512 KB L2 por núcleo y 2 MB L3 compartida.
  - Conjunto de instrucciones: ARMv8.2-A con aceleración vectorial **ARM NEON** (esencial para operaciones tensoriales cuantizadas a INT8 en ONNX Runtime ejecutadas en 4 hilos concurrentes).
- **Memoria del Sistema (RAM)**: 8 GB LPDDR4X-4267 SDRAM de alto ancho de banda.
  - Provee transferencia ultrarrápida para buffers *Zero-Copy* en memoria volátil compartida (`/dev/shm`) y garantiza amplio margen frente al límite estricto del proceso ($\le 350\text{ MB}$).
- **Ingesta de Video (MIPI / CSI)**: 2 × conectores MIPI bidireccionales de 4 carriles (interfaz para sensor de cámara CSI de alta velocidad con ancho de banda dedicado).
- **Gestión Térmica y Enfriamiento**: Conector dedicado para ventilador con control inteligente PWM.
  - Requiere disipación activa obligatoria. La API suspende preventivamente la inferencia si la CPU supera $75.0^\circ\text{C}$ (HTTP 422 `THERMAL_THROTTLING_ACTIVE`), anticipándose al estrangulamiento térmico de hardware del kernel.
- **Alimentación y Confiabilidad Eléctrica**: 5V / 5A DC vía USB-C Power Delivery (fuente oficial recomendada de 27W) para prevenir microcortes o caídas de tensión (*undervoltage*) bajo carga de inferencia total en los 4 núcleos.
- **Auditoría Temporal Offline (RTC)**: Reloj en tiempo real (RTC) integrado con respaldo de batería externa, asegurando marcas de tiempo ISO-8601 precisas en `sesiones_diagnostico` en entornos 100% desconectados de internet (sin sincronización NTP).
- **Almacenamiento Local**: MicroSD SDR104 / interfaz PCIe 2.0 x1 (NVMe SSD) para el alojamiento del sistema operativo y la base de datos transaccional SQLite.

---

## 2. Esquema de Datos (Tercera Forma Normal - SQLite 3NF)

Todo almacenamiento relacional persistente se restringe a **SQLite embebido** con activación mandatoria de claves foráneas (`PRAGMA foreign_keys = ON;`), limitándose exclusivamente a catálogos deterministas y metadatos clínicos anonimizados.

### 2.1. Diagrama Entidad-Relación (Relacional)

```plaintext
+-----------------------+      +---------------------------+      +------------------------+
|   SEVERIDAD_NIVELES   |      |     REGLAS_BOTANICAS      |      |   ESPECIES_BOTANICAS   |
+-----------------------+      +---------------------------+      +------------------------+
| PK severidad_id       |<-----| FK severidad_id           |----->| PK especie_id          |
|    codigo             |      | FK especie_id             |      |    nombre_comun        |
|    umbral_min_pct     |      | FK condicion_id           |--+   |    nombre_cientifico   |
|    umbral_max_pct     |      | PK regla_id               |  |   |    precauciones        |
+-----------------------+      +---------------------------+  |   +------------------------+
                                                              v
+-----------------------+      +---------------------------+  +------------------------+
| SESIONES_DIAGNOSTICO  |      |   SESION_PRESCRIPCIONES   |  | CONDICIONES_OBJETIVO   |
+-----------------------+      +---------------------------+  +------------------------+
| PK sesion_id (TEXT)   |<-----| PK,FK sesion_id           |  | PK condicion_id        |
| FK severidad_id       |      | PK,FK regla_id            |  |    codigo              |
|    edad_estimada      |      +---------------------------+  |    descripcion_clinica |
|    porcentaje_manchas |                                     +------------------------+
|    tiempo_proc_ms     |
|    creado_en          |
+-----------------------+
```

### 2.2. Definición DDL (Strict SQLite 3NF DDL Template)

```sql
PRAGMA foreign_keys = ON;

-- Catálogos Atómicos
CREATE TABLE IF NOT EXISTS severidad_niveles (
    severidad_id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE, -- 'NINGUNA', 'LEVE', 'MODERADA', 'ALTA'
    umbral_min_pct REAL NOT NULL,
    umbral_max_pct REAL NOT NULL,
    CONSTRAINT chk_umbrales CHECK (umbral_min_pct < umbral_max_pct)
);

CREATE TABLE IF NOT EXISTS condiciones_objetivo (
    condicion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE, -- 'HIPERPIGMENTACION', 'ENVEJECIMIENTO_PREMATURO'
    descripcion_clinica TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS especies_botanicas (
    especie_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_cientifico TEXT NOT NULL UNIQUE,
    nombre_comun TEXT NOT NULL,
    precauciones TEXT NOT NULL
);

-- Motor de Reglas Determinista
CREATE TABLE IF NOT EXISTS reglas_botanicas (
    regla_id INTEGER PRIMARY KEY AUTOINCREMENT,
    edad_min INTEGER NOT NULL,
    edad_max INTEGER NOT NULL,
    severidad_id INTEGER NOT NULL,
    condicion_id INTEGER NOT NULL,
    especie_id INTEGER NOT NULL,
    CONSTRAINT fk_regla_severidad FOREIGN KEY (severidad_id) REFERENCES severidad_niveles(severidad_id) ON DELETE RESTRICT,
    CONSTRAINT fk_regla_condicion FOREIGN KEY (condicion_id) REFERENCES condiciones_objetivo(condicion_id) ON DELETE RESTRICT,
    CONSTRAINT fk_regla_especie FOREIGN KEY (especie_id) REFERENCES especies_botanicas(especie_id) ON DELETE RESTRICT,
    CONSTRAINT chk_rango_edad CHECK (edad_min <= edad_max),
    CONSTRAINT uq_regla_unica UNIQUE (edad_min, edad_max, severidad_id, condicion_id, especie_id)
);

-- Entidad Principal: Sesión de Diagnóstico (Anónima)
CREATE TABLE IF NOT EXISTS sesiones_diagnostico (
    sesion_id TEXT PRIMARY KEY, -- UUID v5 determinista (Namespace + Hash de inputs)
    severidad_id INTEGER NOT NULL,
    edad_estimada INTEGER NOT NULL,
    porcentaje_manchas REAL NOT NULL,
    tiempo_procesamiento_ms REAL NOT NULL,
    creado_en TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CONSTRAINT fk_sesion_severidad FOREIGN KEY (severidad_id) REFERENCES severidad_niveles(severidad_id) ON DELETE RESTRICT
);

-- Tabla de Detalle: Prescripciones Asignadas a la Sesión
CREATE TABLE IF NOT EXISTS sesion_prescripciones (
    sesion_id TEXT NOT NULL,
    regla_id INTEGER NOT NULL,
    PRIMARY KEY (sesion_id, regla_id),
    CONSTRAINT fk_sp_sesion FOREIGN KEY (sesion_id) REFERENCES sesiones_diagnostico(sesion_id) ON DELETE CASCADE,
    CONSTRAINT fk_sp_regla FOREIGN KEY (regla_id) REFERENCES reglas_botanicas(regla_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_sesiones_fecha ON sesiones_diagnostico(creado_en);
```

---

## 3. Endpoints y Contratos de Interfaz (API Contracts)

El sistema expone un servidor HTTP local enlazado exclusivamente a la interfaz loopback (`127.0.0.1`), consumido por la interfaz de usuario local y orquestado en conjunto con el daemon de cámara.

### 3.1. Estándar de Seguridad y Autenticación
- **Protocolo de Autenticación**: Token efímero de dispositivo generado y rotado en cada inicio del sistema, almacenado en memoria volátil (`tmpfs` en `/run/lock/derma_device.token`).
- **Encabezados Globales Obligatorios**:
  ```http
  Authorization: Bearer <device_tmp_token>
  X-Correlation-ID: <uuid_v4>
  Content-Type: application/json
  ```

### 3.2. Catálogo de Operaciones

#### Operación 1: Ejecutar Inferencia y Generar Diagnóstico
- **Ruta**: `POST /api/v1/diagnostics/analyze`
- **Propósito**: Lee el buffer de memoria compartida validado, ejecuta los modelos ONNX cuantizados (MobileNetV3 y U-Net) y procesa las reglas botánicas en SQLite.
- **Control de Acceso**: Validación obligatoria de Bearer token y enlace exclusivo a localhost.

##### Esquema de Entrada (`Request Body JSON Schema`):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AnalyzeRequest",
  "type": "object",
  "required": ["shm_descriptor", "telemetry"],
  "properties": {
    "shm_descriptor": {
      "type": "string",
      "description": "Identificador POSIX shm (/dev/shm) que expone el buffer alineado de 224x224x3 (RGB/YUV420) de la región facial estabilizada."
    },
    "telemetry": {
      "type": "object",
      "required": ["stability_duration_ms", "thermal_soc_celsius"],
      "properties": {
        "stability_duration_ms": { 
          "type": "integer", 
          "minimum": 1500,
          "description": "Tiempo continuo de estabilidad facial garantizado por el tracker antes de solicitar inferencia."
        },
        "thermal_soc_celsius": { 
          "type": "number", 
          "maximum": 75.0,
          "description": "Lectura térmica actual de la CPU Broadcom BCM2712."
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

##### Esquema de Salida Exitosa (`201 Created`):
```json
{
  "datos": {
    "sesion_id": "a1b2c3d4-e5f6-5a8b-9c0d-1e2f3a4b5c6d",
    "clinica": {
      "edad_biologica_estimada": 32,
      "porcentaje_hiperpigmentacion": 2.4,
      "clasificacion_severidad": "LEVE"
    },
    "prescripciones": [
      {
        "condicion_objetivo": "HIPERPIGMENTACION",
        "especie": "Arctostaphylos uva-ursi",
        "nombre_comun": "Gayuba",
        "precauciones": "No combinar simultáneamente con peróxido de benzoilo."
      }
    ]
  },
  "metadatos": {
    "correlation_id": "c1f7a0b2-3e4d-4c8a-9f0e-1a2b3c4d5e6f",
    "execution_time_ms": 142.5
  }
}
```

##### Matriz de Errores Estandarizados:
| Código HTTP | Error Code | Causa Raíz | Mitigación / Formato |
| :--- | :--- | :--- | :--- |
| `400 Bad Request` | `INVALID_SHM_DESCRIPTOR` | El descriptor de memoria compartida es nulo, inaccesible o su dimensión no es $224 \times 224 \times 3$. | Abortar análisis, reintentar captura. |
| `401 Unauthorized` | `INVALID_DEVICE_TOKEN` | Token ausente, corrupto o no coincide con el secreto en `tmpfs`. | Bloquear tráfico no originado por la UI local. |
| `422 Unprocessable` | `THERMAL_THROTTLING_ACTIVE` | Temperatura del SoC Broadcom $> 75.0^\circ\text{C}$. | Suspender inferencia y emitir alerta de enfriamiento a la UI. |

---

## 4. Lógica de Negocio y Reglas del Dominio

### 4.1. Arquitectura y Máquina de Estados Finita (FSM)

```plaintext
 [DAEMON CÁMARA: Sensor CSI]
             │
      (Detectar Rostro)
             │
             ▼
     (RASTREO_ACTIVO) ◄──────────────┐
             │                       │
 ┌───────────┴───────────┐           │
 ▼                       ▼           │
[Movimiento/Inestable]  [Estabilidad > 1.5s]
 │                       │
 └─►(REINICIAR_TIMER)    ▼
                   (ESCRIBIR SHM 224x224)
                         │
                         ▼
             [POST /api/v1/diagnostics/analyze]
                         │
                         ▼
                 (INFERENCIA ONNX INT8)
                   ├─ MobileNetV3 (Edad)
                   └─ U-Net Nano (Hiperpigmentación)
                         │
                         ▼
                [Motor de Reglas SQLite 3NF]
                         │
                         ▼
             (201 CREATED & LIBERACIÓN SHM)
```

### 4.2. Invariantes y Reglas Transaccionales
1. **Atomicidad Volátil (Zero-Copy & Zero-Disk)**:
   - La conversión de color y la normalización de tensores ($[H, W, C] \to [1, C, H, W]$) se efectúa *in-place* sobre memoria RAM.
   - Ninguna imagen, máscara binaria ni vector intermedio puede ser escrito en el sistema de archivos (`/`, `/home`, `/tmp` en disco físico).
2. **Mitigación Térmica (SLA de Hardware)**:
   - Si `telemetry.thermal_soc_celsius > 75.0^\circ\text{C}`, la API rechaza inmediatamente la ejecución con HTTP 422 (`THERMAL_THROTTLING_ACTIVE`).
3. **Determinismo de Sesión (UUID v5)**:
   - Para cumplir con el principio de repetibilidad en pruebas, el identificador `sesion_id` se genera mediante **UUID v5**, derivado de un UUID Namespace del dominio (`ns:derma.system`) y del hash SHA-1 de `(edad_estimada, round(porcentaje_manchas, 2), seed)`.
4. **Evaluación de Umbrales de Severidad**:
   - Los rangos de `severidad_niveles` se evalúan con la convención semiabierta:
     $$\text{umbral\_min\_pct} \le \text{porcentaje\_manchas} < \text{umbral\_max\_pct}$$
     excepto para el nivel de severidad más alto ('ALTA'), donde el intervalo es cerrado superiormente ($\le \text{umbral\_max\_pct}$).
5. **Optimización On-Edge para Presupuesto de 180 ms**:
   - Los modelos ONNX deben emplear cuantización **INT8** simétrica calibrada.
   - La sesión ONNX Runtime debe configurarse con `intra_op_num_threads = 4` y optimizaciones de grafos activadas (`ORT_ENABLE_ALL`).
6. **Consolidación de Precauciones**:
   - Si una combinación de severidad y edad activa múltiples reglas botánicas, el payload debe incluir cada especie con sus precauciones individuales consolidadas sin duplicados.

### 4.3. Algoritmo de Procesamiento Paso a Paso
1. **RECIBIR** petición HTTP en el hilo de inferencia.
2. **VALIDAR** token de dispositivo en cabecera `Authorization` contra secreto en `tmpfs`.
   - Si es inválido: **ABORTAR** con `401 Unauthorized`.
3. **VALIDAR** telemetría térmica (`thermal_soc_celsius < 75.0`).
   - Si excede: **ABORTAR** con `422 Unprocessable` (`THERMAL_THROTTLING_ACTIVE`).
4. **MAPEAR** descriptor POSIX `shm_descriptor` vía `mmap` y verificar dimensiones $[224, 224, 3]$.
   - Si no es válido: **ABORTAR** con `400 Bad Request` (`INVALID_SHM_DESCRIPTOR`).
5. **TRANSFORMAR** buffer in-memory al tensor de entrada $[1, 3, 224, 224]$ normalizado.
6. **EJECUTAR** sesión ONNX 1: MobileNetV3 INT8 $\to$ obtener `edad_biologica_estimada` (entero).
7. **EJECUTAR** sesión ONNX 2: U-Net INT8 $\to$ generar máscara binaria de pigmentación.
8. **CALCULAR** densidad porcentual de píxeles activos:
   $$\text{porcentaje\_hiperpigmentacion} = \frac{\sum \text{píxeles activos}}{\text{total píxeles útiles}} \times 100$$
9. **ABRIR** transacción en SQLite (`BEGIN IMMEDIATE`).
10. **CONSULTAR** nivel de severidad en `severidad_niveles` correspondiente al porcentaje calculado.
11. **INSERTAR** métricas en `sesiones_diagnostico` con `sesion_id` determinista (UUID v5).
12. **CONSULTAR** `reglas_botanicas` cruzando `edad_biologica_estimada`, `severidad_id` y `condicion_id` (`HIPERPIGMENTACION`).
13. **INSERTAR** asociaciones resultantes en `sesion_prescripciones`.
14. **CONFIRMAR** transacción (`COMMIT`).
15. **LIBERAR/UNMAP** descriptor de memoria compartida.
16. **RETORNAR** `201 Created` con payload clínico estructurado y tiempo de ejecución en milisegundos.

---

## 5. Suite de Tests Necesaria (Test-First)

Ninguna línea de implementación en código de producción se considerará válida si no satisface previamente los siguientes casos de prueba automatizados.

### 5.1. Pruebas de Seguridad e Integridad de Accesos

```plaintext
[Suite: Aislamiento Local y Privacidad]
├── test_peticion_sin_token_rechazada_inmediatamente()
│   ├── Given: Petición a /api/v1/diagnostics/analyze sin header Authorization
│   └── Then: HTTP Status == 401, Código Error == 'INVALID_DEVICE_TOKEN'.
│
├── test_cero_persistencia_biometrica_tras_ejecucion()
│   ├── Given: Payload válido con buffer sintético en memoria compartida
│   ├── When: La transacción se procesa y retorna 201 Created
│   └── Then: 
│       ├── El sistema de archivos no contiene archivos .png, .jpg, .npy ni temporales en disco
│       └── El conteo en `sesiones_diagnostico` aumenta en 1 sin blobs de imagen.
│
└── test_bloqueo_termico_seguro()
    ├── Given: Payload con telemetry.thermal_soc_celsius == 76.5
    └── Then: HTTP Status == 422, Código Error == 'THERMAL_THROTTLING_ACTIVE'
```

### 5.2. Pruebas de Lógica de Negocio Principal y Casos Borde

```plaintext
[Suite: Dominio y Reglas Botánicas]
├── test_edad_30_severidad_leve_retorna_arbutina()
│   ├── Given: Mock ONNX (Edad=30, Hiperpigmentación=1.5% -> LEVE)
│   ├── When: Se procesa el motor de reglas
│   └── Then: Payload incluye 'Arctostaphylos uva-ursi' (Gayuba).
│
├── test_restriccion_conflictos_multiples_compuestos()
│   ├── Given: Mock ONNX (Edad=65, Hiperpigmentación=5.0% -> ALTA)
│   ├── When: Se procesa el motor de reglas
│   └── Then: 
│       ├── Se retornan 2 registros (Rosa canina y Glycyrrhiza glabra)
│       └── Ambas especies incluyen sus precauciones específicas consolidadas.
│
└── test_shape_incorrecto_en_buffer_shm_lanza_400()
    ├── Given: Buffer SHM con matriz 100x100 (Esperado 224x224x3)
    └── Then: HTTP Status == 400, Código Error == 'INVALID_SHM_DESCRIPTOR'
```

---

## 6. Criterios de Aceptación Técnicos (Definition of Done)

1. **Validación Formal 3NF en SQLite**: Tablas libres de dependencias transitivas y multivaluadas, con claves foráneas verificadas mediante `PRAGMA foreign_keys = ON;`.
2. **Cero Persistencia de Imágenes**: Verificación mediante monitoreo de E/S (`inotify` / test runner) demostrando 0 bytes de imágenes en disco tras 1,000 ejecuciones.
3. **Determinismo Estricto**: Mismas entradas de prueba generan idéntico `sesion_id` (UUID v5) y prescripciones idénticas sin ramificaciones ocultas.
4. **Cumplimiento de Latencia On-Edge**: Tiempo de ciclo total $\le 180\text{ ms}$ en entorno objetivo Raspberry Pi 5.

## Extensión: consulta móvil local (2026-10-05)

El panel autenticado del puerto 8080 permite controlar la repetición del escaneo y
leer el resultado final que mantiene el proceso de cámara. Es una extensión LAN
separada del API de inferencia; no cambia sus reglas clínicas ni sus modelos.

- `GET /api/status`: requiere el código temporal Bearer. Devuelve estado, contador,
  revisión del control y `diagnostic` con sesión anónima, identificador del análisis,
  número de lectura, hora de publicación, métricas clínicas y recomendaciones.
- La proyección usa una lista explícita de campos; excluye fotografías, máscaras,
  descriptores SHM y cualquier campo no previsto. No recalcula valores clínicos.
- `diagnostic` es nulo cuando la cámara no está disponible, está capturando o
  analizando, o existe un reinicio pendiente. Una lectura anterior nunca sustituye
  a un resultado que no llegó. Los campos faltantes indican «No disponible».
- La hora representa la publicación del resultado por la cámara, permanece estable
  entre consultas y se muestra en la zona horaria del celular.
- `POST /api/restart` conserva la sesión y valida la revisión; las órdenes expiran
  a los diez segundos. La confirmación refleja aplicación efectiva por la cámara.
- Código y resultados permanecen en memoria; las respuestas llevan `no-store`.
  La interfaz retira el resultado al perder conexión, cerrar la consulta o pasar
  a segundo plano; al regresar consulta nuevamente al equipo.
- La interfaz presenta las estimaciones y recomendaciones existentes para revisión
  del dermatólogo. No agrega diagnósticos de enfermedades ni tratamientos.

Verificaciones: `tests/test_mobile_control.py` cubre acceso, caducidad, duplicados,
proyección, valores inválidos y retiro de resultados; `scripts/check_mobile_browser.py`
comprueba el flujo del celular con lecturas sintéticas y sin hardware.
