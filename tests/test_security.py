from starlette.testclient import TestClient


def test_peticion_sin_token_rechazada_inmediatamente(client: TestClient, create_shm_buffer):
    """
    Given: Petición a /api/v1/diagnostics/analyze sin header Authorization
    Then: HTTP Status == 401, Código Error == 'INVALID_DEVICE_TOKEN'
    """
    shm_name, _ = create_shm_buffer()
    payload = {
        "shm_descriptor": shm_name,
        "telemetry": {
            "stability_duration_ms": 1600,
            "thermal_soc_celsius": 45.0,
        },
    }

    # Petición sin encabezado Authorization
    response = client.post("/api/v1/diagnostics/analyze", json=payload)

    assert response.status_code == 401
    data = response.json()
    assert data.get("error_code") == "INVALID_DEVICE_TOKEN"


def test_peticion_token_invalido_rechazada(client: TestClient, create_shm_buffer):
    """
    Given: Petición con token que no coincide con el secreto en tmpfs
    Then: HTTP Status == 401, Código Error == 'INVALID_DEVICE_TOKEN'
    """
    shm_name, _ = create_shm_buffer()
    payload = {
        "shm_descriptor": shm_name,
        "telemetry": {
            "stability_duration_ms": 1600,
            "thermal_soc_celsius": 45.0,
        },
    }
    headers = {
        "Authorization": "Bearer token_falso_no_autorizado",
        "Content-Type": "application/json",
    }

    response = client.post("/api/v1/diagnostics/analyze", json=payload, headers=headers)

    assert response.status_code == 401
    data = response.json()
    assert data.get("error_code") == "INVALID_DEVICE_TOKEN"
