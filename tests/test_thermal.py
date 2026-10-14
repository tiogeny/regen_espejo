from starlette.testclient import TestClient


def test_bloqueo_termico_seguro(client: TestClient, auth_headers: dict, create_shm_buffer):
    """
    Given: Payload con telemetry.thermal_soc_celsius == 76.5 (> 75.0°C)
    Then: HTTP Status == 422, Código Error == 'THERMAL_THROTTLING_ACTIVE'
    """
    shm_name, _ = create_shm_buffer()
    payload = {
        "shm_descriptor": shm_name,
        "telemetry": {
            "stability_duration_ms": 1600,
            "thermal_soc_celsius": 76.5,
        },
    }

    response = client.post("/api/v1/diagnostics/analyze", json=payload, headers=auth_headers)

    assert response.status_code == 422
    data = response.json()
    assert data.get("error_code") == "THERMAL_THROTTLING_ACTIVE"
