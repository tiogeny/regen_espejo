from unittest.mock import Mock
import cv2
import numpy as np
import pytest
from src.inference.region_analysis import CaptureRejected, capture_quality, encode_zone_preview
from src.mobile.server import ScanControl
from tests.test_web_mirror import local_client

REGION = {'x': .5, 'y': .5, 'radius': .08}


def test_exposure_gate_accepts_skin_image_and_rejects_extremes():
    rgb = np.full((224, 224, 3), [150, 110, 85], dtype=np.uint8)
    assert capture_quality(rgb, REGION)['status'] == 'ACEPTABLE'
    for value in (0, 255):
        with pytest.raises(CaptureRejected):
            capture_quality(np.full_like(rgb, value), REGION)
    with pytest.raises(ValueError):
        capture_quality(rgb, {'x': 0, 'y': 0, 'radius': .08})


def test_overlay_marks_only_real_segmented_area():
    rgb = np.full((224, 224, 3), [150, 110, 85], dtype=np.uint8)
    mask = np.zeros((224, 224), dtype=bool)
    mask[110:115, 110:115] = True
    jpeg = encode_zone_preview(rgb, mask, REGION)
    decoded = cv2.cvtColor(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    assert decoded.shape == (224, 224, 3)
    assert decoded[110, 110, 0] > 170
    np.testing.assert_allclose(decoded[30, 30], [150, 110, 85], atol=4)


def complete(control):
    result = {'datos': {'sesion_id': 'analysis-a', 'clinica': {'zona_seleccionada': REGION,
                       'porcentaje_hiperpigmentacion_zona': 0}, 'prescripciones': []}}
    control.publish('DIAGNOSTICADO', 1, result, 'session-a')
    control.publish_analysis_preview(np.full((224, 224, 3), 128, np.uint8),
                                     np.zeros((224, 224), bool), REGION, 'analysis-a')


def test_measured_image_is_bound_to_current_reading_and_removed_on_restart():
    control = ScanControl()
    complete(control)
    client = local_client(control)
    assert client.get('/mirror/api/analysis-frame?analysis_id=wrong').status_code == 409
    response = client.get('/mirror/api/analysis-frame?analysis_id=analysis-a')
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert control.snapshot()['diagnostic']['zone_preview_available']
    assert client.post('/mirror/api/restart', json={'revision': 0}).status_code == 202
    assert client.get('/mirror/api/analysis-frame?analysis_id=analysis-a').status_code == 409
    assert control._analysis_preview is None
    complete(control)
    control.disconnect()
    assert control._analysis_preview is None


def test_new_person_is_applied_by_camera_callback():
    control = ScanControl()
    complete(control)
    client = local_client(control)
    assert client.post('/mirror/api/restart', json={'revision': 0, 'new_person': True}).status_code == 202
    repeat, new_person = Mock(), Mock()
    control.apply_pending(repeat, new_person)
    repeat.assert_not_called()
    new_person.assert_called_once()
    assert control.snapshot()['applied_revision'] == 0
    assert control.snapshot()['revision'] == 1
    assert control.snapshot()['diagnostic'] is None


def test_projection_keeps_unknown_phototype_unavailable():
    from src.mobile.diagnostic import project_diagnostic
    diagnostic = project_diagnostic({'datos': {'clinica': {'fototipo_fitzpatrick': None, 'ita_deg': None},
        'capture_quality': {'status': 'ACEPTABLE', 'luminance': 123.4, 'private': 'omit'}}}, 'test', 1)
    assert 'fototipo_fitzpatrick' not in diagnostic['clinical']
    assert diagnostic['capture_quality'] == {'status': 'ACEPTABLE', 'luminance': 123.4}


def test_camera_rejects_dark_capture_before_running_models():
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    tree = ast.parse(Path('demo_camara.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LiveDermaCameraApp')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'execute_diagnosis')
    scope = {'np': np, 'cv2': cv2, 'capture_quality': capture_quality}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<camera>', 'exec'), scope)
    camera = SimpleNamespace(mobile_control=Mock(), selected_region=REGION, session_ages=[])
    with pytest.raises(CaptureRejected):
        scope['execute_diagnosis'](camera, np.zeros((224, 224, 3), np.uint8))


def test_empty_person_session_gets_new_id_and_clears_old_fields():
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    from datetime import datetime
    tree = ast.parse(Path('demo_camara.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LiveDermaCameraApp')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'start_new_person')
    scope = {'datetime': datetime}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<camera>', 'exec'), scope)
    camera = SimpleNamespace(session_id='old', session_idx=1, session_ages=[],
                             finalize_session_and_restart=Mock(), restart_scan=Mock())
    scope['start_new_person'](camera)
    assert camera.session_id != 'old' and camera.session_idx == 2
    assert camera.session_ages == [] and camera.session_csv_path is None
    assert not camera.patient_sensitive_skin and not camera.patient_is_pregnant
    camera.restart_scan.assert_called_once()
