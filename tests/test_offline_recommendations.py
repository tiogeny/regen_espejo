import json
import socket
from datetime import date, timedelta

import pytest
from src.db.database import get_db
from src.domain.recommendations import Questionnaire, recommend, rule_fingerprint
from src.domain.rules_engine import RulesEngine
from src.domain.age_stratified_rules import PatientProfile


def test_unknown_compound_is_blocked():
    safe, blocked = RulesEngine().filter_db_prescriptions_by_safety([{'especie': 'Unknown'}], PatientProfile(age=30))
    assert safe == []
    assert blocked[0]['contraindicaciones'][0]['category'] == 'UNKNOWN_COMPOUND'


def test_missing_answers_are_not_negative():
    with get_db() as conn:
        result = recommend(conn, 1.5, Questionnaire(age=30))
    assert result['estado'] == 'DATOS_INCOMPLETOS'
    assert 'is_pregnant' in result['datos_faltantes']
    assert result['prescripciones'] == []


@pytest.mark.parametrize('field,value', [('is_pregnant', True), ('is_lactating', True),
    ('current_treatments', ['retinoide']), ('known_allergies', ['desconocida']),
    ('concerning_changes', True), ('age', 12), ('has_open_wounds', True)])
def test_uncovered_profiles_require_review(questionnaire, reviewed_catalog, field, value):
    with get_db() as conn:
        result = recommend(conn, 1.5, questionnaire.model_copy(update={field: value}))
    assert result['estado'] == 'REVISION_PROFESIONAL'
    assert result['prescripciones'] == []


def test_approved_catalog_runs_without_network(questionnaire, reviewed_catalog, monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError('Network access')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket, 'getaddrinfo', deny)
    with get_db() as conn:
        result = recommend(conn, 1.5, questionnaire)
    assert result['prescripciones'][0]['especie'] == 'Arctostaphylos uva-ursi'
    assert result['prescripciones'][0]['precauciones'] == 'Precaución de prueba'


@pytest.mark.parametrize('mode', ['expired', 'changed', 'draft', 'broken', 'duplicate'])
def test_invalid_catalog_never_recommends(questionnaire, reviewed_catalog, mode):
    data = json.loads(reviewed_catalog.read_text())
    if mode == 'expired': data['rules'][0]['valid_until'] = '2000-01-01'
    if mode == 'changed': data['rules'][0]['fingerprint'] = '0' * 64
    if mode == 'draft': data['rules'][0]['status'] = 'draft'
    if mode == 'duplicate': data['rules'].append(data['rules'][0])
    reviewed_catalog.write_text('invalid' if mode == 'broken' else json.dumps(data))
    with get_db() as conn:
        result = recommend(conn, 1.5, questionnaire)
    assert result['prescripciones'] == []


def test_salicylate_filter(questionnaire, reviewed_catalog):
    q = questionnaire.model_copy(update={'salicylate_allergy': True})
    with get_db() as conn:
        result = recommend(conn, 5, q)
    assert result['prescripciones'] == []
    assert result['exclusiones'][0]['regla_id'] == 107


def test_api_requires_profile_and_uses_declared_age(client, auth_headers, create_shm_buffer, monkeypatch, questionnaire, reviewed_catalog):
    from src.api.app import inference_engine
    monkeypatch.setattr(inference_engine, 'run_inference', lambda _: (65, 1.5))
    name, _ = create_shm_buffer()
    payload = dict(shm_descriptor=name, telemetry=dict(stability_duration_ms=1600, thermal_soc_celsius=40))
    response = client.post('/api/v1/diagnostics/analyze', json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()['datos']['prescripciones'] == []
    import uuid
    auth_headers['X-Correlation-ID'] = str(uuid.uuid4())
    payload['questionnaire'] = questionnaire.model_dump()
    response = client.post('/api/v1/diagnostics/analyze', json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()['datos']
    assert data['clinica']['edad_biologica_estimada'] == 65
    assert data['prescripciones'][0]['especie'] == 'Arctostaphylos uva-ursi'


def test_report_does_not_reintroduce_prescriptions():
    from src.reports.clinical_report_generator import ClinicalReportGenerator
    report = ClinicalReportGenerator()
    for data in ({}, {'datos': {'prescripciones': []}}):
        assert report._resolve_prescriptions(data, 30, 1.5, 'LEVE') == []


def test_mobile_questionnaire_is_bound_to_current_reading(client, auth_headers, create_shm_buffer, monkeypatch, questionnaire, reviewed_catalog):
    from fastapi.testclient import TestClient
    from src.api.app import inference_engine
    from src.mobile.server import ScanControl, create_mobile_app
    monkeypatch.setattr(inference_engine, 'run_inference', lambda _: (30, 1.5))
    name, _ = create_shm_buffer()
    payload = dict(shm_descriptor=name, telemetry=dict(stability_duration_ms=1600, thermal_soc_celsius=40))
    reading = client.post('/api/v1/diagnostics/analyze', json=payload, headers=auth_headers).json()
    control = ScanControl()
    control.publish('DIAGNOSTICADO', 1, reading, 'person-1')
    mobile = TestClient(create_mobile_app(control, 'test-token'))
    headers = {'Authorization': 'Bearer test-token'}
    body = dict(analysis_id=reading['datos']['sesion_id'], questionnaire=questionnaire.model_dump())
    assert mobile.post('/api/recommendations', json=body).status_code == 401
    assert mobile.post('/api/recommendations', headers=headers, json={**body, 'analysis_id': 'old'}).status_code == 409
    response = mobile.post('/api/recommendations', headers=headers, json=body)
    assert response.status_code == 200
    assert response.json()['prescriptions'][0]['especie'] == 'Arctostaphylos uva-ursi'
    assert reading['datos']['prescripciones']  # El PDF y cámara comparten este resultado.
    assert 'questionnaire' not in str(control.snapshot())
    with get_db() as conn:
        assert conn.execute('SELECT regla_id FROM sesion_prescripciones WHERE sesion_id=?', (body['analysis_id'],)).fetchone()[0] == 1
    control.request_restart(0)
    assert mobile.post('/api/recommendations', headers=headers, json=body).status_code == 409


def test_empty_report_list_overrides_legacy_candidates():
    from src.reports.clinical_report_generator import ClinicalReportGenerator
    data = {'prescripciones': [], 'activos_estratificados_recomendados': [{'especie': 'Salix alba'}]}
    assert ClinicalReportGenerator()._resolve_prescriptions(data, 30, 5, 'ALTA') == []
