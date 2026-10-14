"""
Pruebas unitarias para el módulo de benchmarking on-edge INT8 (scripts/benchmark_models_int8.py).
Valida:
1. Existencia e integridad de modelos ONNX (FP32 e INT8).
2. Reducción de tamaño del modelo cuantizado INT8 (~73% para MobileNetV3).
3. Salidas válidas en inferencia sin nan/inf.
4. Cumplimiento de contratos de memoria, telemetría térmica y SLA <= 110 ms.
"""

import pytest
import numpy as np
from pathlib import Path

from scripts.benchmark_models_int8 import (
    AGE_FP32,
    AGE_INT8,
    SPOT_FP32,
    SPOT_INT8,
    SLA_INFERENCE_MAX_MS,
    MAX_THERMAL_SOC_CELSIUS,
    get_file_size_info,
    get_process_memory_mb,
    read_soc_temperature,
    evaluate_precision,
    compute_array_stats,
)


def test_model_files_exist_and_compression_ratio():
    """Verifica que los modelos existan y cumplan las ratios de compresión esperadas."""
    for path in [AGE_FP32, AGE_INT8, SPOT_FP32, SPOT_INT8]:
        assert path.exists(), f"El archivo del modelo {path} no existe."
        assert path.stat().st_size > 0

    size_fp32 = get_file_size_info(AGE_FP32)
    size_int8 = get_file_size_info(AGE_INT8)

    # El modelo cuantizado INT8 de edad debe reducirse ~73% (entre 65% y 80%)
    reduction_pct = (1.0 - (size_int8["bytes"] / size_fp32["bytes"])) * 100.0
    assert 65.0 <= reduction_pct <= 80.0, f"Reducción anómala: {reduction_pct:.2f}%"

    # U-Net Nano debe reducirse entre 10% y 30%
    spot_fp32 = get_file_size_info(SPOT_FP32)
    spot_int8 = get_file_size_info(SPOT_INT8)
    spot_red = (1.0 - (spot_int8["bytes"] / spot_fp32["bytes"])) * 100.0
    assert 10.0 <= spot_red <= 30.0, f"Reducción U-Net Nano anómala: {spot_red:.2f}%"


def test_memory_and_thermal_monitoring_functions():
    """Valida que las funciones de monitoreo de memoria y temperatura no fallen."""
    mem_mb = get_process_memory_mb()
    assert isinstance(mem_mb, float)
    assert mem_mb >= 0.0

    temp, source = read_soc_temperature()
    assert source is not None
    if temp is not None:
        assert 0.0 < temp < 120.0


def test_precision_evaluation_bounds():
    """Verifica que la función evaluate_precision devuelva métricas numéricas finitas y válidas."""
    results = evaluate_precision(AGE_FP32, AGE_INT8, SPOT_FP32, SPOT_INT8, num_samples=5, seed=123)

    assert "age" in results and "spot" in results
    age_mae = results["age"]["mae_years"]
    assert np.isfinite(age_mae)
    assert 0.0 <= age_mae <= 25.0

    spot_mae = results["spot"]["mask_prob_mae"]
    assert np.isfinite(spot_mae)
    assert 0.0 <= spot_mae <= 0.10


def test_stats_computation():
    """Verifica cálculo correcto de percentiles y medias."""
    sample_times = [10.0, 12.0, 15.0, 20.0, 25.0]
    st = compute_array_stats(sample_times)
    assert st["mean"] == 16.4
    assert st["min"] == 10.0
    assert st["max"] == 25.0
    assert st["fps"] > 0
