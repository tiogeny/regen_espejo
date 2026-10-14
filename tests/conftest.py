import os
import tempfile
from pathlib import Path
from multiprocessing import shared_memory
import numpy as np
import pytest
from starlette.testclient import TestClient

from src.config import BASE_DIR, DEV_TOKEN
from src.db.database import init_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(tmp_path_factory):
    # Crear directorio temporal para BD de tests
    tmp_dir = tmp_path_factory.mktemp("derma_test_env")
    test_db = tmp_dir / "test_derma.db"
    test_token_file = tmp_dir / "derma_device.token"
    test_token_file.write_text("test_secret_token_12345", encoding="utf-8")

    os.environ["DERMA_DB_PATH"] = str(test_db)
    os.environ["DERMA_TOKEN_PATH"] = str(test_token_file)
    os.environ["DERMA_DEVICE_TOKEN"] = "test_secret_token_12345"

    # Inicializar base de datos con esquema y semillas
    schema_path = BASE_DIR / "src" / "db" / "schema.sql"
    seeds_path = BASE_DIR / "data" / "seeds.sql"
    init_db(db_path=str(test_db), schema_path=schema_path, seeds_path=seeds_path)

    yield {
        "db_path": str(test_db),
        "token_path": str(test_token_file),
        "valid_token": "test_secret_token_12345",
        "tmp_dir": tmp_dir,
    }


@pytest.fixture
def client():
    from src.api.app import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(setup_test_environment):
    import uuid
    return {
        "Authorization": f"Bearer {setup_test_environment['valid_token']}",
        "X-Correlation-ID": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


@pytest.fixture
def create_shm_buffer():
    created_shms = []

    def _create(shape=(224, 224, 3), dtype="uint8", fill_value=128):
        total_bytes = int(np.prod(shape)) * np.dtype(dtype).itemsize
        shm = shared_memory.SharedMemory(create=True, size=total_bytes)
        arr = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
        arr.fill(fill_value)
        created_shms.append(shm)
        return shm.name, shm

    yield _create

    for shm in created_shms:
        try:
            shm.close()
            shm.unlink()
        except Exception:
            pass

import json
from datetime import date, timedelta
from src.db.database import get_db
from src.domain.recommendations import Questionnaire, rule_fingerprint

@pytest.fixture
def questionnaire():
    return Questionnaire(age=30, sensitive_skin=False, salicylate_allergy=False,
        is_pregnant=False, is_lactating=False, known_allergies=[], has_open_wounds=False,
        has_cystic_acne=False, current_treatments=[], concerning_changes=False)


@pytest.fixture
def reviewed_catalog(tmp_path, monkeypatch):
    with get_db() as conn:
        rules = [dict(rule_id=i, fingerprint=rule_fingerprint(conn, i), status="approved",
            reviewed_by="Revisor ficticio de prueba", reviewed_on=str(date.today()),
            valid_until=str(date.today()+timedelta(days=1)), sources=["Referencia de prueba"],
            explanation="Texto de prueba", precautions="Precaución de prueba") for i in (1, 2, 3, 107)]
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps(dict(version="test", rules=rules)))
    monkeypatch.setenv('DERMA_KNOWLEDGE_PATH', str(path))
    return path
