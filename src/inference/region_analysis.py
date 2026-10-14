"""Captura y visualización de una zona: RGB y máscaras reales, solo en RAM."""
import cv2
import numpy as np
from src.inference.segmentation import facial_support, localized_spot_percentage


class CaptureRejected(ValueError):
    """La captura no contiene una señal visual suficiente para analizar."""


def region_support(region=None):
    if region is None:
        return facial_support()
    # Compartir exactamente el soporte/coordenadas del cálculo de área.
    localized_spot_percentage(np.zeros((224, 224), dtype=bool), **region)
    yy, xx = np.ogrid[:224, :224]
    return ((xx / 223 - region['x']) ** 2 + (yy / 223 - region['y']) ** 2
            <= region['radius'] ** 2) & facial_support()


def capture_quality(rgb, region=None):
    if not isinstance(rgb, np.ndarray) or rgb.shape != (224, 224, 3) or rgb.dtype != np.uint8:
        raise ValueError('Se requiere RGB uint8 de 224x224')
    support = region_support(region)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)[support]
    mean = float(np.mean(gray))
    dark = float(np.mean(gray <= 3))
    clipped = float(np.mean(gray >= 252))
    # Solo extremos de exposición; no se infiere hidratación, pH ni sebo.
    # Estos límites son controles técnicos, no umbrales de enfermedad.
    if mean < 20 or dark > .35:
        raise CaptureRejected('Hay muy poca luz en la zona. Ilumina el rostro y vuelve a señalar.')
    if mean > 235 or clipped > .25:
        raise CaptureRejected('La zona está sobreexpuesta. Reduce la luz directa y vuelve a señalar.')
    return {'status': 'ACEPTABLE', 'luminance': round(mean, 1),
            'clipped_percent': round(clipped * 100, 1)}


def encode_zone_preview(rgb, mask, region):
    """JPEG de la zona medida; dorado únicamente donde la máscara detecta área."""
    support = region_support(region)
    localized_spot_percentage(mask, **region)  # valida forma/dtype de máscara
    capture_quality(rgb, region)
    overlay = rgb.copy()
    selected = np.asarray(mask) & support
    gold = np.array([238, 190, 91], dtype=np.float32)
    overlay[selected] = np.round(.55 * overlay[selected] + .45 * gold).astype(np.uint8)
    ys, xs = np.where(support)
    # La región válida está dentro del soporte facial, por lo que no hay padding.
    image = overlay[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    image = cv2.resize(image, (224, 224), interpolation=cv2.INTER_LINEAR)
    ok, encoded = cv2.imencode('.jpg', cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
                               [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError('No se pudo preparar la ampliación de la zona')
    return encoded.tobytes()
