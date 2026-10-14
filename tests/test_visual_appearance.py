"""Contratos y señales sintéticas; no valida correlación clínica con sequedad."""
import cv2
import numpy as np
import pytest
from src.inference.visual_appearance import analyze_visual_appearance
from src.mobile.diagnostic import project_diagnostic
from src.mobile.server import ScanControl

REGION = {'x': .5, 'y': .5, 'radius': .1}


def image():
    return np.full((512, 512, 3), [150, 110, 85], np.uint8)


def test_no_fake_readings_without_valid_zone_resolution_or_light():
    rgb = image()
    for img, region, status in (
        (rgb, None, 'SELECCIONA_ZONA'),
        (rgb, {'x': 0, 'y': 0, 'radius': .1}, 'ZONA_INVALIDA'),
        (rgb[:224, :224], {**REGION, 'radius': .04}, 'SIN_DETALLE'),
        (np.zeros_like(rgb), REGION, 'LUZ_INADECUADA'),
        (np.full_like(rgb, 255), REGION, 'LUZ_INADECUADA'),
    ):
        result = analyze_visual_appearance(img, region)
        assert result['status'] == status
        assert all(result[key] is None for key in ('shine', 'texture', 'dryness_cues'))
    with pytest.raises(ValueError):
        analyze_visual_appearance(np.zeros((100, 100)), REGION)


def test_flat_capture_does_not_invent_signals_and_input_is_unchanged():
    rgb = image()
    before = rgb.copy()
    result = analyze_visual_appearance(rgb, REGION)
    assert result['status'] == 'EXPERIMENTAL'
    assert [result[key] for key in ('shine', 'texture', 'dryness_cues')] == [0, 0, 0]
    np.testing.assert_array_equal(rgb, before)


def test_signals_distinguish_highlights_and_fine_fragments():
    rgb = image()
    cv2.circle(rgb, (256, 256), 10, (240, 240, 230), -1)
    result = analyze_visual_appearance(rgb, REGION)
    assert result['shine'] > 0
    assert result['dryness_cues'] == 0  # Reflejo amplio no es fragmento.
    fragments = image()
    for y in range(223, 290, 8):
        for x in range(223, 290, 8):
            fragments[y:y+3, x:x+2] = [225, 222, 215]
    result = analyze_visual_appearance(fragments, REGION)
    assert result['dryness_cues'] > 0 and result['texture'] > 0
    assert result['shine'] == 0
    assert all(isinstance(result[key], float) and 0 <= result[key] <= 100
               for key in ('shine', 'texture', 'dryness_cues'))


def test_far_outside_selected_zone_does_not_change_results():
    rgb = image()
    reference = analyze_visual_appearance(rgb, REGION)
    rgb[:100, :100] = 255
    assert analyze_visual_appearance(rgb, REGION) == reference


def test_projection_sanitizes_signals_and_restart_removes_them():
    appearance = analyze_visual_appearance(image(), REGION)
    result = {'datos': {'sesion_id': 'appearance-1', 'clinica': {},
                       'visual_appearance': {**appearance, 'shine': np.nan,
                                             'texture': True, 'dryness_cues': 101,
                                             'image': 'private'}}}
    projected = project_diagnostic(result, 'session', 1)['visual_appearance']
    assert all(projected[key] is None for key in ('shine', 'texture', 'dryness_cues'))
    assert 'image' not in projected
    control = ScanControl()
    result['datos']['visual_appearance'] = appearance
    control.publish('DIAGNOSTICADO', 1, result, 'session')
    assert control.snapshot()['diagnostic']['visual_appearance'] == appearance
    control.request_restart(0)
    assert control.snapshot()['diagnostic'] is None
    control.apply_pending(lambda: None)
    assert control.snapshot()['diagnostic'] is None


def test_unavailable_reading_cannot_expose_stale_values():
    result = {'datos': {'clinica': {}, 'visual_appearance': {
        'method': 'visual-appearance-v1', 'status': 'SIN_DETALLE',
        'shine': 70, 'texture': 80, 'dryness_cues': 90}}}
    projected = project_diagnostic(result, 'session', 1)['visual_appearance']
    assert all(projected[key] is None for key in ('shine', 'texture', 'dryness_cues'))
