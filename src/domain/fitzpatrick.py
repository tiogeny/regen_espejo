"""
Dermatological skin phototype classification and spectral calibration domain module.

Implements the Individual Typology Angle (ITA) in CIELAB color space,
Fitzpatrick phototype mapping (I-VI) according to dermatological standards,
and dynamic melanin segmentation thresholds for U-Net Nano inference.
"""

import math
from typing import Any, Dict, List
import cv2
import numpy as np

# Standard dermatological descriptions aligned with Fitzpatrick classification & SKILL.md
FITZPATRICK_DESCRIPTIONS: Dict[int, str] = {
    1: "Muy Clara",
    2: "Clara",
    3: "Intermedia",
    4: "Bronceada / Morena",
    5: "Oscura",
    6: "Muy Oscura",
}

FITZPATRICK_CLINICAL_NAMES: Dict[int, str] = {
    1: "Fototipo I (Muy claro)",
    2: "Fototipo II (Claro)",
    3: "Fototipo III (Intermedio)",
    4: "Fototipo IV (Bronceado / Moreno)",
    5: "Fototipo V (Oscuro)",
    6: "Fototipo VI (Muy oscuro)",
}

# Dynamic melanin contrast thresholds for U-Net Nano segmentation.
# Phototypes I-II utilize Δ >= 0.14. Higher phototypes (III-VI) require
# dynamically increased thresholds to prevent false positives from basal melanin.
CALIBRATED_SPOT_THRESHOLDS: Dict[int, float] = {
    1: 0.14,
    2: 0.14,
    3: 0.17,
    4: 0.20,
    5: 0.24,
    6: 0.28,
}


def calculate_ita(l_star: float, b_star: float) -> float:
    """
    Computes the Individual Typology Angle (ITA) in degrees:
        ITA = arctan((L* - 50) / b*) * (180 / pi)

    Parameters
    ----------
    l_star : float
        Perceptual lightness coordinate in CIELAB space [0.0, 100.0].
    b_star : float
        Yellow-blue chromatic coordinate in CIELAB space. For physiological skin,
        b* must be strictly positive (yellow pigmentation component).

    Returns
    -------
    float
        The ITA value in degrees, bounded within (-90.0, 90.0).

    Raises
    ------
    TypeError
        If l_star or b_star are not numeric.
    ValueError
        If inputs are NaN/Inf, l_star is outside [0.0, 100.0], or b_star <= 0.0.
    """
    if isinstance(l_star, bool) or not isinstance(l_star, (int, float, np.floating, np.integer)):
        raise TypeError(f"l_star must be a numeric value, got {type(l_star).__name__}")
    if isinstance(b_star, bool) or not isinstance(b_star, (int, float, np.floating, np.integer)):
        raise TypeError(f"b_star must be a numeric value, got {type(b_star).__name__}")

    l_val = float(l_star)
    b_val = float(b_star)

    if math.isnan(l_val) or math.isinf(l_val):
        raise ValueError(f"l_star must be a finite number, got {l_star}")
    if math.isnan(b_val) or math.isinf(b_val):
        raise ValueError(f"b_star must be a finite number, got {b_star}")

    if not (0.0 <= l_val <= 100.0):
        raise ValueError(f"l_star must be in the range [0.0, 100.0], got {l_star}")
    if b_val <= 0.0:
        raise ValueError(f"b_star must be strictly positive for skin ITA calculation, got {b_star}")

    ita_rad = math.atan((l_val - 50.0) / b_val)
    return float(math.degrees(ita_rad))


def classify_fitzpatrick_from_ita(ita_deg: float) -> int:
    """
    Classifies skin tone into Fitzpatrick scale (1 to 6) based on dermatological ITA brackets:
      - Phototype I   (Muy Clara):           ITA > 55°
      - Phototype II  (Clara):        41° <  ITA <= 55°
      - Phototype III (Intermedia):   28° <  ITA <= 41°
      - Phototype IV  (Bronceada):    10° <  ITA <= 28°
      - Phototype V   (Oscura):      -30° <  ITA <= 10°
      - Phototype VI  (Muy Oscura):          ITA <= -30°

    Parameters
    ----------
    ita_deg : float
        The Individual Typology Angle in degrees, theoretically in [-90.0, 90.0].

    Returns
    -------
    int
        Fitzpatrick phototype scale (1 to 6).

    Raises
    ------
    TypeError
        If ita_deg is not a numeric value.
    ValueError
        If ita_deg is NaN, Inf, or outside theoretical range [-90.0, 90.0].
    """
    if isinstance(ita_deg, bool) or not isinstance(ita_deg, (int, float, np.floating, np.integer)):
        raise TypeError(f"ita_deg must be a numeric value, got {type(ita_deg).__name__}")

    val = float(ita_deg)

    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"ita_deg must be a finite number, got {ita_deg}")
    if val < -90.0 or val > 90.0:
        raise ValueError(f"ita_deg must be within theoretical bounds [-90.0, 90.0], got {ita_deg}")

    if val > 55.0:
        return 1
    elif val > 41.0:
        return 2
    elif val > 28.0:
        return 3
    elif val > 10.0:
        return 4
    elif val > -30.0:
        return 5
    else:
        return 6


def get_calibrated_spot_threshold(fitzpatrick_type: int) -> float:
    """
    Returns the dynamic melanin contrast threshold for U-Net Nano spot segmentation.

    For fair phototypes (I-II), threshold is fixed at Δ >= 0.14.
    For darker phototypes (III-VI), dynamic scaling prevents false positives
    caused by elevated basal epidermal melanin.

    Parameters
    ----------
    fitzpatrick_type : int
        Fitzpatrick phototype scale (1 to 6).

    Returns
    -------
    float
        The calibrated melanin contrast threshold.

    Raises
    ------
    TypeError
        If fitzpatrick_type is not an integer.
    ValueError
        If fitzpatrick_type is outside 1..6.
    """
    if isinstance(fitzpatrick_type, bool) or not isinstance(fitzpatrick_type, (int, np.integer)):
        raise TypeError(f"fitzpatrick_type must be an integer, got {type(fitzpatrick_type).__name__}")

    f_type = int(fitzpatrick_type)
    if f_type not in CALIBRATED_SPOT_THRESHOLDS:
        raise ValueError(
            f"Invalid Fitzpatrick phototype: {fitzpatrick_type}. Must be an integer between 1 and 6."
        )

    return CALIBRATED_SPOT_THRESHOLDS[f_type]


def extract_skin_phototype(face_patch_rgb: np.ndarray) -> Dict[str, Any]:
    """
    Extracts skin phototype from an RGB face patch.

    Converts the patch from RGB to CIELAB space, computes the median L* and b* coordinates
    (robust to specular reflections, shine, and localized shadows), computes the Individual
    Typology Angle (ITA), and returns the classified Fitzpatrick phototype and clinical description.

    Parameters
    ----------
    face_patch_rgb : np.ndarray
        RGB image patch of shape (H, W, 3). Can be uint8 [0, 255] or float [0.0, 1.0].

    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
          - "phototype": int (1 to 6)
          - "description": str (e.g. "Clara")
          - "clinical_label": str (e.g. "Fototipo II (Claro)")
          - "ita": float (ITA rounded to 2 decimal places)
          - "ita_deg": float (raw ITA in degrees)
          - "l_star": float (median L* coordinate)
          - "b_star": float (median b* coordinate)
          - "spot_threshold": float (dynamic melanin segmentation threshold)

    Raises
    ------
    TypeError
        If face_patch_rgb is not a numpy ndarray.
    ValueError
        If shape is not (H, W, 3), image is empty, contains NaNs/Infs, or has invalid color values.
    """
    lab_patch = _validate_and_convert_patch_to_lab(face_patch_rgb)

    l_channel = lab_patch[:, :, 0]
    b_channel = lab_patch[:, :, 2]

    median_l = float(np.median(l_channel))
    median_b = float(np.median(b_channel))

    ita_val = calculate_ita(median_l, median_b)
    phototype = classify_fitzpatrick_from_ita(ita_val)
    threshold = get_calibrated_spot_threshold(phototype)

    return {
        "phototype": phototype,
        "description": FITZPATRICK_DESCRIPTIONS[phototype],
        "clinical_label": FITZPATRICK_CLINICAL_NAMES[phototype],
        "ita": round(ita_val, 2),
        "ita_deg": ita_val,
        "l_star": round(median_l, 2),
        "b_star": round(median_b, 2),
        "spot_threshold": threshold,
    }


def _validate_and_convert_patch_to_lab(face_patch_rgb: np.ndarray) -> np.ndarray:
    """
    Validates an RGB face patch and converts it to CIELAB space via OpenCV float32.

    Parameters
    ----------
    face_patch_rgb : np.ndarray
        RGB image patch of shape (H, W, 3). Can be uint8 [0, 255] or float [0.0, 1.0].

    Returns
    -------
    np.ndarray
        CIELAB patch with L* in [0, 100], a* in [-128, 127], b* in [-128, 127].

    Raises
    ------
    TypeError
        If face_patch_rgb is not a numpy ndarray.
    ValueError
        If shape is not (H, W, 3), image is empty, or contains NaNs/Infs/negatives.
    """
    if not isinstance(face_patch_rgb, np.ndarray):
        raise TypeError(f"face_patch_rgb must be a numpy.ndarray, got {type(face_patch_rgb).__name__}")

    if face_patch_rgb.ndim != 3:
        raise ValueError(f"face_patch_rgb must be a 3D array (H, W, 3), got ndim={face_patch_rgb.ndim}")

    if face_patch_rgb.shape[2] != 3:
        raise ValueError(
            f"face_patch_rgb must have exactly 3 color channels (RGB), got shape {face_patch_rgb.shape}"
        )

    h, w, _ = face_patch_rgb.shape
    if h == 0 or w == 0:
        raise ValueError(f"face_patch_rgb must not be empty, got shape {face_patch_rgb.shape}")

    # Validate and normalize input to float32 in [0.0, 1.0] for standard CIELAB conversion
    if face_patch_rgb.dtype == np.uint8:
        patch_norm = face_patch_rgb.astype(np.float32) / 255.0
    elif np.issubdtype(face_patch_rgb.dtype, np.floating):
        if np.any(np.isnan(face_patch_rgb)) or np.any(np.isinf(face_patch_rgb)):
            raise ValueError("face_patch_rgb contains NaN or Infinite values.")
        if np.any(face_patch_rgb < 0.0):
            raise ValueError("face_patch_rgb contains negative pixel values.")
        max_val = float(np.max(face_patch_rgb))
        if max_val > 1.0:
            patch_norm = (face_patch_rgb / 255.0).astype(np.float32)
        else:
            patch_norm = face_patch_rgb.astype(np.float32)
    elif np.issubdtype(face_patch_rgb.dtype, np.integer):
        if np.any(face_patch_rgb < 0):
            raise ValueError("face_patch_rgb contains negative pixel values.")
        patch_norm = (face_patch_rgb.astype(np.float32) / 255.0)
    else:
        raise TypeError(f"Unsupported dtype for face_patch_rgb: {face_patch_rgb.dtype}")

    return cv2.cvtColor(patch_norm, cv2.COLOR_RGB2LAB)


def extract_skin_phototype_multisample(face_patches_rgb: List[np.ndarray]) -> Dict[str, Any]:
    """
    Extracts temporally stabilized skin phototype across a sequence of skin patches or frames.

    Designed for the camera daemon stillness buffer (búfer de quietud). In borderline
    dermatological skin tones (notably at the Type IV / Type V boundary around ITA = 10.0°),
    single-frame measurements can fluctuate (flicker) due to webcam auto-exposure micro-adjustments,
    minor sensor noise, and specular highlights.

    This function:
      1. Validates and converts each patch in the temporal buffer to CIELAB color space.
      2. Extracts median L* and b* coordinates for each individual sample.
      3. Computes the temporal median of L* and b* across the entire multi-sample sequence,
         filtering out transient exposure blinks, motion blur, and localized specular reflections.
      4. Calculates the stabilized Individual Typology Angle (ITA) and maps it to Fitzpatrick (I-VI).
      5. Returns the calibrated melanin threshold and multi-sample diagnostic telemetry.

    Parameters
    ----------
    face_patches_rgb : List[np.ndarray]
        List of RGB image patches or temporal stillness frames of shape (H, W, 3).
        Each patch can be uint8 [0, 255] or float [0.0, 1.0].

    Returns
    -------
    Dict[str, Any]
        Dictionary containing:
          - "phototype": int (1 to 6, stabilized Fitzpatrick scale)
          - "description": str (e.g. "Bronceada / Morena")
          - "clinical_label": str (e.g. "Fototipo IV (Bronceado / Moreno)")
          - "ita": float (stabilized ITA rounded to 2 decimal places)
          - "ita_deg": float (raw stabilized ITA in degrees)
          - "l_star": float (temporal median L* coordinate rounded to 2 decimal places)
          - "b_star": float (temporal median b* coordinate rounded to 2 decimal places)
          - "spot_threshold": float (dynamic melanin segmentation threshold)
          - "sample_count": int (number of frames/patches analyzed)
          - "individual_phototypes": List[int] (per-frame classified phototypes)
          - "individual_itas": List[float] (per-frame ITA values)

    Raises
    ------
    TypeError
        If face_patches_rgb is not a list/sequence or any element is not a numpy ndarray.
    ValueError
        If face_patches_rgb is empty, any patch has invalid dimensions/values,
        or median b* is non-positive.
    """
    if isinstance(face_patches_rgb, (str, bytes)) or not isinstance(face_patches_rgb, (list, tuple)):
        raise TypeError(
            f"face_patches_rgb must be a list of numpy.ndarray, got {type(face_patches_rgb).__name__}"
        )

    if len(face_patches_rgb) == 0:
        raise ValueError("face_patches_rgb must contain at least one patch (got empty sequence).")

    l_medians: List[float] = []
    b_medians: List[float] = []
    individual_itas: List[float] = []
    individual_pts: List[int] = []

    for idx, patch in enumerate(face_patches_rgb):
        if not isinstance(patch, np.ndarray):
            raise TypeError(
                f"Item at index {idx} in face_patches_rgb must be a numpy.ndarray, got {type(patch).__name__}"
            )
        lab_patch = _validate_and_convert_patch_to_lab(patch)
        l_channel = lab_patch[:, :, 0]
        b_channel = lab_patch[:, :, 2]

        sample_l = float(np.median(l_channel))
        sample_b = float(np.median(b_channel))

        # calculate_ita validates b_star > 0
        sample_ita = calculate_ita(sample_l, sample_b)
        sample_pt = classify_fitzpatrick_from_ita(sample_ita)

        l_medians.append(sample_l)
        b_medians.append(sample_b)
        individual_itas.append(sample_ita)
        individual_pts.append(sample_pt)

    # Multi-sample temporal median across the stillness buffer
    temporal_median_l = float(np.median(l_medians))
    temporal_median_b = float(np.median(b_medians))

    stable_ita = calculate_ita(temporal_median_l, temporal_median_b)
    stable_phototype = classify_fitzpatrick_from_ita(stable_ita)
    threshold = get_calibrated_spot_threshold(stable_phototype)

    return {
        "phototype": stable_phototype,
        "description": FITZPATRICK_DESCRIPTIONS[stable_phototype],
        "clinical_label": FITZPATRICK_CLINICAL_NAMES[stable_phototype],
        "ita": round(stable_ita, 2),
        "ita_deg": stable_ita,
        "l_star": round(temporal_median_l, 2),
        "b_star": round(temporal_median_b, 2),
        "spot_threshold": threshold,
        "sample_count": len(face_patches_rgb),
        "individual_itas": [round(x, 2) for x in individual_itas],
        "individual_phototypes": individual_pts,
    }
