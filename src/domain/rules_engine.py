"""
Motor de Reglas Clínicas y de Negocio para Proyecto_derma.

Integra:
1. El motor de prescripciones fitoterapéuticas estratificadas por edad
   (Piel Joven, Adulta y Madura) y verificación de contraindicaciones médicas.
2. El repositorio transaccional SQLite 3NF, asegurando determinismo clínico,
   cero persistencia de biometría y compatibilidad hacia atrás total con la API.
"""

from __future__ import annotations
import sqlite3
from typing import Dict, Any, List, Optional, Tuple

from src.domain.age_stratified_rules import (
    AgeGroup,
    classify_age_group,
    PatientProfile,
    BotanicalCompound,
    ContraindicationIssue,
    PrescriptionResult,
    AgeStratifiedRulesEngine,
    get_clinical_engine,
    BOTANICAL_CATALOG,
)
from src.db.repository import (
    get_severity_by_spot_pct,
    query_botanical_prescriptions,
    generate_deterministic_session_id,
    save_diagnostic_session,
)


class RulesEngine:
    """
    Motor unificado de reglas clínicas y farmacológicas.
    Permite evaluar diagnósticos de forma desacoplada en memoria (pure domain)
    o integrada con el catálogo normalizado SQLite 3NF.
    """

    def __init__(self, age_engine: Optional[AgeStratifiedRulesEngine] = None):
        self.age_engine = age_engine or get_clinical_engine()

    def evaluate_profile(self, profile: PatientProfile) -> PrescriptionResult:
        """
        Evalúa un perfil clínico dermatológico en memoria utilizando
        estratificación etaria y reglas de seguridad farmacológica.
        """
        return self.age_engine.evaluate(profile)

    def evaluate_clinical_case(
        self,
        age: int,
        sensitive_skin: bool = False,
        is_pregnant: bool = False,
        salicylate_allergy: bool = False,
        is_lactating: bool = False,
        known_allergies: Optional[List[str]] = None,
        has_open_wounds: bool = False,
        has_cystic_acne: bool = False,
        fitzpatrick_phototype: Optional[int] = None,
        hyperpigmentation_pct: Optional[float] = None,
        **kwargs,
    ) -> PrescriptionResult:
        """
        Método de conveniencia para evaluar rápidamente un caso clínico
        sin instanciar manualmente el PatientProfile.
        """
        profile = PatientProfile(
            age=age,
            sensitive_skin=sensitive_skin,
            is_pregnant=is_pregnant,
            salicylate_allergy=salicylate_allergy,
            is_lactating=is_lactating,
            known_allergies=known_allergies or [],
            has_open_wounds=has_open_wounds,
            has_cystic_acne=has_cystic_acne,
            fitzpatrick_phototype=fitzpatrick_phototype,
            hyperpigmentation_pct=hyperpigmentation_pct,
            **kwargs,
        )
        return self.evaluate_profile(profile)

    def filter_db_prescriptions_by_safety(
        self,
        prescriptions: List[Dict[str, Any]],
        profile: PatientProfile,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filtra las prescripciones obtenidas de la base de datos aplicando
        las reglas de contraindicaciones clínicas y farmacológicas del paciente.

        Returns:
            Tuple con (prescripciones_aprobadas, prescripciones_contraindicadas).
        """
        safe_prescriptions: List[Dict[str, Any]] = []
        contraindicated: List[Dict[str, Any]] = []

        for p in prescriptions:
            species_name = p.get("especie")
            compound = BOTANICAL_CATALOG.get(species_name)

            if compound is not None:
                issues = self.age_engine.check_contraindications(compound, profile)
                if issues:
                    item_with_issues = dict(p)
                    item_with_issues["contraindicaciones"] = [i.to_dict() for i in issues]
                    contraindicated.append(item_with_issues)
                else:
                    safe_prescriptions.append(p)
            else:
                item_with_issues = dict(p)
                item_with_issues["contraindicaciones"] = [{
                    "category": "UNKNOWN_COMPOUND",
                    "reason": "Especie sin reglas de seguridad disponibles; requiere revisión profesional.",
                }]
                contraindicated.append(item_with_issues)

        return safe_prescriptions, contraindicated

    def evaluate_with_db(
        self,
        conn: sqlite3.Connection,
        profile: PatientProfile,
        condition_code: str = "HIPERPIGMENTACION",
    ) -> Dict[str, Any]:
        """
        Orquesta el análisis integrando:
        1. Consulta de umbrales y severidad en SQLite.
        2. Extracción de reglas de catálogo 3NF.
        3. Enriquecimiento y filtro con reglas farmacológicas de contraindicación.
        4. Triaje etario fitoterapéutico.
        """
        spot_pct = profile.hyperpigmentation_pct or 0.0
        severity_info = get_severity_by_spot_pct(conn, spot_pct)
        severity_id = severity_info["severidad_id"]
        severity_code = severity_info["codigo"]

        # Consulta SQL a las reglas base
        db_rules = query_botanical_prescriptions(
            conn=conn,
            age=profile.age,
            severity_id=severity_id,
            condition_code=condition_code,
        )

        # Filtro de seguridad clínica
        safe_prescriptions, contraindicated = self.filter_db_prescriptions_by_safety(
            prescriptions=db_rules,
            profile=profile,
        )

        # Evaluación complementaria del estrato etario en memoria
        age_eval = self.evaluate_profile(profile)

        return {
            "clinica": {
                "edad_biologica": profile.age,
                "estrato_etario": age_eval.age_group.value,
                "indicacion_primaria": age_eval.primary_indication,
                "porcentaje_hiperpigmentacion": spot_pct,
                "severidad": severity_code,
            },
            "prescripciones_db_aprobadas": safe_prescriptions,
            "prescripciones_db_contraindicadas": contraindicated,
            "activos_estratificados_recomendados": [
                c.to_dict() for c in age_eval.approved_prescriptions
            ],
            "advertencias_clinicas": age_eval.clinical_warnings,
        }


# Alias para diseño orientado a DDD
ClinicalRulesEngine = RulesEngine
