"""
Pruebas unitarias para el subsistema de persistencia de calibración (calibration_store.py).
Valida:
1. Carga por defecto (+2.5 años) ante ausencia de fichero o datos corruptos.
2. Guardado atómico y creación de directorios automáticos en data/config/.
3. Recuperación exacta de offsets positivos, negativos y neutros.
4. Resiliencia y fallback seguro ante archivos malformados o no numéricos.
"""

import json
from pathlib import Path
import pytest

from src.utils.calibration_store import (
    load_calibration_offset,
    save_calibration_offset,
    DEFAULT_CALIBRATION_FILE,
    DEFAULT_OFFSET,
)


class TestCalibrationStore:
    """Suite de pruebas unitarias para la persistencia del offset de calibración de edad."""

    def test_default_offset_is_two_point_five(self):
        """Verifica que la constante por defecto según especificación clínica sea +2.5."""
        assert DEFAULT_OFFSET == 2.5

    def test_load_default_when_file_not_exists(self, tmp_path):
        """Si el archivo no existe, debe retornar el valor por defecto de +2.5."""
        non_existent = tmp_path / "subdir" / "inexistente.json"
        offset = load_calibration_offset(filepath=non_existent)
        assert offset == 2.5
        assert isinstance(offset, float)

    def test_load_custom_default_when_file_not_exists(self, tmp_path):
        """Si se especifica un default_offset personalizado y no hay archivo, lo retorna."""
        non_existent = tmp_path / "inexistente.json"
        offset = load_calibration_offset(default_offset=4.2, filepath=non_existent)
        assert offset == 4.2

    def test_save_and_load_roundtrip_positive(self, tmp_path):
        """Verifica el ciclo completo de guardado y carga de un offset positivo."""
        cfg_file = tmp_path / "config" / "calibracion_camara.json"
        save_calibration_offset(offset=2.5, filepath=cfg_file)

        assert cfg_file.exists()
        loaded = load_calibration_offset(filepath=cfg_file)
        assert loaded == 2.5
        assert isinstance(loaded, float)

    def test_save_and_load_roundtrip_negative(self, tmp_path):
        """Verifica el guardado y carga de un offset negativo."""
        cfg_file = tmp_path / "calibracion.json"
        save_calibration_offset(offset=-3.0, filepath=cfg_file)

        loaded = load_calibration_offset(filepath=cfg_file)
        assert loaded == -3.0

    def test_save_and_load_roundtrip_zero(self, tmp_path):
        """Verifica el guardado y carga de offset cero (sin corrección)."""
        cfg_file = tmp_path / "calibracion.json"
        save_calibration_offset(offset=0.0, filepath=cfg_file)

        loaded = load_calibration_offset(filepath=cfg_file)
        assert loaded == 0.0

    def test_save_creates_parent_directories_automatically(self, tmp_path):
        """Verifica que si la ruta padre no existe (ej. nested/dirs), se cree automáticamente."""
        deep_file = tmp_path / "deep" / "nested" / "dir" / "calibracion_camara.json"
        assert not deep_file.parent.exists()

        save_calibration_offset(offset=1.5, filepath=deep_file)
        assert deep_file.exists()
        assert deep_file.is_file()

    def test_save_persists_valid_json_with_metadata(self, tmp_path):
        """Verifica que el archivo generado sea JSON válido y contenga metadatos auditables."""
        cfg_file = tmp_path / "calibracion.json"
        save_calibration_offset(offset=2.5, filepath=cfg_file)

        with open(cfg_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "age_offset" in data
        assert data["age_offset"] == 2.5
        assert "offset" in data
        assert data["offset"] == 2.5
        assert "updated_at" in data
        assert "description" in data
        assert "version" in data

    def test_save_overwrites_existing_file(self, tmp_path):
        """Verifica que guardar múltiples veces actualice el valor correctamente."""
        cfg_file = tmp_path / "calibracion.json"
        save_calibration_offset(offset=1.0, filepath=cfg_file)
        assert load_calibration_offset(filepath=cfg_file) == 1.0

        save_calibration_offset(offset=3.8, filepath=cfg_file)
        assert load_calibration_offset(filepath=cfg_file) == 3.8

    def test_load_corrupted_json_returns_default(self, tmp_path):
        """Si el JSON está corrupto (sintaxis rota), retorna de forma segura default_offset."""
        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("{esta_no_es: sintaxis_valida_json", encoding="utf-8")

        offset = load_calibration_offset(default_offset=2.5, filepath=corrupt_file)
        assert offset == 2.5

    def test_load_empty_file_returns_default(self, tmp_path):
        """Si el archivo está vacío (0 bytes), retorna default_offset."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("", encoding="utf-8")

        offset = load_calibration_offset(default_offset=2.5, filepath=empty_file)
        assert offset == 2.5

    def test_load_json_missing_keys_returns_default(self, tmp_path):
        """Si el JSON no contiene ninguna clave esperada, retorna default_offset."""
        missing_keys_file = tmp_path / "missing.json"
        missing_keys_file.write_text(json.dumps({"otra_propiedad": 42}), encoding="utf-8")

        offset = load_calibration_offset(default_offset=2.5, filepath=missing_keys_file)
        assert offset == 2.5

    def test_load_json_with_offset_alias(self, tmp_path):
        """Verifica compatibilidad si el archivo solo contiene 'offset'."""
        alias_file = tmp_path / "alias.json"
        alias_file.write_text(json.dumps({"offset": 1.75}), encoding="utf-8")

        assert load_calibration_offset(filepath=alias_file) == 1.75

    def test_load_json_with_calibracion_offset_alias(self, tmp_path):
        """Verifica compatibilidad con 'calibracion_offset'."""
        alias_file = tmp_path / "cal_alias.json"
        alias_file.write_text(json.dumps({"calibracion_offset": -1.2}), encoding="utf-8")

        assert load_calibration_offset(filepath=alias_file) == -1.2

    def test_load_json_with_non_numeric_value_returns_default(self, tmp_path):
        """Si la clave contiene un valor no numérico, retorna default_offset."""
        invalid_type_file = tmp_path / "type_err.json"
        invalid_type_file.write_text(json.dumps({"age_offset": "no_es_un_numero"}), encoding="utf-8")

        offset = load_calibration_offset(default_offset=2.5, filepath=invalid_type_file)
        assert offset == 2.5

    def test_save_invalid_type_raises_error(self, tmp_path):
        """Pasar un tipo no numérico a save_calibration_offset debe lanzar ValueError o TypeError."""
        cfg_file = tmp_path / "test.json"
        with pytest.raises((ValueError, TypeError)):
            save_calibration_offset(offset="invalido", filepath=cfg_file)  # type: ignore
