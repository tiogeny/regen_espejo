from starlette.testclient import TestClient
from src.api.app import inference_engine


def test_edad_30_severidad_leve_retorna_arbutina(
    client: TestClient,
    auth_headers: dict,
    create_shm_buffer,
    monkeypatch, questionnaire, reviewed_catalog
):
    """
    Given: Mock inferencia ONNX -> (Edad=30, Spots=1.5% -> LEVE)
    When: Se procesa el motor de reglas
    Then: El payload JSON de salida incluye 'Arctostaphylos uva-ursi' (Gayuba)
    """
    shm_name, _ = create_shm_buffer()
    payload = {
        "shm_descriptor": shm_name,
        "questionnaire": questionnaire.model_dump(),
        "telemetry": {
            "stability_duration_ms": 1600,
            "thermal_soc_celsius": 42.0,
        },
    }

    # Mock de inferencia ONNX según el Given de la especificación
    monkeypatch.setattr(inference_engine, "run_inference", lambda tensor: (30, 1.5))

    response = client.post("/api/v1/diagnostics/analyze", json=payload, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    clinica = body["datos"]["clinica"]
    assert clinica["edad_biologica_estimada"] == 30
    assert clinica["porcentaje_hiperpigmentacion"] == 1.5
    assert clinica["clasificacion_severidad"] == "LEVE"

    prescriptions = body["datos"]["prescripciones"]
    species_list = [p["especie"] for p in prescriptions]
    assert "Arctostaphylos uva-ursi" in species_list

    gayuba_entry = next(p for p in prescriptions if p["especie"] == "Arctostaphylos uva-ursi")
    assert gayuba_entry["nombre_comun"] == "Gayuba"
    assert gayuba_entry["precauciones"] == "Precaución de prueba"


def test_restriccion_conflictos_multiples_compuestos(
    client: TestClient,
    auth_headers: dict,
    create_shm_buffer,
    monkeypatch, questionnaire, reviewed_catalog
):
    """
    Given: Mock inferencia ONNX -> (Edad=65, Spots=5.0% -> ALTA)
    When: Se procesa el motor de reglas
    Then: Se retornan 2 registros (Rosa canina y Glycyrrhiza glabra) y ambas especies
          incluyen sus precauciones específicas consolidadas en el payload
    """
    shm_name, _ = create_shm_buffer()
    payload = {
        "shm_descriptor": shm_name,
        "questionnaire": questionnaire.model_copy(update={"age": 65}).model_dump(),
        "telemetry": {
            "stability_duration_ms": 1600,
            "thermal_soc_celsius": 42.0,
        },
    }

    # Mock de inferencia ONNX según el Given de la especificación
    monkeypatch.setattr(inference_engine, "run_inference", lambda tensor: (65, 5.0))

    response = client.post("/api/v1/diagnostics/analyze", json=payload, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    clinica = body["datos"]["clinica"]
    assert clinica["edad_biologica_estimada"] == 65
    assert clinica["porcentaje_hiperpigmentacion"] == 5.0
    assert clinica["clasificacion_severidad"] == "ALTA"

    prescriptions = body["datos"]["prescripciones"]
    assert len(prescriptions) == 2

    species_list = [p["especie"] for p in prescriptions]
    assert "Rosa canina" in species_list
    assert "Glycyrrhiza glabra" in species_list

    # Validar que cada especie mantiene sus precauciones específicas
    for item in prescriptions:
        assert item["precauciones"] is not None
        assert len(item["precauciones"]) > 0
