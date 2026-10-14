"""
Pruebas unitarias para detección de hardware on-edge, selección de modelos INT8
con fallback transparente a FP32 y utilidades de captura de cámara multiplataforma
(Raspberry Pi OS / V4L2 vs Windows DirectShow).
"""

import os
import sys
import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import cv2

from src.inference.hardware_detect import (
    is_raspberry_pi,
    get_cpu_temperature,
    get_system_memory,
    is_arm_architecture,
    get_hardware_profile,
    get_rpi_model_name,
)
from src.inference.pipeline import (
    should_use_int8,
    resolve_model_path,
    InferenceEngine,
    MOBILENET_AGE_INT8,
    UNET_SPOT_INT8,
    AGE_FP32_DEFAULT,
    SPOT_FP32_DEFAULT,
)
from src.utils.camera_utils import (
    get_preferred_camera_backend,
    get_camera_capture,
)


# ============================================================================
# 1. Pruebas de Detección de Hardware On-Edge (hardware_detect.py)
# ============================================================================

class TestHardwareDetection:
    """Valida la identificación del hardware del sistema embebido y telemetría térmica."""

    def test_is_raspberry_pi_env_override(self, monkeypatch):
        """Verifica que la variable de entorno DERMA_FORCE_RPI fuerce el resultado."""
        monkeypatch.setenv("DERMA_FORCE_RPI", "1")
        assert is_raspberry_pi() is True

        monkeypatch.setenv("DERMA_FORCE_RPI", "true")
        assert is_raspberry_pi() is True

        monkeypatch.setenv("DERMA_FORCE_RPI", "yes")
        assert is_raspberry_pi() is True

        monkeypatch.setenv("DERMA_FORCE_RPI", "0")
        assert is_raspberry_pi() is False

        monkeypatch.setenv("DERMA_FORCE_RPI", "false")
        assert is_raspberry_pi() is False

    def test_is_raspberry_pi_device_tree(self, monkeypatch, tmp_path):
        """Verifica la detección vía /proc/device-tree/model o /sys/firmware/devicetree/base/model."""
        monkeypatch.delenv("DERMA_FORCE_RPI", raising=False)

        fake_dt = tmp_path / "model"
        fake_dt.write_text("Raspberry Pi 5 Model B Rev 1.0\x00", encoding="utf-8")

        # Mocking Path.exists y Path.read_text para los paths de device-tree
        original_exists = Path.exists
        original_read_text = Path.read_text

        def mock_exists(self):
            if str(self).replace("\\", "/") in [
                "/proc/device-tree/model",
                "/sys/firmware/devicetree/base/model",
            ]:
                return True
            return original_exists(self)

        def mock_read_text(self, *args, **kwargs):
            if str(self).replace("\\", "/") in [
                "/proc/device-tree/model",
                "/sys/firmware/devicetree/base/model",
            ]:
                return "Raspberry Pi 5 Model B Rev 1.0\x00"
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "exists", mock_exists)
        monkeypatch.setattr(Path, "read_text", mock_read_text)

        assert is_raspberry_pi() is True
        assert get_rpi_model_name() == "Raspberry Pi 5 Model B Rev 1.0"

    def test_is_raspberry_pi_cpuinfo(self, monkeypatch):
        """Verifica detección de RPi a través de /proc/cpuinfo."""
        monkeypatch.delenv("DERMA_FORCE_RPI", raising=False)

        original_exists = Path.exists
        original_read_text = Path.read_text

        def mock_exists(self):
            p = str(self).replace("\\", "/")
            if p == "/proc/cpuinfo":
                return True
            if p in ["/proc/device-tree/model", "/sys/firmware/devicetree/base/model"]:
                return False
            return original_exists(self)

        def mock_read_text(self, *args, **kwargs):
            p = str(self).replace("\\", "/")
            if p == "/proc/cpuinfo":
                return "Hardware\t: BCM2712\nModel\t: Raspberry Pi 5\n"
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "exists", mock_exists)
        monkeypatch.setattr(Path, "read_text", mock_read_text)
        # Asegurar que vcgencmd no dé falso positivo
        monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=FileNotFoundError))

        assert is_raspberry_pi() is True

    def test_is_raspberry_pi_vcgencmd(self, monkeypatch):
        """Verifica detección por comando vcgencmd."""
        monkeypatch.delenv("DERMA_FORCE_RPI", raising=False)

        # Sin device-tree ni cpuinfo
        original_exists = Path.exists

        def mock_exists(self):
            p = str(self).replace("\\", "/")
            if p in ["/proc/device-tree/model", "/sys/firmware/devicetree/base/model", "/proc/cpuinfo"]:
                return False
            return original_exists(self)

        monkeypatch.setattr(Path, "exists", mock_exists)

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "version 1.0 (release)\n"
        monkeypatch.setattr(subprocess, "run", MagicMock(return_value=mock_res))

        assert is_raspberry_pi() is True

    def test_is_arm_architecture(self):
        """Verifica la clasificación precisa de arquitecturas de CPU."""
        assert is_arm_architecture("aarch64") is True
        assert is_arm_architecture("arm64") is True
        assert is_arm_architecture("armv7l") is True
        assert is_arm_architecture("armv8l") is True
        assert is_arm_architecture("ARM") is True

        assert is_arm_architecture("AMD64") is False
        assert is_arm_architecture("x86_64") is False
        assert is_arm_architecture("i386") is False

    def test_get_cpu_temperature_linux_sysfs(self, monkeypatch):
        """Verifica la lectura de temperatura mediante Linux SysFS."""
        original_exists = Path.exists
        original_read_text = Path.read_text

        def mock_exists(self):
            if str(self).replace("\\", "/") == "/sys/class/thermal/thermal_zone0/temp":
                return True
            return original_exists(self)

        def mock_read_text(self, *args, **kwargs):
            if str(self).replace("\\", "/") == "/sys/class/thermal/thermal_zone0/temp":
                return "48500\n"  # 48.5 °C en miligrados
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "exists", mock_exists)
        monkeypatch.setattr(Path, "read_text", mock_read_text)

        temp, source = get_cpu_temperature()
        assert temp == 48.5
        assert "Linux SysFS" in source

    def test_get_cpu_temperature_vcgencmd(self, monkeypatch):
        """Verifica la lectura de temperatura mediante vcgencmd."""
        original_exists = Path.exists

        def mock_exists(self):
            if "thermal_zone" in str(self):
                return False
            return original_exists(self)

        monkeypatch.setattr(Path, "exists", mock_exists)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "temp=53.2'C\n"
        monkeypatch.setattr(subprocess, "run", MagicMock(return_value=mock_proc))

        temp, source = get_cpu_temperature()
        assert temp == 53.2
        assert "vcgencmd" in source

    def test_get_system_memory_linux(self, monkeypatch):
        """Verifica la lectura de memoria mediante /proc/meminfo en plataformas Linux."""
        original_exists = Path.exists

        def mock_exists(self):
            if str(self).replace("\\", "/") == "/proc/meminfo":
                return True
            return original_exists(self)

        meminfo_content = (
            "MemTotal:        8192000 kB\n"
            "MemFree:         4096000 kB\n"
            "MemAvailable:    6144000 kB\n"
        )

        from io import StringIO
        original_open = Path.open

        def mock_open(self, mode="r", *args, **kwargs):
            if str(self).replace("\\", "/") == "/proc/meminfo":
                return StringIO(meminfo_content)
            return original_open(self, mode, *args, **kwargs)

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(Path, "exists", mock_exists)
        monkeypatch.setattr(Path, "open", mock_open)

        mem = get_system_memory()
        assert mem["total_mb"] == round(8192000 / 1024.0, 2)
        assert mem["available_mb"] == round(6144000 / 1024.0, 2)

    def test_get_hardware_profile_structure(self, monkeypatch):
        """Verifica la completitud del contrato de datos de get_hardware_profile."""
        monkeypatch.setenv("DERMA_FORCE_RPI", "1")
        monkeypatch.setattr(platform, "machine", lambda: "aarch64")

        profile = get_hardware_profile()

        assert isinstance(profile, dict)
        assert profile["is_raspberry_pi"] is True
        assert profile["arch"] == "aarch64"
        assert profile["is_arm"] is True
        assert profile["cpu_count"] >= 1
        assert "thermal" in profile
        assert isinstance(profile["thermal"], dict)
        assert "max_limit_celsius" in profile["thermal"]
        assert profile["thermal"]["max_limit_celsius"] == 75.0
        assert "thermal_throttled" in profile["thermal"]

    def test_get_hardware_profile_thermal_throttling_detection(self, monkeypatch):
        """Verifica que temperaturas superiores al SLA clínico (75.0 °C) activen thermal_throttled."""
        monkeypatch.setattr(
            "src.inference.hardware_detect.get_cpu_temperature",
            lambda: (78.5, "Mock Sensor"),
        )
        profile = get_hardware_profile()
        assert profile["thermal"]["supported"] is True
        assert profile["thermal"]["temperature_celsius"] == 78.5
        assert profile["thermal"]["thermal_throttled"] is True


# ============================================================================
# 2. Pruebas de Selección de Modelos y Fallback Transparente (pipeline.py)
# ============================================================================

class TestModelSelectorAndFallback:
    """Valida la selección automática de modelos INT8 y fallback a FP32."""

    def test_should_use_int8_environment(self, monkeypatch):
        """Verifica que DERMA_USE_INT8=1 active la preferencia por INT8."""
        monkeypatch.setenv("DERMA_USE_INT8", "1")
        assert should_use_int8() is True

        monkeypatch.setenv("DERMA_USE_INT8", "true")
        assert should_use_int8() is True

        monkeypatch.delenv("DERMA_USE_INT8", raising=False)
        monkeypatch.setattr("src.inference.hardware_detect.is_raspberry_pi", lambda: False)
        assert should_use_int8() is False

    def test_should_use_int8_on_raspberry_pi(self, monkeypatch):
        """Verifica que ejecutarse sobre Raspberry Pi active automáticamente INT8."""
        monkeypatch.delenv("DERMA_USE_INT8", raising=False)
        monkeypatch.setattr("src.inference.hardware_detect.is_raspberry_pi", lambda: True)
        assert should_use_int8() is True

    def test_resolve_model_path_int8_selected_when_files_exist(self, tmp_path):
        """Si los archivos INT8 existen y se prefiere INT8, deben ser seleccionados."""
        (tmp_path / MOBILENET_AGE_INT8).touch()
        (tmp_path / UNET_SPOT_INT8).touch()
        (tmp_path / AGE_FP32_DEFAULT).touch()
        (tmp_path / SPOT_FP32_DEFAULT).touch()

        age_path, age_prec = resolve_model_path("age", models_dir=tmp_path, prefer_int8=True)
        assert age_path.name == MOBILENET_AGE_INT8
        assert age_prec == "INT8"

        spot_path, spot_prec = resolve_model_path("spot", models_dir=tmp_path, prefer_int8=True)
        assert spot_path.name == UNET_SPOT_INT8
        assert spot_prec == "INT8"

    def test_resolve_model_path_transparent_fallback_to_fp32(self, tmp_path):
        """
        Si se prefiere INT8 pero los archivos INT8 NO existen,
        debe ocurrir un fallback automático y transparente a los modelos FP32.
        """
        (tmp_path / AGE_FP32_DEFAULT).touch()
        (tmp_path / SPOT_FP32_DEFAULT).touch()

        # Los archivos INT8 no existen en tmp_path
        assert not (tmp_path / MOBILENET_AGE_INT8).exists()
        assert not (tmp_path / UNET_SPOT_INT8).exists()

        age_path, age_prec = resolve_model_path("age", models_dir=tmp_path, prefer_int8=True)
        assert age_path.name == AGE_FP32_DEFAULT
        assert age_prec == "FP32_FALLBACK"

        spot_path, spot_prec = resolve_model_path("spot", models_dir=tmp_path, prefer_int8=True)
        assert spot_path.name == SPOT_FP32_DEFAULT
        assert spot_prec == "FP32_FALLBACK"

    def test_resolve_model_path_fp32_when_int8_not_requested(self, tmp_path):
        """Cuando no se solicita INT8, se selecciona FP32 directamente."""
        (tmp_path / MOBILENET_AGE_INT8).touch()
        (tmp_path / UNET_SPOT_INT8).touch()
        (tmp_path / AGE_FP32_DEFAULT).touch()
        (tmp_path / SPOT_FP32_DEFAULT).touch()

        age_path, age_prec = resolve_model_path("age", models_dir=tmp_path, prefer_int8=False)
        assert age_path.name == AGE_FP32_DEFAULT
        assert age_prec == "FP32"

        spot_path, spot_prec = resolve_model_path("spot", models_dir=tmp_path, prefer_int8=False)
        assert spot_path.name == SPOT_FP32_DEFAULT
        assert spot_prec == "FP32"

    def test_resolve_model_path_invalid_kind(self, tmp_path):
        """Verifica que un tipo de modelo desconocido levante ValueError."""
        with pytest.raises(ValueError, match="Tipo de modelo no reconocido"):
            resolve_model_path("cardiology", models_dir=tmp_path)

    def test_inference_engine_int8_status(self, tmp_path):
        """Verifica que InferenceEngine reporte adecuadamente el estado de precisión."""
        (tmp_path / MOBILENET_AGE_INT8).touch()
        (tmp_path / UNET_SPOT_INT8).touch()

        engine = InferenceEngine(models_dir=tmp_path, prefer_int8=True)
        assert engine.is_using_int8 is True
        status = engine.model_status
        assert status["age"]["precision"] == "INT8"
        assert status["spot"]["precision"] == "INT8"

    def test_inference_engine_fallback_status(self, tmp_path):
        """Verifica que InferenceEngine reporte fallback transparente a FP32."""
        (tmp_path / AGE_FP32_DEFAULT).touch()
        (tmp_path / SPOT_FP32_DEFAULT).touch()

        engine = InferenceEngine(models_dir=tmp_path, prefer_int8=True)
        assert engine.is_using_int8 is False
        status = engine.model_status
        assert status["age"]["precision"] == "FP32_FALLBACK"
        assert status["spot"]["precision"] == "FP32_FALLBACK"

    def test_inference_engine_custom_paths(self, tmp_path):
        """Verifica el paso explícito de rutas personalizadas."""
        p_age = tmp_path / "custom_age.onnx"
        p_spot = tmp_path / "custom_spot.onnx"
        p_age.touch()
        p_spot.touch()

        engine = InferenceEngine(age_model_path=p_age, spot_model_path=p_spot)
        assert engine.age_precision == "CUSTOM"
        assert engine.spot_precision == "CUSTOM"
        assert engine.age_model_path == p_age
        assert engine.spot_model_path == p_spot


# ============================================================================
# 3. Pruebas de Captura de Cámara Multiplataforma (camera_utils.py)
# ============================================================================

class TestCameraUtilities:
    """Valida la configuración de captura con V4L2 MJPG en Linux y DSHOW en Windows."""

    def test_get_preferred_camera_backend_linux(self, monkeypatch):
        """En Linux debe seleccionar cv2.CAP_V4L2."""
        monkeypatch.setattr(sys, "platform", "linux")
        backend = get_preferred_camera_backend()
        assert backend == cv2.CAP_V4L2

    def test_get_preferred_camera_backend_windows(self, monkeypatch):
        """En Windows debe seleccionar cv2.CAP_DSHOW."""
        monkeypatch.setattr(sys, "platform", "win32")
        backend = get_preferred_camera_backend()
        assert backend == cv2.CAP_DSHOW

    def test_get_preferred_camera_backend_other(self, monkeypatch):
        """En otros sistemas operativos (macOS, etc.) debe usar cv2.CAP_ANY."""
        monkeypatch.setattr(sys, "platform", "darwin")
        backend = get_preferred_camera_backend()
        assert backend == cv2.CAP_ANY

    def test_get_camera_capture_linux_v4l2_mjpg_configured(self, monkeypatch):
        """
        Verifica que en Linux/Raspberry Pi se cree la captura con CAP_V4L2
        y se configure FourCC en MJPG.
        """
        monkeypatch.setattr(sys, "platform", "linux")

        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_videocapture_ctor = MagicMock(return_value=mock_cap)
        monkeypatch.setattr(cv2, "VideoCapture", mock_videocapture_ctor)

        expected_fourcc = float(cv2.VideoWriter_fourcc(*"MJPG"))

        cap = get_camera_capture(camera_index=2, width=1280, height=720, fps=30)

        # 1. Verificación de backend
        mock_videocapture_ctor.assert_called_once_with(2, cv2.CAP_V4L2)

        # 2. Verificación de configuración FourCC MJPG
        mock_cap.set.assert_any_call(cv2.CAP_PROP_FOURCC, expected_fourcc)

        # 3. Verificación de resolución y framerate
        mock_cap.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 1280.0)
        mock_cap.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 720.0)
        mock_cap.set.assert_any_call(cv2.CAP_PROP_FPS, 30.0)

        assert cap is mock_cap

    def test_get_camera_capture_windows_dshow(self, monkeypatch):
        """
        Verifica que en Windows se cree la captura con CAP_DSHOW y no se fuerce MJPG.
        """
        monkeypatch.setattr(sys, "platform", "win32")

        mock_cap = MagicMock(spec=cv2.VideoCapture)
        mock_videocapture_ctor = MagicMock(return_value=mock_cap)
        monkeypatch.setattr(cv2, "VideoCapture", mock_videocapture_ctor)

        cap = get_camera_capture(camera_index=0, width=640, height=480)

        # Verificación de backend
        mock_videocapture_ctor.assert_called_once_with(0, cv2.CAP_DSHOW)

        # En Windows no debe configurarse FourCC MJPG de manera obligatoria
        set_calls = [c[0][0] for c in mock_cap.set.call_args_list]
        assert cv2.CAP_PROP_FOURCC not in set_calls

        # Verificación de dimensiones
        mock_cap.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 640.0)
        mock_cap.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 480.0)

        assert cap is mock_cap
