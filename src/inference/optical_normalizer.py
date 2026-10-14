"""
Módulo de Normalización Óptica y Detección de Obstáculos Peri-orbitales.

Implementa los procedimientos clínicos y de visión artificial especificados en:
.agents/skills/cv-optical-normalizer/SKILL.md:
1. Normalización de iluminación mediante CLAHE adaptativo en el espacio de color LAB
   (exclusivamente sobre el canal L para preservar tonos cromáticos y biológicos intactos).
2. Desacoplo de ruido de sensor webcam mediante filtrado bilateral edge-preserving
   (preserva geometría de ojos, nariz, labios y contornos dermatológicos).
3. Detección de accesorios (gafas) y reflejos especulares (glare) en la zona peri-orbital
   (evaluando gradientes ópticos, densidad de bordes y profundidad z en nodos MediaPipe).
"""

from typing import Optional, Dict, Any, Tuple
import numpy as np
import cv2

# Parámetros estándar según SKILL.md y especificación clínica
DEFAULT_CLAHE_CLIP_LIMIT = 2.0
DEFAULT_CLAHE_GRID_SIZE = (8, 8)
DEFAULT_BILATERAL_D = 7
DEFAULT_BILATERAL_SIGMA_COLOR = 45.0
DEFAULT_BILATERAL_SIGMA_SPACE = 45.0

# Nodos peri-orbitales clave de MediaPipe Face Mesh:
# 33: canto lateral derecho, 133: canto medial derecho
# 362: canto medial izquierdo, 263: canto lateral izquierdo
MEDIAPIPE_PERI_ORBITAL_NODES = (33, 133, 362, 263)

# Umbrales heurísticos para detección de monturas y reflejos
DEFAULT_EDGE_THRESHOLD = 0.055
DEFAULT_GRADIENT_THRESHOLD = 70.0
DEFAULT_GLARE_THRESHOLD = 0.008
DEFAULT_GLARE_INTENSITY = 240

# Umbrales estándar para control de calidad de iluminación (semáforo lux/luma gate)
# En escala CIELAB [0.0, 100.0]:
# - L < 30.0: Iluminación insuficiente (LUZ_BAJA / subexpuesta)
# - 30.0 <= L <= 85.0: Iluminación adecuada (OPTIMA / semáforo VERDE)
# - L > 85.0: Iluminación excesiva o deslumbramiento (BRILLO_EXCESIVO / sobreexpuesta)
DEFAULT_MIN_LUMA = 30.0
DEFAULT_MAX_LUMA = 85.0


def _validate_and_prepare_image(img_rgb: np.ndarray) -> np.ndarray:
    """Valida y prepara el tensor de imagen RGB para procesamiento."""
    if not isinstance(img_rgb, np.ndarray):
        raise TypeError(f"img_rgb debe ser un numpy.ndarray, recibido {type(img_rgb).__name__}")

    if img_rgb.ndim != 3 or img_rgb.shape[2] != 3:
        raise ValueError(
            f"Se esperaba una imagen RGB con forma (H, W, 3), recibido shape={img_rgb.shape}"
        )

    h, w = img_rgb.shape[:2]
    if h == 0 or w == 0:
        raise ValueError("Las dimensiones de la imagen deben ser mayores que 0")

    # Conversión a uint8 si es punto flotante
    if np.issubdtype(img_rgb.dtype, np.floating):
        if np.any(np.isnan(img_rgb)) or np.any(np.isinf(img_rgb)):
            raise ValueError("img_rgb contiene valores NaN o Infinitos.")
        if img_rgb.max() <= 1.0:
            return np.clip(img_rgb * 255.0, 0, 255).astype(np.uint8)
        return np.clip(img_rgb, 0, 255).astype(np.uint8)

    if img_rgb.dtype != np.uint8:
        return np.clip(img_rgb, 0, 255).astype(np.uint8)

    return img_rgb.copy()


def normalize_optical_conditions(
    img_rgb: np.ndarray,
    clip_limit: float = DEFAULT_CLAHE_CLIP_LIMIT,
    tile_grid_size: Tuple[int, int] = DEFAULT_CLAHE_GRID_SIZE,
    bilateral_d: int = DEFAULT_BILATERAL_D,
    sigma_color: float = DEFAULT_BILATERAL_SIGMA_COLOR,
    sigma_space: float = DEFAULT_BILATERAL_SIGMA_SPACE,
) -> np.ndarray:
    """
    Normaliza condiciones ópticas e iluminación para inferencia dermatológica.

    Pasos:
    1. Convierte la imagen RGB al espacio LAB.
    2. Aplica CLAHE adaptativo estrictamente sobre el canal L (luminancia),
       garantizando que los canales cromáticos A y B permanezcan inalterados
       (preservación rigurosa de melanina, eritema y tono biológico de la piel).
    3. Recombina canales y convierte de regreso a RGB.
    4. Aplica filtrado bilateral edge-preserving (d=7, sigmaColor=45, sigmaSpace=45)
       para atenuar ruido de alta frecuencia del sensor ISO sin difuminar
       bordes anatómicos ni lesiones dermatológicas.

    Parámetros:
    - img_rgb: Tensor de entrada (H, W, 3) en formato RGB.
    - clip_limit: Umbral de contraste para CLAHE (default: 2.0).
    - tile_grid_size: Tamaño de grilla para ecualización local (default: (8, 8)).
    - bilateral_d: Diámetro de vecindad para filtrado bilateral (default: 7).
    - sigma_color: Varianza en espacio de color para filtro bilateral (default: 45.0).
    - sigma_space: Varianza en espacio geométrico para filtro bilateral (default: 45.0).

    Retorna:
    - np.ndarray de forma (H, W, 3) y dtype uint8 normalizado.
    """
    img_u8 = _validate_and_prepare_image(img_rgb)

    # 1. Conversión a espacio LAB
    lab = cv2.cvtColor(img_u8, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    # 2. CLAHE estrictamente sobre canal L
    clahe = cv2.createCLAHE(
        clipLimit=float(clip_limit),
        tileGridSize=(int(tile_grid_size[0]), int(tile_grid_size[1])),
    )
    l_enhanced = clahe.apply(l_channel)

    # 3. Fusión manteniendo canales A y B inalterados y reconversión a RGB
    lab_enhanced = cv2.merge((l_enhanced, a_channel, b_channel))
    rgb_clahe = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)

    # 4. Filtrado bilateral edge-preserving
    normalized_rgb = cv2.bilateralFilter(
        rgb_clahe,
        d=int(bilateral_d),
        sigmaColor=float(sigma_color),
        sigmaSpace=float(sigma_space),
    )

    return normalized_rgb


def detect_glasses_or_glare(
    img_rgb: np.ndarray,
    face_landmarks: Optional[np.ndarray] = None,
    edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
    gradient_threshold: float = DEFAULT_GRADIENT_THRESHOLD,
    glare_threshold: float = DEFAULT_GLARE_THRESHOLD,
    glare_intensity_threshold: int = DEFAULT_GLARE_INTENSITY,
) -> Dict[str, Any]:
    """
    Evalúa gradientes ópticos y saturación luminosa en zonas peri-orbitales para
    detectar potencial uso de gafas (monturas/bordes) o destellos/reflejos (glare),
    emitiendo recomendaciones clínicas pertinentes.

    Parámetros:
    - img_rgb: Tensor de entrada RGB (H, W, 3).
    - face_landmarks: Opcional. Coordenadas de puntos de referencia faciales.
      Puede ser:
      * Tensor (N, 2) o (N, 3) de Face Mesh con N >= 363 (utiliza nodos 33, 133, 362, 263).
      * Tensor (4, 2) o (4, 3) conteniendo directamente los 4 nodos peri-orbitales.
      * Si es None, se utiliza la ROI peri-orbital antropométrica canónica.
    - edge_threshold: Fracción mínima de píxeles con bordes Canny para clasificar montura (default: 0.055).
    - gradient_threshold: Magnitud promedio de gradiente Sobel para clasificar montura (default: 70.0).
    - glare_threshold: Fracción mínima de píxeles saturados para clasificar reflejo (default: 0.008).
    - glare_intensity_threshold: Nivel de gris para considerar saturación especular (default: 240).

    Retorna:
    - dict con:
      * has_glasses_or_glare: bool
      * glasses_detected: bool
      * glare_detected: bool
      * confidence: float [0.0, 1.0]
      * clinical_hint: str con recomendación clínica
      * metrics: dict con mediciones cuantitativas (edge_density, mean_gradient, glare_ratio, peri_orbital_roi, z_depth)
    """
    img_u8 = _validate_and_prepare_image(img_rgb)
    h, w = img_u8.shape[:2]

    z_metrics: Optional[Dict[str, float]] = None

    # Delimitación de ROI peri-orbital
    if face_landmarks is not None:
        lm_arr = np.asarray(face_landmarks, dtype=np.float32)
        if lm_arr.ndim != 2 or lm_arr.shape[1] not in (2, 3):
            raise ValueError(
                f"face_landmarks debe tener dimensión 2D con forma (N, 2) o (N, 3), recibido {lm_arr.shape}"
            )

        if len(lm_arr) >= 363:
            pts = lm_arr[list(MEDIAPIPE_PERI_ORBITAL_NODES)]
        elif len(lm_arr) == 4:
            pts = lm_arr
        else:
            raise ValueError(
                f"face_landmarks debe tener al menos 363 puntos de Face Mesh o exactamente 4 nodos peri-orbitales, recibido {len(lm_arr)}"
            )

        # Conversión de coordenadas normalizadas a píxeles si están en [0.0, 1.05]
        pts_px = pts.copy()
        if pts[:, :2].max() <= 1.05 and pts[:, :2].min() >= 0.0:
            pts_px[:, 0] = pts[:, 0] * w
            pts_px[:, 1] = pts[:, 1] * h

        min_x = float(np.min(pts_px[:, 0]))
        max_x = float(np.max(pts_px[:, 0]))
        min_y = float(np.min(pts_px[:, 1]))
        max_y = float(np.max(pts_px[:, 1]))

        span_x = max(10.0, max_x - min_x)
        pad_x = int(span_x * 0.20)
        pad_y = int(span_x * 0.35)

        x1 = max(0, int(min_x - pad_x))
        x2 = min(w, int(max_x + pad_x))
        y1 = max(0, int(min_y - pad_y))
        y2 = min(h, int(max_y + pad_y))

        # Métricas de profundidad Z si están disponibles
        if pts.shape[1] >= 3:
            z_vals = pts[:, 2]
            z_metrics = {
                "mean": round(float(np.mean(z_vals)), 5),
                "variance": round(float(np.var(z_vals)), 5),
                "std": round(float(np.std(z_vals)), 5),
                "range": round(float(np.ptp(z_vals)), 5),
            }
    else:
        # ROI peri-orbital antropométrica canónica facial
        y1 = max(0, int(h * 0.22))
        y2 = min(h, int(h * 0.52))
        x1 = max(0, int(w * 0.15))
        x2 = min(w, int(w * 0.85))

    # Asegurar dimensiones válidas de ROI
    if y2 <= y1 or x2 <= x1:
        y1, y2 = 0, h
        x1, x2 = 0, w

    roi = img_u8[y1:y2, x1:x2]
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)

    # 1. Detección de bordes Canny
    edges = cv2.Canny(roi_gray, threshold1=50, threshold2=150)
    edge_density = float(np.mean(edges > 0))

    # 2. Gradientes ópticos de Sobel
    grad_x = cv2.Sobel(roi_gray, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(roi_gray, cv2.CV_64F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(grad_x, grad_y)
    mean_gradient = float(np.mean(grad_mag))

    # 3. Reflejos especulares (glare)
    glare_mask = roi_gray >= int(glare_intensity_threshold)
    glare_ratio = float(np.mean(glare_mask))

    # Clasificación heurística
    glasses_detected = bool(edge_density >= edge_threshold or mean_gradient >= gradient_threshold)
    glare_detected = bool(glare_ratio >= glare_threshold)
    has_glasses_or_glare = bool(glasses_detected or glare_detected)

    # Cálculo de nivel de confianza [0.0, 1.0]
    if has_glasses_or_glare:
        edge_ratio = edge_density / max(edge_threshold, 1e-6)
        grad_ratio = mean_gradient / max(gradient_threshold, 1e-6)
        g_strength = max(edge_ratio, grad_ratio) if glasses_detected else 0.0
        gl_strength = (glare_ratio / max(glare_threshold, 1e-6)) if glare_detected else 0.0
        overall_strength = max(g_strength, gl_strength)
        confidence = float(np.clip(0.5 + 0.5 * (1.0 - np.exp(-1.0 * (overall_strength - 1.0))), 0.5, 0.99))
    else:
        margin_edge = max(0.0, 1.0 - (edge_density / max(edge_threshold, 1e-6)))
        margin_grad = max(0.0, 1.0 - (mean_gradient / max(gradient_threshold, 1e-6)))
        margin_glare = max(0.0, 1.0 - (glare_ratio / max(glare_threshold, 1e-6)))
        clean_margin = min(margin_edge, margin_grad, margin_glare)
        confidence = float(np.clip(0.6 + 0.4 * clean_margin, 0.5, 0.99))

    # Generación del indicio clínico (clinical hint)
    if glasses_detected and glare_detected:
        clinical_hint = (
            "Se detectaron monturas de gafas y reflejos ópticos especulares en la zona peri-orbital. "
            "Se recomienda retirar las gafas y evitar fuentes de iluminación directa para una evaluación dermatológica óptima."
        )
    elif glasses_detected:
        clinical_hint = (
            "Se detectaron monturas o bordes compatibles con gafas en la zona peri-orbital. "
            "Se recomienda retirar las gafas para permitir la visualización cutánea y estimación biológica sin oclusiones."
        )
    elif glare_detected:
        clinical_hint = (
            "Se detectó reflejo especular o brillo óptico excesivo en la zona peri-orbital. "
            "Se recomienda reajustar el ángulo de captura o atenuar la iluminación directa para evitar artefactos."
        )
    else:
        clinical_hint = "Condiciones ópticas peri-orbitales adecuadas para evaluación dermatológica."

    metrics: Dict[str, Any] = {
        "edge_density": round(edge_density, 5),
        "mean_gradient": round(mean_gradient, 2),
        "glare_ratio": round(glare_ratio, 5),
        "peri_orbital_roi": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
    }

    if z_metrics is not None:
        metrics["z_depth"] = z_metrics

    return {
        "has_glasses_or_glare": has_glasses_or_glare,
        "glasses_detected": glasses_detected,
        "glare_detected": glare_detected,
        "confidence": round(confidence, 4),
        "clinical_hint": clinical_hint,
        "metrics": metrics,
    }


def check_lighting_quality(
    frame_or_roi_rgb: np.ndarray,
    min_luma: float = DEFAULT_MIN_LUMA,
    max_luma: float = DEFAULT_MAX_LUMA,
) -> Dict[str, Any]:
    """
    Evalúa la calidad de iluminación de un fotograma facial o región de interés (ROI)
    mediante el análisis de luminancia media en el espacio de color CIELAB (canal L),
    actuando como compuerta de calidad (semáforo lux/luma gate) antes de la inferencia.

    Clasificación del estado:
      - 'LUZ_BAJA': Luminancia media inferior al umbral mínimo (L < min_luma).
        Indica penumbra o subexposición que introduce ruido de sensor ISO y
        degrada la segmentación de pigmentación y estimación de edad.
      - 'BRILLO_EXCESIVO': Luminancia media superior al umbral máximo (L > max_luma).
        Indica sobreexposición, saturación de blancos o reflejos directos
        que ocultan textura cutánea y lesiones.
      - 'OPTIMA': Luminancia dentro del rango clínico adecuado [min_luma, max_luma].
        Garantiza contraste óptimo y balance cromático para inferencia.

    Parámetros
    ----------
    frame_or_roi_rgb : np.ndarray
        Tensor de entrada RGB (H, W, 3) del fotograma o ROI.
        Acepta uint8 [0, 255] o flotante [0.0, 1.0] / [0.0, 255.0].
    min_luma : float, opcional
        Umbral inferior de luminancia en escala CIELAB [0.0, 100.0] (por defecto: 30.0).
    max_luma : float, opcional
        Umbral superior de luminancia en escala CIELAB [0.0, 100.0] (por defecto: 85.0).

    Retorna
    -------
    Dict[str, Any]
        Diccionario con las métricas y diagnóstico de calidad de iluminación:
          - "status": str ('OPTIMA', 'LUZ_BAJA', 'BRILLO_EXCESIVO')
          - "estado": str (alias de status)
          - "mean_luminance": float (luminancia L media en CIELAB [0.0, 100.0], redondeada a 2 decimales)
          - "luminancia_media": float (alias de mean_luminance)
          - "estimated_lux": float (iluminancia estimada en lux, redondeada a 1 decimal)
          - "lux_estimado": float (alias de estimated_lux)
          - "lux": float (alias de estimated_lux)
          - "is_optimal": bool (True si status == 'OPTIMA')
          - "gate_pass": bool (True si status == 'OPTIMA', pasa la compuerta de inferencia)
          - "semaforo": str ('VERDE', 'AMARILLO', 'ROJO')
          - "clinical_message": str (recomendación clínica y corrección requerida)
          - "clinical_hint": str (alias de clinical_message)
          - "recommendation": str (alias de clinical_message)
          - "mensaje_clinico": str (alias de clinical_message)

    Raises
    ------
    TypeError
        Si frame_or_roi_rgb no es un numpy ndarray o los umbrales no son numéricos.
    ValueError
        Si la imagen tiene dimensiones inválidas, está vacía, contiene NaNs/Infs,
        o min_luma >= max_luma.
    """
    if isinstance(min_luma, bool) or not isinstance(min_luma, (int, float, np.floating, np.integer)):
        raise TypeError(f"min_luma debe ser numérico, recibido {type(min_luma).__name__}")
    if isinstance(max_luma, bool) or not isinstance(max_luma, (int, float, np.floating, np.integer)):
        raise TypeError(f"max_luma debe ser numérico, recibido {type(max_luma).__name__}")

    min_l_val = float(min_luma)
    max_l_val = float(max_luma)

    if min_l_val >= max_l_val:
        raise ValueError(f"min_luma ({min_l_val}) debe ser menor que max_luma ({max_l_val})")
    if min_l_val < 0.0 or max_l_val > 100.0:
        raise ValueError(
            f"Los umbrales deben estar en el rango [0.0, 100.0], recibido min={min_l_val}, max={max_l_val}"
        )

    img_u8 = _validate_and_prepare_image(frame_or_roi_rgb)

    # Conversión al espacio CIELAB (OpenCV uint8: L en [0, 255] donde L* = L_u8 * 100 / 255)
    lab = cv2.cvtColor(img_u8, cv2.COLOR_RGB2LAB)
    l_channel = lab[:, :, 0]
    l_star = l_channel.astype(np.float32) * (100.0 / 255.0)
    mean_l = float(np.mean(l_star))

    # Estimación empírica de iluminancia (lux) mediante modelo fotométrico estándar CIE
    # Luminancia relativa Y/Yn = ((L* + 16)/116)^3 para L* > 8, escala clínica de 1000 lux a 100% reflectancia
    if mean_l > 8.0:
        y_rel = ((mean_l + 16.0) / 116.0) ** 3.0
    else:
        y_rel = mean_l / 903.3
    estimated_lux = float(np.clip(y_rel * 1000.0, 0.0, 2500.0))

    # Evaluación del semáforo y estado de compuerta luma gate
    if mean_l < min_l_val:
        status = "LUZ_BAJA"
        semaforo = "AMARILLO"
        clinical_message = (
            "Iluminación insuficiente detectada (luz baja). "
            "Se recomienda encender una luz frontal o ubicarse frente a una fuente de luz difusa "
            "para evitar ruido de sensor y artefactos en el diagnóstico."
        )
    elif mean_l > max_l_val:
        status = "BRILLO_EXCESIVO"
        semaforo = "ROJO"
        clinical_message = (
            "Iluminación excesiva o deslumbramiento detectado (brillo excesivo). "
            "Se recomienda atenuar la iluminación directa o reposicionar la cámara "
            "para prevenir sobreexposición y pérdida de contraste."
        )
    else:
        status = "OPTIMA"
        semaforo = "VERDE"
        clinical_message = (
            "Condiciones de iluminación óptimas para evaluación dermatológica e inferencia espectral."
        )

    return {
        "status": status,
        "estado": status,
        "mean_luminance": round(mean_l, 2),
        "luminancia_media": round(mean_l, 2),
        "estimated_lux": round(estimated_lux, 1),
        "lux_estimado": round(estimated_lux, 1),
        "lux": round(estimated_lux, 1),
        "is_optimal": bool(status == "OPTIMA"),
        "gate_pass": bool(status == "OPTIMA"),
        "semaforo": semaforo,
        "clinical_message": clinical_message,
        "clinical_hint": clinical_message,
        "recommendation": clinical_message,
        "mensaje_clinico": clinical_message,
    }
