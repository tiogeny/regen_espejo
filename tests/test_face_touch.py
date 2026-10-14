import numpy as np
import pytest
from src.inference.face_touch import FaceTouchSelector, FaceAnchor, EXCLUDED, skin_point
from src.inference.segmentation import localized_spot_percentage


@pytest.fixture
def face():
    angles = np.linspace(0, 2*np.pi, 26, endpoint=False)
    points = np.array([(320 + 135*r*np.cos(a), 260 + 170*r*np.sin(a)) for r in np.linspace(.1, 1, 18) for a in angles])
    for ids, center in zip(EXCLUDED, [(280, 215), (360, 215), (320, 340)]):
        for i, index in enumerate(ids):
            a = i * 2*np.pi / len(ids)
            points[index] = [center[0] + 10*np.cos(a), center[1] + 5*np.sin(a)]
    points[4] = [320, 260]
    return points


@pytest.fixture
def hand():
    hand = np.tile([470., 460.], (21, 1))
    hand[0], hand[9] = [450, 450], [430, 380]
    hand[5], hand[6], hand[8] = [400, 360], [385, 325], [380, 280]
    return hand


def select(selector, face, hand):
    for t in np.arange(0, 1.01, .1):
        assert not selector.update(face, [hand], t)
    assert selector.state == 'RETIRA_MANO'


def test_requires_hold_release_and_stability(face, hand):
    selector = FaceTouchSelector()
    select(selector, face, hand)
    for t in np.arange(1.1, 2.1, .1):
        assert not selector.update(face, [hand], t)
    outcomes = [selector.update(face, [], t) for t in np.arange(2.1, 4.5, .1)]
    assert any(outcomes)
    assert selector.state == 'LISTO'


def test_face_loss_and_long_gap_clear_selection(face, hand):
    selector = FaceTouchSelector()
    select(selector, face, hand)
    assert not selector.update(None, [], 1.1)
    assert selector.anchor is None
    select(selector, face, hand)
    assert not selector.update(face, [], 3)
    assert selector.anchor is None


def test_hand_return_restarts_stability(face, hand):
    selector = FaceTouchSelector()
    select(selector, face, hand)
    for t in np.arange(1.1, 2.3, .1):
        assert not selector.update(face, [], t)
    assert selector.state == 'ESTABILIZANDO'
    assert not selector.update(face, [hand], 2.3)
    assert selector.state == 'RETIRA_MANO'
    assert selector.stable_since is None


def test_anchor_tracks_face_translation(face):
    anchor = FaceAnchor.at(face, [380, 280])
    np.testing.assert_allclose(anchor.point(face + [30, 15]), [410, 295], atol=.001)


def test_reject_eyes_lips_background_and_two_hands(face, hand):
    assert not skin_point(face, [280, 215])
    assert not skin_point(face, [320, 340])
    assert not skin_point(face, [20, 20])
    selector = FaceTouchSelector()
    assert not selector.update(face, [hand, hand], 0)
    assert selector.state == 'ESPERANDO_ZONA'


def test_local_percentage_uses_local_denominator():
    mask = np.zeros((224, 224), dtype=bool)
    mask[95:130, 95:130] = True
    assert localized_spot_percentage(mask, .5, .5, .05) == 100
    assert localized_spot_percentage(mask, .7, .5, .04) == 0
    with pytest.raises(ValueError):
        localized_spot_percentage(mask, 0, 0, .05)
    with pytest.raises(ValueError):
        localized_spot_percentage(mask, np.nan, .5, .05)


def test_api_keeps_global_and_local_measurements_separate(client, auth_headers, create_shm_buffer, monkeypatch):
    from src.api.app import inference_engine
    monkeypatch.setattr(inference_engine, 'run_inference', lambda tensor: (30, 7.0))
    monkeypatch.setattr(inference_engine, 'get_segmentation_mask', lambda tensor: np.ones((224,224), dtype=bool))
    name, _ = create_shm_buffer()
    response = client.post('/api/v1/diagnostics/analyze', headers=auth_headers, json={
        'shm_descriptor': name, 'telemetry': {'stability_duration_ms': 1600, 'thermal_soc_celsius': 40},
        'selected_region': {'x': .5, 'y': .5, 'radius': .05}})
    assert response.status_code == 201
    data = response.json()['datos']
    assert data['clinica']['porcentaje_hiperpigmentacion'] == 7.0
    assert data['clinica']['porcentaje_hiperpigmentacion_zona'] == 100.0
    assert data['prescripciones'] == []
    assert data['orientacion']['estado'] == 'REVISION_ZONA'


def test_api_rejects_zone_outside_support(client, auth_headers, create_shm_buffer, monkeypatch):
    from src.api.app import inference_engine
    monkeypatch.setattr(inference_engine, 'run_inference', lambda tensor: (30, 7.0))
    monkeypatch.setattr(inference_engine, 'get_segmentation_mask', lambda tensor: np.ones((224,224), dtype=bool))
    name, _ = create_shm_buffer()
    response = client.post('/api/v1/diagnostics/analyze', headers=auth_headers, json={
        'shm_descriptor': name, 'telemetry': {'stability_duration_ms': 1600, 'thermal_soc_celsius': 40},
        'selected_region': {'x': .01, 'y': .01, 'radius': .05}})
    assert response.status_code == 422
    assert response.json()['error_code'] == 'INVALID_REGION'


def test_default_selects_in_half_a_second_despite_small_jitter(face, hand):
    selector = FaceTouchSelector()
    for t in np.arange(0, .51, 1 / 15):
        moving = hand.copy()
        moving[8, 0] += 5 if int(round(t * 15)) % 2 else -5
        assert not selector.update(face, [moving], t)
    assert selector.state == 'RETIRA_MANO'
    assert selector.anchor is not None


def test_moving_to_another_zone_restarts_hold(face, hand):
    selector = FaceTouchSelector()
    for t in (0, .1, .2):
        selector.update(face, [hand], t)
    moved = hand.copy()
    moved[8, 0] -= 20
    selector.update(face, [moved], .3)
    assert selector.progress == 0
    assert selector.anchor is None


def test_shorter_hold_still_requires_release_and_full_stability(face, hand):
    selector = FaceTouchSelector()
    for t in np.arange(0, .61, .1):
        assert not selector.update(face, [hand], t)
    assert selector.state == 'RETIRA_MANO'
    for t in np.arange(.7, 1.01, .1):
        assert not selector.update(face, [hand], t)
    for t in np.arange(1.1, 2.91, .1):
        assert not selector.update(face, [], t)
    assert selector.update(face, [], 3.1)
