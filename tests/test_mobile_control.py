"""Control remoto real sin depender de cámara, MediaPipe o modelos ONNX."""
import ast
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.mobile.server import ScanControl, create_mobile_app


@pytest.fixture
def remote():
    control = ScanControl()
    control.publish("DIAGNOSTICADO", 3)
    return control, TestClient(create_mobile_app(control, "private-test-token"))


HEADERS = {"Authorization": "Bearer private-test-token"}


def test_authentication_and_no_clinical_data(remote):
    control, client = remote
    assert client.get('/api/status').status_code == 401
    assert client.post('/api/restart', json={'revision': 0}).status_code == 401
    assert client.get('/api/status', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    response = client.get('/api/status', headers=HEADERS)
    assert response.json() == dict(connected=True, state='DIAGNOSTICADO', samples=3, revision=0, applied_revision=None, pending=False, diagnostic=None)
    assert response.headers['cache-control'] == 'no-store'
    for path in ('/', '/mobile.css', '/mobile.js'):
        assert client.get(path).status_code == 200
    assert client.get('/api/v1/diagnostics/analyze').status_code == 404


def test_restart_only_acknowledged_after_camera_applies(remote):
    control, client = remote
    assert client.post('/api/restart', headers=HEADERS, json={'revision': 0}).status_code == 202
    assert control.snapshot()['pending']
    assert control.snapshot()['revision'] == 0
    assert client.post('/api/restart', headers=HEADERS, json={'revision': 0}).status_code == 409
    restart = Mock()
    control.apply_pending(restart)
    control.apply_pending(restart)
    restart.assert_called_once()
    assert control.snapshot()['revision'] == 1
    assert control.snapshot()['samples'] == 3
    assert control.snapshot()['state'] == 'BUSCANDO'
    assert client.post('/api/restart', headers=HEADERS, json={'revision': 0}).status_code == 409


def test_offline_busy_and_invalid_requests(remote):
    control, client = remote
    control.publish('ANALIZANDO', 3)
    assert client.post('/api/restart', headers=HEADERS, json={'revision': 0}).status_code == 409
    control.disconnect()
    assert client.post('/api/restart', headers=HEADERS, json={'revision': 0}).status_code == 503
    assert not control.snapshot()['connected']
    assert client.post('/api/restart', headers=HEADERS, json={'revision': -1}).status_code == 422


def test_stale_camera_and_expired_command(remote, monkeypatch):
    control, client = remote
    now = time.monotonic()
    control.request_restart(0)
    monkeypatch.setattr('src.mobile.server.time.monotonic', lambda: now + 11)
    assert not control.snapshot()['connected']
    restart = Mock()
    control.apply_pending(restart)
    restart.assert_not_called()
    assert not control.snapshot()['pending']
    assert control.snapshot()['revision'] == 0
    with pytest.raises(HTTPException) as exc:
        control.request_restart(0)
    assert exc.value.status_code == 503


def test_simultaneous_phones_cannot_queue_duplicate_restart(remote):
    control, _ = remote
    def request(_):
        try:
            control.request_restart(0)
            return 202
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(request, range(8)))
    assert results.count(202) == 1
    assert results.count(409) == 7


def test_camera_reset_clears_capture_but_preserves_session():
    # Ejecuta el método real aislado del hardware y sus importaciones pesadas.
    tree = ast.parse(Path('demo_camara.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LiveDermaCameraApp')
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('restart_scan', 'reset_stability')]
    scope = {'time': time}
    exec(compile(ast.Module(body=methods, type_ignores=[]), 'demo_camara.py', 'exec'), scope)
    camera = SimpleNamespace(state='DIAGNOSTICADO', stability_roi_buffer=[1], session_ages=[30, 31], session_id='same-person')
    camera.reset_stability = lambda: scope['reset_stability'](camera)
    scope['restart_scan'](camera)
    assert camera.state == 'BUSCANDO'
    assert camera.last_result is None
    assert camera.last_face_roi is None
    assert camera.last_mask is None
    assert camera.stability_roi_buffer == []
    assert camera.session_ages == [30, 31]
    assert camera.session_id == 'same-person'


def test_local_session_change_cancels_pending_without_false_ack(remote):
    control, _ = remote
    control.request_restart(0)
    control.invalidate()
    restart = Mock()
    control.apply_pending(restart)
    restart.assert_not_called()
    assert control.snapshot()['revision'] == 1
    assert control.snapshot()['applied_revision'] is None


@pytest.fixture
def diagnostic_result():
    return {'datos': {'sesion_id': 'analysis-123', 'clinica': {
        'edad_biologica_estimada': 34, 'porcentaje_hiperpigmentacion': 1.25,
        'clasificacion_severidad': 'LEVE', 'fototipo_fitzpatrick': 3,
        'fototipo_label': 'Fototipo III', 'ita_deg': 35.6,
        'indicacion_primaria': 'Texto generado por el equipo', 'gafas_detectadas': False,
        'private_extra': 'must-not-leak'}, 'prescripciones': [
        {'especie': 'Especie de prueba', 'nombre_comun': 'Nombre de prueba',
         'precauciones': 'Precaución generada', 'condicion_objetivo': 'HIPERPIGMENTACION'}]},
        'image': b'not-serializable', 'metadatos': {'total_call_ms': 84.2}}


def test_diagnostic_authenticated_projection_and_stable_timestamp(remote, diagnostic_result):
    control, client = remote
    control.publish('DIAGNOSTICADO', 2, diagnostic_result, 'session-abc')
    first = client.get('/api/status', headers=HEADERS).json()['diagnostic']
    assert first['session_id'] == 'session-abc'
    assert first['reading'] == 2
    assert first['clinical']['edad_biologica_estimada'] == 34
    assert first['clinical']['gafas_detectadas'] is False
    assert first['prescriptions'][0]['precauciones'] == 'Precaución generada'
    assert 'private_extra' not in first['clinical']
    assert 'image' not in str(first)
    control.publish('DIAGNOSTICADO', 2, diagnostic_result, 'session-abc')
    assert control.snapshot()['diagnostic']['reported_at'] == first['reported_at']
    first['clinical']['edad_biologica_estimada'] = 99
    assert control.snapshot()['diagnostic']['clinical']['edad_biologica_estimada'] == 34
    assert client.get('/api/status').status_code == 401


def test_diagnostic_cleared_while_scanning_offline_or_restarting(remote, diagnostic_result, monkeypatch):
    control, _ = remote
    for state in ('BUSCANDO', 'ESTABILIZANDO', 'ANALIZANDO'):
        control.publish('DIAGNOSTICADO', 1, diagnostic_result, 'session')
        control.publish(state, 1, diagnostic_result, 'session')
        assert control.snapshot()['diagnostic'] is None
    control.publish('DIAGNOSTICADO', 1, diagnostic_result, 'session')
    control.request_restart(0)
    assert control.snapshot()['diagnostic'] is None
    control.apply_pending(Mock())
    assert control.snapshot()['diagnostic'] is None
    control.publish('DIAGNOSTICADO', 1, diagnostic_result, 'session')
    now = time.monotonic()
    monkeypatch.setattr('src.mobile.server.time.monotonic', lambda: now + 11)
    assert control.snapshot()['diagnostic'] is None
    control.disconnect()
    assert control.snapshot()['diagnostic'] is None


def test_missing_nonfinite_and_invalid_diagnostic_values(remote):
    control, client = remote
    result = {'datos': {'clinica': {'edad_biologica_estimada': float('nan'),
                                   'porcentaje_hiperpigmentacion': float('inf')},
                        'prescripciones': None}}
    control.publish('DIAGNOSTICADO', 1, result, 'session')
    response = client.get('/api/status', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['diagnostic']['clinical'] == {}
    assert response.json()['diagnostic']['prescriptions'] == []
    control.publish('DIAGNOSTICADO', 1, {'error': 'failed'}, 'session')
    assert control.snapshot()['diagnostic'] is None
