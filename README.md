# 🌿 Derma On-Edge: Sistema Embebido de Diagnóstico Dermatoscópico Facial y Recomendación Fitoterapéutica (SPEC-001)

La interfaz principal ahora es el **espejo web REGEN**, basado en la referencia
visual del proyecto: espejo circular iluminado, señalamiento de piel con el
índice y resultados sobre la cámara en vivo. Python procesa la cámara en segundo
plano y ya no abre su ventana por defecto.

```bash
python demo_camara.py
```

Abrir `http://127.0.0.1:8080/mirror` en el navegador del equipo.
Ver [ejecución y arranque automático en Raspberry Pi](deploy/README-regen-web.md).
El espejo muestra el [análisis por cámara y su alcance](deploy/README-analysis.md):
área segmentada, edad y fototipo estimados, con ampliación de la captura evaluada.
La pestaña [Análisis visual](docs/analisis-visual.md) añade barras experimentales
de brillo, textura y posibles señales de sequedad de la zona seleccionada.
No mide hidratación, sebo ni pH; su instalación en la Raspberry está pendiente.
Las instrucciones de HUD y teclado de las secciones siguientes corresponden
al modo heredado (`DERMA_WEB=0`).

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-INT8_ARM_NEON-orange.svg)](https://onnxruntime.ai/)
[![SQLite 3NF](https://img.shields.io/badge/SQLite-3NF_Strict-lightgrey.svg)](https://sqlite.org/)
[![Privacy](https://img.shields.io/badge/Privacy-Zero--Disk_Biometrics-red.svg)](#-privacidad-radical-y-seguridad-zero-disk)
[![Tests](https://img.shields.io/badge/Tests-8%20Passed-brightgreen.svg)](#-suite-de-pruebas-automatizadas-tdd)

Sistema de visión clínica artificial e inferencia dermatológica de alta precisión diseñado para operar **en el borde (*on-edge*)** sobre **Raspberry Pi 5**, con garantía de **privacidad radical (cero persistencia biométrica en disco)**, motor de reglas fitoterapéuticas relacional bajo **SQLite en Tercera Forma Normal (3NF)** y servidor HTTP loopback de latencia ultra-baja.

---

## 📑 Tabla de Contenidos

- [🌿 Derma On-Edge: Sistema Embebido de Diagnóstico Dermatoscópico Facial y Recomendación Fitoterapéutica (SPEC-001)](#-derma-on-edge-sistema-embebido-de-diagnóstico-dermatoscópico-facial-y-recomendación-fitoterapéutica-spec-001)
  - [📑 Tabla de Contenidos](#-tabla-de-contenidos)
  - [🎯 Descripción General](#-descripción-general)
  - [🏛️ Arquitectura del Sistema y Flujo de Datos](#️-arquitectura-del-sistema-y-flujo-de-datos)
  - [💻 Especificación de Hardware Objetivo (Raspberry Pi 5)](#-especificación-de-hardware-objetivo-raspberry-pi-5)
  - [📂 Estructura del Repositorio](#-estructura-del-repositorio)
  - [⚙️ Instalación y Puesta en Marcha](#️-instalación-y-puesta-en-marcha)
    - [Requisitos Previos](#requisitos-previos)
    - [1. Clonar o acceder al proyecto](#1-clonar-o-acceder-al-proyecto)
    - [2. Crear y activar el entorno virtual](#2-crear-y-activar-el-entorno-virtual)
    - [3. Instalar las dependencias](#3-instalar-las-dependencias)
  - [🚀 Guía de Ejecución](#-guía-de-ejecución)
    - [1. Demostración Interactiva en Vivo con Cámara (`demo_camara.py`)](#1-demostración-interactiva-en-vivo-con-cámara-demo_camarapy)
    - [2. Servidor API FastAPI Loopback](#2-servidor-api-fastapi-loopback)
    - [3. Verificación Extremo a Extremo (`verify_live_pipeline.py`)](#3-verificación-extremo-a-extremo-verify_live_pipelinepy)
    - [4. Benchmark de Latencia On-Edge (`benchmark_latency.py`)](#4-benchmark-de-latencia-on-edge-benchmark_latencypy)
    - [5. Diagnóstico de Cámaras (`diagnose_cameras.py`)](#5-diagnóstico-de-cámaras-diagnose_cameraspy)
  - [🧪 Suite de Pruebas Automatizadas (TDD)](#-suite-de-pruebas-automatizadas-tdd)
    - [Cobertura de las Pruebas:](#cobertura-de-las-pruebas)
  - [📡 Contratos de la API REST](#-contratos-de-la-api-rest)
    - [`POST /api/v1/diagnostics/analyze`](#post-apiv1diagnosticsanalyze)
      - [Cabeceras de Petición (Headers)](#cabeceras-de-petición-headers)
      - [Cuerpo de la Petición (JSON Request)](#cuerpo-de-la-petición-json-request)
      - [Respuesta Exitosa (`HTTP 201 Created`)](#respuesta-exitosa-http-201-created)
      - [Respuestas de Error](#respuestas-de-error)
  - [🌿 Modelo de Datos y Reglas Fitoterapéuticas (SQLite 3NF)](#-modelo-de-datos-y-reglas-fitoterapéuticas-sqlite-3nf)
    - [Catálogo de Especies Fitoterapéuticas Calibradas:](#catálogo-de-especies-fitoterapéuticas-calibradas)
  - [🔒 Privacidad Radical y Seguridad (Zero-Disk)](#-privacidad-radical-y-seguridad-zero-disk)
  - [🌐 Variables de Entorno](#-variables-de-entorno)
  - [📄 Licencia y Conformidad](#-licencia-y-conformidad)

---

## 🎯 Descripción General

El proyecto aborda la evaluación dermatológica facial automatizada y la prescripción fitoterapéutica personalizada en dispositivos embebidos desconectados (*offline*), cumpliendo tres principios no negociables:

1. **Privacidad Radical (Zero-Disk)**: Ningún fotograma capturado por el sensor de video, recorte facial, ni vector biométrico es persistido jamás en almacenamiento permanente (ni en disco, ni en swap, ni en logs). Todo el procesamiento ocurre en memoria compartida volátil (`shm`) y memoria RAM transitoria.
2. **Inferencia Eficiente On-Edge**: Redes neuronales convolucionales cuantizadas a **INT8** ejecutadas mediante **ONNX Runtime** optimizadas con instrucciones vectoriales **ARM NEON** en 4 hilos concurrentes, alcanzando inferencia completa en menos de 50 ms.
3. **Farmacognosia Basada en Evidencia y Determinismo Clínico**: Las recomendaciones fitoterapéuticas derivan de un motor relacional en SQLite 3NF validado, vinculando la edad biológica estimada y el porcentaje de hiperpigmentación con especies botánicas activas y sus precauciones clínicas.

---

## 🏛️ Arquitectura del Sistema y Flujo de Datos

El ciclo de vida de un diagnóstico se ejecuta en memoria volátil de extremo a extremo:

```plaintext
 +-----------------------------------------------------------------------------------+
 |                             FLUJO ZERO-COPY ON-EDGE                              |
 +-----------------------------------------------------------------------------------+
 
 [ Cámara / Sensor CSI ]
         │ (Stream de video en tiempo real)
         ▼
 [ Detector Facial Frontal + FSM de Estabilidad (demo_camara.py) ]
         │ (Espera posición estable del rostro > 1.5s)
         ▼
 [ Extracción y Alineación de ROI: 224x224x3 uint8 ]
         │ (Copia directa en memoria compartida volátil)
         ▼
 [ Buffer POSIX SHM (/dev/shm o multiprocessing.shared_memory) ]
         │
         │ Petición HTTP POST local (127.0.0.1)
         │ Header: Authorization: Bearer <TOKEN_TMPFS>
         │ Payload: {"shm_descriptor": "psm_...", "telemetry": {...}}
         ▼
 [ API FastAPI Loopback (src/api/app.py) ]
   ├── 1. Verificación de Token de Dispositivo en tmpfs (src/api/security.py)
   ├── 2. Control de Salvaguarda Térmica (Rechazo HTTP 422 si SoC > 75.0°C)
   ├── 3. Mapeo Zero-Copy del buffer SHM (src/memory/shm_manager.py)
   ├── 4. Inferencia Dual en RAM (src/inference/pipeline.py):
   │      ├── MobileNetV3 INT8  ──► Estimación de Edad Biológica (ej. 30 años)
   │      └── U-Net Nano INT8   ──► Segmentación y % de Hiperpigmentación (ej. 1.2%)
   ├── 5. Liberación inmediata del descriptor y puntero SHM
   ├── 6. Motor de Reglas Relacionales en SQLite 3NF (src/db/repository.py):
   │      ├── Clasificación de Severidad (NINGUNA, LEVE, MODERADA, ALTA)
   │      ├── Consulta de Especies Botánicas y Contraindicaciones
   │      └── Registro transaccional anónimo con UUID v5 determinista
   └── 7. Emisión de Respuesta HTTP 201 Created con Receta y Telemetría
         │
         ▼
 [ HUD Táctico / Interfaz de Usuario (demo_camara.py) ]
   Visualización en vivo de diagnóstico clínico y prescripciones fitoterapéuticas.
```

  ---

  ## 💻 Especificación de Hardware Objetivo (Raspberry Pi 5)

  | Parámetro | Especificación Requerida | Justificación Técnica |
  | :--- | :--- | :--- |
  | **SoC / CPU** | Broadcom BCM2712 Quad-core ARM Cortex-A76 @ 2.4 GHz | Capacidad de cómputo para inferencia multihilo simultánea sin acelerador dedicado. |
  | **Aceleración Vectorial**| ARMv8.2-A con instrucciones **ARM NEON** | Esencial para ejecutar tensores cuantizados a INT8 en ONNX Runtime con latencia mínima. |
  | **Memoria RAM** | 8 GB LPDDR4X-4267 SDRAM | Transferencias ultrarrápidas de memoria volátil (`/dev/shm`) y consumo del proceso $\le 350$ MB. |
  | **Ingesta de Video** | Interfaz MIPI CSI de 4 carriles (o cámara USB UVC) | Ancho de banda dedicado para captura de fotogramas sin contención de bus. |
  | **Refrigeración** | Disipador activo con ventilador regulado por PWM | **Obligatoria**. El sistema suspende inferencias a $>75.0^\circ\text{C}$ (corte preventivo térmico). |
  | **Alimentación** | Fuente oficial Raspberry Pi 27W USB-C (5V / 5A) | Previene caídas de tensión (*undervoltage*) bajo estrés multihilo de los 4 núcleos. |
  | **Reloj RTC** | RTC integrado con batería de respaldo | Garantiza marcas de tiempo ISO-8601 consistentes en entornos totalmente fuera de línea (*offline*). |

  ---

## 📂 Estructura del Repositorio

```plaintext
Proyecto_derma/
├── data/
│   ├── derma.db                  # Base de datos SQLite embebida (generada en runtime)
│   └── seeds.sql                 # Catálogos maestros y reglas farmacognósticas
├── models/
│   ├── age_estimator.onnx        # MobileNetV3 cuantizado a INT8 (Hermes ML Pipeline)
│   ├── age_estimator_fp32.onnx   # Versión FP32 de referencia
│   ├── spot_segmentation.onnx    # U-Net Nano cuantizado a INT8 (Hermes ML Pipeline)
│   └── spot_segmentation_fp32.onnx # Versión FP32 de referencia
├── scripts/
│   ├── benchmark_latency.py      # Medición de latencia y cumplimiento del SLA de hardware
│   ├── diagnose_cameras.py       # Diagnóstico de cámaras disponibles (DirectShow/PnP)
│   ├── export_models.py          # Script de definición y exportación PyTorch -> ONNX INT8
│   └── verify_live_pipeline.py   # Test de integración extremo a extremo con SHM sintético
├── spec/
│   └── Spec.md                   # Especificación canónica formal del sistema (SPEC-001)
├── src/
│   ├── api/
│   │   ├── app.py                # Servidor FastAPI loopback (127.0.0.1) con ciclo de vida
│   │   ├── schemas.py            # Modelos Pydantic v2 de entrada y salida
│   │   └── security.py           # Autenticación con token Bearer en memoria volátil tmpfs
│   ├── db/
│   │   ├── database.py           # Conexión SQLite con PRAGMA foreign_keys = ON
│   │   ├── repository.py         # Consultas SQL optimizadas y UUID v5 determinista
│   │   └── schema.sql            # Definición DDL relacional en Tercera Forma Normal (3NF)
│   ├── inference/
│   │   └── pipeline.py           # Motor de inferencia ONNX in-memory (Zero-Disk)
│   ├── memory/
│   │   └── shm_manager.py        # Gestor de memoria compartida POSIX/Windows (224x224x3)
│   └── config.py                 # Configuración centralizada, variables de entorno y límites
├── tests/
│   ├── conftest.py               # Fixtures de pruebas y creación de buffers SHM aislados
│   ├── test_domain_rules.py      # Verificación clínica de reglas fitoterapéuticas
│   ├── test_privacy.py           # Cero persistencia biométrica en disco
│   ├── test_security.py          # Seguridad de tokens y control de acceso 401
│   ├── test_shm_validation.py    # Validación de buffers y descriptores SHM corruptos (400)
│   └── test_thermal.py           # Salvaguarda de estrangulamiento térmico (422)
├── demo_camara.py                # Aplicación interactiva con cámara web y HUD en tiempo real
├── pyproject.toml                # Metadatos del paquete y configuración de pytest
├── requirements.txt              # Archivo estándar de dependencias pip
└── README.md                     # Documentación técnica principal
```

---

## ⚙️ Instalación y Puesta en Marcha

### Requisitos Previos
- **Python 3.11** o superior instalado en el sistema.
- Entorno Windows 10/11 o Linux (Debian Bookworm en Raspberry Pi OS de 64 bits).

### 1. Clonar o acceder al proyecto
```bash
cd C:\Users\PC-4154\Desktop\Proyecto_derma
```

### 2. Crear y activar el entorno virtual
En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Linux / Raspberry Pi OS (Bash):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar las dependencias
Instala todas las librerías necesarias mediante el archivo estándar `requirements.txt`:
```bash
pip install -r requirements.txt
```

*(Opcional: Si deseas instalar el paquete en modo editable junto a sus extras de desarrollo: `pip install -e .[dev]`)*.

---

## 🚀 Guía de Ejecución

### 1. Demostración Interactiva en Vivo con Cámara (`demo_camara.py`)
Inicia la aplicación completa con detección facial, máquina de estados finita de estabilidad (FSM), escritura en memoria compartida, inferencia ONNX y HUD táctico en tiempo real:

```bash
python demo_camara.py
```

**Controles del teclado durante la ejecución:**
- <kbd>Q</kbd> o <kbd>ESC</kbd>: Cerrar la aplicación y liberar recursos.
- <kbd>R</kbd>: Reiniciar la máquina de estados y limpiar el diagnóstico actual.
- <kbd>C</kbd>: Alternar entre las cámaras conectadas al equipo.
- <kbd>D</kbd>: Forzar disparo manual del diagnóstico con el encuadre actual.

---

### 2. Servidor API FastAPI Loopback
Para levantar únicamente el servicio de inferencia y motor de reglas como un microservicio local:

```bash
uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Documentación interactiva disponible en el navegador (en modo local):
- Swagger UI: `http://127.0.0.1:8000/docs`
- Redoc: `http://127.0.0.1:8000/redoc`

---

### 3. Verificación Extremo a Extremo (`verify_live_pipeline.py`)
Ejecuta una prueba completa de integración sintética sin necesidad de encender la cámara física:
```bash
python scripts/verify_live_pipeline.py
```

---

### 4. Benchmark de Latencia On-Edge (`benchmark_latency.py`)
Mide la latencia de inferencia en milisegundos de los modelos INT8 (`MobileNetV3` y `U-Net Nano`) en 4 hilos:
```bash
python scripts/benchmark_latency.py
```

---

### 5. Diagnóstico de Cámaras (`diagnose_cameras.py`)
En entornos Windows, lista los dispositivos de captura disponibles registrados en DirectShow y PnP:
```bash
python scripts/diagnose_cameras.py
```

---

## 🧪 Suite de Pruebas Automatizadas (TDD)

El proyecto cuenta con una batería de pruebas unitarias y de integración que validan de forma estricta los requerimientos del sistema:

```bash
pytest
```

### Cobertura de las Pruebas:
| Archivo de Prueba | Validación |
| :--- | :--- |
| `tests/test_domain_rules.py` | Reglas de prescripción botánica deterministas por edad y severidad en SQLite 3NF. |
| `tests/test_privacy.py` | Garantía de Cero Persistencia Biométrica: Cero imágenes escritas en disco. |
| `tests/test_security.py` | Validación del token de dispositivo Bearer; rechazo con 401 si falta o es inválido. |
| `tests/test_shm_validation.py` | Control de descriptores SHM inexistentes o buffers corruptos/incompletos (HTTP 400). |
| `tests/test_thermal.py` | Salvaguarda de estrangulamiento térmico: Bloqueo de inferencia a $>75.0^\circ\text{C}$ (HTTP 422). |

---

## 📡 Contratos de la API REST

### `POST /api/v1/diagnostics/analyze`

Ejecuta el análisis dermatoscópico a partir de un descriptor de memoria compartida volátil.

#### Cabeceras de Petición (Headers)
```http
Authorization: Bearer test_device_secret_token_2026
X-Correlation-ID: 73bf6ea6-4403-4de8-84cb-ab6048b4bd01
Content-Type: application/json
```

#### Cuerpo de la Petición (JSON Request)
```json
{
  "shm_descriptor": "psm_12345678",
  "telemetry": {
    "stability_duration_ms": 1600,
    "thermal_soc_celsius": 48.5
  }
}
```

#### Respuesta Exitosa (`HTTP 201 Created`)
```json
{
  "datos": {
    "sesion_id": "c7a8b9e0-1234-5678-9abc-def012345678",
    "clinica": {
      "edad_biologica_estimada": 30,
      "porcentaje_hiperpigmentacion": 1.25,
      "clasificacion_severidad": "LEVE"
    },
    "prescripciones": [
      {
        "condicion_objetivo": "HIPERPIGMENTACION",
        "especie": "Arctostaphylos uva-ursi",
        "nombre_comun": "Gayuba",
        "precauciones": "No combinar simultáneamente con peróxido de benzoilo ni hidroquinona. Evitar exposición solar directa sin fotoprotección SPF 50+."
      }
    ]
  },
  "metadatos": {
    "correlation_id": "73bf6ea6-4403-4de8-84cb-ab6048b4bd01",
    "execution_time_ms": 12.45
  }
}
```

#### Respuestas de Error
| Código HTTP | Error Code | Causa |
| :--- | :--- | :--- |
| `401 Unauthorized` | `INVALID_DEVICE_TOKEN` | Cabecera `Authorization` ausente o token no coincide con el secreto en `tmpfs`. |
| `400 Bad Request` | `INVALID_SHM_DESCRIPTOR` | Descriptor de memoria compartida no encontrado o tamaño menor a 150,528 bytes. |
| `422 Unprocessable` | `THERMAL_THROTTLING_ACTIVE` | Temperatura del SoC Broadcom $> 75.0^\circ\text{C}$. Inferencia suspendida por protección térmica. |

---

## 🌿 Modelo de Datos y Reglas Fitoterapéuticas (SQLite 3NF)

El esquema de datos relacional asegura integridad referencial y atomicidad total (`PRAGMA foreign_keys = ON;`).

```mermaid
erDiagram
    SEVERIDAD_NIVELES ||--o{ REGLAS_BOTANICAS : clasifica
    CONDICIONES_OBJETIVO ||--o{ REGLAS_BOTANICAS : aborda
    ESPECIES_BOTANICAS ||--o{ REGLAS_BOTANICAS : compone
    SESIONES_DIAGNOSTICO ||--o{ SESION_PRESCRIPCIONES : registra
    REGLAS_BOTANICAS ||--o{ SESION_PRESCRIPCIONES : aplica

    SEVERIDAD_NIVELES {
        int severidad_id PK
        text codigo UK "NINGUNA, LEVE, MODERADA, ALTA"
        real umbral_min_pct
        real umbral_max_pct
    }
    ESPECIES_BOTANICAS {
        int especie_id PK
        text nombre_cientifico UK
        text nombre_comun
        text precauciones
    }
    REGLAS_BOTANICAS {
        int regla_id PK
        int edad_min
        int edad_max
        int severidad_id FK
        int condicion_id FK
        int especie_id FK
    }
    SESIONES_DIAGNOSTICO {
        text sesion_id PK "UUID v5 determinista"
        int severidad_id FK
        int edad_estimada
        real porcentaje_manchas
        real tiempo_proc_ms
        datetime creado_en
    }
```

### Catálogo de Especies Fitoterapéuticas Calibradas:
1. **Gayuba (*Arctostaphylos uva-ursi*)**: Inhibidor natural de la tirosinasa vía arbutina para hiperpigmentación leve a moderada.
2. **Rosa mosqueta (*Rosa canina*)**: Estimulador de regeneración celular dérmica rica en ácido trans-retinoico y antioxidantes.
3. **Regaliz (*Glycyrrhiza glabra*)**: Dispersión de melanina mediante glabridina para hiperpigmentaciones maduras.
4. **Té verde (*Camellia sinensis*)**: Polifenoles y EGCG para foto-protección preventiva y estrés oxidativo.
5. **Gotu Kola (*Centella asiatica*)**: Síntesis de colágeno y remodelación de la matriz extracelular (anti-aging).
6. **Sauce blanco (*Salix alba*)**: Queratolítico natural con derivados de salicina para manchas queratósicas.

---

## 🔒 Privacidad Radical y Seguridad (Zero-Disk)

El diseño del software respeta rigurosamente las normas de protección de datos de salud y biometría:
1. **Aislamiento en Memoria Compartida**: Las imágenes de video se almacenan únicamente en el buffer RAM mapeado por `/dev/shm` (o el subsistema de memoria compartida del SO). El descriptor se abre con un gestor de contexto seguro que libera el mapeo de memoria en cuanto finaliza el paso de inferencia.
2. **Cero Logs de Imágenes**: No existen sentencias `cv2.imwrite`, escrituras en archivos temporales o serialización a disco del tensor de imagen.
3. **Anonimización por Diseño**: La sesión no almacena identificadores personales, nombres, ni vectores de incrustación facial. El `sesion_id` se genera mediante **UUID v5 determinista** empleando un Namespace clínico reservado y el hash de los parámetros de diagnóstico.
4. **Token de Dispositivo en `tmpfs`**: En producción sobre Raspberry Pi OS, el token de autenticación se lee desde `/run/lock/derma_device.token` montado en memoria volátil `tmpfs`, regenerado dinámicamente al reiniciar el sistema.

---

## 🌐 Variables de Entorno

Puedes personalizar el comportamiento del sistema mediante las siguientes variables de entorno:

| Variable | Valor por Defecto | Descripción |
| :--- | :--- | :--- |
| `DERMA_DB_PATH` | `data/derma.db` | Ruta a la base de datos SQLite embebida. |
| `DERMA_TOKEN_PATH` | `/run/lock/derma_device.token` | Ruta al archivo con el token de dispositivo en `tmpfs`. |
| `DERMA_DEV_TOKEN` | `test_device_secret_token_2026` | Token de desarrollo para pruebas locales sin archivo físico. |
| `DERMA_DEVICE_TOKEN`| N/A | Token explícito en variable de entorno para sobreescribir la autenticación. |

---

## 📄 Licencia y Conformidad
Este proyecto está implementado bajo la especificación técnica **[SPEC-001](spec/Spec.md)** para sistemas embebidos de diagnóstico clínico *on-edge*.

## Control móvil para el dermatólogo

El panel web adaptable permite **reiniciar el escaneo de la misma persona** desde el
navegador del celular, consultar el estado de la cámara y ver cuántas lecturas lleva
la sesión. Muestra además el **resultado actual**: hiperpigmentación, severidad,
edad biológica estimada, fototipo, indicación y recomendaciones con sus precauciones.
La sesión, el número de lectura y la hora permiten identificar el resultado.
Repetir la captura limpia el resultado visible y conserva las lecturas anteriores. No inicia una sesión de otro paciente.

Actívalo al ejecutar la cámara (Linux / Raspberry Pi):

```bash
DERMA_MOBILE=1 python demo_camara.py
```

En PowerShell:

```powershell
$env:DERMA_MOBILE="1"
python demo_camara.py
```

1. Conecta el celular y el equipo a la misma red Wi-Fi de confianza.
2. Abre `http://<IP-LAN-del-equipo>:8080` en el celular. En Linux puedes consultar
   la IP local con `hostname -I`; en Windows, con `ipconfig`.
3. Ingresa el código temporal que aparece en la consola al arrancar la cámara.
4. Pulsa **Reiniciar escaneo** y confirma. El panel distingue la solicitud enviada
   de la confirmación de que la cámara aplicó el reinicio.

El código cambia cada vez que se inicia el servidor y se mantiene únicamente en
memoria del navegador; recargar la página requiere volver a conectarse. La interfaz
recibe únicamente los campos clínicos necesarios de la lectura actual, sin imágenes.
No usa almacenamiento local ni caché para resultados. Al perder conexión, cambiar
de pestaña o cerrar la consulta, retira el diagnóstico de la pantalla. Desactiva el botón durante el análisis o
cuando la cámara deja de responder, e intenta recuperar la conexión automáticamente.
Una solicitud pendiente caduca a los 10 segundos para evitar ejecutarla tarde.

El servidor móvil se inicia dentro del proceso de cámara, escucha en el puerto
8080 (configurable mediante `DERMA_MOBILE_PORT`) y se cierra junto con la cámara.
No expone el API de inferencia ni cambia su configuración loopback. Por defecto el
control móvil está desactivado. El acceso HTTP está previsto para una red local de
confianza; para redes compartidas utiliza un proxy HTTPS y no publiques el puerto
directamente en Internet.

Pruebas del control móvil: `pytest tests/test_mobile_control.py`.

Prueba de interfaz con datos sintéticos (requiere Playwright y Chromium):
`python scripts/check_mobile_browser.py`. Esta prueba no usa una cámara ni escribe
lecturas clínicas en la base de datos.

Para la Raspberry ya instalada, ver [operación y respaldo](deploy/README-mobile.md).

## Recomendaciones locales con cuestionario

La selección de recomendaciones usa reglas locales, SQLite y un catálogo versionado; no necesita internet ni un modelo de lenguaje. Completa el cuestionario de la lectura desde la interfaz móvil. Las reglas sin revisión clínica vigente quedan bloqueadas y los casos no cubiertos solicitan evaluación profesional.

El catálogo inicial está pendiente de revisión clínica. Consulta [uso, API y actualización por USB](docs/recomendaciones-offline.md).

El flujo del cuestionario y las recomendaciones del espejo está documentado en
[deploy/README-recommendations.md](deploy/README-recommendations.md).
