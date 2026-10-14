"""
Verificación de Inferencia en Vivo Extremo a Extremo (Hermes & Antigravity)
Prueba la ingesta desde POSIX SHM, inferencia real con los modelos ONNX INT8,
cruce con SQLite y generación del payload clínico 201.
"""

import sys
import tempfile
from pathlib import Path
from multiprocessing import shared_memory
import numpy as np
from starlette.testclient import TestClient

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import uuid

from src.api.app import app
from src.config import DEV_TOKEN


def test_live_inference():
    print("=" * 65)
    print("🔬 TEST DE INTEGRACIÓN REAL EN VIVO (FastAPI + SHM + ONNX INT8)")
    print("=" * 65)

    client = TestClient(app)

    # 1. Crear buffer sintético en memoria compartida (simulando daemon de cámara)
    shape = (224, 224, 3)
    total_bytes = 224 * 224 * 3
    shm = shared_memory.SharedMemory(create=True, size=total_bytes)
    
    try:
        arr = np.ndarray(shape, dtype=np.uint8, buffer=shm.buf)
        # Llenar con valores típicos de piel con manchas (valores RGB sintéticos)
        arr.fill(160)
        # Simular mácula oscura en región central
        arr[80:140, 80:140, :] = 50

        payload = {
            "shm_descriptor": shm.name,
            "telemetry": {
                "stability_duration_ms": 1800,
                "thermal_soc_celsius": 48.5,
            },
        }

        # Warm-up previo para inicializar conexiones y pools de memoria ONNX
        warmup_headers = {
            "Authorization": f"Bearer {DEV_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        _ = client.post("/api/v1/diagnostics/analyze", json=payload, headers=warmup_headers)

        print("Enviando petición POST /api/v1/diagnostics/analyze (Medición de SLA en estado estacionario)...")
        headers = {
            "Authorization": f"Bearer {DEV_TOKEN}",
            "X-Correlation-ID": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        response = client.post("/api/v1/diagnostics/analyze", json=payload, headers=headers)
        
        print(f"Status Code: {response.status_code}")
        assert response.status_code == 201, f"Error en endpoint: {response.text}"

        data = response.json()
        print("\nPayload Clínico Generado con Éxito:")
        import json
        print(json.dumps(data, indent=2, ensure_ascii=False))

        clinica = data["datos"]["clinica"]
        print(f"\nResultados Clínicos:")
        print(f"  - Edad Biológica Estimada: {clinica['edad_biologica_estimada']} años")
        print(f"  - Hiperpigmentación: {clinica['porcentaje_hiperpigmentacion']}%")
        print(f"  - Clasificación de Severidad: {clinica['clasificacion_severidad']}")
        print(f"  - Prescripciones Emitidas: {len(data['datos']['prescripciones'])}")
        print(f"  - Tiempo de Ejecución Total: {data['metadatos']['execution_time_ms']} ms")
        
        assert data["metadatos"]["execution_time_ms"] <= 180.0, "Tiempo de ejecución supera el SLA de 180 ms!"
        print("\n✅ Verificación de inferencia real en vivo superada con éxito.")
        print("=" * 65)

    finally:
        shm.close()
        shm.unlink()


if __name__ == "__main__":
    test_live_inference()
