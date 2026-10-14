"""Recomendaciones locales deterministas. No realiza llamadas de red."""
import hashlib
import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from src.domain.age_stratified_rules import PatientProfile
from src.domain.rules_engine import RulesEngine
from src.db.repository import get_severity_by_spot_pct, query_botanical_prescriptions


class Questionnaire(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age: int | None = Field(default=None, ge=0, le=120, strict=True)
    sensitive_skin: StrictBool | None = None
    salicylate_allergy: StrictBool | None = None
    is_pregnant: StrictBool | None = None
    is_lactating: StrictBool | None = None
    known_allergies: list[str] | None = Field(default=None, max_length=30)
    has_open_wounds: StrictBool | None = None
    has_cystic_acne: StrictBool | None = None
    current_treatments: list[str] | None = Field(default=None, max_length=30)
    concerning_changes: StrictBool | None = None


class ReviewedRule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    rule_id: int
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["draft", "approved"] = "draft"
    reviewed_by: str = Field(min_length=1)
    reviewed_on: date
    valid_until: date
    sources: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1, max_length=1000)
    precautions: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_approval(self):
        if self.status == "approved":
            texts = [self.reviewed_by, self.explanation, self.precautions, *self.sources]
            if any(not text.strip() or text.strip().upper() == "PENDIENTE" for text in texts):
                raise ValueError("Una aprobación debe incluir revisión, fuentes y textos completos")
            if self.valid_until < self.reviewed_on:
                raise ValueError("Vigencia anterior a la revisión")
        return self


class KnowledgeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=1)
    rules: list[ReviewedRule]


def rule_fingerprint(conn, rule_id):
    """Invalida la revisión si cambian criterios, especies o filtros de seguridad."""
    row = conn.execute("""SELECT rb.*, eb.nombre_cientifico, eb.precauciones,
        s.codigo, s.umbral_min_pct, s.umbral_max_pct, c.codigo AS condicion
        FROM reglas_botanicas rb JOIN especies_botanicas eb USING(especie_id)
        JOIN severidad_niveles s USING(severidad_id)
        JOIN condiciones_objetivo c USING(condicion_id) WHERE regla_id=?""", (rule_id,)).fetchone()
    if row is None:
        raise ValueError("Regla inexistente")
    data = json.dumps(dict(row), sort_keys=True, ensure_ascii=False).encode()
    for name in ("age_stratified_rules.py", "rules_engine.py", "recommendations.py"):
        data += Path(__file__).with_name(name).read_bytes()
    return hashlib.sha256(data).hexdigest()


def load_knowledge():
    path = Path(os.environ.get("DERMA_KNOWLEDGE_PATH", str(Path(__file__).resolve().parents[2] / "data/recommendations.json")))
    return KnowledgeBase.model_validate_json(path.read_text(encoding="utf-8"))


def recommend(conn, spot_pct, questionnaire=None):
    result = dict(estado="DATOS_INCOMPLETOS", mensajes=[], datos_faltantes=[],
                  prescripciones=[], exclusiones=[], version_catalogo="no_disponible")
    if not isinstance(spot_pct, (float, int)) or not math.isfinite(spot_pct) or not 0 <= spot_pct <= 100:
        result.update(estado="LECTURA_INVALIDA", mensajes=["Repite la captura: la medición no es válida."])
        return result
    q = questionnaire or Questionnaire()
    missing = [name for name in Questionnaire.model_fields if getattr(q, name) is None]
    result["datos_faltantes"] = missing
    if missing:
        result["mensajes"] = ["Completa el cuestionario para evaluar recomendaciones. Los datos no respondidos no se consideran negativos."]
        return result
    if any(not item.strip() for item in q.known_allergies + q.current_treatments):
        result["mensajes"] = ["Corrige las alergias o tratamientos vacíos; usa una lista vacía si no hay ninguno."]
        return result
    # Casos que el catálogo inicial no cubre: no improvisar tratamientos ni sustitutos.
    if q.age < 18 or q.concerning_changes or q.has_open_wounds or q.has_cystic_acne or q.is_pregnant or q.is_lactating or q.current_treatments or q.known_allergies:
        result.update(estado="REVISION_PROFESIONAL", mensajes=["El perfil requiere evaluación profesional antes de seleccionar activos: el catálogo local no cubre este contexto."])
        return result
    profile = PatientProfile(**q.model_dump(exclude={"current_treatments", "concerning_changes"}), hyperpigmentation_pct=spot_pct)
    severity = get_severity_by_spot_pct(conn, spot_pct)
    rows = query_botanical_prescriptions(conn, profile.age, severity["severidad_id"])
    safe, excluded = RulesEngine().filter_db_prescriptions_by_safety(rows, profile)
    result["exclusiones"] = [{"regla_id": r["regla_id"], "motivo": "Reglas de seguridad incompatibles o no disponibles."} for r in excluded]
    try:
        knowledge = load_knowledge()
        ids = [r.rule_id for r in knowledge.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Reglas duplicadas")
    except (OSError, ValueError):
        result.update(estado="CATALOGO_NO_DISPONIBLE", mensajes=["El catálogo local no está disponible o no es válido. Solicita su revisión."])
        return result
    result["version_catalogo"] = knowledge.version
    reviews = {r.rule_id: r for r in knowledge.rules}
    for row in safe:
        review = reviews.get(row["regla_id"])
        if not (review and review.status == "approved" and review.reviewed_on <= date.today() <= review.valid_until
                and all(source.strip() for source in review.sources)
                and review.fingerprint == rule_fingerprint(conn, row["regla_id"])):
            result["exclusiones"].append({"regla_id": row["regla_id"], "motivo": "Regla pendiente de revisión clínica vigente."})
            continue
        result["prescripciones"].append({**row, "precauciones": review.precautions,
            "explicacion": review.explanation, "fuentes": review.sources})
    if result["prescripciones"]:
        result.update(estado="RECOMENDACIONES_DISPONIBLES", mensajes=["Orientación del catálogo local para revisión del profesional. No constituye un diagnóstico."])
    else:
        result.update(estado="SIN_RECOMENDACION_VALIDADA", mensajes=["No hay recomendaciones revisadas y compatibles para este caso. Solicita evaluación profesional."])
    return result


def localized_orientation():
    """Las reglas de rostro completo no están validadas para porcentajes de una zona."""
    return dict(estado="REVISION_ZONA", mensajes=[
        "Medición de la zona señalada para revisión profesional. El catálogo actual no contiene recomendaciones validadas para áreas localizadas."],
        datos_faltantes=[], prescripciones=[], exclusiones=[], version_catalogo="no_aplicable_zona")
