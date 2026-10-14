"""
Unit tests for dermatological Fitzpatrick classification and ITA calibration.
Covers calculate_ita, classify_fitzpatrick_from_ita, get_calibrated_spot_threshold,
and extract_skin_phototype across all boundaries, edge cases, and invalid inputs.
"""

import math
import numpy as np
import pytest

from src.domain.fitzpatrick import (
    calculate_ita,
    classify_fitzpatrick_from_ita,
    extract_skin_phototype,
    extract_skin_phototype_multisample,
    get_calibrated_spot_threshold,
    CALIBRATED_SPOT_THRESHOLDS,
    FITZPATRICK_DESCRIPTIONS,
    FITZPATRICK_CLINICAL_NAMES,
)


# ==============================================================================
# 1. Tests for calculate_ita
# ==============================================================================

class TestCalculateIta:
    """Tests for the Individual Typology Angle (ITA) calculation."""

    def test_calculate_ita_known_angles(self):
        """Verify mathematical correctness against analytical geometry solutions."""
        # When L* == 50.0, (L* - 50) == 0, arctan(0) == 0 deg
        assert math.isclose(calculate_ita(50.0, 10.0), 0.0, abs_tol=1e-5)

        # When L* - 50 == b*, ratio is 1.0, arctan(1.0) == 45 deg
        assert math.isclose(calculate_ita(60.0, 10.0), 45.0, abs_tol=1e-5)

        # When L* - 50 == -b*, ratio is -1.0, arctan(-1.0) == -45 deg
        assert math.isclose(calculate_ita(40.0, 10.0), -45.0, abs_tol=1e-5)

        # arctan(sqrt(3)) == 60 deg
        l_60 = 50.0 + 10.0 * math.sqrt(3)
        assert math.isclose(calculate_ita(l_60, 10.0), 60.0, abs_tol=1e-4)

        # arctan(-sqrt(3)) == -60 deg
        l_minus_60 = 50.0 - 10.0 * math.sqrt(3)
        assert math.isclose(calculate_ita(l_minus_60, 10.0), -60.0, abs_tol=1e-4)

    def test_calculate_ita_boundary_l_values(self):
        """Test L* extreme boundaries in [0, 100]."""
        # L* = 100.0 (maximum lightness)
        ita_max_l = calculate_ita(100.0, 20.0)
        expected_max = math.degrees(math.atan((100.0 - 50.0) / 20.0))
        assert math.isclose(ita_max_l, expected_max, rel_tol=1e-5)
        assert ita_max_l > 0

        # L* = 0.0 (minimum lightness)
        ita_min_l = calculate_ita(0.0, 20.0)
        expected_min = math.degrees(math.atan((0.0 - 50.0) / 20.0))
        assert math.isclose(ita_min_l, expected_min, rel_tol=1e-5)
        assert ita_min_l < 0

    def test_calculate_ita_extreme_b_values(self):
        """Test small and large valid b* values."""
        # Very small b* (approaching +90 deg if L* > 50)
        ita_small_b = calculate_ita(80.0, 0.001)
        assert ita_small_b > 89.0
        assert ita_small_b < 90.0

        # Large b* (ratio approaches 0)
        ita_large_b = calculate_ita(55.0, 500.0)
        assert 0.0 < ita_large_b < 1.0

    @pytest.mark.parametrize("invalid_l", [-0.01, -10.0, 100.01, 150.0])
    def test_calculate_ita_l_out_of_range(self, invalid_l):
        """L* outside [0.0, 100.0] must raise ValueError."""
        with pytest.raises(ValueError, match="l_star must be in the range"):
            calculate_ita(invalid_l, 15.0)

    @pytest.mark.parametrize("invalid_b", [0.0, -0.001, -10.0, -100.0])
    def test_calculate_ita_b_zero_or_negative(self, invalid_b):
        """b* <= 0.0 must raise ValueError (division by zero or unnatural skin chroma)."""
        with pytest.raises(ValueError, match="b_star must be strictly positive"):
            calculate_ita(60.0, invalid_b)

    @pytest.mark.parametrize(
        "l_val, b_val",
        [
            (float("nan"), 10.0),
            (60.0, float("nan")),
            (float("inf"), 10.0),
            (60.0, float("inf")),
            (float("-inf"), 10.0),
            (60.0, float("-inf")),
        ],
    )
    def test_calculate_ita_nan_inf(self, l_val, b_val):
        """NaN or Inf inputs must raise ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            calculate_ita(l_val, b_val)

    @pytest.mark.parametrize(
        "l_val, b_val",
        [
            ("60", 10.0),
            (60.0, "10"),
            (None, 10.0),
            (60.0, None),
            (True, 10.0),
            (60.0, False),
            ([60.0], 10.0),
        ],
    )
    def test_calculate_ita_invalid_types(self, l_val, b_val):
        """Non-numeric or boolean types must raise TypeError."""
        with pytest.raises(TypeError, match="must be a numeric value"):
            calculate_ita(l_val, b_val)


# ==============================================================================
# 2. Tests for classify_fitzpatrick_from_ita
# ==============================================================================

class TestClassifyFitzpatrickFromIta:
    """Tests for Fitzpatrick classification according to clinical ITA brackets."""

    @pytest.mark.parametrize(
        "ita_deg, expected_type",
        [
            # Phototype I: ITA > 55°
            (90.0, 1),
            (75.0, 1),
            (55.0001, 1),
            # Phototype II: 41° < ITA <= 55°
            (55.0, 2),
            (50.0, 2),
            (41.0001, 2),
            # Phototype III: 28° < ITA <= 41°
            (41.0, 3),
            (35.0, 3),
            (28.0001, 3),
            # Phototype IV: 10° < ITA <= 28°
            (28.0, 4),
            (20.0, 4),
            (10.0001, 4),
            # Phototype V: -30° < ITA <= 10°
            (10.0, 5),
            (0.0, 5),
            (-15.0, 5),
            (-29.9999, 5),
            # Phototype VI: ITA <= -30°
            (-30.0, 6),
            (-45.0, 6),
            (-75.0, 6),
            (-90.0, 6),
        ],
    )
    def test_classify_all_brackets_and_boundaries(self, ita_deg, expected_type):
        """Verifies exact bracket mapping and inclusive/exclusive boundary rules."""
        assert classify_fitzpatrick_from_ita(ita_deg) == expected_type

    @pytest.mark.parametrize(
        "boundary, lower_type, upper_type",
        [
            (55.0, 2, 1),
            (41.0, 3, 2),
            (28.0, 4, 3),
            (10.0, 5, 4),
            (-30.0, 6, 5),
        ],
    )
    def test_precise_boundary_transitions(self, boundary, lower_type, upper_type):
        """Tests delta-step transitions across all 5 clinical bracket boundaries."""
        eps = 1e-4
        assert classify_fitzpatrick_from_ita(boundary) == lower_type
        assert classify_fitzpatrick_from_ita(boundary + eps) == upper_type

    @pytest.mark.parametrize("out_of_bounds", [90.01, 120.0, -90.01, -180.0])
    def test_classify_out_of_theoretical_bounds(self, out_of_bounds):
        """Angles outside theoretical range [-90.0, 90.0] must raise ValueError."""
        with pytest.raises(ValueError, match="theoretical bounds"):
            classify_fitzpatrick_from_ita(out_of_bounds)

    @pytest.mark.parametrize("invalid_val", [float("nan"), float("inf"), float("-inf")])
    def test_classify_nan_inf(self, invalid_val):
        """NaN or Inf inputs must raise ValueError."""
        with pytest.raises(ValueError, match="finite number"):
            classify_fitzpatrick_from_ita(invalid_val)

    @pytest.mark.parametrize("invalid_type", ["50", None, True, False, [45]])
    def test_classify_invalid_types(self, invalid_type):
        """Non-numeric or boolean types must raise TypeError."""
        with pytest.raises(TypeError, match="must be a numeric value"):
            classify_fitzpatrick_from_ita(invalid_type)


# ==============================================================================
# 3. Tests for get_calibrated_spot_threshold
# ==============================================================================

class TestCalibratedSpotThreshold:
    """Tests for dynamic melanin segmentation threshold calculation."""

    def test_threshold_values_per_phototype(self):
        """Verifies exact calibrated values matching dermatological requirements."""
        # Phototypes I-II must be 0.14
        assert get_calibrated_spot_threshold(1) == 0.14
        assert get_calibrated_spot_threshold(2) == 0.14

        # Phototypes III-VI increase dynamically
        assert get_calibrated_spot_threshold(3) == 0.17
        assert get_calibrated_spot_threshold(4) == 0.20
        assert get_calibrated_spot_threshold(5) == 0.24
        assert get_calibrated_spot_threshold(6) == 0.28

    def test_monotonic_and_bounds(self):
        """Thresholds must be non-decreasing with increasing phototype (1 to 6)."""
        thresholds = [get_calibrated_spot_threshold(pt) for pt in range(1, 7)]
        for i in range(len(thresholds) - 1):
            assert thresholds[i] <= thresholds[i + 1]
            assert 0.10 <= thresholds[i] <= 0.40

    @pytest.mark.parametrize("invalid_pt", [0, 7, -1, 10, 100])
    def test_invalid_phototype_values(self, invalid_pt):
        """Phototypes outside 1..6 must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Fitzpatrick phototype"):
            get_calibrated_spot_threshold(invalid_pt)

    @pytest.mark.parametrize("invalid_type", ["1", 1.5, None, True, False, [2]])
    def test_invalid_phototype_types(self, invalid_type):
        """Non-integer types must raise TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            get_calibrated_spot_threshold(invalid_type)


# ==============================================================================
# 4. Tests for extract_skin_phototype
# ==============================================================================

class TestExtractSkinPhototype:
    """Tests for full pipeline from RGB patch to CIELAB and Fitzpatrick classification."""

    def test_extract_skin_phototype_structure(self):
        """Verify returned dictionary schema and field types."""
        patch = np.full((32, 32, 3), [240, 200, 170], dtype=np.uint8)
        result = extract_skin_phototype(patch)

        assert isinstance(result, dict)
        expected_keys = {
            "phototype",
            "description",
            "clinical_label",
            "ita",
            "ita_deg",
            "l_star",
            "b_star",
            "spot_threshold",
        }
        assert expected_keys.issubset(result.keys())

        assert isinstance(result["phototype"], int)
        assert 1 <= result["phototype"] <= 6
        assert isinstance(result["description"], str)
        assert result["description"] in FITZPATRICK_DESCRIPTIONS.values()
        assert isinstance(result["clinical_label"], str)
        assert isinstance(result["ita"], float)
        assert isinstance(result["l_star"], float)
        assert isinstance(result["b_star"], float)
        assert result["spot_threshold"] == CALIBRATED_SPOT_THRESHOLDS[result["phototype"]]

    def test_extract_phototype_fair_skin(self):
        """Very fair skin tone patch maps to Phototype I."""
        # Light peach skin: high L*, moderate b*
        patch = np.full((20, 20, 3), [255, 230, 205], dtype=np.uint8)
        result = extract_skin_phototype(patch)

        assert result["phototype"] == 1
        assert result["description"] == "Muy Clara"
        assert result["ita"] > 55.0
        assert result["spot_threshold"] == 0.14

    def test_extract_phototype_dark_skin(self):
        """Dark skin tone patch maps to Phototype VI."""
        # Deep dark brown tone: low L*, low-medium b*
        patch = np.full((20, 20, 3), [55, 38, 28], dtype=np.uint8)
        result = extract_skin_phototype(patch)

        assert result["phototype"] == 6
        assert result["description"] == "Muy Oscura"
        assert result["ita"] <= -30.0
        assert result["spot_threshold"] == 0.28

    def test_extract_phototype_intermediate_skin(self):
        """Intermediate skin tone patch maps to Phototype III."""
        # Intermediate beige tone
        patch = np.full((20, 20, 3), [212, 170, 120], dtype=np.uint8)
        result = extract_skin_phototype(patch)

        assert result["phototype"] == 3
        assert result["description"] == "Intermedia"
        assert 28.0 < result["ita"] <= 41.0
        assert result["spot_threshold"] == 0.17

    def test_extract_phototype_float32_normalized_input(self):
        """Verify float32 in [0.0, 1.0] produces identical phototype to equivalent uint8."""
        u8_patch = np.full((16, 16, 3), [220, 180, 140], dtype=np.uint8)
        f32_patch = u8_patch.astype(np.float32) / 255.0

        res_u8 = extract_skin_phototype(u8_patch)
        res_f32 = extract_skin_phototype(f32_patch)

        assert res_u8["phototype"] == res_f32["phototype"]
        assert math.isclose(res_u8["ita"], res_f32["ita"], abs_tol=0.2)

    def test_extract_phototype_float32_unnormalized_input(self):
        """Verify float32 in [0.0, 255.0] is handled and normalized correctly."""
        f32_patch_255 = np.full((16, 16, 3), [220.0, 180.0, 140.0], dtype=np.float32)
        res = extract_skin_phototype(f32_patch_255)
        assert 1 <= res["phototype"] <= 6

    def test_median_robustness_against_specular_highlights(self):
        """
        Verify that using median L* and b* provides resilience against
        isolated specular highlights (e.g. flash reflection / oily skin shine).
        """
        base_patch = np.full((21, 21, 3), [212, 170, 120], dtype=np.uint8)
        clean_res = extract_skin_phototype(base_patch)

        # Inject 10 specular highlight pixels (pure white [255, 255, 255])
        corrupted_patch = base_patch.copy()
        corrupted_patch[:2, :5, :] = 255
        corrupted_res = extract_skin_phototype(corrupted_patch)

        # Median ensures phototype and ITA remain consistent
        assert clean_res["phototype"] == corrupted_res["phototype"]
        assert math.isclose(clean_res["ita"], corrupted_res["ita"], abs_tol=0.5)

    def test_extract_invalid_input_type(self):
        """Passing non-ndarray must raise TypeError."""
        with pytest.raises(TypeError, match="must be a numpy.ndarray"):
            extract_skin_phototype([[200, 150, 100]])

    @pytest.mark.parametrize(
        "invalid_shape",
        [
            (32, 32),          # 2D grayscale
            (1, 32, 32, 3),    # 4D batch
            (32, 32, 1),       # 1 channel
            (32, 32, 4),       # RGBA 4 channels
            (0, 32, 3),        # Empty height
            (32, 0, 3),        # Empty width
        ],
    )
    def test_extract_invalid_shape(self, invalid_shape):
        """Patches with invalid dimensions or channels must raise ValueError."""
        arr = np.zeros(invalid_shape, dtype=np.uint8)
        with pytest.raises(ValueError):
            extract_skin_phototype(arr)

    def test_extract_contains_nan(self):
        """Floating-point patch containing NaN must raise ValueError."""
        arr = np.full((16, 16, 3), 0.5, dtype=np.float32)
        arr[5, 5, 0] = np.nan
        with pytest.raises(ValueError, match="contains NaN or Infinite"):
            extract_skin_phototype(arr)

    def test_extract_contains_negative_values(self):
        """Patch containing negative pixel values must raise ValueError."""
        arr = np.full((16, 16, 3), 0.5, dtype=np.float32)
        arr[5, 5, 0] = -0.1
        with pytest.raises(ValueError, match="contains negative pixel"):
            extract_skin_phototype(arr)

    def test_extract_unnatural_blue_patch(self):
        """Pure blue patch (non-positive b*) must raise ValueError as invalid skin."""
        blue_patch = np.zeros((16, 16, 3), dtype=np.uint8)
        blue_patch[:, :, 2] = 255  # Pure Blue in RGB (channel 2 is B, channel 0 is R)
        with pytest.raises(ValueError, match="b_star must be strictly positive"):
            extract_skin_phototype(blue_patch)


# ==============================================================================
# 5. Tests for extract_skin_phototype_multisample (Temporal Stability Buffer)
# ==============================================================================

class TestExtractSkinPhototypeMultisample:
    """Tests for multi-sample temporal stillness buffer and phototype stabilization."""

    def test_multisample_single_patch_consistency(self):
        """A single-patch list produces results consistent with single-frame extract_skin_phototype."""
        patch = np.full((32, 32, 3), [240, 200, 170], dtype=np.uint8)
        single_res = extract_skin_phototype(patch)
        multi_res = extract_skin_phototype_multisample([patch])

        assert multi_res["phototype"] == single_res["phototype"]
        assert multi_res["description"] == single_res["description"]
        assert multi_res["clinical_label"] == single_res["clinical_label"]
        assert math.isclose(multi_res["ita"], single_res["ita"], abs_tol=1e-2)
        assert math.isclose(multi_res["l_star"], single_res["l_star"], abs_tol=1e-2)
        assert math.isclose(multi_res["b_star"], single_res["b_star"], abs_tol=1e-2)
        assert multi_res["spot_threshold"] == single_res["spot_threshold"]
        assert multi_res["sample_count"] == 1
        assert len(multi_res["individual_phototypes"]) == 1
        assert len(multi_res["individual_itas"]) == 1

    def test_multisample_flicker_mitigation_type4_type5_borderline(self):
        """
        Verify temporal stabilization at the critical Type 4 / Type 5 boundary (ITA ~ 10.0°).
        Simulates webcam auto-exposure fluctuations where single frames oscillate
        between Phototype 4 (ITA > 10.0°) and Phototype 5 (ITA <= 10.0°).
        The multi-sample median must eliminate flicker and yield a stable classification.
        """
        # Patch A: RGB (158, 138, 60) -> ITA ≈ 10.15° -> Phototype 4
        patch_a = np.full((24, 24, 3), [158, 138, 60], dtype=np.uint8)
        # Patch B: RGB (156, 138, 60) -> ITA ≈ 9.96° -> Phototype 5
        patch_b = np.full((24, 24, 3), [156, 138, 60], dtype=np.uint8)
        # Patch C: RGB (160, 138, 60) -> ITA ≈ 10.32° -> Phototype 4
        patch_c = np.full((24, 24, 3), [160, 138, 60], dtype=np.uint8)
        # Patch D: RGB (154, 138, 60) -> ITA ≈ 9.77° -> Phototype 5
        patch_d = np.full((24, 24, 3), [154, 138, 60], dtype=np.uint8)

        # 5-frame sequence with alternating flicker: 4 -> 5 -> 4 -> 5 -> 4
        flicker_sequence = [patch_a, patch_b, patch_c, patch_d, patch_a]

        res = extract_skin_phototype_multisample(flicker_sequence)

        # Confirm that raw single frames indeed oscillate (flicker)
        assert res["individual_phototypes"] == [4, 5, 4, 5, 4]
        assert res["sample_count"] == 5

        # Temporal median must be stably Phototype 4 without flicker
        assert res["phototype"] == 4
        assert res["description"] == FITZPATRICK_DESCRIPTIONS[4]
        assert res["ita"] > 10.0
        assert res["spot_threshold"] == CALIBRATED_SPOT_THRESHOLDS[4]

    def test_multisample_flicker_mitigation_type5_dominant(self):
        """
        Verify that when Type 5 frames dominate the temporal sequence (e.g. 3 of 5 frames),
        the multi-sample temporal median cleanly converges to Phototype 5.
        """
        patch_type4 = np.full((20, 20, 3), [158, 138, 60], dtype=np.uint8)  # ITA ~ 10.15° -> Type 4
        patch_type5_a = np.full((20, 20, 3), [156, 138, 60], dtype=np.uint8)  # ITA ~ 9.96° -> Type 5
        patch_type5_b = np.full((20, 20, 3), [154, 138, 60], dtype=np.uint8)  # ITA ~ 9.77° -> Type 5

        # Sequence: [5, 4, 5, 4, 5] -> 3 Type 5 vs 2 Type 4
        seq = [patch_type5_a, patch_type4, patch_type5_b, patch_type4, patch_type5_a]
        res = extract_skin_phototype_multisample(seq)

        assert res["individual_phototypes"] == [5, 4, 5, 4, 5]
        assert res["phototype"] == 5
        assert res["description"] == FITZPATRICK_DESCRIPTIONS[5]
        assert res["ita"] <= 10.0
        assert res["spot_threshold"] == CALIBRATED_SPOT_THRESHOLDS[5]

    def test_multisample_transient_outlier_rejection(self):
        """
        Verify that a transient corrupted frame (e.g. sudden camera flash or specular reflection)
        is completely rejected by temporal median filtering.
        """
        # Baseline intermediate skin patch (Phototype III)
        base_patch = np.full((20, 20, 3), [212, 170, 120], dtype=np.uint8)
        clean_res = extract_skin_phototype(base_patch)

        # Corrupted frame with intense specular blowout
        corrupted_frame = np.full((20, 20, 3), [255, 255, 250], dtype=np.uint8)

        # 5-frame sequence with 1 corrupted frame
        sequence = [base_patch, base_patch, corrupted_frame, base_patch, base_patch]
        multi_res = extract_skin_phototype_multisample(sequence)

        assert multi_res["phototype"] == clean_res["phototype"]
        assert multi_res["phototype"] == 3
        assert math.isclose(multi_res["ita"], clean_res["ita"], abs_tol=0.5)

    def test_multisample_fair_skin_sequence(self):
        """Sequence of very fair skin frames stably classifies as Phototype I."""
        patch = np.full((16, 16, 3), [255, 230, 205], dtype=np.uint8)
        res = extract_skin_phototype_multisample([patch] * 4)

        assert res["phototype"] == 1
        assert res["description"] == "Muy Clara"
        assert res["ita"] > 55.0
        assert res["sample_count"] == 4
        assert all(pt == 1 for pt in res["individual_phototypes"])

    def test_multisample_dark_skin_sequence(self):
        """Sequence of deeply pigmented frames stably classifies as Phototype VI."""
        patch = np.full((16, 16, 3), [55, 38, 28], dtype=np.uint8)
        res = extract_skin_phototype_multisample([patch] * 6)

        assert res["phototype"] == 6
        assert res["description"] == "Muy Oscura"
        assert res["ita"] <= -30.0
        assert res["sample_count"] == 6
        assert all(pt == 6 for pt in res["individual_phototypes"])

    def test_multisample_mixed_dtypes_and_resolutions(self):
        """Verify support for mixed uint8 and float32 patches of varying spatial dimensions."""
        p1 = np.full((20, 20, 3), [212, 170, 120], dtype=np.uint8)
        p2 = (np.full((32, 28, 3), [212, 170, 120], dtype=np.float32) / 255.0)
        p3 = np.full((16, 24, 3), [212.0, 170.0, 120.0], dtype=np.float32)

        res = extract_skin_phototype_multisample([p1, p2, p3])
        assert res["phototype"] == 3
        assert res["sample_count"] == 3

    def test_multisample_empty_sequence_raises(self):
        """Passing an empty sequence must raise ValueError."""
        with pytest.raises(ValueError, match="at least one patch"):
            extract_skin_phototype_multisample([])

    @pytest.mark.parametrize("invalid_input", ["not_a_list", 123, None, True, np.zeros((32, 32, 3))])
    def test_multisample_invalid_container_types(self, invalid_input):
        """Non-list/tuple input must raise TypeError."""
        with pytest.raises(TypeError, match="must be a list"):
            extract_skin_phototype_multisample(invalid_input)

    def test_multisample_non_ndarray_item_raises(self):
        """A list containing a non-ndarray element must raise TypeError."""
        valid_patch = np.full((16, 16, 3), [212, 170, 120], dtype=np.uint8)
        with pytest.raises(TypeError, match="must be a numpy.ndarray"):
            extract_skin_phototype_multisample([valid_patch, "corrupted_element", valid_patch])

    @pytest.mark.parametrize(
        "invalid_patch_shape",
        [
            (32, 32),          # 2D
            (1, 32, 32, 3),    # 4D
            (32, 32, 4),       # 4 channels
            (0, 32, 3),        # empty height
        ],
    )
    def test_multisample_invalid_patch_shape_raises(self, invalid_patch_shape):
        """A list containing a patch with invalid shape must raise ValueError."""
        valid_patch = np.full((16, 16, 3), [212, 170, 120], dtype=np.uint8)
        invalid_patch = np.zeros(invalid_patch_shape, dtype=np.uint8)
        with pytest.raises(ValueError):
            extract_skin_phototype_multisample([valid_patch, invalid_patch])

    def test_multisample_patch_with_nan_raises(self):
        """A list containing a patch with NaN must raise ValueError."""
        valid_patch = np.full((16, 16, 3), [212, 170, 120], dtype=np.uint8)
        nan_patch = np.full((16, 16, 3), 0.5, dtype=np.float32)
        nan_patch[2, 2, 0] = np.nan
        with pytest.raises(ValueError, match="contains NaN or Infinite"):
            extract_skin_phototype_multisample([valid_patch, nan_patch])

    def test_multisample_patch_with_negative_raises(self):
        """A list containing a patch with negative pixel values must raise ValueError."""
        valid_patch = np.full((16, 16, 3), [212, 170, 120], dtype=np.uint8)
        neg_patch = np.full((16, 16, 3), 0.5, dtype=np.float32)
        neg_patch[2, 2, 0] = -0.5
        with pytest.raises(ValueError, match="contains negative pixel"):
            extract_skin_phototype_multisample([valid_patch, neg_patch])

    def test_multisample_patch_with_unnatural_blue_raises(self):
        """A list containing a pure blue patch (non-positive b*) must raise ValueError."""
        valid_patch = np.full((16, 16, 3), [212, 170, 120], dtype=np.uint8)
        blue_patch = np.zeros((16, 16, 3), dtype=np.uint8)
        blue_patch[:, :, 2] = 255
        with pytest.raises(ValueError, match="b_star must be strictly positive"):
            extract_skin_phototype_multisample([valid_patch, blue_patch])
