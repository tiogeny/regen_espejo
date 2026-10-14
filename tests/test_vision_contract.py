from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
from src.inference.segmentation import facial_support, prepare_rgb, segmentation_mask, spot_area_percentage
from src.inference.pipeline import InferenceEngine


def test_background_is_not_measured_as_face():
    support = facial_support()
    probability = np.where(support, .001, .99).astype(np.float32)
    mask = segmentation_mask(probability, percentile=98, signal_floor=.01)
    assert not mask.any()
    assert spot_area_percentage(mask) == 0


def test_area_is_bounded_and_matches_actual_support():
    assert spot_area_percentage(np.ones((224, 224), dtype=bool)) == 100
    mask = np.zeros((224, 224), dtype=bool)
    mask[100:110, 100:110] = True
    assert spot_area_percentage(mask) == pytest.approx(10000 / facial_support().sum())
    assert not facial_support().flags.writeable


def test_empty_prediction_is_not_replaced_with_dark_edge_heuristic():
    probability = np.zeros((224, 224), dtype=np.float32)
    assert not segmentation_mask(probability).any()
    assert not segmentation_mask(probability, percentile=98).any()
    probability[100:110, 100:110] = .9
    assert segmentation_mask(probability).sum() == 100


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -.1, 1.1])
def test_invalid_probability_rejected(value):
    probability = np.zeros((224, 224), dtype=np.float32)
    probability[112,112] = value
    with pytest.raises(ValueError):
        segmentation_mask(probability)


def test_rgb_preprocessing_preserves_training_pixels():
    rgb = np.random.default_rng(7).integers(0,256,(224,224,3),dtype=np.uint8)
    prepared = prepare_rgb(rgb)
    assert prepared.dtype == np.float32 and prepared.flags.c_contiguous
    np.testing.assert_array_equal(prepared[0].transpose(1,2,0), rgb.astype(np.float32)/255)
    with pytest.raises(ValueError):
        prepare_rgb(rgb.astype(np.float32))
    with pytest.raises(ValueError):
        segmentation_mask(np.zeros((112,112)))


def engine_without_loading():
    return InferenceEngine.__new__(InferenceEngine)


def test_missing_models_do_not_fabricate_age_or_spots():
    engine = engine_without_loading()
    engine._age_session = None
    engine._spot_session = None
    with pytest.raises(RuntimeError):
        engine.run_inference(np.zeros((224,224,3),dtype=np.uint8))
    with pytest.raises(RuntimeError):
        engine.get_segmentation_mask(np.zeros((224,224,3),dtype=np.uint8))


def test_inference_uses_raw_rgb_and_exact_face_area(monkeypatch):
    engine = engine_without_loading()
    age_session = Mock()
    age_session.get_inputs.return_value = [SimpleNamespace(name='input')]
    age_session.run.return_value = [np.array([[40]], dtype=np.float32)]
    spot_session = Mock()
    spot_session.get_inputs.return_value = [SimpleNamespace(name='input')]
    spot_session.run.return_value = [np.ones((1,1,224,224),dtype=np.float32)]
    engine._age_session = age_session
    engine._spot_session = spot_session
    monkeypatch.setattr('src.config.get_age_offset',lambda:0)
    rgb=np.random.default_rng(8).integers(0,256,(224,224,3),dtype=np.uint8)
    age,pct=engine.run_inference(rgb)
    assert age == 40 and pct == 100.0
    np.testing.assert_array_equal(age_session.run.call_args.args[1]['input'], prepare_rgb(rgb))


def test_api_does_not_save_diagnostic_when_model_unavailable(client, auth_headers, create_shm_buffer, monkeypatch):
    name, _ = create_shm_buffer()
    def unavailable(tensor):
        raise RuntimeError('Model not loaded')
    monkeypatch.setattr('src.api.app.inference_engine.run_inference', unavailable)
    response = client.post('/api/v1/diagnostics/analyze', headers=auth_headers, json={
        'shm_descriptor': name,
        'telemetry': {'stability_duration_ms': 1600, 'thermal_soc_celsius': 40.0}})
    assert response.status_code == 503
    assert response.json()['error_code'] == 'INFERENCE_UNAVAILABLE'
    assert 'datos' not in response.json()
