"""Cuestionario del espejo: alcance, seguridad y vínculo a la lectura vigente."""
import uuid
import pytest
from fastapi.testclient import TestClient
from src.db.database import get_db
from src.db.repository import get_severity_by_spot_pct, save_diagnostic_session
from src.mobile.server import ScanControl, create_mobile_app


@pytest.fixture
def mirror_reading():
    analysis_id = str(uuid.uuid4())
    with get_db() as conn:
        severity = get_severity_by_spot_pct(conn, 1.5)
        save_diagnostic_session(conn, analysis_id, severity['severidad_id'], 65, 1.5, 10, [])
    result = {'datos': {'sesion_id': analysis_id, 'clinica': {
        'edad_biologica_estimada': 65, 'porcentaje_hiperpigmentacion': 1.5,
        'porcentaje_hiperpigmentacion_zona': 90,
        'zona_seleccionada': {'x': .5, 'y': .5, 'radius': .1}}}}
    control = ScanControl()
    control.publish('DIAGNOSTICADO', 1, result, 'test-person')
    client = TestClient(create_mobile_app(control, 'token'), base_url='http://127.0.0.1', client=('127.0.0.1', 12345))
    return control, client, analysis_id


def test_explicit_face_scope_uses_global_measurement_and_declared_age(mirror_reading, questionnaire, reviewed_catalog):
    control, client, analysis_id = mirror_reading
    payload = {'analysis_id': analysis_id, 'questionnaire': questionnaire.model_dump(), 'scope': 'face', 'revision': 0}
    response = client.post('/mirror/api/recommendations', json=payload)
    assert response.status_code == 200
    diagnostic = response.json()
    assert diagnostic['orientation']['alcance'] == 'rostro_completo'
    assert diagnostic['prescriptions'][0]['especie'] == 'Arctostaphylos uva-ursi'
    assert diagnostic['clinical']['edad_biologica_estimada'] == 65
    assert 'questionnaire' not in str(control.snapshot())
    # Recomendación del rostro (1.5%), no de la zona (90%).
    with get_db() as conn:
        ids = [r[0] for r in conn.execute('SELECT regla_id FROM sesion_prescripciones WHERE sesion_id=?', (analysis_id,))]
    assert 1 in ids
    assert client.post('/mirror/api/recommendations', json={**payload, 'scope': 'zone'}).json()['prescriptions'] == []


def test_unknown_answers_and_uncovered_profile_are_explained(mirror_reading, questionnaire):
    _, client, analysis_id = mirror_reading
    payload = {'analysis_id': analysis_id, 'scope': 'face', 'revision': 0, 'questionnaire': questionnaire.model_dump()}
    payload['questionnaire']['sensitive_skin'] = None
    response = client.post('/mirror/api/recommendations', json=payload).json()
    assert response['orientation']['estado'] == 'DATOS_INCOMPLETOS'
    assert 'sensitive_skin' in response['orientation']['datos_faltantes']
    payload['questionnaire'] = questionnaire.model_copy(update={'is_pregnant': True}).model_dump()
    response = client.post('/mirror/api/recommendations', json=payload).json()
    assert response['orientation']['estado'] == 'REVISION_PROFESIONAL'
    assert response['prescriptions'] == []


def test_empty_catalog_does_not_fabricate_recommendations(mirror_reading, questionnaire, tmp_path, monkeypatch):
    path = tmp_path / 'empty.json'
    path.write_text('{"version":"pending","rules":[]}')
    monkeypatch.setenv('DERMA_KNOWLEDGE_PATH', str(path))
    _, client, analysis_id = mirror_reading
    response = client.post('/mirror/api/recommendations', json={'analysis_id': analysis_id, 'scope': 'face', 'revision': 0, 'questionnaire': questionnaire.model_dump()}).json()
    assert response['orientation']['estado'] == 'SIN_RECOMENDACION_VALIDADA'
    assert response['prescriptions'] == []


def test_local_access_validation_and_current_reading(mirror_reading, questionnaire):
    control, client, analysis_id = mirror_reading
    payload = {'analysis_id': analysis_id, 'scope': 'face', 'revision': 0, 'questionnaire': questionnaire.model_dump()}
    remote = TestClient(create_mobile_app(control, 'token'), base_url='http://127.0.0.1', client=('192.168.1.5', 12345))
    assert remote.post('/mirror/api/recommendations', json=payload).status_code == 403
    assert client.post('/mirror/api/recommendations', json=payload, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/mirror/api/recommendations', json={**payload, 'analysis_id': 'old'}).status_code == 409
    assert client.post('/mirror/api/recommendations', json={**payload, 'scope': 'invalid'}).status_code == 422
    invalid = {**payload, 'questionnaire': {**payload['questionnaire'], 'age': 30.5}}
    assert client.post('/mirror/api/recommendations', json=invalid).status_code == 422
    control.request_restart(0)
    assert client.post('/mirror/api/recommendations', json=payload).status_code == 409
