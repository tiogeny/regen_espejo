import uuid
import sqlite3
from typing import List, Dict, Any, Optional
from src.config import DERMA_UUID_NAMESPACE


def generate_deterministic_session_id(
    age: int,
    spot_pct: float,
    seed: Optional[str] = None
) -> str:
    namespace = uuid.UUID(DERMA_UUID_NAMESPACE)
    name = f"derma:{age}:{round(spot_pct, 2)}:{seed or 'std_seed'}"
    return str(uuid.uuid5(namespace, name))


def get_severity_by_spot_pct(
    conn: sqlite3.Connection,
    spot_pct: float
) -> Dict[str, Any]:
    # Primero verificar el nivel ALTA (intervalo cerrado hasta 100.0)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT severidad_id, codigo, umbral_min_pct, umbral_max_pct
        FROM severidad_niveles
        WHERE codigo = 'ALTA' AND ? >= umbral_min_pct AND ? <= umbral_max_pct
        """,
        (spot_pct, spot_pct)
    )
    row = cursor.fetchone()
    if row:
        return dict(row)

    # Para los demás niveles: [umbral_min_pct, umbral_max_pct)
    cursor.execute(
        """
        SELECT severidad_id, codigo, umbral_min_pct, umbral_max_pct
        FROM severidad_niveles
        WHERE ? >= umbral_min_pct AND ? < umbral_max_pct
        ORDER BY umbral_min_pct ASC
        LIMIT 1
        """,
        (spot_pct, spot_pct)
    )
    row = cursor.fetchone()
    if row:
        return dict(row)

    # Fallback si spot_pct < 0.0 o fuera de rango
    cursor.execute(
        """
        SELECT severidad_id, codigo, umbral_min_pct, umbral_max_pct
        FROM severidad_niveles
        ORDER BY umbral_min_pct ASC
        LIMIT 1
        """
    )
    return dict(cursor.fetchone())


def query_botanical_prescriptions(
    conn: sqlite3.Connection,
    age: int,
    severity_id: int,
    condition_code: str = "HIPERPIGMENTACION"
) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            rb.regla_id,
            co.codigo AS condicion_objetivo,
            eb.nombre_cientifico AS especie,
            eb.nombre_comun,
            eb.precauciones
        FROM reglas_botanicas rb
        JOIN condiciones_objetivo co ON rb.condicion_id = co.condicion_id
        JOIN especies_botanicas eb ON rb.especie_id = eb.especie_id
        WHERE ? >= rb.edad_min AND ? <= rb.edad_max
          AND rb.severidad_id = ?
          AND co.codigo = ?
        ORDER BY eb.especie_id ASC
        """,
        (age, age, severity_id, condition_code)
    )
    return [dict(row) for row in cursor.fetchall()]


def save_diagnostic_session(
    conn: sqlite3.Connection,
    session_id: str,
    severity_id: int,
    age: int,
    spot_pct: float,
    processing_time_ms: float,
    rule_ids: List[int]
) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO sesiones_diagnostico (
                sesion_id, severidad_id, edad_estimada, porcentaje_manchas, tiempo_procesamiento_ms
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, severity_id, age, spot_pct, processing_time_ms)
        )
        for r_id in rule_ids:
            conn.execute(
                """
                INSERT INTO sesion_prescripciones (sesion_id, regla_id)
                VALUES (?, ?)
                """,
                (session_id, r_id)
            )
