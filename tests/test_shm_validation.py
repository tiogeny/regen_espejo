from multiprocessing import shared_memory
import numpy as np
from starlette.testclient import TestClient


def test_shape_incorrecto_en_buffer_shm_lanza_400(client: TestClient, auth_headers: dict):
    """
    Given: Buffer de memoria compartida expone matriz 100x100 (Esperado 224x224x3)
    Then: Excepción capturada, HTTP Status == 400 Bad Request, Código Error == 'INVALID_SHM_DESCRIPTOR'
    """
    # Crear buffer erróneo con tamaño 100x100 (10000 bytes)
    wrong_size = 100 * 100
    shm = shared_memory.SharedMemory(create=True, size=wrong_size)
    try:
        payload = {
            "shm_descriptor": shm.name,
            "telemetry": {
                "stability_duration_ms": 1600,
                "thermal_soc_celsius": 50.0,
            },
        }

        response = client.post("/api/v1/diagnostics/analyze", json=payload, headers=auth_headers)

        assert response.status_code == 400
        data = response.json()
        assert data.get("error_code") == "INVALID_SHM_DESCRIPTOR"
    finally:
        shm.close()
        shm.unlink()


def test_descriptor_inexistente_lanza_400(client: TestClient, auth_headers: dict):
    """
    Given: Descriptor de memoria compartida que no existe o es inaccesible
    Then: HTTP Status == 400 Bad Request, Código Error == 'INVALID_SHM_DESCRIPTOR'
    """
    payload = {
        "shm_descriptor": "non_existent_shm_descriptor_99999",
        "telemetry": {
            "stability_duration_ms": 1600,
            "thermal_soc_celsius": 50.0,
        },
    }

    response = client.post("/api/v1/diagnostics/analyze", json=payload, headers=auth_headers)

    assert response.status_code == 400
    data = response.json()
    assert data.get("error_code") == "INVALID_SHM_DESCRIPTOR"
