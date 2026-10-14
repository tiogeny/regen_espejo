"""Espejo local: RAM, coordenadas del recorte, acceso y estados reales."""
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from src.mobile.server import ScanControl, create_mobile_app


def local_client(control):
    return TestClient(create_mobile_app(control, 'test-token'), base_url='http://127.0.0.1', client=('127.0.0.1', 43210))


def test_preview_crop_and_target_use_same_coordinates():
    control = ScanControl()
    frame = np.zeros((200, 400, 3), dtype=np.uint8)
    frame[:, 100:300] = (25, 90, 160)
    control.publish_preview(frame, SimpleNamespace(point=(200, 100), radius=20))
    response = local_client(control).get('/mirror/api/frame')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['content-type'] == 'image/jpeg'
    assert response.headers['x-zone-x'] == '0.5'
    assert response.headers['x-zone-y'] == '0.5'
    assert response.headers['x-zone-radius'] == '0.1'
    decoded = cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (720, 720, 3)
    assert np.allclose(decoded[360, 360], [25, 90, 160], atol=3)


def test_camera_image_stale_or_disconnected_is_unavailable(monkeypatch):
    control = ScanControl()
    client = local_client(control)
    assert client.get('/mirror/api/frame').status_code == 503
    control.publish_preview(np.zeros((200, 200, 3), dtype=np.uint8))
    assert client.get('/mirror/api/frame').status_code == 200
    timestamp = control._preview_at
    monkeypatch.setattr('src.mobile.server.time.monotonic', lambda: timestamp + 4)
    assert client.get('/mirror/api/frame').status_code == 503
    control.disconnect()
    with pytest.raises(HTTPException):
        control.preview()


def test_camera_and_commands_are_local_only():
    control = ScanControl()
    control.publish('BUSCANDO', 0)
    remote = TestClient(create_mobile_app(control, 'test-token'), base_url='http://127.0.0.1', client=('192.168.1.5', 43210))
    for path in ('frame', 'status'):
        assert remote.get('/mirror/api/' + path).status_code == 403
    assert remote.post('/mirror/api/restart', json={'revision': 0}).status_code == 403
    client = local_client(control)
    assert client.get('/mirror/api/status').status_code == 200
    assert client.get('/mirror/api/status', headers={'Host': 'attacker.example'}).status_code == 403
    assert client.post('/mirror/api/restart', json={'revision': 0}, headers={'Origin': 'https://attacker.example'}).status_code == 403
    assert client.post('/mirror/api/restart', json={'revision': 0}).status_code == 202
    assert control.snapshot()['pending']


def test_web_entry_and_mobile_entry_remain_available(monkeypatch):
    control = ScanControl()
    monkeypatch.setenv('DERMA_WEB', '1')
    local = local_client(control)
    assert 'REGEN' in local.get('/').text
    remote = TestClient(create_mobile_app(control, 'test-token'))
    assert 'Consulta móvil' in remote.get('/').text
    for path in ('/mirror', '/mirror.css', '/mirror.js'):
        assert local.get(path).status_code == 200
