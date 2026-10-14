"""
Pruebas Unitarias para el Módulo de Normalización Óptica y Detección de Gafas/Glare.
Verifica:
1. Tipos y dimensiones de entrada/salida en normalize_optical_conditions.
2. Preservación estricta de canales cromáticos A/B y compensación de luminancia L.
3. Desacoplo de ruido y preservación de bordes anatómicos.
4. Heurística de detección de monturas (gafas) y reflejos especulares (glare).
5. Compatibilidad con puntos de referencia faciales (Face Mesh y 4 nodos peri-orbitales).
"""

import math
import pytest
import numpy as np
import cv2

from src.inference.optical_normalizer import (
    normalize_optical_conditions,
    detect_glasses_or_glare,
    check_lighting_quality,
    DEFAULT_CLAHE_CLIP_LIMIT,
    DEFAULT_CLAHE_GRID_SIZE,
    DEFAULT_BILATERAL_D,
    DEFAULT_BILATERAL_SIGMA_COLOR,
    DEFAULT_BILATERAL_SIGMA_SPACE,
    DEFAULT_MIN_LUMA,
    DEFAULT_MAX_LUMA,
    MEDIAPIPE_PERI_ORBITAL_NODES,
)


def _create_synthetic_face(
    with_glasses: bool = False,
    with_glare: bool = False,
    shape: tuple = (224, 224, 3),
) -> np.ndarray:
    """Genera una imagen sintética de rostro facial con piel y rasgos estándar."""
    h, w = shape[:2]
    # Tono base de piel biológica
    img = np.full((h, w, 3), (210, 175, 150), dtype=np.uint8)

    eye_y = int(h * 0.42)
    left_eye_x = int(w * 0.33)
    right_eye_x = int(w * 0.67)

    # Ojos y cejas
    cv2.circle(img, (left_eye_x, eye_y), int(w * 0.035), (60, 40, 30), -1)
    cv2.circle(img, (right_eye_x, eye_y), int(w * 0.035), (60, 40, 30), -1)
    cv2.ellipse(
        img,
        (left_eye_x, eye_y - int(h * 0.06)),
        (int(w * 0.08), int(h * 0.02)),
        0, 180, 360, (50, 35, 25), 2,
    )
    cv2.ellipse(
        img,
        (right_eye_x, eye_y - int(h * 0.06)),
        (int(w * 0.08), int(h * 0.02)),
        0, 180, 360, (50, 35, 25), 2,
    )

    # Nariz y labios
    cv2.line(img, (w // 2, eye_y), (w // 2, int(h * 0.6)), (180, 140, 120), 2)
    cv2.ellipse(
        img,
        (w // 2, int(h * 0.75)),
        (int(w * 0.12), int(h * 0.04)),
        0, 0, 180, (170, 70, 70), 3,
    )

    # Añadir monturas de gafas
    if with_glasses:
        box_w = int(w * 0.22)
        box_h = int(h * 0.18)
        cv2.rectangle(
            img,
            (left_eye_x - box_w // 2, eye_y - box_h // 2),
            (left_eye_x + box_w // 2, eye_y + box_h // 2),
            (20, 20, 20), 2,
        )
        cv2.rectangle(
            img,
            (right_eye_x - box_w // 2, eye_y - box_h // 2),
            (right_eye_x + box_w // 2, eye_y + box_h // 2),
            (20, 20, 20), 2,
        )
        # Puente nasal de gafas
        cv2.line(
            img,
            (left_eye_x + box_w // 2, eye_y),
            (right_eye_x - box_w // 2, eye_y),
            (20, 20, 20), 2,
        )

    # Añadir reflejo especular (glare)
    if with_glare:
        cv2.circle(img, (left_eye_x + int(w * 0.05), eye_y - int(h * 0.02)), int(w * 0.03), (255, 255, 255), -1)

    return img


# =========================================================================
# 1. Pruebas de Normalización Óptica: Tipos, Dimensiones y Validación
# =========================================================================

def test_normalize_optical_conditions_types_and_dimensions():
    """Verifica que el tensor de salida mantenga dimensiones y sea uint8."""
    img = np.random.randint(0, 256, (224, 224, 3), dtype=np.uint8)
    norm = normalize_optical_conditions(img)

    assert isinstance(norm, np.ndarray)
    assert norm.shape == (224, 224, 3)
    assert norm.dtype == np.uint8

    # Probar con dimensiones no cuadradas
    img_rect = np.random.randint(0, 256, (120, 160, 3), dtype=np.uint8)
    norm_rect = normalize_optical_conditions(img_rect)
    assert norm_rect.shape == (120, 160, 3)
    assert norm_rect.dtype == np.uint8


def test_normalize_optical_conditions_floating_point_input():
    """Verifica manejo de tensores float en rango [0.0, 1.0] y [0.0, 255.0]."""
    img_float_01 = np.random.rand(100, 100, 3).astype(np.float32)
    norm_01 = normalize_optical_conditions(img_float_01)
    assert norm_01.dtype == np.uint8
    assert norm_01.shape == (100, 100, 3)

    img_float_255 = (np.random.rand(100, 100, 3) * 255.0).astype(np.float32)
    norm_255 = normalize_optical_conditions(img_float_255)
    assert norm_255.dtype == np.uint8
    assert norm_255.shape == (100, 100, 3)


def test_normalize_optical_conditions_invalid_inputs():
    """Verifica el rechazo estricto de entradas inválidas o malformadas."""
    # Entrada no numpy
    with pytest.raises(TypeError, match="numpy.ndarray"):
        normalize_optical_conditions([[1, 2, 3]])

    with pytest.raises(TypeError, match="numpy.ndarray"):
        normalize_optical_conditions(None)

    # Dimensiones incorrectas (imagen 2D / escala de grises)
    with pytest.raises(ValueError, match="RGB"):
        normalize_optical_conditions(np.zeros((224, 224), dtype=np.uint8))

    # 4 canales (RGBA)
    with pytest.raises(ValueError, match="RGB"):
        normalize_optical_conditions(np.zeros((224, 224, 4), dtype=np.uint8))

    # Imagen vacía (0x0)
    with pytest.raises(ValueError, match="mayores que 0"):
        normalize_optical_conditions(np.zeros((0, 224, 3), dtype=np.uint8))


# =========================================================================
# 2. Pruebas de Preservación de Canales Cromáticos (A/B en Espacio LAB)
# =========================================================================

def test_normalize_optical_conditions_chromaticity_preservation():
    """
    Verifica que la ecualización CLAHE sobre L conserve intactos los canales
    cromáticos A y B, preservando el tono biológico cutáneo.
    """
    # Crear parche con tono cutáneo y gradiente de sombra profunda
    h, w = 120, 120
    skin_rgb = np.array([210, 175, 145], dtype=np.float32)
    gradient = np.linspace(0.3, 1.1, h)[:, None, None]
    illuminated = np.clip(skin_rgb * gradient, 0, 255).astype(np.uint8)

    norm = normalize_optical_conditions(illuminated)

    lab_orig = cv2.cvtColor(illuminated, cv2.COLOR_RGB2LAB)
    lab_norm = cv2.cvtColor(norm, cv2.COLOR_RGB2LAB)

    # Los canales A y B representan crominancia verde-roja y azul-amarilla
    orig_a_mean = float(np.mean(lab_orig[:, :, 1]))
    orig_b_mean = float(np.mean(lab_orig[:, :, 2]))

    norm_a_mean = float(np.mean(lab_norm[:, :, 1]))
    norm_b_mean = float(np.mean(lab_norm[:, :, 2]))

    # La diferencia promedio en crominancia debe ser prácticamente despreciable (< 2 unidades LAB)
    assert abs(orig_a_mean - norm_a_mean) < 2.0, (
        f"Desviación excesiva en canal A: orig={orig_a_mean}, norm={norm_a_mean}"
    )
    assert abs(orig_b_mean - norm_b_mean) < 2.0, (
        f"Desviación excesiva en canal B: orig={orig_b_mean}, norm={norm_b_mean}"
    )


def test_normalize_optical_conditions_achromatic_neutrality():
    """Verifica que una imagen en escala de grises permanezca acromática tras la normalización."""
    gray_ramp = np.tile(np.linspace(20, 220, 100, dtype=np.uint8), (100, 1))
    gray_rgb = np.stack([gray_ramp, gray_ramp, gray_ramp], axis=2)

    norm = normalize_optical_conditions(gray_rgb)

    # Verificar que los canales R, G y B sigan siendo idénticos entre sí
    diff_rg = np.max(np.abs(norm[:, :, 0].astype(int) - norm[:, :, 1].astype(int)))
    diff_gb = np.max(np.abs(norm[:, :, 1].astype(int) - norm[:, :, 2].astype(int)))

    assert diff_rg <= 1, "La normalización desbalanceó canales en imagen acromática"
    assert diff_gb <= 1, "La normalización desbalanceó canales en imagen acromática"


# =========================================================================
# 3. Pruebas de Corrección de Iluminación y Sombras Profundas
# =========================================================================

def test_normalize_optical_conditions_shadow_compensation():
    """
    Verifica que las zonas de sombras profundas experimenten una elevación
    de luminancia y expansión del contraste dinámico.
    """
    # Parche con iluminación normal y una región de sombra profunda (cuenca ocular/cejas)
    img = np.full((120, 120, 3), (190, 160, 135), dtype=np.uint8)
    # Región de sombra profunda con gradiente sutil
    img[:50, :] = np.clip(np.linspace(20, 50, 50)[:, None, None] * np.array([1.0, 0.9, 0.8]), 0, 255).astype(np.uint8)

    norm = normalize_optical_conditions(img)

    lab_orig = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    lab_norm = cv2.cvtColor(norm, cv2.COLOR_RGB2LAB)

    l_orig_shadow_mean = float(np.mean(lab_orig[:50, :, 0]))
    l_norm_shadow_mean = float(np.mean(lab_norm[:50, :, 0]))

    # La luminancia en la zona oscura debe elevarse significativamente (+5 o más)
    assert l_norm_shadow_mean > l_orig_shadow_mean + 5.0, (
        f"Luminancia no incrementó adecuadamente en sombras: {l_orig_shadow_mean} -> {l_norm_shadow_mean}"
    )

    # El rango dinámico (ptp) en la sombra debe expandirse tras CLAHE
    ptp_orig = float(np.ptp(lab_orig[:50, :, 0]))
    ptp_norm = float(np.ptp(lab_norm[:50, :, 0]))
    assert ptp_norm >= ptp_orig, (
        f"El rango dinámico no se expandió: orig={ptp_orig}, norm={ptp_norm}"
    )


# =========================================================================
# 4. Pruebas de Filtrado Bilateral Edge-Preserving
# =========================================================================

def test_normalize_optical_conditions_edge_preservation():
    """
    Verifica que los bordes anatómicos abruptos se preserven nítidos,
    a diferencia de lo que ocurriría con un filtro gaussiano o de caja.
    """
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :50] = (60, 40, 30)    # Borde oscuro (ej. lunar o iris)
    img[:, 50:] = (210, 175, 145)  # Piel clara

    norm = normalize_optical_conditions(img)

    # El salto de intensidad a través de la frontera (columna 48 vs 52) debe mantenerse nítido
    jump_orig = int(img[50, 52, 0]) - int(img[50, 47, 0])
    jump_norm = int(norm[50, 52, 0]) - int(norm[50, 47, 0])

    # El salto no debe haberse difuminado drásticamente
    assert jump_norm >= jump_orig * 0.85, (
        f"El filtro difuminó excesivamente el borde: salto orig={jump_orig}, norm={jump_norm}"
    )


# =========================================================================
# 5. Pruebas de Detección de Gafas y Glare (Heurística Peri-orbital)
# =========================================================================

def test_detect_glasses_or_glare_clean_face():
    """Verifica que un rostro sin gafas ni reflejos sea catalogado como ópticamente limpio."""
    face_clean = _create_synthetic_face(with_glasses=False, with_glare=False)
    result = detect_glasses_or_glare(face_clean)

    assert result["has_glasses_or_glare"] is False
    assert result["glasses_detected"] is False
    assert result["glare_detected"] is False
    assert result["confidence"] >= 0.5
    assert "adecuadas" in result["clinical_hint"].lower()
    assert result["metrics"]["edge_density"] < 0.055
    assert result["metrics"]["glare_ratio"] < 0.008


def test_detect_glasses_or_glare_with_glasses():
    """Verifica detección positiva de monturas de gafas por gradientes elevados."""
    face_glasses = _create_synthetic_face(with_glasses=True, with_glare=False)
    result = detect_glasses_or_glare(face_glasses)

    assert result["has_glasses_or_glare"] is True
    assert result["glasses_detected"] is True
    assert result["glare_detected"] is False
    assert "gafas" in result["clinical_hint"].lower()
    assert result["confidence"] >= 0.5
    assert (
        result["metrics"]["edge_density"] >= 0.055
        or result["metrics"]["mean_gradient"] >= 70.0
    )


def test_detect_glasses_or_glare_with_specular_glare():
    """Verifica detección positiva de reflejos especulares por saturación peri-orbital."""
    face_glare = _create_synthetic_face(with_glasses=False, with_glare=True)
    result = detect_glasses_or_glare(face_glare)

    assert result["has_glasses_or_glare"] is True
    assert result["glare_detected"] is True
    assert "reflejo" in result["clinical_hint"].lower() or "brillo" in result["clinical_hint"].lower()
    assert result["metrics"]["glare_ratio"] >= 0.008


def test_detect_glasses_or_glare_with_both_glasses_and_glare():
    """Verifica detección conjunta de monturas y reflejos especulares con recomendación dual."""
    face_both = _create_synthetic_face(with_glasses=True, with_glare=True)
    result = detect_glasses_or_glare(face_both)

    assert result["has_glasses_or_glare"] is True
    assert result["glasses_detected"] is True
    assert result["glare_detected"] is True
    assert "gafas" in result["clinical_hint"].lower()
    assert "reflejos" in result["clinical_hint"].lower()


# =========================================================================
# 6. Pruebas de Integración con Landmarks Peri-orbitales de MediaPipe
# =========================================================================

def test_detect_glasses_or_glare_with_mediapipe_landmarks():
    """Verifica extracción de ROI y métricas Z usando 468 nodos de MediaPipe Face Mesh."""
    face_clean = _create_synthetic_face(with_glasses=False, with_glare=False)
    h, w = face_clean.shape[:2]

    # Simular 468 nodos normalizados [0.0, 1.0] con profundidad Z
    landmarks = np.zeros((468, 3), dtype=np.float32)
    landmarks[33] = [0.26, 0.42, -0.015]   # Canto lateral derecho
    landmarks[133] = [0.41, 0.42, -0.008]  # Canto medial derecho
    landmarks[362] = [0.59, 0.42, -0.008]  # Canto medial izquierdo
    landmarks[263] = [0.74, 0.42, -0.015]  # Canto lateral izquierdo

    result = detect_glasses_or_glare(face_clean, face_landmarks=landmarks)

    assert "z_depth" in result["metrics"]
    z_depth = result["metrics"]["z_depth"]
    assert "mean" in z_depth
    assert "variance" in z_depth
    assert "std" in z_depth
    assert "range" in z_depth
    assert z_depth["range"] > 0.0


def test_detect_glasses_or_glare_with_4_landmarks_pixel_coords():
    """Verifica compatibilidad cuando se pasan directamente los 4 nodos en píxeles."""
    face_glasses = _create_synthetic_face(with_glasses=True, with_glare=False)
    h, w = face_glasses.shape[:2]

    landmarks_4 = np.array([
        [int(w * 0.26), int(h * 0.42), -15.0],
        [int(w * 0.41), int(h * 0.42), -8.0],
        [int(w * 0.59), int(h * 0.42), -8.0],
        [int(w * 0.74), int(h * 0.42), -15.0],
    ], dtype=np.float32)

    result = detect_glasses_or_glare(face_glasses, face_landmarks=landmarks_4)

    assert result["glasses_detected"] is True
    assert "z_depth" in result["metrics"]
    roi = result["metrics"]["peri_orbital_roi"]
    assert roi["x1"] < roi["x2"]
    assert roi["y1"] < roi["y2"]


def test_detect_glasses_or_glare_invalid_landmarks():
    """Verifica que landmarks con forma incorrecta levanten ValueError."""
    face = _create_synthetic_face()

    # Número insuficiente de landmarks (no son 4 ni >= 363)
    with pytest.raises(ValueError, match="face_landmarks debe tener al menos 363 puntos"):
        detect_glasses_or_glare(face, face_landmarks=np.zeros((10, 2)))

    # Dimensión no 2D
    with pytest.raises(ValueError, match="dimensión 2D"):
        detect_glasses_or_glare(face, face_landmarks=np.zeros((468, 3, 1)))


def test_detect_glasses_or_glare_custom_thresholds():
    """Verifica que los umbrales personalizados modifiquen la sensibilidad de detección."""
    face_clean = _create_synthetic_face(with_glasses=False, with_glare=False)

    # Con umbral de borde artificialmente bajo, se activará la detección
    result_sensitive = detect_glasses_or_glare(face_clean, edge_threshold=0.001)
    assert result_sensitive["glasses_detected"] is True

    # Con umbral de glare artificialmente bajo, se activará la detección
    result_glare_sensitive = detect_glasses_or_glare(face_clean, glare_threshold=0.0)
    assert result_glare_sensitive["glare_detected"] is True


# =========================================================================
# 7. Pruebas de Control de Calidad de Iluminación (Semáforo Lux / Luma Gate)
# =========================================================================

def test_check_lighting_quality_schema_and_types():
    """Verifica el esquema completo del diccionario retornado y tipos de datos."""
    face = _create_synthetic_face()
    res = check_lighting_quality(face)

    assert isinstance(res, dict)
    required_keys = {
        "status",
        "estado",
        "mean_luminance",
        "luminancia_media",
        "estimated_lux",
        "lux_estimado",
        "lux",
        "is_optimal",
        "gate_pass",
        "semaforo",
        "clinical_message",
        "clinical_hint",
        "recommendation",
        "mensaje_clinico",
    }
    assert required_keys.issubset(res.keys())

    assert isinstance(res["status"], str)
    assert res["status"] in ("OPTIMA", "LUZ_BAJA", "BRILLO_EXCESIVO")
    assert res["estado"] == res["status"]
    assert isinstance(res["mean_luminance"], float)
    assert res["luminancia_media"] == res["mean_luminance"]
    assert isinstance(res["estimated_lux"], float)
    assert res["lux_estimado"] == res["estimated_lux"]
    assert res["lux"] == res["estimated_lux"]
    assert isinstance(res["is_optimal"], bool)
    assert isinstance(res["gate_pass"], bool)
    assert res["gate_pass"] == res["is_optimal"]
    assert isinstance(res["semaforo"], str)
    assert res["semaforo"] in ("VERDE", "AMARILLO", "ROJO")
    assert isinstance(res["clinical_message"], str)
    assert len(res["clinical_message"]) > 0


def test_check_lighting_quality_optimal():
    """Verifica que un rostro con iluminación estándar sea catalogado como OPTIMA (semáforo VERDE)."""
    face = _create_synthetic_face(with_glasses=False, with_glare=False)
    res = check_lighting_quality(face)

    assert res["status"] == "OPTIMA"
    assert res["estado"] == "OPTIMA"
    assert res["semaforo"] == "VERDE"
    assert res["is_optimal"] is True
    assert res["gate_pass"] is True
    assert DEFAULT_MIN_LUMA <= res["mean_luminance"] <= DEFAULT_MAX_LUMA
    assert res["estimated_lux"] > 100.0
    assert "óptimas" in res["clinical_message"].lower() or "optimas" in res["clinical_message"].lower()


def test_check_lighting_quality_low_light():
    """Verifica detección de iluminación insuficiente (LUZ_BAJA / semáforo AMARILLO)."""
    # Imagen subexpuesta / oscura (pixel RGB 25) -> L* < 10
    dark_frame = np.full((120, 120, 3), 25, dtype=np.uint8)
    res = check_lighting_quality(dark_frame)

    assert res["status"] == "LUZ_BAJA"
    assert res["estado"] == "LUZ_BAJA"
    assert res["semaforo"] == "AMARILLO"
    assert res["is_optimal"] is False
    assert res["gate_pass"] is False
    assert res["mean_luminance"] < DEFAULT_MIN_LUMA
    assert res["estimated_lux"] < 100.0
    assert "insuficiente" in res["clinical_message"].lower() or "luz baja" in res["clinical_message"].lower()


def test_check_lighting_quality_excessive_brightness():
    """Verifica detección de sobreexposición (BRILLO_EXCESIVO / semáforo ROJO)."""
    # Imagen sobreexpuesta / saturada (pixel RGB 245) -> L* > 95
    bright_frame = np.full((120, 120, 3), 245, dtype=np.uint8)
    res = check_lighting_quality(bright_frame)

    assert res["status"] == "BRILLO_EXCESIVO"
    assert res["estado"] == "BRILLO_EXCESIVO"
    assert res["semaforo"] == "ROJO"
    assert res["is_optimal"] is False
    assert res["gate_pass"] is False
    assert res["mean_luminance"] > DEFAULT_MAX_LUMA
    assert res["estimated_lux"] > 650.0
    assert "excesiv" in res["clinical_message"].lower() or "brillo" in res["clinical_message"].lower()


def test_check_lighting_quality_custom_thresholds():
    """Verifica que umbrales personalizados de luma modifiquen la clasificación."""
    # Parche con luminancia intermedia controlada
    mid_patch = np.full((80, 80, 3), 130, dtype=np.uint8)
    default_res = check_lighting_quality(mid_patch)
    # Por defecto (30..85), ~54 L* es OPTIMA
    assert default_res["status"] == "OPTIMA"

    # Con min_luma=60.0, 54 L* debe ser LUZ_BAJA
    res_high_min = check_lighting_quality(mid_patch, min_luma=60.0)
    assert res_high_min["status"] == "LUZ_BAJA"
    assert res_high_min["is_optimal"] is False

    # Con max_luma=50.0, 54 L* debe ser BRILLO_EXCESIVO
    res_low_max = check_lighting_quality(mid_patch, max_luma=50.0)
    assert res_low_max["status"] == "BRILLO_EXCESIVO"
    assert res_low_max["is_optimal"] is False


def test_check_lighting_quality_lux_monotonicity():
    """Verifica que la estimación de lux sea estrictamente creciente con la luminancia."""
    black_frame = np.zeros((64, 64, 3), dtype=np.uint8)
    dim_frame = np.full((64, 64, 3), 40, dtype=np.uint8)
    mid_frame = np.full((64, 64, 3), 120, dtype=np.uint8)
    bright_frame = np.full((64, 64, 3), 200, dtype=np.uint8)
    white_frame = np.full((64, 64, 3), 255, dtype=np.uint8)

    res_black = check_lighting_quality(black_frame)
    res_dim = check_lighting_quality(dim_frame)
    res_mid = check_lighting_quality(mid_frame)
    res_bright = check_lighting_quality(bright_frame)
    res_white = check_lighting_quality(white_frame)

    assert res_black["estimated_lux"] == 0.0
    assert res_black["mean_luminance"] == 0.0
    assert (
        res_black["estimated_lux"]
        < res_dim["estimated_lux"]
        < res_mid["estimated_lux"]
        < res_bright["estimated_lux"]
        < res_white["estimated_lux"]
    )
    assert res_white["estimated_lux"] >= 990.0


def test_check_lighting_quality_floating_point_and_aspect_ratios():
    """Verifica soporte para entradas float32 normalizadas [0, 1], [0, 255] y dimensiones rectangulares."""
    u8_img = np.full((60, 140, 3), 160, dtype=np.uint8)
    f32_01 = (u8_img / 255.0).astype(np.float32)
    f32_255 = u8_img.astype(np.float32)

    res_u8 = check_lighting_quality(u8_img)
    res_f32_01 = check_lighting_quality(f32_01)
    res_f32_255 = check_lighting_quality(f32_255)

    assert res_u8["status"] == res_f32_01["status"] == res_f32_255["status"]
    assert math.isclose(res_u8["mean_luminance"], res_f32_01["mean_luminance"], abs_tol=1.0)
    assert math.isclose(res_u8["estimated_lux"], res_f32_01["estimated_lux"], abs_tol=5.0)


def test_check_lighting_quality_invalid_inputs():
    """Verifica rechazo estricto de entradas inválidas y parámetros fuera de rango."""
    # No es ndarray
    with pytest.raises(TypeError, match="numpy.ndarray"):
        check_lighting_quality([[100, 100, 100]])

    with pytest.raises(TypeError, match="numpy.ndarray"):
        check_lighting_quality(None)

    # Dimensiones incorrectas (2D)
    with pytest.raises(ValueError, match="RGB"):
        check_lighting_quality(np.zeros((64, 64), dtype=np.uint8))

    # Dimensiones incorrectas (4D)
    with pytest.raises(ValueError, match="RGB"):
        check_lighting_quality(np.zeros((1, 64, 64, 3), dtype=np.uint8))

    # Imagen vacía (0x64x3)
    with pytest.raises(ValueError, match="mayores que 0"):
        check_lighting_quality(np.zeros((0, 64, 3), dtype=np.uint8))

    # Imagen con NaNs
    nan_img = np.full((32, 32, 3), 0.5, dtype=np.float32)
    nan_img[5, 5, 0] = np.nan
    with pytest.raises(ValueError, match="NaN o Infinitos"):
        check_lighting_quality(nan_img)

    # Umbral mínimo mayor o igual que máximo
    face = _create_synthetic_face()
    with pytest.raises(ValueError, match="debe ser menor que max_luma"):
        check_lighting_quality(face, min_luma=80.0, max_luma=70.0)

    with pytest.raises(ValueError, match="debe ser menor que max_luma"):
        check_lighting_quality(face, min_luma=50.0, max_luma=50.0)

    # Umbrales fuera de rango [0, 100]
    with pytest.raises(ValueError, match="rango"):
        check_lighting_quality(face, min_luma=-5.0)

    with pytest.raises(ValueError, match="rango"):
        check_lighting_quality(face, max_luma=105.0)

    # Umbrales no numéricos o booleanos
    with pytest.raises(TypeError, match="debe ser numérico"):
        check_lighting_quality(face, min_luma="30")

    with pytest.raises(TypeError, match="debe ser numérico"):
        check_lighting_quality(face, max_luma=True)
