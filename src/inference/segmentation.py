"""Contratos y cálculo de área de segmentación; no calibra la red clínica."""
from functools import lru_cache
import numpy as np
import cv2


@lru_cache(maxsize=1)
def facial_support() -> np.ndarray:
    """Soporte elíptico canónico existente. No equivale a una máscara anatómica de piel."""
    support = np.zeros((224, 224), dtype=np.uint8)
    cv2.ellipse(support, (112, 112), (int(224 * .36), int(224 * .44)), 0, 0, 360, 1, -1)
    support = support.astype(bool)
    support.setflags(write=False)
    return support


def prepare_rgb(image: np.ndarray) -> np.ndarray:
    """RGB uint8 HWC -> NCHW float32 /255, como en entrenamiento; sin filtros."""
    if not isinstance(image, np.ndarray) or image.shape != (224, 224, 3) or image.dtype != np.uint8:
        raise ValueError('Se requiere una imagen RGB uint8 con forma (224, 224, 3)')
    return np.ascontiguousarray(image.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0


def validate_probability(probability: np.ndarray) -> np.ndarray:
    probability = np.asarray(probability)
    if probability.shape != (224, 224):
        raise ValueError('El modelo debe devolver un mapa de probabilidades de 224x224')
    if not np.isfinite(probability).all() or np.any(probability < 0) or np.any(probability > 1):
        raise ValueError('El modelo devolvió probabilidades inválidas; no se emite un diagnóstico')
    return probability


def segmentation_mask(probability, threshold=.5, *, percentile=None, signal_floor=.01):
    """Recorta al soporte; conserva la selección global por percentil si se solicita.

    El percentil del sistema instalado es estadístico y no está clínicamente
    calibrado. No se ajusta ni se convierte aquí en un umbral de enfermedad.
    """
    probability = validate_probability(probability)
    if percentile is not None:
        if not 0 <= percentile <= 100 or not 0 < signal_floor <= 1:
            raise ValueError('Percentil o suelo de señal fuera de rango')
        cutoff = max(float(np.percentile(probability, percentile)), signal_floor)
        mask = probability >= cutoff
    else:
        if not 0 <= threshold <= 1:
            raise ValueError('Umbral fuera de rango')
        mask = probability > threshold
    return mask & facial_support()


def spot_area_percentage(mask):
    """Numerador y denominador comparten exactamente los mismos píxeles de soporte."""
    mask = np.asarray(mask)
    if mask.shape != (224, 224) or mask.dtype != np.bool_:
        raise ValueError('Se requiere una máscara booleana de 224x224')
    support = facial_support()
    return 100.0 * np.count_nonzero(mask & support) / np.count_nonzero(support)


def localized_spot_percentage(mask, x, y, radius):
    """Área segmentada en un círculo normalizado del mismo tensor facial, sin reescalarlo."""
    mask = np.asarray(mask)
    if mask.shape != (224, 224) or mask.dtype != np.bool_:
        raise ValueError('Se requiere una máscara booleana de 224x224')
    if not all(np.isfinite(v) for v in (x, y, radius)) or not (0 <= x <= 1 and 0 <= y <= 1 and .01 <= radius <= .2):
        raise ValueError('Zona seleccionada fuera de rango')
    yy, xx = np.ogrid[:224, :224]
    disk = (xx / 223 - x) ** 2 + (yy / 223 - y) ** 2 <= radius ** 2
    support = facial_support()
    count = np.count_nonzero(disk)
    if count < 16 or np.count_nonzero(disk & support) < count * .95:
        raise ValueError('Selecciona una zona dentro del área facial evaluable')
    area = disk & support
    return round(100.0 * np.count_nonzero(mask & area) / np.count_nonzero(area), 2)
