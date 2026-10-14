"""Señales visibles experimentales de una zona de piel, calculadas solo en RAM.

Los valores representan cobertura de patrones de imagen, no concentraciones de
agua/sebo, pH ni probabilidades clínicas. La luz, el vello y los cosméticos pueden
producir los mismos patrones. No se usan para seleccionar tratamientos.
"""
import cv2
import numpy as np

from src.inference.region_analysis import CaptureRejected, capture_quality, region_support


METHOD = 'visual-appearance-v1'
METRICS = ('shine', 'texture', 'dryness_cues')


def unavailable(status):
    return {'status': status, 'method': METHOD, 'scope': 'selected_region',
            'unit': 'visible_area_percent', **dict.fromkeys(METRICS)}


def analyze_visual_appearance(rgb, region=None):
    """Extrae brillo, microcontraste y fragmentos claros en la captura original.

    La máscara utiliza las coordenadas normalizadas del recorte facial. Solo se
    reduce resolución; ampliar un recorte pequeño no inventa detalle de piel.
    """
    if (not isinstance(rgb, np.ndarray) or rgb.ndim != 3 or rgb.shape[2] != 3
            or rgb.dtype != np.uint8 or min(rgb.shape[:2]) < 1):
        raise ValueError('Se requiere un recorte RGB uint8')
    if region is None:
        return unavailable('SELECCIONA_ZONA')
    try:
        region_support(region)
        capture_quality(cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA), region)
    except CaptureRejected:
        return unavailable('LUZ_INADECUADA')
    except (ValueError, KeyError, TypeError):
        return unavailable('ZONA_INVALIDA')

    height, width = rgb.shape[:2]
    cx, cy = region['x'] * (width - 1), region['y'] * (height - 1)
    radius = region['radius'] * min(width - 1, height - 1)
    if radius * 2 < 32:
        return unavailable('SIN_DETALLE')
    padding = radius * 1.4 + 3
    x0, x1 = max(0, int(cx - padding)), min(width, int(np.ceil(cx + padding)) + 1)
    y0, y1 = max(0, int(cy - padding)), min(height, int(np.ceil(cy + padding)) + 1)
    patch = rgb[y0:y1, x0:x1]
    yy, xx = np.ogrid[y0:y1, x0:x1]
    support = ((xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2).astype(np.uint8)
    if max(patch.shape[:2]) > 160:
        scale = 160 / max(patch.shape[:2])
        size = (round(patch.shape[1] * scale), round(patch.shape[0] * scale))
        patch = cv2.resize(patch, size, interpolation=cv2.INTER_AREA)
        support = cv2.resize(support, size, interpolation=cv2.INTER_NEAREST)
    support = cv2.erode(support, np.ones((3, 3), np.uint8)).astype(bool)
    count = np.count_nonzero(support)
    if count < 600:
        return unavailable('SIN_DETALLE')

    # Brillo sobre RGB original; CLAHE solo participa en el microcontraste.
    gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    saturation = cv2.cvtColor(patch, cv2.COLOR_RGB2HSV)[..., 1].astype(np.float32)
    denoised = cv2.bilateralFilter(gray, 5, 15, 2).astype(np.float32)
    background = cv2.GaussianBlur(denoised, (0, 0), 3)
    median = float(np.median(denoised[support]))
    median_sat = float(np.median(saturation[support]))
    neutral = saturation <= max(15, median_sat * .85)
    highlights = (neutral & (denoised >= median + 20)
                  & (denoised - background >= 8))
    highlights = cv2.morphologyEx(highlights.astype(np.uint8), cv2.MORPH_OPEN,
                                  cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))).astype(bool)

    normalized = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(denoised.astype(np.uint8))
    detail = np.abs(normalized.astype(np.float32)
                    - cv2.GaussianBlur(normalized.astype(np.float32), (0, 0), 1.2))
    texture = (detail >= 6) & ~highlights

    # Candidatos de fragmentos pequeños y claros; no confirma descamación.
    fine_detail = denoised - cv2.GaussianBlur(denoised, (0, 0), 1.2)
    candidates = (neutral & (denoised >= median + 12) & (fine_detail >= 7)
                  & ~highlights & support)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(candidates.astype(np.uint8), connectivity=8)
    fragments = np.zeros_like(support)
    for label in range(1, n):
        _, _, w, h, area = stats[label]
        if 3 <= area <= 48 and max(w, h) <= 4 * min(w, h):
            fragments |= labels == label

    def coverage(mask):
        return float(round(100 * np.count_nonzero(mask & support) / count, 1))

    return {'status': 'EXPERIMENTAL', 'method': METHOD, 'scope': 'selected_region',
            'unit': 'visible_area_percent', 'shine': coverage(highlights),
            'texture': coverage(texture), 'dryness_cues': coverage(fragments)}
