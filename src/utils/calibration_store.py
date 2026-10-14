"""
Almacenamiento y persistencia del offset de calibración de edad para cámara clínica.

Proyecto Derma - Subsistema de Calibración Óptica y Sesgo de Hardware.
Permite persistir y recuperar dinámicamente el sesgo etario (offset) determinado
por calibración con cámara dermatoscópica o en caliente desde la interfaz táctica.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

# Ruta por defecto según especificación: data/config/calibracion_camara.json
DEFAULT_CONFIG_DIR: Path = DATA_DIR / "config"
DEFAULT_CALIBRATION_FILE: Path = DEFAULT_CONFIG_DIR / "calibracion_camara.json"
DEFAULT_OFFSET: float = 2.5


def load_calibration_offset(
    default_offset: float = DEFAULT_OFFSET,
    filepath: Optional[Path] = None,
) -> float:
    """
    Carga el offset de calibración de edad biológica desde el archivo JSON de configuración.

    Si el archivo no existe, está corrupto o carece del campo esperado,
    retorna de forma segura el valor por defecto configurado (+2.5 años).

    Args:
        default_offset: Valor de respaldo en caso de ausencia o fallo de lectura. Default: 2.5.
        filepath: Ruta opcional personalizada al archivo JSON de calibración.

    Returns:
        float: Offset de calibración en años (puede ser positivo, negativo o cero).
    """
    target_path = filepath if filepath is not None else DEFAULT_CALIBRATION_FILE

    if not target_path.exists():
        logger.debug(
            "Archivo de calibración '%s' no encontrado. Usando valor por defecto: %.1f",
            target_path,
            default_offset,
        )
        return float(default_offset)

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            # Prioridad de claves: 'age_offset', 'offset', 'calibracion_offset'
            if "age_offset" in data:
                return float(data["age_offset"])
            elif "offset" in data:
                return float(data["offset"])
            elif "calibracion_offset" in data:
                return float(data["calibracion_offset"])
            else:
                logger.warning(
                    "Archivo de calibración '%s' no contiene claves reconocidas ('age_offset'/'offset'). "
                    "Retornando default: %.1f",
                    target_path,
                    default_offset,
                )
                return float(default_offset)
        elif isinstance(data, (int, float)):
            return float(data)
        else:
            logger.warning(
                "Estructura JSON inválida en '%s'. Retornando default: %.1f",
                target_path,
                default_offset,
            )
            return float(default_offset)
    except Exception as exc:
        logger.warning(
            "Error al leer archivo de calibración '%s': %s. Retornando default: %.1f",
            target_path,
            exc,
            default_offset,
        )
        return float(default_offset)


def save_calibration_offset(
    offset: float,
    filepath: Optional[Path] = None,
) -> None:
    """
    Persiste el offset de calibración de edad biológica en formato JSON estructurado.

    Garantiza la creación recursiva de directorios padre y escritura atómica
    para evitar archivos corruptos en caso de apagado repentino o concurrencia.

    Args:
        offset: Valor numérico del offset de calibración en años.
        filepath: Ruta opcional personalizada donde persistir el archivo JSON.

    Raises:
        TypeError / ValueError: Si offset no es convertible a float.
        OSError: Si existen restricciones de permisos en el sistema de archivos.
    """
    numeric_offset = float(offset)
    target_path = filepath if filepath is not None else DEFAULT_CALIBRATION_FILE

    # Asegurar que el directorio padre existe
    target_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "age_offset": numeric_offset,
        "offset": numeric_offset,
        "updated_at": datetime.now().isoformat(),
        "version": "1.0",
        "description": "Offset de calibración de edad para cámara clínica (Proyecto Derma)",
    }

    # Escritura atómica vía archivo temporal
    temp_path = target_path.with_name(f"{target_path.name}.tmp.{datetime.now().timestamp()}")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        temp_path.replace(target_path)
        logger.info(
            "Offset de calibración (%.1f años) guardado exitosamente en '%s'.",
            numeric_offset,
            target_path,
        )
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
