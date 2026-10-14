"""
Pipeline de Inferencia On-Edge para Diagnóstico Dermatoscópico Facial (SPEC-001).

Modelos:
- Estimador de Edad Biológica (MobileNetV3): INT8 on-edge con fallback a FP32.
- Segmentación de Lesiones Pigmentarias (U-Net Nano): INT8 on-edge con fallback a FP32.
- Calibración espectral adaptativa y análisis morfológico facial.
"""

import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import numpy as np
from src.config import MODELS_DIR
from src.inference.segmentation import prepare_rgb, validate_probability, segmentation_mask, spot_area_percentage

# Nombres canónicos de modelos cuantizados e inferencia on-edge
MOBILENET_AGE_INT8 = "mobilenetv3_age_int8.onnx"
UNET_SPOT_INT8 = "unet_nano_spots_int8.onnx"

AGE_FP32_DEFAULT = "age_estimator.onnx"
AGE_FP32_ALT = "age_estimator_fp32.onnx"

SPOT_FP32_DEFAULT = "spot_segmentation.onnx"
SPOT_FP32_ALT = "spot_segmentation_fp32.onnx"


def should_use_int8() -> bool:
    """
    Determina si el entorno actual requiere la selección de modelos cuantizados INT8:
    1. Si la variable de entorno `DERMA_USE_INT8` está activa ('1', 'true', 'yes').
    2. Si se detecta que el sistema corre sobre una Raspberry Pi (ARM/aarch64).
    """
    env_val = os.getenv("DERMA_USE_INT8", "").strip().lower()
    if env_val in ("1", "true", "yes"):
        return True

    try:
        from src.inference.hardware_detect import is_raspberry_pi
        return is_raspberry_pi()
    except Exception:
        return False


def resolve_model_path(
    model_type: str,
    models_dir: Path = MODELS_DIR,
    prefer_int8: Optional[bool] = None,
) -> Tuple[Path, str]:
    """
    Selecciona automáticamente la ruta del modelo ONNX y su nivel de precisión.

    Estrategia de selección:
    - Si se solicita INT8 (via prefer_int8 o should_use_int8()):
      - Para 'age': busca `mobilenetv3_age_int8.onnx`.
      - Para 'spot': busca `unet_nano_spots_int8.onnx`.
      - Si el archivo INT8 existe, lo selecciona ('INT8').
      - Si NO existe, aplica fallback transparente al modelo FP32 correspondiente ('FP32_FALLBACK').
    - Si no se solicita INT8:
      - Selecciona el modelo FP32 correspondiente ('FP32').

    Args:
        model_type: Tipo de modelo ("age" o "spot").
        models_dir: Directorio base donde residen los modelos.
        prefer_int8: Forzar INT8 (True), forzar FP32 (False) o autodetectar (None).

    Returns:
        Tuple[Path, str]: (ruta_al_modelo, precision_label).
    """
    use_int8 = prefer_int8 if prefer_int8 is not None else should_use_int8()

    if model_type.lower() in ("age", "age_estimator"):
        int8_candidate = models_dir / MOBILENET_AGE_INT8
        if not int8_candidate.exists():
            alt = models_dir / "age_estimator_int8.onnx"
            if alt.exists():
                int8_candidate = alt

        fp32_candidate = models_dir / AGE_FP32_DEFAULT
        if not fp32_candidate.exists():
            alt = models_dir / AGE_FP32_ALT
            if alt.exists():
                fp32_candidate = alt

        if use_int8:
            if int8_candidate.exists():
                return int8_candidate, "INT8"
            return fp32_candidate, "FP32_FALLBACK"
        return fp32_candidate, "FP32"

    elif model_type.lower() in ("spot", "spot_segmentation"):
        int8_candidate = models_dir / UNET_SPOT_INT8
        if not int8_candidate.exists():
            alt = models_dir / "spot_segmentation_int8.onnx"
            if alt.exists():
                int8_candidate = alt

        fp32_candidate = models_dir / SPOT_FP32_DEFAULT
        if not fp32_candidate.exists():
            alt = models_dir / SPOT_FP32_ALT
            if alt.exists():
                fp32_candidate = alt

        if use_int8:
            if int8_candidate.exists():
                return int8_candidate, "INT8"
            return fp32_candidate, "FP32_FALLBACK"
        return fp32_candidate, "FP32"

    raise ValueError(f"Tipo de modelo no reconocido: '{model_type}'. Valores esperados: 'age', 'spot'")


# Rutas de modelos resueltas por defecto (compatibilidad hacia atrás)
AGE_MODEL_PATH, _ = resolve_model_path("age")
SPOT_MODEL_PATH, _ = resolve_model_path("spot")


class InferenceEngine:
    """
    Motor de Inferencia Neuronal On-Edge con autoselector de precisión
    (INT8 acelerado / FP32 fallback transparente) y filtrado espectral morfológico.
    """

    def __init__(
        self,
        age_model_path: Optional[Path] = None,
        spot_model_path: Optional[Path] = None,
        models_dir: Path = MODELS_DIR,
        prefer_int8: Optional[bool] = None,
    ):
        if age_model_path is None:
            self.age_model_path, self.age_precision = resolve_model_path(
                "age", models_dir=models_dir, prefer_int8=prefer_int8
            )
        else:
            self.age_model_path = Path(age_model_path)
            self.age_precision = "CUSTOM"

        if spot_model_path is None:
            self.spot_model_path, self.spot_precision = resolve_model_path(
                "spot", models_dir=models_dir, prefer_int8=prefer_int8
            )
        else:
            self.spot_model_path = Path(spot_model_path)
            self.spot_precision = "CUSTOM"

        self._age_session = None
        self._spot_session = None
        self._load_sessions_if_available()

    @property
    def is_using_int8(self) -> bool:
        """Indica si ambos modelos activos son cuantizados INT8."""
        return self.age_precision == "INT8" and self.spot_precision == "INT8"

    @property
    def model_status(self) -> Dict[str, Any]:
        """Retorna el estado de los modelos cargados en el motor."""
        return {
            "age": {
                "path": str(self.age_model_path),
                "precision": self.age_precision,
                "loaded": self._age_session is not None,
            },
            "spot": {
                "path": str(self.spot_model_path),
                "precision": self.spot_precision,
                "loaded": self._spot_session is not None,
            },
        }

    def _load_sessions_if_available(self):
        try:
            import onnxruntime as ort
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = 4
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            if self.age_model_path and self.age_model_path.exists():
                self._age_session = ort.InferenceSession(str(self.age_model_path), sess_options)
            if self.spot_model_path and self.spot_model_path.exists():
                self._spot_session = ort.InferenceSession(str(self.spot_model_path), sess_options)
        except Exception:
            pass

    def run_inference(
        self,
        image_tensor: np.ndarray,
        mock_age: Optional[int] = None,
        mock_spot_pct: Optional[float] = None,
    ) -> Tuple[int, float]:
        """
        Ejecuta la inferencia sobre el tensor [224, 224, 3] en memoria volátil.
        Retorna (edad_biologica_estimada, porcentaje_hiperpigmentacion).
        """
        # Si se suministran mocks explícitos (utilizados en suites de pruebas unitarias)
        if mock_age is not None and mock_spot_pct is not None:
            return mock_age, mock_spot_pct

        input_chw = prepare_rgb(image_tensor)
        if self._age_session is None or self._spot_session is None:
            raise RuntimeError("Modelos ONNX no disponibles; no se puede emitir un diagnóstico")

        if self._age_session is not None:
            input_name = self._age_session.get_inputs()[0].name
            outputs = self._age_session.run(None, {input_name: input_chw})
            raw_age = float(np.squeeze(outputs[0]))
            if not np.isfinite(raw_age):
                raise RuntimeError('El modelo de edad devolvió un valor inválido')

            # Calibración clínica de sesgo óptico/sensor de cámara
            from src.config import get_age_offset
            offset = get_age_offset()
            calibrated_age = raw_age + offset
            estimated_age = int(round(calibrated_age))
            estimated_age = max(15, min(90, estimated_age))

        elif mock_age is not None:
            estimated_age = mock_age

        if self._spot_session is not None:
            mask = self.get_segmentation_mask(image_tensor)
            spot_percentage = spot_area_percentage(mask)
        elif mock_spot_pct is not None:
            spot_percentage = mock_spot_pct

        return estimated_age, round(spot_percentage, 2)

    def get_spot_probability(self, image_tensor: np.ndarray) -> np.ndarray:
        input_chw = prepare_rgb(image_tensor)
        if self._spot_session is None:
            raise RuntimeError("Modelo ONNX de segmentación no disponible")
        input_name = self._spot_session.get_inputs()[0].name
        outputs = self._spot_session.run(None, {input_name: input_chw})
        return validate_probability(np.squeeze(outputs[0]))

    def get_segmentation_mask(self, image_tensor: np.ndarray) -> np.ndarray:
        """Máscara del modelo dentro del soporte facial, sin sustitución heurística."""
        return segmentation_mask(self.get_spot_probability(image_tensor))


# Instancia singleton del motor de inferencia
inference_engine = InferenceEngine()
