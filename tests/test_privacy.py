import sqlite3
from pathlib import Path
from starlette.testclient import TestClient
from src.config import BASE_DIR, DB_PATH


def test_cero_persistencia_biometrica_tras_ejecucion(
    client: TestClient,
    auth_headers: dict,
    create_shm_buffer,
    setup_test_environment,
    monkeypatch
):
    """
    Given: Payload válido con puntero a memoria compartida sintética
    When: La transacción se procesa y retorna 201 Created
    Then: 
        - Inspección del sistema de archivos en particiones no contiene artefactos de imagen
        - El conteo de filas en `sesiones_diagnostico` aumenta en 1 sin blobs asociados.
    """
    # La privacidad de persistencia se prueba con una inferencia explícita,
    # sin depender de pesos ausentes ni valores clínicos predeterminados.
    monkeypatch.setattr("src.api.app.inference_engine.run_inference", lambda tensor: (30, 1.5))

    # Snapshot inicial de archivos de imagen en el espacio del proyecto
    forbidden_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".npy", ".raw", ".yuv"}
    before_images = [
        p for p in BASE_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in forbidden_extensions
    ]

    # Conteo previo en base de datos
    conn = sqlite3.connect(setup_test_environment["db_path"])
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sesiones_diagnostico")
    count_before = cur.fetchone()[0]

    # Ejecutar petición de análisis
    shm_name, _ = create_shm_buffer()
    payload = {
        "shm_descriptor": shm_name,
        "telemetry": {
            "stability_duration_ms": 1600,
            "thermal_soc_celsius": 40.0,
        },
    }

    response = client.post("/api/v1/diagnostics/analyze", json=payload, headers=auth_headers)
    assert response.status_code == 201

    # Verificar que el conteo en sesiones_diagnostico aumentó en exactamente 1
    cur.execute("SELECT COUNT(*) FROM sesiones_diagnostico")
    count_after = cur.fetchone()[0]
    assert count_after == count_before + 1

    # Verificar que las columnas en sesiones_diagnostico no contienen datos binarios de imagen
    cur.execute("PRAGMA table_info(sesiones_diagnostico)")
    columns = [col[1] for col in cur.fetchall()]
    assert "imagen" not in columns
    assert "foto" not in columns
    assert "frame" not in columns
    assert "blob" not in columns
    conn.close()

    # Snapshot posterior: no debe haber ningún archivo de imagen nuevo creado en disco
    after_images = [
        p for p in BASE_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in forbidden_extensions
    ]
    assert len(after_images) == len(before_images), "Se detectaron archivos de imagen persistidos en disco!"
