import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
def get_db_path() -> str:
    return os.getenv("DERMA_DB_PATH", str(DATA_DIR / "derma.db"))


def get_token_path() -> str:
    return os.getenv("DERMA_TOKEN_PATH", "/run/lock/derma_device.token")


DB_PATH = get_db_path()
TOKEN_PATH = get_token_path()
DEV_TOKEN = os.getenv("DERMA_DEV_TOKEN", "test_device_secret_token_2026")

# Límites y SLAs de Hardware
MAX_THERMAL_SOC_CELSIUS = 75.0
MIN_STABILITY_DURATION_MS = 1500
EXPECTED_BUFFER_SHAPE = (224, 224, 3)
EXPECTED_BUFFER_DTYPE = "uint8"
EXPECTED_BUFFER_SIZE_BYTES = 224 * 224 * 3

# UUID Namespace para determinismo clínico (UUID v5)
DERMA_UUID_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"

# Calibración clínica y corrección de sesgo óptico/cámara (0.0 por defecto: modelo Bounded calibrado)
def get_age_offset() -> float:
    return float(os.getenv("DERMA_AGE_OFFSET", "0.0"))

AGE_CALIBRATION_OFFSET = get_age_offset()
