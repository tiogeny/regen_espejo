"""
Módulo de utilidades transversales para Proyecto Derma.
"""

from src.utils.calibration_store import (
    load_calibration_offset,
    save_calibration_offset,
    DEFAULT_CALIBRATION_FILE,
)

__all__ = [
    "load_calibration_offset",
    "save_calibration_offset",
    "DEFAULT_CALIBRATION_FILE",
]
