"""
Módulo de Detección e Identificación de Hardware On-Edge (Raspberry Pi 5 / ARM Cortex-A76).

Proporciona telemetría del sistema embebido:
- Detección precisa de plataforma Raspberry Pi (Pi 5, Pi 4, BCM2712, BCM2711).
- Arquitecturas de microprocesador (ARM64 / aarch64 vs x86_64).
- Conteo de núcleos de cómputo CPU.
- Telemetría de memoria RAM residente (Total y Disponible).
- Sensores térmicos del SoC con umbrales clínicos de seguridad (<= 75.0 °C).
"""

import os
import sys
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from src.config import MAX_THERMAL_SOC_CELSIUS


def is_raspberry_pi() -> bool:
    """
    Determina si la aplicación se está ejecutando sobre hardware Raspberry Pi.
    
    Verifica de forma progresiva:
    1. Variable de entorno de anulación `DERMA_FORCE_RPI` (para entornos de test o emulación).
    2. Árbol de dispositivos Linux `/proc/device-tree/model` o `/sys/firmware/devicetree/base/model`.
    3. Registros de CPU en `/proc/cpuinfo` (modelo BCM o Raspberry Pi).
    4. Disponibilidad del comando oficial `vcgencmd`.
    """
    # 1. Override mediante variable de entorno
    force_env = os.getenv("DERMA_FORCE_RPI", "").strip().lower()
    if force_env in ("1", "true", "yes"):
        return True
    if force_env in ("0", "false", "no"):
        return False

    # 2. Linux Device Tree (estándar en Raspberry Pi OS)
    devicetree_paths = [
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model"),
    ]
    for dt_path in devicetree_paths:
        try:
            if dt_path.exists():
                content = dt_path.read_text(encoding="utf-8", errors="ignore")
                if "raspberry pi" in content.lower():
                    return True
        except Exception:
            pass

    # 3. Inspección de /proc/cpuinfo
    cpuinfo_path = Path("/proc/cpuinfo")
    try:
        if cpuinfo_path.exists():
            content = cpuinfo_path.read_text(encoding="utf-8", errors="ignore").lower()
            if "raspberry pi" in content or "bcm27" in content or "bcm28" in content:
                return True
    except Exception:
        pass

    # 4. Verificación de comando nativo vcgencmd
    try:
        res = subprocess.run(
            ["vcgencmd", "version"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    return False


def get_cpu_temperature() -> Tuple[Optional[float], str]:
    """
    Lee la temperatura térmica actual del SoC/CPU en grados Celsius.
    
    Fuentes soportadas:
    - Linux SysFS (/sys/class/thermal/thermal_zone*/temp)
    - Raspberry Pi vcgencmd (vcgencmd measure_temp)
    - Windows WMI ACPI ThermalZone (si el hardware y BIOS lo exponen)
    """
    # 1. Linux SysFS (Raspberry Pi 5 / Linux embebido)
    thermal_paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
        "/sys/class/thermal/thermal_zone1/temp",
    ]
    for tp in thermal_paths:
        try:
            p = Path(tp)
            if p.exists():
                raw_val = float(p.read_text().strip())
                # En Linux sysfs el valor se reporta habitualmente en miligrados Celsius
                temp_c = raw_val / 1000.0 if raw_val > 200 else raw_val
                if 0.0 < temp_c < 125.0:
                    return round(temp_c, 2), f"Linux SysFS ({tp})"
        except Exception:
            pass

    # 2. Raspberry Pi CLI vcgencmd
    try:
        res = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode == 0 and res.stdout:
            # Formato típico: "temp=47.2'C"
            txt = res.stdout.strip().replace("temp=", "").replace("'C", "")
            temp_c = float(txt)
            if 0.0 < temp_c < 125.0:
                return round(temp_c, 2), "Raspberry Pi vcgencmd"
    except Exception:
        pass

    # 3. Windows WMI ACPI
    if sys.platform == "win32":
        try:
            cmd = (
                'powershell -NoProfile -Command "'
                "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
                '-ErrorAction SilentlyContinue | Select-Object -ExpandProperty CurrentTemperature"'
            )
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                raw = float(res.stdout.strip().split()[0])
                # WMI entrega la temperatura en décimas de Kelvin
                temp_c = (raw - 2732.0) / 10.0
                if 0.0 < temp_c < 125.0:
                    return round(temp_c, 2), "Windows WMI MSAcpi_ThermalZoneTemperature"
        except Exception:
            pass

    return None, "Sensor térmico no accesible directamente"


def get_system_memory() -> Dict[str, Optional[float]]:
    """
    Obtiene la memoria RAM total y disponible del sistema en MegaBytes (MB)
    sin requerir dependencias externas como psutil.
    """
    total_mb: Optional[float] = None
    available_mb: Optional[float] = None

    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_mb = round(stat.ullTotalPhys / (1024.0 * 1024.0), 2)
                available_mb = round(stat.ullAvailPhys / (1024.0 * 1024.0), 2)
        except Exception:
            pass
    else:
        # Linux /proc/meminfo
        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.exists():
            try:
                mem_dict: Dict[str, float] = {}
                with meminfo_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip().split()[0]
                            mem_dict[key] = float(val)
                if "MemTotal" in mem_dict:
                    total_mb = round(mem_dict["MemTotal"] / 1024.0, 2)
                if "MemAvailable" in mem_dict:
                    available_mb = round(mem_dict["MemAvailable"] / 1024.0, 2)
                elif "MemFree" in mem_dict:
                    available_mb = round(mem_dict["MemFree"] / 1024.0, 2)
            except Exception:
                pass

    return {
        "total_mb": total_mb,
        "available_mb": available_mb,
    }


def is_arm_architecture(machine_str: Optional[str] = None) -> bool:
    """Indica si la arquitectura del procesador corresponde a la familia ARM/aarch64."""
    arch = (machine_str or platform.machine()).lower()
    return arch in ("aarch64", "arm64", "armv7l", "armv8l", "armv6l", "arm")


def get_rpi_model_name() -> Optional[str]:
    """Extrae el nombre descriptivo del modelo de Raspberry Pi si está presente."""
    dt_paths = [
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model"),
    ]
    for p in dt_paths:
        try:
            if p.exists():
                text = p.read_text(encoding="utf-8", errors="ignore").strip().replace("\x00", "")
                if text:
                    return text
        except Exception:
            pass
    return None


def get_hardware_profile() -> Dict[str, Any]:
    """
    Retorna el perfil integral de hardware on-edge:
    - `is_raspberry_pi`: Booleano de detección de placa RPi.
    - `device_model`: Nombre del modelo detectado o None.
    - `arch`: Arquitectura de máquina (ej. 'aarch64', 'AMD64').
    - `is_arm`: Booleano que confirma familia ARM/aarch64.
    - `cpu_count`: Número de núcleos de cómputo lógicos disponibles.
    - `memory_total_mb`: Memoria RAM física total en MB.
    - `memory_available_mb`: Memoria RAM disponible en MB.
    - `thermal`: Información del subsistema térmico (soporte, temperatura, origen, throttle).
    """
    is_rpi = is_raspberry_pi()
    arch = platform.machine()
    is_arm = is_arm_architecture(arch)
    cpu_cores = os.cpu_count() or 1
    mem_info = get_system_memory()
    temp_val, temp_source = get_cpu_temperature()

    thermal_supported = temp_val is not None
    thermal_throttled = bool(temp_val is not None and temp_val > MAX_THERMAL_SOC_CELSIUS)

    device_model = get_rpi_model_name()
    if is_rpi and not device_model:
        device_model = "Raspberry Pi (Modelo genérico / Emulado)"

    return {
        "is_raspberry_pi": is_rpi,
        "device_model": device_model,
        "os": platform.system(),
        "arch": arch,
        "is_arm": is_arm,
        "cpu_count": cpu_cores,
        "memory_total_mb": mem_info.get("total_mb"),
        "memory_available_mb": mem_info.get("available_mb"),
        "thermal": {
            "supported": thermal_supported,
            "temperature_celsius": temp_val,
            "source": temp_source,
            "max_limit_celsius": float(MAX_THERMAL_SOC_CELSIUS),
            "thermal_throttled": thermal_throttled,
        },
    }
