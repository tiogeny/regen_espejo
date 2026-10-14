import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from src.config import get_db_path, BASE_DIR

SCHEMA_PATH = BASE_DIR / "src" / "db" / "schema.sql"
SEEDS_PATH = BASE_DIR / "data" / "seeds.sql"


def is_db_initialized(conn: sqlite3.Connection) -> bool:
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='severidad_niveles';")
        return cursor.fetchone() is not None
    except Exception:
        return False


def ensure_db_initialized(
    conn: sqlite3.Connection,
    schema_path: Path = SCHEMA_PATH,
    seeds_path: Path = SEEDS_PATH,
) -> None:
    if not is_db_initialized(conn):
        with conn:
            if schema_path.exists():
                conn.executescript(schema_path.read_text(encoding="utf-8"))
            if seeds_path.exists():
                conn.executescript(seeds_path.read_text(encoding="utf-8"))


def get_connection(db_path: str = None, auto_init: bool = True) -> sqlite3.Connection:
    target_path = db_path or get_db_path()
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    if auto_init:
        ensure_db_initialized(conn)
    return conn


def init_db(
    db_path: str = None,
    schema_path: Path = SCHEMA_PATH,
    seeds_path: Path = SEEDS_PATH,
) -> None:
    target_path = db_path or get_db_path()
    conn = get_connection(target_path, auto_init=False)
    try:
        with conn:
            if schema_path.exists():
                conn.executescript(schema_path.read_text(encoding="utf-8"))
            if seeds_path.exists():
                conn.executescript(seeds_path.read_text(encoding="utf-8"))
    finally:
        conn.close()


@contextmanager
def get_db(db_path: str = None) -> Generator[sqlite3.Connection, None, None]:
    target_path = db_path or get_db_path()
    conn = get_connection(target_path, auto_init=True)
    try:
        yield conn
    finally:
        conn.close()
